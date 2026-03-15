from __future__ import annotations

from typing import Any

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
except ImportError:
    LGBMClassifier = None
    LGBMRegressor = None


def make_model(model_class: str) -> Any:
    if model_class == "elasticnet":
        from sklearn.linear_model import ElasticNet
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", ElasticNet(alpha=0.001, l1_ratio=0.5, random_state=42, max_iter=10000)),
            ]
        )

    if model_class == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        penalty="l2",
                        C=1.0,
                        max_iter=5000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        )

    if model_class == "lgbm_reg":
        if LGBMRegressor is None:
            raise ImportError("lightgbm not installed")
        return LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )

    if model_class == "lgbm_clf":
        if LGBMClassifier is None:
            raise ImportError("lightgbm not installed")
        return LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=42,
        )

    raise ValueError(f"Unsupported model_class: {model_class}")
