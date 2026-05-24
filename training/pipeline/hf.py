from __future__ import annotations

from pathlib import Path


def upload_model_artifacts(repo_id: str, model_path: Path, metadata_path: Path, private: bool = True) -> dict:
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError("Install huggingface_hub to upload model artifacts") from exc

    if not model_path.exists() or not metadata_path.exists():
        raise ValueError("Model and metadata paths must exist before upload")

    api = HfApi()
    api.create_repo(repo_id=repo_id, private=private, exist_ok=True)
    api.upload_file(path_or_fileobj=str(model_path), path_in_repo=model_path.name, repo_id=repo_id)
    api.upload_file(path_or_fileobj=str(metadata_path), path_in_repo=metadata_path.name, repo_id=repo_id)
    return {"uploaded": True, "repo_id": repo_id, "files": [model_path.name, metadata_path.name]}
