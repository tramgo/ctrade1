from __future__ import annotations

import json
import math
import shutil
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

from .auth import get_kite_client, get_ticker
from .auth import kite_call_with_retry
from .collector import kite_allow_totp_login, kite_token_config_dir, load_config, output_root, resolve_configured_instruments
from .collector import config_path
from .collector import enforce_symbol_cap
from .instruments import ResolvedInstrument


DEPTH_LEVELS = 5
BASE_L2_COLUMNS = [
    "collector_received_utc",
    "collector_received_utc_ms",
    "collector_received_monotonic_ns",
    "exchange_timestamp",
    "last_trade_time",
    "trade_date",
    "exchange",
    "tradingsymbol",
    "requested_symbol",
    "instrument_token",
    "last_price",
    "last_traded_quantity",
    "volume_traded",
    "average_traded_price",
    "total_buy_quantity",
    "total_sell_quantity",
    "oi",
    "oi_day_high",
    "oi_day_low",
    "ohlc_open",
    "ohlc_high",
    "ohlc_low",
    "ohlc_close",
    "change",
]


def parquet_available() -> bool:
    try:
        import pyarrow  # noqa: F401

        return True
    except ImportError:
        return False


def parse_hhmm(value: str) -> datetime_time:
    hour_text, minute_text = str(value).strip().split(":", 1)
    return datetime_time(hour=int(hour_text), minute=int(minute_text))


def load_holidays(config: dict[str, Any]) -> set[str]:
    session = config.get("market_session", {})
    holidays_file = session.get("holidays_file")
    if not holidays_file:
        return set()
    path = config_path(config, holidays_file)
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
    except Exception:
        return set()
    if "date" not in df.columns:
        return set()
    dates = pd.to_datetime(df["date"], errors="coerce").dropna().dt.date.astype(str)
    return set(dates.tolist())


def market_session_status(config: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    session = config.get("market_session", {})
    enabled = bool(session.get("enabled", True))
    tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
    now_local = now.astimezone(tz) if now is not None and now.tzinfo is not None else (now.replace(tzinfo=tz) if now is not None else datetime.now(tz))
    weekdays = {int(day) for day in session.get("weekdays", [0, 1, 2, 3, 4])}
    start_time = parse_hhmm(session.get("start", "09:10"))
    end_time = parse_hhmm(session.get("end", "15:35"))
    holidays = load_holidays(config)
    today = now_local.date().isoformat()
    is_weekday = now_local.weekday() in weekdays
    is_holiday = today in holidays
    is_in_time = start_time <= now_local.time() <= end_time
    is_open = bool((not enabled) or (is_weekday and not is_holiday and is_in_time))
    reason = "market_session_open" if is_open else "market_session_disabled" if not enabled else "outside_market_session"
    if enabled and is_holiday:
        reason = "configured_holiday"
    elif enabled and not is_weekday:
        reason = "non_trading_weekday"
    elif enabled and not is_in_time:
        reason = "outside_session_time"
    return {
        "enabled": enabled,
        "now_local": now_local.isoformat(),
        "trade_date": today,
        "weekday": now_local.weekday(),
        "session_start": start_time.strftime("%H:%M"),
        "session_end": end_time.strftime("%H:%M"),
        "is_weekday": is_weekday,
        "is_holiday": is_holiday,
        "is_in_time": is_in_time,
        "is_open": is_open,
        "reason": reason,
    }


def seconds_until_session_end(config: dict[str, Any]) -> int:
    session = config.get("market_session", {})
    tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
    now_local = datetime.now(tz)
    end_time = parse_hhmm(session.get("end", "15:35"))
    end_local = datetime.combine(now_local.date(), end_time, tzinfo=tz)
    return max(int((end_local - now_local).total_seconds()), 1)


def depth_columns() -> list[str]:
    cols: list[str] = []
    for side in ("buy", "sell"):
        for level in range(1, DEPTH_LEVELS + 1):
            cols.extend(
                [
                    f"{side}_{level}_price",
                    f"{side}_{level}_quantity",
                    f"{side}_{level}_orders",
                ]
            )
    return cols


def l2_columns() -> list[str]:
    return BASE_L2_COLUMNS + depth_columns()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def infer_trade_date(tick: dict[str, Any], received_utc: datetime, tz: ZoneInfo) -> str:
    value = tick.get("exchange_timestamp") or tick.get("timestamp") or tick.get("last_trade_time")
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(tz).date().isoformat()
    return received_utc.astimezone(tz).date().isoformat()


def normalize_l2_tick(
    tick: dict[str, Any],
    instrument: ResolvedInstrument,
    received_utc: datetime,
    received_monotonic_ns: int,
    tz: ZoneInfo,
) -> dict[str, Any]:
    ohlc = tick.get("ohlc", {}) if isinstance(tick.get("ohlc"), dict) else {}
    row: dict[str, Any] = {
        "collector_received_utc": received_utc.isoformat(),
        "collector_received_utc_ms": int(received_utc.timestamp() * 1000),
        "collector_received_monotonic_ns": int(received_monotonic_ns),
        "exchange_timestamp": _to_iso(tick.get("exchange_timestamp") or tick.get("timestamp")),
        "last_trade_time": _to_iso(tick.get("last_trade_time")),
        "trade_date": infer_trade_date(tick, received_utc, tz),
        "exchange": instrument.exchange,
        "tradingsymbol": instrument.tradingsymbol,
        "requested_symbol": instrument.requested_symbol,
        "instrument_token": int(instrument.instrument_token),
        "last_price": tick.get("last_price"),
        "last_traded_quantity": tick.get("last_traded_quantity") or tick.get("last_quantity"),
        "volume_traded": tick.get("volume_traded") or tick.get("volume"),
        "average_traded_price": tick.get("average_traded_price"),
        "total_buy_quantity": tick.get("total_buy_quantity"),
        "total_sell_quantity": tick.get("total_sell_quantity"),
        "oi": tick.get("oi"),
        "oi_day_high": tick.get("oi_day_high"),
        "oi_day_low": tick.get("oi_day_low"),
        "ohlc_open": ohlc.get("open"),
        "ohlc_high": ohlc.get("high"),
        "ohlc_low": ohlc.get("low"),
        "ohlc_close": ohlc.get("close"),
        "change": tick.get("change"),
    }
    depth = tick.get("depth", {}) if isinstance(tick.get("depth"), dict) else {}
    for side in ("buy", "sell"):
        levels = depth.get(side, []) if isinstance(depth.get(side), list) else []
        for idx in range(DEPTH_LEVELS):
            level = levels[idx] if idx < len(levels) and isinstance(levels[idx], dict) else {}
            prefix = f"{side}_{idx + 1}"
            row[f"{prefix}_price"] = level.get("price")
            row[f"{prefix}_quantity"] = level.get("quantity")
            row[f"{prefix}_orders"] = level.get("orders")
    return row


class CollectorEventLogger:
    def __init__(self, root: Path, tz: ZoneInfo):
        self.root = root
        self.tz = tz
        self.event_dir = root / "collector_events"
        self.event_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, **fields: Any) -> None:
        now = datetime.now(UTC)
        payload = {
            "event_utc": now.isoformat(),
            "event_ist": now.astimezone(self.tz).isoformat(),
            "event_type": event_type,
            **{key: _json_safe(value) for key, value in fields.items()},
        }
        path = self.event_dir / f"events_{now.date().isoformat()}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


class HeartbeatWriter:
    def __init__(self, root: Path, tz: ZoneInfo, heartbeat_seconds: int):
        self.root = root
        self.tz = tz
        self.heartbeat_seconds = max(int(heartbeat_seconds), 1)
        self.last_write_monotonic = 0.0
        self.heartbeat_dir = root / "heartbeat"
        self.heartbeat_dir.mkdir(parents=True, exist_ok=True)

    def maybe_write(
        self,
        *,
        connected: bool,
        subscribed_count: int,
        ticks_since_start: int,
        last_tick_utc: str,
        buffered_rows: int,
    ) -> None:
        now_mono = time.monotonic()
        if now_mono - self.last_write_monotonic < self.heartbeat_seconds:
            return
        self.last_write_monotonic = now_mono
        now = datetime.now(UTC)
        row = {
            "heartbeat_utc": now.isoformat(),
            "heartbeat_ist": now.astimezone(self.tz).isoformat(),
            "connected": bool(connected),
            "subscribed_count": int(subscribed_count),
            "ticks_since_start": int(ticks_since_start),
            "last_tick_utc": last_tick_utc,
            "buffered_rows": int(buffered_rows),
        }
        path = self.heartbeat_dir / f"heartbeat_{now.date().isoformat()}.csv"
        pd.DataFrame([row]).to_csv(path, index=False, mode="a", header=not path.exists())


class L2ParquetRollingWriter:
    def __init__(
        self,
        root: Path,
        *,
        compression: str = "zstd",
        flush_seconds: int = 10,
        max_buffer_rows: int = 25000,
    ):
        self.root = root
        self.compression = compression
        self.flush_seconds = max(int(flush_seconds), 1)
        self.max_buffer_rows = max(int(max_buffer_rows), 1)
        self.buffer: list[dict[str, Any]] = []
        self.last_flush_monotonic = time.monotonic()
        self.part_counter = 0

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        self.buffer.extend(rows)
        if self.should_flush():
            self.flush()

    def should_flush(self) -> bool:
        return (
            len(self.buffer) >= self.max_buffer_rows
            or time.monotonic() - self.last_flush_monotonic >= self.flush_seconds
        )

    def flush(self) -> list[Path]:
        if not self.buffer:
            self.last_flush_monotonic = time.monotonic()
            return []
        if not parquet_available():
            raise RuntimeError("pyarrow is required for typed Parquet L2 writes. Install requirements.txt.")

        df = pd.DataFrame(self.buffer)
        for col in l2_columns():
            if col not in df.columns:
                df[col] = pd.NA
        df = df[l2_columns()].copy()
        written: list[Path] = []
        for (trade_date, exchange, symbol), group in df.groupby(["trade_date", "exchange", "tradingsymbol"], dropna=False):
            self.part_counter += 1
            folder = self.root / "raw_l2" / f"trade_date={trade_date}" / f"exchange={exchange}" / f"symbol={symbol}"
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%H%M%S_%f")
            final_path = folder / f"part-{stamp}-{self.part_counter:06d}.parquet"
            tmp_path = final_path.with_suffix(".tmp.parquet")
            group.to_parquet(tmp_path, engine="pyarrow", compression=self.compression, index=False)
            tmp_path.replace(final_path)
            written.append(final_path)
        self.buffer.clear()
        self.last_flush_monotonic = time.monotonic()
        return written


class L2DepthCollector:
    def __init__(self, config: dict[str, Any], instruments: list[ResolvedInstrument]):
        self.config = config
        self.l2 = config.get("l2", {})
        self.tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
        self.root = output_root(config)
        self.instruments = instruments
        self.instruments_by_token = {item.instrument_token: item for item in instruments}
        self.writer = L2ParquetRollingWriter(
            self.root,
            compression=str(self.l2.get("compression", "zstd")),
            flush_seconds=int(self.l2.get("flush_seconds", 10)),
            max_buffer_rows=int(self.l2.get("max_buffer_rows", 25000)),
        )
        self.events = CollectorEventLogger(self.root, self.tz)
        self.heartbeat = HeartbeatWriter(
            self.root,
            self.tz,
            heartbeat_seconds=int(self.l2.get("heartbeat_seconds", 60)),
        )
        self.connected = False
        self.stopped = False
        self.ticks_since_start = 0
        self.last_tick_utc = ""

    @property
    def tokens(self) -> list[int]:
        return [item.instrument_token for item in self.instruments]

    def on_connect(self, ws, response: Any) -> None:
        self.connected = True
        self.events.log("connect", subscribed_count=len(self.tokens), response=response)
        ws.subscribe(self.tokens)
        ws.set_mode(ws.MODE_FULL, self.tokens)

    def on_ticks(self, _ws, ticks: list[dict[str, Any]]) -> None:
        received_utc = datetime.now(UTC)
        received_monotonic_ns = time.monotonic_ns()
        rows: list[dict[str, Any]] = []
        for tick in ticks:
            token = int(tick.get("instrument_token", 0) or 0)
            instrument = self.instruments_by_token.get(token)
            if instrument is None:
                continue
            rows.append(normalize_l2_tick(tick, instrument, received_utc, received_monotonic_ns, self.tz))
        if rows:
            self.ticks_since_start += len(rows)
            self.last_tick_utc = received_utc.isoformat()
            self.writer.add_rows(rows)
        self.heartbeat.maybe_write(
            connected=self.connected,
            subscribed_count=len(self.tokens),
            ticks_since_start=self.ticks_since_start,
            last_tick_utc=self.last_tick_utc,
            buffered_rows=len(self.writer.buffer),
        )

    def on_error(self, _ws, code: Any, reason: Any) -> None:
        self.events.log("error", code=code, reason=reason)

    def on_close(self, _ws, code: Any, reason: Any) -> None:
        self.connected = False
        self.events.log("close", code=code, reason=reason)
        self.flush("close")

    def on_reconnect(self, _ws, attempts_count: int) -> None:
        self.connected = False
        self.events.log("reconnect_attempt", attempts_count=attempts_count)

    def on_noreconnect(self, _ws) -> None:
        self.connected = False
        self.events.log("reconnect_exhausted")

    def flush(self, reason: str) -> None:
        written = self.writer.flush()
        if written:
            self.events.log("flush", reason=reason, files=[str(path) for path in written], file_count=len(written))

    def stop(self, ticker=None) -> None:
        self.stopped = True
        self.flush("stop")
        self.heartbeat.maybe_write(
            connected=False,
            subscribed_count=len(self.tokens),
            ticks_since_start=self.ticks_since_start,
            last_tick_utc=self.last_tick_utc,
            buffered_rows=len(self.writer.buffer),
        )
        self.events.log("stop", ticks_since_start=self.ticks_since_start)
        if ticker is not None:
            for method_name in ("stop_retry", "close", "stop"):
                method = getattr(ticker, method_name, None)
                if not callable(method):
                    continue
                try:
                    method()
                except Exception as exc:
                    self.events.log("ticker_stop_error", method=method_name, error=str(exc))


def run_l2_live(
    config: dict[str, Any],
    *,
    duration_seconds: int | None = None,
    allow_outside_session: bool = False,
) -> None:
    if str(config.get("l2", {}).get("mode", "full")).lower() != "full":
        raise RuntimeError("L2 depth collection requires KiteTicker full mode.")
    session = market_session_status(config)
    if not session["is_open"] and not allow_outside_session:
        root = output_root(config)
        CollectorEventLogger(root, ZoneInfo(config.get("timezone", "Asia/Kolkata"))).log(
            "blocked_outside_market_session",
            session=session,
        )
        raise RuntimeError(
            "Refusing to start l2-live outside configured market session. "
            f"reason={session['reason']} now={session['now_local']}. "
            "Use --allow-outside-session for an intentional connectivity test."
        )
    token_dir = kite_token_config_dir(config)
    allow_login = kite_allow_totp_login()
    kite = get_kite_client(config_dir=token_dir, allow_login=allow_login)
    resolved = resolve_configured_instruments(kite, config)
    ticker = get_ticker(config_dir=token_dir, allow_login=allow_login)
    collector = L2DepthCollector(config, resolved)

    if hasattr(ticker, "enable_reconnect"):
        ticker.enable_reconnect(
            reconnect_interval=int(config.get("l2", {}).get("reconnect_interval_seconds", 5)),
            reconnect_tries=int(config.get("l2", {}).get("reconnect_tries", 50)),
        )

    def stop(_signum=None, _frame=None):
        collector.stop(ticker)

    import signal

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    ticker.on_connect = collector.on_connect
    ticker.on_ticks = collector.on_ticks
    ticker.on_error = collector.on_error
    ticker.on_close = collector.on_close
    ticker.on_reconnect = collector.on_reconnect
    ticker.on_noreconnect = collector.on_noreconnect
    collector.events.log("start", instruments=[asdict(item) for item in resolved])
    if duration_seconds is None:
        duration_seconds = seconds_until_session_end(config)
        collector.events.log("session_end_stop_scheduled", duration_seconds=int(duration_seconds))
    timer = None
    if duration_seconds is not None and duration_seconds > 0:
        collector.events.log("bounded_run_scheduled", duration_seconds=int(duration_seconds))
        timer = threading.Timer(float(duration_seconds), lambda: collector.stop(ticker))
        timer.daemon = True
        timer.start()
    ticker.connect(threaded=False)
    if timer is not None:
        timer.cancel()


def run_l2_market_check(config: dict[str, Any]) -> pd.DataFrame:
    root = output_root(config)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    status = market_session_status(config)
    out = pd.DataFrame([status])
    path = audit_dir / "l2_market_check.csv"
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(f"[l2-market-check] status -> {path}")
    return out


def raw_l2_files(root: Path) -> list[Path]:
    raw_dir = root / "raw_l2"
    if not raw_dir.exists():
        return []
    return sorted(raw_dir.glob("trade_date=*/exchange=*/symbol=*/*.parquet"))


def verify_l2_parquet_readability(root: Path) -> dict[str, Any]:
    files = raw_l2_files(root)
    unreadable = []
    total_rows = 0
    required_columns = set(l2_columns())
    missing_column_files = []
    for path in files:
        try:
            df = pd.read_parquet(path)
        except Exception as exc:
            unreadable.append({"path": str(path), "error": str(exc)})
            continue
        total_rows += int(len(df))
        missing = sorted(required_columns - set(df.columns))
        if missing:
            missing_column_files.append({"path": str(path), "missing_columns": missing})
    return {
        "parquet_files": len(files),
        "total_rows": total_rows,
        "unreadable_files": unreadable,
        "missing_column_files": missing_column_files,
        "all_files_readable": bool(files) and not unreadable and not missing_column_files,
    }


def build_tick_count_frame(root: Path) -> pd.DataFrame:
    rows = []
    for path in raw_l2_files(root):
        try:
            df = pd.read_parquet(path, columns=["trade_date", "exchange", "tradingsymbol"])
        except Exception:
            rows.append({"path": str(path), "read_error": True, "tick_count": 0})
            continue
        if df.empty:
            rows.append({"path": str(path), "read_error": False, "tick_count": 0})
            continue
        grouped = df.groupby(["trade_date", "exchange", "tradingsymbol"], dropna=False).size().reset_index(name="tick_count")
        for row in grouped.to_dict("records"):
            row["path"] = str(path)
            row["read_error"] = False
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["trade_date", "exchange", "tradingsymbol", "tick_count", "path", "read_error"])
    out = pd.DataFrame(rows)
    if {"trade_date", "exchange", "tradingsymbol"}.issubset(out.columns):
        out = (
            out.groupby(["trade_date", "exchange", "tradingsymbol"], dropna=False)
            .agg(tick_count=("tick_count", "sum"), parquet_files=("path", "count"), read_error=("read_error", "max"))
            .reset_index()
        )
    return out


def heartbeat_gap_minutes(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted((root / "heartbeat").glob("heartbeat_*.csv")) if (root / "heartbeat").exists() else []:
        df = pd.read_csv(path)
        if df.empty or "heartbeat_utc" not in df.columns:
            continue
        df["heartbeat_utc"] = pd.to_datetime(df["heartbeat_utc"], errors="coerce", utc=True)
        df = df.dropna(subset=["heartbeat_utc"]).sort_values("heartbeat_utc")
        if df.empty:
            continue
        diffs = df["heartbeat_utc"].diff().dt.total_seconds().fillna(60)
        gap_minutes = float(diffs.loc[diffs > 90].sub(60).sum() / 60.0)
        rows.append({"trade_date": df["heartbeat_utc"].dt.date.iloc[0].isoformat(), "heartbeat_rows": len(df), "heartbeat_gap_minutes": gap_minutes})
    return pd.DataFrame(rows)


def event_reconnect_gap_minutes(root: Path) -> pd.DataFrame:
    rows = []
    event_dir = root / "collector_events"
    if not event_dir.exists():
        return pd.DataFrame(columns=["trade_date", "event_reconnect_gap_minutes", "disconnect_events"])
    for path in sorted(event_dir.glob("events_*.jsonl")):
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            continue
        df = pd.DataFrame(events)
        if "event_utc" not in df.columns or "event_type" not in df.columns:
            continue
        df["event_utc"] = pd.to_datetime(df["event_utc"], errors="coerce", utc=True)
        df = df.dropna(subset=["event_utc"]).sort_values("event_utc")
        gap_seconds = 0.0
        disconnect_events = 0
        open_disconnect: pd.Timestamp | None = None
        for row in df[["event_utc", "event_type"]].itertuples(index=False):
            event_type = str(row.event_type)
            if event_type in {"close", "error", "reconnect_attempt", "reconnect_exhausted"} and open_disconnect is None:
                open_disconnect = row.event_utc
                disconnect_events += 1
            elif event_type == "connect" and open_disconnect is not None:
                gap_seconds += max((row.event_utc - open_disconnect).total_seconds(), 0.0)
                open_disconnect = None
        trade_date = df["event_utc"].dt.date.iloc[0].isoformat()
        rows.append(
            {
                "trade_date": trade_date,
                "event_reconnect_gap_minutes": gap_seconds / 60.0,
                "disconnect_events": disconnect_events,
            }
        )
    return pd.DataFrame(rows)


def run_l2_audit(config: dict[str, Any]) -> pd.DataFrame:
    root = output_root(config)
    tick_counts = build_tick_count_frame(root)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    if tick_counts.empty:
        tick_counts.to_csv(audit_dir / "l2_daily_audit_detail.csv", index=False)
        pd.DataFrame([{"status": "no_l2_parquet_files", "symbol_days": 0}]).to_csv(
            audit_dir / "l2_daily_audit_summary.csv", index=False
        )
        print(f"[l2-audit] no parquet files under {root / 'raw_l2'}")
        return tick_counts

    tick_counts["trade_date"] = pd.to_datetime(tick_counts["trade_date"], errors="coerce")
    tick_counts = tick_counts.sort_values(["exchange", "tradingsymbol", "trade_date"])
    median_days = int(config.get("l2", {}).get("rolling_median_days", 7))
    suspect_ratio = float(config.get("l2", {}).get("tick_count_suspect_ratio", 0.60))
    tick_counts["rolling_7d_median"] = (
        tick_counts.groupby(["exchange", "tradingsymbol"])["tick_count"]
        .transform(lambda s: s.shift(1).rolling(median_days, min_periods=1).median())
    )
    tick_counts["tick_count_ratio"] = tick_counts["tick_count"] / tick_counts["rolling_7d_median"].replace({0: math.nan})
    tick_counts["suspect_tick_count"] = tick_counts["tick_count_ratio"].lt(suspect_ratio).fillna(False)
    gaps = heartbeat_gap_minutes(root)
    if not gaps.empty:
        gaps["trade_date"] = pd.to_datetime(gaps["trade_date"], errors="coerce")
        tick_counts = tick_counts.merge(gaps, on="trade_date", how="left")
    else:
        tick_counts["heartbeat_rows"] = 0
        tick_counts["heartbeat_gap_minutes"] = math.nan
    event_gaps = event_reconnect_gap_minutes(root)
    if not event_gaps.empty:
        event_gaps["trade_date"] = pd.to_datetime(event_gaps["trade_date"], errors="coerce")
        tick_counts = tick_counts.merge(event_gaps, on="trade_date", how="left")
    else:
        tick_counts["event_reconnect_gap_minutes"] = math.nan
        tick_counts["disconnect_events"] = 0
    tick_counts["trade_date"] = tick_counts["trade_date"].dt.date.astype(str)
    tick_counts.to_csv(audit_dir / "l2_daily_audit_detail.csv", index=False)
    summary = pd.DataFrame(
        [
            {
                "status": "audit_complete",
                "symbol_days": int(len(tick_counts)),
                "suspect_symbol_days": int(tick_counts["suspect_tick_count"].sum()),
                "read_error_symbol_days": int(tick_counts["read_error"].astype(bool).sum()) if "read_error" in tick_counts.columns else 0,
                "median_days": median_days,
                "suspect_ratio": suspect_ratio,
                "output_detail": str(audit_dir / "l2_daily_audit_detail.csv"),
            }
        ]
    )
    summary.to_csv(audit_dir / "l2_daily_audit_summary.csv", index=False)
    print(f"[l2-audit] detail -> {audit_dir / 'l2_daily_audit_detail.csv'}")
    return tick_counts


def run_l2_shakedown_report(config: dict[str, Any]) -> pd.DataFrame:
    root = output_root(config)
    audit = run_l2_audit(config)
    audit_dir = root / "audit"
    min_stable_days = int(config.get("l2", {}).get("shakedown_min_stable_days", 15))
    max_gap = float(config.get("l2", {}).get("shakedown_max_reconnect_gap_minutes_per_symbol_day", 5.0))
    hardkill_path = audit_dir / "hardkill_verification.json"
    hardkill_verified = False
    if hardkill_path.exists():
        try:
            hardkill_verified = bool(json.loads(hardkill_path.read_text(encoding="utf-8")).get("hardkill_verified"))
        except Exception:
            hardkill_verified = False

    if audit.empty:
        status = "blocked_no_l2_data"
        stable_symbol_days = 0
        stable_trade_dates = 0
        full_stable_trade_dates = 0
        avg_gap = math.nan
        suspect_days = 0
    else:
        stable = audit.loc[~audit.get("suspect_tick_count", pd.Series(False, index=audit.index)).astype(bool)].copy()
        stable_symbol_days = int(len(stable))
        suspect_days = int(audit.get("suspect_tick_count", pd.Series(False, index=audit.index)).astype(bool).sum())
        expected_symbols_per_day = int(audit.groupby("trade_date")["tradingsymbol"].nunique().max()) if "tradingsymbol" in audit.columns else 0
        stable_by_date = (
            stable.groupby("trade_date")["tradingsymbol"].nunique()
            if "trade_date" in stable.columns and "tradingsymbol" in stable.columns and not stable.empty
            else pd.Series(dtype=int)
        )
        stable_trade_dates = int(len(stable_by_date))
        full_stable_trade_dates = int((stable_by_date >= expected_symbols_per_day).sum()) if expected_symbols_per_day else 0
        heartbeat_gap = pd.to_numeric(audit.get("heartbeat_gap_minutes", pd.Series(dtype=float)), errors="coerce").fillna(0)
        event_gap = pd.to_numeric(audit.get("event_reconnect_gap_minutes", pd.Series(dtype=float)), errors="coerce").fillna(0)
        avg_gap = float(pd.concat([heartbeat_gap, event_gap], axis=1).max(axis=1).mean())
        status = (
            "shakedown_gate_passed"
            if full_stable_trade_dates >= min_stable_days and suspect_days == 0 and avg_gap <= max_gap and hardkill_verified
            else "shakedown_gate_blocked"
        )

    report = pd.DataFrame(
        [
            {
                "status": status,
                "stable_symbol_days": stable_symbol_days,
                "stable_trade_dates": stable_trade_dates,
                "full_stable_trade_dates": full_stable_trade_dates,
                "min_full_stable_trade_dates_required": min_stable_days,
                "suspect_symbol_days": suspect_days,
                "avg_heartbeat_gap_minutes": avg_gap,
                "max_gap_minutes_allowed": max_gap,
                "hardkill_verified": hardkill_verified,
                "hardkill_verification_path": str(hardkill_path),
            }
        ]
    )
    report.to_csv(audit_dir / "l2_shakedown_gate_report.csv", index=False)
    print(f"[l2-shakedown] report -> {audit_dir / 'l2_shakedown_gate_report.csv'}")
    return report


def run_l2_plan_status(config: dict[str, Any]) -> pd.DataFrame:
    root = output_root(config)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    plan = config.get("plan", {})
    audit = latest_csv_row(audit_dir / "l2_daily_audit_summary.csv")
    shakedown = latest_csv_row(audit_dir / "l2_shakedown_gate_report.csv")
    detail_path = audit_dir / "l2_daily_audit_detail.csv"
    first_trade_date = ""
    latest_trade_date = ""
    calendar_days_observed = 0
    if detail_path.exists():
        try:
            detail = pd.read_csv(detail_path)
            trade_dates = pd.to_datetime(detail.get("trade_date", pd.Series(dtype=str)), errors="coerce").dropna()
            if not trade_dates.empty:
                first = trade_dates.min().date()
                latest = trade_dates.max().date()
                first_trade_date = first.isoformat()
                latest_trade_date = latest.isoformat()
                calendar_days_observed = (latest - first).days + 1
        except Exception:
            first_trade_date = ""
            latest_trade_date = ""
            calendar_days_observed = 0

    shakedown_status = str(shakedown.get("status", "missing_shakedown_report"))
    shakedown_days_required = int(config.get("l2", {}).get("shakedown_min_stable_days", 15))
    shakedown_full_days = int(float(shakedown.get("full_stable_trade_dates", 0) or 0))
    shakedown_calendar_days = int(plan.get("shakedown_calendar_days", 28))
    shakedown_passed = shakedown_status == "shakedown_gate_passed"
    shakedown_window_expired = calendar_days_observed >= shakedown_calendar_days
    kill_switch_1_fired = bool(shakedown_window_expired and not shakedown_passed)
    feature_work_allowed = bool(
        shakedown_passed or plan.get("feature_work_allowed_before_shakedown_pass", False)
    )
    if kill_switch_1_fired:
        plan_status = "kill_switch_1_due_rebuild_or_delay"
        next_allowed_action = "stop_or_rebuild_collector_before_research"
    elif shakedown_passed:
        plan_status = "phase1_passed_phase2_collection_allowed"
        next_allowed_action = "begin_nine_month_collection_and_weekly_feature_panel_builds"
    else:
        plan_status = "phase1_shakedown_active"
        next_allowed_action = "continue_collector_shakedown_only"

    payload = {
        "status": plan_status,
        "current_phase": plan.get("current_phase", "phase1_collector_shakedown"),
        "next_allowed_action": next_allowed_action,
        "feature_work_allowed": feature_work_allowed,
        "vendor_l2_backfill_allowed": bool(plan.get("vendor_l2_backfill_allowed", False)),
        "symbol_cap_before_interim_gate": int(plan.get("max_symbols_before_interim_gate", 33)),
        "first_trade_date": first_trade_date,
        "latest_trade_date": latest_trade_date,
        "calendar_days_observed": calendar_days_observed,
        "shakedown_calendar_days": shakedown_calendar_days,
        "shakedown_window_expired": shakedown_window_expired,
        "shakedown_status": shakedown_status,
        "shakedown_full_stable_trade_dates": shakedown_full_days,
        "shakedown_required_full_stable_trade_dates": shakedown_days_required,
        "kill_switch_1_fired": kill_switch_1_fired,
        "audit_status": audit.get("status", "missing_audit_summary"),
        "interim_signal_readout_months": int(plan.get("interim_signal_readout_months", 9)),
        "interim_gap_ic_kill_below": float(plan.get("interim_gap_ic_kill_below", 0.01)),
        "interim_gap_ic_continue_threshold": float(plan.get("interim_gap_ic_continue_threshold", 0.02)),
        "generated_utc": datetime.now(UTC).isoformat(),
    }
    (audit_dir / "l2_plan_status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = pd.DataFrame([payload])
    out.to_csv(audit_dir / "l2_plan_status.csv", index=False)
    print(out.to_string(index=False))
    print(f"[l2-plan-status] status -> {audit_dir / 'l2_plan_status.csv'}")
    return out


def latest_csv_row(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    if df.empty:
        return {}
    return df.tail(1).iloc[0].to_dict()


def latest_jsonl_event(event_dir: Path) -> dict[str, Any]:
    if not event_dir.exists():
        return {}
    files = sorted(event_dir.glob("events_*.jsonl"))
    for path in reversed(files):
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            continue
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            return {"event_file": str(path), "event_parse_error": True}
    return {}


def run_l2_status(config: dict[str, Any]) -> pd.DataFrame:
    root = output_root(config)
    audit_dir = root / "audit"
    files = raw_l2_files(root)
    detail = latest_csv_row(audit_dir / "l2_daily_audit_summary.csv")
    shakedown = latest_csv_row(audit_dir / "l2_shakedown_gate_report.csv")
    latest_event = latest_jsonl_event(root / "collector_events")
    heartbeat_files = sorted((root / "heartbeat").glob("heartbeat_*.csv")) if (root / "heartbeat").exists() else []
    latest_heartbeat = latest_csv_row(heartbeat_files[-1]) if heartbeat_files else {}
    status = pd.DataFrame(
        [
            {
                "raw_l2_parquet_files": len(files),
                "latest_audit_status": detail.get("status", ""),
                "latest_audit_symbol_days": detail.get("symbol_days", ""),
                "latest_shakedown_status": shakedown.get("status", ""),
                "latest_shakedown_full_stable_trade_dates": shakedown.get("full_stable_trade_dates", ""),
                "latest_shakedown_required_trade_dates": shakedown.get("min_full_stable_trade_dates_required", ""),
                "latest_heartbeat_utc": latest_heartbeat.get("heartbeat_utc", ""),
                "latest_heartbeat_ticks_since_start": latest_heartbeat.get("ticks_since_start", ""),
                "latest_event_utc": latest_event.get("event_utc", ""),
                "latest_event_type": latest_event.get("event_type", ""),
            }
        ]
    )
    status_path = audit_dir / "l2_status.csv"
    audit_dir.mkdir(parents=True, exist_ok=True)
    status.to_csv(status_path, index=False)
    print(status.to_string(index=False))
    print(f"[l2-status] status -> {status_path}")
    return status


def run_l2_preflight(config: dict[str, Any]) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    root = output_root(config)
    add_check("pyarrow_available", parquet_available(), "required for Parquet writes")
    try:
        test_dir = root / "preflight"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_path = test_dir / "write_test.tmp"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        add_check("output_dir_writable", True, str(root))
    except Exception as exc:
        add_check("output_dir_writable", False, str(exc))

    try:
        kite = get_kite_client(config_dir=kite_token_config_dir(config), allow_login=kite_allow_totp_login())
        profile = kite_call_with_retry(kite.profile)
        add_check("kite_profile", True, f"{profile.get('user_name', 'user')} ({profile.get('user_id', 'id')})")
    except Exception as exc:
        kite = None
        add_check("kite_profile", False, str(exc))

    if kite is not None:
        try:
            resolved = resolve_configured_instruments(kite, config)
            add_check("instrument_resolution", len(resolved) > 0, f"resolved={len(resolved)}")
            if resolved:
                quote_keys = [item.key for item in resolved[: min(4, len(resolved))]]
                quotes = kite_call_with_retry(kite.quote, quote_keys)
                add_check("kite_quote_sample", len(quotes) == len(quote_keys), f"quotes={len(quotes)} keys={','.join(quote_keys)}")
        except Exception as exc:
            add_check("instrument_resolution", False, str(exc))

    out = pd.DataFrame(checks)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "l2_preflight.csv"
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(f"[l2-preflight] checks -> {path}")
    if not bool(out["passed"].all()):
        raise RuntimeError("L2 preflight failed; see l2_preflight.csv")
    return out


def run_l2_verify_hardkill(config: dict[str, Any], *, mark_hardkill_tested: bool = False) -> dict[str, Any]:
    root = output_root(config)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    readability = verify_l2_parquet_readability(root)
    now = datetime.now(UTC)
    payload = {
        "verification_utc": now.isoformat(),
        "hardkill_verified": bool(mark_hardkill_tested and readability["all_files_readable"]),
        "manual_hardkill_test_claimed": bool(mark_hardkill_tested),
        "note": (
            "Set hardkill_verified=true only when this command is run after a manual hard-kill/restart "
            "test and all current Parquet partitions are readable."
        ),
        **readability,
    }
    path = audit_dir / "hardkill_verification.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[l2-hardkill] verification -> {path}")
    if not payload["hardkill_verified"]:
        print("[l2-hardkill] hardkill_verified=false; run with --mark-hardkill-tested after a real hard-kill test.")
    return payload


def sample_depth_tick(token: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "instrument_token": token,
        "last_price": 100.5,
        "last_traded_quantity": 10,
        "volume_traded": 1000,
        "average_traded_price": 100.1,
        "total_buy_quantity": 5000,
        "total_sell_quantity": 4500,
        "oi": 0,
        "exchange_timestamp": now,
        "last_trade_time": now,
        "ohlc": {"open": 99.0, "high": 101.0, "low": 98.5, "close": 100.0},
        "depth": {
            "buy": [{"price": 100.45 - i * 0.05, "quantity": 100 + i, "orders": 2 + i} for i in range(DEPTH_LEVELS)],
            "sell": [{"price": 100.55 + i * 0.05, "quantity": 110 + i, "orders": 3 + i} for i in range(DEPTH_LEVELS)],
        },
    }


def run_l2_self_test(config: dict[str, Any]) -> None:
    if not parquet_available():
        raise RuntimeError("pyarrow is required for l2-self-test. Install requirements.txt.")
    tmp = Path(tempfile.mkdtemp(prefix="l2_self_test_"))
    try:
        local_config = dict(config)
        local_config["output_dir"] = str(tmp)
        instrument = ResolvedInstrument("TEST", "NSE", "TEST", 12345, "", "TEST")
        collector = L2DepthCollector(local_config, [instrument])
        ticks = [sample_depth_tick(12345) for _ in range(3)]
        collector.on_ticks(None, ticks)
        collector.flush("self_test")
        collector.heartbeat.maybe_write(
            connected=True,
            subscribed_count=1,
            ticks_since_start=collector.ticks_since_start,
            last_tick_utc=collector.last_tick_utc,
            buffered_rows=len(collector.writer.buffer),
        )
        audit = run_l2_audit(local_config)
        if audit.empty or int(audit["tick_count"].sum()) != 3:
            raise RuntimeError("l2-self-test failed: expected 3 written ticks.")
        hardkill = run_l2_verify_hardkill(local_config, mark_hardkill_tested=True)
        if not hardkill.get("hardkill_verified"):
            raise RuntimeError("l2-self-test failed: hardkill readability verification did not pass.")
        cap_config = {"plan": {"max_symbols_before_interim_gate": 2}, "_allow_symbol_cap_override": False}
        cap_table = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC"]})
        try:
            enforce_symbol_cap(cap_config, cap_table)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("l2-self-test failed: symbol cap did not reject oversized universe.")
        cap_config["_allow_symbol_cap_override"] = True
        enforce_symbol_cap(cap_config, cap_table)
        print("[l2-self-test] passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
