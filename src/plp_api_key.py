"""
PredictLottoPro API Key verification (v2 router only)

Non-breaking: applies exclusively to /api/v2 endpoints when enabled via PLP_API_ENABLED.
Reads API key from env var PREDICTLOTTOPRO_API_KEY.
"""

import os
import time
from fastapi import Header, HTTPException, Response

def _is_truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}

def get_plp_api_key() -> str | None:
    return os.getenv("PREDICTLOTTOPRO_API_KEY")

_RATE_STATE: dict[str, dict[str, int]] = {}

def _rate_limit_headers(limit: int, remaining: int, reset_epoch: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(reset_epoch),
    }

async def verify_plp_api_key(authorization: str | None = Header(default=None), response: Response = None) -> None:
    """Simple Bearer API key check + per-key rate limit for PLP v2 endpoints.

    - Requires env PREDICTLOTTOPRO_API_KEY
    - Expects header: Authorization: Bearer <API_KEY>
    """
    # If PLP API disabled, skip check (router shouldn't be mounted in that case)
    if not _is_truthy(os.getenv("PLP_API_ENABLED", "false")):
        return

    expected = get_plp_api_key()
    if not expected:
        # Misconfiguration: deny with 503-like message but keep 401 for security
        raise HTTPException(status_code=401, detail="PLP API key not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Lightweight per-key rate limiting (fixed 60s window)
    try:
        rpm = int(os.getenv("PLP_RATE_LIMIT_RPM", "100"))
    except Exception:
        rpm = 100

    now = int(time.time())
    window_start = now - (now % 60)
    window_reset = window_start + 60

    state = _RATE_STATE.get(token)
    if not state or state.get("window", 0) != window_start:
        state = {"window": window_start, "count": 0}
        _RATE_STATE[token] = state

    state["count"] += 1
    remaining = max(0, rpm - state["count"])

    # Attach headers for both success and limit exceeded
    headers = _rate_limit_headers(rpm, remaining, window_reset)
    if response is not None:
        for k, v in headers.items():
            try:
                response.headers[k] = v
            except Exception:
                pass

    if state["count"] > rpm:
        # Over limit: raise with headers as well
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers=headers,
        )

    # Success: allow request to proceed

