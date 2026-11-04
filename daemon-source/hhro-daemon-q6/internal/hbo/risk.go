package hbo

// EstimateRisk uses deterministic linear forecasting over H ticks to estimate
// the probability of SLO violation. No ML — just current score + slope.
func EstimateRisk(p PressureSet, f FeatureSet, cfg Cfg) RiskSet {
	var r RiskSet
	h := cfg.RiskHorizonTicks
	dt := cfg.MidIntervalSec

	// CP risk
	r.CP, r.ForecastMaxCP = computeNFRisk(p.CP, getScoreSlope(f.HhroCpScore, f.CpuCP, cfg), h, dt, cfg.CpHigh, cfg.MaxScoreSlope)

	// UP risk
	r.UP, r.ForecastMaxUP = computeNFRisk(p.UP, getScoreSlope(f.HhroUpScore, f.CpuUP, cfg), h, dt, cfg.UpHigh, cfg.MaxScoreSlope)

	// VyOS risk
	r.Vyos, r.ForecastMaxVyos = computeNFRisk(p.Vyos, getScoreSlope(f.HhroVyosScore, f.CpuVyos, cfg), h, dt, cfg.VyosHigh, cfg.MaxScoreSlope)

	return r
}

// computeNFRisk forecasts score over h ticks and accumulates squared excess
// above the high threshold.
func computeNFRisk(c0, slope float64, h int, dt, highThresh, maxSlope float64) (risk, forecastMax float64) {
	s := clamp(slope, -maxSlope, maxSlope)
	fmax := c0
	for k := 1; k <= h; k++ {
		forecast := clamp(c0+float64(k)*s*dt, 0, 1)
		excess := forecast - highThresh
		if excess > 0 {
			risk += excess * excess
		}
		if forecast > fmax {
			fmax = forecast
		}
	}
	return risk, fmax
}

// getScoreSlope tries to use the exported HHRO score's derivative first,
// falling back to the primary CPU metric's slope.
func getScoreSlope(scoreFeature, cpuFeature WindowFeature, cfg Cfg) float64 {
	if metricAvailable(scoreFeature) {
		return scoreFeature.Slope120
	}
	return cpuFeature.Slope120
}
