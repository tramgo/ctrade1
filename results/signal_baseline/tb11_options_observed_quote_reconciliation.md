# TB11 Observed Quote Reconciliation

Status: `template_ready_no_order`

This artifact defines the Phase 1 observed-quote workflow. It does not call a broker, place orders, or authorize paper/live trading.

## Daily Capture Workflow

1. Start from `tb11_options_observed_quote_capture_template.csv`.
2. For each live dry-run candidate, copy the matching signal row or create a new row with the same schema.
3. Record the observation timestamp in IST, quote source, quote age, and bid/ask for every required leg.
4. Compute observed defensive credit, observed growth credit, and weighted observed credit.
5. Compare observed weighted credit with modeled credit.
6. Mark whether the observation passes 10% and 15% adverse-premium tolerance.
7. Leave `broker_order_allowed` as `False`; Phase 1 remains no-order.

## Gate Rules

- quote freshness target: `300` seconds or newer
- all legs must have usable bid/ask quotes
- observed premium must stay within the 10-15% adverse tolerance band before Phase 2 consideration
- any surprise cost, stale quote, missing leg, or spread-quality failure becomes a skip reason
- collect real observed dry-run evidence for 1-2 months before paper-at-real-prices validation

## Readout

- template rows: `50`
- broker orders allowed: `False`
- template gate passed: `True`
