import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression


FEATURES = [
    "RSI",
    "MACD",
    "ADX",
    "EMA20",
    "VWAP",
    "Lagged_Return",
    "Volatility",
    "Bollinger_Width",
]


def classify_sharpe(sharpe: float) -> str:
    if not np.isfinite(sharpe):
        return "invalid"
    if sharpe < 0.2:
        return "no_alpha_likely"
    if sharpe < 0.6:
        return "weak_alpha"
    if sharpe < 1.0:
        return "moderate_alpha"
    return "strong_alpha"


def run_single_ticker(csv_path: Path, test_size: float, rf_trees: int) -> list[dict]:
    df = pd.read_csv(csv_path)
    if "Close" not in df.columns:
        return []

    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        return []

    df = df.copy()
    df["target"] = df["Close"].pct_change().shift(-1)
    df = df.dropna(subset=FEATURES + ["target"]).reset_index(drop=True)
    if len(df) < 200:
        return []

    split_idx = int(len(df) * (1 - test_size))
    if split_idx <= 0 or split_idx >= len(df):
        return []

    x_train = df.loc[: split_idx - 1, FEATURES]
    y_train = df.loc[: split_idx - 1, "target"]
    x_test = df.loc[split_idx:, FEATURES]
    y_test = df.loc[split_idx:, "target"].values

    models = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=rf_trees, random_state=42, n_jobs=-1),
    }

    out = []
    for model_name, model in models.items():
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        signal = np.sign(pred)
        strategy_returns = signal * y_test

        mean_return = float(np.mean(strategy_returns))
        std_return = float(np.std(strategy_returns))
        sharpe = float(mean_return / std_return * np.sqrt(252)) if std_return > 0 else float("nan")
        hit_rate = float(np.mean(np.sign(y_test) == signal))

        out.append(
            {
                "ticker": csv_path.stem.replace("data_fetched_", ""),
                "model": model_name,
                "rows_total": len(df),
                "rows_train": len(x_train),
                "rows_test": len(x_test),
                "mean_daily_return": mean_return,
                "std_daily_return": std_return,
                "sharpe_annualized": sharpe,
                "hit_rate": hit_rate,
                "alpha_class": classify_sharpe(sharpe),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha sanity test: features -> next-day return.")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--tickers", nargs="*", default=None, help="Example: ICICIBANK.NS JYOTHYLAB.NS TATVA.NS")
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--rf-trees", type=int, default=200)
    parser.add_argument("--out-csv", default="results/alpha_feature_signal_report.csv")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if args.tickers:
        csv_files = [results_dir / f"data_fetched_{t}.csv" for t in args.tickers]
    else:
        csv_files = sorted(results_dir.glob("data_fetched_*.csv"))

    rows = []
    for csv_path in csv_files:
        if csv_path.exists():
            rows.extend(run_single_ticker(csv_path, test_size=args.test_size, rf_trees=args.rf_trees))

    if not rows:
        print("No usable ticker data found for alpha test.")
        return

    report = pd.DataFrame(rows).sort_values(["ticker", "model"]).reset_index(drop=True)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_csv, index=False)

    print("Saved:", out_csv)
    print(report.to_string(index=False))

    agg = (
        report.groupby("model", as_index=False)
        .agg(
            mean_sharpe=("sharpe_annualized", "mean"),
            median_sharpe=("sharpe_annualized", "median"),
            mean_hit_rate=("hit_rate", "mean"),
        )
        .sort_values("model")
    )
    print("\nAggregate:")
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
