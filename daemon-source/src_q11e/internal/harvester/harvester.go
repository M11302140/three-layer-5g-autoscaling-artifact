// Package harvester is a minimal kube-apiserver REST client targeting
// Harvester's embedded RKE2 cluster. Scope intentionally narrow: only the
// verbs / paths the worker + VyOS VM lifecycle needs.
package harvester

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

type Harvester struct {
	URL       string
	Token     string
	Namespace string
	hc        *http.Client
}

func NewFromEnv() (*Harvester, error) {
	url := os.Getenv("HARVESTER_URL")
	tokenPath := envcfg.Get("HARVESTER_TOKEN_FILE", "/var/run/secrets/harvester/token")
	caPath := envcfg.Get("HARVESTER_CA_FILE", "/var/run/secrets/harvester/ca.crt")
	ns := envcfg.Get("HARVESTER_NAMESPACE", "default")
	if url == "" {
		return nil, fmt.Errorf("HARVESTER_URL is required")
	}
	tokB, err := os.ReadFile(tokenPath)
	if err != nil {
		return nil, fmt.Errorf("read token: %w", err)
	}
	caB, err := os.ReadFile(caPath)
	if err != nil {
		return nil, fmt.Errorf("read ca: %w", err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(caB) {
		return nil, fmt.Errorf("ca pem parse failed")
	}
	return &Harvester{
		URL:       url,
		Token:     string(bytes.TrimSpace(tokB)),
		Namespace: ns,
		hc: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig: &tls.Config{RootCAs: pool},
			},
		},
	}, nil
}

func (h *Harvester) do(ctx context.Context, method, path string, body []byte) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, h.URL+path, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+h.Token)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := h.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return b, fmt.Errorf("harvester %s %s -> %d: %s", method, path, resp.StatusCode, string(b))
	}
	return b, nil
}

type VMSummary struct {
	Name    string
	Phase   string
	Created time.Time
}

func (h *Harvester) ListVMs(ctx context.Context, labelSel string) ([]VMSummary, error) {
	path := fmt.Sprintf("/apis/kubevirt.io/v1/namespaces/%s/virtualmachines", h.Namespace)
	if labelSel != "" {
		path += "?labelSelector=" + labelSel
	}
	b, err := h.do(ctx, "GET", path, nil)
	if err != nil {
		return nil, err
	}
	var out struct {
		Items []struct {
			Metadata struct {
				Name              string    `json:"name"`
				CreationTimestamp time.Time `json:"creationTimestamp"`
			} `json:"metadata"`
			Status struct {
				PrintableStatus string `json:"printableStatus"`
			} `json:"status"`
		} `json:"items"`
	}
	if err := json.Unmarshal(b, &out); err != nil {
		return nil, err
	}
	r := make([]VMSummary, 0, len(out.Items))
	for _, it := range out.Items {
		r = append(r, VMSummary{
			Name:    it.Metadata.Name,
			Phase:   it.Status.PrintableStatus,
			Created: it.Metadata.CreationTimestamp,
		})
	}
	return r, nil
}

// VFResourceName is the extended resource for Mellanox CX-5 SR-IOV VFs.
const VFResourceName = "mellanox.com/MT27800_FAMILY_CONNECTX5_VIRTUAL_FUNCTION"

// Capacity holds free resources on the Harvester host for pre-flight checks.
type Capacity struct {
	FreeMemoryBytes int64 // node allocatable memory minus sum of pod memory requests
	FreeVFs         int64 // mellanox VF resource — allocatable minus requests
}

// CheckCapacity queries Harvester's embedded k8s API for the named node and
// returns free memory and free Mellanox VFs. Sums pod resource.requests across
// all pods scheduled on the node (regardless of phase) to compute what k8s
// would actually allocate — matches scheduler view.
//
// v1.38 — added to gate scale_out: daemon rejects CreateWorker / DeployVyOS
// when the request would exceed available capacity, with a clear log message.
func (h *Harvester) CheckCapacity(ctx context.Context, nodeName string) (*Capacity, error) {
	nodeBody, err := h.do(ctx, "GET", "/api/v1/nodes/"+nodeName, nil)
	if err != nil {
		return nil, fmt.Errorf("get node %s: %w", nodeName, err)
	}
	var node struct {
		Status struct {
			Allocatable map[string]string `json:"allocatable"`
		} `json:"status"`
	}
	if err := json.Unmarshal(nodeBody, &node); err != nil {
		return nil, err
	}
	memAlloc, err := parseQuantity(node.Status.Allocatable["memory"])
	if err != nil {
		return nil, fmt.Errorf("parse memory allocatable: %w", err)
	}
	vfsAlloc, err := parseQuantity(node.Status.Allocatable[VFResourceName])
	if err != nil {
		vfsAlloc = 0
	}

	// Sum pod requests on this node.
	podsBody, err := h.do(ctx, "GET", "/api/v1/pods?fieldSelector=spec.nodeName="+nodeName, nil)
	if err != nil {
		return nil, fmt.Errorf("list pods on %s: %w", nodeName, err)
	}
	var pods struct {
		Items []struct {
			Status struct {
				Phase string `json:"phase"`
			} `json:"status"`
			Spec struct {
				Containers []struct {
					Resources struct {
						Requests map[string]string `json:"requests"`
					} `json:"resources"`
				} `json:"containers"`
			} `json:"spec"`
		} `json:"items"`
	}
	if err := json.Unmarshal(podsBody, &pods); err != nil {
		return nil, err
	}
	var memUsed, vfsUsed int64
	for _, p := range pods.Items {
		// Skip terminated pods (Succeeded/Failed) — they don't hold resources.
		if p.Status.Phase == "Succeeded" || p.Status.Phase == "Failed" {
			continue
		}
		for _, c := range p.Spec.Containers {
			if v, ok := c.Resources.Requests["memory"]; ok {
				if q, err := parseQuantity(v); err == nil {
					memUsed += q
				}
			}
			if v, ok := c.Resources.Requests[VFResourceName]; ok {
				if q, err := parseQuantity(v); err == nil {
					vfsUsed += q
				}
			}
		}
	}
	return &Capacity{
		FreeMemoryBytes: memAlloc - memUsed,
		FreeVFs:         vfsAlloc - vfsUsed,
	}, nil
}

// parseQuantity parses a Kubernetes resource quantity (e.g. "8Gi", "5004576Ki",
// "2", "200m"). Returns the value in raw units (bytes for memory; integers for
// counts; millicores for cpu). Caller must know what unit applies.
func parseQuantity(s string) (int64, error) {
	if s == "" {
		return 0, nil
	}
	// Strip suffix
	suffix := ""
	num := s
	for i := len(s) - 1; i >= 0; i-- {
		c := s[i]
		if c >= '0' && c <= '9' {
			suffix = s[i+1:]
			num = s[:i+1]
			break
		}
	}
	var base int64
	for _, c := range num {
		if c < '0' || c > '9' {
			return 0, fmt.Errorf("bad quantity %q", s)
		}
		base = base*10 + int64(c-'0')
	}
	mul := int64(1)
	switch suffix {
	case "", "m":
		// "m" = millis (cpu millicores); for memory it'd be unusual. Treat as base.
		if suffix == "m" {
			// for cpu we want base; for memory caller won't pass "m". Keep mul=1.
		}
	case "Ki":
		mul = 1024
	case "Mi":
		mul = 1024 * 1024
	case "Gi":
		mul = 1024 * 1024 * 1024
	case "Ti":
		mul = 1024 * 1024 * 1024 * 1024
	case "K", "k":
		mul = 1000
	case "M":
		mul = 1000 * 1000
	case "G":
		mul = 1000 * 1000 * 1000
	default:
		return 0, fmt.Errorf("unknown quantity suffix %q in %q", suffix, s)
	}
	return base * mul, nil
}

func (h *Harvester) CreateSecret(ctx context.Context, body []byte) error {
	_, err := h.do(ctx, "POST", fmt.Sprintf("/api/v1/namespaces/%s/secrets", h.Namespace), body)
	return err
}

func (h *Harvester) DeleteSecret(ctx context.Context, name string) error {
	_, err := h.do(ctx, "DELETE", fmt.Sprintf("/api/v1/namespaces/%s/secrets/%s", h.Namespace, name), nil)
	return err
}

func (h *Harvester) CreateVM(ctx context.Context, body []byte) error {
	_, err := h.do(ctx, "POST", fmt.Sprintf("/apis/kubevirt.io/v1/namespaces/%s/virtualmachines", h.Namespace), body)
	return err
}

func (h *Harvester) DeleteVM(ctx context.Context, name string) error {
	_, err := h.do(ctx, "DELETE", fmt.Sprintf("/apis/kubevirt.io/v1/namespaces/%s/virtualmachines/%s", h.Namespace, name), nil)
	return err
}

func (h *Harvester) DeletePVC(ctx context.Context, name string) error {
	_, err := h.do(ctx, "DELETE", fmt.Sprintf("/api/v1/namespaces/%s/persistentvolumeclaims/%s", h.Namespace, name), nil)
	return err
}
