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

## Immediate Required Action

Run the dedicated `E1903` execution sweep.

Purpose:

- test whether tighter thresholds rescue `E1903`
- test whether forced longer holding improves cost amortization
- keep the comparison explicit against `FLAT` and `SIGNAL_E211_BANDED_68`

## Next Command

```powershell
python -u -B ssell1.py --mode signal_baseline_native_15m_holding_horizon_execution_sweep
```

## Already Wired Next

After `TB03_T05` finishes, the next queued validation mode is:

```powershell
python -u -B ssell1.py --mode signal_baseline_portfolio_rank_60m_long_only_hold_walkforward
```

Purpose:

- validate the best hold-sweep cells across `3` contiguous folds
- keep the comparison explicit against `FLAT` and `SIGNAL_E211_BANDED_68`
- decide whether `E1002@15` or `E1006@10` survives as the true swing-book candidate

## Then Run

```powershell
python -u -B ssell1.py --mode signal_baseline_portfolio_rank_60m_long_only_hold_sweep
```

Purpose:

- keep the longer-hold sweep evidence available as the annualization map
- use it together with hold walk-forward to separate robust swing from fragile upside

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
