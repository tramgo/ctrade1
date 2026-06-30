# TB11 Phase 2 Transition Controller

- Status: `blocked_phase1_transition_gate_not_met`
- Transition passed: `False`
- clean observations: `14` / `15`
- unique observation dates: `4` / `5`
- Phase 1 evidence gate passed: `True`
- readiness Phase 2 gate passed: `False`
- selected leg coverage: `4` / `4`
- modeled credit available: `True`
- broker-block violations: `0`
- blockers: `phase1_target_15_clean_observations_not_yet_reached|phase1_unique_observation_dates_below_5|t28_freshness_gate_not_passed`
- runbook written: `False`
- automation state advanced: `False`

Next action: Do not advance automation state. Continue scheduled no-order Phase 1/T28 collection until clean observations >= 15, unique dates >= 5, Phase 1 evidence gate is true, and broker blocks remain 0.
