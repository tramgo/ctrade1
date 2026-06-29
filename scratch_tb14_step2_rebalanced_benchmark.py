from typing import Dict, List

import numpy as np
import pandas as pd

import ssell1
from signal_targets import estimate_roundtrip_cost


def annualize(total_return: float, fold_days: int) -> float:
    return ssell1._tb12_annualize_total(total_return, fold_days)


def compound(values: list[float]) -> float:
    return ssell1._tb12_compound(values)


def active_weights(longs: pd.DataFrame) -> pd.Series:
    centered = pd.to_numeric(longs["Prediction"], errors="coerce")
    centered = centered - float(centered.min()) + 1e-6
    denom = float(centered.sum())
    if not np.isfinite(denom) or denom <= 0.0:
        return pd.Series([1.0 / max(1, len(longs))] * len(longs), index=longs.index)
    return centered / denom


def build_costed_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    merged, _pred_csv, _dataset_csv = ssell1._load_tb12_portfolio_rank_source(
        "E1006",
        "outputs_portfolio_rank_60m_10y",
        "research_dataset_portfolio_rank_60m_10y.csv",
    )
    trade_dates = sorted(pd.Series(merged["TradeDate"].dropna().unique()).tolist())
    date_folds = [
        fold.tolist()
        for fold in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), 10)
        if len(fold) > 0
    ]
    event_rows: List[dict] = []
    fold_rows: List[dict] = []
    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_date_index = pd.to_datetime(pd.Series(fold_dates)).dt.normalize().unique()
        fold_df = merged.loc[merged["TradeDate"].isin(fold_date_index)].copy()
        open_times = fold_df.groupby("TradeDate")["Date"].min().dropna().sort_values().tolist()
        if len(open_times) < 2:
            continue

        start_snapshot = fold_df.loc[fold_df["Date"] == open_times[0]].copy()
        end_snapshot = fold_df.loc[fold_df["Date"] == open_times[-1], ["Ticker", "Close"]].rename(columns={"Close": "EndClose"})
        bh_df = start_snapshot.merge(end_snapshot, on="Ticker", how="inner")
        bh_df["Close"] = pd.to_numeric(bh_df["Close"], errors="coerce")
        bh_df["EndClose"] = pd.to_numeric(bh_df["EndClose"], errors="coerce")
        bh_df = bh_df.dropna(subset=["Close", "EndClose"]).copy()
        raw_buyhold_total = float(np.mean((bh_df["EndClose"] / bh_df["Close"]) - 1.0)) if not bh_df.empty else np.nan
        raw_buyhold_ann = annualize(raw_buyhold_total, len(fold_dates))

        rebalanced_returns = []
        for idx in range(len(open_times) - 1):
            if idx % 30 != 0:
                continue
            open_ts = open_times[idx]
            next_open_ts = open_times[min(idx + 30, len(open_times) - 1)]
            if next_open_ts == open_ts:
                continue
            current = fold_df.loc[fold_df["Date"] == open_ts].copy()
            future = fold_df.loc[fold_df["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner")
            current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            if len(current) < 10:
                continue
            current["raw_interval_return"] = (current["NextClose"] / current["Close"]) - 1.0
            current["est_cost"] = estimate_roundtrip_cost(current)
            core_weight = 1.0 / len(current)
            core_net = float((core_weight * current["raw_interval_return"] - core_weight * current["est_cost"]).sum())
            rebalanced_returns.append(core_net)
            ranked = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            longs = ranked.head(10).copy()
            weights = active_weights(longs)
            active_net = float((weights * longs["raw_interval_return"] - weights * longs["est_cost"]).sum())
            event_rows.append(
                {
                    "fold_id": int(fold_idx),
                    "rebalance_ts": open_ts,
                    "next_rebalance_ts": next_open_ts,
                    "eligible_count": int(len(current)),
                    "core_return_net": core_net,
                    "active_return_net": active_net,
                    "BreadthAdvFrac_1": float(pd.to_numeric(current.get("BreadthAdvFrac_1"), errors="coerce").mean()),
                    "BreadthRelAdvFrac_3": float(pd.to_numeric(current.get("BreadthRelAdvFrac_3"), errors="coerce").mean()),
                    "top_names": "|".join(longs["Ticker"].astype(str).tolist()),
                }
            )
        rebalanced_total = compound(rebalanced_returns)
        fold_rows.append(
            {
                "fold_id": int(fold_idx),
                "fold_trade_dates": int(len(fold_dates)),
                "raw_buyhold_total_return": raw_buyhold_total,
                "raw_buyhold_annualized_return": raw_buyhold_ann,
                "rebalanced_benchmark_total_return": rebalanced_total,
                "rebalanced_benchmark_annualized_return": annualize(rebalanced_total, len(fold_dates)),
                "rebalance_count": int(len(rebalanced_returns)),
            }
        )
    return pd.DataFrame(event_rows), pd.DataFrame(fold_rows)


def score(events: pd.DataFrame, folds: pd.DataFrame, variant_id: str, returns_by_event: pd.Series) -> list[dict]:
    tmp = events[["fold_id"]].copy()
    tmp["strategy_return"] = returns_by_event.values
    rows = []
    for fold_id, fold_events in tmp.groupby("fold_id"):
        base = folds.loc[folds["fold_id"] == fold_id].iloc[0]
        total = compound(pd.to_numeric(fold_events["strategy_return"], errors="coerce").fillna(0.0).tolist())
        ann = annualize(total, int(base["fold_trade_dates"]))
        bench = float(base["rebalanced_benchmark_annualized_return"])
        rows.append(
            {
                "variant_id": variant_id,
                "fold_id": int(fold_id),
                "strategy_total_return": total,
                "strategy_annualized_return": ann,
                "rebalanced_benchmark_annualized_return": bench,
                "excess_vs_rebalanced_benchmark_annualized": ann - bench,
                "beats_rebalanced_benchmark": bool(ann > bench),
            }
        )
    return rows


def main() -> None:
    events, folds = build_costed_events()
    breadth_adv = pd.to_numeric(events["BreadthAdvFrac_1"], errors="coerce").fillna(0.0)
    rel_breadth = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    core = pd.to_numeric(events["core_return_net"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(events["active_return_net"], errors="coerce").fillna(0.0)

    tb13_gated = np.where(breadth_adv >= 0.50, active, core)
    tb13_return = 0.50 * core + 0.50 * tb13_gated
    tb14_return = np.where(
        rel_breadth <= 0.3703703703703703,
        1.20 * core - 0.20 * active,
        0.90 * core + 0.10 * active,
    )
    detail_rows = []
    detail_rows.extend(score(events, folds, "tb13_breadth_adv50_core50_active50_costed_core", pd.Series(tb13_return)))
    detail_rows.extend(score(events, folds, "tb14_dynamic_hedge_costed_core", pd.Series(tb14_return)))
    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby("variant_id", as_index=False)
        .agg(
            fold_count=("fold_id", "nunique"),
            mean_strategy_annualized=("strategy_annualized_return", "mean"),
            mean_rebalanced_benchmark_annualized=("rebalanced_benchmark_annualized_return", "mean"),
            mean_excess_vs_rebalanced_benchmark_annualized=("excess_vs_rebalanced_benchmark_annualized", "mean"),
            min_strategy_annualized=("strategy_annualized_return", "min"),
            folds_beating_rebalanced_benchmark=("beats_rebalanced_benchmark", "sum"),
        )
        .reset_index()
    )
    tb14_beats = int(summary.loc[summary["variant_id"] == "tb14_dynamic_hedge_costed_core", "folds_beating_rebalanced_benchmark"].iloc[0])
    decision = "kill_switch_retract_10_of_10_claim" if tb14_beats < 7 else "step2_survives"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step2_rebalanced_benchmark",
                "tb14_folds_beating_rebalanced_benchmark": tb14_beats,
                "kill_switch_min_folds": 7,
                "decision": decision,
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    folds.to_csv(out_dir / "tb14_step2_rebalanced_benchmark_benchmark_folds.csv", index=False)
    detail.to_csv(out_dir / "tb14_step2_rebalanced_benchmark_detail.csv", index=False)
    summary.to_csv(out_dir / "tb14_step2_rebalanced_benchmark_summary.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step2_rebalanced_benchmark_decision.csv", index=False)
    print(decision_df.to_string(index=False))
    print(summary.to_string(index=False))
    print(detail.to_string(index=False))


if __name__ == "__main__":
    main()
