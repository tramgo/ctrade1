# TB11 Phase 2 No-Order Paper-Price Reconciliation

Status: `phase2_no_order_reconciliation_passed`

- Phase 1 latest weighted credit: `2.1750000000000003`
- Phase 2 T28 weighted credit: `2.1`
- Phase 2 vs Phase 1 drift: `-0.03448275862068973`
- Phase 1 to T28 timestamp gap seconds: `116.771544`
- same-window gate passed: `True`
- all legs reconciliation ok: `True`
- within 10% / 15% adverse tolerance: `True` / `True`
- broker block violations: `0`
- counted Phase 2 observations: `1` / `15`
- passed counted observations: `1`
- unique observation dates: `1` / `10`
- calendar evidence days: `1` / `90`
- Phase 2 evidence status: `phase2_evidence_collection_in_progress`
- Phase 2 evidence blockers: `phase2_target_15_same_window_observations_not_reached|phase2_min_10_unique_dates_not_reached|phase2_min_90_calendar_days_not_reached`
- Phase 3 human-review eligible: `False`
- broker orders allowed: `False`

Next action: continue no-order Phase 2 paper-price observations; do not place broker orders.
