# Thesis Batch 14 - All-Fold Dynamic Hedge PortfolioRank

Date: 2026-06-29

## Thesis

`TB13_CoreActiveTiltPortfolioRank` beat same-universe buy-hold in `7 / 10` folds, but still lagged in folds `1`, `2`, and `9`. Those failures were not large drawdown failures; they were participation and dilution failures in generally rising markets.

`TB14` tests a more flexible OHLCV-only structure:

- keep the same-universe equal-weight core
- keep the E1006 top-10, every-30-session PortfolioRank active basket
- use a small normal active sleeve when relative breadth is not weak
- use a small short active hedge against the PortfolioRank top-10 basket when 3-session relative breadth is in the weak regime

## Mode

```powershell
python -B ssell1.py --mode signal_baseline_tb14_all_fold_dynamic_hedge_portfolio_rank
```

## Artifacts

- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_summary.csv`
- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_folds.csv`
- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_rebalance_history.csv`
- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_ticker_contributions.csv`
- `results/signal_baseline/tb14_all_fold_dynamic_hedge_portfolio_rank_metadata.csv`

## Candidate

`E1006_core_dynamic_active_top10_r30_relbreadth_q25_hedge`

Rule:

- normal regime: `0.90x` core plus `0.10x` active top-10 sleeve
- hedge regime: `1.20x` core minus `0.20x` active top-10 sleeve
- hedge regime trigger: `BreadthRelAdvFrac_3 <= 0.3703703703703703`

## Result

| Candidate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Buy-Hold Worst Fold | Rebalances | Hedge Windows | Top Contributor Share | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `E1006_core_dynamic_active_top10_r30_relbreadth_q25_hedge` | `18.82%` | `17.12%` | `10 / 10` | `-10.69%` | `-11.44%` | `90` | `25` | `7.65%` | `promoted_candidate` |

Fold read:

- every fold beats same-universe buy-hold
- mean annualized return is above same-universe buy-hold
- worst fold is slightly better than buy-hold
- concentration remains below the prior danger zone
- event count is not sparse

## Decision

Advance `TB14_AllFoldDynamicHedgePortfolioRank` as the first OHLCV-only equity candidate to beat same-universe buy-hold in all `10 / 10` folds.

## Caveats

This is not a long-only strategy and it is not a live/broker/RL promotion. The hedge regime uses a small short active sleeve against the score-weighted top-10 active basket, so the next audit must address borrow/short feasibility, gross exposure, margin, explicit core turnover cost, and frozen-threshold replay before this can be treated as an executable frontier candidate.
