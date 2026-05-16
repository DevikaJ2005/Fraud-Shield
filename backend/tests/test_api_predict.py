from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


async def noop_persist_prediction(*args, **kwargs) -> None:
    return None


async def noop_persist_graph(*args, **kwargs) -> None:
    return None


def test_api_predict_flow(monkeypatch) -> None:
    monkeypatch.setattr(routes.database, "verify_connection", lambda: {"available": False, "tables": {}, "error": "test"})
    monkeypatch.setattr(routes.database, "register_active_model", lambda _path: None)
    monkeypatch.setattr(routes.database, "persist_prediction", noop_persist_prediction)
    monkeypatch.setattr(routes.database, "persist_graph_relationships", noop_persist_graph)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predict",
            json={
                "transaction_id": "api-test-1",
                "account_id": "api-account-a",
                "merchant_id": "api-merchant",
                "device_id": "api-device",
                "ip_address": "10.0.0.5",
                "amount": 1200,
                "timestamp": "2026-05-15T10:00:00Z",
                "is_mobile": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transaction_id"] == "api-test-1"
    assert payload["model_version"] == "demo_xgboost"
    assert len(payload["shap_explanation"]) == 5
    assert "graph_degree" in payload["graph"]
