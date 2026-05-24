from datetime import datetime, timedelta, timezone
import logging

import networkx as nx

from app.schemas.transaction import GraphAnalysis, GraphRelationship, TransactionRequest

logger = logging.getLogger(__name__)


class GraphEngine:
    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._created_at = datetime.now(timezone.utc)
        self._latest_relationships: list[GraphRelationship] = []

    def add_transaction(self, tx: TransactionRequest) -> GraphAnalysis:
        self._reset_if_due(tx.timestamp)
        self._prune(tx.timestamp)

        account = f"account:{tx.account_id}"
        device = f"device:{tx.device_id}"
        merchant = f"merchant:{tx.merchant_id}"
        ip_address = f"ip:{tx.ip_address}"
        transaction = f"transaction:{tx.transaction_id}"

        self._graph.add_node(account, type="account", last_seen=tx.timestamp)
        self._graph.add_node(device, type="device", last_seen=tx.timestamp)
        self._graph.add_node(merchant, type="merchant", last_seen=tx.timestamp)
        self._graph.add_node(ip_address, type="ip", last_seen=tx.timestamp)
        self._graph.add_node(transaction, type="transaction", last_seen=tx.timestamp)

        edge_rows = [
            (account, "account", "account_transaction", transaction, "transaction"),
            (transaction, "transaction", "transaction_merchant", merchant, "merchant"),
            (account, "account", "account_device", device, "device"),
            (device, "device", "device_account", account, "account"),
            (account, "account", "account_ip", ip_address, "ip"),
            (ip_address, "ip", "ip_account", account, "account"),
        ]
        new_edge_rows = []
        for source, source_type, edge_type, target, target_type in edge_rows:
            if not self._graph.has_edge(source, target):
                new_edge_rows.append((source, source_type, edge_type, target, target_type))
            self._graph.add_edge(source, target, type=edge_type)
        self._latest_relationships = self._relationships(tx, new_edge_rows)

        undirected = self._graph.to_undirected()
        component_nodes = nx.node_connected_component(undirected, account)
        ring_detected, shared_entities = self._detect_ring(component_nodes)
        shared_device = any(node.startswith("device:") for node in shared_entities)
        shared_ip = any(node.startswith("ip:") for node in shared_entities)
        suspicious_cluster = len(component_nodes) >= 8 and (shared_device or shared_ip)
        degree = int(self._graph.degree(account))
        cluster = nx.clustering(undirected, account) if account in undirected else 0.0

        if ring_detected:
            logger.info(
                "fraud_ring_detected",
                extra={
                    "transaction_id": tx.transaction_id,
                    "ring_detected": True,
                    "severity": "HIGH",
                },
            )

        return GraphAnalysis(
            graph_degree=degree,
            clustering_coefficient=round(float(cluster), 4),
            ring_detected=ring_detected,
            shared_device_detected=shared_device,
            shared_ip_detected=shared_ip,
            suspicious_cluster_detected=suspicious_cluster,
            shared_entities=shared_entities,
            risk_propagation_score=self._risk_propagation(component_nodes),
        )

    def latest_relationships(self) -> list[GraphRelationship]:
        return self._latest_relationships

    def integrity_report(self) -> dict:
        edge_keys = [(source, target, data.get("type")) for source, target, data in self._graph.edges(data=True)]
        latest_keys = {
            (item.node_id, item.connected_node_id, item.edge_type)
            for item in self._latest_relationships
        }
        runtime_keys = set(edge_keys)
        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "duplicate_edges_detected": len(edge_keys) != len(runtime_keys),
            "latest_relationships_match_runtime": latest_keys.issubset(runtime_keys),
            "latest_relationship_count": len(self._latest_relationships),
        }

    def current_payload(self, max_nodes: int = 500) -> dict:
        nodes = list(self._graph.nodes(data=True))[:max_nodes]
        allowed = {node for node, _ in nodes}
        links = [
            {"source": source, "target": target, "type": data.get("type", "related")}
            for source, target, data in self._graph.edges(data=True)
            if source in allowed and target in allowed
        ]
        return {
            "nodes": [{"id": node, "type": data.get("type", "unknown")} for node, data in nodes],
            "links": links,
            "truncated": self._graph.number_of_nodes() > max_nodes,
        }

    def _detect_ring(self, component_nodes: set[str]) -> tuple[bool, list[str]]:
        if len(component_nodes) < 3:
            return False, []
        account_count = sum(1 for node in component_nodes if node.startswith("account:"))
        shared = [
            node
            for node in component_nodes
            if node.startswith(("device:", "ip:")) and self._graph.degree(node) >= 2
        ]
        return account_count >= 2 and bool(shared), shared

    @staticmethod
    def _risk_propagation(component_nodes: set[str]) -> float:
        return min(1.0, len(component_nodes) / 25)

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(days=7)
        stale = [
            node
            for node, data in self._graph.nodes(data=True)
            if data.get("last_seen", now) < cutoff
        ]
        self._graph.remove_nodes_from(stale)
        if stale:
            logger.info("graph_pruned", extra={"transaction_id": "", "ring_detected": False, "severity": "", "fraud_probability": None, "model_version": ""})

    def _reset_if_due(self, now: datetime) -> None:
        if now - self._created_at >= timedelta(hours=24):
            self._graph.clear()
            self._created_at = now

    @staticmethod
    def _relationships(
        tx: TransactionRequest,
        rows: list[tuple[str, str, str, str, str]],
    ) -> list[GraphRelationship]:
        return [
            GraphRelationship(
                node_id=node_id,
                node_type=node_type,
                edge_type=edge_type,
                connected_node_id=connected_node_id,
                connected_node_type=connected_node_type,
                timestamp=tx.timestamp,
            )
            for node_id, node_type, edge_type, connected_node_id, connected_node_type in rows
        ]
