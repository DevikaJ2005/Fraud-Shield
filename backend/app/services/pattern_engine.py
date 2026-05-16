from collections import defaultdict, deque
from datetime import timedelta

from app.schemas.transaction import PatternFlag, TransactionRequest


class PatternEngine:
    def __init__(self) -> None:
        self._account_events: dict[str, deque[TransactionRequest]] = defaultdict(deque)
        self._device_accounts: dict[str, set[str]] = defaultdict(set)

    def evaluate(self, tx: TransactionRequest) -> list[PatternFlag]:
        events = self._account_events[tx.account_id]
        self._prune(events, tx)
        self._device_accounts[tx.device_id].add(tx.account_id)

        flags = [
            self._velocity(tx, events, timedelta(hours=1), "velocity_abuse_1h", 5),
            self._velocity(tx, events, timedelta(hours=24), "velocity_abuse_24h", 20),
            self._threshold_splitting(tx, events),
            self._device_reuse(tx),
            self._geo_anomaly(tx),
            self._round_amount_pattern(tx),
        ]
        events.append(tx)
        return flags

    @staticmethod
    def _prune(events: deque[TransactionRequest], tx: TransactionRequest) -> None:
        cutoff = tx.timestamp - timedelta(hours=24)
        while events and events[0].timestamp < cutoff:
            events.popleft()

    @staticmethod
    def _velocity(
        tx: TransactionRequest,
        events: deque[TransactionRequest],
        window: timedelta,
        name: str,
        threshold: int,
    ) -> PatternFlag:
        count = sum(1 for event in events if event.timestamp >= tx.timestamp - window)
        value = count + 1 >= threshold
        return PatternFlag(name=name, value=value, evidence=f"{count + 1} transactions in {window}")

    @staticmethod
    def _threshold_splitting(tx: TransactionRequest, events: deque[TransactionRequest]) -> PatternFlag:
        recent = [event for event in events if event.timestamp >= tx.timestamp - timedelta(hours=1)]
        near_round_threshold = 900 <= tx.amount < 1000 or 9_000 <= tx.amount < 10_000
        value = near_round_threshold and len(recent) >= 2
        return PatternFlag(name="threshold_splitting", value=value, evidence=f"{len(recent)} recent transactions near threshold")

    def _device_reuse(self, tx: TransactionRequest) -> PatternFlag:
        accounts = self._device_accounts[tx.device_id]
        value = len(accounts) >= 2
        return PatternFlag(name="device_reuse", value=value, evidence=f"device linked to {len(accounts)} accounts")

    @staticmethod
    def _geo_anomaly(tx: TransactionRequest) -> PatternFlag:
        value = tx.latitude is not None and tx.longitude is not None and abs(tx.latitude) < 0.1 and abs(tx.longitude) < 0.1
        return PatternFlag(name="geo_anomaly", value=value, evidence="coordinates near null island" if value else "no deterministic geo anomaly")

    @staticmethod
    def _round_amount_pattern(tx: TransactionRequest) -> PatternFlag:
        value = tx.amount >= 100 and tx.amount % 100 == 0
        return PatternFlag(name="round_amount_pattern", value=value, evidence=f"amount={tx.amount}")
