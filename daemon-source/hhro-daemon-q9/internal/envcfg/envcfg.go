// Package envcfg holds the tiny env-var parsing helpers shared across the
// daemon. Kept in its own package so every other internal/* package can pull
// them in without a cycle through main.
package envcfg

import (
	"os"
	"strconv"
	"time"
)

func Get(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func Dur(k string, def time.Duration) time.Duration {
	if v := os.Getenv(k); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}

func Float(k string, def float64) float64 {
	if v := os.Getenv(k); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return def
}

func Int(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func Bool(k string, def bool) bool {
	if v := os.Getenv(k); v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
	}
	return def
}

// Round3 truncates to 3 decimal places for log/Prom display. Kept here as the
// catch-all util to avoid a separate one-function package.
func Round3(f float64) float64 { return float64(int(f*1000)) / 1000 }
