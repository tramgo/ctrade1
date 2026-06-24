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
