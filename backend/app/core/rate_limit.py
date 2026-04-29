"""Per-IP rate limiting for sensitive endpoints (login, etc.).

The Limiter is created here as a module-level singleton so both ``main.py``
(for the 429 exception handler and ``app.state`` registration) and the
routers can import the same instance without a circular dependency.

Trust model: the backend container only exposes its port on the internal
docker bridge network, so ``X-Forwarded-For`` can only originate from the
frontend nginx container in the deployed setup. We pull the original
client from that header directly — bypassing uvicorn's ``--proxy-headers``
parsing — so tests can control the client IP via a request header instead
of needing a real reverse proxy in front of TestClient.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter


def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry is the original client; intermediate proxies append.
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client is not None:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=get_real_ip)
