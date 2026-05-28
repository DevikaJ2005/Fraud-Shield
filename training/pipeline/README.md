# FraudShield Training Pipeline

Governed XGBoost training for FraudShield. The pipeline preserves the backend
feature schema and never deploys a model automatically.

## Run

```bash
python -m training.pipeline.cli --dataset demo_paysim --output-dir training/artifacts/candidates
```

External datasets:

```bash
python -m training.pipeline.cli --dataset creditcard --dataset-path /kaggle/input/creditcard.csv --output-dir /kaggle/working/fraudshield-models
python -m training.pipeline.cli --dataset paysim --dataset-path /kaggle/input/paysim.csv --output-dir /kaggle/working/fraudshield-models
```

## Governance

Every candidate produces:

- XGBoost native JSON model artifact
- metadata JSON with schema version, ordered features, temporal split, metrics,
  SHAP compatibility, and approval result

Approval rejects candidates with schema/order drift, SHAP incompatibility, or
metrics below gate thresholds. Approved artifacts can be registered in the
existing `model_registry` table, but activation and deployment remain explicit
operator actions.

## Hugging Face Registry

Approved candidates can be uploaded manually:

```bash
python -m training.pipeline.cli \
  --dataset demo_paysim \
  --output-dir /kaggle/working/fraudshield-models \
  --model-version fraudshield_xgboost_YYYYMMDD \
  --upload-approved \
  --hf-repo DevikaJ2005/fraudshield-models \
  --hf-token "$HF_TOKEN"
```

This uploads the model JSON, metadata JSON, and metrics JSON. It does not
activate the model in production. Runtime activation is a separate authenticated
backend operation that downloads, validates, and swaps the model only if all
governance checks pass.
