import numpy as np
import pandas as pd

import ssell1
from scratch_tb14_step2_rebalanced_benchmark import build_costed_events, score


def mean_excess_for_returns(events: pd.DataFrame, folds: pd.DataFrame, returns: pd.Series) -> tuple[float, int]:
    detail = pd.DataFrame(score(events, folds, "candidate", returns.reset_index(drop=True)))
    return (
        float(detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
        int(detail["beats_rebalanced_benchmark"].sum()),
    )


def main() -> None:
    events, folds = build_costed_events()
    events = events.reset_index(drop=True)
    core = pd.to_numeric(events["core_return_net"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(events["active_return_net"], errors="coerce").fillna(0.0)
    rel_breadth = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    actual_hedge_mask = rel_breadth <= 0.3703703703703703
    hedge_count = int(actual_hedge_mask.sum())
    actual_returns = pd.Series(
        np.where(actual_hedge_mask, 1.20 * core - 0.20 * active, 0.90 * core + 0.10 * active),
        index=events.index,
    )
    actual_mean_excess, actual_folds = mean_excess_for_returns(events, folds, actual_returns)

    rows = []
    event_count = len(events)
    for seed in range(1000):
        rng = np.random.default_rng(seed)
        hedge_indices = set(rng.choice(event_count, size=hedge_count, replace=False).tolist())
        random_mask = pd.Series([idx in hedge_indices for idx in range(event_count)], index=events.index)
        random_returns = pd.Series(
            np.where(random_mask, 1.20 * core - 0.20 * active, 0.90 * core + 0.10 * active),
            index=events.index,
        )
        mean_excess, fold_wins = mean_excess_for_returns(events, folds, random_returns)
        rows.append(
            {
                "seed": seed,
                "hedge_count": hedge_count,
                "mean_excess_vs_rebalanced_benchmark_annualized": mean_excess,
                "folds_beating_rebalanced_benchmark": fold_wins,
            }
        )
    null_df = pd.DataFrame(rows)
    p75 = float(null_df["mean_excess_vs_rebalanced_benchmark_annualized"].quantile(0.75))
    p90 = float(null_df["mean_excess_vs_rebalanced_benchmark_annualized"].quantile(0.90))
    percentile = float((null_df["mean_excess_vs_rebalanced_benchmark_annualized"] < actual_mean_excess).mean())
    decision = "kill_switch_dynamic_hedge_not_informative" if actual_mean_excess <= p75 else "step4_survives"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step4_random_hedge_null",
                "seed_count": 1000,
                "event_count": event_count,
                "actual_hedge_count": hedge_count,
                "actual_mean_excess_vs_rebalanced_benchmark_annualized": actual_mean_excess,
                "actual_folds_beating_rebalanced_benchmark": actual_folds,
                "null_p75_mean_excess": p75,
                "null_p90_mean_excess": p90,
                "actual_percentile_vs_null": percentile,
                "kill_switch_threshold_percentile": 0.75,
                "decision": decision,
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    null_df.to_csv(out_dir / "tb14_step4_random_hedge_null_distribution.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step4_random_hedge_null_decision.csv", index=False)
    print(decision_df.to_string(index=False))


if __name__ == "__main__":
    main()
