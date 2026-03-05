import argparse
import ast
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

import MultBacktest1 as mb


DEFAULT_TEST_TICKERS = [
    "KOTAKBANK.NS",
    "ITC.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "LT.NS",
    "NTPC.NS",
    "SBIN.NS",
]


def load_best_params_from_log(log_path: Path) -> dict:
    if not log_path.exists():
        return {}
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        marker = "[OPTUNA] Best hyperparameters:"
        if marker in line:
            raw = line.split(marker, 1)[1].strip()
            try:
                return ast.literal_eval(raw)
            except Exception:
                return {}
    return {}


def load_data_with_cache_first(ticker: str, start_date: str, end_date: str, results_dir: Path, cache_only: bool) -> pd.DataFrame:
    csv_path = results_dir / f"data_fetched_{ticker}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
            if not df.empty:
                return df
        except Exception:
            pass

    if cache_only:
        return pd.DataFrame()

    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            group_by="ticker",
            progress=False,
            threads=False,
        )
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        df = df.reset_index()
        if "Date" not in df.columns:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def build_test_env_kwargs(df_test: pd.DataFrame, ticker: str, best_params: dict) -> dict:
    return dict(
        df=df_test,
        ticker=ticker,
        initial_balance=100000,
        stop_loss=best_params.get("stop_loss", 0.90),
        take_profit=best_params.get("take_profit", 1.10),
        max_position_size=best_params.get("max_position_size", 0.5),
        max_drawdown=best_params.get("max_drawdown", 0.20),
        annual_trading_days=252,
        transaction_cost=best_params.get("transaction_cost", 0.0001),
        env_rank=9999,
        some_factor=best_params.get("drawdown_penalty_factor", 0.01),
        hold_threshold=0.0,
        reward_weights={
            "reward_scale": best_params.get("reward_scale", 1.0),
            "profit_weight": best_params.get("profit_weight", 1.5),
            "sharpe_bonus_weight": best_params.get("sharpe_bonus_weight", 0.05),
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1e-3),
            "turnover_penalty_weight": best_params.get("turnover_penalty_weight", 1e-3),
            "min_trade_value_frac": best_params.get("min_trade_value_frac", 0.01),
            "sell_threshold_mult": best_params.get("sell_threshold_mult", 0.5),
            "min_hold_steps": int(best_params.get("min_hold_steps", 3)),
            "action_dead_zone": best_params.get("action_dead_zone", 0.05),
            "action_smoothing_alpha": best_params.get("action_smoothing_alpha", 0.9),
            "profit_clip": best_params.get("profit_clip", 0.01),
            "holding_bonus_weight": best_params.get("holding_bonus_weight", 0.001),
            "transaction_penalty_scale": best_params.get("transaction_penalty_scale", 1.0),
            "volatility_threshold": best_params.get("volatility_threshold", 1.0),
            "momentum_threshold_min": best_params.get("momentum_threshold_min", 30),
            "momentum_threshold_max": best_params.get("momentum_threshold_max", 70),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
        },
        max_episode_steps=len(df_test),
        mode="test",
        inference_buy_threshold=best_params.get("inference_buy_threshold", 0.1),
        inference_sell_threshold=best_params.get("inference_sell_threshold", 0.1),
    )


def run_inference_for_ticker(
    ticker: str,
    df_test: pd.DataFrame,
    model_path: Path,
    vecnorm_path: Path,
    best_params: dict,
    results_dir: Path,
) -> None:
    env_kwargs = build_test_env_kwargs(df_test, ticker, best_params)
    vec = DummyVecEnv([mb.make_env_factory(env_kwargs)])
    vec = VecNormalize.load(str(vecnorm_path), vec)
    vec.training = False
    vec.norm_reward = False
    vec.clip_obs = 10.0
    vec.clip_reward = 10.0

    model = PPO.load(str(model_path), env=vec)
    obs = vec.reset()
    done = [False]
    max_steps = len(df_test)
    steps = 0

    while not all(done) and steps < max_steps:
        action, _ = model.predict(obs, deterministic=True)
        obs, rewards, done, infos = vec.step(action)
        steps += 1

    metrics = vec.env_method("get_final_metrics")[0]
    history = metrics.get("history", [])
    out_file = results_dir / f"inference_{ticker}_history.csv"
    pd.DataFrame(history).to_csv(out_file, index=False)

    final_full_worth = float(history[-1].get("Full Worth", history[-1].get("Net Worth", 100000.0))) if history else 100000.0
    pnl_pct = (final_full_worth - 100000.0) / 100000.0 * 100.0
    print(f"{ticker}: steps={steps}, final_full_worth={final_full_worth:.2f}, pnl={pnl_pct:.2f}% -> {out_file}")

    vec.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run inference using saved PPO model + VecNormalize.")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--model", default="results/ppo_final_model.zip")
    parser.add_argument("--vecnorm", default="results/vec_normalize.pkl")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2025-02-05")
    parser.add_argument("--split-ratio", type=float, default=0.8)
    parser.add_argument("--cache-only", action="store_true", help="Use cached CSV only; no yfinance calls.")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TEST_TICKERS)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    model_path = Path(args.model)
    vecnorm_path = Path(args.vecnorm)
    log_path = results_dir / "main.log"

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not vecnorm_path.exists():
        raise FileNotFoundError(f"VecNormalize not found: {vecnorm_path}")

    best_params = load_best_params_from_log(log_path)
    print(f"Loaded best params keys: {len(best_params)}")

    for ticker in args.tickers:
        df_full = load_data_with_cache_first(ticker, args.start, args.end, results_dir, args.cache_only)
        if df_full.empty:
            print(f"{ticker}: skipped (no data).")
            continue

        split_idx = int(len(df_full) * args.split_ratio)
        df_test = df_full.iloc[split_idx:].reset_index(drop=True)
        if df_test.empty:
            print(f"{ticker}: skipped (empty test split).")
            continue

        try:
            run_inference_for_ticker(ticker, df_test, model_path, vecnorm_path, best_params, results_dir)
        except Exception as exc:
            print(f"{ticker}: inference failed: {exc}")


if __name__ == "__main__":
    main()
