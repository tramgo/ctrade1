# TB11 Scheduled Jobs Inference - 2026-07-02

Generated at IST: `2026-07-02 21:48`

## Scheduler Evidence

- `schtasks /Query /FO LIST /V` shows the four TB11 tasks present, ready, and returning last result `0`.
- `\TB11_Phase1_QuoteObservation_0940`
  - last run time: `2026-07-02 20:38:13`
  - next run time: `2026-07-03 09:40:00`
  - task route: `run_tb11_phase1_auto_quote_observation.bat`
- `\TB11_Phase1_QuoteObservation_1230`
  - last run time: `2026-07-02 20:38:13`
  - next run time: `2026-07-03 12:30:00`
  - task route: `run_tb11_phase1_auto_quote_observation.bat`
- `\TB11_Phase1_QuoteObservation_1445`
  - last run time: `2026-07-02 20:38:13`
  - next run time: `2026-07-03 14:45:00`
  - task route: `run_tb11_phase1_auto_quote_observation.bat`
- `\TB11_T28_ChainBandFreshness_0945`
  - last run time: `2026-07-02 20:38:13`
  - next run time: `2026-07-03 09:45:00`
  - task route: `run_tb11_t28_chain_band_freshness_gate.bat`

## Latest Log Evidence

- `results/log_runs/signal_baseline_tb11_options_phase1_auto_quote_observation_20260702_203939_scheduled.log`
  - T25, T24, T26, Phase 2 readiness, and transition controller all exited `0`.
  - The wrapper renewed the Kite token after one failed login attempt and captured quote-only artifacts for `2026-07-02`.
- `results/log_runs/tb11_t28_chain_band_freshness_gate_20260702_203939_scheduled.log`
  - T28 collector, T28 freshness gate, Phase 2 readiness, and transition controller all exited `0`.
  - The wrapper renewed the Kite token and captured chain-band artifacts for `2026-07-02`.

## Latest Artifact Read

- Phase 1 ledger summary:
  - collection date: `2026-07-02`
  - ledger rows: `18`
  - clean observations: `16 / 15`
  - unique observation dates: `6 / 5`
  - broker-block violations: `0`
  - Phase 1 evidence gate: `True`
- T28 freshness gate:
  - collector status: `chain_band_quotes_captured_stale`
  - quote packets received: `96`
  - fresh quote rows: `0`
  - median quote age seconds: `12002.884757`
  - max quote age seconds: `12002.884757`
  - Phase 2 gate passed: `False`
  - gate status: `blocked_needs_fresh_intraday_t28`
- Phase 2 readiness:
  - Phase 2 gate passed: `False`
  - T28 selected leg hits: `2 / 4`
  - full selected-leg coverage: `False`
  - modeled credit available: `True`
  - broker orders allowed: `False`
  - blockers: `t28_freshness_gate_not_passed|t28_chain_band_missing_selected_long_wing_coverage`
- Transition controller:
  - transition passed: `False`
  - runbook written: `False`
  - automation state advanced: `False`
  - blockers: `t28_freshness_gate_not_passed|t28_selected_leg_full_coverage_not_passed`

## Inference

The scheduled jobs are operationally alive: they run, log, renew tokens, write artifacts, and return exit code `0`. However, the latest run occurred at `20:38` to `20:42 IST`, outside the live market window. The captured T28 quotes were stale, with `0` fresh rows and quote ages around `12002` seconds, so the latest artifacts are not valid Phase 2 paper-price reconciliation evidence.

The prior committed Phase 2 runbook opening from `2026-07-01` remains the durable state in `automation_state.json`, but the latest after-hours summaries should be interpreted as a stale-data guard firing, not as a regression of the already committed runbook handoff.

## Next Action

Wait for the next live-market scheduled run on `2026-07-03`, then require fresh T28 rows, selected-leg coverage `4 / 4`, and Phase 2 readiness pass before starting no-order paper-price reconciliation. No broker order endpoint is allowed.
