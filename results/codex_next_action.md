# Codex Next Action

## Current Status

- Last completed Batch 01 executable thesis: `TB01_T09 EventConditionedSizingVeto`
- `TB01_T10 NewDataAxisIfAvailable`: not opened because no concrete new local data axis was found
- Active batch: `TB02`
- Active thesis: none
- Active stage: `idle`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## Immediate Required Action

Design and implement `TB02_T01 CrossSectionalCommonalityResidual`.

Do this as a slice-first thesis:

- `Slice`: market/sector/commonality-adjusted residual leadership or residual reversal state
- `Selector`: rank only inside that favorable residual slice
- `Execution`: simple baseline policies first, no RL
- `Failure condition`: close if executable validation stays below `FLAT` or below `SIGNAL_E211_BANDED_68`

## Required Preflight

- Confirm the needed market and sector context fields already exist in `build_rl_features`
- Avoid creating a broad generic classifier
- Keep the experiment family small, ideally `3-4` experiments
- Baseline only the strongest `1-2` research survivors

## Do Not Do

- Do not start RL.
- Do not tune PPO or reward functions.
- Do not open `TB02_T10` without a real local external data feed.
- Do not delete old results.
