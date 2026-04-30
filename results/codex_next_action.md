# Codex Next Action

## Current Status

- Active batch: `TB03`
- Last completed thesis: `PortfolioRank60m post-2020 full-context benchmark`
- Last verdict: `research_only_shelved`
- Active thesis: `TB03_T06 BenchmarkSuiteRefresh`
- Active stage: `baseline_ready`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

## Fresh Adjudication

- The pre-defined post-2020 rescue gate failed.
- `E1006` post-2020 results:
  - `score_weighted_top3_ungated`
    - mean annualized = `20.55%`
    - buy-hold mean annualized = `20.07%`
    - folds beating buy-hold = `3 / 6`
    - min fold annualized = `-6.36%`
  - `score_weighted_top3_dispersion_sized`
    - mean annualized = `19.00%`
    - buy-hold mean annualized = `20.07%`
    - folds beating buy-hold = `3 / 6`
    - min fold annualized = `-15.41%`
- Interpretation:
  - post-2020 full-context data removed the cleanest remaining data-quality objection
  - the strategy still did not clear the robustness bar
  - the branch should be treated as shelved, not promoted

## Closeout

- `PortfolioRank60m E1006` is closed as:
  - `research_only_shelved`
- Keep one small diagnostic follow-up only:
  - fold-attribution decomposition on the existing 10-fold and post-2020 histories
  - purpose: learn whether failures came mostly from selection, sizing, gate, or timing

## Next Thesis

Proceed to the next planned item in the queue:

- `TB03_T06 BenchmarkSuiteRefresh`

This is the right next move because:

- `TB03_T05` is closed
- `PortfolioRank60m` rescue is closed
- the project now needs a cleaner benchmark/reporting layer before opening another rescue cycle

## Next Command

No new long run is wired for `TB03_T06` yet in this note.

Immediate non-run artifact follow-up:

```powershell
Get-Content results\thesis_batch_05_closeout.md
```
