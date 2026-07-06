# TB18 Earnings Overlay Backtest

Status: `no_earnings_overlay_promoted_sparse_or_no_improvement`

- earnings event range: `2025-01-07` / `2026-08-13`
- TB11 selected allocation: `def_full_resg0_ovg50`
- candidate summary rows: `0`
- sparse or not-testable summary rows: `10`
- broker orders allowed: `False`

## Best Observed Variants

- TB15_T04 `symbol_event_pm1d_window` / `stock_symbol`: status `overlay_not_promoted`, vetoes `5`, mean delta `-0.000021`, worst delta `0.000000`, decision `do_not_promote`
- TB15_T04 `symbol_event_entry_to_expiry` / `stock_symbol`: status `research_preview_sparse_event_vetoes`, vetoes `4`, mean delta `-0.000020`, worst delta `0.000000`, decision `do_not_promote_observe_more_or_backfill_earnings_history`
- TB11 `nifty_event_weight_ge_10pct` / `base`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`
- TB11 `nifty_event_weight_ge_15pct` / `base`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`
- TB11 `nifty_event_weight_ge_20pct` / `base`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`
- TB11 `nifty_event_weight_ge_10pct` / `harsh_stress`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`
- TB11 `nifty_event_weight_ge_15pct` / `harsh_stress`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`
- TB11 `nifty_event_weight_ge_20pct` / `harsh_stress`: status `not_historically_testable_no_event_overlap`, vetoes `0`, mean delta `0.000000`, worst delta `0.000000`, decision `do_not_promote_until_deeper_earnings_history`

Next action: do not promote an earnings overlay to live sizing until historical earnings coverage is deeper or repeated paper observations show stable benefit.
