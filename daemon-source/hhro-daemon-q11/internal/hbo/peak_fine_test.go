package hbo

import (
	"testing"
	"time"
)

func TestPeakOfferedSinceUsesFineHistory(t *testing.T) {
	v := NewV6Shadow(testLogger())
	now := time.Now()
	v.offHist = []offSample{{T: now.Add(-60 * time.Second), V: 6.77e6}, {T: now.Add(-30 * time.Second), V: 6.77e6}}
	if p := v.PeakOfferedSince(115*time.Second, 6.76e6); p > 6.8e6 {
		t.Fatalf("baseline without fine history: peak %.2fM", p/1e6)
	}
	v.mu.Lock()
	v.mergeOfferedFine([]OfferedSample{
		{T: now.Add(-45 * time.Second), PPS: 3.875e6}, // 31 UE UL for one 5 s bucket
		{T: now.Add(-40 * time.Second), PPS: 3.4e6},
		{T: now.Add(-10 * time.Second), PPS: 3.38e6},
	})
	v.mu.Unlock()
	if p := v.PeakOfferedSince(115*time.Second, 6.76e6); p < 7.7e6 {
		t.Fatalf("fine history must raise the window peak to 7.75M, got %.2fM", p/1e6)
	}
	// outside the window it must not count
	if p := v.PeakOfferedSince(30*time.Second, 6.76e6); p > 6.8e6 {
		t.Fatalf("sample 45 s ago must not count in a 30 s window, got %.2fM", p/1e6)
	}
	// merging the same bucket twice keeps one entry (max)
	v.mu.Lock()
	v.mergeOfferedFine([]OfferedSample{{T: now.Add(-45 * time.Second), PPS: 3.0e6}})
	n := len(v.offFine)
	v.mu.Unlock()
	if n != 3 {
		t.Fatalf("dedupe by bucket time: want 3 entries, got %d", n)
	}
}
