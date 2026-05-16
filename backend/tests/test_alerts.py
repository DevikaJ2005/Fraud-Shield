from app.schemas.transaction import GraphAnalysis, Severity
from app.services.alerts import severity_for


def test_high_severity_for_ring() -> None:
    assert severity_for(0.2, GraphAnalysis(ring_detected=True)) == Severity.high


def test_medium_severity_for_score() -> None:
    assert severity_for(0.8, GraphAnalysis()) == Severity.medium
