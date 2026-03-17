from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_roundtrip_cost(
    df: pd.DataFrame,
    base_cost_bps: float = 8.0,
    atr_cost_multiplier: float = 0.25,
) -> pd.Series:
    base = base_cost_bps / 10000.0
    atr_component = atr_cost_multiplier * np.exp(df["ATR20_log"].clip(-20, 5))
    cost = base + atr_component
    return pd.Series(cost, index=df.index).fillna(base)


def generate_forward_returns(
    df: pd.DataFrame,
    horizon: int,
    close_col: str = "Close",
    market_close_col: str | None = None,
) -> pd.DataFrame:
    out = df.copy()
    out[f"raw_fwd_ret_{horizon}"] = out[close_col].shift(-horizon) / out[close_col] - 1.0

    if market_close_col and market_close_col in out.columns:
        out[f"mkt_fwd_ret_{horizon}"] = (
            out[market_close_col].shift(-horizon) / out[market_close_col] - 1.0
        )
    else:
        out[f"mkt_fwd_ret_{horizon}"] = (
            out["MktRet_1"].rolling(horizon).sum().shift(-horizon + 1)
        )

    out[f"alpha_fwd_{horizon}"] = out[f"raw_fwd_ret_{horizon}"] - out[f"mkt_fwd_ret_{horizon}"]
    return out


def make_target_t1_cost_aware_return(
    df: pd.DataFrame,
    horizon: int,
    deadzone_bps: float = 0.0,
) -> pd.DataFrame:
    out = generate_forward_returns(df, horizon)
    out[f"est_cost_{horizon}"] = estimate_roundtrip_cost(out)
    out[f"net_fwd_ret_{horizon}"] = out[f"raw_fwd_ret_{horizon}"] - out[f"est_cost_{horizon}"]

    deadzone = deadzone_bps / 10000.0
    y_col = f"y_t1_dir_{horizon}"
    out[y_col] = 0
    out.loc[out[f"net_fwd_ret_{horizon}"] > deadzone, y_col] = 1
    out.loc[out[f"net_fwd_ret_{horizon}"] < -deadzone, y_col] = -1
    return out


def make_target_t2_alpha_return(
    df: pd.DataFrame,
    horizon: int,
    deadzone_bps: float = 0.0,
) -> pd.DataFrame:
    out = generate_forward_returns(df, horizon)
    out[f"est_cost_{horizon}"] = estimate_roundtrip_cost(out)
    out[f"net_alpha_fwd_{horizon}"] = out[f"alpha_fwd_{horizon}"] - out[f"est_cost_{horizon}"]

    deadzone = deadzone_bps / 10000.0
    y_col = f"y_t2_dir_{horizon}"
    out[y_col] = 0
    out.loc[out[f"net_alpha_fwd_{horizon}"] > deadzone, y_col] = 1
    out.loc[out[f"net_alpha_fwd_{horizon}"] < -deadzone, y_col] = -1
    return out


def make_target_t3_opportunity(
    df: pd.DataFrame,
    horizon: int,
    threshold_bps: float = 0.0,
) -> pd.DataFrame:
    out = generate_forward_returns(df, horizon)
    out[f"est_cost_{horizon}"] = estimate_roundtrip_cost(out)
    out[f"opp_score_{horizon}"] = out[f"raw_fwd_ret_{horizon}"].abs() - out[f"est_cost_{horizon}"]

    threshold = threshold_bps / 10000.0
    out[f"y_t3_opp_{horizon}"] = (out[f"opp_score_{horizon}"] > threshold).astype(int)
    return out


def make_target_t4_triple_barrier(
    df: pd.DataFrame,
    horizon: int,
    up_mult: float = 1.0,
    down_mult: float = 1.0,
) -> pd.DataFrame:
    out = df.copy()
    atr_frac = np.exp(out["ATR20_log"].clip(-20, 5)).fillna(0.0)
    labels = np.zeros(len(out), dtype=int)

    highs = out["High"].to_numpy()
    lows = out["Low"].to_numpy()
    closes = out["Close"].to_numpy()

    for i in range(len(out) - horizon):
        entry = closes[i]
        up_barrier = entry * (1.0 + up_mult * atr_frac.iloc[i])
        down_barrier = entry * (1.0 - down_mult * atr_frac.iloc[i])

        label = 0
        for j in range(i + 1, min(i + horizon + 1, len(out))):
            if highs[j] >= up_barrier:
                label = 1
                break
            if lows[j] <= down_barrier:
                label = -1
                break
        labels[i] = label

    out[f"y_t4_tb_{horizon}"] = labels
    return out


def make_target_t6_cross_sectional_relative_return(
    df: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    out = df.copy()
    if "Ticker" not in out.columns or "Date" not in out.columns or "Close" not in out.columns:
        out[f"xs_rel_fwd_ret_{horizon}"] = np.nan
        return out

    out = out.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    close = pd.to_numeric(out["Close"], errors="coerce")
    ticker_groups = out.groupby("Ticker", sort=False)
    raw_fwd = ticker_groups["Close"].shift(-horizon) / close - 1.0
    out[f"raw_fwd_ret_xs_{horizon}"] = pd.to_numeric(raw_fwd, errors="coerce")
    xs_mean = out.groupby("Date")[f"raw_fwd_ret_xs_{horizon}"].transform("mean")
    out[f"xs_rel_fwd_ret_{horizon}"] = (
        pd.to_numeric(out[f"raw_fwd_ret_xs_{horizon}"], errors="coerce")
        - pd.to_numeric(xs_mean, errors="coerce")
    )
    return out


def build_targets(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    out = df.copy()
    out = make_target_t1_cost_aware_return(out, horizon=horizon)
    out = make_target_t2_alpha_return(out, horizon=horizon)
    out = make_target_t3_opportunity(out, horizon=horizon)
    out = make_target_t4_triple_barrier(out, horizon=horizon)
    out = make_target_t6_cross_sectional_relative_return(out, horizon=horizon)
    return out
