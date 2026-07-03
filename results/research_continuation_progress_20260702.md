# Research Continuation Progress - 2026-07-02

Source plan: `c:\Users\Ramic\Downloads\new golas today jun_07_26.txt`

## Plan Reconciliation

The attached plan sequences work as:

1. Complete post-TB14 validation steps 3, 4, 5, and 6.
2. Run TB15_T03 fresh forward sample.
3. Implement TB11_T30 IV-conditioned sizing.

Current repo evidence shows item 1 is already completed and closed:

- Step 3 walk-forward threshold replay: `step3_survives`
  - selected quantile: `0.4`
  - holdout folds beating rebalanced benchmark: `4 / 4`
- Step 4 random hedge null: `step4_survives`
  - random seeds: `1000`
  - actual percentile versus null: `0.999`
- Step 5 short feasibility: `short_cost_stress_survives`
  - hedge windows: `25`
  - historical FUTSTK coverage: `27 / 27`
  - base folds beating rebalanced benchmark: `7`
  - note: historical FUTSTK coverage is not live SLB borrow availability
- Step 6 strict OOS replay: `kill_switch_oos_replay_failed`
  - fit folds: `1-8`
  - OOS folds: `9-10`
  - OOS folds beating rebalanced benchmark: `1 / 2`
  - required OOS folds: `2`

Inference: post-TB14 does not reopen the equity family. The already-recorded strict OOS kill-switch remains the controlling evidence, so the plan should not spend more cycles on OHLCV-only TB14 promotion work unless a genuinely external validation path is added.

## TB15_T03 Fresh Forward Sample

Refresh mode:

```powershell
python -B ssell1.py --mode signal_fetch_tb15_udiff_fno_bhavcopy_forward_window
```

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t03_fresh_forward_sample
```

Artifacts:

- `results/signal_baseline/tb15_t03_fresh_forward_sample_summary.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_metadata.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_detail.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_decision.md`
- `results/signal_baseline/tb15_udiff_fno_bhavcopy_forward_fetch.csv`

Current result:

- status: `t03_passed_unlock_tb15_t04`
- source TB15 base trades: `522`
- source first trade date: `2016-05-09`
- source last expiry date: `2024-07-25`
- local F&O zip count: `2467`
- archive min/max date: `2015-01-01` / `2024-12-31`
- UDiFF forward fetch: `121` files fetched from `2024-07-08` through `2024-12-31`, with `6` HTTP 404 gaps
- held-out trade count: `33`
- held-out first trade date: `2024-08-22`
- held-out last expiry date: `2025-01-30`
- held-out mean return on cash: `0.4576%`
- held-out portfolio mean return on cash: `0.4339%`
- held-out win rate: `84.85%`
- held-out assignment rate: `15.15%`
- held-out worst expiry return on cash: `-0.5012%`
- gates mean / assignment / worst: `True` / `True` / `True`
- broker orders allowed: `False`

Inference: the old NSE F&O bhavcopy archive stopped before the original TB15 expiry horizon, but the UDiFF common bhavcopy archive provides a valid non-overlapping forward slice. T03 now passes its held-out gates and unlocks only the defined-risk T04 redesign path.

## Current Next Action

Proceed to TB15_T04 defined-risk bull put spread redesign as research-only/no-order work. Do not open naked cash-secured put paper trading from T03; the tail-risk reduction must be proven through the capped-risk spread version first.

## TB15_T04 Defined-Risk Bull Put Redesign

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t04_defined_risk_bull_put_redesign
```

Artifacts:

- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_detail.csv`
- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_summary.csv`
- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_kelly_sizing.csv`
- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_skipped.csv`
- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_metadata.csv`
- `results/signal_baseline/tb15_t04_defined_risk_bull_put_redesign_decision.md`

Current result:

- status: `t04_passed_candidate_for_phase1_observation`
- trades: `523`
- first trade date / last expiry date: `2016-05-09` / `2025-01-30`
- mean return on capped max loss: `5.4315%`
- mean return on cash-equivalent collateral: `0.1719%`
- worst portfolio expiry return on cash-equivalent collateral: `-3.0581%`
- positive Kelly symbols: `6`
- gates positive-Kelly / worst / mean: `True` / `True` / `True`
- broker orders allowed: `False`

Inference: T04 is the first TB15 branch that converts the CSP idea into capped-loss spreads and passes initial gates on the refreshed archive. It is a candidate for quote-only Phase 1 observation, not for broker execution.

## TB15_T05 Zerodha Quote-Only Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t05_zerodha_quote_only_readiness
```

Artifacts:

- `results/signal_baseline/tb15_t05_zerodha_quote_only_readiness_template_20260703.csv`
- `results/signal_baseline/tb15_t05_zerodha_quote_only_readiness_detail_20260703.csv`
- `results/signal_baseline/tb15_t05_zerodha_quote_only_readiness_summary.csv`
- `results/signal_baseline/tb15_t05_zerodha_quote_only_readiness_metadata.csv`
- `results/signal_baseline/tb15_t05_zerodha_quote_only_readiness_decision.md`

Current result:

- status: `quote_only_readiness_passed`
- candidate symbols: `SBIN`, `ICICIBANK`, `LT`, `TCS`, `BHARTIARTL`
- excluded by minimum sample gate: `RELIANCE` because T04 had only `3` trades despite positive raw Kelly
- resolved spreads: `5 / 5`
- quote-ready spreads: `5 / 5`
- clean quote-ready spreads: `4 / 5`
- mean executable credit: `6.47`
- minimum executable credit: `3.40`
- dirty spread: `LT`, due to wide/stale long-put quote with max leg spread percentage `1.2669`
- broker block violations: `0`
- broker orders allowed: `False`

Inference: the Zerodha quote-only path is live for TB15 and can resolve/current-quote stock-option bull put spread candidates without using order endpoints. Same-day repeat captures improved the clean-observation count, but the date-diversity gate still blocks promotion.

## TB15_T06 Quote-Only Observation Ledger

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t06_quote_only_observation_ledger
```

Artifacts:

- `results/signal_baseline/tb15_t06_quote_only_observation_ledger.csv`
- `results/signal_baseline/tb15_t06_quote_only_observation_ledger_latest_detail.csv`
- `results/signal_baseline/tb15_t06_quote_only_observation_ledger_summary.csv`
- `results/signal_baseline/tb15_t06_quote_only_observation_ledger_metadata.csv`
- `results/signal_baseline/tb15_t06_quote_only_observation_ledger_decision.md`

Current result:

- status: `collecting_quote_only_observations`
- latest capture rows: `5`
- latest clean quote spreads: `4`
- clean observations: `8 / 10`
- unique observation dates: `1 / 5`
- remaining: `2` clean observations and `4` unique dates
- broker block violations: `0`
- broker orders allowed: `False`

Inference: TB15 has entered a no-order Zerodha observation lane. The gate remains open/collecting until repeated market-hour captures reach at least `10` clean observations across `5` dates.

## TB11_T30 IV-Conditioned Sizing Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t30_iv_conditioned_sizing_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_detail.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_latest_snapshot.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_summary.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_metadata.csv`
- `results/signal_baseline/tb11_t30_iv_conditioned_sizing_readiness_decision.md`

Current result:

- status: `blocked_insufficient_iv_history`
- source chain-band detail files: `5`
- raw chain rows: `486`
- eligible OTM fresh rows: `100`
- modeled IV rows: `100`
- unique fresh capture dates: `2`
- first/latest fresh capture date: `2026-07-01` / `2026-07-03`
- history span: `2 / 60` days
- latest median modeled IV: `0.12964946775400768`
- latest median available-history IV rank: `1.0`
- provisional sizing tier: `no_entry_insufficient_history`
- broker orders allowed: `False`

Inference: the chain-band data is sufficient to compute modeled implied volatility from mid quotes, spot, strike, option type, and DTE, and fresh-history coverage has advanced to `2` dates. It is still not sufficient to use a 60-day IV percentile. T30 remains a research-only preview until enough fresh market-hour chain-band captures accumulate.

Next action: keep scheduled T28 chain-band collection alive and rerun T30 after the fresh capture history spans 60 days or at least 20 fresh capture dates. Do not use the provisional IV rank for sizing yet.

## TB18 Earnings-Avoidance Overlay Readiness

Fetch mode:

```powershell
python -B ssell1.py --mode signal_fetch_tb18_earnings_and_nifty_weights
```

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb18_earnings_overlay_readiness
```

Backtest mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb18_earnings_overlay_backtest
```

Artifacts:

- `data/earnings_calendar.csv`
- `data/earnings_calendar_nse_raw.csv`
- `data/nifty50_constituents.csv`
- `data/nifty50_index_weights.csv`
- `data/nifty50_index_weights_smart_investing_raw.csv`
- `results/signal_baseline/tb18_external_data_fetch.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_summary.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_detail.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_metadata.csv`
- `results/signal_baseline/tb18_earnings_overlay_readiness_decision.md`
- `results/signal_baseline/tb18_earnings_overlay_backtest_detail.csv`
- `results/signal_baseline/tb18_earnings_overlay_backtest_summary.csv`
- `results/signal_baseline/tb18_earnings_overlay_backtest_metadata.csv`
- `results/signal_baseline/tb18_earnings_overlay_backtest_decision.md`

Current result:

- status: `ready_for_tb18_overlay_backtest`
- earnings calendar path: `data/earnings_calendar.csv`
- earnings source: NSE event calendar plus NSE quarterly financial-results filings
- earnings status: `ready`
- earnings rows: `2324`
- event range: `2025-01-07` / `2026-08-13`
- TB15 symbol coverage: `8 / 8`
- NIFTY constituent source: official NSE/Nifty constituent CSV, `50` rows
- NIFTY weight source: Smart-Investing NIFTY weightage table mapped to official constituent symbols
- NIFTY weight rows: `49`, sum `100%`, all source weight rows mapped
- NIFTY weight status: `ready`
- TB11 overlay ready: `True`
- TB15 overlay ready: `True`
- broker orders allowed: `False`
- blockers: `none`
- backtest status: `no_earnings_overlay_promoted_sparse_or_no_improvement`
- TB15 `entry_to_expiry` vetoes: `4 / 523`, mean return delta `-0.0000199322`, worst return delta `0.0`, decision `do_not_promote_observe_more_or_backfill_earnings_history`
- TB15 `±1d` vetoes: `5 / 523`, mean return delta `-0.0000209959`, worst return delta `0.0`, decision `do_not_promote`
- TB11 selected allocation: `def_full_resg0_ovg50`
- TB11 event-weight veto variants: `10%`, `15%`, `20%`
- TB11 historical event overlap: `0` trades because selected TB11 detail spans `2019-02-25` / `2024-05-15` while fetched earnings events start `2025-01-07`

Inference: TB18 is no longer data-blocked, but the no-order backtest does not promote an earnings overlay. TB15 has too few overlapping earnings vetoes and the veto slightly lowers mean return; TB11 cannot be historically tested against the current NSE earnings file because the selected TB11 backtest window ends before the fetched earnings window begins.

Next action: do not apply TB18 earnings vetoes to live or paper sizing yet. Backfill older earnings history or collect repeated paper observations before reconsidering the overlay.

## TB16 Defined-Risk NIFTY Bull Put Spread

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb16_defined_risk_nifty_bull_put_spread
```

Artifacts:

- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_detail.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_summary.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_skipped.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_metadata.csv`
- `results/signal_baseline/tb16_defined_risk_nifty_bull_put_spread_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- trades: `308`
- first entry / last expiry: `2016-07-25` / `2024-07-11`
- annualized return on estimated margin: `14.91%`
- win rate: `74.68%`
- worst trade: `-325.18` points
- max drawdown: `-1078.95` points
- TB11 return correlation: `0.4700` over `161` overlapping expiries
- correlation source: `tb11_options_conditional_overlay_frontier_detail.csv`
- blocker: `annualized_rom_below_15pct`
- broker orders allowed: `False`

Inference: TB16 has acceptable diversification versus the TB11 balanced overlay, but it misses the 15% annualized return-on-margin gate by a narrow margin and carries materially larger point drawdown than the current TB11 defensive/balanced profiles. Do not promote this first bull-put spread variant.

Next action: keep TB16 as a documented reject unless we intentionally test a narrower follow-up variant with a higher credit floor, lower liquidity threshold sensitivity, or a stronger trend/volatility gate. The plan order can move to TB11_T31 staggered multi-expiry or TB19 OI positioning while TB15_T03, TB11_T30, and TB18 remain blocked by data readiness.

## TB11_T31 Staggered Multi-Expiry Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_t31_staggered_multi_expiry_readiness
```

Artifacts:

- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_detail.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_summary.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_skipped.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_metadata.csv`
- `results/signal_baseline/tb11_t31_staggered_multi_expiry_readiness_decision.md`

Current result:

- status: `research_rejected_or_blocked`
- source strategy: `TB11_T09_low_loss_h15_c1` / `TB11_T09_low_loss_h30_c3`
- source selected trades: `51`
- second-expiry usable trades: `3`
- coverage rate: `5.88%`
- best base stagger variant on covered rows: `stagger_25_75`
- best base annualized return on covered rows: `3.60%`
- best base max drawdown on covered rows: `0.0`
- dominant blocker: `second_expiry_leg_or_liquidity_missing` (`44` base rows and `44` harsh rows)
- broker orders allowed: `False`

Inference: T31 cannot be promoted from current local real-chain coverage. The few covered rows look benign, but only `3 / 51` selected entries have a tradable next-expiry construction under the current 60k total-contract threshold and local spot-settlement requirement. That is too little evidence for a staggered multi-expiry policy.

Next action: move to `TB19` OI positioning as the next plan item that can use current local `data/nse_fno_bhavcopy_oi.csv` and option-chain/bhavcopy artifacts. Keep T31 closed unless a later liquidity model or refreshed chain archive materially improves second-expiry coverage.

## TB19 OI Positioning Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb19_oi_positioning_readiness
```

Artifacts:

- `results/signal_baseline/tb19_oi_positioning_readiness_detail.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_summary.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_metadata.csv`
- `results/signal_baseline/tb19_oi_positioning_readiness_decision.md`

Current result:

- status: `no_oi_filter_promoted`
- local futures OI source: `data/nse_fno_bhavcopy_oi.csv`
- local option OI source: `tb11_nifty_option_chain_bhavcopy_archive_liquid_detail.csv`
- source selected TB11 trades: `51`
- base-case candidate: `pcr_high`
- base `pcr_high` trades: `32`
- base `pcr_high` annualized return on margin: `18.23%` versus all-trades `17.57%`
- base `pcr_high` max drawdown: `-0.66` versus all-trades `-1.25`
- harsh `pcr_high` annualized return on margin: `7.78%` versus all-trades `9.11%`
- harsh `pcr_high` max drawdown: `-19.94` versus all-trades `-18.77`
- durable filters passing base and harsh: `none`
- broker orders allowed: `False`

Inference: OI positioning has a useful base-case signal, but it does not survive the harsh-cost robustness requirement. The `pcr_high` filter trims trades and improves the base drawdown, yet it underperforms the all-trades harsh case and worsens harsh drawdown. Do not promote TB19.

Next action: proceed to the next attached-plan item, `TB17` covered-call overwrite, only as a readiness/backtest milestone if underlying holdings or synthetic holding assumptions are explicit. Otherwise keep the active no-order TB11/TB15 blockers as the operational priority.

## TB17 Covered-Call Overwrite Readiness

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb17_covered_call_overwrite_readiness
```

Artifacts:

- `results/signal_baseline/tb17_covered_call_overwrite_readiness_detail.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_summary.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_skipped.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_metadata.csv`
- `results/signal_baseline/tb17_covered_call_overwrite_readiness_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- symbols tested: `RELIANCE`, `HDFCBANK`, `ICICIBANK`, `INFY`, `TCS`
- raw F&O bhavcopy files: `2346`
- weekly-entry files scanned: `426`
- sanity-passing trades: `238`
- first trade / last expiry: `2016-05-09` / `2024-06-27`
- portfolio incremental yield annualized: `4.38%`
- portfolio covered-call annualized return: `8.95%`
- portfolio buy-hold annualized return over matched windows: `2.84%`
- assignment rate: `28.57%`
- upside give-up / premium: `67.77%`
- HDFCBANK and RELIANCE were excluded by the price-scale sanity filter after their adjusted spot closes did not line up with unadjusted option strikes/premiums
- broker orders allowed: `False`

Inference: TB17 is not a promotion candidate from current local data. The first raw pass showed impossible premiums caused by adjusted-equity versus unadjusted-option price-scale mismatch; after adding strike/spot and premium/spot sanity gates, the remaining sample still gives up too much upside relative to premium and fails both portfolio gates.

Next action: keep TB17 closed as a documented reject until a corporate-action-adjusted spot/options alignment exists and a real passive holding file is specified. `TB20` is now completed below with the required Zerodha gold/debt assets, while `TB15_T03`, `TB11_T30`, and `TB18` remain data-readiness blocked.

## TB20 Cross-Asset Defensive Tilt

Implemented mode:

```powershell
python -B ssell1.py --mode signal_fetch_tb20_defensive_assets_from_zerodha
python -B ssell1.py --mode signal_baseline_tb20_cross_asset_defensive_tilt
```

Artifacts:

- `results/signal_baseline/tb20_defensive_assets_zerodha_fetch.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_detail.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_summary.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_folds.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_metadata.csv`
- `results/signal_baseline/tb20_cross_asset_defensive_tilt_decision.md`

Current result:

- status: `research_rejected_by_initial_gates`
- Zerodha fetch: `GOLDBEES` rows `2471` from `2016-07-05` to `2026-07-02`; `LIQUIDBEES` rows `2473` from `2016-07-05` to `2026-07-03`
- universe: `NIFTYBEES`, `GOLDBEES`, `LIQUIDBEES`
- rule: baseline `90%` NIFTYBEES / `5%` GOLDBEES / `5%` LIQUIDBEES; shift to `50%` / `15%` / `15%` plus `20%` cash when trailing 60-session NIFTYBEES drawdown breaches `12%`
- events: `242`
- risk-off events: `10`
- NIFTYBEES interval benchmark annualized return: `12.23%`
- static 90/5/5 annualized return: `9.21%`
- defensive tilt annualized return: `8.53%`
- benchmark max drawdown: `-32.03%`
- static 90/5/5 max drawdown: `-29.04%`
- defensive tilt max drawdown: `-24.01%`
- drawdown improvement versus benchmark: `25.03%`
- annualized return give-up versus benchmark: `3.69%`
- folds beating benchmark: `1 / 10`
- broker orders allowed: `False`

Inference: TB20 now uses the attached plan's required gold/debt defensive assets from Zerodha instead of the earlier PHARMABEES proxy. The mechanical drawdown trigger does reduce max drawdown by the required `25%` threshold, but it gives up `3.69%` annualized return versus the `3%` cap and beats the benchmark in only `1 / 10` folds. Do not promote this defensive tilt.

Next action: the attached plan is now exhausted into either completed rejects or explicit data blockers. Return to operational/data-readiness work: keep T28/Phase 2 no-order collection healthy, refresh F&O/spot data for `TB15_T03`, accumulate IV history for `TB11_T30`, and populate earnings/index weights for `TB18`.

## TB11 Phase 2 No-Order Refresh - 2026-07-03 14:17 IST

Implemented modes:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_nifty_chain_band_quote_collector
python -B ssell1.py --mode signal_baseline_tb11_options_t28_freshness_gate
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_transition_controller
python -B ssell1.py --mode signal_baseline_tb11_options_phase2_no_order_paper_price_reconciliation
```

Artifacts:

- `results/signal_baseline/tb11_nifty_chain_band_quote_collector_summary.csv`
- `results/signal_baseline/tb11_t28_freshness_gate_summary.csv`
- `results/signal_baseline/tb11_phase2_paper_price_reconciliation_readiness_summary.csv`
- `results/signal_baseline/tb11_phase2_transition_controller_summary.csv`
- `results/signal_baseline/tb11_phase2_no_order_paper_price_reconciliation_summary.csv`
- `results/signal_baseline/tb11_phase2_no_order_paper_price_reconciliation_detail_20260703.csv`

Current result:

- T28 generated at: `2026-07-03T14:17:22.893136+05:30`
- spot: `24283.2`
- selected expiry: `2026-07-07`
- quote packets/fresh rows: `98 / 98`
- selected profile legs covered: `4 / 4`
- freshness gate: `phase2_paper_price_reconciliation_ready`
- readiness status: `phase2_paper_price_reconciliation_ready`
- reconciliation status: `phase2_no_order_reconciliation_passed`
- Phase 1 latest weighted credit: `7.125`
- Phase 1 modeled credit: `7.275`
- Phase 2 defensive credit: `4.85`
- Phase 2 weighted credit: `7.275`
- drift versus latest Phase 1: `+2.11%`
- drift versus latest modeled credit: `0.00%`
- within 10% / 15% adverse tolerance: `True` / `True`
- broker block violations: `0`
- broker orders allowed: `False`

Inference: the 14:17 IST Zerodha quote-only refresh keeps TB11 Phase 2 healthy. The selected four legs are fully covered, the weighted paper credit reconciles to the modeled Phase 1 credit, and no broker-order route was enabled.

Next action: continue no-order Phase 2 collection across more market-hour timestamps. Do not place broker orders.
