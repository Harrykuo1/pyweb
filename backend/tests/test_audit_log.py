"""Unit tests for the auth audit logger.

The autouse `audit_log_dir` fixture in conftest.py redirects the file
handler to a per-test temp dir and clears module state, so each test
starts with an empty log file and an empty failure tracker.
"""

from app.core import audit_log


def _read_log(audit_log_dir):
    log_file = audit_log_dir / "auth.log"
    if not log_file.exists():
        return ""
    return log_file.read_text(encoding="utf-8")


def test_record_failure_writes_warning_line(audit_log_dir):
    audit_log.record_failure("1.2.3.4")

    content = _read_log(audit_log_dir)
    assert "WARNING" in content
    assert "login_failed" in content
    assert "ip=1.2.3.4" in content
    assert "reason=bad_password" in content


def test_record_success_without_recent_failures_emits_nothing(audit_log_dir):
    audit_log.record_success("1.2.3.4", role="admin")

    # No log line means the file may not even have been created.
    content = _read_log(audit_log_dir)
    assert content == ""


def test_record_success_after_threshold_failures_logs_suspicious(audit_log_dir):
    for _ in range(audit_log.FAIL_THRESHOLD):
        audit_log.record_failure("1.2.3.4")
    audit_log.record_success("1.2.3.4", role="admin")

    content = _read_log(audit_log_dir)
    assert "login_success_after_failures" in content
    assert "ip=1.2.3.4" in content
    assert "role=admin" in content
    assert f"fails_in_window={audit_log.FAIL_THRESHOLD}" in content


def test_record_success_below_threshold_does_not_log_success(audit_log_dir):
    audit_log.record_failure("1.2.3.4")
    audit_log.record_success("1.2.3.4", role="admin")

    content = _read_log(audit_log_dir)
    # The single failure is logged, but the success below threshold is not.
    assert "login_failed" in content
    assert "login_success_after_failures" not in content


def test_failures_outside_window_are_evicted(audit_log_dir, monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr(audit_log.time, "monotonic", lambda: fake_now[0])

    for _ in range(audit_log.FAIL_THRESHOLD):
        audit_log.record_failure("1.2.3.4")

    # Jump past the 10-minute window.
    fake_now[0] += audit_log.WINDOW_SECONDS + 1

    audit_log.record_success("1.2.3.4", role="admin")

    content = _read_log(audit_log_dir)
    assert "login_success_after_failures" not in content


def test_failures_from_different_ips_are_independent(audit_log_dir):
    for _ in range(audit_log.FAIL_THRESHOLD):
        audit_log.record_failure("1.1.1.1")

    # A clean IP should not inherit 1.1.1.1's reputation.
    audit_log.record_success("2.2.2.2", role="admin")

    content = _read_log(audit_log_dir)
    assert "login_success_after_failures" not in content


def test_ip_cap_evicts_oldest_first(audit_log_dir, monkeypatch):
    monkeypatch.setattr(audit_log, "IP_CAP", 3)

    for ip in ("a", "b", "c"):
        audit_log.record_failure(ip)
    # Adding a 4th IP should evict "a" (oldest).
    audit_log.record_failure("d")

    assert "a" not in audit_log._tracker._by_ip
    assert {"b", "c", "d"} <= set(audit_log._tracker._by_ip.keys())


class _FakeRequest:
    def __init__(self, headers=None, host="9.9.9.9"):
        self.headers = headers or {}

        class _Client:
            pass

        client = _Client()
        client.host = host
        self.client = client


def test_client_ip_uses_x_real_ip_and_ignores_forwarded_for():
    # X-Real-IP is nginx-controlled (overwritten each hop); X-Forwarded-For's
    # first token is client-forgeable and must not be trusted for attribution.
    req = _FakeRequest(
        headers={"x-real-ip": "1.1.1.1", "x-forwarded-for": "6.6.6.6, 10.0.0.5"}
    )
    assert audit_log.client_ip(req) == "1.1.1.1"


def test_client_ip_ignores_forwarded_for_without_real_ip():
    # A client-supplied X-Forwarded-For alone must not be trusted — fall
    # back to the direct peer instead of the spoofable header.
    req = _FakeRequest(headers={"x-forwarded-for": "6.6.6.6"})
    assert audit_log.client_ip(req) == "9.9.9.9"


def test_client_ip_falls_back_to_request_client_host():
    req = _FakeRequest()
    assert audit_log.client_ip(req) == "9.9.9.9"


def test_client_ip_returns_unknown_when_nothing_available():
    req = _FakeRequest()
    req.client = None
    assert audit_log.client_ip(req) == "unknown"
