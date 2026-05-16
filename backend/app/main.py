from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import database, model_service, router
from app.core.config import get_settings
from app.core.logging_config import configure_logging

configure_logging()

app = FastAPI(title="FraudShield", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    model_service.load()
    database.verify_connection()
    database.register_active_model(get_settings().active_model_path)
