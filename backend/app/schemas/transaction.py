from datetime import datetime, timezone
from enum import Enum
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


class TransactionRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    account_id: str = Field(min_length=1, max_length=128)
    merchant_id: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=128)
    ip_address: IPv4Address | IPv6Address
    amount: float = Field(gt=0, le=1_000_000)
    timestamp: datetime
    is_mobile: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class PatternFlag(BaseModel):
    name: str
    value: bool
    evidence: str


class ShapExplanation(BaseModel):
    feature: str
    value: float | int | bool
    shap_value: float
    direction: str


class GraphAnalysis(BaseModel):
    graph_degree: int = 0
    clustering_coefficient: float = 0.0
    ring_detected: bool = False
    shared_device_detected: bool = False
    shared_ip_detected: bool = False
    suspicious_cluster_detected: bool = False
    shared_entities: list[str] = Field(default_factory=list)
    risk_propagation_score: float = 0.0


class GraphRelationship(BaseModel):
    node_id: str
    node_type: str
    edge_type: str
    connected_node_id: str
    connected_node_type: str
    timestamp: datetime


class PredictionResponse(BaseModel):
    transaction_id: str
    fraud_probability: float
    confidence: float
    severity: Severity | None
    model_version: str
    feature_schema_version: str
    patterns: list[PatternFlag]
    graph: GraphAnalysis
    shap_explanation: list[ShapExplanation]
    narration: str


class FeedbackRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    corrected_label: bool
    notes: str | None = Field(default=None, max_length=2000)


class TransactionSummary(BaseModel):
    transaction_id: str
    account_id: str
    merchant_id: str
    amount: float
    occurred_at: datetime
    fraud_probability: float | None = None
    confidence: float | None = None
    severity: Severity | None = None
    model_version: str
    feature_schema_version: str
