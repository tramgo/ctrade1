from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from signal_config import DEFAULT_EXPERIMENTS, E004_SWEEP_EXPERIMENTS, ExperimentDef
from signal_runner import (
    make_adjacent_window_pairs,
    promote_signal,
    run_experiment,
    run_experiment_predictions,
    summarize_real_vs_shuffled,
)


def load_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.sort_values(["Ticker", "Date"]).reset_index(drop=True)


def select_experiments(
    experiments: Sequence[ExperimentDef],
    experiment_ids: Iterable[str] | None = None,
) -> list[ExperimentDef]:
    if not experiment_ids:
        return list(experiments)
    wanted = {exp_id.strip() for exp_id in experiment_ids if exp_id.strip()}
    return [experiment for experiment in experiments if experiment.experiment_id in wanted]


def resolve_experiment_pool(experiment_set: str) -> list[ExperimentDef]:
    if experiment_set == "default":
        return list(DEFAULT_EXPERIMENTS)
    if experiment_set == "e004_sweep":
        return list(E004_SWEEP_EXPERIMENTS)
    if experiment_set == "all":
        return list(DEFAULT_EXPERIMENTS) + list(E004_SWEEP_EXPERIMENTS)
    raise ValueError(f"Unsupported experiment set: {experiment_set}")


def build_window_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Ticker" not in df.columns or "WindowID" not in df.columns:
        return pd.DataFrame()
    out = (
        df.groupby(["Ticker", "WindowID"])
        .size()
        .reset_index(name="Rows")
        .sort_values(["Ticker", "WindowID"])
        .reset_index(drop=True)
    )
    return out


def build_target_sanity(df: pd.DataFrame, horizons: Sequence[int]) -> pd.DataFrame:
    rows = []
    for horizon in sorted(set(int(h) for h in horizons)):
        row = {"Horizon": horizon}
        for col in [
            f"raw_fwd_ret_{horizon}",
            f"net_fwd_ret_{horizon}",
            f"alpha_fwd_{horizon}",
            f"net_alpha_fwd_{horizon}",
            f"opp_score_{horizon}",
            f"est_cost_{horizon}",
        ]:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors="coerce")
                row[f"{col}_mean"] = float(series.mean())
                row[f"{col}_median"] = float(series.median())
        rows.append(row)
    return pd.DataFrame(rows)


def make_run_output_dir(base_out_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_out_dir / f"run_{timestamp}"


def refresh_latest_dir(base_out_dir: Path, run_dir: Path) -> Path:
    latest_dir = base_out_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    return latest_dir


def run_signal_pipeline(
    df: pd.DataFrame,
    out_dir: Path,
    experiments=DEFAULT_EXPERIMENTS,
    experiment_ids: Sequence[str] | None = None,
    max_window_pairs: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from signal_targets import build_targets

    base_out_dir = out_dir
    run_out_dir = make_run_output_dir(base_out_dir)
    run_out_dir.mkdir(parents=True, exist_ok=True)
    train_window_ids, test_window_ids = make_adjacent_window_pairs(df["WindowID"].dropna().astype(int).tolist())
    if max_window_pairs is not None and max_window_pairs > 0:
        train_window_ids = train_window_ids[:max_window_pairs]
        test_window_ids = test_window_ids[:max_window_pairs]

    selected_experiments = select_experiments(experiments, experiment_ids=experiment_ids)
    if not selected_experiments:
        raise ValueError("No experiments selected for signal pipeline run.")

    window_diag = build_window_diagnostics(df)
    window_diag.to_csv(run_out_dir / "window_diagnostics.csv", index=False)

    target_preview = df.copy()
    for horizon in sorted({experiment.horizon for experiment in selected_experiments}):
        target_preview = build_targets(target_preview, horizon=horizon)
    target_sanity = build_target_sanity(target_preview, [experiment.horizon for experiment in selected_experiments])
    target_sanity.to_csv(run_out_dir / "target_sanity.csv", index=False)

    all_real = []
    all_shuffled = []
    all_predictions = []
    for experiment in selected_experiments:
        real_df = run_experiment(
            df=df,
            experiment=experiment,
            train_window_ids=train_window_ids,
            test_window_ids=test_window_ids,
            shuffled=False,
        )
        shuffled_df = run_experiment(
            df=df,
            experiment=experiment,
            train_window_ids=train_window_ids,
            test_window_ids=test_window_ids,
            shuffled=True,
        )
        if not real_df.empty:
            all_real.append(real_df)
        if not shuffled_df.empty:
            all_shuffled.append(shuffled_df)
        pred_df = run_experiment_predictions(
            df=df,
            experiment=experiment,
            train_window_ids=train_window_ids,
            test_window_ids=test_window_ids,
        )
        if not pred_df.empty:
            all_predictions.append(pred_df)

    real_all = pd.concat(all_real, ignore_index=True) if all_real else pd.DataFrame()
    shuffled_all = pd.concat(all_shuffled, ignore_index=True) if all_shuffled else pd.DataFrame()
    predictions_all = pd.concat(all_predictions, ignore_index=True) if all_predictions else pd.DataFrame()
    compare = summarize_real_vs_shuffled(real_all, shuffled_all)

    if not compare.empty:
        compare["PromotedToRL"] = compare.apply(promote_signal, axis=1)

    real_all.to_csv(run_out_dir / "experiment_results_real.csv", index=False)
    shuffled_all.to_csv(run_out_dir / "experiment_results_shuffled.csv", index=False)
    compare.to_csv(run_out_dir / "experiment_summary_real_vs_shuffled.csv", index=False)
    predictions_all.to_csv(run_out_dir / "experiment_predictions_oos.csv", index=False)
    if not compare.empty and not predictions_all.empty:
        promoted_ids = set(compare.loc[compare["PromotedToRL"] == True, "ExperimentID"].tolist())
        promoted_predictions = predictions_all.loc[predictions_all["ExperimentID"].isin(promoted_ids)].copy()
        promoted_predictions.to_csv(run_out_dir / "promoted_predictions_oos.csv", index=False)
    refresh_latest_dir(base_out_dir, run_out_dir)
    return real_all, shuffled_all, compare


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run signal research experiments.")
    parser.add_argument("--data", required=True, help="Path to research dataset CSV")
    parser.add_argument(
        "--out-dir",
        default="signal_research_outputs",
        help="Output directory for experiment artifacts",
    )
    parser.add_argument(
        "--experiments",
        nargs="*",
        default=None,
        help="Optional list of experiment IDs to run, e.g. E001 E003 E004",
    )
    parser.add_argument(
        "--experiment-set",
        choices=["default", "e004_sweep", "all"],
        default="default",
        help="Named experiment bundle to use before optional --experiments filtering.",
    )
    parser.add_argument(
        "--max-window-pairs",
        type=int,
        default=None,
        help="Optional cap on adjacent train/test window pairs for smoke tests.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    df = load_dataset(args.data)
    experiment_pool = resolve_experiment_pool(args.experiment_set)
    _, _, compare = run_signal_pipeline(
        df=df,
        out_dir=Path(args.out_dir),
        experiments=experiment_pool,
        experiment_ids=args.experiments,
        max_window_pairs=args.max_window_pairs,
    )
    print(f"Saved outputs under {Path(args.out_dir).resolve()}")
    print(f"Latest outputs at {(Path(args.out_dir) / 'latest').resolve()}")
    if not compare.empty:
        promoted = compare.loc[compare["PromotedToRL"] == True, "ExperimentID"].tolist()
        print(f"Promoted experiments: {promoted}")


if __name__ == "__main__":
    main()
