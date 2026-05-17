import re

from app.core.config import Settings


def test_cors_keeps_localhost_and_allows_vercel_previews() -> None:
    settings = Settings(_env_file=None)

    assert "http://localhost:5173" in settings.allowed_origins
    assert "http://127.0.0.1:5173" in settings.allowed_origins
    assert "https://fraud-shield-blue.vercel.app" in settings.allowed_origins
    assert re.fullmatch(
        settings.allowed_origin_regex,
        "https://fraud-shield-pkn6j4q6e-devikaj2005-7788s-projects.vercel.app",
    )
    assert not re.fullmatch(settings.allowed_origin_regex, "http://fraud-shield-blue.vercel.app")
    assert not re.fullmatch(settings.allowed_origin_regex, "https://example.com")


def test_blank_cors_regex_env_falls_back_to_vercel_pattern() -> None:
    settings = Settings(_env_file=None, CORS_ORIGIN_REGEX=" ")

    assert re.fullmatch(
        settings.allowed_origin_regex,
        "https://fraud-shield-pkn6j4q6e-devikaj2005-7788s-projects.vercel.app",
    )
