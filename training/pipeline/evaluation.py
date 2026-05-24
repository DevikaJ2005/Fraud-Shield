from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xgboost as xgb
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score

from training.pipeline.schema import FEATURE_SCHEMA_VERSION, ORDERED_FEATURES


@dataclass(frozen=True)
class ApprovalThresholds:
    roc_auc: float = 0.85
    precision: float = 0.60
    recall: float = 0.55
    f1: float = 0.60
    pr_auc: float = 0.60


def metric_report(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 4),
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 4),
    }


def validate_shap_compatibility(booster: xgb.Booster, sample: np.ndarray) -> dict:
    try:
        import shap
    except ImportError as exc:
        raise RuntimeError("SHAP must be installed to approve model compatibility") from exc

    explainer = shap.TreeExplainer(booster)
    values = explainer.shap_values(sample)
    row = np.asarray(values)
    if row.ndim == 1:
        row = row.reshape(1, -1)
    if row.shape[1] != len(ORDERED_FEATURES):
        raise ValueError(f"SHAP output shape {row.shape} does not match feature schema")
    return {"compatible": True, "validated_rows": int(row.shape[0]), "output_columns": int(row.shape[1])}


def approve_model(metadata: dict, thresholds: ApprovalThresholds | None = None) -> dict:
    thresholds = thresholds or ApprovalThresholds()
    reasons: list[str] = []
    if metadata.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        reasons.append("feature schema version mismatch")
    if metadata.get("ordered_features") != ORDERED_FEATURES:
        reasons.append("feature ordering mismatch")
    if metadata.get("feature_count") != len(ORDERED_FEATURES):
        reasons.append("feature count mismatch")
    if not metadata.get("shap_compatibility", {}).get("compatible"):
        reasons.append("SHAP compatibility failed")
    metrics = metadata.get("metrics", {}).get("test", metadata.get("metrics", {}))
    for metric_name in ("roc_auc", "precision", "recall", "f1", "pr_auc"):
        if float(metrics.get(metric_name, 0.0)) < getattr(thresholds, metric_name):
            reasons.append(f"{metric_name} below threshold")
    return {"approved": not reasons, "reasons": reasons, "thresholds": thresholds.__dict__}
