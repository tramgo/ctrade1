# Codex Next Action

## Current Status

- Last completed Batch 01 executable thesis: `TB01_T09 EventConditionedSizingVeto`
- `TB01_T10 NewDataAxisIfAvailable`: not opened because no concrete new local data axis was found
- Active batch: `TB02`
- Active thesis: `TB02_T01 CrossSectionalCommonalityResidual`
- Active stage: `research_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## Immediate Required Action

Run `TB02_T01 CrossSectionalCommonalityResidual` research.

Do this as a slice-first thesis:

- `Slice`: market/sector/commonality-adjusted residual leadership or residual reversal state
- `Selector`: rank only inside that favorable residual slice
- `Execution`: simple baseline policies first, no RL
- `Failure condition`: close if executable validation stays below `FLAT` or below `SIGNAL_E211_BANDED_68`

## Required Preflight

- Research mode is wired as `signal_research_cross_sectional_commonality_residual`
- Baseline mode is wired as `signal_baseline_cross_sectional_commonality_residual`
- Experiment family is `E2501-E2504`
- Baseline only the strongest `1-2` research survivors

## Next Command

```powershell
run_mode.bat signal_research_cross_sectional_commonality_residual
```

## Do Not Do

- Do not start RL.
- Do not tune PPO or reward functions.
- Do not open `TB02_T10` without a real local external data feed.
- Do not delete old results.
