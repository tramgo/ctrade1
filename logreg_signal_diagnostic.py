from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, roc_auc_score
except ImportError as exc:
    raise SystemExit(
        "scikit-learn is required for this diagnostic. Install it with "
        "`python -m pip install scikit-learn`."
    ) from exc


DEFAULT_GLOB = "results/eval_harness/rl_histories/history_rl_*_real_cost_on.csv"
FEATURE_COLUMNS = [
    "LagRet_1",
    "LagRet_5",
    "LagRet_20",
    "Trend_30",
    "Trend_2h",
    "Trend_slope",
    "RSI14",
    "MACD_z",
    "ATR20_log",
    "RealVol20_log",
    "MktRet_1",
    "MktRet_3",
    "MktRet_6",
    "StockMinusMkt_1",
    "StockMinusMkt_3",
    "SectorMinusMkt_3",
    "VWAP_Dist",
    "SessionOpenDist_ATR",
    "OpeningRangeBreakout",
    "TimeSinceNewHigh",
    "TimeSinceNewLow",
    "IntradayVolPercentile",
    "RelativeVolumeTime",
    "BodyToRange",
    "UpperWickRatio",
    "LowerWickRatio",
    "Breakout_3bar",
    "SignPersistence_5",
    "RetSkew_5",
    "CloseLocation_3",
    "MktVolRank",
    "VolRegime",
    "MinuteNorm",
    "RegimeBull",
    "RegimeBear",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test whether the current RL feature set has predictive power without RL."
    )
    parser.add_argument(
        "--glob",
        default=DEFAULT_GLOB,
        help=f"Glob pattern for RL history CSVs. Default: {DEFAULT_GLOB}",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=5,
        help="Prediction horizon in bars for the binary target.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.30,
        help="Chronological holdout size for the pooled train/test split.",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=2,
        help="Minimum number of input files required to run the diagnostic.",
    )
    return parser.parse_args()


def discover_files(pattern: str) -> List[Path]:
    files = sorted(Path(".").glob(pattern))
    return [path for path in files if path.is_file()]


def load_histories(files: Iterable[Path], horizon: int) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path)
        if df.empty or "Close" not in df.columns:
            continue
        df = df.copy()
        df["source_file"] = path.name
        df["ticker"] = df.get("ticker", path.name.split("_")[2] if "_" in path.name else "UNKNOWN")
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df["future_return"] = df["Close"].shift(-horizon) / df["Close"] - 1.0
        df["label"] = (df["future_return"] > 0).astype(int)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def choose_feature_columns(df: pd.DataFrame) -> List[str]:
    return [col for col in FEATURE_COLUMNS if col in df.columns]


def prepare_dataset(df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
    data = df.copy()
    numeric_cols = features + ["future_return", "label"]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=features + ["future_return", "label"]).reset_index(drop=True)
    return data


def fit_and_score(train_df: pd.DataFrame, test_df: pd.DataFrame, features: List[str]) -> dict:
    if train_df.empty or test_df.empty:
        return {
            "accuracy": np.nan,
            "roc_auc": np.nan,
            "samples_train": len(train_df),
            "samples_test": len(test_df),
            "positive_rate_test": np.nan,
        }

    y_train = train_df["label"]
    y_test = test_df["label"]
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(train_df[features], y_train)

    pred = model.predict(test_df[features])
    prob = model.predict_proba(test_df[features])[:, 1]

    if len(np.unique(y_test)) < 2:
        auc = np.nan
    else:
        auc = float(roc_auc_score(y_test, prob))

    return {
        "accuracy": float(accuracy_score(y_test, pred)),
        "roc_auc": auc,
        "samples_train": int(len(train_df)),
        "samples_test": int(len(test_df)),
        "positive_rate_test": float(y_test.mean()),
        "coefficients": pd.Series(model.coef_[0], index=features).sort_values(ascending=False),
    }


def pooled_split(data: pd.DataFrame, features: List[str], test_size: float) -> None:
    split_idx = max(1, int(len(data) * (1.0 - test_size)))
    train_df = data.iloc[:split_idx].copy()
    test_df = data.iloc[split_idx:].copy()
    result = fit_and_score(train_df, test_df, features)

    print("\nPooled chronological split")
    print(f"Train samples: {result['samples_train']}")
    print(f"Test samples:  {result['samples_test']}")
    print(f"Accuracy:      {result['accuracy']:.4f}")
    print(f"ROC AUC:       {result['roc_auc']:.4f}" if pd.notna(result["roc_auc"]) else "ROC AUC:       n/a")
    print(f"Test pos rate: {result['positive_rate_test']:.4f}")
    print("\nTop positive coefficients")
    print(result["coefficients"].head(8).to_string())
    print("\nTop negative coefficients")
    print(result["coefficients"].tail(8).sort_values().to_string())


def leave_one_ticker_out(data: pd.DataFrame, features: List[str]) -> None:
    tickers = sorted(data["ticker"].dropna().astype(str).unique())
    rows = []
    for ticker in tickers:
        train_df = data[data["ticker"] != ticker].copy()
        test_df = data[data["ticker"] == ticker].copy()
        result = fit_and_score(train_df, test_df, features)
        rows.append(
            {
                "ticker": ticker,
                "accuracy": result["accuracy"],
                "roc_auc": result["roc_auc"],
                "samples_test": result["samples_test"],
                "positive_rate_test": result["positive_rate_test"],
            }
        )

    if rows:
        print("\nLeave-one-ticker-out")
        print(pd.DataFrame(rows).sort_values("ticker").to_string(index=False))


def main() -> None:
    args = parse_args()
    files = discover_files(args.glob)
    if len(files) < args.min_files:
        raise SystemExit(
            f"Found only {len(files)} files for pattern '{args.glob}'. "
            f"Need at least {args.min_files} files."
        )

    df = load_histories(files, horizon=args.horizon)
    if df.empty:
        raise SystemExit("No usable RL history rows found.")

    features = choose_feature_columns(df)
    if not features:
        raise SystemExit("No matching feature columns found in the RL history files.")

    data = prepare_dataset(df, features)
    if data.empty:
        raise SystemExit("No usable rows remain after dropping NaNs.")

    print("Files used:", len(files))
    print("Rows used:", len(data))
    print("Tickers:", ", ".join(sorted(data["ticker"].dropna().astype(str).unique())))
    print("Horizon:", args.horizon)
    print("Features:", ", ".join(features))
    print("\nLabel balance")
    print(data["label"].value_counts(normalize=True).sort_index().rename(index={0: "down_or_flat", 1: "up"}).to_string())

    pooled_split(data, features, args.test_size)
    leave_one_ticker_out(data, features)


if __name__ == "__main__":
    main()
