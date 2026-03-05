import os
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from ta import trend, momentum, volatility, volume
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import yfinance as yf

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.vec_env import VecNormalize
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback, CallbackList

import torch
import warnings
from typing import Optional, Tuple
import random
import datetime
import math
import logging
from pathlib import Path
import optuna
import joblib
import time
import plotly.io as pio
import traceback
from functools import partial
import threading

from ta.momentum import StochasticOscillator
from ta.volume import ChaikinMoneyFlowIndicator, OnBalanceVolumeIndicator, ForceIndexIndicator
from ta.volatility import KeltnerChannel

try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
except ImportError:
    raise ImportError("Please install 'concurrent-log-handler' package via pip: pip install concurrent-log-handler")

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)

BASE_DIR = Path('.').resolve()
RESULTS_DIR = BASE_DIR / 'results'
PLOTS_DIR = BASE_DIR / 'plots'
TB_LOG_DIR = BASE_DIR / 'tensorboard_logs'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
TB_LOG_DIR.mkdir(parents=True, exist_ok=True)

def setup_logger(name: str, log_file: Path, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = ConcurrentRotatingFileHandler(str(log_file), maxBytes=10**6, backupCount=300, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

main_logger = setup_logger('main_logger', RESULTS_DIR / 'main.log', level=logging.DEBUG)
training_logger = setup_logger('training_logger', RESULTS_DIR / 'training.log', level=logging.DEBUG)
testing_logger = setup_logger('testing_logger', RESULTS_DIR / 'testing.log', level=logging.DEBUG)
phase_logger = setup_logger('phase_logger', RESULTS_DIR / 'phase.log', level=logging.INFO)

def log_phase(phase: str, status: str = "Starting", env_details: dict = None, duration: float = None):
    log_message = f"***** {status} {phase} *****"
    if env_details:
        log_message += f"\nEnvironment Details: {env_details}"
    if duration is not None:
        log_message += f"\nDuration: {duration:.2f} seconds ({duration/60:.2f} minutes)"
    phase_logger.info(log_message)

def check_versions():
    import stable_baselines3
    import gymnasium
    import optuna
    sb3_version = stable_baselines3.__version__
    gymnasium_version = gymnasium.__version__
    optuna_version = optuna.__version__
    main_logger.debug(f"Stable Baselines3 version: {sb3_version}")
    main_logger.debug(f"Gymnasium version: {gymnasium_version}")
    main_logger.debug(f"Optuna version: {optuna_version}")
    try:
        sb3_major, sb3_minor, sb3_patch = map(int, sb3_version.split('.')[:3])
        if sb3_major < 2:
            main_logger.error("Stable Baselines3 version must be at least 2.0.0. Please upgrade SB3.")
            exit()
    except:
        main_logger.error("Unable to parse Stable Baselines3 version. Please ensure it's installed correctly.")
        exit()
    if gymnasium_version < '0.28.1':
        main_logger.warning("Consider upgrading Gymnasium to the latest version for better compatibility.")

check_versions()

# We define the feature list but do not scale it in this revised code
FEATURES_TO_SCALE = [
    'Close', 'SMA10', 'SMA50', 'RSI', 'MACD', 'ADX',
    'BB_Upper', 'BB_Lower', 'Bollinger_Width',
    'EMA20', 'VWAP', 'Lagged_Return', 'Volatility', 'Volume',

    # NEW microstructure indicators (add them in):
    'Chaikin_MF',        # Chaikin Money Flow
    'OBV',               # On-Balance Volume
    'Stoch_RSI',         # Stochastic RSI %K
    'Stoch_RSI_signal',  # Stochastic RSI %D
    'KC_High',           # Keltner Channel High
    'KC_Low',            # Keltner Channel Low
    'KC_Mid',            # Keltner Channel Mid
    'Force_Index',       # Force Index
    'Intraday_Pct_Range' # (optional) Captures daily volatility range relative to open
]

LOG_TRANSFORM_FEATURES = ["Close", "Volume", "Chaikin_MF"]  # or whichever are strictly > 0


def build_single_stock_env(env_kwargs: dict):
    """Top-level constructor used by SubprocVecEnv workers (pickle-safe)."""
    return SingleStockTradingEnv(**env_kwargs)


def make_env_factory(env_kwargs: dict):
    """Create a subprocess-safe environment factory that builds a fresh env per worker."""
    return partial(build_single_stock_env, env_kwargs=env_kwargs)

class SingleStockTradingEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(
        self,
        df: pd.DataFrame,
        ticker: str,
        initial_balance: float = 100000,
        stop_loss: float = 0.90,
        take_profit: float = 1.10,
        max_position_size: float = 0.5,
        max_drawdown: float = 0.20,
        annual_trading_days: int = 252,
        transaction_cost: float = 0.0001,
        env_rank: int = 0,
        some_factor: float = 0.01,
        hold_threshold: float = 0.1, 
        reward_weights: Optional[dict] = None,
        trailing_drawdown_trigger: float = 0.20,
        trailing_drawdown_grace: int = 3,
        forced_liquidation_penalty: float = -5.0,
        max_episode_steps: Optional[int] = None,
        mode: str = "train",           # New parameter: "train" or "test"
        inference_buy_threshold: float = 0.5,   # New: threshold for buy signals (tuned between 0.5 and 1.0)
        inference_sell_threshold: float = 0.5   # New: threshold for sell signals (tuned between 0.5 and 1.0)
    ):
        super(SingleStockTradingEnv, self).__init__()
        self.env_rank = env_rank
        self.ticker = ticker
        self.df = df.copy().reset_index(drop=True)

        self.initial_balance = initial_balance
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_position_size = max_position_size
        self.max_drawdown = max_drawdown
        self.annual_trading_days = annual_trading_days
        self.transaction_cost = transaction_cost
        self.some_factor = some_factor
        self.hold_threshold = hold_threshold
        self.trailing_drawdown_trigger = trailing_drawdown_trigger
        self.trailing_drawdown_grace = trailing_drawdown_grace
        self.forced_liquidation_penalty = forced_liquidation_penalty
        # Initialize your dictionary here (optional)
        self.current_obs_dict = {}

        # Set maximum steps per episode; if not provided, default to 1000 or the number of data rows if fewer.
        if max_episode_steps is None:
            self.max_episode_steps = min(1000, len(self.df))
        else:
            self.max_episode_steps = max_episode_steps

        # NEW: Store the mode and inference thresholds
        self.mode = mode  
        self.inference_buy_threshold = inference_buy_threshold
        self.inference_sell_threshold = inference_sell_threshold
        self.profit_reference = initial_balance
        self.realized_gain = 0.0  # to store cashed-out gains

        if self.mode == "test":
            main_logger.info(f"[Env {self.env_rank}] In test mode: Inference Buy Threshold set to {self.inference_buy_threshold}, "
                         f"Inference Sell Threshold set to {self.inference_sell_threshold}")
        
        import collections
        self.reward_history = collections.deque(maxlen=500)

        self.action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)
        self.num_features = len(FEATURES_TO_SCALE)
        self.market_phase = ['Bull', 'Bear', 'Sideways']

        # Observation: technical features + (balance ratio, net worth ratio, position ratio) + market phase flags + drawdown stats.
        # Assuming previous observation space dimensions were:
        # self.num_features + 3 + len(self.market_phase) + 2
        # We add 2 more dimensions for profit and loss percentages.
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.num_features + 3 + len(self.market_phase) + 5, ),  # Increased by 2 extra dimensions
            dtype=np.float32
        )


        if reward_weights is not None:
            self.reward_weights = reward_weights
        else:
            self.reward_weights = {'reward_scale': 1.0}

        # Cooldowns (in steps) between forced trigger events.
        self.sl_cooldown_steps = int(self.reward_weights.get("sl_cooldown_steps", 10))
        self.tp_cooldown_steps = int(self.reward_weights.get("tp_cooldown_steps", 10))
        self.dd_cooldown_steps = int(self.reward_weights.get("dd_cooldown_steps", 20))
        
        self.cumulative_reward = 0.0  # Running total updated each step.
        self._force_termination = False  # Flag set by early stopping.
        self.final_metrics = None  # Final metrics available after episode ends.
        
        self.reset()

    def seed(self, seed=None):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        training_logger.debug(f"[Env {self.env_rank}] Seed set to {seed}")

    def _next_observation(self):
        """
        Returns a NumPy array for the RL algorithm and
        also creates a labeled dictionary stored in `self.current_obs_dict`
        for logging or CSV output.
        """
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1

        self.current_obs_dict = {}  # Re-initialize or update as needed

        current_data = self.df.iloc[self.current_step]

        # Use the raw columns as defined in FEATURES_TO_SCALE
        features = current_data[FEATURES_TO_SCALE].values  # array of length len(FEATURES_TO_SCALE)

        # Build an ordered dictionary for the labeled observation
        obs_dict = {}

        # 1) Technical Indicators from FEATURES_TO_SCALE
        for i, feat_name in enumerate(FEATURES_TO_SCALE):
            val = float(features[i])
            # Log transform if in LOG_TRANSFORM_FEATURES
            if feat_name in LOG_TRANSFORM_FEATURES:
                if val <= 0:
                    val = 1e-9  # ensure strictly positive
                val = np.log(val)
            obs_dict[feat_name] = val

        # 2) Ratios: balance, net worth, position
        obs_dict["Balance_Ratio"] = self.balance / self.profit_reference
        obs_dict["NetWorth_Ratio"] = self.net_worth / self.profit_reference
        # Keep units consistent: position value (currency) / reference (currency).
        current_price = float(current_data.get("Close", 0.0))
        position_value = float(self.position) * current_price
        obs_dict["Position_Ratio"] = position_value / max(self.profit_reference, 1e-9)

        # 3) Market Phase (Bull, Bear, Sideways) â€“ one-hot
        phase = 'Sideways'
        adx_val = float(current_data.get('ADX', 0.0))
        if adx_val > 25:
            sma10_val = float(current_data.get('SMA10', 0.0))
            sma50_val = float(current_data.get('SMA50', 0.0))
            phase = 'Bull' if sma10_val > sma50_val else 'Bear'
        obs_dict["Phase_Bull"] = 1.0 if phase == 'Bull' else 0.0
        obs_dict["Phase_Bear"] = 1.0 if phase == 'Bear' else 0.0
        obs_dict["Phase_Sideways"] = 1.0 if phase == 'Sideways' else 0.0

        # 4) Drawdown Stats
        current_drawdown_fraction = (self.peak - self.net_worth) / self.peak if self.peak > 0 else 0.0
        meltdown_threshold = self.max_drawdown
        drawdown_buffer = max(0.0, meltdown_threshold - current_drawdown_fraction)
        obs_dict["Drawdown_Fraction"] = current_drawdown_fraction
        obs_dict["Drawdown_Buffer"] = drawdown_buffer

        # 5) Profit & Loss Percent
        # Profit and Loss Percent calculated relative to profit_reference.
        obs_dict["Profit_Percent"] = max(0.0, (self.net_worth - self.profit_reference) / self.profit_reference)
        obs_dict["Loss_Percent"] = max(0.0, (self.profit_reference - self.net_worth) / self.profit_reference)
        """ obs_dict["Profit_Percent"] = profit_percent
        obs_dict["Loss_Percent"]   = loss_percent """

        # 6) Additional Feature: Log_Return (or 0.0 if missing)
        obs_dict["Log_Return"] = float(current_data.get('Log_Return', 0.0))

        # Convert obs_dict to an array for the RL observation
        # (The order here must match self.observation_space shape)
        obs_list = [
            obs_dict[name] for name in FEATURES_TO_SCALE  # all your tech indicators in order
        ]
        obs_list += [
            obs_dict["Balance_Ratio"],
            obs_dict["NetWorth_Ratio"],
            obs_dict["Position_Ratio"],
            obs_dict["Phase_Bull"],
            obs_dict["Phase_Bear"],
            obs_dict["Phase_Sideways"],
            obs_dict["Drawdown_Fraction"],
            obs_dict["Drawdown_Buffer"],
            obs_dict["Profit_Percent"],
            obs_dict["Loss_Percent"],
            obs_dict["Log_Return"]
        ]

        obs_array = np.array(obs_list, dtype=np.float32)
        # Check for any NaN or Inf
        if np.isnan(obs_array).any() or np.isinf(obs_array).any():
            obs_array = np.nan_to_num(obs_array, nan=0.0, posinf=0.0, neginf=0.0)

        expected_size = self.observation_space.shape[0]
        assert obs_array.shape[0] == expected_size, (
            f"Observation shape mismatch: {obs_array.shape[0]} vs {expected_size}"
        )

        # Store this labeled dictionary for usage in step()
        self.current_obs_dict = obs_dict

        return obs_array

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.position = 0
        self.net_worth = self.initial_balance
        self.profit_reference = self.initial_balance  # Reset profit reference here
        self.realized_gain = 0.0                         # amount cashed out
        self.current_step = 0
        self.history = []
        self.prev_net_worth = self.net_worth
        self.last_action = 0.0
        self.prev_action = 0.0
        self.prev_policy_action = 0.0
        self.prev_target_value = 0.0
        self.peak = self.net_worth
        self.returns_window = []
        self.transaction_count = 0
        self.consecutive_drawdown_steps = 0
        self.reward_history.clear()
        self.cumulative_reward = 0.0  # Running total updated each step.
        self._force_termination = False  # Flag set by early stopping.
        self.final_metrics = None  # Final metrics available after episode ends.
        # --- Trigger hysteresis / cooldown state ---
        self.prev_loss = 0.0
        self.prev_profit = 0.0
        self.prev_drawdown = 0.0
        self.last_sl_step = -10**9
        self.last_tp_step = -10**9
        self.last_dd_step = -10**9
        return self._next_observation(), {}
    
    def get_final_metrics(self):
        return getattr(self, "last_episode_metrics", {
            "cumulative_reward": 0.0,
            "net_worth": self.initial_balance,
            "balance": self.initial_balance,
            "position": 0,
            "transaction_count": 0,
            "peak": self.initial_balance,
            "history": []
        })

    def get_current_metrics(self):
        """
        Returns the up-to-date cumulative metrics (including cumulative reward) based on the current state.
        This is used by the early stopping callback at every step.
        """
        return {
            "cumulative_reward": self.cumulative_reward,
            "net_worth": self.net_worth,
            "balance": self.balance,
            "position": self.position,
            "transaction_count": self.transaction_count,
            "peak": self.peak,
            "history": self.history.copy()
        }
    
    def set_force_termination(self, force: bool = True):
        """
        Sets a flag that forces the next call to step() to immediately return done=True.
        This is used by the early stopping callback.
        """
        self._force_termination = force

    def step(self, action: np.ndarray):
    
        # If a forced termination is requested (by early stopping), end the episode immediately.
        if self._force_termination:
            obs = self._next_observation()
            self.final_metrics = self.get_current_metrics()
            self._force_termination = False  # Reset the flag.
            return obs, 0.0, True, True, {}

        terminated = False

        #print(f"DEBUG step env_rank={self.env_rank}: returning 5 items!")
        training_logger.debug(f"DEBUG step env_rank={self.env_rank}: returning 5 items!")
        training_logger.debug(f"[Env {self.env_rank}] step() called at current_step={self.current_step} with action={action}")
        if (self.current_step % 50 == 0) or self._force_termination:
            print(f"[Env {self.env_rank}] step={self.current_step} action={action} net_worth={self.net_worth:.2f}")

        training_logger.debug(
            f"[Env {self.env_rank} step()] action={action} "
            f"type={type(action)} "
            f"shape={(action.shape if hasattr(action, 'shape') else None)}"
        )

        # Capture the "current" observation (the state on which the agent acts)
        current_obs_array = self._next_observation()

        try:
            raw_action = float(np.clip(float(action[0]), -1.0, 1.0))
            smooth_alpha = float(self.reward_weights.get("action_smoothing_alpha", 0.9))
            smoothed_raw = smooth_alpha * float(self.prev_policy_action) + (1.0 - smooth_alpha) * raw_action
            smoothed_raw = float(np.clip(smoothed_raw, -1.0, 1.0))
            # Dead-zone to suppress micro-jitter trading.
            action_dead_zone = float(self.reward_weights.get("action_dead_zone", 0.05))
            if abs(smoothed_raw) < action_dead_zone:
                smoothed_raw = 0.0
            action_value = smoothed_raw
            # Apply dead-zone only during inference/testing diagnostics.
            if self.mode != "train":
                if abs(action_value) < self.hold_threshold:
                    action_value = 0.0
                if action_value > 0 and action_value < self.inference_buy_threshold:
                    action_value = 0.0  # Ignore weak buy signals
                elif action_value < 0 and abs(action_value) < self.inference_sell_threshold:
                    action_value = 0.0  # Ignore weak sell signals
            adjusted_action = np.array([action_value], dtype=np.float32)
            assert self.action_space.contains(adjusted_action), f"[Env {self.env_rank}] Invalid action: {adjusted_action}"
        except Exception as e:
            training_logger.error(f"[Env {self.env_rank}] Action validation failed: {e}")
            return self._next_observation(), -1000.0, True, False, {}        
        
        invalid_action_penalty = -0.01

        # If we've exhausted the dataset, force termination.
        if self.current_step >= len(self.df):
            terminated = True
            truncated = False
            reward = -1000
            obs = self._next_observation()
            self.history.append({
                'Date': None,
                'Close': None,
                'Action': np.nan,
                'trade_side': "HOLD",
                'Buy_Signal_Price': np.nan,
                'Sell_Signal_Price': np.nan,
                'shares_traded': 0.0,
                'delta_value': 0.0,
                'Net Worth': self.net_worth,
                'Balance': self.balance,
                'Position': self.position,
                'Reward': reward,
                'Trade_Cost': 0.0
            })
            training_logger.error(f"[Env {self.env_rank}] Terminating episode at step {self.current_step} due to data overflow.")
            return obs, reward, terminated, truncated, {}

        current_data = self.df.iloc[self.current_step]
        current_price = float(current_data['Close'])
        current_date = current_data['Date']

        shares_traded = 0
        trade_side = "HOLD"
        trade_cost = 0.0
        invalid_act_penalty = 0.0        

        net_worth = float(self.balance + self.position * current_price)

        # 1) Initialize local flags:
        stop_loss_triggered = False
        take_profit_triggered = False
        drawdown_triggered = False

        # --- Step-wise Forced Stop Loss Logic ---        
        # Retrieve the weight for forced stop penalties
        forced_stop_penalty_weight = self.reward_weights.get('forced_stop_penalty_weight', 0.001)

        forced_stop_penalty = 0.0
        stop_loss_triggered = False
        current_loss = (self.initial_balance - net_worth) / self.initial_balance if net_worth < self.initial_balance else 0.0

        stop_loss_tiers = [
            {"threshold": 0.05, "fraction_to_sell": 0.2, "penalty_factor": 1.0},
            {"threshold": 0.08, "fraction_to_sell": 0.5, "penalty_factor": 1.5},
            {"threshold": 0.10, "fraction_to_sell": 1.0, "penalty_factor": 2.0},
        ]

        # Sort tiers in descending order so the highest applicable tier is applied first.
        sorted_sl_tiers = sorted(stop_loss_tiers, key=lambda x: x["threshold"], reverse=True)
        sl_ready = (self.current_step - self.last_sl_step) >= self.sl_cooldown_steps

        for tier in sorted_sl_tiers:
            crossed = (self.prev_loss <= tier["threshold"]) and (current_loss > tier["threshold"])
            if sl_ready and crossed and self.position > 0:
                # Mark that stop-loss logic was triggered in this step
                stop_loss_triggered = True
                self.last_sl_step = self.current_step
                # Calculate incremental penalty
                tier_penalty = -forced_stop_penalty_weight * current_loss * tier["penalty_factor"] 
                #tier_penalty = -forced_stop_penalty_weight * tier["penalty_factor"] * current_loss
                forced_stop_penalty += tier_penalty

                # Perform partial (or full) liquidation
                fraction_of_shares = math.floor(self.position * tier["fraction_to_sell"])
                if fraction_of_shares == 0 and tier["fraction_to_sell"] < 1.0 and self.position > 0:
                    fraction_of_shares = 1
                if fraction_of_shares > 0:
                    proceeds = fraction_of_shares * current_price * (1 - self.transaction_cost)
                    self.balance += proceeds
                    self.position -= fraction_of_shares
                    self.transaction_count += 1
                    self.net_worth = float(self.balance + self.position * current_price)
                    self.peak = max(self.peak, net_worth)

                # If this is the highest tier (10%), do a full liquidation and truncate
                # e.g., detect threshold == 0.10 or fraction_to_sell == 1.0
                if tier.get("fraction_to_sell", 0.0) == 1.0:
                    terminated = True                
                break

        net_worth = float(self.balance + self.position * current_price)
        # Retrieve the weight for forced take-profit penalties
        forced_tp_penalty_weight = self.reward_weights.get('forced_tp_penalty_weight', 0.001)

        # Step-wise Forced Take Profit Logic with 4 Tiers
        forced_tp_penalty = 0.0
        #current_profit = (net_worth - self.initial_balance) / self.initial_balance if net_worth > self.initial_balance else 0.0
        # Compute current profit relative to the new baseline (profit_reference) instead of initial_balance
        current_profit = (net_worth - self.profit_reference) / self.profit_reference if net_worth > self.profit_reference else 0.0

        take_profit_tiers = [
            {"threshold": 0.05, "fraction_to_sell": 0.25, "penalty_factor": 1.0},
            {"threshold": 0.10, "fraction_to_sell": 0.5, "penalty_factor": 1.5},
            {"threshold": 0.15, "fraction_to_sell": 1.0, "penalty_factor": 2.0},
        ]


        # Sort tiers in descending order so the highest applicable tier is applied first.
        sorted_tp_tiers = sorted(take_profit_tiers, key=lambda x: x["threshold"], reverse=True)
        tp_ready = (self.current_step - self.last_tp_step) >= self.tp_cooldown_steps

        # We'll iterate from lower to higher threshold
        for tier in sorted_tp_tiers:
            crossed = (self.prev_profit <= tier["threshold"]) and (current_profit > tier["threshold"])
            if tp_ready and crossed and self.position > 0:
                take_profit_triggered = True
                self.last_tp_step = self.current_step
                # Apply incremental penalty
                tier_penalty = -forced_tp_penalty_weight * current_profit * tier["penalty_factor"]
                forced_tp_penalty += tier_penalty

                # Determine the number of shares to sell according to the tier's fraction
                fraction_of_shares = math.floor(self.position * tier["fraction_to_sell"])
                # Ensure at least 1 share is sold for partial liquidation if needed
                if fraction_of_shares == 0 and tier["fraction_to_sell"] < 1.0 and self.position > 0:
                    fraction_of_shares = 1

                # Execute the sale if there are shares to sell
                if fraction_of_shares > 0:
                    proceeds = fraction_of_shares * current_price * (1 - self.transaction_cost)
                    self.balance += proceeds
                    self.position -= fraction_of_shares
                    self.transaction_count += 1
                    self.net_worth = float(self.balance + self.position * current_price)
                    self.peak = max(self.peak, self.net_worth)
                    main_logger.critical(
                        f"[TakeProfit] Sold {fraction_of_shares} shares at {current_price:.2f}, proceeds={proceeds:.2f}, "
                        f"new_balance={self.balance:.2f}, new_position={self.position}, new_net_worth={self.net_worth:.2f}"
                    )

                # Cash-out excess profit: if net worth exceeds the profit reference by at least $100 or 1% increase,
                # update the profit reference and cash out the excess.
                excess = 0.0
                if self.mode != "train":
                    if self.net_worth > self.profit_reference * 1.05:
                        new_profit_reference = self.profit_reference * 1.03
                        excess = self.net_worth - new_profit_reference
                        cash_out = max(0.0, excess)

                        main_logger.critical(
                            f"[Trial {getattr(self, 'trial_id', 'N/A')}][Env {self.env_rank}][Ticker={self.ticker}][Step={self.current_step}] "
                            f"TAKE-PROFIT cash-out triggered. old_profit_ref={self.profit_reference:.2f}, net_worth={self.net_worth:.2f}, "
                            f"excess={excess:.2f}, new_profit_ref={new_profit_reference:.2f}, cash_out={cash_out:.2f}"
                        )

                        self.realized_gain += cash_out
                        self.balance -= cash_out
                        self.net_worth = float(self.balance + self.position * current_price)
                        self.profit_reference = new_profit_reference

                        main_logger.critical(
                            f"[Trial {getattr(self, 'trial_id', 'N/A')}][Env {self.env_rank}][Ticker={self.ticker}][Step={self.current_step}] "
                            f"After TAKE-PROFIT cash-out: realized_gain={self.realized_gain:.2f}, balance={self.balance:.2f}, "
                            f"net_worth={self.net_worth:.2f}, profit_reference={self.profit_reference:.2f}"
                        )
                break  # Exit the loop after processing the first applicable tier

                # If this is the highest tier (10%), we mark truncated = True
                # Typically you'd check threshold == 0.10 or penalty_factor == 3, etc.
                """ if tier.get("fraction_to_sell", 0.0) == 1.0:
                    # Full liquidation occurred; update profit reference:
                    self.profit_reference = self.net_worth
                    #terminated = True """


        profit_weight = self.reward_weights.get('profit_weight', 1.5)
        sharpe_bonus_weight = self.reward_weights.get('sharpe_bonus_weight', 0.05)
        holding_bonus_weight = self.reward_weights.get('holding_bonus_weight', 0.001)
        sharpe_bonus = 0.0

        self.peak = max(self.peak, net_worth)
        net_worth = float(self.balance + self.position * current_price)
        current_drawdown = (self.peak - net_worth) / self.peak if self.peak > 0 else 0.0
        drawdown_penalty = 0.0

        # Only apply drawdown penalties if no stop-loss was triggered
        if not stop_loss_triggered:
            # Define cumulative drawdown tiers
            drawdown_tiers = [
                {"threshold": 0.03, "penalty_factor": 1.0, "liquidate": False},  # 1% drawdown: No liquidation
                {"threshold": 0.04, "penalty_factor": 1.5, "liquidate": True, "fraction_to_sell": 0.5},  # 1.5% drawdown: Sell 50%
                {"threshold": 0.05, "penalty_factor": 2.0, "liquidate": True, "fraction_to_sell": 1.0},  # 2% drawdown: Full liquidation
            ]
            
            # Base penalty value can be adjusted; here we use a simple constant plus a scaled component.
            base_penalty = self.some_factor * current_drawdown
            dd_ready = (self.current_step - self.last_dd_step) >= self.dd_cooldown_steps
            
            # Loop through all tiers and accumulate penalties if the current_drawdown exceeds each threshold.
            for tier in drawdown_tiers:
                crossed = (self.prev_drawdown <= tier["threshold"]) and (current_drawdown > tier["threshold"])
                if dd_ready and crossed and self.position > 0:
                    # Accumulate penalty for this tier
                    drawdown_penalty -= base_penalty * tier["penalty_factor"]
                    drawdown_triggered = True
                    self.last_dd_step = self.current_step
                    # If liquidation is specified for this tier and there is a position, perform it.
                    if tier.get("liquidate", False) and self.position > 0:                        
                        frac = tier.get("fraction_to_sell", 0.0)
                        if frac > 0:
                            if frac < 1.0:
                                shares_to_sell = math.floor(self.position * frac)
                            else:
                                shares_to_sell = self.position
                            if shares_to_sell > 0:
                                proceeds = shares_to_sell * current_price * (1 - self.transaction_cost)
                                self.balance += proceeds
                                self.position -= shares_to_sell
                                self.transaction_count += 1
                                self.net_worth = float(self.balance + self.position * current_price)
                                self.peak = max(self.peak, net_worth)
                                
                    # For full liquidation, mark truncated
                    if tier.get("fraction_to_sell", 0.0) == 1.0:
                        terminated = True
                    break
            # End for tiers

        net_worth = float(self.balance + self.position * current_price)
        self.net_worth = net_worth

        if any([stop_loss_triggered, take_profit_triggered, drawdown_triggered]) and terminated:
            action_value = 0

        # ---- Target allocation trading (replaces buy/sell blocks) ----
        net_worth = float(self.balance + self.position * current_price)
        current_pos_value = float(self.position * current_price)

        # Map raw policy output [-1, 1] to long-only allocation signal [0, 1].
        alloc_signal = 1.0 / (1.0 + np.exp(-2.0 * action_value))
        alloc = float(np.clip(alloc_signal, 0.0, 1.0)) * float(self.max_position_size)
        action_value = alloc
        target_pos_value = alloc * net_worth

        min_trade_value_frac = float(self.reward_weights.get("min_trade_value_frac", 0.01))
        min_trade_value = min_trade_value_frac * net_worth
        sell_threshold_mult = float(self.reward_weights.get("sell_threshold_mult", 0.5))
        min_sell_trade_value = min_trade_value * sell_threshold_mult
        delta_value = target_pos_value - current_pos_value

        if delta_value > 0:
            if delta_value >= min_trade_value:
                max_spend = min(delta_value, self.balance)
                shares_to_buy = int(max_spend // current_price)
                if shares_to_buy > 0:
                    total_cost = shares_to_buy * current_price * (1 + self.transaction_cost)
                    if total_cost <= self.balance:
                        self.balance -= total_cost
                        self.position += shares_to_buy
                        self.transaction_count += 1
                        shares_traded = shares_to_buy
                        trade_side = "BUY"
                        trade_cost = shares_traded * current_price * self.transaction_cost
                    else:
                        invalid_act_penalty = invalid_action_penalty
            else:
                delta_value = 0.0
        elif delta_value < 0:
            if abs(delta_value) >= min_sell_trade_value:
                desired_sell_value = min(-delta_value, current_pos_value)
                shares_to_sell = int(desired_sell_value // current_price)
                shares_to_sell = min(shares_to_sell, int(self.position))
                if shares_to_sell > 0:
                    proceeds = shares_to_sell * current_price * (1 - self.transaction_cost)
                    self.position -= shares_to_sell
                    self.balance += proceeds
                    self.transaction_count += 1
                    shares_traded = shares_to_sell
                    trade_side = "SELL"
                    trade_cost = shares_traded * current_price * self.transaction_cost
            else:
                delta_value = 0.0

        net_worth = float(self.balance + self.position * current_price)
        self.net_worth = net_worth

        # IMPORTANT: compute reward-driving deltas after all step trades/liquidations.
        net_worth_change = net_worth - self.prev_net_worth
        profit_reward = (net_worth_change / max(self.initial_balance, 1e-9)) * profit_weight
        log_return = np.log(net_worth / self.prev_net_worth) if self.prev_net_worth > 0 else 0.0
        self.returns_window.append(log_return)
        if len(self.returns_window) > 30:
            self.returns_window.pop(0)
        if self.position == 0:
            self.returns_window = []
        if self.position > 0 and len(self.returns_window) >= 5:
            mean_log_return = np.mean(self.returns_window)
            std_log_return = np.std(self.returns_window) + 1e-9
            sharpe = mean_log_return / std_log_return
            sharpe_bonus = sharpe * sharpe_bonus_weight

        hold_factor = max(0, 1 - abs(action_value) / 0.1)
        raw_vol = current_data['Volatility']
        vol_thresh = self.reward_weights.get('volatility_threshold', 1.0)
        volatility_factor = 1.0 - np.clip(raw_vol / vol_thresh, 0.0, 1.0)

        mom_thresh_min = self.reward_weights.get('momentum_threshold_min', 30)
        mom_thresh_max = self.reward_weights.get('momentum_threshold_max', 70)
        if mom_thresh_max > mom_thresh_min:
            raw_rsi = current_data['RSI']
            rsi_factor = (raw_rsi - mom_thresh_min) / (mom_thresh_max - mom_thresh_min)
            rsi_factor = np.clip(rsi_factor, 0.0, 1.0)
        else:
            rsi_factor = 0.0

        favorable_hold_factor = hold_factor * volatility_factor * rsi_factor
        if self.position > 0:
            holding_bonus = favorable_hold_factor * holding_bonus_weight
        else:
            holding_bonus = 0.0

        transaction_penalty_weight = float(self.reward_weights.get('transaction_penalty_weight', 1.0))
        transaction_penalty_scale = float(self.reward_weights.get('transaction_penalty_scale', 1.0))
        transaction_penalty = -(trade_cost / self.initial_balance) * transaction_penalty_weight * transaction_penalty_scale
        turnover_penalty_weight = self.reward_weights.get("turnover_penalty_weight", 0.001)
        turnover = abs(action_value - self.prev_action)
        turnover_penalty = turnover * turnover_penalty_weight

        reward = (
            profit_reward
            + sharpe_bonus
            + forced_stop_penalty
            + forced_tp_penalty
            + drawdown_penalty
            + transaction_penalty
            - turnover_penalty
            + holding_bonus
            + invalid_act_penalty
        )

        reward_scale = float(self.reward_weights.get("reward_scale", 1.0))
        raw_reward = reward * reward_scale
        self.reward_history.append(raw_reward)
        
        normalized_reward = float(raw_reward)
        
        self.cumulative_reward += float(reward)
        
        logged_trade_side = "BUY" if (shares_traded > 0 and delta_value > 0) else ("SELL" if (shares_traded > 0 and delta_value < 0) else "HOLD")
        self.history.append({
            'Date': current_date,
            'Close': current_price,
            'ticker': self.ticker,
            'env_rank': self.env_rank,
            'Action': action_value,
            'trade_side': logged_trade_side,
            'Buy_Signal_Price': current_price if logged_trade_side == "BUY" else np.nan,
            'Sell_Signal_Price': current_price if logged_trade_side == "SELL" else np.nan,
            'shares_traded': float(shares_traded),
            'delta_value': float(delta_value),
            'Full Worth': self.net_worth + self.realized_gain, 
            'Net Worth': self.net_worth,
            'Balance': self.balance,
            'Realized Gain': self.realized_gain,
            'Position': self.position,
            'Reward': normalized_reward,
            'profit_reward': profit_reward,
            'sharpe_bonus': sharpe_bonus,
            'holding_bonus': holding_bonus,
            'Trade_Cost': trade_cost,
            'cumulative_reward': self.cumulative_reward,            
            'forced_stop_penalty': forced_stop_penalty,
            'forced_tp_penalty': forced_tp_penalty,
            'drawdown_penalty': drawdown_penalty,
            'transaction_penalty': transaction_penalty,
            'turnover_penalty': -turnover_penalty,
            'target_position_value': target_pos_value,
            'is_terminated': terminated,
            # New flags added
            'stop_loss_triggered': stop_loss_triggered,
            'take_profit_triggered': take_profit_triggered,
            'drawdown_triggered': drawdown_triggered,
            'new_profit_reference': self.profit_reference,
            'invalid_act_penalty': invalid_act_penalty,
            'profit_weight': profit_weight,
            'sharpe_bonus_weight': sharpe_bonus_weight,
            'transaction_penalty_weight': transaction_penalty_weight,
            'turnover_penalty_weight': turnover_penalty_weight,
            'holding_bonus_weight': holding_bonus_weight,            
            'inference_buy_threshold': self.inference_buy_threshold,
            'inference_sell_threshold': self.inference_sell_threshold,
            'forced_stop_penalty_weight': forced_stop_penalty_weight,
            'forced_tp_penalty_weight': forced_tp_penalty_weight,
            **{f"Obs_{k}": float(v) for k, v in self.current_obs_dict.items()}
        })


        # Store each indicator as a top-level key
        # (Remove the ones you already have if you consider them duplicates)
        # Now store the additional technical indicators from the DataFrame row.
        row_data = self.df.iloc[self.current_step].copy()
        # Remove columns that are already in your step dict (like 'Date', 'Close', etc.)
        redundant_cols = ['Date', 'Close', 'Adj Close', 'Open', 'High', 'Low', 'Volume']
        row_data.drop(labels=redundant_cols, errors='ignore', inplace=True)

        # For example, store each technical column as a separate key:
        indicator_cols = [
            "SMA10", "SMA50", "RSI", "MACD", "ADX",
            "BB_Upper", "BB_Lower", "Bollinger_Width",
            "EMA20", "VWAP", "Lagged_Return", "Volatility"
        ]
        for col in indicator_cols:
            # Prefix with 'Indicator_' if you like, or just use col
            self.history[-1][col] = row_data[col]

        # --- Revised Termination Condition ---
        # Ensure a minimum number of steps before termination.                
        MIN_STEPS = 10
        if self.current_step >= MIN_STEPS:
            if net_worth <= 0:
                terminated = True
                normalized_reward -= 10.0
                self.final_metrics = self.get_current_metrics()
            elif self.current_step >= len(self.df) - 1:
                terminated = True
                self.final_metrics = self.get_current_metrics()
            elif self.current_step >= self.max_episode_steps:
                terminated = True
                self.final_metrics = self.get_current_metrics()
            else:
                terminated = terminated
        else:
            terminated = terminated

        # Always set truncated after the termination check.
        truncated = False        

        # --------------------------------------
        # When the episode terminates, capture final metrics.
        if terminated:
            self.last_episode_metrics = {
                "cumulative_reward": sum(entry.get('Reward', 0.0) for entry in self.history),
                "net_worth": self.net_worth,
                "balance": self.balance,
                "position": self.position,
                "transaction_count": self.transaction_count,
                "peak": self.peak,
                "history": self.history.copy()  # copy the full list of step records
            }

        # Persist trigger-state markers for edge detection on the next step.
        self.prev_loss = current_loss
        self.prev_profit = current_profit
        self.prev_drawdown = current_drawdown
        self.prev_action = action_value
        self.prev_policy_action = smoothed_raw
        self.prev_target_value = target_pos_value

        if not terminated:
            self.prev_net_worth = net_worth
            self.current_step += 1
        
        training_logger.debug(f"[Env {self.env_rank}] Updated current_step: {self.current_step} / {len(self.df)}")
        self.current_step = min(self.current_step, len(self.df) - 1)

        obs = self._next_observation()
        
        return obs, normalized_reward, terminated, truncated, {}

class EarlyStoppingCallback(BaseCallback):
    """
    Monitors the running cumulative reward from each sub-environment via
    get_current_metrics(). If no improvement (by at least min_delta) is seen
    for a number of consecutive steps (patience), it forces termination on
    all sub-environments and stops training.
    """
    def __init__(self, monitor: str, patience: int, min_delta: float = 0.0, verbose: int = 0, trial_id: int = None):
        super(EarlyStoppingCallback, self).__init__(verbose)
        self.monitor = monitor  # (for documentation; not used directly)
        self.patience = patience
        self.min_delta = min_delta
        self.trial_id = trial_id
        self.best_value = -np.inf
        self.no_improve_steps = 0

    def _on_step(self) -> bool:
        try:
            # Always retrieve the current cumulative metrics from each sub-environment.
            metrics_list = self.training_env.env_method("get_current_metrics")
            metric_values = [m.get("cumulative_reward", -np.inf) for m in metrics_list if m is not None]
            current_metric = float(np.mean(metric_values)) if metric_values else -np.inf
        except Exception as e:
            if self.verbose:
                main_logger.critical(f"[EarlyStoppingCallback] Error retrieving current metrics: {e}")
            current_metric = -np.inf

        if self.verbose:
            main_logger.critical(f"[EarlyStoppingCallback][Trial {self.trial_id}] Current cumulative reward = {current_metric}, "
                  f"Best = {self.best_value}, No Improvement Steps = {self.no_improve_steps}")

        # If improvement exceeds min_delta, reset the counter.
        if current_metric - self.best_value > self.min_delta:
            self.best_value = current_metric
            self.no_improve_steps = 0
        else:
            self.no_improve_steps += 1

        # When no improvement is seen for 'patience' steps, force termination.
        if self.no_improve_steps >= self.patience:
            if self.verbose:
                main_logger.critical(f"[EarlyStoppingCallback][Trial {self.trial_id}] Patience exceeded. Forcing termination.")
            self.training_env.env_method("set_force_termination", True)
            return False  # Stops training in model.learn()
        return True
        
        
class CustomTensorboardCallback(BaseCallback):
    def __init__(self, verbose=0, window_size=100):
        super(CustomTensorboardCallback, self).__init__(verbose)
        self.window_size = window_size
        self.rewards_buffer = []
        self.start_time = None

    def _on_training_start(self) -> None:
        self.start_time = time.time()

    def _on_step(self) -> bool:
        # Use get_attr() to fetch 'history' from the first sub-environment
        histories = self.training_env.get_attr('history', indices=0)
        if histories and histories[0]:
            last_step = histories[0][-1]
            recent_reward = last_step.get('Reward', 0.0)
            self.rewards_buffer.append(recent_reward)
            if len(self.rewards_buffer) > self.window_size:
                self.rewards_buffer.pop(0)
            rolling_avg_reward = np.mean(self.rewards_buffer)
            self.logger.record("train/reward_env", rolling_avg_reward)
            self.logger.record("train/net_worth_env", last_step.get('Net Worth', 0.0))
            self.logger.record("train/balance_env", last_step.get('Balance', 0.0))
            self.logger.record("train/position_env", last_step.get('Position', 0.0))
            
            # EXTRA: Log additional environment attributes.
            # Retrieve env_rank, ticker, current_step, and the dataframe lengths from the first sub-environment.
            env_ids = self.training_env.get_attr("env_rank", indices=0)
            tickers = self.training_env.get_attr("ticker", indices=0)
            current_steps = self.training_env.get_attr("current_step", indices=0)
            dataframes = self.training_env.get_attr("df", indices=0)
            df_lengths = [len(df) for df in dataframes] if dataframes is not None else "Unknown"
            self.logger.record("train/env_ids", str(env_ids))
            self.logger.record("train/tickers", str(tickers))
            self.logger.record("train/current_steps", str(current_steps))
            self.logger.record("train/data_lengths", str(df_lengths))
        
        # Record elapsed time (optional)
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
            self.logger.record("train/elapsed_time_env", elapsed_time)
            self.logger.record("train/elapsed_time_formatted_env", formatted_time)
        return True

    def _on_training_end(self) -> None:
        # Retrieve history from the first sub-environment
        histories = self.training_env.get_attr('history', indices=0)
        if histories and histories[0]:
            last_step = histories[0][-1]
            self.logger.record("train/final_net_worth", last_step.get('Net Worth', 0.0))
            
            # Safely sum only numeric rewards:
            valid_rewards = []
            for entry in histories[0]:
                r = entry.get('Reward', 0.0)
                if isinstance(r, (int, float)):
                    valid_rewards.append(r)
                else:
                    self.logger.record("train/non_numeric_reward_detected", str(r))
                    valid_rewards.append(0.0)
            total_reward = sum(valid_rewards)
            self.logger.record("train/final_reward", total_reward)
            self.logger.record("train/final_balance", last_step.get('Balance', 0.0))
            self.logger.record("train/final_position", last_step.get('Position', 0.0))
            if valid_rewards:
                final_rolling_avg = np.mean(valid_rewards[-self.window_size:])
            else:
                final_rolling_avg = 0.0
            self.logger.record("train/final_rolling_avg_reward", final_rolling_avg)
            
            # EXTRA: Log additional final attributes from the first sub-environment
            env_ids = self.training_env.get_attr("env_rank", indices=0)
            tickers = self.training_env.get_attr("ticker", indices=0)
            current_steps = self.training_env.get_attr("current_step", indices=0)
            dataframes = self.training_env.get_attr("df", indices=0)
            df_lengths = [len(df) for df in dataframes] if dataframes is not None else "Unknown"
            self.logger.record("train/final_env_ids", str(env_ids))
            self.logger.record("train/final_tickers", str(tickers))
            self.logger.record("train/final_current_steps", str(current_steps))
            self.logger.record("train/final_data_lengths", str(df_lengths))
        else:
            self.logger.record("train/final_net_worth", 0.0)
            self.logger.record("train/final_reward", 0.0)
            self.logger.record("train/final_balance", 0.0)
            self.logger.record("train/final_position", 0.0)
            self.logger.record("train/final_rolling_avg_reward", 0.0)

def calculate_max_drawdown(net_worth_series: pd.Series) -> float:
    rolling_max = net_worth_series.cummax()
    drawdown = (net_worth_series - rolling_max) / rolling_max
    return drawdown.min()

def calculate_annualized_return(net_worth_series: pd.Series, periods_per_year: int = 252) -> float:
    start_value = net_worth_series.iloc[0]
    end_value = net_worth_series.iloc[-1]
    num_periods = len(net_worth_series)
    if num_periods == 0:
        return 0.0
    return (end_value / start_value) ** (periods_per_year / num_periods) - 1

def generate_unique_study_name(base_name='rl_trading_agent_study'):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}"

def compute_sharpe_ratio(rewards, risk_free_rate=0.0, epsilon=1e-8, cap=10.0, min_std=1e-6, penalty_value=-10.0):
    """
    Compute the Sharpe Ratio while penalizing inactive trading.
    If the standard deviation of rewards is below min_std (indicating low trading activity),
    return a penalty value.
    """
    rewards = np.array(rewards)
    std_dev = np.std(rewards)
    if std_dev < min_std:
        # Penalize inactive strategies (very low volatility)
        return penalty_value
    sharpe = (np.mean(rewards) - risk_free_rate) / (std_dev + epsilon)
    return min(sharpe, cap)

def compute_sortino_ratio(rewards, risk_free_rate=0.0, epsilon=1e-8, cap=10.0, min_std=1e-6, penalty_value=-10.0):
    """
    Compute the Sortino Ratio while penalizing inactive trading.
    If the standard deviation of negative rewards is extremely low, return a penalty value.
    """
    rewards = np.array(rewards)
    negative_rewards = rewards[rewards < risk_free_rate]
    if len(negative_rewards) == 0 or np.std(negative_rewards) < min_std:
        return penalty_value
    sortino = (np.mean(rewards) - risk_free_rate) / (np.std(negative_rewards) + epsilon)
    return min(sortino, cap)

def compute_max_drawdown(rewards: np.ndarray) -> float:
    """
    Treat 'rewards' as a cumulative series (like net worth or cumulative composite).
    Returns max drawdown as a positive fraction (e.g. 0.2 means 20% drawdown).
    If the series is strictly negative or zero, returns 0 or negative value for safety.
    """
    if len(rewards) == 0:
        return 0.0
    # Convert rewards to a cumulative series if it isn't already
    cumulative = np.cumsum(rewards)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / np.maximum(peak, 1e-9)
    return -drawdown.min()  # negative min => positive drawdown

def compute_expected_return_per_trade(trade_returns):
    """
    Compute the expected return per trade (expectancy) using:
    
        Expectancy = P(win) * avg_win - P(loss) * avg_loss
        
    where:
      - P(win) is the proportion of profitable trades,
      - avg_win is the average profit on winning trades,
      - P(loss) is the proportion of losing trades,
      - avg_loss is the average absolute loss on losing trades.
    """
    trade_returns = np.array(trade_returns)
    if len(trade_returns) == 0:
        return 0.0
    
    winning_trades = trade_returns[trade_returns > 0]
    losing_trades = trade_returns[trade_returns < 0]
    
    win_rate = len(winning_trades) / len(trade_returns) if len(trade_returns) > 0 else 0
    loss_rate = len(losing_trades) / len(trade_returns) if len(trade_returns) > 0 else 0
    
    avg_win = np.mean(winning_trades) if len(winning_trades) > 0 else 0
    avg_loss = np.mean(np.abs(losing_trades)) if len(losing_trades) > 0 else 0
    
    expectancy = win_rate * avg_win - loss_rate * avg_loss
    return expectancy
def objective(
    trial,
    train_tickers: list,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
    transaction_cost: float,
    preloaded_data: Optional[dict] = None
):
    import math
    import numpy as np
    import torch
    import pandas as pd
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList

    # === Define PPO Hyperparameters ===
    learning_rate = trial.suggest_float('learning_rate', 1e-5, 5e-4, log=True)
    #n_steps = trial.suggest_categorical('n_steps', [128, 256, 512])
    n_steps = trial.suggest_categorical('n_steps', [256])
    batch_size = trial.suggest_categorical('batch_size', [32, 64])
    gamma = trial.suggest_uniform('gamma', 0.98, 0.999)
    gae_lambda = trial.suggest_uniform('gae_lambda', 0.80, 1.00)
    clip_range = trial.suggest_uniform('clip_range', 0.1, 0.3)
    ent_coef = trial.suggest_loguniform('ent_coef', 1e-4, 1e-1)
    vf_coef = trial.suggest_uniform('vf_coef', 0.1, 0.5)
    max_grad_norm = trial.suggest_uniform('max_grad_norm', 0.5, 1.0)
    #net_arch_str = trial.suggest_categorical('net_arch', ['128_128', '256_256', '128_256_128'])
    
    # === Define Environment-Specific Tuning Parameters ===
    #drawdown_penalty_factor = trial.suggest_float('drawdown_penalty_factor', 0.0001, 1.0, log=True)
    #drawdown_penalty_factor = trial.suggest_float('drawdown_penalty_factor', 0.5, 1000.0, log=False)
    drawdown_penalty_factor = trial.suggest_float('drawdown_penalty_factor', 0.001, 2.0, log=True)
    tuned_stop_loss = trial.suggest_float('stop_loss', 0.80, 0.95, step=0.01)
    tuned_take_profit = trial.suggest_float('take_profit', 1.05, 1.20, step=0.01)
    tuned_transaction_cost = trial.suggest_float('transaction_cost', 0.0001, 0.0005, step=0.0001)
    tuned_reward_scale = trial.suggest_float('reward_scale', 0.5, 2.0, step=0.1)
    tuned_max_position_size = trial.suggest_float('max_position_size', 0.1, 0.5, step=0.1)
    tuned_max_drawdown = trial.suggest_float('max_drawdown', 0.1, 0.3, step=0.01)
    profit_weight = trial.suggest_float('profit_weight', 0.5, 30.0, log=True)
    sharpe_bonus_weight = trial.suggest_float('sharpe_bonus_weight', 0.001, 0.5, log=True)
    transaction_penalty_weight = trial.suggest_float('transaction_penalty_weight', 0.1, 20.0, log=True)
    turnover_penalty_weight = trial.suggest_float("turnover_penalty_weight", 0.01, 2.0, log=True)
    min_trade_value_frac = trial.suggest_float("min_trade_value_frac", 0.005, 0.03)
    action_dead_zone = trial.suggest_float("action_dead_zone", 0.03, 0.10)
    action_smoothing_alpha = trial.suggest_float("action_smoothing_alpha", 0.60, 0.85)
    sell_threshold_mult = trial.suggest_float("sell_threshold_mult", 0.3, 0.7)
    holding_bonus_weight = trial.suggest_float('holding_bonus_weight', 0.0, 0.2, log=False)
    transaction_penalty_scale = trial.suggest_float('transaction_penalty_scale', 0.5, 2.0)
    volatility_threshold = trial.suggest_float("volatility_threshold", 0.5, 2.0)
    momentum_threshold_min = trial.suggest_float("momentum_threshold_min", 30, 45)
    momentum_threshold_max = trial.suggest_float("momentum_threshold_max", 55, 70)
    hold_threshold = 0.0
    
    tuned_inference_buy_threshold = trial.suggest_float("inference_buy_threshold", 0.1, 0.5)
    tuned_inference_sell_threshold = trial.suggest_float("inference_sell_threshold", 0.1, 0.5)

    # In the objective function, add:
    """ forced_stop_penalty_weight = trial.suggest_float("forced_stop_penalty_weight", 0.001, 5.0, log=True)
    forced_tp_penalty_weight = trial.suggest_float("forced_tp_penalty_weight", 0.001, 5.0, log=True) """

    """ forced_stop_penalty_weight = trial.suggest_float("forced_stop_penalty_weight", 0.5, 1000.0, log=False)
    forced_tp_penalty_weight = trial.suggest_float("forced_tp_penalty_weight", 0.5, 1000.0, log=False) """

    forced_stop_penalty_weight = trial.suggest_float("forced_stop_penalty_weight", 0.001, 2.0, log=True)
    forced_tp_penalty_weight = trial.suggest_float("forced_tp_penalty_weight", 0.001, 2.0, log=True)

    # === Build Environment List and Store Ticker-Env Pairs ===
    env_factories = []
    env_pairs = []  # list of (ticker, env_instance)
    for i, ticker in enumerate(train_tickers):
        main_logger.info(f"[Trial {trial.number}] Creating training environment for ticker {ticker}")
        if preloaded_data is not None:
            # When preloaded data is provided, never hit network inside Optuna trials.
            df_full = preloaded_data.get(ticker, pd.DataFrame()).copy()
        else:
            df_full = get_data(ticker, "2018-01-01", "2025-02-05")
        if df_full.empty:
            main_logger.warning(f"[Trial {trial.number}] No data for ticker {ticker}. Skipping.")
            continue
        split_idx = int(len(df_full) * 0.8)
        df_train = df_full.iloc[:split_idx].copy()
        if df_train.empty:
            main_logger.warning(f"[Trial {trial.number}] Training data empty for ticker {ticker}. Skipping.")
            continue

        env_kwargs = dict(
            df=df_train,
            ticker=ticker,
            initial_balance=initial_balance,
            stop_loss=tuned_stop_loss,
            take_profit=tuned_take_profit,
            max_position_size=tuned_max_position_size,
            max_drawdown=tuned_max_drawdown,
            annual_trading_days=annual_trading_days,
            transaction_cost=tuned_transaction_cost,
            env_rank=i,
            some_factor=drawdown_penalty_factor,
            hold_threshold=hold_threshold,
            reward_weights={
                'reward_scale': tuned_reward_scale,
                'profit_weight': profit_weight,
                'sharpe_bonus_weight': sharpe_bonus_weight,
                'transaction_penalty_weight': transaction_penalty_weight,
                'turnover_penalty_weight': turnover_penalty_weight,
                'min_trade_value_frac': min_trade_value_frac,
                'sell_threshold_mult': sell_threshold_mult,
                'action_dead_zone': action_dead_zone,
                'action_smoothing_alpha': action_smoothing_alpha,
                'holding_bonus_weight': holding_bonus_weight,
                'transaction_penalty_scale': transaction_penalty_scale,
                'volatility_threshold': volatility_threshold,
                'momentum_threshold_min': momentum_threshold_min,
                'momentum_threshold_max': momentum_threshold_max,
                'forced_stop_penalty_weight': forced_stop_penalty_weight,
                'forced_tp_penalty_weight': forced_tp_penalty_weight
            },
            max_episode_steps=len(df_train),
            mode="train",
            inference_buy_threshold=tuned_inference_buy_threshold,
            inference_sell_threshold=tuned_inference_sell_threshold
        )
        env_instance = SingleStockTradingEnv(**env_kwargs)
        main_logger.info(f"[Trial {trial.number}] Environment for ticker {ticker} created (env_rank={i}).")
        env_pairs.append((ticker, env_instance))
        env_factories.append(make_env_factory(env_kwargs))
    
    if not env_factories:
        main_logger.critical(f"[Trial {trial.number}] No training environments were created. Exiting trial.")
        return -math.inf

    vec_env_train = SubprocVecEnv(env_factories)
    vec_env_train = VecNormalize(vec_env_train, norm_obs=True, norm_reward=False, clip_obs=10.0, clip_reward=10.0)
    
    # === Build PPO Model with Dynamic Network Architecture ===
    # Sample the number of layers (4-8) and each layer's size ([64, 128, 256])
    num_layers = trial.suggest_int("num_layers", 2, 4)
    net_arch = []
    for layer_i in range(num_layers):
        layer_size = trial.suggest_categorical(f"layer_size_{layer_i}", [64, 128])
        net_arch.append(layer_size)

    policy_kwargs = dict(
        activation_fn=torch.nn.ReLU,
        net_arch=net_arch
    )
    
    trial_log_dir = TB_LOG_DIR / f"trial_{trial.number}"
    trial_log_dir.mkdir(parents=True, exist_ok=True)
    
    model = PPO(
        'MlpPolicy',
        vec_env_train,
        verbose=0,
        seed=RANDOM_SEED,
        policy_kwargs=policy_kwargs,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        ent_coef=ent_coef,
        vf_coef=vf_coef,
        max_grad_norm=max_grad_norm,
        tensorboard_log=str(trial_log_dir),
        device='cpu'
    )
    
    # === Set Up Callbacks ===
    trial_checkpoint_dir = RESULTS_DIR / f"checkpoints_trial_{trial.number}"
    trial_checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_callback = CheckpointCallback(
        save_freq=500,
        save_path=str(trial_checkpoint_dir),
        name_prefix="ppo_model"
    )
    custom_callback = CustomTensorboardCallback()
    early_stopping_callback = EarlyStoppingCallback(
        monitor='cumulative_reward',  # Now reflecting the running cumulative reward from get_current_metrics()
        patience=500,
        min_delta=1e-5,
        verbose=1,
        trial_id=trial.number
    )

    callback_list = CallbackList([custom_callback, checkpoint_callback, early_stopping_callback])
    
    # === PPO Training ===
    total_timesteps = 15000
    start_time = time.time()
    main_logger.info(f"[Trial {trial.number}] Trial Hyperparameters: {trial.params}")
    main_logger.info(f"[Trial {trial.number}] Starting PPO training with {total_timesteps} timesteps.")
    try:
        model.learn(total_timesteps=total_timesteps, callback=callback_list)
    except Exception as e:
        error_message = traceback.format_exc()  # Capture full traceback
        main_logger.critical(f"[Trial {trial.number}] Training failed with exception:\n{error_message}")
        return -np.inf
    duration = time.time() - start_time
    main_logger.info(f"[Trial {trial.number}] Finished PPO training in {duration:.2f} seconds.")
    
    # === Rollout Evaluation ===
    vec_env_train.training = False    
    vec_env_train.norm_reward = False
    # For example, if training used the default Â±10 clipping:
    vec_env_train.clip_obs = 10.0      # match training's observation clipping range
    vec_env_train.clip_reward = 10.0   # match training's reward clipping range

    num_episodes_to_run = 1  # or desired number
    all_episode_rewards = []

    for episode in range(num_episodes_to_run):
        main_logger.info(f"[Trial {trial.number}] Starting rollout episode {episode + 1}.")
        obs = vec_env_train.reset()
        
        # Log initial current_step values for each ticker:
        for idx, (ticker, env_instance) in enumerate(env_pairs):
            cs = env_instance.current_step
            total_steps = len(env_instance.df)
            main_logger.info(f"[Trial {trial.number}] Rollout episode {episode + 1} start for ticker {ticker}: current_step = {cs} / {total_steps}")

        done = [False] * vec_env_train.num_envs
        ep_rewards = np.zeros(vec_env_train.num_envs, dtype=np.float64)
        episode_steps = 0
        
        max_rollout_steps = 1500  # or a fixed number if you prefer, e.g., 500
        while not all(done) and episode_steps < max_rollout_steps:
            action, _ = model.predict(obs, deterministic=False)
            obs, rewards, done, infos = vec_env_train.step(action)

            # Log the done flags and infos for this step:
            main_logger.debug(f"[Trial {trial.number}] Step {episode_steps}: done = {done}")
            main_logger.debug(f"[Trial {trial.number}] Step {episode_steps}: infos = {infos}")

            ep_rewards += rewards
            episode_steps += 1
        main_logger.info(f"[Trial {trial.number}] Episode {episode + 1} complete: {episode_steps} steps, rewards: {ep_rewards}")
        
        # Log final current_step values for each ticker:
        for idx, (ticker, env_instance) in enumerate(env_pairs):
            cs = env_instance.current_step
            total_steps = len(env_instance.df)
            main_logger.info(f"[Trial {trial.number}] Rollout episode {episode + 1} end for ticker {ticker}: current_step = {cs} / {total_steps}")
        
        all_episode_rewards.extend(ep_rewards)

    if len(all_episode_rewards) == 0:
        rollout_cumulative_reward = -math.inf
    else:
        rollout_cumulative_reward = float(np.mean(all_episode_rewards))
    main_logger.info(f"[Trial {trial.number}] Rollout cumulative reward: {rollout_cumulative_reward}") 
    
    # === Final Environment Evaluation via env_method() ===
    # Retrieve the final metrics from each sub-environment. Each metrics dict includes the full history.
    final_metrics_all = vec_env_train.env_method("get_final_metrics")    
    #main_logger.info(f"[Trial {trial.number}] Retrieved final_metrics_all: {final_metrics_all}")    

    # Collect full net worth from each sub-environment's history
    full_worth_list = []
    for metrics_dict in final_metrics_all:
        if metrics_dict is None:
            continue
        history = metrics_dict.get("history", [])
        if len(history) == 0:
            continue
        # Use 'Full Worth' if available; fallback to 'Net Worth' if not.
        final_record = history[-1]
        full_worth = final_record.get("Full Worth", final_record.get("Net Worth", 0.0))
        full_worth_list.append(full_worth)

    # Compute average final full net worth across sub-environments
    if len(full_worth_list) == 0:
        avg_full_worth = 0
    else:
        avg_full_worth = float(np.mean(full_worth_list))

    # Compute net worth change relative to the initial balance
    networth_change = (avg_full_worth - initial_balance) / initial_balance
    cost_fracs = []
    for metrics_dict in final_metrics_all:
        history = metrics_dict.get("history", []) if metrics_dict else []
        if not history:
            continue
        total_cost = sum(float(r.get("Trade_Cost", 0.0)) for r in history)
        cost_fracs.append(total_cost / max(initial_balance, 1e-9))
    avg_cost_frac = float(np.mean(cost_fracs)) if cost_fracs else 0.0
    lambda_cost = 1.0
    objective_value = float(networth_change - lambda_cost * avg_cost_frac)

    # --- Log Detailed Metrics for Each Ticker via a For Loop (using full net worth change) ---
    for idx, (ticker, env_instance) in enumerate(env_pairs):
        if idx < len(full_worth_list):
            final_full_worth = full_worth_list[idx]
            # Calculate net worth change (percentage)
            networth_change_ticker = (final_full_worth - initial_balance) / initial_balance
            
            main_logger.info("=" * 80)
            main_logger.info(f"[Trial {trial.number}] Rollout Summary for Ticker: '{ticker}'")
            main_logger.info(f"[Trial {trial.number}] Env {idx} - Final Full Net Worth = {final_full_worth:.2f}")
            main_logger.info(f"[Trial {trial.number}] Env {idx} - Net Worth Change = {networth_change_ticker*100:.2f}%")
            main_logger.info("=" * 80)

    # Log the episode length for each environment (ticker)
    for idx, (ticker, env_instance) in enumerate(env_pairs):
        metrics = final_metrics_all[idx] if idx < len(final_metrics_all) else {}
        history = metrics.get("history", [])
        episode_length = len(history)
        main_logger.info(f"[Trial {trial.number}] For ticker {ticker}: Episode length = {episode_length} steps (Data length: {len(env_instance.df)})")

    # Now proceed with writing CSV files from the metrics...
    for idx, (ticker, _) in enumerate(env_pairs):
        metrics = final_metrics_all[idx] if idx < len(final_metrics_all) else {}
        summary = {
            "cumulative_reward": metrics.get("cumulative_reward", 0.0),
            "net_worth": metrics.get("net_worth", initial_balance),
            "balance": metrics.get("balance", initial_balance),
            "position": metrics.get("position", 0),
            "transaction_count": metrics.get("transaction_count", 0),
            "peak": metrics.get("peak", initial_balance)
        }
        # Raw history as recorded in self.history.
        history = metrics.get("history", [])
        
        # --- Create a normalized version of the history ---
        norm_history = []
        for record in history:
            # For reward: use the raw reward (key "raw_reward", or fallback to "Reward").
            raw_r = record.get("raw_reward", record.get("Reward", 0.0))
            norm_r = vec_env_train.normalize_reward(np.array([raw_r]))[0]
            # For observation: use the raw observation stored in "Observation".
            raw_obs = record.get("Observation", None)
            if raw_obs is not None:
                norm_obs = vec_env_train.normalize_obs(np.array([raw_obs]))[0]
            else:
                norm_obs = None
            new_record = record.copy()
            new_record["Normalized_Reward"] = norm_r
            new_record["Normalized_Observation"] = norm_obs
            norm_history.append(new_record)
        
        # Write summary CSV.
        """ summary_file = RESULTS_DIR / f"trial_{trial.number}_{ticker}_final_summary.csv"
        try:
            pd.DataFrame([summary]).to_csv(summary_file, index=False)
            main_logger.info(f"[Trial {trial.number}] Ticker {ticker}: Final summary saved to {summary_file}")
        except Exception as e:
            main_logger.warning(f"[Trial {trial.number}] Ticker {ticker}: Failed to save final summary: {e}") """
        
        # Write raw history CSV.
        history_file = RESULTS_DIR / f"trial_{trial.number}_{ticker}_full_history.csv"
        try:
            pd.DataFrame(history).to_csv(history_file, index=False)
            main_logger.info(f"[Trial {trial.number}] Ticker {ticker}: Full raw history saved to {history_file}")
        except Exception as e:
            main_logger.warning(f"[Trial {trial.number}] Ticker {ticker}: Failed to save raw history: {e}")
        
        # Write normalized history CSV.
        """ norm_history_file = RESULTS_DIR / f"trial_{trial.number}_{ticker}_full_history_normalized.csv"
        try:
            pd.DataFrame(norm_history).to_csv(norm_history_file, index=False)
            main_logger.info(f"[Trial {trial.number}] Ticker {ticker}: Normalized history saved to {norm_history_file}")
        except Exception as e:
            main_logger.warning(f"[Trial {trial.number}] Ticker {ticker}: Failed to save normalized history: {e}") """

    # Clean up vectorized environment to free memory after the trial
    vec_env_train.close()      # Close all subprocesses
    del vec_env_train          # Delete the reference
    import gc
    gc.collect()               # Force garbage collection

    return objective_value


if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    main_logger.info("Starting pipeline for multiâ€ticker training (ITC, APOLLOTYRE) and singleâ€ticker testing (GRINDWELL).")

    # ----------------------------------------------------------------
    # 1. Function to read CSV from 'data/' and parse indicators
    # ----------------------------------------------------------------
    import os
    import pandas as pd
    import yfinance as yf
    from pathlib import Path
    from ta import trend, momentum, volatility, volume

    DATA_CACHE = {}
    DATA_CACHE_LOCK = threading.Lock()
    YF_RATE_LIMIT_COOLDOWN_UNTIL = 0.0

    def get_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetches data from yfinance for a given ticker and date range, then performs
        validations and technical indicator calculations. Returns a validated
        DataFrame or an empty DataFrame if any critical validation fails.
        """
        cache_key = (ticker, start_date, end_date)
        with DATA_CACHE_LOCK:
            cached_df = DATA_CACHE.get(cache_key)
        if cached_df is not None:
            main_logger.info(f"[get_data] Cache hit for {ticker} between {start_date} and {end_date}")
            return cached_df.copy()

        RESULTS_DIR = Path("./results")
        RESULTS_DIR.mkdir(exist_ok=True, parents=True)
        raw_csv_file = RESULTS_DIR / f"data_fetched_{ticker}.csv"

        # Prefer existing on-disk cache before any network call.
        if raw_csv_file.exists():
            try:
                cached_disk_df = pd.read_csv(raw_csv_file)
                cached_disk_df["Date"] = pd.to_datetime(cached_disk_df["Date"], errors="coerce")
                cached_disk_df.dropna(subset=["Date"], inplace=True)
                cached_disk_df.sort_values("Date", inplace=True)
                cached_disk_df.reset_index(drop=True, inplace=True)
                if len(cached_disk_df) >= 200:
                    main_logger.info(f"[get_data] Using on-disk cache for {ticker}: {raw_csv_file}")
                    with DATA_CACHE_LOCK:
                        DATA_CACHE[cache_key] = cached_disk_df.copy()
                    return cached_disk_df
            except Exception as disk_e:
                main_logger.warning(f"[get_data] Could not read on-disk cache for {ticker}: {disk_e}")

        global YF_RATE_LIMIT_COOLDOWN_UNTIL
        now_ts = time.time()
        if now_ts < YF_RATE_LIMIT_COOLDOWN_UNTIL:
            cooldown_left = int(YF_RATE_LIMIT_COOLDOWN_UNTIL - now_ts)
            main_logger.warning(
                f"[get_data] Skipping yfinance for {ticker}; rate-limit cooldown active ({cooldown_left}s left)."
            )
            with DATA_CACHE_LOCK:
                DATA_CACHE[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        main_logger.info(f"Fetching data from yfinance for ticker {ticker} between {start_date} and {end_date}")

        required_columns = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
        df = pd.DataFrame()
        max_retries = 1
        for attempt in range(1, max_retries + 1):
            try:
                # Disable internal threading to reduce request bursts.
                df = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    auto_adjust=False,
                    group_by="ticker",
                    progress=False,
                    threads=False
                )
                if not df.empty:
                    break
                main_logger.warning(
                    f"[get_data] Empty response from yfinance for {ticker} on attempt {attempt}/{max_retries}."
                )
            except Exception as e:
                err_msg = str(e)
                is_rate_limited = ("YFRateLimitError" in err_msg) or ("Too Many Requests" in err_msg)
                if attempt < max_retries and is_rate_limited:
                    sleep_s = min(60, 5 * (2 ** (attempt - 1)))
                    main_logger.warning(
                        f"[get_data] Rate limited for {ticker} (attempt {attempt}/{max_retries}). "
                        f"Sleeping {sleep_s}s before retry."
                    )
                    time.sleep(sleep_s)
                    continue
                if is_rate_limited:
                    YF_RATE_LIMIT_COOLDOWN_UNTIL = time.time() + 15 * 60
                    main_logger.warning(
                        f"[get_data] Rate limit detected; enabling 900s cooldown for yfinance calls."
                    )
                main_logger.error(f"Error fetching data from yfinance for ticker {ticker}: {e}")
                break

            if attempt < max_retries:
                # Small jitter between attempts to avoid synchronized hits.
                time.sleep(1 + random.random())

        if df.empty:
            # yfinance can return empty on throttling without raising; enter cooldown to avoid hammering.
            YF_RATE_LIMIT_COOLDOWN_UNTIL = time.time() + 15 * 60
            main_logger.warning(
                f"[get_data] Empty yfinance response for {ticker}; enabling 900s cooldown."
            )
            if raw_csv_file.exists():
                try:
                    fallback_df = pd.read_csv(raw_csv_file)
                    fallback_df["Date"] = pd.to_datetime(fallback_df["Date"], errors="coerce")
                    fallback_df.dropna(subset=["Date"], inplace=True)
                    fallback_df.sort_values("Date", inplace=True)
                    fallback_df.reset_index(drop=True, inplace=True)
                    if len(fallback_df) >= 200:
                        main_logger.warning(
                            f"[get_data] Using local fallback CSV for {ticker}: {raw_csv_file}"
                        )
                        with DATA_CACHE_LOCK:
                            DATA_CACHE[cache_key] = fallback_df.copy()
                        return fallback_df
                except Exception as csv_e:
                    main_logger.error(f"[get_data] Failed local fallback for {ticker}: {csv_e}")

            main_logger.error(f"No usable data fetched from yfinance for ticker {ticker}")
            with DATA_CACHE_LOCK:
                DATA_CACHE[cache_key] = pd.DataFrame()
            return pd.DataFrame()

        # Reset index to ensure Date is a column
        df.reset_index(inplace=True)

        # Flatten MultiIndex columns if present and remove ticker prefixes
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[1] if col[1] else col[0] for col in df.columns]

        # Check for duplicates
        if df.columns.duplicated().any():
            duplicated_cols = df.columns[df.columns.duplicated()].unique()
            main_logger.error(f"[get_data] Duplicate columns found for {ticker}: {list(duplicated_cols)}")
            return pd.DataFrame()

        # Confirm required columns exist
        for col in required_columns:
            if col not in df.columns:
                main_logger.error(f"[get_data] Missing required column '{col}' for {ticker}.")
                return pd.DataFrame()

        # Convert Date to datetime format
        try:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df.dropna(subset=["Date"], inplace=True)
        except Exception as e:
            main_logger.error(f"[get_data] Error converting 'Date' column for {ticker}: {e}")
            return pd.DataFrame()

        # Sort by Date
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        # Convert numeric columns
        numeric_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        
        # Check minimum data length
        if len(df) < 200:
            main_logger.error(f"[get_data] Not enough data points ({len(df)}) for ticker {ticker}. Need >= 200.")
            return pd.DataFrame()
        
        # Calculate technical indicators
        try:
            close = df["Close"].squeeze()
            high = df["High"].squeeze()
            low = df["Low"].squeeze()
            vol_series = df["Volume"].squeeze()

            df['Log_Close'] = np.log(df['Close'])
            df['Log_Return'] = df['Log_Close'].diff().fillna(0)

            df["SMA10"] = trend.SMAIndicator(close=close, window=10).sma_indicator()
            df["SMA50"] = trend.SMAIndicator(close=close, window=50).sma_indicator()
            df["RSI"] = momentum.RSIIndicator(close=close, window=14).rsi()
            df["MACD"] = trend.MACD(close=close).macd()
            df["ADX"] = trend.ADXIndicator(high=high, low=low, close=close, window=14).adx()
            bollinger = volatility.BollingerBands(close=close, window=20, window_dev=2)
            df["BB_Upper"] = bollinger.bollinger_hband()
            df["BB_Lower"] = bollinger.bollinger_lband()
            df["Bollinger_Width"] = bollinger.bollinger_wband()
            df["EMA20"] = trend.EMAIndicator(close=close, window=20).ema_indicator()
            df["VWAP"] = volume.VolumeWeightedAveragePrice(high=high, low=low, close=close, volume=vol_series, window=14).volume_weighted_average_price()
            df["Lagged_Return"] = close.pct_change().fillna(0)
            df["Volatility"] = volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()

            # 1) Chaikin Money Flow
            cmf_indicator = ChaikinMoneyFlowIndicator(
                high=high, low=low, close=close, volume=vol_series, window=20
            )
            df["Chaikin_MF"] = cmf_indicator.chaikin_money_flow()

            # 2) On-Balance Volume
            obv_indicator = OnBalanceVolumeIndicator(close=close, volume=vol_series)
            df["OBV"] = obv_indicator.on_balance_volume()

            # 3) Stochastic RSI (14, 3, 3) as typical defaults
            #    If you already have RSI, Stochastic Oscillator, etc., you can combine them or rename them.
            stoch_rsi = StochasticOscillator(
                close=close, high=high, low=low, window=14, smooth_window=3
            )
            df["Stoch_RSI"] = stoch_rsi.stoch()
            df["Stoch_RSI_signal"] = stoch_rsi.stoch_signal()

            # 4) Keltner Channels (using a 20-day EMA + 10-day ATR, for example)
            kc_indicator = KeltnerChannel(
                high=high, low=low, close=close, window=20, window_atr=10
            )
            df["KC_High"] = kc_indicator.keltner_channel_hband()
            df["KC_Low"]  = kc_indicator.keltner_channel_lband()
            df["KC_Mid"]  = kc_indicator.keltner_channel_mband()

            # 5) Force Index
            #    Often used with a short window (e.g., 2) for near-term microstructure signals
            fi_indicator = ForceIndexIndicator(close=close, volume=vol_series, window=2)
            df["Force_Index"] = fi_indicator.force_index()

            # Optional: If you want â€œIntraday_Pct_Rangeâ€ or â€œRange/Openâ€
            df["Intraday_Pct_Range"] = (df["High"] - df["Low"]) / df["Open"].replace(0, np.nan)
        except Exception as e:
            main_logger.error(f"[get_data] Error calculating indicators for {ticker}: {e}")
            return pd.DataFrame()

        # Drop initial warm-up region where rolling indicators are unreliable.
        warmup_rows = 60
        if len(df) > warmup_rows:
            df = df.iloc[warmup_rows:].copy()
            df.reset_index(drop=True, inplace=True)
        if len(df) < 200:
            main_logger.error(f"[get_data] Not enough data points after warm-up ({len(df)}) for ticker {ticker}.")
            return pd.DataFrame()

        # Fill missing values
        df.fillna(method="ffill", inplace=True)
        df.fillna(0, inplace=True)

        # Save raw CSV
        try:
            df.to_csv(raw_csv_file, index=False)
            main_logger.info(f"[get_data] Wrote raw CSV for ticker {ticker}: {raw_csv_file}")
        except Exception as e:
            main_logger.error(f"[get_data] Failed to write raw CSV for {ticker}: {e}")
            return pd.DataFrame()
        
        main_logger.info(f"[get_data] Successfully fetched & validated data for {ticker}. Final shape: {df.shape}")
        with DATA_CACHE_LOCK:
            DATA_CACHE[cache_key] = df.copy()
        return df


    """ train_tickers = [
    # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
    "APOLLOTYRE.NS", "KPIL.NS", "EXIDEIND.NS",

    # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
    "GABRIEL.NS", "TATVA.NS"
    ]

    optuna_tickers = [
        # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
        "ICICIBANK.NS", "JYOTHYLAB.NS", "APOLLOTYRE.NS",

        # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
        "GODREJIND.NS", "MAHSEAMLES.NS"
    ] """

    train_tickers = [
    # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
    "APOLLOTYRE.NS", "KPIL.NS",

    # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
    "GABRIEL.NS"
    ]

    optuna_tickers = [
        # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
        "ICICIBANK.NS", "JYOTHYLAB.NS",

        # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
        "TATVA.NS"
    ]

    """ train_tickers = [
    # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
    "GRINDWELL.NS", "APOLLOTYRE.NS", "EXIDEIND.NS", "KPIL.NS", "ICICIBANK.NS",

    # ðŸ”¹ **Large-Cap Stocks** (NIFTY 50)
    "HDFCBANK.NS", "INFY.NS", "TCS.NS", "RELIANCE.NS",

    # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
    "JYOTHYLAB.NS", "GABRIEL.NS", "MAHSEAMLES.NS", "GODREJIND.NS", "TATVA.NS"
    ]


    optuna_tickers = [
    # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
    "ICICIBANK.NS", "APOLLOTYRE.NS", "JYOTHYLAB.NS", "KPIL.NS",

    # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
    "CROMPTON.NS", "GABRIEL.NS", "MAHSEAMLES.NS", "GODREJIND.NS", "TATVA.NS"
    ] """

    """ train_tickers = [
    "GRINDWELL.NS",  # Mid-Cap
    "HDFCBANK.NS",   # Large-Cap
    "JYOTHYLAB.NS"   # Small-Cap
    ]

    optuna_tickers = [
        "ICICIBANK.NS",  # Mid-Cap
        "CROMPTON.NS",   # Small-Cap
        "APOLLOTYRE.NS"  # Mid-Cap
    ] """


    # ----------------------------------------------------------------
    # 3. Prepare single ticker (GRINDWELL) for final testing
    # ----------------------------------------------------------------
    """ test_ticker = "ITC.NS"
    df_test_full = get_data(test_ticker, "2018-01-01", "2025-02-05")
    if df_test_full.empty:
        main_logger.error(f"No data for test ticker {test_ticker}. Exiting.")
        exit()

    split_idx_test = int(len(df_test_full) * 0.8)
    test_df = df_test_full.iloc[split_idx_test:].reset_index(drop=True)
    main_logger.info(f"{test_ticker} test portion rows = {len(test_df)}") """

    # ----------------------------------------------------------------
    # 4. Basic config + Setup Optuna
    # ----------------------------------------------------------------
    INITIAL_BALANCE = 100000
    STOP_LOSS = 0.90
    TAKE_PROFIT = 1.10
    MAX_POSITION_SIZE = 0.5
    MAX_DRAWDOWN = 0.20
    ANNUAL_TRADING_DAYS = 252
    TRANSACTION_COST = 0.001

    storage = optuna.storages.RDBStorage(
        url='sqlite:///optuna_study.db',
        engine_kwargs={'connect_args': {'check_same_thread': False}}
    )
    unique_study_name = generate_unique_study_name()
    study = optuna.create_study(
        direction='maximize',
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
        storage=storage,
        study_name=unique_study_name,
        load_if_exists=False
    )

    n_trials = 8
    main_logger.info(f"Starting Optuna study for {n_trials} trials with multiple training envs.")

    # Preload once for Optuna tickers so objective() runs fully offline.
    preloaded_market_data = {}
    preload_tickers = list(optuna_tickers)
    for ticker in preload_tickers:
        df_full = get_data(ticker, "2018-01-01", "2025-02-05")
        if not df_full.empty:
            preloaded_market_data[ticker] = df_full.copy()

    available_optuna_tickers = [t for t in optuna_tickers if t in preloaded_market_data]
    if not available_optuna_tickers:
        main_logger.critical(
            f"No Optuna tickers have usable preloaded data. Requested={optuna_tickers}. "
            "Likely yfinance throttling with no local cache present."
        )
        exit()
    if len(available_optuna_tickers) < len(optuna_tickers):
        missing = [t for t in optuna_tickers if t not in available_optuna_tickers]
        main_logger.warning(
            f"Proceeding with subset of Optuna tickers due to missing data: {available_optuna_tickers}. "
            f"Missing={missing}"
        )

    study.optimize(
        lambda trial: objective(
            trial,
            train_tickers=available_optuna_tickers,
            initial_balance=100000,
            stop_loss=0.90,
            take_profit=1.10,
            max_position_size=0.5,
            max_drawdown=0.20,
            annual_trading_days=252,
            transaction_cost=0.001,
            preloaded_data=preloaded_market_data
        ),
        n_trials=n_trials,
        n_jobs=1
    )

    if study.best_params:
        best_params = study.best_params
        main_logger.info(f"[OPTUNA] Best hyperparameters: {best_params}")
    else:
        main_logger.critical("No successful trials found.")
        exit()

    if study.best_params:
        best_trial = study.best_trial
        best_params = best_trial.params
        best_score = best_trial.value
        #user_attrs = best_trial.user_attrs
        main_logger.info(f"[OPTUNA] Best trial number: {best_trial.number}")
        main_logger.info(f"[OPTUNA] Best hyperparameters: {best_params}")
        main_logger.info(f"[OPTUNA] Best composite score: {best_score:.4f}")
        #main_logger.info(f"[OPTUNA] Best trial user attributes: {user_attrs}")
    else:
        main_logger.critical("No successful trials found.")
        exit()
    # Assume these tuned values come from your Optuna study:
    # Diagnostic override for test-time action filtering to verify the policy can trade.
    optuna_tuned_inference_buy_threshold = 0.1
    optuna_tuned_inference_sell_threshold = 0.1

    # ----------------------------------------------------------------
    # 5. Final training pass with best hyperparams
    # ----------------------------------------------------------------
    main_logger.info("Final training pass with best hyperparams from Optuna.")

    final_envs = []
    for i, ticker in enumerate(train_tickers):
        df_full = preloaded_market_data.get(ticker, pd.DataFrame()).copy()
        if df_full.empty:
            main_logger.warning(f"No cached data for final training ticker {ticker}; skipping final env.")
            continue
        split_idx = int(len(df_full) * 0.8)
        df_train = df_full.iloc[:split_idx].reset_index(drop=True)

        env_kwargs = dict(
            df=df_train,
            ticker=ticker,
            initial_balance=INITIAL_BALANCE,
            stop_loss=best_params.get('stop_loss', STOP_LOSS),
            take_profit=best_params.get('take_profit', TAKE_PROFIT),
            max_position_size=best_params.get('max_position_size', MAX_POSITION_SIZE),
            max_drawdown=best_params.get('max_drawdown', MAX_DRAWDOWN),
            annual_trading_days=ANNUAL_TRADING_DAYS,
            transaction_cost=best_params.get('transaction_cost', TRANSACTION_COST),
            env_rank=1000 + i,
            some_factor=best_params.get('drawdown_penalty_factor', 0.01),
            hold_threshold=0.1,
            reward_weights={
                'reward_scale': best_params.get('reward_scale', 1.0),
                'profit_weight': best_params.get('profit_weight', 1.5),
                'sharpe_bonus_weight': best_params.get('sharpe_bonus_weight', 0.05),
                'transaction_penalty_weight': best_params.get('transaction_penalty_weight', 1e-3),
                'turnover_penalty_weight': best_params.get('turnover_penalty_weight', 1e-3),
                'min_trade_value_frac': best_params.get('min_trade_value_frac', 0.01),
                'sell_threshold_mult': best_params.get('sell_threshold_mult', 0.5),
                'action_dead_zone': best_params.get('action_dead_zone', 0.05),
                'action_smoothing_alpha': best_params.get('action_smoothing_alpha', 0.9),
                'holding_bonus_weight': best_params.get('holding_bonus_weight', 0.001),
                'transaction_penalty_scale': best_params.get('transaction_penalty_scale', 1.0),
                'volatility_threshold': best_params.get('volatility_threshold', 1.0),
                'momentum_threshold_min': best_params.get('momentum_threshold_min', 30),
                'momentum_threshold_max': best_params.get('momentum_threshold_max', 70),
                'forced_stop_penalty_weight': best_params.get('forced_stop_penalty_weight', 1.0),
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0)
            },
            max_episode_steps=len(df_train),
            mode="train",
            inference_buy_threshold=optuna_tuned_inference_buy_threshold,
            inference_sell_threshold=optuna_tuned_inference_sell_threshold
        )
        final_envs.append(make_env_factory(env_kwargs))    main_logger.info(f"Final training env count: {len(final_envs)} for train_tickers={train_tickers}")
    if final_envs:
        if len(final_envs) == 1:
            vec_env_final = DummyVecEnv(final_envs)
        else:
            vec_env_final = SubprocVecEnv(final_envs)
        vec_env_final = VecNormalize(vec_env_final, norm_obs=True, norm_reward=False, clip_obs=10.0, clip_reward=10.0)

        net_arch_str = best_params.get('net_arch', '128_128')
        net_arch_list = [int(x) for x in net_arch_str.split('_')]
        policy_kwargs = dict(
            activation_fn=torch.nn.ReLU,
            net_arch=net_arch_list
        )

        model_final = PPO(
            "MlpPolicy",
            vec_env_final,
            verbose=1,
            seed=RANDOM_SEED,
            policy_kwargs=policy_kwargs,
            learning_rate=best_params.get('learning_rate', 1e-4),
            n_steps=best_params.get('n_steps', 256),
            batch_size=best_params.get('batch_size', 64),
            gamma=best_params.get('gamma', 0.99),
            gae_lambda=best_params.get('gae_lambda', 0.95),
            clip_range=best_params.get('clip_range', 0.2),
            ent_coef=best_params.get('ent_coef', 0.01),
            vf_coef=best_params.get('vf_coef', 0.5),
            max_grad_norm=best_params.get('max_grad_norm', 0.5),
            tensorboard_log=str(TB_LOG_DIR / "final_model")
        )

        total_timesteps = int(best_params.get("final_timesteps", 300000))
        if total_timesteps > 0:
            main_logger.info(f"Learning final model for {total_timesteps} timesteps with multiple tickers.")
            model_final.learn(total_timesteps=total_timesteps)
        else:
            main_logger.info("Skipping final training (total_timesteps=0).")

        # Save the model and VecNormalize object to the results directory
        model_save_path = RESULTS_DIR / "ppo_final_model.zip"
        vecenv_save_path = RESULTS_DIR / "vec_normalize.pkl"
        model_final.save(str(model_save_path))
        vec_env_final.save(str(vecenv_save_path))

        main_logger.info(f"Final multi-ticker model saved to {model_save_path} and VecNormalize saved to {vecenv_save_path}.")
    else:
        main_logger.critical("No final training envs created (all df_full empty?). Skipping final training block.")

    # ----------------------------------------------------------------
    # 6. Test on multiple tickers with saved normalization and save test history to CSV
    # ----------------------------------------------------------------

    test_tickers = ["KOTAKBANK.NS", "ITC.NS", "ASIANPAINT.NS", "AXISBANK.NS", "LT.NS", "NTPC.NS", "SBIN.NS"]  # Or whichever tickers
    """ test_tickers = [
    # ðŸ”¹ **Large-Cap Stocks** (NIFTY 50)
    "ULTRACEMCO.NS", "MARUTI.NS", "HCLTECH.NS", "COALINDIA.NS",

    # ðŸ”¹ **Mid-Cap Stocks** (NIFTY Midcap 150)
    "ZEEL.NS", "CANBK.NS", "CUB.NS", "MPHASIS.NS",

    # ðŸ”¹ **Small-Cap Stocks** (NIFTY Smallcap 250)
    "KALYANKJIL.NS", "MAHSCOOTER.NS", "KNRCON.NS", "INOXWIND.NS"
    ] """

    

    for test_ticker in test_tickers:
        main_logger.info(f"Preparing test data for ticker {test_ticker}.")

        # 1) Get the DataFrame for this ticker.
        df_test_full = get_data(test_ticker, "2018-01-01", "2025-02-05")
        if df_test_full.empty:
            main_logger.error(f"No data for test ticker {test_ticker}. Skipping inference.")
            continue

        split_idx_test = int(len(df_test_full) * 0.8)
        test_df = df_test_full.iloc[split_idx_test:].reset_index(drop=True)
        main_logger.info(f"{test_ticker} test portion rows = {len(test_df)}")

        # 2) Create and wrap environment
        test_env_kwargs = dict(
            df=test_df,
            ticker=test_ticker,
            initial_balance=INITIAL_BALANCE,
            stop_loss=best_params.get('stop_loss', STOP_LOSS),
            take_profit=best_params.get('take_profit', TAKE_PROFIT),
            max_position_size=best_params.get('max_position_size', MAX_POSITION_SIZE),
            max_drawdown=best_params.get('max_drawdown', MAX_DRAWDOWN),
            annual_trading_days=ANNUAL_TRADING_DAYS,
            transaction_cost=best_params.get('transaction_cost', TRANSACTION_COST),
            env_rank=9999,
            some_factor=best_params.get('drawdown_penalty_factor', 0.01),
            hold_threshold=0.0,
            reward_weights={
                'reward_scale': best_params.get('reward_scale', 1.0),
                'profit_weight': best_params.get('profit_weight', 1.5),
                'sharpe_bonus_weight': best_params.get('sharpe_bonus_weight', 0.05),
                'transaction_penalty_weight': best_params.get('transaction_penalty_weight', 1e-3),
                'turnover_penalty_weight': best_params.get('turnover_penalty_weight', 1e-3),
                'min_trade_value_frac': best_params.get('min_trade_value_frac', 0.01),
                'sell_threshold_mult': best_params.get('sell_threshold_mult', 0.5),
                'action_dead_zone': best_params.get('action_dead_zone', 0.05),
                'action_smoothing_alpha': best_params.get('action_smoothing_alpha', 0.9),
                'holding_bonus_weight': best_params.get('holding_bonus_weight', 0.001),
                'transaction_penalty_scale': best_params.get('transaction_penalty_scale', 1.0),
                'volatility_threshold': best_params.get('volatility_threshold', 1.0),
                'momentum_threshold_min': best_params.get('momentum_threshold_min', 30),
                'momentum_threshold_max': best_params.get('momentum_threshold_max', 70),
                'forced_stop_penalty_weight': best_params.get('forced_stop_penalty_weight', 1.0),
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0)
            },
            max_episode_steps=len(test_df),
            mode="test",
            inference_buy_threshold=optuna_tuned_inference_buy_threshold,
            inference_sell_threshold=optuna_tuned_inference_sell_threshold
        )

        from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

        test_vec = SubprocVecEnv([make_env_factory(test_env_kwargs)])

        # Load the VecNormalize object from RESULTS_DIR
        vecnorm_path = RESULTS_DIR / "vec_normalize.pkl"
        if not vecnorm_path.exists():
            main_logger.error(f"VecNormalize file not found at {vecnorm_path}")
            continue
        else:
            main_logger.info(f"Loading VecNormalize from {vecnorm_path}")
        test_vec = VecNormalize.load(str(vecnorm_path), test_vec)
        test_vec.training = False
        test_vec.norm_reward = False
        # For example, if training used the default Â±10 clipping:
        test_vec.clip_obs = 10.0      # match training's observation clipping range
        test_vec.clip_reward = 10.0   # match training's reward clipping range


        # Load the final model from RESULTS_DIR
        model_path = RESULTS_DIR / "ppo_final_model.zip"
        if not model_path.exists():
            main_logger.error(f"Model file not found at {model_path}")
            continue
        else:
            main_logger.info(f"Loading model from {model_path}")
        loaded_model = PPO.load(str(model_path), env=test_vec)

        main_logger.info(f"Testing final model on ticker {test_ticker} with {len(test_df)} rows of data.")


        # 4) Run inference
        obs = test_vec.reset()
        done = [False] * test_vec.num_envs
        steps_taken = 0
        max_test_steps = len(test_df)
        rl_test_history = []

        while not all(done) and steps_taken < max_test_steps:
            action, _ = loaded_model.predict(obs, deterministic=False)
            obs, rewards, done, infos = test_vec.step(action)
            steps_taken += 1
            if steps_taken % 100 == 0:
                training_logger.info(f"[Test Ticker={test_ticker}] Step {steps_taken}: Action={action}, Rewards={rewards}")

        # 5) Retrieve the RL agentâ€™s final metrics & history
        final_metrics_list = test_vec.env_method("get_final_metrics")
        if final_metrics_list and len(final_metrics_list) > 0:
            final_metrics = final_metrics_list[0]
            rl_test_history = final_metrics.get("history", [])
            if rl_test_history:
                final_net_worth = final_metrics.get("net_worth", None)
                if final_net_worth is not None:
                    main_logger.info(f"Test complete on {test_ticker}. Final net worth: ${final_net_worth:.2f}")
                else:
                    main_logger.warning(f"Final net worth is not available in the metrics for {test_ticker}.")
            else:
                main_logger.warning(f"No test history recorded in final metrics for {test_ticker}.")
                rl_test_history = []
        else:
            main_logger.warning(f"No final metrics retrieved from the test environment for {test_ticker}.")
            rl_test_history = []

        # 6) Directly convert the environmentâ€™s step-by-step history to DataFrame
        #    (No flatten needed, because we already store indicators & fields top-level.)
        test_history_file = RESULTS_DIR / f"test_env_history_{test_ticker}.csv"
        if rl_test_history:
            rl_test_df = pd.DataFrame(rl_test_history)
            rl_test_df.to_csv(test_history_file, index=False)
            main_logger.info(f"Testing environment history for {test_ticker} saved to {test_history_file}")
        else:
            pd.DataFrame().to_csv(test_history_file, index=False)
            main_logger.warning(f"Test history was empty for {test_ticker}. Saved empty CSV at {test_history_file}")



