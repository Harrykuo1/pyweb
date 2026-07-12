"""Every backend response carries defense-in-depth security headers.
script-src 'none' is the key one: it neutralizes any HTML/JS served from a
backend response opened as a document (a spoofed attachment), on top of the
per-endpoint content-type normalization."""

from fastapi.testclient import TestClient

from app.main import app


def test_backend_responses_carry_security_headers():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "script-src 'none'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["referrer-policy"] == "no-referrer"
