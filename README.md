# FraudShield

Cloud-native fraud graph intelligence platform aligned with the FraudShield v6.0 PRD.

## Architecture

- Backend: FastAPI, Pydantic v2, XGBoost, SHAP, NetworkX
- Frontend: React 18, TypeScript, Vite, Tailwind, TanStack Query, D3, Recharts
- Database: Supabase PostgreSQL
- Model storage: Hugging Face Hub
- Training: Kaggle Notebooks triggered from GitHub Actions
- Workflows: n8n

## Non-Negotiables

- Fraud decisions come only from deterministic rules, graph features, XGBoost, and SHAP.
- LLMs may narrate existing evidence only.
- No local persistent storage, local cron, local model training, Redis, Kafka, Celery, or WebSockets in v1.
- Production models use XGBoost native JSON or Booster binary, never arbitrary pickle blobs.

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
pip install -r ../requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Local development may run the API and UI, but production operation must remain cloud-only.
