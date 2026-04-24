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
- `2026-04-23 late evening` Top-k event-rank research completed; `E2003` and `E2004` led on classification metrics
- `2026-04-23 late evening` Top-k baseline was monitored live and stopped early after enough evidence: `E2003/E2004` stayed broadly negative, `E2002_BANDED_*` stayed weak, and only `E2002_LONGONLY` showed isolated positives
- `2026-04-23 late evening` Decision recorded: `Native15mTopKEventRank -> research_only`
- `2026-04-24 shortly after midnight` Mean-reversion exhaustion research completed; `E2104` and `E2102` led the shortlist
- `2026-04-24 early morning` Direct compare baseline showed `SIGNAL_E2104_LONGONLY` positive against `FLAT` while native-`15m` `E211` was inert in the same frame
- `2026-04-24 morning` Wider validation baseline completed; `SIGNAL_E2104_LONGONLY` turned negative at `-0.0004467734528908` with breadth weakening to `8` positive vs `19` negative tickers
- `2026-04-24 morning` Decision recorded: `Native15mMeanReversionExhaustion -> research_only` after failed broader validation
- `2026-04-24 morning` Sixty-minute daily-context research completed; `E2201` was the only eligible survivor with credible real-vs-shuffled separation
- `2026-04-24 morning` Sixty-minute daily-context baseline completed cleanly; best executable policy was `SIGNAL_E2201_BANDED_70` at `-0.0018261473995522`
- `2026-04-24 morning` Decision recorded: `SixtyMinuteDailyContext -> research_only`
- `2026-04-24 afternoon` State reconciliation completed; next thesis set to `Native15mBreadthEvent`
- `2026-04-24 12:25` `Native15mBreadthEvent` design check cleared; breadth-positive event gating confirmed as a materially new native-`15m` slice
- `2026-04-24 12:25` `Native15mBreadthEvent` research lock opened with expected outputs under `outputs_native_15m_breadth_event/latest`
- `2026-04-24 12:25` Preflight started for `signal_research_native_15m_breadth_event` using `run_codex_env_check.bat` then `run_compile_check.bat`
- `2026-04-24 12:53` `Native15mBreadthEvent` research completed; `E2302` led with the cleanest real-vs-shuffled separation and positive spread
- `2026-04-24 12:56` `Native15mBreadthEvent` baseline started with `E2302` / `E2304` against `FLAT` and `SIGNAL_E211_BANDED_68`
- `2026-04-24 13:16` `Native15mBreadthEvent` baseline completed cleanly; best executable policy was `SIGNAL_E2302_BANDED_70` at `-0.00044532045311487247`
- `2026-04-24 13:50` Decision recorded: `Native15mBreadthEvent -> research_only`
- `2026-04-24 13:50` Next thesis set to `EventConditionedSizingVeto`
- `2026-04-24 14:06` `EventConditionedSizingVeto` implementation started; overlay design narrowed to incumbent-only veto candidates sourced from existing `15m` event prediction feeds
- `2026-04-24 14:15` `EventConditionedSizingVeto` preflight passed via `run_codex_env_check.bat` and `run_compile_check.bat`
- `2026-04-24 14:15` Started `signal_research_event_conditioned_sizing_veto`
- `2026-04-24 14:27` `EventConditionedSizingVeto` research completed; `E2403` led the shortlist and `E2403` / `E2402` earned baseline promotion
- `2026-04-24 14:30` Operational fix applied: `run_mode.bat` now tees console output into a per-run file under `results/log_runs`
- `2026-04-24 14:29` Started `signal_baseline_event_conditioned_sizing_veto` with `E2403` / `E2402` against `FLAT` and `SIGNAL_E211_BANDED_68`
- `2026-04-24 14:44` `EventConditionedSizingVeto` baseline completed cleanly; best executable policy was `SIGNAL_E2403_E211_EVENT_CONTEXT_VETO` at `6.986428963125287e-05`
- `2026-04-24 14:50` Decision recorded: `EventConditionedSizingVeto -> research_only`; drawdown improved but return stayed below `SIGNAL_E211_BANDED_68`
- `2026-04-24 14:50` Lock released and next thesis set to `NewDataAxisIfAvailable`
- `2026-04-24 afternoon` Batch 01 reconciliation completed; `T07-T09` tracker state corrected and `T10` held because no concrete new local data axis was found
- `2026-04-24 afternoon` Batch 02 planning opened; next design candidate set to `TB02_T01 CrossSectionalCommonalityResidual`

Notes:
- Monitoring followed the runtime/integrity-only early-stop rule.
- No early stop was used for weak research metrics.
- One live baseline run was stopped deliberately after enough executable evidence to show the branch was not developing into a real challenger.
