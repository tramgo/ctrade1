## Current Layer Decision Memo

Date: 2026-03-24

### Decision

The current `60m` signal-discovery layer is now explored enough for this cycle.

We are freezing:

- `SIGNAL_E211_BANDED_68` as the incumbent benchmark
- all recent challenger branches as `research_only`
- RL promotion for new branches on this information layer

We are pausing:

- nearby `60m` feature-variant branch creation
- RL rescue attempts for challenger branches
- threshold / reward / PPO tuning as a path to create alpha

### Why

Across multiple distinct theses, the pattern stayed consistent:

- research metrics often showed real structure
- baseline monetization did not beat the incumbent benchmark

Branch summary:

- `E211_Incumbent`
  - best baseline: `SIGNAL_E211_BANDED_68`
  - return: `+0.0001013`
- `MarketState60m`
  - best baseline: `SIGNAL_E801_BANDED_70`
  - return: `+0.0000655`
- `CrossSectional60m`
  - best baseline: `SIGNAL_E501_BANDED_64`
  - return: `-0.0000530`
- `Multiscale60m`
  - best baseline: `SIGNAL_E906_LONGONLY`
  - return: `-0.0001367`
- `SecondTimeframe60m`
  - best baseline: `SIGNAL_E1102_BANDED_70`
  - return: `-0.0029406`
- `IntrahourPathV1`
  - best baseline: `SIGNAL_E1201_BANDED_70`
  - return: `-0.0032871`
- `PortfolioRank60m`
  - best baseline: `E1006_PORTFOLIO_TOP3_BOTTOM3`
  - return: `-0.0021876`
- `SetupRegime`
  - best baseline: `SIGNAL_E703_BANDED_66`
  - return: `-0.0005880`
- `AblationGrid`
  - best baseline: `SIGNAL_E605_BANDED_70`
  - return: `-0.0025437`

### Practical conclusion

This means the current `60m` OHLCV-derived research layer is productive for understanding signal structure, but not for generating a stronger executable post-cost branch than `E211`.

The `intrahour_path_v1` branch strengthened that conclusion rather than weakening it:

- research quality was strong and all four `E120x` candidates survived shortlist review
- best academic candidates were `E1203` and `E1204`
- best executable candidate was `SIGNAL_E1201_BANDED_70`
- baseline result remained materially below `E211` at `-0.0032871`
- turnover and trade count were both substantially higher than the incumbent benchmark

### Native `15m` follow-up

We then tested native `15m` execution directly instead of compressing fast information back into the `60m` decision layer.

What happened:

- native `15m` research was clearly alive
- `E1501` was the research leader in the direct native-`15m` branch
- `E1502` showed a sparse initial positive blip, but broader validation turned negative
- native-`15m` `E211` was inert in direct executable comparison
- broader `15m` shortlist baselines showed native-`15m` `E102` inert and native-`15m` `E1301` active but still negative

Validated native `15m` outcomes:

- `SIGNAL_E1502_BANDED_66`
  - broader validation return: `-0.0001730`
  - turnover: `0.2102`
  - trades: `0.6049`
- native-`15m` `E1501`
  - direct comparison best result: `SIGNAL_E1501_BANDED_70`
  - return: `-0.0006312`
- native-`15m` `E211`
  - direct comparison remained effectively flat / inert
- broader native-`15m` shortlist check
  - `E102` remained inert
  - `E1301_BANDED_70` was active but still negative at `-0.0001287`

This matters because it narrows the interpretation:

- native `15m` is not devoid of predictive structure
- but the classifier / ranking families we ported or adapted so far have not produced a durable executable winner
- the next sensible native-`15m` step is event-driven, not another broad score-port

We then tested the first native `15m` event thesis:

- `native_15m_failed_breakout`
  - research leader: `E1602`
  - research profile:
    - AUC: `0.5750`
    - balanced accuracy: `0.5538`
    - spread: `0.0026511`
  - best executable baseline:
    - `SIGNAL_E1601_BANDED_70`
    - return: `-0.0000582`
    - turnover: `0.0370`
    - trades: `0.0494`
  - important practical read:
    - `E1601` was too sparse to matter
    - `E1602` was the real research candidate, but active and clearly negative in executable baseline at `-0.0016295`
  - verdict:
    - `research_only`

This matters because it rules out another serious native-`15m` event thesis without changing the benchmark:

- native `15m` failed-breakout logic was a valid idea
- research again looked alive
- executable baseline again did not survive

We therefore implemented the next native-`15m` thesis:

- `native_15m_open_drive`
  - opening-range / open-drive event system
  - best research candidate: `E1702`
  - research profile:
    - AUC: `0.5771`
    - balanced accuracy: `0.5565`
    - spread: `0.0014271`
  - best executable baseline:
    - `SIGNAL_E1701_BANDED_70`
    - return: `-0.0006190`
    - turnover: `0.6599`
    - trades: `4.3086`
  - practical read:
    - the branch was active and broad enough to be meaningful
    - but both `E1701` and `E1702` remained net negative after costs
  - verdict:
    - `research_only`

So the native-`15m` event path remains interesting, but not yet executable:

- `Native15mFailedBreakout` was research-alive but baseline-negative
- `Native15mOpenDrive` was research-alive and executable-active, but still baseline-negative

We therefore move to the next native-`15m` thesis:

- `native_15m_session_phase`
  - session-aware event system
  - implementation complete
  - research and baseline results pending

### Sharpened design rule

The latest native-`15m` comparisons clarify an important point that now becomes explicit in the research plan:

- a branch is not interesting just because it classifies well
- a branch must classify within a slice that is itself economically tradable after costs

In practice this means:

- positive relative separation is not enough if the top bucket is still economically weak
- for native `15m`, event selection and regime selection now matter more than another broad continuous score port
- future thesis ranking should prefer branches that first isolate favorable session or regime conditions, and only then rank opportunities inside them

### Fresh incumbent revalidation

We reran the full baseline suite on 2026-03-17 and `E211` replicated its benchmark result exactly.

- policy: `SIGNAL_E211_BANDED_68`
- test return: `+0.0001012555869542606`
- test drawdown: `0.00026512389373354515`
- test Sharpe: `-5.567773919304102`
- test turnover: `0.7253086414654063`
- test trades: `1.2222222222222223`

This confirms:

- `E211` remains the top executable baseline in the current suite
- the benchmark is reproducible on the current code and cached data
- the layer is still not strong enough to treat as deployable alpha

### Raw signal-quality check: `E211` vs `E801`

We also ran a bucketed signal-quality diagnostic on the out-of-sample predictions for `E211` and `E801`.

- `E211`
  - top decile average realized return: `0.01310`
  - bottom decile average realized return: `0.00229`
  - top-minus-bottom spread: `0.01080`
  - bucket monotonicity: `1.00`
- `E801`
  - top decile average realized return: `0.01145`
  - bottom decile average realized return: `0.00276`
  - top-minus-bottom spread: `0.00869`
  - bucket monotonicity: `0.915`

This matters because it shows `E211` is not only the better executable baseline. It also has the cleaner raw ranking profile versus the strongest challenger.

So the current conclusion is stronger:

- `E211` remains the best benchmark on execution
- `E211` also remains the stronger raw signal among the top surviving challengers
- `E801` is still a real signal, but not a superior one

### Allowed next moves

Only reopen active discovery if the next thesis is materially different from the current layer. Preferred options:

1. True second-timeframe input, not only derived multi-scale features.
2. Richer regime/state engine with materially new information, not another variant of current labels.
3. New data or portfolio context beyond the current `60m` OHLCV-derived layer.
4. Native `15m` event systems that are structurally different from the ranking / continuation families already tested.

### Not allowed next moves

- another nearby `60m` setup family sweep
- RL promotion without baseline superiority
- branch-local threshold rescue work
- PPO / reward tuning as a substitute for signal quality

### Operating rule going forward

Until a new branch beats `SIGNAL_E211_BANDED_68` in baseline execution:

- keep `E211` as benchmark
- keep challengers as research artifacts
- keep RL out of scope
