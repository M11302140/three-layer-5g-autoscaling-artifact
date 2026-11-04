package main

import "time"

// baselineEmergLast (2026-10-22, spec §4.114 item 3): refractory clock of the emergency force applied
// on the baseline path when BASELINE_EMERGENCY=true (see internal/hbo/baseline_emergency.go).
var baselineEmergLast time.Time
