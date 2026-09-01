# TB11 Phase 2 Transition Controller

- Status: `blocked_phase1_transition_gate_not_met`
- Transition passed: `False`
- Phase 1 collection date: `2026-08-24`
- readiness collection date: `2026-09-01`
- clean observations: `113` / `15`
- unique observation dates: `36` / `5`
- Phase 1 evidence gate passed: `True`
- readiness Phase 2 gate passed: `False`
- selected leg coverage: `0` / `4`
- modeled credit available: `True`
- broker-block violations: `0`
- blockers: `t28_freshness_gate_not_passed|t28_selected_leg_full_coverage_not_passed|readiness_collection_date_mismatch`
- runbook written: `False`
- automation state advanced: `False`

Next action: Do not advance automation state. Continue scheduled no-order Phase 1/T28 collection until clean observations >= 15, unique dates >= 5, Phase 1 evidence gate is true, and broker blocks remain 0.
