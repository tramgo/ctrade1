# Milestone Log

## 2026-03-25

- Implemented `Native15mFailedBreakout` research and baseline modes
- Recorded `Native15mFailedBreakout` research verdict: `E1602` led research
- Recorded `Native15mFailedBreakout` executable verdict: branch closed as `research_only`
- Added Batch 01 planning artifacts and monitoring logs
- Implemented next native-`15m` thesis: `Native15mOpenDrive`

## 2026-03-27

- Recorded `Native15mOpenDrive` research verdict: `E1702` led the branch after fixing the session filter scale mismatch
- Recorded `Native15mOpenDrive` executable verdict: branch closed as `research_only`
- Implemented next native-`15m` thesis: `Native15mSessionPhase`
- Tightened the written plan to make the new rule explicit: strong ranking is insufficient unless it sits inside a regime with positive absolute economics
- Recorded `Native15mSessionPhase` executable verdict: branch closed as `research_only`
- Implemented next native-`15m` thesis: `Native15mHoldingHorizon`
- Recorded `Native15mHoldingHorizon` executable verdict: branch closed as `research_only`
- Implemented next native-`15m` thesis: `Native15mTopKEventRank`
- Recorded `Native15mTopKEventRank` research verdict: `E2003` / `E2004` improved classification materially
- Recorded `Native15mTopKEventRank` executable verdict: branch closed as `research_only` after live baseline evidence stayed broadly negative

## 2026-04-24

- Recorded `Native15mMeanReversionExhaustion` research verdict: `E2104` / `E2102` led the branch and the first direct compare made `E2104_LONGONLY` the first serious native-`15m` challenger candidate
- Recorded `Native15mMeanReversionExhaustion` wider-validation verdict: branch closed as `research_only` after broader coverage turned `E2104_LONGONLY` negative
- Updated Batch 01 and grand plan documents so `SixtyMinuteDailyContext` is now the next thesis to implement
- Recorded `SixtyMinuteDailyContext` research verdict: `E2201` was the only eligible survivor with real-vs-shuffled separation
- Recorded `SixtyMinuteDailyContext` executable verdict: branch closed as `research_only` after all executable `E2201` policies stayed negative
- Reconciled project state so `Native15mBreadthEvent` is now the next thesis to design and implement
- Implemented `Native15mBreadthEvent` research mode and launcher wiring for the actual `ssell1.py` entrypoint
- Recorded `Native15mBreadthEvent` research verdict: `E2302` survived and justified a narrow executable baseline
- Recorded `Native15mBreadthEvent` executable verdict: branch closed as `research_only` after `SIGNAL_E2302_BANDED_70` stayed below `FLAT`
- Implemented `EventConditionedSizingVeto` as an incumbent-overlay thesis with explicit `E2401-E2403` veto candidates and per-run launcher logging
- Recorded `EventConditionedSizingVeto` research verdict: `E2403` and `E2402` survived the incumbent-entry audit and justified executable baseline
- Recorded `EventConditionedSizingVeto` executable verdict: branch closed as `research_only` after `E2403` improved drawdown and turnover but failed to beat incumbent return
- Reconciled Batch 01 tracker CSVs after `T07-T09` completion and marked `TB01_T10` as not opened because no concrete new local data axis was found
- Opened Batch 02 planning artifacts with `TB02_T01 CrossSectionalCommonalityResidual` as the next design candidate
- Implemented `TB02_T01 CrossSectionalCommonalityResidual` research and baseline wiring with `E2501-E2504`
- Recorded `TB02_T01 CrossSectionalCommonalityResidual` executable verdict: branch closed as `research_only`
- Implemented `TB02_T02 IntradayVolumeLiquidityForecast` research and baseline wiring with `E2601-E2604`
- Recorded `TB02_T02 IntradayVolumeLiquidityForecast` executable verdict: branch closed as `research_only`
- Redesigned `TB02_T03` before run as `EventOutcomeAccounting` and implemented path-aware target wiring with `E2801-E2805`, including an `E211`-logic control
- Recorded first `EventOutcomeAccounting` research read: `E2801-E2804` did not promote, so the next pass narrows to quality-filtered `E2806` plus `E2805`
- Recorded final `TB02_T03 EventOutcomeAccounting` verdict: branch closed `research_only` after `E2806` was too sparse and `E2805` showed predictive separation with negative economic spread
- Updated Batch 02 and grand plan documents so `TB02_T04 RegimeSpecificIncumbentVeto` is now the next action, focused on auditing incumbent `E211` failure modes rather than launching another standalone OHLCV predictor

## 2026-04-28

- Reframed the active plan around execution-cost calibration after reviewing the cost-model, slippage sensitivity, and portfolio-wrapper evidence
- Updated `grand_plan.md`, `codex_next_action.md`, and Batch 02 close-state docs so the next active branch is `TB03_T01 SlippageSensitivityCalibration`
- Opened Batch 03 planning artifacts centered on slippage calibration, futures cost profiles, portfolio-rank long-only wrapping, and holding-horizon rechecks
- Recorded `TB03_T01 SlippageSensitivityCalibration` result: lower friction improved `E211` and `E801` materially, but plausible cash-equity slippage relief alone did not create a meaningful new challenger
- Updated Batch 03 trackers so the next active thesis is `TB03_T03 FuturesCostProfilePort`
- Wired `signal_baseline_futures_cost_profile` into `ssell1.py` with an explicit `stock_futures` cost profile and baseline summary outputs
- Added `revalidation_matrix_2026-04-28.csv` to record branch-by-branch revalidation decisions across the tracked result set
- Recorded `TB03_T03 FuturesCostProfilePort` result: stock-futures cost assumptions improved economics only modestly and did not displace `E211`
- Wired `signal_baseline_portfolio_rank_60m_long_only` as a dedicated low-turnover long-only weekly wrapper experiment for the next active branch
