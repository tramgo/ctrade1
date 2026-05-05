from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_delivery_feature_frame(
    delivery_csv: str | Path,
    min_5d_ma: float = 0.0,
) -> pd.DataFrame:
    path = Path(delivery_csv)
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "deliv_pct",
                "deliv_pct_5d_ma",
                "deliv_pct_20d_ma",
                "deliv_pct_zscore_20d",
                "deliv_rising",
                "deliv_rising_above_floor",
                "deliv_rising_and_zpos",
            ]
        )

    df = pd.read_csv(path)
    rename_map = {}
    for col in df.columns:
        lower = str(col).strip().lower()
        if lower == "date":
            rename_map[col] = "date"
        elif lower in {"symbol", "ticker"}:
            rename_map[col] = "symbol"
        elif lower in {"deliv_pct", "deliverypct", "delivery_pct"}:
            rename_map[col] = "deliv_pct"
    df = df.rename(columns=rename_map)
    required = {"date", "symbol", "deliv_pct"}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        raise ValueError(f"Delivery feature input missing columns: {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["deliv_pct"] = pd.to_numeric(df["deliv_pct"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "deliv_pct"]).copy()
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    grp = df.groupby("symbol", sort=False)
    df["deliv_pct_5d_ma_raw"] = grp["deliv_pct"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    df["deliv_pct_20d_ma_raw"] = grp["deliv_pct"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["deliv_pct_20d_std_raw"] = grp["deliv_pct"].transform(lambda s: s.rolling(20, min_periods=10).std())
    df["deliv_pct_zscore_20d_raw"] = (
        (df["deliv_pct"] - df["deliv_pct_20d_ma_raw"]) / df["deliv_pct_20d_std_raw"].replace(0.0, np.nan)
    )

    # Shift one full daily observation so intraday trading on TradeDate t only sees delivery
    # information finalized on prior dates.
    for raw_col, out_col in [
        ("deliv_pct", "deliv_pct"),
        ("deliv_pct_5d_ma_raw", "deliv_pct_5d_ma"),
        ("deliv_pct_20d_ma_raw", "deliv_pct_20d_ma"),
        ("deliv_pct_zscore_20d_raw", "deliv_pct_zscore_20d"),
    ]:
        df[out_col] = grp[raw_col].shift(1)

    df["deliv_rising"] = (df["deliv_pct_5d_ma"] > df["deliv_pct_20d_ma"]).fillna(False)
    df["deliv_rising_above_floor"] = (
        df["deliv_rising"] & (pd.to_numeric(df["deliv_pct_5d_ma"], errors="coerce") >= float(min_5d_ma))
    ).fillna(False)
    df["deliv_rising_and_zpos"] = (
        df["deliv_rising"] & (pd.to_numeric(df["deliv_pct_zscore_20d"], errors="coerce") > 0.0)
    ).fillna(False)

    out_cols = [
        "symbol",
        "date",
        "deliv_pct",
        "deliv_pct_5d_ma",
        "deliv_pct_20d_ma",
        "deliv_pct_zscore_20d",
        "deliv_rising",
        "deliv_rising_above_floor",
        "deliv_rising_and_zpos",
    ]
    out = df[out_cols].rename(columns={"symbol": "Ticker", "date": "TradeDate"})
    out["Ticker"] = out["Ticker"].astype(str).str.upper()
    out["TradeDate"] = pd.to_datetime(out["TradeDate"], errors="coerce").dt.normalize()
    return out.reset_index(drop=True)


def load_oi_feature_frame(
    oi_csv: str | Path,
    tickers: list[str] | set[str],
    chunksize: int = 250_000,
) -> pd.DataFrame:
    path = Path(oi_csv)
    normalized_tickers = {str(t).strip().upper() for t in tickers if str(t).strip()}
    if not path.exists() or not normalized_tickers:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "oi",
                "chg_in_oi",
                "oi_change_5d_sum",
                "oi_change_20d_sum",
                "oi_rising",
                "oi_rising_and_pos",
            ]
        )

    frames: list[pd.DataFrame] = []
    usecols = ["date", "instrument", "symbol", "expiry", "oi", "chg_in_oi"]
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=chunksize):
        chunk["symbol"] = chunk["symbol"].astype(str).str.strip().str.upper()
        chunk = chunk.loc[chunk["symbol"].isin(normalized_tickers)].copy()
        if chunk.empty:
            continue
        chunk["instrument"] = chunk["instrument"].astype(str).str.strip().str.upper()
        chunk = chunk.loc[chunk["instrument"].isin({"FUTSTK", "FUTIDX"})].copy()
        if chunk.empty:
            continue
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        chunk["expiry"] = pd.to_datetime(chunk["expiry"], errors="coerce").dt.normalize()
        chunk["oi"] = pd.to_numeric(chunk["oi"], errors="coerce")
        chunk["chg_in_oi"] = pd.to_numeric(chunk["chg_in_oi"], errors="coerce")
        chunk = chunk.dropna(subset=["date", "symbol", "expiry", "oi", "chg_in_oi"]).copy()
        if not chunk.empty:
            frames.append(chunk)

    if not frames:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "oi",
                "chg_in_oi",
                "oi_change_5d_sum",
                "oi_change_20d_sum",
                "oi_rising",
                "oi_rising_and_pos",
            ]
        )

    df = pd.concat(frames, ignore_index=True)
    df["days_to_expiry"] = (df["expiry"] - df["date"]).dt.days
    valid = df.loc[df["days_to_expiry"] >= 0].copy()
    source = valid if not valid.empty else df.copy()
    source = source.sort_values(["symbol", "date", "days_to_expiry", "expiry"]).reset_index(drop=True)
    nearest = source.groupby(["symbol", "date"], as_index=False).first()
    nearest = nearest.sort_values(["symbol", "date"]).reset_index(drop=True)

    grp = nearest.groupby("symbol", sort=False)
    nearest["oi_change_5d_sum_raw"] = grp["chg_in_oi"].transform(lambda s: s.rolling(5, min_periods=3).sum())
    nearest["oi_change_20d_sum_raw"] = grp["chg_in_oi"].transform(lambda s: s.rolling(20, min_periods=10).sum())

    # One-day lag so intraday rows on TradeDate t only see prior completed bhavcopy info.
    nearest["oi"] = grp["oi"].shift(1)
    nearest["chg_in_oi"] = grp["chg_in_oi"].shift(1)
    nearest["oi_change_5d_sum"] = grp["oi_change_5d_sum_raw"].shift(1)
    nearest["oi_change_20d_sum"] = grp["oi_change_20d_sum_raw"].shift(1)
    nearest["oi_rising"] = (nearest["oi_change_5d_sum"] > 0.0).fillna(False)
    nearest["oi_rising_and_pos"] = (
        (nearest["oi_change_5d_sum"] > 0.0) & (nearest["chg_in_oi"] > 0.0)
    ).fillna(False)

    out = nearest[
        ["symbol", "date", "oi", "chg_in_oi", "oi_change_5d_sum", "oi_change_20d_sum", "oi_rising", "oi_rising_and_pos"]
    ].rename(columns={"symbol": "Ticker", "date": "TradeDate"})
    out["Ticker"] = out["Ticker"].astype(str).str.upper()
    out["TradeDate"] = pd.to_datetime(out["TradeDate"], errors="coerce").dt.normalize()
    return out.reset_index(drop=True)


def load_earnings_feature_frame(
    earnings_csv: str | Path,
    pre_event_days_wide: int = 5,
    pre_event_days_narrow: int = 2,
    post_event_days: int = 1,
) -> pd.DataFrame:
    path = Path(earnings_csv)
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "earnings_event_day",
                "earnings_near_2d",
                "earnings_near_5d",
                "earnings_clear_2d",
                "earnings_clear_5d",
            ]
        )

    df = pd.read_csv(path)
    rename_map = {}
    for col in df.columns:
        lower = str(col).strip().lower()
        if lower == "date":
            rename_map[col] = "date"
        elif lower in {"ticker", "symbol"}:
            rename_map[col] = "symbol"
        elif lower in {"eventdate", "event_date", "announcement_date"}:
            rename_map[col] = "event_date"
    df = df.rename(columns=rename_map)
    required = {"symbol", "event_date"}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        raise ValueError(f"Earnings feature input missing columns: {missing}")

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["symbol", "event_date"]).copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "earnings_event_day",
                "earnings_near_2d",
                "earnings_near_5d",
                "earnings_clear_2d",
                "earnings_clear_5d",
            ]
        )

    window_rows: list[dict] = []
    min_offset = -abs(int(pre_event_days_wide))
    max_offset = abs(int(post_event_days))
    for _, row in df.iterrows():
        symbol = str(row["symbol"]).strip().upper()
        event_date = pd.Timestamp(row["event_date"]).normalize()
        for offset in range(min_offset, max_offset + 1):
            trade_date = event_date + pd.Timedelta(days=int(offset))
            abs_offset = abs(int(offset))
            window_rows.append(
                {
                    "Ticker": symbol,
                    "TradeDate": trade_date,
                    "earnings_event_day": bool(offset == 0),
                    "earnings_near_2d": bool(abs_offset <= abs(int(pre_event_days_narrow))),
                    "earnings_near_5d": bool(abs_offset <= abs(int(pre_event_days_wide))),
                }
            )

    out = pd.DataFrame(window_rows)
    if out.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "TradeDate",
                "earnings_event_day",
                "earnings_near_2d",
                "earnings_near_5d",
                "earnings_clear_2d",
                "earnings_clear_5d",
            ]
        )
    out["TradeDate"] = pd.to_datetime(out["TradeDate"], errors="coerce").dt.normalize()
    out = (
        out.groupby(["Ticker", "TradeDate"], as_index=False)
        .agg(
            earnings_event_day=("earnings_event_day", "max"),
            earnings_near_2d=("earnings_near_2d", "max"),
            earnings_near_5d=("earnings_near_5d", "max"),
        )
        .sort_values(["Ticker", "TradeDate"])
        .reset_index(drop=True)
    )
    out["earnings_clear_2d"] = ~out["earnings_near_2d"].fillna(False)
    out["earnings_clear_5d"] = ~out["earnings_near_5d"].fillna(False)
    return out


def load_breadth_feature_frame(
    breadth_csv: str | Path,
) -> pd.DataFrame:
    path = Path(breadth_csv)
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "TradeDate",
                "breadth_adv_frac",
                "breadth_5d_ma",
                "breadth_20d_ma",
                "breadth_zscore_20d",
                "breadth_universe_count",
                "breadth_trend_up",
                "breadth_strong",
                "breadth_expanding",
            ]
        )

    df = pd.read_csv(path)
    rename_map = {}
    for col in df.columns:
        lower = str(col).strip().lower()
        if lower == "date":
            rename_map[col] = "date"
        elif lower in {"ticker", "symbol"}:
            rename_map[col] = "symbol"
        elif lower == "close":
            rename_map[col] = "close"
    df = df.rename(columns=rename_map)
    required = {"date", "symbol", "close"}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        raise ValueError(f"Breadth feature input missing columns: {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"]).copy()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "TradeDate",
                "breadth_adv_frac",
                "breadth_5d_ma",
                "breadth_20d_ma",
                "breadth_zscore_20d",
                "breadth_universe_count",
                "breadth_trend_up",
                "breadth_strong",
                "breadth_expanding",
            ]
        )

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    grp = df.groupby("symbol", sort=False)
    df["ret_1d"] = grp["close"].pct_change()
    daily = (
        df.groupby("date", as_index=False)
        .agg(
            breadth_adv_frac=("ret_1d", lambda s: float(np.mean(pd.to_numeric(s, errors="coerce") > 0.0))),
            breadth_universe_count=("symbol", "nunique"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily["breadth_5d_ma_raw"] = daily["breadth_adv_frac"].rolling(5, min_periods=3).mean()
    daily["breadth_20d_ma_raw"] = daily["breadth_adv_frac"].rolling(20, min_periods=10).mean()
    daily["breadth_20d_std_raw"] = daily["breadth_adv_frac"].rolling(20, min_periods=10).std()
    daily["breadth_zscore_20d_raw"] = (
        (daily["breadth_adv_frac"] - daily["breadth_20d_ma_raw"]) / daily["breadth_20d_std_raw"].replace(0.0, np.nan)
    )

    out = pd.DataFrame(
        {
            "TradeDate": daily["date"],
            "breadth_adv_frac": daily["breadth_adv_frac"].shift(1),
            "breadth_5d_ma": daily["breadth_5d_ma_raw"].shift(1),
            "breadth_20d_ma": daily["breadth_20d_ma_raw"].shift(1),
            "breadth_zscore_20d": daily["breadth_zscore_20d_raw"].shift(1),
            "breadth_universe_count": daily["breadth_universe_count"].shift(1),
        }
    )
    out["breadth_trend_up"] = (out["breadth_5d_ma"] > out["breadth_20d_ma"]).fillna(False)
    out["breadth_strong"] = (
        out["breadth_trend_up"] & (pd.to_numeric(out["breadth_5d_ma"], errors="coerce") >= 0.55)
    ).fillna(False)
    out["breadth_expanding"] = (
        out["breadth_trend_up"] & (pd.to_numeric(out["breadth_zscore_20d"], errors="coerce") > 0.0)
    ).fillna(False)
    return out.reset_index(drop=True)
