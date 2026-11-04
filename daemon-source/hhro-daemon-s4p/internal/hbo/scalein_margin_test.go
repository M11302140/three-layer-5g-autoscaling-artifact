package hbo

import "testing"

func TestScaleInMarginHoldR19Dip(t *testing.T) {
	if hold, _ := scaleInMarginHold(18.9212, 18.9642, false, 0.15); !hold {
		t.Fatal("r19 09:25:45 coin-flip scale-in (adv 0.043) must be held")
	}
	if hold, _ := scaleInMarginHold(16.873, 17.156, false, 0.15); hold {
		t.Fatal("r21 11:26:05 single-slot scale-in (adv 0.283 = one slot's λ saving) must pass")
	}
	if hold, _ := scaleInMarginHold(15.2077, 16.2102, false, 0.15); hold {
		t.Fatal("r16 05:16:33 ramp-down tuple (adv 1.0) must pass")
	}
	if hold, _ := scaleInMarginHold(18.9212, 18.9642, true, 0.15); hold {
		t.Fatal("emergency must not be held")
	}
	if hold, _ := scaleInMarginHold(18.9212, 18.9642, false, 0); hold {
		t.Fatal("margin 0 disables the hold")
	}
}
