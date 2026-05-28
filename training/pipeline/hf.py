from __future__ import annotations

import json
from pathlib import Path


def upload_model_artifacts(repo_id: str, model_path: Path, metadata_path: Path, private: bool = True, token: str | None = None) -> dict:
    if not model_path.exists() or not metadata_path.exists():
        raise ValueError("Model and metadata paths must exist before upload")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not metadata.get("approval", {}).get("approved", True):
        raise ValueError("Only approved model metadata can be uploaded")

    api = _api()
    api.create_repo(repo_id=repo_id, private=private, exist_ok=True, token=token)
    api.upload_file(path_or_fileobj=str(model_path), path_in_repo=model_path.name, repo_id=repo_id, token=token)
    api.upload_file(path_or_fileobj=str(metadata_path), path_in_repo=metadata_path.name, repo_id=repo_id, token=token)
    metrics_path = metadata_path.with_name(metadata_path.name.replace(".metadata.json", ".metrics.json"))
    metrics_path.write_text(json.dumps(metadata.get("metrics", {}), indent=2), encoding="utf-8")
    api.upload_file(path_or_fileobj=str(metrics_path), path_in_repo=metrics_path.name, repo_id=repo_id, token=token)
    return {"uploaded": True, "repo_id": repo_id, "files": [model_path.name, metadata_path.name, metrics_path.name]}


def list_model_versions(repo_id: str, token: str | None = None) -> list[dict]:
    files = _api().list_repo_files(repo_id=repo_id, token=token)
    versions: dict[str, dict] = {}
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


def download_model_artifacts(repo_id: str, model_version: str, output_dir: Path, token: str | None = None) -> dict:
    hf_hub_download = _download_fn()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = Path(hf_hub_download(repo_id=repo_id, filename=f"{model_version}.json", token=token, local_dir=output_dir))
    metadata_path = Path(hf_hub_download(repo_id=repo_id, filename=f"{model_version}.metadata.json", token=token, local_dir=output_dir))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {"model_path": str(model_path), "metadata_path": str(metadata_path), "metadata": metadata}


def _api():
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError("Install huggingface_hub to use HF model registry helpers") from exc
    return HfApi()


def _download_fn():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("Install huggingface_hub to use HF model registry helpers") from exc
    return hf_hub_download
