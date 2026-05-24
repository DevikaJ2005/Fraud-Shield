from __future__ import annotations

from datetime import datetime, timezone

from training.pipeline.schema import FEATURE_SCHEMA_VERSION, ORDERED_FEATURES


def build_metadata(
    model_version: str,
    dataset: str,
    random_seed: int,
    split: dict,
    metrics: dict,
    shap_compatibility: dict,
    approval: dict,
) -> dict:
    return {
        "model_version": model_version,
        "mode": "training",
        "dataset": dataset,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "ordered_features": ORDERED_FEATURES,
        "feature_count": len(ORDERED_FEATURES),
        "random_seed": random_seed,
        "split": split,
        "preprocessing_config": {
            "normalization": "schema_preserving_numeric_coercion",
            "graph_features": "provided_or_deterministically_synthesized_for_dataset_adapter",
            "temporal_split": True,
        },
        "metrics": metrics,
        "shap_compatibility": shap_compatibility,
        "approval": approval,
        "serialization": "xgboost_native_json",
    }
