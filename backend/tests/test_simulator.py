from app.core.config import Settings
from app.schemas.transaction import TransactionRequest
from simulator.engine import SCENARIOS, TransactionGenerator


def test_transaction_generator_emits_valid_prediction_requests() -> None:
    generator = TransactionGenerator(seed=7)

    generated = [generator.next() for _ in range(80)]

    assert all(isinstance(tx, TransactionRequest) for tx, _, _ in generated)
    assert all(tx.transaction_id.startswith("sim-") for tx, _, _ in generated)
    assert all(scenario in SCENARIOS for _, scenario, _ in generated)
    assert any(fraud_like for _, _, fraud_like in generated)
    assert any(scenario == "fraud_ring" for _, scenario, _ in generated)


def test_simulator_defaults_match_live_traffic_goal() -> None:
    settings = Settings(_env_file=None)

    assert settings.simulator_enabled is True
    assert settings.simulator_min_interval_seconds == 2.0
    assert settings.simulator_max_interval_seconds == 5.0
