from __future__ import annotations

from pathlib import Path
from typing import Any


class ModelRegistry:
    def __init__(self, client: Any) -> None:
        self._client = client

    def register_approved(self, metadata: dict, model_path: Path, metadata_path: Path, activate: bool = False) -> dict:
        if not metadata.get("approval", {}).get("approved"):
            raise ValueError("Only approved models can be registered")
        if not model_path.exists() or not metadata_path.exists():
            raise ValueError("Model and metadata artifacts must exist before registry registration")
        if activate:
            self._client.table("model_registry").update({"is_active": False}).eq("is_active", True).execute()
        row = _registry_row(metadata, activate)
        result = self._client.table("model_registry").upsert(row, on_conflict="model_version").execute()
        return {"registered": True, "model_version": metadata["model_version"], "data": result.data}

    def rollback(self, model_version: str) -> dict:
        current = self._client.table("model_registry").select("model_version").eq("model_version", model_version).limit(1).execute()
        if not current.data:
            raise ValueError(f"Cannot rollback to unknown model version: {model_version}")
        self._client.table("model_registry").update({"is_active": False}).eq("is_active", True).execute()
        self._client.table("model_registry").update({"is_active": True}).eq("model_version", model_version).execute()
        return {"rolled_back": True, "active_model_version": model_version}

    def active(self) -> dict | None:
        result = self._client.table("model_registry").select("*").eq("is_active", True).limit(1).execute()
        return result.data[0] if result.data else None


def _registry_row(metadata: dict, activate: bool) -> dict:
    return {
        "model_version": metadata["model_version"],
        "feature_schema_version": metadata["feature_schema_version"],
        "ordered_features": metadata["ordered_features"],
        "feature_count": metadata["feature_count"],
        "preprocessing_config": metadata.get("preprocessing_config", {})
        | {
            "mode": metadata.get("mode"),
            "dataset": metadata.get("dataset"),
            "random_seed": metadata.get("random_seed"),
            "split": metadata.get("split"),
            "shap_compatibility": metadata.get("shap_compatibility"),
            "approval": metadata.get("approval"),
        },
        "metrics": metadata["metrics"],
        "is_active": activate,
    }
