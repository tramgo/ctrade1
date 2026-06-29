import numpy as np
import pandas as pd

import ssell1
from scratch_tb14_step2_rebalanced_benchmark import build_costed_events, score


def summarize(detail: pd.DataFrame, fold_set: str, quantile: float, threshold: float) -> dict:
    return {
        "fold_set": fold_set,
        "quantile": quantile,
        "threshold": threshold,
        "fold_count": int(detail["fold_id"].nunique()),
        "mean_strategy_annualized": float(detail["strategy_annualized_return"].mean()),
        "mean_rebalanced_benchmark_annualized": float(detail["rebalanced_benchmark_annualized_return"].mean()),
        "mean_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
        "folds_beating_rebalanced_benchmark": int(detail["beats_rebalanced_benchmark"].sum()),
        "min_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].min()),
    }


def main() -> None:
    events, folds = build_costed_events()
    events = events.reset_index(drop=True)
    rel_breadth = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    core = pd.to_numeric(events["core_return_net"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(events["active_return_net"], errors="coerce").fillna(0.0)
    fit_mask = events["fold_id"].isin([1, 2, 3, 4, 5])
    holdout_event_mask = events["fold_id"].isin([6, 7, 8, 9, 10])
    candidate_quantiles = [0.20, 0.25, 0.33, 0.40, 0.50]
    fit_rows = []
    detail_frames = []
    for quantile in candidate_quantiles:
        threshold = float(rel_breadth.loc[fit_mask].quantile(quantile))
        returns = pd.Series(
            np.where(
            rel_breadth <= threshold,
            1.20 * core - 0.20 * active,
            0.90 * core + 0.10 * active,
            ),
            index=events.index,
        )
        fit_detail = pd.DataFrame(
            score(
                events.loc[fit_mask].copy(),
                folds.loc[folds["fold_id"].isin([1, 2, 3, 4, 5])].copy(),
                f"fit_q{quantile:.2f}",
                returns.loc[fit_mask].reset_index(drop=True),
            )
        )
        fit_summary = summarize(fit_detail, "fit_folds_1_5", quantile, threshold)
        fit_rows.append(fit_summary)
        fit_detail["quantile"] = quantile
        fit_detail["threshold"] = threshold
        detail_frames.append(fit_detail)
    fit_summary_df = pd.DataFrame(fit_rows).sort_values(
        ["folds_beating_rebalanced_benchmark", "mean_excess_vs_rebalanced_benchmark_annualized"],
        ascending=[False, False],
    )
    winner = fit_summary_df.iloc[0]
    frozen_quantile = float(winner["quantile"])
    frozen_threshold = float(winner["threshold"])
    frozen_returns = pd.Series(
        np.where(
        rel_breadth <= frozen_threshold,
        1.20 * core - 0.20 * active,
        0.90 * core + 0.10 * active,
        ),
        index=events.index,
    )
    holdout_detail = pd.DataFrame(
        score(
            events.loc[holdout_event_mask].copy(),
            folds.loc[folds["fold_id"].isin([6, 7, 8, 9, 10])].copy(),
            f"holdout_frozen_q{frozen_quantile:.2f}",
            frozen_returns.loc[holdout_event_mask].reset_index(drop=True),
        )
    )
    holdout_summary = pd.DataFrame([summarize(holdout_detail, "holdout_folds_6_10", frozen_quantile, frozen_threshold)])
    holdout_beats = int(holdout_summary["folds_beating_rebalanced_benchmark"].iloc[0])
    decision = "kill_switch_no_oos_threshold_evidence" if holdout_beats < 4 else "step3_survives"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step3_walkforward_threshold",
                "fit_folds": "1-5",
                "holdout_folds": "6-10",
                "candidate_quantiles": "|".join(f"{q:.2f}" for q in candidate_quantiles),
                "selected_quantile": frozen_quantile,
                "selected_threshold": frozen_threshold,
                "holdout_folds_beating_rebalanced_benchmark": holdout_beats,
                "kill_switch_min_holdout_folds": 4,
                "decision": decision,
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    fit_summary_df.to_csv(out_dir / "tb14_step3_walkforward_threshold_fit_summary.csv", index=False)
    pd.concat(detail_frames, ignore_index=True).to_csv(out_dir / "tb14_step3_walkforward_threshold_fit_detail.csv", index=False)
    holdout_summary.to_csv(out_dir / "tb14_step3_walkforward_threshold_holdout_summary.csv", index=False)
    holdout_detail.to_csv(out_dir / "tb14_step3_walkforward_threshold_holdout_detail.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step3_walkforward_threshold_decision.csv", index=False)
    print(decision_df.to_string(index=False))
    print("FIT")
    print(fit_summary_df.to_string(index=False))
    print("HOLDOUT")
    print(holdout_summary.to_string(index=False))
    print(holdout_detail.to_string(index=False))


if __name__ == "__main__":
    main()
