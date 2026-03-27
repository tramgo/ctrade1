# Run Monitor Log

## 2026-03-25

- `17:53` Started `signal_research_native_15m_failed_breakout`
- `18:03` Research outputs confirmed; shortlist alive with `E1602` as clear leader
- `18:03` Started `signal_baseline_native_15m_failed_breakout`
- `late evening` Baseline finished cleanly; best executable policy was `SIGNAL_E1601_BANDED_70` at `-5.820192894889364e-05`
- `late evening` Decision recorded: `Native15mFailedBreakout -> research_only`
- `late evening` Began implementation of next thesis: `Native15mOpenDrive`

## 2026-03-27

- `morning` Rechecked `Native15mOpenDrive` after research-export fix; empty-output issue traced to `MinuteNorm` scale mismatch in the regime filters
- `late morning` Patched `E1701-E1704` filters to the live `MinuteNorm` range and reran research
- `afternoon` Open-drive research completed cleanly; `E1702` led the shortlist with the best selection score
- `afternoon` Open-drive baseline completed cleanly; best executable policy was `SIGNAL_E1701_BANDED_70` at `-0.0006190150485907`
- `afternoon` Decision recorded: `Native15mOpenDrive -> research_only`
- `afternoon` Began implementation of next thesis: `Native15mSessionPhase`
- `midday` Session-phase research completed; `E1803` led classification while `E1801` and `E1802` looked cleaner in raw executable terms
- `midday` Session-phase baseline completed cleanly; best executable policy was `SIGNAL_E1802_BANDED_70` at `-0.0001341339035688`
- `midday` Decision recorded: `Native15mSessionPhase -> research_only`
- `midday` Began implementation of next thesis: `Native15mHoldingHorizon`
- `afternoon` Holding-horizon research completed; `E1903` led classification while `E1902` looked cleaner in raw executable terms
- `late afternoon` Holding-horizon baseline required two wiring fixes before the branch-specific policies evaluated correctly
- `late afternoon` Holding-horizon baseline completed cleanly; best executable policy was `SIGNAL_E1902_BANDED_70` at `-0.0016108139104049`
- `late afternoon` Decision recorded: `Native15mHoldingHorizon -> research_only`
- `late afternoon` Began implementation of next thesis: `Native15mTopKEventRank`

Notes:
- Monitoring followed the runtime/integrity-only early-stop rule.
- No early stop was used for weak intermediate metrics.
