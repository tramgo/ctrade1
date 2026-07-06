# Project State Checkpoint

> Historical checkpoint. For the current canonical strategy/program view, use [grand_plan.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan.md).

## Update 2026-03-27

This checkpoint is now historically useful but no longer current by itself.

### What has changed since the original checkpoint

- the native `15m` frontier has been opened and tested seriously
- `Native15mExecution` closed as `research_only`
- `Native15mFailedBreakout` closed as `research_only`
- `Native15mOpenDrive` closed as `research_only`
- `Native15mSessionPhase` is now the active thesis

### New strategic rule

The current design rule is now stronger than the original checkpoint stated:

- better research metrics are not enough
- better classification is not enough
- a branch must classify within a slice that is itself economically tradable after costs

### Current source of truth

For live state, use:

- [current_layer_decision_memo.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/current_layer_decision_memo.md)
- [grand_plan_tracker.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan_tracker.md)
- [thesis_batch_01.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01.md)
- [thesis_batch_01_closeout.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01_closeout.md)

Date: 2026-03-17

## Decision

Active branch promotion is paused.

This is not a project stop. It is a controlled pause on:

- new branch promotion into RL
- new nearby `60m` setup-family sweeps
- threshold / reward / PPO rescue work on incumbent branches

## Why

The current research layer has been explored enough to establish a consistent pattern:

- new branches still produce research structure
- but they do not produce stronger executable post-cost baselines than `SIGNAL_E211_BANDED_68`

This has now been observed across:

- cross-sectional `60m`
- formal ablation winners
- setup-regime survivors

## Current Benchmark

- Incumbent benchmark: `SIGNAL_E211_BANDED_68`
- Status: benchmark-only, no active rescue work
- Role: reference policy future branches must beat at baseline level before RL can re-enter

## Branch Verdicts

| Branch | Best Research Candidate | Best Baseline Candidate | Verdict |
|---|---|---|---|
| `E211` incumbent | `E209/E211` family | `SIGNAL_E211_BANDED_68` | benchmark |
| `cross_sectional_60m` | `E504` | `SIGNAL_E501_BANDED_64` | research-only |
| `ablation_grid` | `E610` | `SIGNAL_E605_BANDED_70` | research-only |
| `setup_regimes` | `E705` / `E703` | `SIGNAL_E703_BANDED_66` | research-only |
| `E302` broader branch | `E325/E329` | `SIGNAL_E302_BANDED_70` | research-only |
| `generalization_next` | `E401/E407` | `SIGNAL_E407_BANDED_70` | research-only |
| `generalization_wave2` | `E415` | none promoted | research-only |

## What We Learned

### Stronger research lanes

- `T3` / `T4` style setup/opportunity targets remain stronger than `T1` / `T2` regression targets
- `F4/F5/F6` and `F3/F4/F5` style setup/context families keep surfacing as the best research combinations
- regime-conditioning improves research quality

### Persistent limit

- better research metrics are not converting into better executable post-cost baselines
- breadth is often acceptable, but aggregate return remains weaker than the incumbent
- this suggests the current `60m` information layer is near exhaustion for branch discovery of this type

## Grand-Plan Rule From Here

RL stays out of scope until a new branch proves:

1. stronger standalone baseline return than `SIGNAL_E211_BANDED_68`
2. no obvious breadth collapse
3. no materially worse turnover without compensating return

## Recommended Next Strategic Axis

Do not open another adjacent setup branch immediately.

If research continues, it should reopen only under a genuinely different thesis, such as:

1. better market-state / regime labeling on top of `60m`
2. universe-level cross-sectional ranking logic rather than per-stock setup detection
3. multi-timescale context layered on top of `60m`

## Immediate Operational Posture

- keep current registries and scoreboards as the source of truth
- do not promote any new branch to RL
- do not retune incumbent execution
- choose the next thesis deliberately before resuming discovery
