# Thesis Batch 12 - OHLCV-Regime-Conditioned PortfolioRank

Date: 2026-06-29

## Thesis

`PortfolioRank60m` showed real cross-sectional structure, but prior promotion attempts failed because the edge was regime-sensitive and did not robustly beat same-universe buy-hold.

`TB12` tested whether OHLCV-only market regime gates could rescue the long-only top-3 swing wrapper without adding delivery, OI, earnings, options, broker, or live data.

## Modes

```powershell
python -B ssell1.py --mode signal_diagnostic_tb12_portfolio_rank_regime_attribution
python -B ssell1.py --mode signal_baseline_tb12_ohlcv_regime_conditioned_portfolio_rank
```

## Artifacts

- `results/signal_baseline/tb12_portfolio_rank_regime_attribution_summary.csv`
- `results/signal_baseline/tb12_portfolio_rank_regime_attribution_detail.csv`
- `results/signal_baseline/tb12_portfolio_rank_regime_attribution_folds.csv`
- `results/signal_baseline/tb12_portfolio_rank_regime_attribution_candidate_gate_shortlist.csv`
- `results/signal_baseline/tb12_portfolio_rank_regime_attribution_metadata.csv`
- `results/signal_baseline/tb12_ohlcv_regime_conditioned_portfolio_rank_summary.csv`
- `results/signal_baseline/tb12_ohlcv_regime_conditioned_portfolio_rank_benchmark_comparison.csv`
- `results/signal_baseline/tb12_ohlcv_regime_conditioned_portfolio_rank_rebalance_history.csv`
- `results/signal_baseline/tb12_ohlcv_regime_conditioned_portfolio_rank_ticker_contributions.csv`
- `results/signal_baseline/tb12_ohlcv_regime_conditioned_portfolio_rank_metadata.csv`

## Result

All tested TB12 rows are `research_only`.

Promotion-grade source:

| Candidate | Gate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Verdict |
|---|---|---:|---:|---:|---:|---|
| `E1006 top3 every_10` | `nifty_trend_up` | `10.98%` | `17.12%` | `3 / 10` | `-9.69%` | `research_only` |
| `E1006 top3 every_10` | `composite_ohlcv_support` | `8.65%` | `17.12%` | `3 / 10` | `-15.25%` | `research_only` |
| `E1006 top3 every_10` | `breadth_supportive` | `8.26%` | `17.12%` | `4 / 10` | `-22.28%` | `research_only` |
| `E1006 top3 every_10` | `ungated` | `5.20%` | `17.12%` | `3 / 10` | `-48.13%` | `research_only` |

Shorter-source controls:

- `E1002 top3 every_15` and `E1003 top3 every_21` produced positive shorter-window reads, but they are not promotion-grade because the available source is only `3` folds.
- These controls may guide future data generation, but they do not override the failed 10-fold E1006 buy-hold gate.

## Decision

Close `TB12` as `research_only`.

The OHLCV gates improved the E1006 drawdown shape and raised the best 10-year mean annualized return from `5.20%` ungated to `10.98%` under `nifty_trend_up`, but the branch still failed the required promotion gates:

- mean annualized return stayed below same-universe buy-hold
- folds beating buy-hold stayed far below `7 / 10`
- some gates still worsened worst-fold behavior versus buy-hold

## Next Action

Do not open another broad OHLCV-only equity selector branch from this evidence.

If equity research continues, it should require either:

- a new non-OHLCV information axis with real data coverage, or
- a deliberately different objective than beating same-universe buy-hold.
