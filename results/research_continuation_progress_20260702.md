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

## TB11_T31 Staggered Multi-Expiry Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t31_staggered_multi_expiry_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_detail.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_summary.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_skipped.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_metadata.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_decision.md`

Current result:

- status: `research_rejected_or_blocked`
- source strategy: `TB11_T09_low_loss_h15_c1` / `TB11_T09_low_loss_h30_c3`
- source selected trades: `51`
- second-expiry usable trades: `3`
- coverage rate: `5.88%`
- best base stagger variant on covered rows: `stagger_25_75`
- best base annualized return on covered rows: `3.60%`
- best base max drawdown on covered rows: `0.0`
- dominant blocker: `second_expiry_leg_or_liquidity_missing` (`44` base rows and `44` harsh rows)
- broker orders allowed: `False`

Inference: T31 cannot be promoted from current local real-chain coverage. The few covered rows look benign, but only `3 / 51` selected entries have a tradable next-expiry construction under the current 60k total-contract threshold and local spot-settlement requirement. That is too little evidence for a staggered multi-expiry policy.

Next action: move to `TB19` OI positioning as the next plan item that can use current local `data/nse_fno_bhavcopy_oi.csv` and option-chain/bhavcopy artifacts. Keep T31 closed unless a later liquidity model or refreshed chain archive materially improves second-expiry coverage.

## TB19 OI Positioning Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb19_oi_positioning_readiness
```

Artifacts:

- `results/signal_baseline/tb19_oi_positioning_readiness_detail.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_summary.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_metadata.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_decision.md`

Current result:

- status: `no_oi_filter_promoted`
- local futures OI source: `data/nse_fno_bhavcopy_oi.csv`
- local option OI source: `tb11_nifty_option_chain_bhavcopy_archive_liquid_detail.csv`
- source selected TB11 trades: `51`
- base-case candidate: `pcr_high`
- base `pcr_high` trades: `32`
- base `pcr_high` annualized return on margin: `18.23%` versus all-trades `17.57%`
- base `pcr_high` max drawdown: `-0.66` versus all-trades `-1.25`
- harsh `pcr_high` annualized return on margin: `7.78%` versus all-trades `9.11%`
- harsh `pcr_high` max drawdown: `-19.94` versus all-trades `-18.77`
- durable filters passing base and harsh: `none`
- broker orders allowed: `False`

Inference: OI positioning has a useful base-case signal, but it does not survive the harsh-cost robustness requirement. The `pcr_high` filter trims trades and improves the base drawdown, yet it underperforms the all-trades harsh case and worsens harsh drawdown. Do not promote TB19.

Next action: proceed to the next attached-plan item, `TB17` covered-call overwrite, only as a readiness/backtest milestone if underlying holdings or synthetic holding assumptions are explicit. Otherwise keep the active no-order TB11/TB15 blockers as the operational priority.

## TB17 Covered-Call Overwrite Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb17_covered_call_overwrite_readiness
```

Artifacts:

- `results/signal_baseline/tb17_covered_call_overwrite_readiness_detail.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_summary.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_skipped.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_metadata.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- symbols tested: `RELIANCE`, `HDFCBANK`, `ICICIBANK`, `INFY`, `TCS`
- raw F&O bhavcopy files: `2346`
- weekly-entry files scanned: `426`
- sanity-passing trades: `238`
- first trade / last expiry: `2016-05-09` / `2024-06-27`
- portfolio incremental yield annualized: `4.38%`
- portfolio covered-call annualized return: `8.95%`
- portfolio buy-hold annualized return over matched windows: `2.84%`
- assignment rate: `28.57%`
- upside give-up / premium: `67.77%`
- HDFCBANK and RELIANCE were excluded by the price-scale sanity filter after their adjusted spot closes did not line up with unadjusted option strikes/premiums
- broker orders allowed: `False`

Inference: TB17 is not a promotion candidate from current local data. The first raw pass showed impossible premiums caused by adjusted-equity versus unadjusted-option price-scale mismatch; after adding strike/spot and premium/spot sanity gates, the remaining sample still gives up too much upside relative to premium and fails both portfolio gates.

Next action: keep TB17 closed as a documented reject until a corporate-action-adjusted spot/options alignment exists and a real passive holding file is specified. `TB20` is now completed below with the required Zerodha gold/debt assets, while `TB15_T03`, `TB11_T30`, and `TB18` remain data-readiness blocked.

## TB20 Cross-Asset Defensive Tilt

Implemented mode:

```powershell
python -B ssell1.py --mode signal_fetch_tb20_defensive_assets_from_zerodha
python -B ssell1.py --mode signal_baseline_tb20_cross_asset_defensive_tilt
```

Artifacts:

- `results/signal_baseline/tb20_defensive_assets_zerodha_fetch.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_detail.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_summary.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_folds.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_metadata.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- Zerodha fetch: `GOLDBEES` rows `2471` from `2016-07-05` to `2026-07-02`; `LIQUIDBEES` rows `2473` from `2016-07-05` to `2026-07-03`
- universe: `NIFTYBEES`, `GOLDBEES`, `LIQUIDBEES`
- rule: baseline `90%` NIFTYBEES / `5%` GOLDBEES / `5%` LIQUIDBEES; shift to `50%` / `15%` / `15%` plus `20%` cash when trailing 60-session NIFTYBEES drawdown breaches `12%`
- events: `242`
- risk-off events: `10`
- NIFTYBEES interval benchmark annualized return: `12.23%`
- static 90/5/5 annualized return: `9.21%`
- defensive tilt annualized return: `8.53%`
- benchmark max drawdown: `-32.03%`
- static 90/5/5 max drawdown: `-29.04%`
- defensive tilt max drawdown: `-24.01%`
- drawdown improvement versus benchmark: `25.03%`
- annualized return give-up versus benchmark: `3.69%`
- folds beating benchmark: `1 / 10`
- broker orders allowed: `False`

Inference: TB20 now uses the attached plan's required gold/debt defensive assets from Zerodha instead of the earlier PHARMABEES proxy. The mechanical drawdown trigger does reduce max drawdown by the required `25%` threshold, but it gives up `3.69%` annualized return versus the `3%` cap and beats the benchmark in only `1 / 10` folds. Do not promote this defensive tilt.

Next action: the attached plan is now exhausted into either completed rejects or explicit data blockers. Return to operational/data-readiness work: keep T28/Phase 2 no-order collection healthy, refresh F&O/spot data for `TB15_T03`, accumulate IV history for `TB11_T30`, and populate earnings/index weights for `TB18`.
