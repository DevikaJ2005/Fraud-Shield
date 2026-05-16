from datetime import datetime, timedelta, timezone

from app.schemas.transaction import TransactionRequest
from app.services.graph_engine import GraphEngine


def tx(transaction_id: str, account_id: str, device_id: str, ip_address: str, timestamp: datetime) -> TransactionRequest:
    return TransactionRequest(
        transaction_id=transaction_id,
        account_id=account_id,
        merchant_id="merchant-test",
        device_id=device_id,
        ip_address=ip_address,
        amount=1000,
        timestamp=timestamp,
        is_mobile=True,
    )


def test_graph_ring_detection_shared_device_and_ip() -> None:
    engine = GraphEngine()
    now = datetime.now(timezone.utc)

    engine.add_transaction(tx("ring-1", "account-a", "shared-device", "10.0.0.1", now))
    graph = engine.add_transaction(tx("ring-2", "account-b", "shared-device", "10.0.0.1", now))

    assert graph.ring_detected is True
    assert graph.shared_device_detected is True
    assert graph.shared_ip_detected is True
    assert engine.integrity_report()["duplicate_edges_detected"] is False
    assert engine.integrity_report()["latest_relationships_match_runtime"] is True


def test_graph_prunes_rolling_seven_day_window() -> None:
    engine = GraphEngine()
    old = datetime.now(timezone.utc) - timedelta(days=8)
    now = datetime.now(timezone.utc)

    engine.add_transaction(tx("old", "old-account", "old-device", "10.0.0.2", old))
    engine.add_transaction(tx("new", "new-account", "new-device", "10.0.0.3", now))

    node_ids = {node["id"] for node in engine.current_payload()["nodes"]}
    assert "account:old-account" not in node_ids
    assert "account:new-account" in node_ids
