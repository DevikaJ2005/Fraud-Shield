from functools import lru_cache
from typing import ClassVar

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DEFAULT_VERCEL_ORIGIN_REGEX: ClassVar[str] = r"^https://[a-z0-9-]+\.vercel\.app$"
    PRODUCTION_FRONTEND_ORIGINS: ClassVar[tuple[str, ...]] = (
        "https://fraud-shield-blue.vercel.app",
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"))
    app_mode: str = Field(default="demo", pattern="^(demo|production)$")
    api_key_hashes: str = ""
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    hf_model_repo: str | None = None
    active_model_path: str | None = Field(
        default="models/demo_xgboost.json",
        validation_alias=AliasChoices("ACTIVE_MODEL_PATH", "MODEL_PATH"),
    )
    model_metadata_path: str | None = Field(
        default="models/demo_xgboost.metadata.json",
        validation_alias=AliasChoices("MODEL_METADATA_PATH", "MODEL_METADATA"),
    )
    groq_api_key: str | None = None
    rate_limit_per_minute: int = Field(default=60, ge=1)
    simulator_enabled: bool = Field(default=True, validation_alias=AliasChoices("SIMULATOR_ENABLED", "ENABLE_SIMULATOR"))
    simulator_api_key: str | None = Field(default=None, validation_alias=AliasChoices("SIMULATOR_API_KEY", "API_KEY"))
    simulator_min_interval_seconds: float = Field(default=2.0, ge=0.5)
    simulator_max_interval_seconds: float = Field(default=5.0, ge=0.5)
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,https://fraud-shield-blue.vercel.app",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )
    cors_origin_regex: str = Field(
        default=DEFAULT_VERCEL_ORIGIN_REGEX,
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "ALLOWED_ORIGIN_REGEX"),
    )

    @property
    def allowed_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        for origin in self.PRODUCTION_FRONTEND_ORIGINS:
            if origin not in origins:
                origins.append(origin)
        return origins

    @property
    def allowed_origin_regex(self) -> str:
        return self.cors_origin_regex.strip() or self.DEFAULT_VERCEL_ORIGIN_REGEX

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def resolve_project_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        raw_path = Path(value)
        if raw_path.is_absolute() and raw_path.exists():
            return raw_path

        candidates = [
            Path.cwd() / raw_path,
            self.project_root / raw_path,
            self.project_root / "backend" / raw_path,
            Path.cwd() / "models" / raw_path.name,
            self.project_root / "models" / raw_path.name,
            self.project_root / "backend" / "models" / raw_path.name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return (self.project_root / raw_path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
