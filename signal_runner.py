from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd
from pandas.errors import UndefinedVariableError

from signal_config import ExperimentDef, FEATURE_FAMILIES
from signal_metrics import (
    binary_metrics,
    multiclass_balanced_acc,
    safe_spearman,
    top_bottom_decile_stats,
)
from signal_models import make_model
from signal_targets import build_targets


EXPERIMENT_META_COLUMNS = {
    "ExperimentID",
    "TargetID",
    "ModelClass",
    "LabelType",
    "FeatureFamilies",
    "TrainWindowID",
    "TestWindowID",
    "Shuffled",
}


def _robust_experiment_summary(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if df.empty or "ExperimentID" not in df.columns:
        return pd.DataFrame()

    metric_cols = [col for col in df.columns if col not in EXPERIMENT_META_COLUMNS]
    summaries = []

    for experiment_id, group in df.groupby("ExperimentID"):
        grp = group.copy()
        rows_num = pd.to_numeric(grp.get("Rows"), errors="coerce")
        valid_row_sizes = rows_num.dropna()
        if not valid_row_sizes.empty:
            min_valid_rows = max(50.0, 0.5 * float(valid_row_sizes.median()))
            grp = grp.loc[rows_num >= min_valid_rows].copy()
            rows_num = pd.to_numeric(grp.get("Rows"), errors="coerce")
        if grp.empty:
            continue

        weights = rows_num.fillna(1.0).clip(lower=1.0)
        summary = {"ExperimentID": experiment_id, f"{prefix}_ValidFoldCount": float(len(grp))}
        for col in metric_cols:
            values = pd.to_numeric(grp[col], errors="coerce")
            mask = values.notna()
            if not mask.any():
                summary[f"{prefix}_{col}"] = np.nan
                continue
            w = weights.loc[mask]
            v = values.loc[mask]
            summary[f"{prefix}_{col}"] = float(np.average(v, weights=w))
        summaries.append(summary)

    return pd.DataFrame(summaries).set_index("ExperimentID") if summaries else pd.DataFrame()


def apply_regime_filter(df: pd.DataFrame, regime_filter: str | None) -> pd.DataFrame:
    if not regime_filter:
        return df
    try:
        return df.query(regime_filter).copy()
    except UndefinedVariableError:
        return df.copy()


def get_feature_columns(feature_family_names: List[str]) -> List[str]:
    cols: List[str] = []
    for family in feature_family_names:
        cols.extend(FEATURE_FAMILIES[family])
    return sorted(set(cols))


def trim_experiment_frame(df: pd.DataFrame, experiment: ExperimentDef) -> pd.DataFrame:
    feature_cols = get_feature_columns(experiment.feature_families)
    required_cols = {
        "Ticker",
        "Date",
        "WindowID",
        "Open",
        "High",
        "Low",
        "Close",
        "ATR20_log",
        "MktRet_1",
        "Trend_30",
        "Trend_2h",
        "StockMinusMkt_1",
        "StockMinusMkt_3",
        "Breakout_3bar",
        "SignPersistence_5",
        "XS_Rank_StockMinusMkt_3",
        "BreadthTrendPressure",
    }
    keep_cols = [col for col in sorted(required_cols.union(feature_cols)) if col in df.columns]
    return df[keep_cols].copy()


def get_target_column(experiment: ExperimentDef) -> Tuple[str, str]:
    horizon = experiment.horizon

    if experiment.target_id == "T1":
        if experiment.label_type == "regression":
            return f"net_fwd_ret_{horizon}", f"net_fwd_ret_{horizon}"
        return f"y_t1_dir_{horizon}", f"net_fwd_ret_{horizon}"

    if experiment.target_id == "T2":
        if experiment.label_type == "regression":
            return f"net_alpha_fwd_{horizon}", f"net_alpha_fwd_{horizon}"
        return f"y_t2_dir_{horizon}", f"net_alpha_fwd_{horizon}"

    if experiment.target_id == "T3":
        return f"y_t3_opp_{horizon}", f"opp_score_{horizon}"

    if experiment.target_id == "T4":
        if experiment.label_type == "binary":
            return f"y_t4_upfirst_{horizon}", f"net_fwd_ret_{horizon}"
        return f"y_t4_tb_{horizon}", f"net_fwd_ret_{horizon}"

    if experiment.target_id == "T6":
        return f"xs_rel_fwd_ret_{horizon}", f"xs_rel_fwd_ret_{horizon}"

    if experiment.target_id == "T7":
        return f"y_t7_target_before_stop_{horizon}", f"event_path_payoff_{horizon}"

    if experiment.target_id == "T8":
        return f"y_t8_clean_target_before_stop_{horizon}", f"clean_event_path_payoff_{horizon}"

    raise ValueError(f"Unknown target_id: {experiment.target_id}")


def ensure_experiment_targets(df: pd.DataFrame, experiment: ExperimentDef) -> pd.DataFrame:
    out = df.copy()
    if experiment.target_id == "T4" and experiment.label_type == "binary":
        source_col = f"y_t4_tb_{experiment.horizon}"
        target_col = f"y_t4_upfirst_{experiment.horizon}"
        if source_col in out.columns and target_col not in out.columns:
            source = pd.to_numeric(out[source_col], errors="coerce")
            out[target_col] = (source > 0).astype(int)
    return out


def prepare_xy(df: pd.DataFrame, feature_cols: List[str], y_col: str) -> Tuple[pd.DataFrame, pd.Series]:
    tmp = df[feature_cols + [y_col]].replace([np.inf, -np.inf], np.nan).dropna()
    return tmp[feature_cols], tmp[y_col]


def fit_predict(model, X_train, y_train, X_test, label_type: str) -> pd.Series:
    model.fit(X_train, y_train)

    if label_type == "regression":
        pred = model.predict(X_test)
        return pd.Series(pred, index=X_test.index, name="score")

    if label_type == "binary":
        if hasattr(model, "predict_proba"):
            pred = model.predict_proba(X_test)[:, 1]
        else:
            pred = model.predict(X_test)
        return pd.Series(pred, index=X_test.index, name="score")

    if label_type == "multiclass":
        pred = model.predict(X_test)
        return pd.Series(pred, index=X_test.index, name="score")

    raise ValueError(f"Unsupported label_type: {label_type}")


def evaluate_fold(
    df_test: pd.DataFrame,
    y_true: pd.Series,
    pred_score: pd.Series,
    experiment: ExperimentDef,
    realized_ret_col: str,
) -> dict:
    out = {"Rows": len(df_test)}
    realized = df_test.loc[pred_score.index, realized_ret_col]

    if experiment.label_type == "regression":
        out["IC_Spearman"] = safe_spearman(y_true, pred_score)
        out.update(
            top_bottom_decile_stats(
                pd.DataFrame({"score": pred_score, "ret": realized}),
                score_col="score",
                ret_col="ret",
            )
        )
        return out

    if experiment.label_type == "binary":
        out.update(binary_metrics(y_true, pred_score, threshold=0.5))
        out.update(
            top_bottom_decile_stats(
                pd.DataFrame({"score": pred_score, "ret": realized}),
                score_col="score",
                ret_col="ret",
            )
        )
        return out

    if experiment.label_type == "multiclass":
        out.update(multiclass_balanced_acc(y_true, pred_score))
        out["TradeCount"] = int((pred_score != 0).sum())
        return out

    raise ValueError(f"Unsupported label_type: {experiment.label_type}")


def shuffle_labels_within_ticker(
    df: pd.DataFrame,
    y_col: str,
    ticker_col: str = "Ticker",
    seed: int = 42,
) -> pd.DataFrame:
    out = df.copy()
    rng = np.random.default_rng(seed)
    for _, idx in out.groupby(ticker_col).groups.items():
        vals = out.loc[idx, y_col].to_numpy().copy()
        rng.shuffle(vals)
        out.loc[idx, y_col] = vals
    return out


def run_experiment(
    df: pd.DataFrame,
    experiment: ExperimentDef,
    train_window_ids: List[int],
    test_window_ids: List[int],
    shuffled: bool = False,
) -> pd.DataFrame:
    data = build_targets(trim_experiment_frame(df, experiment), horizon=experiment.horizon)
    data = ensure_experiment_targets(data, experiment)
    data = apply_regime_filter(data, experiment.regime_filter)

    feature_cols = [col for col in get_feature_columns(experiment.feature_families) if col in data.columns]
    if not feature_cols:
        return pd.DataFrame()

    y_col, realized_ret_col = get_target_column(experiment)
    if y_col not in data.columns or realized_ret_col not in data.columns:
        return pd.DataFrame()

    if shuffled:
        data = shuffle_labels_within_ticker(data, y_col=y_col)

    results = []
    for train_window_id, test_window_id in zip(train_window_ids, test_window_ids):
        train_df = data.loc[data["WindowID"] == train_window_id].copy()
        test_df = data.loc[data["WindowID"] == test_window_id].copy()
        if train_df.empty or test_df.empty:
            continue

        X_train, y_train = prepare_xy(train_df, feature_cols, y_col)
        X_test, y_test = prepare_xy(test_df, feature_cols, y_col)
        if len(X_train) < 50 or len(X_test) < 20:
            continue

        model_class = experiment.model_class
        if experiment.label_type == "binary" and model_class == "lgbm_reg":
            model_class = "lgbm_clf"

        try:
            model = make_model(model_class)
        except ImportError:
            continue
        pred_score = fit_predict(model, X_train, y_train, X_test, experiment.label_type)
        fold_metrics = evaluate_fold(
            df_test=test_df,
            y_true=y_test.loc[pred_score.index],
            pred_score=pred_score,
            experiment=experiment,
            realized_ret_col=realized_ret_col,
        )
        fold_metrics.update(
            {
                "ExperimentID": experiment.experiment_id,
                "TargetID": experiment.target_id,
                "ModelClass": experiment.model_class,
                "LabelType": experiment.label_type,
                "FeatureFamilies": "|".join(experiment.feature_families),
                "TrainWindowID": train_window_id,
                "TestWindowID": test_window_id,
                "Shuffled": shuffled,
            }
        )
        results.append(fold_metrics)

    return pd.DataFrame(results)


def run_experiment_predictions(
    df: pd.DataFrame,
    experiment: ExperimentDef,
    train_window_ids: List[int],
    test_window_ids: List[int],
) -> pd.DataFrame:
    data = build_targets(trim_experiment_frame(df, experiment), horizon=experiment.horizon)
    data = ensure_experiment_targets(data, experiment)
    data = apply_regime_filter(data, experiment.regime_filter)

    feature_cols = [col for col in get_feature_columns(experiment.feature_families) if col in data.columns]
    if not feature_cols:
        return pd.DataFrame()

    y_col, realized_ret_col = get_target_column(experiment)
    if y_col not in data.columns or realized_ret_col not in data.columns:
        return pd.DataFrame()

    prediction_rows = []
    base_cols = [col for col in ["Ticker", "Date", "WindowID"] if col in data.columns]

    for train_window_id, test_window_id in zip(train_window_ids, test_window_ids):
        train_df = data.loc[data["WindowID"] == train_window_id].copy()
        test_df = data.loc[data["WindowID"] == test_window_id].copy()
        if train_df.empty or test_df.empty:
            continue

        X_train, y_train = prepare_xy(train_df, feature_cols, y_col)
        X_test, y_test = prepare_xy(test_df, feature_cols, y_col)
        if len(X_train) < 50 or len(X_test) < 20:
            continue

        model_class = experiment.model_class
        if experiment.label_type == "binary" and model_class == "lgbm_reg":
            model_class = "lgbm_clf"

        try:
            model = make_model(model_class)
        except ImportError:
            continue

        pred_score = fit_predict(model, X_train, y_train, X_test, experiment.label_type)
        fold_df = test_df.loc[pred_score.index, base_cols].copy() if base_cols else pd.DataFrame(index=pred_score.index)
        fold_df["ExperimentID"] = experiment.experiment_id
        fold_df["TargetID"] = experiment.target_id
        fold_df["LabelType"] = experiment.label_type
        fold_df["ModelClass"] = experiment.model_class
        fold_df["FeatureFamilies"] = "|".join(experiment.feature_families)
        fold_df["TrainWindowID"] = train_window_id
        fold_df["TestWindowID"] = test_window_id
        fold_df["Prediction"] = pred_score.values
        fold_df["TargetValue"] = y_test.loc[pred_score.index].values
        fold_df["RealizedReturn"] = test_df.loc[pred_score.index, realized_ret_col].values
        prediction_rows.append(fold_df.reset_index(drop=True))

    return pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()


def summarize_real_vs_shuffled(real_df: pd.DataFrame, shuffled_df: pd.DataFrame) -> pd.DataFrame:
    if real_df.empty and shuffled_df.empty:
        return pd.DataFrame()

    if all(df.empty or "ExperimentID" not in df.columns for df in [real_df, shuffled_df]):
        return pd.DataFrame()

    real_summary = _robust_experiment_summary(real_df, prefix="Real")
    shuf_summary = _robust_experiment_summary(shuffled_df, prefix="Shuf")

    out = real_summary.join(shuf_summary, how="outer")
    for base_col in [
        "IC_Spearman",
        "TopDecile_NetRet",
        "Spread_TopBottom",
        "AUC",
        "BalancedAccuracy",
    ]:
        real_col = f"Real_{base_col}"
        shuf_col = f"Shuf_{base_col}"
        if real_col in out.columns and shuf_col in out.columns:
            out[f"Gap_{base_col}"] = out[real_col] - out[shuf_col]
    return out.reset_index()


def promote_signal(summary_row: pd.Series) -> bool:
    checks = []

    for col in [
        "Real_TopDecile_NetRet",
        "Gap_TopDecile_NetRet",
        "Real_Spread_TopBottom",
    ]:
        if col in summary_row and pd.notna(summary_row[col]):
            checks.append(summary_row[col] > 0)

    if "Gap_IC_Spearman" in summary_row and pd.notna(summary_row["Gap_IC_Spearman"]):
        checks.append(summary_row["Gap_IC_Spearman"] > 0)

    # Binary experiments should also beat shuffled on actual classification metrics.
    if "Real_AUC" in summary_row and pd.notna(summary_row["Real_AUC"]):
        checks.append(summary_row["Real_AUC"] > 0.5)
    if "Gap_AUC" in summary_row and pd.notna(summary_row["Gap_AUC"]):
        checks.append(summary_row["Gap_AUC"] > 0)
    if "Real_BalancedAccuracy" in summary_row and pd.notna(summary_row["Real_BalancedAccuracy"]):
        checks.append(summary_row["Real_BalancedAccuracy"] > 0.5)
    if "Gap_BalancedAccuracy" in summary_row and pd.notna(summary_row["Gap_BalancedAccuracy"]):
        checks.append(summary_row["Gap_BalancedAccuracy"] > 0)

    return all(checks) if checks else False


def make_adjacent_window_pairs(window_ids: List[int]) -> Tuple[List[int], List[int]]:
    ordered = sorted(set(window_ids))
    if len(ordered) < 2:
        return [], []
    return ordered[:-1], ordered[1:]
