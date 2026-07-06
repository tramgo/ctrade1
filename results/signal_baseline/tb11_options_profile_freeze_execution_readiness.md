# TB11 Options Profile Freeze And Execution Readiness

Status: `paper_only_profile_frozen`

Date: 2026-06-22

## Frozen Profile

- thesis: `TB11_T19_ProfileFreezeExecutionReadiness`
- selected profile: `def_full_resg0_ovg50`
- profile meaning: defensive allocation at full size, residual growth weight `0`, overlap growth weight `0.50`
- maturity gate: skip the first observed selected-profile trade
- first active trade after maturity gate in historical sample: `2019-02-25`
- reference lot size: `65`
- itemized cost module: mandatory
- cost audit artifact: `results/signal_baseline/tb11_options_itemized_fno_cost_audit_summary.csv`
- no broker order placement from this repo without explicit future human approval

## Reference Evidence

The profile has passed the currently required TB11 checks:

- maturity-adjusted robustness
- rupee and capital-budget calibration
- conservative ITM-expiry STT audit
- itemized Indian F&O cost audit

Reference lot-size `65` itemized-cost read:

- base annualized return after itemized cost: `33.18%`
- moderate-stress annualized return after itemized cost: `28.84%`
- harsh-stress annualized return after itemized cost: `26.50%`
- all years positive
- all folds positive
- historical ITM-expiry trades: `1`
- historical ITM-expiry legs: `2`

This is not live-trading approval. It is a frozen specification for staged paper validation.

## Practical Paper-Trading Plan

| Phase | Duration | Mode | Gate To Pass | Promotion Rule |
|---|---:|---|---|---|
| 1. Dry run | 1-2 months | No broker orders. Log every signal and simulate fills. | Every signal is logged; modeled entry/exit, cost, expiry policy, and skip reason are reproducible; algo trigger timing matches the intended rules. | Advance only if logging is complete and there are no unexplained triggers. |
| 2. Paper at real prices | 3-6 months | Observe real option quotes and paper-fill against captured prices. | At least `10-15` paper trades; actual available premiums within `10-15%` adverse tolerance of modeled premium; no unmodeled costs. | Advance only if fills, costs, and skipped trades match the model closely enough. |
| 3. Tiny live | 3-6 months | Future human-approved minimum-size real-money validation only. | At least `10` real-money trades at `1` lot; confirm broker mechanics, execution friction, taxes/charges, and trader psychology. | Advance only if mechanics and behavior match the paper read; this repo remains blocked until explicitly approved. |
| 4. Scale to target size | ongoing | Gradual size increase. | Phases 1-3 remain valid; cost drift, slippage, and drawdown stay inside guardrails. | Scale only after phase gates hold up and the target budget is revalidated. |

## Phase 1 Dry-Run Requirements

The next implementation gate is a signal logger, not a trading bot.

Each candidate signal must record:

- timestamp and data snapshot used
- selected strategy profile and scenario tag
- spot, VIX, expiry, strikes, and option leg premiums
- model premium, itemized cost estimate, and expected net credit
- entry decision, skip decision, and reason code
- simulated fill assumption
- expiry/exit plan
- itemized cost estimate by leg
- whether the trade would violate any no-trade rule

Required phase-1 artifacts:

- `results/signal_baseline/tb11_options_dry_run_signal_log.csv`
- `results/signal_baseline/tb11_options_dry_run_signal_log_summary.csv`
- `results/signal_baseline/tb11_options_dry_run_reconciliation.md`

## No-Trade Rules

Do not open a TB11 paper/live candidate when any condition is true:

- itemized Indian F&O cost module is unavailable or stale
- option leg premium is missing, stale, crossed, or too wide to estimate a realistic fill
- required expiry chain is incomplete
- a leg would be held through expiry without explicit expiry-risk approval
- actual available premium is worse than modeled premium by more than `15%`
- the trade would exceed the current paper-phase lot, worst-loss, or drawdown budget
- daily signal log or reconciliation is incomplete
- any Zerodha/broker charge schedule has changed and has not been reflected in the model

## Exit-Before-Expiry Rule

Default policy: do not intentionally hold through expiry.

Any expiry-hold test must be separated into its own future thesis and must explicitly model:

- exercised/assigned option STT
- expiry brokerage and GST
- physical-settlement or cash-settlement mechanics where applicable
- margin behavior around expiry
- broker-specific assignment handling

## Kill Switches

Pause TB11 validation immediately if any condition occurs:

- any unmodeled cost appears
- fill slippage exceeds `15%` adverse premium tolerance on a trade
- median adverse fill drift exceeds `10%` across the latest `5` filled/paper-filled trades
- two consecutive signal-log mismatches occur
- any broker/API action is attempted during phases 1 or 2
- a paper/live loss exceeds the current phase loss budget
- data freshness or option-chain integrity cannot be proven

## Current Decision

`TB11_T19` passes as a paper-only profile freeze.

The next gate is `TB11_T20_DryRunSignalLogger`: implement and run a no-order signal logger for 1-2 months before paper-at-real-prices validation.
