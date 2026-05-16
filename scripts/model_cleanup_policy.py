from datetime import datetime


def should_keep_model(model: dict, latest_versions: set[str], top_f1_versions: set[str], monthly_best_versions: set[str]) -> bool:
    if model.get("is_active"):
        return True
    version = model["model_version"]
    if version in latest_versions or version in top_f1_versions or version in monthly_best_versions:
        return True
    created_at = datetime.fromisoformat(model["created_at"].replace("Z", "+00:00"))
    age_days = (datetime.now(created_at.tzinfo) - created_at).days
    return age_days <= 30
