import itertools

import numpy as np
import pandas as pd

import ssell1
from scratch_tb14_step2_rebalanced_benchmark import build_costed_events, score


def summarize(detail: pd.DataFrame, label: str, spec: dict) -> dict:
    return {
        "fold_set": label,
        **spec,
        "fold_count": int(detail["fold_id"].nunique()),
        "mean_strategy_annualized": float(detail["strategy_annualized_return"].mean()),
        "mean_rebalanced_benchmark_annualized": float(detail["rebalanced_benchmark_annualized_return"].mean()),
        "mean_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
        "folds_beating_rebalanced_benchmark": int(detail["beats_rebalanced_benchmark"].sum()),
        "min_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].min()),
    }


def build_returns(
    events: pd.DataFrame,
    quantile: float,
    threshold: float,
    normal_active_weight: float,
    hedge_active_weight: float,
    borrow_annual: float = 0.05,
    short_slippage_bps: float = 25.0,
) -> pd.Series:
    core = pd.to_numeric(events["core_return_net"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(events["active_return_net"], errors="coerce").fillna(0.0)
    rel_breadth = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    hedge_mask = rel_breadth <= threshold
    hold_days = (
        pd.to_datetime(events["next_rebalance_ts"], errors="coerce")
        - pd.to_datetime(events["rebalance_ts"], errors="coerce")
    ).dt.total_seconds().div(86400.0).fillna(30.0)
    extra_short_cost = np.where(
        hedge_mask & (hedge_active_weight < 0.0),
        abs(hedge_active_weight) * ((borrow_annual * hold_days / 365.0) + (short_slippage_bps / 10000.0)),
        0.0,
    )
    weights = np.where(hedge_mask, hedge_active_weight, normal_active_weight)
    returns = (1.0 - weights) * core + weights * active - extra_short_cost
    return pd.Series(returns, index=events.index)


def main() -> None:
    events, folds = build_costed_events()
    events = events.reset_index(drop=True)
    fit_mask = events["fold_id"].isin(range(1, 9))
    oos_mask = events["fold_id"].isin([9, 10])
    rel_fit = pd.to_numeric(events.loc[fit_mask, "BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    candidate_quantiles = [0.20, 0.25, 0.33, 0.40, 0.50]
    normal_weights = [0.00, 0.10, 0.20]
    hedge_weights = [-0.10, -0.20, -0.30]
    fit_rows = []
    fit_details = []
    for quantile, normal_weight, hedge_weight in itertools.product(candidate_quantiles, normal_weights, hedge_weights):
        threshold = float(rel_fit.quantile(quantile))
        spec = {
            "quantile": quantile,
            "threshold": threshold,
            "normal_active_weight": normal_weight,
            "hedge_active_weight": hedge_weight,
            "borrow_annual": 0.05,
            "short_slippage_bps": 25.0,
        }
        returns = build_returns(events, quantile, threshold, normal_weight, hedge_weight)
        detail = pd.DataFrame(
            score(
                events.loc[fit_mask].copy(),
                folds.loc[folds["fold_id"].isin(range(1, 9))].copy(),
                "fit_candidate",
                returns.loc[fit_mask].reset_index(drop=True),
            )
        )
        fit_rows.append(summarize(detail, "fit_folds_1_8", spec))
        detail = detail.assign(**spec)
        fit_details.append(detail)
    fit_summary = pd.DataFrame(fit_rows).sort_values(
        ["folds_beating_rebalanced_benchmark", "mean_excess_vs_rebalanced_benchmark_annualized"],
        ascending=[False, False],
    ).reset_index(drop=True)
    winner = fit_summary.iloc[0].to_dict()
    frozen_spec = {
        "quantile": float(winner["quantile"]),
        "threshold": float(winner["threshold"]),
        "normal_active_weight": float(winner["normal_active_weight"]),
        "hedge_active_weight": float(winner["hedge_active_weight"]),
        "borrow_annual": 0.05,
        "short_slippage_bps": 25.0,
    }
    frozen_returns = build_returns(events, **frozen_spec)
    oos_detail = pd.DataFrame(
        score(
            events.loc[oos_mask].copy(),
            folds.loc[folds["fold_id"].isin([9, 10])].copy(),
            "strict_oos_frozen_folds_9_10",
            frozen_returns.loc[oos_mask].reset_index(drop=True),
        )
    )
    oos_summary = pd.DataFrame([summarize(oos_detail, "oos_folds_9_10", frozen_spec)])
    oos_beats = int(oos_summary["folds_beating_rebalanced_benchmark"].iloc[0])
    decision = "step6_survives_deployment_discussion_allowed" if oos_beats == 2 else "kill_switch_oos_replay_failed"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step6_strict_oos_replay",
                "fit_folds": "1-8",
                "oos_folds": "9-10",
                **frozen_spec,
                "oos_folds_beating_rebalanced_benchmark": oos_beats,
                "required_oos_folds": 2,
                "decision": decision,
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    fit_summary.to_csv(out_dir / "tb14_step6_strict_oos_replay_fit_summary.csv", index=False)
    pd.concat(fit_details, ignore_index=True).to_csv(out_dir / "tb14_step6_strict_oos_replay_fit_detail.csv", index=False)
    oos_summary.to_csv(out_dir / "tb14_step6_strict_oos_replay_oos_summary.csv", index=False)
    oos_detail.to_csv(out_dir / "tb14_step6_strict_oos_replay_oos_detail.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step6_strict_oos_replay_decision.csv", index=False)
    print(decision_df.to_string(index=False))
    print("FIT TOP")
    print(fit_summary.head(10).to_string(index=False))
    print("OOS")
    print(oos_summary.to_string(index=False))
    print(oos_detail.to_string(index=False))


if __name__ == "__main__":
    main()
