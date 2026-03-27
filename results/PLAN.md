# Long-Horizon Signal Research Program for a Tradable Intraday Engine

> Superseded as the primary strategy document by [grand_plan.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan.md). Keep this file as historical/reference context.

## Update 2026-03-27

This document remains broadly valid, but the current operating interpretation is now sharper than when this was first written.

### What is now explicit

- `SIGNAL_E211_BANDED_68` remains the incumbent benchmark
- RL is still frozen unless a branch first survives executable validation
- native `15m` is the active frontier
- native `15m` continuation / score-port families are now lower priority
- event selection and regime/session selection are now higher priority

### Most important added rule

Strong classification alone is not enough.

A branch must not only rank better-vs-worse cases. It must do so inside a slice that is itself economically tradable after costs.

That is the main lesson added by:

- `Native15mExecution`
- `Native15mFailedBreakout`
- `Native15mOpenDrive`
- the current `Native15mSessionPhase` research result

### Immediate operating queue

1. Run `signal_baseline_native_15m_session_phase`
2. If it fails, move to:
   - `Native15mHoldingHorizon`
   - `Native15mTopKEventRank`
3. Do not reopen:
   - native `15m` direct `E102` / `E211` ports
   - nearby `60m` rescue sweeps
   - PPO / reward tuning as signal discovery

### Read this document as superseded where it conflicts

If any older section below conflicts with:

- [current_layer_decision_memo.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/current_layer_decision_memo.md)
- [thesis_batch_01.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01.md)
- [thesis_batch_01_closeout.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/thesis_batch_01_closeout.md)

then the newer files take precedence.

## Summary
The original objective is to build a sound intraday trading engine, with or without RL, that is actually tradable after costs and can clear a meaningful bar: more than `12%` annualized return. The work so far has shown that the research stack is capable of finding real predictive structure, but not yet a durable executable edge stronger than the incumbent benchmark.

Current benchmark:
- `SIGNAL_E211_BANDED_68` remains the best durable executable baseline.
- It exactly replicated on rerun.
- It is benchmark-grade, not convincingly deployable.

What we have achieved:
- Proven the pipeline can discover real signal structure.
- Proven the pipeline can reject weak ideas consistently.
- Proven cost modeling is not the main bottleneck.
- Proven many challenger branches improved research metrics but failed monetization.
- Proven one direct native `15m` thesis can look alive, then fail broader validation.

What we have missed relative to the objective:
- No branch has yet produced a robust post-cost engine clearly meeting the practical target.
- No challenger has displaced `E211` on durable executable quality.
- RL has not been justified as a value-adding next layer because the signal bottleneck remains upstream.

## What We Have Tried So Far
### Core `60m` and adjacent layers
- `E211 / E209 / E102 deep-dive`
  - best result: `SIGNAL_E211_BANDED_68`
  - exact rerun replication
  - best current executable benchmark
- `CrossSectional60m`
  - real research structure
  - failed baseline
- `MarketState60m`
  - `E801` closest challenger
  - still below `E211`
- `Multiscale60m`
  - strong research quality
  - failed baseline monetization
- `SetupRegime`
  - useful research branch
  - failed baseline
- `AblationGrid`
  - strong map of what matters
  - weak executable baseline
- `PortfolioRank60m`
  - valid non-redundant test
  - broad underperformance, high turnover

### Intrahour and true second-timeframe work
- `SecondTimeframe60m`
  - true `15m -> 60m` context
  - improved research quality
  - failed executable baseline
- `IntrahourPathV1`
  - path / rejection / smooth-vs-noisy inside the hour
  - strong research metrics
  - failed baseline
- `TimeDistributionV2`
  - early-vs-late move timing
  - `E1401` looked slightly better than `E211` in research
  - failed baseline
- `E211 + intrahour veto`
  - no-op on actual benchmark behavior

### Native `15m`
- `Native15mExecution`
  - first narrow test produced a sparse positive blip
  - broader validation turned negative
  - conclusion: one tested `15m` thesis is not robust enough
- `All15m` broad research sweep
  - succeeded
  - produced many surviving research candidates
  - conclusion: `15m` research is alive, but `15m` executable validation is still unresolved

### Meta-conclusions from completed work
- Research improvement does not guarantee executable monetization.
- Costs matter, but they are not the main explanation for failures.
- `E211` remains the strongest durable signal/execution pairing found so far.
- The pipeline is mature enough for a long-horizon thesis program rather than ad hoc experimentation.

## Operating Objective Going Forward
Primary objective:
- find a post-cost intraday strategy engine that is tradable and can exceed `12%` annualized return

Secondary objective:
- build an evidence-driven research program that can explore at least `50` high-value signal-generation theses without drifting into tuning churn

Program rule:
- RL is out of scope until a baseline-first signal branch clearly earns promotion
- every thesis must pass research, then executable baseline, then broader validation
- any thesis that fails broader validation is archived as `research_only`

## Research Program Structure
### Thesis budget and batching
- Work in batches of `10` ranked theses at a time.
- Total exploration target: `50` high-value theses.
- Each thesis gets one of three outcomes:
  - `advance`
  - `research_only`
  - `kill`
- Never run more than one major thesis family to full baseline at once.
- Within a batch of `10`, only the top `2-3` research survivors get baseline budget.

### Stage gates for every thesis
1. `Research feasibility`
- Dataset builds cleanly.
- Experiment run completes.
- No leakage or obvious schema issues.
- At least one candidate shows positive real-vs-shuffled separation.

2. `Baseline viability`
- Simple executable rule beats `FLAT`.
- Result is not obviously one-row or one-name concentrated.
- Turnover is not absurd relative to payoff.

3. `Broader validation`
- More windows or broader coverage.
- If previously positive, must remain non-negative and broad enough.
- If it collapses under broader validation, mark `research_only` or `kill`.

4. `Promotion gate`
- Only if a branch is durable and materially stronger than the incumbent benchmark.
- Only then consider RL or more advanced execution.

## Ranked Next 10 High-Value Theses
This is the next batch to explore after the current checkpoint, ranked by expected value.

1. `15m open-drive / opening-range event thesis`
- Native `15m`
- event-driven, not continuous
- likely better aligned with intraday structure than generic continuation

2. `15m failed-breakout reversal thesis`
- native event system
- direct test of intrabar rejection as tradable event, not as feature blend

3. `15m session-phase thesis`
- separate morning, midday, late-session behavior explicitly
- not just one model with time features

4. `15m relative-strength ranking thesis`
- cross-sectional ranking on native `15m`
- top-k selection rather than per-name thresholding

5. `15m holding-horizon sweep thesis`
- same `15m` signal family but explicit hold-horizon families
- e.g. `1 bar`, `2 bars`, `4 bars`, `8 bars`

6. `15m mean-reversion event thesis`
- only after sharp exhaustion / rejection states
- not generic reversal everywhere

7. `15m breakout continuation event thesis`
- only on clean path-quality + participation states
- event-triggered, not continuous score

8. `60m + daily context thesis`
- true higher-timeframe context
- different from intrahour work

9. `breadth-led native 15m thesis`
- reuse breadth idea directly on `15m`
- likely better than forcing breadth through `60m`

10. `newsless regime segmentation thesis`
- explicit market regime engine from observable market internals, breadth, volatility state, sector confirmation
- only if kept small and event-oriented

Default next batch order:
- start with `1-5`
- keep `6-10` as reserve if the first five mostly fail early

## Standard Workflow for Each Batch of 10
### Phase 1: Thesis definition
- Create `results/thesis_batch_XX.md`
- List the 10 theses with:
  - rank
  - hypothesis
  - data interval
  - target type
  - baseline policy style
  - success gate

### Phase 2: Research execution
- Implement research modes only for all 10 theses in the batch.
- Keep each thesis compact: `3-6` experiments per thesis.
- Run and monitor them.
- Terminate early only for:
  - syntax/runtime failure
  - dataset corruption
  - leakage suspicion
  - obviously dead experiment family after partial run evidence

### Phase 3: Research review
- Update:
  - `results/experiment_branch_registry.csv`
  - `results/branch_decision_scoreboard.csv`
  - `results/experiment_performance_master.csv`
- Produce a ranked shortlist for the batch.
- Promote only the top `2-3` research survivors to baseline.

### Phase 4: Baseline execution
- Run narrow baseline modes only for shortlisted survivors.
- Compare to:
  - `FLAT`
  - incumbent benchmark for that layer
- If native `15m`, compare first to `FLAT`, then to current best validated benchmark for the same cadence.

### Phase 5: Broader validation
- For any baseline positive branch:
  - rerun with more windows
  - inspect ticker breadth
  - inspect concentration
  - inspect turnover/trades
- If it collapses, archive it.

### Phase 6: Milestone closeout
- Update memo and scoreboard.
- Commit and push.
- Move to next batch only after the current batch is decision-complete.

## Monitoring and Run Management
### Monitoring cadence
- Check active long runs every `20-30` minutes.
- For heavy research sweeps, also check:
  - first dataset build completion
  - first experiment completion
  - midpoint file growth / log progress
  - final shortlist artifacts

### Reasons to terminate a run early
- syntax/runtime error
- memory blow-up
- obviously wrong mode routing
- leakage suspicion
- repeated data/token failures
- branch producing malformed outputs or empty predictions

### Do not terminate early just because
- early research metrics look mediocre
- one sub-experiment is weak
- a branch is not yet beating benchmark before full completion

### Periodic checkpoints during runs
- confirm mode is correct in `main.log`
- confirm expected output directory exists
- confirm predictions file size is growing for research runs
- confirm baseline summary files are being written for baseline runs
- record anomalies in the current memo or batch note

## Metrics, Logs, and Milestone Artifacts
Update or maintain these at milestone points:
- `results/current_layer_decision_memo.md`
- `results/branch_decision_scoreboard.csv`
- `results/experiment_branch_registry.csv`
- `results/experiment_performance_master.csv`

Add per-batch artifacts:
- `results/thesis_batch_XX.md`
- `results/thesis_batch_XX_ranked.csv`
- `results/thesis_batch_XX_closeout.md`

Use run-specific outputs already produced under:
- `results/signal_research/...`
- `results/signal_baseline/...`

Milestone update points:
- after research batch completes
- after baseline shortlist completes
- after broader validation completes
- after closing a batch of 10

## Commit and Push Policy
Commit and push at these milestones only:
1. after a new batch’s research modes are implemented
2. after a batch’s research results are reviewed and tracked
3. after shortlisted baselines are implemented
4. after broader validation is complete
5. after batch closeout

Commit message pattern:
- `Add thesis batch XX research modes`
- `Record thesis batch XX research verdicts`
- `Add thesis batch XX baseline modes`
- `Record thesis batch XX validation verdicts`
- `Close thesis batch XX`

Never batch unrelated local changes into these milestone commits.

## Acceptance Criteria for the Overall Program
A thesis can be considered a real success only if it:
- survives research screening
- beats `FLAT` in executable baseline
- survives broader validation
- shows acceptable breadth and concentration
- has realistic post-cost behavior
- contributes toward a path to `>12%` annualized return

A batch is complete only if:
- all 10 theses are explicitly marked
  - `advance`
  - `research_only`
  - or `kill`
- trackers and memo are updated
- milestone commit is created and pushed

The 50-thesis program is complete only if:
- 5 batches of 10 are closed
- all branch results are tracked
- either a promotable engine is found or the research space is credibly exhausted

## Assumptions and Defaults
- `E211` remains the incumbent benchmark until clearly displaced.
- RL remains frozen unless a baseline-first branch earns promotion.
- Native `15m` is now a valid research layer, but not yet validated as a profitable engine.
- Broad `15m` research should continue, but baseline budget stays narrow.
- The current environment will provide full local access, and Codex will be allowed to monitor long-running experiments periodically.
- The program favors disciplined iteration over exhaustive simultaneous implementation.
