"""Access control and spend limits for a publicly reachable deployment.

Locally none of this matters: the service listens on loopback beside a robot.
Publicly it matters a great deal, because the expensive endpoints spend real
money on someone else's behalf. A single unauthenticated
``/api/chat/graph-command`` is an OpenAI call, and an unattended crawler --
never mind a malicious one -- can empty an account overnight.

Three independent limits, deliberately layered so that no single mistake in one
of them exposes the account:

1.  **An API key** on the endpoints that cost money. Absent a configured key the
    service stays open, which keeps local development friction-free; setting
    ``PUBLIC_API_KEY`` closes it.
2.  **A per-client rate limit**, so one caller cannot monopolise the service.
3.  **A global daily budget**, which is the backstop that actually bounds the
    bill. Rate limiting alone does not: a hundred clients each politely within
    their own limit still add up.

State is in-process, which is the right trade for a single container and the
wrong one for a horizontally scaled deployment -- with several replicas each
would enforce its own share. Redis is the answer at that point, and is
deliberately not a dependency here.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

# --- configuration, all overridable from the environment ----------------
API_KEY = os.getenv("PUBLIC_API_KEY", "").strip()
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "3600"))
DAILY_BUDGET_CALLS = int(os.getenv("DAILY_BUDGET_CALLS", "300"))

# Paths that spend money or command hardware. Everything else -- the graph
# shape, the place registry, health -- is metadata that costs nothing to serve
# and that the public interface needs in order to render at all.
COSTLY_PREFIXES = (
    "/api/chat/",
    "/api/rag/",
    "/api/vision/",
    "/api/navigation/go-to",
    "/api/robot/stop",
    "/api/robot/capture",
    "/api/localization/",
)


# Exceptions carved out of the prefixes above: metadata the public interface
# needs in order to render, which costs nothing to serve. /api/chat/graph
# returns the shape of the command graph, not a run of it.
FREE_PATHS = frozenset({"/api/chat/graph"})


def is_costly(path: str) -> bool:
    if path.rstrip("/") in FREE_PATHS:
        return False
    return any(path.startswith(p) for p in COSTLY_PREFIXES)


class RateLimiter:
    """Sliding-window counter, keyed by client."""

    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, seconds_until_a_slot_frees)."""
        now = time.time()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False, int(self.window - (now - q[0])) + 1
        q.append(now)
        return True, 0

    def remaining(self, key: str) -> int:
        return max(0, self.limit - len(self._hits.get(key, ())))


class DailyBudget:
    """A hard ceiling on paid calls per UTC day."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._day = time.gmtime().tm_yday
        self._count = 0

    def _roll(self) -> None:
        today = time.gmtime().tm_yday
        if today != self._day:
            self._day, self._count = today, 0

    def check(self) -> bool:
        self._roll()
        if self._count >= self.limit:
            return False
        self._count += 1
        return True

    @property
    def used(self) -> int:
        self._roll()
        return self._count


limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SEC)
budget = DailyBudget(DAILY_BUDGET_CALLS)


def client_key(request: Request) -> str:
    """Identify the caller.

    Behind a proxy the socket address is the proxy's, so the forwarded header is
    preferred where present. It is client-supplied and therefore spoofable; the
    daily budget is what holds when it is forged, which is precisely why the
    budget exists as a separate limit rather than as a larger rate limit.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def guard(request: Request) -> None:
    """Applied as middleware to the costly paths."""
    if not is_costly(request.url.path):
        return

    if API_KEY:
        supplied = request.headers.get("x-api-key", "")
        # compare in constant time; the key is short and the endpoint is public
        import hmac

        if not hmac.compare_digest(supplied, API_KEY):
            raise HTTPException(
                status_code=401,
                detail="This endpoint needs an API key. Send it as X-API-Key.",
            )

    key = client_key(request)
    allowed, retry_after = limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit reached: {RATE_LIMIT_REQUESTS} requests per "
                f"{RATE_LIMIT_WINDOW_SEC // 60} minutes. Try again in "
                f"{retry_after} s."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    if not budget.check():
        raise HTTPException(
            status_code=429,
            detail=(
                f"The daily budget of {DAILY_BUDGET_CALLS} model-backed requests "
                "is spent. This ceiling exists so a public demonstration cannot "
                "run up an unbounded bill; it resets at 00:00 UTC."
            ),
        )


def limits_status() -> dict:
    return {
        "api_key_required": bool(API_KEY),
        "rate_limit": f"{RATE_LIMIT_REQUESTS} per {RATE_LIMIT_WINDOW_SEC}s per client",
        "daily_budget": DAILY_BUDGET_CALLS,
        "daily_budget_used": budget.used,
        "protected_paths": list(COSTLY_PREFIXES),
    }
