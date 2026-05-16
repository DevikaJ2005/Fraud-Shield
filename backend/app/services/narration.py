from app.schemas.transaction import GraphAnalysis, PatternFlag, ShapExplanation


def deterministic_narration(
    fraud_probability: float,
    patterns: list[PatternFlag],
    graph: GraphAnalysis,
    explanations: list[ShapExplanation],
) -> str:
    active_patterns = [pattern.name for pattern in patterns if pattern.value]
    top_features = [item.feature for item in explanations[:3]]
    ring_text = "A fraud ring condition was detected." if graph.ring_detected else "No fraud ring condition was detected."
    pattern_text = ", ".join(active_patterns) if active_patterns else "no deterministic pattern flags"
    feature_text = ", ".join(top_features) if top_features else "no feature attribution available"
    return (
        f"Fraud probability is {fraud_probability:.3f}. "
        f"{ring_text} Pattern evidence: {pattern_text}. "
        f"Primary model evidence: {feature_text}."
    )
