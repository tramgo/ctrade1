from __future__ import annotations

import argparse
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import gymnasium as gym
import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:
    raise SystemExit(
        "scikit-learn is required for signal_gate_env.py. "
        "Install it with `python -m pip install scikit-learn`."
    ) from exc

from ssell1 import (
    FEATURES_TO_SCALE,
    RANDOM_SEED,
    SingleStockTradingEnv,
    get_data_kite,
    get_instrument_token,
    instrument_df,
    kite,
)


BASE_DIR = Path(".").resolve()
RESULTS_DIR = BASE_DIR / "results" / "signal_gate"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SignalGateConfig:
    interval: str = "60minute"
    history_days: int = 1095
    horizon_bars: int = 3
    positive_threshold: float = 0.55
    negative_threshold: float = 0.55
    min_move_threshold: float = 0.0
    max_train_rows_per_ticker: Optional[int] = None
    train_ratio: float = 0.80
    class_weight: str = "balanced"
    max_iter: int = 1000
    output_dir: Path = RESULTS_DIR


class SignalGateModel:
    def __init__(self, feature_columns: list[str], pipeline: Pipeline, metadata: dict):
        self.feature_columns = feature_columns
        self.pipeline = pipeline
        self.metadata = metadata

    def predict_proba_up(self, rows: pd.DataFrame) -> np.ndarray:
        if rows.empty:
            return np.asarray([], dtype=float)
        x = rows[self.feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        return self.pipeline.predict_proba(x)[:, 1]

    def predict_probabilities(self, rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        prob_up = self.predict_proba_up(rows)
        return prob_up, 1.0 - prob_up

    def save(self, path: Path) -> None:
        payload = {
            "feature_columns": self.feature_columns,
            "pipeline": self.pipeline,
            "metadata": self.metadata,
        }
        with path.open("wb") as fh:
            pickle.dump(payload, fh)

    @classmethod
    def load(cls, path: Path) -> "SignalGateModel":
        with path.open("rb") as fh:
            payload = pickle.load(fh)
        return cls(
            feature_columns=list(payload["feature_columns"]),
            pipeline=payload["pipeline"],
            metadata=dict(payload.get("metadata", {})),
        )


def load_engineered_data_for_ticker(
    ticker: str,
    config: SignalGateConfig,
) -> pd.DataFrame:
    token = get_instrument_token(ticker, instrument_df)
    if token is None:
        raise ValueError(f"Instrument token not found for {ticker}")

    df = get_data_kite(
        kite=kite,
        instrument_token=token,
        days=config.history_days,
        interval=config.interval,
        include_relative_context=True,
    )
    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")

    df = df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date").reset_index(drop=True)
    df["Ticker"] = ticker
    return df


def build_binary_target(
    df: pd.DataFrame,
    horizon_bars: int,
    min_move_threshold: float,
) -> pd.DataFrame:
    out = df.copy()
    out["future_return"] = pd.to_numeric(out["Close"], errors="coerce").shift(-horizon_bars) / pd.to_numeric(
        out["Close"], errors="coerce"
    ) - 1.0
    if min_move_threshold > 0.0:
        eligible = out["future_return"].abs() >= min_move_threshold
        out = out.loc[eligible].copy()
    out["label_up"] = (out["future_return"] > 0.0).astype(int)
    return out


def choose_feature_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in FEATURES_TO_SCALE if col in df.columns]


def build_training_frame(
    tickers: Iterable[str],
    config: SignalGateConfig,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        df = load_engineered_data_for_ticker(ticker, config)
        df = build_binary_target(df, config.horizon_bars, config.min_move_threshold)
        if config.max_train_rows_per_ticker is not None and len(df) > config.max_train_rows_per_ticker:
            df = df.iloc[-config.max_train_rows_per_ticker :].copy()
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    if "Date" in combined.columns:
        combined = combined.sort_values(["Date", "Ticker"]).reset_index(drop=True)
    return combined


def prepare_training_data(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    data = df.copy()
    numeric_cols = feature_columns + ["future_return", "label_up", "Close"]
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=feature_columns + ["future_return", "label_up"]).reset_index(drop=True)
    return data


def split_chronological(
    df: pd.DataFrame,
    train_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), df.copy()
    split_idx = max(1, int(len(df) * train_ratio))
    split_idx = min(split_idx, len(df) - 1)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    return train_df, test_df


def fit_signal_gate(
    df: pd.DataFrame,
    config: SignalGateConfig,
    feature_columns: Optional[list[str]] = None,
) -> tuple[SignalGateModel, dict]:
    if df.empty:
        raise ValueError("Training dataframe is empty.")

    working_df = df.copy()
    if "future_return" not in working_df.columns or "label_up" not in working_df.columns:
        working_df = build_binary_target(
            working_df,
            horizon_bars=config.horizon_bars,
            min_move_threshold=config.min_move_threshold,
        )

    feature_columns = feature_columns or choose_feature_columns(working_df)
    if not feature_columns:
        raise ValueError("No feature columns available for signal gate training.")

    data = prepare_training_data(working_df, feature_columns)
    if data.empty:
        raise ValueError("No usable rows remain after cleaning the training data.")

    train_df, test_df = split_chronological(data, config.train_ratio)
    x_train = train_df[feature_columns]
    y_train = train_df["label_up"]
    x_test = test_df[feature_columns]
    y_test = test_df["label_up"]

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "logreg",
                LogisticRegression(
                    max_iter=config.max_iter,
                    class_weight=config.class_weight,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)

    prob_test = pipeline.predict_proba(x_test)[:, 1]
    pred_test = (prob_test >= 0.5).astype(int)
    metrics = {
        "samples_train": int(len(train_df)),
        "samples_test": int(len(test_df)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "accuracy": float(accuracy_score(y_test, pred_test)),
        "roc_auc": float(roc_auc_score(y_test, prob_test)) if len(np.unique(y_test)) > 1 else np.nan,
        "horizon_bars": int(config.horizon_bars),
        "min_move_threshold": float(config.min_move_threshold),
        "feature_columns": feature_columns,
    }
    model = SignalGateModel(
        feature_columns=feature_columns,
        pipeline=pipeline,
        metadata=metrics,
    )
    return model, metrics


def attach_gate_probabilities(
    df: pd.DataFrame,
    gate_model: SignalGateModel,
    long_threshold: float,
    short_threshold: float,
) -> pd.DataFrame:
    out = df.copy()
    x = out[gate_model.feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    prob_up = gate_model.pipeline.predict_proba(x)[:, 1]
    prob_down = 1.0 - prob_up
    out["GateProbUp"] = prob_up
    out["GateProbDown"] = prob_down
    out["GateAllowLong"] = (out["GateProbUp"] >= long_threshold).astype(int)
    out["GateAllowShort"] = (out["GateProbDown"] >= short_threshold).astype(int)
    out["GateDecision"] = np.where(
        out["GateAllowLong"] == 1,
        "allow_long",
        np.where(out["GateAllowShort"] == 1, "allow_short", "gate_hold"),
    )
    return out


class SignalGatedTradingEnv(gym.Wrapper):
    def __init__(
        self,
        env: SingleStockTradingEnv,
        gate_model: SignalGateModel,
        long_threshold: float = 0.55,
        short_threshold: float = 0.55,
    ):
        super().__init__(env)
        self.gate_model = gate_model
        self.long_threshold = float(long_threshold)
        self.short_threshold = float(short_threshold)

    def _gate_row(self) -> tuple[float, float, str]:
        idx = min(self.env.current_step, len(self.env.df) - 1)
        row = self.env.df.iloc[[idx]].copy()
        prob_up, prob_down = self.gate_model.predict_probabilities(row)
        p_up = float(prob_up[0]) if len(prob_up) else 0.5
        p_down = float(prob_down[0]) if len(prob_down) else 0.5
        if p_up >= self.long_threshold:
            decision = "allow_long"
        elif p_down >= self.short_threshold:
            decision = "allow_short"
        else:
            decision = "gate_hold"
        return p_up, p_down, decision

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)

    def step(self, action):
        raw_action = int(np.asarray(action).item()) if isinstance(action, (np.ndarray, list, tuple)) else int(action)
        gate_prob_up, gate_prob_down, gate_decision = self._gate_row()
        gated_action = raw_action

        if raw_action == 1 and gate_prob_up < self.long_threshold:
            gated_action = 0
        elif raw_action == 2 and gate_prob_down < self.short_threshold:
            gated_action = 0

        obs, reward, terminated, truncated, info = self.env.step(gated_action)
        info = dict(info or {})
        info.update(
            {
                "raw_action": raw_action,
                "gated_action": gated_action,
                "gate_prob_up": gate_prob_up,
                "gate_prob_down": gate_prob_down,
                "gate_decision": gate_decision,
            }
        )

        if self.env.history:
            self.env.history[-1]["GateProbUp"] = gate_prob_up
            self.env.history[-1]["GateProbDown"] = gate_prob_down
            self.env.history[-1]["RawAction"] = raw_action
            self.env.history[-1]["GatedAction"] = gated_action
            self.env.history[-1]["GateDecision"] = gate_decision
        return obs, reward, terminated, truncated, info


def make_signal_gated_env(
    df: pd.DataFrame,
    ticker: str,
    env_kwargs: dict,
    gate_model: SignalGateModel,
    long_threshold: float = 0.55,
    short_threshold: float = 0.55,
) -> SignalGatedTradingEnv:
    base_env = SingleStockTradingEnv(df=df.copy(), ticker=ticker, **env_kwargs)
    return SignalGatedTradingEnv(
        env=base_env,
        gate_model=gate_model,
        long_threshold=long_threshold,
        short_threshold=short_threshold,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a supervised signal gate from raw Zerodha engineered bars and wrap the trading env."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["ITC", "SBIN", "RELIANCE", "TCS", "INFY"],
        help="Tickers to use for signal-gate training.",
    )
    parser.add_argument("--interval", default="60minute", help="Bar interval for Zerodha historical data.")
    parser.add_argument("--history-days", type=int, default=1095, help="History length per ticker.")
    parser.add_argument("--horizon-bars", type=int, default=3, help="Prediction horizon in bars.")
    parser.add_argument("--min-move-threshold", type=float, default=0.0, help="Optional absolute move filter.")
    parser.add_argument("--train-ratio", type=float, default=0.80, help="Chronological train ratio.")
    parser.add_argument("--long-threshold", type=float, default=0.55, help="Gate threshold for long actions.")
    parser.add_argument("--short-threshold", type=float, default=0.55, help="Gate threshold for short actions.")
    parser.add_argument(
        "--model-path",
        default=str(RESULTS_DIR / "signal_gate_model.pkl"),
        help="Where to save the fitted gate model.",
    )
    parser.add_argument(
        "--export-probabilities",
        action="store_true",
        help="Also export engineered bars with GateProbUp/GateProbDown per ticker.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SignalGateConfig(
        interval=args.interval,
        history_days=args.history_days,
        horizon_bars=args.horizon_bars,
        positive_threshold=args.long_threshold,
        negative_threshold=args.short_threshold,
        min_move_threshold=args.min_move_threshold,
        train_ratio=args.train_ratio,
    )

    training_df = build_training_frame(args.tickers, config)
    model, metrics = fit_signal_gate(training_df, config)
    model_path = Path(args.model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(model_path)

    print("Saved signal gate:", model_path)
    print("Samples train:", metrics["samples_train"])
    print("Samples test:", metrics["samples_test"])
    print("Accuracy:", f"{metrics['accuracy']:.4f}")
    print("ROC AUC:", "n/a" if pd.isna(metrics["roc_auc"]) else f"{metrics['roc_auc']:.4f}")
    print("Positive rate train:", f"{metrics['positive_rate_train']:.4f}")
    print("Positive rate test:", f"{metrics['positive_rate_test']:.4f}")
    print("Features:", ", ".join(metrics["feature_columns"]))

    if args.export_probabilities:
        for ticker in args.tickers:
            ticker_df = load_engineered_data_for_ticker(ticker, config)
            ticker_df = attach_gate_probabilities(
                ticker_df,
                gate_model=model,
                long_threshold=args.long_threshold,
                short_threshold=args.short_threshold,
            )
            out_path = config.output_dir / f"gate_probs_{ticker}_{args.interval}.csv"
            ticker_df.to_csv(out_path, index=False)
            print("Exported:", out_path)


if __name__ == "__main__":
    main()
