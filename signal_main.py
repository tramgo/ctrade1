from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from signal_config import (
    ABLATION_GRID_EXPERIMENTS,
    CROSS_SECTIONAL_60M_EXPERIMENTS,
    DEFAULT_EXPERIMENTS,
    E004_SWEEP_EXPERIMENTS,
    E102_DEEPDIVE_EXPERIMENTS,
    GENERALIZATION_NEXT_EXPERIMENTS,
    GENERALIZATION_WAVE2_EXPERIMENTS,
    E302_SWEEP_EXPERIMENTS,
    E102_REGIME_EXPERIMENTS,
    FOCUSED_EXECUTION_EXPERIMENTS,
    GENERALIZATION_EXPERIMENTS,
    MARKET_STATE_60M_EXPERIMENTS,
    MULTISCALE_60M_EXPERIMENTS,
    NATIVE_15M_EXECUTION_EXPERIMENTS,
    NATIVE_15M_FAILED_BREAKOUT_EXPERIMENTS,
    NATIVE_15M_OPEN_DRIVE_EXPERIMENTS,
    NATIVE_15M_SESSION_PHASE_EXPERIMENTS,
    BREADTH_CONTEXT_60M_EXPERIMENTS,
    TIME_DISTRIBUTION_V2_EXPERIMENTS,
    INTRAHOUR_PATH_V1_EXPERIMENTS,
    PORTFOLIO_RANK_60M_EXPERIMENTS,
    SECOND_TIMEFRAME_60M_EXPERIMENTS,
    SETUP_REGIME_EXPERIMENTS,
    ExperimentDef,
)
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


def all_known_experiments() -> list[ExperimentDef]:
    ordered: list[ExperimentDef] = []
    seen: set[str] = set()
    for experiment in (
        list(DEFAULT_EXPERIMENTS)
        + list(FOCUSED_EXECUTION_EXPERIMENTS)
        + list(E004_SWEEP_EXPERIMENTS)
        + list(E102_DEEPDIVE_EXPERIMENTS)
        + list(ABLATION_GRID_EXPERIMENTS)
        + list(SETUP_REGIME_EXPERIMENTS)
        + list(MARKET_STATE_60M_EXPERIMENTS)
        + list(CROSS_SECTIONAL_60M_EXPERIMENTS)
        + list(PORTFOLIO_RANK_60M_EXPERIMENTS)
        + list(SECOND_TIMEFRAME_60M_EXPERIMENTS)
        + list(NATIVE_15M_EXECUTION_EXPERIMENTS)
        + list(NATIVE_15M_FAILED_BREAKOUT_EXPERIMENTS)
        + list(NATIVE_15M_OPEN_DRIVE_EXPERIMENTS)
        + list(NATIVE_15M_SESSION_PHASE_EXPERIMENTS)
        + list(BREADTH_CONTEXT_60M_EXPERIMENTS)
        + list(TIME_DISTRIBUTION_V2_EXPERIMENTS)
        + list(INTRAHOUR_PATH_V1_EXPERIMENTS)
        + list(GENERALIZATION_NEXT_EXPERIMENTS)
        + list(GENERALIZATION_WAVE2_EXPERIMENTS)
        + list(E302_SWEEP_EXPERIMENTS)
        + list(E102_REGIME_EXPERIMENTS)
        + list(GENERALIZATION_EXPERIMENTS)
    ):
        if experiment.experiment_id in seen:
            continue
        seen.add(experiment.experiment_id)
        ordered.append(experiment)
    return ordered


def resolve_experiment_pool(experiment_set: str) -> list[ExperimentDef]:
    if experiment_set == "default":
        return list(DEFAULT_EXPERIMENTS)
    if experiment_set == "focused":
        return list(FOCUSED_EXECUTION_EXPERIMENTS)
    if experiment_set == "generalization":
        return list(GENERALIZATION_EXPERIMENTS)
    if experiment_set == "e102_deepdive":
        return list(E102_DEEPDIVE_EXPERIMENTS)
    if experiment_set == "cross_sectional_60m":
        return list(CROSS_SECTIONAL_60M_EXPERIMENTS)
    if experiment_set == "ablation_grid":
        return list(ABLATION_GRID_EXPERIMENTS)
    if experiment_set == "setup_regimes":
        return list(SETUP_REGIME_EXPERIMENTS)
    if experiment_set == "market_state_60m":
        return list(MARKET_STATE_60M_EXPERIMENTS)
    if experiment_set == "multiscale_60m":
        return list(MULTISCALE_60M_EXPERIMENTS)
    if experiment_set == "native_15m_execution":
        return list(NATIVE_15M_EXECUTION_EXPERIMENTS)
    if experiment_set == "native_15m_failed_breakout":
        return list(NATIVE_15M_FAILED_BREAKOUT_EXPERIMENTS)
    if experiment_set == "native_15m_open_drive":
        return list(NATIVE_15M_OPEN_DRIVE_EXPERIMENTS)
    if experiment_set == "native_15m_session_phase":
        return list(NATIVE_15M_SESSION_PHASE_EXPERIMENTS)
    if experiment_set == "breadth_context_60m":
        return list(BREADTH_CONTEXT_60M_EXPERIMENTS)
    if experiment_set == "time_distribution_v2":
        return list(TIME_DISTRIBUTION_V2_EXPERIMENTS)
    if experiment_set == "portfolio_rank_60m":
        return list(PORTFOLIO_RANK_60M_EXPERIMENTS)
    if experiment_set == "second_timeframe_60m":
        return list(SECOND_TIMEFRAME_60M_EXPERIMENTS)
    if experiment_set == "intrahour_path_v1":
        return list(INTRAHOUR_PATH_V1_EXPERIMENTS)
    if experiment_set == "all_15m":
        return (
            list(DEFAULT_EXPERIMENTS)
            + list(E004_SWEEP_EXPERIMENTS)
            + list(E102_DEEPDIVE_EXPERIMENTS)
            + list(ABLATION_GRID_EXPERIMENTS)
            + list(SETUP_REGIME_EXPERIMENTS)
            + list(MARKET_STATE_60M_EXPERIMENTS)
            + list(CROSS_SECTIONAL_60M_EXPERIMENTS)
            + list(BREADTH_CONTEXT_60M_EXPERIMENTS)
            + list(MULTISCALE_60M_EXPERIMENTS)
            + list(PORTFOLIO_RANK_60M_EXPERIMENTS)
            + list(GENERALIZATION_NEXT_EXPERIMENTS)
            + list(GENERALIZATION_WAVE2_EXPERIMENTS)
            + list(E302_SWEEP_EXPERIMENTS)
            + list(E102_REGIME_EXPERIMENTS)
            + list(GENERALIZATION_EXPERIMENTS)
            + list(NATIVE_15M_EXECUTION_EXPERIMENTS)
            + list(NATIVE_15M_FAILED_BREAKOUT_EXPERIMENTS)
            + list(NATIVE_15M_OPEN_DRIVE_EXPERIMENTS)
            + list(NATIVE_15M_SESSION_PHASE_EXPERIMENTS)
        )
    if experiment_set == "generalization_next":
        return list(GENERALIZATION_NEXT_EXPERIMENTS)
    if experiment_set == "generalization_wave2":
        return list(GENERALIZATION_WAVE2_EXPERIMENTS)
    if experiment_set == "e302_sweep":
        return list(E302_SWEEP_EXPERIMENTS)
    if experiment_set == "e004_sweep":
        return list(E004_SWEEP_EXPERIMENTS)
    if experiment_set == "e102_regime":
        return list(E102_REGIME_EXPERIMENTS)
    if experiment_set == "two_track":
        return list(FOCUSED_EXECUTION_EXPERIMENTS) + list(GENERALIZATION_EXPERIMENTS)
    if experiment_set == "all":
        return (
            list(DEFAULT_EXPERIMENTS)
            + list(E004_SWEEP_EXPERIMENTS)
            + list(E102_DEEPDIVE_EXPERIMENTS)
            + list(ABLATION_GRID_EXPERIMENTS)
            + list(SETUP_REGIME_EXPERIMENTS)
            + list(MARKET_STATE_60M_EXPERIMENTS)
            + list(CROSS_SECTIONAL_60M_EXPERIMENTS)
            + list(BREADTH_CONTEXT_60M_EXPERIMENTS)
            + list(TIME_DISTRIBUTION_V2_EXPERIMENTS)
            + list(SECOND_TIMEFRAME_60M_EXPERIMENTS)
            + list(NATIVE_15M_EXECUTION_EXPERIMENTS)
            + list(NATIVE_15M_FAILED_BREAKOUT_EXPERIMENTS)
            + list(NATIVE_15M_OPEN_DRIVE_EXPERIMENTS)
            + list(NATIVE_15M_SESSION_PHASE_EXPERIMENTS)
            + list(INTRAHOUR_PATH_V1_EXPERIMENTS)
            + list(GENERALIZATION_NEXT_EXPERIMENTS)
            + list(GENERALIZATION_WAVE2_EXPERIMENTS)
            + list(E302_SWEEP_EXPERIMENTS)
            + list(E102_REGIME_EXPERIMENTS)
            + list(GENERALIZATION_EXPERIMENTS)
        )
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


def build_e302_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    e302_ids = {experiment.experiment_id for experiment in E302_SWEEP_EXPERIMENTS}
    e302_df = compare.loc[compare["ExperimentID"].isin(e302_ids)].copy()
    if e302_df.empty:
        return pd.DataFrame()
    e302_df["Eligible"] = (
        (pd.to_numeric(e302_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(e302_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(e302_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(e302_df.get("Real_TradeCount"), errors="coerce") >= 1000)
    )
    ranked = e302_df.loc[e302_df["Eligible"]].copy()
    if ranked.empty:
        e302_df["ShortlistRank"] = np.nan
        e302_df["StandalonePromoted"] = False
        return e302_df
    ranked = ranked.sort_values(
        ["Real_AUC", "Real_BalancedAccuracy", "Gap_Spread_TopBottom", "Real_Spread_TopBottom"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= 2
    out = e302_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_generalization_next_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E401": "T4_SetupQuality",
        "E402": "T4_SetupQuality",
        "E403": "T3_HighVol",
        "E404": "T3_HighVol",
        "E405": "T3_LowVol",
        "E406": "T3_LowVol",
        "E407": "SetupProxy",
        "E408": "SetupProxy",
    }
    next_ids = set(family_by_experiment)
    next_df = compare.loc[compare["ExperimentID"].isin(next_ids)].copy()
    if next_df.empty:
        return pd.DataFrame()
    next_df["Family"] = next_df["ExperimentID"].map(family_by_experiment)
    next_df["Eligible"] = (
        (pd.to_numeric(next_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(next_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(next_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(next_df.get("Real_TradeCount"), errors="coerce") >= 750)
    )
    ranked = next_df.loc[next_df["Eligible"]].copy()
    if ranked.empty:
        next_df["FamilyRank"] = np.nan
        next_df["ShortlistRank"] = np.nan
        next_df["StandalonePromoted"] = False
        return next_df
    ranked = ranked.sort_values(
        ["Gap_AUC", "Gap_BalancedAccuracy", "Real_AUC", "Real_Spread_TopBottom"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] == 1].copy()
    ranked = ranked.sort_values(
        ["Gap_AUC", "Gap_BalancedAccuracy", "Real_Spread_TopBottom"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= 3
    out = next_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_generalization_wave2_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E411": "SessionIsolation",
        "E412": "SessionIsolation",
        "E413": "SetupContinuation",
        "E414": "SetupPullback",
        "E415": "FailedBreakout",
        "E416": "RelativeCarry",
    }
    label_type_by_experiment = {
        "E411": "regression",
        "E412": "regression",
        "E413": "regression",
        "E414": "regression",
        "E415": "binary",
        "E416": "regression",
    }
    wave_ids = set(family_by_experiment)
    wave_df = compare.loc[compare["ExperimentID"].isin(wave_ids)].copy()
    if wave_df.empty:
        return pd.DataFrame()
    wave_df["Family"] = wave_df["ExperimentID"].map(family_by_experiment)
    wave_df["LabelTypeResolved"] = wave_df["ExperimentID"].map(label_type_by_experiment)
    auc = pd.to_numeric(wave_df.get("Gap_AUC"), errors="coerce")
    bal = pd.to_numeric(wave_df.get("Gap_BalancedAccuracy"), errors="coerce")
    ic = pd.to_numeric(wave_df.get("Gap_IC_Spearman"), errors="coerce")
    spread = pd.to_numeric(wave_df.get("Gap_Spread_TopBottom"), errors="coerce")
    trade_count = pd.to_numeric(wave_df.get("Real_TradeCount"), errors="coerce")
    binary_eligible = (auc > 0) & (bal > 0) & (spread >= -0.00025)
    regression_eligible = (ic > 0) & (spread >= -0.00025)
    wave_df["Eligible"] = (binary_eligible | regression_eligible) & (trade_count >= 500)
    ranked = wave_df.loc[wave_df["Eligible"]].copy()
    if ranked.empty:
        wave_df["FamilyRank"] = np.nan
        wave_df["ShortlistRank"] = np.nan
        wave_df["StandalonePromoted"] = False
        return wave_df
    ranked["BinaryScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked["RegressionScore"] = (
        pd.to_numeric(ranked.get("Gap_IC_Spearman"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_Spread_TopBottom"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked["SelectionScore"] = np.where(
        ranked["LabelTypeResolved"].eq("binary"),
        ranked["BinaryScore"],
        ranked["RegressionScore"],
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] == 1].copy()
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= 3
    out = wave_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_e102_deepdive_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E201": "Volatility",
        "E202": "Volatility",
        "E203": "VolatilityPlusPersistence",
        "E204": "VolatilityPlusPersistence",
        "E205": "Session",
        "E206": "Session",
        "E207": "SessionPlusPersistence",
        "E208": "SessionPlusPersistence",
        "E209": "TrendRegime",
        "E210": "TrendRegime",
        "E211": "TrendRegimePlusPersistence",
        "E212": "TrendRegimePlusPersistence",
    }
    deep_ids = set(family_by_experiment)
    deep_df = compare.loc[compare["ExperimentID"].isin(deep_ids)].copy()
    if deep_df.empty:
        return pd.DataFrame()
    deep_df["Family"] = deep_df["ExperimentID"].map(family_by_experiment)
    deep_df["Eligible"] = (
        (pd.to_numeric(deep_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(deep_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(deep_df.get("Gap_Spread_TopBottom"), errors="coerce") >= 0)
        & (pd.to_numeric(deep_df.get("Real_TradeCount"), errors="coerce") >= 600)
    )
    ranked = deep_df.loc[deep_df["Eligible"]].copy()
    if ranked.empty:
        deep_df["FamilyRank"] = np.nan
        deep_df["ShortlistRank"] = np.nan
        deep_df["StandalonePromoted"] = False
        return deep_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] == 1].copy()
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= 4
    out = deep_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_cross_sectional_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E501": "RelativeContinuation",
        "E502": "RelativeContinuation",
        "E503": "RelativeMeanReversion",
        "E504": "RelativeMeanReversion",
        "E505": "LeadershipPersistence",
        "E506": "LeadershipPersistence",
        "E507": "SectorSpread",
        "E508": "SectorSpread",
    }
    cross_ids = set(family_by_experiment)
    cross_df = compare.loc[compare["ExperimentID"].isin(cross_ids)].copy()
    if cross_df.empty:
        return pd.DataFrame()
    cross_df["Family"] = cross_df["ExperimentID"].map(family_by_experiment)
    cross_df["Eligible"] = (
        (pd.to_numeric(cross_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(cross_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(cross_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(cross_df.get("Real_TradeCount"), errors="coerce") >= 750)
    )
    ranked = cross_df.loc[cross_df["Eligible"]].copy()
    if ranked.empty:
        cross_df["FamilyRank"] = np.nan
        cross_df["ShortlistRank"] = np.nan
        cross_df["StandalonePromoted"] = False
        return cross_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] == 1].copy()
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= 3
    out = cross_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_ablation_grid_views(compare: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if compare.empty or "ExperimentID" not in compare.columns:
        empty = pd.DataFrame()
        return empty, empty, empty, empty
    experiment_meta = {experiment.experiment_id: experiment for experiment in ABLATION_GRID_EXPERIMENTS}
    grid_ids = set(experiment_meta)
    grid_df = compare.loc[compare["ExperimentID"].isin(grid_ids)].copy()
    if grid_df.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    grid_df["TargetFamily"] = grid_df["ExperimentID"].map(lambda exp_id: experiment_meta[exp_id].target_id)
    grid_df["FeatureCombo"] = grid_df["ExperimentID"].map(
        lambda exp_id: "+".join(experiment_meta[exp_id].feature_families)
    )
    grid_df["LabelTypeResolved"] = grid_df["ExperimentID"].map(lambda exp_id: experiment_meta[exp_id].label_type)
    grid_df["SelectionScore"] = np.where(
        grid_df["LabelTypeResolved"].eq("binary"),
        pd.to_numeric(grid_df.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(grid_df.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(grid_df.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0),
        pd.to_numeric(grid_df.get("Gap_IC_Spearman"), errors="coerce").fillna(0.0)
        + pd.to_numeric(grid_df.get("Gap_Spread_TopBottom"), errors="coerce").fillna(0.0)
        + pd.to_numeric(grid_df.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0),
    )
    grid_df["Eligible"] = np.where(
        grid_df["LabelTypeResolved"].eq("binary"),
        (
            (pd.to_numeric(grid_df.get("Gap_AUC"), errors="coerce") > 0)
            & (pd.to_numeric(grid_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
            & (pd.to_numeric(grid_df.get("Real_TradeCount"), errors="coerce") >= 500)
        ),
        (
            (pd.to_numeric(grid_df.get("Gap_IC_Spearman"), errors="coerce") > 0)
            & (pd.to_numeric(grid_df.get("Real_TradeCount"), errors="coerce") >= 500)
        ),
    )
    best_by_target = (
        grid_df.sort_values(["Eligible", "SelectionScore", "Real_Spread_TopBottom"], ascending=[False, False, False])
        .groupby("TargetFamily", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    best_by_family = (
        grid_df.sort_values(["Eligible", "SelectionScore", "Real_Spread_TopBottom"], ascending=[False, False, False])
        .groupby("FeatureCombo", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    shortlist = (
        grid_df.loc[grid_df["Eligible"]]
        .sort_values(["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"], ascending=[False, False, False])
        .reset_index(drop=True)
    )
    if not shortlist.empty:
        shortlist["ShortlistRank"] = np.arange(1, len(shortlist) + 1)
        shortlist["StandalonePromoted"] = shortlist["ShortlistRank"] <= min(4, len(shortlist))
    else:
        shortlist["ShortlistRank"] = pd.Series(dtype=float)
        shortlist["StandalonePromoted"] = pd.Series(dtype=bool)
    return grid_df, best_by_target, best_by_family, shortlist


def build_setup_regime_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E701": "S1_TrendContinuation",
        "E702": "S1_TrendContinuation",
        "E703": "S2_PullbackToTrend",
        "E704": "S3_MeanReversion",
        "E705": "S4_RelativeStrengthCarry",
        "E706": "S5_FailedBreakoutReversal",
    }
    setup_ids = set(family_by_experiment)
    setup_df = compare.loc[compare["ExperimentID"].isin(setup_ids)].copy()
    if setup_df.empty:
        return pd.DataFrame()
    setup_df["Family"] = setup_df["ExperimentID"].map(family_by_experiment)
    setup_df["Eligible"] = (
        (pd.to_numeric(setup_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(setup_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(setup_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(setup_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = setup_df.loc[setup_df["Eligible"]].copy()
    if ranked.empty:
        setup_df["FamilyRank"] = np.nan
        setup_df["ShortlistRank"] = np.nan
        setup_df["StandalonePromoted"] = False
        return setup_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] == 1].copy()
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = setup_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_market_state_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E801": "BullCalmOpportunity",
        "E802": "BullCalmSetup",
        "E803": "TransitionOpportunity",
        "E804": "TransitionSetup",
        "E805": "BearStressOpportunity",
        "E806": "BearStressSetup",
    }
    state_ids = set(family_by_experiment)
    state_df = compare.loc[compare["ExperimentID"].isin(state_ids)].copy()
    if state_df.empty:
        return pd.DataFrame()
    state_df["Family"] = state_df["ExperimentID"].map(family_by_experiment)
    state_df["Eligible"] = (
        (pd.to_numeric(state_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(state_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(state_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(state_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = state_df.loc[state_df["Eligible"]].copy()
    if ranked.empty:
        state_df["ShortlistRank"] = np.nan
        state_df["StandalonePromoted"] = False
        return state_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = state_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_multiscale_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E901": "AlignedOpportunity",
        "E902": "AlignedSetup",
        "E903": "CompressionOpportunity",
        "E904": "CompressionSetup",
        "E905": "ExpansionOpportunity",
        "E906": "ExpansionSetup",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_second_timeframe_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1101": "PathQuality",
        "E1102": "FailedBreakoutConfirm",
        "E1103": "StateVolContext",
        "E1104": "ExhaustionContext",
        "E1105": "ContinuationQuality",
        "E1106": "EntryEfficiency",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_intrahour_path_v1_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1201": "ContinuationPathQuality",
        "E1202": "BreakoutPersistencePath",
        "E1203": "FailedBreakoutRejection",
        "E1204": "StateAwarePath",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_breadth_context_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1301": "BreadthParticipation",
        "E1302": "BreadthExhaustion",
        "E1303": "BreadthDispersion",
        "E1304": "BreadthStateConfirmation",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_time_distribution_v2_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1401": "EarlyLateContinuation",
        "E1402": "LateConfirmationCandle",
        "E1403": "StateAwareTiming",
        "E1404": "RelativeTimingQuality",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_native_15m_execution_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1501": "Direct15mContinuation",
        "E1502": "Direct15mCandlePath",
        "E1503": "Direct15mRelativeBarrier",
        "E1504": "Direct15mStateAwareBarrier",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_native_15m_failed_breakout_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1601": "FailedUpsideBreakout",
        "E1602": "SessionAwareBreakoutFailure",
        "E1603": "RelativeFailedBreakout",
        "E1604": "StateAwareBreakoutFailure",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_native_15m_open_drive_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1701": "OpeningDriveCore",
        "E1702": "OpeningRangePersistence",
        "E1703": "RelativeOpenDrive",
        "E1704": "StateAwareOpenDrive",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_native_15m_session_phase_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1801": "EarlySessionDriveQuality",
        "E1802": "MidSessionContinuationVsFade",
        "E1803": "RelativeSessionPressure",
        "E1804": "LateSessionRepricing",
    }
    branch_ids = set(family_by_experiment)
    branch_df = compare.loc[compare["ExperimentID"].isin(branch_ids)].copy()
    if branch_df.empty:
        return pd.DataFrame()
    branch_df["Family"] = branch_df["ExperimentID"].map(family_by_experiment)
    branch_df["Eligible"] = (
        (pd.to_numeric(branch_df.get("Gap_AUC"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_BalancedAccuracy"), errors="coerce") > 0)
        & (pd.to_numeric(branch_df.get("Gap_Spread_TopBottom"), errors="coerce") >= -0.00025)
        & (pd.to_numeric(branch_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = branch_df.loc[branch_df["Eligible"]].copy()
    if ranked.empty:
        branch_df["ShortlistRank"] = np.nan
        branch_df["StandalonePromoted"] = False
        return branch_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_AUC"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = branch_df.merge(
        ranked[["ExperimentID", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_portfolio_rank_60m_shortlist(compare: pd.DataFrame) -> pd.DataFrame:
    if compare.empty or "ExperimentID" not in compare.columns:
        return pd.DataFrame()
    family_by_experiment = {
        "E1001": "RelativeContinuation",
        "E1002": "RelativeMeanReversion",
        "E1003": "SectorRelative",
        "E1004": "VolAdjMarketRelative",
        "E1005": "LeadershipPersistence",
        "E1006": "RegimeAwareRanking",
    }
    rank_ids = set(family_by_experiment)
    rank_df = compare.loc[compare["ExperimentID"].isin(rank_ids)].copy()
    if rank_df.empty:
        return pd.DataFrame()
    rank_df["Family"] = rank_df["ExperimentID"].map(family_by_experiment)
    rank_df["Eligible"] = (
        (pd.to_numeric(rank_df.get("Gap_IC_Spearman"), errors="coerce") > 0)
        & (pd.to_numeric(rank_df.get("Gap_Spread_TopBottom"), errors="coerce") > 0)
        & (pd.to_numeric(rank_df.get("Real_TradeCount"), errors="coerce") >= 500)
    )
    ranked = rank_df.loc[rank_df["Eligible"]].copy()
    if ranked.empty:
        rank_df["FamilyRank"] = np.nan
        rank_df["ShortlistRank"] = np.nan
        rank_df["StandalonePromoted"] = False
        return rank_df
    ranked["SelectionScore"] = (
        pd.to_numeric(ranked.get("Gap_IC_Spearman"), errors="coerce").fillna(0.0)
        + pd.to_numeric(ranked.get("Gap_Spread_TopBottom"), errors="coerce").fillna(0.0)
        + 0.25 * pd.to_numeric(ranked.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
    )
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["FamilyRank"] = ranked.groupby("Family").cumcount() + 1
    ranked = ranked.loc[ranked["FamilyRank"] <= 1].copy()
    ranked = ranked.sort_values(
        ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["ShortlistRank"] = np.arange(1, len(ranked) + 1)
    ranked["StandalonePromoted"] = ranked["ShortlistRank"] <= min(4, len(ranked))
    out = rank_df.merge(
        ranked[["ExperimentID", "FamilyRank", "ShortlistRank", "StandalonePromoted", "SelectionScore"]],
        on="ExperimentID",
        how="left",
    )
    out["StandalonePromoted"] = out["StandalonePromoted"].fillna(False)
    return out


def build_branch_comparison_rows_e102_deepdive(base_out_dir: Path, current_shortlist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sibling_dir = base_out_dir.parent
    benchmark_sources = [
        ("FocusedBenchmark", sibling_dir / "outputs_two_track" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E101", "E102", "E105"]),
        ("BroaderBenchmark", sibling_dir / "outputs_e302" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E325", "E329", "E302"]),
        ("Wave1Benchmark", sibling_dir / "outputs_generalization_next" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E401", "E407"]),
    ]
    metric_cols = [
        "ExperimentID",
        "Real_AUC",
        "Real_BalancedAccuracy",
        "Real_Spread_TopBottom",
        "Gap_AUC",
        "Gap_BalancedAccuracy",
        "Gap_Spread_TopBottom",
        "Real_TradeCount",
    ]
    for branch_label, csv_path, candidates in benchmark_sources:
        if not csv_path.exists():
            continue
        src = pd.read_csv(csv_path)
        src = src.loc[src["ExperimentID"].isin(candidates)].copy()
        if src.empty:
            continue
        src["SortScore"] = (
            pd.to_numeric(src.get("Gap_AUC"), errors="coerce").fillna(0.0)
            + pd.to_numeric(src.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
            + pd.to_numeric(src.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
        )
        src = src.sort_values(["SortScore"], ascending=[False]).head(1)
        row = {col: src.iloc[0][col] for col in metric_cols if col in src.columns}
        row["BranchLabel"] = branch_label
        row["Promoted"] = False
        rows.append(row)
    if not current_shortlist.empty:
        promoted = current_shortlist.loc[current_shortlist["StandalonePromoted"] == True].copy()
        for _, row_data in promoted.iterrows():
            row = {col: row_data.get(col) for col in metric_cols}
            row["BranchLabel"] = f"E102DeepDive_{row_data.get('Family', 'Candidate')}"
            row["Promoted"] = True
            rows.append(row)
    return pd.DataFrame(rows)


def build_branch_comparison_rows_cross_sectional(base_out_dir: Path, current_shortlist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sibling_dir = base_out_dir.parent
    benchmark_sources = [
        ("IncumbentResearch", sibling_dir / "outputs_e102_deepdive" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E209", "E211"]),
        ("BroaderBenchmark", sibling_dir / "outputs_e302" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E325", "E329", "E302"]),
        ("Wave1Benchmark", sibling_dir / "outputs_generalization_next" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E401", "E407"]),
    ]
    metric_cols = [
        "ExperimentID",
        "Real_AUC",
        "Real_BalancedAccuracy",
        "Real_Spread_TopBottom",
        "Gap_AUC",
        "Gap_BalancedAccuracy",
        "Gap_Spread_TopBottom",
        "Real_TradeCount",
    ]
    for branch_label, csv_path, candidates in benchmark_sources:
        if not csv_path.exists():
            continue
        src = pd.read_csv(csv_path)
        src = src.loc[src["ExperimentID"].isin(candidates)].copy()
        if src.empty:
            continue
        src["SortScore"] = (
            pd.to_numeric(src.get("Gap_AUC"), errors="coerce").fillna(0.0)
            + pd.to_numeric(src.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
            + pd.to_numeric(src.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
        )
        src = src.sort_values(["SortScore"], ascending=[False]).head(1)
        row = {col: src.iloc[0][col] for col in metric_cols if col in src.columns}
        row["BranchLabel"] = branch_label
        row["Promoted"] = False
        rows.append(row)
    if not current_shortlist.empty:
        promoted = current_shortlist.loc[current_shortlist["StandalonePromoted"] == True].copy()
        for _, row_data in promoted.iterrows():
            row = {col: row_data.get(col) for col in metric_cols}
            row["BranchLabel"] = f"CrossSectional60m_{row_data.get('Family', 'Candidate')}"
            row["Promoted"] = True
            rows.append(row)
    return pd.DataFrame(rows)


def build_branch_comparison_rows(base_out_dir: Path, current_shortlist: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    sibling_dir = base_out_dir.parent
    benchmark_sources = [
        ("FocusedBenchmark", sibling_dir / "outputs_two_track" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E102"]),
        ("BroaderBenchmark", sibling_dir / "outputs_e302" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E325", "E329", "E302"]),
    ]
    metric_cols = [
        "ExperimentID",
        "Real_AUC",
        "Real_BalancedAccuracy",
        "Real_Spread_TopBottom",
        "Gap_AUC",
        "Gap_BalancedAccuracy",
        "Gap_Spread_TopBottom",
        "Real_TradeCount",
    ]
    for branch_label, csv_path, candidates in benchmark_sources:
        if not csv_path.exists():
            continue
        src = pd.read_csv(csv_path)
        src = src.loc[src["ExperimentID"].isin(candidates)].copy()
        if src.empty:
            continue
        src = src.sort_values(
            ["Real_AUC", "Real_BalancedAccuracy", "Real_Spread_TopBottom"],
            ascending=[False, False, False],
        ).head(1)
        row = {col: src.iloc[0][col] for col in metric_cols if col in src.columns}
        row["BranchLabel"] = branch_label
        row["Promoted"] = False
        rows.append(row)
    if not current_shortlist.empty:
        promoted = current_shortlist.loc[current_shortlist["StandalonePromoted"] == True].copy()
        for _, row_data in promoted.iterrows():
            row = {col: row_data.get(col) for col in metric_cols}
            row["BranchLabel"] = f"GeneralizationNext_{row_data.get('Family', 'Candidate')}"
            row["Promoted"] = True
            rows.append(row)
    return pd.DataFrame(rows)


def build_branch_comparison_rows_wave2(base_out_dir: Path, current_shortlist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sibling_dir = base_out_dir.parent
    def _numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
        if col not in df.columns:
            return pd.Series(0.0, index=df.index, dtype=float)
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    benchmark_sources = [
        ("FocusedBenchmark", sibling_dir / "outputs_two_track" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E102"]),
        ("BroaderBenchmark", sibling_dir / "outputs_e302" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E325", "E329", "E302"]),
        ("Wave1Benchmark", sibling_dir / "outputs_generalization_next" / "latest" / "experiment_summary_real_vs_shuffled.csv", ["E401", "E407"]),
    ]
    metric_cols = [
        "ExperimentID",
        "LabelType",
        "Real_AUC",
        "Real_BalancedAccuracy",
        "Real_IC_Spearman",
        "Real_Spread_TopBottom",
        "Gap_AUC",
        "Gap_BalancedAccuracy",
        "Gap_IC_Spearman",
        "Gap_Spread_TopBottom",
        "Real_TradeCount",
    ]
    for branch_label, csv_path, candidates in benchmark_sources:
        if not csv_path.exists():
            continue
        src = pd.read_csv(csv_path)
        src = src.loc[src["ExperimentID"].isin(candidates)].copy()
        if src.empty:
            continue
        src["SortScore"] = (
            _numeric_series(src, "Gap_AUC")
            + _numeric_series(src, "Gap_BalancedAccuracy")
            + _numeric_series(src, "Gap_IC_Spearman")
            + _numeric_series(src, "Real_Spread_TopBottom")
        )
        src = src.sort_values(["SortScore"], ascending=[False]).head(1)
        row = {col: src.iloc[0][col] for col in metric_cols if col in src.columns}
        row["BranchLabel"] = branch_label
        row["Promoted"] = False
        rows.append(row)
    if not current_shortlist.empty:
        promoted = current_shortlist.loc[current_shortlist["StandalonePromoted"] == True].copy()
        for _, row_data in promoted.iterrows():
            row = {col: row_data.get(col) for col in metric_cols}
            row["BranchLabel"] = f"GeneralizationWave2_{row_data.get('Family', 'Candidate')}"
            row["Promoted"] = True
            rows.append(row)
    return pd.DataFrame(rows)


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
    if experiment_ids and not selected_experiments:
        selected_experiments = select_experiments(all_known_experiments(), experiment_ids=experiment_ids)
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
    e302_shortlist = build_e302_shortlist(compare)
    if not e302_shortlist.empty:
        e302_shortlist.to_csv(run_out_dir / "e302_shortlist_summary.csv", index=False)
        promoted_e302 = e302_shortlist.loc[e302_shortlist["StandalonePromoted"] == True, "ExperimentID"].tolist()
        (run_out_dir / "e302_promoted_ids.txt").write_text("\n".join(promoted_e302), encoding="utf-8")
    generalization_next_shortlist = build_generalization_next_shortlist(compare)
    if not generalization_next_shortlist.empty:
        generalization_next_shortlist.to_csv(run_out_dir / "generalization_next_shortlist_summary.csv", index=False)
        promoted_next = generalization_next_shortlist.loc[
            generalization_next_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "generalization_next_promoted_ids.txt").write_text(
            "\n".join(promoted_next),
            encoding="utf-8",
        )
        branch_comparison = build_branch_comparison_rows(base_out_dir, generalization_next_shortlist)
        if not branch_comparison.empty:
            branch_comparison.to_csv(run_out_dir / "generalization_next_branch_comparison.csv", index=False)
    generalization_wave2_shortlist = build_generalization_wave2_shortlist(compare)
    if not generalization_wave2_shortlist.empty:
        generalization_wave2_shortlist.to_csv(run_out_dir / "generalization_wave2_shortlist_summary.csv", index=False)
        promoted_wave2 = generalization_wave2_shortlist.loc[
            generalization_wave2_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "generalization_wave2_promoted_ids.txt").write_text(
            "\n".join(promoted_wave2),
            encoding="utf-8",
        )
        branch_comparison_wave2 = build_branch_comparison_rows_wave2(base_out_dir, generalization_wave2_shortlist)
        if not branch_comparison_wave2.empty:
            branch_comparison_wave2.to_csv(run_out_dir / "generalization_wave2_branch_comparison.csv", index=False)
    e102_deepdive_shortlist = build_e102_deepdive_shortlist(compare)
    if not e102_deepdive_shortlist.empty:
        e102_deepdive_shortlist.to_csv(run_out_dir / "e102_deepdive_shortlist_summary.csv", index=False)
        promoted_e102 = e102_deepdive_shortlist.loc[e102_deepdive_shortlist["StandalonePromoted"] == True, "ExperimentID"].tolist()
        (run_out_dir / "e102_deepdive_promoted_ids.txt").write_text("\n".join(promoted_e102), encoding="utf-8")
        branch_comparison_e102 = build_branch_comparison_rows_e102_deepdive(base_out_dir, e102_deepdive_shortlist)
        if not branch_comparison_e102.empty:
            branch_comparison_e102.to_csv(run_out_dir / "e102_deepdive_branch_comparison.csv", index=False)
    cross_sectional_shortlist = build_cross_sectional_60m_shortlist(compare)
    if not cross_sectional_shortlist.empty:
        cross_sectional_shortlist.to_csv(run_out_dir / "cross_sectional_60m_shortlist_summary.csv", index=False)
        promoted_cross = cross_sectional_shortlist.loc[
            cross_sectional_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "cross_sectional_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_cross),
            encoding="utf-8",
        )
        branch_comparison_cross = build_branch_comparison_rows_cross_sectional(
            base_out_dir,
            cross_sectional_shortlist,
        )
        if not branch_comparison_cross.empty:
            branch_comparison_cross.to_csv(run_out_dir / "cross_sectional_60m_branch_comparison.csv", index=False)
    setup_regime_shortlist = build_setup_regime_shortlist(compare)
    if not setup_regime_shortlist.empty:
        setup_regime_shortlist.to_csv(run_out_dir / "setup_regime_shortlist_summary.csv", index=False)
        promoted_setup = setup_regime_shortlist.loc[
            setup_regime_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "setup_regime_promoted_ids.txt").write_text(
            "\n".join(promoted_setup),
            encoding="utf-8",
        )
    market_state_shortlist = build_market_state_60m_shortlist(compare)
    if not market_state_shortlist.empty:
        market_state_shortlist.to_csv(run_out_dir / "market_state_60m_shortlist_summary.csv", index=False)
        promoted_state = market_state_shortlist.loc[
            market_state_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "market_state_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_state),
            encoding="utf-8",
        )
    multiscale_shortlist = build_multiscale_60m_shortlist(compare)
    if not multiscale_shortlist.empty:
        multiscale_shortlist.to_csv(run_out_dir / "multiscale_60m_shortlist_summary.csv", index=False)
        promoted_multiscale = multiscale_shortlist.loc[
            multiscale_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "multiscale_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_multiscale),
            encoding="utf-8",
        )
    second_timeframe_shortlist = build_second_timeframe_60m_shortlist(compare)
    if not second_timeframe_shortlist.empty:
        second_timeframe_shortlist.to_csv(run_out_dir / "second_timeframe_60m_shortlist_summary.csv", index=False)
        promoted_second_tf = second_timeframe_shortlist.loc[
            second_timeframe_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "second_timeframe_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_second_tf),
            encoding="utf-8",
        )
    intrahour_path_shortlist = build_intrahour_path_v1_shortlist(compare)
    if not intrahour_path_shortlist.empty:
        intrahour_path_shortlist.to_csv(run_out_dir / "intrahour_path_v1_shortlist_summary.csv", index=False)
        promoted_intrahour = intrahour_path_shortlist.loc[
            intrahour_path_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "intrahour_path_v1_promoted_ids.txt").write_text(
            "\n".join(promoted_intrahour),
            encoding="utf-8",
        )
    breadth_context_shortlist = build_breadth_context_60m_shortlist(compare)
    if not breadth_context_shortlist.empty:
        breadth_context_shortlist.to_csv(run_out_dir / "breadth_context_60m_shortlist_summary.csv", index=False)
        promoted_breadth = breadth_context_shortlist.loc[
            breadth_context_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "breadth_context_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_breadth),
            encoding="utf-8",
        )
    time_distribution_shortlist = build_time_distribution_v2_shortlist(compare)
    if not time_distribution_shortlist.empty:
        time_distribution_shortlist.to_csv(run_out_dir / "time_distribution_v2_shortlist_summary.csv", index=False)
        promoted_time_distribution = time_distribution_shortlist.loc[
            time_distribution_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "time_distribution_v2_promoted_ids.txt").write_text(
            "\n".join(promoted_time_distribution),
            encoding="utf-8",
        )
    native_15m_shortlist = build_native_15m_execution_shortlist(compare)
    if not native_15m_shortlist.empty:
        native_15m_shortlist.to_csv(run_out_dir / "native_15m_execution_shortlist_summary.csv", index=False)
        promoted_native_15m = native_15m_shortlist.loc[
            native_15m_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "native_15m_execution_promoted_ids.txt").write_text(
            "\n".join(promoted_native_15m),
            encoding="utf-8",
        )
    native_15m_failed_breakout_shortlist = build_native_15m_failed_breakout_shortlist(compare)
    if not native_15m_failed_breakout_shortlist.empty:
        native_15m_failed_breakout_shortlist.to_csv(
            run_out_dir / "native_15m_failed_breakout_shortlist_summary.csv",
            index=False,
        )
        promoted_native_15m_failed_breakout = native_15m_failed_breakout_shortlist.loc[
            native_15m_failed_breakout_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "native_15m_failed_breakout_promoted_ids.txt").write_text(
            "\n".join(promoted_native_15m_failed_breakout),
            encoding="utf-8",
        )
    native_15m_open_drive_shortlist = build_native_15m_open_drive_shortlist(compare)
    if not native_15m_open_drive_shortlist.empty:
        native_15m_open_drive_shortlist.to_csv(
            run_out_dir / "native_15m_open_drive_shortlist_summary.csv",
            index=False,
        )
        promoted_native_15m_open_drive = native_15m_open_drive_shortlist.loc[
            native_15m_open_drive_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "native_15m_open_drive_promoted_ids.txt").write_text(
            "\n".join(promoted_native_15m_open_drive),
            encoding="utf-8",
        )
    native_15m_session_phase_shortlist = build_native_15m_session_phase_shortlist(compare)
    if not native_15m_session_phase_shortlist.empty:
        native_15m_session_phase_shortlist.to_csv(
            run_out_dir / "native_15m_session_phase_shortlist_summary.csv",
            index=False,
        )
        promoted_native_15m_session_phase = native_15m_session_phase_shortlist.loc[
            native_15m_session_phase_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "native_15m_session_phase_promoted_ids.txt").write_text(
            "\n".join(promoted_native_15m_session_phase),
            encoding="utf-8",
        )
    portfolio_rank_shortlist = build_portfolio_rank_60m_shortlist(compare)
    if not portfolio_rank_shortlist.empty:
        portfolio_rank_shortlist.to_csv(run_out_dir / "portfolio_rank_60m_shortlist.csv", index=False)
        portfolio_rank_summary = portfolio_rank_shortlist.sort_values(
            ["SelectionScore", "Real_Spread_TopBottom", "Real_TradeCount"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        portfolio_rank_summary.to_csv(run_out_dir / "portfolio_rank_60m_summary.csv", index=False)
        promoted_portfolio_rank = portfolio_rank_shortlist.loc[
            portfolio_rank_shortlist["StandalonePromoted"] == True, "ExperimentID"
        ].tolist()
        (run_out_dir / "portfolio_rank_60m_promoted_ids.txt").write_text(
            "\n".join(promoted_portfolio_rank),
            encoding="utf-8",
        )
        if not predictions_all.empty:
            rank_history = predictions_all.loc[
                predictions_all["ExperimentID"].isin(set(portfolio_rank_shortlist["ExperimentID"].tolist()))
            ].copy()
            if not rank_history.empty and "Prediction" in rank_history.columns and "Date" in rank_history.columns:
                rank_history["Date"] = pd.to_datetime(rank_history["Date"], errors="coerce")
                rank_history["RankPct"] = rank_history.groupby(["ExperimentID", "Date"])["Prediction"].rank(
                    method="average", pct=True
                )
                rank_history["RankOrder"] = rank_history.groupby(["ExperimentID", "Date"])["Prediction"].rank(
                    method="first", ascending=False
                )
                rank_history.to_csv(run_out_dir / "portfolio_rank_60m_rank_history.csv", index=False)
    ablation_grid_summary, ablation_best_by_target, ablation_best_by_family, ablation_shortlist = build_ablation_grid_views(compare)
    if not ablation_grid_summary.empty:
        ablation_grid_summary.to_csv(run_out_dir / "ablation_grid_summary.csv", index=False)
        ablation_best_by_target.to_csv(run_out_dir / "ablation_best_by_target.csv", index=False)
        ablation_best_by_family.to_csv(run_out_dir / "ablation_best_by_family.csv", index=False)
        ablation_shortlist.to_csv(run_out_dir / "ablation_shortlist.csv", index=False)
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
        choices=["default", "focused", "generalization", "generalization_next", "generalization_wave2", "e102_deepdive", "cross_sectional_60m", "ablation_grid", "setup_regimes", "market_state_60m", "multiscale_60m", "second_timeframe_60m", "intrahour_path_v1", "breadth_context_60m", "time_distribution_v2", "portfolio_rank_60m", "e302_sweep", "two_track", "e004_sweep", "e102_regime", "all"],
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
