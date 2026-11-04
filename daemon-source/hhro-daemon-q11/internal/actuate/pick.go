package actuate

import (
	"context"
	"fmt"
	"regexp"
	"strconv"

	"github.com/anon/hhro-daemon/internal/harvester"
)

// PickReleaseTarget returns the worker VM name with the highest numeric suffix
// — newest by allocation order, the right one to reap per HHRO §3.6.
func PickReleaseTarget(ctx context.Context, h *harvester.Harvester, prefix string) (string, error) {
	return pickHighestSuffixVM(ctx, h, prefix)
}

// PickReleaseVyosTarget mirrors PickReleaseTarget for VyOS pool members.
// Phase 1 manual VMs (test-vyos / test-vyos-2) don't match the daemon prefix
// so they're preserved.
func PickReleaseVyosTarget(ctx context.Context, h *harvester.Harvester, prefix string) (string, error) {
	return pickHighestSuffixVM(ctx, h, prefix)
}

func pickHighestSuffixVM(ctx context.Context, h *harvester.Harvester, prefix string) (string, error) {
	vms, err := h.ListVMs(ctx, "")
	if err != nil {
		return "", err
	}
	re := regexp.MustCompile(`^` + regexp.QuoteMeta(prefix) + `(\d+)$`)
	best := -1
	bestName := ""
	for _, v := range vms {
		m := re.FindStringSubmatch(v.Name)
		if len(m) != 2 {
			continue
		}
		n, _ := strconv.Atoi(m[1])
		if n > best {
			best = n
			bestName = v.Name
		}
	}
	if bestName == "" {
		return "", fmt.Errorf("no VM matching prefix %q", prefix)
	}
	return bestName, nil
}

