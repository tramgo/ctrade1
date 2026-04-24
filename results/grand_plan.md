# Grand Plan

Date: 2026-03-27

## Objective

Build a sound intraday trading engine that is:

- post-cost profitable
- robust in walk-forward validation
- capable of supporting a path above `12%` annualized return
- allowed to use RL only after a baseline-first signal branch earns promotion

## Canonical Rule

`SIGNAL_E211_BANDED_68` remains the incumbent benchmark until a challenger beats it in executable validation.

RL stays frozen unless a branch first proves itself with:

1. positive executable baseline after costs
2. acceptable breadth and concentration
3. broader validation that does not collapse

## What We Know

### Stable truths

- the research stack can find real predictive structure
- cost modeling is not the main bottleneck
- many branches improve research metrics without improving monetization
- `E211` remains the strongest durable executable benchmark

### Sharpened design rule

Strong classification alone is not enough.

A branch must not only separate better cases from worse cases. It must do so inside a slice of the market that is itself economically tradable after costs.

This is the main lesson added by the recent native `15m` work.

### Explicit thesis template

Going forward, new theses should be designed in this order:

1. isolate a favorable economic slice
2. use classification or ranking only inside that slice
3. test simple execution before any advanced optimization

Every new thesis should explicitly answer:

- `Slice`
  - what market condition, event state, or liquidity/participation regime is being isolated
  - why that slice should have positive absolute economics after costs
- `Selector`
  - how the best opportunities are ranked or classified within that slice
  - why this selector should improve concentration rather than just improve generic prediction metrics
- `Execution`
  - the simplest monetization rule to test first
  - examples: fixed hold, top-k rebalance, one-entry-per-event, banded rule
- `Failure condition`
  - what result kills the thesis quickly
  - examples: top slice still negative after costs, one-name concentration, collapse under broader validation

In short:

> design theses around favorable economic slices first, and only then use classification or ranking as a selector inside those slices.

## Strategic Direction

### Deprioritized

These are not the best next moves now:

- native `15m` continuation score ports
- native `15m` direct `E102` / `E211` ports
- nearby `60m` feature-family remix branches
- PPO / reward tuning as signal discovery

### Preferred

These are the better directions now:

- native `15m` event systems
- session-aware event systems
- regime-aware event systems
- holding-horizon-specific `15m` designs
- top-k event selection
- materially new context layers such as `60m + daily`
- slice-first designs that begin from favorable liquidity, participation, cross-sectional leadership, or volatility states

## Program Structure

### Thesis program

- work in batches of `10` theses
- target roughly `50` high-value theses over time
- run at most `2` major theses concurrently
- baseline only the top `2-3` research survivors per batch

### Branch outcomes

Each thesis ends as one of:

- `advance`
- `research_only`
- `kill`

### Gates

#### Research

- positive real-vs-shuffled separation
- at least one credible candidate

#### Baseline

- beats `FLAT`
- not a one-name / one-window artifact
- reasonable turnover relative to payoff

#### Broader validation

- remains non-negative or clearly superior under wider coverage

#### Promotion

- beats the incumbent for its layer in executable terms
- only then can RL or more advanced execution re-enter discussion

## Current Frontier

### Incumbent

- benchmark: `SIGNAL_E211_BANDED_68`
- role: executable control

### Completed native `15m` theses

- `Native15mExecution`
  - research alive
  - executable validation failed
- `Native15mFailedBreakout`
  - research alive
  - baseline failed
- `Native15mOpenDrive`
  - research alive
  - executable baseline active and broad enough to matter
  - still net negative after costs
- `Native15mSessionPhase`
  - research alive
  - baseline failed
- `Native15mHoldingHorizon`
  - research alive
  - baseline failed
- `Native15mTopKEventRank`
  - research alive
  - live executable evidence failed
- `Native15mMeanReversionExhaustion`
  - research alive
  - first direct compare positive
  - broader validation failed

### Current next thesis

- `SixtyMinuteDailyContext`
  - materially new context layer beyond the current `60m` families
  - next thesis to implement after `Native15mMeanReversionExhaustion` failed broader validation

## Immediate Plan

Implement next:

- wire `SixtyMinuteDailyContext`
- then run its research mode once implementation is complete

Decision rule:

- if research is alive:
  - baseline only the strongest survivor or two
- if research is weak:
  - close quickly and move to the next ranked thesis

## Short-Term Queue

Continue in this order:

1. `SixtyMinuteDailyContext`
2. `Native15mBreadthEvent`
3. `EventConditionedSizingVeto`
4. `NewDataAxisIfAvailable`

## Source Of Truth

### Canonical strategy doc

- [grand_plan.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan.md)

### Current state and verdicts

- [current_layer_decision_memo.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/current_layer_decision_memo.md)
- [branch_decision_scoreboard.csv](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/branch_decision_scoreboard.csv)
- [experiment_branch_registry.csv](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/experiment_branch_registry.csv)
- [experiment_performance_master.csv](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/experiment_performance_master.csv)

### Active batch docs

- [thesis_batch_01.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01.md)
- [thesis_batch_01_closeout.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01_closeout.md)

### Logs

- [milestone_log.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/milestone_log.md)
- [run_monitor_log.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/run_monitor_log.md)

### Reference / historical docs

- [PLAN.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/PLAN.md)
- [grand_plan_tracker.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan_tracker.md)
- [project_state_checkpoint_2026-03-17.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/project_state_checkpoint_2026-03-17.md)
- [experiment_strategy_guide.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/experiment_strategy_guide.md)

## Batch 02 Update

Date: 2026-04-24

Batch 01 is closed / held:

- `T01-T09` reached research or baseline verdicts
- all executable challengers remained `research_only`
- `T10` was not opened because no concrete new local data axis was found
- `SIGNAL_E211_BANDED_68` remains the incumbent
- RL remains frozen

Batch 02 is now the active planning batch.

### Next branch

Start with:

- `TB02_T01 CrossSectionalCommonalityResidual`

Rationale:

- Batch 01 showed that single-name prediction quality is not enough
- recent intraday evidence favors cross-sectional/commonality and liquidity-aware structure
- the current repo already has market and sector context, so this is feasible without inventing a vague new data feed

### Batch 02 artifact set

- [thesis_batch_02.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02.md)
- [thesis_batch_02_ranked.csv](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02_ranked.csv)
- [thesis_batch_02_closeout.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02_closeout.md)

### Batch 02 rule

Every branch must explain why its slice should have positive absolute economics before ranking or classification begins. If that slice cannot be stated plainly, the branch should not be opened.
