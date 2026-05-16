import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.model_service import ModelService


def test_default_model_artifacts_resolve_inside_backend_models(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ACTIVE_MODEL_PATH", "MODEL_PATH", "MODEL_METADATA_PATH", "MODEL_METADATA"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    model_path = settings.resolve_project_path(settings.active_model_path)
    metadata_path = settings.resolve_project_path(settings.model_metadata_path)

    assert model_path is not None
    assert metadata_path is not None
    assert model_path.as_posix().endswith("backend/models/demo_xgboost.json")
    assert metadata_path.as_posix().endswith("backend/models/demo_xgboost.metadata.json")
    assert model_path.exists()
    assert metadata_path.exists()


def test_model_schema_validation_rejects_feature_mismatch() -> None:
    metadata = json.loads(Path("training/artifacts/demo_xgboost.metadata.json").read_text(encoding="utf-8"))
    metadata["feature_count"] = 999

    with pytest.raises(RuntimeError, match="feature count"):
        ModelService._validate_metadata(metadata)


def test_shap_output_shape_and_serialization() -> None:
    from datetime import datetime, timezone

    from app.schemas.transaction import TransactionRequest
    from app.services.graph_engine import GraphEngine
    from app.services.pattern_engine import PatternEngine

    model = ModelService()
    assert model.load() is True

    tx = TransactionRequest(
        transaction_id="shape-test",
        account_id="shape-account",
        merchant_id="shape-merchant",
        device_id="shape-device",
        ip_address="10.0.0.4",
        amount=9000,
        timestamp=datetime.now(timezone.utc),
        is_mobile=True,
    )
    patterns = PatternEngine().evaluate(tx)
    graph = GraphEngine().add_transaction(tx)
    _, _, explanations = model.predict(tx, patterns, graph)

    assert len(explanations) == 5
    assert json.dumps([item.model_dump() for item in explanations])
