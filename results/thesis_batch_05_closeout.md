# Thesis Batch 05 Closeout

Date: 2026-04-30

## Thesis

`PortfolioRank60m E1006` long-only swing rescue through:

- 10-year multi-fold benchmark validation
- post-2020 full-context benchmark validation

## Decision

`Fail`

Action taken:

- shelve `E1006` as a deployment candidate
- retain only diagnostic value from the fold histories

## Core Results

| Window | Variant | Mean Ann. | Buy-Hold Mean Ann. | Folds Beating Buy-Hold | Min Fold Ann. | Verdict |
|---|---|---:|---:|---:|---:|---|
| 10-year, 10 folds | score-weighted ungated | 7.95% | 16.96% | 3 / 10 | -45.21% | fail |
| 10-year, 10 folds | score-weighted dispersion-sized | 8.16% | 16.96% | 4 / 10 | -50.26% | fail |
| post-2020, 6 folds | score-weighted ungated | 20.55% | 20.07% | 3 / 6 | -6.36% | fail |
| post-2020, 6 folds | score-weighted dispersion-sized | 19.00% | 20.07% | 3 / 6 | -15.41% | fail |

## Why It Failed

| Check | Outcome | Notes |
|---|---|---|
| Real signal exists | yes, weak | 10-year `Gap IC` remained positive but small |
| Beats buy-hold on average | mixed | ungated post-2020 barely edged buy-hold on mean only |
| Beats buy-hold robustly across folds | no | both post-2020 variants won only `3 / 6` folds |
| Worst-fold behavior acceptable | no | negative strategy folds remained material |
| Dispersion sizing rescues robustness | no | it helped some folds and hurt others |

## Inference Matrix

| Hypothesis | Result |
|---|---|
| The earlier 3-year winner was a durable long-window edge | rejected |
| Missing pre-2020 `ITBEES` history was the main confound | rejected |
| Post-2020 full-context era would rescue the branch | rejected |
| Dispersion sizing would convert the branch into a robust deployment candidate | rejected |
| The branch still contains useful design information for future theses | accepted |

## What We Learned

1. `E1006` is a real but regime-sensitive signal, not a durable market-beating deployment strategy.
2. Mean return alone was misleading; fold win-rate versus buy-hold was the right gate.
3. Dispersion sizing is not a universal rescue lever.
4. Future theses should reuse the fold-level failure analysis, not the branch itself.

## Follow-Up

One small diagnostic remains worth doing on existing CSVs:

- fold-attribution decomposition of:
  - name selection
  - sizing
  - gate
  - timing

That is research support for the next thesis, not a reopening of `E1006`.

## Next Item

Move forward to:

- `TB03_T06 BenchmarkSuiteRefresh`
