package hbo

import "time"

// nowFn is the package clock. Production code uses the wall clock; the
// decision-equivalence harness (equiv_test.go, 10-05) substitutes a simulated
// clock so a 60-minute trace can be replayed through V6Shadow/Controller in
// milliseconds with the same in-flight / lock / history semantics as the daemon.
var nowFn = time.Now

func sinceFn(t time.Time) time.Duration { return nowFn().Sub(t) }
