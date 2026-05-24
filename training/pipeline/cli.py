from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.pipeline.trainer import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description="FraudShield governed XGBoost training pipeline")
    parser.add_argument("--dataset", choices=["demo_paysim", "creditcard", "paysim"], default="demo_paysim")
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("training/artifacts/candidates"))
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    result = run_training(
        dataset=args.dataset,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        model_version=args.model_version,
        rows=args.rows,
        random_seed=args.random_seed,
    )
    print(json.dumps(result["metadata"], indent=2))


if __name__ == "__main__":
    main()
