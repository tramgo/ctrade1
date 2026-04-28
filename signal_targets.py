from __future__ import annotations

import numpy as np
import pandas as pd


def infer_event_direction_proxy(df: pd.DataFrame) -> pd.Series:
    score = (
        1.5 * pd.to_numeric(df.get("Trend_30"), errors="coerce").fillna(0.0)
        + 1.0 * pd.to_numeric(df.get("Trend_2h"), errors="coerce").fillna(0.0)
        + 2.0 * pd.to_numeric(df.get("StockMinusMkt_3"), errors="coerce").fillna(0.0)
        + 1.0 * pd.to_numeric(df.get("StockMinusMkt_1"), errors="coerce").fillna(0.0)
        + 0.75 * pd.to_numeric(df.get("Breakout_3bar"), errors="coerce").fillna(0.0)
        + 0.50 * pd.to_numeric(df.get("SignPersistence_5"), errors="coerce").fillna(0.0)
    )
    direction = pd.Series(0, index=df.index, dtype=float)
    direction.loc[score > 0.001] = 1.0
    direction.loc[score < -0.001] = -1.0
    return direction


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


def make_target_t7_event_outcome_accounting(
    df: pd.DataFrame,
    horizon: int,
    target_mult: float = 1.0,
    stop_mult: float = 1.0,
) -> pd.DataFrame:
    out = generate_forward_returns(df, horizon)
    out[f"est_cost_{horizon}"] = estimate_roundtrip_cost(out)

    atr_frac = np.exp(pd.to_numeric(out["ATR20_log"], errors="coerce").clip(-20, 5)).fillna(0.0)
    direction = infer_event_direction_proxy(out)

    labels = np.full(len(out), np.nan)
    clean_labels = np.full(len(out), np.nan)
    payoff = np.full(len(out), np.nan)
    barrier_outcome = np.full(len(out), np.nan)
    time_to_target = np.full(len(out), np.nan)
    time_to_stop = np.full(len(out), np.nan)
    mae_before_resolution = np.full(len(out), np.nan)
    mfe_before_resolution = np.full(len(out), np.nan)

    highs = pd.to_numeric(out["High"], errors="coerce").to_numpy()
    lows = pd.to_numeric(out["Low"], errors="coerce").to_numpy()
    closes = pd.to_numeric(out["Close"], errors="coerce").to_numpy()
    costs = pd.to_numeric(out[f"est_cost_{horizon}"], errors="coerce").fillna(0.0).to_numpy()
    atr_vals = atr_frac.to_numpy()
    dir_vals = direction.to_numpy()

    for i in range(len(out) - horizon):
        entry = closes[i]
        dir_i = dir_vals[i]
        atr_i = atr_vals[i]
        if not np.isfinite(entry) or entry <= 0 or not np.isfinite(dir_i) or dir_i == 0 or not np.isfinite(atr_i):
            continue

        success_ret = target_mult * atr_i
        stop_ret = stop_mult * atr_i
        resolved = 0
        max_adverse = 0.0
        max_favorable = 0.0
        resolution_step = horizon

        for step, j in enumerate(range(i + 1, min(i + horizon + 1, len(out))), start=1):
            high_ret = highs[j] / entry - 1.0 if np.isfinite(highs[j]) else np.nan
            low_ret = lows[j] / entry - 1.0 if np.isfinite(lows[j]) else np.nan

            if dir_i > 0:
                favorable = high_ret
                adverse = low_ret
                hit_target = np.isfinite(high_ret) and high_ret >= success_ret
                hit_stop = np.isfinite(low_ret) and low_ret <= -stop_ret
            else:
                favorable = -low_ret if np.isfinite(low_ret) else np.nan
                adverse = -high_ret if np.isfinite(high_ret) else np.nan
                hit_target = np.isfinite(low_ret) and low_ret <= -success_ret
                hit_stop = np.isfinite(high_ret) and high_ret >= stop_ret

            if np.isfinite(adverse):
                max_adverse = min(max_adverse, adverse)
            if np.isfinite(favorable):
                max_favorable = max(max_favorable, favorable)

            if hit_target and hit_stop:
                resolved = -1
                time_to_target[i] = float(step)
                time_to_stop[i] = float(step)
                resolution_step = step
                break
            if hit_target:
                resolved = 1
                time_to_target[i] = float(step)
                resolution_step = step
                break
            if hit_stop:
                resolved = -1
                time_to_stop[i] = float(step)
                resolution_step = step
                break

        if resolved == 0:
            expiry_idx = min(i + horizon, len(out) - 1)
            timeout_ret = dir_i * (closes[expiry_idx] / entry - 1.0) if np.isfinite(closes[expiry_idx]) else np.nan
            gross_payoff = timeout_ret
        elif resolved > 0:
            gross_payoff = success_ret
        else:
            gross_payoff = -stop_ret

        labels[i] = 1.0 if resolved > 0 else 0.0
        barrier_outcome[i] = float(resolved)
        payoff[i] = gross_payoff - costs[i] if np.isfinite(gross_payoff) else np.nan
        mae_before_resolution[i] = max_adverse
        mfe_before_resolution[i] = max_favorable

        clean_success = (
            resolved > 0
            and np.isfinite(max_adverse)
            and max_adverse >= -(0.50 * stop_ret)
            and resolution_step <= max(1, int(np.ceil(horizon / 2)))
        )
        clean_labels[i] = 1.0 if clean_success else 0.0

    out[f"event_direction_{horizon}"] = direction
    out[f"y_t7_target_before_stop_{horizon}"] = labels
    out[f"y_t8_clean_target_before_stop_{horizon}"] = clean_labels
    out[f"event_path_payoff_{horizon}"] = payoff
    out[f"event_barrier_outcome_{horizon}"] = barrier_outcome
    out[f"time_to_target_{horizon}"] = time_to_target
    out[f"time_to_stop_{horizon}"] = time_to_stop
    out[f"mae_before_resolution_{horizon}"] = mae_before_resolution
    out[f"mfe_before_resolution_{horizon}"] = mfe_before_resolution
    out[f"clean_event_path_payoff_{horizon}"] = (
        pd.Series(payoff, index=out.index) - 0.25 * pd.Series(np.abs(mae_before_resolution), index=out.index)
    )
    return out


def build_targets(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    out = df.copy()
    out = make_target_t1_cost_aware_return(out, horizon=horizon)
    out = make_target_t2_alpha_return(out, horizon=horizon)
    out = make_target_t3_opportunity(out, horizon=horizon)
    out = make_target_t4_triple_barrier(out, horizon=horizon)
    out = make_target_t6_cross_sectional_relative_return(out, horizon=horizon)
    out = make_target_t7_event_outcome_accounting(out, horizon=horizon)
    return out
