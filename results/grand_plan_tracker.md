# Grand Plan Tracker

> Superseded as the primary strategy document by [grand_plan.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan.md). Keep this file as a tracking/reference artifact.

Date: 2026-03-17

## Current Phase

- Active phase: `Signal Discovery / Signal Validation`
- Current posture: `Consolidation pause on branch promotion`
- Incumbent benchmark: `SIGNAL_E211_BANDED_68`
- Active challenger branch: `none`
- RL status: frozen for new branch until baseline proof exists

## Macro Progress

| Area | Status | CompletionPct | Notes |
|---|---|---:|---|
| Architecture and evaluation backbone | Strong | 90 | Walk-forward, baselines, real-vs-shuffled, control-path histories are in place. |
| RL-first exploration | Complete lesson | 100 | We have already learned not to use PPO as the alpha source. |
| Signal research framework | Mature | 80 | Multiple research waves and shortlist paths already exist. |
| Systematic ablation program | Partial | 50 | We still need a formal family-by-target grid. |
| Current live branch implementation | In progress | 70 | `cross_sectional_60m` has been implemented, but not run yet. |
| Production-ready strategy | Early | 25 | No broad, durable post-cost edge proven yet. |

## Detailed Tracker

| Plan Area | Status | CompletionPct | Notes |
|---|---|---:|---|
| 1. Strategic reset: signal lab vs RL lab | Done | 100 | New work is baseline-first. |
| 2. Freeze one stable benchmark baseline | Done | 95 | `E211` is the incumbent benchmark. |
| 3. Replace weak targets with stronger research targets | Mostly done | 75 | `T1-T4` exist; regime-conditional behavior uses filters rather than a distinct `T5` target. |
| 4. Build feature-family matrix | Done | 90 | `F1-F8` now cover trend, volatility, relative, setup, and cross-sectional families. |
| 5. Run formal ablation grid by family/target | Partial | 45 | Several waves were run, but not yet as one formal grid. |
| 6. Use monetizable success metrics | Done | 90 | Spread, trade count, IC, real-vs-shuffled, and post-cost framing are active. |
| 7. Build setup libraries S1-S5 | Partial | 60 | Several setup-style branches were explored, but not in one explicit scoreboard yet. |
| 8. Change research question to stable post-cost edge | Done | 100 | This is now the active research question. |
| 9. 3-stage pipeline: discovery -> validation -> RL | Done | 85 | Operationally present, though promotion reporting can still be tightened. |
| 10. Hard kill rule for weak branches | Mostly done | 80 | Used strategically; not yet unified in one artifact across all branches. |
| 11. Use RL later only as execution overlay | Done | 90 | New branch explicitly keeps RL out of scope. |
| 12. Exact next 10 experiments program | In progress | 35 | We have pieces of it, not the full formal program. |
| 13. Top immediate priorities | In progress | 65 | Targets, post-cost validation, and a new branch exist; formal ablation remains. |
| 14. Strategic outcome branching | In progress | 70 | We have retired branch rescue and moved to benchmark-first logic. |
| 15. Credential cleanup | Partial | 70 | Env-var path exists; full secret audit still pending. |

## Immediate Next Gate

1. Freeze current branch map
2. Use `branch_decision_scoreboard.csv` and `setup_library_scoreboard.csv` as current source of truth
3. Do not promote new branches into RL
4. Choose one new, non-redundant information thesis before reopening discovery

## Pending Workstreams

### A. Formal ablation grid by family / target

- Goal: run a compact matrix across targets and feature families instead of only curated branches.
- Proposed shape:
  - Targets: `T1`, `T2`, `T3`, `T4`
  - Families / combos:
    - `F1`
    - `F3`
    - `F4`
    - `F5`
    - `F1+F3`
    - `F3+F4`
    - `F3+F4+F5`
    - `F3+F7`
    - `F3+F7+F8`
- Output needed:
  - one ablation summary table
  - one best-per-target table
  - one best-per-family table

### B. Setup-library scoreboard

- Goal: standardize setup families into one scoreboard instead of treating each discovery wave independently.
- Proposed setup families:
  - `S1` Trend continuation
  - `S2` Pullback to trend
  - `S3` Mean reversion
  - `S4` Relative-strength carry
  - `S5` Failed breakout reversal
- Output needed:
  - setup-to-experiment mapping
  - best experiment per setup
  - best baseline per setup
  - breadth / turnover / concentration summary

### C. Cross-sectional 60m branch verdict

- Goal: determine whether the newly implemented cross-sectional branch beats the incumbent benchmark.
- Required files:
  - `results/signal_research/outputs_cross_sectional_60m/latest/cross_sectional_60m_shortlist_summary.csv`
  - `results/signal_research/outputs_cross_sectional_60m/latest/cross_sectional_60m_promoted_ids.txt`
  - `results/signal_baseline/cross_sectional_60m_policy_summary.csv`
  - `results/signal_baseline/cross_sectional_60m_branch_scoreboard.csv`

### D. Branch-decision scoreboard across active families

- Goal: one table showing incumbent vs challengers, with a single decision label per branch.
- Branches to include:
  - `E211` incumbent benchmark
  - `ablation_grid`
  - `E302` broader generalization branch
  - `generalization_next`
  - `generalization_wave2`
  - `cross_sectional_60m`
- Output needed:
  - one scoreboard with:
    - best research candidate
    - best baseline policy
    - breadth
    - turnover
    - decision label
