import logging
import json
import time
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from supabase import Client, create_client

from app.core.config import get_settings
from app.schemas.transaction import FeedbackRequest, GraphRelationship, PredictionResponse, TransactionRequest

logger = logging.getLogger(__name__)


class DatabaseService:
    REQUIRED_TABLES = (
        "transactions",
        "feedback",
        "model_registry",
        "graph_features",
        "graph_relationships",
        "alerts",
        "fraud_patterns",
    )
    REQUIRED_COLUMNS = {
        "transactions": (
            "transaction_id",
            "account_id",
            "merchant_id",
            "device_id",
            "ip_address",
            "amount",
            "occurred_at",
            "fraud_probability",
            "confidence",
            "severity",
            "shap_explanations",
            "graph_features",
            "model_version",
            "feature_schema_version",
            "created_at",
        ),
        "feedback": ("transaction_id", "corrected_label", "notes", "created_at"),
        "model_registry": (
            "model_version",
            "feature_schema_version",
            "ordered_features",
            "feature_count",
            "preprocessing_config",
            "metrics",
            "is_active",
            "deployed_at",
            "created_at",
        ),
        "graph_features": (
            "transaction_id",
            "graph_degree",
            "clustering_coefficient",
            "ring_detected",
            "shared_entities",
            "created_at",
        ),
        "graph_relationships": (
            "node_id",
            "node_type",
            "edge_type",
            "connected_node_id",
            "connected_node_type",
            "observed_at",
            "created_at",
        ),
        "alerts": (
            "id",
            "transaction_id",
            "severity",
            "notification_state",
            "acknowledged_at",
            "created_at",
        ),
        "fraud_patterns": ("source", "title", "summary", "evidence", "created_at"),
    }

    def __init__(self) -> None:
        self._client: Client | None = None
        self._available = False
        self._last_error: str | None = None
        self._missing_tables: list[str] = []
        self._migration_compatible = False
        self._runtime_transactions: list[dict] = []
        self._runtime_alerts: list[dict] = []
        self._runtime_feedback: list[dict] = []

    def client(self) -> Client | None:
        if self._client is not None:
            return self._client
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            self._available = False
            self._last_error = "Supabase environment variables are not configured"
            return None
        if not self._validate_supabase_settings(settings.supabase_url, settings.supabase_service_role_key):
            return None
        try:
            self._client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.warning("Supabase client initialization failed: %s", exc)
            return None
        return self._client

    def verify_connection(self) -> dict[str, Any]:
        settings = get_settings()
        logger.info(
            "supabase_env_detected",
            extra={
                "transaction_id": "",
                "model_version": "",
                "fraud_probability": None,
                "severity": "",
                "ring_detected": False,
                "supabase_url_detected": bool(settings.supabase_url),
                "supabase_service_role_key_detected": bool(settings.supabase_service_role_key),
            },
        )
        client = self.client()
        if client is None:
            logger.warning("Supabase unavailable: %s", self._last_error)
            return self.status()

        table_status: dict[str, bool] = {}
        missing_tables: list[str] = []
        try:
            self._rest_health_check()
            for table in self.REQUIRED_TABLES:
                columns = ",".join(self.REQUIRED_COLUMNS[table])
                try:
                    client.table(table).select(columns).limit(1).execute()
                    table_status[table] = True
                except Exception:
                    table_status[table] = False
                    missing_tables.append(table)
            self._available = True
            self._missing_tables = missing_tables
            self._migration_compatible = not missing_tables
            self._last_error = None if self._migration_compatible else f"Missing or incompatible tables: {', '.join(missing_tables)}"
            logger.info(
                "Supabase connectivity verified",
                extra={
                    "transaction_id": "",
                    "model_version": "",
                    "fraud_probability": None,
                    "severity": "",
                    "ring_detected": False,
                },
            )
            return self.status() | {"tables": table_status}
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            self._migration_compatible = False
            logger.warning(
                "Supabase connectivity verification failed: %s",
                exc,
                extra={
                    "transaction_id": "",
                    "model_version": "",
                    "fraud_probability": None,
                    "severity": "",
                    "ring_detected": False,
                },
            )
            return self.status() | {"tables": table_status}

    def status(self) -> dict[str, Any]:
        return {
            "available": self._available,
            "runtime_cache_active": not self._available or not self._migration_compatible,
            "migration_compatible": self._migration_compatible,
            "missing_tables": self._missing_tables,
            "error": self._last_error,
        }

    def storage_status(self) -> dict[str, Any]:
        if not self._available:
            self.verify_connection()
        status = self.status()
        return {
            "supabase_connected": status["available"],
            "runtime_cache_active": status["runtime_cache_active"],
            "migration_compatible": status["migration_compatible"],
            "missing_tables": status["missing_tables"],
            "last_db_error": status["error"],
            "runtime_transactions": len(self._runtime_transactions),
            "runtime_alerts": len(self._runtime_alerts),
            "runtime_feedback": len(self._runtime_feedback),
        }

    async def persist_prediction(self, tx: TransactionRequest, response: PredictionResponse) -> None:
        self._cache_prediction(tx, response)
        client = self.client()
        if client is None:
            logger.warning("Supabase is not configured; prediction was not persisted")
            return
        try:
            client.table("transactions").upsert(
                self._transaction_row(tx, response),
                on_conflict="transaction_id",
            ).execute()
            self._verify_transaction_row(tx.transaction_id, response)

            client.table("graph_features").insert(self._graph_feature_row(tx, response)).execute()
            self._verify_graph_feature_row(tx.transaction_id, response)

            if response.severity is not None:
                logger.info(
                    "alert_created",
                    extra={
                        "transaction_id": tx.transaction_id,
                        "severity": response.severity.value,
                        "fraud_probability": response.fraud_probability,
                        "model_version": response.model_version,
                        "ring_detected": response.graph.ring_detected,
                    },
                )
                alert_result = client.table("alerts").insert(
                    {
                        "transaction_id": tx.transaction_id,
                        "severity": response.severity.value,
                        "notification_state": "pending",
                    }
                ).execute()
                if not alert_result.data:
                    raise RuntimeError("Alert insert did not return inserted row")
                self._verify_alert_row(str(alert_result.data[0]["id"]), tx.transaction_id, response.severity.value)
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to persist prediction for transaction %s", tx.transaction_id)

    async def persist_graph_relationships(self, relationships: list[GraphRelationship]) -> None:
        client = self.client()
        if client is None or not relationships:
            return
        try:
            rows = [self._graph_relationship_row(item) for item in relationships]
            result = client.table("graph_relationships").insert(rows).execute()
            if len(result.data or []) != len(rows):
                raise RuntimeError("Graph relationship insert verification failed")
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to persist graph relationships")

    async def persist_feedback(self, feedback: FeedbackRequest) -> None:
        self._cache_feedback(feedback)
        client = self.client()
        if client is None:
            logger.warning("Supabase is not configured; feedback was stored in runtime cache")
            return
        try:
            result = client.table("feedback").insert(feedback.model_dump()).execute()
            if not result.data:
                raise RuntimeError("Feedback insert did not return inserted row")
            stored = result.data[0]
            if stored.get("transaction_id") != feedback.transaction_id or stored.get("corrected_label") != feedback.corrected_label:
                raise RuntimeError("Feedback read-back verification failed")
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to persist feedback for transaction %s; using runtime cache", feedback.transaction_id)

    def recent_transactions(self, limit: int = 50) -> list[dict]:
        client = self.client()
        if client is None:
            return self._runtime_transactions[:limit]
        try:
            result = (
                client.table("transactions")
                .select("transaction_id,account_id,merchant_id,amount,occurred_at,fraud_probability,confidence,severity,model_version,feature_schema_version")
                .order("occurred_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to query recent transactions; using runtime cache")
            return self._runtime_transactions[:limit]

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        client = self.client()
        if client is None:
            return self._runtime_alerts[:limit]
        try:
            result = client.table("alerts").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to query recent alerts; using runtime cache")
            return self._runtime_alerts[:limit]

    def fraud_intelligence(self, limit: int = 25) -> list[dict]:
        client = self.client()
        if client is None:
            return []
        try:
            result = client.table("fraud_patterns").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to query fraud intelligence")
            return []

    def register_active_model(self, model_path: str | None) -> None:
        client = self.client()
        if client is None or not model_path:
            return
        if not self._available or not self._migration_compatible:
            logger.warning("Skipping model registry write because Supabase is unavailable or migration-incompatible")
            return
        settings = get_settings()
        metadata_path = settings.resolve_project_path(settings.model_metadata_path) if settings.model_metadata_path else None
        if metadata_path is None:
            resolved_model_path = settings.resolve_project_path(model_path)
            metadata_path = resolved_model_path.with_suffix(".metadata.json") if resolved_model_path else None
        if metadata_path is None:
            return
        if not metadata_path.exists():
            return
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            client.table("model_registry").upsert(
                {
                    "model_version": metadata["model_version"],
                    "feature_schema_version": metadata["feature_schema_version"],
                    "ordered_features": metadata["ordered_features"],
                    "feature_count": metadata["feature_count"],
                    "preprocessing_config": {
                        "mode": metadata.get("mode"),
                        "dataset": metadata.get("dataset"),
                        "random_seed": metadata.get("random_seed"),
                        "split": metadata.get("split"),
                        "baselines": metadata.get("baselines"),
                    },
                    "metrics": metadata["metrics"],
                    "is_active": True,
                },
                on_conflict="model_version",
            ).execute()
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to register active model")

    def register_model_metadata(self, metadata: dict, activate: bool = True) -> None:
        client = self.client()
        if client is None:
            return
        if not self._available or not self._migration_compatible:
            logger.warning("Skipping model metadata registry write because Supabase is unavailable or migration-incompatible")
            return
        try:
            if activate:
                client.table("model_registry").update({"is_active": False}).eq("is_active", True).execute()
            client.table("model_registry").upsert(
                {
                    "model_version": metadata["model_version"],
                    "feature_schema_version": metadata["feature_schema_version"],
                    "ordered_features": metadata["ordered_features"],
                    "feature_count": metadata["feature_count"],
                    "preprocessing_config": {
                        "mode": metadata.get("mode"),
                        "dataset": metadata.get("dataset"),
                        "random_seed": metadata.get("random_seed"),
                        "split": metadata.get("split"),
                        "shap_compatibility": metadata.get("shap_compatibility"),
                        "approval": metadata.get("approval"),
                    },
                    "metrics": metadata["metrics"],
                    "is_active": activate,
                    "deployed_at": datetime.now(timezone.utc).isoformat() if activate else None,
                },
                on_conflict="model_version",
            ).execute()
            logger.info(
                "model_registry_updated",
                extra={
                    "transaction_id": "",
                    "model_version": metadata["model_version"],
                    "fraud_probability": None,
                    "severity": "",
                    "ring_detected": False,
                },
            )
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to register model metadata")

    def _cache_prediction(self, tx: TransactionRequest, response: PredictionResponse) -> None:
        self._runtime_transactions.insert(
            0,
            {
                "transaction_id": tx.transaction_id,
                "account_id": tx.account_id,
                "merchant_id": tx.merchant_id,
                "amount": tx.amount,
                "occurred_at": tx.timestamp.isoformat(),
                "fraud_probability": response.fraud_probability,
                "confidence": response.confidence,
                "severity": response.severity.value if response.severity else None,
                "model_version": response.model_version,
                "feature_schema_version": response.feature_schema_version,
            },
        )
        self._runtime_transactions = self._runtime_transactions[:100]
        if response.severity is not None:
            logger.info(
                "alert_created_runtime",
                extra={
                    "transaction_id": tx.transaction_id,
                    "severity": response.severity.value,
                    "fraud_probability": response.fraud_probability,
                    "model_version": response.model_version,
                    "ring_detected": response.graph.ring_detected,
                },
            )
            self._runtime_alerts.insert(
                0,
                {
                    "id": f"runtime-{tx.transaction_id}",
                    "transaction_id": tx.transaction_id,
                    "severity": response.severity.value,
                    "notification_state": "pending",
                    "created_at": tx.timestamp.isoformat(),
                },
            )
            self._runtime_alerts = self._runtime_alerts[:100]

    def _cache_feedback(self, feedback: FeedbackRequest) -> None:
        self._runtime_feedback.insert(
            0,
            {
                "transaction_id": feedback.transaction_id,
                "corrected_label": feedback.corrected_label,
                "notes": feedback.notes,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._runtime_feedback = self._runtime_feedback[:100]

    def acknowledge_alert(self, alert_id: str) -> dict | None:
        acknowledged_at = datetime.now(timezone.utc).isoformat()
        client = self.client()
        if client is None:
            return self._acknowledge_runtime_alert(alert_id, acknowledged_at)

        try:
            query = client.table("alerts").update(
                {
                    "notification_state": "acknowledged",
                    "acknowledged_at": acknowledged_at,
                }
            )
            if alert_id.isdigit():
                result = query.eq("id", int(alert_id)).execute()
            else:
                result = query.eq("id", alert_id).execute()
            if result.data:
                return result.data[0]
            return self._acknowledge_runtime_alert(alert_id, acknowledged_at)
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            logger.exception("Failed to acknowledge alert %s; using runtime cache", alert_id)
            return self._acknowledge_runtime_alert(alert_id, acknowledged_at)

    def _acknowledge_runtime_alert(self, alert_id: str, acknowledged_at: str) -> dict | None:
        for alert in self._runtime_alerts:
            if str(alert["id"]) == str(alert_id):
                alert["notification_state"] = "acknowledged"
                alert["acknowledged_at"] = acknowledged_at
                return alert
        return None

    @staticmethod
    def _transaction_row(tx: TransactionRequest, response: PredictionResponse) -> dict:
        return {
            "transaction_id": tx.transaction_id,
            "account_id": tx.account_id,
            "merchant_id": tx.merchant_id,
            "device_id": tx.device_id,
            "ip_address": str(tx.ip_address),
            "amount": tx.amount,
            "occurred_at": tx.timestamp.isoformat(),
            "fraud_probability": response.fraud_probability,
            "confidence": response.confidence,
            "severity": response.severity.value if response.severity else None,
            "shap_explanations": [item.model_dump() for item in response.shap_explanation],
            "graph_features": response.graph.model_dump(),
            "model_version": response.model_version,
            "feature_schema_version": response.feature_schema_version,
        }

    @staticmethod
    def _graph_feature_row(tx: TransactionRequest, response: PredictionResponse) -> dict:
        return {
            "transaction_id": tx.transaction_id,
            "graph_degree": response.graph.graph_degree,
            "clustering_coefficient": response.graph.clustering_coefficient,
            "ring_detected": response.graph.ring_detected,
            "shared_entities": response.graph.shared_entities,
        }

    @staticmethod
    def _graph_relationship_row(item: GraphRelationship) -> dict:
        return {
            "node_id": item.node_id,
            "node_type": item.node_type,
            "edge_type": item.edge_type,
            "connected_node_id": item.connected_node_id,
            "connected_node_type": item.connected_node_type,
            "observed_at": item.timestamp.isoformat(),
        }

    def _verify_transaction_row(self, transaction_id: str, response: PredictionResponse) -> None:
        client = self.client()
        if client is None:
            return
        result = (
            client.table("transactions")
            .select("transaction_id,fraud_probability,model_version,feature_schema_version")
            .eq("transaction_id", transaction_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RuntimeError("Transaction read-back verification failed")
        stored = result.data[0]
        if stored.get("transaction_id") != transaction_id or stored.get("model_version") != response.model_version:
            raise RuntimeError("Transaction persisted values do not match runtime values")

    def _verify_graph_feature_row(self, transaction_id: str, response: PredictionResponse) -> None:
        client = self.client()
        if client is None:
            return
        result = (
            client.table("graph_features")
            .select("transaction_id,graph_degree,ring_detected")
            .eq("transaction_id", transaction_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RuntimeError("Graph feature read-back verification failed")
        stored = result.data[0]
        if stored.get("graph_degree") != response.graph.graph_degree or stored.get("ring_detected") != response.graph.ring_detected:
            raise RuntimeError("Graph feature persisted values do not match runtime values")

    def _verify_alert_row(self, alert_id: str, transaction_id: str, severity: str) -> None:
        client = self.client()
        if client is None:
            return
        result = client.table("alerts").select("id,transaction_id,severity").eq("id", alert_id).limit(1).execute()
        if not result.data:
            raise RuntimeError("Alert read-back verification failed")
        stored = result.data[0]
        if stored.get("transaction_id") != transaction_id or stored.get("severity") != severity:
            raise RuntimeError("Alert persisted values do not match runtime values")

    def _validate_supabase_settings(self, supabase_url: str, service_role_key: str) -> bool:
        parsed = urlparse(supabase_url)
        if parsed.scheme != "https" or not parsed.netloc:
            self._available = False
            self._last_error = "Supabase URL must be an HTTPS URL"
            logger.warning("Invalid Supabase URL format")
            return False
        if len(service_role_key.split(".")) != 3:
            self._available = False
            self._last_error = "Supabase service role key must be a JWT-like token"
            logger.warning("Invalid Supabase service role key format")
            return False
        return True

    def _rest_health_check(self, attempts: int = 3, timeout_seconds: float = 8.0) -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase environment variables are not configured")
        url = settings.supabase_url.rstrip("/") + "/rest/v1/"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=timeout_seconds) as http_client:
                    response = http_client.get(url, headers=headers)
                    response.raise_for_status()
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Supabase REST health check failed on attempt %s: %s",
                    attempt,
                    exc,
                    extra={
                        "transaction_id": "",
                        "model_version": "",
                        "fraud_probability": None,
                        "severity": "",
                        "ring_detected": False,
                    },
                )
                time.sleep(0.5 * attempt)
        raise RuntimeError(f"Supabase REST health check failed after {attempts} attempts: {last_error}")
