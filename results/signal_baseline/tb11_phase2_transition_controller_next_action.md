# TB11 Phase 2 Transition Controller

- Status: `blocked_phase1_transition_gate_not_met`
- Transition passed: `False`
- Phase 1 collection date: `2026-07-06`
- readiness collection date: `nan`
- clean observations: `3` / `15`
- unique observation dates: `1` / `5`
- Phase 1 evidence gate passed: `False`
- readiness Phase 2 gate passed: `False`
- selected leg coverage: `0` / `4`
- modeled credit available: `True`
- broker-block violations: `0`
- blockers: `phase1_target_15_clean_observations_not_yet_reached|phase1_unique_observation_dates_below_5|phase1_evidence_gate_not_passed|t28_freshness_gate_not_passed|t28_selected_leg_full_coverage_not_passed|readiness_collection_date_mismatch`
- runbook written: `False`
- automation state advanced: `False`

Next action: Do not advance automation state. Continue scheduled no-order Phase 1/T28 collection until clean observations >= 15, unique dates >= 5, Phase 1 evidence gate is true, and broker blocks remain 0.
