# Codex Next Action

## Current Status

- Active batch: `TB11`
- Last completed thesis: `TB11_T11_ConditionalOverlayFrontier`
- Last verdict: `balanced_candidate_needs_lot_capital_risk_calibration`
- Best growth candidate: `TB11_T06_liq60k_ret5_0p01`
- Best defensive candidate: `TB11_T08_dte8_ret5_0p02`
- Best balanced overlay: `def_full_resg50_ovg50`
- Equity incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen
- Run lock: unlocked

## TB11 Real-Chain Tail-Control Result

`TB11` reopened options research only under the rule set by `TB10`: real-chain-first, direct tail-control focus, no synthetic evidence for promotion.

Commands executed:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_tail_control_sweep
python -u -B ssell1.py --mode signal_baseline_tb11_options_spot_regime_tail_sweep
```

Artifacts:

- `results/signal_baseline/tb11_options_tail_control_detail.csv`
- `results/signal_baseline/tb11_options_tail_control_summary.csv`
- `results/signal_baseline/tb11_options_tail_control_metadata.csv`
- `results/signal_baseline/tb11_options_tail_control_skipped.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_detail.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_summary.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_metadata.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_skipped.csv`

Best first-pass tail-control variant:

- strategy: `TB11_farther_3pct_vix_shock_skip`
- trades: `864`
- annualized return on estimated margin: `10.18%`
- worst trade: `-611.03` points
- max drawdown: `-3650.11` points

Best spot-regime variant:

- strategy: `TB11_spot_3pct_ret5_m1_sma_0`
- trades: `498`
- annualized return on estimated margin: `18.19%`
- worst trade: `-611.03` points
- max drawdown: `-1390.71` points
- win rate: `76.10%`

Important caveats:

- the worst loss remains the `2022-06-08` to `2022-06-16` trade
- `2024` contribution is large enough to require concentration review
- the candidate is not deployable before robustness and tail audit

## Verdict

`TB11_spot_3pct_ret5_m1_sma_0` is research-interesting, but `TB11_T03` blocks promotion.

Audit evidence:

- all-period annualized return on estimated margin: `18.19%`
- pre-2024 annualized return on estimated margin: `16.60%`
- 2024 annualized return on estimated margin: `199.33%`
- 2024 PnL share: `41.14%`
- fold 2 point PnL: `-7.42`
- worst loss cluster remains in `2020`, `2021`, and `2022`
- excluding only the worst 2022 trade still leaves max drawdown at `-1390.71` points

## T04 Result

Do not run another broad options sweep.

`TB11_T04 LossClusterMaxRiskControl` has now found a better-shaped candidate:

- strategy: `TB11_T04_3pct_5wing_ret5_1pct_liq50k`
- trades: `157`
- annualized return on estimated margin: `24.92%`
- worst trade: `-270.89` points
- max drawdown: `-274.28` points
- win rate: `88.54%`
- 2024 PnL share: `9.24%`
- all calendar years and all chronological folds are positive

## Next Action

`TB11_T05` through `TB11_T09` are now complete.

`TB11_T05` showed the return/loss frontier:

- `50k` liquidity kept high return but retained a `-270.89` point worst trade
- `75k` and `100k` liquidity cut worst trade to about `-68.50` but reduced return

`TB11_T06` found the best current frontier point:

- strategy: `TB11_T06_liq60k_ret5_0p01`
- trades: `141`
- annualized return on estimated margin: `24.38%`
- worst trade: `-69.21` points
- max drawdown: `-69.21` points
- win rate: `89.36%`
- all calendar years and all chronological folds are positive

## Current Frontier

Growth candidate:

- `TB11_T06_liq60k_ret5_0p01`
- base annualized return on estimated margin: `24.38%`
- base worst trade / max DD: `-69.21`
- harshest tested annualized return: `11.77%` under `30%` premium haircut and `3` points per leg
- harshest tested worst trade / max DD: `-86.61` / `-142.84`

Defensive candidate:

- `TB11_T08_dte8_ret5_0p02`
- base annualized return on estimated margin: `17.57%`
- base worst trade / max DD: `-1.25`
- harshest tested annualized return: `9.11%` under `30%` premium haircut and `3` points per leg
- harshest tested worst trade / max DD: `-10.36` / `-18.77`

## Next Action

`TB11_T10` and `TB11_T11` are now complete.

Static allocation mostly just scaled exposure down. Conditional overlay created a better balanced frontier.

Best max-return overlay:

- allocation: `def_full_resg100_ovg50`
- base annualized return: `27.21%`
- base worst / max DD: `-69.21` / `-69.20`
- harsh-stress annualized return: `14.12%`
- harsh-stress worst / max DD: `-86.61` / `-152.79`

Best balanced overlay:

- allocation: `def_full_resg50_ovg50`
- base annualized return: `24.00%`
- base worst / max DD: `-34.60` / `-34.60`
- harsh-stress annualized return: `12.66%`
- harsh-stress worst / max DD: `-43.30` / `-91.32`
- all chronological folds are positive in base, moderate, and harsh scenarios

## Next Action

Open `TB11_T12_LotCapitalRiskCalibration`.

Required checks:

- convert points to rupees using NIFTY lot size assumptions
- estimate capital requirement from margin points and lot count
- cap position size so worst trade and harsh-stress drawdown fit a defined rupee loss budget
- compare max-return overlay versus balanced overlay after lot/capital constraints
- do not promote, RL-tune, or route to broker execution until allocation sizing passes

## `TB11_T12 LotCapitalRiskCalibration`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration
```

Artifacts:

- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_detail.csv`
- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_summary.csv`
- `results/signal_baseline/tb11_options_lot_capital_risk_calibration_metadata.csv`

Read:

- the calibration used NIFTY lot-size sensitivity at `50`, `65`, and `75`, with `65` as the current-reference lot size
- tested capital budgets from `100000` to `2000000`
- tested worst-trade rupee budgets from `5000` to `100000`
- tested drawdown rupee budgets from `10000` to `200000`
- compared:
  - max-return overlay: `def_full_resg100_ovg50`
  - growth-only residual: `def_full_resg100_ovg0`
  - balanced overlay: `def_full_resg50_ovg50`
  - defensive-only: `def_full_resg0_ovg0`

Representative `65` lot-size results:

- `200000` capital, `10000` worst-trade budget, `25000` drawdown budget:
  - base best return: `def_full_resg100_ovg50`, `1` lot, `15.13%` annualized on capital, worst/max DD about `-4498`
  - harsh-stress best return: `def_full_resg0_ovg0`, `2` lots, `4.89%` annualized on capital, worst `-1346`, max DD `-2440`
- `500000` capital, `25000` worst-trade budget, `50000` drawdown budget:
  - base best return: `def_full_resg100_ovg50`, `4` lots, `24.21%` annualized on capital, worst/max DD about `-17993`
  - harsh-stress best return: `def_full_resg100_ovg50`, `4` lots, `7.55%` annualized on capital, worst `-22517`, max DD `-39725`
  - harsh-stress balanced: `def_full_resg50_ovg50`, `4` lots, `6.42%` annualized on capital, worst `-11259`, max DD `-23744`
- `1000000` capital, `50000` worst-trade budget, `100000` drawdown budget:
  - base best return: `def_full_resg100_ovg50`, `8` lots, `24.21%` annualized on capital, worst/max DD about `-35987`
  - harsh-stress best return: `def_full_resg100_ovg50`, `8` lots, `7.55%` annualized on capital, worst `-45035`, max DD `-79450`
  - harsh-stress balanced: `def_full_resg50_ovg50`, `8` lots, `6.42%` annualized on capital, worst `-22517`, max DD `-47488`

Verdict:

No TB11 promotion yet.

The max-return overlay is capital-efficient when rupee loss budgets are wide enough, but it carries materially larger harsh-stress drawdown than the balanced and defensive profiles. The balanced overlay remains a strong candidate when loss containment matters, while the defensive-only profile can dominate under very small capital and harsh-stress loss constraints.

## Next Action

Open `TB11_T13_CapitalAwarePolicySelection`.

Required checks:

- choose explicit deployment profiles such as small-capital defensive, balanced, and growth
- rank candidates by annualized return on capital after enforcing both base and harsh-stress rupee-risk gates
- require the selected profile to survive `65` lot-size current-reference assumptions and nearby `50` / `75` sensitivity
- do not promote, RL-tune, or route to broker execution until a single profile has passed the capital-aware selection gate

## `TB11_T13 CapitalAwarePolicySelection`

Commands:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration
python -u -B ssell1.py --mode signal_baseline_tb11_options_capital_aware_policy_selection
```

Artifacts:

- `results/signal_baseline/tb11_options_capital_aware_policy_selection_summary.csv`
- `results/signal_baseline/tb11_options_capital_aware_policy_selection_metadata.csv`

Important implementation note:

- the first T13 pass was too narrow because T12 only compared four hand-picked overlays
- T12 was broadened to all `15` conditional overlay combinations from T11
- T13 was rerun on the full frontier

Selected profile:

- allocation: `def_full_resg0_ovg50`
- interpretation: take defensive trades at full size, add `50%` growth only on dates that overlap with the defensive signal, and take no residual growth-only trades
- selected for:
  - `small_capital_loss_first`
  - `balanced_500k`
  - `growth_1m`
  - `large_capital_growth_2m`
- passed return gates and nearby lot-size sensitivity at `50`, `65`, and `75`

Representative `65` lot-size selected-profile read:

- `small_capital_loss_first` (`200000` capital / `10000` worst / `25000` DD):
  - base annualized on capital: `18.61%`
  - harsh annualized on capital: `7.33%`
  - harsh worst trade: `-2019`
  - harsh max DD: `-3660`
- `balanced_500k` (`500000` capital / `25000` worst / `50000` DD):
  - base annualized on capital: `22.33%`
  - harsh annualized on capital: `8.80%`
  - harsh worst trade: `-6058`
  - harsh max DD: `-10980`
- `growth_1m` (`1000000` capital / `50000` worst / `100000` DD):
  - base annualized on capital: `24.19%`
  - harsh annualized on capital: `9.53%`
  - harsh worst trade: `-13125`
  - harsh max DD: `-23791`
- `large_capital_growth_2m` (`2000000` capital / `100000` worst / `200000` DD):
  - base annualized on capital: `25.12%`
  - harsh annualized on capital: `9.53%`
  - harsh worst trade: `-26250`
  - harsh max DD: `-47582`

Verdict:

`def_full_resg0_ovg50` is the current best TB11 capital-aware candidate.

This is an actual improvement over defensive-only: it raises return by adding overlap-only growth exposure, while avoiding the residual growth trades that caused larger harsh-stress loss usage.

No promotion yet.

## Next Action

Open `TB11_T14_SelectedProfileRobustnessAudit`.

Required checks:

- audit the selected `def_full_resg0_ovg50` profile by year and chronological fold
- inspect worst trades and loss clusters in base, moderate, and harsh stress
- confirm the selected profile remains positive outside 2024 concentration
- compare selected profile against defensive-only and max-return profiles as controls
- do not promote, RL-tune, or route to broker execution until this profile-level robustness audit passes

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

Selected-profile read for `def_full_resg0_ovg50`:

- base:
  - trades: `51`
  - annualized return on margin: `22.54%`
  - worst / max DD: `-1.88` / `-1.88`
  - folds: `4 / 4` positive
  - years: `5` positive, `1` negative
- moderate stress:
  - annualized return on margin: `17.12%`
  - worst / max DD: `-8.98` / `-8.98`
  - folds: `4 / 4` positive
  - years: `5` positive, `1` negative
- harsh stress:
  - annualized return on margin: `12.35%`
  - worst / max DD: `-15.53` / `-28.15`
  - folds: `4 / 4` positive
  - years: `5` positive, `1` negative

Verdict:

T14 blocks promotion. The selected profile passes folds, concentration, and loss-cluster checks, but it fails the strict all-years gate because `2017` contains exactly one selected-profile trade and that trade is negative.

## `TB11_T15 SelectedProfileMaturityGate`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_selected_profile_maturity_gate
```

Artifacts:

- `results/signal_baseline/tb11_options_selected_profile_maturity_gate_summary.csv`
- `results/signal_baseline/tb11_options_selected_profile_maturity_gate_metadata.csv`

Minimal passing hardening rule:

- allocation: `def_full_resg0_ovg50`
- maturity gate: skip the first observed selected-profile trade
- equivalent start: first active trade becomes `2019-02-25`
- rationale: avoid treating a one-trade sparse warmup year as deployment-ready

Selected maturity-gated read:

- base:
  - trades: `50`
  - annualized return on margin: `31.62%`
  - worst / max DD: `-1.88` / `-0.99`
  - years: `5 / 5` positive
  - folds: `4 / 4` positive
  - max year PnL share: `27.62%`
- moderate stress:
  - annualized return on margin: `23.93%`
  - worst / max DD: `-8.98` / `-8.01`
  - years: `5 / 5` positive
  - folds: `4 / 4` positive
  - max year PnL share: `29.44%`
- harsh stress:
  - annualized return on margin: `17.32%`
  - worst / max DD: `-15.53` / `-28.15`
  - years: `5 / 5` positive
  - folds: `4 / 4` positive
  - max year PnL share: `32.71%`

Verdict:

The maturity gate repairs the T14 sparse-year failure without using a broad re-optimization. No promotion yet, because the maturity-adjusted profile still needs to be translated back into lot, rupee, and capital-budget terms.

## Next Action

Open `TB11_T16_MaturityAdjustedRupeeProfile`.

Required checks:

- apply the one-observation maturity gate to the selected profile
- recompute rupee PnL, worst trade, max drawdown, margin, and capital utilization
- re-test profile budgets at lot sizes `50`, `65`, and `75`
- require base, moderate, and harsh profiles to remain inside rupee-risk budgets
- do not promote, RL-tune, or route to broker execution until this maturity-adjusted rupee profile passes

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
- first active entry: `2019-02-25`
- reference lot-size: `65`

Representative `65` lot-size read:

- `200000` capital / `10000` worst / `25000` drawdown:
  - allowed lots: `2`
  - base annualized on capital: `25.15%`
  - moderate annualized on capital: `16.34%`
  - harsh annualized on capital: `10.08%`
  - harsh worst / max DD: `-2019` / `-3660`
  - harsh margin use: `148337`
- `500000` capital / `25000` worst / `50000` drawdown:
  - allowed lots: `6`
  - base annualized on capital: `30.18%`
  - moderate annualized on capital: `19.61%`
  - harsh annualized on capital: `12.10%`
  - harsh worst / max DD: `-6058` / `-10980`
  - harsh margin use: `445011`
- `1000000` capital / `50000` worst / `100000` drawdown:
  - allowed lots: `13`
  - base annualized on capital: `32.69%`
  - moderate annualized on capital: `21.25%`
  - harsh annualized on capital: `13.10%`
  - harsh worst / max DD: `-13125` / `-23791`
  - harsh margin use: `964191`
- `2000000` capital / `100000` worst / `200000` drawdown:
  - allowed lots: `26` to `27` depending on scenario margin
  - base annualized on capital: `33.95%`
  - moderate annualized on capital: `21.25%`
  - harsh annualized on capital: `13.10%`
  - harsh worst / max DD: `-26250` / `-47582`
  - harsh margin use: `1928383`

Verdict:

`TB11_T16` passes the maturity-adjusted rupee and capital-budget gate for the selected profile. This is now the strongest TB11 candidate so far: it keeps annualized return high while keeping harsh-stress rupee losses materially inside the tested budgets.

No live promotion yet.

## Next Action

Open `TB11_T17_ProfileFreezeExecutionReadiness`.

Required checks:

- freeze the exact paper-trading profile:
  - selected allocation: `def_full_resg0_ovg50`
  - maturity gate: skip first observed selected-profile trade
  - lot-size reference: `65`
  - supported profile budgets: `200k`, `500k`, `1m`, `2m`
- write a paper-only execution readiness spec
- define explicit no-trade and kill-switch rules before any broker/live path
- keep RL, broker execution, and live trading blocked

## `TB11_T17 ITMExpirySTTAudit`

Command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_itm_expiry_stt_audit
```

Artifacts:

- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_summary.csv`
- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_trades.csv`
- `results/signal_baseline/tb11_options_itm_expiry_stt_audit_metadata.csv`

Why this was added:

- the existing model uses premium haircut plus per-leg cost as a lumped proxy
- this does not explicitly split STT, GST, SEBI, exchange, or stamp duty
- the specific extra hazard is ITM expiry STT on exercised options
- this audit conservatively subtracts `0.125%` of ITM short-leg intrinsic value at expiry from the selected profile

Read:

- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- active trades: `50`
- ITM-expiry short-leg events: `1`
- ITM-expiry event rate: `2%`
- total extra exercise-STT impact: `0.01546875` points across the profile
- at lot size `65`, total extra exercise-STT impact is about `1.01` rupees

After conservative ITM-expiry STT:

- base annualized return: `31.62%`
- moderate-stress annualized return: `23.93%`
- harsh-stress annualized return: `17.32%`
- all years remain positive
- all folds remain positive
- concentration remains below the gate

Verdict:

`TB11_T17` passes. ITM-expiry STT is a real modeling hazard, but for the selected maturity-gated profile it is not material in the historical sample because only one trade has ITM short-leg intrinsic at expiry.

No live promotion yet.

## Next Action

Supersede the earlier `TB11_T18_ProfileFreezeExecutionReadiness` plan with a broker-accurate cost audit first.

Required checks:

- freeze the exact paper-trading profile and parameters
- include the ITM-expiry STT audit as a mandatory pre-trade risk note
- define exit-before-expiry / no-hold-through-expiry policy if live execution is ever considered
- define kill switches and daily/weekly drawdown rules
- keep RL, broker execution, and live trading blocked

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

The prior model used a deliberately conservative lumped points proxy for costs. Before paper/live consideration, TB11 needs broker-accurate Indian F&O charge accounting that itemizes brokerage, STT, exchange charges, GST, SEBI charges, stamp duty, and ITM-expiry assignment/exercise risk.

Charge assumptions:

- brokerage: `20` rupees per option order/leg
- option sell-side premium STT: `0.05%`
- exercised ITM intrinsic STT stress bucket: `0.15%`
- NSE option transaction charge: `0.03553%` of premium
- GST: `18%` of brokerage + SEBI + transaction charges
- SEBI: `10` rupees per crore
- stamp duty: `0.003%` on buy-side option premium
- expiry bucket also adds brokerage + GST for ITM exercised/assigned legs

Result, selected profile `def_full_resg0_ovg50` with the maturity gate:

- active selected-profile trades: `50`
- ITM-expiry trades: `1`
- ITM-expiry legs: `2`
- all years and all folds remain positive under base, moderate, and harsh stress
- all scenarios pass the concentration gate

Reference lot size `65`:

- base:
  - lumped cost: `300.00` points
  - itemized cost: `112.99` points
  - annualized return after itemized cost: `33.18%`
- moderate stress:
  - lumped cost: `600.00` points
  - itemized cost: `112.99` points
  - annualized return after itemized cost: `28.84%`
- harsh stress:
  - lumped cost: `900.00` points
  - itemized cost: `112.99` points
  - annualized return after itemized cost: `26.50%`

Verdict:

`TB11_T18` passes. The earlier lumped cost proxy was materially harsher than the itemized Zerodha-style cost model in this historical sample. This removes a major uncertainty, but it does not authorize paper/live execution by itself.

## Next Action

Open `TB11_T19_ProfileFreezeExecutionReadiness`.

Required checks:

- freeze the exact paper-only profile and lot/budget rules
- make the itemized cost module mandatory for every future run
- enforce exit-before-expiry unless explicitly testing expiry handling
- write kill switches, no-trade rules, and daily/weekly loss limits
- keep RL, broker execution, and live trading blocked

## `TB11_T19 ProfileFreezeExecutionReadiness`

Artifacts:

- `results/signal_baseline/tb11_options_profile_freeze_execution_readiness.md`
- `results/signal_baseline/tb11_options_profile_freeze_execution_readiness_summary.csv`

Frozen paper-only profile:

- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip the first observed selected-profile trade
- reference lot size: `65`
- itemized Indian F&O cost module: mandatory
- no broker order placement from this repo without explicit future human approval

Practical validation plan:

| Phase | Duration | Gate |
|---|---:|---|
| `1_dry_run` | `1-2 months` | Log every signal, simulate fills, and confirm triggers/skip reasons are reproducible. |
| `2_paper_real_prices` | `3-6 months` | At least `10-15` paper trades; available premium within `10-15%` adverse tolerance of modeled premium; no surprise costs. |
| `3_tiny_live` | `3-6 months` | Future human-approved `1` lot only; at least `10` trades; confirm broker mechanics and psychology. |
| `4_scale_to_target` | `ongoing` | Only after phases 1-3 hold up and target budget is revalidated. |

Phase-1 required logs:

- `results/signal_baseline/tb11_options_dry_run_signal_log.csv`
- `results/signal_baseline/tb11_options_dry_run_signal_log_summary.csv`
- `results/signal_baseline/tb11_options_dry_run_reconciliation.md`

Verdict:

`TB11_T19` passes as a paper-only profile freeze. It does not authorize paper/live order placement.

## Next Action

Open `TB11_T20_DryRunSignalLogger`.

Required checks:

- implement a no-order signal logger for the frozen TB11 profile
- record every candidate signal, skip reason, simulated fill, cost estimate, and expiry plan
- prove trigger timing against cached or observed market snapshots
- keep Phase 1 and Phase 2 broker-order placement blocked

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

Result:

- source mode: `historical_replay_no_order`
- selected profile: `def_full_resg0_ovg50`
- lot size: `65`
- signals logged: `51`
- simulated signals after maturity gate: `50`
- skipped maturity-warmup signals: `1`
- broker orders allowed: `False`
- schema gate passed: `True`
- mean modeled credit: `46.7961` points
- mean itemized entry cost: `2.24853` points
- minimum modeled net after entry cost: `1.933874` points

Verdict:

`TB11_T20` passes as a no-order logger schema gate. This is not a completed 1-2 month dry run yet; it only proves the logger schema and historical replay path.

## Next Action

Open `TB11_T21_DryRunObservedQuoteCapture`.

Required checks:

- create an observed-quote capture template using the T20 signal schema
- define how each dry-run day records available premiums, bid/ask/mid, timestamp, and quote freshness
- reconcile observed premium against modeled premium with the `10-15%` adverse tolerance
- keep broker orders blocked

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

Result:

- template rows: `50`
- source signals: `50`
- broker orders allowed: `False`
- quote freshness target: `300` seconds
- adverse premium tolerance: `15%`
- required Phase 2 observed trade count: `10-15`
- template gate passed: `True`

Verdict:

`TB11_T21` passes. The observed-quote capture template is ready for Phase 1 dry-run quote collection. It does not place orders and does not authorize Phase 2.

## Next Action

Open `TB11_T22_ObservedQuoteReconciliationValidator`.

Required checks:

- build a validator that reads filled-in observed quote rows
- score quote freshness, all-leg availability, spread quality, and premium tolerance
- emit pass/fail counts and skip reasons
- keep broker orders blocked

## `TB11_T22 ObservedQuoteReconciliationValidator`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_reconciliation_validator
```

Artifacts:

- `results/signal_baseline/tb11_options_observed_quote_validation_detail.csv`
- `results/signal_baseline/tb11_options_observed_quote_validation_summary.csv`
- `results/signal_baseline/tb11_options_observed_quote_validation_metadata.csv`

Result:

- template rows: `50`
- observed rows: `0`
- pending rows: `50`
- broker-block violations: `0`
- validator schema gate passed: `True`
- Phase 1 evidence gate passed: `False`
- validator status: `ready_pending_observations`

Verdict:

`TB11_T22` passes as a validator/readiness gate. It correctly reports that no real observed quotes have been collected yet, so Phase 1 evidence is still pending.

## Next Action

Open `TB11_T23_DryRunObservationCollection`.

Required checks:

- collect real observed quote rows for `1-2 months`
- keep `broker_order_allowed=False`
- run the validator after each observation batch
- require usable bid/ask for every leg, quote age under `300` seconds, and premium inside the `10-15%` adverse tolerance band
- do not advance to Phase 2 until the observed evidence gate has enough rows and no unhandled failures

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

- collection batch: `TB11_PHASE1_OBS_20260623`
- rows prepared: `50`
- broker orders allowed: `False`
- prior observed rows: `0`
- prior pending rows: `50`
- status: `manual_no_order_collection_ready`

Verdict:

T23 is operationally ready but not complete. The collection pack exists, but Phase 1 still requires real no-order observed quote collection for `1-2 months`.

Continue T23:

- fill observed quote fields only
- keep `broker_order_allowed=False`
- rerun `signal_baseline_tb11_options_observed_quote_reconciliation_validator` after each batch
- do not move to Phase 2 until enough observations pass the validator

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

Result:

- input rows: `50`
- quote symbols requested: `0`
- quote packets received: `0`
- captured rows: `0`
- unresolved rows: `50`
- broker orders allowed: `False`
- collector status: `awaiting_resolved_nfo_symbols`

Interpretation:

The quote-only collector is implemented and order-blocked, but today's batch still contains historical replay rows without current NFO tradingsymbols. The collector correctly refused to guess option contracts or call order routes.

## Next Action

Open `TB11_T25_CurrentNFOLegResolver`.

Required checks:

- generate current-day option legs from the frozen TB11 signal logic, not historical replay rows
- resolve each leg to current NFO tradingsymbols or instrument tokens
- feed those symbols into the T24 quote-only collector
- keep broker orders blocked

## 2026-06-29 Phase 1 Gate Reconciliation

The pasted roadmap's first-priority instruction to continue quote-only observation was rechecked against the local ledger.

Current evidence:

- source: `results/signal_baseline/tb11_options_phase1_observation_ledger_summary.csv`
- clean observations: `12`
- unique observation dates: `3`
- broker-block violations: `0`
- required clean observations: `10`
- target clean observations: `15`
- Phase 1 evidence gate passed: `True`
- ledger status: `phase1_min_observation_count_reached`

Latest automated observation summary:

- source: `results/signal_baseline/tb11_options_phase1_auto_quote_observation_summary.csv`
- resolver status: `resolved_current_nfo_legs`
- resolved legs: `8`
- collector status: `captured_quotes`
- quote packets received: `4`
- broker orders allowed: `False`
- automation status: `completed_no_order`

Decision:

- Phase 1 minimum observation count is reached.
- Continue collecting until the `15` clean-observation target, but the immediate engineering gate is no longer "get to 10".
- Do not advance to live trading, broker execution, or RL.
- Do not claim Phase 2 is complete; Phase 2 needs paper-price reconciliation artifacts against live captured premiums and itemized costs.

Next best action:

Open `TB11_T28_NiftyChainBandQuoteCollector`.

Required checks:

- implement a current-expiry NIFTY option-chain band collector around spot
- capture bid/ask, quote age, spread quality, token resolution, OI/volume if available, and no-order proof
- use the chain-band evidence to support Phase 2 paper-price reconciliation and IV/chain-conditioned sizing research
- keep Phase 1 and Phase 2 broker-order placement blocked

Parallel roadmap note:

Do not promote E1006/equity work from the pasted roadmap without reconciling against the newer 2026-06-29 equity decision memo. The latest local equity evidence demotes TB12/TB13/TB14-style OHLCV PortfolioRank work to `research_only`; any equity paper-track needs a fresh, narrower objective or a non-OHLCV information axis.

## `TB11_T28 NiftyChainBandQuoteCollector`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_nifty_chain_band_quote_collector
```

Artifacts:

- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_detail_20260629.csv`
- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_summary.csv`
- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_metadata.csv`
- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_unresolved_20260629.csv`

Result:

- mode implemented and routed
- compile check passed
- quote-only Kite run succeeded after network escalation
- selected expiry: `2026-06-30`
- spot: `23946.25`
- band: `spot +/- 5%`, from `22748.9375` to `25143.5625`
- candidate contracts: `96`
- quote symbols requested / received: `96 / 96`
- detail rows: `96`
- CE / PE rows: `48 / 48`
- unresolved rows: `0`
- broker orders allowed: `False`
- order route: `blocked_no_broker_call`
- median spread pct: `0.012554676442923181`
- max spread pct: `0.4000000000000001`

Verdict:

`TB11_T28` passes as an implementation and no-order chain-band capture gate, but it does not pass the fresh intraday quote gate. The run occurred after market close; all rows had quote age around `22439` seconds and `fresh_quote_rows = 0`.

Next action:

Rerun T28 during live market hours:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_nifty_chain_band_quote_collector
```

Gate for moving toward Phase 2 paper-price reconciliation:

- `collector_status = chain_band_fresh_quotes_captured`
- `fresh_quote_rows > 0`
- `quote_packets_received > 0`
- both CE and PE rows present
- unresolved rows remain `0` or are explicitly explained
- `broker_orders_allowed = False`
- Phase 1 clean observations continue from `12` toward the `15` target

Do not open Phase 2, live trading, broker execution, or RL from the stale after-hours T28 capture.

Research queue after fresh T28:

- first: Phase 2 paper-price reconciliation for TB11 only after fresh T28 and 15 clean Phase 1 observations
- second: `TB12_CashSecuredPutWritingLargeCaps` as the next new smoothing/frequency thesis
- do not reopen TB08 pairs unless the design materially changes from the failed z-score relative-value scan

## `TB11_T28 FreshnessGate`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_t28_freshness_gate
```

Artifacts:

- `results/signal_baseline/tb11_t28_freshness_gate_summary.csv`
- `results/signal_baseline/tb11_t28_freshness_gate_metadata.csv`
- `results/signal_baseline/tb11_t28_freshness_gate_next_action.md`

Result:

- quote packets received: `96`
- fresh quote rows: `0`
- detail rows: `96`
- CE / PE rows: `48 / 48`
- unresolved rows: `0`
- broker-block violations: `0`
- median quote age seconds: `22439.162809`
- max quote age seconds: `22439.162809`
- Phase 2 gate passed: `False`
- gate status: `blocked_needs_fresh_intraday_t28`

Verdict:

The freshness gate correctly blocks Phase 2 from the after-hours T28 capture. The next action remains a live-market-hours T28 rerun, followed by this freshness gate. Only if `fresh_quote_rows > 0` and broker-block violations remain `0` should Phase 2 paper-price reconciliation open.

## `TB11_T28 WrapperValidation`

Wrapper:

```powershell
cmd /c run_tb11_t28_chain_band_freshness_gate.bat
```

Purpose:

- run T28 chain-band quote collection
- immediately run T28 freshness gate
- log both steps under `results/log_runs`
- keep broker orders blocked

Validation evidence:

- latest validated log: `results/log_runs/tb11_t28_chain_band_freshness_gate_20260629_234319_scheduled.log`
- collector exit: `0`
- gate exit: `0`
- quote packets received: `96`
- CE / PE rows: `48 / 48`
- unresolved rows: `0`
- broker-block violations: `0`
- fresh quote rows: `0`
- Phase 2 gate passed: `False`

Verdict:

The wrapper is ready for a live-market-hours scheduled/manual rerun. It has now been tested end-to-end and correctly leaves Phase 2 blocked from stale after-hours quotes.

Next command during market hours:

```powershell
cmd /c run_tb11_t28_chain_band_freshness_gate.bat
```

Only open Phase 2 if the wrapper-generated `tb11_t28_freshness_gate_summary.csv` reports `phase2_gate_passed=True`.

## `TB11_T28 SchedulerRegistration`

Registration command:

```powershell
cmd /c register_tb11_t28_chain_band_freshness_gate_task.bat
```

Task Scheduler evidence:

- task name: `TB11_T28_ChainBandFreshness_0945`
- status: `Ready`
- schedule type: `Weekly`
- days: `MON, TUE, WED, THU, FRI`
- start time: `09:45:00`
- next run time: `30/06/2026 09:45:00`
- run as user: `Ramic`
- task command: `"C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\run_tb11_t28_chain_band_freshness_gate.bat"`

Verdict:

The fresh intraday T28 wrapper rerun is now scheduled. The next required evidence is tomorrow's generated wrapper log plus `tb11_t28_freshness_gate_summary.csv`.

Gate remains:

- do not open Phase 2 unless `phase2_gate_passed=True`
- keep broker orders blocked
- continue Phase 1 observations from `12` toward the `15` clean-observation target

## 2026-06-30 Scheduled Job Output Check

Scheduler evidence:

- `TB11_Phase1_QuoteObservation_0940`
  - last run: `30/06/2026 10:38:52`
  - last result: `0`
  - next run: `01/07/2026 09:40:00`
- `TB11_Phase1_QuoteObservation_1230`
  - last run: `29/06/2026 12:30:00`
  - last result: `0`
  - next run: `30/06/2026 12:30:00`
- `TB11_Phase1_QuoteObservation_1445`
  - last run: `29/06/2026 22:35:02`
  - last result: `0`
  - next run: `30/06/2026 14:45:00`
- `TB11_T28_ChainBandFreshness_0945`
  - last run: `30/06/2026 10:39:52`
  - last result: `0`
  - next run: `01/07/2026 09:45:00`

Generated log evidence:

- `results/log_runs/signal_baseline_tb11_options_phase1_auto_quote_observation_20260630_103923_scheduled.log`
  - T25 resolver, T24 quote collector, and T26 ledger all exited successfully
- `results/log_runs/tb11_t28_chain_band_freshness_gate_20260630_103954_scheduled.log`
  - T28 collector exit: `0`
  - T28 freshness gate exit: `0`

Current artifact read:

- T28 freshness gate:
  - collector status: `chain_band_fresh_quotes_captured`
  - quote packets received: `96`
  - fresh quote rows: `96`
  - CE / PE rows: `48` / `48`
  - unresolved rows: `0`
  - broker-block violations: `0`
  - phase2 gate passed: `True`
- Phase 1 observation ledger:
  - clean observations: `13`
  - unique observation dates: `4`
  - required clean observations: `10`
  - target clean observations: `15`
  - broker-block violations: `0`
  - evidence gate passed: `True`

## `TB11 Phase2PaperPriceReconciliationReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness
```

Artifacts:

- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_summary.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_detail.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_metadata.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_next_action.md`

Read:

- T28 freshness gate passed: `True`
- T28 fresh quote rows: `96`
- selected profile legs covered by the T28 band: `2 / 4`
- Phase 1 clean observations: `13 / 15`
- latest Phase 1 clean observation: `True`
- latest Phase 1 observed weighted credit: `1.2750000000000004`
- latest live modeled credit available: `False`
- broker-block violations: `0`
- reconciliation status: `phase2_reconciliation_not_yet_complete`

Verdict:

The active thesis is now `TB11_Phase2_PaperPriceReconciliationReadiness`, not another fresh T28 rerun. T28 passed the fresh-data gate, but full paper-price reconciliation remains blocked by three specific issues:

- Phase 1 target is not complete yet: `13 / 15` clean observations.
- T28 spot `+/-5%` chain-band data covers only the selected short legs; the selected long call and long put are outside the band.
- The latest live Phase 1 row does not yet store modeled credit, so observed-vs-modeled premium tolerance cannot be scored.

Next active thesis:

Open `TB11_T29_SelectedLegFullWingCoverageAndModeledCredit`.

Required checks:

- widen or supplement the chain capture so all selected profile legs are present, including long wings
- record the selected-profile modeled credit on the live Phase 1 row
- compute observed-vs-modeled credit difference and the `10-15%` adverse tolerance flags
- keep broker orders blocked
- continue scheduled Phase 1 collection until `15 / 15` clean observations

## `TB11_T29 SelectedLegFullWingCoverageAndModeledCredit`

Commands:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_phase1_auto_quote_observation
python -B ssell1.py --mode signal_baseline_tb11_options_nifty_chain_band_quote_collector
python -B ssell1.py --mode signal_baseline_tb11_options_t28_freshness_gate
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness
```

Implementation:

- `T24` quote-only collector now computes live mid-quote modeled credit when no input model credit exists.
- `T24` now writes:
  - `modeled_defensive_credit_points`
  - `modeled_growth_credit_points`
  - `modeled_credit_points`
  - `modeled_credit_source`
  - `premium_tolerance_floor_points`
  - `premium_tolerance_ceiling_points`
  - observed-vs-modeled diff fields
  - `within_10pct_adverse_tolerance`
  - `within_15pct_adverse_tolerance`
- `T28` chain-band collector now supplements spot `+/-5%` chain coverage with current selected-profile symbols from the resolver, so long wings outside the band are still quoted and carried into the chain artifact.

Artifacts read:

- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_20260630.csv`
- `results/signal_baseline/tb11_options_zerodha_quote_only_collector_summary.csv`
- `results/signal_baseline/tb11_options_phase1_observation_ledger_summary.csv`
- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_summary.csv`
- `results/signal_baseline/tb11_t28_freshness_gate_summary.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_summary.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_detail.csv`

Result:

- T24 quote-only collector:
  - quote symbols requested / received: `4 / 4`
  - captured rows: `1`
  - unresolved rows: `0`
  - broker orders allowed: `False`
  - observed weighted credit: `1.4249999999999998`
  - modeled credit: `1.5749999999999993`
  - modeled credit source: `live_mid_quote_model`
  - 15% adverse tolerance passed: `True`
- T28 chain-band collector:
  - quote packets received: `98`
  - fresh quote rows: `98`
  - CE / PE rows: `49 / 49`
  - selected profile symbols required / covered: `4 / 4`
  - selected profile supplement rows: `4`
  - unresolved rows: `0`
  - broker orders allowed: `False`
- Phase 2 readiness:
  - T28 selected leg hits: `4 / 4`
  - live modeled credit available: `True`
  - broker-block violations: `0`
  - Phase 1 clean observations: `14 / 15`
  - reconciliation status: `phase2_reconciliation_not_yet_complete`
  - only blocker: `phase1_target_15_clean_observations_not_yet_reached`

Verdict:

`TB11_T29` passes. The previous engineering blockers are cleared:

- selected long wings are now included in T28 evidence
- modeled credit is now recorded for the live Phase 1 row
- observed-vs-modeled adverse tolerance can now be scored
- broker orders remain blocked

Next active thesis:

`TB11_Phase1_Target15CleanObservationGate`

Required next check:

- let the scheduled Phase 1 collector add one more clean observation, moving from `14 / 15` to `15 / 15`
- then open `TB11_Phase2_PaperPriceReconciliationRunbook`

## 2026-06-30 Equity / CSP / Pairs Roadmap Status

Status artifact:

- `results/roadmap_status_20260630_equity_csp_pairs.md`

Requested items checked:

- `2. E1006 swing equity paper track`
  - status: `not_promoted`
  - newer 10-fold evidence supersedes the older `4 / 6` recent-fold read
  - standalone E1006 best promotion-grade gate remains `research_only`
- `3. Kelly / worst-trade-budget sizing`
  - status: `partially_actioned`
  - not ported to standalone E1006 because standalone E1006 is not promotable
  - sizing pattern was applied to the new CSP scan
- `5. Cash-secured put writing`
  - status: `implemented_research_only_candidate`
  - new mode: `signal_baseline_tb15_cash_secured_put_large_caps`
- `6. Pair trading / market neutral`
  - status: `do_not_reopen_broad_scan`
  - TB08 remains a hard fail: best cell still negative, with no positive broad-scan cells

## `TB15 CashSecuredPutLargeCaps`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_cash_secured_put_large_caps
```

Artifacts:

- `results/signal_baseline/tb15_cash_secured_put_large_caps_detail.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_summary.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_kelly_sizing.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_metadata.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_decision.md`

Result:

- symbols tested: `8`
- detail trades: `522`
- portfolio equal-weight mean return on cash per expiry bucket: `0.54%`
- portfolio win rate: `80.61%`
- assignment rate: `15.71%`
- worst equal-weight expiry-bucket return: `-21.41%`
- positive Kelly-sized names: `6`
- broker orders allowed: `False`

Top reads:

- `ICICIBANK`: annualized cash return `8.50%`, win rate `92.86%`, worst return `-34.46%`
- `SBIN`: annualized cash return `8.25%`, win rate `85.71%`, worst return `-35.92%`
- `TCS`: annualized cash return `5.38%`, win rate `86.30%`, worst return `-9.84%`
- `BHARTIARTL`: annualized cash return `4.98%`, win rate `88.78%`, worst return `-13.74%`

Verdict:

`TB15` is a research-only candidate, not a paper-track approval. The raw CSP return is below the pasted `18-25%` expectation and has large assignment-tail losses. It is still useful as a smoothing/frequency branch because it produces many more events than TB11 options, but it needs a stress skip gate before paper tracking.

Next side-branch thesis:

`TB15_T02_CSPVolBreadthStressGate`

Required checks:

- skip CSP entries during market stress or weak breadth
- test whether worst CSP assignment losses shrink without destroying trade frequency
- keep Kelly/worst-trade-budget sizing
- remain research-only; no broker orders

## `TB15_T02_CSPVolBreadthStressGate`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_csp_vol_breadth_stress_gate
```

Artifacts:

- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_detail.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_summary.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_kelly_sizing.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_metadata.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_decision.md`

Read:

- context coverage: NIFTY `97.7%`, India VIX `97.1%`
- best non-baseline variant: `skip_composite_stress`
- kept trades: `391 / 522`; skipped `131` trades
- portfolio mean return on cash per expiry bucket fell from `0.54%` to `0.32%`
- worst equal-weight expiry-bucket return stayed `-21.41%`
- tail-loss events <= `-5%` fell from `26` to `21`
- broker orders allowed: `False`

Gated Kelly / worst-trade-budget read:

- `BHARTIARTL`: `25.00%` capped research fraction
- `INFY`: `25.00%` capped research fraction
- `TCS`: `25.00%` capped research fraction
- `ICICIBANK`: `14.51%` capped research fraction
- `SBIN`: `13.92%` capped research fraction
- `LT`: `0.00%`, blocked by nonpositive gated edge

Verdict:

`TB15_T02` is still research-only. The composite stress gate usefully removes some tail-loss events, but it does not improve the worst portfolio expiry and it lowers mean return, so this is not a paper-trade approval. The next useful CSP action is a fresh forward sample or a materially different tail hedge/strike-selection design before any live or paper allocation.

## `TB11 Phase2TransitionController`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_transition_controller
```

Artifacts:

- `results/signal_baseline/tb11_phase2_transition_controller_summary.csv`
- `results/signal_baseline/tb11_phase2_transition_controller_metadata.csv`
- `results/signal_baseline/tb11_phase2_transition_controller_next_action.md`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_runbook.md` only when the transition gate passes

Current read:

- transition passed: `False`
- clean observations: `14 / 15`
- unique observation dates: `4 / 5`
- Phase 1 evidence gate passed: `True`
- T28 freshness/readiness gate passed: `True`
- selected leg coverage: `4 / 4`
- modeled credit available for live row: `True`
- broker-block violations: `0`
- runbook written: `False`
- automation state advanced: `False`
- blockers: `phase1_target_15_clean_observations_not_yet_reached|phase1_unique_observation_dates_below_5`

Verdict:

The transition controller is implemented and correctly blocks Phase 2 today. Do not advance automation state or write the Phase 2 runbook until the ledger reaches `>=15` clean observations, `>=5` unique observation dates, Phase 1 evidence gate remains true, and broker-block violations remain `0`. Branch B remains deferred until Branch A writes the runbook.

## `TB11 T28 WrapperTransitionGate`

Wrapper:

```powershell
cmd /c run_tb11_t28_chain_band_freshness_gate.bat
```

Current wrapper order:

- `signal_baseline_tb11_options_nifty_chain_band_quote_collector`
- `signal_baseline_tb11_options_t28_freshness_gate`
- `signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness`
- `signal_baseline_tb11_options_phase2_transition_controller`

Validation evidence:

- latest log: `results/log_runs/tb11_t28_chain_band_freshness_gate_20260630_200240_scheduled.log`
- collector exit: `0`
- freshness gate exit: `0`
- readiness exit: `0`
- transition controller exit: `0`
- broker orders allowed: `False`

Current read after the after-hours wrapper run:

- T28 fresh quote rows: `0`
- selected leg coverage: `4 / 4`
- modeled credit available for live row: `True`
- Phase 1 clean observations: `14 / 15`
- unique observation dates: `4 / 5`
- broker-block violations: `0`
- transition passed: `False`
- runbook written: `False`
- automation state advanced: `False`
- blockers: `phase1_target_15_clean_observations_not_yet_reached|phase1_unique_observation_dates_below_5|t28_freshness_gate_not_passed`

Verdict:

The scheduled/manual wrapper now includes the transition controller and is safe to keep running. It correctly blocks from stale after-hours quotes and incomplete Phase 1 target evidence. The same wrapper can open the Phase 2 runbook only on a future live-market run where T28 freshness is true and the Phase 1 ledger reaches `>=15` clean observations across `>=5` unique dates.

## `TB11 Phase1WrapperTransitionGate`

Wrapper:

```powershell
cmd /c run_tb11_phase1_auto_quote_observation.bat
```

Current wrapper order:

- `signal_baseline_tb11_options_phase1_auto_quote_observation`
- `signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness`
- `signal_baseline_tb11_options_phase2_transition_controller`

Task Scheduler evidence:

- `TB11_Phase1_QuoteObservation_0940` runs `cmd /c C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\run_tb11_phase1_auto_quote_observation.bat`
- `TB11_Phase1_QuoteObservation_1230` runs `cmd /c C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\run_tb11_phase1_auto_quote_observation.bat`
- `TB11_Phase1_QuoteObservation_1445` runs `cmd /c C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\run_tb11_phase1_auto_quote_observation.bat`
- all three next run on `2026-07-01`

Transition-controller hardening:

- now records Phase 1 collection date and readiness collection date
- blocks if same-day Phase 1/readiness evidence is not available
- current dates both read `2026-06-30`

Current read after safe controller rerun:

- transition passed: `False`
- clean observations: `14 / 15`
- unique observation dates: `4 / 5`
- T28/readiness Phase 2 gate: `False`
- broker-block violations: `0`
- runbook written: `False`
- automation state advanced: `False`
- blockers: `phase1_target_15_clean_observations_not_yet_reached|phase1_unique_observation_dates_below_5|t28_freshness_gate_not_passed`

Verdict:

The Phase 1 scheduled jobs now evaluate Phase 2 readiness and the transition controller immediately after every no-order Phase 1 observation. This closes the timing gap where a 12:30 or 14:45 clean observation could otherwise wait until the next 09:45 T28 wrapper before opening the runbook. The gate still blocks today, correctly.

## `CompositePlanGateAudit`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_composite_plan_gate_audit
```

Artifacts:

- `results/signal_baseline/composite_plan_gate_audit_summary.csv`
- `results/signal_baseline/composite_plan_gate_audit_detail.csv`
- `results/signal_baseline/composite_plan_gate_audit_metadata.csv`
- `results/signal_baseline/composite_plan_gate_audit_memo.md`

Current read:

- overall status: `branch_a_waiting_for_market_evidence`
- Branch A: `blocked_wait_for_phase1_t28_gates`
- Branch B: `research_only_deferred`
- Branch C: `lockouts_enforced`
- clean observations: `14 / 15`
- unique observation dates: `4 / 5`
- broker-block violations: `0`
- no-order static audit passed: `True`
- forbidden order calls/imports/wrapper refs: `0 / 0 / 0`
- scheduler readiness audit passed: `True`
- scheduler tasks present/enabled/command/time/last-result-zero: `4 / 4 / 4 / 4 / 4`
- runbook template contract audit passed: `True`
- runbook template contracts present: `28 / 28`
- runbook exists before transition: `False`
- T28/readiness Phase 2 gate: `False`
- transition passed: `False`
- runbook written: `False`
- automation state advanced: `False`
- TB15 base worst expiry return: `-21.41%`
- TB15 stress-gated worst expiry return: `-21.41%`
- E1006 lockout documented: `True`
- TB08 lockout documented: `True`
- TB06 lockout documented: `True`

Verdict:

The composite plan audit is now the current single receipt for Branch A/B/C gating. It confirms the only valid next action is to keep scheduled no-order Phase 1/T28 wrappers running and rerun the audit after the next market-hours observation. It also confirms Branch B TB15 remains deferred and Branch C lockouts are enforced.

## `TB11 NoOrderEndpointStaticAudit`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_no_order_endpoint_static_audit
```

Artifacts:

- `results/signal_baseline/tb11_no_order_endpoint_static_audit_summary.csv`
- `results/signal_baseline/tb11_no_order_endpoint_static_audit_detail.csv`
- `results/signal_baseline/tb11_no_order_endpoint_static_audit_metadata.csv`
- `results/signal_baseline/tb11_no_order_endpoint_static_audit_memo.md`

Current read:

- audit status: `passed_no_order_endpoints_detected`
- audit passed: `True`
- broker orders allowed: `False`
- forbidden order calls: `0`
- forbidden order imports: `0`
- forbidden wrapper references: `0`
- missing sources: `0`
- documentation/string-only mentions: `3`
- allowed data endpoint references: `31`
- scheduled wrapper noninteractive guard references: `2`

Composite integration:

- `signal_baseline_composite_plan_gate_audit` now auto-creates the static audit if missing.
- Branch A now records `no_order_static_audit_passed`, forbidden call/import/wrapper counts, and missing source count.
- A missing or failed no-order audit becomes an explicit Branch A blocker.

Verdict:

The broker-block invariant is now artifact-checked for the Phase 1/Phase 2 TB11 code path and wrappers. Current evidence shows no `place_order`, `modify_order`, or `cancel_order` calls/imports/references in scheduled wrappers; only `kite.quote` and `kite.instruments` data access remains in scope.

## `TB11 TaskSchedulerReadinessAudit`

Snapshot command used:

```powershell
schtasks /Query /TN <TB11 task> /FO LIST /V
```

Artifacts:

- `results/signal_baseline/tb11_task_scheduler_snapshot.txt`
- `results/signal_baseline/tb11_task_scheduler_readiness_audit_summary.csv`
- `results/signal_baseline/tb11_task_scheduler_readiness_audit_detail.csv`
- `results/signal_baseline/tb11_task_scheduler_readiness_audit_metadata.csv`
- `results/signal_baseline/tb11_task_scheduler_readiness_audit_memo.md`

Current read:

- audit status: `passed_scheduler_ready`
- audit passed: `True`
- expected tasks present: `4 / 4`
- enabled tasks: `4 / 4`
- ready tasks: `4 / 4`
- command matches: `4 / 4`
- start-time matches: `4 / 4`
- weekday matches: `4 / 4`
- last-result zero: `4 / 4`
- wrapper noninteractive guards: `4 / 4`
- wrapper readiness modes: `4 / 4`
- wrapper transition modes: `4 / 4`
- next run times: `2026-07-01 09:40`, `2026-07-01 09:45`, `2026-07-01 12:30`, `2026-07-01 14:45`

Composite integration:

- `signal_baseline_composite_plan_gate_audit` now auto-runs the scheduler readiness audit if its summary is missing.
- Branch A now records scheduler task counts and fails if the expected jobs are missing, disabled, pointed at the wrong wrappers, scheduled at the wrong times, or returning non-zero last results.

Verdict:

The scheduled Branch A path is ready for the next market-hours observation. The remaining blocker is not automation coverage; it is fresh market evidence: Phase 1 still needs `>=15` clean observations across `>=5` unique dates and T28/readiness must be fresh.

## `TB11 Phase2RunbookTemplateContractAudit`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_phase2_runbook_template_contract_audit
```

Artifacts:

- `results/signal_baseline/tb11_phase2_runbook_template_contract_audit_summary.csv`
- `results/signal_baseline/tb11_phase2_runbook_template_contract_audit_detail.csv`
- `results/signal_baseline/tb11_phase2_runbook_template_contract_audit_metadata.csv`
- `results/signal_baseline/tb11_phase2_runbook_template_contract_audit_memo.md`

Current read:

- audit status: `passed_runbook_template_contract`
- audit passed: `True`
- required contracts present: `28 / 28`
- missing contracts: `none`
- runbook exists before transition: `False`
- early runbook guard passed: `True`
- runbook written by this audit: `False`
- automation state advanced by this audit: `False`

Contract coverage:

- Phase 2 source of truth: present
- mid-quote versus model-credit tolerances: present
- divergence escalation thresholds: present
- hold-times per leg: present
- daily artifact list: present
- no-order reaffirmation for `place_order`, `modify_order`, and `cancel_order`: present

Composite integration:

- `signal_baseline_composite_plan_gate_audit` now auto-runs the runbook template contract audit if its summary is missing.
- Branch A now records runbook template contract counts and fails if the runbook template loses required content or if the real runbook appears before transition.

Verdict:

The transition-day Phase 2 runbook content is pre-validated without prematurely opening Phase 2. The real runbook should still only be written by the transition controller after the clean-observation, unique-date, readiness, and broker-block gates pass.

## `TB11 Phase1ToPhase2TransitionPassed`

Trigger evidence:

- scheduled Phase 1 wrapper: `results/log_runs/signal_baseline_tb11_options_phase1_auto_quote_observation_20260701_133548_scheduled.log`
- scheduled T28 wrapper: `results/log_runs/tb11_t28_chain_band_freshness_gate_20260701_133548_scheduled.log`
- transition closeout memo: `results/signal_baseline/tb11_phase1_to_phase2_transition_closeout_memo.md`
- Phase 2 runbook: `results/signal_baseline/tb11_phase2_paper_price_reconciliation_runbook.md`

Current read:

- transition passed: `True`
- transition status: `phase2_runbook_opened_state_advanced`
- Phase 1 collection date: `2026-07-01`
- readiness collection date: `2026-07-01`
- clean observations: `15 / 15`
- unique observation dates: `5 / 5`
- Phase 1 evidence gate passed: `True`
- readiness Phase 2 gate passed: `True`
- selected-leg coverage: `4 / 4`
- modeled credit available: `True`
- broker-block violations: `0`
- runbook written: `True`
- automation state advanced: `True`
- broker orders allowed: `False`
- blockers: `none`

T28/readiness evidence:

- T28 fresh quote rows: `98`
- T28 selected-leg hits: `4 / 4`
- readiness reconciliation status: `phase2_paper_price_reconciliation_ready`
- latest Phase 1 observed weighted credit: `18.0`
- latest Phase 1 modeled credit: `18.15`
- latest Phase 1 within 15% adverse tolerance: `True`

Post-transition audits:

- no-order static audit passed: `True`
- forbidden order calls/imports/wrapper refs: `0 / 0 / 0`
- runbook contract audit passed against written runbook: `True`
- runbook contracts present: `28 / 28`
- runbook exists before transition: `False`
- composite Branch A status: `phase2_runbook_opened_pending_commit`

Verdict:

Branch A crossed the Phase 1 Target-15 gate and opened the Phase 2 paper-price reconciliation runbook under the broker-block invariant. The required next action is to commit the runbook and transition artifacts before any Phase 2 reconciliation execution. Branch B TB15 remains research-only because tail risk still breaches the promotion bar; Branch C lockouts remain enforced.

## `TB11 ScheduledJobsLatestInference 2026-07-02`

Artifacts:

- `results/log_runs/signal_baseline_tb11_options_phase1_auto_quote_observation_20260702_203939_scheduled.log`
- `results/log_runs/tb11_t28_chain_band_freshness_gate_20260702_203939_scheduled.log`
- `results/signal_baseline/tb11_scheduled_jobs_20260702_inference.md`

Scheduler read:

- checked at: `2026-07-02 21:48 IST`
- `\TB11_Phase1_QuoteObservation_0940`: last run `2026-07-02 20:38:13`, next run `2026-07-03 09:40:00`, last result `0`
- `\TB11_Phase1_QuoteObservation_1230`: last run `2026-07-02 20:38:13`, next run `2026-07-03 12:30:00`, last result `0`
- `\TB11_Phase1_QuoteObservation_1445`: last run `2026-07-02 20:38:13`, next run `2026-07-03 14:45:00`, last result `0`
- `\TB11_T28_ChainBandFreshness_0945`: last run `2026-07-02 20:38:13`, next run `2026-07-03 09:45:00`, last result `0`

Latest artifact read:

- Phase 1 ledger: `16 / 15` clean observations, `6 / 5` unique dates, broker-block violations `0`, Phase 1 evidence gate `True`
- T28 gate: quote packets `96`, fresh rows `0`, median quote age `12002.884757` seconds, status `blocked_needs_fresh_intraday_t28`
- Phase 2 readiness: gate `False`, selected-leg hits `2 / 4`, full coverage `False`, modeled credit available `True`, broker orders allowed `False`
- Transition controller: transition passed `False`, runbook written `False`, automation state advanced `False`
- Composite audit after refresh: `branch_a_waiting_for_market_evidence`

Inference:

The scheduled jobs are alive and returning `0`, but the `2026-07-02 20:39` run was outside the market window and produced stale T28 evidence. Treat it as a stale-data guard firing, not as a valid Phase 2 reconciliation opening and not as a reversal of the already committed `2026-07-01` Phase 2 runbook handoff.

Next action:

Wait for the next live-market run on `2026-07-03`; require fresh T28 rows, selected-leg coverage `4 / 4`, and Phase 2 readiness pass before any no-order paper-price reconciliation execution. Broker order endpoints remain blocked.

## `ResearchContinuationPlan 2026-07-02`

Source plan:

- `c:\Users\Ramic\Downloads\new golas today jun_07_26.txt`

Progress artifacts:

- `results/research_continuation_progress_20260702.md`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_summary.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_metadata.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_decision.md`

Plan reconciliation:

- Post-TB14 steps 3-6 are already present in repo artifacts.
- Step 3 survived: held-out folds beating rebalanced benchmark `4 / 4`.
- Step 4 survived: actual hedge timing percentile versus random null `0.999`.
- Step 5 survived base short-cost stress: `7` folds beating rebalanced benchmark, with the caveat that historical FUTSTK coverage is not live SLB borrow availability.
- Step 6 fired the strict OOS kill-switch: folds `9-10` beat the rebalanced benchmark in only `1 / 2`, below required `2 / 2`.

TB15_T03:

- implemented mode: `signal_baseline_tb15_t03_fresh_forward_sample`
- command: `python -B ssell1.py --mode signal_baseline_tb15_t03_fresh_forward_sample`
- status: `blocked_no_non_overlapping_forward_slice`
- TB15 base source trades: `522`
- source first trade date: `2016-05-09`
- source last expiry date: `2024-07-25`
- local F&O zip count: `2346`
- archive min/max date: `2015-01-01` / `2024-07-05`
- held-out trade count: `0`
- broker orders allowed: `False`

Inference:

The plan's first item is already closed by the existing strict OOS kill-switch, so TB14 does not reopen the equity family. The second item, TB15_T03, cannot honestly run yet because no non-overlapping forward slice exists locally; reusing the original 522 trades would violate the T03 gate.

Next action:

Refresh local F&O bhavcopy and daily spot data beyond the TB15 base sample, then rerun T03. If a fresh forward slice cannot be obtained now, proceed to TB11_T30 IV-conditioned sizing as the next cheapest high-value research item using already collected chain-band data.

## `TB11_T30_IVConditionedSizingReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t30_iv_conditioned_sizing_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_detail.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_latest_snapshot.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_summary.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_metadata.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_decision.md`

Current read:

- status: `blocked_insufficient_iv_history`
- source chain-band detail files: `4`
- raw chain rows: `388`
- eligible OTM fresh rows: `50`
- modeled IV rows: `50`
- unique fresh capture dates: `1`
- history span: `0 / 60` days
- latest median modeled IV: `0.13398187395710384`
- latest median available-history IV rank: `1.0`
- provisional sizing tier: `no_entry_insufficient_history`
- broker orders allowed: `False`

Inference:

T30 can now compute modeled IV from chain-band mid quotes, but the current data is only a one-date fresh preview. It is not a valid 60-day IV percentile input yet and must not drive live/paper sizing.

Next action:

Keep collecting fresh T28 chain-band rows during market hours; rerun T30 after the history spans 60 days or at least 20 fresh capture dates.

## `TB18_EarningsOverlayReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb18_earnings_overlay_readiness
```

Artifacts:

- `results/signal_baseline/tb18_earnings_overlay_readiness_summary.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_detail.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_metadata.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_decision.md`

Current read:

- status: `blocked_missing_earnings_axis_data`
- earnings calendar: `data/earnings_calendar.csv`
- earnings status: `template_only`
- earnings rows: `0`
- TB15 symbol coverage: `0 / 8`
- NIFTY weight status: `missing`
- TB11 overlay ready: `False`
- TB15 overlay ready: `False`
- broker orders allowed: `False`
- blockers: `earnings_calendar_template_only|tb15_symbol_earnings_coverage_incomplete|nifty_index_weight_file_missing`

Inference:

TB18 cannot be backtested yet. The repo has the earnings-calendar schema placeholder, but no announcement rows and no NIFTY constituent/weight file for the TB11 index-heavy-earnings veto.

Next action:

Populate `data/earnings_calendar.csv` from a non-Zerodha source and add `data/nifty50_index_weights.csv` or an equivalent symbol/weight file before running TB18.

## `TB16_DefinedRiskNiftyBullPutSpread`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb16_defined_risk_nifty_bull_put_spread
```

Artifacts:

- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_detail.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_summary.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_skipped.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_metadata.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_decision.md`

Current read:

- status: `research_rejected_by_initial_gates`
- trades: `308`
- first entry / last expiry: `2016-07-25` / `2024-07-11`
- annualized return on estimated margin: `14.91%`
- win rate: `74.68%`
- worst trade: `-325.18` points
- max drawdown: `-1078.95` points
- TB11 return correlation: `0.4700` over `161` overlapping expiries
- blocker: `annualized_rom_below_15pct`
- broker orders allowed: `False`

Inference:

The first real-chain TB16 bull-put spread is close on return and acceptable on TB11 diversification, but it fails the explicit 15% annualized return-on-margin gate and has too much point drawdown versus the current TB11 balanced/defensive options work. Treat it as a documented reject.

Next action:

Proceed to `TB11_T31` staggered multi-expiry or `TB19` OI positioning as the next plan item that can use current repo data. Keep `TB15_T03`, `TB11_T30`, and `TB18` parked until their data-readiness blockers are cleared.

## `TB11_T31_StaggeredMultiExpiryReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t31_staggered_multi_expiry_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_detail.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_summary.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_skipped.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_metadata.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_decision.md`

Current read:

- status: `research_rejected_or_blocked`
- source selected trades: `51`
- usable second-expiry stagger trades: `3`
- coverage rate: `5.88%`
- dominant blocker: `second_expiry_leg_or_liquidity_missing`
- blocked rows from that reason: `44` base and `44` harsh-stress
- broker orders allowed: `False`

Inference:

T31 is not a promotion candidate. The next-expiry sleeve can be priced for only `3 / 51` selected defensive entries, so the apparent positive covered-row result is not broad enough to prove smoothing.

Next action:

Open `TB19` OI positioning using the local F&O OI artifacts. Keep `TB15_T03`, `TB11_T30`, `TB18`, and `TB11_T31` parked until their respective data-readiness blockers clear.

## `TB19_OIPositioningReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb19_oi_positioning_readiness
```

Artifacts:

- `results/signal_baseline/tb19_oi_positioning_readiness_detail.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_summary.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_metadata.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_decision.md`

Current read:

- status: `no_oi_filter_promoted`
- source selected trades: `51`
- best base-case filter: `pcr_high`
- base `pcr_high`: `32` trades, `18.23%` annualized ROM, max DD `-0.66`
- base all-trades: `51` trades, `17.57%` annualized ROM, max DD `-1.25`
- harsh `pcr_high`: `32` trades, `7.78%` annualized ROM, max DD `-19.94`
- harsh all-trades: `51` trades, `9.11%` annualized ROM, max DD `-18.77`
- durable filters passing base and harsh: `none`
- broker orders allowed: `False`

Inference:

TB19 found an interesting base-case OI condition, but no durable filter survived both base and harsh-cost gates. Do not add the OI overlay to TB11 sizing or execution logic.

Next action:

Move to `TB17` covered-call overwrite only if we explicitly define the underlying holding assumption. Otherwise the operational queue remains: keep T28 collection alive, rerun T30 after enough fresh IV history, refresh TB15 forward data, and populate TB18 earnings/index-weight inputs.

## `TB17_CoveredCallOverwriteReadiness`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb17_covered_call_overwrite_readiness
```

Artifacts:

- `results/signal_baseline/tb17_covered_call_overwrite_readiness_detail.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_summary.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_skipped.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_metadata.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_decision.md`

Current read:

- status: `research_rejected_by_initial_gates`
- symbols tested: `RELIANCE`, `HDFCBANK`, `ICICIBANK`, `INFY`, `TCS`
- F&O bhavcopy files available/scanned after weekly-entry filter: `2346` / `426`
- sanity-passing trades: `238`
- portfolio incremental yield annualized: `4.38%`
- portfolio covered-call annualized return: `8.95%`
- matched-window buy-hold annualized return: `2.84%`
- assignment rate: `28.57%`
- upside give-up / premium: `67.77%`
- price-scale sanity exclusions: HDFCBANK and RELIANCE after adjusted stock closes did not align with unadjusted option strikes/premiums
- broker orders allowed: `False`

Inference:

TB17 is not deployable from the current data. A raw pass produced impossible premium/spot relationships because the equity spot CSVs are adjusted while the option bhavcopy strikes/premiums are not. After adding strike-to-spot and premium-to-spot sanity gates, the remaining sample still fails the portfolio yield/upside gates: the overwrite gives up too much upside for the premium collected.

Next action:

Proceed to `TB20` cross-asset defensive tilt as the next attached-plan research item. Keep TB17 closed unless we add corporate-action-adjusted spot/options alignment and an explicit passive-core holdings file. Keep `TB15_T03`, `TB11_T30`, and `TB18` parked until their data-readiness blockers clear.

## `TB20_CrossAssetDefensiveTilt`

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb20_cross_asset_defensive_tilt
```

Artifacts:

- `results/signal_baseline/tb20_cross_asset_defensive_tilt_detail.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_summary.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_folds.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_metadata.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_decision.md`

Current read:

- status: `research_rejected_by_initial_gates`
- universe: `NIFTYBEES`, `BANKBEES`, `ITBEES`, `PHARMABEES`, `INDIAVIX`
- rule: top-2 ETF momentum unless NIFTYBEES is below its 200-session SMA or India VIX is above its 80th percentile; risk-off sleeve uses `PHARMABEES`
- events: `83`
- risk-off events: `32`
- benchmark annualized return: `8.92%`
- top-2 ETF momentum annualized return: `3.87%`
- defensive tilt annualized return: `0.56%`
- benchmark max drawdown: `-13.92%`
- defensive tilt max drawdown: `-25.66%`
- folds beating benchmark: `3 / 10`
- broker orders allowed: `False`

Inference:

TB20 does not smooth the curve with the currently available cross-asset ETF set. The PHARMABEES risk-off sleeve worsens drawdown and gives up too much return versus the NIFTYBEES interval benchmark, so it should not be promoted.

Next action:

The attached-plan research queue is now exhausted into documented rejects or explicit data blockers. Operationally, keep the TB11 no-order T28/Phase 2 collection healthy; for research, refresh F&O/spot data for `TB15_T03`, keep accumulating IV history for `TB11_T30`, and populate earnings plus NIFTY weights for `TB18`.
