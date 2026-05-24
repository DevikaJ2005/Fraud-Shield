import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

import numpy as np
import pytest
import xgboost as xgb

from app.services.model_service import ModelService
from training.pipeline.datasets import generate_demo_paysim
from training.pipeline.evaluation import ApprovalThresholds, approve_model, validate_shap_compatibility
from training.pipeline.features import temporal_split
from training.pipeline.registry import ModelRegistry
from training.pipeline.schema import FEATURE_SCHEMA_VERSION, ORDERED_FEATURES
from training.pipeline.trainer import run_training


def test_temporal_split_preserves_time_order() -> None:
    frame = generate_demo_paysim(rows=120, seed=1)
    splits = temporal_split(frame)

    assert splits["train"]["timestamp"].max() < splits["validation"]["timestamp"].min()
    assert splits["validation"]["timestamp"].max() < splits["test"]["timestamp"].min()


def test_approval_rejects_schema_and_metric_mismatch() -> None:
    metadata = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "ordered_features": ORDERED_FEATURES[:-1],
        "feature_count": len(ORDERED_FEATURES) - 1,
        "shap_compatibility": {"compatible": True},
        "metrics": {"test": {"roc_auc": 0.1, "precision": 0.1, "recall": 0.1, "f1": 0.1, "pr_auc": 0.1}},
    }

    approval = approve_model(metadata, ApprovalThresholds())

    assert approval["approved"] is False
    assert "feature ordering mismatch" in approval["reasons"]
    assert "roc_auc below threshold" in approval["reasons"]


def test_training_outputs_reloadable_shap_compatible_model(tmp_path: Path) -> None:
    pytest.importorskip("shap")
    result = run_training(
        dataset="demo_paysim",
        output_dir=tmp_path,
        model_version="test_xgboost_governed",
        rows=600,
        random_seed=9,
        thresholds=ApprovalThresholds(roc_auc=0.5, precision=0.3, recall=0.3, f1=0.3, pr_auc=0.3),
    )
    metadata = result["metadata"]
    model_path = Path(result["model_path"])
    metadata_path = Path(result["metadata_path"])

    assert metadata["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert metadata["ordered_features"] == ORDERED_FEATURES
    assert metadata["approval"]["approved"] is True
    ModelService._validate_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))
    booster = xgb.Booster()
    booster.load_model(model_path)
    assert validate_shap_compatibility(booster, np.zeros((2, len(ORDERED_FEATURES))))["compatible"] is True


class _Result:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, state):
        self.state = state
        self.operation = None
        self.payload = None
        self.filters = {}

    def select(self, *_args):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, _value):
        return self

    def execute(self):
        if self.operation == "select":
            rows = [row for row in self.state if all(row.get(k) == v for k, v in self.filters.items())]
            return _Result(rows)
        if self.operation == "update":
            for row in self.state:
                if all(row.get(k) == v for k, v in self.filters.items()):
                    row.update(self.payload)
            return _Result([])
        if self.operation == "upsert":
            self.state.append(self.payload)
            return _Result([self.payload])
        raise AssertionError("unexpected operation")


class _Client:
    def __init__(self, state):
        self.state = state

    def table(self, _name):
        return _Table(self.state)


def test_registry_rejects_unapproved_and_rolls_back_known_model(tmp_path: Path) -> None:
    state = [{"model_version": "previous", "is_active": False}]
    registry = ModelRegistry(_Client(state))
    unapproved = {"approval": {"approved": False}}

    with pytest.raises(ValueError):
        registry.register_approved(unapproved, tmp_path / "missing.json", tmp_path / "missing.metadata.json")

    result = registry.rollback("previous")

    assert result["rolled_back"] is True
    assert state[0]["is_active"] is True
