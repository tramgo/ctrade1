# Composite Plan Gate Audit

Generated at IST: `2026-07-02T21:48:30.688637+05:30`

- overall status: `branch_a_waiting_for_market_evidence`
- Branch A: `blocked_wait_for_phase1_t28_gates`
- Branch B: `research_only_deferred`
- Branch C: `lockouts_enforced`
- next best action: Keep scheduled no-order Phase 1/T28 wrappers running; rerun this audit after the next market-hours observation.

## Branch A - TB11 Phase 1 To Phase 2

- clean observations: `16` / `15`
- unique observation dates: `6` / `5`
- Phase 1 evidence gate: `True`
- readiness Phase 2 gate: `False`
- modeled credit available: `True`
- selected-leg coverage: `False`
- broker-block violations: `0`
- no-order static audit passed: `True`
- forbidden order calls/imports/wrapper refs: `0` / `0` / `0`
- scheduler readiness audit passed: `True`
- scheduler tasks present/enabled/command/time/last-result-zero: `4` / `4` / `4` / `4` / `4`
- runbook template contract audit passed: `True`
- runbook template contracts present: `28` / `28`
- runbook exists before transition: `False`
- blockers: `t28_or_readiness_gate_not_passed|selected_leg_coverage_not_4_of_4`

## Branch B - TB15

- base mean return on cash: `0.0053956817785046`
- base worst expiry return: `-0.214128009698503`
- stress best variant: `skip_composite_stress`
- stress worst expiry return: `-0.214128009698503`
- positive sized symbols: `5`
- blockers: `branch_a_phase2_runbook_not_committed|tb15_worst_expiry_worse_than_minus_8pct|tb15_stress_worst_expiry_worse_than_minus_8pct`

## Branch C - Lockouts

- E1006 lockout documented: `True`
- TB08 lockout documented: `True`
- TB06 lockout documented: `True`
- blockers: `none`
