package actuate

import (
	"testing"
	"time"
)

func TestPlanHotReliefMovesOneToColdest(t *testing.T) {
	ues := map[int]ueInfo{}
	for i := 0; i < 5; i++ {
		ues[10+i] = ueInfo{Dnn: "internet2", AgeS: 600}
	}
	ues[20], ues[21] = ueInfo{Dnn: "internet3", AgeS: 600}, ueInfo{Dnn: "internet3", AgeS: 600}
	ues[30], ues[31] = ueInfo{Dnn: "internet5", AgeS: 600}, ueInfo{Dnn: "internet5", AgeS: 600}
	for i := 0; i < 5; i++ {
		ues[40+i] = ueInfo{Dnn: "internet", AgeS: 600}
	}
	set := map[string]bool{"internet": true, "internet2": true, "internet3": true, "internet5": true}
	mv, cnt, ok := planHotRelief(ues, set, "internet2", 5)
	if !ok || mv.UE != 10 || mv.Dnn != "internet3" {
		t.Fatalf("want UE-10 -> internet3, got %+v ok=%v cnt=%v", mv, ok, cnt)
	}
	full := map[int]ueInfo{}
	for i := 0; i < 5; i++ {
		full[i] = ueInfo{Dnn: "internet2", AgeS: 600}
		full[10+i] = ueInfo{Dnn: "internet", AgeS: 600}
	}
	if _, _, ok := planHotRelief(full, map[string]bool{"internet": true, "internet2": true}, "internet2", 5); ok {
		t.Fatal("no receiver with room: must not move")
	}
	one := map[int]ueInfo{0: {Dnn: "internet2", AgeS: 600}, 1: {Dnn: "internet", AgeS: 600}}
	if _, _, ok := planHotRelief(one, map[string]bool{"internet": true, "internet2": true}, "internet2", 5); ok {
		t.Fatal("single-UE hot slot: nothing to relieve")
	}
	fresh := map[int]ueInfo{0: {Dnn: "internet2", AgeS: 10}, 1: {Dnn: "internet2", AgeS: 20}, 2: {Dnn: "internet", AgeS: 600}}
	if _, _, ok := planHotRelief(fresh, map[string]bool{"internet": true, "internet2": true}, "internet2", 5); ok {
		t.Fatal("fresh UEs are never moved")
	}
}

func TestHotSlotStreakAndParse(t *testing.T) {
	page := "# HELP x\nupf_vf_rx_out_of_buffer{slot=\"31\",iface=\"enp13s0\"} 1000\nupf_vf_rx_out_of_buffer{slot=\"38\",iface=\"enp14s0\"} 5000\nupf_vf_rx_packets{slot=\"31\"} 99\n"
	cum := parseVFOob(page)
	if cum[31] != 1000 || cum[38] != 5000 || len(cum) != 2 {
		t.Fatalf("parse: %v", cum)
	}
	h := &hotSlotState{prev: map[int]vfOobSample{}, rate: map[int]float64{}, streak: map[int]int{}, lastMove: map[int]time.Time{}}
	t0 := time.Now()
	thr := 1500.0
	h.ingestVFOob(t0, map[int]int64{31: 1000, 38: 5000}, thr)
	h.ingestVFOob(t0.Add(30*time.Second), map[int]int64{31: 1000 + 2700*30, 38: 5000 + 300*30}, thr)
	if len(h.hotSlots(t0.Add(30*time.Second), 2, 120*time.Second)) != 0 {
		t.Fatal("one hot sample is not yet a hot slot")
	}
	h.ingestVFOob(t0.Add(60*time.Second), map[int]int64{31: 1000 + 2700*30 + 3000*30, 38: 5000 + 300*60}, thr)
	hot := h.hotSlots(t0.Add(60*time.Second), 2, 120*time.Second)
	if len(hot) != 1 || hot[0] != 31 {
		t.Fatalf("slot 31 must be hot after two samples and .38 at 300 pps must not, got %v (rates %v)", hot, h.rate)
	}
	h.lastMove[31] = t0.Add(60 * time.Second)
	h.ingestVFOob(t0.Add(90*time.Second), map[int]int64{31: 1000 + 2700*30 + 3000*60, 38: 5000 + 300*90}, thr)
	if len(h.hotSlots(t0.Add(90*time.Second), 2, 120*time.Second)) != 0 {
		t.Fatal("cooldown must suppress a second move within 120 s")
	}
	h.ingestVFOob(t0.Add(120*time.Second), map[int]int64{31: 10, 38: 5000 + 300*120}, thr)
	if h.rate[31] != 0 || h.streak[31] != 0 {
		t.Fatalf("counter reset must clear rate/streak: %v %v", h.rate[31], h.streak[31])
	}
}
