# Codex Next Action

## Current Status

- Active batch: `TB02`
- Last completed thesis: `TB02_T03 EventOutcomeAccounting`
- Last verdict: `research_only`
- Active thesis: `TB02_T04 RegimeSpecificIncumbentVeto`
- Active stage: `research_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## Fresh Result Read

`TB02_T03 EventOutcomeAccounting` did not promote.

- broad `E2801-E2804` event-outcome accounting produced no promoted IDs
- refined `E2806` was too restrictive and produced no valid experiment rows
- `E2805`, the `E211`-style event-outcome control, showed real predictive separation but negative economics:
  - AUC: `0.5585800644447346`
  - balanced accuracy: `0.5438344743187962`
  - top-decile net return: `-0.001912395609680604`
  - top-minus-bottom spread: `-0.00015781370424895353`
  - real-vs-shuffled spread gap: `-0.00015285913114700461`
- target-before-stop labels were not enough:
  - `T7` hit rates were non-trivial
  - `T8` clean-path hit rates were lower
  - mean path payoff stayed negative

## Interpretation

This closes the current standalone OHLCV-derived event-outcome path for now.

The important lesson is not that prediction is impossible. The important lesson is that the current predictors can separate statistical outcomes while still selecting trades with negative expected executable payoff. More generic classifier work is therefore not the right next move.

## Immediate Required Action

Run an incumbent-only `E211` entry audit.

Purpose:

- inspect where the existing `SIGNAL_E211_BANDED_68` entries lose money
- identify separable failure regimes before building any veto, delay, or sizing overlay
- do not create another standalone alpha family unless the audit shows a clear actionable pattern

## Next Command

```powershell
run_mode.bat signal_baseline_e211_entry_audit
```

## Do Not Do

- Do not start RL.
- Do not tune PPO or reward functions.
- Do not launch another broad OHLCV classifier sweep.
- Do not open `TB02_T10` without a real local external data feed.
- Do not baseline `E2806`; it did not create a testable research sample.
