import itertools

import pandas as pd

from scratch_tb14_step2_rebalanced_benchmark import build_costed_events, score
from scratch_tb14_step6_strict_oos_replay import build_returns
import ssell1


def summarize(detail: pd.DataFrame, fit_folds: list[int], oos_folds: list[int], spec: dict) -> dict:
    return {
        "fit_folds": ",".join(map(str, fit_folds)),
        "oos_folds": ",".join(map(str, oos_folds)),
        **spec,
        "oos_fold_count": int(detail["fold_id"].nunique()),
        "mean_strategy_annualized": float(detail["strategy_annualized_return"].mean()),
        "mean_rebalanced_benchmark_annualized": float(detail["rebalanced_benchmark_annualized_return"].mean()),
        "mean_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
        "folds_beating_rebalanced_benchmark": int(detail["beats_rebalanced_benchmark"].sum()),
        "min_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].min()),
    }


def run_case(events: pd.DataFrame, folds: pd.DataFrame, fit_folds: list[int], oos_folds: list[int]) -> tuple[dict, pd.DataFrame]:
    fit_mask = events["fold_id"].isin(fit_folds)
    oos_mask = events["fold_id"].isin(oos_folds)
    rel_fit = pd.to_numeric(events.loc[fit_mask, "BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    candidates = []
    for quantile, normal_weight, hedge_weight in itertools.product(
        [0.20, 0.25, 0.33, 0.40, 0.50],
        [0.00, 0.10, 0.20],
        [-0.10, -0.20, -0.30],
    ):
        threshold = float(rel_fit.quantile(quantile))
        spec = {
            "quantile": quantile,
            "threshold": threshold,
            "normal_active_weight": normal_weight,
            "hedge_active_weight": hedge_weight,
            "borrow_annual": 0.05,
            "short_slippage_bps": 25.0,
        }
        returns = build_returns(events, **spec)
        fit_detail = pd.DataFrame(
            score(
                events.loc[fit_mask].copy(),
                folds.loc[folds["fold_id"].isin(fit_folds)].copy(),
                "fit_candidate",
                returns.loc[fit_mask].reset_index(drop=True),
            )
        )
        candidates.append(
            {
                **spec,
                "fit_folds_beating": int(fit_detail["beats_rebalanced_benchmark"].sum()),
                "fit_mean_excess": float(fit_detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
                "fit_min_excess": float(fit_detail["excess_vs_rebalanced_benchmark_annualized"].min()),
            }
        )
    candidate_df = pd.DataFrame(candidates).sort_values(
        ["fit_folds_beating", "fit_mean_excess"],
        ascending=[False, False],
    )
    winner = candidate_df.iloc[0].to_dict()
    spec = {
        "quantile": float(winner["quantile"]),
        "threshold": float(winner["threshold"]),
        "normal_active_weight": float(winner["normal_active_weight"]),
        "hedge_active_weight": float(winner["hedge_active_weight"]),
        "borrow_annual": 0.05,
        "short_slippage_bps": 25.0,
    }
    returns = build_returns(events, **spec)
    oos_detail = pd.DataFrame(
        score(
            events.loc[oos_mask].copy(),
            folds.loc[folds["fold_id"].isin(oos_folds)].copy(),
            "oos_candidate",
            returns.loc[oos_mask].reset_index(drop=True),
        )
    )
    return summarize(oos_detail, fit_folds, oos_folds, spec), oos_detail.assign(
        fit_folds=",".join(map(str, fit_folds)),
        oos_folds=",".join(map(str, oos_folds)),
        **spec,
    )


def main() -> None:
    events, folds = build_costed_events()
    events = events.reset_index(drop=True)
    cases = [
        ([1, 2, 3, 4, 5], [6, 7, 8, 9, 10]),
        ([1, 2, 3, 4, 5, 6], [7, 8, 9, 10]),
        ([1, 2, 3, 4, 5, 6, 7], [8, 9, 10]),
        ([1, 2, 3, 4, 5, 6, 7, 8], [9, 10]),
    ]
    rows = []
    details = []
    for fit_folds, oos_folds in cases:
        summary, detail = run_case(events, folds, fit_folds, oos_folds)
        rows.append(summary)
        details.append(detail)
    summary_df = pd.DataFrame(rows)
    detail_df = pd.concat(details, ignore_index=True)
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    summary_df.to_csv(out_dir / "tb14_step6_oos_window_sensitivity_summary.csv", index=False)
    detail_df.to_csv(out_dir / "tb14_step6_oos_window_sensitivity_detail.csv", index=False)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
