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

Implemented mode:

```powershell
python -B ssell1.py --mode signal_baseline_tb15_t03_fresh_forward_sample
```

Artifacts:

- `results/signal_baseline/tb15_t03_fresh_forward_sample_summary.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_metadata.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_detail.csv`
- `results/signal_baseline/tb15_t03_fresh_forward_sample_decision.md`

Current result:

- status: `blocked_no_non_overlapping_forward_slice`
- source TB15 base trades: `522`
- source first trade date: `2016-05-09`
- source last expiry date: `2024-07-25`
- local F&O zip count: `2346`
- archive min/max date: `2015-01-01` / `2024-07-05`
- held-out trade count: `0`
- broker orders allowed: `False`

Inference: a genuine fresh forward sample is not locally available. The F&O archive ends before the already-used TB15 base sample expiry horizon. Reusing the original 522 trades would violate the T03 non-overlap requirement.

## Current Next Action

Do not proceed to TB15_T04 defined-risk bull put spread redesign from this blocked T03 result. Refresh local F&O bhavcopy and daily spot data beyond the TB15 base sample, then rerun T03. If refreshing the forward slice is not possible, move to TB11_T30 IV-conditioned sizing as the next cheapest high-value research item that uses already collected chain-band data.
