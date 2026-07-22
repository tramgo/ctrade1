# TB11 Phase 2 Paper-Price Reconciliation Runbook

Generated at IST: `2026-07-22T14:46:24.223433+05:30`

## Gate Evidence

- Phase 1 clean observations: `48` / `15`
- unique observation dates: `13`
- Phase 1 evidence gate passed: `True`
- broker-block violations: `0`
- T28 selected-leg coverage: `4` / `4`
- modeled credit available for live row: `True`

## Source Of Truth

- Paper prices use broker quote snapshots captured by quote-only collectors.
- No Phase 2 artifact may use broker order endpoints or inferred fills as execution evidence.
- The current selected-leg resolver defines the leg symbols; T28 chain-band artifacts verify current bid/ask availability.

## Reconciliation Tolerances

- Compare observed weighted credit against live mid-quote modeled credit recorded by the Phase 1 row.
- Maintain the existing 10% and 15% adverse tolerance flags.
- Treat any row outside 15% adverse tolerance as review-required, not as a paper pass.

## Divergence Escalation

- Escalate if modeled credit is missing, selected-leg coverage is below 4/4, quote freshness fails, or broker-block violations are non-zero.
- Escalate if observed-vs-modeled credit drift repeatedly fails the 15% adverse tolerance.
- Escalation means no paper promotion and a root-cause memo before further advancement.

## Hold Times Per Leg

- Short call and short put: track through the selected paper horizon with daily quote reconciliation.
- Long call and long put: track as hard-risk wings; do not omit them even when outside spot +/-5% chain bands.
- Record leg-level bid, ask, mid, age, and spread quality for every observation.

## Daily Artifact List

- `tb11_options_current_nfo_leg_resolver_template.csv`
- `tb11_options_zerodha_quote_only_collector_summary.csv`
- `tb11_options_phase1_observation_ledger_summary.csv`
- `tb11_nifty_chain_band_quote_collector_summary.csv`
- `tb11_t28_freshness_gate_summary.csv`
- `tb11_phase2_paper_price_reconciliation_readiness_summary.csv`
- `tb11_phase2_paper_price_reconciliation_runbook.md`

## Broker-Block Reaffirmation

- Phase 2 remains no-order and paper-price only.
- `place_order`, `modify_order`, and `cancel_order` must not be imported or called.
- Broker execution, live trading, and one-lot validation require explicit future human approval.
