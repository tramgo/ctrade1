# Thesis Batch 02 Closeout

Date: 2026-04-25

Status: `TB02_T01`, `TB02_T02`, and `TB02_T03` completed and closed `research_only`; `TB02_T04` is next.

## Open Items

- `TB02_T04 RegimeSpecificIncumbentVeto`: next action is incumbent-only entry audit via `signal_baseline_e211_entry_audit`
- `TB02_T10 NewExternalDataAxis`: blocked until a real new local data source exists

## `TB02_T03` EventOutcomeAccounting

- pre-run redesign:
  - superseded the narrower `OpeningAuctionGapLiquidity` framing before any research run was launched
  - kept the active slot as `TB02_T03` but changed the thesis template
- thesis logic:
  - isolate event windows first
  - define success as `target before stop` in the live trade direction
  - separately track path cleanliness instead of assuming fixed-horizon return is enough
- implementation:
  - research mode: `signal_research_event_outcome_accounting`
  - baseline mode: `signal_baseline_event_outcome_accounting`
  - experiment family: `E2801-E2805`
  - includes `E2805` as an `E211`-logic control expressed on event-outcome labels for the same run
- broad research result:
  - `E2801-E2804` produced no promoted IDs
  - `E2801` and `E2804` showed only weak structure
  - all top-decile economics remained negative or too small to justify baseline
- refined research result:
  - `E2806` was added as a quality-filtered `E2801` refinement
  - `E2806` produced no valid experiment rows because the filter was too restrictive
  - `E2805` was the only valid refined-run row group
- `E2805` control read:
  - AUC: `0.5585800644447346`
  - balanced accuracy: `0.5438344743187962`
  - top-decile net return: `-0.001912395609680604`
  - top-minus-bottom spread: `-0.00015781370424895353`
  - real-vs-shuffled spread gap: `-0.00015285913114700461`
- verdict:
  - `research_only`

Reason: event-outcome accounting improved the realism of the label, but the candidate events still did not have positive absolute economics. The `E211` control could classify target-before-stop outcomes, yet its highest-ranked bucket still had negative trade payoff. This is evidence against more standalone OHLCV-derived predictive exploration as the next primary path.

## `TB02_T04` RegimeSpecificIncumbentVeto

- status:
  - next active thesis
- immediate action:
  - run `signal_baseline_e211_entry_audit`
- thesis logic:
  - start from actual `SIGNAL_E211_BANDED_68` entries
  - audit losing regimes and path risk
  - build a veto, delay, or sizing overlay only if the failure modes are clearly separable
- reason:
  - `E211` remains the only durable executable benchmark
  - Batch 01 and early Batch 02 suggest improving the incumbent may be higher value than replacing it with another standalone classifier

## `TB02_T01` CrossSectionalCommonalityResidual

- research:
  - promoted only `E2501`
  - best research score: `0.009293325587313273`
- executable:
  - best policy: `SIGNAL_E2501_BANDED_66`
  - return: `1.0075225258618678e-05`
  - turnover: `0.0555555555432098`
  - trades: `0.2222222222222222`
  - breadth: `1` positive, `25` zero, `1` negative
- incumbent compare:
  - benchmark `SIGNAL_E211_BANDED_68 = 0.0001012555869542`
  - excess vs benchmark: `-9.117036169558132e-05`
- verdict:
  - `research_only`

Reason: the slice was research-alive but the executable edge was too small and too sparse to challenge the incumbent.

## `TB02_T02` IntradayVolumeLiquidityForecast

- research:
  - promoted only `E2601`
  - best research score: `0.11047634140232482`
- executable:
  - best policy: `SIGNAL_E2601_BANDED_70`
  - return: `-0.0007258334009476`
  - turnover: `0.96355973841595`
  - trades: `2.2222222222222223`
  - breadth: `5` positive, `12` zero, `10` negative
- incumbent compare:
  - benchmark `SIGNAL_E211_BANDED_68 = 0.0001012555869542`
  - excess vs benchmark: `-0.0008270889879018`
- verdict:
  - `research_only`

Reason: liquidity-conditioned research separation was real, but once traded the edge collapsed under turnover and still stayed clearly below the incumbent.

## Current Benchmark

- incumbent: `SIGNAL_E211_BANDED_68`
- RL status: frozen
