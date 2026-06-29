## Current Layer Decision Memo

Date: 2026-03-24

## 2026-06-29 Equity OHLCV Update

`TB12_OHLCVRegimeConditionedPortfolioRank` is complete as a runtime-validated equity side branch.

Decision:

- close `TB12` as `research_only`
- do not promote any OHLCV-only equity PortfolioRank regime gate
- keep the active automation state on `TB11`; this was a side validation of the equity roadmap, not a replacement for the current options workflow
- do not open another broad OHLCV-only selector family unless a genuinely new design constraint is supplied

Key evidence:

| Candidate | Best Gate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Verdict |
|---|---|---:|---:|---:|---|
| `E1006 top3 every_10` | `nifty_trend_up` | `10.98%` | `17.12%` | `3 / 10` | fail |
| `E1006 top3 every_10` | `breadth_supportive` | `8.26%` | `17.12%` | `4 / 10` | fail |
| `E1006 top3 every_10` | `composite_ohlcv_support` | `8.65%` | `17.12%` | `3 / 10` | fail |

Practical conclusion: the OHLCV regime gates improved the old E1006 shape versus the ungated 10-year result, but they did not solve the core buy-hold robustness failure. The best promotion-grade gate still lost badly on mean annualized return and won only `3 / 10` folds. `E1002` and `E1003` remain shorter-source controls only, not promotion-grade 10-fold evidence.

## 2026-06-29 Iterative Equity Goal - Iteration 01

The post-`TB12` iterative research loop was actioned with an external-data readiness refresh.

Command:

```powershell
python -B ssell1.py --mode signal_diagnostic_tb07_external_data_readiness
```

Result:

- `TB07_T01 DeliveryPercentRegime`: data still ready, but already tested and failed
- `TB07_T02 FOOpenInterestPositioning`: data still ready, but already tested and failed
- `TB07_T04 BreadthConfirmationGate`: data still ready, but already tested and failed
- `TB07_T03 EarningsEventRisk`: still `template_only`, not runnable as a real new data axis

Decision:

- mark Iteration 01 as `stop_path`
- do not open another equity selector, ranker, or broad OHLCV regime branch
- do not reopen delivery, OI, or breadth as standalone alpha branches without a materially new objective
- if equity work resumes, require either a populated earnings/event feed, a narrow incumbent overlay, or a deliberately different benchmark objective

## 2026-06-29 Iterative Equity Goal - Iteration 02

The OHLCV-only equity loop was reopened under the stricter user objective: find an equity strategy that beats same-universe buy-hold on mean annualized return and wins at least `7 / 10` folds.

New thesis:

- `TB13_CoreActiveTiltPortfolioRank`
- keep the same-universe equal-weight book as the core exposure
- add an E1006 PortfolioRank active sleeve only when OHLCV-derived breadth or trend gates say the active sleeve is worth taking
- use no delivery, OI, earnings, options, broker, or live data

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb13_core_active_tilt_portfolio_rank
```

Best clean candidate:

| Candidate | Gate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Buy-Hold Worst Fold | Rebalances | Top Contributor Share | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `E1006_core0.50_active0.50_top10_r30_breadth_adv_50` | `BreadthAdvFrac_1 >= 0.50` | `20.16%` | `17.12%` | `7 / 10` | `-7.49%` | `-11.44%` | `90` | `6.68%` | `promoted_candidate` |

Decision:

- mark `TB13_CoreActiveTiltPortfolioRank` as the first OHLCV-only equity `promoted_candidate` found by the iterative loop
- do not alter active automation away from `TB11`; this remains an equity research candidate, not a broker/live or RL promotion
- next required audit is explicit turnover/cost treatment for the equal-weight core sleeve plus a frozen out-of-sample replay of the predeclared breadth gate

## 2026-06-29 Iterative Equity Goal - Iteration 03

The equity objective was raised from `7 / 10` folds to beating same-universe buy-hold on every fold.

New thesis:

- `TB14_AllFoldDynamicHedgePortfolioRank`
- keep the same E1006 top-10, every-30-session PortfolioRank event stream
- use a small normal active sleeve of `+0.10`
- when relative breadth is weak (`BreadthRelAdvFrac_3 <= 0.3703703703703703`), switch to a `-0.20` active sleeve against the score-weighted top-10 basket while holding `1.20x` of the same-universe core
- use only OHLCV-derived PortfolioRank, breadth, and market-state features

Command:

```powershell
python -B ssell1.py --mode signal_baseline_tb14_all_fold_dynamic_hedge_portfolio_rank
```

Result:

| Candidate | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Worst Fold | Buy-Hold Worst Fold | Rebalances | Hedge Windows | Top Contributor Share | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `E1006_core_dynamic_active_top10_r30_relbreadth_q25_hedge` | `18.82%` | `17.12%` | `10 / 10` | `-10.69%` | `-11.44%` | `90` | `25` | `7.65%` | `promoted_candidate` |

Decision:

- mark `TB14_AllFoldDynamicHedgePortfolioRank` as the first OHLCV-only equity candidate to beat same-universe buy-hold in all `10 / 10` folds
- do not treat it as a long-only successor to `TB13`; it uses a small short active hedge in weak relative breadth regimes
- do not alter `automation_state.json` away from the active `TB11` options workflow
- next required audit is borrow/short feasibility, gross exposure and margin treatment, explicit core turnover cost, and a frozen-threshold replay without further parameter search

## 2026-05-05 Update

`TB07` is now effectively closed on the current retail-accessible stack.

Decision:

- close `TB07_T01 DeliveryPercentRegime` as `research_only`
- close `TB07_T02 FOOpenInterestPositioning` as `research_only`
- close `TB07_T04 BreadthConfirmationGate` as `research_only`
- keep `TB07_T03 EarningsEventRisk` as `template_only`
- close the first retail-feasible `TB08` pairs / relative-value scan as `research_only`
- do not open another broad standalone OHLCV or market-wide gate branch on this stack
- if research continues, narrow the scope to a delivery-aware overlay on `SIGNAL_E211_BANDED_68`

Key evidence:

| Thesis | Best Variant | Mean Ann. | Benchmark | Folds Beating Benchmark | Verdict |
|---|---|---:|---:|---:|---|
| `TB07_T01 Delivery %` | `delivery_rising` | `4.42%` | `17.95%` buy-hold | `4 / 10` | fail |
| `TB07_T02 F&O OI` | `oi_rising_and_pos` | `8.91%` | `19.02%` buy-hold | `3 / 10` | fail |
| `TB07_T04 Breadth gate` | `breadth_strong` | `2.67%` | `16.96%` buy-hold | `1 / 10` | fail |
| `TB08 Pairs` | `ICICIBANK|LT z120 e2.0` | `-52.57%` | `0%` flat | `0 / 2106` positive cells | fail |

Practical conclusion: under the current data ceiling, new information axes mainly improved participation or drawdown shape, not alpha. The only honest next systematic branch is a narrow incumbent overlay rather than another standalone selector family.

## 2026-06-20 Update

`TB10 OptionsPremiumSyntheticViability` is opened as a separate options-premium viability branch.

Decision:

- keep `TB09 DeliveryAwareIncumbentOverlay` intact
- keep `SIGNAL_E211_BANDED_68` as the equity incumbent benchmark
- do not compare the options-premium strategy to `E211` as if it were the same instrument class
- use `TB10` only to decide whether real option-chain validation is worth building
- keep live trading, broker execution, and RL out of scope

First command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb10_options_premium_scan
```

Synthetic result:

- `TB10_T02_iron_condor_2pct_5pct_wing` was the only variant worth advancing
- synthetic annualized return on estimated margin: `17.83%`
- worst trade: `-673.55` points
- max drawdown: `-1691.77` points
- naked strangles remained research-only because the 2020 crash weeks produced unacceptable tail losses
- VIX-above-median gating failed because it did not avoid the crash losses

Decision:

- advance only `TB10_T02` to real option-chain validation
- do not promote or deploy any synthetic TB10 result
- next validation must use actual NIFTY option expiries, strikes, premiums, bid-ask haircut, lot size, and margin assumptions

Real-chain validation result:

- `TB10_T02_real_chain_iron_condor_2pct_5pct_wing` produced `978` trades from `2016-06-23` to `2024-06-27`
- annualized return on estimated margin: `6.60%`
- worst trade: `-723.53` points
- max drawdown: `-4831.48` points
- verdict: `research_only`

Decision update:

- close `TB10_T02` as `research_only`
- no TB10 options variant is promoted
- only reopen options if the next branch is real-chain-first and directly targets tail control

## 2026-06-22 Update

`TB11 Real-Chain Options Tail Control` was opened under the `TB10` constraint: real-chain-first, no synthetic promotion evidence, and direct focus on reducing tail losses.

Completed commands:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_tail_control_sweep
python -u -B ssell1.py --mode signal_baseline_tb11_options_spot_regime_tail_sweep
```

Key evidence:

| Thesis | Best Variant | Trades | Ann. Return On Est. Margin | Worst Trade | Max DD | Verdict |
|---|---|---:|---:|---:|---:|---|
| `TB11_T01 OptionsTailControlSweep` | `TB11_farther_3pct_vix_shock_skip` | `864` | `10.18%` | `-611.03` | `-3650.11` | improve, not enough |
| `TB11_T02 SpotRegimeTailSweep` | `TB11_spot_3pct_ret5_m1_sma_0` | `498` | `18.19%` | `-611.03` | `-1390.71` | `advance_candidate` |

Decision:

- keep `TB11_spot_3pct_ret5_m1_sma_0` as an `advance_candidate`
- do not promote it or connect it to broker execution
- open `TB11_T03 RobustnessTailAudit` as the next required gate
- audit fold robustness, pre-2024 versus 2024 contribution, stress-week sensitivity, and max-loss budget before any further options branch expansion

`TB11_T03 RobustnessTailAudit` is now complete.

Audit read:

- all-period annualized return on estimated margin: `18.19%`
- pre-2024 annualized return on estimated margin: `16.60%`
- 2024 annualized return on estimated margin: `199.33%`
- 2024 PnL share: `41.14%`
- fold 2 point PnL: `-7.42`
- worst trade remains `-611.03`
- excluding the worst 2022 trade window leaves max drawdown unchanged at `-1390.71`

Decision update:

- block promotion of `TB11_spot_3pct_ret5_m1_sma_0`
- keep it as a research artifact
- only continue options through a narrow `TB11_T04 LossClusterMaxRiskControl` design
- do not run broad sweep, RL, live trading, or broker execution

`TB11_T04 LossClusterMaxRiskControl` is now complete.

Best candidate:

- `TB11_T04_3pct_5wing_ret5_1pct_liq50k`
- trades: `157`
- annualized return on estimated margin: `24.92%`
- total PnL: `3229.66` points
- worst trade: `-270.89` points
- max drawdown: `-274.28` points
- win rate: `88.54%`
- 2024 PnL share: `9.24%`

Decision update:

- mark `TB11_T04_3pct_5wing_ret5_1pct_liq50k` as `advance_candidate_needs_broader_validation`
- do not promote yet
- next gate is `TB11_T05 BroaderValidation`
- the validation must stress costs/haircuts, liquidity-floor stability, skipped-leg bias, and missing-wing sensitivity

`TB11_T05 BroaderValidation` and `TB11_T06 FrontierOptimization` are now complete.

Key result:

- `TB11_T06_liq60k_ret5_0p01`
- trades: `141`
- annualized return on estimated margin: `24.38%`
- total PnL: `2984.61` points
- worst trade: `-69.21` points
- max drawdown: `-69.21` points
- win rate: `89.36%`
- all calendar years positive
- all four chronological folds positive

Decision update:

- supersede the T04 candidate with `TB11_T06_liq60k_ret5_0p01`
- keep verdict as `advance_candidate_needs_harsh_cost_validation`
- next gate is `TB11_T07 HarshCostValidation`
- do not promote until this exact candidate survives `20-25%` premium haircut and `2-3` points per-leg cost stress

`TB11_T07 HarshCostValidation`, `TB11_T08 ExpiryRiskFrontier`, and `TB11_T09 LowLossHarshCost` are now complete.

Current frontier:

| Candidate | Role | Trades | Base Ann. | Base Worst | Base Max DD | Harshest Ann. | Harshest Worst | Harshest Max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `TB11_T06_liq60k_ret5_0p01` | growth | `141` | `24.38%` | `-69.21` | `-69.21` | `11.77%` | `-86.61` | `-142.84` |
| `TB11_T08_dte8_ret5_0p02` | defensive | `51` | `17.57%` | `-1.25` | `-1.25` | `9.11%` | `-10.36` | `-18.77` |

Decision update:

- do not choose a final promoted branch yet
- preserve both candidates as the current efficient frontier
- next gate is `TB11_T10 AllocationSizingFrontier`
- compare fixed-risk allocation between growth and defensive candidates before any promotion discussion

`TB11_T10 AllocationSizingFrontier` and `TB11_T11 ConditionalOverlayFrontier` are now complete.

Key read:

- fixed allocation reduced risk mostly by scaling down growth exposure
- conditional overlay created a better frontier by using defensive trades on defensive dates and retaining partial growth exposure elsewhere

Current preferred balanced overlay:

- allocation: `def_full_resg50_ovg50`
- base annualized return: `24.00%`
- base worst trade: `-34.60`
- base max drawdown: `-34.60`
- harsh-stress annualized return: `12.66%`
- harsh-stress worst trade: `-43.30`
- harsh-stress max drawdown: `-91.32`
- base, moderate, and harsh chronological folds are all positive

Decision update:

- mark `def_full_resg50_ovg50` as the current balanced candidate
- keep `def_full_resg100_ovg50` as the max-return candidate
- next gate is `TB11_T12 LotCapitalRiskCalibration`
- no promotion until point-based results are converted into rupee/lot/capital risk constraints

## 2026-05-04 Update

`TB06` is closed. The Zerodha-only OHLCV swing rescue path failed across large-cap stocks, ETFs, and the 30-name mid/small-cap universe.

Decision:

- keep `SIGNAL_E211_BANDED_68` as incumbent
- keep RL frozen
- stop opening pure OHLCV rotation / wrapper / guardrail rescue theses
- move to `TB07 ExternalDataAxisReadiness`

Key evidence:

| Strategy Group | Best Mean Ann. | Buy-Hold Ann. | Best Fold Wins | Verdict |
|---|---:|---:|---:|---|
| Large-cap OHLCV variants | `14.01%` | `17.12%` | `4 / 10` | fail |
| ETF rotation variants | `12.18%` | `15.51%` | `2 / 10` | fail |
| Mid/small-cap OHLCV variants | `12.52%` | `33.17%` | `3 / 10` | fail |
| Guardrail overlays | `16.79%` | `17.12%` | `4 / 10` | fail |

Practical conclusion: guardrails can reduce risk, but they are not alpha. The next strategy work must use a new information axis such as delivery percentage, F&O OI, earnings calendar, or market breadth.

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

### Execution-cost recalibration checkpoint

The newer review of Batch 01 and Batch 02 changes the immediate priority, but not the honesty standard.

What changed:

- the fee stack itself looks correctly modeled
- the current global slippage default is likely doing too much work in the final economics
- the `PortfolioRank60m` branch looks more like a wrapper failure than a signal failure
- several near-boundary branches still failed honestly, but they are close enough to justify a narrow cost-calibration pass

What did not change:

- there is still no confirmed executable winner
- we should not reopen broad standalone predictor discovery yet
- lower-friction or cheaper-instrument positives still need the same breadth and benchmark discipline as any other challenger

So the next operating step becomes:

- start `TB03_T01 SlippageSensitivityCalibration`
- use the existing cost-sensitivity baseline mode
- then decide whether Batch 03 should move next toward tiered slippage, futures cost profiles, portfolio-rank long-only, or an incumbent timing overlay

### TB11 options lot/capital checkpoint

`TB11_T12 LotCapitalRiskCalibration` is complete.

Evidence:

- command: `python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration`
- outputs:
  - `results/signal_baseline/tb11_options_lot_capital_risk_calibration_detail.csv`
  - `results/signal_baseline/tb11_options_lot_capital_risk_calibration_summary.csv`
  - `results/signal_baseline/tb11_options_lot_capital_risk_calibration_metadata.csv`
- tested lot sizes: `50`, `65`, `75`
- tested capital budgets: `100000` through `2000000`
- tested worst-trade budgets: `5000` through `100000`
- tested drawdown budgets: `10000` through `200000`

Decision read:

- max-return overlay `def_full_resg100_ovg50` remains the strongest capital-return profile when budgets are loose enough
- balanced overlay `def_full_resg50_ovg50` materially reduces worst trade and drawdown under harsh stress for a modest return haircut
- defensive-only `def_full_resg0_ovg0` becomes the better profile under small-capital, tight-loss, harsh-stress constraints
- no TB11 profile should be promoted until the capital-aware objective is explicit

Immediate next gate:

- `TB11_T13_CapitalAwarePolicySelection`
- choose deployment profiles and rank candidates after enforcing base plus harsh-stress rupee-risk constraints
- keep RL, live trading, and broker execution blocked

### TB11 capital-aware profile checkpoint

`TB11_T13 CapitalAwarePolicySelection` is complete.

Evidence:

- commands:
  - `python -u -B ssell1.py --mode signal_baseline_tb11_options_lot_capital_risk_calibration`
  - `python -u -B ssell1.py --mode signal_baseline_tb11_options_capital_aware_policy_selection`
- outputs:
  - `results/signal_baseline/tb11_options_capital_aware_policy_selection_summary.csv`
  - `results/signal_baseline/tb11_options_capital_aware_policy_selection_metadata.csv`

Decision read:

- after broadening T12 to all `15` T11 conditional overlays, `def_full_resg0_ovg50` wins all four capital-aware profiles
- the selected profile keeps full defensive exposure, adds `50%` growth exposure only on defensive-overlap dates, and avoids residual growth-only trades
- this improves return versus defensive-only while keeping harsh-stress budget usage much lower than max-return or residual-growth profiles

Representative current-reference lot-size `65` reads:

- `200000` capital profile: `18.61%` base / `7.33%` harsh annualized on capital, harsh worst `-2019`, harsh DD `-3660`
- `500000` capital profile: `22.33%` base / `8.80%` harsh annualized on capital, harsh worst `-6058`, harsh DD `-10980`
- `1000000` capital profile: `24.19%` base / `9.53%` harsh annualized on capital, harsh worst `-13125`, harsh DD `-23791`
- `2000000` capital profile: `25.12%` base / `9.53%` harsh annualized on capital, harsh worst `-26250`, harsh DD `-47582`

Immediate next gate:

- `TB11_T14_SelectedProfileRobustnessAudit`
- audit selected profile by year, fold, worst trades, and loss clusters
- compare against defensive-only and max-return controls
- keep RL, live trading, and broker execution blocked

### TB11 selected-profile robustness and maturity checkpoint

`TB11_T14 SelectedProfileRobustnessAudit` and `TB11_T15 SelectedProfileMaturityGate` are complete.

T14 evidence:

- selected profile: `def_full_resg0_ovg50`
- outputs:
  - `results/signal_baseline/tb11_options_selected_profile_robustness_audit_summary.csv`
  - `results/signal_baseline/tb11_options_selected_profile_robustness_audit_years.csv`
  - `results/signal_baseline/tb11_options_selected_profile_robustness_audit_folds.csv`
  - `results/signal_baseline/tb11_options_selected_profile_robustness_audit_worst_trades.csv`
  - `results/signal_baseline/tb11_options_selected_profile_robustness_audit_loss_clusters.csv`
- result:
  - folds pass in base, moderate, and harsh stress
  - concentration passes
  - loss clusters pass
  - strict all-years gate fails because `2017` contains one selected-profile trade and it is negative

T15 evidence:

- output:
  - `results/signal_baseline/tb11_options_selected_profile_maturity_gate_summary.csv`
- minimal passing hardening:
  - skip first observed selected-profile trade
  - first active trade becomes `2019-02-25`
- result:
  - base: `31.62%` annualized on margin, all years and folds positive
  - moderate stress: `23.93%` annualized on margin, all years and folds positive
  - harsh stress: `17.32%` annualized on margin, all years and folds positive

Decision read:

- the selected profile is still not promoted
- the maturity gate is promising because it fixes a sparse warmup-year failure without changing the strategy weights
- the next required check is to redo rupee and capital-budget calibration after this maturity gate

Immediate next gate:

- `TB11_T16_MaturityAdjustedRupeeProfile`
- recompute lot, rupee, margin, and capital utilization after applying the one-observation maturity gate
- keep RL, live trading, and broker execution blocked

### TB11 maturity-adjusted rupee checkpoint

`TB11_T16 MaturityAdjustedRupeeProfile` is complete.

Evidence:

- command: `python -u -B ssell1.py --mode signal_baseline_tb11_options_maturity_adjusted_rupee_profile`
- outputs:
  - `results/signal_baseline/tb11_options_maturity_adjusted_rupee_profile_summary.csv`
  - `results/signal_baseline/tb11_options_maturity_adjusted_rupee_profile_metadata.csv`
- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade

Decision read:

- the maturity-adjusted selected profile passes rupee/capital gates across base, moderate, and harsh stress
- at lot-size `65`, the `500000` capital profile supports `6` lots and keeps harsh-stress worst / DD at roughly `-6058` / `-10980`
- at `1000000` capital, the profile supports `13` lots and keeps harsh-stress worst / DD at roughly `-13125` / `-23791`
- annualized return on capital remains positive under harsh stress across tested profiles

Immediate next gate:

- superseded by `TB11_T18_ItemizedIndianFNOCostAudit`
- freeze work must wait until broker-accurate Indian F&O costs are audited
- keep RL, live trading, and broker execution blocked

### TB11 itemized Indian F&O cost checkpoint

`TB11_T17 ITMExpirySTTAudit` and `TB11_T18 ItemizedIndianFNOCostAudit` are complete.

T17 evidence:

- output:
  - `results/signal_baseline/tb11_options_itm_expiry_stt_audit_summary.csv`
  - `results/signal_baseline/tb11_options_itm_expiry_stt_audit_trades.csv`
- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- result: only `1` selected-profile trade had ITM short-leg intrinsic at expiry
- conservative short-leg intrinsic STT check did not break the base/moderate/harsh gates

T18 evidence:

- command: `python -u -B ssell1.py --mode signal_baseline_tb11_options_itemized_fno_cost_audit`
- outputs:
  - `results/signal_baseline/tb11_options_itemized_fno_cost_audit_summary.csv`
  - `results/signal_baseline/tb11_options_itemized_fno_cost_audit_trades.csv`
  - `results/signal_baseline/tb11_options_itemized_fno_cost_audit_legs.csv`
  - `results/signal_baseline/tb11_options_itemized_fno_cost_audit_metadata.csv`
- current cost assumptions:
  - `20` rupees option brokerage per order/leg
  - `0.05%` option sell-side premium STT
  - `0.15%` ITM intrinsic exercise/assignment stress bucket
  - `0.03553%` NSE option transaction charge on premium
  - `18%` GST on brokerage + SEBI + transaction charges
  - `10` rupees per crore SEBI charge
  - `0.003%` buy-side option stamp duty

Decision read:

- the selected maturity-gated profile passes the itemized-cost gate in base, moderate, and harsh stress
- at reference lot size `65`, itemized cost is `112.99` points versus `300/600/900` points in the old base/moderate/harsh lumped proxy
- harsh-stress annualized return after itemized cost is `26.50%`
- all years and folds remain positive
- the old lumped proxy was harsher than broker-itemized costs in this sample, but the cost module must now be mandatory for any future paper/live read

Immediate next gate:

- `TB11_T19_ProfileFreezeExecutionReadiness`
- freeze the paper-only selected profile and budget rules
- require the itemized Indian F&O cost module in every future TB11 run
- write exit-before-expiry, kill-switch, and no-trade rules
- keep RL, live trading, and broker execution blocked

### TB11 profile-freeze and staged validation checkpoint

`TB11_T19 ProfileFreezeExecutionReadiness` is complete.

Evidence:

- artifacts:
  - `results/signal_baseline/tb11_options_profile_freeze_execution_readiness.md`
  - `results/signal_baseline/tb11_options_profile_freeze_execution_readiness_summary.csv`
- selected profile: `def_full_resg0_ovg50`
- maturity gate: skip first observed selected-profile trade
- reference lot size: `65`
- itemized Indian F&O cost module: mandatory
- broker/live execution: still blocked

Staged validation plan:

- Phase 1 dry run for `1-2 months`: log every signal and simulate fills; no broker orders
- Phase 2 paper at real prices for `3-6 months`: at least `10-15` paper trades; available premiums within `10-15%` adverse tolerance; no surprise costs
- Phase 3 tiny live for `3-6 months`: future human-approved `1` lot only; at least `10` real-money trades
- Phase 4 scale: ongoing, only after phases 1-3 hold up and the target budget is revalidated

Decision read:

- T19 passes as a profile-freeze and process-readiness gate
- the result is not a live/paper order-placement approval
- the next useful engineering task is to build the dry-run signal logger so Phase 1 can produce evidence rather than relying on manual notes

Immediate next gate:

- `TB11_T20_DryRunSignalLogger`
- implement no-order signal logging for every candidate signal and skip reason
- output signal log, summary, and reconciliation artifacts
- keep Phase 1 and Phase 2 broker-order placement blocked

### TB11 dry-run signal logger checkpoint

`TB11_T20 DryRunSignalLogger` is complete.

Evidence:

- command: `python -B ssell1.py --mode signal_baseline_tb11_options_dry_run_signal_logger`
- outputs:
  - `results/signal_baseline/tb11_options_dry_run_signal_log.csv`
  - `results/signal_baseline/tb11_options_dry_run_signal_log_summary.csv`
  - `results/signal_baseline/tb11_options_dry_run_reconciliation.md`
  - `results/signal_baseline/tb11_options_dry_run_signal_log_metadata.csv`
- source mode: `historical_replay_no_order`
- selected profile: `def_full_resg0_ovg50`
- lot size: `65`

Decision read:

- the logger recorded `51` signals
- `50` signals are simulated after the maturity gate
- `1` signal is skipped by the maturity warmup rule
- broker orders allowed is `False` for the artifact
- schema gate passed
- this is a logger/readiness pass, not completion of the required 1-2 month Phase 1 dry run

Immediate next gate:

- `TB11_T21_DryRunObservedQuoteCapture`
- define the observed quote capture template and daily reconciliation workflow
- compare observed available premiums against modeled premium with the `10-15%` adverse tolerance
- keep broker orders blocked

### TB11 observed quote capture checkpoint

`TB11_T21 DryRunObservedQuoteCapture` is complete.

Evidence:

- command: `python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_capture_template`
- outputs:
  - `results/signal_baseline/tb11_options_observed_quote_capture_template.csv`
  - `results/signal_baseline/tb11_options_observed_quote_capture_template_summary.csv`
  - `results/signal_baseline/tb11_options_observed_quote_capture_template_metadata.csv`
  - `results/signal_baseline/tb11_options_observed_quote_reconciliation.md`

Decision read:

- template rows: `50`
- all rows keep `broker_order_allowed=False`
- observed quote fields are blank and ready for Phase 1 capture
- quote freshness target is `300` seconds
- adverse premium tolerance is `15%`
- template gate passed
- this is still no-order dry-run infrastructure, not paper/live approval

Immediate next gate:

- `TB11_T22_ObservedQuoteReconciliationValidator`
- score filled-in observations for quote freshness, leg completeness, spread quality, and premium tolerance
- summarize pass/fail counts and skip reasons
- keep broker orders blocked

### TB11 observed quote validator checkpoint

`TB11_T22 ObservedQuoteReconciliationValidator` is complete.

Evidence:

- command: `python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_reconciliation_validator`
- outputs:
  - `results/signal_baseline/tb11_options_observed_quote_validation_detail.csv`
  - `results/signal_baseline/tb11_options_observed_quote_validation_summary.csv`
  - `results/signal_baseline/tb11_options_observed_quote_validation_metadata.csv`

Decision read:

- validator schema gate passed
- template rows: `50`
- observed rows: `0`
- pending rows: `50`
- broker-block violations: `0`
- Phase 1 evidence gate has not passed because no real observed quotes have been collected yet

Immediate next gate:

- `TB11_T23_DryRunObservationCollection`
- collect real no-order observed quote rows for `1-2 months`
- rerun the validator after each observation batch
- require fresh quotes, all legs available, acceptable spread quality, and observed credit inside the `10-15%` adverse tolerance
- keep broker orders blocked

### TB11 dry-run observation collection setup

`TB11_T23 DryRunObservationCollection` is operationally prepared but not complete.

Evidence:

- command: `python -B ssell1.py --mode signal_baseline_tb11_options_dry_run_observation_collection_pack`
- outputs:
  - `results/signal_baseline/tb11_options_dry_run_observation_collection_20260623.csv`
  - `results/signal_baseline/tb11_options_dry_run_observation_collection_ledger.csv`
  - `results/signal_baseline/tb11_options_dry_run_observation_collection_summary.csv`
  - `results/signal_baseline/tb11_options_dry_run_observation_collection_metadata.csv`
  - `results/signal_baseline/tb11_options_dry_run_observation_collection_runbook.md`

Decision read:

- collection batch id: `TB11_PHASE1_OBS_20260623`
- rows prepared: `50`
- prior observed rows: `0`
- broker orders allowed: `False`
- status: `manual_no_order_collection_ready`
- the Phase 1 evidence gate is still open and needs real observed quote rows over `1-2 months`

Continue current gate:

- fill observed quote fields only
- rerun the observed-quote validator after each batch
- do not advance to Phase 2 until enough observations pass freshness, all-leg, spread-quality, and premium-tolerance checks

### TB11 Zerodha quote-only collector checkpoint

`TB11_T24 ZerodhaQuoteOnlyCollector` is complete as a safe collector implementation.

Evidence:

- command: `python -B ssell1.py --mode signal_baseline_tb11_options_zerodha_quote_only_collector`
- outputs:
  - `results/signal_baseline/tb11_options_zerodha_quote_only_collector_20260624.csv`
  - `results/signal_baseline/tb11_options_zerodha_quote_only_collector_summary.csv`
  - `results/signal_baseline/tb11_options_zerodha_quote_only_collector_metadata.csv`
  - `results/signal_baseline/tb11_options_zerodha_quote_only_collector_unresolved_20260624.csv`

Decision read:

- input rows: `50`
- quote symbols requested: `0`
- quote packets received: `0`
- captured rows: `0`
- unresolved rows: `50`
- broker orders allowed: `False`
- collector status: `awaiting_resolved_nfo_symbols`

Interpretation:

The quote collector is now available, but the current observation batch is still historical-replay based and has no current NFO tradingsymbols. The collector correctly refused to guess contracts or call order routes.

Immediate next gate:

- `TB11_T25_CurrentNFOLegResolver`
- generate current-day option legs from the frozen TB11 profile
- resolve those legs to current NFO symbols/tokens
- feed resolved symbols into the quote-only collector
- keep broker orders blocked
