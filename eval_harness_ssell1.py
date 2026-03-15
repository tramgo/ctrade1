import math
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

# NOTE:
# Importing ssell1 currently initializes Kite session at module import time.
# This harness reuses those objects as-is.
from ssell1 import (
    SingleStockTradingEnv,
    get_data_kite,
    get_instrument_token,
    build_rl_features,
    instrument_df,
    kite,
    RANDOM_SEED,
)


BASE_DIR = Path(".").resolve()
RESULTS_DIR = BASE_DIR / "results" / "eval_harness"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RL_EXPORT_DIR = RESULTS_DIR / "rl_histories"
RL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
DIRECTIONAL_EXPORT_DIR = RESULTS_DIR / "directional_diagnostics"
DIRECTIONAL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
TB_DIR = BASE_DIR / "tensorboard_logs" / "eval_harness"
TB_DIR.mkdir(parents=True, exist_ok=True)

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


@dataclass
class HarnessConfig:
    interval: str = "60minute"
    history_days: int = 1095

    # Walk-forward window sizes in bars
    train_bars: int = 700
    val_bars: int = 120
    test_bars: int = 80
    step_bars: int = 80
    max_windows: Optional[int] = 3
    window_ids: Optional[List[int]] = None

    initial_balance: float = 100000.0
    annual_trading_days: int = 252

    # Frictions
    use_transaction_cost: bool = True
    use_slippage: bool = True
    slippage_rate: float = 0.001

    # PPO train
    total_timesteps: int = 8000
    deterministic_eval: bool = True
    sb3_verbose: int = 1

    # Env params
    stop_loss: float = 0.90
    take_profit: float = 1.10
    max_position_size: float = 0.5
    max_drawdown: float = 0.20
    some_factor: float = 0.01
    hold_threshold: float = 0.1
    inference_buy_threshold: float = 0.2
    inference_sell_threshold: float = 0.2
    reward_weights: Optional[dict] = None

    # Universe
    tickers: Optional[List[str]] = None

    # Diagnostics
    run_shuffled_test: bool = True
    run_cost_off_test: bool = False


@dataclass
class ExperimentRow:
    ticker: str
    window_id: int
    model_name: str
    data_variant: str
    friction_variant: str
    total_return: float
    annualized_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    trade_count: int
    hold_ratio: float
    avg_abs_action: float
    final_net_worth: float
    bars: int


def compute_style_mix(
    history_df: pd.DataFrame,
    ticker: str,
    window_id: int,
    model_name: str,
    data_variant: str,
    friction_variant: str,
) -> pd.DataFrame:
    cols = [
        "ticker", "window_id", "model_name", "data_variant", "friction_variant",
        "style", "bars", "trade_rows", "trade_ratio", "mean_reward",
        "start_net_worth", "end_net_worth", "net_change",
    ]
    if history_df.empty or "StrategyStyle" not in history_df.columns:
        return pd.DataFrame(columns=cols)

    h = history_df.copy()
    h["StrategyStyle"] = h["StrategyStyle"].fillna("unknown").astype(str)
    if "Net Worth" in h.columns:
        h["Net Worth"] = pd.to_numeric(h["Net Worth"], errors="coerce").ffill().bfill()
    else:
        h["Net Worth"] = pd.to_numeric(h.get("Full Worth", 0.0), errors="coerce").ffill().bfill()
    h["Reward"] = pd.to_numeric(h.get("Reward", 0.0), errors="coerce").fillna(0.0)
    action_col = "Action" if "Action" in h.columns else "ActionLegacy"
    h[action_col] = pd.to_numeric(h.get(action_col, 0.0), errors="coerce").fillna(0.0)

    rows: List[Dict[str, object]] = []
    for style, g in h.groupby("StrategyStyle", dropna=False):
        start_nw = float(g["Net Worth"].iloc[0]) if len(g) else 0.0
        end_nw = float(g["Net Worth"].iloc[-1]) if len(g) else 0.0
        trade_rows = int((g[action_col] != 0).sum())
        rows.append({
            "ticker": ticker,
            "window_id": window_id,
            "model_name": model_name,
            "data_variant": data_variant,
            "friction_variant": friction_variant,
            "style": style,
            "bars": int(len(g)),
            "trade_rows": trade_rows,
            "trade_ratio": float(trade_rows / max(len(g), 1)),
            "mean_reward": float(g["Reward"].mean()) if len(g) else 0.0,
            "start_net_worth": start_nw,
            "end_net_worth": end_nw,
            "net_change": end_nw - start_nw,
        })
    return pd.DataFrame(rows, columns=cols)


def compute_directional_diagnostic(
    history_df: pd.DataFrame,
    ticker: str,
    window_id: int,
    model_name: str,
    data_variant: str,
    friction_variant: str,
) -> pd.DataFrame:
    cols = [
        "ticker", "window_id", "model_name", "data_variant", "friction_variant",
        "horizon", "sample_count", "directional_accuracy",
        "avg_future_return", "avg_long_future_return", "avg_short_future_return",
        "avg_future_return_correct", "avg_future_return_wrong", "net_expectancy",
    ]
    if history_df.empty or "Close" not in history_df.columns:
        return pd.DataFrame(columns=cols)

    h = history_df.copy()
    h["Close"] = pd.to_numeric(h["Close"], errors="coerce")
    action_col = "Action" if "Action" in h.columns else "ActionLegacy"
    h[action_col] = pd.to_numeric(h.get(action_col, 0.0), errors="coerce").fillna(0.0)
    h["action_dir"] = np.sign(h[action_col])
    h = h[h["action_dir"] != 0].copy()
    if h.empty:
        return pd.DataFrame(columns=cols)

    rows: List[Dict[str, object]] = []
    for horizon in (1, 3):
        hc = h.copy()
        hc["future_return"] = hc["Close"].shift(-horizon) / hc["Close"] - 1.0
        hc["future_dir"] = np.sign(hc["future_return"])
        hc = hc.dropna(subset=["future_return"])
        if hc.empty:
            continue

        correct = hc["action_dir"] == hc["future_dir"]
        rows.append({
            "ticker": ticker,
            "window_id": window_id,
            "model_name": model_name,
            "data_variant": data_variant,
            "friction_variant": friction_variant,
            "horizon": horizon,
            "sample_count": int(len(hc)),
            "directional_accuracy": float(correct.mean()),
            "avg_future_return": float(hc["future_return"].mean()),
            "avg_long_future_return": float(hc.loc[hc["action_dir"] > 0, "future_return"].mean()) if (hc["action_dir"] > 0).any() else 0.0,
            "avg_short_future_return": float(hc.loc[hc["action_dir"] < 0, "future_return"].mean()) if (hc["action_dir"] < 0).any() else 0.0,
            "avg_future_return_correct": float(hc.loc[correct, "future_return"].mean()) if correct.any() else 0.0,
            "avg_future_return_wrong": float(hc.loc[~correct, "future_return"].mean()) if (~correct).any() else 0.0,
            "net_expectancy": float((hc["action_dir"] * hc["future_return"]).mean()),
        })
    return pd.DataFrame(rows, columns=cols)


def annualization_factor_from_interval(interval: str, annual_trading_days: int = 252) -> float:
    iv = interval.lower().strip()
    if iv == "day":
        return annual_trading_days
    if iv == "60minute":
        return annual_trading_days * 6.25
    if iv == "30minute":
        return annual_trading_days * 12.5
    if iv == "15minute":
        return annual_trading_days * 25
    if iv == "5minute":
        return annual_trading_days * 75
    return annual_trading_days


def calculate_max_drawdown_from_series(series: pd.Series) -> float:
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max.replace(0, np.nan)
    return float(drawdown.min()) if len(drawdown) else 0.0


def calculate_sharpe(returns: pd.Series, annual_factor: float) -> float:
    std = returns.std()
    if std is None or np.isnan(std) or std < 1e-12:
        return 0.0
    return float((returns.mean() / std) * math.sqrt(annual_factor))


def calculate_sortino(returns: pd.Series, annual_factor: float) -> float:
    downside = returns[returns < 0]
    downside_std = downside.std()
    if downside_std is None or np.isnan(downside_std) or downside_std < 1e-12:
        return 0.0
    return float((returns.mean() / downside_std) * math.sqrt(annual_factor))


def compute_metrics_from_history(
    history_df: pd.DataFrame,
    ticker: str,
    window_id: int,
    model_name: str,
    data_variant: str,
    friction_variant: str,
    interval: str,
) -> ExperimentRow:
    if history_df.empty:
        return ExperimentRow(
            ticker=ticker,
            window_id=window_id,
            model_name=model_name,
            data_variant=data_variant,
            friction_variant=friction_variant,
            total_return=0.0,
            annualized_return=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            trade_count=0,
            hold_ratio=1.0,
            avg_abs_action=0.0,
            final_net_worth=0.0,
            bars=0,
        )

    if "Net Worth" in history_df.columns:
        nw = pd.to_numeric(history_df["Net Worth"], errors="coerce").ffill().bfill()
    elif "Full Worth" in history_df.columns:
        nw = pd.to_numeric(history_df["Full Worth"], errors="coerce").ffill().bfill()
    else:
        raise ValueError("History has no 'Net Worth'/'Full Worth' column")

    nw = nw.replace([np.inf, -np.inf], np.nan).ffill().bfill()
    returns = nw.pct_change().fillna(0.0)
    annual_factor = annualization_factor_from_interval(interval)

    total_return = float((nw.iloc[-1] / nw.iloc[0]) - 1.0) if len(nw) >= 2 and nw.iloc[0] != 0 else 0.0
    annualized_return = float((1.0 + total_return) ** (annual_factor / max(len(nw), 1)) - 1.0) if len(nw) > 1 else 0.0
    sharpe = calculate_sharpe(returns, annual_factor)
    sortino = calculate_sortino(returns, annual_factor)
    max_dd = calculate_max_drawdown_from_series(nw)

    action_col = "Action" if "Action" in history_df.columns else "ActionLegacy"
    if action_col in history_df.columns:
        actions = pd.to_numeric(history_df[action_col], errors="coerce").fillna(0.0)
        trade_count = int((actions != 0).sum())
        hold_ratio = float((actions == 0).mean())
        avg_abs_action = float(actions.abs().mean())
    else:
        trade_count = 0
        hold_ratio = 1.0
        avg_abs_action = 0.0

    return ExperimentRow(
        ticker=ticker,
        window_id=window_id,
        model_name=model_name,
        data_variant=data_variant,
        friction_variant=friction_variant,
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        trade_count=trade_count,
        hold_ratio=hold_ratio,
        avg_abs_action=avg_abs_action,
        final_net_worth=float(nw.iloc[-1]),
        bars=len(history_df),
    )


def load_data_for_ticker(ticker: str, config: HarnessConfig) -> pd.DataFrame:
    token = get_instrument_token(ticker, instrument_df)
    if token is None:
        raise ValueError(f"Instrument token not found for {ticker}")

    df = get_data_kite(kite=kite, instrument_token=token, days=config.history_days, interval=config.interval)
    if df is None or df.empty:
        raise ValueError(f"No data for {ticker}")

    df = df.copy().reset_index(drop=True)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date").reset_index(drop=True)
    return df


def split_walk_forward_windows(
    df: pd.DataFrame,
    train_bars: int,
    val_bars: int,
    test_bars: int,
    step_bars: int,
) -> List[Dict[str, pd.DataFrame]]:
    windows: List[Dict[str, pd.DataFrame]] = []
    start = 0
    total = len(df)
    while start + train_bars + val_bars + test_bars <= total:
        train_df = df.iloc[start: start + train_bars].copy()
        val_df = df.iloc[start + train_bars: start + train_bars + val_bars].copy()
        test_df = df.iloc[start + train_bars + val_bars: start + train_bars + val_bars + test_bars].copy()
        windows.append({"train": train_df, "val": val_df, "test": test_df, "start_idx": start})
        start += step_bars
    return windows


def shuffle_close_series(df: pd.DataFrame, interval: str, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    close = pd.to_numeric(out["Close"], errors="coerce").ffill().bfill().values
    if len(close) < 3:
        return out
    returns = pd.Series(close).pct_change().fillna(0.0).values
    shuffled = returns.copy()
    shuffled[1:] = rng.permutation(shuffled[1:])
    new_close = [close[0]]
    for r in shuffled[1:]:
        new_close.append(max(1e-9, new_close[-1] * (1.0 + float(r))))
    out["Close"] = np.asarray(new_close)
    out["Open"] = out["Close"].shift(1).fillna(out["Close"])
    spread = (pd.to_numeric(df["High"], errors="coerce") - pd.to_numeric(df["Low"], errors="coerce")).abs().fillna(0.0)
    spread = spread.replace(0.0, spread.median() if len(spread) else 0.0)
    h = spread.values / 2.0
    out["High"] = np.maximum(out["Open"], out["Close"]) + h
    out["Low"] = np.minimum(out["Open"], out["Close"]) - h
    if "Adj Close" in out.columns:
        out["Adj Close"] = out["Close"]
    out = build_rl_features(out, interval=interval)
    return out


def make_env_from_df(
    df: pd.DataFrame,
    ticker: str,
    config: HarnessConfig,
    env_rank: int = 0,
    mode: str = "train",
):
    reward_weights = config.reward_weights or {
        "transaction_penalty_weight": 1.0,
        "forced_stop_penalty_weight": 0.001,
        "forced_tp_penalty_weight": 0.001,
        "volatility_penalty_weight": 0.10,
        "trade_fraction": 0.25,
        "reduce_fraction": 0.50,
    }

    def _init():
        return SingleStockTradingEnv(
            df=df.copy(),
            ticker=ticker,
            initial_balance=config.initial_balance,
            stop_loss=config.stop_loss,
            take_profit=config.take_profit,
            max_position_size=config.max_position_size,
            max_drawdown=config.max_drawdown,
            annual_trading_days=config.annual_trading_days,
            env_rank=env_rank,
            some_factor=config.some_factor,
            hold_threshold=config.hold_threshold,
            reward_weights=reward_weights,
            max_episode_steps=len(df),
            mode=mode,
            inference_buy_threshold=config.inference_buy_threshold,
            inference_sell_threshold=config.inference_sell_threshold,
            slippage_rate=(config.slippage_rate if config.use_slippage else 0.0),
            disable_costs=(not config.use_transaction_cost),
        )

    return _init


def train_rl_model_on_window(
    train_df: pd.DataFrame,
    ticker: str,
    config: HarnessConfig,
    save_dir: Path,
    tb_log_name: str,
) -> Tuple[Path, Path]:
    env_fn = make_env_from_df(train_df, ticker=ticker, config=config, env_rank=0, mode="train")
    vec_env = DummyVecEnv([env_fn])
    vec_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    model = PPO(
        policy="MlpPolicy",
        env=vec_env,
        verbose=config.sb3_verbose,
        seed=RANDOM_SEED,
        tensorboard_log=str(TB_DIR),
        n_steps=256,
        batch_size=64,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.001,
    )
    model.learn(
        total_timesteps=config.total_timesteps,
        tb_log_name=tb_log_name,
    )

    save_dir.mkdir(parents=True, exist_ok=True)
    model_path = save_dir / "ppo_model.zip"
    vecnorm_path = save_dir / "vecnormalize.pkl"
    model.save(str(model_path))
    vec_env.save(str(vecnorm_path))
    vec_env.close()
    return model_path, vecnorm_path


def extract_vecenv_history(vec_env: DummyVecEnv) -> List[dict]:
    final_metrics_list = vec_env.env_method("get_final_metrics")
    final_metrics = final_metrics_list[0] if final_metrics_list else {}
    history = final_metrics.get("history", []) if final_metrics else []
    if history:
        return history

    current_metrics_list = vec_env.env_method("get_current_metrics")
    current_metrics = current_metrics_list[0] if current_metrics_list else {}
    history = current_metrics.get("history", []) if current_metrics else []
    if history:
        return history

    histories = vec_env.get_attr("history")
    return histories[0] if histories else []


def run_rl_backtest(
    model_path: Path,
    vecnorm_path: Path,
    test_df: pd.DataFrame,
    ticker: str,
    config: HarnessConfig,
) -> pd.DataFrame:
    test_env_fn = make_env_from_df(test_df, ticker=ticker, config=config, env_rank=0, mode="test")
    test_env = DummyVecEnv([test_env_fn])
    test_env = VecNormalize.load(str(vecnorm_path), test_env)
    test_env.training = False
    test_env.norm_reward = False

    model = PPO.load(str(model_path), env=test_env)
    obs = test_env.reset()
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=config.deterministic_eval)
        obs, reward, done, info = test_env.step(action)
        if isinstance(done, np.ndarray):
            done = bool(done[0])
    history = extract_vecenv_history(test_env)
    test_env.close()
    return pd.DataFrame(history)


# Baseline policies mapped to env discrete actions:
# 0 hold, 1 long, 2 short, 3 reduce
def flat_policy(_: pd.Series) -> int:
    return 0


def random_policy(_: pd.Series) -> int:
    return int(np.random.choice([0, 1, 2, 3]))


def sma_policy(row: pd.Series) -> int:
    t30 = float(row.get("Trend_30", 0.0))
    if t30 > 0:
        return 1
    if t30 < 0:
        return 2
    return 0


def rsi_policy(row: pd.Series) -> int:
    rsi = float(row.get("RSI14", row.get("RSI", 50.0)))
    if rsi < 30:
        return 1
    if rsi > 70:
        return 2
    return 0


def run_baseline_backtest(
    df: pd.DataFrame,
    ticker: str,
    config: HarnessConfig,
    policy_fn: Callable[[pd.Series], int],
) -> pd.DataFrame:
    env = make_env_from_df(df=df, ticker=ticker, config=config, env_rank=0, mode="test")()
    obs, _ = env.reset()
    terminated = False
    truncated = False
    while not (terminated or truncated):
        current_idx = min(env.current_step, len(env.df) - 1)
        row = env.df.iloc[current_idx]
        action = int(policy_fn(row))
        obs, reward, terminated, truncated, info = env.step(action)
    return pd.DataFrame(env.history)


def save_history_csv(history_df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history_df.to_csv(out_path, index=False)


def export_rl_history_copy(
    history_df: pd.DataFrame,
    ticker: str,
    window_id: int,
    data_variant: str,
    friction_variant: str,
) -> Path:
    filename = f"history_rl_{ticker}_window_{window_id:03d}_{data_variant}_{friction_variant}.csv"
    out_path = RL_EXPORT_DIR / filename
    save_history_csv(history_df, out_path)
    return out_path


def export_directional_diagnostic_copy(
    diagnostic_df: pd.DataFrame,
    ticker: str,
    window_id: int,
    data_variant: str,
    friction_variant: str,
) -> Path:
    filename = f"directional_diagnostic_{ticker}_window_{window_id:03d}_{data_variant}_{friction_variant}.csv"
    out_path = DIRECTIONAL_EXPORT_DIR / filename
    save_history_csv(diagnostic_df, out_path)
    return out_path


def run_single_window_suite(
    ticker: str,
    window_id: int,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    config: HarnessConfig,
    base_out_dir: Path,
    data_variant: str = "real",
    friction_variant: str = "cost_on",
) -> List[ExperimentRow]:
    rows: List[ExperimentRow] = []
    style_rows: List[pd.DataFrame] = []
    diagnostic_rows: List[pd.DataFrame] = []
    out_dir = base_out_dir / ticker / f"window_{window_id:03d}" / data_variant / friction_variant
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path, vecnorm_path = train_rl_model_on_window(
        train_df=train_df,
        ticker=ticker,
        config=config,
        save_dir=out_dir / "rl_model",
        tb_log_name=f"{ticker}_w{window_id:03d}_{data_variant}_{friction_variant}",
    )

    rl_history = run_rl_backtest(model_path, vecnorm_path, test_df, ticker, config)
    save_history_csv(rl_history, out_dir / "history_rl.csv")
    export_rl_history_copy(rl_history, ticker, window_id, data_variant, friction_variant)
    rows.append(
        compute_metrics_from_history(
            rl_history, ticker, window_id, "RL", data_variant, friction_variant, config.interval
        )
    )
    style_rows.append(compute_style_mix(rl_history, ticker, window_id, "RL", data_variant, friction_variant))
    diagnostic_rows.append(compute_directional_diagnostic(rl_history, ticker, window_id, "RL", data_variant, friction_variant))

    baseline_map = {
        "FLAT": flat_policy,
        "RANDOM": random_policy,
        "SMA": sma_policy,
        "RSI": rsi_policy,
    }
    for model_name, policy_fn in baseline_map.items():
        hist = run_baseline_backtest(test_df, ticker, config, policy_fn)
        save_history_csv(hist, out_dir / f"history_{model_name.lower()}.csv")
        rows.append(
            compute_metrics_from_history(
                hist, ticker, window_id, model_name, data_variant, friction_variant, config.interval
            )
        )
        style_rows.append(compute_style_mix(hist, ticker, window_id, model_name, data_variant, friction_variant))
        diagnostic_rows.append(compute_directional_diagnostic(hist, ticker, window_id, model_name, data_variant, friction_variant))

    pd.DataFrame([asdict(r) for r in rows]).to_csv(out_dir / "summary_metrics.csv", index=False)
    style_df = pd.concat([df for df in style_rows if not df.empty], ignore_index=True) if style_rows else pd.DataFrame()
    if not style_df.empty:
        style_df.to_csv(out_dir / "style_summary.csv", index=False)
    diagnostic_df = pd.concat([df for df in diagnostic_rows if not df.empty], ignore_index=True) if diagnostic_rows else pd.DataFrame()
    if not diagnostic_df.empty:
        diagnostic_df.to_csv(out_dir / "directional_diagnostic.csv", index=False)
        export_directional_diagnostic_copy(diagnostic_df, ticker, window_id, data_variant, friction_variant)
    return rows


def aggregate_results(rows: List[ExperimentRow], out_path: Path) -> pd.DataFrame:
    df = pd.DataFrame([asdict(r) for r in rows])
    df.to_csv(out_path, index=False)
    agg = (
        df.groupby(["model_name", "data_variant", "friction_variant"], as_index=False)
        .agg(
            mean_total_return=("total_return", "mean"),
            median_total_return=("total_return", "median"),
            mean_annualized_return=("annualized_return", "mean"),
            mean_sharpe=("sharpe", "mean"),
            mean_sortino=("sortino", "mean"),
            mean_max_drawdown=("max_drawdown", "mean"),
            mean_trade_count=("trade_count", "mean"),
            mean_hold_ratio=("hold_ratio", "mean"),
            mean_final_net_worth=("final_net_worth", "mean"),
            windows=("window_id", "nunique"),
            rows=("ticker", "count"),
        )
    )
    agg.to_csv(out_path.with_name("aggregate_summary.csv"), index=False)
    return agg


def aggregate_style_results(base_dir: Path, out_path: Path) -> pd.DataFrame:
    style_files = sorted(base_dir.glob("*/*/*/*/style_summary.csv"))
    if not style_files:
        empty = pd.DataFrame()
        empty.to_csv(out_path, index=False)
        return empty

    df = pd.concat((pd.read_csv(path) for path in style_files), ignore_index=True)
    df.to_csv(out_path.with_name("master_style_results.csv"), index=False)
    agg = (
        df.groupby(["model_name", "data_variant", "friction_variant", "style"], as_index=False)
        .agg(
            windows=("window_id", "nunique"),
            rows=("ticker", "count"),
            total_bars=("bars", "sum"),
            total_trade_rows=("trade_rows", "sum"),
            mean_trade_ratio=("trade_ratio", "mean"),
            mean_reward=("mean_reward", "mean"),
            mean_net_change=("net_change", "mean"),
        )
    )
    agg.to_csv(out_path, index=False)
    return agg


def aggregate_directional_results(base_dir: Path, out_path: Path) -> pd.DataFrame:
    diagnostic_files = sorted(base_dir.glob("*/*/*/*/directional_diagnostic.csv"))
    if not diagnostic_files:
        empty = pd.DataFrame()
        empty.to_csv(out_path, index=False)
        return empty

    df = pd.concat((pd.read_csv(path) for path in diagnostic_files), ignore_index=True)
    df.to_csv(out_path.with_name("master_directional_results.csv"), index=False)
    agg = (
        df.groupby(["model_name", "data_variant", "friction_variant", "horizon"], as_index=False)
        .agg(
            windows=("window_id", "nunique"),
            rows=("ticker", "count"),
            total_samples=("sample_count", "sum"),
            mean_directional_accuracy=("directional_accuracy", "mean"),
            mean_avg_future_return=("avg_future_return", "mean"),
            mean_avg_long_future_return=("avg_long_future_return", "mean"),
            mean_avg_short_future_return=("avg_short_future_return", "mean"),
            mean_avg_future_return_correct=("avg_future_return_correct", "mean"),
            mean_avg_future_return_wrong=("avg_future_return_wrong", "mean"),
            mean_net_expectancy=("net_expectancy", "mean"),
        )
    )
    agg.to_csv(out_path, index=False)
    return agg


def run_experiment_suite(config: HarnessConfig) -> pd.DataFrame:
    if not config.tickers:
        raise ValueError("Please set config.tickers")

    all_rows: List[ExperimentRow] = []
    for ticker in config.tickers:
        print(f"\n=== Loading data for {ticker} ===")
        full_df = load_data_for_ticker(ticker, config)
        windows = split_walk_forward_windows(
            df=full_df,
            train_bars=config.train_bars,
            val_bars=config.val_bars,
            test_bars=config.test_bars,
            step_bars=config.step_bars,
        )
        indexed_windows = list(enumerate(windows, start=1))
        if config.window_ids:
            wanted = set(config.window_ids)
            indexed_windows = [(window_id, w) for window_id, w in indexed_windows if window_id in wanted]
        elif config.max_windows is not None:
            indexed_windows = indexed_windows[: config.max_windows]
        print(f"{ticker}: generated {len(indexed_windows)} windows")

        for window_id, w in indexed_windows:
            print(f"Running {ticker} window {window_id}")

            cfg_cost_on = HarnessConfig(**asdict(config))
            cfg_cost_on.use_transaction_cost = True
            cfg_cost_on.use_slippage = True
            all_rows.extend(
                run_single_window_suite(
                    ticker=ticker,
                    window_id=window_id,
                    train_df=w["train"],
                    test_df=w["test"],
                    config=cfg_cost_on,
                    base_out_dir=RESULTS_DIR,
                    data_variant="real",
                    friction_variant="cost_on",
                )
            )

            if config.run_cost_off_test:
                cfg_cost_off = HarnessConfig(**asdict(config))
                cfg_cost_off.use_transaction_cost = False
                cfg_cost_off.use_slippage = False
                all_rows.extend(
                    run_single_window_suite(
                        ticker=ticker,
                        window_id=window_id,
                        train_df=w["train"],
                        test_df=w["test"],
                        config=cfg_cost_off,
                        base_out_dir=RESULTS_DIR,
                        data_variant="real",
                        friction_variant="cost_off",
                    )
                )

            if config.run_shuffled_test:
                shuffled_train = shuffle_close_series(w["train"], interval=config.interval, seed=RANDOM_SEED + window_id)
                shuffled_test = shuffle_close_series(w["test"], interval=config.interval, seed=RANDOM_SEED + window_id + 17)
                cfg_shuffle = HarnessConfig(**asdict(config))
                cfg_shuffle.use_transaction_cost = True
                cfg_shuffle.use_slippage = True
                all_rows.extend(
                    run_single_window_suite(
                        ticker=ticker,
                        window_id=window_id,
                        train_df=shuffled_train,
                        test_df=shuffled_test,
                        config=cfg_shuffle,
                        base_out_dir=RESULTS_DIR,
                        data_variant="shuffled",
                        friction_variant="cost_on",
                    )
                )

    master_path = RESULTS_DIR / "master_results.csv"
    aggregate_results(all_rows, master_path)
    aggregate_style_results(RESULTS_DIR, RESULTS_DIR / "aggregate_style_summary.csv")
    aggregate_directional_results(RESULTS_DIR, RESULTS_DIR / "aggregate_directional_summary.csv")
    return pd.read_csv(master_path.with_name("aggregate_summary.csv"))


if __name__ == "__main__":
    config = HarnessConfig(
        interval="60minute",
        history_days=1095,
        train_bars=700,
        val_bars=120,
        test_bars=80,
        step_bars=80,
        total_timesteps=5000,
        tickers=[
            "ITC", "SBIN", "RELIANCE", "TCS", "INFY",
        ],
        max_windows=3,
        window_ids=None,
        reward_weights={
            "transaction_penalty_weight": 1.0,
            "forced_stop_penalty_weight": 0.001,
            "forced_tp_penalty_weight": 0.001,
            "volatility_penalty_weight": 0.10,
            "trade_fraction": 0.15,
            "min_trade_fraction": 0.05,
            "reduce_fraction": 0.50,
            "directional_weight": 0.01,
            "regime_gate_min_confidence": 0.60,
            "regime_gate_min_confirmations": 2,
            "reversion_gate_min_confidence": 0.55,
            "reversion_gate_min_confirmations": 2,
            "style_router_margin": 0.15,
            "style_router_min_strength": 0.55,
            "action_penalty_weight": 0.001,
            "reduce_penalty_multiplier": 1.5,
            "flat_threshold": 0.0010,
            "weak_move_threshold": 0.0025,
            "flat_reward_bonus": 0.20,
            "wrong_flat_penalty": 0.25,
            "rebalance_threshold": 0.20,
            "entry_min_exposure": 0.02,
            "reduce_hold_threshold": 0.02,
            "min_market_vol_rank": 0.30,
        },
        run_cost_off_test=False,
        run_shuffled_test=True,
    )

    summary = run_experiment_suite(config)
    print("\n=== Aggregate Summary ===")
    print(summary)
