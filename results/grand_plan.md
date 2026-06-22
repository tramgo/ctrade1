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

## 2026-06-20 TB10 Options Update

`TB10 OptionsPremiumSyntheticViability` is opened as a separate instrument-class research gate, not as a replacement for `TB09 DeliveryAwareIncumbentOverlay`.

The branch tests synthetic NIFTY weekly option-premium selling with India VIX as the volatility input. It is allowed only to decide whether real option-chain validation is worth building. It must not be treated as deployable evidence, must not use live trading, and must write explicit metadata if a NIFTY proxy is used.

Runnable mode:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb10_options_premium_scan
```

Synthetic verdict:

- `TB10_T02 IronCondorDefinedRisk` advances to real option-chain validation only
- naked short strangles stay research-only because crash-week losses are too large
- simple VIX gating failed to protect the tail
- no TB10 result is deployable until actual option-chain premiums, strikes, expiries, bid-ask haircut, lot size, and margin are validated

Real-chain verdict:

- `TB10_T02` produced a positive but weak real-chain result: `6.60%` annualized return on estimated margin across `978` trades
- worst trade was `-723.53` points and max drawdown was `-4831.48` points
- the branch is closed `research_only`
- no options-premium variant is promoted

## 2026-06-22 TB11 Options Update

`TB11 Real-Chain Options Tail Control` tested only actual option-chain bhavcopy premiums and focused on tail-control changes to the `TB10` iron-condor idea.

Executed modes:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_tail_control_sweep
python -u -B ssell1.py --mode signal_baseline_tb11_options_spot_regime_tail_sweep
```

Result:

- `TB11_farther_3pct_vix_shock_skip` improved the real-chain baseline to `10.18%` annualized return on estimated margin, with worst trade `-611.03` and max drawdown `-3650.11`
- `TB11_spot_3pct_ret5_m1_sma_0` is the current best candidate at `18.19%` annualized return on estimated margin across `498` trades, with worst trade `-611.03`, max drawdown `-1390.71`, and `76.10%` win rate
- the result is still not promoted because the worst loss remains and 2024 contribution is large enough to require concentration review

Next gate:

- run `TB11_T03 RobustnessTailAudit`
- require fold-level robustness, pre-2024 versus 2024 split, stress-week sensitivity, and max-loss-budget review
- do not promote, RL-tune, or connect options execution to broker APIs before that audit passes

Audit result:

- `TB11_T03` blocks promotion
- 2024 supplies `41.14%` of total point PnL
- fold 2 is slightly negative in point PnL at `-7.42`
- the major tail losses remain clustered around `2020-02`, `2021-01`, and `2022-06`
- excluding only the worst 2022 window does not reduce the reported max drawdown, so tail risk is not a one-trade artifact

Updated TB11 rule:

- no promotion from `TB11_spot_3pct_ret5_m1_sma_0`
- only continue through a narrow loss-cluster and max-risk-control thesis
- no broad options sweep, RL, or broker execution

`TB11_T04 LossClusterMaxRiskControl` result:

- best deployability-shaped candidate: `TB11_T04_3pct_5wing_ret5_1pct_liq50k`
- annualized return on estimated margin: `24.92%`
- trades: `157`
- worst trade: `-270.89` points
- max drawdown: `-274.28` points
- win rate: `88.54%`
- all calendar years and chronological folds are positive
- 2024 PnL share falls to `9.24%`

Updated gate:

- `TB11_T04_3pct_5wing_ret5_1pct_liq50k` is an advance candidate, not a promotion
- next gate is `TB11_T05 BroaderValidation`
- before any promotion, stress premium haircut, per-leg cost, liquidity threshold stability, skipped-leg bias, and missing-wing sensitivity

`TB11_T05` and `TB11_T06` update:

- `TB11_T05` confirmed the candidate family survives cost/haircut stress, but also showed a return/loss tradeoff across liquidity floors
- `TB11_T06_liq60k_ret5_0p01` is now the best current frontier point
- annualized return on estimated margin: `24.38%`
- worst trade and max drawdown: `-69.21` points
- all years and chronological folds are positive

Updated gate:

- do not promote yet
- run `TB11_T07 HarshCostValidation` on the exact `60k` liquidity / `1%` 5-day momentum candidate
- require survival under `20-25%` premium haircut and `2-3` points per-leg cost before any promotion discussion

`TB11_T07-TB11_T09` update:

- `TB11_T07` confirmed the growth candidate survives harsh costs in aggregate
- `TB11_T08` found a defensive expiry-risk candidate with much smaller historical losses
- `TB11_T09` confirmed the defensive candidate survives harsh costs

Current frontier:

- growth: `TB11_T06_liq60k_ret5_0p01`, base `24.38%`, worst `-69.21`, harshest tested `11.77%`
- defensive: `TB11_T08_dte8_ret5_0p02`, base `17.57%`, worst `-1.25`, harshest tested `9.11%`

Updated gate:

- next step is allocation/sizing, not another entry filter
- run `TB11_T10 AllocationSizingFrontier`
- compare growth and defensive candidates under fixed-risk capital budgets and harsh-cost lower-bound assumptions

`TB11_T10-TB11_T11` update:

- fixed allocation did not materially improve the frontier beyond exposure scaling
- conditional defensive overlay improved the return/loss shape
- max-return overlay: `def_full_resg100_ovg50`, base `27.21%`, harsh `14.12%`
- balanced overlay: `def_full_resg50_ovg50`, base `24.00%`, harsh `12.66%`, base worst loss `-34.60`

Updated gate:

- next step is rupee/lot/capital calibration
- run `TB11_T12 LotCapitalRiskCalibration`
- decide whether the balanced overlay can satisfy explicit position-size and rupee drawdown limits

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
