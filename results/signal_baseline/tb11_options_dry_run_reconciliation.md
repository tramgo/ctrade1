# TB11 Dry-Run Reconciliation

Status: `schema_ready_no_order_logger`

This artifact is a Phase 1 dry-run logger replay from historical selected-profile chain detail.
It does not call a broker, place orders, or authorize paper/live trading.

## Readout

- profile: `def_full_resg0_ovg50`
- source mode: `historical_replay_no_order`
- lot size: `65`
- signals logged: `51`
- simulated signals after maturity gate: `50`
- skipped signals: `1`
- broker orders allowed: `False`
- schema gate passed: `True`

## Next Use

Use the same schema for real-time Phase 1 dry-run observations, then reconcile observed quote snapshots against modeled premium and itemized costs before Phase 2.
