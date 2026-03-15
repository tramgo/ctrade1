from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


FEATURE_FAMILIES: Dict[str, List[str]] = {
    "F1_TrendMomentum": [
        "LagRet_1",
        "LagRet_5",
        "LagRet_20",
        "Trend_30",
        "Trend_2h",
        "Trend_slope",
        "RSI14",
        "MACD_z",
    ],
    "F2_VolRisk": [
        "ATR20_log",
        "RealVol20_log",
        "VolRegime",
        "MktVolRank",
    ],
    "F3_Relative": [
        "MktRet_1",
        "MktRet_3",
        "MktRet_6",
        "StockMinusMkt_1",
        "StockMinusMkt_3",
        "SectorMinusMkt_3",
    ],
    "F4_SessionContext": [
        "VWAP_Dist",
        "SessionOpenDist_ATR",
        "OpeningRangeBreakout",
        "TimeSinceNewHigh",
        "TimeSinceNewLow",
        "IntradayVolPercentile",
        "RelativeVolumeTime",
        "MinuteNorm",
    ],
    "F5_CandleShape": [
        "BodyToRange",
        "UpperWickRatio",
        "LowerWickRatio",
        "CloseLocation_3",
        "RetSkew_5",
    ],
    "F6_PersistenceBreakout": [
        "Breakout_3bar",
        "SignPersistence_5",
        "RegimeBull",
        "RegimeBear",
    ],
}


@dataclass(frozen=True)
class ExperimentDef:
    experiment_id: str
    target_id: str
    horizon: int
    label_type: str
    feature_families: List[str]
    model_class: str
    regime_filter: Optional[str] = None
    selection_rule: Optional[str] = None
    notes: str = ""


DEFAULT_EXPERIMENTS: List[ExperimentDef] = [
    ExperimentDef(
        experiment_id="E101",
        target_id="T3",
        horizon=2,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="Primary opportunity detector: h=2, F4+F5",
    ),
    ExperimentDef(
        experiment_id="E105",
        target_id="T3",
        horizon=2,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape", "F6_PersistenceBreakout"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="Opportunity detector with persistence/breakout context",
    ),
    ExperimentDef(
        experiment_id="E102",
        target_id="T3",
        horizon=3,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="Legacy h=3 opportunity baseline",
    ),
]


E004_SWEEP_EXPERIMENTS: List[ExperimentDef] = [
    ExperimentDef(
        experiment_id="E101",
        target_id="T3",
        horizon=2,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=2, F4+F5",
    ),
    ExperimentDef(
        experiment_id="E102",
        target_id="T3",
        horizon=3,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=3, F4+F5",
    ),
    ExperimentDef(
        experiment_id="E103",
        target_id="T3",
        horizon=4,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=4, F4+F5",
    ),
    ExperimentDef(
        experiment_id="E104",
        target_id="T3",
        horizon=5,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=5, F4+F5",
    ),
    ExperimentDef(
        experiment_id="E105",
        target_id="T3",
        horizon=2,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape", "F6_PersistenceBreakout"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=2, F4+F5+F6",
    ),
    ExperimentDef(
        experiment_id="E106",
        target_id="T3",
        horizon=3,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape", "F6_PersistenceBreakout"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=3, F4+F5+F6",
    ),
    ExperimentDef(
        experiment_id="E107",
        target_id="T3",
        horizon=4,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape", "F6_PersistenceBreakout"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=4, F4+F5+F6",
    ),
    ExperimentDef(
        experiment_id="E108",
        target_id="T3",
        horizon=5,
        label_type="binary",
        feature_families=["F4_SessionContext", "F5_CandleShape", "F6_PersistenceBreakout"],
        model_class="logistic",
        selection_rule="prob>=0.60",
        notes="E004 neighborhood sweep: h=5, F4+F5+F6",
    ),
]
