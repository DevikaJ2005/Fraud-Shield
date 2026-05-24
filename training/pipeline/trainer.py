from __future__ import annotations

import json
from pathlib import Path

import xgboost as xgb

from training.pipeline.datasets import DatasetConfig, load_dataset
from training.pipeline.evaluation import ApprovalThresholds, approve_model, metric_report, validate_shap_compatibility
from training.pipeline.features import prepare_features, split_summary, temporal_split
from training.pipeline.metadata import build_metadata
from training.pipeline.schema import ORDERED_FEATURES, validate_feature_order


def run_training(
    dataset: str = "demo_paysim",
    dataset_path: Path | None = None,
    output_dir: Path = Path("training/artifacts/candidates"),
    model_version: str | None = None,
    rows: int = 5000,
    random_seed: int = 42,
    thresholds: ApprovalThresholds | None = None,
) -> dict:
    validate_feature_order(ORDERED_FEATURES)
    frame = load_dataset(DatasetConfig(name=dataset, path=dataset_path), rows=rows, seed=random_seed)
    splits = temporal_split(frame)
    x_train, y_train = prepare_features(splits["train"])
    x_validation, y_validation = prepare_features(splits["validation"])
    x_test, y_test = prepare_features(splits["test"])

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=random_seed,
        n_jobs=1,
    )
    model.fit(x_train, y_train, eval_set=[(x_validation, y_validation)], verbose=False)
    booster = model.get_booster()
    booster.feature_names = ORDERED_FEATURES

    metrics = {
        "validation": metric_report(y_validation.to_numpy(), model.predict_proba(x_validation)[:, 1]),
        "test": metric_report(y_test.to_numpy(), model.predict_proba(x_test)[:, 1]),
    }
    shap_compatibility = validate_shap_compatibility(booster, x_test[ORDERED_FEATURES].head(32).to_numpy())
    provisional = build_metadata(
        model_version=model_version or f"{dataset}_xgboost_v1",
        dataset=dataset,
        random_seed=random_seed,
        split=split_summary(splits),
        metrics=metrics,
        shap_compatibility=shap_compatibility,
        approval={"approved": False, "reasons": ["pending approval gate"]},
    )
    approval = approve_model(provisional, thresholds)
    metadata = provisional | {"approval": approval}

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{metadata['model_version']}.json"
    metadata_path = output_dir / f"{metadata['model_version']}.metadata.json"
    booster.save_model(model_path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"metadata": metadata, "model_path": str(model_path), "metadata_path": str(metadata_path)}
