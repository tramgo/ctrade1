# TB11 Phase 2 No-Order Paper-Price Reconciliation

Status: `phase2_no_order_reconciliation_passed`

- Phase 1 latest weighted credit: `6.825000000000001`
- Phase 2 T28 weighted credit: `6.375`
- Phase 2 vs Phase 1 drift: `-0.06593406593406607`
- Phase 1 to T28 timestamp gap seconds: `293.25828`
- same-window gate passed: `True`
- all legs reconciliation ok: `True`
- within 10% / 15% adverse tolerance: `True` / `True`
- broker block violations: `0`
- counted Phase 2 observations: `4` / `15`
- passed counted observations: `4`
- unique observation dates: `4` / `10`
- calendar evidence days: `4` / `90`
- Phase 2 evidence status: `phase2_evidence_collection_in_progress`
- Phase 2 evidence blockers: `phase2_target_15_same_window_observations_not_reached|phase2_min_10_unique_dates_not_reached|phase2_min_90_calendar_days_not_reached`
- Phase 3 human-review eligible: `False`
- broker orders allowed: `False`

Next action: continue no-order Phase 2 paper-price observations; do not place broker orders.
