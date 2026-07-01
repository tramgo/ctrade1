# Composite Plan Gate Audit

Generated at IST: `2026-07-01T14:42:28.769045+05:30`

- overall status: `branch_a_phase2_runbook_opened_pending_commit`
- Branch A: `phase2_runbook_opened_pending_commit`
- Branch B: `research_only_deferred`
- Branch C: `lockouts_enforced`
- next best action: Commit the Phase 2 runbook and transition artifacts before any reconciliation execution.

## Branch A - TB11 Phase 1 To Phase 2

- clean observations: `15` / `15`
- unique observation dates: `5` / `5`
- Phase 1 evidence gate: `True`
- readiness Phase 2 gate: `True`
- modeled credit available: `True`
- selected-leg coverage: `True`
- broker-block violations: `0`
- no-order static audit passed: `True`
- forbidden order calls/imports/wrapper refs: `0` / `0` / `0`
- scheduler readiness audit passed: `True`
- scheduler tasks present/enabled/command/time/last-result-zero: `4` / `4` / `4` / `4` / `4`
- runbook template contract audit passed: `True`
- runbook template contracts present: `28` / `28`
- runbook exists before transition: `False`
- blockers: `none`

## Branch B - TB15

- base mean return on cash: `0.0053956817785046`
- base worst expiry return: `-0.214128009698503`
- stress best variant: `skip_composite_stress`
- stress worst expiry return: `-0.214128009698503`
- positive sized symbols: `5`
- blockers: `tb15_worst_expiry_worse_than_minus_8pct|tb15_stress_worst_expiry_worse_than_minus_8pct`

## Branch C - Lockouts

- E1006 lockout documented: `True`
- TB08 lockout documented: `True`
- TB06 lockout documented: `True`
- blockers: `none`
