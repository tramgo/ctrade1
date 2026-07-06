# TB15 T02 CSP Vol/Breadth Stress Gate

Status: `research_only_stress_gate_candidate`

- source trades: `522`
- best non-baseline variant: `skip_composite_stress`
- NIFTY context coverage: `97.7%`
- India VIX context coverage: `97.1%`
- best variant kept trades: `391`
- best variant portfolio mean return on cash: `0.3229%`
- best variant worst portfolio expiry return: `-21.4128%`
- best variant tail-loss events <= -5%: `21` (`5` fewer than ungated)
- broker orders allowed: `False`

Next action: Review `tb15_csp_vol_breadth_stress_gate_kelly_sizing.csv` and only consider capped fractional paper sizing after a fresh forward sample.
