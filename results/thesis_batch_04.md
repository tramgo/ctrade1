# Thesis Batch 04

Date prepared: 2026-04-29  
Author: Codex  
Status: queued_next_batch

## Theme

Batch 04 is a focused swing-validation program for the `PortfolioRank60m` family.

It is not a broad rerun of prior intraday branches at slower cadence.
It exists to answer one question cleanly:

- is there a robust deployable swing book in the existing `PortfolioRank60m` signal family, and if so which cadence and concentration settings maximize return without losing validation discipline?

## Why Batch 04 Exists

Fresh repo evidence established:

- `E1002 top3 every_5` = `walkforward_validated`
- `E1006 top3 every_5` = higher upside but `walkforward_fragile`
- hold sweep showed:
  - `E1002 top3 every_15` ≈ `18.94%` approximate annualized backtest return
  - `E1006 top3 every_10` ≈ `27.21%` approximate annualized backtest return
  - `E1003 top3 every_21` ≈ `17.08%` approximate annualized backtest return

That means the next unit of work is targeted hold-specific validation, not new signal discovery.

## Thesis Queue

1. `TB04_T01 PortfolioRankHoldWalkforward`
   - validate `E1002@15`, `E1006@10`, and `E1003@21` across 3 contiguous folds
2. `TB04_T02 PortfolioRankTopKSweep`
   - evaluate `top_k in {2,3,4,5,7}` on the winning hold cadence
3. `TB04_T03 PortfolioRankScoreWeightedSizing`
   - compare equal weight versus score-weighted sizing on the winning cell
4. `TB04_T04 PortfolioRankRegimeGate`
   - apply `E801` market-state veto or skip gate to the winning swing cell
5. `TB04_T05 PortfolioRankLiquidSubsetAudit`
   - retest the winning cell on the most liquid subset to reduce real-execution drift
6. `TB04_T06 PortfolioRankPaperTradeGate`
   - open only after walk-forward and concentration gates pass

## Hard Rules

- Do not reopen broad single-name classifier research here.
- Do not unfreeze RL.
- Do not promote on raw backtest CAGR alone.
- Keep `SIGNAL_E211_BANDED_68` as incumbent control until broader validation says otherwise.
