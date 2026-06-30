# Roadmap Status - Equity, Kelly Sizing, CSP, Pairs

Generated: `2026-06-30`

## 2. E1006 Swing Equity Paper Track

Status: `not_promoted`

Current evidence says not to promote standalone `E1006` to paper trading yet.

- `TB12_OHLCVRegimeConditionedPortfolioRank` tested promotion-grade 10-fold E1006 variants.
- Best E1006 gate was `nifty_trend_up`.
- Mean strategy annualized: `10.98%`
- Mean buy-hold annualized: `17.12%`
- Folds beating buy-hold: `3 / 10`
- Verdict: `research_only`

The older "4/6 recent folds" read is not enough to override the newer 10-fold evidence. E1006 can stay in the research queue, but not as a paper-trade sleeve unless the objective changes from standalone buy-hold outperformance to a narrower overlay or core/active construction.

## 3. Kelly / Worst-Trade-Budget Sizing For Equity

Status: `partially_actioned`

The options lot-capital idea has not been ported to standalone E1006 because standalone E1006 is not promotable. However, the sizing pattern was applied to the new cash-secured-put scan:

- artifact: `results/signal_baseline/tb15_cash_secured_put_large_caps_kelly_sizing.csv`
- method: raw Kelly from mean/variance of cash return, half-Kelly, then capped by worst-trade budget
- cap: `5%` worst-trade cash budget
- max half-Kelly fraction: `25%`

Next equity-specific sizing action, if equity resumes:

- use `TB13_CoreActiveTiltPortfolioRank` instead of standalone E1006
- apply Kelly only to the active sleeve, not the whole core book
- cap active sleeve by worst fold, worst rebalance, and turnover-cost stress

## 5. Cash-Secured Put Writing On Large Caps

Status: `implemented_research_only_candidate`

New implementation:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_cash_secured_put_large_caps
```

Artifacts:

- `results/signal_baseline/tb15_cash_secured_put_large_caps_detail.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_summary.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_kelly_sizing.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_metadata.csv`
- `results/signal_baseline/tb15_cash_secured_put_large_caps_decision.md`

Setup:

- symbols: `RELIANCE`, `HDFCBANK`, `ICICIBANK`, `INFY`, `TCS`, `SBIN`, `LT`, `BHARTIARTL`
- local source: NSE F&O bhavcopy zip archive plus existing daily equity CSVs
- put selection: cash-secured `OPTSTK` PE, target about `5%` OTM, `7-35` DTE
- broker orders allowed: `False`

Read:

- detail trades: `522`
- portfolio equal-weight mean return on cash per expiry bucket: `0.54%`
- portfolio win rate: `80.61%`
- assignment rate: `15.71%`
- worst equal-weight expiry-bucket return: `-21.41%`
- positive Kelly-sized names: `6`

Best individual annualized cash-return reads:

- `ICICIBANK`: `8.50%`, win rate `92.86%`, worst return `-34.46%`
- `SBIN`: `8.25%`, win rate `85.71%`, worst return `-35.92%`
- `TCS`: `5.38%`, win rate `86.30%`, worst return `-9.84%`
- `BHARTIARTL`: `4.98%`, win rate `88.78%`, worst return `-13.74%`

Sizing read:

- `BHARTIARTL`, `INFY`, and `TCS` hit the configured `25%` max fraction cap.
- `LT` sizes to `17.02%`.
- `ICICIBANK` sizes to `14.51%`.
- `SBIN` sizes to `13.92%`.
- `RELIANCE` is blocked by insufficient sample: only `1` trade.

Verdict:

Cash-secured put writing is now a valid research-only candidate, but not ready for paper trading. The raw return level is far below the pasted 18-25% expectation, and March 2020-style assignment losses dominate the risk budget. The next useful refinement is a volatility/breadth/market-stress skip gate before paper tracking.

## 6. Pair Trading / Market Neutral

Status: `do_not_reopen_broad_scan`

Existing TB08 result is a hard fail.

- best pair/cell: `ICICIBANK|LT`, `z_window=120`, `entry_z=2.0`
- mean event return: `-0.496%`
- approximate annualized return: about `-52.57%`
- positive cells: `0 / 2106`
- verdict: `research_only`

TB07 breadth data exists, but breadth as a standalone confirmation gate also failed:

- best breadth variant: `breadth_strong`
- mean strategy annualized: `2.67%`
- buy-hold annualized: `16.96%`
- folds beating buy-hold: `1 / 10`

Next pair-trading action, if reopened:

- do not rerun the same z-score relative-value scan
- require a materially different design: sector-matched pairs, cointegration/stability prefilter, borrow/cost model, and breadth as a regime veto only
- otherwise keep pair trading closed as `research_only`

## Immediate Next Thesis

Keep active execution focus on `TB11_Phase1_Target15CleanObservationGate`.

For the smoothing-roadmap side branch, the next research thesis is:

`TB15_T02_CSPVolBreadthStressGate`

Required checks:

- skip CSP entries during market stress or weak breadth
- test whether worst CSP assignment losses shrink without destroying trade frequency
- keep Kelly/worst-trade-budget sizing
- remain research-only; no broker orders

## TB15_T02 CSP Vol/Breadth Stress Gate Result

Mode:

- `signal_baseline_tb15_csp_vol_breadth_stress_gate`

Artifacts:

- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_detail.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_summary.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_kelly_sizing.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_metadata.csv`
- `results/signal_baseline/tb15_csp_vol_breadth_stress_gate_decision.md`

Result:

- NIFTY context coverage: `97.7%`
- India VIX context coverage: `97.1%`
- best non-baseline variant: `skip_composite_stress`
- kept trades: `391 / 522`
- skipped trades: `131`
- portfolio mean return on cash per expiry bucket: `0.32%`, down from ungated `0.54%`
- worst equal-weight expiry-bucket return: unchanged at `-21.41%`
- tail-loss events <= `-5%`: `21`, down from ungated `26`

Gated Kelly / worst-trade-budget sizing:

- capped research fraction `25.00%`: `BHARTIARTL`, `INFY`, `TCS`
- capped research fraction `14.51%`: `ICICIBANK`
- capped research fraction `13.92%`: `SBIN`
- blocked at `0.00%`: `LT`, due nonpositive gated edge

Verdict:

`TB15_T02` is a research-only stress-gate candidate, not a paper-track approval. It reduces the count of medium tail losses but does not improve the worst portfolio expiry and reduces mean return. The next CSP action should be forward-sample confirmation or a materially different tail-risk design, not immediate paper sizing.
