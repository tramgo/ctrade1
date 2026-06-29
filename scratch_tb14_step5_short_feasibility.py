from pathlib import Path

import numpy as np
import pandas as pd

import ssell1
from scratch_tb14_step2_rebalanced_benchmark import build_costed_events, score


def load_futstk_symbols(required_symbols: set[str]) -> set[str]:
    path = Path("data") / "nse_fno_bhavcopy_oi.csv"
    if not path.exists():
        return set()
    found: set[str] = set()
    usecols = ["instrument", "symbol"]
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=500_000):
        fut = chunk.loc[chunk["instrument"].astype(str).str.upper().eq("FUTSTK"), "symbol"].astype(str).str.upper()
        found.update(set(fut[fut.isin(required_symbols)].tolist()))
        if required_symbols.issubset(found):
            break
    return found


def main() -> None:
    events, folds = build_costed_events()
    events = events.reset_index(drop=True)
    core = pd.to_numeric(events["core_return_net"], errors="coerce").fillna(0.0)
    active = pd.to_numeric(events["active_return_net"], errors="coerce").fillna(0.0)
    rel_breadth = pd.to_numeric(events["BreadthRelAdvFrac_3"], errors="coerce").fillna(1.0)
    hedge_mask = rel_breadth <= 0.3703703703703703
    events["hedge_regime"] = hedge_mask
    events["rebalance_ts"] = pd.to_datetime(events["rebalance_ts"], errors="coerce")
    events["next_rebalance_ts"] = pd.to_datetime(events["next_rebalance_ts"], errors="coerce")
    events["holding_days"] = (events["next_rebalance_ts"] - events["rebalance_ts"]).dt.total_seconds().div(86400.0).fillna(30.0)

    hedge_events = events.loc[hedge_mask].copy()
    short_rows = []
    required_symbols: set[str] = set()
    for _, event in hedge_events.iterrows():
        names = [name for name in str(event.get("top_names", "")).split("|") if name]
        for name in names:
            symbol = name.upper()
            required_symbols.add(symbol)
            short_rows.append(
                {
                    "fold_id": int(event["fold_id"]),
                    "rebalance_ts": event["rebalance_ts"],
                    "next_rebalance_ts": event["next_rebalance_ts"],
                    "ticker": symbol,
                    "short_notional_weight_proxy": 0.20 / max(1, len(names)),
                }
            )
    fut_symbols = load_futstk_symbols(required_symbols)
    short_df = pd.DataFrame(short_rows)
    if not short_df.empty:
        short_df["has_historical_futstk_coverage"] = short_df["ticker"].isin(fut_symbols)
    missing_symbols = sorted(required_symbols - fut_symbols)

    stress_rows = []
    for borrow_annual in [0.02, 0.05, 0.10]:
        for slippage_bps in [10, 25, 50]:
            extra_cost = np.where(
                hedge_mask,
                0.20 * ((borrow_annual * events["holding_days"] / 365.0) + (slippage_bps / 10000.0)),
                0.0,
            )
            stressed_return = pd.Series(
                np.where(
                    hedge_mask,
                    1.20 * core - 0.20 * active - extra_cost,
                    0.90 * core + 0.10 * active,
                ),
                index=events.index,
            )
            detail = pd.DataFrame(score(events, folds, "tb14_short_cost_stress", stressed_return.reset_index(drop=True)))
            stress_rows.append(
                {
                    "borrow_annual": borrow_annual,
                    "short_slippage_bps": slippage_bps,
                    "mean_strategy_annualized": float(detail["strategy_annualized_return"].mean()),
                    "mean_rebalanced_benchmark_annualized": float(detail["rebalanced_benchmark_annualized_return"].mean()),
                    "mean_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].mean()),
                    "folds_beating_rebalanced_benchmark": int(detail["beats_rebalanced_benchmark"].sum()),
                    "min_excess_vs_rebalanced_benchmark_annualized": float(detail["excess_vs_rebalanced_benchmark_annualized"].min()),
                }
            )
    stress_df = pd.DataFrame(stress_rows)
    base_case = stress_df.loc[(stress_df["borrow_annual"] == 0.05) & (stress_df["short_slippage_bps"] == 25)].iloc[0]
    decision = "short_cost_stress_survives" if int(base_case["folds_beating_rebalanced_benchmark"]) >= 7 else "short_cost_stress_weakens_candidate"
    decision_df = pd.DataFrame(
        [
            {
                "audit_id": "TB14_step5_short_feasibility",
                "hedge_window_count": int(hedge_mask.sum()),
                "unique_short_symbols": int(len(required_symbols)),
                "symbols_with_historical_futstk_coverage": int(len(fut_symbols)),
                "symbols_missing_historical_futstk_coverage": "|".join(missing_symbols),
                "base_borrow_annual": 0.05,
                "base_short_slippage_bps": 25,
                "base_folds_beating_rebalanced_benchmark": int(base_case["folds_beating_rebalanced_benchmark"]),
                "base_mean_excess_vs_rebalanced_benchmark_annualized": float(base_case["mean_excess_vs_rebalanced_benchmark_annualized"]),
                "decision": decision,
                "note": "Historical FUTSTK coverage is not the same as live SLB borrow availability.",
            }
        ]
    )
    out_dir = ssell1.RESULTS_DIR / "signal_baseline"
    short_df.to_csv(out_dir / "tb14_step5_short_feasibility_hedge_names.csv", index=False)
    stress_df.to_csv(out_dir / "tb14_step5_short_feasibility_stress_summary.csv", index=False)
    decision_df.to_csv(out_dir / "tb14_step5_short_feasibility_decision.csv", index=False)
    print(decision_df.to_string(index=False))
    print(stress_df.to_string(index=False))


if __name__ == "__main__":
    main()
