# TB11 Phase 1 Observation Collection Runbook

Status: `manual_no_order_collection_ready`

- collection date IST: `2026-06-24`
- batch id: `TB11_PHASE1_OBS_20260624`
- collection batch: `tb11_options_dry_run_observation_collection_20260624.csv`
- rows prepared: `50`
- broker orders allowed: `False`

## Daily Procedure

1. Use the collection batch CSV for the current dry-run session.
2. Record only observed quote data: timestamp, quote source, quote age, and bid/ask for every required leg.
3. Keep `broker_order_allowed` as `False` for every row.
4. Do not place broker orders from Phase 1.
5. After entering observations, run:

```powershell
python -B ssell1.py --mode signal_baseline_tb11_options_observed_quote_reconciliation_validator
```

## Acceptance Rules

- Quote age must be `300` seconds or newer.
- Every required leg must have usable bid/ask quotes.
- Observed weighted credit must stay inside the 10-15% adverse tolerance band.
- Any stale quote, missing leg, spread-quality failure, or surprise cost becomes a skip reason.
- Collect observations for `1-2 months`; do not advance to Phase 2 from a single-day batch.
