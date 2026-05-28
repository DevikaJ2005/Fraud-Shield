from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
from typing import Any

from app.core.config import get_settings
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedModel:
    model_version: str
    model_path: Path
    metadata_path: Path
    metadata: dict


class ModelCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def version_dir(self, model_version: str) -> Path:
        safe = "".join(char for char in model_version if char.isalnum() or char in {"-", "_", "."})
        return self.root / safe

    def cached(self, model_version: str) -> CachedModel | None:
        directory = self.version_dir(model_version)
        metadata_paths = sorted(directory.glob("*.metadata.json"))
        model_paths = sorted(path for path in directory.glob("*.json") if not path.name.endswith(".metadata.json"))
        if not metadata_paths or not model_paths:
            return None
        metadata = json.loads(metadata_paths[0].read_text(encoding="utf-8"))
        return CachedModel(model_version, model_paths[0], metadata_paths[0], metadata)

    def store(self, model_version: str, model_source: Path, metadata_source: Path) -> CachedModel:
        self.prepare()
        directory = self.version_dir(model_version)
        temp = directory.with_suffix(".tmp")
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True, exist_ok=True)
        model_target = temp / model_source.name
        metadata_target = temp / metadata_source.name
        shutil.copy2(model_source, model_target)
        shutil.copy2(metadata_source, metadata_target)
        metadata = json.loads(metadata_target.read_text(encoding="utf-8"))
        _validate_artifact_hash(model_target)
        _validate_artifact_hash(metadata_target)
        if directory.exists():
            shutil.rmtree(directory)
        temp.replace(directory)
        logger.info(
            "model_cache_refreshed",
            extra=_log_extra(metadata.get("model_version", model_version), cache_path=str(directory)),
        )
        return CachedModel(model_version, directory / model_source.name, directory / metadata_source.name, metadata)

    def cleanup(self, keep_versions: set[str], max_versions: int = 5) -> dict:
        self.prepare()
        entries = [path for path in self.root.iterdir() if path.is_dir() and not path.name.endswith(".tmp")]
        entries.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        kept = set(keep_versions)
        removed: list[str] = []
        for index, path in enumerate(entries):
            if path.name in kept or index < max_versions:
                continue
            shutil.rmtree(path)
            removed.append(path.name)
        logger.info("model_cache_cleanup", extra=_log_extra("", removed_versions=removed))
        return {"removed_versions": removed, "kept_versions": sorted(kept)}


class HuggingFaceModelRegistry:
    def __init__(self, repo_id: str, token: str | None = None) -> None:
        self.repo_id = repo_id
        self.token = token

    def list_versions(self) -> list[dict]:
        api = self._api()
        files = api.list_repo_files(repo_id=self.repo_id, token=self.token)
        versions = {}
        for filename in files:
            if filename.endswith(".metadata.json"):
                version = Path(filename).name.replace(".metadata.json", "")
                versions.setdefault(version, {})["metadata_file"] = filename
            elif filename.endswith(".metrics.json"):
                version = Path(filename).name.replace(".metrics.json", "")
                versions.setdefault(version, {})["metrics_file"] = filename
            elif filename.endswith(".json"):
                version = Path(filename).stem
                versions.setdefault(version, {})["model_file"] = filename
        return [{"model_version": version, **payload} for version, payload in sorted(versions.items())]

    def download(self, model_version: str, cache: ModelCache) -> CachedModel:
        cached = cache.cached(model_version)
        if cached:
            logger.info("model_download_cache_hit", extra=_log_extra(model_version))
            return cached
        hf_hub_download = self._download_fn()
        model_file = f"{model_version}.json"
        metadata_file = f"{model_version}.metadata.json"
        target = cache.version_dir(model_version)
        target.mkdir(parents=True, exist_ok=True)
        model_path = Path(hf_hub_download(repo_id=self.repo_id, filename=model_file, token=self.token, local_dir=target))
        metadata_path = Path(hf_hub_download(repo_id=self.repo_id, filename=metadata_file, token=self.token, local_dir=target))
        logger.info("model_download_succeeded", extra=_log_extra(model_version, repo_id=self.repo_id))
        return cache.store(model_version, model_path, metadata_path)

    def upload(self, model_path: Path, metadata_path: Path, private: bool = True) -> dict:
        api = self._api()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not metadata.get("approval", {}).get("approved", True):
            raise ValueError("Only approved model metadata can be uploaded")
        api.create_repo(repo_id=self.repo_id, private=private, exist_ok=True, token=self.token)
        api.upload_file(path_or_fileobj=str(model_path), path_in_repo=model_path.name, repo_id=self.repo_id, token=self.token)
        api.upload_file(path_or_fileobj=str(metadata_path), path_in_repo=metadata_path.name, repo_id=self.repo_id, token=self.token)
        metrics_path = metadata_path.with_name(metadata_path.name.replace(".metadata.json", ".metrics.json"))
        metrics_path.write_text(json.dumps(metadata.get("metrics", {}), indent=2), encoding="utf-8")
        api.upload_file(path_or_fileobj=str(metrics_path), path_in_repo=metrics_path.name, repo_id=self.repo_id, token=self.token)
        logger.info("model_upload_succeeded", extra=_log_extra(metadata.get("model_version", model_path.stem), repo_id=self.repo_id))
        return {"uploaded": True, "repo_id": self.repo_id, "files": [model_path.name, metadata_path.name, metrics_path.name]}

    @staticmethod
    def _api() -> Any:
        try:
            from huggingface_hub import HfApi
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required for HF model registry operations") from exc
        return HfApi()

    @staticmethod
    def _download_fn() -> Any:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise RuntimeError("huggingface_hub is required for HF model registry operations") from exc
        return hf_hub_download


class ModelLifecycleService:
    def __init__(self, model_service: ModelService) -> None:
        self.model_service = model_service
        self.previous_active: CachedModel | None = None
        self.active_cached: CachedModel | None = None
        self.last_activation: dict | None = None

    def status(self) -> dict:
        settings = get_settings()
        return {
            "active_model_version": self.model_service.model_version,
            "previous_model_version": self.previous_active.model_version if self.previous_active else None,
            "hf_repo_configured": bool(settings.hf_model_repo),
            "cache_dir": str(settings.resolve_project_path(settings.model_cache_dir)),
            "last_activation": self.last_activation,
        }

    def list_remote_versions(self) -> list[dict]:
        registry = self._registry()
        return registry.list_versions()

    def activate_remote(self, model_version: str) -> dict:
        settings = get_settings()
        cache = self._cache()
        registry = self._registry()
        try:
            cached = registry.download(model_version, cache)
            return self.activate_cached(cached)
        except Exception as exc:
            self.last_activation = {"activated": False, "model_version": model_version, "error": str(exc)}
            logger.error("remote_model_activation_failed", extra=_log_extra(model_version, activation_error=str(exc)))
            return self.last_activation

    def activate_cached(self, cached: CachedModel) -> dict:
        current = self.active_cached or self._current_cached()
        result = self.model_service.activate_candidate(cached.model_path, cached.metadata_path)
        if result["activated"]:
            self.previous_active = current
            self.active_cached = cached
            self._cache().cleanup({cached.model_version, current.model_version if current else ""})
        self.last_activation = result | {"model_version": cached.model_version}
        return self.last_activation

    def rollback(self) -> dict:
        if self.previous_active is None:
            return {"rolled_back": False, "error": "No previous active model is available"}
        result = self.model_service.activate_candidate(self.previous_active.model_path, self.previous_active.metadata_path)
        if result["activated"]:
            self.active_cached = self.previous_active
            logger.info("model_rollback_succeeded", extra=_log_extra(self.previous_active.model_version))
        else:
            logger.error("model_rollback_failed", extra=_log_extra(self.previous_active.model_version, activation_error=result.get("error")))
        return result | {"rolled_back": result["activated"]}

    def _current_cached(self) -> CachedModel | None:
        settings = get_settings()
        model_path = settings.resolve_project_path(settings.active_model_path)
        metadata_path = settings.resolve_project_path(settings.model_metadata_path)
        if not model_path or not metadata_path or not model_path.exists() or not metadata_path.exists():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return CachedModel(metadata.get("model_version", model_path.stem), model_path, metadata_path, metadata)

    def _cache(self) -> ModelCache:
        settings = get_settings()
        cache_dir = settings.resolve_project_path(settings.model_cache_dir) or Path(settings.model_cache_dir)
        return ModelCache(cache_dir)

    def _registry(self) -> HuggingFaceModelRegistry:
        settings = get_settings()
        if not settings.hf_model_repo:
            raise RuntimeError("HF_MODEL_REPO is not configured")
        return HuggingFaceModelRegistry(settings.hf_model_repo, settings.hf_token)


def _validate_artifact_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not digest:
        raise ValueError(f"Artifact hash failed for {path}")
    return digest


def _log_extra(model_version: str, **values: Any) -> dict:
    return {
        "transaction_id": "",
        "model_version": model_version,
        "fraud_probability": None,
        "severity": "",
        "ring_detected": False,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        **values,
    }
