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
    # Trust X-Real-IP, which nginx OVERWRITES with the connecting client's
    # address on every hop, so it can't be forged. X-Forwarded-For is NOT
    # safe here: nginx appends to it, leaving its first token fully
    # client-controlled, which would let an attacker rotate the rate-limit
    # key per request and defeat the login throttle entirely.
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=get_real_ip)
