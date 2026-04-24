# Thesis Batch 01

Date: 2026-03-25

This batch is the first disciplined native-`15m` event-focused backlog under the long-horizon research program. The incumbent benchmark remains `SIGNAL_E211_BANDED_68`. Batch policy is `Light Parallel`: at most two major theses active at once. Early-stop policy is `Strict Runtime Only`.

## Explicit Thesis Template

Every new thesis in this batch and future batches should be designed in this order:

1. `Slice`
   - define the favorable economic slice first
   - examples: early-session leader state, high relative-volume event, calm-market stock-specific pressure, favorable liquidity/volatility regime
2. `Selector`
   - define the ranking or classification rule only inside that slice
   - examples: top-k rank, persistence score, event-quality score, relative-strength selector
3. `Execution`
   - define the simplest executable rule first
   - examples: fixed 1-2 bar hold, top-k rebalance every `15m`, one-entry-per-event rule
4. `Failure condition`
   - define what will kill the thesis quickly
   - examples: top slice still negative after costs, one-name concentration, collapse in broader validation

Working doctrine:

> design theses around favorable economic slices first, and only then use classification or ranking as a selector inside those slices.

## Ranked Theses

### 1. `TB01_T01` Native15mFailedBreakout
Interval: `15m`

Hypothesis: short-lived rejection and failed-breakout structures on native `15m` bars may monetize better as event systems than as broad classifier ports.

Success gate: at least one baseline policy must beat `FLAT` without being a one-name / one-window artifact.

### 2. `TB01_T02` Native15mOpenDrive
Interval: `15m`

Hypothesis: opening-range breakout quality, open-drive persistence, and relative early-session participation may produce a more durable intraday event edge than the failed-breakout thesis.

Success gate: at least one baseline policy must beat `FLAT` on the wider native-`15m` frame and show non-trivial breadth.

### 3. `TB01_T03` Native15mSessionPhase
Interval: `15m`

Hypothesis: separate early-session, midday, and late-session behaviors can outperform single-model `15m` scoring because the same price action means different things at different session phases.

Success gate: research must show positive real-vs-shuffled separation in at least one phase-specific candidate.

### 4. `TB01_T04` Native15mHoldingHorizon
Interval: `15m`

Hypothesis: some `15m` event signals fail because the holding horizon is wrong, not because the event is weak. Explicit short hold-vs-medium hold targets may surface usable edges.

Success gate: at least one horizon-specific branch must survive research and produce a baseline that beats `FLAT`.

### 5. `TB01_T05` Native15mTopKEventRank
Interval: `15m`

Hypothesis: top-k event selection across the universe may outperform per-name thresholding by concentrating capital only into the strongest contemporaneous `15m` setups.

Success gate: research shortlist must show stronger concentration-adjusted spread than threshold-based peers.

### 6. `TB01_T06` Native15mMeanReversionExhaustion
Interval: `15m`

Hypothesis: true exhaustion events after extreme short-horizon extension may monetize better than continuation-style `15m` families.

Success gate: at least one candidate must beat shuffled controls and survive narrow baseline.

### 7. `TB01_T07` SixtyMinuteDailyContext
Interval: `60m + daily`

Hypothesis: adding genuine higher-timeframe context is more promising than more `60m` feature recombination because it changes the information layer instead of restating it.

Success gate: must beat `SIGNAL_E211_BANDED_68` in baseline or justify broader validation with clear breadth.

### 8. `TB01_T08` Native15mBreadthEvent
Interval: `15m`

Hypothesis: market-internal breadth at native `15m` cadence may help identify when fast event signals are worth acting on.

Success gate: research must show breadth-led event candidates stronger than current native `15m` ranking survivors.

### 9. `TB01_T09` EventConditionedSizingVeto
Interval: `60m + 15m`

Hypothesis: fast `15m` event information may be more useful as sizing or veto logic on top of the slow incumbent than as a standalone alpha engine.

Success gate: must improve drawdown or Sharpe without degrading breadth materially.

### 10. `TB01_T10` NewDataAxisIfAvailable
Interval: `TBD`

Hypothesis: if price-derived information keeps failing executable validation, a materially new data axis is required.

Success gate: only opens if a concrete new data source is locally available and can be integrated without breaking the evaluation discipline.

## Batch Working Rules

- `E211` remains the benchmark until displaced in executable validation.
- Baseline budget goes only to the top `2-3` research survivors.
- Branches that fail broader validation are archived as `research_only`.
- RL remains out of scope unless a baseline-first branch earns promotion.
- Strong classification alone is not enough; a thesis must first isolate a favorable economic slice where the best-ranked cases are plausibly attractive after costs.
- Native `15m` work should prefer event selection and regime selection over broad continuous scoring, because several score-port branches already showed that relative separation can exist without tradable absolute edge.
- New theses should be rejected at design time if they begin as generic score-every-bar classifier ports without a clear favorable-slice argument.
