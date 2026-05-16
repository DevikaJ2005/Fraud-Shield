from pathlib import Path
import json
import logging

import numpy as np
import shap
import xgboost as xgb
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.transaction import GraphAnalysis, PatternFlag, ShapExplanation, TransactionRequest


FEATURE_SCHEMA_VERSION = "v1"
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

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(self) -> None:
        self._model: xgb.Booster | None = None
        self._explainer: shap.TreeExplainer | None = None
        self.model_version = "unloaded"
        self.last_error: str | None = None

    def load(self) -> bool:
        settings = get_settings()
        path = settings.active_model_path
        if not path:
            self.last_error = "ACTIVE_MODEL_PATH is not configured"
            logger.error(self.last_error)
            return False
        model_path = settings.resolve_project_path(path)
        try:
            booster, metadata = self._load_candidate(model_path)
            explainer = shap.TreeExplainer(booster)
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Rejected model load from %s: %s", model_path, exc)
            return False

        self._model = booster
        self._explainer = explainer
        self.model_version = metadata.get("model_version", model_path.stem)
        self.last_error = None
        logger.info("Loaded model %s with feature schema %s", self.model_version, FEATURE_SCHEMA_VERSION)
        return True

    def predict(self, tx: TransactionRequest, patterns: list[PatternFlag], graph: GraphAnalysis) -> tuple[float, float, list[ShapExplanation]]:
        if self._model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Active fraud model is unavailable",
            )

        feature_values = self._features(tx, patterns, graph)
        matrix = xgb.DMatrix(np.array([[feature_values[name] for name in ORDERED_FEATURES]]), feature_names=ORDERED_FEATURES)
        probability = float(self._model.predict(matrix)[0])
        confidence = max(probability, 1 - probability)
        return probability, confidence, self._shap_explanations(feature_values, probability)

    @staticmethod
    def _features(tx: TransactionRequest, patterns: list[PatternFlag], graph: GraphAnalysis) -> dict[str, float]:
        pattern_map = {pattern.name: pattern.value for pattern in patterns}
        return {
            "amount": tx.amount,
            "hour": float(tx.timestamp.hour),
            "day": float(tx.timestamp.weekday()),
            "is_mobile": float(tx.is_mobile),
            "velocity_1h": float(pattern_map.get("velocity_abuse_1h", False)),
            "velocity_24h": float(pattern_map.get("velocity_abuse_24h", False)),
            "graph_degree": float(graph.graph_degree),
            "graph_cluster": float(graph.clustering_coefficient),
            "ring_detected": float(graph.ring_detected),
            "risk_propagation_score": float(graph.risk_propagation_score),
        }

    def _shap_explanations(self, feature_values: dict[str, float], probability: float) -> list[ShapExplanation]:
        if self._explainer is None:
            return self._fallback_explanations(feature_values, probability)
        try:
            values = np.array([[feature_values[name] for name in ORDERED_FEATURES]])
            shap_values = self._explainer.shap_values(values)
            row = np.asarray(shap_values)
            if row.ndim == 1:
                row = row.reshape(1, -1)
            if row.shape != (1, len(ORDERED_FEATURES)):
                raise RuntimeError(f"SHAP output shape {row.shape} does not match feature schema")
            shap_row = row[0]
            ranked = sorted(
                zip(range(len(ORDERED_FEATURES)), ORDERED_FEATURES, shap_row, strict=True),
                key=lambda item: (-abs(float(item[2])), item[0]),
            )[:5]
            return [
                ShapExplanation(
                    feature=name,
                    value=feature_values[name],
                    shap_value=round(float(shap_value), 6),
                    direction="fraud" if float(shap_value) >= 0 else "legitimate",
                )
                for _, name, shap_value in ranked
            ]
        except Exception as exc:
            logger.warning("SHAP generation failed; using deterministic fallback: %s", exc)
            return self._fallback_explanations(feature_values, probability)

    @staticmethod
    def _fallback_explanations(feature_values: dict[str, float], probability: float) -> list[ShapExplanation]:
        direction = "fraud" if probability >= 0.5 else "legitimate"
        ranked = sorted(feature_values.items(), key=lambda item: abs(float(item[1])), reverse=True)[:5]
        return [
            ShapExplanation(feature=name, value=value, shap_value=0.0, direction=direction)
            for name, value in ranked
        ]

    def _load_candidate(self, model_path: Path | None) -> tuple[xgb.Booster, dict]:
        if model_path is None or not model_path.exists() or model_path.suffix not in {".json", ".ubj"}:
            raise RuntimeError("Active model must be an XGBoost native JSON or UBJ artifact")

        metadata_path = self._metadata_path(model_path)
        if metadata_path is None or not metadata_path.exists():
            raise RuntimeError("Model metadata is required for schema validation")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self._validate_metadata(metadata)

        booster = xgb.Booster()
        booster.load_model(str(model_path))
        if booster.feature_names and booster.feature_names != ORDERED_FEATURES:
            raise RuntimeError("Model feature order does not match inference feature schema")
        return booster, metadata

    @staticmethod
    def _metadata_path(model_path: Path) -> Path | None:
        settings = get_settings()
        if settings.model_metadata_path:
            return settings.resolve_project_path(settings.model_metadata_path)
        return model_path.with_suffix(".metadata.json")

    @staticmethod
    def _validate_metadata(metadata: dict) -> None:
        if metadata.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise RuntimeError("Model feature schema version is incompatible")
        if metadata.get("ordered_features") != ORDERED_FEATURES:
            raise RuntimeError("Model ordered feature list is incompatible")
        if metadata.get("feature_count") != len(ORDERED_FEATURES):
            raise RuntimeError("Model feature count is incompatible")
        if metadata.get("serialization") != "xgboost_native_json":
            raise RuntimeError("Model serialization metadata is incompatible")
