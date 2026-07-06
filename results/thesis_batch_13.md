# Thesis Batch 13 - Core Active Tilt PortfolioRank

Date: 2026-06-29

## Thesis

`TB12` showed that a pure long-only top-k PortfolioRank swing book still failed same-universe buy-hold even after OHLCV regime gating. `TB13` changed the structure instead of opening another selector family:

- keep the same-universe equal-weight book as the portfolio core
- add a PortfolioRank active sleeve only when OHLCV-derived breadth or trend features say the active sleeve is favorable
- fall back to the core return when the active gate is off
- use only existing OHLCV-derived E1006 PortfolioRank artifacts and derived breadth/trend fields

## Mode

```powershell
python -B ssell1.py --mode signal_baseline_tb13_core_active_tilt_portfolio_rank
```

## Artifacts

- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_summary.csv`
- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_folds.csv`
- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_rebalance_history.csv`
- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_ticker_contributions.csv`
- `results/signal_baseline/tb13_core_active_tilt_portfolio_rank_metadata.csv`

## Result

Best clean candidate:

| Candidate | Gate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Buy-Hold Worst Fold | Rebalances | Active Gate Passes | Top Contributor Share | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `E1006_core0.50_active0.50_top10_r30_breadth_adv_50` | `BreadthAdvFrac_1 >= 0.50` | `20.16%` | `17.12%` | `7 / 10` | `-7.49%` | `-11.44%` | `90` | `53` | `6.68%` | `research_only` |

Other promotion-gate passers:

| Candidate | Mean Ann. | Folds Beating Buy-Hold | Verdict |
|---|---:|---:|---|
| `E1006_core0.60_active0.40_top10_r30_breadth_adv_50` | `19.57%` | `7 / 10` | `research_only` |
| `E1006_core0.00_active1.00_top5_r15_breadth_adv_50` | `19.53%` | `7 / 10` | `research_only` |
| `E1006_core0.80_active0.20_top5_r30_trend_score_positive` | `18.73%` | `7 / 10` | `research_only` |

## Decision

Keep `TB13_CoreActiveTiltPortfolioRank` as `research_only`. The preferred raw candidate is `E1006_core0.50_active0.50_top10_r30_breadth_adv_50` because it uses the simplest predeclared breadth gate and passes the raw buy-hold gate:

- mean annualized return above same-universe buy-hold
- `7 / 10` folds beating buy-hold
- worst fold better than same-universe buy-hold
- low top contributor concentration
- enough rebalance events to avoid a sparse artifact

## Caveats

This is not a live, broker, RL, or automation promotion. Before merging into the main strategy frontier, run a closeout audit that explicitly charges any equal-weight core sleeve turnover, freezes the breadth gate, and replays the exact specification without adding new parameter search.

## Strict Audit Update

The subsequent TB14/TB13 validation audit found that TB13 survives the costed rebalanced benchmark at `7 / 10`, but remains within a selected seven-spec sweep and does not clear the stricter final OOS deployment standard. Its verdict is therefore `research_only`, not `promoted_candidate`.
