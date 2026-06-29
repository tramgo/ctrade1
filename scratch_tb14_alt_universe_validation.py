from pathlib import Path

import numpy as np
import pandas as pd

import ssell1


def annualize(total_return: float, sessions: int) -> float:
    if not np.isfinite(total_return) or total_return <= -0.999999:
        return np.nan
    return float((1.0 + total_return) ** (250.0 / max(1.0, float(sessions))) - 1.0)


def compound(values: list[float]) -> float:
    return float(np.prod([1.0 + float(v) for v in values]) - 1.0) if values else np.nan


def score_weights(scores: pd.Series) -> pd.Series:
    centered = pd.to_numeric(scores, errors="coerce")
    centered = centered - float(centered.min()) + 1e-6
    denom = float(centered.sum())
    if not np.isfinite(denom) or denom <= 0:
        return pd.Series([1.0 / len(scores)] * len(scores), index=scores.index)
    return centered / denom


def load_alt_daily() -> tuple[pd.DataFrame, list[str]]:
    frames = []
    missing = []
    for ticker in ssell1.TB06_MIDSMALL_UNIVERSE:
        path = Path("data") / f"data_fetched_{ticker}_60m_3650d.csv"
        if not path.exists():
            missing.append(ticker)
            continue
        df = pd.read_csv(path, usecols=lambda c: c in {"Date", "Close"})
        if "Date" not in df.columns or "Close" not in df.columns:
            missing.append(ticker)
            continue
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["TradeDate"] = df["Date"].dt.normalize()
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        daily = (
            df.dropna(subset=["TradeDate", "Close"])
            .sort_values("Date")
            .groupby("TradeDate", as_index=False)["Close"]
            .last()
        )
        daily["Ticker"] = ticker
        frames.append(daily[["Ticker", "TradeDate", "Close"]])
    return pd.concat(frames, ignore_index=True), missing


def main() -> None:
    out_dir = Path("results") / "signal_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    daily, missing = load_alt_daily()
    daily = daily.sort_values(["Ticker", "TradeDate"]).reset_index(drop=True)
    daily["ret3"] = daily.groupby("Ticker")["Close"].pct_change(3)
    daily["mom60"] = daily.groupby("Ticker")["Close"].pct_change(60)
    market = (
        daily.groupby("TradeDate", as_index=False)["Close"]
        .count()
        .rename(columns={"Close": "available_symbol_count"})
    )
    market_ret = (
        daily.pivot(index="TradeDate", columns="Ticker", values="Close")
        .sort_index()
        .pct_change(3)
        .mean(axis=1)
        .rename("mkt_ret3")
        .reset_index()
    )
    daily = daily.merge(market_ret, on="TradeDate", how="left")
    daily["rel_adv3"] = (daily["ret3"] - daily["mkt_ret3"]) > 0
    breadth = (
        daily.groupby("TradeDate", as_index=False)
        .agg(BreadthRelAdvFrac_3=("rel_adv3", "mean"))
        .merge(market, on="TradeDate", how="left")
    )
    trade_dates = sorted(daily["TradeDate"].dropna().unique().tolist())
    folds = [fold.tolist() for fold in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), 10) if len(fold)]
    threshold = 0.3703703703703703
    normal_active_weight = 0.10
    hedge_active_weight = -0.20
    top_k = 10
    rebalance_every = 30
    fold_rows = []
    event_rows = []
    for fold_idx, fold_dates in enumerate(folds, start=1):
        dates = pd.to_datetime(pd.Series(fold_dates)).dt.normalize().tolist()
        fold_df = daily[daily["TradeDate"].isin(dates)].copy()
        start = fold_df[fold_df["TradeDate"] == dates[0]][["Ticker", "Close"]]
        end = fold_df[fold_df["TradeDate"] == dates[-1]][["Ticker", "Close"]].rename(columns={"Close": "EndClose"})
        bh = start.merge(end, on="Ticker", how="inner")
        bh_total = float(((bh["EndClose"] / bh["Close"]) - 1.0).mean()) if not bh.empty else np.nan
        bh_ann = annualize(bh_total, len(dates))
        strategy_returns = []
        for idx in range(0, len(dates) - 1, rebalance_every):
            current_date = dates[idx]
            next_date = dates[min(idx + rebalance_every, len(dates) - 1)]
            current = fold_df[fold_df["TradeDate"] == current_date].copy()
            future = fold_df[fold_df["TradeDate"] == next_date][["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner").dropna(subset=["Close", "NextClose", "mom60"])
            if len(current) < top_k:
                continue
            current["interval_return"] = (current["NextClose"] / current["Close"]) - 1.0
            core_return = float(current["interval_return"].mean())
            longs = current.sort_values("mom60", ascending=False).head(top_k).copy()
            weights = score_weights(longs["mom60"])
            active_return = float((weights * longs["interval_return"]).sum())
            breadth_row = breadth[breadth["TradeDate"] == current_date]
            breadth_rel = float(breadth_row.iloc[0]["BreadthRelAdvFrac_3"]) if not breadth_row.empty else np.nan
            hedge_regime = bool(np.isfinite(breadth_rel) and breadth_rel <= threshold)
            active_weight = hedge_active_weight if hedge_regime else normal_active_weight
            core_weight = 1.0 - active_weight
            strategy_return = core_weight * core_return + active_weight * active_return
            strategy_returns.append(strategy_return)
            event_rows.append(
                {
                    "fold_id": fold_idx,
                    "rebalance_date": current_date,
                    "next_rebalance_date": next_date,
                    "available_symbol_count": int(len(current)),
                    "BreadthRelAdvFrac_3": breadth_rel,
                    "hedge_regime": hedge_regime,
                    "core_weight": core_weight,
                    "active_weight": active_weight,
                    "core_return": core_return,
                    "active_return": active_return,
                    "strategy_return": strategy_return,
                    "top_names": "|".join(longs["Ticker"].astype(str).tolist()),
                }
            )
        total = compound(strategy_returns)
        ann = annualize(total, len(dates))
        fold_rows.append(
            {
                "fold_id": fold_idx,
                "fold_start_date": dates[0],
                "fold_end_date": dates[-1],
                "available_symbol_count": int(fold_df["Ticker"].nunique()),
                "event_count": len(strategy_returns),
                "strategy_total_return": total,
                "strategy_annualized_return": ann,
                "buyhold_total_return": bh_total,
                "buyhold_annualized_return": bh_ann,
                "excess_vs_buyhold_annualized": ann - bh_ann if np.isfinite(ann) and np.isfinite(bh_ann) else np.nan,
                "beats_buyhold": bool(np.isfinite(ann) and np.isfinite(bh_ann) and ann > bh_ann),
            }
        )
    folds_df = pd.DataFrame(fold_rows)
    summary = pd.DataFrame(
        [
            {
                "validation_id": "TB14_alt_mid_small_frozen_rule_momentum_proxy",
                "universe": "TB06_MIDSMALL_UNIVERSE",
                "available_symbols": int(daily["Ticker"].nunique()),
                "missing_symbols": "|".join(missing),
                "rank_proxy": "60_session_momentum",
                "threshold_source": "frozen_from_TB14_original_universe",
                "low_breadth_rel_threshold": threshold,
                "fold_count": int(folds_df["fold_id"].nunique()),
                "mean_strategy_annualized": float(folds_df["strategy_annualized_return"].mean()),
                "mean_buyhold_annualized": float(folds_df["buyhold_annualized_return"].mean()),
                "min_strategy_annualized": float(folds_df["strategy_annualized_return"].min()),
                "min_buyhold_annualized": float(folds_df["buyhold_annualized_return"].min()),
                "folds_beating_buyhold": int(folds_df["beats_buyhold"].sum()),
                "all_folds_beat_buyhold": bool(folds_df["beats_buyhold"].all()),
            }
        ]
    )
    prefix = "tb14_alt_universe_mid_small_frozen_rule"
    summary.to_csv(out_dir / f"{prefix}_summary.csv", index=False)
    folds_df.to_csv(out_dir / f"{prefix}_folds.csv", index=False)
    pd.DataFrame(event_rows).to_csv(out_dir / f"{prefix}_events.csv", index=False)
    print(summary.to_string(index=False))
    print(folds_df.to_string(index=False))


if __name__ == "__main__":
    main()
