import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


_request_windows: dict[str, deque[float]] = defaultdict(deque)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configured_hashes = {
        value.strip()
        for value in get_settings().api_key_hashes.split(",")
        if value.strip()
    }
    if not configured_hashes:
        return

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    presented_hash = hash_api_key(x_api_key)
    if not any(hmac.compare_digest(presented_hash, stored) for stored in configured_hashes):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def enforce_rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_per_minute
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window = _request_windows[client]

    while window and now - window[0] > 60:
        window.popleft()

    if len(window) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    window.append(now)
