from app.schemas.transaction import GraphAnalysis, Severity


def severity_for(fraud_probability: float, graph: GraphAnalysis) -> Severity | None:
    if fraud_probability >= 0.85 or graph.ring_detected:
        return Severity.high
    if fraud_probability >= 0.75:
        return Severity.medium
    if fraud_probability >= 0.60:
        return Severity.low
    return None
