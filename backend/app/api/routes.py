import logging

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException, status

from app.core.security import enforce_rate_limit, require_api_key
from app.schemas.transaction import FeedbackRequest, PredictionResponse, TransactionRequest
from app.services.alerts import severity_for
from app.services.database import DatabaseService
from app.services.graph_engine import GraphEngine
from app.services.model_lifecycle import ModelLifecycleService
from app.services.model_service import FEATURE_SCHEMA_VERSION, ModelService
from app.services.narration import deterministic_narration
from app.services.pattern_engine import PatternEngine
from simulator import simulator_service

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
logger = logging.getLogger(__name__)

pattern_engine = PatternEngine()
graph_engine = GraphEngine()
model_service = ModelService()
model_lifecycle = ModelLifecycleService(model_service)
database = DatabaseService()


@router.post("/predict", response_model=PredictionResponse)
async def predict(tx: TransactionRequest, request: Request) -> PredictionResponse:
    enforce_rate_limit(request)
    patterns = pattern_engine.evaluate(tx)
    graph = graph_engine.add_transaction(tx)
    probability, confidence, explanations = model_service.predict(tx, patterns, graph)
    severity = severity_for(probability, graph)
    response = PredictionResponse(
        transaction_id=tx.transaction_id,
        fraud_probability=probability,
        confidence=confidence,
        severity=severity,
        model_version=model_service.model_version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        patterns=patterns,
        graph=graph,
        shap_explanation=explanations,
        narration=deterministic_narration(probability, patterns, graph, explanations),
    )
    await database.persist_prediction(tx, response)
    await database.persist_graph_relationships(graph_engine.latest_relationships())
    logger.info(
        "prediction_completed",
        extra={
            "transaction_id": tx.transaction_id,
            "model_version": response.model_version,
            "fraud_probability": response.fraud_probability,
            "severity": response.severity.value if response.severity else None,
            "ring_detected": response.graph.ring_detected,
        },
    )
    return response


@router.post("/feedback")
async def feedback(payload: FeedbackRequest, request: Request) -> dict[str, str]:
    enforce_rate_limit(request)
    await database.persist_feedback(payload)
    return {"status": "accepted"}


@router.get("/transactions")
async def transactions(request: Request) -> list[dict]:
    enforce_rate_limit(request)
    return database.recent_transactions()


@router.get("/graph/current")
async def graph_current(request: Request) -> dict:
    enforce_rate_limit(request)
    payload = graph_engine.current_payload(max_nodes=500)
    payload["integrity"] = graph_engine.integrity_report()
    return payload


@router.get("/model/status")
async def model_status(request: Request) -> dict[str, str]:
    enforce_rate_limit(request)
    return {
        "model_version": model_service.model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "status": "available" if model_service._model is not None else "unavailable",
        "last_error": model_service.last_error or "",
    }


@router.get("/models/lifecycle/status")
async def model_lifecycle_status(request: Request) -> dict:
    enforce_rate_limit(request)
    return model_lifecycle.status()


@router.get("/models/remote")
async def remote_models(request: Request) -> list[dict]:
    enforce_rate_limit(request)
    return model_lifecycle.list_remote_versions()


@router.post("/models/activate/{model_version}")
async def activate_remote_model(model_version: str, request: Request) -> dict:
    enforce_rate_limit(request)
    result = model_lifecycle.activate_remote(model_version)
    if result.get("activated") and model_lifecycle.active_cached:
        database.register_model_metadata(model_lifecycle.active_cached.metadata, activate=True)
    return result


@router.post("/models/rollback")
async def rollback_model(request: Request) -> dict:
    enforce_rate_limit(request)
    result = model_lifecycle.rollback()
    if result.get("rolled_back") and model_lifecycle.previous_active:
        database.register_model_metadata(model_lifecycle.previous_active.metadata, activate=True)
    return result


@router.get("/alerts")
async def alerts(request: Request) -> list[dict]:
    enforce_rate_limit(request)
    return database.recent_alerts()


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: Request) -> dict:
    enforce_rate_limit(request)
    alert = database.acknowledge_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.get("/fraud-intelligence")
async def fraud_intelligence(request: Request) -> list[dict]:
    enforce_rate_limit(request)
    return database.fraud_intelligence()


@router.get("/health")
async def health() -> dict[str, str]:
    db_status = database.status()
    return {
        "status": "ok",
        "model": "available" if model_service._model is not None else "unavailable",
        "supabase": "available" if db_status["available"] else "unavailable",
    }


@router.get("/system/storage-status")
async def storage_status(request: Request) -> dict:
    enforce_rate_limit(request)
    return database.storage_status()


@router.post("/simulator/start")
async def simulator_start(request: Request) -> dict:
    enforce_rate_limit(request)
    return await simulator_service.start()


@router.post("/simulator/stop")
async def simulator_stop(request: Request) -> dict:
    enforce_rate_limit(request)
    return await simulator_service.stop()


@router.get("/simulator/status")
async def simulator_status(request: Request) -> dict:
    enforce_rate_limit(request)
    return simulator_service.status()
