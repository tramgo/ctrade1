# Research Continuation Progress - 2026-07-02

Source plan: `c:\Users\Ramic\Downloads\new golas today jun_07_26.txt`

## Plan Reconciliation

The attached plan sequences work as:

1. Complete post-TB14 validation steps 3, 4, 5, and 6.
2. Run TB15_T03 fresh forward sample.
3. Implement TB11_T30 IV-conditioned sizing.

Current repo evidence shows item 1 is already completed and closed:

- Step 3 walk-forward threshold replay: `step3_survives`
  - selected quantile: `0.4`
  - holdout folds beating rebalanced benchmark: `4 / 4`
- Step 4 random hedge null: `step4_survives`
  - random seeds: `1000`
  - actual percentile versus null: `0.999`
- Step 5 short feasibility: `short_cost_stress_survives`
  - hedge windows: `25`
  - historical FUTSTK coverage: `27 / 27`
  - base folds beating rebalanced benchmark: `7`
  - note: historical FUTSTK coverage is not live SLB borrow availability
- Step 6 strict OOS replay: `kill_switch_oos_replay_failed`
  - fit folds: `1-8`
  - OOS folds: `9-10`
  - OOS folds beating rebalanced benchmark: `1 / 2`
  - required OOS folds: `2`

Inference: post-TB14 does not reopen the equity family. The already-recorded strict OOS kill-switch remains the controlling evidence, so the plan should not spend more cycles on OHLCV-only TB14 promotion work unless a genuinely external validation path is added.

## TB15_T03 Fresh Forward Sample

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t03_fresh_forward_sample
```

Artifacts:

- `results/signal_baseline/tb15_t03_fresh_forward_sample_summary.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_metadata.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_detail.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_decision.md`

Current result:

- status: `blocked_no_non_overlapping_forward_slice`
- source TB15 base trades: `522`
- source first trade date: `2016-05-09`
- source last expiry date: `2024-07-25`
- local F&O zip count: `2346`
- archive min/max date: `2015-01-01` / `2024-07-05`
- held-out trade count: `0`
- broker orders allowed: `False`

Inference: a genuine fresh forward sample is not locally available. The F&O archive ends before the already-used TB15 base sample expiry horizon. Reusing the original 522 trades would violate the T03 non-overlap requirement.

## Current Next Action

Do not proceed to TB15_T04 defined-risk bull put spread redesign from this blocked T03 result. Refresh local F&O bhavcopy and daily spot data beyond the TB15 base sample, then rerun T03. If refreshing the forward slice is not possible, move to TB11_T30 IV-conditioned sizing as the next cheapest high-value research item that uses already collected chain-band data.

## TB11_T30 IV-Conditioned Sizing Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t30_iv_conditioned_sizing_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_detail.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_latest_snapshot.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_summary.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_metadata.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_decision.md`

Current result:

- status: `blocked_insufficient_iv_history`
- source chain-band detail files: `4`
- raw chain rows: `388`
- eligible OTM fresh rows: `50`
- modeled IV rows: `50`
- unique fresh capture dates: `1`
- first/latest fresh capture date: `2026-07-01` / `2026-07-01`
- history span: `0 / 60` days
- latest median modeled IV: `0.13398187395710384`
- latest median available-history IV rank: `1.0`
- provisional sizing tier: `no_entry_insufficient_history`
- broker orders allowed: `False`

Inference: the chain-band data is sufficient to compute modeled implied volatility from mid quotes, spot, strike, option type, and DTE, but it is not yet sufficient to use a 60-day IV percentile. T30 remains a research-only preview until enough fresh market-hour chain-band captures accumulate.

Next action: keep scheduled T28 chain-band collection alive and rerun T30 after the fresh capture history spans 60 days or at least 20 fresh capture dates. Do not use the provisional IV rank for sizing yet.

## TB18 Earnings-Avoidance Overlay Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb18_earnings_overlay_readiness
```

Artifacts:

- `results/signal_baseline/tb18_earnings_overlay_readiness_summary.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_detail.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_metadata.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_decision.md`

Current result:

- status: `blocked_missing_earnings_axis_data`
- earnings calendar path: `data/earnings_calendar.csv`
- earnings status: `template_only`
- earnings rows: `0`
- TB15 symbol coverage: `0 / 8`
- NIFTY weight status: `missing`
- TB11 overlay ready: `False`
- TB15 overlay ready: `False`
- broker orders allowed: `False`
- blockers: `earnings_calendar_template_only|tb15_symbol_earnings_coverage_incomplete|nifty_index_weight_file_missing`

Inference: TB18 is not runnable yet. The repo has the schema placeholder for earnings dates, but no actual event rows, and it also lacks the NIFTY index-weight/constituent file required to compute the TB11 "heavy earnings week" veto.

Next action: populate `data/earnings_calendar.csv` with non-Zerodha earnings dates and add a NIFTY constituent/weight file with symbol and weight columns before running any TB18 overlay backtest.

## TB16 Defined-Risk NIFTY Bull Put Spread

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb16_defined_risk_nifty_bull_put_spread
```

Artifacts:

- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_detail.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_summary.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_skipped.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_metadata.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- trades: `308`
- first entry / last expiry: `2016-07-25` / `2024-07-11`
- annualized return on estimated margin: `14.91%`
- win rate: `74.68%`
- worst trade: `-325.18` points
- max drawdown: `-1078.95` points
- TB11 return correlation: `0.4700` over `161` overlapping expiries
- correlation source: `tb11_options_conditional_overlay_frontier_detail.csv`
- blocker: `annualized_rom_below_15pct`
- broker orders allowed: `False`

Inference: TB16 has acceptable diversification versus the TB11 balanced overlay, but it misses the 15% annualized return-on-margin gate by a narrow margin and carries materially larger point drawdown than the current TB11 defensive/balanced profiles. Do not promote this first bull-put spread variant.

Next action: keep TB16 as a documented reject unless we intentionally test a narrower follow-up variant with a higher credit floor, lower liquidity threshold sensitivity, or a stronger trend/volatility gate. The plan order can move to TB11_T31 staggered multi-expiry or TB19 OI positioning while TB15_T03, TB11_T30, and TB18 remain blocked by data readiness.
