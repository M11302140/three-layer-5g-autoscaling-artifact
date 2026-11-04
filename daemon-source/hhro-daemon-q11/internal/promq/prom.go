// Package promq is a tiny Prometheus query client — just /api/v1/query, the
// only thing the daemon needs.
package promq

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

type Prom struct {
	base string
	hc   *http.Client
}

func New(base string) *Prom {
	return &Prom{base: base, hc: &http.Client{Timeout: 10 * time.Second}}
}

type Sample struct {
	Metric map[string]string
	V      float64
}

type promResp struct {
	Status string `json:"status"`
	Error  string `json:"error,omitempty"`
	Data   struct {
		ResultType string `json:"resultType"`
		Result     []struct {
			Metric map[string]string `json:"metric"`
			Value  [2]any            `json:"value"`
		} `json:"result"`
	} `json:"data"`
}

func (p *Prom) QueryScalar(ctx context.Context, q string) (float64, error) {
	v, err := p.Query(ctx, q)
	if err != nil {
		return 0, err
	}
	if len(v) == 0 {
		return 0, nil
	}
	return v[0].V, nil
}

func (p *Prom) Query(ctx context.Context, q string) ([]Sample, error) {
	u := fmt.Sprintf("%s/api/v1/query?query=%s", p.base, url.QueryEscape(q))
	req, _ := http.NewRequestWithContext(ctx, "GET", u, nil)
	resp, err := p.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("prom http %d: %s", resp.StatusCode, string(body))
	}
	var r promResp
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, err
	}
	if r.Status != "success" {
		return nil, fmt.Errorf("prom: %s", r.Error)
	}
	out := make([]Sample, 0, len(r.Data.Result))
	for _, s := range r.Data.Result {
		var f float64
		switch x := s.Value[1].(type) {
		case string:
			f, _ = strconv.ParseFloat(x, 64)
		case float64:
			f = x
		}
		out = append(out, Sample{Metric: s.Metric, V: f})
	}
	return out, nil
}
