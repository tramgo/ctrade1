# Codex Next Action

## Current Status

- Active batch: `TB03`
- Last completed thesis: `TB03_T04 PortfolioRankLongOnly`
- Last verdict: `diagnostic_complete`
- Active thesis: `TB03_T05 HoldingHorizonE1903Sweep`
- Active stage: `baseline_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

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
run_mode.bat signal_baseline_native_15m_holding_horizon_execution_sweep
```

## Do Not Do

- Do not reopen broad new signal research yet.
- Do not trust cost-only rescue stories for single-name branches unless this new execution sweep actually flips a result.
- Do not treat the refreshed `branch_decision_scoreboard.csv` as the only truth source until its benchmark field regeneration is repaired.
- Do not start RL.
