# Thesis Batch 06 - Swing Research

Date: 2026-04-30

## Operating Rule

Every thesis must explicitly differ from a plain momentum classifier on OHLCV.

Pure "another classifier on different features" theses are closed for this batch.

## Thesis Queue

| ID | Thesis | Core Difference From Momentum Classifier | Data Needed | Wiring Status |
|---|---|---|---|---|
| `TB06_T01` | `MomentumPlusBuyHoldEnsemble` | Composes passive buy-hold and `E1006` by regime weight instead of replacing passive exposure with a selector | none | completed, failed |
| `TB06_T02` | `MomentumWithDrawdownStop` | Adds portfolio-level risk state and cash switch after rolling drawdown breach | none | completed, failed |
| `TB06_T03` | `LowVolPortfolioRank` | Replaces momentum score with inverse realized volatility rank | none | completed, failed |
| `TB06_T04` | `EarningsCalendarOverlay` | Drops selected names around earnings instead of changing the alpha score | NSE/BSE earnings calendar | data-required artifact wired |
| `TB06_T05` | `IndexRelativeMomentum` | Scores stock 60-session return minus Nifty 60-session return | NIFTYBEES history, already cached if available | completed, failed |
| `TB06_T06` | `SectorRotationLongOnly` | Rotates sector sleeves instead of individual stocks | 11 NSE sector index or ETF histories | data-required artifact wired |
| `TB06_T07` | `FAndODeliveryFiltered` | Filters the universe by trailing delivery percent before selection | NSE delivery bhavcopy | data-required artifact wired |
| `TB06_T08` | `OIChangeAugmentedScore` | Adds positioning data through F&O open-interest change | NSE F&O bhavcopy | data-required artifact wired |
| `TB06_T09` | `BreadthGate` | Uses Nifty 500 breadth as a strategy on/off switch | Nifty 500 constituent OHLCV | data-required artifact wired |
| `TB06_T10` | `SmallCapMomentum` | Tests the same idea on a less-efficient mid/smallcap universe | Midcap-150 or Smallcap-250 OHLCV | data-required artifact wired |
| `TB06_Z04` | `ETFMomentumRotation` | Rotates cached ETF sleeves instead of individual stocks | Zerodha ETF OHLCV cache | wired |
| `TB06_Z05` | `ETFLowVolRotation` | Uses ETF volatility as a non-momentum sleeve selector | Zerodha ETF OHLCV cache | wired |

## Completed Results

| Thesis | Mean Buy-Hold Ann. | Strategy Ann. | Folds Beat Buy-Hold | Worst Fold | Verdict |
|---|---:|---:|---:|---:|---|
| `TB06_T01 MomentumPlusBuyHoldEnsemble` | `17.12%` | `10.16%` | `4 / 10` | `-37.05%` | fail |
| `TB06_T02 MomentumWithDrawdownStop` | `17.12%` | `0.16%` | `0 / 10` | `-26.07%` | fail |
| `TB06_T03 LowVolPortfolioRank` | `16.91%` | `9.57%` | `3 / 10` | `-13.01%` | fail |
| `TB06_T05 IndexRelativeMomentum` | `16.91%` | `8.53%` | `3 / 10` | `-14.39%` | fail |

## Current Command

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_swing_batch
```

## Zerodha-Only Extension

Given the current data constraint, the next useful run stays inside existing Zerodha OHLCV plus existing `E1006` predictions:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_zerodha_only_extensions
```

| ID | Thesis | Logic |
|---|---|---|
| `TB06_Z01` | `BuyHoldMomentumThrottle` | starts from buy-hold and adds active E1006 weight only when dispersion is supportive |
| `TB06_Z02` | `WinnerRetentionRotation` | keeps current winners unless they fall below rank 7 |
| `TB06_Z03` | `LoserAvoidanceOverlay` | holds broad universe but excludes bottom 3 ranked names |

## Fresh Zerodha-Only Result

| ID | Strategy | Mean Ann. | Buy-Hold Ann. | Folds Beat Buy-Hold | Worst Fold | Verdict |
|---|---|---:|---:|---:|---:|---|
| `TB06_Z01` | `BuyHoldMomentumThrottle` | `14.01%` | `17.12%` | `4 / 10` | `-26.33%` | fail |
| `TB06_Z02` | `WinnerRetentionRotation` | `7.00%` | `17.12%` | `3 / 10` | `-43.37%` | fail |
| `TB06_Z03` | `LoserAvoidanceOverlay` | `8.95%` | `17.12%` | `0 / 10` | `-20.71%` | fail |

## Guardrail Overlay

The next diagnostic tests whether RL-style capital protection improves already-computed event return streams.

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_guardrail_overlay
```

This is a risk overlay, not a new alpha thesis. The wired version sweeps:

| Profile | Exposure Rule |
|---|---|
| `rl_hard_5_75_10_cash` | `0.75x` after `5%`, `0.50x` after `7.5%`, cash after `10%` |
| `soft_5_10_floor50` | `0.75x` after `5%`, `0.50x` after `10%` |
| `medium_8_12_floor25` | `0.60x` after `8%`, `0.25x` after `12%` |
| `late_10_15_floor50` | `0.75x` after `10%`, `0.50x` after `15%` |

## Guardrail Result

The guardrail overlay is closed as a rescue attempt. It reduced risk in some variants, but no strategy cleared buy-hold after de-risking.

| Strategy | Best Profile | Buy-Hold Ann. | Base Ann. | Guarded Ann. | Worst Guarded Fold | Folds Beat Buy-Hold | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| `TB06_T03_LowVolPortfolioRank` | `medium_8_12_floor25` | `17.12%` | `9.49%` | `9.30%` | `-9.77%` | `2 / 10` | fail |
| `TB06_T05_IndexRelativeMomentum` | `medium_8_12_floor25` | `17.12%` | `8.42%` | `8.74%` | `-10.74%` | `3 / 10` | fail |
| `TB06_Z01_ActiveSleeveOnly` | `rl_hard_5_75_10_cash` | `17.12%` | `5.06%` | `11.14%` | `-10.04%` | `4 / 10` | fail |
| `TB06_Z01_BuyHoldMomentumThrottle` | `late_10_15_floor50` | `17.12%` | `13.74%` | `13.82%` | `-20.58%` | `4 / 10` | fail |
| `TB06_Z01_UniverseTimedOnly` | `late_10_15_floor50` | `17.12%` | `16.99%` | `16.79%` | `-12.73%` | `4 / 10` | fail |

Interpretation: drawdown controls are guardrails, not an alpha engine. They can reduce damage, but they cannot make a weak large-cap OHLCV edge robust against passive buy-hold.

## Next Command

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_zerodha_etf_rotation
```

This tests the cached Zerodha ETF universe:

| ID | Thesis | Logic |
|---|---|---|
| `TB06_Z04` | `ETFMomentumRotation` | rank `NIFTYBEES`, `BANKBEES`, `ITBEES`, `PHARMABEES` by trailing 60-session return, hold top 2 every 10 sessions |
| `TB06_Z05` | `ETFLowVolRotation` | hold the 2 lowest-realized-vol ETFs every 10 sessions |

## Expected Artifacts

- `results/signal_baseline/tb06_swing_batch_summary.csv`
- `results/signal_baseline/tb06_swing_batch_events.csv`
- `results/signal_baseline/tb06_swing_batch_aggregate.csv`

## Gate

For an executable thesis to stay alive:

- mean annualized return must beat buy-hold
- fold win-rate must beat `5 / 10`
- worst-fold annualized return must not materially underperform buy-hold

For data-required theses:

- do not mark pass/fail until the required external file exists
- keep the output as `data_required`
