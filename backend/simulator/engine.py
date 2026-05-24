from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import random
from typing import Any

import httpx
from fastapi import FastAPI

from app.core.config import get_settings
from app.schemas.transaction import TransactionRequest

logger = logging.getLogger(__name__)


SCENARIOS = (
    "normal_payment",
    "wallet_transfer",
    "p2p_transfer",
    "merchant_payment",
    "cashout_pattern",
    "repeated_transfer",
    "velocity_abuse",
    "shared_device_fraud",
    "shared_ip_fraud",
    "fraud_ring",
    "mule_account",
    "account_takeover",
)


@dataclass
class SimulatorMetrics:
    running: bool = False
    generated_count: int = 0
    fraud_count: int = 0
    failed_count: int = 0
    last_transaction_id: str | None = None
    last_scenario: str | None = None
    last_error: str | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    recent_scenarios: list[str] = field(default_factory=list)


class TransactionGenerator:
    def __init__(self, seed: int = 20260524) -> None:
        self._random = random.Random(seed)
        self._sequence = 0
        self._normal_accounts = [f"acct-{index:04d}" for index in range(1, 81)]
        self._mule_accounts = [f"mule-{index:03d}" for index in range(1, 11)]
        self._merchants = [f"merchant-{index:03d}" for index in range(1, 31)]
        self._cashout_merchants = [f"cashout-atm-{index:02d}" for index in range(1, 6)]
        self._devices = [f"device-{index:04d}" for index in range(1, 71)]
        self._ips = [f"198.51.100.{index}" for index in range(10, 180)]
        self._ring_devices = [f"ring-device-{index:02d}" for index in range(1, 5)]
        self._ring_ips = [f"203.0.113.{index}" for index in range(40, 48)]
        self._ato_devices = [f"ato-device-{index:02d}" for index in range(1, 6)]

    def next(self) -> tuple[TransactionRequest, str, bool]:
        self._sequence += 1
        scenario = self._choose_scenario()
        payload = getattr(self, f"_{scenario}")()
        tx = TransactionRequest(
            transaction_id=f"sim-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._sequence:06d}",
            timestamp=datetime.now(timezone.utc),
            is_mobile=self._random.random() < 0.72,
            **payload,
        )
        return tx, scenario, scenario not in {
            "normal_payment",
            "wallet_transfer",
            "p2p_transfer",
            "merchant_payment",
            "repeated_transfer",
        }

    def _choose_scenario(self) -> str:
        phase = (self._sequence // 25) % 6
        spike = phase in {2, 5}
        roll = self._random.random()
        if spike and roll < 0.34:
            return self._random.choice(("velocity_abuse", "fraud_ring", "mule_account", "account_takeover"))
        if roll < 0.72:
            return self._random.choice(("normal_payment", "wallet_transfer", "p2p_transfer", "merchant_payment"))
        if roll < 0.88:
            return self._random.choice(("cashout_pattern", "repeated_transfer"))
        return self._random.choice(("velocity_abuse", "shared_device_fraud", "shared_ip_fraud", "fraud_ring", "mule_account", "account_takeover"))

    def _normal_payment(self) -> dict[str, Any]:
        return self._base(
            account=self._random.choice(self._normal_accounts),
            merchant=self._random.choice(self._merchants),
            amount=self._money(8, 220),
        )

    def _wallet_transfer(self) -> dict[str, Any]:
        return self._base(
            account=self._random.choice(self._normal_accounts),
            merchant=f"wallet-{self._random.randint(1, 12):02d}",
            amount=self._money(20, 650),
        )

    def _p2p_transfer(self) -> dict[str, Any]:
        return self._base(
            account=self._random.choice(self._normal_accounts),
            merchant=f"p2p-{self._random.choice(self._normal_accounts)}",
            amount=self._money(15, 450),
        )

    def _merchant_payment(self) -> dict[str, Any]:
        return self._base(
            account=self._random.choice(self._normal_accounts),
            merchant=f"merchant-premium-{self._random.randint(1, 10):02d}",
            amount=self._money(50, 1800),
        )

    def _cashout_pattern(self) -> dict[str, Any]:
        return self._base(
            account=self._random.choice(self._normal_accounts + self._mule_accounts),
            merchant=self._random.choice(self._cashout_merchants),
            amount=float(self._random.choice((1000, 2000, 3000, 5000, 7500))),
        )

    def _repeated_transfer(self) -> dict[str, Any]:
        account = self._normal_accounts[self._sequence % len(self._normal_accounts)]
        return self._base(account=account, merchant=f"p2p-repeat-{account}", amount=float(self._random.choice((99, 199, 499, 999))))

    def _velocity_abuse(self) -> dict[str, Any]:
        account = self._mule_accounts[self._sequence % len(self._mule_accounts)]
        return self._base(
            account=account,
            merchant="wallet-rapid-cashout",
            amount=float(self._random.choice((2500, 4900, 9900, 14900))),
            device=f"velocity-device-{self._sequence % 3}",
            ip=f"203.0.113.{70 + (self._sequence % 3)}",
        )

    def _shared_device_fraud(self) -> dict[str, Any]:
        return self._base(
            account=f"acct-shared-device-{self._sequence % 9}",
            merchant=self._random.choice(self._merchants),
            amount=self._money(1200, 12000),
            device=self._ring_devices[self._sequence % len(self._ring_devices)],
        )

    def _shared_ip_fraud(self) -> dict[str, Any]:
        return self._base(
            account=f"acct-shared-ip-{self._sequence % 12}",
            merchant=f"merchant-risk-{self._sequence % 5}",
            amount=self._money(800, 9000),
            ip=self._ring_ips[self._sequence % len(self._ring_ips)],
        )

    def _fraud_ring(self) -> dict[str, Any]:
        ring = self._sequence % 4
        return self._base(
            account=f"ring-{ring}-acct-{self._sequence % 8}",
            merchant=f"ring-{ring}-merchant-{self._sequence % 3}",
            amount=float(self._random.choice((4999, 9999, 14999, 19999))),
            device=self._ring_devices[ring],
            ip=self._ring_ips[ring],
        )

    def _mule_account(self) -> dict[str, Any]:
        mule = self._mule_accounts[self._sequence % len(self._mule_accounts)]
        return self._base(
            account=mule,
            merchant=self._random.choice(self._cashout_merchants),
            amount=float(self._random.choice((5000, 10000, 15000, 25000))),
            device=f"mule-device-{self._sequence % 4}",
            ip=f"203.0.113.{90 + (self._sequence % 6)}",
        )

    def _account_takeover(self) -> dict[str, Any]:
        account = self._normal_accounts[self._sequence % len(self._normal_accounts)]
        return self._base(
            account=account,
            merchant="merchant-new-device-high-value",
            amount=self._money(6000, 28000),
            device=self._ato_devices[self._sequence % len(self._ato_devices)],
            ip=f"203.0.113.{110 + (self._sequence % 8)}",
        )

    def _base(
        self,
        account: str,
        merchant: str,
        amount: float,
        device: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        return {
            "account_id": account,
            "merchant_id": merchant,
            "device_id": device or self._devices[self._sequence % len(self._devices)],
            "ip_address": ip or self._ips[self._sequence % len(self._ips)],
            "amount": round(amount, 2),
            "latitude": round(self._random.uniform(8.0, 28.0), 6),
            "longitude": round(self._random.uniform(72.0, 88.0), 6),
        }

    def _money(self, minimum: float, maximum: float) -> float:
        return self._random.uniform(minimum, maximum)


class TransactionSimulator:
    def __init__(self) -> None:
        self._app: FastAPI | None = None
        self._task: asyncio.Task[None] | None = None
        self._generator = TransactionGenerator()
        self._metrics = SimulatorMetrics()
        self._lock = asyncio.Lock()

    def configure(self, app: FastAPI) -> None:
        self._app = app

    async def start(self) -> dict[str, Any]:
        if self._app is None:
            raise RuntimeError("Simulator is not configured with a FastAPI app")
        settings = get_settings()
        if self._auth_required(settings) and not settings.simulator_api_key:
            self._metrics.running = False
            self._metrics.last_error = "SIMULATOR_API_KEY is required when API_KEY_HASHES is configured"
            self._log("simulator_start_rejected")
            return self.status()
        async with self._lock:
            if self._task is not None and not self._task.done():
                return self.status()
            self._metrics.running = True
            self._metrics.started_at = datetime.now(timezone.utc).isoformat()
            self._metrics.stopped_at = None
            self._metrics.last_error = None
            self._task = asyncio.create_task(self._run(), name="fraudshield-transaction-simulator")
            self._log("simulator_started")
            return self.status()

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            task = self._task
            self._task = None
            self._metrics.running = False
            self._metrics.stopped_at = datetime.now(timezone.utc).isoformat()
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._log("simulator_stopped")
        return self.status()

    def status(self) -> dict[str, Any]:
        task_alive = self._task is not None and not self._task.done()
        return {
            "running": self._metrics.running and task_alive,
            "generated_count": self._metrics.generated_count,
            "fraud_count": self._metrics.fraud_count,
            "failed_count": self._metrics.failed_count,
            "last_transaction_id": self._metrics.last_transaction_id,
            "last_scenario": self._metrics.last_scenario,
            "last_error": self._metrics.last_error,
            "started_at": self._metrics.started_at,
            "stopped_at": self._metrics.stopped_at,
            "recent_scenarios": self._metrics.recent_scenarios[-12:],
            "traffic_interval_seconds": self._intervals(),
            "scenario_catalog": list(SCENARIOS),
        }

    async def _run(self) -> None:
        settings = get_settings()
        headers = {"X-API-Key": settings.simulator_api_key} if settings.simulator_api_key else {}
        transport = httpx.ASGITransport(app=self._app, client=("simulator", 0))  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://fraudshield.internal", timeout=20.0) as client:
            while True:
                try:
                    tx, scenario, fraud_like = self._generator.next()
                    response = await client.post("/api/v1/predict", json=tx.model_dump(mode="json"), headers=headers)
                    response.raise_for_status()
                    payload = response.json()
                    self._record_success(tx.transaction_id, scenario, fraud_like or bool(payload.get("severity")))
                    if payload.get("graph", {}).get("ring_detected"):
                        self._log("simulator_ring_generated", tx.transaction_id, scenario)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._record_failure(exc)
                await asyncio.sleep(self._delay())

    def _record_success(self, transaction_id: str, scenario: str, fraud_like: bool) -> None:
        self._metrics.generated_count += 1
        self._metrics.fraud_count += int(fraud_like)
        self._metrics.last_transaction_id = transaction_id
        self._metrics.last_scenario = scenario
        self._metrics.last_error = None
        self._metrics.recent_scenarios.append(scenario)
        self._metrics.recent_scenarios = self._metrics.recent_scenarios[-40:]
        self._log("simulator_transaction_generated", transaction_id, scenario)

    def _record_failure(self, exc: Exception) -> None:
        self._metrics.failed_count += 1
        self._metrics.last_error = str(exc)
        self._log("simulator_failure")

    def _delay(self) -> float:
        minimum, maximum = self._intervals()
        return random.uniform(minimum, maximum)

    @staticmethod
    def _intervals() -> tuple[float, float]:
        settings = get_settings()
        minimum = settings.simulator_min_interval_seconds
        maximum = max(settings.simulator_max_interval_seconds, minimum)
        return minimum, maximum

    @staticmethod
    def _auth_required(settings: Any) -> bool:
        return any(value.strip() for value in settings.api_key_hashes.split(","))

    def _log(self, message: str, transaction_id: str = "", scenario: str | None = None) -> None:
        logger.info(
            message,
            extra={
                "transaction_id": transaction_id,
                "model_version": "",
                "fraud_probability": None,
                "severity": "",
                "ring_detected": message == "simulator_ring_generated",
                "simulator_running": self._metrics.running,
                "simulator_generated_count": self._metrics.generated_count,
                "simulator_fraud_count": self._metrics.fraud_count,
                "simulator_failed_count": self._metrics.failed_count,
                "simulator_scenario": scenario or self._metrics.last_scenario or "",
                "simulator_last_error": self._metrics.last_error or "",
            },
        )


simulator_service = TransactionSimulator()
