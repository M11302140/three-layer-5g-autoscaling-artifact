package hbo


import (
	_ "embed"
	"encoding/json"
	"math"
	"strconv"
	"sync"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

//go:embed prior_r2.json
var embeddedR2Prior []byte

type r2Prior struct {
	PExceed  map[string][][]float64 `json:"p_exceed"`
	ET       [][]float64            `json:"e_t"`
	HLo      int                    `json:"h_lo"`
	HHi      int                    `json:"h_hi"`
	BucketUE float64                `json:"bucket_ue"`
	NBuckets int                    `json:"n_buckets"`
	CapUP    float64                `json:"cap_up"`
	SPW      int                    `json:"spw"`
	CoresUP  float64                `json:"cores_up"`
	CoresWK  float64                `json:"cores_wk"`
	LUP      float64                `json:"l_up"`
	LWK      float64                `json:"l_wk"`
}

var (
	r2Once sync.Once
	r2Tab  *r2Prior
)

func loadR2() *r2Prior {
	r2Once.Do(func() {
		var p r2Prior
		if err := json.Unmarshal(embeddedR2Prior, &p); err != nil {
			panic("prior_r2.json: " + err.Error())
		}
		r2Tab = &p
	})
	return r2Tab
}

func s4pIndepWK() bool { return envcfg.Bool("V6_S4P_INDEP_WK", false) }

// s4pR2W returns (w, enabled).
func s4pR2W() (float64, bool) {
	v := envcfg.Get("V6_S4P_R2_W", "")
	if v == "" {
		return 0, false
	}
	w, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return 0, false
	}
	return w, true
}

func r2OK(D float64, nUP, nWK int, w float64) bool {
	p := loadR2()
	h := float64(nUP-1)*p.CapUP - D
	hi := int(math.Floor(h))
	if hi < p.HLo {
		hi = p.HLo
	}
	if hi > p.HHi {
		hi = p.HHi
	}
	b := int(math.Floor(D / p.BucketUE))
	if b < 0 {
		b = 0
	}
	if b >= p.NBuckets {
		b = p.NBuckets - 1
	}
	bb := (nUP - 1) <= (nWK-1)*p.SPW
	rate, L, k := p.CoresUP, p.LUP, "up"
	if bb {
		rate, L, k = p.CoresUP+p.CoresWK, p.LWK, "wk"
	}
	pe := p.PExceed[k][b][hi-p.HLo]
	et := p.ET[b][hi-p.HLo]
	return rate*et/60.0-w*(pe*L/60.0) > 0
}
