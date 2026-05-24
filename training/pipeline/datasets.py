from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from training.pipeline.schema import LABEL_COLUMN, TIMESTAMP_COLUMN


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    path: Path | None = None
    timestamp_column: str | None = None
    label_column: str | None = None


def load_dataset(config: DatasetConfig, rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    if config.name == "demo_paysim":
        return generate_demo_paysim(rows=rows, seed=seed)
    if config.path is None:
        raise ValueError("A dataset path is required for non-demo training")

    raw = pd.read_csv(config.path)
    if config.name == "creditcard":
        return normalize_creditcard(raw, config)
    if config.name == "paysim":
        return normalize_paysim(raw, config)
    raise ValueError(f"Unsupported dataset: {config.name}")


def normalize_creditcard(raw: pd.DataFrame, config: DatasetConfig) -> pd.DataFrame:
    label = config.label_column or "Class"
    if label not in raw:
        raise ValueError("Credit Card Fraud Dataset requires a Class label column")
    timestamp_source = config.timestamp_column or ("Time" if "Time" in raw else None)
    frame = pd.DataFrame()
    frame[TIMESTAMP_COLUMN] = _timestamp_series(raw, timestamp_source)
    frame["amount"] = raw.get("Amount", pd.Series(0, index=raw.index)).astype(float)
    frame[LABEL_COLUMN] = raw[label].astype(int)
    return _with_operational_features(frame)


def normalize_paysim(raw: pd.DataFrame, config: DatasetConfig) -> pd.DataFrame:
    label = config.label_column or ("isFraud" if "isFraud" in raw else "is_fraud")
    if label not in raw:
        raise ValueError("PaySim requires isFraud or is_fraud label column")
    frame = pd.DataFrame()
    if config.timestamp_column and config.timestamp_column in raw:
        frame[TIMESTAMP_COLUMN] = pd.to_datetime(raw[config.timestamp_column], utc=True)
    else:
        step = raw.get("step", pd.Series(range(len(raw)), index=raw.index)).astype(int)
        frame[TIMESTAMP_COLUMN] = pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(step, unit="h")
    frame["amount"] = raw.get("amount", pd.Series(0, index=raw.index)).astype(float)
    frame[LABEL_COLUMN] = raw[label].astype(int)
    return _with_operational_features(frame)


def generate_demo_paysim(rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-01-01", periods=rows, freq="10min", tz="UTC")
    frame = pd.DataFrame(
        {
            TIMESTAMP_COLUMN: timestamps,
            "amount": rng.lognormal(mean=5.2, sigma=1.0, size=rows).clip(1, 25000),
        }
    )
    frame = _with_operational_features(frame, rng)
    fraud_signal = (
        (frame["amount"] > 2500).astype(int)
        + (frame["velocity_1h"] >= 5).astype(int)
        + (frame["velocity_24h"] >= 15).astype(int)
        + (frame["graph_degree"] >= 6).astype(int)
        + frame["ring_detected"] * 3
        + (frame["risk_propagation_score"] > 0.55).astype(int)
        + ((frame["hour"] < 5) & (frame["amount"] > 800)).astype(int)
    )
    frame[LABEL_COLUMN] = (
        (fraud_signal >= 3)
        | ((frame["amount"] > 5000) & (frame["velocity_1h"] >= 2))
        | ((frame["ring_detected"] == 1) & (frame["graph_degree"] >= 3))
    ).astype(int)
    return frame


def _timestamp_series(raw: pd.DataFrame, source: str | None) -> pd.Series:
    if source and source in raw:
        values = raw[source]
        if np.issubdtype(values.dtype, np.number):
            return pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(values.astype(float), unit="s")
        return pd.to_datetime(values, utc=True)
    return pd.date_range("2026-01-01", periods=len(raw), freq="min", tz="UTC").to_series(index=raw.index)


def _with_operational_features(frame: pd.DataFrame, rng: np.random.Generator | None = None) -> pd.DataFrame:
    rng = rng or np.random.default_rng(42)
    result = frame.copy()
    timestamps = pd.to_datetime(result[TIMESTAMP_COLUMN], utc=True)
    result[TIMESTAMP_COLUMN] = timestamps
    result["hour"] = timestamps.dt.hour.astype(float)
    result["day"] = timestamps.dt.dayofweek.astype(float)
    result["is_mobile"] = result.get("is_mobile", pd.Series(rng.binomial(1, 0.64, len(result)), index=result.index)).astype(float)
    result["velocity_1h"] = result.get("velocity_1h", pd.Series(rng.poisson(1.2, len(result)), index=result.index)).astype(float)
    result["velocity_24h"] = result.get("velocity_24h", result["velocity_1h"] + rng.poisson(4.5, len(result))).astype(float)
    result["graph_degree"] = result.get("graph_degree", pd.Series(rng.poisson(2.2, len(result)), index=result.index)).astype(float)
    result["graph_cluster"] = result.get("graph_cluster", pd.Series(rng.beta(1.2, 8.0, len(result)), index=result.index)).astype(float)
    result["ring_detected"] = result.get("ring_detected", pd.Series(rng.binomial(1, 0.035, len(result)), index=result.index)).astype(float)
    result["risk_propagation_score"] = result.get(
        "risk_propagation_score",
        np.clip((result["graph_degree"] / 14) + (result["ring_detected"] * 0.45) + rng.normal(0, 0.05, len(result)), 0, 1),
    ).astype(float)
    return result
