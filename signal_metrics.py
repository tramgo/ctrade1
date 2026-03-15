from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from scipy.stats import spearmanr
except ImportError:
    spearmanr = None


def safe_spearman(y_true: pd.Series, y_pred: pd.Series) -> float:
    mask = y_true.notna() & y_pred.notna()
    if mask.sum() < 5:
        return np.nan
    if spearmanr is not None:
        val, _ = spearmanr(y_true[mask], y_pred[mask])
        return float(val) if np.isfinite(val) else np.nan
    ranked = pd.Series(y_true[mask]).rank().corr(pd.Series(y_pred[mask]).rank())
    return float(ranked) if ranked is not None and np.isfinite(ranked) else np.nan


def top_bottom_decile_stats(
    df: pd.DataFrame,
    score_col: str,
    ret_col: str,
) -> dict:
    tmp = df[[score_col, ret_col]].dropna().copy()
    if len(tmp) < 20:
        return {
            "TopDecile_NetRet": np.nan,
            "BottomDecile_NetRet": np.nan,
            "Spread_TopBottom": np.nan,
            "TradeCount": len(tmp),
        }

    tmp["rank_pct"] = tmp[score_col].rank(pct=True, method="average")
    top = tmp.loc[tmp["rank_pct"] >= 0.90, ret_col]
    bottom = tmp.loc[tmp["rank_pct"] <= 0.10, ret_col]

    top_ret = float(top.mean()) if len(top) else np.nan
    bottom_ret = float(bottom.mean()) if len(bottom) else np.nan
    spread = top_ret - bottom_ret if np.isfinite(top_ret) and np.isfinite(bottom_ret) else np.nan
    return {
        "TopDecile_NetRet": top_ret,
        "BottomDecile_NetRet": bottom_ret,
        "Spread_TopBottom": spread,
        "TradeCount": len(tmp),
    }


def binary_metrics(y_true: pd.Series, prob: pd.Series, threshold: float = 0.5) -> dict:
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score

    mask = y_true.notna() & prob.notna()
    if mask.sum() < 10:
        return {"AUC": np.nan, "BalancedAccuracy": np.nan}

    yt = y_true[mask].astype(int)
    yp = prob[mask]
    pred_label = (yp >= threshold).astype(int)

    auc = np.nan
    if yt.nunique() > 1:
        auc = roc_auc_score(yt, yp)
    bal_acc = balanced_accuracy_score(yt, pred_label)
    return {
        "AUC": float(auc) if np.isfinite(auc) else np.nan,
        "BalancedAccuracy": float(bal_acc),
    }


def multiclass_balanced_acc(y_true: pd.Series, y_pred: pd.Series) -> dict:
    from sklearn.metrics import balanced_accuracy_score

    mask = y_true.notna() & y_pred.notna()
    if mask.sum() < 10:
        return {"BalancedAccuracy": np.nan}
    val = balanced_accuracy_score(y_true[mask], y_pred[mask])
    return {"BalancedAccuracy": float(val)}
