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

We then tested a hold-duration correction thesis:

- `native_15m_holding_horizon`
  - best research candidate: `E1903`
  - research profile:
    - AUC: `0.6071`
    - balanced accuracy: `0.5832`
    - spread: `0.0008443`
  - best executable baseline:
    - `SIGNAL_E1902_BANDED_70`
    - return: `-0.0016108`
    - turnover: `0.7236`
    - trades: `3.3827`
  - practical read:
    - `E1902` was the least-bad executable version and the branch was broad enough to be meaningful
    - explicit hold-duration matching still did not produce a positive post-cost baseline
  - verdict:
    - `research_only`

We therefore move to the next native-`15m` thesis:

- `native_15m_topk_event_rank`
  - cross-sectional event ranking inside strict favorable slices
  - research completed and alive
  - best research candidate:
    - `E2003`
  - research profile:
    - AUC: `0.6068`
    - balanced accuracy: `0.5823`
    - spread: `0.0010655`
  - important practical read:
    - classification quality improved meaningfully versus native-`15m` `E211`
    - but the raw economic shape was still weaker than `E211`
  - baseline read:
    - live baseline output showed `E2003` and `E2004` broadly negative
    - `E2002_BANDED_*` was mostly flat or negative
    - only `E2002_LONGONLY` showed occasional isolated positive slices
  - verdict:
    - `research_only`

We then tested the next slice-first native-`15m` thesis:

- `native_15m_mean_reversion_exhaustion`
  - research completed and alive
  - best research candidates:
    - `E2104`
    - `E2102`
  - research profile:
    - `E2104`
      - AUC: `0.6266`
      - balanced accuracy: `0.5980`
      - spread: `0.0006549`
    - `E2102`
      - AUC: `0.6214`
      - balanced accuracy: `0.5885`
      - spread: `0.0044532`
  - best executable baseline:
    - `SIGNAL_E2104_LONGONLY`
    - return: `+0.0006684`
    - turnover: `0.1552`
    - trades: `6.2469`
  - direct compare read:
    - `SIGNAL_E2104_LONGONLY` beat `FLAT`
    - `SIGNAL_E2104_LONGONLY` also beat native-`15m` `SIGNAL_E211_BANDED_68` in the direct comparison frame, where `E211` was inert
    - breadth remained meaningful:
      - positive rows `34`
      - zero rows `6`
      - negative rows `41`
      - positive tickers `15`
      - negative tickers `12`
      - top positive share `0.4823`
  - practical read:
    - this is the first recent native-`15m` branch with a positive executable baseline and real breadth
    - the result is still not strong enough to declare a new incumbent because the path remains noisy and the rest of the family is weak
  - wider validation:
    - `SIGNAL_E2104_LONGONLY` widened to `162` rows and turned negative at `-0.0004468`
    - row breadth weakened to `52` positive, `15` zero, `95` negative
    - ticker breadth weakened to `8` positive versus `19` negative
    - native-`15m` `SIGNAL_E211_BANDED_68` remained inert in the same frame
  - verdict:
    - `research_only`

This matters because it shows the process is working as intended:

- the first positive baseline was not ignored
- the branch earned a broader validation pass
- broader coverage then rejected it before we mistook a promising lead for a durable engine

### Sharpened design rule

The latest native-`15m` comparisons clarify an important point that now becomes explicit in the research plan:

- a branch is not interesting just because it classifies well
- a branch must classify within a slice that is itself economically tradable after costs

In practice this means:

- positive relative separation is not enough if the top bucket is still economically weak
- for native `15m`, event selection and regime selection now matter more than another broad continuous score port
- future thesis ranking should prefer branches that first isolate favorable session or regime conditions, and only then rank opportunities inside them

This also means:

- even the cleaner slice-first `TopK` design was not enough by itself
- the next thesis should isolate economic favorability even more directly rather than widening back into generic scoring

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

### Daily-context result: still research-only

We then tested the materially new higher-timeframe context thesis:

- `SixtyMinuteDailyContext`
  - research completed and was alive
  - best research candidate:
    - `E2201`
  - research profile:
    - AUC: `0.571551488124976`
    - balanced accuracy: `0.5577539690068156`
    - spread: `0.003482326754324493`
    - shuffled AUC: `0.5009387106034251`
    - shuffled balanced accuracy: `0.5003693764548243`
  - shortlist read:
    - `E2201` was the only eligible survivor with both positive real-vs-shuffled gaps and enough sample count
    - `E2202-E2204` either lost separation, lost economics, or became too weak to justify executable promotion
  - best executable baseline:
    - `SIGNAL_E2201_BANDED_70`
    - return: `-0.0018261473995522`
    - drawdown: `0.0020396454407398`
    - turnover: `0.6037986701253815`
    - trades: `1.6296296296296295`
  - breadth / concentration read:
    - positive tickers `2`
    - zero tickers `14`
    - negative tickers `11`
    - top positive share `0.917653928609168`
  - verdict:
    - `research_only`

This matters because the thesis did satisfy the "materially new information layer" requirement, but it still failed the only test that matters here:

- the research separation was real
- the executable baseline was negative after costs
- it did not beat `FLAT`
- it did not come close to beating `SIGNAL_E211_BANDED_68`
- the positive contribution profile was too narrow to justify rescue work

So the conclusion becomes sharper again:

- adding daily carry/context information was a valid thesis
- it improved understanding of where signal structure exists
- it still did not produce a better executable challenger than `E211`
- the next thesis should return to native `15m` event gating, now using breadth as the favorable slice rather than another generic score family

### Breadth-event result: still research-only

We then tested the next native `15m` event-gating thesis:

- `Native15mBreadthEvent`
  - research completed and was alive
  - best research candidate:
    - `E2302`
  - research profile:
    - AUC: `0.5391964901260273`
    - balanced accuracy: `0.5270546797374717`
    - spread: `0.0007192402278572606`
    - shuffled AUC: `0.49908554485027284`
    - shuffled balanced accuracy: `0.4994444781878123`
  - shortlist read:
    - `E2302` was the clear breadth-event survivor
    - `E2304` was weak enough to justify only a narrow executable check
    - `E2301` missed the economics gate and `E2303` was research-alive but not strong enough to change the baseline plan
  - best executable baseline:
    - `SIGNAL_E2302_BANDED_70`
    - return: `-0.00044532045311487247`
    - drawdown: `0.000683371613682473`
    - turnover: `0.2656089743301093`
    - trades: `2.6`
  - practical read:
    - the breadth-positive slice was real enough to produce one credible research survivor
    - but executable monetization still failed the only gate that matters here
    - looser `E2302` bands and all tested `E2304` policies became more negative rather than improving concentration
  - verdict:
    - `research_only`

This sharpens the native `15m` lesson again:

- internal breadth can help isolate a cleaner research slice
- that alone is still not enough to produce a post-cost executable challenger
- the next thesis should therefore move one layer closer to execution control and test whether event-conditioned veto / sizing can improve `E211` rather than replacing it outright

### Allowed next moves

Only reopen active discovery if the next thesis is materially different from the current layer. Preferred options:

1. Native `15m` event systems that isolate favorable breadth states before ranking entries.
2. True second-timeframe input, not only derived multi-scale features.
3. Richer regime/state engine with materially new information, not another variant of current labels.
4. New data or portfolio context beyond the current price-derived layer.

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

### Event-conditioned veto overlay result: useful control, not a challenger

We closed the incumbent-overlay thesis `EventConditionedSizingVeto` after a clean research-plus-baseline cycle.

- research read:
  - `E2403` was the strongest overlay survivor
  - incumbent-entry audit spread: `0.001316191246583983`
  - kept mean trade pnl: `0.0011981066685668035`
  - vetoed mean trade pnl: `-0.00011808457801717949`
- executable read:
  - best policy: `SIGNAL_E2403_E211_EVENT_CONTEXT_VETO`
  - return: `6.986428963125287e-05`
  - drawdown: `9.031270134116682e-05`
  - turnover: `0.370370370037037`
  - trades: `0.4444444444444444`
  - ticker breadth: `3` positive, `21` zero, `3` negative
- incumbent compare:
  - `SIGNAL_E211_BANDED_68` kept the better return at `0.0001012555869542`
  - the overlay did improve drawdown and turnover, but not enough to justify replacing or advancing past the incumbent
- verdict:
  - `research_only`

So the project lesson becomes more precise again:

- prior failed standalone branches can still add value as execution-control overlays
- that value is not enough unless it survives the executable benchmark gate
- reduced drawdown alone does not promote a branch when return falls below the incumbent

### Immediate next gate

- `TB01_T10 NewDataAxisIfAvailable` was not opened because no concrete local new data source was found
- Batch 01 is now closed / held with no promoted challenger
- Batch 02 is opened for planning, with `TB02_T01 CrossSectionalCommonalityResidual` as the next design candidate
- do not open `TB02_T10 NewExternalDataAxis` until a real local external data feed exists

### Batch 02 direction

Batch 02 should move away from nearby native-`15m` classifier variants and toward:

- cross-sectional/commonality residual slices
- volume and liquidity state filters
- incumbent-aware veto or entry timing overlays
- portfolio construction constraints that explicitly control turnover and concentration

`TB02_T01 CrossSectionalCommonalityResidual` is now closed `research_only`.

- research:
  - only `E2501` survived promotion
  - research separation was real but weak
- executable:
  - best policy `SIGNAL_E2501_BANDED_66 = 1.0075225258618678e-05`
  - incumbent `SIGNAL_E211_BANDED_68 = 0.0001012555869542`
  - executable breadth was sparse at `1` positive, `25` zero, `1` negative
- interpretation:
  - residual/commonality slicing can produce a cleaner research candidate
  - but this first formulation did not isolate a strong enough economic slice to survive the executable gate

`TB02_T02 IntradayVolumeLiquidityForecast` is now closed `research_only`.

- research:
  - only `E2601` survived promotion
  - research separation was materially stronger than `TB02_T01`
- executable:
  - best policy `SIGNAL_E2601_BANDED_70 = -0.0007258334009476`
  - incumbent `SIGNAL_E211_BANDED_68 = 0.0001012555869542`
  - breadth was mixed at `5` positive, `12` zero, `10` negative
- interpretation:
  - adding participation and liquidity state improves research discrimination
  - but the branch still does not create a post-cost tradable edge, so "more liquidity filters" by themselves are not enough

The pre-run `TB02_T03 OpeningAuctionGapLiquidity` design has now been superseded.

The active `TB02_T03` branch is `EventOutcomeAccounting`.

Why this pivot:

- event/state ideas were already present in the repo
- the narrower remaining gap is that we still kept scoring them mostly as fixed-horizon return labels
- the next useful test is whether an event actually resolves in a tradable way, not whether it predicts a generic return statistic

So the next branch now asks:

- did the event hit target before stop in the live trade direction
- did it do so with a clean enough path to be executable
- and do the resulting simple baseline policies beat `SIGNAL_E211_BANDED_68`

`TB02_T03 EventOutcomeAccounting` is now closed `research_only`.

- broad research:
  - `E2801-E2804` produced no promoted IDs
  - the broad event definitions were too noisy
  - `E2801` and `E2804` showed only weak structure, not executable economics
- refined research:
  - `E2806` attempted to tighten `E2801` into a high-quality breakout, pullback, and reattempt pattern
  - the filter became too sparse and produced no valid experiment rows
  - `E2805`, the `E211`-style event-outcome control, was the only valid refined-run group
- `E2805` read:
  - AUC: `0.5585800644447346`
  - balanced accuracy: `0.5438344743187962`
  - top-decile net return: `-0.001912395609680604`
  - top-minus-bottom spread: `-0.00015781370424895353`
  - real-vs-shuffled spread gap: `-0.00015285913114700461`

This is a useful negative result.

It shows that the current stack can still classify path-aware outcomes, but the selected trades do not have positive expected payoff. So the next useful question is not another standalone OHLCV predictor. The next useful question is whether the incumbent's realized losers can be audited and avoided.

Next active thesis:

- `TB02_T04 RegimeSpecificIncumbentVeto`
  - run `signal_baseline_e211_entry_audit`
  - inspect where `SIGNAL_E211_BANDED_68` loses money
  - only build a veto, delay, or sizing rule if the losing regimes are clearly separable
