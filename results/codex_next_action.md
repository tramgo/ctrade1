# Codex Next Action

## Current Status

- Active batch: `TB09` proposed overlay fork
- Last completed thesis family: `TB07 delivery, OI, and breadth`
- Last verdict: `closed_research_only`
- Active thesis: `TB09_T01 DeliveryAwareIncumbentOverlay`
- Active stage: `tb07_closed_breadth_failed_earnings_template_only_next_is_delivery_overlay_or_stop`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## TB06 Final Verdict

TB06 is closed. Large-cap OHLCV, ETF OHLCV, mid/small-cap OHLCV, and drawdown guardrails all failed the same-universe buy-hold robustness gate.

| Strategy | Ann. | Buy-Hold | Folds Won | Verdict |
|---|---:|---:|---:|---|
| `T01 MomentumPlusBuyHoldEnsemble` | `10.16%` | `17.12%` | `4 / 10` | fail |
| `T02 MomentumWithDrawdownStop` | `0.16%` | `17.12%` | `0 / 10` | fail |
| `T03 LowVolPortfolioRank` | `9.57%` | `16.91%` | `3 / 10` | fail |
| `T05 IndexRelativeMomentum` | `8.53%` | `16.91%` | `3 / 10` | fail |
| `Z01 BuyHoldMomentumThrottle` | `14.01%` | `17.12%` | `4 / 10` | fail |
| `Z02 WinnerRetentionRotation` | `7.00%` | `17.12%` | `3 / 10` | fail |
| `Z03 LoserAvoidanceOverlay` | `8.95%` | `17.12%` | `0 / 10` | fail |
| `Z04 ETFMomentumRotation` | `7.02%` | `15.51%` | `1 / 10` | fail |
| `Z05 ETFLowVolRotation` | `12.18%` | `15.51%` | `2 / 10` | fail |
| `T10 MidSmallMomentumTopK` | `8.52%` | `33.17%` | `3 / 10` | fail |
| `T10 MidSmallLowVolTopK` | `12.52%` | `33.17%` | `1 / 10` | fail |
| Guardrail overlay | best `16.79%` | `17.12%` | max `4 / 10` | fail |

## Guardrails Tested

Guardrails were implemented as peak-drawdown exposure controls on existing event-return streams:

| Profile | Exposure Rule | Result |
|---|---|---|
| `rl_hard_5_75_10_cash` | `0.75x` after `5%`, `0.50x` after `7.5%`, cash after `10%` | reduced some active-sleeve tail loss; failed buy-hold |
| `soft_5_10_floor50` | `0.75x` after `5%`, `0.50x` after `10%` | gentler protection; failed buy-hold |
| `medium_8_12_floor25` | `0.60x` after `8%`, `0.25x` after `12%` | best for some weak factor variants; failed buy-hold |
| `late_10_15_floor50` | `0.75x` after `10%`, `0.50x` after `15%` | best universe-timed profile; still below buy-hold |

Conclusion: guardrails are reusable risk controls, not an alpha source.

## TB07 T01 Outcome

`TB07_T01 DeliveryPercentRegime` is now decision-grade and should be treated as closed.

10-fold result:

| Variant | Mean Ann. | Min Fold Ann. | Buy-Hold Ann. | Folds Beat Buy-Hold | Mean Eligibility |
|---|---:|---:|---:|---:|---:|
| `delivery_rising` | `4.42%` | `-4.84%` | `17.95%` | `4 / 10` | `13.83%` |
| `delivery_rising_above_floor` | `3.31%` | `-8.88%` | `17.95%` | `4 / 10` | `12.52%` |
| `delivery_rising_and_zpos` | `2.55%` | `-16.35%` | `17.95%` | `3 / 10` | `9.48%` |
| `ungated` | `4.38%` | `-50.74%` | `17.95%` | `3 / 10` | `100%` |

Interpretation:

- delivery filtering improves worst-fold behavior materially versus ungated
- but none of the delivery variants come close to beating same-universe buy-hold
- the best delivery variant is `delivery_rising`, but it is still far below the benchmark

Verdict: `TB07_T01` failed the buy-hold gate and is closed.

## TB07 T02 Outcome

`TB07_T02 FOOpenInterestPositioning` is now decision-grade and should be treated as closed.

10-fold result:

| Variant | Mean Ann. | Min Fold Ann. | Buy-Hold Ann. | Folds Beat Buy-Hold | Mean Eligibility |
|---|---:|---:|---:|---:|---:|
| `ungated` | `15.52%` | `-28.83%` | `19.02%` | `2 / 10` | `100%` |
| `oi_rising_and_pos` | `8.91%` | `-22.49%` | `19.02%` | `3 / 10` | `16.39%` |
| `oi_rising` | `3.31%` | `-24.88%` | `19.02%` | `2 / 10` | `28.01%` |

Verdict: `TB07_T02` failed the buy-hold gate and is closed.

## TB08 Outcome

`TB08 Pairs Relative Value Scan` has now completed its first retail-feasible formulation and is also closed.

Result:

- `2106` pair / parameter cells evaluated
- `0` positive annualized cells
- best cell still `-52.57%` annualized

Verdict: current distance/z-score pairs formulation is decisively non-viable on this cache.

## TB07 T04 Outcome

`TB07_T04 BreadthConfirmationGate` has now been run after fetching broad daily OHLCV from Zerodha.

10-fold result:

| Variant | Mean Ann. | Min Fold Ann. | Buy-Hold Ann. | Folds Beat Buy-Hold | Mean Gate Pass |
|---|---:|---:|---:|---:|---:|
| `ungated` | `5.20%` | `-48.13%` | `16.96%` | `3 / 10` | `100%` |
| `breadth_strong` | `2.67%` | `-16.86%` | `16.96%` | `1 / 10` | `33.6%` |
| `breadth_trend_up` | `1.61%` | `-22.84%` | `16.96%` | `1 / 10` | `50.4%` |
| `breadth_expanding` | `-1.04%` | `-10.17%` | `16.96%` | `1 / 10` | `32.8%` |

Interpretation:

- breadth gating reduced some catastrophic fold damage relative to ungated
- but every breadth variant still failed same-universe buy-hold decisively
- breadth therefore joins delivery and OI as a useful risk-thinner, not an alpha rescue

Verdict: `TB07_T04` is closed.

## Earnings Status

`TB07_T03 EarningsEventRisk` is now wired but only as `template_only`.

- `data/earnings_calendar.csv` exists with the expected schema
- the file contains `0` rows
- Zerodha does not provide the earnings-calendar feed needed to populate it

Verdict: earnings remains unavailable on the current Zerodha-only path.

## Next Command

No further broad retail-data strategy mode is justified to run immediately from the current code path.

Recommended next thesis to wire and run:

- `TB09_T01 DeliveryAwareIncumbentOverlay`
  - keep `SIGNAL_E211_BANDED_68` as the base engine
  - use prior-day delivery features only for entry veto / size-down / hold-extension decisions
  - compare strictly against incumbent, not against buy-hold as if it were a new standalone engine

Proposal artifact:

```powershell
Get-Content results\thesis_batch_09.md
```

## Batch 07 Rule

Do not open another broad OHLCV selector, long-only ranker, or market-wide gate thesis.

What is now closed:

- `TB07_T01 delivery`
- `TB07_T02 OI`
- `TB07_T04 breadth`
- `TB08 pairs`

What remains honest under current data limits:

- a narrow delivery-aware overlay on the incumbent
- otherwise stop autonomous systematic research on this stack

## Wiring Status

Both remaining Batch 07 modes are now wired and CLI-registered:

- `signal_baseline_tb07_breadth_confirmation_gate`
- `signal_baseline_tb07_earnings_event_risk`

Each will fail cleanly with an empty artifact set until its required data file exists.
