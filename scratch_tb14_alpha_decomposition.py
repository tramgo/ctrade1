import numpy as np
import pandas as pd

import ssell1


def score_variant(events: pd.DataFrame, folds: pd.DataFrame, return_col: str, variant_id: str) -> list[dict]:
    rows = []
    for fold_id, fold_events in events.groupby("fold_id"):
        fold_events = fold_events.sort_values("rebalance_ts").copy()
        base_fold = folds.loc[folds["fold_id"] == fold_id].iloc[0]
        total_return = ssell1._tb12_compound(pd.to_numeric(fold_events[return_col], errors="coerce").fillna(0.0).tolist())
        annualized = ssell1._tb12_annualize_total(total_return, int(base_fold["fold_trade_dates"]))
        buyhold_ann = float(base_fold["buyhold_annualized_return"])
        rows.append(
            {
                "variant_id": variant_id,
                "fold_id": int(fold_id),
                "fold_trade_dates": int(base_fold["fold_trade_dates"]),
                "rebalance_count": int(len(fold_events)),
                "strategy_total_return": total_return,
                "strategy_annualized_return": annualized,
                "buyhold_annualized_return": buyhold_ann,
                "excess_vs_buyhold_annualized": annualized - buyhold_ann,
                "beats_buyhold": bool(annualized > buyhold_ann),
            }
        )
    return rows


def main() -> None:
    events, folds, meta = ssell1._tb12_build_candidate_events(
        "E1006",
        10,
        30,
        "outputs_portfolio_rank_60m_10y",
        "research_dataset_portfolio_rank_60m_10y.csv",
        10,
    )
    events = events.copy()
    events["core_return"] = pd.to_numeric(events["universe_interval_return"], errors="coerce").fillna(0.0)
    events["active_return"] = pd.to_numeric(events["portfolio_return"], errors="coerce").fillna(0.0)
    events["BreadthRelAdvFrac_3"] = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce")
    threshold = 0.3703703703703703
    events["hedge_regime"] = events["BreadthRelAdvFrac_3"].fillna(1.0) <= threshold
    events["full_tb14_return"] = np.where(
        events["hedge_regime"],
        1.20 * events["core_return"] - 0.20 * events["active_return"],
        0.90 * events["core_return"] + 0.10 * events["active_return"],
    )
    # Pure active is the E1006 top10 score-weighted active basket with hedge logic off.
    # It includes the same active-sleeve roundtrip cost embedded by _tb12_build_candidate_events.
    events["pure_active_return"] = events["active_return"]
    events["core_only_return"] = events["core_return"]

    rows = []
    rows.extend(score_variant(events, folds, "core_only_return", "core_only_rebalanced_equal_weight"))
    rows.extend(score_variant(events, folds, "pure_active_return", "pure_e1006_top10_active_no_hedge"))
    rows.extend(score_variant(events, folds, "full_tb14_return", "full_tb14_dynamic_hedge"))
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("variant_id", as_index=False)
        .agg(
            fold_count=("fold_id", "nunique"),
            rebalance_count=("rebalance_count", "sum"),
            mean_strategy_annualized=("strategy_annualized_return", "mean"),
            mean_buyhold_annualized=("buyhold_annualized_return", "mean"),
            mean_excess_vs_buyhold_annualized=("excess_vs_buyhold_annualized", "mean"),
            min_strategy_annualized=("strategy_annualized_return", "min"),
            folds_beating_buyhold=("beats_buyhold", "sum"),
        )
        .sort_values("mean_excess_vs_buyhold_annualized", ascending=False)
        .reset_index(drop=True)
    )
    full_excess = float(summary.loc[summary["variant_id"] == "full_tb14_dynamic_hedge", "mean_excess_vs_buyhold_annualized"].iloc[0])
    core_excess = float(summary.loc[summary["variant_id"] == "core_only_rebalanced_equal_weight", "mean_excess_vs_buyhold_annualized"].iloc[0])
    active_excess = float(summary.loc[summary["variant_id"] == "pure_e1006_top10_active_no_hedge", "mean_excess_vs_buyhold_annualized"].iloc[0])
    rebalance_bonus_share = core_excess / full_excess if np.isfinite(full_excess) and full_excess != 0.0 else np.nan
    decision = "kill_switch_demote_tb13_tb14" if np.isfinite(rebalance_bonus_share) and rebalance_bonus_share >= 0.60 else "step1_survives"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step1_alpha_decomposition",
                "source_rows": int(meta.get("source_rows", 0)),
                "threshold": threshold,
                "full_tb14_mean_excess": full_excess,
                "core_only_mean_excess": core_excess,
                "pure_active_mean_excess": active_excess,
                "rebalance_bonus_share_of_full_excess": rebalance_bonus_share,
                "kill_switch_threshold": 0.60,
                "decision": decision,
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    detail.to_csv(out_dir / "tb14_step1_alpha_decomposition_detail.csv", index=False)
    summary.to_csv(out_dir / "tb14_step1_alpha_decomposition_summary.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step1_alpha_decomposition_decision.csv", index=False)
    print(decision_df.to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
