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

## `TB11_T12 LotCapitalRiskCalibration`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration
```

Artifacts:

- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_detail.csv`
- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_summary.csv`
- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_metadata.csv`

Scope:

- post-processes `TB11_T11` overlay rows
- converts point PnL, worst trade, max drawdown, and estimated margin into rupees
- tests lot sizes `50`, `65`, and `75`, with `65` as current-reference NIFTY sizing
- tests capital budgets from `100000` to `2000000`
- tests worst-trade budgets from `5000` to `100000`
- tests drawdown budgets from `10000` to `200000`

Representative current-reference `65` lot-size read:

- `200000` capital / `10000` worst-trade / `25000` drawdown:
  - base top: `def_full_resg100_ovg50`, `1` lot, `15.13%` annualized on capital
  - harsh-stress top: `def_full_resg0_ovg0`, `2` lots, `4.89%` annualized on capital
  - interpretation: small capital plus tight loss budgets forces defensive behavior under harsh stress
- `500000` capital / `25000` worst-trade / `50000` drawdown:
  - base top: `def_full_resg100_ovg50`, `4` lots, `24.21%` annualized on capital
  - harsh-stress top: `def_full_resg100_ovg50`, `4` lots, `7.55%` annualized on capital, worst `-22517`, max DD `-39725`
  - harsh-stress balanced: `def_full_resg50_ovg50`, `4` lots, `6.42%` annualized on capital, worst `-11259`, max DD `-23744`
- `1000000` capital / `50000` worst-trade / `100000` drawdown:
  - base top: `def_full_resg100_ovg50`, `8` lots, `24.21%` annualized on capital
  - harsh-stress top: `def_full_resg100_ovg50`, `8` lots, `7.55%` annualized on capital, worst `-45035`, max DD `-79450`
  - harsh-stress balanced: `def_full_resg50_ovg50`, `8` lots, `6.42%` annualized on capital, worst `-22517`, max DD `-47488`

Verdict:

`TB11_T12` completes the lot/capital translation but does not promote TB11.

The max-return overlay is still best when the account can tolerate wider rupee drawdowns. The balanced overlay remains valuable because it cuts harsh-stress worst trade and drawdown materially for a smaller return haircut. The defensive-only profile becomes the correct behavior under small-capital, tight-loss, harsh-stress constraints.

Next required gate:

- open `TB11_T13_CapitalAwarePolicySelection`
- define explicit profile constraints
- choose a single candidate by capital-aware objective rather than raw annualized return alone
- keep broker execution and live routing blocked

## `TB11_T13 CapitalAwarePolicySelection`

Commands:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration
python -u -B ssell1.py --mode signal_baseline_tb11_options_capital_aware_policy_selection
```

Artifacts:

- `results/signal_baseline/tb11_options_capital_aware_policy_selection_summary.csv`
- `results/signal_baseline/tb11_options_capital_aware_policy_selection_metadata.csv`

Implementation adjustment:

The first policy-selection pass was too narrow because the lot/capital calibration only compared four overlays:

- max-return overlay
- growth-only residual
- balanced overlay
- defensive-only

That could miss the actual frontier between return and loss control. The calibration was widened to all `15` conditional overlay combinations from `TB11_T11`, then `TB11_T12` and `TB11_T13` were rerun.

Selected capital-aware profile:

- `def_full_resg0_ovg50`
- defensive trades stay at full size
- growth exposure is added only on defensive-overlap dates at `50%`
- residual growth-only exposure is `0%`

Why it wins:

- it improves materially on defensive-only return
- it avoids the residual growth-only dates that create the largest harsh-stress loss usage
- it passes base, moderate, and harsh-stress return gates
- it remains deployable under lot-size sensitivity at `50`, `65`, and `75`

Reference `65` lot-size results:

- small capital profile:
  - capital / worst / drawdown budget: `200000` / `10000` / `25000`
  - base annualized on capital: `18.61%`
  - harsh annualized on capital: `7.33%`
  - harsh worst / max DD: `-2019` / `-3660`
- balanced profile:
  - capital / worst / drawdown budget: `500000` / `25000` / `50000`
  - base annualized on capital: `22.33%`
  - harsh annualized on capital: `8.80%`
  - harsh worst / max DD: `-6058` / `-10980`
- growth profile:
  - capital / worst / drawdown budget: `1000000` / `50000` / `100000`
  - base annualized on capital: `24.19%`
  - harsh annualized on capital: `9.53%`
  - harsh worst / max DD: `-13125` / `-23791`
- large-capital growth profile:
  - capital / worst / drawdown budget: `2000000` / `100000` / `200000`
  - base annualized on capital: `25.12%`
  - harsh annualized on capital: `9.53%`
  - harsh worst / max DD: `-26250` / `-47582`

Verdict:

`def_full_resg0_ovg50` becomes the current best TB11 capital-aware candidate.

No promotion yet. The next required gate is `TB11_T14 SelectedProfileRobustnessAudit`: inspect yearly contribution, chronological folds, worst trades, and loss clusters for the selected profile against defensive-only and max-return controls.

## `TB11_T14 SelectedProfileRobustnessAudit`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_selected_profile_robustness_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_summary.csv`
- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_years.csv`
- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_folds.csv`
- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_worst_trades.csv`
- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_loss_clusters.csv`
- `results/signal_baseline/tb11_options_selected_profile_robustness_audit_metadata.csv`

Selected profile:

- `def_full_resg0_ovg50`

Read:

- base annualized return on margin: `22.54%`
- moderate-stress annualized return on margin: `17.12%`
- harsh-stress annualized return on margin: `12.35%`
- all chronological folds are positive in base, moderate, and harsh stress
- concentration passes in base, moderate, and harsh stress
- loss-cluster checks pass
- strict all-years gate fails because `2017` has one selected-profile trade and that single trade is negative

Verdict:

T14 blocks promotion. The failure is not a broad drawdown or concentration problem; it is a sparse warmup-year problem. The next useful hardening test is a maturity gate, not another strategy search.

## `TB11_T15 SelectedProfileMaturityGate`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_selected_profile_maturity_gate
```

Artifacts:

- `results/signal_baseline/tb11_options_selected_profile_maturity_gate_summary.csv`
- `results/signal_baseline/tb11_options_selected_profile_maturity_gate_metadata.csv`

Minimal passing maturity rule:

- skip the first observed selected-profile trade
- first active trade after gate: `2019-02-25`
- this is equivalent to removing the one-trade 2017 warmup year without changing the selected overlay weights

Maturity-gated read:

- base:
  - trades: `50`
  - annualized return on margin: `31.62%`
  - worst / max DD: `-1.88` / `-0.99`
  - all `5` active years positive
  - all `4` chronological folds positive
- moderate stress:
  - annualized return on margin: `23.93%`
  - worst / max DD: `-8.98` / `-8.01`
  - all `5` active years positive
  - all `4` chronological folds positive
- harsh stress:
  - annualized return on margin: `17.32%`
  - worst / max DD: `-15.53` / `-28.15`
  - all `5` active years positive
  - all `4` chronological folds positive

Verdict:

The maturity gate repairs the sparse-year failure and improves the selected profile without re-optimizing the overlay. No promotion yet. The next required gate is `TB11_T16 MaturityAdjustedRupeeProfile`: recompute lot, rupee, margin, and capital-budget reads after applying the one-observation maturity gate.

## `TB11_T16 MaturityAdjustedRupeeProfile`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_maturity_adjusted_rupee_profile
```

Artifacts:

- `results/signal_baseline/tb11_options_maturity_adjusted_rupee_profile_summary.csv`
- `results/signal_baseline/tb11_options_maturity_adjusted_rupee_profile_metadata.csv`

Profile:

- allocation: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- first active trade after gate: `2019-02-25`

Reference `65` lot-size read:

- `200000` capital / `10000` worst / `25000` drawdown:
  - lots: `2`
  - base / moderate / harsh annualized on capital: `25.15%` / `16.34%` / `10.08%`
  - harsh worst / max DD: `-2019` / `-3660`
- `500000` capital / `25000` worst / `50000` drawdown:
  - lots: `6`
  - base / moderate / harsh annualized on capital: `30.18%` / `19.61%` / `12.10%`
  - harsh worst / max DD: `-6058` / `-10980`
- `1000000` capital / `50000` worst / `100000` drawdown:
  - lots: `13`
  - base / moderate / harsh annualized on capital: `32.69%` / `21.25%` / `13.10%`
  - harsh worst / max DD: `-13125` / `-23791`
- `2000000` capital / `100000` worst / `200000` drawdown:
  - lots: `26` to `27`
  - base / moderate / harsh annualized on capital: `33.95%` / `21.25%` / `13.10%`
  - harsh worst / max DD: `-26250` / `-47582`

Verdict:

`TB11_T16` passes the maturity-adjusted rupee and capital-budget gate. The selected profile is now the strongest TB11 candidate so far because it combines:

- all-years and all-folds maturity-adjusted robustness
- controlled harsh-stress drawdown
- positive harsh-stress annualized return on capital across tested budget tiers

No live promotion yet. The next required gate is `TB11_T17 ProfileFreezeExecutionReadiness`: freeze the paper-trading profile, document kill switches, and keep broker execution blocked.

## `TB11_T17 ITMExpirySTTAudit`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_itm_expiry_stt_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_summary.csv`
- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_trades.csv`
- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_metadata.csv`

Reason:

The prior cost model used premium haircut plus points-per-leg costs as a lumped cost proxy. That is deliberately conservative for normal execution frictions, but it does not separately model STT, GST, SEBI, exchange, stamp duty, or ITM expiry STT. The specific high-risk omission is STT on exercised ITM options, so this gate audits short-leg intrinsic exposure at expiry.

Method:

- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- conservative extra charge: `0.125%` of ITM short-leg intrinsic value at expiry
- charge applied before selected-profile aggregation and lot-size read

Result:

- active selected-profile trades: `50`
- ITM-expiry short-leg trades: `1`
- ITM-expiry event rate: `2%`
- total extra exercise-STT impact: `0.01546875` points
- lot-size `65` total extra exercise-STT impact: about `1.01` rupees
- base annualized return after STT: `31.62%`
- moderate-stress annualized return after STT: `23.93%`
- harsh-stress annualized return after STT: `17.32%`
- all years and folds remain positive

Verdict:

`TB11_T17` passes. ITM-expiry STT is still a mandatory risk note, but it is not material for the selected maturity-gated profile in the historical sample. The planned profile-freeze gate is superseded by `TB11_T18 ItemizedIndianFNOCostAudit` before any paper/live consideration.

## `TB11_T18 ItemizedIndianFNOCostAudit`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_itemized_fno_cost_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_itemized_fno_cost_audit_summary.csv`
- `results/signal_baseline/tb11_options_itemized_fno_cost_audit_trades.csv`
- `results/signal_baseline/tb11_options_itemized_fno_cost_audit_legs.csv`
- `results/signal_baseline/tb11_options_itemized_fno_cost_audit_metadata.csv`

Reason:

TB11 previously used a premium haircut plus points-per-leg cost proxy. That proxy was intentionally conservative, but it did not itemize Zerodha-style Indian F&O costs. This gate adds explicit per-leg accounting for option brokerage, sell-side premium STT, exchange transaction charges, SEBI charges, GST, buy-side stamp duty, plus a conservative ITM-expiry intrinsic STT and brokerage bucket.

Current broker-charge assumptions used:

- brokerage: `20` rupees per option order/leg
- option sell-side premium STT: `0.05%`
- ITM exercised intrinsic STT stress bucket: `0.15%`
- NSE option transaction charge: `0.03553%` of premium
- GST: `18%` of brokerage + SEBI + transaction charges
- SEBI: `10` rupees per crore
- stamp duty: `0.003%` on buy-side option premium

Result:

- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- active selected-profile trades: `50`
- ITM-expiry trades: `1`
- ITM-expiry legs: `2`
- all years and folds remain positive under base, moderate, and harsh stress
- concentration remains below the gate

Reference lot size `65`:

- base itemized cost: `112.99` points versus `300.00` lumped points; annualized return after itemized cost: `33.18%`
- moderate-stress itemized cost: `112.99` points versus `600.00` lumped points; annualized return after itemized cost: `28.84%`
- harsh-stress itemized cost: `112.99` points versus `900.00` lumped points; annualized return after itemized cost: `26.50%`

Verdict:

`TB11_T18` passes. The itemized cost model shows that the prior lumped proxy was materially harsher than the Zerodha-style cost model in this selected-profile sample. No paper/live promotion yet.

The next gate becomes `TB11_T19 ProfileFreezeExecutionReadiness`: freeze the paper-only profile, require this cost module for every future run, specify exit-before-expiry behavior, and keep broker/live execution blocked.

## `TB11_T19 ProfileFreezeExecutionReadiness`

Artifacts:

- `results/signal_baseline/tb11_options_profile_freeze_execution_readiness.md`
- `results/signal_baseline/tb11_options_profile_freeze_execution_readiness_summary.csv`

Frozen paper-only profile:

- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- reference lot size: `65`
- itemized Indian F&O cost module is mandatory
- broker/live execution remains blocked

Practical staged validation plan:

| Phase | Duration | Mode | Gate |
|---|---:|---|---|
| 1. Dry run | 1-2 months | Log signals and simulate fills only. | Every signal is logged; trigger timing and skip reasons are reproducible. |
| 2. Paper at real prices | 3-6 months | Paper-fill from observed option prices. | At least `10-15` paper trades; real available premiums within `10-15%` adverse tolerance; no surprise costs. |
| 3. Tiny live | 3-6 months | Future human-approved `1` lot only. | At least `10` real-money trades; broker mechanics, charges, and psychology are acceptable. |
| 4. Scale to target | ongoing | Gradual size increase. | Only after phases 1-3 hold up and budget is revalidated. |

No-trade and kill-switch rules:

- no itemized cost module, no trade
- no complete option chain and realistic leg premiums, no trade
- no intentional hold through expiry without a separate expiry-risk thesis
- pause if premium slippage exceeds `15%` adverse tolerance
- pause if median adverse fill drift exceeds `10%` across the latest `5` fills
- pause on any unmodeled cost or broker/API order attempt during phases 1 or 2

Verdict:

`TB11_T19` passes as a paper-only profile freeze. The next gate is `TB11_T20 DryRunSignalLogger`, which must implement no-order signal logging before any paper-at-real-prices phase.

## `TB11_T20 DryRunSignalLogger`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_dry_run_signal_logger
```

Artifacts:

- `results/signal_baseline/tb11_options_dry_run_signal_log.csv`
- `results/signal_baseline/tb11_options_dry_run_signal_log_summary.csv`
- `results/signal_baseline/tb11_options_dry_run_reconciliation.md`
- `results/signal_baseline/tb11_options_dry_run_signal_log_metadata.csv`

Method:

The logger replays the frozen selected profile into the Phase 1 signal schema using historical chain-detail rows. It records signal id, entry/expiry date, profile, skip reason, simulated fill proxy, itemized entry cost, premium tolerance band, expiry policy, and broker-order block status.

Result:

- signals logged: `51`
- simulated signals after maturity gate: `50`
- skipped warmup signals: `1`
- broker orders allowed: `False`
- schema gate passed: `True`
- mean modeled credit: `46.7961` points
- mean itemized entry cost: `2.24853` points
- minimum modeled net after entry cost: `1.933874` points

Verdict:

`TB11_T20` passes as a no-order logger schema gate. The next gate is `TB11_T21 DryRunObservedQuoteCapture`, which must capture real observed quotes during Phase 1 and reconcile them against modeled premium before any Phase 2 paper-at-real-prices gate.

## `TB11_T21 DryRunObservedQuoteCapture`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_capture_template
```

Artifacts:

- `results/signal_baseline/tb11_options_observed_quote_capture_template.csv`
- `results/signal_baseline/tb11_options_observed_quote_capture_template_summary.csv`
- `results/signal_baseline/tb11_options_observed_quote_capture_template_metadata.csv`
- `results/signal_baseline/tb11_options_observed_quote_reconciliation.md`

Method:

The template is generated from the T20 no-order signal log. It keeps modeled premium, tolerance bands, itemized costs, profile, expiry policy, and broker-order block fields, then adds blank observed quote fields for timestamp, quote source, bid/ask by leg, observed weighted credit, tolerance checks, freshness checks, spread-quality checks, and operator notes.

Result:

- template rows: `50`
- source signals: `50`
- broker orders allowed: `False`
- stale quote threshold: `300` seconds
- adverse premium tolerance: `15%`
- template gate passed: `True`

Verdict:

`TB11_T21` passes. The next gate is `TB11_T22 ObservedQuoteReconciliationValidator`, which should score filled-in observed quotes against freshness, leg completeness, spread quality, and 10-15% adverse-premium tolerance.

## `TB11_T22 ObservedQuoteReconciliationValidator`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_reconciliation_validator
```

Artifacts:

- `results/signal_baseline/tb11_options_observed_quote_validation_detail.csv`
- `results/signal_baseline/tb11_options_observed_quote_validation_summary.csv`
- `results/signal_baseline/tb11_options_observed_quote_validation_metadata.csv`

Method:

The validator reads the observed-quote capture template. For filled rows, it computes observed weighted credit from leg bid/ask quotes, checks quote freshness, all-leg availability, spread quality, adverse-premium tolerance, surprise-cost flags, and broker-order blocking. Empty observed rows remain explicitly pending.

Result:

- template rows: `50`
- observed rows: `0`
- pending rows: `50`
- broker-block violations: `0`
- validator schema gate passed: `True`
- Phase 1 evidence gate passed: `False`
- validator status: `ready_pending_observations`

Verdict:

`TB11_T22` passes as a validator/readiness gate, not as observed trading evidence. The next gate is `TB11_T23 DryRunObservationCollection`: collect real no-order quote observations for `1-2 months` and rerun the validator after each batch.

## `TB11_T23 DryRunObservationCollection` Setup

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_dry_run_observation_collection_pack
```

Artifacts:

- `results/signal_baseline/tb11_options_dry_run_observation_collection_20260623.csv`
- `results/signal_baseline/tb11_options_dry_run_observation_collection_ledger.csv`
- `results/signal_baseline/tb11_options_dry_run_observation_collection_summary.csv`
- `results/signal_baseline/tb11_options_dry_run_observation_collection_metadata.csv`
- `results/signal_baseline/tb11_options_dry_run_observation_collection_runbook.md`

Result:

- collection date: `2026-06-23`
- batch id: `TB11_PHASE1_OBS_20260623`
- rows prepared: `50`
- broker orders allowed: `False`
- prior observed rows: `0`
- status: `manual_no_order_collection_ready`

Verdict:

`TB11_T23` is prepared for manual Phase 1 collection but remains open. The strategy cannot advance to Phase 2 until real no-order observations are collected for `1-2 months` and the validator shows enough clean rows.

## `TB11_T24 ZerodhaQuoteOnlyCollector`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_zerodha_quote_only_collector
```

Artifacts:

- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_20260624.csv`
- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_summary.csv`
- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_metadata.csv`
- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_unresolved_20260624.csv`

Method:

The collector is quote-only. It accepts current NFO tradingsymbols if present, optionally resolves current/future expiry rows through the NFO instrument dump, fetches bid/ask snapshots through Kite quote APIs, computes observed weighted credit, and keeps `broker_order_allowed=False`. It does not call order endpoints.

Result:

- input rows: `50`
- quote symbols requested: `0`
- quote packets received: `0`
- captured rows: `0`
- unresolved rows: `50`
- collector status: `awaiting_resolved_nfo_symbols`

Verdict:

`TB11_T24` passes as a safe quote-only collector implementation, but it has not captured live quotes yet. The current blocker is that the T23 batch is built from historical replay rows and lacks current NFO tradingsymbols. The next gate is `TB11_T25 CurrentNFOLegResolver`.
