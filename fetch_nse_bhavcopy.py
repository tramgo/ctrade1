from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EQUITY_RAW_DIR = DATA_DIR / "nse_equity_bhavcopy"
FNO_RAW_DIR = DATA_DIR / "nse_fno_bhavcopy"
DELIVERY_MASTER_CSV = DATA_DIR / "nse_delivery_bhavcopy.csv"
FNO_MASTER_CSV = DATA_DIR / "nse_fno_bhavcopy_oi.csv"

NSE_HOME_URL = "https://www.nseindia.com"
EQUITY_URL_TEMPLATES = [
    "https://archives.nseindia.com/products/content/sec_bhavdata_full_{day_month_year_numeric}.csv",
    "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{day_month_year_numeric}.csv",
]
FNO_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{year}/{month}/"
    "fo{day_month_year}bhav.csv.zip"
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_HOME_URL,
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "DNT": "1",
}

REQUEST_TIMEOUT_SECONDS = 30
BOOTSTRAP_URLS = [
    "https://www.nseindia.com/",
    "https://www.nseindia.com/all-reports",
    "https://nsearchives.nseindia.com/",
]


@dataclass
class DownloadResult:
    trade_date: date
    dataset: str
    status: str
    path: Optional[Path] = None
    message: str = ""


@dataclass
class MasterStats:
    rows: int
    symbols: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download NSE equity/F&O bhavcopy archives, cache the daily files, "
            "and build merged delivery/OI master CSVs."
        )
    )
    parser.add_argument("--start-date", default="2015-01-01", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument(
        "--end-date",
        default=date.today().isoformat(),
        help="Inclusive end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Sleep between download attempts to avoid hammering NSE.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Maximum retries per file download.",
    )
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="Do not hit the network; rebuild the two master CSVs from existing cached archives only.",
    )
    parser.add_argument(
        "--skip-equity",
        action="store_true",
        help="Skip downloading/parsing equity bhavcopy archives.",
    )
    parser.add_argument(
        "--skip-fno",
        action="store_true",
        help="Skip downloading/parsing F&O bhavcopy archives.",
    )
    parser.add_argument(
        "--force-equity-delivery-backfill",
        action="store_true",
        help=(
            "Even when a legacy local cm... price bhavcopy exists for a date, still try to "
            "download the delivery-style sec_bhavdata_full file from NSE."
        ),
    )
    return parser.parse_args()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EQUITY_RAW_DIR.mkdir(parents=True, exist_ok=True)
    FNO_RAW_DIR.mkdir(parents=True, exist_ok=True)


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_weekdays(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def build_equity_urls(trade_date: date) -> list[str]:
    return [
        template.format(day_month_year_numeric=trade_date.strftime("%d%m%Y"))
        for template in EQUITY_URL_TEMPLATES
    ]


def build_fno_url(trade_date: date) -> str:
    return FNO_URL_TEMPLATE.format(
        year=trade_date.strftime("%Y"),
        month=trade_date.strftime("%b").upper(),
        day_month_year=trade_date.strftime("%d%b%Y").upper(),
    )


def bootstrap_session(session: requests.Session, quiet: bool = False) -> tuple[bool, str]:
    session.headers.update(DEFAULT_HEADERS)
    last_error = ""
    for url in BOOTSTRAP_URLS:
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code < 400:
                return (True, f"bootstrapped via {url}")
            last_error = f"{url} -> HTTP {response.status_code}"
        except Exception as exc:
            last_error = f"{url} -> {exc}"
    if not quiet:
        print(f"[BOOTSTRAP] continuing without NSE cookie warmup: {last_error}", flush=True)
    return (False, last_error)


def download_text_file(
    session: requests.Session,
    urls: list[str],
    out_path: Path,
    sleep_seconds: float,
    max_retries: int,
) -> tuple[str, str]:
    if out_path.exists():
        return ("cached", "file already present")

    last_message = "no attempt made"
    for url in urls:
        for attempt in range(1, max_retries + 1):
            try:
                response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.status_code == 404:
                    last_message = f"{url} -> not found"
                    break
                if response.status_code in {401, 403}:
                    ok, bootstrap_msg = bootstrap_session(session, quiet=True)
                    if attempt >= max_retries:
                        last_message = f"{url} -> HTTP {response.status_code}; bootstrap={bootstrap_msg}"
                        break
                    time.sleep(max(0.5, sleep_seconds * attempt))
                    continue
                response.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(response.content)
                return ("downloaded", f"ok via {url}")
            except Exception as exc:
                last_message = f"{url} -> {exc}"
                if attempt >= max_retries:
                    break
                time.sleep(max(0.5, sleep_seconds * attempt))
    if "not found" in last_message.lower():
        return ("not_found", last_message)
    return ("error", last_message)


def download_file(
    session: requests.Session,
    url: str,
    out_path: Path,
    sleep_seconds: float,
    max_retries: int,
) -> tuple[str, str]:
    if out_path.exists():
        return ("cached", "archive already present")

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 404:
                return ("not_found", "archive not published for this date")
            if response.status_code in {401, 403}:
                ok, bootstrap_msg = bootstrap_session(session, quiet=True)
                if attempt >= max_retries:
                    return ("error", f"HTTP {response.status_code}; bootstrap={bootstrap_msg}")
                time.sleep(max(0.5, sleep_seconds * attempt))
                continue
            response.raise_for_status()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(response.content)
            return ("downloaded", "ok")
        except Exception as exc:
            if attempt >= max_retries:
                return ("error", str(exc))
            time.sleep(max(0.5, sleep_seconds * attempt))
    return ("error", "retry loop exhausted")


def load_csv_from_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not members:
            raise ValueError(f"No CSV found inside archive: {zip_path}")
        with zf.open(members[0]) as handle:
            content = handle.read()
    try:
        return pd.read_csv(io.BytesIO(content))
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(content), encoding="latin-1")


def load_csv_from_file(file_path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(file_path)
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding="latin-1")


def normalize_equity_bhavcopy(df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    df = df.rename(columns=lambda col: str(col).strip())
    upper_cols = {col.upper(): col for col in df.columns}

    def pick(*names: str) -> Optional[str]:
        for name in names:
            if name.upper() in upper_cols:
                return upper_cols[name.upper()]
        return None

    symbol_col = pick("SYMBOL")
    total_qty_col = pick("TTL_TRD_QNTY", "TOTTRDQTY", "TOTTRD_QTY", "TOTTRDVAL", "TURNOVER_LACS")
    delivery_qty_col = pick("DELIV_QTY", "DELIV_QTY ", "DELIV_QTY", "DELIVERABLE_QTY")
    delivery_pct_col = pick("DELIV_PER", "DELIV_PER ", "DELIV_PERCENT", "DELIV_PER(% )")

    required = [symbol_col, total_qty_col, delivery_qty_col, delivery_pct_col]
    if any(col is None for col in required):
        raise ValueError(f"Unexpected equity bhavcopy schema columns={list(df.columns)}")

    out = pd.DataFrame(
        {
            "date": pd.Timestamp(trade_date),
            "symbol": df[symbol_col].astype(str).str.strip().str.upper(),
            "total_qty": pd.to_numeric(df[total_qty_col], errors="coerce"),
            "deliv_qty": pd.to_numeric(df[delivery_qty_col], errors="coerce"),
            "deliv_pct": pd.to_numeric(df[delivery_pct_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["symbol"])
    out = out.loc[out["symbol"] != ""].copy()
    return out.reset_index(drop=True)


def normalize_fno_bhavcopy(df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    df = df.rename(columns=lambda col: str(col).strip())
    upper_cols = {col.upper(): col for col in df.columns}

    def pick(*names: str) -> Optional[str]:
        for name in names:
            if name.upper() in upper_cols:
                return upper_cols[name.upper()]
        return None

    instrument_col = pick("INSTRUMENT")
    symbol_col = pick("SYMBOL")
    expiry_col = pick("EXPIRY_DT", "EXPIRY")
    oi_col = pick("OPEN_INT", "OPENINTEREST", "OPENINTEREST ")
    chg_oi_col = pick("CHG_IN_OI", "CHANGEINOI", "CHANGE_IN_OI")

    required = [instrument_col, symbol_col, expiry_col, oi_col, chg_oi_col]
    if any(col is None for col in required):
        raise ValueError(f"Unexpected F&O bhavcopy schema columns={list(df.columns)}")

    out = pd.DataFrame(
        {
            "date": pd.Timestamp(trade_date),
            "instrument": df[instrument_col].astype(str).str.strip().str.upper(),
            "symbol": df[symbol_col].astype(str).str.strip().str.upper(),
            "expiry": pd.to_datetime(df[expiry_col], errors="coerce"),
            "oi": pd.to_numeric(df[oi_col], errors="coerce"),
            "chg_in_oi": pd.to_numeric(df[chg_oi_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["symbol"])
    out = out.loc[out["symbol"] != ""].copy()
    return out.reset_index(drop=True)


def scan_equity_cache() -> MasterStats:
    csv_paths = sorted(EQUITY_RAW_DIR.rglob("sec_bhavdata_full_*.csv"))
    if not csv_paths:
        print(
            "[EQUITY] no delivery-style sec_bhavdata_full_*.csv files found in cache; "
            "older cm...bhav price archives are ignored by design",
            flush=True,
        )
        return MasterStats(rows=0, symbols=0)

    wrote_any = False
    row_count = 0
    symbols_seen: set[str] = set()

    for csv_path in csv_paths:
        trade_date = infer_trade_date_from_name(csv_path.name, prefix="sec_bhavdata_full_", suffix=".csv", fmt="%d%m%Y")
        if trade_date is None:
            continue
        try:
            df = normalize_equity_bhavcopy(load_csv_from_file(csv_path), trade_date)
            if df.empty:
                continue
            write_mode = "w" if not wrote_any else "a"
            df.to_csv(DELIVERY_MASTER_CSV, mode=write_mode, index=False, header=not wrote_any)
            wrote_any = True
            row_count += len(df)
            symbols_seen.update(df["symbol"].dropna().astype(str).str.upper())
        except Exception as exc:
            print(f"[EQUITY] failed to parse {csv_path.name}: {exc}", flush=True)

    if not wrote_any:
        return MasterStats(rows=0, symbols=0)
    return MasterStats(rows=row_count, symbols=len(symbols_seen))


def scan_fno_cache() -> MasterStats:
    zip_paths = sorted(FNO_RAW_DIR.rglob("*.zip"))
    if not zip_paths:
        print("[FNO] no fo...bhav.csv.zip files found in cache", flush=True)
        return MasterStats(rows=0, symbols=0)

    wrote_any = False
    row_count = 0
    symbols_seen: set[str] = set()

    for zip_path in zip_paths:
        trade_date = infer_trade_date_from_name(zip_path.name, prefix="fo", suffix="bhav.csv.zip")
        if trade_date is None:
            continue
        try:
            df = normalize_fno_bhavcopy(load_csv_from_zip(zip_path), trade_date)
            if df.empty:
                continue
            write_mode = "w" if not wrote_any else "a"
            df.to_csv(FNO_MASTER_CSV, mode=write_mode, index=False, header=not wrote_any)
            wrote_any = True
            row_count += len(df)
            symbols_seen.update(df["symbol"].dropna().astype(str).str.upper())
        except Exception as exc:
            print(f"[FNO] failed to parse {zip_path.name}: {exc}", flush=True)

    if not wrote_any:
        return MasterStats(rows=0, symbols=0)
    return MasterStats(rows=row_count, symbols=len(symbols_seen))


def infer_trade_date_from_name(name: str, prefix: str, suffix: str, fmt: str = "%d%b%Y") -> Optional[date]:
    if not name.lower().startswith(prefix.lower()) or not name.lower().endswith(suffix.lower()):
        return None
    stem = name[len(prefix) : -len(suffix)]
    try:
        return datetime.strptime(stem.upper(), fmt).date()
    except ValueError:
        return None


def write_master_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def build_output_zip_path(base_dir: Path, trade_date: date, dataset: str) -> Path:
    if dataset == "equity":
        file_name = f"sec_bhavdata_full_{trade_date.strftime('%d%m%Y')}.csv"
    else:
        file_name = f"fo{trade_date.strftime('%d%b%Y').upper()}bhav.csv.zip"
    return base_dir / trade_date.strftime("%Y") / trade_date.strftime("%m") / file_name


def build_legacy_equity_price_path(trade_date: date) -> Path:
    file_name = f"cm{trade_date.strftime('%d%b%Y').upper()}bhav.csv.zip"
    return EQUITY_RAW_DIR / trade_date.strftime("%Y") / trade_date.strftime("%m") / file_name


def run_downloads(args: argparse.Namespace) -> list[DownloadResult]:
    results: list[DownloadResult] = []
    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    if start_date > end_date:
        raise ValueError("start-date must be <= end-date")

    session = requests.Session()
    if not args.rebuild_only:
        bootstrap_session(session)

    for trade_date in iter_weekdays(start_date, end_date):
        if not args.skip_equity:
            urls = build_equity_urls(trade_date)
            out_path = build_output_zip_path(EQUITY_RAW_DIR, trade_date, dataset="equity")
            legacy_equity_path = build_legacy_equity_price_path(trade_date)
            if args.rebuild_only:
                status, message = ("skipped", "rebuild-only mode")
            elif out_path.exists():
                status, message = ("cached", "delivery file already present")
            elif legacy_equity_path.exists() and not args.force_equity_delivery_backfill:
                status, message = (
                    "legacy_cached",
                    "legacy cm price bhavcopy already cached locally; skipping delivery backfill for this date",
                )
            else:
                status, message = download_text_file(session, urls, out_path, args.sleep_seconds, args.max_retries)
                time.sleep(max(0.0, args.sleep_seconds))
            results.append(
                DownloadResult(trade_date=trade_date, dataset="equity", status=status, path=out_path, message=message)
            )
            print(f"[EQUITY] {trade_date} {status} {message}", flush=True)

        if not args.skip_fno:
            url = build_fno_url(trade_date)
            out_path = build_output_zip_path(FNO_RAW_DIR, trade_date, dataset="fno")
            if args.rebuild_only:
                status, message = ("skipped", "rebuild-only mode")
            else:
                status, message = download_file(session, url, out_path, args.sleep_seconds, args.max_retries)
                time.sleep(max(0.0, args.sleep_seconds))
            results.append(
                DownloadResult(trade_date=trade_date, dataset="fno", status=status, path=out_path, message=message)
            )
            print(f"[FNO] {trade_date} {status} {message}", flush=True)

    return results


def main() -> int:
    args = parse_args()
    ensure_dirs()

    try:
        run_downloads(args)
    except KeyboardInterrupt:
        print("Interrupted by user.", flush=True)
        return 130
    except Exception as exc:
        print(f"Download phase failed: {exc}", flush=True)
        return 1

    try:
        if not args.skip_equity:
            equity_stats = scan_equity_cache()
            print(
                f"[EQUITY] master saved: {DELIVERY_MASTER_CSV} rows={equity_stats.rows} "
                f"symbols={equity_stats.symbols}",
                flush=True,
            )
        if not args.skip_fno:
            fno_stats = scan_fno_cache()
            print(
                f"[FNO] master saved: {FNO_MASTER_CSV} rows={fno_stats.rows} "
                f"symbols={fno_stats.symbols}",
                flush=True,
            )
    except Exception as exc:
        print(f"Master build failed: {exc}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
