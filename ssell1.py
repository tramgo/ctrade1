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
from stable_baselines3.common.vec_env import SubprocVecEnv, SubprocVecEnv
from stable_baselines3.common.vec_env import VecNormalize
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import CheckpointCallback, BaseCallback, CallbackList

import torch
import warnings
from typing import Optional, Tuple, Callable, Dict, List
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
import pytz
import shutil

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

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 10
MAX_RETRY_DELAY = 120  # seconds; changeable

TICKINT = "60minute"
TRAIN_HISTORY_DAYS = 1095
TEST_HISTORY_DAYS = 365
DTDAYS = TRAIN_HISTORY_DAYS

NSE_LIQUID_UNIVERSE = [
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
    "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
    "ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA",
    "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO",
    "RELIANCE", "ONGC", "BPCL",
    "LT", "ADANIPORTS", "ULTRACEMCO",
    "SUNPHARMA", "DRREDDY", "CIPLA",
    "BHARTIARTL"
]

def kite_call_with_retry(func, *args, **kwargs):
    """
    Call a Kite function with exponential backoff retries. If an API call fails, renew the Kite session
    using the get_access_token() function and then retry the call.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES:
                factor = math.ceil(MAX_RETRY_DELAY ** (1 / (MAX_RETRIES - 1)))
                sleep_time = min(factor ** (attempt - 1), MAX_RETRY_DELAY)
                training_logger.warning(
                    f"[{func.__name__}] Attempt {attempt} failed: {e}. Retrying in {sleep_time} seconds..."
                )
                time.sleep(sleep_time)
                # Renew the Kite session if order related. (Assuming get_access_token refresh logic)
                if func.__name__ in ["place_order", "historical_data", "instruments"]:
                    try:
                        token = get_access_token()
                        kite.set_access_token(token)
                        training_logger.info("Kite session renewed successfully.")
                    except Exception as renewal_e:
                        training_logger.error(f"Failed to renew Kite session: {renewal_e}")
            else:
                msg = f"Failed to call {func.__name__} after {MAX_RETRIES} retries: {e}"
                training_logger.error(msg)
                raise RuntimeError(msg)

# --- Place these at the top of your script (after BASE_DIR is defined) ---
TOKEN_CACHE_FILE = BASE_DIR / "access_token_cache.txt"

def load_cached_token():
    if TOKEN_CACHE_FILE.exists():
        with open(TOKEN_CACHE_FILE, "r") as f:
            token = f.read().strip()
            return token
    return None

def save_token_to_cache(token):
    with open(TOKEN_CACHE_FILE, "w") as f:
        f.write(token)

# --- Revised get_valid_kite_session() using cached token ---
def get_valid_kite_session():
    # Attempt to load a cached token first.
    cached_token = load_cached_token()
    if cached_token:
        try:
            kite.set_access_token(cached_token)
            # Revised caller for profile using the utility function:
            profile = kite_call_with_retry(kite.profile)
            print(f"[Cached] Logged in as: {profile['user_name']} ({profile['user_id']})")
            return kite
        except Exception as e:
            print(f"[Cached] Token invalid or expired: {e}. Fetching new token...")

    # If no valid cached token, get a new token.
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[Attempt {attempt}] Getting access token...")
            token = get_access_token()  # Your full TOTP-based login function
            kite.set_access_token(token)
            profile = kite.profile()
            print(f"[Success] Logged in as: {profile['user_name']} ({profile['user_id']})")
            save_token_to_cache(token)  # Save the new token for future use
            return kite
        except Exception as e:
            print(f"[Error] Login attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"Retrying in {RETRY_DELAY_SECONDS} seconds...\n")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print("Max retries reached. Exiting.")
                raise

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
# ===== core intraday feature grid (20 items) =====
FEATURES_TO_SCALE = [
    # ---- momentum / returns (6) ----
    "LagRet_1", "LagRet_5", "LagRet_20",
    "OHLC_pct", "High_Low_pct", "Rel_Close_HL",

    # ---- trend / structure (3) ----
    "Trend_30", "Trend_2h", "Trend_slope",

    # ---- momentum oscillator (2) ----
    "RSI14", "MACD_z",

    # ---- volatility (2) ----
    "ATR20_log", "RealVol20_log",

    # ---- liquidity / volume regime (2) ----
    "Vol_log", "VolRegime",

    # ---- session structure (3) ----
    "MinuteNorm", "MinutesOpen", "LunchDummy",

    # ---- market regime one-hots (2) ----
    "RegimeBull", "RegimeBear"
]


LOG_TRANSFORM_FEATURES = ["Close", "Volume"]  # Only apply log transform to columns guaranteed to be > 0

import requests
import pyotp
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

API_KEY = "gqi9lxf3meq6iiwa"
API_SECRET = "1gu1alcoe96598xhooum6hxh8udf4m7o"
USERNAME = "KY4369"
PASSWORD = "Maligai321!"
TOTP_KEY = "XZ2SZ5L4CQDGAHYZQVMPDZQERZOOV3UF"  # Base32 format

kite = KiteConnect(api_key=API_KEY)

def get_access_token():
    session = requests.Session()

    # 1. Basic login
    login_resp = session.post(
        "https://kite.zerodha.com/api/login",
        data={"user_id": USERNAME, "password": PASSWORD},
    )
    request_id = login_resp.json()["data"]["request_id"]

    # 2. TOTP 2FA
    session.post(
        "https://kite.zerodha.com/api/twofa",
        data={
            "user_id": USERNAME,
            "request_id": request_id,
            "twofa_value": pyotp.TOTP(TOTP_KEY).now(),
        },
    )

    # 3. Follow redirects until we find ?request_token=...
    next_url = f"https://kite.trade/connect/login?api_key={API_KEY}"
    for _ in range(10):  # Up to 5 hops
        r = session.get(next_url, allow_redirects=False)
        location = r.headers.get("Location", "")
        parsed = urlparse(location)
        qs = parse_qs(parsed.query)
        if "request_token" in qs:
            request_token = qs["request_token"][0]
            # 4. Generate the access token
            # Revised caller for generate_session using the utility function:
            data = kite_call_with_retry(kite.generate_session, request_token, api_secret=API_SECRET)
            return data["access_token"]
        if not location:
            raise RuntimeError("No Location header – stopped early.")
        # Keep following the chain
        next_url = location

    raise RuntimeError("No request_token found after multiple redirects.")

# --- Usage ---
kite = get_valid_kite_session()
""" # 1) Log in to Zerodha to get access token
tokken = get_access_token()
kite.set_access_token(tokken)
main_logger.info("Logged in. Kite profile:", kite.profile()) """

# Get dump of all NSE instruments using Kite
instrument_dump = kite_call_with_retry(kite.instruments, "NSE")
instrument_df = pd.DataFrame(instrument_dump)

def get_instrument_token(ticker: str, instrument_df: pd.DataFrame) -> Optional[int]:
    # Assumes the instrument_df contains a 'tradingsymbol' column for ticker symbols
    token_series = instrument_df.loc[instrument_df["tradingsymbol"] == ticker, "instrument_token"]
    if not token_series.empty:
        return int(token_series.iloc[0])
    else:
        return None

def get_ticker_from_token(instrument_token: int, instrument_df: pd.DataFrame) -> Optional[str]:
    """
    Reverse lookup: Given an instrument token, returns the corresponding ticker symbol.
    
    Assumes instrument_df contains the columns:
      - 'instrument_token' : the unique ID for the instrument.
      - 'tradingsymbol' : the ticker symbol for the instrument.
    """
    ticker_series = instrument_df.loc[instrument_df["instrument_token"] == instrument_token, "tradingsymbol"]
    if not ticker_series.empty:
        return ticker_series.iloc[0]
    else:
        return None

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# We'll assume 'ta' is already installed.
from ta import trend, momentum, volatility, volume

# ----------------------------------------------------------------------
#  feature builder for RL state
# ----------------------------------------------------------------------
def build_rl_features(df: pd.DataFrame, interval: str = "1minute") -> pd.DataFrame:
    # Features here are built with past-looking rolling windows only (no centered windows),
    # so each row depends on current/past bars and does not peek into future bars.
    df = df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if hasattr(df["Date"], "dt"):
            try:
                df["Date"] = df["Date"].dt.tz_localize(None)
            except Exception:
                pass

    if not all(col in df.columns for col in ["Open", "High", "Low", "Close", "Volume"]):
        return df

    bar_len = int(interval.rstrip("minute").rstrip("m")) if interval.endswith("minute") else 1
    win_30m = max(2, 30 // max(bar_len, 1))
    win_2h = max(2, 120 // max(bar_len, 1))
    win_14m = max(2, 14 // max(bar_len, 1))
    win_20 = 20
    eps = 1e-9

    close = pd.to_numeric(df["Close"], errors="coerce")
    open_ = pd.to_numeric(df["Open"], errors="coerce")
    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    vol = pd.to_numeric(df["Volume"], errors="coerce")

    df["LagRet_1"] = np.log((close / close.shift(1)).clip(lower=eps)).fillna(0)
    df["LagRet_5"] = np.log((close / close.shift(5)).clip(lower=eps)).fillna(0)
    df["LagRet_20"] = np.log((close / close.shift(win_20)).clip(lower=eps)).fillna(0)
    df["LagRet_30"] = np.log((close / close.shift(win_30m)).clip(lower=eps)).fillna(0)

    df["OHLC_pct"] = (close - open_) / (open_ + eps)
    df["High_Low_pct"] = (high - low) / (close + eps)
    df["Rel_Close_HL"] = (close - low) / (high - low + eps)

    sma30 = close.rolling(win_30m).mean()
    sma2h = close.rolling(win_2h).mean()
    df["Trend_30"] = (close - sma30) / (sma30 + eps)
    df["Trend_2h"] = (close - sma2h) / (sma2h + eps)
    df["Trend_slope"] = ((close - close.shift(3)) / (3 * max(bar_len, 1))).fillna(0)

    df["RSI14"] = momentum.RSIIndicator(close, window=win_14m).rsi()
    macd_val = trend.MACD(close).macd()
    macd_mu = macd_val.rolling(win_30m).mean()
    macd_sigma = macd_val.rolling(win_30m).std()
    df["MACD_z"] = ((macd_val - macd_mu) / (macd_sigma + eps)).clip(-10, 10)
    df["RSI"] = df["RSI14"]

    atr20 = volatility.AverageTrueRange(high, low, close, window=win_20).average_true_range()
    df["Volatility"] = atr20
    df["ATR20_log"] = np.log((atr20 / close).clip(lower=eps))
    realized20 = df["LagRet_1"].rolling(win_20).std()
    df["RealVol20_log"] = np.log(realized20.clip(lower=eps))

    df["Vol_log"] = np.log1p(vol.clip(lower=0))
    vol_pct = vol.rolling(win_20).rank(pct=True)
    df["VolRegime"] = vol_pct.fillna(0.5)
    df["Vol_z30"] = ((vol - vol.rolling(win_30m).mean()) / (vol.rolling(win_30m).std() + eps)).fillna(0)

    if "Date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Date"]):
        mins = df["Date"].dt.hour * 60 + df["Date"].dt.minute
    else:
        mins = pd.Series(np.zeros(len(df)), index=df.index, dtype=float)
    df["MinuteNorm"] = mins / 390.0
    df["MinutesOpen"] = mins
    df["LunchDummy"] = ((mins > 150) & (mins < 210)).astype(int)

    df["RegimeBull"] = (df["Trend_2h"] > 0).astype(float)
    df["RegimeBear"] = (df["Trend_2h"] < 0).astype(float)
    df["ADX_strong"] = (trend.ADXIndicator(high, low, close, window=win_30m).adx() >= 25).astype(float)
    df["ADX_weak"] = 1.0 - df["ADX_strong"]

    numeric_cols = [c for c in df.columns if c != "Date"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df.fillna(method="ffill", inplace=True)
    df.fillna(0, inplace=True)
    return df

# ----------------------------------------------------------------------
#  get_data_kite – robust version
# ----------------------------------------------------------------------
def get_data_kite(
    kite,
    instrument_token: int,
    days: int       = 5,
    interval: str   = "1minute",
    tz_name: str    = "Asia/Kolkata"
) -> pd.DataFrame:
    """
    Download intraday OHLCV via Kite and build a compact, **always-complete**
    technical-feature dataframe ready for RL.
    """
    # Determine ticker string from instrument token.
    tickerval = get_ticker_from_token(instrument_token, instrument_df)
    csv_path = RESULTS_DIR / f"data_fetched_{tickerval}.csv"
    
    # Check if cached data exists.
    if csv_path.exists():
        print(f"Loading cached data from: {csv_path}")
        df = pd.read_csv(csv_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
        df = build_rl_features(df, interval=interval)
        return df
    
    # ---------- 1) pull raw bars ------------------------------------------------
    max_days_per_call = 30 if "minute" in interval else 100
    tz  = pytz.timezone(tz_name)
    end = datetime.now(tz)
    beg = end - timedelta(days=days)

    rows, cur = [], beg
    while cur < end:
        nxt = min(cur + timedelta(days=max_days_per_call), end)
        rows.extend(
            kite.historical_data(
                instrument_token,
                cur.strftime("%Y-%m-%d %H:%M:%S"),
                nxt.strftime("%Y-%m-%d %H:%M:%S"),
                interval
            )
        )
        cur = nxt + timedelta(seconds=1)      # avoid overlap
        time.sleep(0.35)                      # API rate-limit

    if not rows:
        return pd.DataFrame()                 # nothing fetched

    df = (pd.DataFrame(rows)
            .rename(columns={"date":"Date","open":"Open","high":"High",
                             "low":"Low","close":"Close","volume":"Volume"})
            .assign(Date=lambda x: pd.to_datetime(x["Date"]).dt.tz_localize(None))
            .drop_duplicates("Date")
            .sort_values("Date")
            .reset_index(drop=True))

    # ---------- 2) engineered features -----------------------------------------
    df = build_rl_features(df, interval=interval)

    # Save the fetched and processed data to CSV for future caching.
    try:
        df.to_csv(csv_path, index=False)
        print(f"Data successfully saved to: {csv_path}")
    except Exception as e:
        print(f"[get_data_kite] Failed to write CSV: {e}")

    return df

class SingleStockTradingEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(
        self,
        df: pd.DataFrame,
        ticker: str,
        initial_balance: float = 10000,
        stop_loss: float = 0.90,
        take_profit: float = 1.10,
        max_position_size: float = 0.5,
        max_drawdown: float = 0.20,
        annual_trading_days: int = 252,        
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
        inference_sell_threshold: float = 0.5,  # New: threshold for sell signals (tuned between 0.5 and 1.0)
        slippage_rate: float = 0.001,
        disable_costs: bool = False
    ):
        super(SingleStockTradingEnv, self).__init__()
        self.env_rank = env_rank
        self.ticker = ticker
        self.df = df.copy()
        if "Date" in self.df.columns:
            self.df = self.df.sort_values("Date").reset_index(drop=True)
        else:
            self.df = self.df.reset_index(drop=True)

        self.initial_balance = initial_balance
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_position_size = max_position_size
        self.max_drawdown = max_drawdown
        self.annual_trading_days = annual_trading_days
        self.transaction_cost = 0
        self.some_factor = some_factor
        self.hold_threshold = hold_threshold
        self.trailing_drawdown_trigger = trailing_drawdown_trigger
        self.trailing_drawdown_grace = trailing_drawdown_grace
        self.forced_liquidation_penalty = forced_liquidation_penalty
        # Initialize cumulative slippage cost for this step
        self.cumulative_slippage_cost = 0.0
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
        self.slippage_rate = float(max(0.0, slippage_rate))
        self.disable_costs = bool(disable_costs)
        self.profit_reference = initial_balance
        self.realized_gain = 0.0  # to store cashed-out gains
        self.dp_charge_applied = False
        self.last_dp_charge_amount = 0.0
        self.current_step = 0
        # --- in __init__ ---------------------------------------------
        self.warmup_steps = 200      # try 100–300; tune later

        if self.mode == "test":
            main_logger.info(f"[Env {self.env_rank}] In test mode: Inference Buy Threshold set to {self.inference_buy_threshold}, "
                         f"Inference Sell Threshold set to {self.inference_sell_threshold}")
        
        import collections
        self.reward_history = collections.deque(maxlen=500)

        self.action_space = spaces.Discrete(4)
        self.num_features = len(FEATURES_TO_SCALE)
        self.market_phase = ['Bull', 'Bear', 'Sideways']

        # Observation: technical features + (balance ratio, net worth ratio, position ratio) + market phase flags + drawdown stats.
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf,
                                    shape=(24,), dtype=np.float32)

        if reward_weights is not None:
            self.reward_weights = reward_weights
        else:
            self.reward_weights = {'reward_scale': 1.0}
        
        self.cumulative_reward = 0.0  # Running total updated each step.
        self._force_termination = False  # Flag set by early stopping.
        self.final_metrics = None  # Final metrics available after episode ends.

        # Initialize episode-specific state variables in __init__
        self.balance = initial_balance
        self.position = 0
        self.net_worth = initial_balance
        self.current_step = 0
        self.history = []
        self.prev_net_worth = self.net_worth
        self.last_action = 0.0
        self.peak = self.net_worth
        self.returns_window = []
        self.transaction_count = 0
        self.consecutive_drawdown_steps = 0
        self.last_dp_charge_flag = 0
        
        #self.reset()

    def seed(self, seed=None):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        training_logger.debug(f"[Env {self.env_rank}] Seed set to {seed}")

    # ---------------------------------------------------------------------
    # SingleStockTradingEnv._next_observation   (drop-in replacement)
    # ---------------------------------------------------------------------
    def _next_observation(self) -> np.ndarray:
        """
        Assemble one-step observation vector:

        • 20 technical features  (FEATURES_TO_SCALE)
        • 4 agent-state metrics  (balance/net-worth/position/drawdown)
        -----------------------------------------------------------
        total length = 24   → observation_space.shape == (24,)
        """

        # Clamp index so we never run past the end
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1

        # ---- 1) grab current bar from dataframe -------------------------
        row = self.df.iloc[self.current_step]
        obs_dict: dict[str, float] = {}

        eps = 1e-12           # for safe division / log

        # ---- 2) copy / sanitise feature columns -------------------------
        for feat in FEATURES_TO_SCALE:
            # If the column is missing, fall back to 0.0
            val = row.get(feat, 0.0)
            # Cast & sanitise (strip NaNs / infs)
            obs_dict[feat] = float(
                0.0 if (pd.isna(val) or np.isinf(val)) else val
            )

        # ---- 3) agent-state metrics -------------------------------------
        obs_dict["Balance_Ratio"]  = self.balance   / self.initial_balance
        obs_dict["NetWorth_Ratio"] = self.net_worth / self.initial_balance

        # position scaled by how many shares ≈ initial_balance could buy
        shares_scale = max(1.0, self.initial_balance / (row["Close"] + eps))
        obs_dict["Position_Ratio"] = self.position / shares_scale

        peak = max(self.peak, self.net_worth)
        obs_dict["Drawdown_Frac"] = (peak - self.net_worth) / peak if peak > 0 else 0.0

        # ---- 4) stack into np.array -------------------------------------
        tech_values   = [obs_dict[f] for f in FEATURES_TO_SCALE]           # 20
        agent_values  = [
            obs_dict["Balance_Ratio"],
            obs_dict["NetWorth_Ratio"],
            obs_dict["Position_Ratio"],
            obs_dict["Drawdown_Frac"],
        ]                                                                  # 4
        obs_array = np.asarray(tech_values + agent_values, dtype=np.float32)

        # Housekeeping
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
        self.peak = self.net_worth
        self.returns_window = []
        self.transaction_count = 0
        self.consecutive_drawdown_steps = 0
        self.reward_history.clear()
        self.cumulative_reward = 0.0  # Running total updated each step.
        self._force_termination = False  # Flag set by early stopping.
        self.dp_charge_applied = False
        self.last_dp_charge_flag = 0
        self.transaction_cost = 0.0
        self.final_metrics = None  # Final metrics available after episode ends.
        self.cumulative_slippage_cost = 0.0
        self.warmup_steps = 200
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

    def calculate_transaction_cost(self, order_value: float, side: str, quantity: int) -> tuple:
        """
        Calculate the transaction cost for a given order_value and side ('buy' or 'sell')
        using the revised fee components:
        
        - Brokerage Fee: min(₹20, 0.03% of order_value)  
        (Applicable on both Buy & Sell orders)
        
        - STT (Securities Transaction Tax): 0.025% of order_value  
        (Applicable on Sell orders only)
        
        - Transaction Charges: 0.00297% of order_value  
        (Applicable on both Buy & Sell orders)
        
        - SEBI Charges: 0.0001% of order_value (i.e., ₹10 per crore)  
        (Applicable on both Buy & Sell orders)
        
        - Stamp Duty: 0.003% of order_value (or ₹300 per crore)  
        (Applicable on Buy orders only)
        
        - GST: 18% on the sum of (Brokerage Fee + Transaction Charges + SEBI Charges)  
        (Applicable on both Buy & Sell orders)
        
        - DP Charges: Not applicable
        """
        if self.disable_costs:
            breakdown = {
                'Brokerage_Fee': 0.0,
                'STT': 0.0,
                'Transaction_Charge': 0.0,
                'SEBI_Fee': 0.0,
                'GST': 0.0,
                'Stamp_Duty': 0.0,
                'shares_bought': quantity if side.lower() == 'buy' else 0,
                'shares_sold': quantity if side.lower() == 'sell' else 0
            }
            return 0.0, breakdown

        brokerage_fee = min(20, 0.0003 * order_value)
        stt = 0.00025 * order_value if side.lower() == 'sell' else 0.0
        transaction_charge = 0.0000297 * order_value
        sebi_fee = 1e-6 * order_value  # 0.0001% of order_value
        gst = 0.18 * (brokerage_fee + transaction_charge + sebi_fee)
        stamp_duty = 0.00003 * order_value if side.lower() == 'buy' else 0.0

        total_cost = brokerage_fee + stt + transaction_charge + sebi_fee + gst + stamp_duty

        if side.lower() == 'buy':
            shares_bought = quantity
            shares_sold = 0
        else:
            shares_bought = 0
            shares_sold = quantity

        breakdown = {
            'Brokerage_Fee': brokerage_fee,
            'STT': stt,
            'Transaction_Charge': transaction_charge,
            'SEBI_Fee': sebi_fee,
            'GST': gst,
            'Stamp_Duty': stamp_duty,
            'shares_bought': shares_bought,
            'shares_sold': shares_sold
        }

        return total_cost, breakdown

    def step(self, action):
        # Declare slippage constant and corresponding multipliers.
        SLIPPAGE_RATE = self.slippage_rate
        BUY_MULTIPLIER = 1 + SLIPPAGE_RATE   # Replaces 1.01 (i.e., 1.001 now)
        SELL_MULTIPLIER = 1 - SLIPPAGE_RATE  # Replaces 0.99 (i.e., 0.999 now)
        eps = 1e-9

        # Initialize a list to accumulate breakdown dictionaries for each transaction.
        breakdowns_list = []
        self.cumulative_slippage_cost = 0.0

        # If a forced termination is requested (by early stopping), end the episode immediately.
        if self._force_termination:
            obs = self._next_observation()
            self.final_metrics = self.get_current_metrics()
            self._force_termination = False  # Reset the flag.
            return obs, 0.0, True, True, {}
        
        terminated = False
        training_logger.debug(f"[Env {self.env_rank}] step() called at current_step={self.current_step} with action={action}")
        print(f"[Env {self.env_rank}] step() called at current_step={self.current_step} with action={action}")

        training_logger.debug(
            f"[Env {self.env_rank} step()] action={action} "
            f"type={type(action)} "
            f"shape={(action.shape if hasattr(action, 'shape') else None)}"
        )        

        # 2) Capture the "current" observation (the state on which the agent acts)
        current_obs_array = self._next_observation()
        
        try:
            action_id = int(np.asarray(action).item()) if isinstance(action, (np.ndarray, list, tuple)) else int(action)
            assert self.action_space.contains(action_id), f"[Env {self.env_rank}] Invalid action: {action_id}"
        except Exception as e:
            training_logger.error(f"[Env {self.env_rank}] Action validation failed: {e}")
            return self._next_observation(), -1000.0, True, False, {}

        action_labels = {0: "hold", 1: "long", 2: "short", 3: "reduce"}
        action_name = action_labels.get(action_id, "hold")
        # Compatibility field for existing logs.
        action_value = 0.0 if action_id in (0, 3) else (1.0 if action_id == 1 else -1.0)

        invalid_action_penalty = -0.001

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
                'Buy_Signal_Price': np.nan,
                'Sell_Signal_Price': np.nan,
                'Net Worth': self.net_worth,
                'Balance': self.balance,
                'Position': self.position,
                'Reward': reward,
                'Trade_Cost': 0.0,
                'Transaction_Breakdowns': []
            })
            training_logger.error(f"[Env {self.env_rank}] Terminating episode at step {self.current_step} due to data overflow.")
            return obs, reward, terminated, truncated, {}

        current_data = self.df.iloc[self.current_step]
        current_price = float(current_data['Close'])
        current_date = current_data['Date']

        shares_traded = 0
        total_trade_cost = 0.0  # New accumulator for transaction costs
        transaction_cost = 0.0
        invalid_act_penalty = 0.0        

        # Revised net worth calculation at the beginning of step()
        net_worth = float(self.balance + self.position * current_price + self.realized_gain)
        net_worth_change = net_worth - self.prev_net_worth

        # 1) Initialize local flags:
        stop_loss_triggered = False
        take_profit_triggered = False
        drawdown_triggered = False
        
        # --- Step-wise Forced Stop Loss Logic ---
        forced_stop_penalty_weight = self.reward_weights.get('forced_stop_penalty_weight', 0.001)
        
        forced_stop_penalty = 0.0
        stop_loss_triggered = False
        current_loss = (self.initial_balance - net_worth) / self.initial_balance if net_worth < self.initial_balance else 0.0

        stop_loss_tiers = [ 
            {"threshold": 0.0125, "fraction_to_sell": 0.1, "penalty_factor": 1},     # Small sell-off at 1.25%
            {"threshold": 0.025, "fraction_to_sell": 0.3, "penalty_factor": 1.5},    # 150% liquidation at 2.5%
            {"threshold": 0.0375, "fraction_to_sell": 0.6, "penalty_factor": 2},     # 300% liquidation at 3.75%
            {"threshold": 0.05, "fraction_to_sell": 1.0, "penalty_factor": 2.5},     # 500% liquidation at 5%
        ]

        # Sort tiers in descending order so the highest applicable tier is applied first.
        sorted_sl_tiers = sorted(stop_loss_tiers, key=lambda x: x["threshold"], reverse=True)
        fraction_of_shares = 0.0

        for tier in sorted_sl_tiers:
            if current_loss > tier["threshold"] and self.position > 0:
                stop_loss_triggered = True
                tier_penalty = -forced_stop_penalty_weight * current_loss * tier["penalty_factor"]  
                forced_stop_penalty += tier_penalty

                # Execute sell with slippage (sell orders at price * SELL_MULTIPLIER)
                fraction_of_shares = math.floor(self.position * tier["fraction_to_sell"])
                if fraction_of_shares == 0 and tier["fraction_to_sell"] < 1.0 and self.position > 0:
                    fraction_of_shares = 1
                if fraction_of_shares > 0:
                    order_value = fraction_of_shares * current_price * SELL_MULTIPLIER
                    cost, breakdown = self.calculate_transaction_cost(order_value, "sell", fraction_of_shares)
                    transaction_cost = cost
                    total_trade_cost += transaction_cost
                    proceeds = order_value - transaction_cost
                    self.balance += proceeds
                    self.position -= fraction_of_shares
                    self.transaction_count += 1
                    # After executing stop-loss sell orders, update net worth to include realized gain
                    self.net_worth = float(self.balance + self.position * current_price + self.realized_gain)
                    self.peak = max(self.peak, net_worth)
                    breakdowns_list.append(breakdown)
                    # For stop loss sells, assume execution at price * SELL_MULTIPLIER
                    executed_price = current_price * SELL_MULTIPLIER
                    # Add slippage cost: shares * (current_price - executed_price)
                    slippage_cost = fraction_of_shares * (current_price - executed_price)
                    self.cumulative_slippage_cost += slippage_cost
                if tier.get("fraction_to_sell", 0.0) == 1.0:
                    terminated = True                
                break

        net_worth = float(self.balance + self.position * current_price + self.realized_gain)

        # --- Forced Take Profit Logic ---
        forced_tp_penalty_weight = self.reward_weights.get('forced_tp_penalty_weight', 0.001)
        forced_tp_penalty = 0.0
        current_profit = (net_worth - self.profit_reference) / self.profit_reference if net_worth > self.profit_reference else 0.0

        # Define new take profit tiers: only trigger if current profit exceeds 10% of initial balance,
        # then additional tiers in increments of 5% (i.e. 10%, 15%, and 20% gains)
        take_profit_tiers = [ 
            {"threshold": 0.05, "fraction_to_sell": 0.25, "penalty_factor": 1},  # 5% gain: sell 25%
            {"threshold": 0.075, "fraction_to_sell": 0.50, "penalty_factor": 2},  # 7.5% gain: sell 50%
            {"threshold": 0.10, "fraction_to_sell": 1.0,  "penalty_factor": 3},  # 10% gain: full liquidation
        ]

        sorted_tp_tiers = sorted(take_profit_tiers, key=lambda x: x["threshold"], reverse=True)
        fraction_of_shares = 0.0

        for tier in sorted_tp_tiers:
            # 'current_profit' is assumed to be defined as a fraction (e.g., (net_worth/initial_balance - 1))
            if current_profit > tier["threshold"] and self.position > 0:
                take_profit_triggered = True
                tier_penalty = -forced_tp_penalty_weight * current_profit * tier["penalty_factor"]
                forced_tp_penalty += tier_penalty

                fraction_of_shares = math.floor(self.position * tier["fraction_to_sell"])
                if fraction_of_shares == 0 and tier["fraction_to_sell"] < 1.0 and self.position > 0:
                    fraction_of_shares = 1

                if fraction_of_shares > 0:
                    order_value = fraction_of_shares * current_price * SELL_MULTIPLIER  # Apply SELL_MULTIPLIER
                    cost, breakdown = self.calculate_transaction_cost(order_value, "sell", fraction_of_shares)
                    transaction_cost = cost
                    total_trade_cost += transaction_cost
                    proceeds = order_value - transaction_cost
                    self.balance += proceeds
                    self.position -= fraction_of_shares
                    self.transaction_count += 1
                    # After processing forced take profit cash-out, update net worth calculation accordingly
                    self.net_worth = float(self.balance + self.position * current_price + self.realized_gain)
                    self.peak = max(self.peak, self.net_worth)
                    breakdowns_list.append(breakdown)
                    executed_price = current_price * SELL_MULTIPLIER
                    # Add slippage cost: shares * (current_price - executed_price)
                    slippage_cost = fraction_of_shares * (current_price - executed_price)
                    self.cumulative_slippage_cost += slippage_cost
                    main_logger.critical(
                        f"[TakeProfit] Sold {fraction_of_shares} shares at {current_price:.2f}, proceeds={proceeds:.2f}, "
                        f"new_balance={self.balance:.2f}, new_position={self.position}, new_net_worth={self.net_worth:.2f}"
                    )

                # Revised cash-out condition: only cash out if net_worth exceeds the profit reference by 10%
                if self.net_worth > self.profit_reference * 1.05:
                    excess = self.net_worth - self.profit_reference * 1.05

                    # only money *above* the original float can be skimmed
                    available_cash = max(0.0, self.balance - self.initial_balance)
                    cash_out       = min(excess, available_cash)
                    if cash_out > 0:
                        self.balance       -= cash_out          # keeps float ≥ initial_balance
                        self.realized_gain += cash_out

                    # raise the floor so the trigger doesn’t fire again immediately
                    self.profit_reference += cash_out
                    new_profit_reference = self.profit_reference

                    main_logger.critical(
                        f"[Trial {getattr(self, 'trial_id', 'N/A')}][Env {self.env_rank}][Ticker={self.ticker}][Step={self.current_step}] "
                        f"TAKE-PROFIT cash-out triggered. old_profit_ref={self.profit_reference:.2f}, net_worth={self.net_worth:.2f}, "
                        f"excess={excess:.2f}, new_profit_ref={new_profit_reference:.2f}, cash_out={cash_out:.2f}"
                    )
                    self.net_worth = float(self.balance + self.position * current_price + self.realized_gain)
                    #self.profit_reference = new_profit_reference
                    main_logger.critical(
                        f"[Trial {getattr(self, 'trial_id', 'N/A')}][Env {self.env_rank}][Ticker={self.ticker}][Step={self.current_step}] "
                        f"After TAKE-PROFIT cash-out: realized_gain={self.realized_gain:.2f}, balance={self.balance:.2f}, "
                        f"net_worth={self.net_worth:.2f}, profit_reference={self.profit_reference:.2f}"
                    )
                break

        # --- Drawdown Penalty Logic ---
        self.peak = max(self.peak, net_worth)
        net_worth = float(self.balance + self.position * current_price + self.realized_gain)

        current_drawdown = (self.peak - net_worth) / self.peak if self.peak > 0 else 0.0
        drawdown_penalty = 0.0

        drawdown_tiers = [
            {"threshold": 0.05, "penalty_factor": 1.0, "liquidate": False},
            {"threshold": 0.075, "penalty_factor": 1.5, "liquidate": True, "fraction_to_sell": 0.5},
            {"threshold": 0.10, "penalty_factor": 2.0, "liquidate": True, "fraction_to_sell": 1.0},
        ]
        sorted_dd_tiers = sorted(drawdown_tiers, key=lambda x: x["threshold"], reverse=True)
        fraction_of_shares = 0.0

        if not stop_loss_triggered:            
            
            base_penalty = -self.some_factor * current_drawdown
            
            for tier in sorted_dd_tiers:
                if current_drawdown > tier["threshold"] and self.position > 0:
                    drawdown_penalty += base_penalty * tier["penalty_factor"]
                    drawdown_triggered = True
                    if tier.get("liquidate", False) and self.position > 0:
                        frac = tier.get("fraction_to_sell", 0.0)
                        if frac > 0:
                            shares_to_sell = math.floor(self.position * frac) if frac < 1.0 else self.position
                            if shares_to_sell > 0:
                                order_value = shares_to_sell * current_price * SELL_MULTIPLIER
                                cost, breakdown = self.calculate_transaction_cost(order_value, "sell", shares_to_sell)
                                transaction_cost = cost
                                total_trade_cost += transaction_cost
                                proceeds = order_value - transaction_cost
                                self.balance += proceeds
                                self.position -= shares_to_sell
                                self.transaction_count += 1
                                # After processing forced take profit cash-out, update net worth calculation accordingly
                                self.net_worth = float(self.balance + self.position * current_price + self.realized_gain)
                                self.peak = max(self.peak, net_worth)
                                breakdowns_list.append(breakdown)
                                executed_price = current_price * SELL_MULTIPLIER
                                # Add slippage cost: shares * (current_price - executed_price)
                                slippage_cost = shares_to_sell * (current_price - executed_price)
                                self.cumulative_slippage_cost += slippage_cost
                    if tier.get("fraction_to_sell", 0.0) == 1.0:
                        terminated = True
                    break

        # Update net worth after executing drawdown penalty related trades
        net_worth = float(self.balance + self.position * current_price + self.realized_gain)
        self.net_worth = net_worth

        if any([stop_loss_triggered, take_profit_triggered, drawdown_triggered]) and terminated:
            action_value = 0

        buy_signal_price = np.nan
        sell_signal_price = np.nan

        eps = 1e-9
        live_equity = max(self.balance + self.position * current_price, eps)
        trade_fraction = float(self.reward_weights.get("trade_fraction", 0.25))
        reduce_fraction = float(self.reward_weights.get("reduce_fraction", 0.5))
        shares_to_buy = 0
        shares_to_sell = 0

        if action_id == 1:
            target_notional = trade_fraction * self.max_position_size * live_equity
            shares_to_buy = max(1, math.floor(target_notional / (current_price * BUY_MULTIPLIER)))
            order_value = shares_to_buy * current_price * BUY_MULTIPLIER
            cost, breakdown = self.calculate_transaction_cost(order_value, "buy", shares_to_buy)
            transaction_cost = cost
            total_trade_cost += transaction_cost
            total_cost = order_value + transaction_cost
            if total_cost <= self.balance:
                buy_signal_price = current_price
                self.balance -= total_cost
                self.position += shares_to_buy
                self.transaction_count += 1
                shares_traded = shares_to_buy
                breakdowns_list.append(breakdown)
                self.cumulative_slippage_cost += shares_to_buy * (current_price * BUY_MULTIPLIER - current_price)
            else:
                invalid_act_penalty = invalid_action_penalty
        elif action_id == 2:
            target_notional = trade_fraction * self.max_position_size * live_equity
            shares_to_sell = max(1, math.floor(target_notional / (current_price * SELL_MULTIPLIER)))
            order_value = shares_to_sell * current_price * SELL_MULTIPLIER
            cost, breakdown = self.calculate_transaction_cost(order_value, "sell", shares_to_sell)
            transaction_cost = cost
            total_trade_cost += transaction_cost
            proceeds = order_value - transaction_cost
            self.position -= shares_to_sell
            self.balance += proceeds
            self.transaction_count += 1
            shares_traded = shares_to_sell
            sell_signal_price = current_price
            breakdowns_list.append(breakdown)
            self.cumulative_slippage_cost += shares_to_sell * (current_price - current_price * SELL_MULTIPLIER)
        elif action_id == 3:
            if self.position > 0:
                shares_to_sell = max(1, math.floor(abs(self.position) * reduce_fraction))
                shares_to_sell = min(shares_to_sell, int(abs(self.position)))
                order_value = shares_to_sell * current_price * SELL_MULTIPLIER
                cost, breakdown = self.calculate_transaction_cost(order_value, "sell", shares_to_sell)
                transaction_cost = cost
                total_trade_cost += transaction_cost
                proceeds = order_value - transaction_cost
                self.balance += proceeds
                self.position -= shares_to_sell
                self.transaction_count += 1
                shares_traded = shares_to_sell
                sell_signal_price = current_price
                breakdowns_list.append(breakdown)
                self.cumulative_slippage_cost += shares_to_sell * (current_price - current_price * SELL_MULTIPLIER)
            elif self.position < 0:
                shares_to_buy = max(1, math.floor(abs(self.position) * reduce_fraction))
                shares_to_buy = min(shares_to_buy, int(abs(self.position)))
                order_value = shares_to_buy * current_price * BUY_MULTIPLIER
                cost, breakdown = self.calculate_transaction_cost(order_value, "buy", shares_to_buy)
                total_cost = order_value + cost
                if total_cost <= self.balance:
                    transaction_cost = cost
                    total_trade_cost += transaction_cost
                    self.balance -= total_cost
                    self.position += shares_to_buy
                    self.transaction_count += 1
                    shares_traded = shares_to_buy
                    buy_signal_price = current_price
                    breakdowns_list.append(breakdown)
                    self.cumulative_slippage_cost += shares_to_buy * (current_price * BUY_MULTIPLIER - current_price)
                else:
                    invalid_act_penalty = invalid_action_penalty
        if self.cumulative_slippage_cost > 1000:
            print(f"[Env {self.env_rank}]: Ticker{self.ticker}: High slippage at step {self.current_step}: {self.cumulative_slippage_cost:.2f}, shares={shares_to_buy}, price={current_price}")
            training_logger.debug(f"[Env {self.env_rank}]: Ticker{self.ticker}: High slippage at step {self.current_step}: {self.cumulative_slippage_cost:.2f}, shares={shares_to_buy}, price={current_price}")

        net_worth = float(self.balance + self.position * current_price + self.realized_gain)
        self.net_worth = net_worth

        # ─── Automatic margin call / forced short-cover ─────────────────────
        if self.position < 0:                                      # we are short
            mark_to_market_cost = abs(self.position) * current_price * BUY_MULTIPLIER

            if mark_to_market_cost > self.balance:
                # how many shares can we afford to buy back right now?
                affordable_shares = math.floor(self.balance / (current_price * BUY_MULTIPLIER))

                # if even 1 share is unaffordable, liquidate the episode
                if affordable_shares == 0:
                    terminated = True
                    # optional: add big penalty so the agent hates this outcome
                    invalid_act_penalty -= 1.0
                else:
                    # cover affordable_shares
                    cover_order_value = affordable_shares * current_price * BUY_MULTIPLIER
                    cost, breakdown = self.calculate_transaction_cost(cover_order_value,
                                                                    "buy",
                                                                    affordable_shares)
                    total_trade_cost += cost

                    self.balance  -= cover_order_value + cost
                    self.position += affordable_shares                 # less negative
                    breakdowns_list.append(breakdown)

                    executed_price = current_price * BUY_MULTIPLIER
                    self.cumulative_slippage_cost += affordable_shares * (
                            executed_price - current_price)

        net_worth = float(self.balance + self.position * current_price + self.realized_gain)
        self.net_worth = net_worth

        net_worth_change = net_worth - self.prev_net_worth
        safe_prev = max(self.prev_net_worth, eps)
        step_return = net_worth_change / safe_prev

        self.returns_window.append(step_return)
        if len(self.returns_window) > 50:
            self.returns_window.pop(0)
        rolling_volatility = float(np.std(self.returns_window)) if len(self.returns_window) >= 2 else 0.0

        self.transaction_cost = total_trade_cost
        transaction_penalty_weight = float(self.reward_weights.get("transaction_penalty_weight", 1.0))
        transaction_penalty = (total_trade_cost / safe_prev) * transaction_penalty_weight
        volatility_penalty_weight = float(self.reward_weights.get("volatility_penalty_weight", 0.10))

        # Backward-compatible metric keys retained for logs.
        profit_reward = step_return
        sharpe_bonus = 0.0
        holding_bonus = 0.0
        profit_weight = 1.0
        sharpe_bonus_weight = 0.0
        holding_bonus_weight = 0.0

        # After all transactions in step(), update heavy transaction cost info:
        heavy_flag = 0
        heavy_amount = 0.0
        for breakdown in breakdowns_list:
            if breakdown.get('DP_Charge', 0) >= 20:
                heavy_flag = 1
                heavy_amount = breakdown.get('DP_Charge', 0)
                break
        self.last_dp_charge_flag = heavy_flag
        self.last_dp_charge_amount = heavy_amount

        risk_adjusted_reward = step_return - volatility_penalty_weight * rolling_volatility - transaction_penalty
        reward = (
            risk_adjusted_reward
            + forced_stop_penalty
            + forced_tp_penalty
            + drawdown_penalty
            + invalid_act_penalty
        )
        raw_reward = reward
        self.reward_history.append(raw_reward)
        
        normalized_reward = float(raw_reward)
        self.cumulative_reward += float(reward)
        
        self.history.append({
            'Date': current_date,
            'Close': current_price,
            'ticker': self.ticker,
            'env_rank': self.env_rank,
            'Action': action_id,
            'ActionName': action_name,
            'ActionLegacy': action_value,
            'Buy_Signal_Price': buy_signal_price,
            'Sell_Signal_Price': sell_signal_price,
            'Full Worth': self.net_worth,
            'Net Worth': self.net_worth,
            'Balance': self.balance,
            'Realized Gain': self.realized_gain,
            'Position': self.position,
            'Reward': normalized_reward,
            'profit_reward': profit_reward,
            'sharpe_bonus': sharpe_bonus,
            'holding_bonus': holding_bonus,
            'TransactionCost': self.transaction_cost,
            'Slippage': self.cumulative_slippage_cost,
            'Transaction_Breakdowns': breakdowns_list,
            'cumulative_reward': self.cumulative_reward,
            'forced_stop_penalty': forced_stop_penalty,
            'forced_tp_penalty': forced_tp_penalty,
            'drawdown_penalty': drawdown_penalty,
            'transaction_penalty': -transaction_penalty,
            'rolling_volatility': rolling_volatility,
            'risk_adjusted_reward': risk_adjusted_reward,
            'is_terminated': terminated,
            'stop_loss_triggered': stop_loss_triggered,
            'take_profit_triggered': take_profit_triggered,
            'drawdown_triggered': drawdown_triggered,
            'new_profit_reference': self.profit_reference,
            'invalid_act_penalty': invalid_act_penalty,
            'profit_weight': profit_weight,
            'sharpe_bonus_weight': sharpe_bonus_weight,
            'transaction_penalty_weight': transaction_penalty_weight,
            'holding_bonus_weight': holding_bonus_weight,            
            'inference_buy_threshold': self.inference_buy_threshold,
            'inference_sell_threshold': self.inference_sell_threshold,
            'forced_stop_penalty_weight': forced_stop_penalty_weight,
            'forced_tp_penalty_weight': forced_tp_penalty_weight,            
            **{f"Obs_{k}": float(v) for k, v in self.current_obs_dict.items()}
        })

        row_data = self.df.iloc[self.current_step].copy()
        redundant_cols = ['Date', 'Close', 'Adj Close', 'Open', 'High', 'Low', 'Volume']
        row_data.drop(labels=redundant_cols, errors='ignore', inplace=True)

        # ------------------------------------------------------------------
        # ❶  TECHNICAL COLUMNS THAT ACTUALLY EXIST IN get_data_kite()
        # ------------------------------------------------------------------
        TECH_FEATURES = FEATURES_TO_SCALE

        # ------------------------------------------------------------------
        # ❷  SAVE THEM INTO self.history  – robust to any future tweaks
        # ------------------------------------------------------------------
        for col in TECH_FEATURES:
            # Series.get() ⇒ np.nan if the column is missing
            self.history[-1][col] = row_data.get(col, np.nan)


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

        truncated = False        

        if terminated:
            self.last_episode_metrics = {
                "cumulative_reward": sum(entry.get('Reward', 0.0) for entry in self.history),
                "net_worth": self.net_worth,
                "balance": self.balance,
                "position": self.position,
                "transaction_count": self.transaction_count,
                "peak": self.peak,
                "history": self.history.copy()
            }

        if not terminated:
            self.prev_net_worth = net_worth
            self.current_step += 1
        
        training_logger.debug(f"[Env {self.env_rank}] Updated current_step: {self.current_step} / {len(self.df)}")
        self.current_step = min(self.current_step, len(self.df) - 1)        

        obs = self._next_observation()
        
        if not np.isfinite(normalized_reward):
            normalized_reward = 0.0

        return obs, normalized_reward, terminated, truncated, {}

    


# --- at the top of callbacks.py ------------------------------------
from collections import deque
# -------------------------------------------------------------------

class EarlyStoppingCallback(BaseCallback):
    def __init__(self, monitor: str, patience: int,
                 min_delta: float = 0.0, verbose: int = 0,
                 trial_id: int = None,       # ← existing arg list
                 window: int = 2000):        # ← one new arg
        super().__init__(verbose)
        self.monitor      = monitor
        self.patience     = patience
        self.min_delta    = min_delta
        self.trial_id     = trial_id
        self.best_value   = -np.inf
        self.no_improve   = 0

        # NEW ↓ – keep a sliding window of recent *step* rewards
        self.window       = window
        self.ret_window   = deque(maxlen=window)
        self.eps          = 1e-8

    # ----------------------------------------------------------------
    def _on_step(self) -> bool:
        # 1) grab **vector of rewards** already in SB3 locals
        step_ret = float(np.mean(self.locals["rewards"]))
        self.ret_window.append(step_ret)

        # 2) compute rolling Sharpe once we have enough data
        if len(self.ret_window) < 2:          # need ≥2 to get σ
            current_metric = -np.inf
        else:
            mu  = np.mean(self.ret_window)
            sig = np.std (self.ret_window) + self.eps
            current_metric = mu / sig         # ↑ Sharpe

        # 3) unchanged improvement / patience logic
        if current_metric - self.best_value > self.min_delta:
            self.best_value = current_metric
            self.no_improve = 0
        else:
            self.no_improve += 1

        if self.verbose and self.num_timesteps % 500 == 0:
            main_logger.critical(
                f"[EarlyStoppingCallback][Trial {self.trial_id}] "
                f"roll‑Sharpe={current_metric:.3f}  "
                f"Best={self.best_value:.3f}  "
                f"No Imp={self.no_improve}"
            )

        if self.no_improve >= self.patience:
            if self.verbose:
                main_logger.critical(
                    f"[EarlyStoppingCallback][Trial {self.trial_id}] "
                    f"Patience exceeded – stopping."
                )
            self.training_env.env_method("set_force_termination", True)
            return False
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

def split_chronological(df: pd.DataFrame, train_ratio: float = 0.70, val_ratio: float = 0.15):
    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)
    total = len(df)
    if total < 20:
        return df.copy(), pd.DataFrame(), pd.DataFrame()
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()
    return train_df, val_df, test_df

def interval_to_bars_per_day(interval: str) -> int:
    iv = str(interval).lower().strip()
    if "minute" in iv:
        minutes = int(iv.replace("minute", "").strip() or "1")
    elif iv.endswith("m"):
        minutes = int(iv[:-1] or "1")
    else:
        minutes = 5
    # NSE cash session is ~375 minutes (09:15-15:30 IST).
    return max(1, int(round(375 / max(1, minutes))))

def make_walk_forward_slices(
    df: pd.DataFrame,
    interval: str,
    train_days: int = 180,
    val_days: int = 20,
    test_days: int = 10,
    step_days: int = 20
):
    bars_per_day = interval_to_bars_per_day(interval)
    train_bars = train_days * bars_per_day
    val_bars = val_days * bars_per_day
    test_bars = test_days * bars_per_day
    step_bars = step_days * bars_per_day

    windows = []
    start = 0
    total = len(df)
    while True:
        train_end = start + train_bars
        val_end = train_end + val_bars
        test_end = val_end + test_bars
        if test_end > total:
            break
        windows.append((start, train_end, val_end, test_end))
        start += step_bars
    return windows

def _compute_cycle_metrics(history: list, initial_balance: float) -> dict:
    if not history:
        return {
            "net_return": -1.0,
            "max_drawdown": 1.0,
            "sharpe": -10.0,
            "turnover": 1.0,
            "trade_count": 0,
            "score": -999.0
        }
    dfh = pd.DataFrame(history)
    net_worth = pd.to_numeric(dfh.get("Net Worth", pd.Series(dtype=float)), errors="coerce").fillna(method="ffill").fillna(initial_balance)
    positions = pd.to_numeric(dfh.get("Position", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    rewards = pd.to_numeric(dfh.get("Reward", pd.Series(dtype=float)), errors="coerce").fillna(0.0).values
    if len(net_worth) < 2:
        return {
            "net_return": (float(net_worth.iloc[-1]) - initial_balance) / max(initial_balance, 1e-9),
            "max_drawdown": 1.0,
            "sharpe": -10.0,
            "turnover": 1.0,
            "trade_count": int(np.sum(np.abs(np.diff(positions.values)) > 0)),
            "score": -999.0
        }
    net_return = (float(net_worth.iloc[-1]) - initial_balance) / max(initial_balance, 1e-9)
    max_drawdown = abs(float(calculate_max_drawdown(net_worth)))
    sharpe = float(compute_sharpe_ratio(rewards))
    turnover = float(np.sum(np.abs(np.diff(positions.values))) / (np.sum(np.abs(positions.values)) + 1e-9))
    trade_count = int(np.sum(np.abs(np.diff(positions.values)) > 0))
    score = (
        0.5 * net_return
        + 0.3 * sharpe
        - 0.4 * max_drawdown
        - 0.2 * turnover
    )
    if trade_count < 3:
        score -= 0.5
    return {
        "net_return": net_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "turnover": turnover,
        "trade_count": trade_count,
        "score": score
    }

def _evaluate_slice_with_frozen_norm(
    model_path: Path,
    vecnorm_path: Path,
    df_slice: pd.DataFrame,
    ticker: str,
    initial_balance: float,
    env_kwargs: dict,
    eval_tag: str
) -> dict:
    if df_slice.empty:
        return {"history": [], "metrics": _compute_cycle_metrics([], initial_balance)}

    env_eval = SingleStockTradingEnv(
        df=df_slice.reset_index(drop=True),
        ticker=ticker,
        initial_balance=initial_balance,
        max_episode_steps=len(df_slice),
        mode="test",
        **env_kwargs
    )
    eval_vec = SubprocVecEnv([lambda: env_eval])
    eval_vec = VecNormalize.load(str(vecnorm_path), eval_vec)
    eval_vec.training = False
    eval_vec.norm_reward = False

    model = PPO.load(str(model_path), env=eval_vec)
    obs = eval_vec.reset()
    done = [False] * eval_vec.num_envs
    steps = 0
    while not all(done) and steps < len(df_slice):
        action, _ = model.predict(obs, deterministic=True)
        obs, rewards, done, infos = eval_vec.step(action)
        steps += 1

    final_metrics_list = eval_vec.env_method("get_final_metrics")
    eval_vec.close()
    history = final_metrics_list[0].get("history", []) if final_metrics_list else []
    metrics = _compute_cycle_metrics(history, initial_balance)
    main_logger.info(f"[WF:{ticker}:{eval_tag}] score={metrics['score']:.4f}, return={metrics['net_return']:.4f}, dd={metrics['max_drawdown']:.4f}, sharpe={metrics['sharpe']:.4f}, turnover={metrics['turnover']:.4f}, trades={metrics['trade_count']}")
    return {"history": history, "metrics": metrics}

def walk_forward_runner(
    ticker_list: list,
    instrument_df: pd.DataFrame,
    best_params: dict,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
    interval: str = "5minute",
    history_days: int = 365,
    train_days: int = 180,
    val_days: int = 20,
    test_days: int = 10,
    step_days: int = 20,
    train_timesteps: int = 50000
):
    wf_dir = RESULTS_DIR / "walk_forward"
    wf_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []

    common_env_kwargs = {
        "stop_loss": best_params.get('stop_loss', stop_loss),
        "take_profit": best_params.get('take_profit', take_profit),
        "max_position_size": best_params.get('max_position_size', max_position_size),
        "max_drawdown": best_params.get('max_drawdown', max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get('drawdown_penalty_factor', 0.01),
        "hold_threshold": best_params.get('hold_threshold', 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": best_params.get("trade_fraction", 0.25),
            "reduce_fraction": best_params.get("reduce_fraction", 0.50),
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08)
    }

    for ticker in ticker_list:
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[WF:{ticker}] token missing, skipping.")
            continue

        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            main_logger.warning(f"[WF:{ticker}] no data, skipping.")
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days
        )
        if not windows:
            main_logger.warning(f"[WF:{ticker}] not enough rows ({len(df_full)}) for walk-forward windows.")
            continue

        ticker_best_score = -np.inf
        ticker_best_model = None
        ticker_best_norm = None

        for cycle_idx, (s, tr_end, va_end, te_end) in enumerate(windows, start=1):
            train_df = df_full.iloc[s:tr_end].reset_index(drop=True)
            val_df = df_full.iloc[tr_end:va_end].reset_index(drop=True)
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if train_df.empty or val_df.empty or test_df.empty:
                continue

            env_train = SingleStockTradingEnv(
                df=train_df,
                ticker=ticker,
                initial_balance=initial_balance,
                max_episode_steps=len(train_df),
                mode="train",
                env_rank=cycle_idx,
                **common_env_kwargs
            )
            vec_train = SubprocVecEnv([lambda e=env_train: e])
            vec_train = VecNormalize(vec_train, norm_obs=True, norm_reward=True, clip_obs=10000.0, clip_reward=250000.0)

            net_arch = [128, 128]
            policy_kwargs = dict(activation_fn=torch.nn.ReLU, net_arch=net_arch)
            model = PPO(
                "MlpPolicy",
                vec_train,
                verbose=0,
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
                tensorboard_log=str(TB_LOG_DIR / "walk_forward"),
                device='cpu'
            )
            model.learn(total_timesteps=train_timesteps)

            cycle_dir = wf_dir / ticker / f"cycle_{cycle_idx:03d}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            model_path = cycle_dir / "model.zip"
            vecnorm_path = cycle_dir / "vecnorm.pkl"
            model.save(str(model_path))
            vec_train.save(str(vecnorm_path))
            vec_train.close()

            val_eval = _evaluate_slice_with_frozen_norm(
                model_path=model_path,
                vecnorm_path=vecnorm_path,
                df_slice=val_df,
                ticker=ticker,
                initial_balance=initial_balance,
                env_kwargs=common_env_kwargs,
                eval_tag=f"cycle_{cycle_idx:03d}_val"
            )
            test_eval = _evaluate_slice_with_frozen_norm(
                model_path=model_path,
                vecnorm_path=vecnorm_path,
                df_slice=test_df,
                ticker=ticker,
                initial_balance=initial_balance,
                env_kwargs=common_env_kwargs,
                eval_tag=f"cycle_{cycle_idx:03d}_test"
            )

            val_metrics = val_eval["metrics"]
            test_metrics = test_eval["metrics"]
            row = {
                "ticker": ticker,
                "cycle": cycle_idx,
                "train_rows": len(train_df),
                "val_rows": len(val_df),
                "test_rows": len(test_df),
                "val_score": val_metrics["score"],
                "val_return": val_metrics["net_return"],
                "val_drawdown": val_metrics["max_drawdown"],
                "val_sharpe": val_metrics["sharpe"],
                "val_turnover": val_metrics["turnover"],
                "val_trades": val_metrics["trade_count"],
                "test_score": test_metrics["score"],
                "test_return": test_metrics["net_return"],
                "test_drawdown": test_metrics["max_drawdown"],
                "test_sharpe": test_metrics["sharpe"],
                "test_turnover": test_metrics["turnover"],
                "test_trades": test_metrics["trade_count"],
                "model_path": str(model_path),
                "vecnorm_path": str(vecnorm_path)
            }
            all_rows.append(row)

            if val_metrics["score"] > ticker_best_score:
                ticker_best_score = val_metrics["score"]
                ticker_best_model = model_path
                ticker_best_norm = vecnorm_path

        if ticker_best_model is not None and ticker_best_norm is not None:
            approved_dir = wf_dir / ticker / "approved"
            approved_dir.mkdir(parents=True, exist_ok=True)
            approved_model = approved_dir / "model.zip"
            approved_norm = approved_dir / "vecnorm.pkl"
            shutil.copy2(ticker_best_model, approved_model)
            shutil.copy2(ticker_best_norm, approved_norm)
            main_logger.info(f"[WF:{ticker}] approved model updated. score={ticker_best_score:.4f}, model={approved_model}")

    if all_rows:
        wf_df = pd.DataFrame(all_rows)
        wf_csv = wf_dir / "walk_forward_summary.csv"
        wf_df.to_csv(wf_csv, index=False)
        main_logger.info(f"[WF] summary saved: {wf_csv}")
    else:
        main_logger.warning("[WF] no cycles produced results.")

    return all_rows

def shuffle_close_series(df: pd.DataFrame, seed: int = 42, interval: str = "60minute") -> pd.DataFrame:
    df2 = df.copy().sort_values("Date").reset_index(drop=True)
    if df2.empty:
        return df2
    rng = np.random.default_rng(seed)
    close = pd.to_numeric(df2["Close"], errors="coerce").fillna(method="ffill").fillna(method="bfill").values
    rets = pd.Series(close).pct_change().fillna(0.0).values
    shuffled = np.concatenate(([0.0], rng.permutation(rets[1:])))
    new_close = [close[0]]
    for r in shuffled[1:]:
        new_close.append(max(1e-9, new_close[-1] * (1.0 + float(r))))
    df2["Close"] = np.asarray(new_close[:len(df2)], dtype=float)
    # Keep OHLC coherent around new close.
    df2["Open"] = df2["Close"].shift(1).fillna(df2["Close"])
    spread = (0.0015 * df2["Close"]).clip(lower=1e-6)
    df2["High"] = np.maximum(df2["Open"], df2["Close"]) + spread
    df2["Low"] = np.minimum(df2["Open"], df2["Close"]) - spread
    if "Adj Close" in df2.columns:
        df2["Adj Close"] = df2["Close"]
    return build_rl_features(df2, interval=interval)

def compute_history_metrics(history_df: pd.DataFrame, initial_balance: float, bars_per_day: int) -> Dict[str, float]:
    if history_df.empty or "Net Worth" not in history_df.columns:
        return {
            "total_return": -1.0, "annualized_return": -1.0, "max_drawdown": 1.0, "sharpe": -10.0,
            "sortino": -10.0, "turnover": 1.0, "trade_count": 0, "hold_ratio": 1.0, "avg_holding_bars": 0.0
        }
    nw = pd.to_numeric(history_df["Net Worth"], errors="coerce").fillna(method="ffill").fillna(initial_balance)
    rets = nw.pct_change().fillna(0.0).values
    total_return = float(nw.iloc[-1] / max(nw.iloc[0], 1e-9) - 1.0)
    periods_per_year = max(1, 252 * bars_per_day)
    annualized = float(calculate_annualized_return(nw, periods_per_year=periods_per_year))
    max_dd = abs(float(calculate_max_drawdown(nw)))
    sharpe = float(compute_sharpe_ratio(rets))
    sortino = float(compute_sortino_ratio(rets))

    if "Position" in history_df.columns:
        pos = pd.to_numeric(history_df["Position"], errors="coerce").fillna(0.0).values
        turnover = float(np.sum(np.abs(np.diff(pos))) / (np.sum(np.abs(pos)) + 1e-9))
        trade_count = int(np.sum(np.abs(np.diff(pos)) > 0))
        nonzero = (np.abs(pos) > 0).astype(int)
        blocks = np.where(np.diff(np.concatenate(([0], nonzero, [0]))) != 0)[0]
        run_lengths = blocks[1::2] - blocks[::2] if len(blocks) >= 2 else np.array([0])
        avg_holding_bars = float(np.mean(run_lengths)) if len(run_lengths) else 0.0
    else:
        turnover, trade_count, avg_holding_bars = 0.0, 0, 0.0

    if "Action" in history_df.columns:
        acts = pd.to_numeric(history_df["Action"], errors="coerce").fillna(0).astype(int).values
        hold_ratio = float(np.mean(acts == 0))
    else:
        hold_ratio = 1.0

    return {
        "total_return": total_return,
        "annualized_return": annualized,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "sortino": sortino,
        "turnover": turnover,
        "trade_count": trade_count,
        "hold_ratio": hold_ratio,
        "avg_holding_bars": avg_holding_bars
    }

def compute_directional_edge(history_df: pd.DataFrame) -> Dict[str, float]:
    if history_df.empty or "Close" not in history_df.columns or "Action" not in history_df.columns:
        return {"pos_next1": 0.0, "neg_next1": 0.0, "pos_next3": 0.0, "neg_next3": 0.0, "edge_gap_1": 0.0, "edge_gap_3": 0.0}
    h = history_df.copy()
    h["Close"] = pd.to_numeric(h["Close"], errors="coerce")
    h["Action"] = pd.to_numeric(h["Action"], errors="coerce").fillna(0).astype(int)
    h["ret1"] = h["Close"].shift(-1) / h["Close"] - 1.0
    h["ret3"] = h["Close"].shift(-3) / h["Close"] - 1.0
    pos = h[h["Action"] == 1]
    neg = h[h["Action"] == 2]
    pos1 = float(pos["ret1"].mean()) if not pos.empty else 0.0
    neg1 = float(neg["ret1"].mean()) if not neg.empty else 0.0
    pos3 = float(pos["ret3"].mean()) if not pos.empty else 0.0
    neg3 = float(neg["ret3"].mean()) if not neg.empty else 0.0
    return {"pos_next1": pos1, "neg_next1": neg1, "pos_next3": pos3, "neg_next3": neg3, "edge_gap_1": pos1 - neg1, "edge_gap_3": pos3 - neg3}

def _baseline_action(policy_name: str, row: pd.Series, rng: np.random.Generator) -> int:
    if policy_name == "FLAT":
        return 0
    if policy_name == "RANDOM":
        return int(rng.choice([0, 1, 2, 3], p=[0.30, 0.25, 0.25, 0.20]))
    if policy_name == "SMA":
        trend_v = float(row.get("Trend_30", 0.0))
        if trend_v > 0:
            return 1
        if trend_v < 0:
            return 2
        return 0
    if policy_name == "RSI":
        rsi = float(row.get("RSI14", row.get("RSI", 50.0)))
        if rsi < 30:
            return 1
        if rsi > 70:
            return 2
        return 0
    return 0

def run_baseline_backtest(
    df_slice: pd.DataFrame,
    ticker: str,
    initial_balance: float,
    env_kwargs: dict,
    policy_name: str,
    seed: int = 42
) -> Dict[str, object]:
    env = SingleStockTradingEnv(
        df=df_slice.reset_index(drop=True),
        ticker=ticker,
        initial_balance=initial_balance,
        max_episode_steps=len(df_slice),
        mode="test",
        env_rank=0,
        **env_kwargs
    )
    obs, _ = env.reset()
    terminated = False
    truncated = False
    rng = np.random.default_rng(seed)
    while not (terminated or truncated):
        row = env.df.iloc[env.current_step]
        action = _baseline_action(policy_name, row, rng)
        obs, reward, terminated, truncated, info = env.step(action)
    hist = pd.DataFrame(env.history)
    metrics = compute_history_metrics(hist, initial_balance, interval_to_bars_per_day(TICKINT))
    dirm = compute_directional_edge(hist)
    return {"history": hist, "metrics": metrics, "directional": dirm}

def train_rl_on_window(
    train_df: pd.DataFrame,
    ticker: str,
    best_params: dict,
    initial_balance: float,
    env_kwargs: dict,
    out_dir: Path,
    timesteps: int = 30000
) -> Tuple[Path, Path]:
    env_train = SingleStockTradingEnv(
        df=train_df.reset_index(drop=True),
        ticker=ticker,
        initial_balance=initial_balance,
        max_episode_steps=len(train_df),
        mode="train",
        env_rank=1,
        **env_kwargs
    )
    vec_train = SubprocVecEnv([lambda e=env_train: e])
    vec_train = VecNormalize(vec_train, norm_obs=True, norm_reward=True, clip_obs=10000.0, clip_reward=250000.0)

    model = PPO(
        "MlpPolicy",
        vec_train,
        verbose=0,
        seed=RANDOM_SEED,
        policy_kwargs=dict(activation_fn=torch.nn.ReLU, net_arch=[128, 128]),
        learning_rate=best_params.get("learning_rate", 1e-4),
        n_steps=best_params.get("n_steps", 256),
        batch_size=best_params.get("batch_size", 64),
        gamma=best_params.get("gamma", 0.99),
        gae_lambda=best_params.get("gae_lambda", 0.95),
        clip_range=best_params.get("clip_range", 0.2),
        ent_coef=best_params.get("ent_coef", 0.01),
        vf_coef=best_params.get("vf_coef", 0.5),
        max_grad_norm=best_params.get("max_grad_norm", 0.5),
        tensorboard_log=str(TB_LOG_DIR / "diag_suite"),
        device="cpu"
    )
    model.learn(total_timesteps=timesteps)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "model.zip"
    vecnorm_path = out_dir / "vecnorm.pkl"
    model.save(str(model_path))
    vec_train.save(str(vecnorm_path))
    vec_train.close()
    return model_path, vecnorm_path

def run_experiment_suite(
    ticker_list: List[str],
    instrument_df: pd.DataFrame,
    best_params: dict,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
    interval: str = "60minute",
    history_days: int = 1095,
    train_days: int = 180,
    val_days: int = 20,
    test_days: int = 10,
    step_days: int = 20,
    max_windows_per_ticker: int = 2,
    rl_timesteps: int = 30000
) -> pd.DataFrame:
    exp_dir = RESULTS_DIR / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ticker in ticker_list:
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            continue
        windows = make_walk_forward_slices(df_full, interval, train_days, val_days, test_days, step_days)
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        for widx, (s, tr, va, te) in enumerate(windows, start=1):
            for data_mode in ["real", "shuffled"]:
                df_source = df_full if data_mode == "real" else shuffle_close_series(df_full, seed=RANDOM_SEED + widx, interval=interval)
                train_df = df_source.iloc[s:tr].reset_index(drop=True)
                test_df = df_source.iloc[va:te].reset_index(drop=True)
                if train_df.empty or test_df.empty:
                    continue
                for friction in ["realistic", "frictionless"]:
                    env_kwargs = {
                        "stop_loss": best_params.get("stop_loss", stop_loss),
                        "take_profit": best_params.get("take_profit", take_profit),
                        "max_position_size": best_params.get("max_position_size", max_position_size),
                        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
                        "annual_trading_days": annual_trading_days,
                        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
                        "hold_threshold": best_params.get("hold_threshold", 0.1),
                        "reward_weights": {
                            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
                            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
                            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
                            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
                            "trade_fraction": best_params.get("trade_fraction", 0.25),
                            "reduce_fraction": best_params.get("reduce_fraction", 0.50),
                        },
                        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
                        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
                        "slippage_rate": 0.001 if friction == "realistic" else 0.0,
                        "disable_costs": friction != "realistic",
                    }
                    cycle_dir = exp_dir / f"{ticker}_w{widx:03d}_{data_mode}_{friction}"
                    model_path, vecnorm_path = train_rl_on_window(
                        train_df=train_df,
                        ticker=ticker,
                        best_params=best_params,
                        initial_balance=initial_balance,
                        env_kwargs=env_kwargs,
                        out_dir=cycle_dir,
                        timesteps=rl_timesteps
                    )
                    rl_eval = _evaluate_slice_with_frozen_norm(
                        model_path=model_path,
                        vecnorm_path=vecnorm_path,
                        df_slice=test_df,
                        ticker=ticker,
                        initial_balance=initial_balance,
                        env_kwargs=env_kwargs,
                        eval_tag=f"suite_w{widx:03d}_{data_mode}_{friction}"
                    )
                    rl_hist = pd.DataFrame(rl_eval["history"])
                    rl_metrics = compute_history_metrics(rl_hist, initial_balance, interval_to_bars_per_day(interval))
                    rl_dir = compute_directional_edge(rl_hist)
                    rows.append({"ticker": ticker, "window": widx, "model": "RL", "data_mode": data_mode, "friction": friction, **rl_metrics, **rl_dir})

                    for bname in ["FLAT", "RANDOM", "SMA", "RSI"]:
                        bres = run_baseline_backtest(test_df, ticker, initial_balance, env_kwargs, bname, seed=RANDOM_SEED + widx)
                        rows.append({"ticker": ticker, "window": widx, "model": bname, "data_mode": data_mode, "friction": friction, **bres["metrics"], **bres["directional"]})

    summary_df = pd.DataFrame(rows)
    out_csv = exp_dir / "experiment_comparison.csv"
    summary_df.to_csv(out_csv, index=False)
    main_logger.info(f"[EXPERIMENT SUITE] saved comparison table: {out_csv}")
    return summary_df


def objective(
    trial,
    train_tickers: list,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int
):
    import math
    import numpy as np
    import torch
    import pandas as pd
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList

    # === Define PPO Hyperparameters ===
    learning_rate = trial.suggest_loguniform('learning_rate', 1e-6, 1e-3)
    #n_steps = trial.suggest_categorical('n_steps', [128, 256, 512])
    n_steps = trial.suggest_categorical('n_steps', [512])
    batch_size = trial.suggest_categorical('batch_size', [32, 64])
    gamma = trial.suggest_uniform('gamma', 0.95, 0.999)  # broadened lower bound
    gae_lambda = trial.suggest_uniform('gae_lambda', 0.80, 1.00)
    clip_range = trial.suggest_uniform('clip_range', 0.05, 0.3)  # allowing lower clip range
    ent_coef = trial.suggest_loguniform('ent_coef', 1e-5, 1e-1)
    vf_coef = trial.suggest_uniform('vf_coef', 0.05, 0.5)
    max_grad_norm = trial.suggest_uniform('max_grad_norm', 0.3, 1.0)
    #net_arch_str = trial.suggest_categorical('net_arch', ['128_128', '256_256', '128_256_128'])

    # === Define Environment-Specific Tuning Parameters ===
    drawdown_penalty_factor = trial.suggest_float('drawdown_penalty_factor', 0.0, 5.0, log=False)
    tuned_stop_loss = trial.suggest_float('stop_loss', 0.75, 0.95, step=0.01)  # broadened lower bound for stop loss
    tuned_take_profit = trial.suggest_float('take_profit', 1.01, 1.50, step=0.01)  # broader take profit range    
    tuned_reward_scale = trial.suggest_float('reward_scale', 0.5, 3.0, step=0.1)  # higher upper bound
    tuned_max_position_size = trial.suggest_float('max_position_size', 0.5, 1.0, step=0.1)
    tuned_max_drawdown = trial.suggest_float('max_drawdown', 0.02, 0.2, step=0.005)  # allow for a higher maximum drawdown
    profit_weight = trial.suggest_float('profit_weight', 0.0, 5.0)
    sharpe_bonus_weight = trial.suggest_float('sharpe_bonus_weight', 0.01, 5.0)
    transaction_penalty_weight = trial.suggest_float("transaction_penalty_weight", 0.0, 5.0, log=False)
    holding_bonus_weight = trial.suggest_float('holding_bonus_weight', 0.0, 5.0)
    
    volatility_threshold = trial.suggest_float("volatility_threshold", 0.5, 2.5)
    momentum_threshold_min = trial.suggest_float("momentum_threshold_min", 30, 50)
    momentum_threshold_max = trial.suggest_float("momentum_threshold_max", 50, 80)  # broadened range
    hold_threshold = trial.suggest_float("hold_threshold", 0.0, 0.1, step=0.01)

    tuned_inference_buy_threshold = trial.suggest_float("inference_buy_threshold", 0.05, 0.1)
    tuned_inference_sell_threshold = trial.suggest_float("inference_sell_threshold", 0.05, 0.1)

    # === New Hyperparameters for Forced Penalty Weights ===
    # Broadened to allow near-zero (minimal penalty) up to higher values if needed.
    forced_stop_penalty_weight = trial.suggest_float("forced_stop_penalty_weight", 0.0, 5.0,  log=False)
    forced_tp_penalty_weight = trial.suggest_float("forced_tp_penalty_weight", 0.0, 5.0, log=False)

    # === Build Environment List and Store Ticker-Env Pairs ===
    env_factories = []
    env_pairs = []  # list of (ticker, env_instance)
    for i, ticker in enumerate(train_tickers):
        main_logger.info(f"[Trial {trial.number}] Creating training environment for ticker {ticker}")
        # After: Fetching data with Kite
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.error(f"Token not found for ticker {ticker}. Skipping.")
            continue  # Skip this ticker if the token isn't found
        df_full = get_data_kite(kite, instrument_token=token, days=DTDAYS, interval=TICKINT)

        if df_full.empty:
            main_logger.warning(f"[Trial {trial.number}] No data for ticker {ticker}. Skipping.")
            continue
        df_train, df_val, df_test = split_chronological(df_full, train_ratio=0.70, val_ratio=0.15)
        if df_train.empty:
            main_logger.warning(f"[Trial {trial.number}] Training data empty for ticker {ticker}. Skipping.")
            continue
        main_logger.info(f"[Trial {trial.number}] {ticker} split sizes train/val/test: {len(df_train)}/{len(df_val)}/{len(df_test)}")

        env_instance = SingleStockTradingEnv(
            df=df_train,
            ticker=ticker,
            initial_balance=initial_balance,
            stop_loss=tuned_stop_loss,
            take_profit=tuned_take_profit,
            max_position_size=tuned_max_position_size,
            max_drawdown=tuned_max_drawdown,
            annual_trading_days=annual_trading_days,            
            env_rank=i,
            some_factor=drawdown_penalty_factor,
            hold_threshold=hold_threshold,
            reward_weights={
                'reward_scale': tuned_reward_scale,
                'profit_weight': profit_weight,
                'sharpe_bonus_weight': sharpe_bonus_weight,
                'transaction_penalty_weight': transaction_penalty_weight,
                'holding_bonus_weight': holding_bonus_weight,                
                'volatility_threshold': volatility_threshold,
                'momentum_threshold_min': momentum_threshold_min,
                'momentum_threshold_max': momentum_threshold_max,
                'forced_stop_penalty_weight': forced_stop_penalty_weight,
                'forced_tp_penalty_weight': forced_tp_penalty_weight
            },
            max_episode_steps=len(df_train),
            mode="train",  # Training mode: filtering is NOT applied here.
            inference_buy_threshold=tuned_inference_buy_threshold,
            inference_sell_threshold=tuned_inference_sell_threshold  
        )
        main_logger.info(f"[Trial {trial.number}] Environment for ticker {ticker} created (env_rank={i}).")
        env_pairs.append((ticker, env_instance))
        # Wrap each environment instance in a lambda for SubprocVecEnv.
        env_factories.append(lambda e=env_instance: e)
    
    if not env_factories:
        main_logger.critical(f"[Trial {trial.number}] No training environments were created. Exiting trial.")
        return -math.inf

    vec_env_train = SubprocVecEnv(env_factories)
    vec_env_train = VecNormalize(vec_env_train, norm_obs=True, norm_reward=True, clip_obs=10000.0, clip_reward=250000.0)
    
    # === Build PPO Model with Dynamic Network Architecture ===
    # Sample the number of layers (6-9) and each layer's size ([64, 128, 256])
    num_layers = trial.suggest_int("num_layers", 2, 5)
    net_arch = []
    for layer_i in range(num_layers):
        layer_size = trial.suggest_categorical(f"layer_size_{layer_i}", [64, 128, 256])
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
        monitor="rolling_sharpe",   # (name is cosmetic now)
        patience=3000,              # lower is fine – metric is smoother
        min_delta=0.02,             # require 0.02 Sharpe uplift
        verbose=1,
        trial_id=trial.number,
        window=2000)                # 2 000 SB3 steps ≈ few episodes

    callback_list = CallbackList([custom_callback, checkpoint_callback, early_stopping_callback])
    
    # === PPO Training ===
    total_timesteps = 50000
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
    # For example, if training used the default ±10 clipping:
    vec_env_train.clip_obs = 10000.0      # match training's observation clipping range
    vec_env_train.clip_reward = 25000.0   # match training's reward clipping range

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
            action, _ = model.predict(obs, deterministic=True)
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
        
        # Write raw history CSV.
        history_file = RESULTS_DIR / f"trial_{trial.number}_{ticker}_full_history.csv"
        try:
            pd.DataFrame(history).to_csv(history_file, index=False)
            main_logger.info(f"[Trial {trial.number}] Ticker {ticker}: Full raw history saved to {history_file}")
        except Exception as e:
            main_logger.warning(f"[Trial {trial.number}] Ticker {ticker}: Failed to save raw history: {e}")

    # Clean up vectorized environment to free memory after the trial
    vec_env_train.close()      # Close all subprocesses
    del vec_env_train          # Delete the reference
    import gc
    gc.collect()               # Force garbage collection

    return networth_change


if __name__ == "__main__":
    main_logger.info("Starting pipeline for multi‐ticker training (ITC, APOLLOTYRE) and single‐ticker testing (GRINDWELL).")

    # ----------------------------------------------------------------
    # 1. Function to read CSV from 'data/' and parse indicators
    # ----------------------------------------------------------------
    import os
    import pandas as pd
    import yfinance as yf
    from pathlib import Path
    from ta import trend, momentum, volatility, volume

    def get_data(ticker: str, period: str = "60d", interval: str = "15m") -> pd.DataFrame:
        """
        Fetches intraday data from yfinance for a given ticker using the specified period and interval,
        then performs validations and technical indicator calculations.
        
        This version is tailored for data where:
        - The row index is a DatetimeIndex named "Datetime".
        - The columns are a MultiIndex with the first level containing actual field names
            (e.g. "Close", "High", "Low", "Open", "Volume") and the second level holding the ticker.
        The function resets and flattens the DataFrame so that downstream code sees:
        ["Date", "Close", "High", "Low", "Open", "Volume", "Adj Close", ...] 
        """
        main_logger.info(f"Fetching {interval} data from yfinance for ticker {ticker} over period {period}")
        
        RESULTS_DIR = Path("./results")
        RESULTS_DIR.mkdir(exist_ok=True, parents=True)
        
        # We'll require these columns (we expect "Adj Close" for compatibility)
        required_columns = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
        
        try:
            # Download intraday data; set auto_adjust=False to preserve "Adj Close" (if available)
            df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
        except Exception as e:
            main_logger.error(f"Error fetching data from yfinance for ticker {ticker}: {e}")
            return pd.DataFrame()
        
        if df.empty:
            main_logger.error(f"No data fetched from yfinance for ticker {ticker}")
            return pd.DataFrame()
        
        # Reset index so that the DatetimeIndex becomes a column.
        df.reset_index(inplace=True)
        
        # Flatten MultiIndex columns by taking the first level.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        
        # After reset, the date information is in a column likely named "Datetime".
        # Rename it to "Date" for compatibility.
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Date"}, inplace=True)
        
        # (Optional) If the first row of the Date column contains the literal "Date", drop that row.
        if "Date" in df.columns and df["Date"].iloc[0] == "Date":
            df = df.iloc[1:]
        
        # If "Adj Close" is missing, create it from "Close"
        if "Adj Close" not in df.columns:
            df["Adj Close"] = df["Close"]
        
        # Confirm required columns exist.
        for col in ["Date", "Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                main_logger.error(f"[get_data] Missing required column '{col}' for {ticker}.")
                return pd.DataFrame()
        
        # Convert the "Date" column to datetime.
        try:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            # If conversion fails entirely, fallback to an integer series.
            if df["Date"].isna().all():
                raise ValueError("All Date conversion results are NaT")
            # Remove timezone information.
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception as e:
            main_logger.warning(f"[get_data] Could not convert 'Date' column for {ticker} ({e}). Using integer series instead.")
            df["Date"] = np.arange(len(df))
        
        # Sort by Date and reset index.
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        # Convert numeric columns.
        numeric_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        
        # Check minimum data length (adjust if needed for intraday data)
        if len(df) < 200:
            main_logger.error(f"[get_data] Not enough data points ({len(df)}) for ticker {ticker}. Need >= 200.")
            return pd.DataFrame()
        
        
        # Calculate technical indicators.
        try:
            # Inside the get_data() function, after verifying the DataFrame is not empty:
            # After sorting, converting numeric columns, etc.
            # Determine indicator parameters based on interval
            if interval.endswith("m"):
                sma_short_window = 3    # for "SMA10", use a shorter window in intraday data
                sma_long_window = 9     # for "SMA50"
                rsi_window = 7          # shorter RSI window
                adx_window = 7          # shorter ADX window
                bollinger_window = 10   # shorter Bollinger window
                ema_window = 5          # for "EMA20"
            else:
                sma_short_window = 10
                sma_long_window = 50
                rsi_window = 14
                adx_window = 14
                bollinger_window = 20
                ema_window = 20

            close = df["Close"].squeeze()
            high = df["High"].squeeze()
            low = df["Low"].squeeze()
            vol_series = df["Volume"].squeeze()

            # Apply log transformation to the Close price and compute log returns
            df['Log_Close'] = np.log(df['Close'])
            df['Log_Return'] = df['Log_Close'].diff().fillna(0)

            # Calculate technical indicators and assign them to the same column names for compatibility:
            df["SMA10"] = trend.SMAIndicator(close=close, window=sma_short_window).sma_indicator()
            df["SMA50"] = trend.SMAIndicator(close=close, window=sma_long_window).sma_indicator()
            df["RSI"] = momentum.RSIIndicator(close=close, window=rsi_window).rsi()
            df["MACD"] = trend.MACD(close=close).macd()
            df["ADX"] = trend.ADXIndicator(high=high, low=low, close=close, window=adx_window).adx()
            bollinger = volatility.BollingerBands(close=close, window=bollinger_window, window_dev=2)
            df["BB_Upper"] = bollinger.bollinger_hband()
            df["BB_Lower"] = bollinger.bollinger_lband()
            df["Bollinger_Width"] = bollinger.bollinger_wband()
            df["EMA20"] = trend.EMAIndicator(close=close, window=ema_window).ema_indicator()
            df["VWAP"] = volume.VolumeWeightedAveragePrice(
                high=high, low=low, close=close, volume=vol_series, window=14
            ).volume_weighted_average_price()
            df["Lagged_Return"] = close.pct_change().fillna(0)
            df["Volatility"] = volatility.AverageTrueRange(
                high=high, low=low, close=close, window=adx_window
            ).average_true_range()

            # ------------------- ADD/EDIT THESE LINES IN get_data() -------------------
            # 1) Add time-of-day and day-of-week features
            df['HourOfDay'] = df['Date'].dt.hour
            df['MinuteOfHour'] = df['Date'].dt.minute
            df['DayOfWeek'] = df['Date'].dt.dayofweek  # Monday=0, Sunday=6

            # 2) Short-lag returns (e.g. 1-bar, 2-bar, etc.)
            df['Lag_Return_1'] = df['Close'].pct_change(1).fillna(0)
            df['Lag_Return_2'] = df['Close'].pct_change(2).fillna(0)
            # Or you can do lagged log-returns if you prefer
            # df['Lag_Log_Return_1'] = df['Log_Close'].diff(1).fillna(0)

            # 3) Volume-based features: e.g. volume delta, rolling ratio
            df['Volume_Change_1'] = df['Volume'].pct_change(1).fillna(0)
            df['Volume_RollRatio'] = (df['Volume'] / df['Volume'].rolling(5).mean()).fillna(1)

            # 4) Range-based feature: difference or percentage of (High - Low)
            df['Intraday_Range'] = df['High'] - df['Low']
            df['Intraday_Range_Pct'] = (df['High'] - df['Low']) / (df['Close'] + 1e-9)

            # 5) Time-since-market-open or etc. (requires you know market open time)
            # For partial demonstration, if your local exchange day starts at 09:30:
            df['MinutesSinceOpen'] = (df['Date'] - df['Date'].dt.normalize() - pd.Timedelta("9h30m")).dt.total_seconds() / 60
            df['MinutesSinceOpen'] = df['MinutesSinceOpen'].clip(lower=0)  # no negatives

        except Exception as e:
            main_logger.error(f"[get_data] Error calculating indicators for {ticker}: {e}")
            return pd.DataFrame()
        
        # Fill missing values.
        df.fillna(method="ffill", inplace=True)
        df.fillna(0, inplace=True)
        
        # Save raw CSV for reference.
        raw_csv_file = RESULTS_DIR / f"data_fetched_{ticker}.csv"
        try:
            df.to_csv(raw_csv_file, index=False)
            main_logger.info(f"[get_data] Wrote raw CSV for ticker {ticker}: {raw_csv_file}")
        except Exception as e:
            main_logger.error(f"[get_data] Failed to write raw CSV for {ticker}: {e}")
            return pd.DataFrame()
        
        main_logger.info(f"[get_data] Successfully fetched & validated data for {ticker}. Final shape: {df.shape}")
        return df   

    train_tickers = NSE_LIQUID_UNIVERSE.copy()
    optuna_tickers = NSE_LIQUID_UNIVERSE[:16]

    # ----------------------------------------------------------------
    # 3. Prepare single ticker (GRINDWELL) for final testing
    # ----------------------------------------------------------------
    """ test_ticker = "ITC.NS"
    df_test_full = get_data(test_ticker, period="60d", interval="15m")
    if df_test_full.empty:
        main_logger.error(f"No data for test ticker {test_ticker}. Exiting.")
        exit()

    split_idx_test = int(len(df_test_full) * 0.8)
    test_df = df_test_full.iloc[split_idx_test:].reset_index(drop=True)
    main_logger.info(f"{test_ticker} test portion rows = {len(test_df)}") """

    # ----------------------------------------------------------------
    # 4. Basic config + Setup Optuna
    # ----------------------------------------------------------------
    INITIAL_BALANCE = 10000
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

    n_trials = 10
    main_logger.info(f"Starting Optuna study for {n_trials} trials with multiple training envs.")

    study.optimize(
        lambda trial: objective(
            trial,
            train_tickers=optuna_tickers,
            initial_balance=INITIAL_BALANCE,
            stop_loss=0.90,
            take_profit=1.10,
            max_position_size=0.5,
            max_drawdown=0.20,
            annual_trading_days=252
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
    optuna_tuned_inference_buy_threshold = best_params["inference_buy_threshold"]
    optuna_tuned_inference_sell_threshold = best_params["inference_sell_threshold"]

    # ----------------------------------------------------------------
    # 4b. Walk-forward mode (recommended for non-stationary markets)
    # ----------------------------------------------------------------
    ENABLE_EXPERIMENT_SUITE = False
    if ENABLE_EXPERIMENT_SUITE:
        main_logger.info("Starting diagnostic experiment suite (RL vs baselines, real/shuffled, cost-on/off).")
        diag_tickers = NSE_LIQUID_UNIVERSE[:5]
        run_experiment_suite(
            ticker_list=diag_tickers,
            instrument_df=instrument_df,
            best_params=best_params,
            initial_balance=INITIAL_BALANCE,
            stop_loss=STOP_LOSS,
            take_profit=TAKE_PROFIT,
            max_position_size=MAX_POSITION_SIZE,
            max_drawdown=MAX_DRAWDOWN,
            annual_trading_days=ANNUAL_TRADING_DAYS,
            interval=TICKINT,
            history_days=max(TRAIN_HISTORY_DAYS, 1095),
            train_days=180,
            val_days=20,
            test_days=10,
            step_days=20,
            max_windows_per_ticker=2,
            rl_timesteps=30000
        )
        raise SystemExit(0)

    ENABLE_WALK_FORWARD = True
    if ENABLE_WALK_FORWARD:
        main_logger.info("Starting walk-forward training/validation/testing pipeline.")
        wf_tickers = NSE_LIQUID_UNIVERSE.copy()
        walk_forward_runner(
            ticker_list=wf_tickers,
            instrument_df=instrument_df,
            best_params=best_params,
            initial_balance=INITIAL_BALANCE,
            stop_loss=STOP_LOSS,
            take_profit=TAKE_PROFIT,
            max_position_size=MAX_POSITION_SIZE,
            max_drawdown=MAX_DRAWDOWN,
            annual_trading_days=ANNUAL_TRADING_DAYS,
            interval=TICKINT,
            history_days=max(TRAIN_HISTORY_DAYS, 1095),
            train_days=730,
            val_days=90,
            test_days=30,
            step_days=30,
            train_timesteps=50000
        )
        raise SystemExit(0)

    # ----------------------------------------------------------------
    # 5. Final training pass with best hyperparams
    # ----------------------------------------------------------------
    main_logger.info("Final training pass with best hyperparams from Optuna.")

    final_envs = []
    for i, ticker in enumerate(train_tickers):
        # After: Fetching data with Kite
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.error(f"Token not found for ticker {ticker}. Skipping.")
            continue  # Skip this ticker if the token isn't found
        df_full = get_data_kite(kite, instrument_token=token, days=TRAIN_HISTORY_DAYS, interval=TICKINT)

        if df_full.empty:
            continue
        df_train, df_val, df_test = split_chronological(df_full, train_ratio=0.70, val_ratio=0.15)
        df_train = df_train.reset_index(drop=True)
        main_logger.info(f"[Final Train] {ticker} split sizes train/val/test: {len(df_train)}/{len(df_val)}/{len(df_test)}")

        env_instance = SingleStockTradingEnv(
            df=df_train,
            ticker=ticker,
            initial_balance=INITIAL_BALANCE,
            stop_loss=best_params.get('stop_loss', STOP_LOSS),
            take_profit=best_params.get('take_profit', TAKE_PROFIT),
            max_position_size=best_params.get('max_position_size', MAX_POSITION_SIZE),
            max_drawdown=best_params.get('max_drawdown', MAX_DRAWDOWN),
            annual_trading_days=ANNUAL_TRADING_DAYS,            
            env_rank=1000 + i,
            some_factor=best_params.get('drawdown_penalty_factor', 0.01),
            hold_threshold=best_params.get('hold_threshold', 0.1),
            reward_weights={
                'reward_scale': best_params.get('reward_scale', 1.0),
                'profit_weight': best_params.get('profit_weight', 1.5),
                'sharpe_bonus_weight': best_params.get('sharpe_bonus_weight', 0.05),
                'transaction_penalty_weight': best_params.get('transaction_penalty_weight', 1),
                'holding_bonus_weight': best_params.get('holding_bonus_weight', 0.001),                
                'volatility_threshold': best_params.get('volatility_threshold', 1.0),
                'momentum_threshold_min': best_params.get('momentum_threshold_min', 30),
                'momentum_threshold_max': best_params.get('momentum_threshold_max', 70),
                # New hyperparameters for penalty weights:
                'forced_stop_penalty_weight': best_params.get('forced_stop_penalty_weight', 1.0),
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0)
            },
            max_episode_steps=len(df_train),
            mode="train",  # Training mode
            inference_buy_threshold=optuna_tuned_inference_buy_threshold,
            inference_sell_threshold=optuna_tuned_inference_sell_threshold
        )
        final_envs.append(lambda e=env_instance: e)

    vec_env_final = SubprocVecEnv(final_envs)
    vec_env_final = VecNormalize(vec_env_final, norm_obs=True, norm_reward=True, clip_obs=10000.0, clip_reward=250000.0)

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
        tensorboard_log=str(TB_LOG_DIR / "final_model"),
        device='cpu'
    )

    total_timesteps = 150000
    main_logger.info(f"Learning final model for {total_timesteps} timesteps with multiple tickers.")
    model_final.learn(total_timesteps=total_timesteps)

    # Save the model and VecNormalize object to the results directory
    model_save_path = RESULTS_DIR / "ppo_final_model.zip"
    vecenv_save_path = RESULTS_DIR / "vec_normalize.pkl"
    model_final.save(str(model_save_path))
    vec_env_final.save(str(vecenv_save_path))

    main_logger.info(f"Final multi‐ticker model saved to {model_save_path} and VecNormalize saved to {vecenv_save_path}.")


    # ----------------------------------------------------------------
    # 6. Test on multiple tickers with saved normalization and save test history to CSV
    # ----------------------------------------------------------------

    test_tickers = ["KOTAKBANK", "ITC", "ASIANPAINT", "AXISBANK", "LT", "NTPC", "SBIN"]


    for test_ticker in test_tickers:
        main_logger.info(f"Preparing test data for ticker {test_ticker}.")

        # 1) Get the DataFrame for this ticker.
        # After: Using Kite to get test data
        token = get_instrument_token(test_ticker, instrument_df)
        if token is None:
            main_logger.error(f"Token not found for test ticker {test_ticker}. Skipping inference.")
            continue
        df_test_full = get_data_kite(kite, instrument_token=token, days=TEST_HISTORY_DAYS, interval=TICKINT)
        if df_test_full.empty:
            main_logger.error(f"No data for test ticker {test_ticker}. Skipping inference.")
            continue

        train_df_tmp, val_df_tmp, test_df = split_chronological(df_test_full, train_ratio=0.70, val_ratio=0.15)
        test_df = test_df.reset_index(drop=True)
        main_logger.info(f"{test_ticker} split sizes train/val/test: {len(train_df_tmp)}/{len(val_df_tmp)}/{len(test_df)}")

        # 2) Create and wrap environment
        env_test = SingleStockTradingEnv(
            df=test_df,
            ticker=test_ticker,
            initial_balance=INITIAL_BALANCE,
            stop_loss=best_params.get('stop_loss', STOP_LOSS),
            take_profit=best_params.get('take_profit', TAKE_PROFIT),
            max_position_size=best_params.get('max_position_size', MAX_POSITION_SIZE),
            max_drawdown=best_params.get('max_drawdown', MAX_DRAWDOWN),
            annual_trading_days=ANNUAL_TRADING_DAYS,            
            env_rank=9999,
            some_factor=best_params.get('drawdown_penalty_factor', 0.01),
            hold_threshold=best_params.get('hold_threshold', 0.1),
            reward_weights={
                'reward_scale': best_params.get('reward_scale', 1.0),
                'profit_weight': best_params.get('profit_weight', 1.5),
                'sharpe_bonus_weight': best_params.get('sharpe_bonus_weight', 0.05),
                'transaction_penalty_weight': best_params.get('transaction_penalty_weight', 1e-3),
                'holding_bonus_weight': best_params.get('holding_bonus_weight', 0.001),                
                'volatility_threshold': best_params.get('volatility_threshold', 1.0),
                'momentum_threshold_min': best_params.get('momentum_threshold_min', 30),
                'momentum_threshold_max': best_params.get('momentum_threshold_max', 70),
                # New hyperparameters for penalty weights:
                'forced_stop_penalty_weight': best_params.get('forced_stop_penalty_weight', 1.0),
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0)
            },
            max_episode_steps=len(test_df),
            mode="test",
            inference_buy_threshold=optuna_tuned_inference_buy_threshold,
            inference_sell_threshold=optuna_tuned_inference_sell_threshold
        )

        from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

        # Create the vectorized test environment using env_test
        test_vec = SubprocVecEnv([lambda: env_test])

        # Load the VecNormalize object from RESULTS_DIR
        vecnorm_path = RESULTS_DIR / "vec_normalize.pkl"
        if not vecnorm_path.exists():
            main_logger.error(f"VecNormalize file not found at {vecnorm_path}")
        else:
            main_logger.info(f"Loading VecNormalize from {vecnorm_path}")
        test_vec = VecNormalize.load(str(vecnorm_path), test_vec)
        test_vec.training = False
        test_vec.norm_reward = False
        # For example, if training used the default ±10 clipping:
        test_vec.clip_obs = 10000.0      # match training's observation clipping range
        test_vec.clip_reward = 25000.0   # match training's reward clipping range

        # Load the final model from RESULTS_DIR
        model_path = RESULTS_DIR / "ppo_final_model.zip"
        if not model_path.exists():
            main_logger.error(f"Model file not found at {model_path}")
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
            action, _ = loaded_model.predict(obs, deterministic=True)
            obs, rewards, done, infos = test_vec.step(action)
            steps_taken += 1
            if steps_taken % 100 == 0:
                training_logger.info(f"[Test Ticker={test_ticker}] Step {steps_taken}: Action={action}, Rewards={rewards}")

        # 5) Retrieve the RL agent’s final metrics & history
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

        # 6) Directly convert the environment’s step-by-step history to DataFrame
        #    (No flatten needed, because we already store indicators & fields top-level.)
        test_history_file = RESULTS_DIR / f"test_env_history_{test_ticker}.csv"
        if rl_test_history:            
            rl_test_df = pd.DataFrame(rl_test_history)
            rl_test_df.to_csv(test_history_file, index=False)
            main_logger.info(f"Testing environment history for {test_ticker} saved to {test_history_file}")
        else:
            pd.DataFrame().to_csv(test_history_file, index=False)
            main_logger.warning(f"Test history was empty for {test_ticker}. Saved empty CSV at {test_history_file}")
