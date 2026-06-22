from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import zipfile
from typing import Iterable, Optional

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252.0


@dataclass(frozen=True)
class OptionScanConfig:
    risk_free_rate: float = 0.06
    premium_haircut: float = 0.15
    cost_per_leg_points: float = 1.0
    strike_step: int = 50
    entry_trading_days_before_expiry: int = 5
    min_days_to_expiry: int = 3
    strangle_margin_fraction: float = 0.18
    condor_min_margin_fraction: float = 0.02


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def bs_call_premium(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European call premium."""
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)
    if S <= 0 or K <= 0:
        return 0.0
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K)
    vol_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    return max(0.0, S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2))


def bs_put_premium(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European put premium."""
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    sigma = float(sigma)
    if S <= 0 or K <= 0:
        return 0.0
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    vol_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_t
    d2 = d1 - vol_t
    return max(0.0, K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1))


def _round_strike(value: float, step: int, direction: str) -> float:
    if step <= 0:
        return float(value)
    value = float(value)
    if direction == "up":
        return float(math.ceil(value / step) * step)
    if direction == "down":
        return float(math.floor(value / step) * step)
    return float(round(value / step) * step)


def _first_existing_path(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def load_price_frame(paths: Iterable[Path], label: str) -> tuple[pd.DataFrame, Optional[Path], str]:
    path = _first_existing_path(paths)
    if path is None:
        return pd.DataFrame(columns=["Date", label]), None, "missing"
    df = pd.read_csv(path)
    date_col = next((c for c in df.columns if str(c).lower() in {"date", "datetime", "timestamp"}), None)
    close_col = next((c for c in df.columns if str(c).lower() in {"close", "last", "last_price"}), None)
    if date_col is None or close_col is None:
        return pd.DataFrame(columns=["Date", label]), path, "invalid_schema"
    out = pd.DataFrame(
        {
            "Date": pd.to_datetime(df[date_col], errors="coerce").dt.normalize(),
            label: pd.to_numeric(df[close_col], errors="coerce"),
        }
    ).dropna()
    out = out.sort_values("Date").drop_duplicates("Date", keep="last").reset_index(drop=True)
    return out, path, "ok" if not out.empty else "empty"


def build_weekly_cycles(
    spot_df: pd.DataFrame,
    entry_trading_days_before_expiry: int = 5,
    min_days_to_expiry: int = 3,
) -> pd.DataFrame:
    if spot_df.empty:
        return pd.DataFrame(columns=["entry_date", "expiry_date", "spot_entry", "spot_expiry"])
    df = spot_df[["Date", "Spot"]].dropna().sort_values("Date").reset_index(drop=True)
    week_key = df["Date"].dt.strftime("%G-%V")
    cycles = []
    for _, week_df in df.groupby(week_key, sort=True):
        before_or_on_thursday = week_df.loc[week_df["Date"].dt.weekday <= 3]
        expiry_row = (before_or_on_thursday if not before_or_on_thursday.empty else week_df).iloc[-1]
        expiry_idx = int(expiry_row.name)
        entry_idx = max(0, expiry_idx - int(entry_trading_days_before_expiry))
        if entry_idx >= expiry_idx:
            continue
        entry_row = df.iloc[entry_idx]
        days_to_expiry = int((expiry_row["Date"] - entry_row["Date"]).days)
        if days_to_expiry < int(min_days_to_expiry):
            continue
        cycles.append(
            {
                "entry_date": entry_row["Date"],
                "expiry_date": expiry_row["Date"],
                "spot_entry": float(entry_row["Spot"]),
                "spot_expiry": float(expiry_row["Spot"]),
                "calendar_days_to_expiry": days_to_expiry,
            }
        )
    return pd.DataFrame(cycles).drop_duplicates(["entry_date", "expiry_date"]).reset_index(drop=True)


def synth_strangle_pnl(
    spot_entry: float,
    spot_expiry: float,
    vix_entry: float,
    days_to_expiry: int,
    call_strike_offset: float,
    put_strike_offset: float,
    cost_per_leg_points: float,
    premium_haircut: float,
    risk_free_rate: float,
    strike_step: int,
    margin_fraction: float,
) -> dict:
    sigma = float(vix_entry) / 100.0 if float(vix_entry) > 1.0 else float(vix_entry)
    T = max(float(days_to_expiry) / 365.0, 1.0 / 365.0)
    call_strike = _round_strike(spot_entry * (1.0 + call_strike_offset), strike_step, "up")
    put_strike = _round_strike(spot_entry * (1.0 - put_strike_offset), strike_step, "down")
    call_premium = bs_call_premium(spot_entry, call_strike, T, risk_free_rate, sigma)
    put_premium = bs_put_premium(spot_entry, put_strike, T, risk_free_rate, sigma)
    gross_credit = call_premium + put_premium
    net_credit = gross_credit * (1.0 - premium_haircut)
    payoff = max(spot_expiry - call_strike, 0.0) + max(put_strike - spot_expiry, 0.0)
    total_cost = 2.0 * float(cost_per_leg_points)
    net_pnl = net_credit - payoff - total_cost
    margin = max(abs(float(spot_entry)) * float(margin_fraction), 1.0)
    return {
        "call_strike": call_strike,
        "put_strike": put_strike,
        "call_wing": np.nan,
        "put_wing": np.nan,
        "gross_credit": gross_credit,
        "net_credit": net_credit,
        "expiry_payoff": payoff,
        "total_cost_points": total_cost,
        "net_pnl_points": net_pnl,
        "margin_estimate_points": margin,
        "return_on_margin": net_pnl / margin,
    }


def synth_iron_condor_pnl(
    spot_entry: float,
    spot_expiry: float,
    vix_entry: float,
    days_to_expiry: int,
    short_call_offset: float,
    short_put_offset: float,
    wing_width_pct: float,
    cost_per_leg_points: float,
    premium_haircut: float,
    risk_free_rate: float,
    strike_step: int,
    min_margin_fraction: float,
) -> dict:
    sigma = float(vix_entry) / 100.0 if float(vix_entry) > 1.0 else float(vix_entry)
    T = max(float(days_to_expiry) / 365.0, 1.0 / 365.0)
    call_strike = _round_strike(spot_entry * (1.0 + short_call_offset), strike_step, "up")
    put_strike = _round_strike(spot_entry * (1.0 - short_put_offset), strike_step, "down")
    call_wing = _round_strike(call_strike + spot_entry * wing_width_pct, strike_step, "up")
    put_wing = _round_strike(put_strike - spot_entry * wing_width_pct, strike_step, "down")
    short_credit = (
        bs_call_premium(spot_entry, call_strike, T, risk_free_rate, sigma)
        + bs_put_premium(spot_entry, put_strike, T, risk_free_rate, sigma)
    )
    long_debit = (
        bs_call_premium(spot_entry, call_wing, T, risk_free_rate, sigma)
        + bs_put_premium(spot_entry, put_wing, T, risk_free_rate, sigma)
    )
    net_credit = short_credit * (1.0 - premium_haircut) - long_debit * (1.0 + premium_haircut)
    short_payoff = max(spot_expiry - call_strike, 0.0) + max(put_strike - spot_expiry, 0.0)
    long_payoff = max(spot_expiry - call_wing, 0.0) + max(put_wing - spot_expiry, 0.0)
    payoff = short_payoff - long_payoff
    total_cost = 4.0 * float(cost_per_leg_points)
    net_pnl = net_credit - payoff - total_cost
    max_width = max(call_wing - call_strike, put_strike - put_wing)
    margin = max(max_width - net_credit, abs(float(spot_entry)) * float(min_margin_fraction), 1.0)
    return {
        "call_strike": call_strike,
        "put_strike": put_strike,
        "call_wing": call_wing,
        "put_wing": put_wing,
        "gross_credit": short_credit - long_debit,
        "net_credit": net_credit,
        "expiry_payoff": payoff,
        "total_cost_points": total_cost,
        "net_pnl_points": net_pnl,
        "margin_estimate_points": margin,
        "return_on_margin": net_pnl / margin,
    }


def _max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    running_max = series.cummax()
    dd = series - running_max
    return float(dd.min())


def summarize_option_scan(detail_df: pd.DataFrame) -> pd.DataFrame:
    if detail_df.empty:
        return pd.DataFrame()
    rows = []
    for strategy, group in detail_df.groupby("strategy", dropna=False):
        equity = pd.to_numeric(group["net_pnl_points"], errors="coerce").fillna(0.0).cumsum()
        returns = pd.to_numeric(group["return_on_margin"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        trade_count = int(len(group))
        years = max(
            (pd.to_datetime(group["expiry_date"]).max() - pd.to_datetime(group["entry_date"]).min()).days / 365.25,
            trade_count / 52.0,
            1.0 / 52.0,
        )
        total_return_on_margin = float(returns.sum()) if not returns.empty else np.nan
        annualized_return_on_margin = (1.0 + total_return_on_margin) ** (1.0 / years) - 1.0 if total_return_on_margin > -0.999999 else np.nan
        rows.append(
            {
                "strategy": strategy,
                "trade_count": trade_count,
                "first_entry": pd.to_datetime(group["entry_date"]).min(),
                "last_expiry": pd.to_datetime(group["expiry_date"]).max(),
                "total_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").sum()),
                "mean_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").mean()),
                "median_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").median()),
                "worst_trade_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").min()),
                "win_rate": float((pd.to_numeric(group["net_pnl_points"], errors="coerce") > 0).mean()),
                "max_drawdown_points": _max_drawdown(equity),
                "mean_return_on_margin": float(returns.mean()) if not returns.empty else np.nan,
                "total_return_on_margin": total_return_on_margin,
                "annualized_return_on_margin": float(annualized_return_on_margin),
                "mean_vix": float(pd.to_numeric(group["vix_entry"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["annualized_return_on_margin", "max_drawdown_points"],
        ascending=[False, False],
    ).reset_index(drop=True)


def run_options_premium_scan(
    spot_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    config: OptionScanConfig = OptionScanConfig(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cycles = build_weekly_cycles(
        spot_df,
        entry_trading_days_before_expiry=config.entry_trading_days_before_expiry,
        min_days_to_expiry=config.min_days_to_expiry,
    )
    if cycles.empty or vix_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    vix = vix_df.sort_values("Date").copy()
    vix["vix_median_20"] = vix["VIX"].rolling(20, min_periods=10).median()
    vix["vix_change_1d"] = vix["VIX"].pct_change()
    merged = pd.merge_asof(
        cycles.sort_values("entry_date"),
        vix[["Date", "VIX", "vix_median_20", "vix_change_1d"]].sort_values("Date"),
        left_on="entry_date",
        right_on="Date",
        direction="backward",
    ).drop(columns=["Date"])
    merged = merged.dropna(subset=["VIX"]).reset_index(drop=True)

    variants = [
        ("TB10_T01_strangle_2pct", "strangle", {"call_offset": 0.02, "put_offset": 0.02}),
        ("TB10_T01_strangle_3pct", "strangle", {"call_offset": 0.03, "put_offset": 0.03}),
        ("TB10_T02_iron_condor_2pct_5pct_wing", "condor", {"call_offset": 0.02, "put_offset": 0.02, "wing_width_pct": 0.05}),
        ("TB10_T03_vix_gated_strangle_2pct", "strangle", {"call_offset": 0.02, "put_offset": 0.02, "require_vix_above_median": True}),
        ("TB10_T04_guardrail_vix_shock_strangle_2pct", "strangle", {"call_offset": 0.02, "put_offset": 0.02, "skip_vix_shock": True}),
    ]

    rows = []
    for _, row in merged.iterrows():
        for strategy, kind, params in variants:
            if params.get("require_vix_above_median") and not (row["VIX"] > row.get("vix_median_20", np.nan)):
                continue
            if params.get("skip_vix_shock") and row.get("vix_change_1d", 0.0) > 0.25:
                continue
            common = {
                "spot_entry": float(row["spot_entry"]),
                "spot_expiry": float(row["spot_expiry"]),
                "vix_entry": float(row["VIX"]),
                "days_to_expiry": int(row["calendar_days_to_expiry"]),
                "cost_per_leg_points": config.cost_per_leg_points,
                "premium_haircut": config.premium_haircut,
                "risk_free_rate": config.risk_free_rate,
                "strike_step": config.strike_step,
            }
            if kind == "strangle":
                result = synth_strangle_pnl(
                    call_strike_offset=float(params["call_offset"]),
                    put_strike_offset=float(params["put_offset"]),
                    margin_fraction=config.strangle_margin_fraction,
                    **common,
                )
            else:
                result = synth_iron_condor_pnl(
                    short_call_offset=float(params["call_offset"]),
                    short_put_offset=float(params["put_offset"]),
                    wing_width_pct=float(params["wing_width_pct"]),
                    min_margin_fraction=config.condor_min_margin_fraction,
                    **common,
                )
            rows.append(
                {
                    "strategy": strategy,
                    "entry_date": row["entry_date"],
                    "expiry_date": row["expiry_date"],
                    "calendar_days_to_expiry": int(row["calendar_days_to_expiry"]),
                    "spot_entry": float(row["spot_entry"]),
                    "spot_expiry": float(row["spot_expiry"]),
                    "vix_entry": float(row["VIX"]),
                    "vix_median_20": float(row["vix_median_20"]) if pd.notna(row.get("vix_median_20")) else np.nan,
                    "vix_change_1d": float(row["vix_change_1d"]) if pd.notna(row.get("vix_change_1d")) else np.nan,
                    **result,
                }
            )
    detail_df = pd.DataFrame(rows)
    summary_df = summarize_option_scan(detail_df)
    return detail_df, summary_df


def _parse_bhavcopy_date(path: Path) -> Optional[pd.Timestamp]:
    name = path.name.upper()
    if not name.startswith("FO") or "BHAV" not in name:
        return None
    date_text = name[2:name.index("BHAV")]
    return pd.to_datetime(date_text, format="%d%b%Y", errors="coerce")


def _read_nifty_options_bhavcopy(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if not names:
            return pd.DataFrame()
        df = pd.read_csv(
            zf.open(names[0]),
            usecols=lambda c: c
            in {
                "INSTRUMENT",
                "SYMBOL",
                "EXPIRY_DT",
                "STRIKE_PR",
                "OPTION_TYP",
                "CLOSE",
                "SETTLE_PR",
                "CONTRACTS",
                "OPEN_INT",
                "TIMESTAMP",
            },
        )
    df.columns = [str(c).strip().upper() for c in df.columns]
    if df.empty:
        return df
    df = df.loc[
        (df["INSTRUMENT"].astype(str).str.upper() == "OPTIDX")
        & (df["SYMBOL"].astype(str).str.upper() == "NIFTY")
    ].copy()
    if df.empty:
        return df
    df["TRADE_DATE"] = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y", errors="coerce").dt.normalize()
    df["EXPIRY_DATE"] = pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y", errors="coerce").dt.normalize()
    for col in ["STRIKE_PR", "CLOSE", "SETTLE_PR", "CONTRACTS", "OPEN_INT"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["OPTION_TYP"] = df["OPTION_TYP"].astype(str).str.upper().str.strip()
    return df.dropna(subset=["TRADE_DATE", "EXPIRY_DATE", "STRIKE_PR", "CLOSE"])


def _pick_leg(
    option_df: pd.DataFrame,
    option_type: str,
    target: float,
    direction: str,
    require_traded: bool,
) -> Optional[pd.Series]:
    leg_df = option_df.loc[option_df["OPTION_TYP"] == option_type].copy()
    if require_traded and "CONTRACTS" in leg_df.columns:
        leg_df = leg_df.loc[pd.to_numeric(leg_df["CONTRACTS"], errors="coerce").fillna(0) > 0]
    leg_df = leg_df.loc[pd.to_numeric(leg_df["CLOSE"], errors="coerce").fillna(0) > 0]
    if direction == "up":
        leg_df = leg_df.loc[leg_df["STRIKE_PR"] >= float(target)]
        leg_df = leg_df.sort_values("STRIKE_PR", ascending=True)
    elif direction == "down":
        leg_df = leg_df.loc[leg_df["STRIKE_PR"] <= float(target)]
        leg_df = leg_df.sort_values("STRIKE_PR", ascending=False)
    else:
        leg_df["distance"] = (leg_df["STRIKE_PR"] - float(target)).abs()
        leg_df = leg_df.sort_values("distance", ascending=True)
    if leg_df.empty:
        return None
    return leg_df.iloc[0]


def summarize_real_chain_condor(detail_df: pd.DataFrame) -> pd.DataFrame:
    if detail_df.empty:
        return pd.DataFrame()
    rows = []
    for strategy, group in detail_df.groupby("strategy", dropna=False):
        equity = pd.to_numeric(group["net_pnl_points"], errors="coerce").fillna(0.0).cumsum()
        returns = pd.to_numeric(group["return_on_margin"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        years = max(
            (pd.to_datetime(group["expiry_date"]).max() - pd.to_datetime(group["entry_date"]).min()).days / 365.25,
            len(group) / 52.0,
            1.0 / 52.0,
        )
        total_rom = float(returns.sum()) if not returns.empty else np.nan
        ann_rom = (1.0 + total_rom) ** (1.0 / years) - 1.0 if total_rom > -0.999999 else np.nan
        rows.append(
            {
                "strategy": strategy,
                "trade_count": int(len(group)),
                "first_entry": pd.to_datetime(group["entry_date"]).min(),
                "last_expiry": pd.to_datetime(group["expiry_date"]).max(),
                "total_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").sum()),
                "mean_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").mean()),
                "median_pnl_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").median()),
                "worst_trade_points": float(pd.to_numeric(group["net_pnl_points"], errors="coerce").min()),
                "win_rate": float((pd.to_numeric(group["net_pnl_points"], errors="coerce") > 0).mean()),
                "max_drawdown_points": _max_drawdown(equity),
                "mean_return_on_margin": float(returns.mean()) if not returns.empty else np.nan,
                "total_return_on_margin": total_rom,
                "annualized_return_on_margin": float(ann_rom),
                "mean_days_to_expiry": float(pd.to_numeric(group["days_to_expiry"], errors="coerce").mean()),
                "mean_total_contracts": float(pd.to_numeric(group["total_entry_contracts"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["annualized_return_on_margin", "worst_trade_points"],
        ascending=[False, False],
    ).reset_index(drop=True)


def run_real_chain_condor_scan(
    spot_df: pd.DataFrame,
    bhavcopy_root: Path,
    vix_df: Optional[pd.DataFrame] = None,
    variants: Optional[list[dict]] = None,
    short_call_offset: float = 0.02,
    short_put_offset: float = 0.02,
    wing_width_pct: float = 0.05,
    premium_haircut: float = 0.15,
    cost_per_leg_points: float = 1.0,
    min_days_to_expiry: int = 3,
    max_days_to_expiry: int = 10,
    require_traded: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    spot = spot_df[["Date", "Spot"]].dropna().copy()
    spot["Date"] = pd.to_datetime(spot["Date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    spot["Spot"] = pd.to_numeric(spot["Spot"], errors="coerce")
    spot = spot.dropna().sort_values("Date").drop_duplicates("Date", keep="last")
    spot["spot_ret_5d"] = spot["Spot"].pct_change(5)
    spot["spot_sma20"] = spot["Spot"].rolling(20, min_periods=10).mean()
    spot["spot_vs_sma20"] = spot["Spot"] / spot["spot_sma20"] - 1.0
    spot_by_date = dict(zip(spot["Date"], spot["Spot"]))
    spot_context_by_date = {
        row["Date"]: {
            "spot_ret_5d": float(row["spot_ret_5d"]) if pd.notna(row["spot_ret_5d"]) else np.nan,
            "spot_vs_sma20": float(row["spot_vs_sma20"]) if pd.notna(row["spot_vs_sma20"]) else np.nan,
        }
        for _, row in spot.iterrows()
    }

    vix_by_date: dict[pd.Timestamp, dict] = {}
    if vix_df is not None and not vix_df.empty:
        vix = vix_df[["Date", "VIX"]].dropna().copy()
        vix["Date"] = pd.to_datetime(vix["Date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
        vix["VIX"] = pd.to_numeric(vix["VIX"], errors="coerce")
        vix = vix.dropna().sort_values("Date").drop_duplicates("Date", keep="last")
        vix["vix_median_20"] = vix["VIX"].rolling(20, min_periods=10).median()
        vix["vix_p60_60"] = vix["VIX"].rolling(60, min_periods=20).quantile(0.60)
        vix["vix_change_1d"] = vix["VIX"].pct_change()
        vix_by_date = {
            row["Date"]: {
                "vix_entry": float(row["VIX"]),
                "vix_median_20": float(row["vix_median_20"]) if pd.notna(row["vix_median_20"]) else np.nan,
                "vix_p60_60": float(row["vix_p60_60"]) if pd.notna(row["vix_p60_60"]) else np.nan,
                "vix_change_1d": float(row["vix_change_1d"]) if pd.notna(row["vix_change_1d"]) else np.nan,
            }
            for _, row in vix.iterrows()
        }

    if variants is None:
        variants = [
            {
                "strategy": "TB10_T02_real_chain_iron_condor_2pct_5pct_wing",
                "short_call_offset": short_call_offset,
                "short_put_offset": short_put_offset,
                "wing_width_pct": wing_width_pct,
            }
        ]

    files = sorted(Path(bhavcopy_root).rglob("fo*bhav.csv.zip"))
    file_by_date = {date: path for path in files if (date := _parse_bhavcopy_date(path)) is not None}
    rows = []
    skips = []
    for entry_date in sorted(set(spot["Date"]).intersection(file_by_date.keys())):
        spot_entry = float(spot_by_date[entry_date])
        options = _read_nifty_options_bhavcopy(file_by_date[entry_date])
        if options.empty:
            skips.append({"entry_date": entry_date, "reason": "no_nifty_options"})
            continue
        expiries = sorted(
            exp
            for exp in options["EXPIRY_DATE"].dropna().unique()
            if min_days_to_expiry <= int((pd.Timestamp(exp) - entry_date).days) <= max_days_to_expiry
        )
        if not expiries:
            skips.append({"entry_date": entry_date, "reason": "no_weekly_expiry_in_window"})
            continue
        expiry_date = pd.Timestamp(expiries[0]).normalize()
        if expiry_date not in spot_by_date:
            skips.append({"entry_date": entry_date, "expiry_date": expiry_date, "reason": "missing_spot_expiry"})
            continue
        chain = options.loc[options["EXPIRY_DATE"] == expiry_date].copy()
        spot_expiry = float(spot_by_date[expiry_date])
        vix_context = vix_by_date.get(entry_date, {})
        spot_context = spot_context_by_date.get(entry_date, {})
        for variant in variants:
            strategy = str(variant.get("strategy", "real_chain_iron_condor"))
            days_to_expiry = int((expiry_date - entry_date).days)
            variant_min_dte = variant.get("min_days_to_expiry")
            if variant_min_dte is not None and days_to_expiry < int(variant_min_dte):
                continue
            variant_max_dte = variant.get("max_days_to_expiry")
            if variant_max_dte is not None and days_to_expiry > int(variant_max_dte):
                continue
            spot_ret_5d_min = variant.get("spot_ret_5d_min")
            if spot_ret_5d_min is not None and (
                not np.isfinite(spot_context.get("spot_ret_5d", np.nan))
                or spot_context["spot_ret_5d"] < float(spot_ret_5d_min)
            ):
                continue
            spot_vs_sma20_min = variant.get("spot_vs_sma20_min")
            if spot_vs_sma20_min is not None and (
                not np.isfinite(spot_context.get("spot_vs_sma20", np.nan))
                or spot_context["spot_vs_sma20"] < float(spot_vs_sma20_min)
            ):
                continue
            vix_max = variant.get("vix_max")
            if vix_max is not None and (not np.isfinite(vix_context.get("vix_entry", np.nan)) or vix_context["vix_entry"] > float(vix_max)):
                continue
            if variant.get("require_vix_below_p60"):
                if not (
                    np.isfinite(vix_context.get("vix_entry", np.nan))
                    and np.isfinite(vix_context.get("vix_p60_60", np.nan))
                    and vix_context["vix_entry"] <= vix_context["vix_p60_60"]
                ):
                    continue
            vix_change_max = variant.get("vix_change_max")
            if vix_change_max is not None and np.isfinite(vix_context.get("vix_change_1d", np.nan)):
                if vix_context["vix_change_1d"] > float(vix_change_max):
                    continue
            variant_call_offset = float(variant.get("short_call_offset", short_call_offset))
            variant_put_offset = float(variant.get("short_put_offset", short_put_offset))
            variant_wing_width = float(variant.get("wing_width_pct", wing_width_pct))
            variant_haircut = float(variant.get("premium_haircut", premium_haircut))
            variant_cost_per_leg = float(variant.get("cost_per_leg_points", cost_per_leg_points))
            short_call = _pick_leg(chain, "CE", spot_entry * (1.0 + variant_call_offset), "up", require_traded)
            short_put = _pick_leg(chain, "PE", spot_entry * (1.0 - variant_put_offset), "down", require_traded)
            if short_call is None or short_put is None:
                skips.append({"entry_date": entry_date, "expiry_date": expiry_date, "strategy": strategy, "reason": "missing_short_leg"})
                continue
            call_wing = _pick_leg(
                chain,
                "CE",
                float(short_call["STRIKE_PR"]) + spot_entry * variant_wing_width,
                "up",
                require_traded,
            )
            put_wing = _pick_leg(
                chain,
                "PE",
                float(short_put["STRIKE_PR"]) - spot_entry * variant_wing_width,
                "down",
                require_traded,
            )
            if call_wing is None or put_wing is None:
                skips.append({"entry_date": entry_date, "expiry_date": expiry_date, "strategy": strategy, "reason": "missing_wing_leg"})
                continue
            short_credit_raw = float(short_call["CLOSE"]) + float(short_put["CLOSE"])
            long_debit_raw = float(call_wing["CLOSE"]) + float(put_wing["CLOSE"])
            net_credit = short_credit_raw * (1.0 - variant_haircut) - long_debit_raw * (1.0 + variant_haircut)
            short_payoff = max(spot_expiry - float(short_call["STRIKE_PR"]), 0.0) + max(
                float(short_put["STRIKE_PR"]) - spot_expiry,
                0.0,
            )
            long_payoff = max(spot_expiry - float(call_wing["STRIKE_PR"]), 0.0) + max(
                float(put_wing["STRIKE_PR"]) - spot_expiry,
                0.0,
            )
            expiry_payoff = short_payoff - long_payoff
            total_cost = 4.0 * variant_cost_per_leg
            net_pnl = net_credit - expiry_payoff - total_cost
            width = max(
                float(call_wing["STRIKE_PR"]) - float(short_call["STRIKE_PR"]),
                float(short_put["STRIKE_PR"]) - float(put_wing["STRIKE_PR"]),
            )
            margin = max(width - net_credit, spot_entry * 0.02, 1.0)
            max_margin_points = variant.get("max_margin_points")
            if max_margin_points is not None and margin > float(max_margin_points):
                skips.append(
                    {
                        "entry_date": entry_date,
                        "expiry_date": expiry_date,
                        "strategy": strategy,
                        "reason": "margin_above_variant_cap",
                        "margin_estimate_points": margin,
                        "max_margin_points": float(max_margin_points),
                    }
                )
                continue
            min_total_contracts = variant.get("min_total_contracts")
            total_entry_contracts = (
                float(short_call.get("CONTRACTS", 0))
                + float(short_put.get("CONTRACTS", 0))
                + float(call_wing.get("CONTRACTS", 0))
                + float(put_wing.get("CONTRACTS", 0))
            )
            if min_total_contracts is not None and total_entry_contracts < float(min_total_contracts):
                skips.append(
                    {
                        "entry_date": entry_date,
                        "expiry_date": expiry_date,
                        "strategy": strategy,
                        "reason": "contracts_below_variant_floor",
                        "total_entry_contracts": total_entry_contracts,
                        "min_total_contracts": float(min_total_contracts),
                    }
                )
                continue
            rows.append(
                {
                    "strategy": strategy,
                    "entry_date": entry_date,
                    "expiry_date": expiry_date,
                    "days_to_expiry": days_to_expiry,
                    "spot_entry": spot_entry,
                    "spot_expiry": spot_expiry,
                    "vix_entry": vix_context.get("vix_entry", np.nan),
                    "vix_p60_60": vix_context.get("vix_p60_60", np.nan),
                    "vix_change_1d": vix_context.get("vix_change_1d", np.nan),
                    "spot_ret_5d": spot_context.get("spot_ret_5d", np.nan),
                    "spot_vs_sma20": spot_context.get("spot_vs_sma20", np.nan),
                    "short_call_offset": variant_call_offset,
                    "short_put_offset": variant_put_offset,
                    "wing_width_pct": variant_wing_width,
                    "premium_haircut": variant_haircut,
                    "cost_per_leg_points": variant_cost_per_leg,
                    "short_call_strike": float(short_call["STRIKE_PR"]),
                    "short_put_strike": float(short_put["STRIKE_PR"]),
                    "call_wing_strike": float(call_wing["STRIKE_PR"]),
                    "put_wing_strike": float(put_wing["STRIKE_PR"]),
                    "short_call_close": float(short_call["CLOSE"]),
                    "short_put_close": float(short_put["CLOSE"]),
                    "call_wing_close": float(call_wing["CLOSE"]),
                    "put_wing_close": float(put_wing["CLOSE"]),
                    "short_credit_raw": short_credit_raw,
                    "long_debit_raw": long_debit_raw,
                    "net_credit": net_credit,
                    "expiry_payoff": expiry_payoff,
                    "total_cost_points": total_cost,
                    "net_pnl_points": net_pnl,
                    "margin_estimate_points": margin,
                    "return_on_margin": net_pnl / margin,
                    "max_margin_points": float(max_margin_points) if max_margin_points is not None else np.nan,
                    "min_total_contracts": float(min_total_contracts) if min_total_contracts is not None else np.nan,
                    "total_entry_contracts": total_entry_contracts,
                    "total_entry_open_int": float(short_call.get("OPEN_INT", 0))
                    + float(short_put.get("OPEN_INT", 0))
                    + float(call_wing.get("OPEN_INT", 0))
                    + float(put_wing.get("OPEN_INT", 0)),
                }
            )
    detail_df = pd.DataFrame(rows)
    summary_df = summarize_real_chain_condor(detail_df)
    skip_df = pd.DataFrame(skips)
    return detail_df, summary_df, skip_df
