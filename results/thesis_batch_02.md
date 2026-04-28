# Thesis Batch 02

Date: 2026-04-24

Batch 02 starts after Batch 01 produced several research-alive branches but no executable challenger to `SIGNAL_E211_BANDED_68`. The lesson is not that prediction is absent. The lesson is that generic prediction, even with good AUC or top/bottom spread, has not translated into robust post-cost trading.

## Batch Objective

Find a branch that can beat `SIGNAL_E211_BANDED_68` in executable validation by designing around economic structure first:

1. `Slice`: isolate a condition where absolute economics should be favorable after costs.
2. `Selector`: rank or classify only inside that slice.
3. `Execution`: test the simplest executable rule before advanced optimization.
4. `Failure condition`: close quickly if the slice itself is not profitable, breadth collapses, or turnover overwhelms payoff.

RL remains frozen. It can return only after a baseline-first branch survives wider validation.

## Literature-Informed Direction

Recent intraday literature points us toward three practical themes:

- cross-sectional/commonality structure can carry intraday predictability better than isolated single-name classifiers
- volume, liquidity, and execution timing can decide whether a small edge survives costs
- reinforcement learning is more credible as an execution/control layer after alpha exists, not as the first alpha discovery engine

Batch 02 therefore shifts from "find a better classifier" to "find a better tradable market state, then select within it."

## Ranked Theses

### 1. `TB02_T01` CrossSectionalCommonalityResidual
Interval: `60m`

Hypothesis: the strongest tradable slice may be where a stock is moving favorably after removing market, sector, and commonality pressure. This tests residual leadership rather than raw continuation.

Success gate: best executable policy must beat `FLAT`, beat `SIGNAL_E211_BANDED_68`, and avoid one-sector concentration.

### 2. `TB02_T02` IntradayVolumeLiquidityForecast
Interval: `15m + 60m`

Hypothesis: many signals fail because they trigger during poor liquidity or exhausted participation. A volume/liquidity forecast can define when an entry is worth paying costs for.

Success gate: lower turnover-adjusted loss than prior event systems in research, and positive executable return in baseline.

### 3. `TB02_T03` EventOutcomeAccounting
Interval: `15m`

Hypothesis: event/state ideas were not the real gap; event outcome accounting was. This branch keeps the slice-first event framing, but changes the label to whether the move actually reaches target before stop in the live trade direction and with a clean enough path.

Success gate: positive post-cost baseline over multiple names, not just a few opening-window outliers.

### 4. `TB02_T04` RegimeSpecificIncumbentVeto
Interval: `60m + 15m`

Hypothesis: the best near-term path may be improving `E211` by avoiding a small number of bad regimes, not replacing its entry logic.

Success gate: improve return or materially improve Sharpe/drawdown without reducing the incumbent to a sparse artifact.

### 5. `TB02_T05` PortfolioConstructionOverlay
Interval: `60m`

Hypothesis: weak single-name edges may become useful only when position selection, concentration, and turnover are handled at the portfolio level.

Success gate: portfolio return beats `E211` after costs with controlled turnover and no single-name dominance.

### 6. `TB02_T06` RelativeVolumeLeaderLag
Interval: `15m`

Hypothesis: relative-volume leadership may isolate real institutional participation better than price-only ranking.

Success gate: top ranked slice must be positive after costs and retain breadth across names.

### 7. `TB02_T07` VolatilityCompressionExpansion
Interval: `15m + 60m`

Hypothesis: expansion after compression may be cleaner than generic continuation if liquidity and breadth are favorable.

Success gate: positive baseline with turnover no worse than the current incumbent family.

### 8. `TB02_T08` ExecutionCostAwareEntryDelay
Interval: `60m + 15m`

Hypothesis: some incumbent entries may be directionally right but entered too early or during poor micro-liquidity. A one-bar delay or liquidity-aware timing rule may improve realized economics.

Success gate: improve incumbent executable return or Sharpe without killing breadth.

### 9. `TB02_T09` SectorRotationMicroRegime
Interval: `60m`

Hypothesis: sector-relative rotation states may define a more stable favorable slice than stock-only continuation.

Success gate: executable return must be positive after costs and not dominated by one sector.

### 10. `TB02_T10` NewExternalDataAxis
Interval: `external`

Hypothesis: if all price-derived and internally derived axes continue failing, a genuinely new input source is required.

Success gate: do not open until a concrete local feed exists, such as options open interest, news/events, FII/DII flows, index futures basis, or order-book proxy data.

## Immediate Batch 02 Plan

`TB02_T01 CrossSectionalCommonalityResidual`, `TB02_T02 IntradayVolumeLiquidityForecast`, and `TB02_T03 EventOutcomeAccounting` are now closed `research_only`.

Next active branch: `TB02_T04 RegimeSpecificIncumbentVeto`.

Reason:

- `TB02_T03` showed that path-aware event labels can still classify while failing economically
- the refined `E2806` quality filter became too sparse to test, which means the current event definition has no useful middle ground between noisy and absent
- `E2805` proved the key lesson: an `E211`-style model can separate target-before-stop outcomes while its selected top bucket still loses money after costs
- the next highest-value question is therefore not "can we find another standalone predictor", but "can we isolate and avoid the incumbent's specific losing regimes"
- this keeps the research close to the only durable executable benchmark instead of widening back into generic OHLCV classifier discovery

Do not start `TB02_T10` until a real new data source exists locally.

## Batch 02 Lesson So Far

The first three Batch 02 theses reinforce the Batch 01 conclusion:

- OHLCV-derived research structure exists
- better labels and cleaner slices improve diagnosis
- none of the standalone branches have produced robust positive executable economics
- prediction remains useful as an audit, veto, sizing, or execution-control tool
- prediction should not be treated as the primary alpha generator unless a thesis first defines a slice with positive absolute economics

## Batch Rules

- No RL.
- No PPO/reward tuning.
- No broad classifier ports.
- No baseline unless research shows a favorable slice with positive economics.
- Compare every promoted branch against `SIGNAL_E211_BANDED_68`.
- Close quickly if executable validation fails after costs.
