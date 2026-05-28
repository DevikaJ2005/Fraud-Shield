from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.pipeline.hf import upload_model_artifacts
from training.pipeline.trainer import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description="FraudShield governed XGBoost training pipeline")
    parser.add_argument("--dataset", choices=["demo_paysim", "creditcard", "paysim"], default="demo_paysim")
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("training/artifacts/candidates"))
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--hf-repo", default=None)
    parser.add_argument("--hf-token", default=None)
    parser.add_argument("--upload-approved", action="store_true")
    args = parser.parse_args()

    result = run_training(
        dataset=args.dataset,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        model_version=args.model_version,
        rows=args.rows,
        random_seed=args.random_seed,
    )
    if args.upload_approved:
        if not args.hf_repo:
            raise SystemExit("--hf-repo is required with --upload-approved")
        if not result["metadata"].get("approval", {}).get("approved"):
            raise SystemExit("Candidate was not approved; refusing HF upload")
        result["hf_upload"] = upload_model_artifacts(
            repo_id=args.hf_repo,
            model_path=Path(result["model_path"]),
            metadata_path=Path(result["metadata_path"]),
            token=args.hf_token,
        )
    print(json.dumps(result["metadata"], indent=2))


if __name__ == "__main__":
    main()
