# Thesis Batch 01 Closeout

Date: 2026-03-25

This closeout file records completed decisions within Batch 01 as they happen. The batch is not fully closed yet.

## Completed Decisions

### `TB01_T01` Native15mFailedBreakout
- Research verdict: alive
- Best research candidate: `E1602`
- Best research profile:
  - AUC `0.5750242309686432`
  - balanced accuracy `0.5537999010069146`
  - spread `0.0026510840805298846`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1601_BANDED_70`
- Best executable return: `-5.820192894889364e-05`
- Decision: `research_only`

Reason:
- `E1601` was too sparse to matter.
- `E1602` was the real research candidate but remained clearly negative after costs in executable baseline.

### `TB01_T02` Native15mOpenDrive
- Research verdict: alive
- Best research candidate: `E1702`
- Best research profile:
  - AUC `0.5770899622388297`
  - balanced accuracy `0.5565408256687087`
  - spread `0.0014270931107690785`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1701_BANDED_70`
- Best executable return: `-0.0006190150485907`
- Decision: `research_only`

Reason:
- `E1702` and `E1701` both produced real research signal and real executable activity.
- The branch was not a fake no-trade artifact after the filter fix, but the best executable policy still stayed net negative after costs.

### `TB01_T03` Native15mSessionPhase
- Research verdict: alive
- Best research candidate: `E1803`
- Best research profile:
  - AUC `0.6341835397008408`
  - balanced accuracy `0.6081429351342786`
  - spread `0.0008386969864369726`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1802_BANDED_70`
- Best executable return: `-0.0001341339035688`
- Decision: `research_only`

Reason:
- `E1803` was a very strong classifier in research terms, but still sat in a weak economic slice.
- `E1802` was the least-bad executable candidate, but it still failed to beat `FLAT`.

### `TB01_T04` Native15mHoldingHorizon
- Research verdict: alive
- Best research candidate: `E1903`
- Best research profile:
  - AUC `0.6070648832522949`
  - balanced accuracy `0.5832163359768442`
  - spread `0.0008443445213692815`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1902_BANDED_70`
- Best executable return: `-0.0016108139104049`
- Decision: `research_only`

Reason:
- Explicit hold-duration matching did change the research profile and `E1902` was the least-bad executable version.
- But horizon selection alone did not repair the economics; the branch traded broadly enough to be meaningful and still stayed clearly below `FLAT`.

## Current Next Action

### `TB01_T05` Native15mTopKEventRank
- Status: implemented
- Next step: run research, inspect shortlist, baseline only survivors if the favorable-slice ranking thesis is alive

## Batch Status

- Closed theses: `4 / 10`
- Active theses: `1`
- Backlog theses: `5`
