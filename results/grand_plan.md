# Grand Plan

Date: 2026-03-27

## 2026-05-05 Status Update

The broad external-data rescue program has now been tested enough to tighten the plan.

- `TB07_T01 DeliveryPercentRegime`: completed, failed same-universe buy-hold
- `TB07_T02 FOOpenInterestPositioning`: completed, failed same-universe buy-hold
- `TB07_T04 BreadthConfirmationGate`: completed, failed same-universe buy-hold
- `TB07_T03 EarningsEventRisk`: template-only; not populated from Zerodha
- `TB08` retail-feasible pairs / relative-value scan: completed, decisively negative

Updated planning rule:

1. do not open another broad OHLCV selector, wrapper, or market-wide gate branch on this retail stack
2. treat delivery, OI, and breadth as possible conditioning signals, not as proven standalone alpha engines
3. if research continues, the next branch should be a narrow incumbent overlay such as `TB09_T01 DeliveryAwareIncumbentOverlay`
4. if that overlay also fails, stop autonomous systematic research on this stack rather than widening the branch family again

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
- the regulatory fee stack is stable and correctly modeled
- slippage calibration, portfolio wrapper choice, holding horizon, and instrument choice are still open economic levers
- many branches improve research metrics without improving monetization
- `E211` remains the strongest durable executable benchmark
- Batch 01 and early Batch 02 now show that standalone OHLCV-derived short-horizon classifiers, event classifiers, and path-aware event-outcome labels are not the current highest-value alpha path

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

### Batch 01 and Batch 02 update

The slice-first rule remains correct, but the evidence is now sharper:

- a better classifier is not enough
- a better event label is not enough
- target-before-stop labels are not enough if the event slice has negative path payoff
- quality filters that become too sparse are not tradable evidence
- the next useful role for prediction is audit, veto, sizing, timing, and portfolio construction around the incumbent

So the research program should not keep widening standalone OHLCV predictor families until a materially new information axis is available.

## Strategic Direction

### Deprioritized

These are not the best next moves now:

- native `15m` continuation score ports
- native `15m` direct `E102` / `E211` ports
- nearby `60m` feature-family remix branches
- PPO / reward tuning as signal discovery

### Preferred

These are the better directions now:

- cost and slippage calibration on the existing incumbent and strongest challengers
- portfolio construction overlays that control concentration, short-side drag, and turnover
- instrument migration tests where the same signal is evaluated on cheaper futures cost profiles
- incumbent-specific execution timing, veto, and sizing overlays on `SIGNAL_E211_BANDED_68`
- only after those, a small number of event/state theses whose favorable slice has positive absolute economics before classification begins

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

### Batch 06 closeout

Date: 2026-05-04

`TB06` is closed as `research_only`.

The batch tested Zerodha-only OHLCV swing rescue paths after the `PortfolioRank60m E1006` long-window failure:

- large-cap stock rotation
- passive-plus-active throttle
- winner retention
- loser avoidance
- ETF momentum and ETF low-vol rotation
- mid/small-cap momentum and low-vol rotation
- RL-style drawdown guardrail overlays

None beat same-universe buy-hold with adequate fold robustness. The strongest guarded profile reached `16.79%` against `17.12%` buy-hold with only `4 / 10` folds won. The mid/small-cap test was especially decisive: buy-hold averaged `33.17%`, while the best rotation variant reached only `12.52%`.

Conclusion:

- do not reopen pure OHLCV rotation or guardrail-rescue theses in this cycle
- guardrails remain useful only as risk controls after alpha exists
- the next real research move must add a new information axis

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

- `TB07 ExternalDataAxisReadiness`
  - first command: `python -u -B ssell1.py --mode signal_diagnostic_tb07_external_data_readiness`
  - purpose: check whether delivery percentage, F&O OI, earnings calendar, or breadth files are locally available with usable schemas
  - do not open another OHLCV-only thesis unless the universe, benchmark, or data axis changes materially

## Immediate Plan

Implement next:

- run `TB07` external-data readiness
- if a file is ready, wire only that thesis first
- if no file is ready, pause model work and prepare the missing data file before opening another strategy run

Decision rule:

- if a new information axis is available:
  - test it against same-universe buy-hold, not just against `E211`
- if no new information axis is available:
  - do not run another OHLCV selector; the evidence base is exhausted for this cycle

## Short-Term Queue

Continue in this order:

1. `TB07_T00 ExternalDataAxisReadiness`
2. `TB07_T01 DeliveryPercentRegime`, only if `data/nse_delivery_bhavcopy.csv` is ready
3. `TB07_T02 FOOpenInterestPositioning`, only if `data/nse_fno_bhavcopy_oi.csv` is ready
4. `TB07_T03 EarningsEventRisk`, only if `data/earnings_calendar.csv` is ready
5. `TB07_T04 BreadthConfirmationGate`, only if `data/nifty500_daily_ohlcv.csv` is ready
6. Deployment/risk guardrails only after a strategy beats buy-hold

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

Batch 02 is now treated as the completed diagnostic batch that confirmed the current standalone predictor ceiling.

### Current branch

Batch 02 has completed:

- `TB02_T01 CrossSectionalCommonalityResidual`: closed `research_only`
- `TB02_T02 IntradayVolumeLiquidityForecast`: closed `research_only`
- `TB02_T03 EventOutcomeAccounting`: closed `research_only`

The next active branch is now:

- `TB03_T01 SlippageSensitivityCalibration`

Rationale:

- Batch 02 confirmed that better OHLCV-derived prediction and better event labels still do not guarantee positive executable economics
- the revised review of Batch 01 and Batch 02 also showed that several branches sit closer to the friction boundary than the older writeups implied
- the fastest next information gain is therefore not another predictor family, but an execution-cost recalibration pass inside the current framework

### Batch 03 update

Date: 2026-04-28

Batch 03 is now the active planning batch.

Theme:

- treat signal quality as real but economically marginal
- measure how much slippage, wrapper design, holding horizon, and instrument cost profile change executable sign
- only resume broader discovery after these internal levers are exhausted honestly

Priority order:

1. `TB03_T01 SlippageSensitivityCalibration`
2. `TB03_T02 LiquidityTieredSlippageMap`
3. `TB03_T03 FuturesCostProfilePort`
4. `TB03_T04 PortfolioRankLongOnly`
5. `TB03_T05 HoldingHorizonE1903Sweep`

### Batch 02 artifact set

- [thesis_batch_02.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02.md)
- [thesis_batch_02_ranked.csv](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02_ranked.csv)
- [thesis_batch_02_closeout.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_02_closeout.md)

### Batch 02 rule

Every branch must explain why its slice should have positive absolute economics before ranking or classification begins. If that slice cannot be stated plainly, the branch should not be opened.
