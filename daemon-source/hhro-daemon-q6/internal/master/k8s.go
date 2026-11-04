package master

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Generic raw-object CRUD on top of inClusterDo, plus a couple of typed
// conveniences used by the UPF actuator + Rebalancer.

func (m *MasterCluster) k8sDo(ctx context.Context, method, path string, body []byte, contentType string) ([]byte, error) {
	url := "https://kubernetes.default.svc" + path
	req, err := http.NewRequestWithContext(ctx, method, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+m.token)
	if body != nil {
		if contentType == "" {
			contentType = "application/json"
		}
		req.Header.Set("Content-Type", contentType)
	}
	resp, err := m.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return b, fmt.Errorf("%s %s: %d: %s", method, path, resp.StatusCode, string(b))
	}
	return b, nil
}

func (m *MasterCluster) K8sGet(ctx context.Context, path string) ([]byte, error) {
	return m.k8sDo(ctx, "GET", path, nil, "")
}

func (m *MasterCluster) K8sCreate(ctx context.Context, path string, body []byte) error {
	_, err := m.k8sDo(ctx, "POST", path, body, "")
	return err
}

func (m *MasterCluster) K8sDelete(ctx context.Context, path string) error {
	_, err := m.k8sDo(ctx, "DELETE", path, nil, "")
	return err
}

func (m *MasterCluster) K8sMergePatch(ctx context.Context, path string, body []byte) error {
	_, err := m.k8sDo(ctx, "PATCH", path, body, "application/merge-patch+json")
	return err
}

func (m *MasterCluster) GetConfigMapData(ctx context.Context, ns, name, key string) (string, error) {
	p := fmt.Sprintf("/api/v1/namespaces/%s/configmaps/%s", ns, name)
	b, err := m.K8sGet(ctx, p)
	if err != nil {
		return "", err
	}
	var cm struct {
		Data map[string]string `json:"data"`
	}
	if err := json.Unmarshal(b, &cm); err != nil {
		return "", err
	}
	return cm.Data[key], nil
}

func (m *MasterCluster) UpdateConfigMapData(ctx context.Context, ns, name, key, value string) error {
	p := fmt.Sprintf("/api/v1/namespaces/%s/configmaps/%s", ns, name)
	patch, _ := json.Marshal(map[string]any{"data": map[string]string{key: value}})
	return m.K8sMergePatch(ctx, p, patch)
}

func (m *MasterCluster) PatchServiceExternalIPs(ctx context.Context, ns, name string, ips []string) error {
	p := fmt.Sprintf("/api/v1/namespaces/%s/services/%s", ns, name)
	patch, _ := json.Marshal(map[string]any{"spec": map[string]any{"externalIPs": ips}})
	return m.K8sMergePatch(ctx, p, patch)
}

func (m *MasterCluster) RolloutRestart(ctx context.Context, ns, name string) error {
	p := fmt.Sprintf("/apis/apps/v1/namespaces/%s/deployments/%s", ns, name)
	patch, _ := json.Marshal(map[string]any{
		"spec": map[string]any{
			"template": map[string]any{
				"metadata": map[string]any{
					"annotations": map[string]string{
						"kubectl.kubernetes.io/restartedAt": time.Now().UTC().Format(time.RFC3339),
					},
				},
			},
		},
	})
	return m.K8sMergePatch(ctx, p, patch)
}

// StripObjectMetadata removes server-managed metadata + status so the raw JSON
// can be POSTed as a new object. Caller mutates `obj` in place.
func StripObjectMetadata(obj map[string]any) {
	if md, ok := obj["metadata"].(map[string]any); ok {
		for _, k := range []string{"resourceVersion", "uid", "creationTimestamp", "generation", "managedFields", "selfLink", "annotations", "ownerReferences"} {
			delete(md, k)
		}
	}
	delete(obj, "status")
}
