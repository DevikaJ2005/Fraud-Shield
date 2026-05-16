import json
from pathlib import Path

import pytest

from app.services.model_service import ModelService


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
