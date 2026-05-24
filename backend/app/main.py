import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import database, model_service, router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from simulator import simulator_service

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="FraudShield", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(router)
simulator_service.configure(app)


@app.on_event("startup")
async def startup() -> None:
    settings = get_settings()
    model_path = settings.resolve_project_path(settings.active_model_path)
    metadata_path = settings.resolve_project_path(settings.model_metadata_path)
    logger.info(
        "startup_env_detected",
        extra={
            "transaction_id": "",
            "model_version": "",
            "fraud_probability": None,
            "severity": "",
            "ring_detected": False,
            "supabase_url_detected": bool(settings.supabase_url),
            "supabase_service_role_key_detected": bool(settings.supabase_service_role_key),
            "model_path_detected": bool(settings.active_model_path),
            "model_metadata_path_detected": bool(settings.model_metadata_path),
            "resolved_model_path_exists": bool(model_path and model_path.exists()),
            "resolved_model_metadata_path_exists": bool(metadata_path and metadata_path.exists()),
        },
    )
    model_service.load()
    database.verify_connection()
    database.register_active_model(settings.active_model_path)
    if settings.simulator_enabled:
        await simulator_service.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await simulator_service.stop()
