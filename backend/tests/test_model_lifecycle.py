import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.services.model_lifecycle import CachedModel, ModelCache, ModelLifecycleService


def _artifact_pair(directory: Path, version: str, approved: bool = True) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / f"{version}.json"
    metadata_path = directory / f"{version}.metadata.json"
    model_path.write_text('{"learner": {}}', encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "model_version": version,
                "feature_schema_version": "v1",
                "ordered_features": [
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
                ],
                "feature_count": 10,
                "serialization": "xgboost_native_json",
                "approval": {"approved": approved},
                "shap_compatibility": {"compatible": True},
                "metrics": {"test": {"f1": 0.9}},
            }
        ),
        encoding="utf-8",
    )
    return model_path, metadata_path


def test_model_cache_stores_and_reuses_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    model_path, metadata_path = _artifact_pair(source, "candidate")
    cache = ModelCache(tmp_path / "cache")

    cached = cache.store("candidate", model_path, metadata_path)
    reused = cache.cached("candidate")

    assert cached.model_path.exists()
    assert cached.metadata_path.exists()
    assert reused is not None
    assert reused.metadata["model_version"] == "candidate"


class _FakeModelService:
    def __init__(self) -> None:
        self.model_version = "current"

    def activate_candidate(self, model_path: Path, metadata_path: Path) -> dict:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.model_version = metadata["model_version"]
        return {"activated": True, "active_model_version": self.model_version, "previous_model_version": "current"}


def test_lifecycle_rollback_preserves_previous_cached_model(tmp_path: Path) -> None:
    previous_model, previous_metadata = _artifact_pair(tmp_path / "previous", "previous")
    candidate_model, candidate_metadata = _artifact_pair(tmp_path / "candidate", "candidate")
    service = ModelLifecycleService(_FakeModelService())  # type: ignore[arg-type]
    previous = CachedModel("previous", previous_model, previous_metadata, json.loads(previous_metadata.read_text(encoding="utf-8")))
    candidate = CachedModel("candidate", candidate_model, candidate_metadata, json.loads(candidate_metadata.read_text(encoding="utf-8")))
    service.previous_active = previous

    activated = service.activate_cached(candidate)
    service.previous_active = previous
    rolled_back = service.rollback()

    assert activated["activated"] is True
    assert rolled_back["rolled_back"] is True
    assert rolled_back["active_model_version"] == "previous"
