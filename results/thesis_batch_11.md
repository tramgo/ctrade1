# Thesis Batch 11 - Real-Chain Options Tail Control

Date: 2026-06-22

## Why This Branch Exists

`TB10` proved that synthetic NIFTY option-premium selling was too optimistic. The real-chain iron-condor version stayed positive, but the return was too weak and the drawdown too large.

`TB11` therefore stays real-chain-first and tests only tail-control changes on actual NSE F&O bhavcopy option prices.

## Operating Rule

This batch may:

- use actual NIFTY option `CLOSE` prices from local F&O bhavcopy files
- use NIFTY spot and India VIX as entry filters
- test lower-risk condor geometry and entry-regime filters

It may not:

- use synthetic option premiums as evidence
- promote to live trading
- use RL
- treat a high-return filtered result as deployable before robustness and tail audit

## Completed Runs

### `TB11_T01 OptionsTailControlSweep`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_tail_control_sweep
```

Best variant:

- `TB11_farther_3pct_vix_shock_skip`
- trades: `864`
- annualized return on estimated margin: `10.18%`
- worst trade: `-611.03` points
- max drawdown: `-3650.11` points

Interpretation:

- better than the `TB10` real-chain baseline
- still not good enough; drawdown remains too large

### `TB11_T02 SpotRegimeTailSweep`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_spot_regime_tail_sweep
```

Best variant:

- `TB11_spot_3pct_ret5_m1_sma_0`
- trades: `498`
- annualized return on estimated margin: `18.19%`
- worst trade: `-611.03` points
- max drawdown: `-1390.71` points
- win rate: `76.10%`

Year read:

- positive in most calendar years
- one losing year: `2021`
- 2024 contribution is large and should be treated as a possible concentration warning

Worst-loss read:

- worst week remains `2022-06-08` to `2022-06-16`
- the simple spot and VIX filters did not eliminate that loss

## Verdict

`TB11_spot_3pct_ret5_m1_sma_0` was an `advance_candidate` after `TB11_T02`, but `TB11_T03` blocks promotion.

## `TB11_T03 RobustnessTailAudit`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_robustness_tail_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_robustness_tail_audit_summary.csv`
- `results/signal_baseline/tb11_options_robustness_tail_audit_years.csv`
- `results/signal_baseline/tb11_options_robustness_tail_audit_folds.csv`
- `results/signal_baseline/tb11_options_robustness_tail_audit_stress.csv`
- `results/signal_baseline/tb11_options_robustness_tail_audit_worst_trades.csv`

Audit findings:

- all-period annualized return on estimated margin: `18.19%`
- pre-2024 annualized return on estimated margin: `16.60%`
- 2024 annualized return on estimated margin: `199.33%`
- 2024 PnL share: `41.14%`
- fold 2 point PnL was slightly negative at `-7.42` points despite positive margin-return aggregation
- worst losses clustered in `2020`, `2021`, and `2022`
- excluding only the single worst 2022 window still leaves max drawdown at `-1390.71` points

Worst loss cluster:

- `2022-06-08` to `2022-06-16`: `-611.03`
- `2020-02-18` to `2020-02-27`: `-535.74`
- `2021-01-19` to `2021-01-28`: `-523.98`
- `2021-01-20` to `2021-01-28`: `-494.81`
- `2020-02-19` to `2020-02-27`: `-494.62`

Final TB11 read:

- candidate remains research-interesting
- no promotion
- no RL
- no broker execution
- only continue options work through a narrow loss-cluster / max-loss-budget design

## `TB11_T04 LossClusterMaxRiskControl`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_loss_cluster_control
python -u -B ssell1.py --mode signal_baseline_tb11_options_loss_cluster_control_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_loss_cluster_control_detail.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_summary.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_metadata.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_skipped.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_audit_summary.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_audit_years.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_audit_folds.csv`
- `results/signal_baseline/tb11_options_loss_cluster_control_audit_worst_trades.csv`

Best deployability-shaped candidate:

- `TB11_T04_3pct_5wing_ret5_1pct_liq50k`
- trades: `157`
- validation span: `2016-08-17` to `2024-06-27`
- annualized return on estimated margin: `24.92%`
- total PnL: `3229.66` points
- worst trade: `-270.89` points
- max drawdown: `-274.28` points
- win rate: `88.54%`
- 2024 PnL share: `9.24%`

Audit read:

- all calendar years from `2016` through `2024` are positive
- all four chronological folds are positive
- worst trade is reduced from `-611.03` in `TB11_T02` to `-270.89`
- max drawdown is reduced from `-1390.71` in `TB11_T02` to `-274.28`
- the large 2024-contribution problem is removed

Verdict:

`TB11_T04_3pct_5wing_ret5_1pct_liq50k` is an `advance_candidate_needs_broader_validation`.

No promotion yet. The next required gate is broader validation of data quality, liquidity assumptions, skipped-leg sensitivity, cost/haircut stress, and whether the liquidity floor is an overfit selection rule.

## `TB11_T05 BroaderValidation`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_broader_validation
```

Artifacts:

- `results/signal_baseline/tb11_options_broader_validation_detail.csv`
- `results/signal_baseline/tb11_options_broader_validation_summary.csv`
- `results/signal_baseline/tb11_options_broader_validation_metadata.csv`
- `results/signal_baseline/tb11_options_broader_validation_skipped.csv`

Read:

- `TB11_T05_base_liq50k_h15_c1`: `24.92%` annualized, worst `-270.89`, max DD `-274.28`
- `TB11_T05_h20_liq50k_c2`: `20.04%` annualized, worst `-281.91`, max DD `-302.91`
- `TB11_T05_h25_liq50k_c2`: `17.58%` annualized, worst `-288.92`, max DD `-311.54`
- `TB11_T05_h15_liq75k_c1`: `21.81%` annualized, worst `-68.50`, max DD `-68.50`
- `TB11_T05_h15_liq100k_c1`: `16.23%` annualized, worst `-68.50`, max DD `-68.50`

Interpretation:

- the `50k` liquidity candidate survives harsh cost/haircut stress but keeps one material tail event
- the `75k` and `100k` liquidity variants sharply reduce tail loss but give up return
- this creates a clear return/loss frontier worth optimizing narrowly

## `TB11_T06 FrontierOptimization`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_frontier_optimization
```

Artifacts:

- `results/signal_baseline/tb11_options_frontier_optimization_detail.csv`
- `results/signal_baseline/tb11_options_frontier_optimization_summary.csv`
- `results/signal_baseline/tb11_options_frontier_optimization_metadata.csv`
- `results/signal_baseline/tb11_options_frontier_optimization_skipped.csv`

Best current return/loss candidate:

- `TB11_T06_liq60k_ret5_0p01`
- trades: `141`
- validation span: `2016-08-17` to `2024-06-27`
- annualized return on estimated margin: `24.38%`
- total PnL: `2984.61` points
- worst trade: `-69.21` points
- max drawdown: `-69.21` points
- win rate: `89.36%`
- all calendar years positive
- all four chronological folds positive

Why it supersedes T04:

- T04 best deployability-shaped candidate returned `24.92%` annualized with worst trade `-270.89`
- T06 keeps almost the same return at `24.38%`
- T06 cuts worst trade and max drawdown by roughly `75%`

Verdict:

`TB11_T06_liq60k_ret5_0p01` is the new best TB11 advance candidate.

No promotion yet. The next required gate is focused harsh-cost validation for this exact `60k` liquidity / `1%` 5-day momentum rule, especially `20-25%` premium haircut and `2-3` points per-leg cost.

## `TB11_T07 HarshCostValidation`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_harsh_cost_validation
```

Artifacts:

- `results/signal_baseline/tb11_options_harsh_cost_validation_detail.csv`
- `results/signal_baseline/tb11_options_harsh_cost_validation_summary.csv`
- `results/signal_baseline/tb11_options_harsh_cost_validation_metadata.csv`
- `results/signal_baseline/tb11_options_harsh_cost_validation_skipped.csv`

Growth-candidate stress read:

- base `15%` haircut / `1` point per leg: `24.38%` annualized, worst `-69.21`, max DD `-69.21`
- `25%` haircut / `2` points per leg: `18.11%` annualized, worst `-79.24`, max DD `-81.72`
- `30%` haircut / `3` points per leg: `11.77%` annualized, worst `-86.61`, max DD `-142.84`

Interpretation:

- the growth candidate remains positive even under harsh cost assumptions
- the harshest assumptions create weak/negative early calendar years, so this is still not a final promotion
- the next useful optimization is not another broad filter sweep, but a return/loss frontier comparison

## `TB11_T08 ExpiryRiskFrontier`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_expiry_risk_frontier
```

Artifacts:

- `results/signal_baseline/tb11_options_expiry_risk_frontier_detail.csv`
- `results/signal_baseline/tb11_options_expiry_risk_frontier_summary.csv`
- `results/signal_baseline/tb11_options_expiry_risk_frontier_metadata.csv`
- `results/signal_baseline/tb11_options_expiry_risk_frontier_skipped.csv`

Best low-loss candidate:

- `TB11_T08_dte8_ret5_0p02`
- trades: `51`
- annualized return on estimated margin: `17.57%`
- total PnL: `1351.04` points
- worst trade: `-1.25` points
- max drawdown: `-1.25` points
- win rate: `94.12%`
- all chronological folds positive

## `TB11_T09 LowLossHarshCost`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_low_loss_harsh_cost
```

Artifacts:

- `results/signal_baseline/tb11_options_low_loss_harsh_cost_detail.csv`
- `results/signal_baseline/tb11_options_low_loss_harsh_cost_summary.csv`
- `results/signal_baseline/tb11_options_low_loss_harsh_cost_metadata.csv`
- `results/signal_baseline/tb11_options_low_loss_harsh_cost_skipped.csv`

Low-loss harsh-cost read:

- base `15%` haircut / `1` point per leg: `17.57%` annualized, worst `-1.25`, max DD `-1.25`
- `25%` haircut / `2` points per leg: `12.99%` annualized, worst `-5.99`, max DD `-5.99`
- `30%` haircut / `3` points per leg: `9.11%` annualized, worst `-10.36`, max DD `-18.77`

Final current TB11 frontier:

- Growth candidate: `TB11_T06_liq60k_ret5_0p01`
  - best for annualized return: `24.38%`
  - worst trade: `-69.21`
  - harshest tested return: `11.77%`
- Defensive candidate: `TB11_T08_dte8_ret5_0p02`
  - best for loss control: `17.57%`
  - worst trade: `-1.25`
  - harshest tested return: `9.11%`

Verdict:

No single final promotion yet.

The next required step is `TB11_T10 AllocationSizingFrontier`: compare fixed risk budgets and sizing between the growth and defensive candidates, using the harsh-cost rows as conservative lower bounds.

## `TB11_T10 AllocationSizingFrontier`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_allocation_sizing_frontier
```

Artifacts:

- `results/signal_baseline/tb11_options_allocation_sizing_frontier_detail.csv`
- `results/signal_baseline/tb11_options_allocation_sizing_frontier_summary.csv`
- `results/signal_baseline/tb11_options_allocation_sizing_frontier_metadata.csv`

Read:

- fixed allocation mostly scales down the growth candidate on dates where the defensive candidate is idle
- this reduces losses, but does not create a true improvement versus choosing one candidate family directly
- the useful next idea is conditional overlay, not static allocation

## `TB11_T11 ConditionalOverlayFrontier`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_conditional_overlay_frontier
```

Artifacts:

- `results/signal_baseline/tb11_options_conditional_overlay_frontier_detail.csv`
- `results/signal_baseline/tb11_options_conditional_overlay_frontier_summary.csv`
- `results/signal_baseline/tb11_options_conditional_overlay_frontier_metadata.csv`

Best max-return overlay:

- `def_full_resg100_ovg50`
- base annualized return on estimated margin: `27.21%`
- base worst trade: `-69.21`
- base max drawdown: `-69.20`
- harsh-stress annualized return: `14.12%`
- harsh-stress worst trade: `-86.61`
- harsh-stress max drawdown: `-152.79`

Best balanced overlay:

- `def_full_resg50_ovg50`
- base annualized return on estimated margin: `24.00%`
- base worst trade: `-34.60`
- base max drawdown: `-34.60`
- harsh-stress annualized return: `12.66%`
- harsh-stress worst trade: `-43.30`
- harsh-stress max drawdown: `-91.32`
- all chronological folds are positive in base, moderate-stress, and harsh-stress scenarios

Verdict:

`def_full_resg50_ovg50` becomes the current balanced candidate because it preserves nearly all of the original growth return while cutting base worst loss roughly in half and improving harsh-stress return/drawdown versus growth-only.

No promotion yet. The next required gate is `TB11_T12 LotCapitalRiskCalibration`: translate points, margin estimate, and lot size into rupee risk, capital requirement, and position-size caps.
