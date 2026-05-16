"""Training entrypoints for FraudShield.

Production training should run inside Kaggle and publish approved XGBoost
artifacts to Hugging Face Hub. The demo training path creates a deterministic,
PaySim-style sample dataset for local MVP validation without fake predictions.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

ORDERED_FEATURES = [
    "amount",
    "hour",
    "day",
    "is_mobile",
    "velocity_1h",
    "velocity_24h",
    "graph_degree",
    "graph_cluster",
    "ring_detected",
    "risk_propagation_score",
]

FEATURE_SCHEMA_VERSION = "v1"
RANDOM_SEED = 42


def save_metadata(output_dir: Path, metrics: dict, ordered_features: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "ordered_features": ordered_features,
        "feature_count": len(ordered_features),
        "metrics": metrics,
        "split": "temporal",
        "serialization": "xgboost_native_json",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def approve_candidate(candidate_metrics: dict, current_f1: float) -> bool:
    gates = {
        "precision": 0.88,
        "recall": 0.82,
        "f1": 0.85,
        "roc_auc": 0.97,
    }
    if candidate_metrics.get("false_positive_rate", 1.0) > 0.05:
        return False
    if any(candidate_metrics.get(metric, 0.0) < minimum for metric, minimum in gates.items()):
        return False
    return candidate_metrics["f1"] > current_f1


def save_model(model: xgb.Booster, output_path: Path) -> None:
    if output_path.suffix != ".json":
        raise ValueError("Production model artifacts must use XGBoost native JSON")
    model.save_model(output_path)


def generate_demo_paysim_sample(rows: int = 2500) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="10min")
    amount = rng.lognormal(mean=5.2, sigma=1.0, size=rows).clip(1, 25000)
    hour = timestamps.hour
    day = timestamps.dayofweek
    is_mobile = rng.binomial(1, 0.64, size=rows)
    velocity_1h = rng.poisson(1.2, size=rows)
    velocity_24h = velocity_1h + rng.poisson(4.5, size=rows)
    graph_degree = rng.poisson(2.2, size=rows)
    graph_cluster = rng.beta(1.2, 8.0, size=rows)
    ring_detected = rng.binomial(1, 0.035, size=rows)
    risk_propagation_score = np.clip((graph_degree / 14) + (ring_detected * 0.45) + rng.normal(0, 0.05, rows), 0, 1)

    fraud_signal = (
        (amount > 2500).astype(int)
        + (velocity_1h >= 5).astype(int)
        + (velocity_24h >= 15).astype(int)
        + (graph_degree >= 6).astype(int)
        + ring_detected * 3
        + (risk_propagation_score > 0.55).astype(int)
        + ((hour < 5) & (amount > 800)).astype(int)
    )
    label = (
        (fraud_signal >= 3)
        | ((amount > 5000) & (velocity_1h >= 2))
        | ((ring_detected == 1) & (graph_degree >= 3))
    ).astype(int)

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "amount": amount,
            "hour": hour,
            "day": day,
            "is_mobile": is_mobile,
            "velocity_1h": velocity_1h,
            "velocity_24h": velocity_24h,
            "graph_degree": graph_degree,
            "graph_cluster": graph_cluster,
            "ring_detected": ring_detected,
            "risk_propagation_score": risk_propagation_score,
            "is_fraud": label,
        }
    )


def metric_report(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    predictions = (probabilities >= 0.5).astype(int)
    false_positive = int(((predictions == 1) & (y_true == 0)).sum())
    true_negative = int(((predictions == 0) & (y_true == 0)).sum())
    return {
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "false_positive_rate": round(false_positive / max(false_positive + true_negative, 1), 4),
    }


def train_demo_model(output_dir: Path) -> dict:
    data = generate_demo_paysim_sample()
    split_index = int(len(data) * 0.8)
    train = data.iloc[:split_index]
    test = data.iloc[split_index:]

    x_train = train[ORDERED_FEATURES]
    y_train = train["is_fraud"].to_numpy()
    x_test = test[ORDERED_FEATURES]
    y_test = test["is_fraud"].to_numpy()

    logistic = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)
    logistic.fit(x_train, y_train)
    logistic_metrics = metric_report(y_test, logistic.predict_proba(x_test)[:, 1])

    forest = RandomForestClassifier(n_estimators=80, max_depth=6, random_state=RANDOM_SEED, n_jobs=1)
    forest.fit(x_train, y_train)
    forest_metrics = metric_report(y_test, forest.predict_proba(x_test)[:, 1])

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=90,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=RANDOM_SEED,
    )
    model.fit(x_train, y_train)
    xgboost_metrics = metric_report(y_test, model.predict_proba(x_test)[:, 1])

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "demo_xgboost.json"
    model.get_booster().save_model(model_path)
    metadata = {
        "model_version": "demo_xgboost",
        "mode": "demo",
        "dataset": "deterministic_paysim_style_sample",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "ordered_features": ORDERED_FEATURES,
        "feature_count": len(ORDERED_FEATURES),
        "random_seed": RANDOM_SEED,
        "split": {
            "type": "temporal",
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "train_start": str(train["timestamp"].min()),
            "train_end": str(train["timestamp"].max()),
            "test_start": str(test["timestamp"].min()),
            "test_end": str(test["timestamp"].max()),
        },
        "baselines": {
            "logistic_regression": logistic_metrics,
            "random_forest": forest_metrics,
        },
        "metrics": xgboost_metrics,
        "serialization": "xgboost_native_json",
    }
    (output_dir / "demo_xgboost.metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    result = train_demo_model(Path("training/artifacts"))
    print(json.dumps(result, indent=2))
