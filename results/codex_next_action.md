# Codex Next Action

## Current Status

- Active batch: `TB03`
- Last completed thesis: `TB03_T04 PortfolioRankLongOnly`
- Last verdict: `diagnostic_complete`
- Active thesis: `TB03_T05 HoldingHorizonE1903Sweep`
- Active stage: `baseline_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen
- Fresh walk-forward update:
  - `E1002 top3 every_5` = `walkforward_validated`
  - `E1006 top3 every_5` = `walkforward_fragile`
  - `E1003 top3 every_5` = `walkforward_fragile`
- Fresh hold-sweep update:
  - `E1006 top3 every_10` = highest approximate annualized backtest return at `27.21%`, but still treated as fragile until hold-specific walk-forward passes
  - `E1002 top3 every_15` = strongest robust swing candidate at `18.94%` approximate annualized backtest return
  - `E1003 top3 every_21` = `17.08%` approximate annualized backtest return, but lower priority because weekly walk-forward was fragile
- Fresh hold-specific walk-forward update:
  - `E1006 top3 every_10` = `hold_walkforward_validated`
  - `E1002 top3 every_15` = `hold_walkforward_fragile`
  - `E1003 top3 every_21` = `hold_walkforward_fragile`
- Fresh top-k update:
  - `E1006 top2 every_10` = highest approximate annualized backtest return at `34.18%`
  - `top_k = 2 / 3 / 4 / 5 / 7` all stayed positive and beat `SIGNAL_E211_BANDED_68`
  - this means the swing edge is not knife-edge to selection width
- Fresh regime-gate update:
  - `E801` gate did not help
  - threshold `0.50` only allowed `4/73` rebalances and cut approximate annualized return to `2.89%`
  - thresholds `0.60+` blocked all trades
  - conclusion: close `E801` gate as a failed monetization add-on for this swing cell
- Fresh sizing update:
  - score-weighted sizing beat equal-weight on the current winner
  - `E1006 top2 every_10 score_weighted = 53.79%` approximate annualized backtest return
  - `E1006 top2 every_10 equal_weight = 34.18%`
  - concentration rose, but stayed below the current `0.60` red-flag line
- Fresh liquid-subset update:
  - the top-liquidity subset underperformed the full universe materially
  - `subset_14 equal_weight = 10.44%` approximate annualized backtest return
  - `subset_14 score_weighted = 8.10%`
  - conclusion: the current edge depends on the broader 27-name universe and should not be narrowed prematurely
- Fresh score-weighted top-k walk-forward update:
  - no score-weighted top-k cell passed all 3 folds
  - `top_k = 2` kept the highest mean fold return but failed fold 3 at `-0.29%` per rebalance
  - `top_k = 3` had the best robustness-return tradeoff with a smaller fold-3 loss than `top_k = 2`
  - selected capital leaned toward the non-top-liquid half of the universe in every score-weighted variant
  - conclusion: shift the working base from `top_k = 2` to `top_k = 3` before testing any gate or trip-wire
- Fresh dispersion-gate update:
  - the binary prediction-spread gate reduced turnover and concentration but also cut too much edge on the full sample
  - best gate setting remained below the ungated `top_k = 3 score_weighted` walk-forward central case
  - conclusion: move from binary gating to continuous dispersion-sized exposure instead of staying flat in compressed-rank regimes
- Fresh dispersion-sized walk-forward update:
  - the rerun stayed strongly positive across all 3 folds:
    - fold 1 = `0.03038`
    - fold 2 = `0.00234`
    - fold 3 = `0.00486`
  - but fold 1 still used an internal warm-up prior, so treat the result as nearly final, not final
  - the mode is now patched one last time to be fully non-peeking:
    - fold 1 = constant `1.0x`
    - fold 2 = fold 1 reference median
    - fold 3 = fold 2 reference median
  - rerun the same mode once more before treating the strategy as fully validated

## Fresh Result Read

Today's Batch 03 sequence gave a clean ranking of the external-feedback hypotheses:

- `TB03_T01 SlippageSensitivityCalibration`
  - lower friction improved economics
  - did not overturn `E211 > E801`
- `TB03_T03 FuturesCostProfilePort`
  - cheaper stock-futures assumptions improved economics modestly
  - still did not overturn `E211 > E801`
- `TB03_T04 PortfolioRankLongOnly`
  - this is the hypothesis that actually flipped the sign
  - daily rebalancing stayed negative
  - weekly long-only rebalancing turned strongly positive
  - `E1006 top3 weekly = 0.0041071`
  - `E1006 top5 weekly = 0.0025953`
  - `E1003 top5 weekly = 0.0016477`
  - `E1002 top5 weekly = 0.0010301`

## Interpretation

What the repo says now:

- the external feedback was right that the wrapper deserved another iteration
- the external feedback was too optimistic that slippage calibration alone would expose a hidden single-name winner
- the strongest executable challenger path is now `PortfolioRank60m`, specifically `E1006` in a weekly long-only wrapper
- the next unresolved salvage hypothesis is `E1903`, but it now needs an explicit execution-hold sweep rather than another generic rerun

## Already Wired Next

Rerun the final fully non-peeking dispersion-sized walk-forward:

```powershell
python -u -B ssell1.py --mode signal_baseline_portfolio_rank_60m_dispersion_sizing_walkforward
```

Purpose:

- test whether a continuous dispersion-sized multiplier can improve fold 3 without collapsing fold 1 using:
  - fold 1 constant `1.0x`
  - fold 2 using fold 1 as reference
  - fold 3 using fold 2 as reference
- keep the comparison explicit against `FLAT` and `SIGNAL_E211_BANDED_68`
- test the new working base `E1006 every_10 top_k = 3 score_weighted`
- log size multipliers, reference-source metadata, dispersion percentiles, and liquidity-bucket exposure inside each fold

## Then Run

```powershell
python -u -B ssell1.py --mode signal_baseline_native_15m_holding_horizon_execution_sweep
```

Purpose:

- close `TB03_T05` with an explicit pass/fail artifact so the single-name rescue cycle can be ended cleanly

## Closed Diagnostic

```powershell
python -u -B ssell1.py --mode signal_baseline_portfolio_rank_60m_liquid_subset_audit
```

Outcome:

- retain the liquid-subset evidence as a closed realism check
- narrowing to the top-liquidity subset weakened the strategy materially
- keep the broader 27-name universe in the deployment candidate unless later execution evidence forces a narrower universe

## Batch 04 Direction

- `TB04_T01 PortfolioRankHoldWalkforward`
- `TB04_T02 PortfolioRankTopKSweep`
- `TB04_T03 PortfolioRankScoreWeightedSizing`
- `TB04_T04 PortfolioRankRegimeGate`
- `TB04_T05 PortfolioRankLiquidSubsetAudit`

## Do Not Do

- Do not reopen broad new signal research yet.
- Do not trust cost-only rescue stories for single-name branches unless this new execution sweep actually flips a result.
- Do not treat the refreshed `branch_decision_scoreboard.csv` as the only truth source until its benchmark field regeneration is repaired.
- Do not start RL.
