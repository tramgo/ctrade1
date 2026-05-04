# Codex Next Action

## Current Status

- Active batch: `TB06`
- Last completed thesis: `TB06_T02 MomentumWithDrawdownStop`
- Last verdict: `research_only`
- Active thesis: `TB06 Zerodha ETF rotation`
- Active stage: `wired_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## Newly Wired

Mode:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_swing_batch
```

This mode evaluates immediately executable theses and emits explicit `data_required` rows for theses that need external files.

## Executable Now

| ID | Thesis | Test |
|---|---|---|
| `TB06_T03` | `LowVolPortfolioRank` | buy the 3 lowest realized-vol names every 10 sessions |
| `TB06_T05` | `IndexRelativeMomentum` | buy top-3 stocks by 60-session return minus Nifty 60-session return |

## Data Required

| ID | Thesis | Required Input |
|---|---|---|
| `TB06_T04` | `EarningsCalendarOverlay` | `data/earnings_calendar.csv` |
| `TB06_T06` | `SectorRotationLongOnly` | `data/sector_indices_60m_or_daily.csv` |
| `TB06_T07` | `FAndODeliveryFiltered` | `data/nse_delivery_bhavcopy.csv` |
| `TB06_T08` | `OIChangeAugmentedScore` | `data/nse_fno_bhavcopy_oi.csv` |
| `TB06_T09` | `BreadthGate` | `data/nifty500_daily_ohlcv.csv` |
| `TB06_T10` | `SmallCapMomentum` | `data/nse_midcap_smallcap_60m.csv` |

## Output Artifacts

- `results/signal_baseline/tb06_swing_batch_summary.csv`
- `results/signal_baseline/tb06_swing_batch_events.csv`
- `results/signal_baseline/tb06_swing_batch_aggregate.csv`

## Decision Gate

For an executable thesis to stay alive:

- mean annualized return must beat buy-hold
- fold win-rate must beat `5 / 10`
- worst-fold annualized return must not materially underperform buy-hold

## Zerodha-Only Next Step

Because we are staying inside Zerodha limits, the next wired run avoids earnings, delivery, OI, breadth, and smallcap constituent dependencies.

Mode:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_zerodha_only_extensions
```

It tests:

| ID | Thesis | Zerodha-only logic |
|---|---|---|
| `TB06_Z01` | `BuyHoldMomentumThrottle` | starts from buy-hold and adds active E1006 weight only when dispersion is supportive |
| `TB06_Z02` | `WinnerRetentionRotation` | keeps current winners unless they fall below rank 7, reducing forced churn |
| `TB06_Z03` | `LoserAvoidanceOverlay` | holds the broad universe but excludes the bottom 3 ranked names |

Expected artifacts:

- `results/signal_baseline/tb06_zerodha_only_extensions_summary.csv`
- `results/signal_baseline/tb06_zerodha_only_extensions_events.csv`
- `results/signal_baseline/tb06_zerodha_only_extensions_aggregate.csv`

If these fail:

- pause Batch 06 until one of the external-data files is available
- do not open another pure OHLCV momentum branch

## Fresh Zerodha-Only Result

| ID | Strategy | Mean Ann. | Buy-Hold Ann. | Folds Beat Buy-Hold | Worst Fold | Verdict |
|---|---|---:|---:|---:|---:|---|
| `TB06_Z01` | `BuyHoldMomentumThrottle` | `14.01%` | `17.12%` | `4 / 10` | `-26.33%` | fail |
| `TB06_Z02` | `WinnerRetentionRotation` | `7.00%` | `17.12%` | `3 / 10` | `-43.37%` | fail |
| `TB06_Z03` | `LoserAvoidanceOverlay` | `8.95%` | `17.12%` | `0 / 10` | `-20.71%` | fail |

## Guardrail Overlay

Next command:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_guardrail_overlay
```

What it tests:

- applies peak-drawdown exposure reduction to existing TB06 event-return artifacts
- sweeps four profiles:
  - `rl_hard_5_75_10_cash`: `0.75x` after `5%`, `0.50x` after `7.5%`, cash after `10%`
  - `soft_5_10_floor50`: `0.75x` after `5%`, `0.50x` after `10%`
  - `medium_8_12_floor25`: `0.60x` after `8%`, `0.25x` after `12%`
  - `late_10_15_floor50`: `0.75x` after `10%`, `0.50x` after `15%`

Decision rule:

- guardrails can support deployment only if the guarded strategy still has positive edge after de-risking
- guardrails should not be used to promote a strategy that fails buy-hold before risk control

## Fresh Guardrail Result

The drawdown guardrail sweep did not promote any strategy. It improved some tail losses, but every guarded profile still failed the buy-hold robustness gate.

| Strategy | Best Guardrail Profile | Buy-Hold Ann. | Base Ann. | Guarded Ann. | Worst Guarded Fold | Folds Beat Buy-Hold | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| `TB06_T03_LowVolPortfolioRank` | `medium_8_12_floor25` | `17.12%` | `9.49%` | `9.30%` | `-9.77%` | `2 / 10` | fail |
| `TB06_T05_IndexRelativeMomentum` | `medium_8_12_floor25` | `17.12%` | `8.42%` | `8.74%` | `-10.74%` | `3 / 10` | fail |
| `TB06_Z01_ActiveSleeveOnly` | `rl_hard_5_75_10_cash` | `17.12%` | `5.06%` | `11.14%` | `-10.04%` | `4 / 10` | fail |
| `TB06_Z01_BuyHoldMomentumThrottle` | `late_10_15_floor50` | `17.12%` | `13.74%` | `13.82%` | `-20.58%` | `4 / 10` | fail |
| `TB06_Z01_UniverseTimedOnly` | `late_10_15_floor50` | `17.12%` | `16.99%` | `16.79%` | `-12.73%` | `4 / 10` | fail |

Conclusion: guardrails are useful for capital protection, but they are not alpha. The large-cap Zerodha-only OHLCV line remains closed unless a structurally different universe or instrument is tested.

## Next Wired Zerodha-Only Test

The next action uses only already cached Zerodha ETF OHLCV files and tests a structurally different sleeve: ETF/sector rotation instead of individual-stock large-cap ranking.

```powershell
python -u -B ssell1.py --mode signal_baseline_tb06_zerodha_etf_rotation
```

It evaluates:

| ID | Thesis | Logic |
|---|---|---|
| `TB06_Z04` | `ETFMomentumRotation` | rank `NIFTYBEES`, `BANKBEES`, `ITBEES`, `PHARMABEES` by trailing 60-session return, hold top 2 every 10 sessions |
| `TB06_Z05` | `ETFLowVolRotation` | hold the 2 lowest-realized-vol ETFs every 10 sessions |

Expected artifacts:

- `results/signal_baseline/tb06_zerodha_etf_rotation_summary.csv`
- `results/signal_baseline/tb06_zerodha_etf_rotation_events.csv`
- `results/signal_baseline/tb06_zerodha_etf_rotation_aggregate.csv`

## Fresh ETF Rotation Result

The ETF rotation proxy is also closed as a deployable candidate. The low-vol ETF sleeve is better than ETF momentum, but neither beats passive ETF buy-hold robustly.

| ID | Strategy | Mean Ann. | Buy-Hold Ann. | Worst Fold | Folds Beat Buy-Hold | Verdict |
|---|---|---:|---:|---:|---:|---|
| `TB06_Z04` | `ETFMomentumRotation` | `7.02%` | `15.51%` | `-32.21%` | `1 / 10` | fail |
| `TB06_Z05` | `ETFLowVolRotation` | `12.18%` | `15.51%` | `-32.21%` | `2 / 10` | fail |

Implementation note: the first ETF run exposed a missing `ATR20_log` cost-input issue. The fix now gives ETF rows a high/low-derived ATR proxy and makes `estimate_roundtrip_cost()` safely fall back to the regulatory floor when `ATR20_log` is absent.

## Next Practical Path

The large-cap stock OHLCV line and ETF rotation line are both closed. The only Zerodha-only path still worth testing is a less-efficient universe:

1. Define a 30-50 name midcap/smallcap universe with a liquidity floor.
2. Fetch 60m Zerodha candles into `data/data_fetched_<TICKER>_60m_3650d.csv`.
3. Run a cached-universe momentum/low-vol baseline against buy-hold.

Do not reopen another large-cap or ETF guardrail rescue cycle unless the benchmark or universe changes materially.
