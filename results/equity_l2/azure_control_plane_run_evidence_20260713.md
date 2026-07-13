# Equity L2 and Kite Token Azure Run Evidence - 2026-07-13

Generated from Azure Container Apps job execution history checked on 2026-07-13 during market hours.

## Token Refresh

| run_date_ist | expected_time_ist | azure_execution | status | start_utc | end_utc | note |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-09 | 08:30 | kite-token-refresh-29726100 | Succeeded | 2026-07-09T03:00:00+00:00 | 2026-07-09T03:00:42+00:00 | Shared token refresh ran before market open. |
| 2026-07-10 | 08:30 | kite-token-refresh-29727540 | Succeeded | 2026-07-10T03:00:00+00:00 | 2026-07-10T03:01:15+00:00 | Shared token refresh ran before market open. |
| 2026-07-13 | 08:30 | kite-token-refresh-29731860 | Succeeded | 2026-07-13T03:00:00+00:00 | 2026-07-13T03:00:43+00:00 | Shared token refresh ran before market open. |

## Equity L2

| run_date_ist | expected_time_ist | azure_execution | status | start_utc | end_utc | note |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-09 | manual late start | equity-l2-live-q5pua1d | Succeeded | 2026-07-09T06:25:15+00:00 | 2026-07-09T10:05:03+00:00 | Manual late run; self-stopped near 15:35 IST. |
| 2026-07-10 | 09:11 | equity-l2-live-29727581 | Succeeded | 2026-07-10T03:41:00+00:00 | 2026-07-10T10:05:08+00:00 | Scheduled run; self-stopped near 15:35 IST. |
| 2026-07-13 | 09:11 | equity-l2-live-29731901 | Running | 2026-07-13T03:41:00+00:00 |  | Scheduled run was still running at the verification time. |

## Forward Evidence Wiring

ACR image `heldc1.azurecr.io/ctrade1/equity-12-c011ector:shared-token` was rebuilt with GitHub evidence publishing support. The pushed digest was `sha256:ab339db9283089e3c3b56806659f0d4aace510560e456f304334ddce9c6d7441`.

Both Azure job templates were configured with `GITHUB_OUTPUT_PUSH_ENABLED=1`, `GITHUB_REPO_URL=https://github.com/tramgo/ctrade1.git`, `GITHUB_BRANCH=main`, and `GITHUB_TOKEN` from the `github-token` Container Apps secret.

Future runs should publish:

- `results/log_runs/kite_token_refresh_YYYYMMDD_HHMMSS_azure.json`
- `results/log_runs/equity_l2_live_YYYYMMDD_HHMMSS_azure.json`
- `results/equity_l2/kite_token_refresh_daily_run_summary.csv`
- `results/equity_l2/equity_l2_live_daily_run_summary.csv`
- `results/equity_l2/latest_kite_token_refresh_run.json`
- `results/equity_l2/latest_equity_l2_live_run.json`
