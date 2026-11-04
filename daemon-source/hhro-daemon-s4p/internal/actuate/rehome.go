package actuate

import (
	"strconv"
	"os"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

// RehomeClient drives the sender-side rehome agent (experiment/rehome_agent.py).
// Story: the core (daemon, acting as SMF) notifies specific UEs to re-register
// onto a new DNN — SMF-initiated PDU session release with reactivation. The
// notification rides the data network first (10.0.1.100:9800) and falls back
// to mgmt (10.0.0.146:9801) when the in-band path is down.
type RehomeClient struct {
	URLs    []string
	Enabled bool
	hc      *http.Client
}

func NewRehomeClient() *RehomeClient {
	raw := envcfg.Get("REHOME_AGENT_URLS",
		"http://10.0.1.100:9800,http://10.0.0.146:9801")
	var urls []string
	for _, u := range strings.Split(raw, ",") {
		if u = strings.TrimSpace(u); u != "" {
			urls = append(urls, u)
		}
	}
	return &RehomeClient{
		URLs:    urls,
		Enabled: envcfg.Get("REHOME_ENABLED", "true") == "true",
		// /rehome is async on the agent (202 + background job) — requests
		// return fast; completion is observed by polling /ues. A long client
		// timeout here caused fallback-URL retries = double-posted jobs.
		hc: &http.Client{Timeout: 30 * time.Second},
	}
}

type RehomeMove struct {
	UE  int    `json:"ue"`
	Dnn string `json:"dnn"`
}

type ueInfo struct {
	Dnn  string `json:"dnn"`
	Upf  string `json:"upf"`
	Vyos string `json:"vyos"`
	// AgeS: seconds since this UE's current anchor first appeared in the agent's
	// view (agent r7, 2026-09-06). Zero when the agent predates the field.
	AgeS float64 `json:"age_s"`
}

// reliefMinAgeS: UEs younger than this are never picked for a relief move.
// r8 min49-50 (2026-09-06): UE-11 arrived and was picked by the scale-out
// relief within seconds; its NAS was still busy (UAC/T3580) so cli_move
// failed and the UE went dark until it departed (1.37%/1.19% minutes). A
// fresh UE has nothing to relieve anyway — arrivals already steer to the
// least-loaded slot. Measured quantity (NAS settle ≈ T3580 16 s + margin).
func reliefMinAgeS() float64 { return envcfg.Float("UP_RELIEF_MIN_AGE_S", 90) }

// eligibleForMove reports whether a UE may be moved by a best-effort relief.
func eligibleForMove(u ueInfo) bool { return u.AgeS <= 0 || u.AgeS >= reliefMinAgeS() }

// UEs returns the agent's current UE→DNN map (GET /ues).
func (r *RehomeClient) UEs(ctx context.Context) (map[int]ueInfo, error) {
	return r.ues(ctx, "/ues")
}

// UEsLive asks the agent to REBUILD its view from ground truth (nr-cli
// ps-list + eupf pfcp_sessions) before answering. Slow (~10-20s) — use at
// scale DECISION points only (drain planning / zombie arbitration /
// rebalance planning). v5.1.5: the cached view goes stale whenever
// UEs as zombies and deleted eupf-6 under 5 live sessions (2026-07-28).
func (r *RehomeClient) UEsLive(ctx context.Context) (map[int]ueInfo, error) {
	return r.ues(ctx, "/ues?live=1")
}

// PendingReleases reports how many rehome jobs still owe an old-anchor release
// (GET /status → pending_releases). The agent defers releases to
// RELEASE_DELAY_S (75 s) AFTER job-done so the harness switches streams first;
// DrainAndDelete used to race that with a fixed timeout and lost (orph3: even
// 210 s missed by 14 s → the slot was deleted first and the release then hit a
// dead peer = `SLOT-LEAK ... PFCP deletion lost`, plus a UE stuck PS-ACTIVE for
// minutes). Waiting on this counter replaces the guess with the fact.
func (r *RehomeClient) PendingReleases(ctx context.Context) (int, error) {
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, base+"/status", nil)
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		var body struct {
			Pending *int `json:"pending_releases"`
		}
		err = json.NewDecoder(resp.Body).Decode(&body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		if body.Pending == nil {
			// older agent build: no counter — treat as "nothing owed" so the
			// caller falls back to its session-emptiness timeout.
			return 0, nil
		}
		return *body.Pending, nil
	}
	return 0, fmt.Errorf("rehome agent unreachable: %w", last)
}

func (r *RehomeClient) ues(ctx context.Context, path string) (map[int]ueInfo, error) {
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, base+path, nil)
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		var body struct {
			UEs map[string]ueInfo `json:"ues"`
		}
		err = json.NewDecoder(resp.Body).Decode(&body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		out := map[int]ueInfo{}
		for k, v := range body.UEs {
			var i int
			if _, err := fmt.Sscanf(k, "%d", &i); err == nil {
				out[i] = v
			}
		}
		return out, nil
	}
	return nil, fmt.Errorf("rehome agent unreachable: %w", last)
}

// Rehome executes the moves (POST /rehome) and returns per-UE failures.
func (r *RehomeClient) Rehome(ctx context.Context, moves []RehomeMove) error {
	if len(moves) == 0 {
		return nil
	}
	payload, _ := json.Marshal(map[string]any{"moves": moves})
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
			base+"/rehome", bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		var body struct {
			Accepted  int  `json:"accepted"`
			Duplicate bool `json:"duplicate"`
		}
		err = json.NewDecoder(resp.Body).Decode(&body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		return nil // accepted (or deduped) — completion observed via WaitCond
	}
	return fmt.Errorf("rehome agent unreachable: %w", last)
}

// WaitCond polls /ues until cond holds. A 503 (agent busy executing the job)
// counts as progress, not failure.
func (r *RehomeClient) WaitCond(ctx context.Context, cond func(map[int]ueInfo) bool) error {
	for {
		ues, err := r.UEs(ctx)
		if err == nil && cond(ues) {
			return nil
		}
		select {
		case <-time.After(10 * time.Second):
		case <-ctx.Done():
			return fmt.Errorf("rehome wait: %w", ctx.Err())
		}
	}
}

// dnnByOctet maps a slot's N3 octet to its DNN (gen_configs convention).
func dnnByOctet(oct int) string {
	m := map[int]string{38: "internet", 31: "internet2", 32: "internet3",
		33: "internet4", 34: "internet5", 35: "internet6", 36: "internet7",
		37: "internet8"}
	return m[oct]
}

// planScaleOut computes the minimal-move even-spread into a newly activated
// slot: repeatedly take one UE from the currently-fullest DNN until the new
// slot holds ⌊U/N⌋. Untouched UEs never move (no churn beyond necessity).
func planScaleOut(ues map[int]ueInfo, activeDnns []string, newDnn string) []RehomeMove {
	count := map[string][]int{}
	for _, d := range activeDnns {
		count[d] = nil
	}
	count[newDnn] = nil
	for i, u := range ues {
		count[u.Dnn] = append(count[u.Dnn], i)
	}
	for d := range count {
		sort.Sort(sort.Reverse(sort.IntSlice(count[d]))) // steal highest idx first (deterministic)
	}
	want := len(ues) / (len(activeDnns) + 1)
	var moves []RehomeMove
	for len(count[newDnn])+len(moves) < want {
		// fullest donor
		donor, max := "", 0
		for d, l := range count {
			if d == newDnn {
				continue
			}
			if len(l) > max {
				donor, max = d, len(l)
			}
		}
		if donor == "" || max <= want {
			break // nothing left worth stealing — spread already even
		}
		ue := count[donor][0]
		count[donor] = count[donor][1:]
		moves = append(moves, RehomeMove{UE: ue, Dnn: newDnn})
	}
	return moves
}

// planScaleIn drains a victim slot: its UEs (and only its UEs) move
// round-robin onto the least-loaded remaining slots.
func planScaleIn(ues map[int]ueInfo, remainingDnns []string, victimDnn string) []RehomeMove {
	return planScaleInCap(ues, remainingDnns, victimDnn, scaleInPackCap())
}

func planScaleInCap(ues map[int]ueInfo, remainingDnns []string, victimDnn string, cap int) []RehomeMove {
	count := map[string]int{}
	for _, d := range remainingDnns {
		count[d] = 0
	}
	var victims []int
	for i, u := range ues {
		if u.Dnn == victimDnn {
			victims = append(victims, i)
		} else if _, ok := count[u.Dnn]; ok {
			count[u.Dnn]++
		}
	}
	sort.Ints(victims)
	var moves []RehomeMove
	for _, ue := range victims {
		best, bestN := "", 1<<30
		for _, d := range remainingDnns {
			if cap > 0 && count[d] < cap {
				best = d
				break
			}
		}
		if best == "" { // every survivor at cap (or cap disabled): least-loaded, ties by order
			for _, d := range remainingDnns {
				if count[d] < bestN {
					best, bestN = d, count[d]
				}
			}
		}
		if best == "" {
			break
		}
		count[best]++
		moves = append(moves, RehomeMove{UE: ue, Dnn: best})
	}
	return moves
}

func scaleInPackCap() int {
	if v, err := strconv.Atoi(os.Getenv("EUPF_SCALEIN_PACK_CAP")); err == nil {
		return v
	}
	return 5
}

type RepathMove struct {
	UE   int    `json:"ue"`
	Vyos string `json:"vyos"`
}

// Repath re-pins UE transport paths (per-session ingress VyOS) via the agent.
// Unlike /rehome this is fast (no re-registration): the agent updates the
// path table and repoints the DL affinity neighbors.
func (r *RehomeClient) Repath(ctx context.Context, moves []RepathMove) error {
	if len(moves) == 0 {
		return nil
	}
	payload, _ := json.Marshal(map[string]any{"moves": moves})
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
			base+"/repath", bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		resp.Body.Close()
		if resp.StatusCode == 200 {
			return nil
		}
		last = fmt.Errorf("repath http %d", resp.StatusCode)
	}
	return fmt.Errorf("rehome agent unreachable: %w", last)
}

// PlanVyosDrain moves every UE currently pathed through victimDataIP onto the
// remaining VyOS instances, round-robin by current load.
func PlanVyosDrain(ues map[int]ueInfo, remaining []string, victimDataIP string) []RepathMove {
	count := map[string]int{}
	for _, v := range remaining {
		count[v] = 0
	}
	var victims []int
	for i, u := range ues {
		if u.Vyos == victimDataIP {
			victims = append(victims, i)
		} else if _, ok := count[u.Vyos]; ok {
			count[u.Vyos]++
		}
	}
	sort.Ints(victims)
	var moves []RepathMove
	for _, ue := range victims {
		best, bestN := "", 1<<30
		for _, v := range remaining {
			if count[v] < bestN {
				best, bestN = v, count[v]
			}
		}
		if best == "" {
			break
		}
		count[best]++
		moves = append(moves, RepathMove{UE: ue, Vyos: best})
	}
	return moves
}

// OfferedSample is one point of the sender-egress UL pps history (agent /offered "hist",
type OfferedSample struct {
	T   time.Time
	PPS float64
}

// Offered returns the sender-egress measured pps from the agent (/offered) plus the
func (r *RehomeClient) Offered(ctx context.Context) (float64, []OfferedSample, error) {
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, base+"/offered", nil)
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		var body struct {
			OfferedPPS float64       `json:"offered_pps"`
			Hist       [][2]float64 `json:"hist"`
		}
		err = json.NewDecoder(resp.Body).Decode(&body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		hist := make([]OfferedSample, 0, len(body.Hist))
		for _, h := range body.Hist {
			hist = append(hist, OfferedSample{T: time.Unix(int64(h[0]), 0), PPS: h[1]})
		}
		return body.OfferedPPS, hist, nil
	}
	return 0, nil, fmt.Errorf("rehome agent unreachable: %w", last)
}

// planRelief moves UEs off donors that exceed donorMin (the per-slot design
// capacity in UEs) onto the newly activated slot — nothing else. Unlike
// planScaleOut's full even-spread, standing sessions on healthy slots are
// never touched (each move costs the UE its in-flight data plane).
//
// v6.0.77 (2026-09-16 r67 warm-in): the receiver is capped at recvMax UEs
// (UP_REBALANCE_RECV_MAX, default 5 = floor(CapUP 1.35M / 0.25M per UE) =
// the slot design capacity). Without it every donor's excess lands on the ONE
// slot that happens to come up first: 25 UEs arriving in 4 min onto the two
// base slots left 8+8 → 8 moves onto .35 (cap ~5) → 7% sustained loss for
// 4 min until the periodic PoolRelief (2 moves / 150 s) caught up. Excess
// beyond the cap stays on its (old, eligible) donors and is picked up by the
// next slot's relief; the arrival steering converges the rest. r61-r66: all
// relief jobs were ≤5 moves (agent log), so the cap is behaviour-neutral there.
func planRelief(ues map[int]ueInfo, newDnn string, donorMin, recvMax int) []RehomeMove {
	// load per DNN counts EVERY UE (a fresh arrival is real load); only settled
	// UEs (eligibleForMove) are candidates to be moved off a donor.
	load := map[string]int{}
	movable := map[string][]int{}
	for i, u := range ues {
		load[u.Dnn]++
		if eligibleForMove(u) {
			movable[u.Dnn] = append(movable[u.Dnn], i)
		}
	}
	// oldest anchors first (settled NAS, longest-lived stream); idx as tie-break
	for d := range movable {
		l := movable[d]
		sort.Slice(l, func(a, b int) bool {
			if ues[l[a]].AgeS != ues[l[b]].AgeS {
				return ues[l[a]].AgeS > ues[l[b]].AgeS
			}
			return l[a] > l[b]
		})
	}
	var moves []RehomeMove
	for {
		if recvMax > 0 && load[newDnn] >= recvMax {
			return moves
		}
		donor, max := "", donorMin
		for d, n := range load {
			if d == newDnn || len(movable[d]) == 0 {
				continue
			}
			if n > max {
				donor, max = d, n
			}
		}
		if donor == "" {
			return moves
		}
		ue := movable[donor][0]
		movable[donor] = movable[donor][1:]
		load[donor]--
		load[newDnn]++
		moves = append(moves, RehomeMove{UE: ue, Dnn: newDnn})
	}
}

// SetDrain marks (or unmarks) a VyOS as draining on the sender agent. The
// agent publishes the set to /tmp/vy_drain.json; the measurement harness polls
// it every ~2s and rebuilds its UL streams off the victim *while the VM is
// still alive*. Without this the harness only learns of a deletion by failing
// to ping the victim's mgmt IP twice — and a deleted KubeVirt VM keeps
// answering mgmt pings for tens of seconds (r29: 33s on one delete, never
// within the window on the other → 5/11 UEs dark for 63s = a 45.44% minute).
func (r *RehomeClient) SetDrain(ctx context.Context, vyosIP string, on bool) error {
	payload, _ := json.Marshal(map[string]any{"vyos": vyosIP, "on": on})
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
			base+"/drain", bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		resp.Body.Close()
		if resp.StatusCode == 200 {
			return nil
		}
		last = fmt.Errorf("drain http %d", resp.StatusCode)
	}
	return fmt.Errorf("rehome agent unreachable: %w", last)
}

// SetSlotDrain publishes (or retracts) an eUPF slot's DNN as draining on the
// sender agent (/tmp/slot_drain.json). r9 min4-5 (2026-09-06): a slot being
// drained looks EMPTIEST to the harness's least-loaded arrival placement and
// still has a live PFCP association, so a fresh UE landed on it 58 s before
// it was deleted. Two-phase drain for slots, mirroring SetDrain for VyOS.
func (r *RehomeClient) SetSlotDrain(ctx context.Context, dnn string, on bool) error {
	payload, _ := json.Marshal(map[string]any{"slot_dnn": dnn, "on": on})
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodPost,
			base+"/drain", bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		resp.Body.Close()
		if resp.StatusCode == 200 {
			return nil
		}
		last = fmt.Errorf("slot drain http %d", resp.StatusCode)
	}
	return fmt.Errorf("rehome agent unreachable: %w", last)
}

// ULPool returns the VyOS set the sender's uplink streams are CURRENTLY built
// on, plus the age of that report. This is the acknowledgement half of the
// two-phase drain: the victim may only be destroyed once it has left this set.
func (r *RehomeClient) ULPool(ctx context.Context) (map[string]bool, float64, error) {
	var last error
	for _, base := range r.URLs {
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet, base+"/ulpool", nil)
		resp, err := r.hc.Do(req)
		if err != nil {
			last = err
			continue
		}
		var body struct {
			Pool []string `json:"pool"`
			Age  float64  `json:"age"`
		}
		err = json.NewDecoder(resp.Body).Decode(&body)
		resp.Body.Close()
		if err != nil {
			last = err
			continue
		}
		set := map[string]bool{}
		for _, v := range body.Pool {
			set[v] = true
		}
		return set, body.Age, nil
	}
	return nil, 0, fmt.Errorf("rehome agent unreachable: %w", last)
}
