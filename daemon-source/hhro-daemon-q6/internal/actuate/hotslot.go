package actuate

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

//
//

var vfOobRe = regexp.MustCompile(`^upf_vf_rx_out_of_buffer\{slot="(\d+)"[^}]*\}\s+(\d+)`)

type vfOobSample struct {
	at  time.Time
	cum int64
}

type hotSlotState struct {
	mu       sync.Mutex
	prev     map[int]vfOobSample // slot octet → last cumulative sample
	rate     map[int]float64     // slot octet → last pps
	streak   map[int]int         // consecutive hot samples
	lastMove map[int]time.Time   // cooldown
}

func (e *EupfActuator) hot() *hotSlotState {
	e.hotOnce.Do(func() {
		e.hotSt = &hotSlotState{prev: map[int]vfOobSample{}, rate: map[int]float64{},
			streak: map[int]int{}, lastMove: map[int]time.Time{}}
	})
	return e.hotSt
}

// parseVFOob returns {slot: cumulative rx_out_of_buffer} from an exporter page.
func parseVFOob(txt string) map[int]int64 {
	out := map[int]int64{}
	start := 0
	for i := 0; i <= len(txt); i++ {
		if i == len(txt) || txt[i] == '\n' {
			line := txt[start:i]
			start = i + 1
			m := vfOobRe.FindStringSubmatch(line)
			if m == nil {
				continue
			}
			s, _ := strconv.Atoi(m[1])
			v, _ := strconv.ParseInt(m[2], 10, 64)
			out[s] = v
		}
	}
	return out
}

// ingestVFOob updates per-slot rates/streaks from a new cumulative snapshot.
func (h *hotSlotState) ingestVFOob(now time.Time, cum map[int]int64, thr float64) {
	h.mu.Lock()
	defer h.mu.Unlock()
	seen := map[int]bool{}
	for s, c := range cum {
		seen[s] = true
		p, ok := h.prev[s]
		h.prev[s] = vfOobSample{at: now, cum: c}
		if !ok || c < p.cum || now.Sub(p.at) <= 0 {
			h.rate[s] = 0
			h.streak[s] = 0
			continue
		}
		r := float64(c-p.cum) / now.Sub(p.at).Seconds()
		h.rate[s] = r
		if r >= thr {
			h.streak[s]++
		} else {
			h.streak[s] = 0
		}
	}
	for s := range h.prev { // slot gone (worker deleted / counter absent): forget
		if !seen[s] {
			delete(h.prev, s)
			delete(h.rate, s)
			delete(h.streak, s)
		}
	}
}

// hotSlots lists slot octets whose streak reached ticks and are out of cooldown, hottest first.
func (h *hotSlotState) hotSlots(now time.Time, ticks int, cooldown time.Duration) []int {
	h.mu.Lock()
	defer h.mu.Unlock()
	var out []int
	for s, n := range h.streak {
		if n >= ticks && now.Sub(h.lastMove[s]) >= cooldown {
			out = append(out, s)
		}
	}
	sort.Slice(out, func(i, j int) bool { return h.rate[out[i]] > h.rate[out[j]] })
	return out
}

// SampleVFOob polls every worker's upf-cpu-exporter (:9101) once and folds the
// rx_out_of_buffer counters into the hot-slot state. Unreachable workers are skipped.
func (e *EupfActuator) SampleVFOob(ctx context.Context, maxWorkers int) map[int]float64 {
	h := e.hot()
	hc := &http.Client{Timeout: 3 * time.Second}
	var wg sync.WaitGroup
	var mu sync.Mutex
	cum := map[int]int64{}
	for w := 0; w < maxWorkers; w++ {
		url := fmt.Sprintf("http://%s%d:9101/metrics", e.A.Cfg.MgmtPrefix, workerMgmtOctet(e.A.Cfg.MgmtBase, w))
		wg.Add(1)
		go func(url string) {
			defer wg.Done()
			req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
			if err != nil {
				return
			}
			resp, err := hc.Do(req)
			if err != nil {
				return
			}
			defer resp.Body.Close()
			b, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
			if err != nil {
				return
			}
			part := parseVFOob(string(b))
			mu.Lock()
			for s, v := range part {
				cum[s] = v
			}
			mu.Unlock()
		}(url)
	}
	wg.Wait()
	h.ingestVFOob(time.Now(), cum, envcfg.Float("V6_HOT_SLOT_OOB_PPS", 1500))
	h.mu.Lock()
	defer h.mu.Unlock()
	out := map[int]float64{}
	for s, r := range h.rate {
		out[s] = r
	}
	return out
}

// HotSlotCandidates returns hot slot octets (streak ≥ V6_HOT_SLOT_TICKS, out of cooldown).
func (e *EupfActuator) HotSlotCandidates() []int {
	return e.hot().hotSlots(time.Now(), envcfg.Int("V6_HOT_SLOT_TICKS", 2),
		time.Duration(envcfg.Int("V6_HOT_SLOT_COOLDOWN_S", 120))*time.Second)
}

// planHotRelief picks one movable UE off hotDnn and the coldest receiver with room.
func planHotRelief(ues map[int]ueInfo, dnnSet map[string]bool, hotDnn string, recvMax int) (RehomeMove, map[string]int, bool) {
	cnt := map[string]int{}
	for d := range dnnSet {
		cnt[d] = 0
	}
	var movable []int
	for i, u := range ues {
		if !dnnSet[u.Dnn] {
			continue
		}
		cnt[u.Dnn]++
		if u.Dnn == hotDnn && eligibleForMove(u) {
			movable = append(movable, i)
		}
	}
	if cnt[hotDnn] < 2 || len(movable) == 0 {
		return RehomeMove{}, cnt, false
	}
	var dnns []string
	for d := range cnt {
		if d != hotDnn {
			dnns = append(dnns, d)
		}
	}
	sort.Strings(dnns)
	cold := ""
	for _, d := range dnns {
		if cold == "" || cnt[d] < cnt[cold] {
			cold = d
		}
	}
	if cold == "" || cnt[cold]+1 > recvMax {
		return RehomeMove{}, cnt, false
	}
	sort.Ints(movable)
	return RehomeMove{UE: movable[0], Dnn: cold}, cnt, true // oldest index = longest-settled UE
}

// HotSlotRelief moves one UE off the hot slot (octet) to the coldest slot with room.
func (e *EupfActuator) HotSlotRelief(ctx context.Context, hotOctet, recvMax int) (int, map[string]int, error) {
	if e.Rehome == nil || !e.Rehome.Enabled {
		return 0, nil, nil
	}
	hotDnn := dnnByOctet(hotOctet)
	if hotDnn == "" {
		return 0, nil, fmt.Errorf("unknown slot octet %d", hotOctet)
	}
	idxs, err := e.ActiveSlotIdxs(ctx)
	if err != nil || len(idxs) < 2 {
		return 0, nil, err
	}
	dnnSet := map[string]bool{}
	for i := range idxs {
		if s := e.slotByIdx(i); s != nil {
			if _, busy := e.draining.Load(fmt.Sprintf("eupf-%d", i)); busy {
				continue // draining slot: neither donor nor receiver
			}
			dnnSet[dnnByOctet(s.N3Octet)] = true
		}
	}
	if !dnnSet[hotDnn] {
		return 0, nil, nil
	}
	ues, err := e.Rehome.UEsLive(ctx)
	if err != nil {
		return 0, nil, err
	}
	mv, cnt, ok := planHotRelief(ues, dnnSet, hotDnn, recvMax)
	h := e.hot()
	h.mu.Lock()
	h.lastMove[hotOctet] = time.Now() // cooldown even when nothing is movable (avoid hammering)
	h.streak[hotOctet] = 0
	h.mu.Unlock()
	if !ok {
		return 0, cnt, nil
	}
	return 1, cnt, e.Rehome.Rehome(ctx, []RehomeMove{mv})
}
