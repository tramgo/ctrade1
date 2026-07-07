from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

from .auth import get_kite_client, get_ticker, kite_call_with_retry
from .instruments import ResolvedInstrument, load_instruments, load_symbol_table, load_symbols, resolve_equities


ROOT = Path(__file__).resolve().parent


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["_config_path"] = str(path.resolve())
    config["_config_dir"] = str(path.resolve().parent)
    return config


def config_path(config: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = Path(config["_config_dir"]) / path
    if candidate.exists():
        return candidate
    return ROOT / path


def output_root(config: dict[str, Any]) -> Path:
    path = Path(config.get("output_dir", "data"))
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_configured_instruments(kite, config: dict[str, Any]) -> list[ResolvedInstrument]:
    exchanges = [str(x).upper() for x in config.get("exchanges", ["NSE"])]
    symbol_table = load_symbol_table(config_path(config, config.get("symbols_file", "config/nifty50_symbols.csv")))
    symbols = symbol_table["symbol"].tolist()
    aliases = dict(zip(symbol_table["symbol"], symbol_table["zerodha_symbol"]))
    instruments = load_instruments(kite, exchanges)
    resolved, unresolved = resolve_equities(instruments, symbols, exchanges, symbol_aliases=aliases)

    audit_dir = output_root(config) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(item) for item in resolved]).to_csv(
        audit_dir / "resolved_instruments.csv", index=False
    )
    unresolved.to_csv(audit_dir / "unresolved_instruments.csv", index=False)

    if not resolved:
        raise RuntimeError("No configured symbols resolved to Zerodha instruments.")
    if not unresolved.empty:
        print(f"[resolve] unresolved rows: {len(unresolved)} -> {audit_dir / 'unresolved_instruments.csv'}")
    print(f"[resolve] resolved instruments: {len(resolved)} -> {audit_dir / 'resolved_instruments.csv'}")
    return resolved


def normalize_candles(rows: list[dict[str, Any]], instrument: ResolvedInstrument) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).rename(
        columns={
            "date": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "oi": "oi",
        }
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if getattr(df["timestamp"].dt, "tz", None) is not None:
        df["timestamp"] = df["timestamp"].dt.tz_convert(None)
    df.insert(0, "requested_symbol", instrument.requested_symbol)
    df.insert(1, "exchange", instrument.exchange)
    df.insert(2, "tradingsymbol", instrument.tradingsymbol)
    df.insert(3, "instrument_token", instrument.instrument_token)
    cols = [
        "requested_symbol",
        "exchange",
        "tradingsymbol",
        "instrument_token",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    if "oi" in df.columns:
        cols.append("oi")
    return df[cols].drop_duplicates("timestamp").sort_values("timestamp")


def append_dedup_csv(path: Path, df: pd.DataFrame, keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(keys, keep="last")
    else:
        combined = df
    combined.to_csv(path, index=False)


def run_historical(config: dict[str, Any]) -> None:
    kite = get_kite_client(config_dir=Path(config["_config_dir"]))
    resolved = resolve_configured_instruments(kite, config)
    hist = config.get("historical", {})
    interval = hist.get("interval", "minute")
    tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
    start = pd.Timestamp(hist["from"], tz=tz).to_pydatetime()
    end = pd.Timestamp(hist["to"], tz=tz).to_pydatetime()
    chunk_days = int(hist.get("chunk_days", 60))
    sleep_seconds = float(config.get("rate_limit_sleep_seconds", 0.35))
    append = bool(hist.get("append", True))
    base = output_root(config) / "historical"

    summary = []
    for idx, instrument in enumerate(resolved, start=1):
        rows = []
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=chunk_days), end)
            print(f"[historical] {idx}/{len(resolved)} {instrument.key} {cur} -> {nxt}")
            rows.extend(
                kite_call_with_retry(
                    kite.historical_data,
                    instrument.instrument_token,
                    cur.strftime("%Y-%m-%d %H:%M:%S"),
                    nxt.strftime("%Y-%m-%d %H:%M:%S"),
                    interval,
                )
            )
            cur = nxt + timedelta(seconds=1)
            time.sleep(sleep_seconds)

        df = normalize_candles(rows, instrument)
        out = base / instrument.exchange / f"{instrument.tradingsymbol}_{interval}.csv"
        if append and not df.empty:
            append_dedup_csv(out, df, ["exchange", "tradingsymbol", "timestamp"])
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out, index=False)
        summary.append(
            {
                **asdict(instrument),
                "rows_fetched": len(df),
                "output_path": str(out),
                "status": "ok" if not df.empty else "empty",
            }
        )

    summary_path = base / "historical_fetch_summary.csv"
    pd.DataFrame(summary).to_csv(summary_path, index=False)
    print(f"[historical] summary -> {summary_path}")


class LiveMinuteAggregator:
    def __init__(self, config: dict[str, Any], instruments: list[ResolvedInstrument]):
        self.config = config
        self.instruments_by_token = {item.instrument_token: item for item in instruments}
        self.tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
        self.root = output_root(config)
        self.current: dict[tuple[int, str], dict[str, Any]] = {}
        self.last_flush = time.monotonic()
        self.stopped = False

    def _tick_time(self, tick: dict[str, Any]) -> datetime:
        value = tick.get("exchange_timestamp") or tick.get("timestamp") or tick.get("last_trade_time")
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.now(self.tz)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def _date_tag(self) -> str:
        return datetime.now(self.tz).strftime("%Y%m%d")

    def on_ticks(self, ticks: list[dict[str, Any]]) -> None:
        if self.config.get("live", {}).get("raw_tick_jsonl", True):
            self.write_raw_ticks(ticks)
        for tick in ticks:
            self.add_tick(tick)
        flush_seconds = float(self.config.get("live", {}).get("flush_seconds", 5))
        if time.monotonic() - self.last_flush >= flush_seconds:
            self.flush_closed_minutes()
            self.last_flush = time.monotonic()

    def write_raw_ticks(self, ticks: list[dict[str, Any]]) -> None:
        date_tag = self._date_tag()
        folder = self.root / "live_ticks" / date_tag
        folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now(self.tz).isoformat()
        grouped: dict[int, list[dict[str, Any]]] = {}
        for tick in ticks:
            token = int(tick.get("instrument_token", 0) or 0)
            grouped.setdefault(token, []).append(tick)
        for token, token_ticks in grouped.items():
            instrument = self.instruments_by_token.get(token)
            if instrument is None:
                continue
            path = folder / f"{instrument.exchange}_{instrument.tradingsymbol}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                for tick in token_ticks:
                    payload = {
                        "capture_time": now,
                        "exchange": instrument.exchange,
                        "tradingsymbol": instrument.tradingsymbol,
                        "requested_symbol": instrument.requested_symbol,
                        "tick": self._json_safe(tick),
                    }
                    handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def add_tick(self, tick: dict[str, Any]) -> None:
        token = int(tick.get("instrument_token", 0) or 0)
        instrument = self.instruments_by_token.get(token)
        price = tick.get("last_price")
        if instrument is None or price is None:
            return
        dt = self._tick_time(tick)
        minute = dt.replace(second=0, microsecond=0).isoformat()
        key = (token, minute)
        last_quantity = tick.get("last_traded_quantity") or tick.get("last_quantity") or 0
        volume = tick.get("volume_traded") or tick.get("volume") or 0
        row = self.current.get(key)
        if row is None:
            self.current[key] = {
                "minute": minute,
                "exchange": instrument.exchange,
                "tradingsymbol": instrument.tradingsymbol,
                "requested_symbol": instrument.requested_symbol,
                "instrument_token": token,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "last_quantity_sum": last_quantity,
                "last_seen_day_volume": volume,
                "tick_count": 1,
                "first_tick_time": dt.isoformat(),
                "last_tick_time": dt.isoformat(),
            }
            return
        row["high"] = max(row["high"], price)
        row["low"] = min(row["low"], price)
        row["close"] = price
        row["last_quantity_sum"] = (row.get("last_quantity_sum") or 0) + last_quantity
        row["last_seen_day_volume"] = volume
        row["tick_count"] = int(row.get("tick_count", 0)) + 1
        row["last_tick_time"] = dt.isoformat()

    def flush_closed_minutes(self, force: bool = False) -> None:
        now_minute = datetime.now(self.tz).replace(second=0, microsecond=0).isoformat()
        ready = []
        for key, row in list(self.current.items()):
            if force or row["minute"] < now_minute:
                ready.append(row)
                del self.current[key]
        if not ready or not self.config.get("live", {}).get("minute_bars_csv", True):
            return

        date_tag = self._date_tag()
        folder = self.root / "live_minute_bars" / date_tag
        folder.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(ready).sort_values(["exchange", "tradingsymbol", "minute"])
        for (exchange, symbol), group in df.groupby(["exchange", "tradingsymbol"]):
            path = folder / f"{exchange}_{symbol}_minute.csv"
            append_dedup_csv(path, group, ["exchange", "tradingsymbol", "minute"])
        print(f"[live] flushed minute bars: {len(df)}")

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): LiveMinuteAggregator._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [LiveMinuteAggregator._json_safe(v) for v in value]
        if isinstance(value, datetime):
            return value.isoformat()
        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)


def run_live(config: dict[str, Any]) -> None:
    kite = get_kite_client(config_dir=Path(config["_config_dir"]))
    resolved = resolve_configured_instruments(kite, config)
    ticker = get_ticker(config_dir=Path(config["_config_dir"]))
    aggregator = LiveMinuteAggregator(config, resolved)
    tokens = [item.instrument_token for item in resolved]
    mode_name = str(config.get("live", {}).get("mode", "quote")).lower()

    def stop(_signum=None, _frame=None):
        aggregator.stopped = True
        aggregator.flush_closed_minutes(force=True)
        try:
            ticker.close()
        except Exception:
            pass

    def on_connect(ws, _response):
        print(f"[live] connected; subscribing {len(tokens)} instruments")
        ws.subscribe(tokens)
        mode = ws.MODE_FULL if mode_name == "full" else ws.MODE_LTP if mode_name == "ltp" else ws.MODE_QUOTE
        ws.set_mode(mode, tokens)

    def on_ticks(_ws, ticks):
        aggregator.on_ticks(ticks)

    def on_error(_ws, code, reason):
        print(f"[live] websocket error {code}: {reason}", file=sys.stderr)

    def on_close(_ws, code, reason):
        print(f"[live] websocket closed {code}: {reason}")
        aggregator.flush_closed_minutes(force=True)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    ticker.on_connect = on_connect
    ticker.on_ticks = on_ticks
    ticker.on_error = on_error
    ticker.on_close = on_close
    ticker.connect(threaded=False)


def run_smoke(config: dict[str, Any]) -> None:
    kite = get_kite_client(config_dir=Path(config["_config_dir"]))
    profile = kite_call_with_retry(kite.profile)
    print(f"[smoke] profile ok: {profile.get('user_name', 'user')} ({profile.get('user_id', 'id')})")

    resolved = resolve_configured_instruments(kite, config)
    sample = resolved[: min(4, len(resolved))]
    quote_keys = [item.key for item in sample]
    quotes = kite_call_with_retry(kite.quote, quote_keys)
    print(f"[smoke] quote packets: {len(quotes)} for {', '.join(quote_keys)}")

    first = sample[0]
    tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
    end = datetime.now(tz)
    start = end - timedelta(days=5)
    candles = kite_call_with_retry(
        kite.historical_data,
        first.instrument_token,
        start.strftime("%Y-%m-%d %H:%M:%S"),
        end.strftime("%Y-%m-%d %H:%M:%S"),
        "minute",
    )
    print(f"[smoke] historical minute candles: {len(candles)} for {first.key}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zerodha NSE/BSE equity minute collector")
    parser.add_argument(
        "command",
        choices=[
            "historical",
            "live",
            "resolve",
            "smoke",
            "l2-live",
            "l2-audit",
            "l2-shakedown-report",
            "l2-verify-hardkill",
            "l2-preflight",
            "l2-status",
            "l2-plan-status",
            "l2-market-check",
            "l2-self-test",
        ],
    )
    parser.add_argument("--config", default=str(ROOT / "config" / "collector_config.json"))
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=None,
        help="For l2-live only: stop the WebSocket collector after this many seconds.",
    )
    parser.add_argument(
        "--mark-hardkill-tested",
        action="store_true",
        help="For l2-verify-hardkill only: assert that a manual hard-kill/restart test was just performed.",
    )
    parser.add_argument(
        "--allow-outside-session",
        action="store_true",
        help="For l2-live only: allow a deliberate WebSocket test outside configured market hours.",
    )
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    if args.command == "historical":
        run_historical(config)
    elif args.command == "live":
        run_live(config)
    elif args.command == "resolve":
        kite = get_kite_client(config_dir=Path(config["_config_dir"]))
        resolve_configured_instruments(kite, config)
    elif args.command == "smoke":
        run_smoke(config)
    elif args.command == "l2-live":
        from .l2_collector import run_l2_live

        run_l2_live(
            config,
            duration_seconds=args.duration_seconds,
            allow_outside_session=args.allow_outside_session,
        )
    elif args.command == "l2-audit":
        from .l2_collector import run_l2_audit

        run_l2_audit(config)
    elif args.command == "l2-shakedown-report":
        from .l2_collector import run_l2_shakedown_report

        run_l2_shakedown_report(config)
    elif args.command == "l2-verify-hardkill":
        from .l2_collector import run_l2_verify_hardkill

        run_l2_verify_hardkill(config, mark_hardkill_tested=args.mark_hardkill_tested)
    elif args.command == "l2-preflight":
        from .l2_collector import run_l2_preflight

        run_l2_preflight(config)
    elif args.command == "l2-status":
        from .l2_collector import run_l2_status

        run_l2_status(config)
    elif args.command == "l2-plan-status":
        from .l2_collector import run_l2_plan_status

        run_l2_plan_status(config)
    elif args.command == "l2-market-check":
        from .l2_collector import run_l2_market_check

        run_l2_market_check(config)
    elif args.command == "l2-self-test":
        from .l2_collector import run_l2_self_test

        run_l2_self_test(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
