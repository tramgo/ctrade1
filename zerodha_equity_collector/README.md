# Zerodha Equity Minute Collector

Config-driven market-data collector for NSE, BSE, or both. It supports:

- historical 1-minute OHLCV backfill through Kite Connect `historical_data`
- live WebSocket tick capture through `KiteTicker`
- minute-level aggregation of live ticks into OHLCV-like bars
- BSE equivalent resolution by ISIN from the Zerodha instrument dump where possible
- Kite WebSocket full-mode 5-level depth capture for the E1006 L2 restart plan

This folder is intentionally separate from `ssell1.py` and does not place orders.

## Setup

Install dependencies:

```powershell
python -m pip install -r zerodha_equity_collector\requirements.txt
```

Provide Zerodha credentials by environment variables:

```powershell
$env:KITE_API_KEY="..."
$env:KITE_ACCESS_TOKEN="..."
```

The collector accepts the modern `KITE_*` names shown in `.env.example`, and also accepts the repo's existing `API_KEY`, `API_SECRET`, `USERNAME`, `PASSWORD`, and `TOTP_KEY` names for compatibility. If `KITE_ACCESS_TOKEN` is omitted, it tries `access_token_cache.txt` in this folder and then the repo root.

## Historical minute backfill

Edit `config/collector_config.json`, then run:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\collector_config.json historical
```

Choose exchanges in config:

```json
"exchanges": ["NSE"]
"exchanges": ["BSE"]
"exchanges": ["NSE", "BSE"]
```

Outputs are written under `zerodha_equity_collector/data/historical/`.

## Real connectivity smoke test

Use this before a full run:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\collector_config.json smoke
```

It checks:

- cached-token or TOTP login with `profile()`
- NSE/BSE instrument dump resolution
- `quote()` for a small resolved sample
- 5-day historical `minute` candles for the first resolved symbol

## Live tick capture with minute aggregation

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\collector_config.json live
```

Outputs are written under:

- `data/live_ticks/YYYYMMDD/*.jsonl`
- `data/live_minute_bars/YYYYMMDD/*.csv`

Stop with `Ctrl+C`; the collector flushes partial minute bars before exit.

## L2 Depth Restart Collector

The L2 restart plan is implemented as a separate command path and config:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-live
```

Azure ACI packaging and deployment notes are in [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md). The Azure path defaults to private ACR `HeldC1`, repository `zerodha-12-c011ector`, a dedicated resource group `rg-12-c011ector-shakedown-cin`, and a dedicated storage account `st12c011ectorramic`.

Run preflight before each shakedown start:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-preflight
```

Check the configured market session guard:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-market-check
```

For a bounded connection test:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-live --duration-seconds 60
```

`l2-live` refuses to start outside the configured weekday/session window unless you explicitly add:

```powershell
--allow-outside-session
```

Default L2 universe:

- E1006 equity universe from `ssell1.py` / `NSE_LIQUID_UNIVERSE`
- ETF context slice: `NIFTYBEES`, `BANKBEES`, `ITBEES`, `JUNIORBEES`, `GOLDBEES`
- Default exchange: `NSE`

`TATAMOTORS` is deliberately omitted from the L2 shakedown list instead of being aliased to `TMPV`. The post-demerger Kite symbol and the pre-demerger Tata Motors history should not be treated as one continuous economic asset for the collector clock.

The L2 plan cap is enforced at runtime. If `plan.max_symbols_before_interim_gate` is set, commands that resolve instruments refuse a symbols file above that cap. A deliberate exception requires:

```powershell
--allow-symbol-cap-override
```

L2 outputs are written below `zerodha_equity_collector/data_l2/`:

- `raw_l2/trade_date=YYYY-MM-DD/exchange=NSE/symbol=SYMBOL/*.parquet`
- `heartbeat/heartbeat_YYYY-MM-DD.csv`
- `collector_events/events_YYYY-MM-DD.jsonl`
- `audit/l2_daily_audit_detail.csv`
- `audit/l2_daily_audit_summary.csv`
- `audit/l2_shakedown_gate_report.csv`
- `audit/l2_plan_status.csv`
- `audit/l2_plan_status.json`

Each incoming WebSocket full-mode tick is stamped with collector receive time in UTC milliseconds, normalised to top-five buy/sell market depth columns, and flushed to rolling Parquet parts. The event log records start, connect, close, reconnect attempts, errors, flushes, and stop events. The heartbeat gives one-row-per-minute liveness evidence for post-hoc gap audits.

Run the daily post-close audit:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-audit
```

Run the shakedown gate report:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-shakedown-report
```

Write the plan gate ledger:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-plan-status
```

Summarize current collector evidence:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-status
```

Standalone shakedown scripts:

```powershell
zerodha_equity_collector\run_l2_depth_collector.bat
zerodha_equity_collector\run_l2_daily_audit.bat
```

Optional Task Scheduler registration for the four-week collector shakedown:

```powershell
zerodha_equity_collector\register_l2_shakedown_tasks.bat
```

The registration creates a weekday-only collector task at `09:10` IST and a daily audit task at `15:45` IST. `l2-live` auto-stops at the configured `market_session.end` time, currently `15:35` IST. It is intentionally separate from the TB11 options automation. The collector also checks `config/nse_holidays.csv`; populate that file with `date,description` rows for exchange holidays before relying on it unattended through holidays.

The shakedown report intentionally remains blocked until the data proves the plan gates:

- full stable trade dates meet the configured minimum of three trading weeks
- suspect tick-count days are zero
- heartbeat gaps are below the configured threshold
- `audit/hardkill_verification.json` records `{"hardkill_verified": true}` after a manual hard-kill test confirms current partitions survive

`l2-plan-status` is the phase ledger for the attached restart plan. It keeps phase 1 active until the shakedown gate passes, records the first kill-switch condition if the four-week window expires without three stable weeks, keeps feature-panel work locked while phase 1 is active, and records the later month-nine Gap IC thresholds without starting premature feature engineering.

After a manual hard-kill/restart test, record the Parquet-readability evidence:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-verify-hardkill --mark-hardkill-tested
```

Without `--mark-hardkill-tested`, the command only checks file readability and writes `hardkill_verified: false`.

Run an offline write/audit self-test after installing `pyarrow`:

```powershell
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-self-test
```

## Notes

- Zerodha historical data is candle data, not individual trade tape. Use `historical` for archived minute candles.
- Use `live` during market hours when you need tick snapshots captured from the WebSocket and rolled up to minute bars.
- Use `l2-live` for the restart plan; it forces Kite WebSocket full mode and writes 5-level MBP depth.
- The bundled symbol list is a default Nifty 50 seed. Update `config/nifty50_symbols.csv` whenever index membership changes.
- If the smoke test says `Invalid username`, the code reached Zerodha after TLS setup; fix the local `USERNAME` value or provide a valid `KITE_ACCESS_TOKEN`.
