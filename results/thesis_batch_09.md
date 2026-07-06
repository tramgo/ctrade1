# Thesis Batch 09 - Delivery-Aware Incumbent Overlay

Date: 2026-05-05

## Why This Branch Exists

`TB07` showed the same pattern across three new information axes:

- delivery, OI, and breadth can improve participation quality or worst-fold damage
- none of them created a new standalone engine that beat same-universe buy-hold

That means the next honest branch is not another broad selector family.

It is a narrow overlay on the existing incumbent:

- base engine stays `SIGNAL_E211_BANDED_68`
- delivery becomes a conditioning input, not a replacement signal

## Operating Rule

This batch must stay overlay-only.

It may not:

- invent a new cross-sectional ranker
- replace the incumbent engine
- reopen broad OHLCV-only family search

It may:

- veto weak incumbent entries
- size down weak-delivery entries
- optionally size up or extend holds on strong-delivery entries

## Proposed Thesis Queue

| ID | Thesis | Overlay Logic | Benchmark |
|---|---|---|---|
| `TB09_T01` | `DeliveryAwareIncumbentOverlay` | only take `E211` entries when prior-day delivery regime is supportive | `SIGNAL_E211_BANDED_68` |
| `TB09_T02` | `DeliveryShockEventSlice` | only act on incumbent entries when delivery z-score and price event align | `SIGNAL_E211_BANDED_68` |

## TB09_T01 Initial Experiment Grid

| Variant | Description |
|---|---|
| `delivery_veto_low` | skip `E211` entries when prior-day delivery is below floor |
| `delivery_veto_non_rising` | skip `E211` entries unless delivery trend is rising |
| `delivery_size_down_low` | keep all entries but cut exposure when delivery is weak |
| `delivery_size_up_strong` | modest size increase only when delivery trend and z-score confirm |
| `delivery_hold_extend_strong` | extend hold only on strong-delivery confirmations |

## Pass / Fail Rule

`TB09` should be judged against the incumbent directly, not against buy-hold.

Pass requires:

- mean return above `SIGNAL_E211_BANDED_68`
- no catastrophic worst-fold degradation versus incumbent
- enough participation to remain tradable

Fail requires:

- lower return than incumbent, or
- trivial gain with sample collapse, or
- improvement only in drawdown while return stays below incumbent

## Honest Expectation

Delivery already showed value as a risk-thinner, not as a new alpha engine.

So the most plausible upside here is:

- slightly lower drawdown
- modest improvement in incumbent economics

The expected ceiling is incremental, not transformational.

If `TB09_T01` cannot beat the incumbent cleanly, the honest next move is to stop autonomous systematic research on this retail stack.
