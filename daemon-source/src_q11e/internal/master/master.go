// Package master talks to the local (in-cluster) kube-apiserver. Combines the
// kubeadm bootstrap-token issuer (for new worker join) with all the
// CRUD/patch/restart primitives the UPF actuator + Rebalancer rely on.
package master

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

type MasterCluster struct {
	APIServer  string
	CACertHash string
	hc         *http.Client
	token      string
}

func NewFromEnv() (*MasterCluster, error) {
	api := os.Getenv("K8S_API_SERVER")
	hash := os.Getenv("K8S_CA_CERT_HASH")
	if api == "" || hash == "" {
		return nil, fmt.Errorf("K8S_API_SERVER and K8S_CA_CERT_HASH required for join provider")
	}
	tok, err := os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/token")
	if err != nil {
		return nil, err
	}
	caB, err := os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
	if err != nil {
		return nil, err
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(caB) {
		return nil, fmt.Errorf("ca pem parse failed")
	}
	return &MasterCluster{
		APIServer:  api,
		CACertHash: hash,
		token:      string(bytes.TrimSpace(tok)),
		hc: &http.Client{Timeout: 30 * time.Second, Transport: &http.Transport{
			TLSClientConfig: &tls.Config{RootCAs: pool},
		}},
	}, nil
}

func (m *MasterCluster) inClusterDo(ctx context.Context, method, path string, body []byte) (int, []byte, error) {
	url := "https://kubernetes.default.svc" + path
	req, err := http.NewRequestWithContext(ctx, method, url, bytes.NewReader(body))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Authorization", "Bearer "+m.token)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := m.hc.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, b, nil
}

func (m *MasterCluster) IssueJoinCommand(ctx context.Context) (string, error) {
	id, err := randHex(3)
	if err != nil {
		return "", err
	}
	sec, err := randHex(8)
	if err != nil {
		return "", err
	}
	body, _ := json.Marshal(map[string]any{
		"apiVersion": "v1",
		"kind":       "Secret",
		"type":       "bootstrap.kubernetes.io/token",
		"metadata": map[string]string{
			"name":      "bootstrap-token-" + id,
			"namespace": "kube-system",
		},
		"stringData": map[string]string{
			"token-id":                       id,
			"token-secret":                   sec,
			"usage-bootstrap-authentication": "true",
			"usage-bootstrap-signing":        "true",
			"auth-extra-groups":              "system:bootstrappers:kubeadm:default-node-token",
			"expiration":                     time.Now().Add(30 * time.Minute).UTC().Format(time.RFC3339),
		},
	})
	code, b, err := m.inClusterDo(ctx, "POST", "/api/v1/namespaces/kube-system/secrets", body)
	if err != nil {
		return "", err
	}
	if code >= 400 {
		return "", fmt.Errorf("create token: %d: %s", code, string(b))
	}
	return fmt.Sprintf("kubeadm join %s --token %s.%s --discovery-token-ca-cert-hash %s",
		m.APIServer, id, sec, m.CACertHash), nil
}

func (m *MasterCluster) PatchDeploymentReplicas(ctx context.Context, ns, name string, replicas int) error {
	body := []byte(fmt.Sprintf(`{"spec":{"replicas":%d}}`, replicas))
	path := fmt.Sprintf("/apis/apps/v1/namespaces/%s/deployments/%s", ns, name)
	req, err := http.NewRequestWithContext(ctx, "PATCH",
		"https://kubernetes.default.svc"+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+m.token)
	req.Header.Set("Content-Type", "application/strategic-merge-patch+json")
	resp, err := m.hc.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return fmt.Errorf("patch %s/%s replicas=%d: %d: %s", ns, name, replicas, resp.StatusCode, string(b))
	}
	return nil
}

func (m *MasterCluster) GetDeploymentReplicas(ctx context.Context, ns, name string) (int, error) {
	path := fmt.Sprintf("/apis/apps/v1/namespaces/%s/deployments/%s", ns, name)
	code, body, err := m.inClusterDo(ctx, "GET", path, nil)
	if err != nil {
		return 0, err
	}
	if code >= 400 {
		return 0, fmt.Errorf("get %s/%s: %d: %s", ns, name, code, string(body))
	}
	var d struct {
		Spec struct {
			Replicas int `json:"replicas"`
		} `json:"spec"`
	}
	if err := json.Unmarshal(body, &d); err != nil {
		return 0, err
	}
	return d.Spec.Replicas, nil
}

// DrainAndDeleteNode mirrors `kubectl drain --ignore-daemonsets --force` and
// then removes the Node object. Best-effort.
func (m *MasterCluster) DrainAndDeleteNode(ctx context.Context, name string) error {
	patch := []byte(`{"spec":{"unschedulable":true}}`)
	cordonReq, _ := http.NewRequestWithContext(ctx, "PATCH",
		"https://kubernetes.default.svc/api/v1/nodes/"+name, bytes.NewReader(patch))
	cordonReq.Header.Set("Authorization", "Bearer "+m.token)
	cordonReq.Header.Set("Content-Type", "application/strategic-merge-patch+json")
	if resp, err := m.hc.Do(cordonReq); err == nil {
		resp.Body.Close()
	}

	code, body, err := m.inClusterDo(ctx, "GET",
		"/api/v1/pods?fieldSelector=spec.nodeName="+name, nil)
	if err != nil || code >= 400 {
		return fmt.Errorf("list pods on %s: code=%d err=%v", name, code, err)
	}
	var pods struct {
		Items []struct {
			Metadata struct {
				Name      string `json:"name"`
				Namespace string `json:"namespace"`
				OwnerRefs []struct {
					Kind       string `json:"kind"`
					Controller bool   `json:"controller"`
				} `json:"ownerReferences"`
				Annotations map[string]string `json:"annotations"`
			} `json:"metadata"`
		} `json:"items"`
	}
	if err := json.Unmarshal(body, &pods); err != nil {
		return fmt.Errorf("decode pods: %w", err)
	}
	for _, p := range pods.Items {
		skip := false
		for _, o := range p.Metadata.OwnerRefs {
			if o.Kind == "DaemonSet" {
				skip = true
				break
			}
		}
		if _, ok := p.Metadata.Annotations["kubernetes.io/config.mirror"]; ok {
			skip = true
		}
		if skip {
			continue
		}
		evictBody := []byte(fmt.Sprintf(
			`{"apiVersion":"policy/v1","kind":"Eviction","metadata":{"name":"%s","namespace":"%s"}}`,
			p.Metadata.Name, p.Metadata.Namespace))
		path := fmt.Sprintf("/api/v1/namespaces/%s/pods/%s/eviction",
			p.Metadata.Namespace, p.Metadata.Name)
		m.inClusterDo(ctx, "POST", path, evictBody)
	}

	code, b, err := m.inClusterDo(ctx, "DELETE", "/api/v1/nodes/"+name, nil)
	if err != nil {
		return err
	}
	if code >= 400 && code != 404 {
		return fmt.Errorf("delete node %s: %d: %s", name, code, string(b))
	}
	return nil
}

func randHex(nBytes int) (string, error) {
	b := make([]byte, nBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	const hex = "0123456789abcdef"
	out := make([]byte, nBytes*2)
	for i, x := range b {
		out[i*2] = hex[x>>4]
		out[i*2+1] = hex[x&0x0f]
	}
	return string(out), nil
}
