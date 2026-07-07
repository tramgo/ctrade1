from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .auth import kite_call_with_retry


REQUIRED_COLUMNS = {
    "instrument_token",
    "tradingsymbol",
    "exchange",
    "segment",
    "instrument_type",
}


@dataclass(frozen=True)
class ResolvedInstrument:
    requested_symbol: str
    exchange: str
    tradingsymbol: str
    instrument_token: int
    isin: str = ""
    name: str = ""

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.tradingsymbol}"


def load_symbols(path: Path) -> list[str]:
    df = load_symbol_table(path)
    return df["symbol"].tolist()


def load_symbol_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "symbol" not in df.columns:
        raise RuntimeError(f"{path} must contain a 'symbol' column.")
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out = out.loc[out["symbol"].ne("")].copy()
    if "zerodha_symbol" not in out.columns:
        out["zerodha_symbol"] = out["symbol"]
    out["zerodha_symbol"] = out["zerodha_symbol"].fillna(out["symbol"]).astype(str).str.strip().str.upper()
    out.loc[out["zerodha_symbol"].isin(["", "NAN", "NONE"]), "zerodha_symbol"] = out["symbol"]
    out = out.drop_duplicates("symbol", keep="first").reset_index(drop=True)
    return out


def load_instruments(kite, exchanges: Iterable[str]) -> pd.DataFrame:
    frames = []
    for exchange in exchanges:
        rows = kite_call_with_retry(kite.instruments, str(exchange).upper())
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frames.append(frame)
    if not frames:
        raise RuntimeError("No instrument rows returned from Zerodha.")

    out = pd.concat(frames, ignore_index=True)
    missing = REQUIRED_COLUMNS - set(out.columns)
    if missing:
        raise RuntimeError(f"Zerodha instrument dump missing columns: {sorted(missing)}")
    out["exchange"] = out["exchange"].astype(str).str.upper()
    out["tradingsymbol"] = out["tradingsymbol"].astype(str).str.upper()
    out["segment"] = out["segment"].astype(str).str.upper()
    out["instrument_type"] = out["instrument_type"].astype(str).str.upper()
    if "isin" not in out.columns:
        out["isin"] = ""
    if "name" not in out.columns:
        out["name"] = ""
    return out


def _cash_equity_rows(instruments: pd.DataFrame, exchange: str) -> pd.DataFrame:
    exchange = exchange.upper()
    df = instruments.loc[instruments["exchange"].eq(exchange)].copy()
    return df.loc[
        df["instrument_type"].eq("EQ")
        | df["segment"].eq(exchange)
        | df["segment"].eq(f"{exchange}-EQ")
    ].copy()


def resolve_equities(
    instruments: pd.DataFrame,
    symbols: list[str],
    exchanges: Iterable[str],
    prefer_bse_by_isin: bool = True,
    symbol_aliases: dict[str, str] | None = None,
) -> tuple[list[ResolvedInstrument], pd.DataFrame]:
    resolved: list[ResolvedInstrument] = []
    unresolved = []
    nse_cash = _cash_equity_rows(instruments, "NSE")
    bse_cash = _cash_equity_rows(instruments, "BSE")
    aliases = {str(k).upper(): str(v).upper() for k, v in (symbol_aliases or {}).items()}

    for requested in symbols:
        lookup_symbol = aliases.get(str(requested).upper(), str(requested).upper())
        nse_match = nse_cash.loc[nse_cash["tradingsymbol"].eq(lookup_symbol)].head(1)
        nse_isin = ""
        if not nse_match.empty:
            nse_isin = str(nse_match.iloc[0].get("isin", "") or "").strip()

        for exchange in [str(x).upper() for x in exchanges]:
            cash = nse_cash if exchange == "NSE" else bse_cash if exchange == "BSE" else _cash_equity_rows(instruments, exchange)
            match = cash.loc[cash["tradingsymbol"].eq(lookup_symbol)].head(1)
            if exchange == "BSE" and prefer_bse_by_isin and nse_isin:
                isin_match = cash.loc[cash["isin"].astype(str).str.strip().eq(nse_isin)].head(1)
                if not isin_match.empty:
                    match = isin_match

            if match.empty:
                unresolved.append(
                    {
                        "requested_symbol": requested,
                        "lookup_symbol": lookup_symbol,
                        "exchange": exchange,
                        "reason": "cash_equity_not_found",
                        "nse_isin": nse_isin,
                    }
                )
                continue

            row = match.iloc[0]
            resolved.append(
                ResolvedInstrument(
                    requested_symbol=requested,
                    exchange=exchange,
                    tradingsymbol=str(row["tradingsymbol"]).upper(),
                    instrument_token=int(row["instrument_token"]),
                    isin=str(row.get("isin", "") or ""),
                    name=str(row.get("name", "") or ""),
                )
            )

    return resolved, pd.DataFrame(unresolved)
