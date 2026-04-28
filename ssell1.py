import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import copy
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
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
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
import argparse
import ast
import re

from ta.momentum import StochasticOscillator
from ta.volume import ChaikinMoneyFlowIndicator, OnBalanceVolumeIndicator, ForceIndexIndicator
from ta.volatility import KeltnerChannel


try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
except ImportError:
    raise ImportError("Please install 'concurrent-log-handler' package via pip: pip install concurrent-log-handler")


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)

BASE_DIR = Path('.').resolve()
load_local_env(BASE_DIR / ".env")
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

ACTIVE_LOG_FILES = ("main.log", "training.log", "testing.log", "phase.log")
LOG_ARCHIVE_DIR = RESULTS_DIR / "log_runs"


def rotate_active_logs(results_dir: Path, archive_dir: Path, filenames: tuple[str, ...]) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = archive_dir / f"run_{timestamp}"
    moved_any = False
    for filename in filenames:
        src = results_dir / filename
        if not src.exists() or src.stat().st_size == 0:
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        dst = run_dir / filename
        try:
            src.replace(dst)
            moved_any = True
        except Exception:
            # If the file is locked for any reason, leave it in place rather than failing startup.
            continue
    if moved_any:
        latest_ptr = archive_dir / "latest_run_dir.txt"
        latest_ptr.write_text(str(run_dir), encoding="utf-8")


rotate_active_logs(RESULTS_DIR, LOG_ARCHIVE_DIR, ACTIVE_LOG_FILES)

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

SECTOR_PROXY_MAP = {
    "HDFCBANK": "BANKBEES",
    "ICICIBANK": "BANKBEES",
    "SBIN": "BANKBEES",
    "AXISBANK": "BANKBEES",
    "KOTAKBANK": "BANKBEES",
    "TCS": "ITBEES",
    "INFY": "ITBEES",
    "WIPRO": "ITBEES",
    "HCLTECH": "ITBEES",
    "TECHM": "ITBEES",
    "SUNPHARMA": "PHARMABEES",
    "DRREDDY": "PHARMABEES",
    "CIPLA": "PHARMABEES",
}

MARKET_PROXY_SYMBOL = "NIFTYBEES"
SIGNAL_OVERLAY_SOURCES: Dict[str, tuple[list[Path], str]] = {
    "E102": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_two_track" / "latest" / "promoted_predictions_oos.csv",
        ],
        "Signal_E102",
    ),
    "E302": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_generalization" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_two_track" / "latest" / "promoted_predictions_oos.csv",
        ],
        "Signal_E302",
    ),
    "E401": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_generalization_next" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_generalization_next" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E401",
    ),
    "E407": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_generalization_next" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_generalization_next" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E407",
    ),
    "E209": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_e102_deepdive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_e102_deepdive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E209",
    ),
    "E211": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_e102_deepdive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_e102_deepdive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E211",
    ),
    "E501": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E501",
    ),
    "E502": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E502",
    ),
    "E503": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E503",
    ),
    "E504": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E504",
    ),
    "E505": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E505",
    ),
    "E506": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E506",
    ),
    "E507": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E507",
    ),
    "E508": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E508",
    ),
    "E605": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E605",
    ),
    "E606": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E606",
    ),
    "E607": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E607",
    ),
    "E610": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_ablation_grid" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E610",
    ),
    "E702": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E702",
    ),
    "E703": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E703",
    ),
    "E705": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E705",
    ),
    "E706": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_setup_regimes" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E706",
    ),
    "E801": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E801",
    ),
    "E803": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E803",
    ),
    "E804": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E804",
    ),
    "E806": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_market_state_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E806",
    ),
    "E903": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E903",
    ),
    "E904": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E904",
    ),
    "E905": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E905",
    ),
    "E906": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_multiscale_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E906",
    ),
    "E1101": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1101",
    ),
    "E1102": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1102",
    ),
    "E1103": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1103",
    ),
    "E1104": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1104",
    ),
    "E1105": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1105",
    ),
    "E1106": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1106",
    ),
    "E1201": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1201",
    ),
    "E1202": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1202",
    ),
    "E1203": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1203",
    ),
    "E1204": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1204",
    ),
    "E1301": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1301",
    ),
    "E1302": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1302",
    ),
    "E1303": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1303",
    ),
    "E1304": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_breadth_context_60m" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1304",
    ),
    "E1401": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1401",
    ),
    "E1402": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1402",
    ),
    "E1403": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1403",
    ),
    "E1404": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_time_distribution_v2" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1404",
    ),
    "E1501": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1501",
    ),
    "E1502": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1502",
    ),
    "E1503": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1503",
    ),
    "E1504": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_execution" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1504",
    ),
    "E1601": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1601",
    ),
    "E1602": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1602",
    ),
    "E1603": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1603",
    ),
    "E1604": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1604",
    ),
    "E1701": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1701",
    ),
    "E1702": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1702",
    ),
    "E1703": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1703",
    ),
    "E1704": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1704",
    ),
    "E2701": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2701",
    ),
    "E2702": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2702",
    ),
    "E2703": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2703",
    ),
    "E2704": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2704",
    ),
    "E1801": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1801",
    ),
    "E1802": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1802",
    ),
    "E1803": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1803",
    ),
    "E1804": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1804",
    ),
    "E1901": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1901",
    ),
    "E1902": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1902",
    ),
    "E1903": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1903",
    ),
    "E1904": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E1904",
    ),
    "E2001": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2001",
    ),
    "E2002": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2002",
    ),
    "E2003": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2003",
    ),
    "E2004": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2004",
    ),
    "E2101": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2101",
    ),
    "E2102": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2102",
    ),
    "E2103": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2103",
    ),
    "E2104": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2104",
    ),
    "E2201": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2201",
    ),
    "E2202": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2202",
    ),
    "E2203": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2203",
    ),
    "E2204": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2204",
    ),
    "E2301": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2301",
    ),
    "E2302": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2302",
    ),
    "E2303": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2303",
    ),
    "E2304": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2304",
    ),
    "E2501": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2501",
    ),
    "E2502": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2502",
    ),
    "E2503": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2503",
    ),
    "E2504": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2504",
    ),
    "E2601": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2601",
    ),
    "E2602": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2602",
    ),
    "E2603": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2603",
    ),
    "E2604": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2604",
    ),
    "E2801": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2801",
    ),
    "E2802": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2802",
    ),
    "E2803": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2803",
    ),
    "E2804": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2804",
    ),
    "E2805": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2805",
    ),
    "E2806": (
        [
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "promoted_predictions_oos.csv",
            BASE_DIR / "results" / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "experiment_predictions_oos.csv",
        ],
        "Signal_E2806",
    ),
}
SIGNAL_OVERLAY_EXPERIMENT_ID = "E102"
_SIGNAL_OVERLAY_CACHE: Dict[str, pd.DataFrame] = {}
_DATA_KITE_CACHE: Dict[tuple, object] = {}
EVENT_CONDITIONED_SIZING_VETO_DIR = (
    RESULTS_DIR / "signal_research" / "outputs_event_conditioned_sizing_veto" / "latest"
)
EVENT_CONDITIONED_SIZING_VETO_CANDIDATES: Dict[str, Dict[str, object]] = {
    "E2401": {
        "policy_name": "SIGNAL_E2401_E211_EVENT_VETO",
        "label": "EventRankConfirm",
        "primary_experiment": "E2004",
        "primary_threshold": 0.60,
        "source_experiments": ["E2004"],
        "description": "Keep E211 only when the 15m top-k event-rank survivor E2004 is high-confidence.",
    },
    "E2402": {
        "policy_name": "SIGNAL_E2402_E211_CONTEXT_VETO",
        "label": "ContextConfirmControl",
        "primary_experiment": "E2201",
        "primary_threshold": 0.60,
        "source_experiments": ["E2201"],
        "description": "Control overlay: keep E211 only when the daily-context survivor E2201 is supportive.",
    },
    "E2403": {
        "policy_name": "SIGNAL_E2403_E211_EVENT_CONTEXT_VETO",
        "label": "EventContextConsensus",
        "primary_experiment": "E2004",
        "primary_threshold": 0.60,
        "secondary_experiment": "E2201",
        "secondary_threshold": 0.60,
        "source_experiments": ["E2004", "E2201"],
        "description": "Keep E211 only when both the 15m event-rank survivor and the slower context survivor agree.",
    },
}
EVENT_CONDITIONED_SIZING_VETO_POLICY_NAMES = [
    str(cfg["policy_name"])
    for cfg in EVENT_CONDITIONED_SIZING_VETO_CANDIDATES.values()
]
EVENT_CONDITIONED_SIZING_VETO_POLICY_CONFIGS = {
    str(cfg["policy_name"]): cfg
    for cfg in EVENT_CONDITIONED_SIZING_VETO_CANDIDATES.values()
}

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


def load_signal_overlay_predictions(experiment_id: str = SIGNAL_OVERLAY_EXPERIMENT_ID) -> pd.DataFrame:
    cache_key = f"signal_overlay::{experiment_id}"
    cached = _SIGNAL_OVERLAY_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()

    export_cfg = SIGNAL_OVERLAY_SOURCES.get(experiment_id)
    if export_cfg is None:
        empty = pd.DataFrame(columns=["Ticker", "Date", f"Signal_{experiment_id}_Pred"])
        _SIGNAL_OVERLAY_CACHE[cache_key] = empty
        return empty.copy()
    export_paths, signal_prefix = export_cfg
    existing_paths = [path for path in export_paths if path.exists()]

    if not existing_paths:
        empty = pd.DataFrame(columns=["Ticker", "Date", f"{signal_prefix}_Pred"])
        _SIGNAL_OVERLAY_CACHE[cache_key] = empty
        return empty.copy()
    pred_df = pd.DataFrame()
    export_path = existing_paths[0]
    for candidate_path in existing_paths:
        try:
            candidate_df = pd.read_csv(candidate_path)
        except Exception as exc:
            main_logger.warning(f"[SIGNAL OVERLAY] failed to read {candidate_path}: {exc}")
            continue
        if candidate_df.empty or "ExperimentID" not in candidate_df.columns:
            continue
        candidate_df = candidate_df.loc[candidate_df["ExperimentID"] == experiment_id].copy()
        if candidate_df.empty:
            continue
        pred_df = candidate_df
        export_path = candidate_path
        break
    if pred_df.empty:
        empty = pd.DataFrame(columns=["Ticker", "Date", f"{signal_prefix}_Pred"])
        _SIGNAL_OVERLAY_CACHE[cache_key] = empty
        return empty.copy()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    pred_df["Prediction"] = pd.to_numeric(pred_df["Prediction"], errors="coerce")
    pred_df = pred_df.dropna(subset=["Ticker", "Date", "Prediction"])
    pred_df = pred_df.sort_values(["Ticker", "Date"]).drop_duplicates(["Ticker", "Date"], keep="last")
    pred_col = f"{signal_prefix}_Pred"
    edge_col = f"{signal_prefix}_Edge"
    high_conf_col = f"{signal_prefix}_HighConf"
    pred_df = pred_df.rename(columns={"Prediction": pred_col})
    pred_df[edge_col] = (pred_df[pred_col] - 0.5).clip(-0.5, 0.5)
    pred_df[high_conf_col] = (pred_df[pred_col] >= 0.60).astype(float)
    keep_cols = ["Ticker", "Date", pred_col, edge_col, high_conf_col]
    pred_df = pred_df[keep_cols].reset_index(drop=True)
    _SIGNAL_OVERLAY_CACHE[cache_key] = pred_df
    main_logger.info(f"[SIGNAL OVERLAY] loaded {len(pred_df)} rows for {experiment_id} from {export_path}")
    return pred_df.copy()


def merge_signal_overlay_features(df: pd.DataFrame, ticker: Optional[str]) -> pd.DataFrame:
    out = df.copy()

    overlay_defaults = [
        ("Signal_E102_Pred", 0.5),
        ("Signal_E102_Edge", 0.0),
        ("Signal_E102_HighConf", 0.0),
        ("Signal_E302_Pred", 0.5),
        ("Signal_E302_Edge", 0.0),
        ("Signal_E302_HighConf", 0.0),
        ("Signal_E401_Pred", 0.5),
        ("Signal_E401_Edge", 0.0),
        ("Signal_E401_HighConf", 0.0),
        ("Signal_E407_Pred", 0.5),
        ("Signal_E407_Edge", 0.0),
        ("Signal_E407_HighConf", 0.0),
        ("Signal_E209_Pred", 0.5),
        ("Signal_E209_Edge", 0.0),
        ("Signal_E209_HighConf", 0.0),
        ("Signal_E211_Pred", 0.5),
        ("Signal_E211_Edge", 0.0),
        ("Signal_E211_HighConf", 0.0),
        ("Signal_E501_Pred", 0.5),
        ("Signal_E501_Edge", 0.0),
        ("Signal_E501_HighConf", 0.0),
        ("Signal_E502_Pred", 0.5),
        ("Signal_E502_Edge", 0.0),
        ("Signal_E502_HighConf", 0.0),
        ("Signal_E503_Pred", 0.5),
        ("Signal_E503_Edge", 0.0),
        ("Signal_E503_HighConf", 0.0),
        ("Signal_E504_Pred", 0.5),
        ("Signal_E504_Edge", 0.0),
        ("Signal_E504_HighConf", 0.0),
        ("Signal_E505_Pred", 0.5),
        ("Signal_E505_Edge", 0.0),
        ("Signal_E505_HighConf", 0.0),
        ("Signal_E506_Pred", 0.5),
        ("Signal_E506_Edge", 0.0),
        ("Signal_E506_HighConf", 0.0),
        ("Signal_E507_Pred", 0.5),
        ("Signal_E507_Edge", 0.0),
        ("Signal_E507_HighConf", 0.0),
        ("Signal_E508_Pred", 0.5),
        ("Signal_E508_Edge", 0.0),
        ("Signal_E508_HighConf", 0.0),
        ("Signal_E605_Pred", 0.5),
        ("Signal_E605_Edge", 0.0),
        ("Signal_E605_HighConf", 0.0),
        ("Signal_E606_Pred", 0.5),
        ("Signal_E606_Edge", 0.0),
        ("Signal_E606_HighConf", 0.0),
        ("Signal_E607_Pred", 0.5),
        ("Signal_E607_Edge", 0.0),
        ("Signal_E607_HighConf", 0.0),
        ("Signal_E610_Pred", 0.5),
        ("Signal_E610_Edge", 0.0),
        ("Signal_E610_HighConf", 0.0),
        ("Signal_E702_Pred", 0.5),
        ("Signal_E702_Edge", 0.0),
        ("Signal_E702_HighConf", 0.0),
        ("Signal_E703_Pred", 0.5),
        ("Signal_E703_Edge", 0.0),
        ("Signal_E703_HighConf", 0.0),
        ("Signal_E705_Pred", 0.5),
        ("Signal_E705_Edge", 0.0),
        ("Signal_E705_HighConf", 0.0),
        ("Signal_E706_Pred", 0.5),
        ("Signal_E706_Edge", 0.0),
        ("Signal_E706_HighConf", 0.0),
        ("Signal_E801_Pred", 0.5),
        ("Signal_E801_Edge", 0.0),
        ("Signal_E801_HighConf", 0.0),
        ("Signal_E803_Pred", 0.5),
        ("Signal_E803_Edge", 0.0),
        ("Signal_E803_HighConf", 0.0),
        ("Signal_E804_Pred", 0.5),
        ("Signal_E804_Edge", 0.0),
        ("Signal_E804_HighConf", 0.0),
        ("Signal_E806_Pred", 0.5),
        ("Signal_E806_Edge", 0.0),
        ("Signal_E806_HighConf", 0.0),
        ("Signal_E903_Pred", 0.5),
        ("Signal_E903_Edge", 0.0),
        ("Signal_E903_HighConf", 0.0),
        ("Signal_E904_Pred", 0.5),
        ("Signal_E904_Edge", 0.0),
        ("Signal_E904_HighConf", 0.0),
        ("Signal_E905_Pred", 0.5),
        ("Signal_E905_Edge", 0.0),
        ("Signal_E905_HighConf", 0.0),
        ("Signal_E906_Pred", 0.5),
        ("Signal_E906_Edge", 0.0),
        ("Signal_E906_HighConf", 0.0),
        ("Signal_E1101_Pred", 0.5),
        ("Signal_E1101_Edge", 0.0),
        ("Signal_E1101_HighConf", 0.0),
        ("Signal_E1102_Pred", 0.5),
        ("Signal_E1102_Edge", 0.0),
        ("Signal_E1102_HighConf", 0.0),
        ("Signal_E1103_Pred", 0.5),
        ("Signal_E1103_Edge", 0.0),
        ("Signal_E1103_HighConf", 0.0),
        ("Signal_E1104_Pred", 0.5),
        ("Signal_E1104_Edge", 0.0),
        ("Signal_E1104_HighConf", 0.0),
        ("Signal_E1105_Pred", 0.5),
        ("Signal_E1105_Edge", 0.0),
        ("Signal_E1105_HighConf", 0.0),
        ("Signal_E1106_Pred", 0.5),
        ("Signal_E1106_Edge", 0.0),
        ("Signal_E1106_HighConf", 0.0),
        ("Signal_E1201_Pred", 0.5),
        ("Signal_E1201_Edge", 0.0),
        ("Signal_E1201_HighConf", 0.0),
        ("Signal_E1202_Pred", 0.5),
        ("Signal_E1202_Edge", 0.0),
        ("Signal_E1202_HighConf", 0.0),
        ("Signal_E1203_Pred", 0.5),
        ("Signal_E1203_Edge", 0.0),
        ("Signal_E1203_HighConf", 0.0),
        ("Signal_E1204_Pred", 0.5),
        ("Signal_E1204_Edge", 0.0),
        ("Signal_E1204_HighConf", 0.0),
        ("Signal_E1301_Pred", 0.5),
        ("Signal_E1301_Edge", 0.0),
        ("Signal_E1301_HighConf", 0.0),
        ("Signal_E1302_Pred", 0.5),
        ("Signal_E1302_Edge", 0.0),
        ("Signal_E1302_HighConf", 0.0),
        ("Signal_E1303_Pred", 0.5),
        ("Signal_E1303_Edge", 0.0),
        ("Signal_E1303_HighConf", 0.0),
        ("Signal_E1304_Pred", 0.5),
        ("Signal_E1304_Edge", 0.0),
        ("Signal_E1304_HighConf", 0.0),
        ("Signal_E1401_Pred", 0.5),
        ("Signal_E1401_Edge", 0.0),
        ("Signal_E1401_HighConf", 0.0),
        ("Signal_E1402_Pred", 0.5),
        ("Signal_E1402_Edge", 0.0),
        ("Signal_E1402_HighConf", 0.0),
        ("Signal_E1403_Pred", 0.5),
        ("Signal_E1403_Edge", 0.0),
        ("Signal_E1403_HighConf", 0.0),
        ("Signal_E1404_Pred", 0.5),
        ("Signal_E1404_Edge", 0.0),
        ("Signal_E1404_HighConf", 0.0),
        ("Signal_E1501_Pred", 0.5),
        ("Signal_E1501_Edge", 0.0),
        ("Signal_E1501_HighConf", 0.0),
        ("Signal_E1502_Pred", 0.5),
        ("Signal_E1502_Edge", 0.0),
        ("Signal_E1502_HighConf", 0.0),
        ("Signal_E1503_Pred", 0.5),
        ("Signal_E1503_Edge", 0.0),
        ("Signal_E1503_HighConf", 0.0),
        ("Signal_E1504_Pred", 0.5),
        ("Signal_E1504_Edge", 0.0),
        ("Signal_E1504_HighConf", 0.0),
        ("Signal_E1601_Pred", 0.5),
        ("Signal_E1601_Edge", 0.0),
        ("Signal_E1601_HighConf", 0.0),
        ("Signal_E1602_Pred", 0.5),
        ("Signal_E1602_Edge", 0.0),
        ("Signal_E1602_HighConf", 0.0),
        ("Signal_E1603_Pred", 0.5),
        ("Signal_E1603_Edge", 0.0),
        ("Signal_E1603_HighConf", 0.0),
        ("Signal_E1604_Pred", 0.5),
        ("Signal_E1604_Edge", 0.0),
        ("Signal_E1604_HighConf", 0.0),
        ("Signal_E1701_Pred", 0.5),
        ("Signal_E1701_Edge", 0.0),
        ("Signal_E1701_HighConf", 0.0),
        ("Signal_E1702_Pred", 0.5),
        ("Signal_E1702_Edge", 0.0),
        ("Signal_E1702_HighConf", 0.0),
        ("Signal_E1703_Pred", 0.5),
        ("Signal_E1703_Edge", 0.0),
        ("Signal_E1703_HighConf", 0.0),
        ("Signal_E1704_Pred", 0.5),
        ("Signal_E1704_Edge", 0.0),
        ("Signal_E1704_HighConf", 0.0),
        ("Signal_E2701_Pred", 0.5),
        ("Signal_E2701_Edge", 0.0),
        ("Signal_E2701_HighConf", 0.0),
        ("Signal_E2702_Pred", 0.5),
        ("Signal_E2702_Edge", 0.0),
        ("Signal_E2702_HighConf", 0.0),
        ("Signal_E2703_Pred", 0.5),
        ("Signal_E2703_Edge", 0.0),
        ("Signal_E2703_HighConf", 0.0),
        ("Signal_E2704_Pred", 0.5),
        ("Signal_E2704_Edge", 0.0),
        ("Signal_E2704_HighConf", 0.0),
        ("Signal_E1801_Pred", 0.5),
        ("Signal_E1801_Edge", 0.0),
        ("Signal_E1801_HighConf", 0.0),
        ("Signal_E1802_Pred", 0.5),
        ("Signal_E1802_Edge", 0.0),
        ("Signal_E1802_HighConf", 0.0),
        ("Signal_E1803_Pred", 0.5),
        ("Signal_E1803_Edge", 0.0),
        ("Signal_E1803_HighConf", 0.0),
        ("Signal_E1804_Pred", 0.5),
        ("Signal_E1804_Edge", 0.0),
        ("Signal_E1804_HighConf", 0.0),
        ("Signal_E1901_Pred", 0.5),
        ("Signal_E1901_Edge", 0.0),
        ("Signal_E1901_HighConf", 0.0),
        ("Signal_E1902_Pred", 0.5),
        ("Signal_E1902_Edge", 0.0),
        ("Signal_E1902_HighConf", 0.0),
        ("Signal_E1903_Pred", 0.5),
        ("Signal_E1903_Edge", 0.0),
        ("Signal_E1903_HighConf", 0.0),
        ("Signal_E1904_Pred", 0.5),
        ("Signal_E1904_Edge", 0.0),
        ("Signal_E1904_HighConf", 0.0),
        ("Signal_E2001_Pred", 0.5),
        ("Signal_E2001_Edge", 0.0),
        ("Signal_E2001_HighConf", 0.0),
        ("Signal_E2002_Pred", 0.5),
        ("Signal_E2002_Edge", 0.0),
        ("Signal_E2002_HighConf", 0.0),
        ("Signal_E2003_Pred", 0.5),
        ("Signal_E2003_Edge", 0.0),
        ("Signal_E2003_HighConf", 0.0),
        ("Signal_E2004_Pred", 0.5),
        ("Signal_E2004_Edge", 0.0),
        ("Signal_E2004_HighConf", 0.0),
        ("Signal_E2101_Pred", 0.5),
        ("Signal_E2101_Edge", 0.0),
        ("Signal_E2101_HighConf", 0.0),
        ("Signal_E2102_Pred", 0.5),
        ("Signal_E2102_Edge", 0.0),
        ("Signal_E2102_HighConf", 0.0),
        ("Signal_E2103_Pred", 0.5),
        ("Signal_E2103_Edge", 0.0),
        ("Signal_E2103_HighConf", 0.0),
        ("Signal_E2104_Pred", 0.5),
        ("Signal_E2104_Edge", 0.0),
        ("Signal_E2104_HighConf", 0.0),
        ("Signal_E2201_Pred", 0.5),
        ("Signal_E2201_Edge", 0.0),
        ("Signal_E2201_HighConf", 0.0),
        ("Signal_E2202_Pred", 0.5),
        ("Signal_E2202_Edge", 0.0),
        ("Signal_E2202_HighConf", 0.0),
        ("Signal_E2203_Pred", 0.5),
        ("Signal_E2203_Edge", 0.0),
        ("Signal_E2203_HighConf", 0.0),
        ("Signal_E2204_Pred", 0.5),
        ("Signal_E2204_Edge", 0.0),
        ("Signal_E2204_HighConf", 0.0),
        ("Signal_E2301_Pred", 0.5),
        ("Signal_E2301_Edge", 0.0),
        ("Signal_E2301_HighConf", 0.0),
        ("Signal_E2302_Pred", 0.5),
        ("Signal_E2302_Edge", 0.0),
        ("Signal_E2302_HighConf", 0.0),
        ("Signal_E2303_Pred", 0.5),
        ("Signal_E2303_Edge", 0.0),
        ("Signal_E2303_HighConf", 0.0),
        ("Signal_E2304_Pred", 0.5),
        ("Signal_E2304_Edge", 0.0),
        ("Signal_E2304_HighConf", 0.0),
        ("Signal_E2501_Pred", 0.5),
        ("Signal_E2501_Edge", 0.0),
        ("Signal_E2501_HighConf", 0.0),
        ("Signal_E2502_Pred", 0.5),
        ("Signal_E2502_Edge", 0.0),
        ("Signal_E2502_HighConf", 0.0),
        ("Signal_E2503_Pred", 0.5),
        ("Signal_E2503_Edge", 0.0),
        ("Signal_E2503_HighConf", 0.0),
        ("Signal_E2504_Pred", 0.5),
        ("Signal_E2504_Edge", 0.0),
        ("Signal_E2504_HighConf", 0.0),
        ("Signal_E2601_Pred", 0.5),
        ("Signal_E2601_Edge", 0.0),
        ("Signal_E2601_HighConf", 0.0),
        ("Signal_E2602_Pred", 0.5),
        ("Signal_E2602_Edge", 0.0),
        ("Signal_E2602_HighConf", 0.0),
        ("Signal_E2603_Pred", 0.5),
        ("Signal_E2603_Edge", 0.0),
        ("Signal_E2603_HighConf", 0.0),
        ("Signal_E2604_Pred", 0.5),
        ("Signal_E2604_Edge", 0.0),
        ("Signal_E2604_HighConf", 0.0),
        ("Signal_E2801_Pred", 0.5),
        ("Signal_E2801_Edge", 0.0),
        ("Signal_E2801_HighConf", 0.0),
        ("Signal_E2802_Pred", 0.5),
        ("Signal_E2802_Edge", 0.0),
        ("Signal_E2802_HighConf", 0.0),
        ("Signal_E2803_Pred", 0.5),
        ("Signal_E2803_Edge", 0.0),
        ("Signal_E2803_HighConf", 0.0),
        ("Signal_E2804_Pred", 0.5),
        ("Signal_E2804_Edge", 0.0),
        ("Signal_E2804_HighConf", 0.0),
        ("Signal_E2805_Pred", 0.5),
        ("Signal_E2805_Edge", 0.0),
        ("Signal_E2805_HighConf", 0.0),
        ("Signal_E2806_Pred", 0.5),
        ("Signal_E2806_Edge", 0.0),
        ("Signal_E2806_HighConf", 0.0),
    ]
    default_map = dict(overlay_defaults)
    if not ticker or "Date" not in out.columns:
        defaults_df = pd.DataFrame({col: np.full(len(out), default) for col, default in overlay_defaults}, index=out.index)
        return pd.concat([out, defaults_df], axis=1)

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.sort_values("Date").reset_index(drop=True)

    overlay_frames = []
    for experiment_id in SIGNAL_OVERLAY_SOURCES.keys():
        pred_df = load_signal_overlay_predictions(experiment_id)
        signal_prefix = SIGNAL_OVERLAY_SOURCES[experiment_id][1]
        pred_col = f"{signal_prefix}_Pred"
        edge_col = f"{signal_prefix}_Edge"
        high_conf_col = f"{signal_prefix}_HighConf"
        if pred_df.empty:
            continue

        ticker_preds = pred_df.loc[pred_df["Ticker"] == ticker].copy()
        if ticker_preds.empty:
            continue

        ticker_preds["Date"] = pd.to_datetime(ticker_preds["Date"], errors="coerce")
        ticker_preds = ticker_preds[["Date", pred_col, edge_col, high_conf_col]].copy()
        ticker_preds = ticker_preds.sort_values("Date").drop_duplicates(["Date"], keep="last").reset_index(drop=True)
        overlay_frames.append(ticker_preds)

    if overlay_frames:
        overlay_merged = overlay_frames[0]
        for frame in overlay_frames[1:]:
            overlay_merged = overlay_merged.merge(frame, on="Date", how="outer")
        out = out.merge(overlay_merged, on="Date", how="left")

    missing_defaults = {
        col: np.full(len(out), default)
        for col, default in overlay_defaults
        if col not in out.columns
    }
    if missing_defaults:
        out = pd.concat([out, pd.DataFrame(missing_defaults, index=out.index)], axis=1)
    for col, default in overlay_defaults:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(default)
    out = out.copy()
    return out

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

# We define the feature list but do not scale it in this revised code.
# ===== core intraday feature grid =====
FEATURES_TO_SCALE = [
    "LagRet_1", "LagRet_5", "LagRet_20",
    "Trend_30", "Trend_2h", "Trend_slope",
    "RSI14", "MACD_z",
    "ATR20_log", "RealVol20_log",
    "MktRet_1", "MktRet_3", "MktRet_6",
    "StockMinusMkt_1", "StockMinusMkt_3",
    "SectorMinusMkt_3",
    "VWAP_Dist", "SessionOpenDist_ATR",
    "OpeningRangeBreakout", "TimeSinceNewHigh", "TimeSinceNewLow",
    "IntradayVolPercentile", "RelativeVolumeTime",
    "BodyToRange", "UpperWickRatio", "LowerWickRatio",
    "Breakout_3bar", "SignPersistence_5",
    "RetSkew_5", "CloseLocation_3",
    "MktVolRank",
    "VolRegime", "MinuteNorm",
    "RegimeBull", "RegimeBear",
    "Signal_E102_Pred", "Signal_E102_Edge", "Signal_E102_HighConf",
    "Signal_E302_Pred", "Signal_E302_Edge", "Signal_E302_HighConf",
    "XS_Rank_StockMinusMkt_1", "XS_Rank_StockMinusMkt_3", "XS_Rank_StockMinusMkt_6",
    "XS_Rank_SectorMinusMkt_3", "XS_Rank_RelativeVolumeTime",
    "XS_Rank_VolAdjStockMinusMkt_1", "XS_Rank_VolAdjStockMinusMkt_3",
    "XS_LeaderSpread_3", "XS_LeaderTop20", "XS_LaggardBottom20",
    "XS_LeaderPersist_3", "XS_LaggardPersist_3", "XS_LeaderPersist_6",
    "XS_LaggardPersist_6", "XS_Rank_Change_3", "XS_VolumeLeaderSpread",
    "SectorResidual_3", "VolAdjSectorResidual_3", "XS_Rank_SectorResidual_3",
    "XS_CommonalityResidual_3", "XS_IdiosyncraticLeader_3", "XS_IdiosyncraticLaggard_3",
    "ResidualLeaderPersist_3", "ResidualLaggardPersist_3",
]


LOG_TRANSFORM_FEATURES = ["Close", "Volume"]  # Only apply log transform to columns guaranteed to be > 0

import requests
import pyotp
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


API_KEY = get_required_env("API_KEY")
API_SECRET = get_required_env("API_SECRET")
USERNAME = get_required_env("USERNAME")
PASSWORD = get_required_env("PASSWORD")
TOTP_KEY = get_required_env("TOTP_KEY")

kite = KiteConnect(api_key=API_KEY)
_AUTHENTICATED_KITE: Optional[KiteConnect] = None


def get_authenticated_kite() -> KiteConnect:
    global _AUTHENTICATED_KITE
    if _AUTHENTICATED_KITE is None:
        _AUTHENTICATED_KITE = get_valid_kite_session()
    return _AUTHENTICATED_KITE


def build_local_instrument_df() -> pd.DataFrame:
    rows = []
    seen_symbols = set()
    for csv_path in sorted(RESULTS_DIR.glob("data_fetched_*.csv")):
        symbol = csv_path.stem.replace("data_fetched_", "", 1)
        if symbol.endswith("_15m"):
            symbol = symbol[:-4]
        symbol = symbol.strip()
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        rows.append(
            {
                "tradingsymbol": symbol,
                "instrument_token": 10_000_000 + len(rows) + 1,
                "exchange": "NSE",
            }
        )
    return pd.DataFrame(rows, columns=["tradingsymbol", "instrument_token", "exchange"])


def load_instrument_df() -> pd.DataFrame:
    required_symbols = set(NSE_LIQUID_UNIVERSE)
    required_symbols.add(MARKET_PROXY_SYMBOL)
    required_symbols.update(SECTOR_PROXY_MAP.values())
    local_df = build_local_instrument_df()
    local_symbols = set(local_df["tradingsymbol"].astype(str)) if not local_df.empty else set()
    if required_symbols.issubset(local_symbols):
        main_logger.info(
            "[DATA] Using cached local instrument map with %s symbols; Kite instrument dump skipped.",
            len(local_symbols),
        )
        return local_df
    try:
        instrument_dump = kite_call_with_retry(get_authenticated_kite().instruments, "NSE")
        return pd.DataFrame(instrument_dump)
    except Exception as exc:
        if not local_df.empty:
            missing_symbols = sorted(required_symbols - local_symbols)
            main_logger.warning(
                "[DATA] Kite instrument dump unavailable; falling back to cached local instrument map. Missing local symbols: %s. Error: %s",
                ", ".join(missing_symbols) if missing_symbols else "none",
                exc,
            )
            return local_df
        raise


def extract_request_token_from_input(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        raise RuntimeError("Empty manual login input; expected a request_token or redirected URL.")
    if "request_token=" in value:
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        request_tokens = qs.get("request_token", [])
        if request_tokens and request_tokens[0].strip():
            return request_tokens[0].strip()
        raise RuntimeError("Could not extract request_token from the pasted redirected URL.")
    return value


def prompt_manual_request_token(login_url: str) -> str:
    print("\n[Manual Login Required] Zerodha requested CAPTCHA / manual login.")
    print("Open this URL in a browser, complete login, and paste either the full redirected URL")
    print("or just the request_token shown in that URL.\n")
    print(login_url)
    raw_value = input("\nPaste redirected URL or request_token: ").strip()
    return extract_request_token_from_input(raw_value)

def get_access_token():
    session = requests.Session()
    login_url = f"https://kite.trade/connect/login?api_key={API_KEY}"

    # 1. Basic login
    login_resp = session.post(
        "https://kite.zerodha.com/api/login",
        data={"user_id": USERNAME, "password": PASSWORD},
    )
    try:
        login_payload = login_resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"Login endpoint returned non-JSON response. status={login_resp.status_code}"
        ) from exc

    login_data = login_payload.get("data") if isinstance(login_payload, dict) else None
    request_id = login_data.get("request_id") if isinstance(login_data, dict) else None
    if not request_id:
        requires_manual = False
        if isinstance(login_payload, dict):
            message_text = str(login_payload.get("message", "")).lower()
            payload_data = login_payload.get("data", {})
            captcha_required = isinstance(payload_data, dict) and bool(payload_data.get("captcha"))
            requires_manual = captcha_required or ("captcha" in message_text)
        if requires_manual:
            manual_request_token = prompt_manual_request_token(login_url)
            data = kite_call_with_retry(kite.generate_session, manual_request_token, api_secret=API_SECRET)
            return data["access_token"]
        raise RuntimeError(
            "Login failed before request_id was issued. "
            f"status={login_resp.status_code}, payload={login_payload}"
        )

    # 2. TOTP 2FA
    twofa_resp = session.post(
        "https://kite.zerodha.com/api/twofa",
        data={
            "user_id": USERNAME,
            "request_id": request_id,
            "twofa_value": pyotp.TOTP(TOTP_KEY).now(),
        },
    )
    try:
        twofa_payload = twofa_resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"Two-factor endpoint returned non-JSON response. status={twofa_resp.status_code}"
        ) from exc
    if twofa_resp.status_code >= 400:
        raise RuntimeError(
            f"Two-factor step failed. status={twofa_resp.status_code}, payload={twofa_payload}"
        )

    # 3. Follow redirects until we find ?request_token=...
    next_url = login_url
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
""" # 1) Log in to Zerodha to get access token
tokken = get_access_token()
kite.set_access_token(tokken)
main_logger.info("Logged in. Kite profile:", kite.profile()) """

# Get dump of all NSE instruments using Kite when needed, otherwise reuse local cached symbols.
instrument_df = load_instrument_df()

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


def get_zerodha_nse_tradingsymbols(instrument_df: pd.DataFrame) -> list[str]:
    if instrument_df.empty or "tradingsymbol" not in instrument_df.columns:
        return []
    df = instrument_df.copy()
    if "exchange" in df.columns:
        df = df[df["exchange"].astype(str).str.upper() == "NSE"]
    if "segment" in df.columns:
        allowed_segments = {"NSE", "NSE-EQ"}
        df = df[df["segment"].astype(str).str.upper().isin(allowed_segments) | df["segment"].isna()]
    symbols = (
        df["tradingsymbol"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    symbols = symbols[symbols != ""]
    return sorted(symbols.unique().tolist())


def extract_latest_walk_forward_test_rows(log_path: Path) -> pd.DataFrame:
    if not log_path.exists():
        return pd.DataFrame()
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if "Resolved execution mode: walk_forward" in line:
            start_idx = idx
    if start_idx is None:
        return pd.DataFrame()

    pattern = re.compile(
        r"\[WF:(.*?):cycle_(\d+)_test\] score=([-0-9.]+), return=([-0-9.]+), dd=([-0-9.]+), "
        r"sharpe=([-0-9.]+), turnover=([-0-9.]+), trades=([0-9]+)"
    )
    rows = []
    for line in lines[start_idx:]:
        match = pattern.search(line)
        if not match:
            continue
        rows.append(
            {
                "ticker": match.group(1),
                "cycle": int(match.group(2)),
                "test_score": float(match.group(3)),
                "test_return": float(match.group(4)),
                "test_drawdown": float(match.group(5)),
                "test_sharpe": float(match.group(6)),
                "test_turnover": float(match.group(7)),
                "test_trades": int(match.group(8)),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def get_latest_archived_main_log() -> Optional[Path]:
    if not LOG_ARCHIVE_DIR.exists():
        return None
    candidates = sorted(LOG_ARCHIVE_DIR.rglob("main.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_focus_source_rows(log_path: Path) -> pd.DataFrame:
    summary_path = RESULTS_DIR / "walk_forward" / "walk_forward_summary.csv"
    if summary_path.exists():
        try:
            wf_df = pd.read_csv(summary_path)
            needed = {"ticker", "test_return", "test_turnover", "test_trades"}
            if not wf_df.empty and needed.issubset(wf_df.columns):
                return wf_df.copy()
        except Exception:
            pass

    wf_df = extract_latest_walk_forward_test_rows(log_path)
    if not wf_df.empty:
        return wf_df

    archived = get_latest_archived_main_log()
    if archived is not None and archived != log_path:
        wf_df = extract_latest_walk_forward_test_rows(archived)
        if not wf_df.empty:
            return wf_df
    return pd.DataFrame()


def extract_latest_focus_tickers_from_log(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    pattern = re.compile(r"\[WF-FOCUS\] selected \d+ tickers .*: \[(.*)\]")
    for line in reversed(lines):
        match = pattern.search(line)
        if not match:
            continue
        payload = match.group(1).strip()
        if not payload:
            return []
        tickers = [item.strip().strip("'\"") for item in payload.split(",") if item.strip()]
        return [ticker for ticker in tickers if ticker]
    return []


def get_recent_archived_focus_tickers(zerodha_symbols: set[str], max_logs: int = 10) -> list[str]:
    archived = sorted(
        (RESULTS_DIR / "log_runs").glob("run_*/main.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for candidate in archived[:max_logs]:
        prior_tickers = [ticker for ticker in extract_latest_focus_tickers_from_log(candidate) if ticker in zerodha_symbols]
        if prior_tickers:
            return prior_tickers
    return []


def get_baseline_backfill_tickers(
    zerodha_symbols: set[str],
    policy_name: str = "SIGNAL_E211_BANDED_68",
    max_count: int = 12,
) -> list[str]:
    summary_csv = RESULTS_DIR / "signal_baseline" / "baseline_walk_forward_summary.csv"
    if not summary_csv.exists():
        return []
    try:
        summary_df = pd.read_csv(summary_csv)
    except Exception:
        return []
    required_cols = {"ticker", "policy", "test_return", "test_turnover", "test_trades"}
    if not required_cols.issubset(summary_df.columns):
        return []
    scoped = summary_df.loc[summary_df["policy"].astype(str) == policy_name].copy()
    if scoped.empty:
        return []
    scoped["ticker"] = scoped["ticker"].astype(str)
    scoped = scoped[scoped["ticker"].isin(zerodha_symbols)].copy()
    if scoped.empty:
        return []
    for col in ["test_return", "test_turnover", "test_trades"]:
        scoped[col] = pd.to_numeric(scoped[col], errors="coerce")
    scoped["has_activity"] = (scoped["test_trades"] > 0).astype(int)
    scoped.sort_values(
        ["has_activity", "test_return", "test_turnover", "test_trades"],
        ascending=[False, False, True, True],
        inplace=True,
    )
    return scoped["ticker"].dropna().drop_duplicates().head(max_count).tolist()


def build_focus_universe_from_latest_walk_forward(
    instrument_df: pd.DataFrame,
    log_path: Path = RESULTS_DIR / "main.log",
    min_return: Optional[float] = None,
    max_turnover: Optional[float] = None,
    require_trades: Optional[bool] = None,
) -> list[str]:
    zerodha_symbols = set(get_zerodha_nse_tradingsymbols(instrument_df))
    if PINNED_FOCUS_UNIVERSE_FILE.exists():
        try:
            pinned_df = pd.read_csv(PINNED_FOCUS_UNIVERSE_FILE)
            if "ticker" in pinned_df.columns:
                pinned_df = pinned_df[pinned_df["ticker"].isin(zerodha_symbols)].copy()
                pinned_tickers = pinned_df["ticker"].dropna().astype(str).tolist()
                if pinned_tickers:
                    main_logger.info(
                        "[WF-FOCUS] using pinned incumbent focus universe from %s: %s",
                        PINNED_FOCUS_UNIVERSE_FILE,
                        pinned_tickers,
                    )
                    return pinned_tickers
        except Exception as exc:
            main_logger.warning("[WF-FOCUS] failed to read pinned focus universe: %s", exc)
    if min_return is None:
        min_return = -0.001
    if max_turnover is None:
        max_turnover = 0.25
    if require_trades is None:
        require_trades = True
    wf_df = load_focus_source_rows(log_path)
    if wf_df.empty:
        main_logger.warning("[WF-FOCUS] no walk-forward test rows found in latest log block.")
        return []

    focus_df = wf_df.copy()
    focus_df = focus_df[focus_df["test_return"] >= float(min_return)]
    focus_df = focus_df[focus_df["test_turnover"] <= float(max_turnover)]
    if require_trades:
        focus_df = focus_df[(focus_df["test_trades"] > 0) | (focus_df["test_return"] > 0)]

    focus_df = focus_df[focus_df["ticker"].isin(zerodha_symbols)].copy()
    if focus_df.empty and FOCUS_UNIVERSE_FILE.exists():
        try:
            prior_df = pd.read_csv(FOCUS_UNIVERSE_FILE)
            if "ticker" in prior_df.columns:
                prior_df = prior_df[prior_df["ticker"].isin(zerodha_symbols)].copy()
                prior_tickers = prior_df["ticker"].dropna().astype(str).tolist()
                if prior_tickers:
                    main_logger.warning(
                        "[WF-FOCUS] latest walk-forward block produced no eligible tickers; reusing prior focus universe from %s",
                        FOCUS_UNIVERSE_FILE,
                    )
                    return prior_tickers
        except Exception as exc:
            main_logger.warning("[WF-FOCUS] failed to reuse prior focus universe: %s", exc)
    if focus_df.empty:
        candidate_logs = [log_path]
        archived = sorted(
            (RESULTS_DIR / "log_runs").glob("run_*/main.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        candidate_logs.extend(archived[:10])
        for candidate in candidate_logs:
            prior_tickers = [ticker for ticker in extract_latest_focus_tickers_from_log(candidate) if ticker in zerodha_symbols]
            if prior_tickers:
                main_logger.warning(
                    "[WF-FOCUS] latest walk-forward block produced no eligible tickers; reusing archived focus universe from %s",
                    candidate,
                )
                return prior_tickers
    focus_df.sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True], inplace=True)
    tickers = focus_df["ticker"].dropna().astype(str).tolist()
    if 0 < len(tickers) < FOCUS_TARGET_MIN_TICKERS:
        archived_focus = get_recent_archived_focus_tickers(zerodha_symbols)
        baseline_backfill = get_baseline_backfill_tickers(zerodha_symbols)
        backfill_candidates = archived_focus + [ticker for ticker in baseline_backfill if ticker not in archived_focus]
        for ticker in backfill_candidates:
            if ticker in tickers:
                continue
            tickers.append(ticker)
            if len(tickers) >= FOCUS_TARGET_MIN_TICKERS:
                break
        if "selection_source" not in focus_df.columns:
            focus_df["selection_source"] = "latest_walk_forward"
        existing_tickers = set(focus_df["ticker"].dropna().astype(str).tolist())
        for ticker in tickers:
            if ticker in existing_tickers:
                continue
            fill_row = {col: np.nan for col in focus_df.columns}
            fill_row["ticker"] = ticker
            fill_row["selection_source"] = (
                "archived_focus_backfill" if ticker in archived_focus else "baseline_e211_backfill"
            )
            focus_df = pd.concat([focus_df, pd.DataFrame([fill_row])], ignore_index=True)
    tickers = tickers[:FOCUS_TARGET_MAX_TICKERS]
    focus_df = focus_df[focus_df["ticker"].astype(str).isin(tickers)].copy()
    focus_df.to_csv(FOCUS_UNIVERSE_FILE, index=False)
    main_logger.info(
        "[WF-FOCUS] selected %s tickers from latest walk-forward block using Zerodha NSE symbols: %s",
        len(tickers),
        tickers,
    )
    return tickers


def load_context_frames_for_token(instrument_token: int, days: int, interval: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    cache_key = ("context", instrument_token, days, interval)
    cached = _DATA_KITE_CACHE.get(cache_key)
    if cached is not None:
        benchmark_df, sector_df = cached
        return (
            benchmark_df.copy() if benchmark_df is not None else None,
            sector_df.copy() if sector_df is not None else None,
        )

    ticker = get_ticker_from_token(instrument_token, instrument_df)
    if ticker is None:
        return None, None

    benchmark_df = None
    benchmark_token = get_instrument_token(MARKET_PROXY_SYMBOL, instrument_df)
    if benchmark_token is not None and benchmark_token != instrument_token:
        try:
            benchmark_df = get_data_kite(
                kite,
                instrument_token=benchmark_token,
                days=days,
                interval=interval,
                include_relative_context=False,
            )
        except Exception as e:
            main_logger.warning(f"Failed to load benchmark context for {ticker}: {e}")

    sector_df = None
    sector_symbol = SECTOR_PROXY_MAP.get(ticker)
    if sector_symbol:
        sector_token = get_instrument_token(sector_symbol, instrument_df)
        if sector_token is not None and sector_token != instrument_token:
            try:
                sector_df = get_data_kite(
                    kite,
                    instrument_token=sector_token,
                    days=days,
                    interval=interval,
                    include_relative_context=False,
                )
            except Exception as e:
                main_logger.warning(f"Failed to load sector context for {ticker}: {e}")

    _DATA_KITE_CACHE[cache_key] = (
        benchmark_df.copy() if benchmark_df is not None else None,
        sector_df.copy() if sector_df is not None else None,
    )
    return benchmark_df, sector_df

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
def _contextualize_with_market(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    sector_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    out = df.copy()
    if "Date" not in out.columns:
        return out

    def _prepare_context(src: Optional[pd.DataFrame], prefix: str) -> Optional[pd.DataFrame]:
        if src is None or src.empty or "Date" not in src.columns or "Close" not in src.columns:
            return None
        ctx = src[["Date", "Close"]].copy()
        ctx["Date"] = pd.to_datetime(ctx["Date"], errors="coerce")
        ctx = ctx.sort_values("Date").reset_index(drop=True)
        close = pd.to_numeric(ctx["Close"], errors="coerce").ffill().bfill()
        ctx[f"{prefix}Ret_1"] = close.pct_change(1).fillna(0.0)
        ctx[f"{prefix}Ret_3"] = close.pct_change(3).fillna(0.0)
        ctx[f"{prefix}Ret_6"] = close.pct_change(6).fillna(0.0)
        ctx[f"{prefix}VolRank"] = ctx[f"{prefix}Ret_1"].rolling(20).std().rolling(60).rank(pct=True).fillna(0.5)
        return ctx.drop(columns=["Close"])

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.sort_values("Date").reset_index(drop=True)

    bench = _prepare_context(benchmark_df, "Mkt")
    if bench is not None:
        out = pd.merge_asof(out, bench, on="Date", direction="backward")
    for col in ["MktRet_1", "MktRet_3", "MktRet_6", "MktVolRank"]:
        if col not in out.columns:
            out[col] = 0.0 if col != "MktVolRank" else 0.5

    sector = _prepare_context(sector_df, "Sector")
    if sector is not None:
        out = pd.merge_asof(out, sector[["Date", "SectorRet_3"]], on="Date", direction="backward")
    if "SectorRet_3" not in out.columns:
        out["SectorRet_3"] = out["MktRet_3"]

    out["StockMinusMkt_1"] = out.get("LagRet_1", 0.0) - out["MktRet_1"]
    out["StockMinusMkt_3"] = out["Close"].pct_change(3).fillna(0.0) - out["MktRet_3"]
    out["SectorMinusMkt_3"] = out["SectorRet_3"] - out["MktRet_3"]
    return out


def build_rl_features(
    df: pd.DataFrame,
    interval: str = "1minute",
    benchmark_df: Optional[pd.DataFrame] = None,
    sector_df: Optional[pd.DataFrame] = None,
    ticker: Optional[str] = None,
) -> pd.DataFrame:
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
    if "Date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Date"]):
        session_key = pd.Series(df["Date"].dt.date, index=df.index)
        mins = df["Date"].dt.hour * 60 + df["Date"].dt.minute
    else:
        session_key = pd.Series(np.arange(len(df)), index=df.index)
        mins = pd.Series(np.zeros(len(df)), index=df.index, dtype=float)

    def _bars_since_extreme(series: pd.Series, fn: str) -> pd.Series:
        out = pd.Series(index=series.index, dtype=float)
        for _, idx in series.groupby(session_key).groups.items():
            s = series.loc[idx]
            extreme = s.cummax() if fn == "max" else s.cummin()
            hit = s.eq(extreme)
            counter = []
            bars_since = 0
            for is_hit in hit.tolist():
                if is_hit:
                    bars_since = 0
                else:
                    bars_since += 1
                counter.append(bars_since)
            out.loc[idx] = counter
        return out.fillna(0.0)

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
    df["VWAP_Dist"] = ((close - volume.VolumeWeightedAveragePrice(high, low, close, vol, window=win_20).volume_weighted_average_price()) / (atr20 + eps)).fillna(0.0)
    session_open = open_.groupby(session_key).transform("first")
    df["SessionOpenDist_ATR"] = ((close - session_open) / (atr20 + eps)).fillna(0.0)
    session_open_map = open_.groupby(session_key).first()
    session_close_map = close.groupby(session_key).last()
    session_high_map = high.groupby(session_key).max()
    session_low_map = low.groupby(session_key).min()
    session_volume_map = vol.groupby(session_key).sum()
    prev_session_open_map = session_open_map.shift(1)
    prev_session_close_map = session_close_map.shift(1)
    prev_session_high_map = session_high_map.shift(1)
    prev_session_low_map = session_low_map.shift(1)
    prev_session_volume_map = session_volume_map.shift(1)
    prev_session_volume_rel_map = (
        prev_session_volume_map / session_volume_map.shift(1).rolling(20, min_periods=3).mean()
    ).replace([np.inf, -np.inf], np.nan)
    prev_session_open = session_key.map(prev_session_open_map)
    prev_session_close = session_key.map(prev_session_close_map)
    prev_session_high = session_key.map(prev_session_high_map)
    prev_session_low = session_key.map(prev_session_low_map)
    prev_session_volume_rel = session_key.map(prev_session_volume_rel_map)
    prev_session_range = (prev_session_high - prev_session_low).clip(lower=0.0)
    df["PrevSessionGap_ATR"] = ((session_open - prev_session_close) / (atr20 + eps)).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10.0, 10.0)
    df["PrevSessionRet"] = ((prev_session_close / (prev_session_open + eps)) - 1.0).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-0.5, 0.5)
    df["PrevSessionRange_ATR"] = (prev_session_range / (atr20 + eps)).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(0.0, 10.0)
    df["PrevSessionCloseLocation"] = ((prev_session_close - prev_session_low) / (prev_session_range + eps)).replace([np.inf, -np.inf], 0.5).fillna(0.5).clip(0.0, 1.0)
    df["PrevSessionBodyToRange"] = ((prev_session_close - prev_session_open) / (prev_session_range + eps)).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-1.0, 1.0)
    df["PrevSessionVolumeRel"] = (prev_session_volume_rel - 1.0).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-5.0, 5.0)
    opening_range_bars = max(2, 30 // max(bar_len, 1))
    opening_range_high = high.groupby(session_key).transform(lambda s: s.expanding().max()).groupby(session_key).shift(1)
    opening_range_low = low.groupby(session_key).transform(lambda s: s.expanding().min()).groupby(session_key).shift(1)
    opening_range_high = opening_range_high.groupby(session_key).transform(
        lambda s: s.fillna(method="ffill").fillna(method="bfill")
    )
    opening_range_low = opening_range_low.groupby(session_key).transform(
        lambda s: s.fillna(method="ffill").fillna(method="bfill")
    )
    bars_from_open = mins.groupby(session_key).cumcount()
    opening_range_high = pd.Series(
        np.where(
            bars_from_open >= opening_range_bars,
            high.groupby(session_key).transform(lambda s: s.iloc[:opening_range_bars].max()),
            np.nan,
        ),
        index=df.index,
    ).ffill()
    opening_range_low = pd.Series(
        np.where(
            bars_from_open >= opening_range_bars,
            low.groupby(session_key).transform(lambda s: s.iloc[:opening_range_bars].min()),
            np.nan,
        ),
        index=df.index,
    ).ffill()
    df["OpeningRangeBreakout"] = (
        (close > opening_range_high).astype(float) - (close < opening_range_low).astype(float)
    ).fillna(0.0)
    df["TimeSinceNewHigh"] = (_bars_since_extreme(high, "max") / max(win_2h, 1)).clip(0.0, 5.0)
    df["TimeSinceNewLow"] = (_bars_since_extreme(low, "min") / max(win_2h, 1)).clip(0.0, 5.0)
    df["IntradayVolPercentile"] = vol.groupby(session_key).transform(lambda s: s.expanding().rank(pct=True)).fillna(0.5)
    minute_slot = mins.astype(int)
    rel_vol_base = vol.groupby(minute_slot).transform(lambda s: s.shift(1).expanding().mean())
    df["RelativeVolumeTime"] = ((vol / (rel_vol_base + eps)) - 1.0).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-5.0, 5.0)
    candle_range = (high - low).clip(lower=eps)
    candle_body = close - open_
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    df["BodyToRange"] = (candle_body / candle_range).fillna(0.0).clip(-1.0, 1.0)
    df["UpperWickRatio"] = (upper_wick / candle_range).fillna(0.0).clip(0.0, 1.0)
    df["LowerWickRatio"] = (lower_wick / candle_range).fillna(0.0).clip(0.0, 1.0)
    df["Breakout_3bar"] = ((close > high.shift(1).rolling(3).max()).astype(float) - (close < low.shift(1).rolling(3).min()).astype(float)).fillna(0.0)
    df["SignPersistence_5"] = np.sign(df["LagRet_1"]).rolling(5).mean().fillna(0.0)
    df["RetSkew_5"] = df["LagRet_1"].rolling(5).skew().fillna(0.0)
    high3 = high.rolling(3).max()
    low3 = low.rolling(3).min()
    df["CloseLocation_3"] = ((close - low3) / (high3 - low3 + eps)).fillna(0.5)
    df["MinuteNorm"] = mins / 390.0
    df["MinutesOpen"] = mins
    df["LunchDummy"] = ((mins > 150) & (mins < 210)).astype(int)

    df["RegimeBull"] = (df["Trend_2h"] > 0).astype(float)
    df["RegimeBear"] = (df["Trend_2h"] < 0).astype(float)
    df["ADX_strong"] = (trend.ADXIndicator(high, low, close, window=win_30m).adx() >= 25).astype(float)
    df["ADX_weak"] = 1.0 - df["ADX_strong"]
    ret_3h = close.pct_change(3).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    ret_6h = close.pct_change(6).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    ret_12h = close.pct_change(12).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    vol_3 = close.pct_change().rolling(3).std()
    vol_20 = close.pct_change().rolling(20).std()
    range_mean_3 = candle_range.rolling(3).mean()
    range_mean_12 = candle_range.rolling(12).mean()
    df["MultiScaleRet_3h"] = ret_3h.clip(-0.2, 0.2)
    df["MultiScaleRet_6h"] = ret_6h.clip(-0.3, 0.3)
    df["MultiScaleRet_12h"] = ret_12h.clip(-0.4, 0.4)
    df["MultiScaleTrendGap"] = (df["Trend_30"] - df["Trend_2h"]).clip(-1.0, 1.0).fillna(0.0)
    df["MultiScaleMomentumAlignment"] = (df["Trend_30"] * df["Trend_2h"]).clip(-1.0, 1.0).fillna(0.0)
    df["MultiScaleVolRatio_3v20"] = (vol_3 / (vol_20 + eps)).replace([np.inf, -np.inf], 1.0).fillna(1.0).clip(0.0, 5.0)
    df["MultiScaleRangeCompression_3v12"] = (range_mean_3 / (range_mean_12 + eps)).replace([np.inf, -np.inf], 1.0).fillna(1.0).clip(0.0, 5.0)
    df["MultiScaleBodyPressure_3"] = df["BodyToRange"].rolling(3).mean().fillna(0.0).clip(-1.0, 1.0)
    ret_1 = close.pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    ret_4 = close.pct_change(4).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    abs_ret_sum_4 = ret_1.abs().rolling(4, min_periods=1).sum()
    sign_1 = np.sign(ret_1).fillna(0.0)
    sign_flip = ((sign_1 != sign_1.shift(1)) & (sign_1 != 0) & (sign_1.shift(1) != 0)).astype(float)
    first_two_ret = ret_1.shift(2).rolling(2, min_periods=2).sum()
    last_two_ret = ret_1.rolling(2, min_periods=2).sum()
    high_4 = high.rolling(4, min_periods=1).max()
    low_4 = low.rolling(4, min_periods=1).min()
    df["M15_Ret_4"] = ret_4.clip(-0.2, 0.2)
    df["M15_PathEfficiency_4"] = (ret_4 / (abs_ret_sum_4 + eps)).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-1.0, 1.0)
    df["M15_PositiveShare_4"] = (ret_1 > 0).astype(float).rolling(4, min_periods=1).mean().fillna(0.0)
    df["M15_SignFlipRate_4"] = sign_flip.rolling(4, min_periods=1).mean().fillna(0.0).clip(0.0, 1.0)
    df["M15_TimeImbalance_4"] = (
        (last_two_ret - first_two_ret) / ret_4.abs().replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-5.0, 5.0)
    df["M15_EarlyExhaustion_4"] = (first_two_ret - last_two_ret).fillna(0.0).clip(-0.2, 0.2)
    df["M15_RejectionScore_4"] = (
        ((high_4 - close) - (close - low_4)) / (high_4 - low_4 + eps)
    ).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-1.0, 1.0)
    df["M15_CloseLocation_4"] = ((close - low_4) / (high_4 - low_4 + eps)).fillna(0.5).clip(0.0, 1.0)
    df["M15_BreakoutPressure_4"] = df["Breakout_3bar"].rolling(4, min_periods=1).mean().fillna(0.0).clip(-1.0, 1.0)
    df["M15_BodyPressure_4"] = df["BodyToRange"].rolling(4, min_periods=1).mean().fillna(0.0).clip(-1.0, 1.0)
    df["M15_VolRatio_2v8"] = (
        ret_1.rolling(2, min_periods=2).std() / ret_1.rolling(8, min_periods=4).std().replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], 1.0).fillna(1.0).clip(0.0, 10.0)
    df = _contextualize_with_market(df, benchmark_df=benchmark_df, sector_df=sector_df)
    mkt_vol_rank = pd.to_numeric(df.get("MktVolRank", 0.5), errors="coerce").fillna(0.5)
    df["MarketStateBullCalm"] = ((df["RegimeBull"] > 0.5) & (mkt_vol_rank <= 0.60)).astype(float)
    df["MarketStateBullStress"] = ((df["RegimeBull"] > 0.5) & (mkt_vol_rank > 0.60)).astype(float)
    df["MarketStateBearCalm"] = ((df["RegimeBear"] > 0.5) & (mkt_vol_rank <= 0.60)).astype(float)
    df["MarketStateBearStress"] = ((df["RegimeBear"] > 0.5) & (mkt_vol_rank > 0.60)).astype(float)
    df["MarketStateTransition"] = ((df["ADX_weak"] > 0.5) | (df["Trend_30"].abs() <= 0.0015)).astype(float)
    df["MarketStateTrendScore"] = (df["Trend_30"] + 0.5 * df["Trend_2h"]).clip(-1.0, 1.0).fillna(0.0)
    df["MarketStateVolPressure"] = ((mkt_vol_rank - 0.5) * 2.0).clip(-1.0, 1.0)
    df["MultiScaleBreakoutPressure_3"] = df["Breakout_3bar"].rolling(3).mean().fillna(0.0).clip(-1.0, 1.0)

    df = merge_signal_overlay_features(df, ticker=ticker)

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
    tz_name: str    = "Asia/Kolkata",
    include_relative_context: bool = True,
) -> pd.DataFrame:
    """
    Download intraday OHLCV via Kite and build a compact, **always-complete**
    technical-feature dataframe ready for RL.
    """
    cache_key = ("data_kite", instrument_token, days, interval, include_relative_context)
    cached_df = _DATA_KITE_CACHE.get(cache_key)
    if isinstance(cached_df, pd.DataFrame):
        return cached_df.copy()

    # Determine ticker string from instrument token.
    tickerval = get_ticker_from_token(instrument_token, instrument_df)
    interval_key = str(interval).lower().strip()
    interval_safe = interval_key.replace("minute", "m").replace(" ", "")
    csv_path = (
        RESULTS_DIR / f"data_fetched_{tickerval}.csv"
        if interval_key == "60minute"
        else RESULTS_DIR / f"data_fetched_{tickerval}_{interval_safe}.csv"
    )
    
    # Check if cached data exists.
    if csv_path.exists():
        print(f"Loading cached data from: {csv_path}")
        df = pd.read_csv(csv_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
        benchmark_df = None
        sector_df = None
        if include_relative_context:
            benchmark_df, sector_df = load_context_frames_for_token(instrument_token, days=days, interval=interval)
        df = build_rl_features(
            df,
            interval=interval,
            benchmark_df=benchmark_df,
            sector_df=sector_df,
            ticker=tickerval,
        )
        _DATA_KITE_CACHE[cache_key] = df.copy()
        return df
    
    # ---------- 1) pull raw bars ------------------------------------------------
    max_days_per_call = 30 if "minute" in interval else 100
    tz  = pytz.timezone(tz_name)
    end = datetime.now(tz)
    beg = end - timedelta(days=days)

    kite_client = get_authenticated_kite()
    rows, cur = [], beg
    while cur < end:
        nxt = min(cur + timedelta(days=max_days_per_call), end)
        rows.extend(
            kite_client.historical_data(
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
    benchmark_df = None
    sector_df = None
    if include_relative_context:
        benchmark_df, sector_df = load_context_frames_for_token(instrument_token, days=days, interval=interval)
    df = build_rl_features(
        df,
        interval=interval,
        benchmark_df=benchmark_df,
        sector_df=sector_df,
        ticker=tickerval,
    )

    # Save the fetched and processed data to CSV for future caching.
    try:
        df.to_csv(csv_path, index=False)
        print(f"Data successfully saved to: {csv_path}")
    except Exception as e:
        print(f"[get_data_kite] Failed to write CSV: {e}")

    _DATA_KITE_CACHE[cache_key] = df.copy()
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
        disable_costs: bool = False,
        cost_profile: str = "cash_equity",
        max_holding_bars: Optional[int] = None,
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
        self.cost_profile = str(cost_profile or "cash_equity").strip().lower()
        self.max_holding_bars = int(max_holding_bars) if max_holding_bars is not None else None
        if self.max_holding_bars is not None and self.max_holding_bars <= 0:
            self.max_holding_bars = None
        self.dp_charge_applied = False
        self.last_dp_charge_amount = 0.0
        self.current_step = 0
        self.position_holding_bars = 0
        self.last_position_sign = 0

        if self.mode == "test":
            main_logger.info(f"[Env {self.env_rank}] In test mode: Inference Buy Threshold set to {self.inference_buy_threshold}, "
                         f"Inference Sell Threshold set to {self.inference_sell_threshold}")
        
        import collections
        self.reward_history = collections.deque(maxlen=500)

        self.action_space = spaces.Discrete(4)
        self.num_features = len(FEATURES_TO_SCALE)
        self.market_phase = ['Bull', 'Bear', 'Sideways']

        # Observation: engineered features plus account-state metrics.
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf,
                                    shape=(len(FEATURES_TO_SCALE) + 4,), dtype=np.float32)

        if reward_weights is not None:
            self.reward_weights = reward_weights
        else:
            self.reward_weights = {'reward_scale': 1.0}
        # Use a short, mode-aware warmup. Test/eval slices already carry precomputed features.
        self.warmup_steps = self._resolve_warmup_steps()
        
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
        self.avg_entry_price = 0.0
        self.position_style = "flat"
        self.position_holding_bars = 0
        self.last_position_sign = 0
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

        • engineered features (FEATURES_TO_SCALE)
        • 4 agent-state metrics  (balance/net-worth/position/drawdown)
        -----------------------------------------------------------
        total length = len(FEATURES_TO_SCALE) + 4
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
        tech_values   = [obs_dict[f] for f in FEATURES_TO_SCALE]
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
        self.current_step = 0
        self.history = []
        self.prev_net_worth = self.net_worth
        self.last_action = 0.0
        self.peak = self.net_worth
        self.returns_window = []
        self.avg_entry_price = 0.0
        self.position_style = "flat"
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
        self.warmup_steps = self._resolve_warmup_steps()
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
        using the configured cost profile.
        
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
                'Cost_Profile': self.cost_profile,
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

        profile = self.cost_profile
        if profile == "stock_futures":
            brokerage_fee = min(20, 0.0003 * order_value)
            stt = 0.0005 * order_value if side.lower() == 'sell' else 0.0
            transaction_charge = 0.0000183 * order_value
            sebi_fee = 1e-6 * order_value
            gst = 0.18 * (brokerage_fee + transaction_charge + sebi_fee)
            stamp_duty = 0.00002 * order_value if side.lower() == 'buy' else 0.0
        else:
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
            'Cost_Profile': profile,
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

    def _recompute_net_worth(self, current_price: float) -> float:
        self.net_worth = float(self.balance + self.position * current_price)
        self.peak = max(self.peak, self.net_worth)
        return self.net_worth

    def _position_return(self, current_price: float) -> float:
        if self.position == 0 or self.avg_entry_price <= 0:
            return 0.0
        if self.position > 0:
            return (current_price - self.avg_entry_price) / self.avg_entry_price
        return (self.avg_entry_price - current_price) / self.avg_entry_price

    def _current_exposure(self, current_price: float) -> float:
        equity = max(self.net_worth, 1e-9)
        return float(np.clip((self.position * current_price) / equity, -1.0, 1.0))

    def _signal_strength(self, row: pd.Series, direction: int) -> float:
        trend_score = float(row.get("Trend_30", 0.0)) + 0.5 * float(row.get("Trend_2h", 0.0))
        rel_score = 2.0 * float(row.get("StockMinusMkt_3", 0.0)) + float(row.get("StockMinusMkt_1", 0.0))
        persistence = float(row.get("SignPersistence_5", 0.0))
        breakout = float(row.get("Breakout_3bar", 0.0))
        regime_trend = float(row.get("RegimeBull", 0.0)) - float(row.get("RegimeBear", 0.0))
        if direction < 0:
            trend_score *= -1.0
            rel_score *= -1.0
            persistence *= -1.0
            breakout *= -1.0
            regime_trend *= -1.0
        raw = trend_score + rel_score + 0.5 * persistence + 0.5 * breakout + 0.25 * regime_trend
        return float(np.clip(1.0 / (1.0 + math.exp(-4.0 * raw)), 0.0, 1.0))

    def _reversion_strength(self, row: pd.Series, direction: int) -> float:
        rsi = float(row.get("RSI14", 50.0))
        vwap_dist = float(row.get("VWAP_Dist", 0.0))
        session_stretch = float(row.get("SessionOpenDist_ATR", 0.0))
        close_loc = float(row.get("CloseLocation_3", 0.5))
        persistence = float(row.get("SignPersistence_5", 0.0))
        breakout = float(row.get("Breakout_3bar", 0.0))
        trend_30 = float(row.get("Trend_30", 0.0))
        if direction > 0:
            raw = (
                max(0.0, (35.0 - rsi) / 20.0)
                + max(0.0, -vwap_dist)
                + 0.5 * max(0.0, -session_stretch)
                + max(0.0, 0.35 - close_loc)
                + 0.5 * max(0.0, -persistence)
                + 0.25 * max(0.0, -trend_30)
                + 0.25 * max(0.0, -breakout)
            )
        else:
            raw = (
                max(0.0, (rsi - 65.0) / 20.0)
                + max(0.0, vwap_dist)
                + 0.5 * max(0.0, session_stretch)
                + max(0.0, close_loc - 0.65)
                + 0.5 * max(0.0, persistence)
                + 0.25 * max(0.0, trend_30)
                + 0.25 * max(0.0, breakout)
            )
        return float(np.clip(1.0 / (1.0 + math.exp(-3.0 * raw)), 0.0, 1.0))

    def _trend_entry_allowed(self, row: pd.Series, direction: int) -> bool:
        strong_trend = float(row.get("ADX_strong", 0.0)) > 0.5
        bull = float(row.get("RegimeBull", 0.0)) > 0.5
        bear = float(row.get("RegimeBear", 0.0)) > 0.5
        confidence = self._signal_strength(row, direction)
        min_confidence = float(self.reward_weights.get("regime_gate_min_confidence", 0.60))
        if self.mode == "test":
            min_confidence = min(min_confidence, 0.55)
        rel_1 = float(row.get("StockMinusMkt_1", 0.0))
        rel_3 = float(row.get("StockMinusMkt_3", 0.0))
        breakout = float(row.get("Breakout_3bar", 0.0))
        trend_30 = float(row.get("Trend_30", 0.0))
        persistence = float(row.get("SignPersistence_5", 0.0))
        min_confirmations = int(self.reward_weights.get("regime_gate_min_confirmations", 2))
        if self.mode == "test":
            min_confirmations = max(2, min_confirmations)
        if direction > 0:
            confirmations = sum([
                rel_3 > 0.0015,
                rel_1 > 0.0005,
                breakout > 0.0,
                trend_30 > 0.0,
                persistence > 0.10,
                bull,
                strong_trend,
            ])
            return confidence >= min_confidence and confirmations >= min_confirmations
        if direction < 0:
            confirmations = sum([
                rel_3 < -0.0015,
                rel_1 < -0.0005,
                breakout < 0.0,
                trend_30 < 0.0,
                persistence < -0.10,
                bear,
                strong_trend,
            ])
            return confidence >= min_confidence and confirmations >= min_confirmations
        return True

    def _reversion_entry_allowed(self, row: pd.Series, direction: int) -> bool:
        rev_confidence = self._reversion_strength(row, direction)
        min_confidence = float(self.reward_weights.get("reversion_gate_min_confidence", 0.55))
        min_confirmations = int(self.reward_weights.get("reversion_gate_min_confirmations", 2))
        if self.mode == "test":
            min_confidence = min(min_confidence, 0.52)
        strong_trend = float(row.get("ADX_strong", 0.0)) > 0.5
        bull = float(row.get("RegimeBull", 0.0)) > 0.5
        bear = float(row.get("RegimeBear", 0.0)) > 0.5
        rsi = float(row.get("RSI14", 50.0))
        vwap_dist = float(row.get("VWAP_Dist", 0.0))
        session_stretch = float(row.get("SessionOpenDist_ATR", 0.0))
        close_loc = float(row.get("CloseLocation_3", 0.5))
        persistence = float(row.get("SignPersistence_5", 0.0))
        breakout = float(row.get("Breakout_3bar", 0.0))
        if direction > 0:
            confirmations = sum([
                rsi < 35.0,
                vwap_dist < -0.20,
                session_stretch < -0.30,
                close_loc < 0.35,
                persistence < 0.05,
                breakout <= 0.0,
                not strong_trend or bear,
            ])
        else:
            confirmations = sum([
                rsi > 65.0,
                vwap_dist > 0.20,
                session_stretch > 0.30,
                close_loc > 0.65,
                persistence > -0.05,
                breakout >= 0.0,
                not strong_trend or bull,
            ])
        return rev_confidence >= min_confidence and confirmations >= min_confirmations

    def _route_entry_style(self, row: pd.Series, direction: int) -> str:
        trend_ok = self._trend_entry_allowed(row, direction)
        reversion_ok = self._reversion_entry_allowed(row, direction)
        trend_strength = self._signal_strength(row, direction)
        reversion_strength = self._reversion_strength(row, direction)
        style_margin = float(self.reward_weights.get("style_router_margin", 0.15))
        single_style_min_strength = float(self.reward_weights.get("style_router_min_strength", 0.55))
        if self.mode == "test":
            style_margin = min(style_margin, 0.12)
            single_style_min_strength = min(single_style_min_strength, 0.50)
        if trend_ok and trend_strength > reversion_strength + style_margin:
            return "trend"
        if reversion_ok and reversion_strength > trend_strength + style_margin:
            return "reversion"
        if trend_ok and not reversion_ok and trend_strength >= single_style_min_strength:
            return "trend"
        if reversion_ok and not trend_ok and reversion_strength >= single_style_min_strength:
            return "reversion"
        return "hold"

    def _regime_allows_direction(self, row: pd.Series, direction: int) -> bool:
        return self._route_entry_style(row, direction) != "hold"

    def _update_avg_entry_after_trade(self, previous_position: int, traded_shares: int, execution_price: float, trade_side: str) -> None:
        if traded_shares <= 0:
            return
        if trade_side == "buy":
            if previous_position >= 0 and self.position > 0:
                prev_qty = max(previous_position, 0)
                new_qty = self.position
                total_cost_basis = prev_qty * self.avg_entry_price + traded_shares * execution_price
                self.avg_entry_price = total_cost_basis / max(new_qty, 1)
            elif self.position == 0:
                self.avg_entry_price = 0.0
            elif previous_position < 0 and self.position < 0:
                self.avg_entry_price = execution_price if abs(self.position) == traded_shares else self.avg_entry_price
        elif trade_side == "sell":
            if previous_position <= 0 and self.position < 0:
                prev_qty = abs(min(previous_position, 0))
                new_qty = abs(self.position)
                total_cost_basis = prev_qty * self.avg_entry_price + traded_shares * execution_price
                self.avg_entry_price = total_cost_basis / max(new_qty, 1)
            elif self.position == 0:
                self.avg_entry_price = 0.0
            elif previous_position > 0 and self.position > 0:
                self.avg_entry_price = self.avg_entry_price

    def _resolve_warmup_steps(self) -> int:
        configured = int(self.reward_weights.get("warmup_steps", 20))
        available_steps = max(0, min(len(self.df), self.max_episode_steps) - 1)
        if available_steps <= 0:
            return 0
        if self.mode == "test":
            return 0
        return max(0, min(configured, available_steps // 10))

    def step(self, action):
        buy_mult = 1.0 + self.slippage_rate
        sell_mult = 1.0 - self.slippage_rate
        eps = 1e-9
        breakdowns_list = []
        self.cumulative_slippage_cost = 0.0

        if self._force_termination:
            obs = self._next_observation()
            self.final_metrics = self.get_current_metrics()
            self._force_termination = False
            return obs, 0.0, True, True, {}

        if self.current_step >= len(self.df):
            return self._next_observation(), -1000.0, True, False, {}

        try:
            action_id = int(np.asarray(action).item()) if isinstance(action, (np.ndarray, list, tuple)) else int(action)
            assert self.action_space.contains(action_id), f"Invalid action: {action_id}"
        except Exception:
            return self._next_observation(), -1000.0, True, False, {}

        self._next_observation()
        current_data = self.df.iloc[self.current_step]
        current_price = float(current_data["Close"])
        current_date = current_data["Date"]
        current_step = self.current_step

        action_labels = {0: "hold", 1: "long", 2: "short", 3: "reduce"}
        action_name = action_labels.get(action_id, "hold")
        action_value = 0.0 if action_id in (0, 3) else (1.0 if action_id == 1 else -1.0)
        invalid_act_penalty = 0.0
        forced_stop_penalty = 0.0
        forced_tp_penalty = 0.0
        drawdown_penalty = 0.0
        stop_loss_triggered = False
        take_profit_triggered = False
        drawdown_triggered = False
        stop_exit_side = "flat"
        tp_exit_side = "flat"
        active_style = self.position_style if self.position != 0 else "flat"
        buy_signal_price = np.nan
        sell_signal_price = np.nan
        shares_traded = 0
        total_trade_cost = 0.0

        if current_step < self.warmup_steps:
            action_id = 0
            action_name = "warmup_hold"
            action_value = 0.0

        def execute_trade(side: str, shares: int, entry_style: Optional[str] = None) -> Tuple[int, float]:
            nonlocal total_trade_cost, shares_traded, buy_signal_price, sell_signal_price
            if shares <= 0:
                return 0, 0.0
            previous_position = self.position
            if side == "buy":
                exec_price = current_price * buy_mult
                order_value = shares * exec_price
                cost, breakdown = self.calculate_transaction_cost(order_value, "buy", shares)
                total_cost = order_value + cost
                if total_cost > self.balance:
                    return 0, 0.0
                self.balance -= total_cost
                self.position += shares
                self._update_avg_entry_after_trade(previous_position, shares, exec_price, "buy")
                self.cumulative_slippage_cost += shares * (exec_price - current_price)
                buy_signal_price = current_price
            else:
                exec_price = current_price * sell_mult
                order_value = shares * exec_price
                cost, breakdown = self.calculate_transaction_cost(order_value, "sell", shares)
                proceeds = order_value - cost
                self.balance += proceeds
                self.position -= shares
                self._update_avg_entry_after_trade(previous_position, shares, exec_price, "sell")
                self.cumulative_slippage_cost += shares * (current_price - exec_price)
                sell_signal_price = current_price

            total_trade_cost += cost
            breakdowns_list.append(breakdown)
            self.transaction_count += 1
            shares_traded += shares
            if self.position == 0:
                self.position_style = "flat"
            elif entry_style and (previous_position == 0 or np.sign(previous_position) != np.sign(self.position)):
                self.position_style = entry_style
            self._recompute_net_worth(current_price)
            return shares, exec_price

        def reduce_position(fraction: float) -> None:
            if self.position > 0:
                qty = min(abs(self.position), max(1, math.floor(abs(self.position) * fraction)))
                execute_trade("sell", qty)
                if self.position == 0:
                    self.avg_entry_price = 0.0
                    self.position_style = "flat"
            elif self.position < 0:
                qty = min(abs(self.position), max(1, math.floor(abs(self.position) * fraction)))
                execute_trade("buy", qty)
                if self.position == 0:
                    self.avg_entry_price = 0.0
                    self.position_style = "flat"

        self._recompute_net_worth(current_price)
        position_return = self._position_return(current_price)
        position_side = "long" if self.position > 0 else "short" if self.position < 0 else "flat"
        forced_stop_penalty_weight = float(self.reward_weights.get("forced_stop_penalty_weight", 0.001))
        forced_tp_penalty_weight = float(self.reward_weights.get("forced_tp_penalty_weight", 0.001))
        if self.position != 0 and self.avg_entry_price > 0:
            if active_style == "reversion":
                long_stop_loss_tiers = [
                    {"threshold": 0.012, "fraction": 0.35, "penalty_factor": 1.0},
                    {"threshold": 0.024, "fraction": 0.70, "penalty_factor": 1.5},
                    {"threshold": 0.035, "fraction": 1.00, "penalty_factor": 2.0},
                ]
                short_stop_loss_tiers = [
                    {"threshold": 0.012, "fraction": 0.35, "penalty_factor": 1.0},
                    {"threshold": 0.024, "fraction": 0.70, "penalty_factor": 1.5},
                    {"threshold": 0.035, "fraction": 1.00, "penalty_factor": 2.0},
                ]
                long_take_profit_tiers = [
                    {"threshold": 0.018, "fraction": 0.50, "penalty_factor": 0.5},
                    {"threshold": 0.035, "fraction": 0.85, "penalty_factor": 1.0},
                    {"threshold": 0.050, "fraction": 1.00, "penalty_factor": 1.5},
                ]
                short_take_profit_tiers = [
                    {"threshold": 0.018, "fraction": 0.50, "penalty_factor": 0.5},
                    {"threshold": 0.035, "fraction": 0.85, "penalty_factor": 1.0},
                    {"threshold": 0.050, "fraction": 1.00, "penalty_factor": 1.5},
                ]
            else:
                long_stop_loss_tiers = [
                    {"threshold": 0.015, "fraction": 0.25, "penalty_factor": 1.0},
                    {"threshold": 0.03, "fraction": 0.50, "penalty_factor": 1.5},
                    {"threshold": 0.05, "fraction": 1.00, "penalty_factor": 2.0},
                ]
                short_stop_loss_tiers = [
                    {"threshold": 0.015, "fraction": 0.25, "penalty_factor": 1.0},
                    {"threshold": 0.03, "fraction": 0.50, "penalty_factor": 1.5},
                    {"threshold": 0.05, "fraction": 1.00, "penalty_factor": 2.0},
                ]
                long_take_profit_tiers = [
                    {"threshold": 0.03, "fraction": 0.25, "penalty_factor": 0.5},
                    {"threshold": 0.06, "fraction": 0.50, "penalty_factor": 1.0},
                    {"threshold": 0.09, "fraction": 1.00, "penalty_factor": 1.5},
                ]
                short_take_profit_tiers = [
                    {"threshold": 0.03, "fraction": 0.25, "penalty_factor": 0.5},
                    {"threshold": 0.06, "fraction": 0.50, "penalty_factor": 1.0},
                    {"threshold": 0.09, "fraction": 1.00, "penalty_factor": 1.5},
                ]

            stop_loss_tiers = long_stop_loss_tiers if self.position > 0 else short_stop_loss_tiers
            take_profit_tiers = long_take_profit_tiers if self.position > 0 else short_take_profit_tiers

            for tier in reversed(stop_loss_tiers):
                if position_return < -tier["threshold"]:
                    stop_loss_triggered = True
                    stop_exit_side = position_side
                    forced_stop_penalty -= forced_stop_penalty_weight * abs(position_return) * tier["penalty_factor"]
                    reduce_position(tier["fraction"])
                    break
            if self.position != 0:
                for tier in reversed(take_profit_tiers):
                    if position_return > tier["threshold"]:
                        take_profit_triggered = True
                        tp_exit_side = position_side
                        forced_tp_penalty -= forced_tp_penalty_weight * abs(position_return) * tier["penalty_factor"]
                        reduce_position(tier["fraction"])
                        break

        self._recompute_net_worth(current_price)
        current_drawdown = (self.peak - self.net_worth) / self.peak if self.peak > 0 else 0.0
        if current_drawdown > 0.05 and self.position != 0:
            drawdown_triggered = True
            drawdown_penalty = -self.some_factor * current_drawdown
            if current_drawdown > 0.10:
                reduce_position(1.0)
            elif current_drawdown > 0.075:
                reduce_position(0.5)
        self._recompute_net_worth(current_price)

        trade_fraction = float(self.reward_weights.get("trade_fraction", 0.15))
        min_trade_fraction = float(self.reward_weights.get("min_trade_fraction", 0.05))
        reduce_fraction = float(self.reward_weights.get("reduce_fraction", 0.5))
        action_penalty_weight = float(self.reward_weights.get("action_penalty_weight", 0.001))
        reduce_penalty_multiplier = float(self.reward_weights.get("reduce_penalty_multiplier", 1.5))
        rebalance_threshold = float(self.reward_weights.get("rebalance_threshold", 0.20))
        reduce_hold_threshold = float(self.reward_weights.get("reduce_hold_threshold", 0.02))
        entry_min_exposure = float(self.reward_weights.get("entry_min_exposure", 0.02))
        min_market_vol_rank = float(self.reward_weights.get("min_market_vol_rank", 0.30))
        signal_gate_enabled = bool(self.reward_weights.get("signal_gate_enabled", False))
        signal_gate_entry_threshold = float(self.reward_weights.get("signal_gate_entry_threshold", 0.68))
        signal_gate_reduce_threshold = float(self.reward_weights.get("signal_gate_reduce_threshold", 0.60))
        signal_confirm_enabled = bool(self.reward_weights.get("signal_confirm_enabled", False))
        signal_confirm_entry_threshold = float(self.reward_weights.get("signal_confirm_entry_threshold", 0.70))
        signal_confirm_reduce_threshold = float(self.reward_weights.get("signal_confirm_reduce_threshold", 0.58))
        equity = max(self.net_worth, eps)
        current_exposure = self._current_exposure(current_price)
        style_trend_strength = 0.0
        style_reversion_strength = 0.0
        target_exposure = current_exposure
        current_mkt_vol_rank = float(current_data.get("MktVolRank", 0.5))
        signal_gate_source = str(self.reward_weights.get("signal_gate_source", "Signal_E102_Pred"))
        current_signal_pred = float(current_data.get(signal_gate_source, 0.5))
        current_confirm_signal_pred = float(current_data.get("Signal_E302_Pred", 0.5))

        if action_id in (1, 2):
            if signal_gate_enabled and current_signal_pred < signal_gate_entry_threshold:
                action_id = 0
                action_name = "signal_gate_hold"
                action_value = 0.0
            elif signal_confirm_enabled and current_confirm_signal_pred < signal_confirm_entry_threshold:
                action_id = 0
                action_name = "signal_confirm_hold"
                action_value = 0.0
            else:
                direction = 1 if action_id == 1 else -1
                style_trend_strength = self._signal_strength(current_data, direction)
                style_reversion_strength = self._reversion_strength(current_data, direction)
                entry_style = self._route_entry_style(current_data, direction)
                if current_mkt_vol_rank < min_market_vol_rank:
                    action_id = 0
                    action_name = "vol_hold"
                    action_value = 0.0
                elif entry_style == "hold":
                    action_id = 0
                    action_name = "style_hold"
                    action_value = 0.0
                else:
                    active_style = entry_style
                    confidence = style_trend_strength if entry_style == "trend" else style_reversion_strength
                    dynamic_fraction = min_trade_fraction + (trade_fraction - min_trade_fraction) * confidence
                    target_exposure = float(np.clip(direction * dynamic_fraction * self.max_position_size, -self.max_position_size, self.max_position_size))
                    exposure_gap = abs(target_exposure - current_exposure)
                    min_gap = rebalance_threshold if abs(current_exposure) > 1e-9 else entry_min_exposure
                    if exposure_gap < min_gap:
                        action_id = 0
                        action_name = f"{entry_style}_inertia_hold"
                        action_value = 0.0
                    else:
                        target_notional_change = abs(target_exposure - current_exposure) * equity
                        shares = max(1, math.floor(target_notional_change / (current_price * (buy_mult if direction > 0 else sell_mult))))
                        if direction > 0:
                            filled, _ = execute_trade("buy", shares, entry_style=entry_style)
                            if filled == 0:
                                invalid_act_penalty -= 0.001
                        else:
                            filled, _ = execute_trade("sell", shares, entry_style=entry_style)
                            if filled == 0:
                                invalid_act_penalty -= 0.001
                        if filled > 0:
                            action_name = f"{entry_style}_{action_name}"
        elif action_id == 3:
            if signal_gate_enabled and current_signal_pred >= signal_gate_reduce_threshold and abs(current_exposure) >= reduce_hold_threshold:
                action_id = 0
                action_name = "signal_gate_keep"
                action_value = 0.0
            elif signal_confirm_enabled and current_confirm_signal_pred >= signal_confirm_reduce_threshold and abs(current_exposure) >= reduce_hold_threshold:
                action_id = 0
                action_name = "signal_confirm_keep"
                action_value = 0.0
            elif abs(current_exposure) < reduce_hold_threshold:
                action_id = 0
                action_name = "reduce_inertia_hold"
                action_value = 0.0
            else:
                reduce_position(reduce_fraction)

        action_penalty = 0.0
        if action_id in (1, 2):
            action_penalty = action_penalty_weight
        elif action_id == 3:
            action_penalty = action_penalty_weight * reduce_penalty_multiplier

        timed_exit_triggered = False
        current_position_sign = int(np.sign(self.position))
        if current_position_sign == 0:
            self.position_holding_bars = 0
        elif current_position_sign != self.last_position_sign:
            self.position_holding_bars = 1
        else:
            self.position_holding_bars += 1

        if (
            self.max_holding_bars is not None
            and self.position != 0
            and self.position_holding_bars >= self.max_holding_bars
        ):
            timed_exit_triggered = True
            reduce_position(1.0)
            if self.position == 0:
                self.avg_entry_price = 0.0
                self.position_style = "flat"
                self.position_holding_bars = 0
            current_position_sign = int(np.sign(self.position))
        self.last_position_sign = current_position_sign

        if self.position < 0:
            mtm_cover_cost = abs(self.position) * current_price * buy_mult
            if mtm_cover_cost > self.balance:
                affordable_shares = math.floor(self.balance / (current_price * buy_mult))
                if affordable_shares <= 0:
                    invalid_act_penalty -= 1.0
                else:
                    execute_trade("buy", affordable_shares)

        self._recompute_net_worth(current_price)
        safe_prev = max(self.prev_net_worth, eps)
        step_return = (self.net_worth - self.prev_net_worth) / safe_prev
        exposure = self._current_exposure(current_price)

        next_idx_1 = min(current_step + 1, len(self.df) - 1)
        next_idx_3 = min(current_step + 3, len(self.df) - 1)
        next_close_1 = float(self.df.iloc[next_idx_1]["Close"])
        next_close_3 = float(self.df.iloc[next_idx_3]["Close"])
        ret_1 = (next_close_1 - current_price) / max(current_price, eps)
        ret_3 = (next_close_3 - current_price) / max(current_price, eps)
        pnl_1 = exposure * ret_1
        pnl_3 = exposure * ret_3
        next_row_3 = self.df.iloc[next_idx_3]
        next_vwap_dist = float(next_row_3.get("VWAP_Dist", current_data.get("VWAP_Dist", 0.0)))
        next_session_stretch = float(next_row_3.get("SessionOpenDist_ATR", current_data.get("SessionOpenDist_ATR", 0.0)))
        curr_vwap_dist = float(current_data.get("VWAP_Dist", 0.0))
        curr_session_stretch = float(current_data.get("SessionOpenDist_ATR", 0.0))
        vwap_reversion_gain = max(0.0, abs(curr_vwap_dist) - abs(next_vwap_dist))
        stretch_reversion_gain = max(0.0, abs(curr_session_stretch) - abs(next_session_stretch))
        reversion_component = 0.5 * vwap_reversion_gain + 0.5 * stretch_reversion_gain

        dir_threshold = float(self.reward_weights.get("direction_threshold", 0.0015))
        flat_threshold = float(self.reward_weights.get("flat_threshold", 0.0010))
        weak_move_threshold = float(self.reward_weights.get("weak_move_threshold", 0.0025))
        flat_reward_bonus = float(self.reward_weights.get("flat_reward_bonus", 0.20))
        wrong_flat_penalty = float(self.reward_weights.get("wrong_flat_penalty", 0.25))
        if action_id == 1:
            directional_component = 1.0 if ret_3 > dir_threshold else -1.0
        elif action_id == 2:
            directional_component = 1.0 if ret_3 < -dir_threshold else -1.0
        else:
            if abs(ret_3) < flat_threshold:
                directional_component = flat_reward_bonus
            elif abs(ret_3) < weak_move_threshold:
                directional_component = 0.0
            else:
                directional_component = -wrong_flat_penalty

        self.returns_window.append(step_return)
        if len(self.returns_window) > 50:
            self.returns_window.pop(0)
        rolling_volatility = float(np.std(self.returns_window)) if len(self.returns_window) >= 2 else 0.0
        transaction_penalty_weight = float(self.reward_weights.get("transaction_penalty_weight", 1.0))
        transaction_penalty = (total_trade_cost / safe_prev) * transaction_penalty_weight
        volatility_penalty_weight = float(self.reward_weights.get("volatility_penalty_weight", 0.10))
        directional_weight = float(self.reward_weights.get("directional_weight", 0.01))
        reversion_weight = float(self.reward_weights.get("reversion_weight", 0.04))
        if active_style == "reversion":
            reward_core = 0.25 * pnl_1 + 0.45 * pnl_3 + directional_weight * directional_component + reversion_weight * reversion_component
        else:
            reward_core = 0.4 * pnl_1 + 0.6 * pnl_3 + directional_weight * directional_component
        risk_adjusted_reward = reward_core - transaction_penalty - volatility_penalty_weight * rolling_volatility - action_penalty
        reward = risk_adjusted_reward + forced_stop_penalty + forced_tp_penalty + drawdown_penalty + invalid_act_penalty
        if current_step < self.warmup_steps:
            reward = 0.0

        self.transaction_cost = total_trade_cost
        self.reward_history.append(reward)
        self.cumulative_reward += float(reward)
        self.last_action = action_id

        self.history.append({
            "Date": current_date,
            "Close": current_price,
            "ticker": self.ticker,
            "env_rank": self.env_rank,
            "Action": action_id,
            "ActionName": action_name,
            "ActionLegacy": action_value,
            "Buy_Signal_Price": buy_signal_price,
            "Sell_Signal_Price": sell_signal_price,
            "Full Worth": self.net_worth,
            "Net Worth": self.net_worth,
            "Balance": self.balance,
            "Realized Gain": 0.0,
            "Position": self.position,
            "AvgEntryPrice": self.avg_entry_price,
            "Exposure": exposure,
            "StrategyStyle": active_style,
            "TrendStrength": style_trend_strength,
            "ReversionStrength": style_reversion_strength,
            "TargetExposure": target_exposure,
            "ExposureGap": abs(target_exposure - current_exposure),
            "Reward": float(reward),
            "profit_reward": reward_core,
            "sharpe_bonus": 0.0,
            "holding_bonus": 0.0,
            "TransactionCost": self.transaction_cost,
            "Slippage": self.cumulative_slippage_cost,
            "Transaction_Breakdowns": breakdowns_list,
            "cumulative_reward": self.cumulative_reward,
            "forced_stop_penalty": forced_stop_penalty,
            "forced_tp_penalty": forced_tp_penalty,
            "drawdown_penalty": drawdown_penalty,
            "transaction_penalty": -transaction_penalty,
            "action_penalty": -action_penalty,
            "rolling_volatility": rolling_volatility,
            "risk_adjusted_reward": risk_adjusted_reward,
            "future_ret_1": ret_1,
            "future_ret_3": ret_3,
            "pnl_1_component": pnl_1,
            "pnl_3_component": pnl_3,
            "directional_component": directional_component,
            "reversion_component": reversion_component,
            "is_terminated": False,
            "stop_loss_triggered": stop_loss_triggered,
            "take_profit_triggered": take_profit_triggered,
            "stop_exit_side": stop_exit_side,
            "tp_exit_side": tp_exit_side,
            "drawdown_triggered": drawdown_triggered,
            "timed_exit_triggered": timed_exit_triggered,
            "position_holding_bars": int(self.position_holding_bars),
            "equity_reference": self.net_worth,
            "invalid_act_penalty": invalid_act_penalty,
            "profit_weight": 1.0,
            "sharpe_bonus_weight": 0.0,
            "transaction_penalty_weight": transaction_penalty_weight,
            "holding_bonus_weight": 0.0,
            "inference_buy_threshold": self.inference_buy_threshold,
            "inference_sell_threshold": self.inference_sell_threshold,
            "forced_stop_penalty_weight": forced_stop_penalty_weight,
            "forced_tp_penalty_weight": forced_tp_penalty_weight,
            **{f"Obs_{k}": float(v) for k, v in self.current_obs_dict.items()}
        })

        row_data = self.df.iloc[current_step].copy()
        row_data.drop(labels=["Date", "Close", "Adj Close", "Open", "High", "Low", "Volume"], errors="ignore", inplace=True)
        for col in FEATURES_TO_SCALE:
            self.history[-1][col] = row_data.get(col, np.nan)

        terminated = False
        if self.net_worth <= 0:
            terminated = True
        elif current_step >= len(self.df) - 1 or current_step >= self.max_episode_steps - 1:
            terminated = True

        truncated = False
        self.history[-1]["is_terminated"] = terminated
        if terminated:
            self.last_episode_metrics = {
                "cumulative_reward": sum(entry.get("Reward", 0.0) for entry in self.history),
                "net_worth": self.net_worth,
                "balance": self.balance,
                "position": self.position,
                "transaction_count": self.transaction_count,
                "peak": self.peak,
                "history": self.history.copy()
            }
        else:
            self.prev_net_worth = self.net_worth
            self.current_step += 1

        self.current_step = min(self.current_step, len(self.df) - 1)
        obs = self._next_observation()
        normalized_reward = 0.0 if not np.isfinite(reward) else float(reward)
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
    step_days: int = 20,
    train_mode: str = "rolling",
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
        train_start = 0 if train_mode == "expanding" else start
        train_end = train_start + train_bars if train_mode != "expanding" else train_bars + start
        val_end = train_end + val_bars
        test_end = val_end + test_bars
        if test_end > total:
            break
        windows.append((train_start, train_end, val_end, test_end))
        start += step_bars
    return windows


def assign_research_window_ids(
    df: pd.DataFrame,
    interval: str,
    window_days: int = 20,
) -> pd.DataFrame:
    out = df.copy()
    bars_per_day = interval_to_bars_per_day(interval)
    rows_per_window = max(1, bars_per_day * max(1, window_days))
    out["WindowID"] = (np.arange(len(out)) // rows_per_window) + 1
    return out


def add_cross_sectional_research_features(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty or "Date" not in dataset.columns or "Ticker" not in dataset.columns:
        return dataset

    out = dataset.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    close = pd.to_numeric(out.get("Close"), errors="coerce")
    mkt_ret_6 = pd.to_numeric(out.get("MktRet_6"), errors="coerce").fillna(0.0)
    real_vol = np.exp(pd.to_numeric(out.get("RealVol20_log"), errors="coerce").fillna(np.log(1e-6)))
    real_vol = pd.Series(real_vol, index=out.index).replace([np.inf, -np.inf], np.nan).clip(lower=1e-6).fillna(1e-6)

    out["StockMinusMkt_6"] = close.groupby(out["Ticker"]).pct_change(6).fillna(0.0) - mkt_ret_6
    out["VolAdjStockMinusMkt_1"] = (
        pd.to_numeric(out.get("StockMinusMkt_1"), errors="coerce").fillna(0.0) / real_vol
    ).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10.0, 10.0)
    out["VolAdjStockMinusMkt_3"] = (
        pd.to_numeric(out.get("StockMinusMkt_3"), errors="coerce").fillna(0.0) / real_vol
    ).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10.0, 10.0)

    rank_inputs = {
        "XS_Rank_StockMinusMkt_1": "StockMinusMkt_1",
        "XS_Rank_StockMinusMkt_3": "StockMinusMkt_3",
        "XS_Rank_StockMinusMkt_6": "StockMinusMkt_6",
        "XS_Rank_SectorMinusMkt_3": "SectorMinusMkt_3",
        "XS_Rank_RelativeVolumeTime": "RelativeVolumeTime",
        "XS_Rank_VolAdjStockMinusMkt_1": "VolAdjStockMinusMkt_1",
        "XS_Rank_VolAdjStockMinusMkt_3": "VolAdjStockMinusMkt_3",
    }
    for feature_col, source_col in rank_inputs.items():
        source = pd.to_numeric(out.get(source_col), errors="coerce")
        out[feature_col] = source.groupby(out["Date"]).rank(method="average", pct=True).fillna(0.5)

    out["XS_LeaderSpread_3"] = (
        out["XS_Rank_StockMinusMkt_3"] - out["XS_Rank_SectorMinusMkt_3"]
    ).fillna(0.0)
    out["XS_VolumeLeaderSpread"] = (out["XS_Rank_RelativeVolumeTime"] - 0.5).fillna(0.0)

    top20 = (out["XS_Rank_StockMinusMkt_3"] >= 0.80).astype(float)
    bottom20 = (out["XS_Rank_StockMinusMkt_3"] <= 0.20).astype(float)
    out["XS_LeaderTop20"] = top20
    out["XS_LaggardBottom20"] = bottom20
    out["XS_LeaderPersist_3"] = top20.groupby(out["Ticker"]).transform(lambda s: s.rolling(3, min_periods=1).sum()).fillna(0.0)
    out["XS_LaggardPersist_3"] = bottom20.groupby(out["Ticker"]).transform(lambda s: s.rolling(3, min_periods=1).sum()).fillna(0.0)
    out["XS_LeaderPersist_6"] = top20.groupby(out["Ticker"]).transform(lambda s: s.rolling(6, min_periods=1).sum()).fillna(0.0)
    out["XS_LaggardPersist_6"] = bottom20.groupby(out["Ticker"]).transform(lambda s: s.rolling(6, min_periods=1).sum()).fillna(0.0)
    out["XS_Rank_Change_3"] = out.groupby("Ticker")["XS_Rank_StockMinusMkt_3"].diff(3).fillna(0.0)

    stock_minus_mkt_3 = pd.to_numeric(out.get("StockMinusMkt_3"), errors="coerce").fillna(0.0)
    sector_minus_mkt_3 = pd.to_numeric(out.get("SectorMinusMkt_3"), errors="coerce").fillna(0.0)
    out["SectorResidual_3"] = stock_minus_mkt_3 - sector_minus_mkt_3
    out["VolAdjSectorResidual_3"] = (
        out["SectorResidual_3"] / real_vol
    ).replace([np.inf, -np.inf], 0.0).fillna(0.0).clip(-10.0, 10.0)
    out["XS_Rank_SectorResidual_3"] = (
        pd.to_numeric(out["SectorResidual_3"], errors="coerce")
        .groupby(out["Date"])
        .rank(method="average", pct=True)
        .fillna(0.5)
    )
    centered_stock_rank = pd.to_numeric(out["XS_Rank_StockMinusMkt_3"], errors="coerce").fillna(0.5) - 0.5
    centered_sector_rank = pd.to_numeric(out["XS_Rank_SectorMinusMkt_3"], errors="coerce").fillna(0.5) - 0.5
    centered_residual_rank = pd.to_numeric(out["XS_Rank_SectorResidual_3"], errors="coerce").fillna(0.5) - 0.5
    out["XS_CommonalityResidual_3"] = (centered_stock_rank - centered_sector_rank).clip(-1.0, 1.0)
    out["XS_IdiosyncraticLeader_3"] = (centered_residual_rank - centered_sector_rank.abs()).clip(-1.0, 1.0)
    out["XS_IdiosyncraticLaggard_3"] = ((-centered_residual_rank) - centered_sector_rank.abs()).clip(-1.0, 1.0)
    residual_top20 = (out["XS_Rank_SectorResidual_3"] >= 0.80).astype(float)
    residual_bottom20 = (out["XS_Rank_SectorResidual_3"] <= 0.20).astype(float)
    out["ResidualLeaderPersist_3"] = residual_top20.groupby(out["Ticker"]).transform(lambda s: s.rolling(3, min_periods=1).sum()).fillna(0.0)
    out["ResidualLaggardPersist_3"] = residual_bottom20.groupby(out["Ticker"]).transform(lambda s: s.rolling(3, min_periods=1).sum()).fillna(0.0)

    mkt_ret_1 = pd.to_numeric(out.get("MktRet_1"), errors="coerce").fillna(0.0)
    lag_ret_1 = pd.to_numeric(out.get("LagRet_1"), errors="coerce").fillna(0.0)
    stock_minus_mkt_1 = pd.to_numeric(out.get("StockMinusMkt_1"), errors="coerce").fillna(0.0)
    relative_volume = pd.to_numeric(out.get("RelativeVolumeTime"), errors="coerce").fillna(0.0)
    sign_stock = np.sign(lag_ret_1)
    sign_mkt = np.sign(mkt_ret_1)
    participation = np.where(sign_mkt == 0.0, 0.5, (sign_stock == sign_mkt).astype(float))

    out["_BreadthAdv1"] = (stock_minus_mkt_1 > 0.0).astype(float)
    out["_BreadthRelAdv3"] = (stock_minus_mkt_3 > 0.0).astype(float)
    out["_BreadthLeader"] = (out["XS_Rank_StockMinusMkt_3"] >= 0.80).astype(float)
    out["_BreadthLaggard"] = (out["XS_Rank_StockMinusMkt_3"] <= 0.20).astype(float)
    out["_BreadthParticipation"] = participation

    breadth_df = (
        out.groupby("Date", as_index=False)
        .agg(
            BreadthAdvFrac_1=("_BreadthAdv1", "mean"),
            BreadthRelAdvFrac_3=("_BreadthRelAdv3", "mean"),
            BreadthLeaderFrac=("_BreadthLeader", "mean"),
            BreadthLaggardFrac=("_BreadthLaggard", "mean"),
            BreadthDispersion_3=("StockMinusMkt_3", "std"),
            BreadthVolumePressure=("RelativeVolumeTime", "mean"),
            BreadthParticipation=("_BreadthParticipation", "mean"),
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )
    breadth_df["BreadthTrendPressure"] = (2.0 * breadth_df["BreadthAdvFrac_1"] - 1.0).clip(-1.0, 1.0)
    breadth_df["BreadthLeaderSpread"] = (
        breadth_df["BreadthLeaderFrac"] - breadth_df["BreadthLaggardFrac"]
    ).clip(-1.0, 1.0)
    breadth_df["BreadthExpansion_3"] = breadth_df["BreadthTrendPressure"].diff(3).fillna(0.0).clip(-1.0, 1.0)
    breadth_df["BreadthDispersion_3"] = (
        pd.to_numeric(breadth_df["BreadthDispersion_3"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .clip(0.0, 5.0)
    )
    breadth_df["BreadthVolumePressure"] = (
        pd.to_numeric(breadth_df["BreadthVolumePressure"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .clip(-5.0, 5.0)
    )
    out = out.merge(breadth_df, on="Date", how="left")
    out.drop(
        columns=["_BreadthAdv1", "_BreadthRelAdv3", "_BreadthLeader", "_BreadthLaggard", "_BreadthParticipation"],
        inplace=True,
        errors="ignore",
    )

    numeric_cols = [col for col in out.columns if col not in {"Ticker", "Date"}]
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out[col] = out[col].fillna(0.0)
    return out


def _bucket_end_60m_from_15m(ts: pd.Series) -> pd.Series:
    ts = pd.to_datetime(ts, errors="coerce")
    return (ts - pd.Timedelta(minutes=15)).dt.floor("60min") + pd.Timedelta(minutes=15)


def _build_second_timeframe_aggregates(df_15m: pd.DataFrame) -> pd.DataFrame:
    if df_15m.empty or "Date" not in df_15m.columns:
        return pd.DataFrame()

    work = df_15m.copy()
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce")
    work = work.sort_values("Date").reset_index(drop=True)
    work["BucketEnd60m"] = _bucket_end_60m_from_15m(work["Date"])
    work["_ret1"] = pd.to_numeric(work.get("Close"), errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)

    rows = []
    eps = 1e-9
    for bucket_end, grp in work.groupby("BucketEnd60m", sort=True):
        grp = grp.sort_values("Date")
        first_open = float(pd.to_numeric(grp["Open"], errors="coerce").iloc[0]) if len(grp) else 0.0
        last_close = float(pd.to_numeric(grp["Close"], errors="coerce").iloc[-1]) if len(grp) else 0.0
        bucket_high = float(pd.to_numeric(grp["High"], errors="coerce").max()) if len(grp) else 0.0
        bucket_low = float(pd.to_numeric(grp["Low"], errors="coerce").min()) if len(grp) else 0.0
        bucket_high_idx = int(pd.to_numeric(grp["High"], errors="coerce").idxmax()) if len(grp) else -1
        bucket_low_idx = int(pd.to_numeric(grp["Low"], errors="coerce").idxmin()) if len(grp) else -1
        intrahour_ret = (last_close / max(first_open, eps)) - 1.0 if first_open > 0 else 0.0
        path_abs = float(pd.to_numeric(grp["_ret1"], errors="coerce").abs().sum())
        ret_sign = np.sign(pd.to_numeric(grp["_ret1"], errors="coerce").fillna(0.0))
        nonzero_sign = ret_sign[ret_sign != 0]
        sign_flip_count = int((nonzero_sign.diff().fillna(0).abs() > 0).sum()) if len(nonzero_sign) else 0
        positive_share = float((ret_sign > 0).mean()) if len(ret_sign) else 0.0
        negative_share = float((ret_sign < 0).mean()) if len(ret_sign) else 0.0
        half = max(1, len(grp) // 2)
        first_half = grp.iloc[:half]
        second_half = grp.iloc[half:]
        first_half_ret = (
            float(pd.to_numeric(first_half["Close"], errors="coerce").iloc[-1]) / max(first_open, eps) - 1.0
            if len(first_half) and first_open > 0
            else 0.0
        )
        second_half_open = float(pd.to_numeric(second_half["Open"], errors="coerce").iloc[0]) if len(second_half) else last_close
        second_half_ret = (
            last_close / max(second_half_open, eps) - 1.0
            if len(second_half) and second_half_open > 0
            else 0.0
        )
        last_quarter = grp.iloc[-1:] if len(grp) else grp
        last_quarter_open = float(pd.to_numeric(last_quarter["Open"], errors="coerce").iloc[0]) if len(last_quarter) else last_close
        last_quarter_ret = (
            last_close / max(last_quarter_open, eps) - 1.0
            if len(last_quarter) and last_quarter_open > 0
            else 0.0
        )
        late_strength_share = second_half_ret / max(abs(intrahour_ret), eps)
        last_quarter_share = last_quarter_ret / max(abs(intrahour_ret), eps)
        running_low = float(pd.to_numeric(grp["Low"], errors="coerce").min()) if len(grp) else first_open
        running_high = float(pd.to_numeric(grp["High"], errors="coerce").max()) if len(grp) else first_open
        max_adverse_excursion = (
            max(0.0, (first_open - running_low) / max(first_open, eps))
            if intrahour_ret >= 0
            else max(0.0, (running_high - first_open) / max(first_open, eps))
        )
        high_before_low = float(bucket_high_idx < bucket_low_idx) if bucket_high_idx >= 0 and bucket_low_idx >= 0 else 0.0
        low_before_high = float(bucket_low_idx < bucket_high_idx) if bucket_high_idx >= 0 and bucket_low_idx >= 0 else 0.0
        intrahour_rejection = (
            ((bucket_high - last_close) - (last_close - bucket_low)) / max(bucket_high - bucket_low, eps)
            if bucket_high > bucket_low
            else 0.0
        )
        early_vol = float(pd.to_numeric(first_half["_ret1"], errors="coerce").std(ddof=0)) if len(first_half) else 0.0
        late_vol = float(pd.to_numeric(second_half["_ret1"], errors="coerce").std(ddof=0)) if len(second_half) else 0.0
        time_imbalance = (
            (second_half_ret - first_half_ret) / max(abs(intrahour_ret), eps)
            if abs(intrahour_ret) > 0
            else 0.0
        )
        early_exhaustion_score = (
            first_half_ret - second_half_ret
            if np.sign(first_half_ret) == np.sign(intrahour_ret)
            else first_half_ret + second_half_ret
        )
        rows.append(
            {
                "Date": bucket_end,
                "STF15_IntrahourRet": intrahour_ret,
                "STF15_PathEfficiency": intrahour_ret / max(path_abs, eps),
                "STF15_FirstHalfRet": first_half_ret,
                "STF15_SecondHalfRet": second_half_ret,
                "STF15_FirstHalfShare": first_half_ret / max(abs(intrahour_ret), eps),
                "STF15_VolBurst": float(pd.to_numeric(grp["_ret1"], errors="coerce").std(ddof=0)),
                "STF15_RangeToOpen": (bucket_high - bucket_low) / max(first_open, eps) if first_open > 0 else 0.0,
                "STF15_FailedBreakoutScore": ((bucket_high - last_close) - (last_close - bucket_low)) / max(first_open, eps) if first_open > 0 else 0.0,
                "STF15_CloseLocation": (last_close - bucket_low) / max(bucket_high - bucket_low, eps),
                "STF15_RelVolumeMean": float(pd.to_numeric(grp.get("RelativeVolumeTime"), errors="coerce").fillna(0.0).mean()),
                "STF15_WickPressure": float((pd.to_numeric(grp.get("LowerWickRatio"), errors="coerce").fillna(0.0) - pd.to_numeric(grp.get("UpperWickRatio"), errors="coerce").fillna(0.0)).mean()),
                "STF15_BodyPressure": float((np.sign(pd.to_numeric(grp["Close"], errors="coerce") - pd.to_numeric(grp["Open"], errors="coerce")).fillna(0.0) * pd.to_numeric(grp.get("BodyToRange"), errors="coerce").fillna(0.0)).mean()),
                "STF15_BreakoutPressure": float(pd.to_numeric(grp.get("Breakout_3bar"), errors="coerce").fillna(0.0).mean()),
                "STF15_PositiveShare": positive_share,
                "STF15_NegativeShare": negative_share,
                "STF15_SignFlipRate": sign_flip_count / max(len(grp) - 1, 1),
                "STF15_LateStrengthShare": late_strength_share,
                "STF15_TimeImbalance": time_imbalance,
                "STF15_EarlyVol": early_vol,
                "STF15_LateVol": late_vol,
                "STF15_MaxAdverseExcursion": max_adverse_excursion,
                "STF15_HighBeforeLow": high_before_low,
                "STF15_LowBeforeHigh": low_before_high,
                "STF15_RejectionScore": intrahour_rejection,
                "STF15_LastQuarterRet": last_quarter_ret,
                "STF15_LastQuarterShare": last_quarter_share,
                "STF15_EarlyExhaustionScore": early_exhaustion_score,
                "STF15_CloseQuarterDominance": (last_quarter_ret - first_half_ret) / max(abs(intrahour_ret), eps),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values("Date").reset_index(drop=True)
    vol_base = pd.to_numeric(out["STF15_VolBurst"], errors="coerce").rolling(20, min_periods=5).mean().replace(0.0, np.nan)
    out["STF15_VolBurstRatio"] = (
        pd.to_numeric(out["STF15_VolBurst"], errors="coerce") / vol_base
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.0, 10.0)
    out["STF15_LateVolRatio"] = (
        pd.to_numeric(out["STF15_LateVol"], errors="coerce")
        / pd.to_numeric(out["STF15_EarlyVol"], errors="coerce").replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.0, 10.0)
    out.fillna(0.0, inplace=True)
    return out


def add_second_timeframe_context(
    df_60m: pd.DataFrame,
    instrument_token: int,
    history_days: int,
) -> pd.DataFrame:
    if df_60m.empty or "Date" not in df_60m.columns:
        return df_60m

    df_15m = get_data_kite(
        kite,
        instrument_token=instrument_token,
        days=history_days,
        interval="15minute",
        include_relative_context=True,
    )
    agg_15m = _build_second_timeframe_aggregates(df_15m)
    out = df_60m.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    if agg_15m.empty:
        for col in [
            "STF15_IntrahourRet", "STF15_PathEfficiency", "STF15_FirstHalfRet", "STF15_SecondHalfRet",
            "STF15_FirstHalfShare", "STF15_VolBurst", "STF15_VolBurstRatio", "STF15_RangeToOpen",
            "STF15_FailedBreakoutScore", "STF15_CloseLocation", "STF15_RelVolumeMean", "STF15_WickPressure",
            "STF15_BodyPressure", "STF15_BreakoutPressure", "STF15_PositiveShare", "STF15_NegativeShare",
            "STF15_SignFlipRate", "STF15_LateStrengthShare", "STF15_MaxAdverseExcursion",
            "STF15_HighBeforeLow", "STF15_LowBeforeHigh", "STF15_RejectionScore",
            "STF15_TimeImbalance", "STF15_EarlyVol", "STF15_LateVol", "STF15_LateVolRatio",
            "STF15_LastQuarterRet", "STF15_LastQuarterShare", "STF15_EarlyExhaustionScore",
            "STF15_CloseQuarterDominance",
        ]:
            out[col] = 0.0
        return out

    agg_15m["Date"] = pd.to_datetime(agg_15m["Date"], errors="coerce")
    out = pd.merge_asof(out.sort_values("Date"), agg_15m.sort_values("Date"), on="Date", direction="backward")
    stf_cols = [col for col in agg_15m.columns if col != "Date"]
    out[stf_cols] = out[stf_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return out


def compact_research_concat_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce per-ticker research frame memory before wide dataset assembly."""
    if df.empty:
        return df

    out = df.copy()
    bool_cols = out.select_dtypes(include=["bool"]).columns.tolist()
    if bool_cols:
        out[bool_cols] = out[bool_cols].astype(np.int8)

    int_cols = out.select_dtypes(include=["int", "int64", "Int64"]).columns.tolist()
    for col in int_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce", downcast="integer")

    float_cols = out.select_dtypes(include=["float", "float64", "Float64"]).columns.tolist()
    for col in float_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce", downcast="float")

    return out


def build_signal_research_dataset(
    ticker_list: List[str],
    instrument_df: pd.DataFrame,
    interval: str = "60minute",
    history_days: int = 1095,
    window_days: int = 20,
    include_second_timeframe_context: bool = False,
    out_csv: Optional[Path] = None,
) -> pd.DataFrame:
    frames = []
    for ticker in ticker_list:
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[SIGNAL DATASET] token missing for {ticker}, skipping.")
            continue

        df_ticker = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_ticker.empty:
            main_logger.warning(f"[SIGNAL DATASET] no data for {ticker}, skipping.")
            continue

        if interval == "60minute" and include_second_timeframe_context:
            df_ticker = add_second_timeframe_context(
                df_ticker,
                instrument_token=token,
                history_days=history_days,
            )
        df_ticker = assign_research_window_ids(df_ticker, interval=interval, window_days=window_days)
        df_ticker["Ticker"] = ticker
        frames.append(compact_research_concat_frame(df_ticker))

    dataset = pd.DataFrame()
    if frames:
        schema_cols: List[str] = []
        for frame in frames:
            for col in frame.columns:
                if col not in schema_cols:
                    schema_cols.append(col)
        aligned_frames = [
            compact_research_concat_frame(frame.reindex(columns=schema_cols))
            for frame in frames
        ]
        dataset = pd.concat(aligned_frames, ignore_index=True, sort=False, copy=False)
    if not dataset.empty:
        dataset = add_cross_sectional_research_features(dataset)
    if out_csv is not None and not dataset.empty:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        dataset.to_csv(out_csv, index=False)
        main_logger.info(f"[SIGNAL DATASET] saved research dataset to {out_csv}")
    return dataset


def run_signal_research_workflow(
    ticker_list: List[str],
    instrument_df: pd.DataFrame,
    interval: str = "60minute",
    history_days: int = 1095,
    window_days: int = 20,
    experiment_ids: Optional[List[str]] = None,
    experiment_set: str = "default",
    max_window_pairs: Optional[int] = None,
) -> pd.DataFrame:
    from signal_main import resolve_experiment_pool, run_signal_pipeline

    signal_dir = RESULTS_DIR / "signal_research"
    dataset_path = signal_dir / "research_dataset.csv"
    output_dir_name = "outputs"
    include_second_timeframe_context = False
    if experiment_set == "generalization":
        output_dir_name = "outputs_generalization"
        main_logger.info("[SIGNAL RESEARCH] E302 branch in broad generalization evaluation mode.")
    elif experiment_set == "generalization_next":
        output_dir_name = "outputs_generalization_next"
        main_logger.info(
            "[SIGNAL RESEARCH] Generalization-next discovery wave enabled. "
            "E102 and E302 are frozen benchmarks; RL integration is intentionally out of scope."
        )
    elif experiment_set == "generalization_wave2":
        output_dir_name = "outputs_generalization_wave2"
        main_logger.info(
            "[SIGNAL RESEARCH] Generalization wave 2 enabled. "
            "Following the productive T4/setup signal from wave 1, now testing session-isolated and setup-library families. "
            "E102/E302 remain frozen benchmarks and RL stays out of scope."
        )
    elif experiment_set == "e102_deepdive":
        output_dir_name = "outputs_e102_deepdive"
        main_logger.info(
            "[SIGNAL RESEARCH] E102 deep-dive enabled. "
            "Testing regime inclusion for volatility, session segment, and trend state while keeping the core E102 idea fixed."
        )
    elif experiment_set == "cross_sectional_60m":
        output_dir_name = "outputs_cross_sectional_60m"
        main_logger.info(
            "[SIGNAL RESEARCH] Cross-sectional 60m discovery enabled. "
            "E211 is frozen as the incumbent benchmark; this wave is baseline-first and RL stays out of scope."
        )
    elif experiment_set == "ablation_grid":
        output_dir_name = "outputs_ablation_grid"
        main_logger.info(
            "[SIGNAL RESEARCH] Formal ablation grid enabled. "
            "Testing targets and feature families systematically while E211 remains the frozen benchmark."
        )
    elif experiment_set == "setup_regimes":
        output_dir_name = "outputs_setup_regimes"
        main_logger.info(
            "[SIGNAL RESEARCH] Setup-regime discovery enabled. "
            "Testing regime-conditional setup families on 60m while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "market_state_60m":
        output_dir_name = "outputs_market_state_60m"
        main_logger.info(
            "[SIGNAL RESEARCH] Market-state 60m discovery enabled. "
            "Testing explicit market-state labels on top of 60m context while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "multiscale_60m":
        output_dir_name = "outputs_multiscale_60m"
        main_logger.info(
            "[SIGNAL RESEARCH] Multi-scale 60m discovery enabled. "
            "Testing multi-timescale context on top of the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "portfolio_rank_60m":
        output_dir_name = "outputs_portfolio_rank_60m"
        main_logger.info(
            "[SIGNAL RESEARCH] Portfolio-rank 60m discovery enabled. "
            "Testing universe-level cross-sectional ranking on the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "second_timeframe_60m":
        output_dir_name = "outputs_second_timeframe_60m"
        include_second_timeframe_context = True
        main_logger.info(
            "[SIGNAL RESEARCH] Second-timeframe 60m discovery enabled. "
            "Testing true 15m context on top of the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "intrahour_path_v1":
        output_dir_name = "outputs_intrahour_path_v1"
        include_second_timeframe_context = True
        main_logger.info(
            "[SIGNAL RESEARCH] Intrahour path v1 enabled. "
            "Testing true 15m path-structure information on top of the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "breadth_context_60m":
        output_dir_name = "outputs_breadth_context_60m"
        main_logger.info(
            "[SIGNAL RESEARCH] Breadth-context 60m discovery enabled. "
            "Testing universe breadth and internal market participation context on top of the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "time_distribution_v2":
        output_dir_name = "outputs_time_distribution_v2"
        include_second_timeframe_context = True
        main_logger.info(
            "[SIGNAL RESEARCH] Time-distribution v2 enabled. "
            "Testing early-vs-late intrahour information distribution on top of the 60m base while E211 remains the frozen benchmark and RL stays out of scope."
        )
    elif experiment_set == "native_15m_execution":
        output_dir_name = "outputs_native_15m_execution"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m execution enabled. "
            "Testing direct 15m signal discovery with 15m execution timing instead of compressing fast information back into the 60m decision layer."
        )
    elif experiment_set == "native_15m_failed_breakout":
        output_dir_name = "outputs_native_15m_failed_breakout"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m failed-breakout events enabled. "
            "Testing event-driven rejection and breakout-failure structures directly on 15m bars instead of another continuously scored continuation family."
        )
    elif experiment_set == "native_15m_open_drive":
        output_dir_name = "outputs_native_15m_open_drive"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m open-drive events enabled. "
            "Testing opening-range and open-drive event structures directly on 15m bars instead of another ported ranking family."
        )
    elif experiment_set == "opening_auction_gap_liquidity":
        output_dir_name = "outputs_opening_auction_gap_liquidity"
        main_logger.info(
            "[SIGNAL RESEARCH] Opening auction gap-liquidity thesis enabled. "
            "Testing only gap events where early participation and opening liquidity imply that follow-through can plausibly survive intraday costs."
        )
    elif experiment_set == "native_15m_session_phase":
        output_dir_name = "outputs_native_15m_session_phase"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m session-phase events enabled. "
            "Testing early, mid, and late-session event structures directly on 15m bars instead of another ported ranking family."
        )
    elif experiment_set == "native_15m_holding_horizon":
        output_dir_name = "outputs_native_15m_holding_horizon"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m holding-horizon experiments enabled. "
            "Testing whether the same 15m event quality only monetizes when matched to the correct forward holding horizon."
        )
    elif experiment_set == "native_15m_topk_event_rank":
        output_dir_name = "outputs_native_15m_topk_event_rank"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m top-k event rank enabled. "
            "Testing whether ranking only within strict favorable event slices improves absolute economics versus broad thresholding."
        )
    elif experiment_set == "native_15m_breadth_event":
        output_dir_name = "outputs_native_15m_breadth_event"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m breadth-event thesis enabled. "
            "Testing whether 15m market-internal breadth identifies favorable event states before ranking selective entries."
        )
    elif experiment_set == "native_15m_mean_reversion_exhaustion":
        output_dir_name = "outputs_native_15m_mean_reversion_exhaustion"
        main_logger.info(
            "[SIGNAL RESEARCH] Native 15m mean-reversion exhaustion enabled. "
            "Testing whether intraday exhaustion and rejection states define an economically favorable snapback slice before ranking."
        )
    elif experiment_set == "sixty_minute_daily_context":
        output_dir_name = "outputs_sixty_minute_daily_context"
        main_logger.info(
            "[SIGNAL RESEARCH] 60m plus daily-context thesis enabled. "
            "Testing whether explicit previous-session context improves 60m executable quality beyond the current intraday-only families."
        )
    elif experiment_set == "cross_sectional_commonality_residual":
        output_dir_name = "outputs_cross_sectional_commonality_residual"
        main_logger.info(
            "[SIGNAL RESEARCH] Cross-sectional commonality-residual thesis enabled. "
            "Testing whether stock-specific residual leadership after market and sector context defines a tradable 60m slice."
        )
    elif experiment_set == "intraday_volume_liquidity_forecast":
        output_dir_name = "outputs_intraday_volume_liquidity_forecast"
        include_second_timeframe_context = True
        main_logger.info(
            "[SIGNAL RESEARCH] Intraday volume-liquidity forecast thesis enabled. "
            "Testing whether 15m participation and liquidity state can isolate 60m slices that survive costs against the E211 benchmark."
        )
    elif experiment_set == "event_outcome_accounting":
        output_dir_name = "outputs_event_outcome_accounting"
        main_logger.info(
            "[SIGNAL RESEARCH] Event-outcome accounting thesis enabled. "
            "Testing event slices on whether target is reached before stop in the live trade direction, not on generic fixed-horizon return."
        )
    elif experiment_set == "all_15m":
        output_dir_name = "outputs_all_15m"
        main_logger.info(
            "[SIGNAL RESEARCH] Broad 15m sweep enabled. "
            "Testing the main experiment library directly on native 15m bars while excluding the 60m-only second-timeframe families."
        )
    elif experiment_set == "e302_sweep":
        output_dir_name = "outputs_e302"
        main_logger.info("[SIGNAL RESEARCH] E302 standalone evaluation mode enabled. RL integration for E302 is intentionally disabled for this phase.")
    elif experiment_set == "two_track":
        output_dir_name = "outputs_two_track"
    elif experiment_set == "focused":
        output_dir_name = "outputs_focused"
    dataset = build_signal_research_dataset(
        ticker_list=ticker_list,
        instrument_df=instrument_df,
        interval=interval,
        history_days=history_days,
        window_days=window_days,
        include_second_timeframe_context=include_second_timeframe_context,
        out_csv=dataset_path,
    )
    if dataset.empty:
        main_logger.warning("[SIGNAL RESEARCH] dataset is empty, skipping pipeline.")
        return pd.DataFrame()

    _, _, compare = run_signal_pipeline(
        df=dataset,
        out_dir=signal_dir / output_dir_name,
        experiments=resolve_experiment_pool(experiment_set),
        experiment_ids=experiment_ids,
        max_window_pairs=max_window_pairs,
    )
    main_logger.info(
        f"[SIGNAL RESEARCH] completed. promoted={int(compare.get('PromotedToRL', pd.Series(dtype=bool)).sum()) if not compare.empty else 0}"
    )
    return compare


def resolve_run_mode(default_mode: str = "walk_forward") -> str:
    return os.getenv("SSELL1_RUN_MODE", default_mode).strip().lower()


BEST_PARAMS_FILE = RESULTS_DIR / "best_params.joblib"
PARETO_TRIALS_FILE = RESULTS_DIR / "optuna_overlay_pareto_trials.csv"
PARETO_ALL_TRIALS_FILE = RESULTS_DIR / "optuna_overlay_all_trials.csv"
PARETO_SELECTED_FILE = RESULTS_DIR / "optuna_overlay_selected_trial.csv"
PARETO_SELECTED_ACTIVE_FILE = RESULTS_DIR / "optuna_overlay_selected_active_trial.csv"
OVERLAY_TUNE_TIMESTEPS = 20000
FIXED_OVERLAY_MAX_POSITION_SIZE = 0.50
FIXED_OVERLAY_TRADE_FRACTION = 0.25
FIXED_OVERLAY_REDUCE_FRACTION = 0.50
FOCUS_UNIVERSE_FILE = RESULTS_DIR / "focus_universe_latest.csv"
PINNED_FOCUS_UNIVERSE_FILE = RESULTS_DIR / "focus_universe_incumbent.csv"
FOCUS_MIN_RETURN = -0.001
FOCUS_MAX_TURNOVER = 0.25
FOCUS_REQUIRE_TRADES = True
FOCUS_TARGET_MIN_TICKERS = 8
FOCUS_TARGET_MAX_TICKERS = 10


def get_default_rl_params() -> dict:
    return {
        "learning_rate": 1e-4,
        "n_steps": 512,
        "batch_size": 64,
        "gamma": 0.99,
        "gae_lambda": 0.95,
        "clip_range": 0.2,
        "ent_coef": 0.01,
        "vf_coef": 0.5,
        "max_grad_norm": 0.5,
        "drawdown_penalty_factor": 0.01,
        "stop_loss": 0.90,
        "take_profit": 1.10,
        "reward_scale": 1.0,
        "max_position_size": 0.5,
        "max_drawdown": 0.20,
        "profit_weight": 1.5,
        "sharpe_bonus_weight": 0.05,
        "transaction_penalty_weight": 1.0,
        "holding_bonus_weight": 0.001,
        "volatility_threshold": 1.0,
        "momentum_threshold_min": 30.0,
        "momentum_threshold_max": 70.0,
        "hold_threshold": 0.08,
        "inference_buy_threshold": 0.08,
        "inference_sell_threshold": 0.08,
        "forced_stop_penalty_weight": 1.0,
        "forced_tp_penalty_weight": 1.0,
        "net_arch": "128_128",
    }


def load_saved_best_params() -> Optional[dict]:
    if not BEST_PARAMS_FILE.exists():
        return None
    try:
        params = joblib.load(BEST_PARAMS_FILE)
        if isinstance(params, dict) and params:
            main_logger.info(f"[RL PARAMS] loaded saved params from {BEST_PARAMS_FILE}")
            return params
    except Exception as exc:
        main_logger.warning(f"[RL PARAMS] failed to load {BEST_PARAMS_FILE}: {exc}")
    return None


def save_best_params(params: dict) -> None:
    try:
        joblib.dump(params, BEST_PARAMS_FILE)
        main_logger.info(f"[RL PARAMS] saved params to {BEST_PARAMS_FILE}")
    except Exception as exc:
        main_logger.warning(f"[RL PARAMS] failed to save {BEST_PARAMS_FILE}: {exc}")


def resolve_runtime_best_params(run_mode: str) -> dict:
    saved = load_saved_best_params()
    if saved:
        return saved
    defaults = get_default_rl_params()
    if run_mode in {"signal_baseline", "walk_forward", "experiment_suite"}:
        main_logger.warning("[RL PARAMS] no saved params found; using fixed defaults for direct execution mode.")
    return defaults


def _normalize_selection_series(values: list[float], higher_is_better: bool) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return np.asarray([], dtype=float)
    finite_mask = np.isfinite(arr)
    if not finite_mask.any():
        return np.zeros_like(arr, dtype=float)
    working = arr.copy()
    fallback = np.nanmin(working[finite_mask]) if higher_is_better else np.nanmax(working[finite_mask])
    working[~finite_mask] = fallback
    lo = np.min(working)
    hi = np.max(working)
    if abs(hi - lo) < 1e-12:
        norm = np.full_like(working, 0.5, dtype=float)
    else:
        norm = (working - lo) / (hi - lo)
    return norm if higher_is_better else (1.0 - norm)


def export_and_select_pareto_trials(study) -> Optional[dict]:
    rows = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE:
            continue
        values = list(trial.values) if trial.values is not None else [trial.value]
        rows.append(
            {
                "trial_number": trial.number,
                "values": values,
                "return_objective": values[0] if len(values) > 0 else np.nan,
                "drawdown_objective": values[1] if len(values) > 1 else np.nan,
                "turnover_objective": values[2] if len(values) > 2 else np.nan,
                "avg_sharpe": trial.user_attrs.get("avg_sharpe", np.nan),
                "avg_trade_count": trial.user_attrs.get("avg_trade_count", np.nan),
                "avg_networth_change": trial.user_attrs.get("avg_networth_change", np.nan),
                "avg_max_drawdown": trial.user_attrs.get("avg_max_drawdown", np.nan),
                "avg_turnover": trial.user_attrs.get("avg_turnover", np.nan),
                "avg_trade_count_raw": trial.user_attrs.get("avg_trade_count_raw", np.nan),
                "params": trial.params,
            }
        )
    if not rows:
        return None

    all_df = pd.DataFrame(rows)
    all_df.to_csv(PARETO_ALL_TRIALS_FILE, index=False)

    pareto_trials = [t for t in study.best_trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not pareto_trials:
        return None

    pareto_rows = [row for row in rows if row["trial_number"] in {t.number for t in pareto_trials}]
    pareto_df = pd.DataFrame(pareto_rows).copy()
    return_norm = _normalize_selection_series(pareto_df["return_objective"].tolist(), higher_is_better=True)
    dd_norm = _normalize_selection_series(pareto_df["drawdown_objective"].tolist(), higher_is_better=False)
    turnover_norm = _normalize_selection_series(pareto_df["turnover_objective"].tolist(), higher_is_better=False)
    sharpe_norm = _normalize_selection_series(pareto_df["avg_sharpe"].tolist(), higher_is_better=True)

    pareto_df["selection_score"] = (
        0.45 * return_norm
        + 0.25 * dd_norm
        + 0.20 * turnover_norm
        + 0.10 * sharpe_norm
    )
    pareto_df.sort_values(
        ["selection_score", "return_objective", "avg_sharpe"],
        ascending=[False, False, False],
        inplace=True,
    )
    pareto_df.to_csv(PARETO_TRIALS_FILE, index=False)

    selected_row = pareto_df.iloc[0].to_dict()
    pd.DataFrame([selected_row]).to_csv(PARETO_SELECTED_FILE, index=False)

    selected_trial = next((trial for trial in pareto_trials if trial.number == int(selected_row["trial_number"])), None)
    if selected_trial is None:
        return None
    main_logger.info(
        "[OPTUNA-MO] selected trial=%s return=%.6f drawdown=%.6f turnover=%.6f sharpe=%.6f selection_score=%.4f",
        selected_trial.number,
        float(selected_row["return_objective"]),
        float(selected_row["drawdown_objective"]),
        float(selected_row["turnover_objective"]),
        float(selected_row.get("avg_sharpe", np.nan)),
        float(selected_row["selection_score"]),
    )
    return selected_trial.params


def select_active_overlay_candidate(min_avg_trades: float = 5.0) -> Optional[dict]:
    if not PARETO_ALL_TRIALS_FILE.exists():
        main_logger.warning(f"[OPTUNA-MO] trial file not found: {PARETO_ALL_TRIALS_FILE}")
        return None
    try:
        df = pd.read_csv(PARETO_ALL_TRIALS_FILE)
    except Exception as exc:
        main_logger.warning(f"[OPTUNA-MO] failed to read {PARETO_ALL_TRIALS_FILE}: {exc}")
        return None
    if df.empty:
        return None

    active = df[df["avg_trade_count"].fillna(0.0) >= float(min_avg_trades)].copy()
    if active.empty:
        main_logger.warning(f"[OPTUNA-MO] no trials met active-trade floor {min_avg_trades:.1f}.")
        return None

    active.sort_values(
        ["return_objective", "drawdown_objective", "turnover_objective", "avg_sharpe"],
        ascending=[False, True, True, False],
        inplace=True,
    )
    selected_row = active.iloc[0].to_dict()
    pd.DataFrame([selected_row]).to_csv(PARETO_SELECTED_ACTIVE_FILE, index=False)

    params_raw = selected_row.get("params", "")
    if not isinstance(params_raw, str) or not params_raw.strip():
        main_logger.warning("[OPTUNA-MO] selected active trial does not contain params.")
        return None
    try:
        params = ast.literal_eval(params_raw)
    except Exception as exc:
        main_logger.warning(f"[OPTUNA-MO] failed to parse selected active params: {exc}")
        return None
    if not isinstance(params, dict) or not params:
        return None

    main_logger.info(
        "[OPTUNA-MO] active candidate trial=%s return=%.6f drawdown=%.6f turnover=%.6f sharpe=%.6f avg_trades=%.2f",
        int(selected_row["trial_number"]),
        float(selected_row["return_objective"]),
        float(selected_row["drawdown_objective"]),
        float(selected_row["turnover_objective"]),
        float(selected_row.get("avg_sharpe", np.nan)),
        float(selected_row.get("avg_trade_count", 0.0)),
    )
    return params

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

def _extract_vecenv_history(vec_env) -> tuple[list, dict]:
    final_metrics_list = vec_env.env_method("get_final_metrics")
    final_metrics = final_metrics_list[0] if final_metrics_list else {}
    history = final_metrics.get("history", []) if final_metrics else []
    if history:
        return history, final_metrics

    current_metrics_list = vec_env.env_method("get_current_metrics")
    current_metrics = current_metrics_list[0] if current_metrics_list else {}
    history = current_metrics.get("history", []) if current_metrics else []
    if history:
        return history, current_metrics

    histories = vec_env.get_attr("history")
    history = histories[0] if histories else []
    metrics = current_metrics if current_metrics else final_metrics
    return history, metrics

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
    eval_vec = DummyVecEnv([lambda: env_eval])
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

    history, metrics_source = _extract_vecenv_history(eval_vec)
    eval_vec.close()
    metrics = _compute_cycle_metrics(history, initial_balance)
    if not history:
        main_logger.warning(f"[WF:{ticker}:{eval_tag}] evaluation history is empty after fallback extraction.")
    main_logger.info(f"[WF:{ticker}:{eval_tag}] score={metrics['score']:.4f}, return={metrics['net_return']:.4f}, dd={metrics['max_drawdown']:.4f}, sharpe={metrics['sharpe']:.4f}, turnover={metrics['turnover']:.4f}, trades={metrics['trade_count']}")
    return {"history": history, "metrics": metrics, "source_metrics": metrics_source}

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
    train_timesteps: int = 50000,
    window_offset: int = 0,
    max_windows_per_ticker: int = 0,
    output_subdir: str = "walk_forward",
    slice_mode: str = "rolling",
    baseline_policy_name: Optional[str] = None,
    save_eval_histories: bool = False,
):
    wf_dir = RESULTS_DIR / output_subdir
    wf_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    compare_rows = []
    control_rows = []
    total_tickers = len(ticker_list)

    common_env_kwargs = {
        "stop_loss": best_params.get('stop_loss', stop_loss),
        "take_profit": best_params.get('take_profit', take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get('max_drawdown', max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get('drawdown_penalty_factor', 0.01),
        "hold_threshold": best_params.get('hold_threshold', 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
            "signal_gate_enabled": True,
            "signal_gate_source": "Signal_E211_Pred",
            "signal_gate_entry_threshold": 0.68,
            "signal_gate_reduce_threshold": 0.60,
            "signal_confirm_enabled": False,
            "signal_confirm_entry_threshold": 0.70,
            "signal_confirm_reduce_threshold": 0.58,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08)
    }
    gate_cfg = common_env_kwargs["reward_weights"]
    main_logger.info(
        "[WF] signal gate enabled=%s source=%s entry=%.2f reduce=%.2f",
        gate_cfg.get("signal_gate_enabled", False),
        gate_cfg.get("signal_gate_source", "Signal_E102_Pred"),
        float(gate_cfg.get("signal_gate_entry_threshold", 0.68)),
        float(gate_cfg.get("signal_gate_reduce_threshold", 0.60)),
    )
    print(
        f"[WF] signal gate enabled={gate_cfg.get('signal_gate_enabled', False)} "
        f"source={gate_cfg.get('signal_gate_source', 'Signal_E102_Pred')} "
        f"entry={float(gate_cfg.get('signal_gate_entry_threshold', 0.68)):.2f} "
        f"reduce={float(gate_cfg.get('signal_gate_reduce_threshold', 0.60)):.2f}"
    )
    main_logger.info(
        "[WF] signal confirm enabled=%s entry=%.2f reduce=%.2f",
        gate_cfg.get("signal_confirm_enabled", False),
        float(gate_cfg.get("signal_confirm_entry_threshold", 0.70)),
        float(gate_cfg.get("signal_confirm_reduce_threshold", 0.58)),
    )
    print(
        f"[WF] signal confirm enabled={gate_cfg.get('signal_confirm_enabled', False)} "
        f"entry={float(gate_cfg.get('signal_confirm_entry_threshold', 0.70)):.2f} "
        f"reduce={float(gate_cfg.get('signal_confirm_reduce_threshold', 0.58)):.2f}"
    )
    main_logger.info("[WF] E302 remains available to the policy as observation features; confirmation gate is soft-disabled.")
    print("[WF] E302 remains available to the policy as observation features; confirmation gate is soft-disabled.")

    for ticker_idx, ticker in enumerate(ticker_list, start=1):
        print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[WF:{ticker}] token missing, skipping.")
            print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (token missing)")
            continue

        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            main_logger.warning(f"[WF:{ticker}] no data, skipping.")
            print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (no data)")
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days
            ,
            train_mode=slice_mode,
        )
        if window_offset > 0:
            windows = windows[window_offset:]
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        if not windows:
            main_logger.warning(
                f"[WF:{ticker}] not enough rows ({len(df_full)}) for requested walk-forward windows "
                f"(offset={window_offset}, max={max_windows_per_ticker})."
            )
            print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (insufficient rows for requested window)")
            continue

        ticker_best_score = -np.inf
        ticker_best_model = None
        ticker_best_norm = None
        print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - {len(windows)} cycle(s)")

        for cycle_idx, (s, tr_end, va_end, te_end) in enumerate(windows, start=1):
            train_df = df_full.iloc[s:tr_end].reset_index(drop=True)
            val_df = df_full.iloc[tr_end:va_end].reset_index(drop=True)
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if train_df.empty or val_df.empty or test_df.empty:
                print(f"[WF] {ticker} cycle {cycle_idx}/{len(windows)} - skipped (empty split)")
                continue

            print(
                f"[WF] {ticker} cycle {cycle_idx}/{len(windows)} - "
                f"train {len(train_df)} / val {len(val_df)} / test {len(test_df)}"
            )

            env_train = SingleStockTradingEnv(
                df=train_df,
                ticker=ticker,
                initial_balance=initial_balance,
                max_episode_steps=len(train_df),
                mode="train",
                env_rank=cycle_idx,
                **common_env_kwargs
            )
            vec_train = DummyVecEnv([lambda e=env_train: e])
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
            print(f"[WF] {ticker} cycle {cycle_idx}/{len(windows)} - training complete")

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
            if save_eval_histories:
                val_hist_df = _save_history_csv(val_eval["history"], cycle_dir / "history_val.csv")
                test_hist_df = _save_history_csv(test_eval["history"], cycle_dir / "history_test.csv")
            else:
                val_hist_df = pd.DataFrame(val_eval["history"])
                test_hist_df = pd.DataFrame(test_eval["history"])
            val_control = summarize_control_history(val_hist_df)
            test_control = summarize_control_history(test_hist_df)
            print(
                f"[WF] {ticker} cycle {cycle_idx}/{len(windows)} - "
                f"val score {val_metrics['score']:.4f}, test score {test_metrics['score']:.4f}, "
                f"test return {test_metrics['net_return']:.4f}"
            )
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
                "slice_mode": slice_mode,
                "model_path": str(model_path),
                "vecnorm_path": str(vecnorm_path)
            }
            all_rows.append(row)
            control_rows.append({
                "ticker": ticker,
                "cycle": cycle_idx,
                "split": "val",
                "slice_mode": slice_mode,
                **val_control,
            })
            control_rows.append({
                "ticker": ticker,
                "cycle": cycle_idx,
                "split": "test",
                "slice_mode": slice_mode,
                **test_control,
            })

            if baseline_policy_name:
                val_baseline = run_baseline_backtest(
                    val_df,
                    ticker,
                    initial_balance,
                    common_env_kwargs,
                    baseline_policy_name,
                    seed=RANDOM_SEED + cycle_idx,
                )
                test_baseline = run_baseline_backtest(
                    test_df,
                    ticker,
                    initial_balance,
                    common_env_kwargs,
                    baseline_policy_name,
                    seed=RANDOM_SEED + 1000 + cycle_idx,
                )
                if save_eval_histories:
                    _save_history_csv(val_baseline["history"], cycle_dir / f"baseline_{baseline_policy_name}_val.csv")
                    _save_history_csv(test_baseline["history"], cycle_dir / f"baseline_{baseline_policy_name}_test.csv")
                baseline_val_metrics = val_baseline["metrics"]
                baseline_test_metrics = test_baseline["metrics"]
                compare_rows.append({
                    "ticker": ticker,
                    "cycle": cycle_idx,
                    "slice_mode": slice_mode,
                    "baseline_policy": baseline_policy_name,
                    "rl_val_return": val_metrics["net_return"],
                    "rl_test_return": test_metrics["net_return"],
                    "rl_test_turnover": test_metrics["turnover"],
                    "rl_test_trades": test_metrics["trade_count"],
                    "baseline_val_return": baseline_val_metrics["total_return"],
                    "baseline_test_return": baseline_test_metrics["total_return"],
                    "baseline_test_turnover": baseline_test_metrics["turnover"],
                    "baseline_test_trades": baseline_test_metrics["trade_count"],
                    "excess_return": test_metrics["net_return"] - baseline_test_metrics["total_return"],
                })

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
            print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - approved score {ticker_best_score:.4f}")
        else:
            print(f"[WF] ticker {ticker_idx}/{total_tickers}: {ticker} - no approved cycle")

    if all_rows:
        wf_df = pd.DataFrame(all_rows)
        wf_csv = wf_dir / "walk_forward_summary.csv"
        wf_df.to_csv(wf_csv, index=False)
        main_logger.info(f"[WF] summary saved: {wf_csv}")
        print(f"[WF] summary saved: {wf_csv}")
        if control_rows:
            control_df = pd.DataFrame(control_rows)
            control_csv = wf_dir / "walk_forward_control_summary.csv"
            control_df.to_csv(control_csv, index=False)
            main_logger.info(f"[WF] control summary saved: {control_csv}")
            test_control_df = control_df.loc[control_df["split"] == "test"].copy()
            if not test_control_df.empty:
                control_stats = (
                    test_control_df.groupby("ticker")[
                        [
                            "long_actions",
                            "short_actions",
                            "reduce_actions",
                            "hold_actions",
                            "signal_gate_holds",
                            "signal_confirm_holds",
                            "vol_holds",
                            "style_holds",
                            "forced_stop_events",
                            "forced_tp_events",
                            "long_position_bars",
                            "short_position_bars",
                            "flat_bars",
                            "control_event_rate",
                        ]
                    ]
                    .mean()
                    .reset_index()
                )
                total_row = {"ticker": "ALL"}
                for col in control_stats.columns:
                    if col == "ticker":
                        continue
                    total_row[col] = float(pd.to_numeric(control_stats[col], errors="coerce").mean())
                control_stats = pd.concat([control_stats, pd.DataFrame([total_row])], ignore_index=True)
                control_stats_csv = wf_dir / "walk_forward_control_stats.csv"
                control_stats.to_csv(control_stats_csv, index=False)
                main_logger.info(f"[WF] control stats saved: {control_stats_csv}")
        if compare_rows:
            compare_df = pd.DataFrame(compare_rows)
            compare_csv = wf_dir / "walk_forward_baseline_compare.csv"
            compare_df.to_csv(compare_csv, index=False)
            ticker_compare = (
                compare_df.groupby("ticker")[
                    [
                        "rl_test_return",
                        "baseline_test_return",
                        "excess_return",
                        "rl_test_turnover",
                        "baseline_test_turnover",
                        "rl_test_trades",
                        "baseline_test_trades",
                    ]
                ]
                .mean()
                .reset_index()
                .sort_values("excess_return", ascending=False)
            )
            ticker_compare_csv = wf_dir / "walk_forward_baseline_compare_by_ticker.csv"
            ticker_compare.to_csv(ticker_compare_csv, index=False)
            stats_df = _build_rl_vs_baseline_stats(compare_df, group_label=f"{output_subdir}_{slice_mode}")
            if not stats_df.empty:
                stats_csv = wf_dir / "walk_forward_stats_report.csv"
                stats_df.to_csv(stats_csv, index=False)
                main_logger.info(f"[WF] stats report saved: {stats_csv}")
                stats_row = stats_df.iloc[0].to_dict()
                main_logger.info(
                    "[WF] stats summary: mean_rl=%.6f mean_baseline=%.6f mean_excess=%.6f hit_rate=%.2f t_stat=%.3f",
                    float(stats_row.get("mean_rl_return", 0.0)),
                    float(stats_row.get("mean_baseline_return", 0.0)),
                    float(stats_row.get("mean_excess_return", 0.0)),
                    float(stats_row.get("hit_rate_vs_baseline", 0.0)),
                    float(stats_row.get("excess_t_stat", 0.0)),
                )
    else:
        main_logger.warning("[WF] no cycles produced results.")
        print("[WF] no cycles produced results.")

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


def summarize_control_history(history_df: pd.DataFrame) -> Dict[str, float]:
    if history_df.empty:
        return {
            "long_actions": 0,
            "short_actions": 0,
            "reduce_actions": 0,
            "hold_actions": 0,
            "signal_gate_holds": 0,
            "signal_confirm_holds": 0,
            "vol_holds": 0,
            "style_holds": 0,
            "forced_stop_events": 0,
            "forced_tp_events": 0,
            "long_position_bars": 0,
            "short_position_bars": 0,
            "flat_bars": 0,
            "control_event_rate": 0.0,
        }
    out = history_df.copy()
    action_series = pd.to_numeric(out.get("Action", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(int)
    action_name = out.get("ActionName", pd.Series(dtype=str)).fillna("").astype(str)
    position = pd.to_numeric(out.get("Position", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    forced_stop_penalty = pd.to_numeric(out.get("forced_stop_penalty", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    forced_tp_penalty = pd.to_numeric(out.get("forced_tp_penalty", pd.Series(dtype=float)), errors="coerce").fillna(0.0)

    signal_gate_holds = int(action_name.str.contains("signal_gate", regex=False).sum())
    signal_confirm_holds = int(action_name.str.contains("signal_confirm", regex=False).sum())
    vol_holds = int(action_name.str.contains("vol_hold", regex=False).sum())
    style_holds = int(action_name.str.contains("style_hold", regex=False).sum())
    forced_stop_events = int((forced_stop_penalty < 0).sum())
    forced_tp_events = int((forced_tp_penalty < 0).sum())
    control_events = signal_gate_holds + signal_confirm_holds + vol_holds + style_holds + forced_stop_events + forced_tp_events
    row_count = max(1, len(out))
    return {
        "long_actions": int((action_series == 1).sum()),
        "short_actions": int((action_series == 2).sum()),
        "reduce_actions": int((action_series == 3).sum()),
        "hold_actions": int((action_series == 0).sum()),
        "signal_gate_holds": signal_gate_holds,
        "signal_confirm_holds": signal_confirm_holds,
        "vol_holds": vol_holds,
        "style_holds": style_holds,
        "forced_stop_events": forced_stop_events,
        "forced_tp_events": forced_tp_events,
        "long_position_bars": int((position > 0).sum()),
        "short_position_bars": int((position < 0).sum()),
        "flat_bars": int((position == 0).sum()),
        "control_event_rate": float(control_events / row_count),
    }


def _save_history_csv(history: list | pd.DataFrame, out_path: Path) -> pd.DataFrame:
    hist_df = history.copy() if isinstance(history, pd.DataFrame) else pd.DataFrame(history)
    hist_df.to_csv(out_path, index=False)
    return hist_df


def _bootstrap_mean_ci(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = RANDOM_SEED) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = rng.choice(arr, size=arr.size, replace=True)
        means[i] = float(np.mean(sample))
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return (lo, hi)


def _build_rl_vs_baseline_stats(compare_df: pd.DataFrame, group_label: str) -> pd.DataFrame:
    if compare_df.empty:
        return pd.DataFrame()
    df = compare_df.copy()
    for col in ["rl_test_return", "baseline_test_return", "excess_return"]:
        df[col] = pd.to_numeric(df.get(col, pd.Series(dtype=float)), errors="coerce")
    df = df[np.isfinite(df["rl_test_return"]) & np.isfinite(df["baseline_test_return"])].copy()
    if df.empty:
        return pd.DataFrame()
    df["excess_return"] = df["rl_test_return"] - df["baseline_test_return"]
    excess = df["excess_return"].to_numpy(dtype=float)
    rl_returns = df["rl_test_return"].to_numpy(dtype=float)
    baseline_returns = df["baseline_test_return"].to_numpy(dtype=float)
    wins = int((excess > 0).sum())
    losses = int((excess < 0).sum())
    ties = int((np.isclose(excess, 0.0)).sum())
    positive_excess = df.loc[df["excess_return"] > 0].groupby("ticker")["excess_return"].sum().sort_values(ascending=False)
    top_ticker = positive_excess.index[0] if not positive_excess.empty else ""
    top_share = float((positive_excess.iloc[0] / positive_excess.sum()) if (not positive_excess.empty and positive_excess.sum() != 0) else 0.0)
    std_excess = float(np.std(excess, ddof=1)) if len(excess) > 1 else 0.0
    mean_excess = float(np.mean(excess))
    t_stat = float(mean_excess / (std_excess / np.sqrt(len(excess)))) if len(excess) > 1 and std_excess > 0 else 0.0
    z_like = float(mean_excess / std_excess) if std_excess > 0 else 0.0
    ci_lo, ci_hi = _bootstrap_mean_ci(excess, n_boot=2000) if len(excess) >= 3 else (mean_excess, mean_excess)
    row = {
        "group": group_label,
        "n_rows": int(len(df)),
        "n_tickers": int(df["ticker"].nunique()),
        "mean_rl_return": float(np.mean(rl_returns)),
        "median_rl_return": float(np.median(rl_returns)),
        "var_rl_return": float(np.var(rl_returns, ddof=1)) if len(rl_returns) > 1 else 0.0,
        "mean_baseline_return": float(np.mean(baseline_returns)),
        "median_baseline_return": float(np.median(baseline_returns)),
        "mean_excess_return": mean_excess,
        "median_excess_return": float(np.median(excess)),
        "var_excess_return": float(np.var(excess, ddof=1)) if len(excess) > 1 else 0.0,
        "hit_rate_vs_baseline": float(wins / len(df)),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "ticker_win_rate": float(df.groupby("ticker")["excess_return"].mean().gt(0).mean()),
        "top_positive_excess_ticker": top_ticker,
        "top_positive_excess_share": top_share,
        "excess_t_stat": t_stat,
        "excess_z_like": z_like,
        "bootstrap_mean_excess_ci_low": ci_lo,
        "bootstrap_mean_excess_ci_high": ci_hi,
    }
    return pd.DataFrame([row])

def _signal_rule_direction(row: pd.Series) -> int:
    trend_30 = float(row.get("Trend_30", 0.0))
    trend_2h = float(row.get("Trend_2h", 0.0))
    rel_1 = float(row.get("StockMinusMkt_1", 0.0))
    rel_3 = float(row.get("StockMinusMkt_3", 0.0))
    breakout = float(row.get("Breakout_3bar", 0.0))
    persistence = float(row.get("SignPersistence_5", 0.0))
    score = (
        1.5 * trend_30
        + 1.0 * trend_2h
        + 2.0 * rel_3
        + 1.0 * rel_1
        + 0.75 * breakout
        + 0.50 * persistence
    )
    if score > 0.001:
        return 1
    if score < -0.001:
        return -1
    return 0

def _parse_signal_banded_threshold(policy_name: str) -> Optional[tuple[float, float]]:
    if policy_name == "SIGNAL_E102_BANDED":
        return (0.60, 0.52)
    prefix = "SIGNAL_E102_BANDED_"
    if not policy_name.startswith(prefix):
        return None
    suffix = policy_name[len(prefix):]
    if not suffix.isdigit():
        return None
    entry_threshold = float(int(suffix)) / 100.0
    reduce_threshold = max(0.50, entry_threshold - 0.08)
    return (entry_threshold, reduce_threshold)


def _parse_signal_banded_threshold_for_prefix(policy_name: str, prefix_root: str) -> Optional[tuple[float, float]]:
    base_name = f"{prefix_root}_BANDED"
    if policy_name == base_name:
        return (0.60, 0.52)
    prefix = f"{prefix_root}_BANDED_"
    if not policy_name.startswith(prefix):
        return None
    suffix = policy_name[len(prefix):]
    if not suffix.isdigit():
        return None
    entry_threshold = float(int(suffix)) / 100.0
    reduce_threshold = max(0.50, entry_threshold - 0.08)
    return (entry_threshold, reduce_threshold)


def _parse_combo_banded_threshold(policy_name: str) -> Optional[tuple[float, float, float]]:
    if policy_name == "SIGNAL_COMBO_E102_E302_BANDED":
        return (0.68, 0.70, 0.56)
    prefix = "SIGNAL_COMBO_E102_E302_BANDED_"
    if not policy_name.startswith(prefix):
        return None
    suffix = policy_name[len(prefix):]
    if not suffix.isdigit():
        return None
    primary_entry = float(int(suffix)) / 100.0
    secondary_entry = min(0.90, primary_entry + 0.02)
    reduce_threshold = max(0.50, primary_entry - 0.12)
    return (primary_entry, secondary_entry, reduce_threshold)


def _signal_policy_action(
    policy_name: str,
    row: pd.Series,
    pred_col: str,
    base_name: str,
) -> Optional[int]:
    banded_thresholds = _parse_signal_banded_threshold_for_prefix(policy_name, base_name)
    pred = float(row.get(pred_col, 0.5))
    direction = _signal_rule_direction(row)
    if policy_name == base_name:
        if pred >= 0.56 and direction > 0:
            return 1
        if pred >= 0.56 and direction < 0:
            return 2
        if pred < 0.49:
            return 3
        return 0
    if banded_thresholds is not None:
        entry_threshold, reduce_threshold = banded_thresholds
        if pred >= entry_threshold and direction > 0:
            return 1
        if pred >= entry_threshold and direction < 0:
            return 2
        if pred < reduce_threshold:
            return 3
        return 0
    if policy_name == f"{base_name}_LONGONLY":
        trend_bias = float(row.get("Trend_30", 0.0)) + 0.5 * float(row.get("Trend_2h", 0.0))
        if pred >= 0.54 and trend_bias >= -0.002:
            return 1
        if pred < 0.49:
            return 3
        return 0
    if policy_name == f"{base_name}_SYMMETRIC":
        if pred >= 0.53:
            if direction >= 0:
                return 1
            return 2
        if pred <= 0.47:
            return 3
        return 0
    return None


def _intrahour_veto_active(row: pd.Series) -> bool:
    rejection = float(row.get("STF15_RejectionScore", 0.0))
    sign_flip = float(row.get("STF15_SignFlipRate", 0.0))
    path_eff = float(row.get("STF15_PathEfficiency", 0.0))
    late_strength = float(row.get("STF15_LateStrengthShare", 0.0))
    early_exhaustion = float(row.get("STF15_EarlyExhaustionScore", 0.0))
    time_imbalance = float(row.get("STF15_TimeImbalance", 0.0))
    veto_votes = 0
    veto_votes += int(rejection <= -0.20)
    veto_votes += int(sign_flip >= 0.60)
    veto_votes += int(path_eff <= 0.15)
    veto_votes += int(late_strength <= -0.15)
    veto_votes += int(early_exhaustion >= 0.003)
    veto_votes += int(time_imbalance <= -0.20)
    return veto_votes >= 2

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
    combo_thresholds = _parse_combo_banded_threshold(policy_name)
    if combo_thresholds is not None:
        pred_e102 = float(row.get("Signal_E102_Pred", 0.5))
        pred_e302 = float(row.get("Signal_E302_Pred", 0.5))
        direction = _signal_rule_direction(row)
        entry_e102, entry_e302, reduce_threshold = combo_thresholds
        if pred_e102 >= entry_e102 and pred_e302 >= entry_e302 and direction > 0:
            return 1
        if pred_e102 >= entry_e102 and pred_e302 >= entry_e302 and direction < 0:
            return 2
        if max(pred_e102, pred_e302) < reduce_threshold:
            return 3
        return 0
    if policy_name == "SIGNAL_E211_VETO_INTRAHOUR":
        pred = float(row.get("Signal_E211_Pred", 0.5))
        direction = _signal_rule_direction(row)
        veto_active = _intrahour_veto_active(row)
        if pred >= 0.68 and direction > 0 and not veto_active:
            return 1
        if pred >= 0.68 and direction < 0 and not veto_active:
            return 2
        if pred < 0.60 or veto_active:
            return 3
        return 0
    overlay_cfg = EVENT_CONDITIONED_SIZING_VETO_POLICY_CONFIGS.get(policy_name)
    if overlay_cfg is not None:
        pred = float(row.get("Signal_E211_Pred", 0.5))
        direction = _signal_rule_direction(row)
        primary_experiment = str(overlay_cfg["primary_experiment"])
        primary_col = f"{SIGNAL_OVERLAY_SOURCES[primary_experiment][1]}_Pred"
        overlay_ok = float(row.get(primary_col, 0.5)) >= float(overlay_cfg["primary_threshold"])
        secondary_experiment = overlay_cfg.get("secondary_experiment")
        if secondary_experiment:
            secondary_experiment = str(secondary_experiment)
            secondary_col = f"{SIGNAL_OVERLAY_SOURCES[secondary_experiment][1]}_Pred"
            overlay_ok = overlay_ok and (
                float(row.get(secondary_col, 0.5)) >= float(overlay_cfg["secondary_threshold"])
            )
        if pred >= 0.68 and direction > 0 and overlay_ok:
            return 1
        if pred >= 0.68 and direction < 0 and overlay_ok:
            return 2
        if pred < 0.60 or not overlay_ok:
            return 3
        return 0
    for _, (_, signal_prefix) in SIGNAL_OVERLAY_SOURCES.items():
        base_name = signal_prefix.replace("Signal_", "SIGNAL_")
        pred_col = f"{signal_prefix}_Pred"
        signal_action = _signal_policy_action(policy_name, row, pred_col, base_name)
        if signal_action is not None:
            return signal_action
    return 0

def run_baseline_backtest(
    df_slice: pd.DataFrame,
    ticker: str,
    initial_balance: float,
    env_kwargs: dict,
    policy_name: str,
    seed: int = 42,
    env_overrides: Optional[dict] = None,
) -> Dict[str, object]:
    local_env_kwargs = copy.deepcopy(env_kwargs)
    if env_overrides:
        local_env_kwargs.update(copy.deepcopy(env_overrides))
    if policy_name.startswith("SIGNAL_E") or policy_name.startswith("SIGNAL_COMBO_E102_E302"):
        reward_weights = dict(local_env_kwargs.get("reward_weights", {}))
        reward_weights["regime_gate_min_confidence"] = min(float(reward_weights.get("regime_gate_min_confidence", 0.60)), 0.45)
        reward_weights["regime_gate_min_confirmations"] = 1
        reward_weights["reversion_gate_min_confidence"] = min(float(reward_weights.get("reversion_gate_min_confidence", 0.55)), 0.45)
        reward_weights["reversion_gate_min_confirmations"] = 1
        reward_weights["min_market_vol_rank"] = 0.0
        reward_weights["trade_fraction"] = max(float(reward_weights.get("trade_fraction", 0.25)), 0.35)
        reward_weights["reduce_fraction"] = max(float(reward_weights.get("reduce_fraction", 0.50)), 0.60)
        local_env_kwargs["reward_weights"] = reward_weights
    env = SingleStockTradingEnv(
        df=df_slice.reset_index(drop=True),
        ticker=ticker,
        initial_balance=initial_balance,
        max_episode_steps=len(df_slice),
        mode="test",
        env_rank=0,
        **local_env_kwargs
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


def _extract_e211_entry_records(
    history_df: pd.DataFrame,
    ticker: str,
    cycle_idx: int,
    split_name: str,
    initial_balance: float,
) -> List[Dict[str, object]]:
    if history_df.empty:
        return []
    h = history_df.copy().reset_index(drop=True)
    position = pd.to_numeric(h.get("Position", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    net_worth = pd.to_numeric(h.get("Full Worth", h.get("Net Worth", pd.Series(dtype=float))), errors="coerce").fillna(method="ffill")
    close = pd.to_numeric(h.get("Close", pd.Series(dtype=float)), errors="coerce")
    prev_position = position.shift(1, fill_value=0.0)
    prev_sign = np.sign(prev_position)
    curr_sign = np.sign(position)
    entry_mask = (
        (prev_sign == 0) & (curr_sign != 0)
    ) | (
        (prev_sign != 0) & (curr_sign != 0) & (prev_sign != curr_sign)
    )
    entry_indices = [int(idx) for idx in np.flatnonzero(entry_mask.to_numpy())]
    records: List[Dict[str, object]] = []
    feature_cols = [
        "Signal_E211_Pred",
        "Trend_30",
        "Trend_2h",
        "StockMinusMkt_1",
        "StockMinusMkt_3",
        "STF15_PathEfficiency",
        "STF15_SignFlipRate",
        "STF15_RejectionScore",
        "STF15_LateStrengthShare",
        "STF15_EarlyExhaustionScore",
        "STF15_TimeImbalance",
        "STF15_FailedBreakoutScore",
        "STF15_MaxAdverseExcursion",
        "STF15_HighBeforeLow",
        "STF15_LowBeforeHigh",
        "STF15_LastQuarterShare",
    ]
    for entry_idx in entry_indices:
        direction = int(np.sign(position.iloc[entry_idx]))
        if direction == 0:
            continue
        exit_idx = len(h) - 1
        for look_ahead in range(entry_idx + 1, len(h)):
            next_sign = int(np.sign(position.iloc[look_ahead]))
            if next_sign == 0 or next_sign != direction:
                exit_idx = look_ahead
                break
        entry_close = float(close.iloc[entry_idx]) if pd.notna(close.iloc[entry_idx]) else np.nan
        exit_close = float(close.iloc[exit_idx]) if pd.notna(close.iloc[exit_idx]) else np.nan
        entry_worth = float(net_worth.iloc[entry_idx]) if pd.notna(net_worth.iloc[entry_idx]) else np.nan
        exit_worth = float(net_worth.iloc[exit_idx]) if pd.notna(net_worth.iloc[exit_idx]) else np.nan
        pnl_abs = exit_worth - entry_worth
        price_move = np.nan
        if pd.notna(entry_close) and entry_close != 0 and pd.notna(exit_close):
            price_move = direction * (exit_close / entry_close - 1.0)
        row = h.iloc[entry_idx]
        record: Dict[str, object] = {
            "ticker": ticker,
            "cycle": cycle_idx,
            "split": split_name,
            "entry_idx": entry_idx,
            "exit_idx": exit_idx,
            "entry_date": row.get("Date"),
            "exit_date": h.iloc[exit_idx].get("Date"),
            "direction": "long" if direction > 0 else "short",
            "entry_action": row.get("ActionName", ""),
            "hold_bars": int(exit_idx - entry_idx),
            "entry_close": entry_close,
            "exit_close": exit_close,
            "entry_net_worth": entry_worth,
            "exit_net_worth": exit_worth,
            "trade_pnl_abs": pnl_abs,
            "trade_pnl_pct_initial": float(pnl_abs / initial_balance) if initial_balance else np.nan,
            "trade_price_move": price_move,
            "outcome": "win" if pnl_abs > 0 else ("loss" if pnl_abs < 0 else "flat"),
            "intrahour_veto_v1_active": _intrahour_veto_active(row),
        }
        for col in feature_cols:
            record[col] = float(pd.to_numeric(pd.Series([row.get(col, np.nan)]), errors="coerce").iloc[0]) if pd.notna(row.get(col, np.nan)) else np.nan
        records.append(record)
    return records


def run_e211_entry_audit(
    ticker_list: List[str],
    instrument_df: pd.DataFrame,
    best_params: dict,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
    interval: str,
    history_days: int = 1095,
    train_days: int = 730,
    val_days: int = 90,
    test_days: int = 30,
    step_days: int = 30,
    max_windows_per_ticker: int = 1,
) -> Dict[str, pd.DataFrame]:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    env_kwargs = {
        "stop_loss": best_params.get("stop_loss", stop_loss),
        "take_profit": best_params.get("take_profit", take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
        "hold_threshold": best_params.get("hold_threshold", 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
    }
    entry_rows: List[Dict[str, object]] = []
    cycle_rows: List[Dict[str, object]] = []
    total_tickers = len(ticker_list)
    for ticker_idx, ticker in enumerate(ticker_list, start=1):
        print(f"[E211 AUDIT] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            continue
        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days,
        )
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        for cycle_idx, (_, tr_end, va_end, te_end) in enumerate(windows, start=1):
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if test_df.empty:
                continue
            test_res = run_baseline_backtest(
                test_df,
                ticker,
                initial_balance,
                env_kwargs,
                "SIGNAL_E211_BANDED_68",
                seed=RANDOM_SEED + 1000 + cycle_idx,
            )
            history = test_res["history"]
            entries = _extract_e211_entry_records(
                history_df=history,
                ticker=ticker,
                cycle_idx=cycle_idx,
                split_name="test",
                initial_balance=initial_balance,
            )
            entry_rows.extend(entries)
            cycle_rows.append(
                {
                    "ticker": ticker,
                    "cycle": cycle_idx,
                    "entries": len(entries),
                    "wins": int(sum(1 for row in entries if row["outcome"] == "win")),
                    "losses": int(sum(1 for row in entries if row["outcome"] == "loss")),
                    "flats": int(sum(1 for row in entries if row["outcome"] == "flat")),
                    "veto_hits": int(sum(1 for row in entries if bool(row["intrahour_veto_v1_active"]))),
                    "mean_trade_pnl_pct_initial": float(np.mean([row["trade_pnl_pct_initial"] for row in entries])) if entries else 0.0,
                    "mean_hold_bars": float(np.mean([row["hold_bars"] for row in entries])) if entries else 0.0,
                }
            )
            print(
                f"[E211 AUDIT] {ticker} cycle {cycle_idx}/{len(windows)} - "
                f"entries {len(entries)}, wins {cycle_rows[-1]['wins']}, losses {cycle_rows[-1]['losses']}, veto_hits {cycle_rows[-1]['veto_hits']}"
            )

    detail_df = pd.DataFrame(entry_rows)
    cycle_df = pd.DataFrame(cycle_rows)
    summary_rows: List[Dict[str, object]] = []
    feature_diff_rows: List[Dict[str, object]] = []
    if not detail_df.empty:
        numeric_feature_cols = [
            "Signal_E211_Pred",
            "Trend_30",
            "Trend_2h",
            "StockMinusMkt_1",
            "StockMinusMkt_3",
            "STF15_PathEfficiency",
            "STF15_SignFlipRate",
            "STF15_RejectionScore",
            "STF15_LateStrengthShare",
            "STF15_EarlyExhaustionScore",
            "STF15_TimeImbalance",
            "STF15_FailedBreakoutScore",
            "STF15_MaxAdverseExcursion",
            "STF15_HighBeforeLow",
            "STF15_LowBeforeHigh",
            "STF15_LastQuarterShare",
        ]
        total_entries = int(len(detail_df))
        wins = int((detail_df["outcome"] == "win").sum())
        losses = int((detail_df["outcome"] == "loss").sum())
        flats = int((detail_df["outcome"] == "flat").sum())
        summary_rows.append(
            {
                "policy": "SIGNAL_E211_BANDED_68",
                "entries": total_entries,
                "wins": wins,
                "losses": losses,
                "flats": flats,
                "win_rate": float(wins / total_entries) if total_entries else 0.0,
                "loss_rate": float(losses / total_entries) if total_entries else 0.0,
                "flat_rate": float(flats / total_entries) if total_entries else 0.0,
                "mean_trade_pnl_pct_initial": float(pd.to_numeric(detail_df["trade_pnl_pct_initial"], errors="coerce").mean()),
                "median_trade_pnl_pct_initial": float(pd.to_numeric(detail_df["trade_pnl_pct_initial"], errors="coerce").median()),
                "mean_hold_bars": float(pd.to_numeric(detail_df["hold_bars"], errors="coerce").mean()),
                "median_hold_bars": float(pd.to_numeric(detail_df["hold_bars"], errors="coerce").median()),
                "veto_hit_rate": float(pd.to_numeric(detail_df["intrahour_veto_v1_active"], errors="coerce").fillna(0.0).mean()),
            }
        )
        win_df = detail_df.loc[detail_df["outcome"] == "win"].copy()
        loss_df = detail_df.loc[detail_df["outcome"] == "loss"].copy()
        for feature_col in numeric_feature_cols:
            win_mean = float(pd.to_numeric(win_df.get(feature_col, pd.Series(dtype=float)), errors="coerce").mean()) if not win_df.empty else np.nan
            loss_mean = float(pd.to_numeric(loss_df.get(feature_col, pd.Series(dtype=float)), errors="coerce").mean()) if not loss_df.empty else np.nan
            feature_diff_rows.append(
                {
                    "feature": feature_col,
                    "winner_mean": win_mean,
                    "loser_mean": loss_mean,
                    "delta_win_minus_loss": win_mean - loss_mean if pd.notna(win_mean) and pd.notna(loss_mean) else np.nan,
                    "winner_median": float(pd.to_numeric(win_df.get(feature_col, pd.Series(dtype=float)), errors="coerce").median()) if not win_df.empty else np.nan,
                    "loser_median": float(pd.to_numeric(loss_df.get(feature_col, pd.Series(dtype=float)), errors="coerce").median()) if not loss_df.empty else np.nan,
                }
            )
    summary_df = pd.DataFrame(summary_rows)
    feature_diff_df = pd.DataFrame(feature_diff_rows)
    detail_csv = baseline_dir / "e211_entry_audit_detail.csv"
    cycle_csv = baseline_dir / "e211_entry_audit_cycle_summary.csv"
    summary_csv = baseline_dir / "e211_entry_audit_summary.csv"
    feature_diff_csv = baseline_dir / "e211_entry_feature_separation.csv"
    detail_df.to_csv(detail_csv, index=False)
    cycle_df.to_csv(cycle_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    feature_diff_df.to_csv(feature_diff_csv, index=False)
    return {
        "detail": detail_df,
        "cycle_summary": cycle_df,
        "summary": summary_df,
        "feature_separation": feature_diff_df,
    }


def _merge_overlay_prediction_for_entries(detail_df: pd.DataFrame, experiment_id: str) -> pd.DataFrame:
    signal_prefix = SIGNAL_OVERLAY_SOURCES[experiment_id][1]
    pred_col = f"{signal_prefix}_Pred"
    pred_df = load_signal_overlay_predictions(experiment_id)
    if pred_df.empty:
        return detail_df.assign(**{pred_col: np.nan})
    overlay_df = pred_df.rename(columns={"Ticker": "ticker", "Date": "entry_date"})
    overlay_df = overlay_df[["ticker", "entry_date", pred_col]].copy()
    overlay_df["entry_date"] = pd.to_datetime(overlay_df["entry_date"], errors="coerce")
    return detail_df.merge(overlay_df, on=["ticker", "entry_date"], how="left")


def run_event_conditioned_sizing_veto_research(
    ticker_list: List[str],
    instrument_df: pd.DataFrame,
    best_params: dict,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
    interval: str,
    history_days: int = 1095,
    train_days: int = 730,
    val_days: int = 90,
    test_days: int = 30,
    step_days: int = 30,
    max_windows_per_ticker: int = 1,
) -> pd.DataFrame:
    EVENT_CONDITIONED_SIZING_VETO_DIR.mkdir(parents=True, exist_ok=True)
    required_overlay_ids: List[str] = []
    for cfg in EVENT_CONDITIONED_SIZING_VETO_CANDIDATES.values():
        required_overlay_ids.extend([exp_id for exp_id in cfg.get("source_experiments", []) if exp_id])
    ensure_signal_overlay_predictions_available(sorted(set(required_overlay_ids)), "EventConditionedSizingVeto research")

    audit_outputs = run_e211_entry_audit(
        ticker_list=ticker_list,
        instrument_df=instrument_df,
        best_params=best_params,
        initial_balance=initial_balance,
        stop_loss=stop_loss,
        take_profit=take_profit,
        max_position_size=max_position_size,
        max_drawdown=max_drawdown,
        annual_trading_days=annual_trading_days,
        interval=interval,
        history_days=history_days,
        train_days=train_days,
        val_days=val_days,
        test_days=test_days,
        step_days=step_days,
        max_windows_per_ticker=max_windows_per_ticker,
    )
    detail_df = audit_outputs.get("detail", pd.DataFrame()).copy()
    summary_path = EVENT_CONDITIONED_SIZING_VETO_DIR / "event_conditioned_sizing_veto_shortlist_summary.csv"
    detail_path = EVENT_CONDITIONED_SIZING_VETO_DIR / "event_conditioned_sizing_veto_research_detail.csv"
    promoted_path = EVENT_CONDITIONED_SIZING_VETO_DIR / "event_conditioned_sizing_veto_promoted_ids.txt"
    if detail_df.empty:
        empty_summary = pd.DataFrame(
            columns=[
                "ExperimentID",
                "OverlayPolicy",
                "Label",
                "SourceExperiments",
                "MatchedEntries",
                "KeptEntries",
                "VetoedEntries",
                "KeptWinRate",
                "KeptLossRate",
                "VetoedLossRate",
                "KeptMeanTradePnL",
                "VetoedMeanTradePnL",
                "BaselineMeanTradePnL",
                "SelectionScore",
                "Eligible",
                "ShortlistRank",
                "StandalonePromoted",
                "Description",
            ]
        )
        empty_summary.to_csv(summary_path, index=False)
        pd.DataFrame().to_csv(detail_path, index=False)
        promoted_path.write_text("", encoding="utf-8")
        return empty_summary

    detail_df["entry_date"] = pd.to_datetime(detail_df["entry_date"], errors="coerce")
    detail_df["trade_pnl_pct_initial"] = pd.to_numeric(detail_df["trade_pnl_pct_initial"], errors="coerce")
    detail_df = detail_df.dropna(subset=["ticker", "entry_date", "trade_pnl_pct_initial"])
    baseline_mean_trade_pnl = float(detail_df["trade_pnl_pct_initial"].mean())

    summary_rows: List[Dict[str, object]] = []
    detail_rows: List[Dict[str, object]] = []
    for candidate_id, cfg in EVENT_CONDITIONED_SIZING_VETO_CANDIDATES.items():
        candidate_df = detail_df.copy()
        primary_experiment = str(cfg["primary_experiment"])
        candidate_df = _merge_overlay_prediction_for_entries(candidate_df, primary_experiment)
        primary_col = f"{SIGNAL_OVERLAY_SOURCES[primary_experiment][1]}_Pred"
        required_cols = [primary_col]
        veto_mask = pd.to_numeric(candidate_df[primary_col], errors="coerce") < float(cfg["primary_threshold"])
        secondary_col = None

        secondary_experiment = cfg.get("secondary_experiment")
        if secondary_experiment:
            secondary_experiment = str(secondary_experiment)
            candidate_df = _merge_overlay_prediction_for_entries(candidate_df, secondary_experiment)
            secondary_col = f"{SIGNAL_OVERLAY_SOURCES[secondary_experiment][1]}_Pred"
            required_cols.append(secondary_col)
            veto_mask = veto_mask | (pd.to_numeric(candidate_df[secondary_col], errors="coerce") < float(cfg["secondary_threshold"]))

        matched_mask = np.ones(len(candidate_df), dtype=bool)
        for col in required_cols:
            matched_mask = matched_mask & pd.to_numeric(candidate_df[col], errors="coerce").notna().to_numpy()

        matched_df = candidate_df.loc[matched_mask].copy()
        matched_df["veto_active"] = veto_mask[matched_mask].astype(bool)
        kept_df = matched_df.loc[~matched_df["veto_active"]].copy()
        vetoed_df = matched_df.loc[matched_df["veto_active"]].copy()

        kept_mean_trade_pnl = float(kept_df["trade_pnl_pct_initial"].mean()) if not kept_df.empty else np.nan
        vetoed_mean_trade_pnl = float(vetoed_df["trade_pnl_pct_initial"].mean()) if not vetoed_df.empty else np.nan
        kept_loss_rate = float((kept_df["outcome"] == "loss").mean()) if not kept_df.empty else np.nan
        vetoed_loss_rate = float((vetoed_df["outcome"] == "loss").mean()) if not vetoed_df.empty else np.nan
        kept_win_rate = float((kept_df["outcome"] == "win").mean()) if not kept_df.empty else np.nan

        eligible = (
            len(matched_df) >= 12
            and len(kept_df) >= 5
            and pd.notna(kept_mean_trade_pnl)
            and kept_mean_trade_pnl > baseline_mean_trade_pnl
            and pd.notna(vetoed_mean_trade_pnl)
            and vetoed_mean_trade_pnl <= baseline_mean_trade_pnl
        )
        selection_score = (
            (kept_mean_trade_pnl - vetoed_mean_trade_pnl)
            if pd.notna(kept_mean_trade_pnl) and pd.notna(vetoed_mean_trade_pnl)
            else -np.inf
        )
        summary_rows.append(
            {
                "ExperimentID": candidate_id,
                "OverlayPolicy": cfg["policy_name"],
                "Label": cfg["label"],
                "SourceExperiments": "|".join(str(x) for x in cfg.get("source_experiments", [])),
                "MatchedEntries": int(len(matched_df)),
                "KeptEntries": int(len(kept_df)),
                "VetoedEntries": int(len(vetoed_df)),
                "KeptWinRate": kept_win_rate,
                "KeptLossRate": kept_loss_rate,
                "VetoedLossRate": vetoed_loss_rate,
                "KeptMeanTradePnL": kept_mean_trade_pnl,
                "VetoedMeanTradePnL": vetoed_mean_trade_pnl,
                "BaselineMeanTradePnL": baseline_mean_trade_pnl,
                "SelectionScore": selection_score,
                "Eligible": bool(eligible),
                "ShortlistRank": np.nan,
                "StandalonePromoted": False,
                "Description": cfg["description"],
            }
        )
        for _, row in matched_df.iterrows():
            detail_row = {
                "ExperimentID": candidate_id,
                "ticker": row["ticker"],
                "entry_date": row["entry_date"],
                "outcome": row["outcome"],
                "trade_pnl_pct_initial": row["trade_pnl_pct_initial"],
                "veto_active": bool(row["veto_active"]),
                primary_col: row.get(primary_col),
            }
            if secondary_col:
                detail_row[secondary_col] = row.get(secondary_col)
            detail_rows.append(detail_row)

    summary_df = pd.DataFrame(summary_rows)
    promoted_ids: List[str] = []
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["Eligible", "SelectionScore", "KeptMeanTradePnL", "KeptEntries"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True)
        shortlist_rank = 1
        for idx in summary_df.index:
            if bool(summary_df.at[idx, "Eligible"]):
                summary_df.at[idx, "ShortlistRank"] = shortlist_rank
                shortlist_rank += 1
                if len(promoted_ids) < 2:
                    summary_df.at[idx, "StandalonePromoted"] = True
                    promoted_ids.append(str(summary_df.at[idx, "ExperimentID"]))

    summary_df.to_csv(summary_path, index=False)
    pd.DataFrame(detail_rows).to_csv(detail_path, index=False)
    promoted_path.write_text("\n".join(promoted_ids), encoding="utf-8")
    print(f"[T09 RESEARCH] shortlist saved: {summary_path}")
    print(f"[T09 RESEARCH] promoted IDs: {', '.join(promoted_ids) if promoted_ids else 'none'}")
    return summary_df


def summarize_signal_slice_coverage(
    df_slice: pd.DataFrame,
    ticker: str,
    cycle_idx: int,
    split_name: str,
) -> Dict[str, object]:
    pred = pd.to_numeric(df_slice.get("Signal_E102_Pred", pd.Series(dtype=float)), errors="coerce").fillna(0.5)
    edge = pd.to_numeric(df_slice.get("Signal_E102_Edge", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    high_conf = pd.to_numeric(df_slice.get("Signal_E102_HighConf", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    pred_e302 = pd.to_numeric(df_slice.get("Signal_E302_Pred", pd.Series(dtype=float)), errors="coerce").fillna(0.5)
    edge_e302 = pd.to_numeric(df_slice.get("Signal_E302_Edge", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    high_conf_e302 = pd.to_numeric(df_slice.get("Signal_E302_HighConf", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    row_count = int(len(df_slice))
    nondefault_mask = (pred - 0.5).abs() > 1e-9
    nondefault_count = int(nondefault_mask.sum())
    nondefault_mask_e302 = (pred_e302 - 0.5).abs() > 1e-9
    nondefault_count_e302 = int(nondefault_mask_e302.sum())
    return {
        "ticker": ticker,
        "cycle": cycle_idx,
        "split": split_name,
        "rows": row_count,
        "signal_nondefault_rows": nondefault_count,
        "signal_nondefault_pct": float(nondefault_count / row_count) if row_count else 0.0,
        "signal_pred_mean": float(pred.mean()) if row_count else 0.5,
        "signal_pred_std": float(pred.std()) if row_count else 0.0,
        "signal_pred_p75": float(pred.quantile(0.75)) if row_count else 0.5,
        "signal_pred_p90": float(pred.quantile(0.90)) if row_count else 0.5,
        "signal_pred_max": float(pred.max()) if row_count else 0.5,
        "signal_edge_mean": float(edge.mean()) if row_count else 0.0,
        "signal_highconf_rows": int((high_conf > 0.5).sum()),
        "signal_pred_ge_053": int((pred >= 0.53).sum()),
        "signal_pred_ge_056": int((pred >= 0.56).sum()),
        "signal_pred_ge_060": int((pred >= 0.60).sum()),
        "signal_pred_ge_065": int((pred >= 0.65).sum()),
        "signal_pred_le_047": int((pred <= 0.47).sum()),
        "signal_pred_le_049": int((pred <= 0.49).sum()),
        "signal_e302_nondefault_rows": nondefault_count_e302,
        "signal_e302_nondefault_pct": float(nondefault_count_e302 / row_count) if row_count else 0.0,
        "signal_e302_pred_mean": float(pred_e302.mean()) if row_count else 0.5,
        "signal_e302_pred_std": float(pred_e302.std()) if row_count else 0.0,
        "signal_e302_pred_p75": float(pred_e302.quantile(0.75)) if row_count else 0.5,
        "signal_e302_pred_p90": float(pred_e302.quantile(0.90)) if row_count else 0.5,
        "signal_e302_pred_max": float(pred_e302.max()) if row_count else 0.5,
        "signal_e302_edge_mean": float(edge_e302.mean()) if row_count else 0.0,
        "signal_e302_highconf_rows": int((high_conf_e302 > 0.5).sum()),
        "signal_e302_pred_ge_060": int((pred_e302 >= 0.60).sum()),
        "signal_e302_pred_ge_065": int((pred_e302 >= 0.65).sum()),
        "signal_combo_ge_068_070": int(((pred >= 0.68) & (pred_e302 >= 0.70)).sum()),
    }


def build_signal_policy_family(experiment_id: str) -> List[str]:
    base = f"SIGNAL_{experiment_id}"
    return [
        f"{base}_LONGONLY",
        f"{base}_BANDED_64",
        f"{base}_BANDED_66",
        f"{base}_BANDED_68",
        f"{base}_BANDED_70",
    ]


def load_cross_sectional_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_cross_sectional_60m" / "latest" / "cross_sectional_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read cross-sectional promoted IDs: {exc}")
        return []
    return ids


def load_ablation_grid_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_ablation_grid" / "latest" / "ablation_shortlist.csv"
    )
    if not promoted_path.exists():
        return []
    try:
        shortlist_df = pd.read_csv(promoted_path)
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read ablation shortlist: {exc}")
        return []
    if shortlist_df.empty or "ExperimentID" not in shortlist_df.columns:
        return []
    promoted_mask = pd.to_numeric(shortlist_df.get("StandalonePromoted"), errors="coerce").fillna(0).astype(bool)
    ids = shortlist_df.loc[promoted_mask, "ExperimentID"].astype(str).tolist()
    return ids


def load_setup_regime_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_setup_regimes" / "latest" / "setup_regime_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read setup-regime promoted IDs: {exc}")
        return []
    return ids


def load_intrahour_path_v1_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_intrahour_path_v1" / "latest" / "intrahour_path_v1_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read intrahour-path promoted IDs: {exc}")
        return []
    return ids


def load_breadth_context_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_breadth_context_60m" / "latest" / "breadth_context_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read breadth-context promoted IDs: {exc}")
        return []
    return ids


def load_time_distribution_v2_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_time_distribution_v2" / "latest" / "time_distribution_v2_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read time-distribution promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_execution_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_execution" / "latest" / "native_15m_execution_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_failed_breakout_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_failed_breakout" / "latest" / "native_15m_failed_breakout_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m failed-breakout promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_open_drive_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_open_drive" / "latest" / "native_15m_open_drive_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m open-drive promoted IDs: {exc}")
        return []
    return ids


def load_opening_auction_gap_liquidity_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_opening_auction_gap_liquidity" / "latest" / "opening_auction_gap_liquidity_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read opening auction gap-liquidity promoted IDs: {exc}")
        return []
    return ids[:2]


def load_native_15m_session_phase_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_session_phase" / "latest" / "native_15m_session_phase_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m session-phase promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_holding_horizon_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_holding_horizon" / "latest" / "native_15m_holding_horizon_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m holding-horizon promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_topk_event_rank_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_topk_event_rank" / "latest" / "native_15m_topk_event_rank_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m top-k event-rank promoted IDs: {exc}")
        return []
    return ids


def load_native_15m_breadth_event_promoted_ids() -> List[str]:
    shortlist_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "native_15m_breadth_event_shortlist_summary.csv"
    )
    if shortlist_path.exists():
        try:
            shortlist_df = pd.read_csv(shortlist_path)
            if not shortlist_df.empty and "ExperimentID" in shortlist_df.columns:
                shortlist_df["ShortlistRank"] = pd.to_numeric(shortlist_df.get("ShortlistRank"), errors="coerce")
                shortlisted = shortlist_df.loc[shortlist_df.get("StandalonePromoted", False) == True].copy()
                shortlisted = shortlisted.sort_values(["ShortlistRank", "ExperimentID"], ascending=[True, True])
                ids = shortlisted["ExperimentID"].astype(str).tolist()[:2]
                if ids:
                    return ids
        except Exception as exc:
            main_logger.warning(f"[BASELINE] failed to read native-15m breadth-event shortlist: {exc}")
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_breadth_event" / "latest" / "native_15m_breadth_event_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m breadth-event promoted IDs: {exc}")
        return []
    return ids[:2]


def load_native_15m_mean_reversion_exhaustion_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "native_15m_mean_reversion_exhaustion_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read native-15m mean-reversion exhaustion promoted IDs: {exc}")
        return []
    return ids


def load_sixty_minute_daily_context_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_sixty_minute_daily_context" / "latest" / "sixty_minute_daily_context_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read 60m daily-context promoted IDs: {exc}")
        return []
    return ids


def load_cross_sectional_commonality_residual_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_cross_sectional_commonality_residual" / "latest" / "cross_sectional_commonality_residual_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read cross-sectional commonality-residual promoted IDs: {exc}")
        return []
    return ids[:2]


def load_intraday_volume_liquidity_forecast_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_intraday_volume_liquidity_forecast" / "latest" / "intraday_volume_liquidity_forecast_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read intraday volume-liquidity promoted IDs: {exc}")
        return []
    return ids[:2]


def load_event_outcome_accounting_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_event_outcome_accounting" / "latest" / "event_outcome_accounting_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read event-outcome accounting promoted IDs: {exc}")
        return []
    return ids[:2]


def load_event_conditioned_sizing_veto_promoted_ids() -> List[str]:
    shortlist_path = (
        RESULTS_DIR
        / "signal_research"
        / "outputs_event_conditioned_sizing_veto"
        / "latest"
        / "event_conditioned_sizing_veto_shortlist_summary.csv"
    )
    if shortlist_path.exists():
        try:
            shortlist_df = pd.read_csv(shortlist_path)
            if not shortlist_df.empty and "ExperimentID" in shortlist_df.columns:
                shortlist_df["ShortlistRank"] = pd.to_numeric(shortlist_df.get("ShortlistRank"), errors="coerce")
                promoted_flag = shortlist_df.get(
                    "StandalonePromoted",
                    pd.Series(False, index=shortlist_df.index, dtype=bool),
                )
                shortlist_df["StandalonePromoted"] = promoted_flag.astype(bool)
                shortlisted = shortlist_df.loc[shortlist_df["StandalonePromoted"]].copy()
                shortlisted = shortlisted.sort_values(["ShortlistRank", "ExperimentID"], ascending=[True, True])
                ids = shortlisted["ExperimentID"].astype(str).tolist()[:2]
                if ids:
                    return ids
        except Exception as exc:
            main_logger.warning(f"[BASELINE] failed to read event-conditioned sizing-veto shortlist: {exc}")
    promoted_path = (
        RESULTS_DIR
        / "signal_research"
        / "outputs_event_conditioned_sizing_veto"
        / "latest"
        / "event_conditioned_sizing_veto_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read event-conditioned sizing-veto promoted IDs: {exc}")
        return []
    return ids[:2]


def ensure_signal_overlay_predictions_available(experiment_ids: List[str], mode_label: str) -> None:
    missing_ids: List[str] = []
    for experiment_id in experiment_ids:
        pred_df = load_signal_overlay_predictions(experiment_id)
        if pred_df.empty:
            missing_ids.append(experiment_id)
    if missing_ids:
        joined = ", ".join(missing_ids)
        message = (
            f"[BASELINE] {mode_label} has no usable overlay predictions for: {joined}. "
            "Run the corresponding signal research mode first, or fix the empty research export before baseline."
        )
        main_logger.error(message)
        raise RuntimeError(message)


def load_market_state_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_market_state_60m" / "latest" / "market_state_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read market-state promoted IDs: {exc}")
        return []
    return ids


def load_multiscale_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_multiscale_60m" / "latest" / "multiscale_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read multiscale promoted IDs: {exc}")
        return []
    return ids


def load_portfolio_rank_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest" / "portfolio_rank_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[PORTFOLIO-RANK] failed to read promoted IDs: {exc}")
        return []
    return ids


def load_second_timeframe_promoted_ids() -> List[str]:
    promoted_path = (
        RESULTS_DIR / "signal_research" / "outputs_second_timeframe_60m" / "latest" / "second_timeframe_60m_promoted_ids.txt"
    )
    if not promoted_path.exists():
        return []
    try:
        ids = [line.strip() for line in promoted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        main_logger.warning(f"[BASELINE] failed to read second-timeframe promoted IDs: {exc}")
        return []
    return ids


def build_cross_sectional_scoreboard(summary_df: pd.DataFrame, policy_summary: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty or policy_summary.empty:
        return pd.DataFrame()

    benchmark_policy = "SIGNAL_E211_BANDED_68"
    challenger_policies = [
        policy
        for policy in policy_summary["policy"].tolist()
        if isinstance(policy, str) and policy.startswith("SIGNAL_E5")
    ]
    if not challenger_policies:
        return pd.DataFrame()

    benchmark_row = policy_summary.loc[policy_summary["policy"] == benchmark_policy].head(1)
    challenger_row = policy_summary.loc[policy_summary["policy"].isin(challenger_policies)].sort_values(
        ["test_return", "test_sharpe", "test_turnover"],
        ascending=[False, False, True],
    ).head(1)
    if benchmark_row.empty or challenger_row.empty:
        return pd.DataFrame()

    def _breadth(policy_name: str) -> dict:
        policy_df = summary_df.loc[summary_df["policy"] == policy_name].copy()
        if policy_df.empty:
            return {
                "positive_tickers": 0,
                "zero_tickers": 0,
                "negative_tickers": 0,
                "top_positive_share": 0.0,
            }
        ticker_means = (
            policy_df.groupby("ticker")[["test_return"]]
            .mean()
            .reset_index()
        )
        positive = int((ticker_means["test_return"] > 0).sum())
        zero = int((ticker_means["test_return"] == 0).sum())
        negative = int((ticker_means["test_return"] < 0).sum())
        positive_returns = ticker_means.loc[ticker_means["test_return"] > 0, "test_return"]
        if positive_returns.empty or float(positive_returns.sum()) <= 0:
            top_share = 0.0
        else:
            top_share = float(positive_returns.max() / positive_returns.sum())
        return {
            "positive_tickers": positive,
            "zero_tickers": zero,
            "negative_tickers": negative,
            "top_positive_share": top_share,
        }

    benchmark = benchmark_row.iloc[0].to_dict()
    challenger = challenger_row.iloc[0].to_dict()
    challenger_breadth = _breadth(str(challenger["policy"]))
    benchmark_breadth = _breadth(str(benchmark["policy"]))
    verdict = "benchmark_only"
    if float(challenger.get("test_return", 0.0)) > float(benchmark.get("test_return", 0.0)):
        verdict = "baseline_promoted"
        if (
            challenger_breadth["positive_tickers"] >= max(2, benchmark_breadth["positive_tickers"])
            and challenger_breadth["top_positive_share"] <= 0.60
            and float(challenger.get("test_turnover", 0.0)) <= (1.15 * max(float(benchmark.get("test_turnover", 0.0)), 1e-9))
        ):
            verdict = "rl_eligible"

    rows = []
    for role, row_data, breadth in [
        ("incumbent_benchmark", benchmark, benchmark_breadth),
        ("cross_sectional_challenger", challenger, challenger_breadth),
    ]:
        rows.append(
            {
                "Role": role,
                "Policy": row_data.get("policy"),
                "MeanReturn": row_data.get("test_return"),
                "MeanSharpe": row_data.get("test_sharpe"),
                "MeanTurnover": row_data.get("test_turnover"),
                "MeanTrades": row_data.get("test_trades"),
                "PositiveTickers": breadth["positive_tickers"],
                "ZeroTickers": breadth["zero_tickers"],
                "NegativeTickers": breadth["negative_tickers"],
                "TopPositiveShare": breadth["top_positive_share"],
                "PromotionVerdict": verdict if role == "cross_sectional_challenger" else "benchmark_only",
            }
        )
    return pd.DataFrame(rows)


def policy_breadth_metrics(summary_df: pd.DataFrame, policy_name: str) -> dict:
    if summary_df.empty or "policy" not in summary_df.columns:
        return {
            "positive_tickers": 0,
            "zero_tickers": 0,
            "negative_tickers": 0,
            "top_positive_share": 0.0,
        }
    policy_df = summary_df.loc[summary_df["policy"] == policy_name].copy()
    if policy_df.empty or "ticker" not in policy_df.columns:
        return {
            "positive_tickers": 0,
            "zero_tickers": 0,
            "negative_tickers": 0,
            "top_positive_share": 0.0,
        }
    ticker_means = policy_df.groupby("ticker")["test_return"].mean().reset_index()
    positive = int((ticker_means["test_return"] > 0).sum())
    zero = int((ticker_means["test_return"] == 0).sum())
    negative = int((ticker_means["test_return"] < 0).sum())
    positive_returns = ticker_means.loc[ticker_means["test_return"] > 0, "test_return"]
    if positive_returns.empty or float(positive_returns.sum()) <= 0:
        top_share = 0.0
    else:
        top_share = float(positive_returns.max() / positive_returns.sum())
    return {
        "positive_tickers": positive,
        "zero_tickers": zero,
        "negative_tickers": negative,
        "top_positive_share": top_share,
    }


def build_experiment_branch_registry() -> tuple[pd.DataFrame, pd.DataFrame]:
    signal_research_dir = RESULTS_DIR / "signal_research"
    signal_baseline_dir = RESULTS_DIR / "signal_baseline"

    baseline_walk_csv = signal_baseline_dir / "baseline_walk_forward_summary.csv"
    baseline_walk_df = pd.read_csv(baseline_walk_csv) if baseline_walk_csv.exists() else pd.DataFrame()

    branch_specs = [
        {
            "branch": "E211_Incumbent",
            "research_summary": signal_research_dir / "outputs_e102_deepdive" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_e102_deepdive" / "latest" / "e102_deepdive_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "e102_deepdive_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E209", "SIGNAL_E211"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E209", "E211"],
        },
        {
            "branch": "AblationGrid",
            "research_summary": signal_research_dir / "outputs_ablation_grid" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_ablation_grid" / "latest" / "ablation_shortlist.csv",
            "baseline_summary": signal_baseline_dir / "ablation_grid_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E605", "SIGNAL_E606", "SIGNAL_E607", "SIGNAL_E610"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E605", "E606", "E607", "E610"],
        },
        {
            "branch": "E302_Broader",
            "research_summary": signal_research_dir / "outputs_e302" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_e302" / "latest" / "e302_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "e302_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E302"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E302", "E325", "E329"],
        },
        {
            "branch": "GeneralizationNext",
            "research_summary": signal_research_dir / "outputs_generalization_next" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_generalization_next" / "latest" / "generalization_next_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "generalization_next_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E401", "SIGNAL_E407"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E401", "E407"],
        },
        {
            "branch": "GeneralizationWave2",
            "research_summary": signal_research_dir / "outputs_generalization_wave2" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_generalization_wave2" / "latest" / "generalization_wave2_shortlist_summary.csv",
            "baseline_summary": None,
            "policy_prefixes": [],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E415"],
        },
        {
            "branch": "CrossSectional60m",
            "research_summary": signal_research_dir / "outputs_cross_sectional_60m" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_cross_sectional_60m" / "latest" / "cross_sectional_60m_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "cross_sectional_60m_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E5"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": [f"E50{i}" for i in range(1, 9)],
        },
        {
            "branch": "Native15mExecution",
            "research_summary": signal_research_dir / "outputs_native_15m_execution" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_execution" / "latest" / "native_15m_execution_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_execution_validate_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E150"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E1501", "E1502", "E1503", "E1504"],
        },
        {
            "branch": "Native15mFailedBreakout",
            "research_summary": signal_research_dir / "outputs_native_15m_failed_breakout" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_failed_breakout" / "latest" / "native_15m_failed_breakout_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_failed_breakout_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E160"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E1601", "E1602", "E1603", "E1604"],
        },
        {
            "branch": "Native15mOpenDrive",
            "research_summary": signal_research_dir / "outputs_native_15m_open_drive" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_open_drive" / "latest" / "native_15m_open_drive_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_open_drive_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E170"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E1701", "E1702", "E1703", "E1704"],
        },
        {
            "branch": "OpeningAuctionGapLiquidity",
            "research_summary": signal_research_dir / "outputs_opening_auction_gap_liquidity" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_opening_auction_gap_liquidity" / "latest" / "opening_auction_gap_liquidity_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "opening_auction_gap_liquidity_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E270"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2701", "E2702", "E2703", "E2704"],
        },
        {
            "branch": "Native15mSessionPhase",
            "research_summary": signal_research_dir / "outputs_native_15m_session_phase" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_session_phase" / "latest" / "native_15m_session_phase_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_session_phase_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E180"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E1801", "E1802", "E1803", "E1804"],
        },
        {
            "branch": "Native15mHoldingHorizon",
            "research_summary": signal_research_dir / "outputs_native_15m_holding_horizon" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_holding_horizon" / "latest" / "native_15m_holding_horizon_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_holding_horizon_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E190"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E1901", "E1902", "E1903", "E1904"],
        },
        {
            "branch": "Native15mTopKEventRank",
            "research_summary": signal_research_dir / "outputs_native_15m_topk_event_rank" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_topk_event_rank" / "latest" / "native_15m_topk_event_rank_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_topk_event_rank_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E200"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2001", "E2002", "E2003", "E2004"],
        },
        {
            "branch": "Native15mMeanReversionExhaustion",
            "research_summary": signal_research_dir / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_native_15m_mean_reversion_exhaustion" / "latest" / "native_15m_mean_reversion_exhaustion_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "native_15m_mean_reversion_exhaustion_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E210"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2101", "E2102", "E2103", "E2104"],
        },
        {
            "branch": "SixtyMinuteDailyContext",
            "research_summary": signal_research_dir / "outputs_sixty_minute_daily_context" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_sixty_minute_daily_context" / "latest" / "sixty_minute_daily_context_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "sixty_minute_daily_context_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E220"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2201", "E2202", "E2203", "E2204"],
        },
        {
            "branch": "CrossSectionalCommonalityResidual",
            "research_summary": signal_research_dir / "outputs_cross_sectional_commonality_residual" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_cross_sectional_commonality_residual" / "latest" / "cross_sectional_commonality_residual_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "cross_sectional_commonality_residual_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E250"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2501", "E2502", "E2503", "E2504"],
        },
        {
            "branch": "IntradayVolumeLiquidityForecast",
            "research_summary": signal_research_dir / "outputs_intraday_volume_liquidity_forecast" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_intraday_volume_liquidity_forecast" / "latest" / "intraday_volume_liquidity_forecast_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "intraday_volume_liquidity_forecast_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E260"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2601", "E2602", "E2603", "E2604"],
        },
        {
            "branch": "EventOutcomeAccounting",
            "research_summary": signal_research_dir / "outputs_event_outcome_accounting" / "latest" / "experiment_summary_real_vs_shuffled.csv",
            "shortlist": signal_research_dir / "outputs_event_outcome_accounting" / "latest" / "event_outcome_accounting_shortlist_summary.csv",
            "baseline_summary": signal_baseline_dir / "event_outcome_accounting_policy_summary.csv",
            "policy_prefixes": ["SIGNAL_E280"],
            "benchmark_policy": "SIGNAL_E211_BANDED_68",
            "candidate_ids": ["E2801", "E2802", "E2803", "E2804", "E2805", "E2806"],
        },
    ]

    candidate_rows = []
    branch_rows = []
    benchmark_return = np.nan
    if not baseline_walk_df.empty:
        bench_df = baseline_walk_df.loc[baseline_walk_df["policy"] == "SIGNAL_E211_BANDED_68"].copy()
        if not bench_df.empty:
            benchmark_return = float(pd.to_numeric(bench_df["test_return"], errors="coerce").mean())

    for spec in branch_specs:
        research_df = pd.read_csv(spec["research_summary"]) if spec["research_summary"] and spec["research_summary"].exists() else pd.DataFrame()
        shortlist_df = pd.read_csv(spec["shortlist"]) if spec["shortlist"] and spec["shortlist"].exists() else pd.DataFrame()
        baseline_policy_df = pd.read_csv(spec["baseline_summary"]) if spec["baseline_summary"] and spec["baseline_summary"].exists() else pd.DataFrame()

        if not shortlist_df.empty:
            candidates_df = shortlist_df.copy()
        elif not research_df.empty:
            candidates_df = research_df.loc[research_df["ExperimentID"].isin(spec["candidate_ids"])].copy()
        else:
            candidates_df = pd.DataFrame(columns=["ExperimentID"])

        best_policy_name = ""
        best_policy_return = np.nan
        best_policy_turnover = np.nan
        best_policy_trades = np.nan
        if not baseline_policy_df.empty and "policy" in baseline_policy_df.columns:
            mask = pd.Series(False, index=baseline_policy_df.index)
            for prefix in spec["policy_prefixes"]:
                mask = mask | baseline_policy_df["policy"].astype(str).str.startswith(prefix)
            branch_policy_df = baseline_policy_df.loc[mask].copy()
            if not branch_policy_df.empty:
                branch_policy_df = branch_policy_df.sort_values(
                    ["test_return", "test_sharpe", "test_turnover"],
                    ascending=[False, False, True],
                )
                best_row = branch_policy_df.iloc[0]
                best_policy_name = str(best_row.get("policy", ""))
                best_policy_return = float(pd.to_numeric(best_row.get("test_return"), errors="coerce"))
                best_policy_turnover = float(pd.to_numeric(best_row.get("test_turnover"), errors="coerce"))
                best_policy_trades = float(pd.to_numeric(best_row.get("test_trades"), errors="coerce"))

        breadth = policy_breadth_metrics(baseline_walk_df, best_policy_name) if best_policy_name else {
            "positive_tickers": 0,
            "zero_tickers": 0,
            "negative_tickers": 0,
            "top_positive_share": 0.0,
        }

        for _, row in candidates_df.iterrows():
            experiment_id = str(row.get("ExperimentID", ""))
            family = row.get("Family", "")
            promoted = bool(row.get("StandalonePromoted", False)) if "StandalonePromoted" in row else False
            candidate_rows.append(
                {
                    "Branch": spec["branch"],
                    "ExperimentID": experiment_id,
                    "Family": family,
                    "StandalonePromoted": promoted,
                    "ResearchAUC": row.get("Real_AUC", np.nan),
                    "ResearchBalancedAccuracy": row.get("Real_BalancedAccuracy", np.nan),
                    "ResearchSpreadTopBottom": row.get("Real_Spread_TopBottom", np.nan),
                    "GapAUC": row.get("Gap_AUC", np.nan),
                    "GapBalancedAccuracy": row.get("Gap_BalancedAccuracy", np.nan),
                    "GapSpreadTopBottom": row.get("Gap_Spread_TopBottom", np.nan),
                    "RealTradeCount": row.get("Real_TradeCount", np.nan),
                    "SelectionScore": row.get("SelectionScore", np.nan),
                    "BestBaselinePolicy": best_policy_name,
                    "BestBaselineReturn": best_policy_return,
                    "BestBaselineTurnover": best_policy_turnover,
                    "BestBaselineTrades": best_policy_trades,
                    "PositiveTickers": breadth["positive_tickers"],
                    "ZeroTickers": breadth["zero_tickers"],
                    "NegativeTickers": breadth["negative_tickers"],
                    "TopPositiveShare": breadth["top_positive_share"],
                    "BenchmarkPolicy": spec["benchmark_policy"],
                    "BenchmarkReturn": benchmark_return,
                }
            )

        verdict = "research_only"
        if best_policy_name:
            verdict = "benchmark_only"
            if np.isfinite(best_policy_return) and np.isfinite(benchmark_return) and best_policy_return > benchmark_return:
                verdict = "baseline_promoted"
                if breadth["positive_tickers"] >= 2 and breadth["top_positive_share"] <= 0.60:
                    verdict = "rl_eligible"
        elif not candidates_df.empty:
            verdict = "research_only"
        else:
            verdict = "not_run"

        branch_rows.append(
            {
                "Branch": spec["branch"],
                "CandidateCount": int(len(candidates_df)),
                "PromotedCandidateCount": int(pd.to_numeric(candidates_df.get("StandalonePromoted", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(bool).sum()) if not candidates_df.empty else 0,
                "BestResearchExperimentID": str(candidates_df.sort_values(["SelectionScore", "Real_Spread_TopBottom"], ascending=[False, False]).iloc[0]["ExperimentID"]) if (not candidates_df.empty and "SelectionScore" in candidates_df.columns and candidates_df["SelectionScore"].notna().any()) else (str(candidates_df.iloc[0]["ExperimentID"]) if not candidates_df.empty else ""),
                "BestBaselinePolicy": best_policy_name,
                "BestBaselineReturn": best_policy_return,
                "BestBaselineTurnover": best_policy_turnover,
                "BestBaselineTrades": best_policy_trades,
                "PositiveTickers": breadth["positive_tickers"],
                "ZeroTickers": breadth["zero_tickers"],
                "NegativeTickers": breadth["negative_tickers"],
                "TopPositiveShare": breadth["top_positive_share"],
                "BenchmarkPolicy": spec["benchmark_policy"],
                "BenchmarkReturn": benchmark_return,
                "Decision": verdict,
            }
        )

    candidate_registry = pd.DataFrame(candidate_rows)
    branch_scoreboard = pd.DataFrame(branch_rows)
    return candidate_registry, branch_scoreboard


def refresh_experiment_branch_registry() -> tuple[Path, Path]:
    candidate_registry, branch_scoreboard = build_experiment_branch_registry()
    candidate_csv = RESULTS_DIR / "experiment_branch_registry.csv"
    branch_csv = RESULTS_DIR / "branch_decision_scoreboard.csv"
    candidate_registry.to_csv(candidate_csv, index=False)
    branch_scoreboard.to_csv(branch_csv, index=False)
    main_logger.info(f"[REGISTRY] experiment branch registry saved: {candidate_csv}")
    main_logger.info(f"[REGISTRY] branch decision scoreboard saved: {branch_csv}")
    print(f"[REGISTRY] experiment branch registry saved: {candidate_csv}")
    print(f"[REGISTRY] branch decision scoreboard saved: {branch_csv}")
    return candidate_csv, branch_csv


def build_setup_library_scoreboard() -> pd.DataFrame:
    signal_research_dir = RESULTS_DIR / "signal_research"
    signal_baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_walk_csv = signal_baseline_dir / "baseline_walk_forward_summary.csv"
    baseline_walk_df = pd.read_csv(baseline_walk_csv) if baseline_walk_csv.exists() else pd.DataFrame()

    setup_map = {
        "S1_TrendContinuation": {
            "experiments": ["E209", "E211", "E501", "E502"],
            "policy_prefixes": ["SIGNAL_E209", "SIGNAL_E211", "SIGNAL_E501"],
        },
        "S2_PullbackToTrend": {
            "experiments": ["E413", "E414"],
            "policy_prefixes": [],
        },
        "S3_MeanReversion": {
            "experiments": ["E503", "E504"],
            "policy_prefixes": ["SIGNAL_E504"],
        },
        "S4_RelativeStrengthCarry": {
            "experiments": ["E407", "E416", "E507", "E508"],
            "policy_prefixes": ["SIGNAL_E407", "SIGNAL_E508"],
        },
        "S5_FailedBreakoutReversal": {
            "experiments": ["E415", "E401"],
            "policy_prefixes": ["SIGNAL_E401"],
        },
    }

    research_sources = [
        signal_research_dir / "outputs_e102_deepdive" / "latest" / "experiment_summary_real_vs_shuffled.csv",
        signal_research_dir / "outputs_generalization_next" / "latest" / "experiment_summary_real_vs_shuffled.csv",
        signal_research_dir / "outputs_generalization_wave2" / "latest" / "experiment_summary_real_vs_shuffled.csv",
        signal_research_dir / "outputs_cross_sectional_60m" / "latest" / "experiment_summary_real_vs_shuffled.csv",
    ]
    research_frames = [pd.read_csv(path) for path in research_sources if path.exists()]
    research_df = pd.concat(research_frames, ignore_index=True) if research_frames else pd.DataFrame()

    policy_summary_files = [
        signal_baseline_dir / "e102_deepdive_policy_summary.csv",
        signal_baseline_dir / "generalization_next_policy_summary.csv",
        signal_baseline_dir / "cross_sectional_60m_policy_summary.csv",
    ]
    policy_frames = [pd.read_csv(path) for path in policy_summary_files if path.exists()]
    policy_df = pd.concat(policy_frames, ignore_index=True) if policy_frames else pd.DataFrame()
    if not policy_df.empty:
        policy_df = policy_df.drop_duplicates(subset=["policy"], keep="last").reset_index(drop=True)

    rows = []
    for setup_name, cfg in setup_map.items():
        setup_research = research_df.loc[research_df["ExperimentID"].isin(cfg["experiments"])].copy() if not research_df.empty else pd.DataFrame()
        if not setup_research.empty:
            setup_research["SetupScore"] = (
                pd.to_numeric(setup_research.get("Gap_AUC"), errors="coerce").fillna(0.0)
                + pd.to_numeric(setup_research.get("Gap_BalancedAccuracy"), errors="coerce").fillna(0.0)
                + pd.to_numeric(setup_research.get("Gap_IC_Spearman"), errors="coerce").fillna(0.0)
                + pd.to_numeric(setup_research.get("Real_Spread_TopBottom"), errors="coerce").fillna(0.0)
            )
            best_research = setup_research.sort_values(
                ["SetupScore", "Real_Spread_TopBottom", "Real_TradeCount"],
                ascending=[False, False, False],
            ).head(1)
            best_research_experiment = str(best_research.iloc[0].get("ExperimentID", ""))
            best_research_score = float(pd.to_numeric(best_research.iloc[0].get("SetupScore"), errors="coerce"))
        else:
            best_research_experiment = ""
            best_research_score = np.nan

        best_policy_name = ""
        best_policy_return = np.nan
        best_policy_turnover = np.nan
        best_policy_trades = np.nan
        if not policy_df.empty and cfg["policy_prefixes"]:
            mask = pd.Series(False, index=policy_df.index)
            for prefix in cfg["policy_prefixes"]:
                mask = mask | policy_df["policy"].astype(str).str.startswith(prefix)
            setup_policies = policy_df.loc[mask].copy()
            if not setup_policies.empty:
                setup_policies = setup_policies.sort_values(
                    ["test_return", "test_sharpe", "test_turnover"],
                    ascending=[False, False, True],
                )
                best_policy = setup_policies.iloc[0]
                best_policy_name = str(best_policy.get("policy", ""))
                best_policy_return = float(pd.to_numeric(best_policy.get("test_return"), errors="coerce"))
                best_policy_turnover = float(pd.to_numeric(best_policy.get("test_turnover"), errors="coerce"))
                best_policy_trades = float(pd.to_numeric(best_policy.get("test_trades"), errors="coerce"))

        breadth = policy_breadth_metrics(baseline_walk_df, best_policy_name) if best_policy_name else {
            "positive_tickers": 0,
            "zero_tickers": 0,
            "negative_tickers": 0,
            "top_positive_share": 0.0,
        }
        rows.append(
            {
                "Setup": setup_name,
                "BestResearchExperimentID": best_research_experiment,
                "BestResearchScore": best_research_score,
                "BestBaselinePolicy": best_policy_name,
                "BestBaselineReturn": best_policy_return,
                "BestBaselineTurnover": best_policy_turnover,
                "BestBaselineTrades": best_policy_trades,
                "PositiveTickers": breadth["positive_tickers"],
                "ZeroTickers": breadth["zero_tickers"],
                "NegativeTickers": breadth["negative_tickers"],
                "TopPositiveShare": breadth["top_positive_share"],
            }
        )

    out = pd.DataFrame(rows)
    scoreboard_csv = RESULTS_DIR / "setup_library_scoreboard.csv"
    out.to_csv(scoreboard_csv, index=False)
    main_logger.info(f"[SETUPS] setup-library scoreboard saved: {scoreboard_csv}")
    print(f"[SETUPS] setup-library scoreboard saved: {scoreboard_csv}")
    return out

def run_signal_baseline_suite(
    ticker_list: List[str],
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
    max_windows_per_ticker: int = 1,
    policy_filter: Optional[List[str]] = None,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = baseline_dir / "baseline_walk_forward_summary.csv"
    coverage_csv = baseline_dir / "signal_coverage_summary.csv"
    policy_csv = baseline_dir / "baseline_policy_summary.csv"

    def _write_baseline_checkpoints(rows_accum: List[dict], coverage_accum: List[dict]) -> None:
        summary_df_local = pd.DataFrame(rows_accum)
        coverage_df_local = pd.DataFrame(coverage_accum)
        summary_df_local.to_csv(summary_csv, index=False)
        coverage_df_local.to_csv(coverage_csv, index=False)
        if summary_df_local.empty:
            return
        policy_summary_local = (
            summary_df_local.groupby("policy")[
                ["test_return", "test_drawdown", "test_sharpe", "test_turnover", "test_trades"]
            ]
            .mean()
            .reset_index()
            .sort_values(["test_return", "test_sharpe"], ascending=[False, False])
        )
        policy_summary_local.to_csv(policy_csv, index=False)

    policy_names = [
        "SIGNAL_E102",
        "SIGNAL_E102_LONGONLY",
        "SIGNAL_E102_SYMMETRIC",
        "SIGNAL_E102_BANDED",
        "SIGNAL_E102_BANDED_62",
        "SIGNAL_E102_BANDED_64",
        "SIGNAL_E102_BANDED_66",
        "SIGNAL_E102_BANDED_68",
        "SIGNAL_E102_BANDED_70",
        "SIGNAL_E102_BANDED_72",
        "SIGNAL_E302",
        "SIGNAL_E302_LONGONLY",
        "SIGNAL_E302_SYMMETRIC",
        "SIGNAL_E302_BANDED",
        "SIGNAL_E302_BANDED_62",
        "SIGNAL_E302_BANDED_64",
        "SIGNAL_E302_BANDED_66",
        "SIGNAL_E302_BANDED_68",
        "SIGNAL_E302_BANDED_70",
        "SIGNAL_E401_LONGONLY",
        "SIGNAL_E401_BANDED_64",
        "SIGNAL_E401_BANDED_66",
        "SIGNAL_E401_BANDED_68",
        "SIGNAL_E401_BANDED_70",
        "SIGNAL_E407_LONGONLY",
        "SIGNAL_E407_BANDED_64",
        "SIGNAL_E407_BANDED_66",
        "SIGNAL_E407_BANDED_68",
        "SIGNAL_E407_BANDED_70",
        "SIGNAL_E209_LONGONLY",
        "SIGNAL_E209_BANDED_64",
        "SIGNAL_E209_BANDED_66",
        "SIGNAL_E209_BANDED_68",
        "SIGNAL_E209_BANDED_70",
        "SIGNAL_E211_LONGONLY",
        "SIGNAL_E211_BANDED_64",
        "SIGNAL_E211_BANDED_66",
        "SIGNAL_E211_BANDED_68",
        "SIGNAL_E211_BANDED_70",
        "SIGNAL_E211_VETO_INTRAHOUR",
        "SIGNAL_COMBO_E102_E302_BANDED",
        "SIGNAL_COMBO_E102_E302_BANDED_70",
        "SIGNAL_COMBO_E102_E302_BANDED_72",
        "SMA",
        "RSI",
        "FLAT",
    ]
    for experiment_id in [f"E50{i}" for i in range(1, 9)]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E605", "E606", "E607", "E610"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E702", "E703", "E705", "E706"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E801", "E803", "E804", "E806"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E903", "E904", "E905", "E906"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1101", "E1102", "E1103", "E1104", "E1105", "E1106"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1201", "E1202", "E1203", "E1204"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1301", "E1302", "E1303", "E1304"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1401", "E1402", "E1403", "E1404"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1501", "E1502", "E1503", "E1504"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1601", "E1602", "E1603", "E1604"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1701", "E1702", "E1703", "E1704"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2701", "E2702", "E2703", "E2704"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1801", "E1802", "E1803", "E1804"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E1901", "E1902", "E1903", "E1904"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2001", "E2002", "E2003", "E2004"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2101", "E2102", "E2103", "E2104"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2201", "E2202", "E2203", "E2204"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2301", "E2302", "E2303", "E2304"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2501", "E2502", "E2503", "E2504"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2601", "E2602", "E2603", "E2604"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    for experiment_id in ["E2801", "E2802", "E2803", "E2804", "E2805", "E2806"]:
        policy_names.extend(build_signal_policy_family(experiment_id))
    policy_names.extend(EVENT_CONDITIONED_SIZING_VETO_POLICY_NAMES)
    if policy_filter:
        wanted = {policy.strip() for policy in policy_filter if policy and policy.strip()}
        policy_names = [policy for policy in policy_names if policy in wanted]
        print(
            "[BASELINE] evaluating policies: "
            + (", ".join(policy_names) if policy_names else "<none>")
        )
    rows = []
    coverage_rows = []
    total_tickers = len(ticker_list)

    env_kwargs = {
        "stop_loss": best_params.get("stop_loss", stop_loss),
        "take_profit": best_params.get("take_profit", take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
        "hold_threshold": best_params.get("hold_threshold", 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
    }

    for ticker_idx, ticker in enumerate(ticker_list, start=1):
        print(f"[BASELINE] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[BASELINE:{ticker}] token missing, skipping.")
            print(f"[BASELINE] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (token missing)")
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            main_logger.warning(f"[BASELINE:{ticker}] no data, skipping.")
            print(f"[BASELINE] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (no data)")
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days,
        )
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        if not windows:
            main_logger.warning(f"[BASELINE:{ticker}] no walk-forward windows, skipping.")
            print(f"[BASELINE] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (no windows)")
            continue

        print(f"[BASELINE] ticker {ticker_idx}/{total_tickers}: {ticker} - {len(windows)} cycle(s)")
        for cycle_idx, (s, tr_end, va_end, te_end) in enumerate(windows, start=1):
            val_df = df_full.iloc[tr_end:va_end].reset_index(drop=True)
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if val_df.empty or test_df.empty:
                print(f"[BASELINE] {ticker} cycle {cycle_idx}/{len(windows)} - skipped (empty split)")
                continue
            val_cov = summarize_signal_slice_coverage(val_df, ticker, cycle_idx, "val")
            test_cov = summarize_signal_slice_coverage(test_df, ticker, cycle_idx, "test")
            coverage_rows.extend([val_cov, test_cov])
            print(
                f"[BASELINE] {ticker} cycle {cycle_idx}/{len(windows)} - "
                f"val {len(val_df)} / test {len(test_df)}"
            )
            print(
                f"[BASELINE] {ticker} cycle {cycle_idx}/{len(windows)} coverage - "
                f"val nondefault {val_cov['signal_nondefault_pct']:.1%}, "
                f"test nondefault {test_cov['signal_nondefault_pct']:.1%}, "
                f"test p90 {test_cov['signal_pred_p90']:.3f}"
            )
            for policy_name in policy_names:
                val_res = run_baseline_backtest(val_df, ticker, initial_balance, env_kwargs, policy_name, seed=RANDOM_SEED + cycle_idx)
                test_res = run_baseline_backtest(test_df, ticker, initial_balance, env_kwargs, policy_name, seed=RANDOM_SEED + 1000 + cycle_idx)
                val_metrics = val_res["metrics"]
                test_metrics = test_res["metrics"]
                rows.append({
                    "ticker": ticker,
                    "cycle": cycle_idx,
                    "policy": policy_name,
                    "val_rows": len(val_df),
                    "test_rows": len(test_df),
                    "val_return": val_metrics["total_return"],
                    "val_drawdown": val_metrics["max_drawdown"],
                    "val_sharpe": val_metrics["sharpe"],
                    "val_turnover": val_metrics["turnover"],
                    "val_trades": val_metrics["trade_count"],
                    "test_return": test_metrics["total_return"],
                    "test_drawdown": test_metrics["max_drawdown"],
                    "test_sharpe": test_metrics["sharpe"],
                    "test_turnover": test_metrics["turnover"],
                    "test_trades": test_metrics["trade_count"],
                    **{f"val_{k}": v for k, v in val_res["directional"].items()},
                    **{f"test_{k}": v for k, v in test_res["directional"].items()},
                })
                print(
                    f"[BASELINE] {ticker} cycle {cycle_idx}/{len(windows)} {policy_name} - "
                    f"test return {test_metrics['total_return']:.4f}, "
                    f"sharpe {test_metrics['sharpe']:.4f}, turnover {test_metrics['turnover']:.4f}"
                )
            _write_baseline_checkpoints(rows, coverage_rows)

    summary_df = pd.DataFrame(rows)
    coverage_df = pd.DataFrame(coverage_rows)
    summary_df.to_csv(summary_csv, index=False)
    coverage_df.to_csv(coverage_csv, index=False)
    if not summary_df.empty:
        policy_summary = (
            summary_df.groupby("policy")[
                ["test_return", "test_drawdown", "test_sharpe", "test_turnover", "test_trades"]
            ]
            .mean()
            .reset_index()
            .sort_values(["test_return", "test_sharpe"], ascending=[False, False])
        )
        policy_summary.to_csv(policy_csv, index=False)
        e302_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    [
                        "FLAT",
                        "SIGNAL_E302_LONGONLY",
                        "SIGNAL_E302_BANDED_64",
                        "SIGNAL_E302_BANDED_66",
                        "SIGNAL_E302_BANDED_68",
                        "SIGNAL_E302_BANDED_70",
                    ]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        e302_policy_csv = baseline_dir / "e302_policy_summary.csv"
        e302_policy_summary.to_csv(e302_policy_csv, index=False)
        generalization_next_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    [
                        "FLAT",
                        "SIGNAL_E401_LONGONLY",
                        "SIGNAL_E401_BANDED_64",
                        "SIGNAL_E401_BANDED_66",
                        "SIGNAL_E401_BANDED_68",
                        "SIGNAL_E401_BANDED_70",
                        "SIGNAL_E407_LONGONLY",
                        "SIGNAL_E407_BANDED_64",
                        "SIGNAL_E407_BANDED_66",
                        "SIGNAL_E407_BANDED_68",
                        "SIGNAL_E407_BANDED_70",
                    ]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        generalization_next_policy_csv = baseline_dir / "generalization_next_policy_summary.csv"
        generalization_next_policy_summary.to_csv(generalization_next_policy_csv, index=False)
        e102_deepdive_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    [
                        "FLAT",
                        "SIGNAL_E102_BANDED_70",
                        "SIGNAL_E102_BANDED_72",
                        "SIGNAL_E209_LONGONLY",
                        "SIGNAL_E209_BANDED_64",
                        "SIGNAL_E209_BANDED_66",
                        "SIGNAL_E209_BANDED_68",
                        "SIGNAL_E209_BANDED_70",
                        "SIGNAL_E211_LONGONLY",
                        "SIGNAL_E211_BANDED_64",
                        "SIGNAL_E211_BANDED_66",
                        "SIGNAL_E211_BANDED_68",
                        "SIGNAL_E211_BANDED_70",
                    ]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        e102_deepdive_policy_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
        e102_deepdive_policy_summary.to_csv(e102_deepdive_policy_csv, index=False)
        cross_sectional_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E5")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        cross_sectional_policy_csv = baseline_dir / "cross_sectional_60m_policy_summary.csv"
        cross_sectional_policy_summary.to_csv(cross_sectional_policy_csv, index=False)
        cross_sectional_scoreboard = build_cross_sectional_scoreboard(summary_df, policy_summary)
        cross_sectional_scoreboard_csv = baseline_dir / "cross_sectional_60m_branch_scoreboard.csv"
        if not cross_sectional_scoreboard.empty:
            cross_sectional_scoreboard.to_csv(cross_sectional_scoreboard_csv, index=False)
        ablation_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E60")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        ablation_policy_csv = baseline_dir / "ablation_grid_policy_summary.csv"
        ablation_policy_summary.to_csv(ablation_policy_csv, index=False)
        setup_regime_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E70")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        setup_regime_policy_csv = baseline_dir / "setup_regime_policy_summary.csv"
        setup_regime_policy_summary.to_csv(setup_regime_policy_csv, index=False)
        market_state_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E80")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        market_state_policy_csv = baseline_dir / "market_state_60m_policy_summary.csv"
        market_state_policy_summary.to_csv(market_state_policy_csv, index=False)
        multiscale_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E90")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        multiscale_policy_csv = baseline_dir / "multiscale_60m_policy_summary.csv"
        multiscale_policy_summary.to_csv(multiscale_policy_csv, index=False)
        second_timeframe_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E11")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        second_timeframe_policy_csv = baseline_dir / "second_timeframe_60m_policy_summary.csv"
        second_timeframe_policy_summary.to_csv(second_timeframe_policy_csv, index=False)
        intrahour_path_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E12")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        intrahour_path_policy_csv = baseline_dir / "intrahour_path_v1_policy_summary.csv"
        intrahour_path_policy_summary.to_csv(intrahour_path_policy_csv, index=False)
        breadth_context_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E13")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        breadth_context_policy_csv = baseline_dir / "breadth_context_60m_policy_summary.csv"
        breadth_context_policy_summary.to_csv(breadth_context_policy_csv, index=False)
        time_distribution_policy_summary = (
            policy_summary.loc[
                policy_summary["policy"].isin(
                    ["FLAT", "SIGNAL_E211_BANDED_68"]
                    + [policy for policy in policy_summary["policy"].tolist() if isinstance(policy, str) and policy.startswith("SIGNAL_E14")]
                )
            ]
            .sort_values(["test_return", "test_turnover", "test_trades"], ascending=[False, True, True])
            .reset_index(drop=True)
        )
        time_distribution_policy_csv = baseline_dir / "time_distribution_v2_policy_summary.csv"
        time_distribution_policy_summary.to_csv(time_distribution_policy_csv, index=False)
        main_logger.info(f"[BASELINE] summary saved: {summary_csv}")
        main_logger.info(f"[BASELINE] signal coverage saved: {coverage_csv}")
        main_logger.info(f"[BASELINE] policy summary saved: {policy_csv}")
        main_logger.info(f"[BASELINE] E302 policy summary saved: {e302_policy_csv}")
        main_logger.info(f"[BASELINE] generalization-next policy summary saved: {generalization_next_policy_csv}")
        main_logger.info(f"[BASELINE] E102 deep-dive policy summary saved: {e102_deepdive_policy_csv}")
        main_logger.info(f"[BASELINE] cross-sectional policy summary saved: {cross_sectional_policy_csv}")
        if not cross_sectional_scoreboard.empty:
            main_logger.info(f"[BASELINE] cross-sectional branch scoreboard saved: {cross_sectional_scoreboard_csv}")
        main_logger.info(f"[BASELINE] ablation-grid policy summary saved: {ablation_policy_csv}")
        main_logger.info(f"[BASELINE] setup-regime policy summary saved: {setup_regime_policy_csv}")
        main_logger.info(f"[BASELINE] market-state policy summary saved: {market_state_policy_csv}")
        main_logger.info(f"[BASELINE] multiscale policy summary saved: {multiscale_policy_csv}")
        main_logger.info(f"[BASELINE] second-timeframe policy summary saved: {second_timeframe_policy_csv}")
        main_logger.info(f"[BASELINE] intrahour-path policy summary saved: {intrahour_path_policy_csv}")
        main_logger.info(f"[BASELINE] breadth-context policy summary saved: {breadth_context_policy_csv}")
        main_logger.info(f"[BASELINE] time-distribution policy summary saved: {time_distribution_policy_csv}")
        print(f"[BASELINE] summary saved: {summary_csv}")
        print(f"[BASELINE] signal coverage saved: {coverage_csv}")
        print(f"[BASELINE] policy summary saved: {policy_csv}")
        print(f"[BASELINE] E302 policy summary saved: {e302_policy_csv}")
        print(f"[BASELINE] generalization-next policy summary saved: {generalization_next_policy_csv}")
        print(f"[BASELINE] E102 deep-dive policy summary saved: {e102_deepdive_policy_csv}")
        print(f"[BASELINE] cross-sectional policy summary saved: {cross_sectional_policy_csv}")
        if not cross_sectional_scoreboard.empty:
            print(f"[BASELINE] cross-sectional branch scoreboard saved: {cross_sectional_scoreboard_csv}")
        print(f"[BASELINE] ablation-grid policy summary saved: {ablation_policy_csv}")
        print(f"[BASELINE] setup-regime policy summary saved: {setup_regime_policy_csv}")
        print(f"[BASELINE] market-state policy summary saved: {market_state_policy_csv}")
        print(f"[BASELINE] multiscale policy summary saved: {multiscale_policy_csv}")
        print(f"[BASELINE] second-timeframe policy summary saved: {second_timeframe_policy_csv}")
        print(f"[BASELINE] intrahour-path policy summary saved: {intrahour_path_policy_csv}")
        print(f"[BASELINE] breadth-context policy summary saved: {breadth_context_policy_csv}")
        print(f"[BASELINE] time-distribution policy summary saved: {time_distribution_policy_csv}")
    else:
        main_logger.warning("[BASELINE] no baseline rows were produced.")
        print("[BASELINE] no baseline rows were produced.")
    return summary_df


def run_signal_cost_sensitivity_audit(
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
    train_days: int = 730,
    val_days: int = 90,
    test_days: int = 30,
    step_days: int = 30,
    max_windows_per_ticker: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    policies = [
        "SIGNAL_E211_BANDED_68",
        "SIGNAL_E801_BANDED_70",
        "SIGNAL_E1102_BANDED_70",
        "FLAT",
    ]
    friction_profiles = [
        {"FrictionProfile": "realistic", "slippage_rate": 0.0010, "disable_costs": False},
        {"FrictionProfile": "half_slippage", "slippage_rate": 0.0005, "disable_costs": False},
        {"FrictionProfile": "fees_only", "slippage_rate": 0.0, "disable_costs": False},
        {"FrictionProfile": "frictionless", "slippage_rate": 0.0, "disable_costs": True},
    ]

    rows = []
    total_tickers = len(ticker_list)

    base_env_kwargs = {
        "stop_loss": best_params.get("stop_loss", stop_loss),
        "take_profit": best_params.get("take_profit", take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
        "hold_threshold": best_params.get("hold_threshold", 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
    }

    for ticker_idx, ticker in enumerate(ticker_list, start=1):
        print(f"[COST AUDIT] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[COST AUDIT:{ticker}] token missing, skipping.")
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            main_logger.warning(f"[COST AUDIT:{ticker}] no data, skipping.")
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days,
        )
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        if not windows:
            main_logger.warning(f"[COST AUDIT:{ticker}] no walk-forward windows, skipping.")
            continue

        for cycle_idx, (s, tr_end, va_end, te_end) in enumerate(windows, start=1):
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if test_df.empty:
                continue
            for profile in friction_profiles:
                env_kwargs = dict(base_env_kwargs)
                env_kwargs["slippage_rate"] = profile["slippage_rate"]
                env_kwargs["disable_costs"] = profile["disable_costs"]
                for policy_name in policies:
                    res = run_baseline_backtest(
                        test_df,
                        ticker,
                        initial_balance,
                        env_kwargs,
                        policy_name,
                        seed=RANDOM_SEED + 2000 + cycle_idx,
                    )
                    metrics = res["metrics"]
                    rows.append(
                        {
                            "ticker": ticker,
                            "cycle": cycle_idx,
                            "policy": policy_name,
                            "friction_profile": profile["FrictionProfile"],
                            "slippage_rate": profile["slippage_rate"],
                            "disable_costs": profile["disable_costs"],
                            "test_return": metrics["total_return"],
                            "test_drawdown": metrics["max_drawdown"],
                            "test_sharpe": metrics["sharpe"],
                            "test_turnover": metrics["turnover"],
                            "test_trades": metrics["trade_count"],
                        }
                    )

    detail_df = pd.DataFrame(rows)
    detail_csv = baseline_dir / "cost_sensitivity_detail.csv"
    detail_df.to_csv(detail_csv, index=False)

    if detail_df.empty:
        summary_df = pd.DataFrame()
    else:
        summary_df = (
            detail_df.groupby(["friction_profile", "policy"])[
                ["test_return", "test_drawdown", "test_sharpe", "test_turnover", "test_trades"]
            ]
            .mean()
            .reset_index()
            .sort_values(["friction_profile", "test_return"], ascending=[True, False])
        )
        benchmark_rows = summary_df.loc[summary_df["policy"] == "SIGNAL_E211_BANDED_68", ["friction_profile", "test_return"]].rename(
            columns={"test_return": "benchmark_return"}
        )
        summary_df = summary_df.merge(benchmark_rows, on="friction_profile", how="left")
        summary_df["excess_vs_e211"] = pd.to_numeric(summary_df["test_return"], errors="coerce") - pd.to_numeric(summary_df["benchmark_return"], errors="coerce")

    summary_csv = baseline_dir / "cost_sensitivity_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    main_logger.info(f"[COST AUDIT] detail saved: {detail_csv}")
    main_logger.info(f"[COST AUDIT] summary saved: {summary_csv}")
    print(f"[COST AUDIT] detail saved: {detail_csv}")
    print(f"[COST AUDIT] summary saved: {summary_csv}")
    return detail_df, summary_df


def run_signal_futures_cost_profile_audit(
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
    train_days: int = 730,
    val_days: int = 90,
    test_days: int = 30,
    step_days: int = 30,
    max_windows_per_ticker: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    policies = [
        "SIGNAL_E211_BANDED_68",
        "SIGNAL_E801_BANDED_70",
        "SIGNAL_E1102_BANDED_70",
        "FLAT",
    ]
    cost_profiles = [
        {"CostProfile": "cash_equity_realistic", "cost_profile": "cash_equity", "slippage_rate": 0.0010, "disable_costs": False},
        {"CostProfile": "cash_equity_half_slippage", "cost_profile": "cash_equity", "slippage_rate": 0.0005, "disable_costs": False},
        {"CostProfile": "stock_futures_realistic", "cost_profile": "stock_futures", "slippage_rate": 0.0010, "disable_costs": False},
        {"CostProfile": "stock_futures_half_slippage", "cost_profile": "stock_futures", "slippage_rate": 0.0005, "disable_costs": False},
        {"CostProfile": "stock_futures_fees_only", "cost_profile": "stock_futures", "slippage_rate": 0.0, "disable_costs": False},
        {"CostProfile": "stock_futures_frictionless", "cost_profile": "stock_futures", "slippage_rate": 0.0, "disable_costs": True},
    ]

    rows = []
    total_tickers = len(ticker_list)

    base_env_kwargs = {
        "stop_loss": best_params.get("stop_loss", stop_loss),
        "take_profit": best_params.get("take_profit", take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
        "hold_threshold": best_params.get("hold_threshold", 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
    }

    for ticker_idx, ticker in enumerate(ticker_list, start=1):
        print(f"[FUTURES COST AUDIT] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.warning(f"[FUTURES COST AUDIT:{ticker}] token missing, skipping.")
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=history_days, interval=interval)
        if df_full.empty:
            main_logger.warning(f"[FUTURES COST AUDIT:{ticker}] no data, skipping.")
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval=interval,
            train_days=train_days,
            val_days=val_days,
            test_days=test_days,
            step_days=step_days,
        )
        if max_windows_per_ticker > 0:
            windows = windows[:max_windows_per_ticker]
        if not windows:
            main_logger.warning(f"[FUTURES COST AUDIT:{ticker}] no walk-forward windows, skipping.")
            continue

        for cycle_idx, (s, tr_end, va_end, te_end) in enumerate(windows, start=1):
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if test_df.empty:
                continue
            for profile in cost_profiles:
                env_kwargs = dict(base_env_kwargs)
                env_kwargs["cost_profile"] = profile["cost_profile"]
                env_kwargs["slippage_rate"] = profile["slippage_rate"]
                env_kwargs["disable_costs"] = profile["disable_costs"]
                for policy_name in policies:
                    res = run_baseline_backtest(
                        test_df,
                        ticker,
                        initial_balance,
                        env_kwargs,
                        policy_name,
                        seed=RANDOM_SEED + 3000 + cycle_idx,
                    )
                    metrics = res["metrics"]
                    rows.append(
                        {
                            "ticker": ticker,
                            "cycle": cycle_idx,
                            "policy": policy_name,
                            "cost_profile_label": profile["CostProfile"],
                            "cost_profile": profile["cost_profile"],
                            "slippage_rate": profile["slippage_rate"],
                            "disable_costs": profile["disable_costs"],
                            "test_return": metrics["total_return"],
                            "test_drawdown": metrics["max_drawdown"],
                            "test_sharpe": metrics["sharpe"],
                            "test_turnover": metrics["turnover"],
                            "test_trades": metrics["trade_count"],
                        }
                    )

    detail_df = pd.DataFrame(rows)
    detail_csv = baseline_dir / "futures_cost_profile_detail.csv"
    detail_df.to_csv(detail_csv, index=False)

    if detail_df.empty:
        summary_df = pd.DataFrame()
    else:
        summary_df = (
            detail_df.groupby(["cost_profile_label", "policy"])[
                ["test_return", "test_drawdown", "test_sharpe", "test_turnover", "test_trades"]
            ]
            .mean()
            .reset_index()
            .sort_values(["cost_profile_label", "test_return"], ascending=[True, False])
        )
        benchmark_rows = summary_df.loc[
            summary_df["policy"] == "SIGNAL_E211_BANDED_68",
            ["cost_profile_label", "test_return"],
        ].rename(columns={"test_return": "benchmark_return"})
        summary_df = summary_df.merge(benchmark_rows, on="cost_profile_label", how="left")
        summary_df["excess_vs_e211"] = (
            pd.to_numeric(summary_df["test_return"], errors="coerce")
            - pd.to_numeric(summary_df["benchmark_return"], errors="coerce")
        )

    summary_csv = baseline_dir / "futures_cost_profile_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    main_logger.info(f"[FUTURES COST AUDIT] detail saved: {detail_csv}")
    main_logger.info(f"[FUTURES COST AUDIT] summary saved: {summary_csv}")
    print(f"[FUTURES COST AUDIT] detail saved: {detail_csv}")
    print(f"[FUTURES COST AUDIT] summary saved: {summary_csv}")
    return detail_df, summary_df


def run_signal_bucket_quality_diagnostic() -> tuple[pd.DataFrame, pd.DataFrame]:
    signal_research_dir = RESULTS_DIR / "signal_research"
    diagnostic_sources = [
        {
            "branch": "E211_Incumbent",
            "experiment_id": "E211",
            "source_csv": signal_research_dir / "outputs_e102_deepdive" / "latest" / "promoted_predictions_oos.csv",
        },
        {
            "branch": "MarketState60m",
            "experiment_id": "E801",
            "source_csv": signal_research_dir / "outputs_market_state_60m" / "latest" / "promoted_predictions_oos.csv",
        },
    ]

    detail_rows = []
    summary_rows = []

    for src in diagnostic_sources:
        path = src["source_csv"]
        if not path.exists():
            main_logger.warning(f"[BUCKET DIAG] missing source file for {src['experiment_id']}: {path}")
            continue
        try:
            df = pd.read_csv(path, usecols=["ExperimentID", "Prediction", "RealizedReturn"])
        except Exception as exc:
            main_logger.warning(f"[BUCKET DIAG] failed to read {path}: {exc}")
            continue

        df = df.loc[df["ExperimentID"].astype(str) == src["experiment_id"]].copy()
        if df.empty:
            main_logger.warning(f"[BUCKET DIAG] no rows found for {src['experiment_id']} in {path}")
            continue

        df["Prediction"] = pd.to_numeric(df["Prediction"], errors="coerce")
        df["RealizedReturn"] = pd.to_numeric(df["RealizedReturn"], errors="coerce")
        df = df.dropna(subset=["Prediction", "RealizedReturn"]).copy()
        if len(df) < 50:
            main_logger.warning(f"[BUCKET DIAG] too few valid rows for {src['experiment_id']}: {len(df)}")
            continue

        df["rank_pct"] = df["Prediction"].rank(method="average", pct=True)
        df["bucket"] = np.minimum(10, np.maximum(1, np.ceil(df["rank_pct"] * 10).astype(int)))

        bucket_df = (
            df.groupby("bucket")
            .agg(
                row_count=("RealizedReturn", "size"),
                mean_prediction=("Prediction", "mean"),
                min_prediction=("Prediction", "min"),
                max_prediction=("Prediction", "max"),
                avg_realized_return=("RealizedReturn", "mean"),
                median_realized_return=("RealizedReturn", "median"),
                positive_rate=("RealizedReturn", lambda s: float((s > 0).mean()) if len(s) else np.nan),
            )
            .reset_index()
            .sort_values("bucket")
        )

        top_ret = float(bucket_df.loc[bucket_df["bucket"] == 10, "avg_realized_return"].iloc[0]) if (bucket_df["bucket"] == 10).any() else np.nan
        bottom_ret = float(bucket_df.loc[bucket_df["bucket"] == 1, "avg_realized_return"].iloc[0]) if (bucket_df["bucket"] == 1).any() else np.nan
        spread = top_ret - bottom_ret if np.isfinite(top_ret) and np.isfinite(bottom_ret) else np.nan
        monotonic_corr = float(bucket_df["bucket"].corr(bucket_df["avg_realized_return"], method="spearman")) if len(bucket_df) >= 3 else np.nan

        summary_rows.append(
            {
                "Branch": src["branch"],
                "ExperimentID": src["experiment_id"],
                "RowCount": int(len(df)),
                "TopDecileAvgReturn": top_ret,
                "BottomDecileAvgReturn": bottom_ret,
                "SpreadTopMinusBottom": spread,
                "BucketReturnSpearman": monotonic_corr,
                "OverallMeanPrediction": float(df["Prediction"].mean()),
                "OverallMeanRealizedReturn": float(df["RealizedReturn"].mean()),
            }
        )

        for _, row in bucket_df.iterrows():
            detail_rows.append(
                {
                    "Branch": src["branch"],
                    "ExperimentID": src["experiment_id"],
                    "Bucket": int(row["bucket"]),
                    "RowCount": int(row["row_count"]),
                    "MeanPrediction": float(row["mean_prediction"]),
                    "MinPrediction": float(row["min_prediction"]),
                    "MaxPrediction": float(row["max_prediction"]),
                    "AvgRealizedReturn": float(row["avg_realized_return"]),
                    "MedianRealizedReturn": float(row["median_realized_return"]),
                    "PositiveRate": float(row["positive_rate"]),
                }
            )

    detail_df = pd.DataFrame(detail_rows)
    summary_df = pd.DataFrame(summary_rows)

    detail_csv = signal_research_dir / "signal_bucket_quality_detail.csv"
    summary_csv = signal_research_dir / "signal_bucket_quality_summary.csv"
    detail_df.to_csv(detail_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    main_logger.info(f"[BUCKET DIAG] detail saved: {detail_csv}")
    main_logger.info(f"[BUCKET DIAG] summary saved: {summary_csv}")
    print(f"[BUCKET DIAG] detail saved: {detail_csv}")
    print(f"[BUCKET DIAG] summary saved: {summary_csv}")
    return detail_df, summary_df


def run_portfolio_rank_baseline(
    promoted_ids: List[str],
    top_k: int = 3,
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    portfolio_style: str = "long_short",
    rebalance_every_sessions: int = 1,
    output_stem: str = "portfolio_rank_60m_portfolio",
    source_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    from signal_targets import estimate_roundtrip_cost

    def _load_portfolio_rank_merged_predictions() -> tuple[pd.DataFrame, float]:
        research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
        predictions_csv = research_dir / "promoted_predictions_oos.csv"
        if not predictions_csv.exists():
            predictions_csv = research_dir / "experiment_predictions_oos.csv"
        dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"

        if not predictions_csv.exists() or not dataset_csv.exists():
            main_logger.warning("[PORTFOLIO-RANK] missing predictions or dataset; no baseline rows were produced.")
            return pd.DataFrame(), 0.0

        pred_df = pd.read_csv(predictions_csv)
        data_df = pd.read_csv(dataset_csv)
        if pred_df.empty or data_df.empty:
            main_logger.warning("[PORTFOLIO-RANK] empty predictions or dataset; no baseline rows were produced.")
            return pd.DataFrame(), 0.0

        pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
        data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
        data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
        merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
        merged_df = pred_df.merge(
            data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
            on=["Ticker", "Date"],
            how="left",
        )
        merged_df["TradeDate"] = merged_df["Date"].dt.normalize()

        benchmark_return_local = 0.0
        benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
        if benchmark_summary_csv.exists():
            try:
                bench_df = pd.read_csv(benchmark_summary_csv)
                bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
                if not bench_row.empty:
                    benchmark_return_local = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
            except Exception as exc:
                main_logger.warning(f"[PORTFOLIO-RANK] failed to read benchmark summary: {exc}")
        return merged_df, benchmark_return_local

    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = baseline_dir / f"{output_stem}_baseline_summary.csv"
    history_csv = baseline_dir / f"{output_stem}_rebalance_history.csv"
    contrib_csv = baseline_dir / f"{output_stem}_ticker_contributions.csv"
    portfolio_style = str(portfolio_style or "long_short").strip().lower()
    rebalance_every_sessions = max(1, int(rebalance_every_sessions))

    if source_df is None:
        merged, benchmark_return = _load_portfolio_rank_merged_predictions()
    else:
        merged = source_df.copy()
        benchmark_return = 0.0
        benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
        if benchmark_summary_csv.exists():
            try:
                bench_df = pd.read_csv(benchmark_summary_csv)
                bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
                if not bench_row.empty:
                    benchmark_return = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
            except Exception as exc:
                main_logger.warning(f"[PORTFOLIO-RANK] failed to read benchmark summary: {exc}")
        if "Date" in merged.columns:
            merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
        if "TradeDate" not in merged.columns and "Date" in merged.columns:
            merged["TradeDate"] = merged["Date"].dt.normalize()
    if merged.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        return pd.DataFrame()

    rows = []
    history_rows = []
    contribution_rows = []

    for experiment_id in promoted_ids:
        exp_df = merged.loc[merged["ExperimentID"] == experiment_id].copy()
        if exp_df.empty:
            continue
        exp_df = exp_df.dropna(subset=["Date", "Ticker", "Prediction", "Close"]).copy()
        if exp_df.empty:
            continue
        open_times = (
            exp_df.groupby("TradeDate")["Date"]
            .min()
            .dropna()
            .sort_values()
            .tolist()
        )
        prev_weights: Dict[str, float] = {}
        event_returns: List[float] = []
        event_turnovers: List[float] = []
        event_longs: List[float] = []
        event_shorts: List[float] = []
        ticker_contrib: Dict[str, float] = {}

        min_names_required = top_k if portfolio_style == "long_only" else 2 * top_k
        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts:
                continue
            current = exp_df.loc[exp_df["Date"] == open_ts].copy()
            future = exp_df.loc[exp_df["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            if len(current) < min_names_required:
                continue
            current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            if len(current) < min_names_required:
                continue

            current = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            current["est_cost"] = estimate_roundtrip_cost(current)
            longs = current.head(top_k).copy()
            shorts = current.tail(top_k).copy() if portfolio_style == "long_short" else current.iloc[0:0].copy()

            weights: Dict[str, float] = {}
            if portfolio_style == "long_only":
                long_weight = 1.0 / top_k
                short_weight = 0.0
            else:
                long_weight = 0.5 / top_k
                short_weight = -0.5 / top_k

            event_return = 0.0
            long_return = 0.0
            short_return = 0.0
            for _, row in longs.iterrows():
                raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                contribution = long_weight * raw_ret - abs(long_weight) * float(row["est_cost"])
                event_return += contribution
                long_return += contribution
                ticker = str(row["Ticker"])
                weights[ticker] = long_weight
                ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution

            if portfolio_style == "long_short":
                for _, row in shorts.iterrows():
                    raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                    contribution = short_weight * raw_ret - abs(short_weight) * float(row["est_cost"])
                    event_return += contribution
                    short_return += contribution
                    ticker = str(row["Ticker"])
                    weights[ticker] = short_weight
                    ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution

            universe = set(prev_weights) | set(weights)
            turnover = float(sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in universe))
            prev_weights = weights

            event_returns.append(event_return)
            event_turnovers.append(turnover)
            event_longs.append(long_return)
            event_shorts.append(short_return)
            history_rows.append(
                {
                    "experiment_id": experiment_id,
                    "rebalance_idx": idx + 1,
                    "open_ts": open_ts,
                    "next_open_ts": next_open_ts,
                    "eligible_count": int(len(current)),
                    "portfolio_return": event_return,
                    "long_contribution": long_return,
                    "short_contribution": short_return,
                    "turnover": turnover,
                    "long_names": ",".join(longs["Ticker"].astype(str).tolist()),
                    "short_names": ",".join(shorts["Ticker"].astype(str).tolist()) if portfolio_style == "long_short" else "",
                }
            )

        if not event_returns:
            continue

        contrib_total_abs = float(sum(abs(v) for v in ticker_contrib.values()))
        top_contrib_share = 0.0
        if contrib_total_abs > 0:
            top_contrib_share = max(abs(v) for v in ticker_contrib.values()) / contrib_total_abs

        for ticker, contribution in sorted(ticker_contrib.items()):
            contribution_rows.append(
                {
                    "experiment_id": experiment_id,
                    "ticker": ticker,
                    "pnl_contribution": contribution,
                }
            )

        mean_return = float(np.mean(event_returns))
        row = {
            "experiment_id": experiment_id,
            "portfolio_style": portfolio_style,
            "rebalance_rule": f"every_{rebalance_every_sessions}_session_open",
            "top_k": top_k,
            "rebalance_count": int(len(event_returns)),
            "portfolio_mean_return": mean_return,
            "portfolio_median_return": float(np.median(event_returns)),
            "portfolio_std_return": float(np.std(event_returns)),
            "portfolio_mean_turnover": float(np.mean(event_turnovers)) if event_turnovers else np.nan,
            "portfolio_mean_long_contribution": float(np.mean(event_longs)) if event_longs else np.nan,
            "portfolio_mean_short_contribution": float(np.mean(event_shorts)) if event_shorts else np.nan,
            "positive_windows": int(sum(val > 0 for val in event_returns)),
            "zero_windows": int(sum(np.isclose(val, 0.0) for val in event_returns)),
            "negative_windows": int(sum(val < 0 for val in event_returns)),
            "portfolio_win_rate": float(np.mean([val > 0 for val in event_returns])),
            "top_contributor_share": top_contrib_share,
            "benchmark_policy": benchmark_policy,
            "benchmark_return": benchmark_return,
            "excess_vs_benchmark": mean_return - benchmark_return,
            "beats_flat": bool(mean_return > 0.0),
            "beats_benchmark": bool(mean_return > benchmark_return),
            "promotion_verdict": "baseline_promoted"
            if (mean_return > 0.0 and mean_return > benchmark_return and top_contrib_share <= 0.60)
            else "research_only",
        }
        rows.append(row)

    summary_df = pd.DataFrame(rows)
    history_df = pd.DataFrame(history_rows)
    contrib_df = pd.DataFrame(contribution_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["portfolio_mean_return", "portfolio_mean_turnover", "rebalance_count"],
            ascending=[False, True, False],
        ).reset_index(drop=True)
    summary_df.to_csv(summary_csv, index=False)
    history_df.to_csv(history_csv, index=False)
    contrib_df.to_csv(contrib_csv, index=False)
    main_logger.info(f"[PORTFOLIO-RANK] summary saved: {summary_csv}")
    main_logger.info(f"[PORTFOLIO-RANK] rebalance history saved: {history_csv}")
    main_logger.info(f"[PORTFOLIO-RANK] ticker contributions saved: {contrib_csv}")
    print(f"[PORTFOLIO-RANK] summary saved: {summary_csv}")
    return summary_df


def run_portfolio_rank_long_only_sweep(
    promoted_ids: List[str],
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    sweep_rows: List[pd.DataFrame] = []

    for top_k, rebalance_every in [(3, 1), (3, 5), (5, 1), (5, 5)]:
        output_stem = f"portfolio_rank_60m_long_only_k{top_k}_r{rebalance_every}"
        summary_df = run_portfolio_rank_baseline(
            promoted_ids=promoted_ids,
            top_k=top_k,
            benchmark_policy=benchmark_policy,
            portfolio_style="long_only",
            rebalance_every_sessions=rebalance_every,
            output_stem=output_stem,
        ).copy()
        if summary_df.empty:
            continue
        summary_df["sweep_top_k"] = int(top_k)
        summary_df["sweep_rebalance_every_sessions"] = int(rebalance_every)
        sweep_rows.append(summary_df)

    combined = pd.concat(sweep_rows, ignore_index=True) if sweep_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_sweep_summary.csv"
    combined.to_csv(combined_csv, index=False)
    main_logger.info(f"[PORTFOLIO-RANK] long-only sweep summary saved: {combined_csv}")
    print(f"[PORTFOLIO-RANK] long-only sweep summary saved: {combined_csv}")
    return combined


def run_portfolio_rank_long_only_cadence_sweep(
    promoted_ids: List[str],
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    sweep_rows: List[pd.DataFrame] = []
    cadence_specs = [(3, 5), (3, 4), (3, 3), (3, 2), (3, 1), (5, 5), (5, 4), (5, 3), (5, 2), (5, 1)]

    print(
        f"[PORTFOLIO-CADENCE] starting cadence sweep for {len(promoted_ids)} experiments across {len(cadence_specs)} variants",
        flush=True,
    )
    for top_k, rebalance_every in cadence_specs:
        output_stem = f"portfolio_rank_60m_long_only_cadence_k{top_k}_r{rebalance_every}"
        print(
            f"[PORTFOLIO-CADENCE] running top_k={top_k} rebalance_every={rebalance_every}",
            flush=True,
        )
        summary_df = run_portfolio_rank_baseline(
            promoted_ids=promoted_ids,
            top_k=top_k,
            benchmark_policy=benchmark_policy,
            portfolio_style="long_only",
            rebalance_every_sessions=rebalance_every,
            output_stem=output_stem,
        ).copy()
        if summary_df.empty:
            print(
                f"[PORTFOLIO-CADENCE] no rows for top_k={top_k} rebalance_every={rebalance_every}",
                flush=True,
            )
            continue
        summary_df["sweep_top_k"] = int(top_k)
        summary_df["sweep_rebalance_every_sessions"] = int(rebalance_every)
        sweep_rows.append(summary_df)

        best_row = summary_df.sort_values(
            ["portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, True],
        ).iloc[0]
        print(
            "[PORTFOLIO-CADENCE] "
            f"best for top_k={top_k} rebalance_every={rebalance_every}: "
            f"{best_row['experiment_id']} ret={float(best_row['portfolio_mean_return']):.6f} "
            f"excess={float(best_row['excess_vs_benchmark']):.6f}",
            flush=True,
        )

    combined = pd.concat(sweep_rows, ignore_index=True) if sweep_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_cadence_summary.csv"
    combined.to_csv(combined_csv, index=False)
    main_logger.info(f"[PORTFOLIO-CADENCE] cadence sweep summary saved: {combined_csv}")
    print(f"[PORTFOLIO-CADENCE] cadence sweep summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_long_only_walkforward(
    promoted_ids: List[str],
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    top_k: int = 3,
    rebalance_every_sessions: int = 5,
    fold_count: int = 3,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    if not predictions_csv.exists() or not dataset_csv.exists():
        main_logger.warning("[PORTFOLIO-WF] missing predictions or dataset; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = pd.read_csv(dataset_csv)
    if pred_df.empty or data_df.empty:
        main_logger.warning("[PORTFOLIO-WF] empty predictions or dataset; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    merged = merged.dropna(subset=["TradeDate"]).copy()
    trade_dates = sorted(pd.Series(merged["TradeDate"].dropna().unique()).tolist())
    if len(trade_dates) < max(2, fold_count):
        main_logger.warning("[PORTFOLIO-WF] insufficient trade dates for fold split; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    date_folds = [list(chunk) for chunk in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), fold_count) if len(chunk) > 0]
    print(
        f"[PORTFOLIO-WF] starting walk-forward validation for {len(promoted_ids)} experiments across {len(date_folds)} contiguous folds",
        flush=True,
    )

    fold_rows: List[pd.DataFrame] = []
    manifest_rows: List[dict] = []
    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_start = pd.Timestamp(fold_dates[0])
        fold_end = pd.Timestamp(fold_dates[-1])
        fold_mask = merged["TradeDate"].isin(pd.to_datetime(fold_dates))
        fold_df = merged.loc[fold_mask].copy()
        manifest_rows.append(
            {
                "fold_id": fold_idx,
                "fold_start_date": fold_start,
                "fold_end_date": fold_end,
                "fold_trade_dates": int(len(fold_dates)),
                "fold_rows": int(len(fold_df)),
            }
        )
        if fold_df.empty:
            print(f"[PORTFOLIO-WF] fold {fold_idx}/{len(date_folds)} empty after filtering; skipped", flush=True)
            continue

        print(
            f"[PORTFOLIO-WF] fold {fold_idx}/{len(date_folds)} {fold_start.date()} -> {fold_end.date()} rows={len(fold_df)}",
            flush=True,
        )
        fold_output_stem = f"portfolio_rank_60m_long_only_walkforward_fold{fold_idx}"
        fold_summary = run_portfolio_rank_baseline(
            promoted_ids=promoted_ids,
            top_k=top_k,
            benchmark_policy=benchmark_policy,
            portfolio_style="long_only",
            rebalance_every_sessions=rebalance_every_sessions,
            output_stem=fold_output_stem,
            source_df=fold_df,
        ).copy()
        if fold_summary.empty:
            print(f"[PORTFOLIO-WF] fold {fold_idx}/{len(date_folds)} produced no summary rows", flush=True)
            continue
        fold_summary["fold_id"] = int(fold_idx)
        fold_summary["fold_start_date"] = fold_start
        fold_summary["fold_end_date"] = fold_end
        fold_summary["fold_trade_dates"] = int(len(fold_dates))
        fold_summary["fold_rows"] = int(len(fold_df))
        fold_rows.append(fold_summary)

        best_row = fold_summary.sort_values(
            ["portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, True],
        ).iloc[0]
        print(
            "[PORTFOLIO-WF] "
            f"best fold {fold_idx}: {best_row['experiment_id']} ret={float(best_row['portfolio_mean_return']):.6f} "
            f"excess={float(best_row['excess_vs_benchmark']):.6f}",
            flush=True,
        )

    combined = pd.concat(fold_rows, ignore_index=True) if fold_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_summary.csv"
    combined.to_csv(combined_csv, index=False)

    aggregate_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_aggregate.csv"
    if combined.empty:
        pd.DataFrame().to_csv(aggregate_csv, index=False)
    else:
        aggregate = (
            combined.groupby(["experiment_id", "portfolio_style", "rebalance_rule", "top_k"], dropna=False)
            .agg(
                fold_count=("fold_id", "nunique"),
                mean_of_fold_returns=("portfolio_mean_return", "mean"),
                min_fold_return=("portfolio_mean_return", "min"),
                max_fold_return=("portfolio_mean_return", "max"),
                std_fold_return=("portfolio_mean_return", "std"),
                mean_of_fold_turnover=("portfolio_mean_turnover", "mean"),
                folds_beating_flat=("beats_flat", "sum"),
                folds_beating_benchmark=("beats_benchmark", "sum"),
                max_top_contributor_share=("top_contributor_share", "max"),
            )
            .reset_index()
        )
        aggregate["all_folds_positive"] = aggregate["folds_beating_flat"] == aggregate["fold_count"]
        aggregate["all_folds_beat_benchmark"] = aggregate["folds_beating_benchmark"] == aggregate["fold_count"]
        aggregate["walkforward_verdict"] = np.where(
            aggregate["all_folds_positive"] & aggregate["all_folds_beat_benchmark"] & (aggregate["max_top_contributor_share"] <= 0.60),
            "walkforward_validated",
            "walkforward_fragile",
        )
        aggregate = aggregate.sort_values(
            ["mean_of_fold_returns", "min_fold_return", "mean_of_fold_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        aggregate.to_csv(aggregate_csv, index=False)

    manifest_csv = baseline_dir / "portfolio_rank_60m_long_only_walkforward_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    main_logger.info(f"[PORTFOLIO-WF] walk-forward summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-WF] walk-forward aggregate saved: {aggregate_csv}")
    main_logger.info(f"[PORTFOLIO-WF] walk-forward manifest saved: {manifest_csv}")
    print(f"[PORTFOLIO-WF] walk-forward summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_long_only_hold_sweep(
    promoted_ids: List[str],
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    top_k: int = 3,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    hold_specs = [5, 7, 10, 15, 21]
    sweep_rows: List[pd.DataFrame] = []

    print(
        f"[PORTFOLIO-HOLD] starting hold sweep for {len(promoted_ids)} experiments across {len(hold_specs)} cadences",
        flush=True,
    )
    for rebalance_every in hold_specs:
        output_stem = f"portfolio_rank_60m_long_only_hold_k{top_k}_r{rebalance_every}"
        print(
            f"[PORTFOLIO-HOLD] running top_k={top_k} rebalance_every={rebalance_every}",
            flush=True,
        )
        summary_df = run_portfolio_rank_baseline(
            promoted_ids=promoted_ids,
            top_k=top_k,
            benchmark_policy=benchmark_policy,
            portfolio_style="long_only",
            rebalance_every_sessions=rebalance_every,
            output_stem=output_stem,
        ).copy()
        if summary_df.empty:
            print(
                f"[PORTFOLIO-HOLD] no rows for rebalance_every={rebalance_every}",
                flush=True,
            )
            continue
        periods_per_year = max(1.0, 250.0 / float(rebalance_every))
        annualized_rows: List[float] = []
        for _, row in summary_df.iterrows():
            mean_return = float(pd.to_numeric(row.get("portfolio_mean_return"), errors="coerce"))
            if np.isfinite(mean_return) and mean_return > -0.999999:
                annualized_rows.append(float((1.0 + mean_return) ** periods_per_year - 1.0))
            else:
                annualized_rows.append(np.nan)
        summary_df["sweep_top_k"] = int(top_k)
        summary_df["sweep_rebalance_every_sessions"] = int(rebalance_every)
        summary_df["approx_periods_per_year"] = periods_per_year
        summary_df["approx_annualized_return"] = annualized_rows
        sweep_rows.append(summary_df)

        best_row = summary_df.sort_values(
            ["portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, True],
        ).iloc[0]
        print(
            "[PORTFOLIO-HOLD] "
            f"best for rebalance_every={rebalance_every}: "
            f"{best_row['experiment_id']} ret={float(best_row['portfolio_mean_return']):.6f} "
            f"ann={float(pd.to_numeric(best_row['approx_annualized_return'], errors='coerce')):.4f}",
            flush=True,
        )

    combined = pd.concat(sweep_rows, ignore_index=True) if sweep_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_sweep_summary.csv"
    combined.to_csv(combined_csv, index=False)

    aggregate_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_sweep_best_by_experiment.csv"
    if combined.empty:
        pd.DataFrame().to_csv(aggregate_csv, index=False)
    else:
        aggregate = (
            combined.sort_values(
                ["experiment_id", "approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
                ascending=[True, False, False, True],
            )
            .groupby("experiment_id", dropna=False)
            .head(1)
            .reset_index(drop=True)
        )
        aggregate.to_csv(aggregate_csv, index=False)

    main_logger.info(f"[PORTFOLIO-HOLD] hold sweep summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-HOLD] hold sweep best-by-experiment saved: {aggregate_csv}")
    print(f"[PORTFOLIO-HOLD] hold sweep summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_long_only_hold_walkforward(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    fold_count: int = 3,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    if not predictions_csv.exists() or not dataset_csv.exists():
        main_logger.warning("[PORTFOLIO-HOLD-WF] missing predictions or dataset; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = pd.read_csv(dataset_csv)
    if pred_df.empty or data_df.empty:
        main_logger.warning("[PORTFOLIO-HOLD-WF] empty predictions or dataset; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    merged = merged.dropna(subset=["TradeDate"]).copy()
    trade_dates = sorted(pd.Series(merged["TradeDate"].dropna().unique()).tolist())
    if len(trade_dates) < max(2, fold_count):
        main_logger.warning("[PORTFOLIO-HOLD-WF] insufficient trade dates for fold split; no walk-forward rows were produced.")
        out_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        return pd.DataFrame()

    hold_specs = [
        {"experiment_id": "E1002", "top_k": 3, "rebalance_every_sessions": 15},
        {"experiment_id": "E1006", "top_k": 3, "rebalance_every_sessions": 10},
        {"experiment_id": "E1003", "top_k": 3, "rebalance_every_sessions": 21},
    ]
    date_folds = [list(chunk) for chunk in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), fold_count) if len(chunk) > 0]
    print(
        f"[PORTFOLIO-HOLD-WF] starting hold walk-forward for {len(hold_specs)} targeted cells across {len(date_folds)} folds",
        flush=True,
    )

    fold_rows: List[pd.DataFrame] = []
    manifest_rows: List[dict] = []
    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_start = pd.Timestamp(fold_dates[0])
        fold_end = pd.Timestamp(fold_dates[-1])
        fold_mask = merged["TradeDate"].isin(pd.to_datetime(fold_dates))
        fold_df = merged.loc[fold_mask].copy()
        manifest_rows.append(
            {
                "fold_id": fold_idx,
                "fold_start_date": fold_start,
                "fold_end_date": fold_end,
                "fold_trade_dates": int(len(fold_dates)),
                "fold_rows": int(len(fold_df)),
            }
        )
        if fold_df.empty:
            continue
        print(
            f"[PORTFOLIO-HOLD-WF] fold {fold_idx}/{len(date_folds)} {fold_start.date()} -> {fold_end.date()} rows={len(fold_df)}",
            flush=True,
        )
        for spec in hold_specs:
            experiment_id = str(spec["experiment_id"])
            top_k = int(spec["top_k"])
            rebalance_every = int(spec["rebalance_every_sessions"])
            print(
                f"[PORTFOLIO-HOLD-WF] fold {fold_idx} running {experiment_id} top_k={top_k} hold={rebalance_every}",
                flush=True,
            )
            fold_summary = run_portfolio_rank_baseline(
                promoted_ids=[experiment_id],
                top_k=top_k,
                benchmark_policy=benchmark_policy,
                portfolio_style="long_only",
                rebalance_every_sessions=rebalance_every,
                output_stem=f"portfolio_rank_60m_long_only_hold_walkforward_{experiment_id}_r{rebalance_every}_fold{fold_idx}",
                source_df=fold_df,
            ).copy()
            if fold_summary.empty:
                continue
            periods_per_year = max(1.0, 250.0 / float(rebalance_every))
            fold_summary["fold_id"] = int(fold_idx)
            fold_summary["fold_start_date"] = fold_start
            fold_summary["fold_end_date"] = fold_end
            fold_summary["fold_trade_dates"] = int(len(fold_dates))
            fold_summary["fold_rows"] = int(len(fold_df))
            fold_summary["approx_periods_per_year"] = periods_per_year
            fold_summary["approx_annualized_return"] = fold_summary["portfolio_mean_return"].apply(
                lambda x: float((1.0 + float(pd.to_numeric(x, errors="coerce"))) ** periods_per_year - 1.0)
                if pd.notna(pd.to_numeric(x, errors="coerce")) and float(pd.to_numeric(x, errors="coerce")) > -0.999999
                else np.nan
            )
            fold_rows.append(fold_summary)

    combined = pd.concat(fold_rows, ignore_index=True) if fold_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_summary.csv"
    combined.to_csv(combined_csv, index=False)

    aggregate_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_aggregate.csv"
    if combined.empty:
        pd.DataFrame().to_csv(aggregate_csv, index=False)
    else:
        aggregate = (
            combined.groupby(
                ["experiment_id", "portfolio_style", "rebalance_rule", "top_k", "sweep_rebalance_every_sessions"]
                if "sweep_rebalance_every_sessions" in combined.columns
                else ["experiment_id", "portfolio_style", "rebalance_rule", "top_k"],
                dropna=False,
            )
            .agg(
                fold_count=("fold_id", "nunique"),
                mean_of_fold_returns=("portfolio_mean_return", "mean"),
                min_fold_return=("portfolio_mean_return", "min"),
                max_fold_return=("portfolio_mean_return", "max"),
                mean_of_fold_annualized=("approx_annualized_return", "mean"),
                min_fold_annualized=("approx_annualized_return", "min"),
                max_fold_annualized=("approx_annualized_return", "max"),
                mean_of_fold_turnover=("portfolio_mean_turnover", "mean"),
                folds_beating_flat=("beats_flat", "sum"),
                folds_beating_benchmark=("beats_benchmark", "sum"),
                max_top_contributor_share=("top_contributor_share", "max"),
            )
            .reset_index()
        )
        aggregate["all_folds_positive"] = aggregate["folds_beating_flat"] == aggregate["fold_count"]
        aggregate["all_folds_beat_benchmark"] = aggregate["folds_beating_benchmark"] == aggregate["fold_count"]
        aggregate["walkforward_verdict"] = np.where(
            aggregate["all_folds_positive"] & aggregate["all_folds_beat_benchmark"] & (aggregate["max_top_contributor_share"] <= 0.60),
            "hold_walkforward_validated",
            "hold_walkforward_fragile",
        )
        aggregate = aggregate.sort_values(
            ["mean_of_fold_annualized", "min_fold_return", "mean_of_fold_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        aggregate.to_csv(aggregate_csv, index=False)

    manifest_csv = baseline_dir / "portfolio_rank_60m_long_only_hold_walkforward_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    main_logger.info(f"[PORTFOLIO-HOLD-WF] hold walk-forward summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-HOLD-WF] hold walk-forward aggregate saved: {aggregate_csv}")
    main_logger.info(f"[PORTFOLIO-HOLD-WF] hold walk-forward manifest saved: {manifest_csv}")
    print(f"[PORTFOLIO-HOLD-WF] hold walk-forward summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_long_only_topk_sweep(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    topk_specs = [2, 3, 4, 5, 7]
    sweep_rows: List[pd.DataFrame] = []

    print(
        f"[PORTFOLIO-TOPK] starting top-k sweep for {experiment_id} across {len(topk_specs)} variants at hold={rebalance_every_sessions}",
        flush=True,
    )
    for top_k in topk_specs:
        output_stem = f"portfolio_rank_60m_long_only_topk_{experiment_id}_k{top_k}_r{rebalance_every_sessions}"
        print(
            f"[PORTFOLIO-TOPK] running experiment={experiment_id} top_k={top_k} rebalance_every={rebalance_every_sessions}",
            flush=True,
        )
        summary_df = run_portfolio_rank_baseline(
            promoted_ids=[experiment_id],
            top_k=top_k,
            benchmark_policy=benchmark_policy,
            portfolio_style="long_only",
            rebalance_every_sessions=rebalance_every_sessions,
            output_stem=output_stem,
        ).copy()
        if summary_df.empty:
            print(f"[PORTFOLIO-TOPK] no rows for top_k={top_k}", flush=True)
            continue
        periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
        summary_df["sweep_experiment_id"] = experiment_id
        summary_df["sweep_top_k"] = int(top_k)
        summary_df["sweep_rebalance_every_sessions"] = int(rebalance_every_sessions)
        summary_df["approx_periods_per_year"] = periods_per_year
        summary_df["approx_annualized_return"] = summary_df["portfolio_mean_return"].apply(
            lambda x: float((1.0 + float(pd.to_numeric(x, errors="coerce"))) ** periods_per_year - 1.0)
            if pd.notna(pd.to_numeric(x, errors="coerce")) and float(pd.to_numeric(x, errors="coerce")) > -0.999999
            else np.nan
        )
        sweep_rows.append(summary_df)

        best_row = summary_df.iloc[0]
        print(
            "[PORTFOLIO-TOPK] "
            f"top_k={top_k} ret={float(best_row['portfolio_mean_return']):.6f} "
            f"ann={float(pd.to_numeric(best_row['approx_annualized_return'], errors='coerce')):.4f} "
            f"share={float(best_row['top_contributor_share']):.4f}",
            flush=True,
        )

    combined = pd.concat(sweep_rows, ignore_index=True) if sweep_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_long_only_topk_sweep_summary.csv"
    combined.to_csv(combined_csv, index=False)

    best_csv = baseline_dir / "portfolio_rank_60m_long_only_topk_sweep_best.csv"
    if combined.empty:
        pd.DataFrame().to_csv(best_csv, index=False)
    else:
        best_df = combined.sort_values(
            ["approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        best_df.to_csv(best_csv, index=False)

    main_logger.info(f"[PORTFOLIO-TOPK] top-k sweep summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-TOPK] top-k sweep best saved: {best_csv}")
    print(f"[PORTFOLIO-TOPK] top-k sweep summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_regime_gate_sweep(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    top_k: int = 2,
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    from signal_targets import estimate_roundtrip_cost

    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    gate_dir = RESULTS_DIR / "signal_research" / "outputs_market_state_60m" / "latest"
    gate_promoted_csv = gate_dir / "promoted_predictions_oos.csv"
    gate_experiment_csv = gate_dir / "experiment_predictions_oos.csv"
    gate_predictions_csv = gate_promoted_csv if gate_promoted_csv.exists() else gate_experiment_csv
    if not predictions_csv.exists() or not dataset_csv.exists() or not gate_predictions_csv.exists():
        out_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-GATE] missing predictions or dataset; no regime-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = pd.read_csv(dataset_csv)
    gate_df = pd.read_csv(gate_predictions_csv)
    if pred_df.empty or data_df.empty or gate_df.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-GATE] empty predictions or dataset; no regime-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    gate_df["Date"] = pd.to_datetime(gate_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    merged = merged.loc[merged["ExperimentID"] == experiment_id].copy()
    merged = merged.dropna(subset=["Date", "Ticker", "Prediction", "Close"]).copy()
    if merged.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        main_logger.warning(f"[PORTFOLIO-GATE] no rows for {experiment_id}; no regime-gate rows were produced.")
        return pd.DataFrame()

    gate_e801_df = gate_df.loc[gate_df["ExperimentID"] == "E801"].copy()
    if gate_e801_df.empty and gate_predictions_csv != gate_experiment_csv and gate_experiment_csv.exists():
        msg = "[PORTFOLIO-GATE] promoted market-state predictions do not include E801; falling back to experiment_predictions_oos.csv"
        main_logger.info(msg)
        print(msg, flush=True)
        gate_df = pd.read_csv(gate_experiment_csv)
        gate_df["Date"] = pd.to_datetime(gate_df["Date"], errors="coerce")
        gate_e801_df = gate_df.loc[gate_df["ExperimentID"] == "E801"].copy()

    gate_scores = (
        gate_e801_df.groupby("Date")["Prediction"]
        .mean()
        .sort_index()
    )
    if gate_scores.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-GATE] no E801 gate scores available; no regime-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    benchmark_return = 0.0
    benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
    if benchmark_summary_csv.exists():
        try:
            bench_df = pd.read_csv(benchmark_summary_csv)
            bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
            if not bench_row.empty:
                benchmark_return = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
        except Exception as exc:
            main_logger.warning(f"[PORTFOLIO-GATE] failed to read benchmark summary: {exc}")

    gate_thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]
    summary_rows: List[dict] = []
    history_rows: List[dict] = []
    print(
        f"[PORTFOLIO-GATE] starting E801 gate sweep for {experiment_id} top_k={top_k} hold={rebalance_every_sessions} across {len(gate_thresholds)} thresholds",
        flush=True,
    )

    open_times = (
        merged.groupby("TradeDate")["Date"]
        .min()
        .dropna()
        .sort_values()
        .tolist()
    )
    min_names_required = top_k
    for gate_threshold in gate_thresholds:
        prev_weights: Dict[str, float] = {}
        event_returns: List[float] = []
        event_turnovers: List[float] = []
        event_gate_scores: List[float] = []
        event_gate_passed: List[bool] = []
        ticker_contrib: Dict[str, float] = {}
        allowed_count = 0
        blocked_count = 0

        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts:
                continue

            gate_score = float(pd.to_numeric(gate_scores.get(open_ts, np.nan), errors="coerce"))
            gate_passed = bool(np.isfinite(gate_score) and gate_score >= gate_threshold)
            current = merged.loc[merged["Date"] == open_ts].copy()
            future = merged.loc[merged["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()

            if len(current) < min_names_required:
                continue

            current = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            current["est_cost"] = estimate_roundtrip_cost(current)
            longs = current.head(top_k).copy()
            weights: Dict[str, float] = {}
            long_weight = 1.0 / top_k
            event_return = 0.0

            if gate_passed:
                allowed_count += 1
                for _, row in longs.iterrows():
                    raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                    contribution = long_weight * raw_ret - abs(long_weight) * float(row["est_cost"])
                    event_return += contribution
                    ticker = str(row["Ticker"])
                    weights[ticker] = long_weight
                    ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution
            else:
                blocked_count += 1

            universe = set(prev_weights) | set(weights)
            turnover = float(sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in universe))
            prev_weights = weights

            event_returns.append(event_return)
            event_turnovers.append(turnover)
            event_gate_scores.append(gate_score)
            event_gate_passed.append(gate_passed)
            history_rows.append(
                {
                    "experiment_id": experiment_id,
                    "top_k": top_k,
                    "rebalance_every_sessions": rebalance_every_sessions,
                    "gate_threshold": gate_threshold,
                    "rebalance_idx": idx + 1,
                    "open_ts": open_ts,
                    "next_open_ts": next_open_ts,
                    "gate_score_e801_mean": gate_score,
                    "gate_passed": gate_passed,
                    "eligible_count": int(len(current)),
                    "portfolio_return": event_return,
                    "turnover": turnover,
                    "long_names": ",".join(longs["Ticker"].astype(str).tolist()) if gate_passed else "",
                }
            )

        if not event_returns:
            continue

        contrib_total_abs = float(sum(abs(v) for v in ticker_contrib.values()))
        top_contrib_share = 0.0
        if contrib_total_abs > 0:
            top_contrib_share = max(abs(v) for v in ticker_contrib.values()) / contrib_total_abs

        periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
        mean_return = float(np.mean(event_returns))
        approx_annualized_return = float((1.0 + mean_return) ** periods_per_year - 1.0) if mean_return > -0.999999 else np.nan
        summary_rows.append(
            {
                "experiment_id": experiment_id,
                "portfolio_style": "long_only",
                "rebalance_rule": f"every_{rebalance_every_sessions}_session_open",
                "top_k": top_k,
                "gate_experiment_id": "E801",
                "gate_threshold": gate_threshold,
                "rebalance_count": int(len(event_returns)),
                "allowed_rebalances": int(allowed_count),
                "blocked_rebalances": int(blocked_count),
                "gate_pass_rate": float(np.mean(event_gate_passed)) if event_gate_passed else np.nan,
                "mean_gate_score": float(np.nanmean(event_gate_scores)) if event_gate_scores else np.nan,
                "portfolio_mean_return": mean_return,
                "portfolio_median_return": float(np.median(event_returns)),
                "portfolio_std_return": float(np.std(event_returns)),
                "portfolio_mean_turnover": float(np.mean(event_turnovers)) if event_turnovers else np.nan,
                "positive_windows": int(sum(val > 0 for val in event_returns)),
                "zero_windows": int(sum(np.isclose(val, 0.0) for val in event_returns)),
                "negative_windows": int(sum(val < 0 for val in event_returns)),
                "portfolio_win_rate": float(np.mean([val > 0 for val in event_returns])),
                "top_contributor_share": top_contrib_share,
                "benchmark_policy": benchmark_policy,
                "benchmark_return": benchmark_return,
                "excess_vs_benchmark": mean_return - benchmark_return,
                "beats_flat": bool(mean_return > 0.0),
                "beats_benchmark": bool(mean_return > benchmark_return),
                "promotion_verdict": "baseline_promoted"
                if (mean_return > 0.0 and mean_return > benchmark_return and top_contrib_share <= 0.60)
                else "research_only",
                "approx_periods_per_year": periods_per_year,
                "approx_annualized_return": approx_annualized_return,
            }
        )

        print(
            "[PORTFOLIO-GATE] "
            f"threshold={gate_threshold:.2f} ret={mean_return:.6f} ann={approx_annualized_return:.4f} "
            f"pass_rate={float(np.mean(event_gate_passed)):.2%}",
            flush=True,
        )

    summary_df = pd.DataFrame(summary_rows)
    history_df = pd.DataFrame(history_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    summary_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_summary.csv"
    history_csv = baseline_dir / "portfolio_rank_60m_regime_gate_sweep_history.csv"
    summary_df.to_csv(summary_csv, index=False)
    history_df.to_csv(history_csv, index=False)
    main_logger.info(f"[PORTFOLIO-GATE] regime gate sweep summary saved: {summary_csv}")
    main_logger.info(f"[PORTFOLIO-GATE] regime gate sweep history saved: {history_csv}")
    print(f"[PORTFOLIO-GATE] regime gate sweep summary saved: {summary_csv}", flush=True)
    return summary_df


def run_portfolio_rank_score_weighted_sizing(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    top_k: int = 2,
    rebalance_every_sessions: int = 10,
    ticker_subset: Optional[List[str]] = None,
    output_stem: str = "portfolio_rank_60m_score_weighted_sizing",
    source_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    from signal_targets import estimate_roundtrip_cost

    top_liquid_subset = {
        "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
        "TCS", "INFY", "WIPRO", "HCLTECH", "ITC",
        "HINDUNILVR", "RELIANCE", "LT", "BHARTIARTL",
    }

    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    summary_csv = baseline_dir / f"{output_stem}_summary.csv"
    history_csv = baseline_dir / f"{output_stem}_history.csv"
    if not predictions_csv.exists() or not dataset_csv.exists():
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = "[PORTFOLIO-SIZING] missing predictions or dataset; no sizing rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = source_df.copy() if source_df is not None else pd.read_csv(dataset_csv)
    if pred_df.empty or data_df.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = "[PORTFOLIO-SIZING] empty predictions or dataset; no sizing rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    exp_df = merged.loc[merged["ExperimentID"] == experiment_id].copy()
    universe_mode = "full_universe"
    if ticker_subset:
        normalized_subset = {str(t).strip().upper() for t in ticker_subset if str(t).strip()}
        exp_df = exp_df.loc[exp_df["Ticker"].astype(str).str.upper().isin(normalized_subset)].copy()
        universe_mode = f"subset_{len(normalized_subset)}"
    exp_df = exp_df.dropna(subset=["Date", "Ticker", "Prediction", "Close"]).copy()
    if exp_df.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = f"[PORTFOLIO-SIZING] no rows for {experiment_id}; no sizing rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    benchmark_return = 0.0
    benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
    if benchmark_summary_csv.exists():
        try:
            bench_df = pd.read_csv(benchmark_summary_csv)
            bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
            if not bench_row.empty:
                benchmark_return = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
        except Exception as exc:
            main_logger.warning(f"[PORTFOLIO-SIZING] failed to read benchmark summary: {exc}")

    weighting_specs = ["equal_weight", "score_weighted"]
    open_times = (
        exp_df.groupby("TradeDate")["Date"]
        .min()
        .dropna()
        .sort_values()
        .tolist()
    )
    history_rows: List[dict] = []
    summary_rows: List[dict] = []
    print(
        f"[PORTFOLIO-SIZING] starting sizing comparison for {experiment_id} top_k={top_k} hold={rebalance_every_sessions}",
        flush=True,
    )

    for weighting_mode in weighting_specs:
        prev_weights: Dict[str, float] = {}
        event_returns: List[float] = []
        event_turnovers: List[float] = []
        event_top_liquid_weights: List[float] = []
        event_non_top_liquid_weights: List[float] = []
        event_majority_non_top_liquid: List[bool] = []
        ticker_contrib: Dict[str, float] = {}
        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts:
                continue

            current = exp_df.loc[exp_df["Date"] == open_ts].copy()
            future = exp_df.loc[exp_df["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            if len(current) < top_k:
                continue

            current = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            current["est_cost"] = estimate_roundtrip_cost(current)
            longs = current.head(top_k).copy()

            if weighting_mode == "equal_weight":
                longs["alloc_weight"] = 1.0 / top_k
            else:
                centered = pd.to_numeric(longs["Prediction"], errors="coerce") - float(pd.to_numeric(longs["Prediction"], errors="coerce").min())
                centered = centered + 1e-6
                denom = float(centered.sum())
                if not np.isfinite(denom) or denom <= 0.0:
                    longs["alloc_weight"] = 1.0 / top_k
                else:
                    longs["alloc_weight"] = centered / denom

            weights: Dict[str, float] = {}
            event_return = 0.0
            for _, row in longs.iterrows():
                w = float(row["alloc_weight"])
                raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                contribution = w * raw_ret - abs(w) * float(row["est_cost"])
                event_return += contribution
                ticker = str(row["Ticker"])
                weights[ticker] = w
                ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution

            top_liquid_weight = float(
                sum(
                    float(w)
                    for ticker, w in weights.items()
                    if str(ticker).strip().upper() in top_liquid_subset
                )
            )
            non_top_liquid_weight = float(
                sum(
                    float(w)
                    for ticker, w in weights.items()
                    if str(ticker).strip().upper() not in top_liquid_subset
                )
            )

            universe = set(prev_weights) | set(weights)
            turnover = float(sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in universe))
            prev_weights = weights
            event_returns.append(event_return)
            event_turnovers.append(turnover)
            event_top_liquid_weights.append(top_liquid_weight)
            event_non_top_liquid_weights.append(non_top_liquid_weight)
            event_majority_non_top_liquid.append(non_top_liquid_weight > top_liquid_weight)
            history_rows.append(
                {
                    "experiment_id": experiment_id,
                    "weighting_mode": weighting_mode,
                    "universe_mode": universe_mode,
                    "top_k": top_k,
                    "rebalance_every_sessions": rebalance_every_sessions,
                    "rebalance_idx": idx + 1,
                    "open_ts": open_ts,
                    "next_open_ts": next_open_ts,
                    "portfolio_return": event_return,
                    "turnover": turnover,
                    "long_names": ",".join(longs["Ticker"].astype(str).tolist()),
                    "long_weights": ",".join(f"{float(w):.6f}" for w in longs["alloc_weight"].tolist()),
                    "selected_weight_top_liquid14": top_liquid_weight,
                    "selected_weight_non_top_liquid": non_top_liquid_weight,
                    "majority_non_top_liquid": bool(non_top_liquid_weight > top_liquid_weight),
                }
            )

        if not event_returns:
            continue

        contrib_total_abs = float(sum(abs(v) for v in ticker_contrib.values()))
        top_contrib_share = 0.0
        if contrib_total_abs > 0:
            top_contrib_share = max(abs(v) for v in ticker_contrib.values()) / contrib_total_abs
        mean_return = float(np.mean(event_returns))
        periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
        approx_annualized_return = float((1.0 + mean_return) ** periods_per_year - 1.0) if mean_return > -0.999999 else np.nan
        summary_rows.append(
            {
                "experiment_id": experiment_id,
                "weighting_mode": weighting_mode,
                "universe_mode": universe_mode,
                "top_k": top_k,
                "rebalance_rule": f"every_{rebalance_every_sessions}_session_open",
                "rebalance_count": int(len(event_returns)),
                "portfolio_mean_return": mean_return,
                "portfolio_median_return": float(np.median(event_returns)),
                "portfolio_std_return": float(np.std(event_returns)),
                "portfolio_mean_turnover": float(np.mean(event_turnovers)) if event_turnovers else np.nan,
                "positive_windows": int(sum(val > 0 for val in event_returns)),
                "zero_windows": int(sum(np.isclose(val, 0.0) for val in event_returns)),
                "negative_windows": int(sum(val < 0 for val in event_returns)),
                "portfolio_win_rate": float(np.mean([val > 0 for val in event_returns])),
                "top_contributor_share": top_contrib_share,
                "mean_selected_weight_top_liquid14": float(np.mean(event_top_liquid_weights)) if event_top_liquid_weights else np.nan,
                "mean_selected_weight_non_top_liquid": float(np.mean(event_non_top_liquid_weights)) if event_non_top_liquid_weights else np.nan,
                "rebalances_majority_non_top_liquid": int(sum(event_majority_non_top_liquid)),
                "majority_non_top_liquid_rate": float(np.mean(event_majority_non_top_liquid)) if event_majority_non_top_liquid else np.nan,
                "benchmark_policy": benchmark_policy,
                "benchmark_return": benchmark_return,
                "excess_vs_benchmark": mean_return - benchmark_return,
                "beats_flat": bool(mean_return > 0.0),
                "beats_benchmark": bool(mean_return > benchmark_return),
                "promotion_verdict": "baseline_promoted"
                if (mean_return > 0.0 and mean_return > benchmark_return and top_contrib_share <= 0.60)
                else "research_only",
                "approx_periods_per_year": periods_per_year,
                "approx_annualized_return": approx_annualized_return,
            }
        )
        print(
            "[PORTFOLIO-SIZING] "
            f"mode={weighting_mode} ret={mean_return:.6f} ann={approx_annualized_return:.4f} "
            f"share={top_contrib_share:.4f}",
            flush=True,
        )

    summary_df = pd.DataFrame(summary_rows)
    history_df = pd.DataFrame(history_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    summary_df.to_csv(summary_csv, index=False)
    history_df.to_csv(history_csv, index=False)
    main_logger.info(f"[PORTFOLIO-SIZING] sizing summary saved: {summary_csv}")
    main_logger.info(f"[PORTFOLIO-SIZING] sizing history saved: {history_csv}")
    print(f"[PORTFOLIO-SIZING] sizing summary saved: {summary_csv}", flush=True)
    return summary_df


def run_portfolio_rank_liquid_subset_audit(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    top_k: int = 2,
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    top_liquid_subset = [
        "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
        "TCS", "INFY", "WIPRO", "HCLTECH", "ITC",
        "HINDUNILVR", "RELIANCE", "LT", "BHARTIARTL",
    ]
    print(
        f"[PORTFOLIO-LIQUID] auditing {experiment_id} top_k={top_k} hold={rebalance_every_sessions} on top-liquidity subset of {len(top_liquid_subset)} names",
        flush=True,
    )
    return run_portfolio_rank_score_weighted_sizing(
        benchmark_policy=benchmark_policy,
        experiment_id=experiment_id,
        top_k=top_k,
        rebalance_every_sessions=rebalance_every_sessions,
        ticker_subset=top_liquid_subset,
        output_stem="portfolio_rank_60m_liquid_subset_audit",
    )


def run_portfolio_rank_score_weighted_topk_sweep(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    topk_specs = [2, 3, 4, 5]
    sweep_rows: List[pd.DataFrame] = []

    print(
        f"[PORTFOLIO-SW-TOPK] starting score-weighted top-k sweep for {experiment_id} at hold={rebalance_every_sessions}",
        flush=True,
    )
    for top_k in topk_specs:
        print(
            f"[PORTFOLIO-SW-TOPK] running top_k={top_k}",
            flush=True,
        )
        summary_df = run_portfolio_rank_score_weighted_sizing(
            benchmark_policy=benchmark_policy,
            experiment_id=experiment_id,
            top_k=top_k,
            rebalance_every_sessions=rebalance_every_sessions,
            output_stem=f"portfolio_rank_60m_score_weighted_topk_{experiment_id}_k{top_k}_r{rebalance_every_sessions}",
        ).copy()
        if summary_df.empty:
            continue
        summary_df["sweep_experiment_id"] = experiment_id
        summary_df["sweep_top_k"] = int(top_k)
        summary_df["sweep_rebalance_every_sessions"] = int(rebalance_every_sessions)
        sweep_rows.append(summary_df)
        best_row = summary_df.iloc[0]
        print(
            "[PORTFOLIO-SW-TOPK] "
            f"top_k={top_k} ret={float(best_row['portfolio_mean_return']):.6f} "
            f"ann={float(pd.to_numeric(best_row['approx_annualized_return'], errors='coerce')):.4f} "
            f"share={float(best_row['top_contributor_share']):.4f}",
            flush=True,
        )

    combined = pd.concat(sweep_rows, ignore_index=True) if sweep_rows else pd.DataFrame()
    summary_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_sweep_summary.csv"
    best_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_sweep_best.csv"
    combined.to_csv(summary_csv, index=False)
    if combined.empty:
        pd.DataFrame().to_csv(best_csv, index=False)
    else:
        combined.sort_values(
            ["approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True).to_csv(best_csv, index=False)
    main_logger.info(f"[PORTFOLIO-SW-TOPK] score-weighted top-k summary saved: {summary_csv}")
    main_logger.info(f"[PORTFOLIO-SW-TOPK] score-weighted top-k best saved: {best_csv}")
    print(f"[PORTFOLIO-SW-TOPK] score-weighted top-k summary saved: {summary_csv}", flush=True)
    return combined


def run_portfolio_rank_score_weighted_topk_walkforward(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    if not dataset_csv.exists():
        out_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-SW-WF] missing research dataset; no walk-forward rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    data_df = pd.read_csv(dataset_csv)
    if data_df.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-SW-WF] empty research dataset; no walk-forward rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.dropna(subset=["Date"]).sort_values(["Date", "Ticker"]).reset_index(drop=True)
    trade_dates = sorted(pd.Series(data_df["Date"].dt.normalize().dropna().unique()).tolist())
    if len(trade_dates) < 9:
        out_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-SW-WF] insufficient trade dates for 3-fold walk-forward."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    topk_specs = [2, 3, 4, 5]
    date_folds = [fold.tolist() for fold in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), 3) if len(fold) > 0]
    manifest_rows: List[dict] = []
    fold_rows: List[pd.DataFrame] = []
    print(
        f"[PORTFOLIO-SW-WF] starting score-weighted walk-forward for {experiment_id} at hold={rebalance_every_sessions} across {len(topk_specs)} top-k cells",
        flush=True,
    )

    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_start = pd.Timestamp(fold_dates[0])
        fold_end = pd.Timestamp(fold_dates[-1])
        fold_date_index = pd.to_datetime(pd.Series(fold_dates)).dt.normalize().unique()
        fold_df = data_df.loc[data_df["Date"].dt.normalize().isin(fold_date_index)].copy()
        manifest_rows.append(
            {
                "fold_id": fold_idx,
                "fold_start_date": fold_start,
                "fold_end_date": fold_end,
                "fold_trade_dates": int(len(fold_dates)),
                "fold_rows": int(len(fold_df)),
            }
        )
        if fold_df.empty:
            continue
        print(
            f"[PORTFOLIO-SW-WF] fold {fold_idx}/{len(date_folds)} {fold_start.date()} -> {fold_end.date()} rows={len(fold_df)}",
            flush=True,
        )
        for top_k in topk_specs:
            print(
                f"[PORTFOLIO-SW-WF] fold {fold_idx} running {experiment_id} top_k={top_k} hold={rebalance_every_sessions}",
                flush=True,
            )
            fold_summary = run_portfolio_rank_score_weighted_sizing(
                benchmark_policy=benchmark_policy,
                experiment_id=experiment_id,
                top_k=top_k,
                rebalance_every_sessions=rebalance_every_sessions,
                output_stem=f"portfolio_rank_60m_score_weighted_topk_walkforward_{experiment_id}_k{top_k}_r{rebalance_every_sessions}_fold{fold_idx}",
                source_df=fold_df,
            ).copy()
            if fold_summary.empty:
                continue
            periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
            fold_summary["fold_id"] = int(fold_idx)
            fold_summary["fold_start_date"] = fold_start
            fold_summary["fold_end_date"] = fold_end
            fold_summary["fold_trade_dates"] = int(len(fold_dates))
            fold_summary["fold_rows"] = int(len(fold_df))
            fold_summary["approx_periods_per_year"] = periods_per_year
            fold_summary["approx_annualized_return"] = fold_summary["portfolio_mean_return"].apply(
                lambda x: float((1.0 + float(pd.to_numeric(x, errors="coerce"))) ** periods_per_year - 1.0)
                if pd.notna(pd.to_numeric(x, errors="coerce")) and float(pd.to_numeric(x, errors="coerce")) > -0.999999
                else np.nan
            )
            fold_rows.append(fold_summary)

    combined = pd.concat(fold_rows, ignore_index=True) if fold_rows else pd.DataFrame()
    combined_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_summary.csv"
    combined.to_csv(combined_csv, index=False)

    aggregate_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_aggregate.csv"
    if combined.empty:
        pd.DataFrame().to_csv(aggregate_csv, index=False)
    else:
        aggregate = (
            combined.groupby(
                ["experiment_id", "weighting_mode", "top_k", "rebalance_rule"],
                dropna=False,
            )
            .agg(
                fold_count=("fold_id", "nunique"),
                mean_of_fold_returns=("portfolio_mean_return", "mean"),
                min_fold_return=("portfolio_mean_return", "min"),
                max_fold_return=("portfolio_mean_return", "max"),
                mean_of_fold_annualized=("approx_annualized_return", "mean"),
                min_fold_annualized=("approx_annualized_return", "min"),
                max_fold_annualized=("approx_annualized_return", "max"),
                mean_of_fold_turnover=("portfolio_mean_turnover", "mean"),
                mean_of_fold_win_rate=("portfolio_win_rate", "mean"),
                mean_selected_weight_top_liquid14=("mean_selected_weight_top_liquid14", "mean"),
                mean_selected_weight_non_top_liquid=("mean_selected_weight_non_top_liquid", "mean"),
                max_majority_non_top_liquid_rate=("majority_non_top_liquid_rate", "max"),
                folds_beating_flat=("beats_flat", "sum"),
                folds_beating_benchmark=("beats_benchmark", "sum"),
                max_top_contributor_share=("top_contributor_share", "max"),
            )
            .reset_index()
        )
        aggregate["all_folds_positive"] = aggregate["folds_beating_flat"] == aggregate["fold_count"]
        aggregate["all_folds_beat_benchmark"] = aggregate["folds_beating_benchmark"] == aggregate["fold_count"]
        aggregate["walkforward_verdict"] = np.where(
            aggregate["all_folds_positive"] & aggregate["all_folds_beat_benchmark"] & (aggregate["max_top_contributor_share"] <= 0.60),
            "score_weighted_topk_walkforward_validated",
            "score_weighted_topk_walkforward_fragile",
        )
        aggregate = aggregate.sort_values(
            ["mean_of_fold_annualized", "min_fold_return", "mean_of_fold_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        aggregate.to_csv(aggregate_csv, index=False)

    manifest_csv = baseline_dir / "portfolio_rank_60m_score_weighted_topk_walkforward_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    main_logger.info(f"[PORTFOLIO-SW-WF] score-weighted walk-forward summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-SW-WF] score-weighted walk-forward aggregate saved: {aggregate_csv}")
    main_logger.info(f"[PORTFOLIO-SW-WF] score-weighted walk-forward manifest saved: {manifest_csv}")
    print(f"[PORTFOLIO-SW-WF] score-weighted walk-forward summary saved: {combined_csv}", flush=True)
    return combined


def run_portfolio_rank_dispersion_gate_sweep(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    top_k: int = 3,
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    from signal_targets import estimate_roundtrip_cost

    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    summary_csv = baseline_dir / "portfolio_rank_60m_dispersion_gate_sweep_summary.csv"
    history_csv = baseline_dir / "portfolio_rank_60m_dispersion_gate_sweep_history.csv"
    if not predictions_csv.exists() or not dataset_csv.exists():
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = "[PORTFOLIO-DISP] missing predictions or dataset; no dispersion-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = pd.read_csv(dataset_csv)
    if pred_df.empty or data_df.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = "[PORTFOLIO-DISP] empty predictions or dataset; no dispersion-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    merged = merged.loc[merged["ExperimentID"] == experiment_id].copy()
    merged = merged.dropna(subset=["Date", "Ticker", "Prediction", "Close"]).copy()
    if merged.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = f"[PORTFOLIO-DISP] no rows for {experiment_id}; no dispersion-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    benchmark_return = 0.0
    benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
    if benchmark_summary_csv.exists():
        try:
            bench_df = pd.read_csv(benchmark_summary_csv)
            bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
            if not bench_row.empty:
                benchmark_return = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
        except Exception as exc:
            main_logger.warning(f"[PORTFOLIO-DISP] failed to read benchmark summary: {exc}")

    open_times = (
        merged.groupby("TradeDate")["Date"]
        .min()
        .dropna()
        .sort_values()
        .tolist()
    )
    spread_values: List[float] = []
    snapshot_map: Dict[pd.Timestamp, pd.DataFrame] = {}
    for idx in range(len(open_times) - 1):
        if idx % rebalance_every_sessions != 0:
            continue
        open_ts = open_times[idx]
        next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
        next_open_ts = open_times[next_idx]
        if next_open_ts == open_ts:
            continue
        current = merged.loc[merged["Date"] == open_ts].copy()
        future = merged.loc[merged["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
        current = current.merge(future, on="Ticker", how="inner")
        current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
        current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
        current = current.dropna(subset=["Prediction"]).copy()
        if len(current) < top_k:
            continue
        spread = float(current["Prediction"].max() - current["Prediction"].min())
        spread_values.append(spread)
        snapshot_map[open_ts] = current

    if not spread_values:
        pd.DataFrame().to_csv(summary_csv, index=False)
        msg = "[PORTFOLIO-DISP] no eligible rebalance snapshots; no dispersion-gate rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    gate_quantiles = [0.40, 0.50, 0.60, 0.70]
    gate_thresholds = [float(np.quantile(spread_values, q)) for q in gate_quantiles]
    summary_rows: List[dict] = []
    history_rows: List[dict] = []
    print(
        f"[PORTFOLIO-DISP] starting dispersion-gate sweep for {experiment_id} top_k={top_k} hold={rebalance_every_sessions}",
        flush=True,
    )

    for gate_quantile, gate_threshold in zip(gate_quantiles, gate_thresholds):
        prev_weights: Dict[str, float] = {}
        event_returns: List[float] = []
        event_turnovers: List[float] = []
        event_gate_spreads: List[float] = []
        event_gate_passed: List[bool] = []
        ticker_contrib: Dict[str, float] = {}
        allowed_count = 0
        blocked_count = 0

        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts or open_ts not in snapshot_map:
                continue

            current = snapshot_map[open_ts].copy()
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Close", "NextClose"]).copy()
            current = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            current["est_cost"] = estimate_roundtrip_cost(current)
            longs = current.head(top_k).copy()

            gate_spread = float(current["Prediction"].max() - current["Prediction"].min())
            gate_passed = bool(np.isfinite(gate_spread) and gate_spread >= gate_threshold)
            weights: Dict[str, float] = {}
            event_return = 0.0

            if gate_passed:
                allowed_count += 1
                centered = pd.to_numeric(longs["Prediction"], errors="coerce") - float(pd.to_numeric(longs["Prediction"], errors="coerce").min())
                centered = centered + 1e-6
                denom = float(centered.sum())
                if not np.isfinite(denom) or denom <= 0.0:
                    longs["alloc_weight"] = 1.0 / top_k
                else:
                    longs["alloc_weight"] = centered / denom
                for _, row in longs.iterrows():
                    w = float(row["alloc_weight"])
                    raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                    contribution = w * raw_ret - abs(w) * float(row["est_cost"])
                    event_return += contribution
                    ticker = str(row["Ticker"])
                    weights[ticker] = w
                    ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution
            else:
                blocked_count += 1
                longs["alloc_weight"] = 0.0

            universe = set(prev_weights) | set(weights)
            turnover = float(sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in universe))
            prev_weights = weights
            event_returns.append(event_return)
            event_turnovers.append(turnover)
            event_gate_spreads.append(gate_spread)
            event_gate_passed.append(gate_passed)
            history_rows.append(
                {
                    "experiment_id": experiment_id,
                    "weighting_mode": "score_weighted",
                    "top_k": top_k,
                    "rebalance_every_sessions": rebalance_every_sessions,
                    "gate_feature": "prediction_spread",
                    "gate_quantile": gate_quantile,
                    "gate_threshold": gate_threshold,
                    "rebalance_idx": idx + 1,
                    "open_ts": open_ts,
                    "next_open_ts": next_open_ts,
                    "gate_spread": gate_spread,
                    "gate_passed": gate_passed,
                    "portfolio_return": event_return,
                    "turnover": turnover,
                    "long_names": ",".join(longs["Ticker"].astype(str).tolist()) if gate_passed else "",
                    "long_weights": ",".join(f"{float(w):.6f}" for w in longs["alloc_weight"].tolist()) if gate_passed else "",
                }
            )

        if not event_returns:
            continue

        contrib_total_abs = float(sum(abs(v) for v in ticker_contrib.values()))
        top_contrib_share = 0.0
        if contrib_total_abs > 0:
            top_contrib_share = max(abs(v) for v in ticker_contrib.values()) / contrib_total_abs
        mean_return = float(np.mean(event_returns))
        periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
        approx_annualized_return = float((1.0 + mean_return) ** periods_per_year - 1.0) if mean_return > -0.999999 else np.nan
        summary_rows.append(
            {
                "experiment_id": experiment_id,
                "weighting_mode": "score_weighted",
                "top_k": top_k,
                "rebalance_rule": f"every_{rebalance_every_sessions}_session_open",
                "gate_feature": "prediction_spread",
                "gate_quantile": gate_quantile,
                "gate_threshold": gate_threshold,
                "rebalance_count": int(len(event_returns)),
                "allowed_rebalances": int(allowed_count),
                "blocked_rebalances": int(blocked_count),
                "gate_pass_rate": float(np.mean(event_gate_passed)) if event_gate_passed else np.nan,
                "mean_gate_spread": float(np.nanmean(event_gate_spreads)) if event_gate_spreads else np.nan,
                "portfolio_mean_return": mean_return,
                "portfolio_median_return": float(np.median(event_returns)),
                "portfolio_std_return": float(np.std(event_returns)),
                "portfolio_mean_turnover": float(np.mean(event_turnovers)) if event_turnovers else np.nan,
                "positive_windows": int(sum(val > 0 for val in event_returns)),
                "zero_windows": int(sum(np.isclose(val, 0.0) for val in event_returns)),
                "negative_windows": int(sum(val < 0 for val in event_returns)),
                "portfolio_win_rate": float(np.mean([val > 0 for val in event_returns])),
                "top_contributor_share": top_contrib_share,
                "benchmark_policy": benchmark_policy,
                "benchmark_return": benchmark_return,
                "excess_vs_benchmark": mean_return - benchmark_return,
                "beats_flat": bool(mean_return > 0.0),
                "beats_benchmark": bool(mean_return > benchmark_return),
                "promotion_verdict": "baseline_promoted"
                if (mean_return > 0.0 and mean_return > benchmark_return and top_contrib_share <= 0.60)
                else "research_only",
                "approx_periods_per_year": periods_per_year,
                "approx_annualized_return": approx_annualized_return,
            }
        )
        print(
            "[PORTFOLIO-DISP] "
            f"q={gate_quantile:.2f} thr={gate_threshold:.6f} ret={mean_return:.6f} ann={approx_annualized_return:.4f} "
            f"pass_rate={float(np.mean(event_gate_passed)):.2%}",
            flush=True,
        )

    summary_df = pd.DataFrame(summary_rows)
    history_df = pd.DataFrame(history_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["approx_annualized_return", "portfolio_mean_return", "portfolio_mean_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    summary_df.to_csv(summary_csv, index=False)
    history_df.to_csv(history_csv, index=False)
    main_logger.info(f"[PORTFOLIO-DISP] dispersion-gate summary saved: {summary_csv}")
    main_logger.info(f"[PORTFOLIO-DISP] dispersion-gate history saved: {history_csv}")
    print(f"[PORTFOLIO-DISP] dispersion-gate summary saved: {summary_csv}", flush=True)
    return summary_df


def run_portfolio_rank_dispersion_sizing_walkforward(
    benchmark_policy: str = "SIGNAL_E211_BANDED_68",
    experiment_id: str = "E1006",
    top_k: int = 3,
    rebalance_every_sessions: int = 10,
) -> pd.DataFrame:
    from signal_targets import estimate_roundtrip_cost

    top_liquid_subset = {
        "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
        "TCS", "INFY", "WIPRO", "HCLTECH", "ITC",
        "HINDUNILVR", "RELIANCE", "LT", "BHARTIARTL",
    }

    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    research_dir = RESULTS_DIR / "signal_research" / "outputs_portfolio_rank_60m" / "latest"
    predictions_csv = research_dir / "promoted_predictions_oos.csv"
    if not predictions_csv.exists():
        predictions_csv = research_dir / "experiment_predictions_oos.csv"
    dataset_csv = RESULTS_DIR / "signal_research" / "research_dataset.csv"
    if not predictions_csv.exists() or not dataset_csv.exists():
        out_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-DISP-SIZE] missing predictions or dataset; no walk-forward rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df = pd.read_csv(predictions_csv)
    data_df = pd.read_csv(dataset_csv)
    if pred_df.empty or data_df.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-DISP-SIZE] empty predictions or dataset; no walk-forward rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    pred_df["Date"] = pd.to_datetime(pred_df["Date"], errors="coerce")
    data_df["Date"] = pd.to_datetime(data_df["Date"], errors="coerce")
    data_df = data_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    merge_cols = [col for col in ["Ticker", "Date", "Close", "ATR20_log", "WindowID"] if col in data_df.columns]
    merged = pred_df.merge(
        data_df[merge_cols].drop_duplicates(["Ticker", "Date"]),
        on=["Ticker", "Date"],
        how="left",
    )
    merged["TradeDate"] = merged["Date"].dt.normalize()
    merged = merged.loc[merged["ExperimentID"] == experiment_id].copy()
    merged = merged.dropna(subset=["Date", "Ticker", "Prediction", "Close"]).copy()
    if merged.empty:
        out_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = f"[PORTFOLIO-DISP-SIZE] no rows for {experiment_id}; no walk-forward rows were produced."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    benchmark_return = 0.0
    benchmark_summary_csv = baseline_dir / "e102_deepdive_policy_summary.csv"
    if benchmark_summary_csv.exists():
        try:
            bench_df = pd.read_csv(benchmark_summary_csv)
            bench_row = bench_df.loc[bench_df["policy"] == benchmark_policy]
            if not bench_row.empty:
                benchmark_return = float(pd.to_numeric(bench_row.iloc[0]["test_return"], errors="coerce"))
        except Exception as exc:
            main_logger.warning(f"[PORTFOLIO-DISP-SIZE] failed to read benchmark summary: {exc}")

    trade_dates = sorted(pd.Series(merged["Date"].dt.normalize().dropna().unique()).tolist())
    if len(trade_dates) < 9:
        out_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_summary.csv"
        pd.DataFrame().to_csv(out_csv, index=False)
        msg = "[PORTFOLIO-DISP-SIZE] insufficient trade dates for 3-fold walk-forward."
        main_logger.warning(msg)
        print(msg, flush=True)
        return pd.DataFrame()

    date_folds = [fold.tolist() for fold in np.array_split(np.array(trade_dates, dtype="datetime64[ns]"), 3) if len(fold) > 0]
    fold_snapshots: List[Dict[pd.Timestamp, pd.DataFrame]] = []
    fold_spreads: List[List[float]] = []
    manifest_rows: List[dict] = []
    history_rows: List[dict] = []
    summary_rows: List[dict] = []
    print(
        f"[PORTFOLIO-DISP-SIZE] starting dispersion-sized walk-forward for {experiment_id} top_k={top_k} hold={rebalance_every_sessions}",
        flush=True,
    )

    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_start = pd.Timestamp(fold_dates[0])
        fold_end = pd.Timestamp(fold_dates[-1])
        fold_date_index = pd.to_datetime(pd.Series(fold_dates)).dt.normalize().unique()
        fold_df = merged.loc[merged["Date"].dt.normalize().isin(fold_date_index)].copy()
        manifest_rows.append(
            {
                "fold_id": fold_idx,
                "fold_start_date": fold_start,
                "fold_end_date": fold_end,
                "fold_trade_dates": int(len(fold_dates)),
                "fold_rows": int(len(fold_df)),
            }
        )
        if fold_df.empty:
            continue

        open_times = (
            fold_df.groupby("TradeDate")["Date"]
            .min()
            .dropna()
            .sort_values()
            .tolist()
        )
        spread_samples: List[float] = []
        snapshots: Dict[pd.Timestamp, pd.DataFrame] = {}
        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts:
                continue
            current = fold_df.loc[fold_df["Date"] == open_ts].copy()
            future = fold_df.loc[fold_df["Date"] == next_open_ts, ["Ticker", "Close"]].rename(columns={"Close": "NextClose"})
            current = current.merge(future, on="Ticker", how="inner")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            current["Prediction"] = pd.to_numeric(current["Prediction"], errors="coerce")
            current["Close"] = pd.to_numeric(current["Close"], errors="coerce")
            current["NextClose"] = pd.to_numeric(current["NextClose"], errors="coerce")
            current = current.dropna(subset=["Prediction", "Close", "NextClose"]).copy()
            if len(current) < max(top_k, 5):
                continue
            current = current.sort_values("Prediction", ascending=False).reset_index(drop=True)
            spread = float(current.iloc[0]["Prediction"] - current.iloc[4]["Prediction"])
            spread_samples.append(spread)
            snapshots[open_ts] = current

        fold_snapshots.append(snapshots)
        fold_spreads.append(spread_samples)

    for fold_idx, fold_dates in enumerate(date_folds, start=1):
        fold_start = pd.Timestamp(fold_dates[0])
        fold_end = pd.Timestamp(fold_dates[-1])
        fold_date_index = pd.to_datetime(pd.Series(fold_dates)).dt.normalize().unique()
        fold_df = merged.loc[merged["Date"].dt.normalize().isin(fold_date_index)].copy()
        open_times = (
            fold_df.groupby("TradeDate")["Date"]
            .min()
            .dropna()
            .sort_values()
            .tolist()
        )
        snapshots = fold_snapshots[fold_idx - 1] if len(fold_snapshots) >= fold_idx else {}
        spread_samples = fold_spreads[fold_idx - 1] if len(fold_spreads) >= fold_idx else []
        if not spread_samples:
            continue
        if fold_idx == 1:
            ref_spreads = []
            ref_source = "fold1_constant_1p0"
        else:
            ref_spreads = fold_spreads[fold_idx - 2]
            ref_source = f"prefold_{fold_idx - 1}"
        if not ref_spreads:
            if fold_idx == 1:
                disp_median = np.nan
            else:
                ref_spreads = spread_samples
                ref_source = f"fallback_fold_{fold_idx}"
                disp_median = float(np.median(ref_spreads))
        else:
            disp_median = float(np.median(ref_spreads))
        print(
            f"[PORTFOLIO-DISP-SIZE] fold {fold_idx}/{len(date_folds)} {fold_start.date()} -> {fold_end.date()} rows={len(fold_df)} ref_median={disp_median if np.isfinite(disp_median) else 'NA'} source={ref_source}",
            flush=True,
        )

        prev_weights: Dict[str, float] = {}
        event_returns: List[float] = []
        event_turnovers: List[float] = []
        event_size_multipliers: List[float] = []
        event_spreads: List[float] = []
        event_top_liquid_weights: List[float] = []
        event_non_top_liquid_weights: List[float] = []
        event_majority_non_top_liquid: List[bool] = []
        ticker_contrib: Dict[str, float] = {}

        for idx in range(len(open_times) - 1):
            if idx % rebalance_every_sessions != 0:
                continue
            open_ts = open_times[idx]
            next_idx = min(idx + rebalance_every_sessions, len(open_times) - 1)
            next_open_ts = open_times[next_idx]
            if next_open_ts == open_ts or open_ts not in snapshots:
                continue

            current = snapshots[open_ts].copy()
            current["est_cost"] = estimate_roundtrip_cost(current)
            longs = current.head(top_k).copy()
            centered = pd.to_numeric(longs["Prediction"], errors="coerce") - float(pd.to_numeric(longs["Prediction"], errors="coerce").min())
            centered = centered + 1e-6
            denom = float(centered.sum())
            if not np.isfinite(denom) or denom <= 0.0:
                longs["alloc_weight"] = 1.0 / top_k
            else:
                longs["alloc_weight"] = centered / denom

            disp = float(current.iloc[0]["Prediction"] - current.iloc[4]["Prediction"])
            if ref_source == "fold1_constant_1p0":
                size_multiplier = 1.0
            elif not np.isfinite(disp_median) or disp_median <= 0.0:
                size_multiplier = 1.0
            else:
                size_multiplier = float(np.clip(disp / disp_median, 0.0, 1.5))
            if ref_spreads:
                dispersion_percentile = float(np.mean(np.asarray(ref_spreads, dtype=float) <= disp))
            else:
                dispersion_percentile = np.nan
            longs["alloc_weight"] = longs["alloc_weight"] * size_multiplier

            weights: Dict[str, float] = {}
            event_return = 0.0
            for _, row in longs.iterrows():
                w = float(row["alloc_weight"])
                raw_ret = (float(row["NextClose"]) / max(float(row["Close"]), 1e-9)) - 1.0
                contribution = w * raw_ret - abs(w) * float(row["est_cost"])
                event_return += contribution
                ticker = str(row["Ticker"])
                weights[ticker] = w
                ticker_contrib[ticker] = ticker_contrib.get(ticker, 0.0) + contribution

            top_liquid_weight = float(
                sum(float(w) for ticker, w in weights.items() if str(ticker).strip().upper() in top_liquid_subset)
            )
            non_top_liquid_weight = float(
                sum(float(w) for ticker, w in weights.items() if str(ticker).strip().upper() not in top_liquid_subset)
            )
            universe = set(prev_weights) | set(weights)
            turnover = float(sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in universe))
            prev_weights = weights

            event_returns.append(event_return)
            event_turnovers.append(turnover)
            event_size_multipliers.append(size_multiplier)
            event_spreads.append(disp)
            event_top_liquid_weights.append(top_liquid_weight)
            event_non_top_liquid_weights.append(non_top_liquid_weight)
            event_majority_non_top_liquid.append(non_top_liquid_weight > top_liquid_weight)
            history_rows.append(
                {
                    "experiment_id": experiment_id,
                    "fold_id": fold_idx,
                    "weighting_mode": "score_weighted_dispersion_sized",
                    "top_k": top_k,
                    "rebalance_every_sessions": rebalance_every_sessions,
                    "rebalance_idx": idx + 1,
                    "open_ts": open_ts,
                    "next_open_ts": next_open_ts,
                    "dispersion_top1_minus_top5": disp,
                    "dispersion_reference_median": disp_median,
                    "dispersion_reference_source": ref_source,
                    "dispersion_percentile_vs_ref": dispersion_percentile,
                    "size_multiplier": size_multiplier,
                    "portfolio_return": event_return,
                    "portfolio_return_sign": int(np.sign(event_return)),
                    "turnover": turnover,
                    "selected_weight_top_liquid14": top_liquid_weight,
                    "selected_weight_non_top_liquid": non_top_liquid_weight,
                    "majority_non_top_liquid": bool(non_top_liquid_weight > top_liquid_weight),
                    "long_names": ",".join(longs["Ticker"].astype(str).tolist()),
                    "long_weights": ",".join(f"{float(w):.6f}" for w in longs["alloc_weight"].tolist()),
                }
            )

        if not event_returns:
            continue

        contrib_total_abs = float(sum(abs(v) for v in ticker_contrib.values()))
        top_contrib_share = 0.0
        if contrib_total_abs > 0:
            top_contrib_share = max(abs(v) for v in ticker_contrib.values()) / contrib_total_abs

        periods_per_year = max(1.0, 250.0 / float(rebalance_every_sessions))
        mean_return = float(np.mean(event_returns))
        approx_annualized_return = float((1.0 + mean_return) ** periods_per_year - 1.0) if mean_return > -0.999999 else np.nan
        summary_rows.append(
            {
                "experiment_id": experiment_id,
                "fold_id": int(fold_idx),
                "fold_start_date": fold_start,
                "fold_end_date": fold_end,
                "fold_trade_dates": int(len(fold_dates)),
                "fold_rows": int(len(fold_df)),
                "weighting_mode": "score_weighted_dispersion_sized",
                "top_k": top_k,
                "rebalance_rule": f"every_{rebalance_every_sessions}_session_open",
                "rebalance_count": int(len(event_returns)),
                "portfolio_mean_return": mean_return,
                "portfolio_median_return": float(np.median(event_returns)),
                "portfolio_std_return": float(np.std(event_returns)),
                "portfolio_mean_turnover": float(np.mean(event_turnovers)) if event_turnovers else np.nan,
                "portfolio_win_rate": float(np.mean([val > 0 for val in event_returns])),
                "positive_windows": int(sum(val > 0 for val in event_returns)),
                "zero_windows": int(sum(np.isclose(val, 0.0) for val in event_returns)),
                "negative_windows": int(sum(val < 0 for val in event_returns)),
                "top_contributor_share": top_contrib_share,
                "mean_dispersion_top1_minus_top5": float(np.mean(event_spreads)) if event_spreads else np.nan,
                "dispersion_reference_median": disp_median,
                "dispersion_reference_source": ref_source,
                "mean_size_multiplier": float(np.mean(event_size_multipliers)) if event_size_multipliers else np.nan,
                "mean_selected_weight_top_liquid14": float(np.mean(event_top_liquid_weights)) if event_top_liquid_weights else np.nan,
                "mean_selected_weight_non_top_liquid": float(np.mean(event_non_top_liquid_weights)) if event_non_top_liquid_weights else np.nan,
                "majority_non_top_liquid_rate": float(np.mean(event_majority_non_top_liquid)) if event_majority_non_top_liquid else np.nan,
                "benchmark_policy": benchmark_policy,
                "benchmark_return": benchmark_return,
                "excess_vs_benchmark": mean_return - benchmark_return,
                "beats_flat": bool(mean_return > 0.0),
                "beats_benchmark": bool(mean_return > benchmark_return),
                "promotion_verdict": "baseline_promoted"
                if (mean_return > 0.0 and mean_return > benchmark_return and top_contrib_share <= 0.60)
                else "research_only",
                "approx_periods_per_year": periods_per_year,
                "approx_annualized_return": approx_annualized_return,
            }
        )

    combined = pd.DataFrame(summary_rows)
    combined_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_summary.csv"
    combined.to_csv(combined_csv, index=False)

    aggregate_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_aggregate.csv"
    if combined.empty:
        pd.DataFrame().to_csv(aggregate_csv, index=False)
    else:
        aggregate = (
            combined.groupby(
                ["experiment_id", "weighting_mode", "top_k", "rebalance_rule"],
                dropna=False,
            )
            .agg(
                fold_count=("fold_id", "nunique"),
                mean_of_fold_returns=("portfolio_mean_return", "mean"),
                min_fold_return=("portfolio_mean_return", "min"),
                max_fold_return=("portfolio_mean_return", "max"),
                mean_of_fold_annualized=("approx_annualized_return", "mean"),
                min_fold_annualized=("approx_annualized_return", "min"),
                max_fold_annualized=("approx_annualized_return", "max"),
                mean_of_fold_turnover=("portfolio_mean_turnover", "mean"),
                mean_of_fold_win_rate=("portfolio_win_rate", "mean"),
                mean_size_multiplier=("mean_size_multiplier", "mean"),
                mean_selected_weight_top_liquid14=("mean_selected_weight_top_liquid14", "mean"),
                mean_selected_weight_non_top_liquid=("mean_selected_weight_non_top_liquid", "mean"),
                max_majority_non_top_liquid_rate=("majority_non_top_liquid_rate", "max"),
                folds_beating_flat=("beats_flat", "sum"),
                folds_beating_benchmark=("beats_benchmark", "sum"),
                max_top_contributor_share=("top_contributor_share", "max"),
            )
            .reset_index()
        )
        aggregate["all_folds_positive"] = aggregate["folds_beating_flat"] == aggregate["fold_count"]
        aggregate["all_folds_beat_benchmark"] = aggregate["folds_beating_benchmark"] == aggregate["fold_count"]
        aggregate["walkforward_verdict"] = np.where(
            aggregate["all_folds_positive"] & aggregate["all_folds_beat_benchmark"] & (aggregate["max_top_contributor_share"] <= 0.60),
            "dispersion_sized_walkforward_validated",
            "dispersion_sized_walkforward_fragile",
        )
        aggregate = aggregate.sort_values(
            ["mean_of_fold_annualized", "min_fold_return", "mean_of_fold_turnover"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        aggregate.to_csv(aggregate_csv, index=False)

    manifest_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_csv, index=False)
    history_csv = baseline_dir / "portfolio_rank_60m_dispersion_sizing_walkforward_history.csv"
    pd.DataFrame(history_rows).to_csv(history_csv, index=False)
    main_logger.info(f"[PORTFOLIO-DISP-SIZE] dispersion-sized walk-forward summary saved: {combined_csv}")
    main_logger.info(f"[PORTFOLIO-DISP-SIZE] dispersion-sized walk-forward aggregate saved: {aggregate_csv}")
    main_logger.info(f"[PORTFOLIO-DISP-SIZE] dispersion-sized walk-forward manifest saved: {manifest_csv}")
    main_logger.info(f"[PORTFOLIO-DISP-SIZE] dispersion-sized walk-forward history saved: {history_csv}")
    print(f"[PORTFOLIO-DISP-SIZE] dispersion-sized walk-forward summary saved: {combined_csv}", flush=True)
    return combined


def run_native_15m_holding_horizon_execution_sweep(
    instrument_df: pd.DataFrame,
    best_params: dict,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int,
) -> pd.DataFrame:
    baseline_dir = RESULTS_DIR / "signal_baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    print("[HOLD-SWEEP] initializing E1903 execution sweep", flush=True)

    def _prediction_coverage(df_slice: pd.DataFrame, pred_col: str) -> float:
        pred = pd.to_numeric(df_slice.get(pred_col, pd.Series(dtype=float)), errors="coerce").fillna(0.5)
        row_count = int(len(pred))
        if row_count == 0:
            return 0.0
        nondefault = (pred - 0.5).abs() > 1e-9
        return float(nondefault.mean())

    def _bootstrap_ci(values: np.ndarray, seed: int, n_bootstrap: int = 1000) -> tuple[float, float]:
        clean = np.asarray(values, dtype=float)
        clean = clean[np.isfinite(clean)]
        if clean.size == 0:
            return (np.nan, np.nan)
        if clean.size == 1:
            only = float(clean[0])
            return (only, only)
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, clean.size, size=(n_bootstrap, clean.size))
        sample_means = clean[idx].mean(axis=1)
        return (
            float(np.quantile(sample_means, 0.05)),
            float(np.quantile(sample_means, 0.95)),
        )

    ensure_signal_overlay_predictions_available(
        ["E1903", "E211"],
        "native-15m holding-horizon execution sweep",
    )

    sweep_specs = [
        {"variant_label": "E1903_hold4_band70", "policy": "SIGNAL_E1903_BANDED_70", "entry_threshold": 0.70, "max_holding_bars": 4},
        {"variant_label": "E1903_hold4_band75", "policy": "SIGNAL_E1903_BANDED_75", "entry_threshold": 0.75, "max_holding_bars": 4},
        {"variant_label": "E1903_hold4_band80", "policy": "SIGNAL_E1903_BANDED_80", "entry_threshold": 0.80, "max_holding_bars": 4},
        {"variant_label": "E1903_hold4_band85", "policy": "SIGNAL_E1903_BANDED_85", "entry_threshold": 0.85, "max_holding_bars": 4},
        {"variant_label": "E1903_hold8_band70", "policy": "SIGNAL_E1903_BANDED_70", "entry_threshold": 0.70, "max_holding_bars": 8},
        {"variant_label": "E1903_hold8_band75", "policy": "SIGNAL_E1903_BANDED_75", "entry_threshold": 0.75, "max_holding_bars": 8},
        {"variant_label": "E1903_hold8_band80", "policy": "SIGNAL_E1903_BANDED_80", "entry_threshold": 0.80, "max_holding_bars": 8},
        {"variant_label": "E1903_hold8_band85", "policy": "SIGNAL_E1903_BANDED_85", "entry_threshold": 0.85, "max_holding_bars": 8},
        {"variant_label": "E1903_hold16_band70", "policy": "SIGNAL_E1903_BANDED_70", "entry_threshold": 0.70, "max_holding_bars": 16},
        {"variant_label": "E1903_hold16_band75", "policy": "SIGNAL_E1903_BANDED_75", "entry_threshold": 0.75, "max_holding_bars": 16},
        {"variant_label": "E1903_hold16_band80", "policy": "SIGNAL_E1903_BANDED_80", "entry_threshold": 0.80, "max_holding_bars": 16},
        {"variant_label": "E1903_hold16_band85", "policy": "SIGNAL_E1903_BANDED_85", "entry_threshold": 0.85, "max_holding_bars": 16},
        {"variant_label": "E1903_eod_band70", "policy": "SIGNAL_E1903_BANDED_70", "entry_threshold": 0.70, "max_holding_bars": interval_to_bars_per_day("15minute")},
        {"variant_label": "E1903_eod_band75", "policy": "SIGNAL_E1903_BANDED_75", "entry_threshold": 0.75, "max_holding_bars": interval_to_bars_per_day("15minute")},
        {"variant_label": "E1903_eod_band80", "policy": "SIGNAL_E1903_BANDED_80", "entry_threshold": 0.80, "max_holding_bars": interval_to_bars_per_day("15minute")},
        {"variant_label": "E1903_eod_band85", "policy": "SIGNAL_E1903_BANDED_85", "entry_threshold": 0.85, "max_holding_bars": interval_to_bars_per_day("15minute")},
        {"variant_label": "FLAT_control", "policy": "FLAT", "entry_threshold": np.nan, "max_holding_bars": np.nan},
        {"variant_label": "E211_incumbent", "policy": "SIGNAL_E211_BANDED_68", "entry_threshold": 0.68, "max_holding_bars": np.nan},
    ]

    for spec in sweep_specs:
        if not str(spec["policy"]).startswith("SIGNAL_E1903_BANDED_"):
            continue
        parsed_thresholds = _parse_signal_banded_threshold_for_prefix(str(spec["policy"]), "SIGNAL_E1903")
        if parsed_thresholds is None:
            raise ValueError(f"Invalid holding-horizon sweep policy: {spec['policy']}")
        parsed_entry_threshold, _ = parsed_thresholds
        expected_threshold = float(spec["entry_threshold"])
        if not math.isclose(parsed_entry_threshold, expected_threshold, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(
                f"Holding-horizon spec mismatch for {spec['variant_label']}: "
                f"policy {spec['policy']} encodes {parsed_entry_threshold:.2f}, "
                f"metadata says {expected_threshold:.2f}"
            )

    detail_rows: List[dict] = []
    baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
    total_tickers = len(baseline_tickers)
    print(
        f"[HOLD-SWEEP] configured {len(sweep_specs)} variants across {total_tickers} tickers",
        flush=True,
    )
    env_kwargs = {
        "stop_loss": best_params.get("stop_loss", stop_loss),
        "take_profit": best_params.get("take_profit", take_profit),
        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
        "annual_trading_days": annual_trading_days,
        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
        "hold_threshold": best_params.get("hold_threshold", 0.1),
        "reward_weights": {
            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": best_params.get("inference_buy_threshold", 0.08),
        "inference_sell_threshold": best_params.get("inference_sell_threshold", 0.08),
    }

    for ticker_idx, ticker in enumerate(baseline_tickers, start=1):
        print(f"[HOLD-SWEEP] ticker {ticker_idx}/{total_tickers}: {ticker} - loading data", flush=True)
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            print(f"[HOLD-SWEEP] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (token missing)", flush=True)
            continue
        df_full = get_data_kite(kite, instrument_token=token, days=540, interval="15minute")
        if df_full.empty:
            print(f"[HOLD-SWEEP] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (no data)", flush=True)
            continue

        windows = make_walk_forward_slices(
            df_full,
            interval="15minute",
            train_days=180,
            val_days=30,
            test_days=15,
            step_days=15,
        )
        windows = windows[:3]
        if not windows:
            print(f"[HOLD-SWEEP] ticker {ticker_idx}/{total_tickers}: {ticker} - skipped (no windows)", flush=True)
            continue
        print(
            f"[HOLD-SWEEP] ticker {ticker_idx}/{total_tickers}: {ticker} - {len(windows)} cycle(s), {len(sweep_specs)} variants each",
            flush=True,
        )

        for cycle_idx, (_, tr_end, va_end, te_end) in enumerate(windows, start=1):
            val_df = df_full.iloc[tr_end:va_end].reset_index(drop=True)
            test_df = df_full.iloc[va_end:te_end].reset_index(drop=True)
            if val_df.empty or test_df.empty:
                print(
                    f"[HOLD-SWEEP] {ticker} cycle {cycle_idx}/{len(windows)} - skipped (empty split)",
                    flush=True,
                )
                continue
            print(
                f"[HOLD-SWEEP] {ticker} cycle {cycle_idx}/{len(windows)} - val {len(val_df)} rows / test {len(test_df)} rows",
                flush=True,
            )
            val_e1903_coverage = _prediction_coverage(val_df, "Signal_E1903_Pred")
            test_e1903_coverage = _prediction_coverage(test_df, "Signal_E1903_Pred")
            print(
                "[HOLD-SWEEP] "
                f"{ticker} cycle {cycle_idx}/{len(windows)} coverage - "
                f"val E1903 nondefault {val_e1903_coverage:.1%}, "
                f"test E1903 nondefault {test_e1903_coverage:.1%}",
                flush=True,
            )
            cycle_variant_rows: List[dict] = []
            for spec in sweep_specs:
                env_overrides = {}
                max_holding_bars = spec["max_holding_bars"]
                if pd.notna(max_holding_bars):
                    env_overrides["max_holding_bars"] = int(max_holding_bars)
                val_res = run_baseline_backtest(
                    val_df,
                    ticker,
                    initial_balance,
                    env_kwargs,
                    str(spec["policy"]),
                    seed=RANDOM_SEED + cycle_idx,
                    env_overrides=env_overrides,
                )
                test_res = run_baseline_backtest(
                    test_df,
                    ticker,
                    initial_balance,
                    env_kwargs,
                    str(spec["policy"]),
                    seed=RANDOM_SEED + 1000 + cycle_idx,
                    env_overrides=env_overrides,
                )
                val_metrics = val_res["metrics"]
                test_metrics = test_res["metrics"]
                detail_rows.append(
                    {
                        "ticker": ticker,
                        "cycle": cycle_idx,
                        "variant_label": spec["variant_label"],
                        "policy": spec["policy"],
                        "entry_threshold": spec["entry_threshold"],
                        "max_holding_bars": spec["max_holding_bars"],
                        "val_return": val_metrics["total_return"],
                        "val_drawdown": val_metrics["max_drawdown"],
                        "val_sharpe": val_metrics["sharpe"],
                        "val_turnover": val_metrics["turnover"],
                        "val_trades": val_metrics["trade_count"],
                        "val_avg_holding_bars": val_metrics["avg_holding_bars"],
                        "val_e1903_coverage": val_e1903_coverage,
                        "test_return": test_metrics["total_return"],
                        "test_drawdown": test_metrics["max_drawdown"],
                        "test_sharpe": test_metrics["sharpe"],
                        "test_turnover": test_metrics["turnover"],
                        "test_trades": test_metrics["trade_count"],
                        "test_avg_holding_bars": test_metrics["avg_holding_bars"],
                        "test_e1903_coverage": test_e1903_coverage,
                    }
                )
                cycle_variant_rows.append(detail_rows[-1])

            if cycle_variant_rows:
                cycle_best = max(cycle_variant_rows, key=lambda row: float(row.get("test_return", -np.inf)))
                print(
                    "[HOLD-SWEEP] "
                    f"{ticker} cycle {cycle_idx}/{len(windows)} best={cycle_best['variant_label']} "
                    f"ret={float(cycle_best['test_return']):.6f} "
                    f"trades={float(cycle_best['test_trades']):.2f} "
                    f"hold={float(cycle_best['test_avg_holding_bars']):.2f}",
                    flush=True,
                )

        if ticker_idx % 5 == 0 or ticker_idx == total_tickers:
            print(
                f"[HOLD-SWEEP] progress checkpoint - completed {ticker_idx}/{total_tickers} tickers, rows={len(detail_rows)}",
                flush=True,
            )

    detail_df = pd.DataFrame(detail_rows)
    detail_csv = baseline_dir / "native_15m_holding_horizon_execution_sweep_detail.csv"
    summary_csv = baseline_dir / "native_15m_holding_horizon_execution_sweep_summary.csv"
    detail_df.to_csv(detail_csv, index=False)

    if detail_df.empty:
        pd.DataFrame().to_csv(summary_csv, index=False)
        main_logger.warning("[HOLD-SWEEP] no rows generated for holding-horizon execution sweep.")
        return pd.DataFrame()

    summary_df = (
        detail_df.groupby(["variant_label", "policy", "entry_threshold", "max_holding_bars"], dropna=False)[
            [
                "val_return",
                "val_drawdown",
                "val_sharpe",
                "val_turnover",
                "val_trades",
                "val_avg_holding_bars",
                "val_e1903_coverage",
                "test_return",
                "test_drawdown",
                "test_sharpe",
                "test_turnover",
                "test_trades",
                "test_avg_holding_bars",
                "test_e1903_coverage",
            ]
        ]
        .mean()
        .reset_index()
        .sort_values(["val_return", "val_sharpe", "test_return", "test_sharpe"], ascending=[False, False, False, False])
        .reset_index(drop=True)
    )

    incumbent_cycle_df = detail_df.loc[
        detail_df["variant_label"] == "E211_incumbent",
        ["ticker", "cycle", "val_return", "test_return"],
    ].rename(
        columns={
            "val_return": "benchmark_val_return",
            "test_return": "benchmark_test_return",
        }
    )
    incumbent_val_return = float(
        pd.to_numeric(incumbent_cycle_df["benchmark_val_return"], errors="coerce").mean()
    ) if not incumbent_cycle_df.empty else np.nan
    incumbent_test_return = float(
        pd.to_numeric(incumbent_cycle_df["benchmark_test_return"], errors="coerce").mean()
    ) if not incumbent_cycle_df.empty else np.nan

    paired_rows: List[dict] = []
    for variant_idx, (variant_label, variant_df) in enumerate(detail_df.groupby("variant_label", dropna=False), start=1):
        paired_df = variant_df.merge(incumbent_cycle_df, on=["ticker", "cycle"], how="inner")
        if paired_df.empty:
            paired_rows.append(
                {
                    "variant_label": variant_label,
                    "paired_obs": 0,
                    "val_paired_excess_mean": np.nan,
                    "val_paired_excess_ci_low": np.nan,
                    "val_paired_excess_ci_high": np.nan,
                    "test_paired_excess_mean": np.nan,
                    "test_paired_excess_ci_low": np.nan,
                    "test_paired_excess_ci_high": np.nan,
                }
            )
            continue
        val_diffs = (
            pd.to_numeric(paired_df["val_return"], errors="coerce")
            - pd.to_numeric(paired_df["benchmark_val_return"], errors="coerce")
        ).to_numpy(dtype=float)
        test_diffs = (
            pd.to_numeric(paired_df["test_return"], errors="coerce")
            - pd.to_numeric(paired_df["benchmark_test_return"], errors="coerce")
        ).to_numpy(dtype=float)
        val_ci_low, val_ci_high = _bootstrap_ci(val_diffs, seed=RANDOM_SEED + variant_idx)
        test_ci_low, test_ci_high = _bootstrap_ci(test_diffs, seed=RANDOM_SEED + 500000 + variant_idx)
        paired_rows.append(
            {
                "variant_label": variant_label,
                "paired_obs": int(np.isfinite(test_diffs).sum()),
                "val_paired_excess_mean": float(np.nanmean(val_diffs)) if np.isfinite(val_diffs).any() else np.nan,
                "val_paired_excess_ci_low": val_ci_low,
                "val_paired_excess_ci_high": val_ci_high,
                "test_paired_excess_mean": float(np.nanmean(test_diffs)) if np.isfinite(test_diffs).any() else np.nan,
                "test_paired_excess_ci_low": test_ci_low,
                "test_paired_excess_ci_high": test_ci_high,
            }
        )

    summary_df = summary_df.merge(pd.DataFrame(paired_rows), on="variant_label", how="left")
    summary_df["benchmark_policy"] = "SIGNAL_E211_BANDED_68"
    summary_df["selection_split"] = "val"
    summary_df["report_split"] = "test"
    summary_df["benchmark_val_return"] = incumbent_val_return
    summary_df["benchmark_test_return"] = incumbent_test_return
    summary_df["val_excess_vs_benchmark"] = pd.to_numeric(summary_df["val_return"], errors="coerce") - incumbent_val_return
    summary_df["test_excess_vs_benchmark"] = pd.to_numeric(summary_df["test_return"], errors="coerce") - incumbent_test_return
    summary_df["excess_vs_benchmark"] = summary_df["test_excess_vs_benchmark"]
    summary_df["beats_flat"] = (
        pd.to_numeric(summary_df["val_return"], errors="coerce") > 0.0
    ) & (
        pd.to_numeric(summary_df["test_return"], errors="coerce") > 0.0
    )
    summary_df["beats_benchmark"] = (
        pd.to_numeric(summary_df["val_paired_excess_mean"], errors="coerce") > 0.0
    ) & (
        pd.to_numeric(summary_df["test_paired_excess_mean"], errors="coerce") > 0.0
    )
    summary_df["promotion_verdict"] = np.where(
        summary_df["beats_flat"] & summary_df["beats_benchmark"],
        "baseline_promoted",
        "research_only",
    )
    summary_df.to_csv(summary_csv, index=False)
    main_logger.info(f"[HOLD-SWEEP] detail saved: {detail_csv}")
    main_logger.info(f"[HOLD-SWEEP] summary saved: {summary_csv}")
    print(f"[HOLD-SWEEP] detail saved: {detail_csv}", flush=True)
    print(f"[HOLD-SWEEP] summary saved: {summary_csv}", flush=True)
    return summary_df


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
    vec_train = DummyVecEnv([lambda e=env_train: e])
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
                        "max_position_size": FIXED_OVERLAY_MAX_POSITION_SIZE,
                        "max_drawdown": best_params.get("max_drawdown", max_drawdown),
                        "annual_trading_days": annual_trading_days,
                        "some_factor": best_params.get("drawdown_penalty_factor", 0.01),
                        "hold_threshold": best_params.get("hold_threshold", 0.1),
                        "reward_weights": {
                            "transaction_penalty_weight": best_params.get("transaction_penalty_weight", 1.0),
                            "forced_stop_penalty_weight": best_params.get("forced_stop_penalty_weight", 1.0),
                            "forced_tp_penalty_weight": best_params.get("forced_tp_penalty_weight", 1.0),
                            "volatility_penalty_weight": best_params.get("volatility_penalty_weight", 0.10),
                            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
                            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
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

                    for bname in ["FLAT", "RANDOM", "SMA", "RSI", "SIGNAL_E102", "SIGNAL_E102_BANDED"]:
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
    validation_slices = []
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
                'forced_tp_penalty_weight': forced_tp_penalty_weight,
                'signal_gate_enabled': True,
                'signal_gate_entry_threshold': 0.68,
                'signal_gate_reduce_threshold': 0.60,
            },
            max_episode_steps=len(df_train),
            mode="train",  # Training mode: filtering is NOT applied here.
            inference_buy_threshold=tuned_inference_buy_threshold,
            inference_sell_threshold=tuned_inference_sell_threshold  
        )
        main_logger.info(f"[Trial {trial.number}] Environment for ticker {ticker} created (env_rank={i}).")
        env_pairs.append((ticker, env_instance))
        validation_slices.append((ticker, df_val.reset_index(drop=True)))
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

    # Collect full net worth and path-quality metrics from each sub-environment's history
    full_worth_list = []
    cycle_metric_list = []
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
        cycle_metric_list.append(_compute_cycle_metrics(history, initial_balance))

    # Compute average final full net worth across sub-environments
    if len(full_worth_list) == 0:
        avg_full_worth = 0
    else:
        avg_full_worth = float(np.mean(full_worth_list))

    # Compute net worth change relative to the initial balance
    networth_change = (avg_full_worth - initial_balance) / initial_balance
    avg_max_drawdown = float(np.mean([m["max_drawdown"] for m in cycle_metric_list])) if cycle_metric_list else 1.0
    avg_turnover = float(np.mean([m["turnover"] for m in cycle_metric_list])) if cycle_metric_list else 1.0
    avg_sharpe = float(np.mean([m["sharpe"] for m in cycle_metric_list])) if cycle_metric_list else -10.0
    avg_trade_count = float(np.mean([m["trade_count"] for m in cycle_metric_list])) if cycle_metric_list else 0.0
    trial.set_user_attr("avg_networth_change", networth_change)
    trial.set_user_attr("avg_max_drawdown", avg_max_drawdown)
    trial.set_user_attr("avg_turnover", avg_turnover)
    trial.set_user_attr("avg_sharpe", avg_sharpe)
    trial.set_user_attr("avg_trade_count_raw", avg_trade_count)
    trial.set_user_attr("avg_trade_count", avg_trade_count)
    main_logger.info(
        f"[Trial {trial.number}] aggregate metrics: "
        f"networth_change={networth_change:.6f}, avg_dd={avg_max_drawdown:.6f}, "
        f"avg_turnover={avg_turnover:.6f}, avg_sharpe={avg_sharpe:.6f}, avg_trades={avg_trade_count:.2f}"
    )

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


def objective_overlay_validation(
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
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
    from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList

    learning_rate = trial.suggest_loguniform('learning_rate', 1e-6, 1e-3)
    n_steps = trial.suggest_categorical('n_steps', [512])
    batch_size = trial.suggest_categorical('batch_size', [32, 64])
    gamma = trial.suggest_uniform('gamma', 0.95, 0.999)
    gae_lambda = trial.suggest_uniform('gae_lambda', 0.80, 1.00)
    clip_range = trial.suggest_uniform('clip_range', 0.05, 0.3)
    ent_coef = trial.suggest_loguniform('ent_coef', 1e-5, 1e-1)
    vf_coef = trial.suggest_uniform('vf_coef', 0.05, 0.5)
    max_grad_norm = trial.suggest_uniform('max_grad_norm', 0.3, 1.0)

    drawdown_penalty_factor = trial.suggest_float('drawdown_penalty_factor', 0.0, 5.0, log=False)
    tuned_stop_loss = trial.suggest_float('stop_loss', 0.75, 0.95, step=0.01)
    tuned_take_profit = trial.suggest_float('take_profit', 1.01, 1.50, step=0.01)
    tuned_reward_scale = trial.suggest_float('reward_scale', 0.5, 3.0, step=0.1)
    tuned_max_position_size = FIXED_OVERLAY_MAX_POSITION_SIZE
    tuned_max_drawdown = trial.suggest_float('max_drawdown', 0.02, 0.2, step=0.005)
    profit_weight = trial.suggest_float('profit_weight', 0.0, 5.0)
    sharpe_bonus_weight = trial.suggest_float('sharpe_bonus_weight', 0.01, 5.0)
    transaction_penalty_weight = trial.suggest_float("transaction_penalty_weight", 0.0, 5.0, log=False)
    holding_bonus_weight = trial.suggest_float('holding_bonus_weight', 0.0, 5.0)
    volatility_threshold = trial.suggest_float("volatility_threshold", 0.5, 2.5)
    momentum_threshold_min = trial.suggest_float("momentum_threshold_min", 30, 50)
    momentum_threshold_max = trial.suggest_float("momentum_threshold_max", 50, 80)
    hold_threshold = trial.suggest_float("hold_threshold", 0.0, 0.1, step=0.01)
    tuned_inference_buy_threshold = trial.suggest_float("inference_buy_threshold", 0.05, 0.1)
    tuned_inference_sell_threshold = trial.suggest_float("inference_sell_threshold", 0.05, 0.1)
    forced_stop_penalty_weight = trial.suggest_float("forced_stop_penalty_weight", 0.0, 5.0, log=False)
    forced_tp_penalty_weight = trial.suggest_float("forced_tp_penalty_weight", 0.0, 5.0, log=False)

    env_factories = []
    validation_slices = []
    for i, ticker in enumerate(train_tickers):
        main_logger.info(f"[Trial {trial.number}] Creating training environment for ticker {ticker}")
        token = get_instrument_token(ticker, instrument_df)
        if token is None:
            main_logger.error(f"Token not found for ticker {ticker}. Skipping.")
            continue
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
                'forced_tp_penalty_weight': forced_tp_penalty_weight,
                'signal_gate_enabled': True,
                'signal_gate_entry_threshold': 0.68,
                'signal_gate_reduce_threshold': 0.60,
            },
            max_episode_steps=len(df_train),
            mode="train",
            inference_buy_threshold=tuned_inference_buy_threshold,
            inference_sell_threshold=tuned_inference_sell_threshold
        )
        env_factories.append(lambda e=env_instance: e)
        validation_slices.append((ticker, df_val.reset_index(drop=True)))
        main_logger.info(f"[Trial {trial.number}] Environment for ticker {ticker} created (env_rank={i}).")

    if not env_factories:
        main_logger.critical(f"[Trial {trial.number}] No training environments were created. Exiting trial.")
        return {
            "net_return": -1.0,
            "avg_max_drawdown": 1.0,
            "avg_turnover": 1.0,
            "avg_sharpe": -10.0,
            "avg_trade_count": 0.0,
        }

    vec_env_train = SubprocVecEnv(env_factories)
    vec_env_train = VecNormalize(vec_env_train, norm_obs=True, norm_reward=True, clip_obs=10000.0, clip_reward=250000.0)

    num_layers = trial.suggest_int("num_layers", 2, 5)
    net_arch = []
    for layer_i in range(num_layers):
        layer_size = trial.suggest_categorical(f"layer_size_{layer_i}", [64, 128, 256])
        net_arch.append(layer_size)

    policy_kwargs = dict(activation_fn=torch.nn.ReLU, net_arch=net_arch)
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

    trial_checkpoint_dir = RESULTS_DIR / f"checkpoints_trial_{trial.number}"
    trial_checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_callback = CheckpointCallback(
        save_freq=500,
        save_path=str(trial_checkpoint_dir),
        name_prefix="ppo_model"
    )
    custom_callback = CustomTensorboardCallback()
    early_stopping_callback = EarlyStoppingCallback(
        monitor="rolling_sharpe",
        patience=3000,
        min_delta=0.02,
        verbose=1,
        trial_id=trial.number,
        window=2000
    )
    callback_list = CallbackList([custom_callback, checkpoint_callback, early_stopping_callback])

    total_timesteps = OVERLAY_TUNE_TIMESTEPS
    start_time = time.time()
    main_logger.info(f"[Trial {trial.number}] Trial Hyperparameters: {trial.params}")
    main_logger.info(f"[Trial {trial.number}] Starting PPO training with {total_timesteps} timesteps.")
    try:
        model.learn(total_timesteps=total_timesteps, callback=callback_list)
    except Exception:
        error_message = traceback.format_exc()
        main_logger.critical(f"[Trial {trial.number}] Training failed with exception:\n{error_message}")
        vec_env_train.close()
        return {
            "net_return": -1.0,
            "avg_max_drawdown": 1.0,
            "avg_turnover": 1.0,
            "avg_sharpe": -10.0,
            "avg_trade_count": 0.0,
        }
    duration = time.time() - start_time
    main_logger.info(f"[Trial {trial.number}] Finished PPO training in {duration:.2f} seconds.")

    trial_model_path = trial_checkpoint_dir / "trial_model_final.zip"
    trial_vecnorm_path = trial_checkpoint_dir / "trial_vecnorm_final.pkl"
    model.save(str(trial_model_path))
    vec_env_train.save(str(trial_vecnorm_path))

    eval_env_kwargs = {
        "stop_loss": tuned_stop_loss,
        "take_profit": tuned_take_profit,
        "max_position_size": tuned_max_position_size,
        "max_drawdown": tuned_max_drawdown,
        "annual_trading_days": annual_trading_days,
        "some_factor": drawdown_penalty_factor,
        "hold_threshold": hold_threshold,
        "reward_weights": {
            "reward_scale": tuned_reward_scale,
            "profit_weight": profit_weight,
            "sharpe_bonus_weight": sharpe_bonus_weight,
            "transaction_penalty_weight": transaction_penalty_weight,
            "holding_bonus_weight": holding_bonus_weight,
            "volatility_threshold": volatility_threshold,
            "momentum_threshold_min": momentum_threshold_min,
            "momentum_threshold_max": momentum_threshold_max,
            "forced_stop_penalty_weight": forced_stop_penalty_weight,
            "forced_tp_penalty_weight": forced_tp_penalty_weight,
            "signal_gate_enabled": True,
            "signal_gate_entry_threshold": 0.68,
            "signal_gate_reduce_threshold": 0.60,
            "trade_fraction": FIXED_OVERLAY_TRADE_FRACTION,
            "reduce_fraction": FIXED_OVERLAY_REDUCE_FRACTION,
        },
        "inference_buy_threshold": tuned_inference_buy_threshold,
        "inference_sell_threshold": tuned_inference_sell_threshold
    }

    validation_results = []
    for ticker, df_val in validation_slices:
        if df_val.empty:
            continue
        eval_result = _evaluate_slice_with_frozen_norm(
            model_path=trial_model_path,
            vecnorm_path=trial_vecnorm_path,
            df_slice=df_val,
            ticker=ticker,
            initial_balance=initial_balance,
            env_kwargs=eval_env_kwargs,
            eval_tag=f"trial_{trial.number}_val"
        )
        validation_results.append((ticker, eval_result["metrics"]))

    vec_env_train.close()
    del vec_env_train
    import gc
    gc.collect()

    cycle_metric_list = [metrics for _, metrics in validation_results]
    result = {
        "net_return": float(np.mean([m["net_return"] for m in cycle_metric_list])) if cycle_metric_list else -1.0,
        "avg_max_drawdown": float(np.mean([m["max_drawdown"] for m in cycle_metric_list])) if cycle_metric_list else 1.0,
        "avg_turnover": float(np.mean([m["turnover"] for m in cycle_metric_list])) if cycle_metric_list else 1.0,
        "avg_sharpe": float(np.mean([m["sharpe"] for m in cycle_metric_list])) if cycle_metric_list else -10.0,
        "avg_trade_count": float(np.mean([m["trade_count"] for m in cycle_metric_list])) if cycle_metric_list else 0.0,
    }
    trial.set_user_attr("avg_networth_change", result["net_return"])
    trial.set_user_attr("avg_max_drawdown", result["avg_max_drawdown"])
    trial.set_user_attr("avg_turnover", result["avg_turnover"])
    trial.set_user_attr("avg_sharpe", result["avg_sharpe"])
    trial.set_user_attr("avg_trade_count_raw", result["avg_trade_count"])
    trial.set_user_attr("avg_trade_count", result["avg_trade_count"])
    main_logger.info(
        f"[Trial {trial.number}] aggregate metrics: "
        f"networth_change={result['net_return']:.6f}, avg_dd={result['avg_max_drawdown']:.6f}, "
        f"avg_turnover={result['avg_turnover']:.6f}, avg_sharpe={result['avg_sharpe']:.6f}, "
        f"avg_trades={result['avg_trade_count']:.2f}"
    )
    for ticker, metrics in validation_results:
        main_logger.info(
            f"[Trial {trial.number}] Validation summary for {ticker}: "
            f"return={metrics['net_return']:.6f}, dd={metrics['max_drawdown']:.6f}, "
            f"turnover={metrics['turnover']:.6f}, sharpe={metrics['sharpe']:.6f}, trades={metrics['trade_count']}"
        )
    return result


def objective_multi_objective(
    trial,
    train_tickers: list,
    initial_balance: float,
    stop_loss: float,
    take_profit: float,
    max_position_size: float,
    max_drawdown: float,
    annual_trading_days: int
):
    result = objective_overlay_validation(
        trial,
        train_tickers=train_tickers,
        initial_balance=initial_balance,
        stop_loss=stop_loss,
        take_profit=take_profit,
        max_position_size=max_position_size,
        max_drawdown=max_drawdown,
        annual_trading_days=annual_trading_days,
    )
    networth_change = float(result.get("net_return", -1.0))
    if not np.isfinite(networth_change):
        return (-1.0, 1.0, 1.0)
    avg_max_drawdown = float(result.get("avg_max_drawdown", trial.user_attrs.get("avg_max_drawdown", 1.0)))
    avg_turnover = float(result.get("avg_turnover", trial.user_attrs.get("avg_turnover", 1.0)))
    return (networth_change, avg_max_drawdown, avg_turnover)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ssell1 trading pipeline")
    parser.add_argument(
        "--mode",
        choices=[
            "signal_research",
            "signal_research_smoke",
            "signal_research_generalization",
            "signal_research_generalization_next",
            "signal_research_generalization_wave2",
            "signal_research_e102_deepdive",
            "signal_research_cross_sectional_60m",
            "signal_research_ablation_grid",
            "signal_research_setup_regimes",
            "signal_research_market_state_60m",
            "signal_research_multiscale_60m",
            "signal_research_second_timeframe_60m",
            "signal_research_intrahour_path_v1",
            "signal_research_breadth_context_60m",
            "signal_research_time_distribution_v2",
            "signal_research_native_15m_execution",
            "signal_research_native_15m_failed_breakout",
            "signal_research_native_15m_open_drive",
            "signal_research_opening_auction_gap_liquidity",
            "signal_research_native_15m_session_phase",
            "signal_research_native_15m_holding_horizon",
            "signal_research_native_15m_topk_event_rank",
            "signal_research_native_15m_breadth_event",
            "signal_research_native_15m_mean_reversion_exhaustion",
            "signal_research_sixty_minute_daily_context",
            "signal_research_cross_sectional_commonality_residual",
            "signal_research_intraday_volume_liquidity_forecast",
            "signal_research_event_outcome_accounting",
            "signal_research_event_outcome_accounting_refined",
            "signal_research_event_conditioned_sizing_veto",
            "signal_research_all_15m",
            "signal_research_portfolio_rank_60m",
            "signal_research_e302",
            "signal_research_two_track",
            "signal_baseline",
            "signal_baseline_e302",
            "signal_baseline_generalization_next",
            "signal_baseline_e102_deepdive",
            "signal_baseline_cross_sectional_60m",
            "signal_baseline_ablation_grid",
            "signal_baseline_setup_regimes",
            "signal_baseline_market_state_60m",
            "signal_baseline_multiscale_60m",
            "signal_baseline_second_timeframe_60m",
            "signal_baseline_intrahour_path_v1",
            "signal_baseline_breadth_context_60m",
            "signal_baseline_time_distribution_v2",
            "signal_baseline_time_distribution_v2_top",
            "signal_baseline_native_15m_execution",
            "signal_baseline_native_15m_execution_validate",
            "signal_baseline_native_15m_execution_top_compare",
            "signal_baseline_native_15m_failed_breakout",
            "signal_baseline_native_15m_open_drive",
            "signal_baseline_opening_auction_gap_liquidity",
            "signal_baseline_native_15m_session_phase",
            "signal_baseline_native_15m_holding_horizon",
            "signal_baseline_native_15m_holding_horizon_execution_sweep",
            "signal_baseline_native_15m_breadth_event",
            "signal_baseline_native_15m_topk_event_rank",
            "signal_baseline_native_15m_mean_reversion_exhaustion",
            "signal_baseline_native_15m_mean_reversion_exhaustion_compare",
            "signal_baseline_native_15m_mean_reversion_exhaustion_validate",
            "signal_baseline_sixty_minute_daily_context",
            "signal_baseline_cross_sectional_commonality_residual",
            "signal_baseline_intraday_volume_liquidity_forecast",
            "signal_baseline_event_outcome_accounting",
            "signal_baseline_event_outcome_accounting_refined",
            "signal_baseline_event_conditioned_sizing_veto",
            "signal_baseline_all_15m_top2",
            "signal_baseline_e211_intrahour_veto",
            "signal_baseline_e211_entry_audit",
            "signal_baseline_portfolio_rank_60m",
            "signal_baseline_portfolio_rank_60m_long_only",
            "signal_baseline_portfolio_rank_60m_long_only_sweep",
            "signal_baseline_portfolio_rank_60m_long_only_cadence_sweep",
            "signal_baseline_portfolio_rank_60m_long_only_walkforward",
            "signal_baseline_portfolio_rank_60m_long_only_hold_sweep",
            "signal_baseline_portfolio_rank_60m_long_only_hold_walkforward",
            "signal_baseline_portfolio_rank_60m_long_only_topk_sweep",
            "signal_baseline_portfolio_rank_60m_regime_gate_sweep",
            "signal_baseline_portfolio_rank_60m_score_weighted_sizing",
            "signal_baseline_portfolio_rank_60m_liquid_subset_audit",
            "signal_baseline_portfolio_rank_60m_score_weighted_topk_sweep",
            "signal_baseline_portfolio_rank_60m_score_weighted_topk_walkforward",
            "signal_baseline_portfolio_rank_60m_dispersion_gate_sweep",
            "signal_baseline_portfolio_rank_60m_dispersion_sizing_walkforward",
            "signal_baseline_cost_sensitivity",
            "signal_baseline_futures_cost_profile",
            "signal_diagnostic_bucket_quality",
            "refresh_branch_registry",
            "refresh_setup_library_scoreboard",
            "experiment_suite",
            "walk_forward",
            "walk_forward_focus",
            "walk_forward_focus_adjacent",
            "walk_forward_focus_timeseries",
            "tune_overlay",
            "select_overlay_candidate",
            "full_training",
        ],
        default=resolve_run_mode(),
        help="Execution mode. Defaults to SSELL1_RUN_MODE or walk_forward.",
    )
    args = parser.parse_args()
    run_mode = args.mode
    main_logger.info(f"Resolved execution mode: {run_mode}")
    main_logger.info("Starting pipeline for multi‐ticker training (ITC, APOLLOTYRE) and single‐ticker testing (GRINDWELL).")

    # ----------------------------------------------------------------
    # 1. Function to read CSV from 'data/' and parse indicators
    # ----------------------------------------------------------------
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

    if run_mode == "signal_research_event_conditioned_sizing_veto":
        main_logger.info(
            "Starting EventConditionedSizingVeto research. "
            "Replaying incumbent E211 entries and testing whether pre-existing 15m event/context signals cleanly identify veto-worthy trades."
        )
        best_params = resolve_runtime_best_params(run_mode)
        research_tickers = NSE_LIQUID_UNIVERSE.copy()
        run_event_conditioned_sizing_veto_research(
            ticker_list=research_tickers,
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
            max_windows_per_ticker=1,
        )
        raise SystemExit(0)

    if run_mode.startswith("signal_research"):
        main_logger.info("Starting signal research workflow before any RL training.")
        experiment_set = "default"
        experiment_ids = None
        max_window_pairs = None
        ticker_list = NSE_LIQUID_UNIVERSE.copy()
        if run_mode == "signal_research_smoke":
            ticker_list = NSE_LIQUID_UNIVERSE[:3]
            experiment_set = "focused"
            experiment_ids = ["E101", "E105", "E102"]
            max_window_pairs = 3
        elif run_mode == "signal_research_generalization":
            experiment_set = "generalization"
        elif run_mode == "signal_research_generalization_next":
            experiment_set = "generalization_next"
        elif run_mode == "signal_research_generalization_wave2":
            experiment_set = "generalization_wave2"
        elif run_mode == "signal_research_e102_deepdive":
            experiment_set = "e102_deepdive"
        elif run_mode == "signal_research_cross_sectional_60m":
            experiment_set = "cross_sectional_60m"
        elif run_mode == "signal_research_ablation_grid":
            experiment_set = "ablation_grid"
        elif run_mode == "signal_research_setup_regimes":
            experiment_set = "setup_regimes"
        elif run_mode == "signal_research_market_state_60m":
            experiment_set = "market_state_60m"
        elif run_mode == "signal_research_multiscale_60m":
            experiment_set = "multiscale_60m"
        elif run_mode == "signal_research_second_timeframe_60m":
            experiment_set = "second_timeframe_60m"
        elif run_mode == "signal_research_intrahour_path_v1":
            experiment_set = "intrahour_path_v1"
        elif run_mode == "signal_research_breadth_context_60m":
            experiment_set = "breadth_context_60m"
        elif run_mode == "signal_research_time_distribution_v2":
            experiment_set = "time_distribution_v2"
        elif run_mode == "signal_research_native_15m_execution":
            experiment_set = "native_15m_execution"
        elif run_mode == "signal_research_native_15m_failed_breakout":
            experiment_set = "native_15m_failed_breakout"
        elif run_mode == "signal_research_native_15m_open_drive":
            experiment_set = "native_15m_open_drive"
        elif run_mode == "signal_research_opening_auction_gap_liquidity":
            experiment_set = "opening_auction_gap_liquidity"
        elif run_mode == "signal_research_native_15m_session_phase":
            experiment_set = "native_15m_session_phase"
        elif run_mode == "signal_research_native_15m_holding_horizon":
            experiment_set = "native_15m_holding_horizon"
        elif run_mode == "signal_research_native_15m_topk_event_rank":
            experiment_set = "native_15m_topk_event_rank"
        elif run_mode == "signal_research_native_15m_breadth_event":
            experiment_set = "native_15m_breadth_event"
        elif run_mode == "signal_research_native_15m_mean_reversion_exhaustion":
            experiment_set = "native_15m_mean_reversion_exhaustion"
        elif run_mode == "signal_research_sixty_minute_daily_context":
            experiment_set = "sixty_minute_daily_context"
        elif run_mode == "signal_research_cross_sectional_commonality_residual":
            experiment_set = "cross_sectional_commonality_residual"
        elif run_mode == "signal_research_intraday_volume_liquidity_forecast":
            experiment_set = "intraday_volume_liquidity_forecast"
        elif run_mode == "signal_research_event_outcome_accounting":
            experiment_set = "event_outcome_accounting"
        elif run_mode == "signal_research_event_outcome_accounting_refined":
            experiment_set = "event_outcome_accounting"
            experiment_ids = ["E2806", "E2805"]
        elif run_mode == "signal_research_all_15m":
            experiment_set = "all_15m"
        elif run_mode == "signal_research_portfolio_rank_60m":
            experiment_set = "portfolio_rank_60m"
        elif run_mode == "signal_research_e302":
            experiment_set = "e302_sweep"
        elif run_mode == "signal_research_two_track":
            experiment_set = "two_track"
        run_signal_research_workflow(
            ticker_list=ticker_list,
            instrument_df=instrument_df,
            interval="15minute" if run_mode in {"signal_research_native_15m_execution", "signal_research_native_15m_failed_breakout", "signal_research_native_15m_open_drive", "signal_research_opening_auction_gap_liquidity", "signal_research_native_15m_session_phase", "signal_research_native_15m_holding_horizon", "signal_research_native_15m_topk_event_rank", "signal_research_native_15m_breadth_event", "signal_research_native_15m_mean_reversion_exhaustion", "signal_research_event_outcome_accounting", "signal_research_event_outcome_accounting_refined", "signal_research_all_15m"} else TICKINT,
            history_days=365 if run_mode in {"signal_research_native_15m_execution", "signal_research_native_15m_failed_breakout", "signal_research_native_15m_open_drive", "signal_research_opening_auction_gap_liquidity", "signal_research_native_15m_session_phase", "signal_research_native_15m_holding_horizon", "signal_research_native_15m_topk_event_rank", "signal_research_native_15m_breadth_event", "signal_research_native_15m_mean_reversion_exhaustion", "signal_research_event_outcome_accounting", "signal_research_event_outcome_accounting_refined", "signal_research_all_15m"} else max(TRAIN_HISTORY_DAYS, 1095),
            window_days=10 if run_mode in {"signal_research_native_15m_execution", "signal_research_native_15m_failed_breakout", "signal_research_native_15m_open_drive", "signal_research_opening_auction_gap_liquidity", "signal_research_native_15m_session_phase", "signal_research_native_15m_holding_horizon", "signal_research_native_15m_topk_event_rank", "signal_research_native_15m_breadth_event", "signal_research_native_15m_mean_reversion_exhaustion", "signal_research_event_outcome_accounting", "signal_research_event_outcome_accounting_refined", "signal_research_all_15m"} else 20,
            experiment_ids=experiment_ids,
            experiment_set=experiment_set,
            max_window_pairs=(
                max_window_pairs
                if run_mode != "signal_research_all_15m"
                else (6 if max_window_pairs is None else min(max_window_pairs, 6))
            ),
        )
        raise SystemExit(0)

    if run_mode == "refresh_branch_registry":
        main_logger.info("Refreshing master experiment branch registry and branch decision scoreboard.")
        refresh_experiment_branch_registry()
        raise SystemExit(0)

    if run_mode == "refresh_setup_library_scoreboard":
        main_logger.info("Refreshing setup-library scoreboard from current research and baseline artifacts.")
        build_setup_library_scoreboard()
        raise SystemExit(0)

    if run_mode == "tune_overlay":
        storage = optuna.storages.RDBStorage(
            url='sqlite:///optuna_study.db',
            engine_kwargs={'connect_args': {'check_same_thread': False}}
        )
        unique_study_name = generate_unique_study_name(base_name="rl_overlay_multiobjective")
        study = optuna.create_study(
            directions=["maximize", "minimize", "minimize"],
            sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
            storage=storage,
            study_name=unique_study_name,
            load_if_exists=False
        )
        n_trials = 10
        main_logger.info(
            "[OPTUNA-MO] Starting gated overlay multi-objective study for %s trials. "
            "Objectives: maximize return, minimize drawdown, minimize turnover.",
            n_trials,
        )
        study.optimize(
            lambda trial: objective_multi_objective(
                trial,
                train_tickers=optuna_tickers,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
            ),
            n_trials=n_trials,
            n_jobs=1
        )
        selected_params = export_and_select_pareto_trials(study)
        if not selected_params:
            main_logger.critical("[OPTUNA-MO] No completed Pareto trials were available.")
            raise SystemExit(1)
        save_best_params(selected_params)
        main_logger.info(
            "[OPTUNA-MO] Saved selected compromise params to %s. Pareto files: %s, %s, %s",
            BEST_PARAMS_FILE,
            PARETO_ALL_TRIALS_FILE,
            PARETO_TRIALS_FILE,
            PARETO_SELECTED_FILE,
        )
        print(f"[OPTUNA-MO] saved selected params to {BEST_PARAMS_FILE}")
        print(f"[OPTUNA-MO] all trials: {PARETO_ALL_TRIALS_FILE}")
        print(f"[OPTUNA-MO] pareto frontier: {PARETO_TRIALS_FILE}")
        print(f"[OPTUNA-MO] selected trial: {PARETO_SELECTED_FILE}")
        raise SystemExit(0)

    if run_mode == "select_overlay_candidate":
        params = select_active_overlay_candidate(min_avg_trades=5.0)
        if not params:
            main_logger.critical("[OPTUNA-MO] Could not select an active overlay candidate.")
            raise SystemExit(1)
        save_best_params(params)
        main_logger.info(
            "[OPTUNA-MO] Saved active overlay candidate to %s using %s",
            BEST_PARAMS_FILE,
            PARETO_SELECTED_ACTIVE_FILE,
        )
        print(f"[OPTUNA-MO] saved active overlay candidate to {BEST_PARAMS_FILE}")
        print(f"[OPTUNA-MO] selected active trial: {PARETO_SELECTED_ACTIVE_FILE}")
        raise SystemExit(0)

    if run_mode == "signal_diagnostic_bucket_quality":
        main_logger.info(
            "Starting bucket-quality diagnostic for E211 and E801. "
            "This is a research-only signal-quality check, not a new trading branch."
        )
        run_signal_bucket_quality_diagnostic()
        raise SystemExit(0)

    if run_mode in {"signal_baseline", "signal_baseline_e302", "signal_baseline_generalization_next", "signal_baseline_e102_deepdive", "signal_baseline_cross_sectional_60m", "signal_baseline_cross_sectional_commonality_residual", "signal_baseline_intraday_volume_liquidity_forecast", "signal_baseline_event_outcome_accounting", "signal_baseline_event_outcome_accounting_refined", "signal_baseline_ablation_grid", "signal_baseline_setup_regimes", "signal_baseline_market_state_60m", "signal_baseline_multiscale_60m", "signal_baseline_second_timeframe_60m", "signal_baseline_intrahour_path_v1", "signal_baseline_breadth_context_60m", "signal_baseline_time_distribution_v2", "signal_baseline_time_distribution_v2_top", "signal_baseline_native_15m_execution", "signal_baseline_native_15m_execution_validate", "signal_baseline_native_15m_execution_top_compare", "signal_baseline_native_15m_failed_breakout", "signal_baseline_native_15m_open_drive", "signal_baseline_opening_auction_gap_liquidity", "signal_baseline_native_15m_session_phase", "signal_baseline_native_15m_holding_horizon", "signal_baseline_native_15m_holding_horizon_execution_sweep", "signal_baseline_native_15m_breadth_event", "signal_baseline_native_15m_topk_event_rank", "signal_baseline_native_15m_mean_reversion_exhaustion", "signal_baseline_native_15m_mean_reversion_exhaustion_compare", "signal_baseline_native_15m_mean_reversion_exhaustion_validate", "signal_baseline_sixty_minute_daily_context", "signal_baseline_event_conditioned_sizing_veto", "signal_baseline_all_15m_top2", "signal_baseline_e211_intrahour_veto", "signal_baseline_e211_entry_audit", "signal_baseline_portfolio_rank_60m", "signal_baseline_portfolio_rank_60m_long_only", "signal_baseline_portfolio_rank_60m_long_only_sweep", "signal_baseline_portfolio_rank_60m_long_only_cadence_sweep", "signal_baseline_portfolio_rank_60m_long_only_walkforward", "signal_baseline_portfolio_rank_60m_long_only_hold_sweep", "signal_baseline_portfolio_rank_60m_long_only_hold_walkforward", "signal_baseline_portfolio_rank_60m_long_only_topk_sweep", "signal_baseline_portfolio_rank_60m_regime_gate_sweep", "signal_baseline_portfolio_rank_60m_score_weighted_sizing", "signal_baseline_portfolio_rank_60m_liquid_subset_audit", "signal_baseline_portfolio_rank_60m_score_weighted_topk_sweep", "signal_baseline_portfolio_rank_60m_score_weighted_topk_walkforward", "signal_baseline_portfolio_rank_60m_dispersion_gate_sweep", "signal_baseline_portfolio_rank_60m_dispersion_sizing_walkforward", "signal_baseline_cost_sensitivity", "signal_baseline_futures_cost_profile", "walk_forward", "walk_forward_focus", "walk_forward_focus_adjacent", "walk_forward_focus_timeseries", "experiment_suite"}:
        best_params = resolve_runtime_best_params(run_mode)
        optuna_tuned_inference_buy_threshold = best_params.get("inference_buy_threshold", 0.08)
        optuna_tuned_inference_sell_threshold = best_params.get("inference_sell_threshold", 0.08)

        if run_mode == "signal_baseline_event_conditioned_sizing_veto":
            promoted_event_overlay_ids = load_event_conditioned_sizing_veto_promoted_ids()
            promoted_policy_names = [
                str(EVENT_CONDITIONED_SIZING_VETO_CANDIDATES[candidate_id]["policy_name"])
                for candidate_id in promoted_event_overlay_ids
                if candidate_id in EVENT_CONDITIONED_SIZING_VETO_CANDIDATES
            ]
            if not promoted_policy_names:
                promoted_policy_names = [
                    str(EVENT_CONDITIONED_SIZING_VETO_CANDIDATES["E2401"]["policy_name"]),
                    str(EVENT_CONDITIONED_SIZING_VETO_CANDIDATES["E2403"]["policy_name"]),
                ]
            main_logger.info(
                "Starting EventConditionedSizingVeto baseline evaluation. "
                "Testing whether pre-qualified overlay veto rules improve the incumbent benchmark without collapsing breadth. "
                f"Evaluating policies: {', '.join(promoted_policy_names)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=["FLAT", "SIGNAL_E211_BANDED_68", *promoted_policy_names],
            )
            event_policy_csv = RESULTS_DIR / "signal_baseline" / "event_conditioned_sizing_veto_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    event_df = pd.read_csv(policy_csv)
                    event_df = event_df.loc[
                        event_df["policy"].isin(["FLAT", "SIGNAL_E211_BANDED_68", *promoted_policy_names])
                    ].copy()
                    event_df.to_csv(event_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] Event-conditioned sizing-veto summary saved: {event_policy_csv}")
                    print(f"[BASELINE] Event-conditioned sizing-veto summary saved: {event_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save event-conditioned sizing-veto summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline":
            main_logger.info("Starting signal-only baseline walk-forward evaluation.")
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_cost_sensitivity":
            main_logger.info(
                "Starting cost-sensitivity audit for the incumbent and strongest challengers. "
                "Comparing realistic costs, half slippage, fees-only, and frictionless settings."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_cost_sensitivity_audit(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_futures_cost_profile":
            main_logger.info(
                "Starting futures cost-profile audit for the incumbent and strongest challengers. "
                "Comparing cash-equity and stock-futures cost stacks under matched slippage settings."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_futures_cost_profile_audit(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_e302":
            main_logger.info("Starting E302 standalone baseline evaluation. RL integration for E302 is intentionally disabled for this phase.")
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=[
                    "FLAT",
                    "SIGNAL_E302_LONGONLY",
                    "SIGNAL_E302_BANDED_64",
                    "SIGNAL_E302_BANDED_66",
                    "SIGNAL_E302_BANDED_68",
                    "SIGNAL_E302_BANDED_70",
                ],
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_generalization_next":
            main_logger.info(
                "Starting generalization-next shortlist baseline evaluation. "
                "Evaluating E401 and E407 as standalone baseline branches only."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=[
                    "FLAT",
                    "SIGNAL_E401_LONGONLY",
                    "SIGNAL_E401_BANDED_64",
                    "SIGNAL_E401_BANDED_66",
                    "SIGNAL_E401_BANDED_68",
                    "SIGNAL_E401_BANDED_70",
                    "SIGNAL_E407_LONGONLY",
                    "SIGNAL_E407_BANDED_64",
                    "SIGNAL_E407_BANDED_66",
                    "SIGNAL_E407_BANDED_68",
                    "SIGNAL_E407_BANDED_70",
                ],
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_e102_deepdive":
            main_logger.info(
                "Starting E102 deep-dive baseline evaluation. "
                "Comparing bull-regime E209/E211 against the plain E102 baseline family."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=[
                    "FLAT",
                    "SIGNAL_E102_BANDED_70",
                    "SIGNAL_E102_BANDED_72",
                    "SIGNAL_E209_LONGONLY",
                    "SIGNAL_E209_BANDED_64",
                    "SIGNAL_E209_BANDED_66",
                    "SIGNAL_E209_BANDED_68",
                    "SIGNAL_E209_BANDED_70",
                    "SIGNAL_E211_LONGONLY",
                    "SIGNAL_E211_BANDED_64",
                    "SIGNAL_E211_BANDED_66",
                    "SIGNAL_E211_BANDED_68",
                    "SIGNAL_E211_BANDED_70",
                ],
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_cross_sectional_60m":
            promoted_cross_ids = load_cross_sectional_promoted_ids()
            if not promoted_cross_ids:
                promoted_cross_ids = [f"E50{i}" for i in range(1, 9)]
            cross_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_cross_ids:
                cross_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting cross-sectional 60m baseline evaluation. "
                "E211 remains benchmark-only; RL stays out of scope until a new baseline clearly beats SIGNAL_E211_BANDED_68. "
                f"Evaluating promoted shortlist: {', '.join(promoted_cross_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=cross_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_ablation_grid":
            promoted_ablation_ids = load_ablation_grid_promoted_ids()
            if not promoted_ablation_ids:
                promoted_ablation_ids = ["E605", "E606", "E607", "E610"]
            ablation_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_ablation_ids:
                ablation_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting ablation-grid baseline evaluation. "
                "Testing promoted ablation survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_ablation_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=ablation_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_setup_regimes":
            promoted_setup_ids = load_setup_regime_promoted_ids()
            if not promoted_setup_ids:
                promoted_setup_ids = ["E702", "E703", "E705", "E706"]
            setup_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_setup_ids:
                setup_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting setup-regime baseline evaluation. "
                "Testing promoted setup-regime survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_setup_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=setup_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_market_state_60m":
            promoted_market_state_ids = load_market_state_promoted_ids()
            if not promoted_market_state_ids:
                promoted_market_state_ids = ["E801", "E803", "E804", "E806"]
            market_state_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_market_state_ids:
                market_state_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting market-state 60m baseline evaluation. "
                "Testing promoted market-state survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_market_state_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=market_state_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_multiscale_60m":
            promoted_multiscale_ids = load_multiscale_promoted_ids()
            if not promoted_multiscale_ids:
                promoted_multiscale_ids = ["E903", "E904", "E905", "E906"]
            multiscale_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_multiscale_ids:
                multiscale_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting multi-scale 60m baseline evaluation. "
                "Testing promoted multi-scale survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_multiscale_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=multiscale_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_second_timeframe_60m":
            promoted_second_tf_ids = load_second_timeframe_promoted_ids()
            if not promoted_second_tf_ids:
                promoted_second_tf_ids = ["E1101", "E1102", "E1103", "E1104", "E1105", "E1106"]
            second_tf_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_second_tf_ids:
                second_tf_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting second-timeframe 60m baseline evaluation. "
                "Testing promoted 15m-context survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_second_tf_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=second_tf_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_intrahour_path_v1":
            promoted_intrahour_ids = load_intrahour_path_v1_promoted_ids()
            if not promoted_intrahour_ids:
                promoted_intrahour_ids = ["E1201", "E1202", "E1203", "E1204"]
            intrahour_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_intrahour_ids:
                intrahour_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting intrahour-path v1 baseline evaluation. "
                "Testing promoted intrahour path survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_intrahour_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=intrahour_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_breadth_context_60m":
            promoted_breadth_ids = load_breadth_context_promoted_ids()
            if not promoted_breadth_ids:
                promoted_breadth_ids = ["E1301", "E1302", "E1303", "E1304"]
            breadth_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_breadth_ids:
                breadth_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting breadth-context 60m baseline evaluation. "
                "Testing promoted breadth-context survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_breadth_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=breadth_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_time_distribution_v2":
            promoted_time_distribution_ids = load_time_distribution_v2_promoted_ids()
            if not promoted_time_distribution_ids:
                promoted_time_distribution_ids = ["E1401", "E1402", "E1403", "E1404"]
            time_distribution_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_time_distribution_ids:
                time_distribution_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting time-distribution v2 baseline evaluation. "
                "Testing promoted time-distribution survivors against SIGNAL_E211_BANDED_68 only. "
                f"Evaluating shortlist: {', '.join(promoted_time_distribution_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=time_distribution_policy_filter,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_execution":
            promoted_native_15m_ids = load_native_15m_execution_promoted_ids()
            if not promoted_native_15m_ids:
                promoted_native_15m_ids = ["E1501", "E1502"]
            promoted_native_15m_ids = [exp_id for exp_id in promoted_native_15m_ids if exp_id in {"E1501", "E1502"}]
            if not promoted_native_15m_ids:
                promoted_native_15m_ids = ["E1501", "E1502"]
            native_15m_policy_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_ids:
                native_15m_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m baseline evaluation. "
                "Testing promoted direct-15m survivors with true 15m decision timing against FLAT. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=max(TRAIN_HISTORY_DAYS, 365),
                train_days=365,
                val_days=45,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=1,
                policy_filter=native_15m_policy_filter,
            )
            native_15m_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_execution_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    native_df = pd.read_csv(policy_csv)
                    native_df = native_df.loc[
                        native_df["policy"].isin(native_15m_policy_filter)
                    ].copy()
                    native_df.to_csv(native_15m_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m policy summary saved: {native_15m_policy_csv}")
                    print(f"[BASELINE] native 15m policy summary saved: {native_15m_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_execution_validate":
            native_15m_policy_filter = ["FLAT", "SIGNAL_E1502_BANDED_66", "SIGNAL_E1502_BANDED_64"]
            main_logger.info(
                "Starting native 15m validation baseline. "
                "Re-testing the sparse native-15m survivor over broader walk-forward coverage to check whether E1502 generalizes beyond one ticker/window."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_policy_filter,
            )
            validate_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_execution_validate_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    validate_df = pd.read_csv(policy_csv)
                    validate_df = validate_df.loc[
                        validate_df["policy"].isin(native_15m_policy_filter)
                    ].copy()
                    validate_df.to_csv(validate_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m validation summary saved: {validate_policy_csv}")
                    print(f"[BASELINE] native 15m validation summary saved: {validate_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m validation summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_execution_top_compare":
            native_15m_policy_filter = [
                "FLAT",
                "SIGNAL_E211_BANDED_68",
                "SIGNAL_E211_BANDED_66",
                "SIGNAL_E1501_BANDED_70",
                "SIGNAL_E1501_BANDED_68",
                "SIGNAL_E1501_BANDED_66",
            ]
            main_logger.info(
                "Starting native 15m top comparison baseline. "
                "Comparing native-15m E1501 against native-15m E211 under the same broader validation frame."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_policy_filter,
            )
            compare_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_execution_top_compare_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    compare_df = pd.read_csv(policy_csv)
                    compare_df = compare_df.loc[
                        compare_df["policy"].isin(native_15m_policy_filter)
                    ].copy()
                    compare_df.to_csv(compare_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m top comparison summary saved: {compare_policy_csv}")
                    print(f"[BASELINE] native 15m top comparison summary saved: {compare_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m top comparison summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_failed_breakout":
            promoted_native_15m_failed_breakout_ids = load_native_15m_failed_breakout_promoted_ids()
            if not promoted_native_15m_failed_breakout_ids:
                promoted_native_15m_failed_breakout_ids = ["E1601", "E1602", "E1603", "E1604"]
            native_15m_failed_breakout_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_failed_breakout_ids:
                native_15m_failed_breakout_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m failed-breakout baseline evaluation. "
                "Testing promoted event-driven rejection and breakout-failure survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_failed_breakout_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_failed_breakout_filter,
            )
            failed_breakout_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_failed_breakout_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    failed_breakout_df = pd.read_csv(policy_csv)
                    failed_breakout_df = failed_breakout_df.loc[
                        failed_breakout_df["policy"].isin(native_15m_failed_breakout_filter)
                    ].copy()
                    failed_breakout_df.to_csv(failed_breakout_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m failed-breakout summary saved: {failed_breakout_policy_csv}")
                    print(f"[BASELINE] native 15m failed-breakout summary saved: {failed_breakout_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m failed-breakout summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_open_drive":
            promoted_native_15m_open_drive_ids = load_native_15m_open_drive_promoted_ids()
            if not promoted_native_15m_open_drive_ids:
                promoted_native_15m_open_drive_ids = ["E1701", "E1702", "E1703", "E1704"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_open_drive_ids,
                "native-15m open-drive baseline",
            )
            native_15m_open_drive_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_open_drive_ids:
                native_15m_open_drive_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m open-drive baseline evaluation. "
                "Testing promoted opening-range and open-drive event survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_open_drive_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_open_drive_filter,
            )
            open_drive_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_open_drive_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    open_drive_df = pd.read_csv(policy_csv)
                    open_drive_df = open_drive_df.loc[
                        open_drive_df["policy"].isin(native_15m_open_drive_filter)
                    ].copy()
                    open_drive_df.to_csv(open_drive_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m open-drive summary saved: {open_drive_policy_csv}")
                    print(f"[BASELINE] native 15m open-drive summary saved: {open_drive_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m open-drive summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_opening_auction_gap_liquidity":
            promoted_opening_gap_ids = load_opening_auction_gap_liquidity_promoted_ids()
            if not promoted_opening_gap_ids:
                promoted_opening_gap_ids = ["E2701", "E2702", "E2703", "E2704"]
            ensure_signal_overlay_predictions_available(
                promoted_opening_gap_ids,
                "opening auction gap-liquidity baseline",
            )
            opening_gap_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_opening_gap_ids:
                opening_gap_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting opening auction gap-liquidity baseline evaluation. "
                "Testing promoted early-gap event survivors against FLAT and SIGNAL_E211_BANDED_68 on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_opening_gap_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=opening_gap_filter,
            )
            opening_gap_policy_csv = RESULTS_DIR / "signal_baseline" / "opening_auction_gap_liquidity_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    opening_gap_df = pd.read_csv(policy_csv)
                    opening_gap_df = opening_gap_df.loc[
                        opening_gap_df["policy"].isin(opening_gap_filter)
                    ].copy()
                    opening_gap_df.to_csv(opening_gap_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] opening auction gap-liquidity summary saved: {opening_gap_policy_csv}")
                    print(f"[BASELINE] opening auction gap-liquidity summary saved: {opening_gap_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save opening auction gap-liquidity summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_session_phase":
            promoted_native_15m_session_phase_ids = load_native_15m_session_phase_promoted_ids()
            if not promoted_native_15m_session_phase_ids:
                promoted_native_15m_session_phase_ids = ["E1801", "E1802", "E1803", "E1804"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_session_phase_ids,
                "native-15m session-phase baseline",
            )
            native_15m_session_phase_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_session_phase_ids:
                native_15m_session_phase_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m session-phase baseline evaluation. "
                "Testing promoted early, mid, and late-session event survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_session_phase_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_session_phase_filter,
            )
            session_phase_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_session_phase_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    session_phase_df = pd.read_csv(policy_csv)
                    session_phase_df = session_phase_df.loc[
                        session_phase_df["policy"].isin(native_15m_session_phase_filter)
                    ].copy()
                    session_phase_df.to_csv(session_phase_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m session-phase summary saved: {session_phase_policy_csv}")
                    print(f"[BASELINE] native 15m session-phase summary saved: {session_phase_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m session-phase summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_holding_horizon":
            promoted_native_15m_holding_horizon_ids = load_native_15m_holding_horizon_promoted_ids()
            if not promoted_native_15m_holding_horizon_ids:
                promoted_native_15m_holding_horizon_ids = ["E1901", "E1902", "E1903", "E1904"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_holding_horizon_ids,
                "native-15m holding-horizon baseline",
            )
            native_15m_holding_horizon_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_holding_horizon_ids:
                native_15m_holding_horizon_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m holding-horizon baseline evaluation. "
                "Testing promoted horizon-specific event survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_holding_horizon_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_holding_horizon_filter,
            )
            holding_horizon_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_holding_horizon_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    holding_horizon_df = pd.read_csv(policy_csv)
                    holding_horizon_df = holding_horizon_df.loc[
                        holding_horizon_df["policy"].isin(native_15m_holding_horizon_filter)
                    ].copy()
                    holding_horizon_df.to_csv(holding_horizon_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m holding-horizon summary saved: {holding_horizon_policy_csv}")
                    print(f"[BASELINE] native 15m holding-horizon summary saved: {holding_horizon_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m holding-horizon summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_holding_horizon_execution_sweep":
            main_logger.info(
                "Starting native 15m holding-horizon execution sweep. "
                "Testing E1903 threshold tightening and execution hold extension variants against FLAT and SIGNAL_E211_BANDED_68 "
                "on the wider native-15m validation frame."
            )
            run_native_15m_holding_horizon_execution_sweep(
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_breadth_event":
            promoted_native_15m_breadth_event_ids = load_native_15m_breadth_event_promoted_ids()
            if not promoted_native_15m_breadth_event_ids:
                promoted_native_15m_breadth_event_ids = ["E2302", "E2304"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_breadth_event_ids,
                "native-15m breadth-event baseline",
            )
            native_15m_breadth_event_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_native_15m_breadth_event_ids:
                native_15m_breadth_event_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m breadth-event baseline evaluation. "
                "Testing only the strongest breadth-event survivors against FLAT and SIGNAL_E211_BANDED_68 on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_breadth_event_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_breadth_event_filter,
            )
            breadth_event_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_breadth_event_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    breadth_event_df = pd.read_csv(policy_csv)
                    breadth_event_df = breadth_event_df.loc[
                        breadth_event_df["policy"].isin(native_15m_breadth_event_filter)
                    ].copy()
                    breadth_event_df.to_csv(breadth_event_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m breadth-event summary saved: {breadth_event_policy_csv}")
                    print(f"[BASELINE] native 15m breadth-event summary saved: {breadth_event_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m breadth-event summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_topk_event_rank":
            promoted_native_15m_topk_event_rank_ids = load_native_15m_topk_event_rank_promoted_ids()
            if not promoted_native_15m_topk_event_rank_ids:
                promoted_native_15m_topk_event_rank_ids = ["E2001", "E2002", "E2003", "E2004"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_topk_event_rank_ids,
                "native-15m top-k event-rank baseline",
            )
            native_15m_topk_event_rank_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_topk_event_rank_ids:
                native_15m_topk_event_rank_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m top-k event-rank baseline evaluation. "
                "Testing promoted favorable-slice ranking survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_topk_event_rank_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_topk_event_rank_filter,
            )
            topk_event_rank_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_topk_event_rank_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    topk_event_rank_df = pd.read_csv(policy_csv)
                    topk_event_rank_df = topk_event_rank_df.loc[
                        topk_event_rank_df["policy"].isin(native_15m_topk_event_rank_filter)
                    ].copy()
                    topk_event_rank_df.to_csv(topk_event_rank_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m top-k event-rank summary saved: {topk_event_rank_policy_csv}")
                    print(f"[BASELINE] native 15m top-k event-rank summary saved: {topk_event_rank_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m top-k event-rank summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_mean_reversion_exhaustion":
            promoted_native_15m_mean_reversion_exhaustion_ids = load_native_15m_mean_reversion_exhaustion_promoted_ids()
            if not promoted_native_15m_mean_reversion_exhaustion_ids:
                promoted_native_15m_mean_reversion_exhaustion_ids = ["E2101", "E2102", "E2103", "E2104"]
            ensure_signal_overlay_predictions_available(
                promoted_native_15m_mean_reversion_exhaustion_ids,
                "native-15m mean-reversion exhaustion baseline",
            )
            native_15m_mean_reversion_exhaustion_filter = ["FLAT"]
            for experiment_id in promoted_native_15m_mean_reversion_exhaustion_ids:
                native_15m_mean_reversion_exhaustion_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m mean-reversion exhaustion baseline evaluation. "
                "Testing promoted exhaustion and rejection snapback survivors against FLAT on the wider native-15m validation frame. "
                f"Evaluating shortlist: {', '.join(promoted_native_15m_mean_reversion_exhaustion_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_mean_reversion_exhaustion_filter,
            )
            mean_reversion_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_mean_reversion_exhaustion_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    mean_reversion_df = pd.read_csv(policy_csv)
                    mean_reversion_df = mean_reversion_df.loc[
                        mean_reversion_df["policy"].isin(native_15m_mean_reversion_exhaustion_filter)
                    ].copy()
                    mean_reversion_df.to_csv(mean_reversion_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m mean-reversion exhaustion summary saved: {mean_reversion_policy_csv}")
                    print(f"[BASELINE] native 15m mean-reversion exhaustion summary saved: {mean_reversion_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m mean-reversion exhaustion summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_mean_reversion_exhaustion_compare":
            ensure_signal_overlay_predictions_available(
                ["E2104"],
                "native-15m mean-reversion exhaustion comparison baseline",
            )
            native_15m_mean_reversion_compare_filter = [
                "FLAT",
                "SIGNAL_E2104_LONGONLY",
                "SIGNAL_E211_BANDED_68",
            ]
            main_logger.info(
                "Starting native 15m mean-reversion exhaustion comparison baseline. "
                "Comparing SIGNAL_E2104_LONGONLY directly against SIGNAL_E211_BANDED_68 and FLAT on the same broader native-15m validation frame."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_mean_reversion_compare_filter,
            )
            mean_reversion_compare_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_mean_reversion_exhaustion_compare_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    mean_reversion_compare_df = pd.read_csv(policy_csv)
                    mean_reversion_compare_df = mean_reversion_compare_df.loc[
                        mean_reversion_compare_df["policy"].isin(native_15m_mean_reversion_compare_filter)
                    ].copy()
                    mean_reversion_compare_df.to_csv(mean_reversion_compare_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m mean-reversion comparison summary saved: {mean_reversion_compare_policy_csv}")
                    print(f"[BASELINE] native 15m mean-reversion comparison summary saved: {mean_reversion_compare_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m mean-reversion comparison summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_native_15m_mean_reversion_exhaustion_validate":
            ensure_signal_overlay_predictions_available(
                ["E2104"],
                "native-15m mean-reversion exhaustion wider validation baseline",
            )
            native_15m_mean_reversion_validate_filter = [
                "FLAT",
                "SIGNAL_E2104_LONGONLY",
                "SIGNAL_E211_BANDED_68",
            ]
            main_logger.info(
                "Starting native 15m mean-reversion exhaustion wider validation baseline. "
                "Re-testing SIGNAL_E2104_LONGONLY against SIGNAL_E211_BANDED_68 and FLAT with wider walk-forward coverage."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=720,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=6,
                policy_filter=native_15m_mean_reversion_validate_filter,
            )
            mean_reversion_validate_policy_csv = RESULTS_DIR / "signal_baseline" / "native_15m_mean_reversion_exhaustion_validate_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    mean_reversion_validate_df = pd.read_csv(policy_csv)
                    mean_reversion_validate_df = mean_reversion_validate_df.loc[
                        mean_reversion_validate_df["policy"].isin(native_15m_mean_reversion_validate_filter)
                    ].copy()
                    mean_reversion_validate_df.to_csv(mean_reversion_validate_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m mean-reversion wider validation summary saved: {mean_reversion_validate_policy_csv}")
                    print(f"[BASELINE] native 15m mean-reversion wider validation summary saved: {mean_reversion_validate_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m mean-reversion wider validation summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_sixty_minute_daily_context":
            promoted_sixty_minute_daily_context_ids = load_sixty_minute_daily_context_promoted_ids()
            if not promoted_sixty_minute_daily_context_ids:
                promoted_sixty_minute_daily_context_ids = ["E2201", "E2202", "E2203", "E2204"]
            ensure_signal_overlay_predictions_available(
                promoted_sixty_minute_daily_context_ids,
                "60m daily-context baseline",
            )
            sixty_minute_daily_context_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_sixty_minute_daily_context_ids:
                sixty_minute_daily_context_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting 60m daily-context baseline evaluation. "
                "Testing promoted 60m plus daily-context survivors against SIGNAL_E211_BANDED_68. "
                f"Evaluating shortlist: {', '.join(promoted_sixty_minute_daily_context_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=sixty_minute_daily_context_filter,
            )
            daily_context_policy_csv = RESULTS_DIR / "signal_baseline" / "sixty_minute_daily_context_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    daily_context_df = pd.read_csv(policy_csv)
                    daily_context_df = daily_context_df.loc[
                        daily_context_df["policy"].isin(sixty_minute_daily_context_filter)
                    ].copy()
                    daily_context_df.to_csv(daily_context_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] 60m daily-context summary saved: {daily_context_policy_csv}")
                    print(f"[BASELINE] 60m daily-context summary saved: {daily_context_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save 60m daily-context summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_cross_sectional_commonality_residual":
            promoted_residual_ids = load_cross_sectional_commonality_residual_promoted_ids()
            if not promoted_residual_ids:
                promoted_residual_ids = ["E2501", "E2502", "E2503", "E2504"]
            ensure_signal_overlay_predictions_available(
                promoted_residual_ids,
                "cross-sectional commonality-residual baseline",
            )
            residual_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_residual_ids:
                residual_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting CrossSectionalCommonalityResidual baseline evaluation. "
                "Testing residual market/sector-adjusted 60m survivors against SIGNAL_E211_BANDED_68. "
                f"Evaluating shortlist: {', '.join(promoted_residual_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=residual_policy_filter,
            )
            residual_policy_csv = RESULTS_DIR / "signal_baseline" / "cross_sectional_commonality_residual_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    residual_df = pd.read_csv(policy_csv)
                    residual_df = residual_df.loc[
                        residual_df["policy"].isin(residual_policy_filter)
                    ].copy()
                    residual_df.to_csv(residual_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] cross-sectional commonality-residual summary saved: {residual_policy_csv}")
                    print(f"[BASELINE] cross-sectional commonality-residual summary saved: {residual_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save cross-sectional commonality-residual summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_intraday_volume_liquidity_forecast":
            promoted_volume_liquidity_ids = load_intraday_volume_liquidity_forecast_promoted_ids()
            if not promoted_volume_liquidity_ids:
                promoted_volume_liquidity_ids = ["E2601", "E2602", "E2603", "E2604"]
            ensure_signal_overlay_predictions_available(
                promoted_volume_liquidity_ids,
                "intraday volume-liquidity forecast baseline",
            )
            volume_liquidity_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_volume_liquidity_ids:
                volume_liquidity_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting IntradayVolumeLiquidityForecast baseline evaluation. "
                "Testing 60m survivors conditioned on 15m participation and liquidity state against SIGNAL_E211_BANDED_68. "
                f"Evaluating shortlist: {', '.join(promoted_volume_liquidity_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=volume_liquidity_filter,
            )
            volume_liquidity_policy_csv = RESULTS_DIR / "signal_baseline" / "intraday_volume_liquidity_forecast_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    volume_liquidity_df = pd.read_csv(policy_csv)
                    volume_liquidity_df = volume_liquidity_df.loc[
                        volume_liquidity_df["policy"].isin(volume_liquidity_filter)
                    ].copy()
                    volume_liquidity_df.to_csv(volume_liquidity_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] intraday volume-liquidity summary saved: {volume_liquidity_policy_csv}")
                    print(f"[BASELINE] intraday volume-liquidity summary saved: {volume_liquidity_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save intraday volume-liquidity summary: {exc}")
            raise SystemExit(0)

        if run_mode in {"signal_baseline_event_outcome_accounting", "signal_baseline_event_outcome_accounting_refined"}:
            promoted_event_outcome_ids = load_event_outcome_accounting_promoted_ids()
            if not promoted_event_outcome_ids:
                promoted_event_outcome_ids = (
                    ["E2806", "E2805"]
                    if run_mode == "signal_baseline_event_outcome_accounting_refined"
                    else ["E2801", "E2802", "E2803", "E2804", "E2805", "E2806"]
                )
            ensure_signal_overlay_predictions_available(
                promoted_event_outcome_ids,
                "event-outcome accounting baseline",
            )
            event_outcome_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_event_outcome_ids:
                event_outcome_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting EventOutcomeAccounting baseline evaluation. "
                "Testing path-aware 15m event survivors on target-before-stop economics against SIGNAL_E211_BANDED_68. "
                f"Evaluating shortlist: {', '.join(promoted_event_outcome_ids)}"
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=event_outcome_filter,
            )
            event_outcome_policy_csv = RESULTS_DIR / "signal_baseline" / "event_outcome_accounting_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    event_outcome_df = pd.read_csv(policy_csv)
                    event_outcome_df = event_outcome_df.loc[
                        event_outcome_df["policy"].isin(event_outcome_filter)
                    ].copy()
                    event_outcome_df.to_csv(event_outcome_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] event-outcome accounting summary saved: {event_outcome_policy_csv}")
                    print(f"[BASELINE] event-outcome accounting summary saved: {event_outcome_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save event-outcome accounting summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_all_15m_top2":
            top_15m_experiment_ids = ["E1301", "E102"]
            native_15m_policy_filter = ["FLAT"]
            for experiment_id in top_15m_experiment_ids:
                native_15m_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting native 15m shortlist baseline evaluation. "
                "Testing the strongest remaining broad-sweep survivors E1301 and E102 against FLAT on the wider native-15m validation frame."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
                instrument_df=instrument_df,
                best_params=best_params,
                initial_balance=INITIAL_BALANCE,
                stop_loss=STOP_LOSS,
                take_profit=TAKE_PROFIT,
                max_position_size=MAX_POSITION_SIZE,
                max_drawdown=MAX_DRAWDOWN,
                annual_trading_days=ANNUAL_TRADING_DAYS,
                interval="15minute",
                history_days=540,
                train_days=180,
                val_days=30,
                test_days=15,
                step_days=15,
                max_windows_per_ticker=3,
                policy_filter=native_15m_policy_filter,
            )
            shortlist_policy_csv = RESULTS_DIR / "signal_baseline" / "all_15m_top2_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    shortlist_df = pd.read_csv(policy_csv)
                    shortlist_df = shortlist_df.loc[
                        shortlist_df["policy"].isin(native_15m_policy_filter)
                    ].copy()
                    shortlist_df.to_csv(shortlist_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] native 15m shortlist summary saved: {shortlist_policy_csv}")
                    print(f"[BASELINE] native 15m shortlist summary saved: {shortlist_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save native 15m shortlist summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_time_distribution_v2_top":
            promoted_time_distribution_ids = ["E1401"]
            time_distribution_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68"]
            for experiment_id in promoted_time_distribution_ids:
                time_distribution_policy_filter.extend(build_signal_policy_family(experiment_id))
            main_logger.info(
                "Starting narrow time-distribution v2 baseline evaluation. "
                "Testing only the top candidate E1401 against SIGNAL_E211_BANDED_68 and FLAT."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=time_distribution_policy_filter,
            )
            top_policy_csv = RESULTS_DIR / "signal_baseline" / "time_distribution_v2_top_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "time_distribution_v2_policy_summary.csv"
                if policy_csv.exists():
                    top_df = pd.read_csv(policy_csv)
                    top_df = top_df.loc[
                        top_df["policy"].isin(["FLAT", "SIGNAL_E211_BANDED_68"] + build_signal_policy_family("E1401"))
                    ].copy()
                    top_df.to_csv(top_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] narrow time-distribution policy summary saved: {top_policy_csv}")
                    print(f"[BASELINE] narrow time-distribution policy summary saved: {top_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save narrow time-distribution summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_e211_intrahour_veto":
            veto_policy_filter = ["FLAT", "SIGNAL_E211_BANDED_68", "SIGNAL_E211_VETO_INTRAHOUR"]
            main_logger.info(
                "Starting E211 intrahour-veto baseline evaluation. "
                "Testing whether intrahour path and timing signals can improve the incumbent by vetoing weak E211 entries."
            )
            baseline_tickers = NSE_LIQUID_UNIVERSE.copy()
            run_signal_baseline_suite(
                ticker_list=baseline_tickers,
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
                max_windows_per_ticker=1,
                policy_filter=veto_policy_filter,
            )
            veto_policy_csv = RESULTS_DIR / "signal_baseline" / "e211_intrahour_veto_policy_summary.csv"
            try:
                policy_csv = RESULTS_DIR / "signal_baseline" / "baseline_policy_summary.csv"
                if policy_csv.exists():
                    veto_df = pd.read_csv(policy_csv)
                    veto_df = veto_df.loc[
                        veto_df["policy"].isin(veto_policy_filter)
                    ].copy()
                    veto_df.to_csv(veto_policy_csv, index=False)
                    main_logger.info(f"[BASELINE] E211 intrahour-veto summary saved: {veto_policy_csv}")
                    print(f"[BASELINE] E211 intrahour-veto summary saved: {veto_policy_csv}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to save E211 intrahour-veto summary: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_e211_entry_audit":
            main_logger.info(
                "Starting E211 entry-bar audit. "
                "Replaying SIGNAL_E211_BANDED_68 and extracting realized entry trades to compare winner vs loser intrahour features."
            )
            audit_tickers = NSE_LIQUID_UNIVERSE.copy()
            audit_outputs = run_e211_entry_audit(
                ticker_list=audit_tickers,
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
                max_windows_per_ticker=1,
            )
            try:
                main_logger.info(
                    "[BASELINE] E211 entry audit saved: summary=%s, detail_rows=%s, feature_rows=%s",
                    RESULTS_DIR / "signal_baseline" / "e211_entry_audit_summary.csv",
                    len(audit_outputs.get("detail", pd.DataFrame())),
                    len(audit_outputs.get("feature_separation", pd.DataFrame())),
                )
                print(f"[BASELINE] E211 entry audit summary saved: {RESULTS_DIR / 'signal_baseline' / 'e211_entry_audit_summary.csv'}")
                print(f"[BASELINE] E211 entry audit detail saved: {RESULTS_DIR / 'signal_baseline' / 'e211_entry_audit_detail.csv'}")
                print(f"[BASELINE] E211 feature separation saved: {RESULTS_DIR / 'signal_baseline' / 'e211_entry_feature_separation.csv'}")
            except Exception as exc:
                main_logger.warning(f"[BASELINE] failed to log E211 entry audit outputs: {exc}")
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1001", "E1002", "E1003", "E1004", "E1005", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m baseline evaluation. "
                "Testing promoted universe-ranking survivors against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_baseline(
                promoted_ids=promoted_portfolio_ids,
                top_k=3,
                benchmark_policy="SIGNAL_E211_BANDED_68",
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1002", "E1003", "E1005", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m long-only baseline evaluation. "
                "Testing low-turnover long-only rank wrappers against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_baseline(
                promoted_ids=promoted_portfolio_ids,
                top_k=5,
                benchmark_policy="SIGNAL_E211_BANDED_68",
                portfolio_style="long_only",
                rebalance_every_sessions=5,
                output_stem="portfolio_rank_60m_long_only",
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_sweep":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1002", "E1003", "E1005", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m long-only wrapper sweep. "
                "Testing top-k and rebalance-cadence variants against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_long_only_sweep(
                promoted_ids=promoted_portfolio_ids,
                benchmark_policy="SIGNAL_E211_BANDED_68",
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_cadence_sweep":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1002", "E1003", "E1005", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m long-only cadence sweep. "
                "Testing top-k 3/5 across rebalance cadence 5/4/3/2/1 sessions against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_long_only_cadence_sweep(
                promoted_ids=promoted_portfolio_ids,
                benchmark_policy="SIGNAL_E211_BANDED_68",
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_walkforward":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1002", "E1003", "E1005", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m long-only walk-forward validation. "
                "Testing the weekly top-k=3 wrapper across three contiguous folds against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_long_only_walkforward(
                promoted_ids=promoted_portfolio_ids,
                benchmark_policy="SIGNAL_E211_BANDED_68",
                top_k=3,
                rebalance_every_sessions=5,
                fold_count=3,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_hold_sweep":
            promoted_portfolio_ids = load_portfolio_rank_promoted_ids()
            if not promoted_portfolio_ids:
                promoted_portfolio_ids = ["E1002", "E1003", "E1005", "E1006"]
            promoted_portfolio_ids = [exp_id for exp_id in promoted_portfolio_ids if exp_id in {"E1002", "E1003", "E1006"}] or ["E1002", "E1003", "E1006"]
            main_logger.info(
                "Starting portfolio-rank 60m long-only hold sweep. "
                "Testing top-k=3 across rebalance cadence 5/7/10/15/21 sessions against SIGNAL_E211_BANDED_68 and FLAT only. "
                f"Evaluating shortlist: {', '.join(promoted_portfolio_ids)}"
            )
            run_portfolio_rank_long_only_hold_sweep(
                promoted_ids=promoted_portfolio_ids,
                benchmark_policy="SIGNAL_E211_BANDED_68",
                top_k=3,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_hold_walkforward":
            main_logger.info(
                "Starting portfolio-rank 60m long-only hold walk-forward validation. "
                "Testing targeted swing cells E1002@15, E1006@10, and E1003@21 across three contiguous folds against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_long_only_hold_walkforward(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                fold_count=3,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_long_only_topk_sweep":
            main_logger.info(
                "Starting portfolio-rank 60m long-only top-k sweep. "
                "Testing validated hold winner E1006 at every_10 sessions across top_k 2/3/4/5/7 against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_long_only_topk_sweep(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_regime_gate_sweep":
            main_logger.info(
                "Starting portfolio-rank 60m regime-gate sweep. "
                "Testing validated swing winner E1006 top2 every_10 with E801 mean-score veto thresholds against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_regime_gate_sweep(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                top_k=2,
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_score_weighted_sizing":
            main_logger.info(
                "Starting portfolio-rank 60m score-weighted sizing comparison. "
                "Testing E1006 top2 every_10 under equal-weight versus score-weighted allocation against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_score_weighted_sizing(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                top_k=2,
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_liquid_subset_audit":
            main_logger.info(
                "Starting portfolio-rank 60m liquid-subset audit. "
                "Testing E1006 top2 every_10 with score-weighted sizing on a top-liquidity subset against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_liquid_subset_audit(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                top_k=2,
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_score_weighted_topk_sweep":
            main_logger.info(
                "Starting portfolio-rank 60m score-weighted top-k sweep. "
                "Testing E1006 every_10 across top_k 2/3/4/5 under score-weighted allocation against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_score_weighted_topk_sweep(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_score_weighted_topk_walkforward":
            main_logger.info(
                "Starting portfolio-rank 60m score-weighted top-k walk-forward. "
                "Testing E1006 every_10 across top_k 2/3/4/5 under score-weighted allocation across 3 contiguous folds against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_score_weighted_topk_walkforward(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_dispersion_gate_sweep":
            main_logger.info(
                "Starting portfolio-rank 60m dispersion-gate sweep. "
                "Testing E1006 every_10 top_k=3 under score-weighted allocation with a self-contained prediction-spread gate against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_dispersion_gate_sweep(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                top_k=3,
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "signal_baseline_portfolio_rank_60m_dispersion_sizing_walkforward":
            main_logger.info(
                "Starting portfolio-rank 60m dispersion-sized walk-forward. "
                "Testing E1006 every_10 top_k=3 under score-weighted allocation with a continuous top1-minus-top5 dispersion sizing multiplier across 3 contiguous folds against SIGNAL_E211_BANDED_68 and FLAT only."
            )
            run_portfolio_rank_dispersion_sizing_walkforward(
                benchmark_policy="SIGNAL_E211_BANDED_68",
                experiment_id="E1006",
                top_k=3,
                rebalance_every_sessions=10,
            )
            raise SystemExit(0)

        if run_mode == "experiment_suite":
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

        main_logger.info("Starting walk-forward training/validation/testing pipeline.")
        if run_mode in {"walk_forward_focus", "walk_forward_focus_adjacent", "walk_forward_focus_timeseries"}:
            wf_tickers = build_focus_universe_from_latest_walk_forward(instrument_df=instrument_df)
            if not wf_tickers:
                main_logger.critical("[WF-FOCUS] No focus tickers were selected from the latest walk-forward block.")
                raise SystemExit(1)
            print(f"[WF-FOCUS] using {len(wf_tickers)} Zerodha NSE tickers: {', '.join(wf_tickers)}")
        else:
            wf_tickers = NSE_LIQUID_UNIVERSE.copy()
        wf_output_subdir = "walk_forward"
        wf_history_days = max(TRAIN_HISTORY_DAYS, 1095)
        wf_window_offset = 0
        wf_max_windows = 0
        wf_train_days = 730
        wf_val_days = 90
        wf_test_days = 30
        wf_step_days = 30
        wf_slice_mode = "rolling"
        wf_baseline_policy = "SIGNAL_E211_BANDED_68"
        wf_save_histories = False
        if run_mode == "walk_forward_focus_adjacent":
            wf_output_subdir = "walk_forward_adjacent"
            wf_history_days = max(TRAIN_HISTORY_DAYS, 1460)
            wf_window_offset = 1
            wf_max_windows = 1
            wf_train_days = 540
            wf_val_days = 60
            wf_test_days = 30
            wf_step_days = 30
            main_logger.info(
                "[WF-FOCUS-ADJ] running adjacent validation window with history_days=%s, "
                "train_days=%s, val_days=%s, test_days=%s, step_days=%s, window_offset=%s",
                wf_history_days,
                wf_train_days,
                wf_val_days,
                wf_test_days,
                wf_step_days,
                wf_window_offset,
            )
        elif run_mode == "walk_forward_focus_timeseries":
            wf_output_subdir = "walk_forward_timeseries_rolling"
            wf_history_days = max(TRAIN_HISTORY_DAYS, 1460)
            wf_window_offset = 0
            wf_max_windows = 4
            wf_train_days = 360
            wf_val_days = 60
            wf_test_days = 30
            wf_step_days = 30
            wf_slice_mode = "rolling"
            wf_save_histories = True
            main_logger.info(
                "[WF-FOCUS-TS] running rolling time-series validation with history_days=%s, "
                "train_days=%s, val_days=%s, test_days=%s, step_days=%s, max_windows=%s",
                wf_history_days,
                wf_train_days,
                wf_val_days,
                wf_test_days,
                wf_step_days,
                wf_max_windows,
            )
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
            history_days=wf_history_days,
            train_days=wf_train_days,
            val_days=wf_val_days,
            test_days=wf_test_days,
            step_days=wf_step_days,
            train_timesteps=50000,
            window_offset=wf_window_offset,
            max_windows_per_ticker=wf_max_windows,
            output_subdir=wf_output_subdir,
            slice_mode=wf_slice_mode,
            baseline_policy_name=wf_baseline_policy,
            save_eval_histories=wf_save_histories,
        )
        if run_mode == "walk_forward_focus_timeseries":
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
                history_days=wf_history_days,
                train_days=wf_train_days,
                val_days=wf_val_days,
                test_days=wf_test_days,
                step_days=wf_step_days,
                train_timesteps=50000,
                window_offset=0,
                max_windows_per_ticker=wf_max_windows,
                output_subdir="walk_forward_timeseries_expanding",
                slice_mode="expanding",
                baseline_policy_name=wf_baseline_policy,
                save_eval_histories=True,
            )
        raise SystemExit(0)

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
        save_best_params(best_params)
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
    if run_mode != "full_training":
        raise ValueError(f"Unsupported run mode: {run_mode}")

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
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0),
                'signal_gate_enabled': True,
                'signal_gate_entry_threshold': 0.68,
                'signal_gate_reduce_threshold': 0.60,
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
                'forced_tp_penalty_weight': best_params.get('forced_tp_penalty_weight', 1.0),
                'signal_gate_enabled': True,
                'signal_gate_entry_threshold': 0.68,
                'signal_gate_reduce_threshold': 0.60,
            },
            max_episode_steps=len(test_df),
            mode="test",
            inference_buy_threshold=optuna_tuned_inference_buy_threshold,
            inference_sell_threshold=optuna_tuned_inference_sell_threshold
        )

        from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

        # Create the vectorized test environment using env_test
        test_vec = DummyVecEnv([lambda: env_test])

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
        final_metrics = {}
        rl_test_history, final_metrics = _extract_vecenv_history(test_vec)
        if rl_test_history:
            final_net_worth = final_metrics.get("net_worth", None)
            if final_net_worth is not None:
                main_logger.info(f"Test complete on {test_ticker}. Final net worth: ${final_net_worth:.2f}")
            else:
                main_logger.warning(f"Final net worth is not available in the extracted metrics for {test_ticker}.")
        else:
            main_logger.warning(f"No test history recorded for {test_ticker} after fallback extraction.")

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
