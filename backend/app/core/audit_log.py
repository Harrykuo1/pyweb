"""Authentication audit log.

Failed login attempts always emit a WARN line. Successful logins normally
do NOT emit a log line — but if the same source IP had >= FAIL_THRESHOLD
failures in the past WINDOW_SECONDS, we treat the success as suspicious
(likely brute-force hit) and emit a separate WARN with a fails_in_window
counter so it stands out when grepping the file.

The failure tracker keeps a rolling per-IP timestamp deque in memory.
Expired entries are evicted lazily at access; the total number of
distinct IPs is FIFO-capped at IP_CAP so a flood of distinct source
IPs cannot exhaust memory.

Log file lives at $AUDIT_LOG_DIR/auth.log (default /data/logs, which
is the existing host bind-mount), daily-rotated and kept for 30 days.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict, deque
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 10-minute rolling window for "recent" failures.
WINDOW_SECONDS = 10 * 60

# Successes preceded by this many recent failures (same IP) are flagged.
FAIL_THRESHOLD = 3

# Per-IP timestamp cap. We only need to know "is the count >= threshold",
# so storing more than this gains nothing and bounds per-attacker memory.
IP_FAIL_CAP = 100

# Distinct-IP cap before FIFO eviction kicks in; protects against a flood
# of unique source IPs (e.g. botnet) growing the dict unbounded.
IP_CAP = 10_000

ROTATE_BACKUP_COUNT = 30  # 30 daily files

LOGGER_NAME = "pyweb.auth"

_handler_lock = threading.Lock()


def _resolve_log_path() -> Path:
    return Path(os.environ.get("AUDIT_LOG_DIR", "/data/logs")) / "auth.log"


def get_logger() -> logging.Logger:
    """Return the audit logger; configures the file handler on first call."""
    logger = logging.getLogger(LOGGER_NAME)
    # Audit lines are intentionally separate from uvicorn's stderr stream;
    # propagating to the root would dump them into the general app log too.
    logger.propagate = False
    logger.setLevel(logging.INFO)

    if any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
        return logger

    with _handler_lock:
        if any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
            return logger
        log_file = _resolve_log_path()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=ROTATE_BACKUP_COUNT,
            encoding="utf-8",
            utc=True,
        )
        # ISO-8601 UTC, second precision is enough for forensic correlation.
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)sZ %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    return logger


class _FailureTracker:
    """Rolling per-IP counter of recent failed-login timestamps."""

    def __init__(self) -> None:
        # OrderedDict makes FIFO eviction O(1) via popitem(last=False).
        self._by_ip: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            timestamps = self._by_ip.get(ip)
            if timestamps is None:
                timestamps = deque(maxlen=IP_FAIL_CAP)
                self._by_ip[ip] = timestamps
            else:
                # Refresh insertion order so a newly-active IP isn't the
                # next victim of FIFO eviction.
                self._by_ip.move_to_end(ip)
            timestamps.append(now)
            self._evict_expired_locked(timestamps, now)
            self._enforce_ip_cap_locked()

    def recent_failure_count(self, ip: str) -> int:
        now = time.monotonic()
        with self._lock:
            timestamps = self._by_ip.get(ip)
            if not timestamps:
                return 0
            self._evict_expired_locked(timestamps, now)
            if not timestamps:
                self._by_ip.pop(ip, None)
                return 0
            return len(timestamps)

    def _evict_expired_locked(self, timestamps: deque[float], now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _enforce_ip_cap_locked(self) -> None:
        while len(self._by_ip) > IP_CAP:
            self._by_ip.popitem(last=False)

    def reset(self) -> None:
        with self._lock:
            self._by_ip.clear()


_tracker = _FailureTracker()


def record_failure(ip: str, reason: str = "bad_password") -> None:
    """Record a failed login attempt — always emits a WARN line."""
    _tracker.record_failure(ip)
    get_logger().warning("login_failed ip=%s reason=%s", ip, reason)


def record_success(ip: str, role: str) -> None:
    """Record a successful login — only logs if it follows recent failures."""
    fails = _tracker.recent_failure_count(ip)
    if fails >= FAIL_THRESHOLD:
        get_logger().warning(
            "login_success_after_failures ip=%s role=%s fails_in_window=%d",
            ip,
            role,
            fails,
        )


def client_ip(request) -> str:
    """Client IP from nginx's X-Real-IP, which is overwritten (not appended)
    on every hop so it can't be forged. X-Forwarded-For's first token is
    client-controlled and must not be trusted for audit attribution."""
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _reset_for_tests() -> None:
    """Drop file handler + clear tracker. Used by the test fixture."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    _tracker.reset()
