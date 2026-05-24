FEATURE_SCHEMA_VERSION = "v1"

ORDERED_FEATURES = [
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
]

LABEL_COLUMN = "is_fraud"
TIMESTAMP_COLUMN = "timestamp"


def validate_feature_order(features: list[str]) -> None:
    if features != ORDERED_FEATURES:
        raise ValueError("Feature ordering mismatch")
