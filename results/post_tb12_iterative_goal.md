# Post-TB12 Iterative Equity Goal

Date: 2026-06-29

## Goal

Run equity research as a repeatable decision loop after `TB12`, with early stop rules instead of opening another broad OHLCV-only branch.

## Current State

- `TB12_OHLCVRegimeConditionedPortfolioRank` is closed as `research_only`.
- `E1006 top3 every_10` improved under `nifty_trend_up`, but still failed same-universe buy-hold robustness.
- Active automation state remains `TB11`; this equity loop is a side validation path.

## Iteration 01 - External Data Readiness Refresh

Command:

```powershell
python -B ssell1.py --mode signal_diagnostic_tb07_external_data_readiness
```

Artifact:

- `results/signal_baseline/tb07_external_data_readiness.csv`

Read:

| Axis | Status | Decision |
|---|---|---|
| Delivery percentage | `ready` | already tested; failed standalone rescue |
| F&O OI | `ready` | already tested; failed standalone rescue |
| Breadth | `ready` | already tested; failed standalone rescue |
| Earnings calendar | `template_only` | not runnable as a real new data axis |

## Verdict

Iteration 01 is `stop_path`.

No new equity branch should be opened from the current data state.

## Iteration 02 - Core Plus Active OHLCV Tilt

The user objective was tightened after Iteration 01: continue creatively with OHLCV-only equity research until a strategy beats same-universe buy-hold on mean annualized return and wins at least `7 / 10` folds.

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb13_core_active_tilt_portfolio_rank
```

Artifact:

- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_summary.csv`

Read:

| Candidate | Gate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Verdict |
|---|---|---:|---:|---:|---:|---|
| `E1006_core0.50_active0.50_top10_r30_breadth_adv_50` | `BreadthAdvFrac_1 >= 0.50` | `20.16%` | `17.12%` | `7 / 10` | `-7.49%` | `research_only` |

Iteration 02 satisfied the raw iterative equity objective but was later demoted to `research_only` after the stricter validation audit.

## Iteration 03 - All-Fold Dynamic Hedge

The target was raised from `7 / 10` folds to beating same-universe buy-hold in every fold.

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb14_all_fold_dynamic_hedge_portfolio_rank
```

Artifact:

- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_summary.csv`

Read:

| Candidate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Verdict |
|---|---:|---:|---:|---:|---|
| `E1006_core_dynamic_active_top10_r30_relbreadth_q25_hedge` | `18.82%` | `17.12%` | `10 / 10` raw buy-hold only | `-10.69%` | `research_only` |

Iteration 03 satisfied the raw raised equity objective, with one important caveat: this is no longer long-only because weak relative breadth uses a small short active hedge against the PortfolioRank top-10 basket. It was later demoted to `research_only` after strict OOS replay failed.

## Iteration 04 - Strict TB14 Validation Audit

The stricter audit sequence was run because TB13/TB14 had in-sample threshold, selection-sweep, benchmark-asymmetry, and uncharged-short concerns.

Read:

| Step | Result | Decision |
|---|---|---|
| Alpha decomposition | core rebalance bonus was `4.65%` of full TB14 excess | survives |
| Rebalanced benchmark | TB14 beat costed rebalanced benchmark in `10 / 10`; TB13 preferred candidate beat it in `7 / 10` | survives |
| Walk-forward threshold | held-out folds `6-10` beat rebalanced benchmark in `4 / 5` | survives |
| Random hedge null | actual hedge was about `99.9th` percentile versus random hedge schedules | survives |
| Short feasibility | all hedge names had historical FUTSTK coverage; base short stress held `7 / 10`, harsh stress fell to `6 / 10` | fragile |
| Strict OOS replay | frozen folds `9-10` beat rebalanced benchmark in only `1 / 2` | kill-switch |

Final verdict: demote TB13 and TB14 to `research_only`.

## Next Allowed Equity Actions

Only continue equity research if one of these becomes true:

- a populated earnings/event feed is added with enough history
- a narrow `E211` incumbent overlay targets a specific known failure mode
- the benchmark objective is explicitly changed away from same-universe buy-hold outperformance
- the `TB13` promoted candidate is put through an explicit closeout audit for equal-weight core turnover cost, frozen-gate replay, and implementation leakage
- the `TB14` all-fold candidate is put through borrow/short feasibility, gross exposure, margin, core turnover, and frozen-threshold replay audits

Otherwise, keep the equity path closed and continue the active `TB11` workflow.
