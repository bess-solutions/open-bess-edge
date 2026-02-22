"""
tests/test_rate_limiting.py
============================
Unit tests for the _RateLimiter class in dashboard_api.py
IEC 62443-3-3 SR 7.1 — Denial-of-Service protection

Tests cover:
  - Normal requests under the limit are allowed
  - Requests that exceed the limit are blocked (is_allowed returns False)
  - Counter resets correctly after the sliding window expires
  - retry_after() returns a positive integer
  - RATE_LIMIT_READ_RPM env var overrides default limit
  - Different IPs have independent counters
"""

from __future__ import annotations

import os
import time

import pytest


# ---------------------------------------------------------------------------
# Import the private _RateLimiter directly from dashboard_api
# (tests the class, not the aiohttp middleware, to avoid needing a running server)
# ---------------------------------------------------------------------------


@pytest.fixture()
def limiter(monkeypatch: pytest.MonkeyPatch):
    """Fresh _RateLimiter with a tiny limit of 5 req/min for fast tests."""
    monkeypatch.setenv("RATE_LIMIT_READ_RPM", "5")
    # Re-import to get a fresh instance using the patched env var
    import importlib
    import src.interfaces.dashboard_api as mod
    importlib.reload(mod)
    return mod._RateLimiter()


class TestRateLimiter:

    def test_allows_requests_under_limit(self, limiter) -> None:
        """First 5 requests for an IP must be allowed."""
        for _ in range(5):
            assert limiter.is_allowed("10.0.0.1") is True

    def test_blocks_request_over_limit(self, limiter) -> None:
        """6th request within the same window must be blocked."""
        for _ in range(5):
            limiter.is_allowed("10.0.0.2")
        assert limiter.is_allowed("10.0.0.2") is False

    def test_different_ips_are_independent(self, limiter) -> None:
        """Blocking one IP must not affect another IP's counter."""
        for _ in range(5):
            limiter.is_allowed("10.0.0.3")
        # IP 3 is now at limit
        assert limiter.is_allowed("10.0.0.3") is False
        # IP 4 is untouched → still allowed
        assert limiter.is_allowed("10.0.0.4") is True

    def test_retry_after_positive(self, limiter) -> None:
        """retry_after() must return a positive integer when limit is exceeded."""
        for _ in range(5):
            limiter.is_allowed("10.0.0.5")
        limiter.is_allowed("10.0.0.5")  # trigger block
        retry = limiter.retry_after("10.0.0.5")
        assert isinstance(retry, int)
        assert retry >= 1

    def test_retry_after_unknown_ip_returns_one(self, limiter) -> None:
        """retry_after() for an IP with no history must return 1."""
        assert limiter.retry_after("10.99.99.99") == 1

    def test_window_evicts_old_timestamps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Timestamps from outside the sliding window must be evicted."""
        import src.interfaces.dashboard_api as mod

        # Use a fresh limiter with limit=2 for this test
        monkeypatch.setenv("RATE_LIMIT_READ_RPM", "2")
        lim = mod._RateLimiter()
        ip = "10.0.0.10"

        # Simulate 2 old timestamps (61 seconds ago)
        old_ts = time.monotonic() - 61
        lim._counters[ip] = __import__("collections").deque([old_ts, old_ts])

        # Now a new request should be allowed (old entries evicted)
        assert lim.is_allowed(ip) is True
        # And a second new request too (only 1 in window)
        assert lim.is_allowed(ip) is True
        # Third one is over the limit of 2
        assert lim.is_allowed(ip) is False

    def test_env_override_sets_custom_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RATE_LIMIT_READ_RPM env var must set the limiter threshold."""
        monkeypatch.setenv("RATE_LIMIT_READ_RPM", "3")
        import importlib
        import src.interfaces.dashboard_api as mod
        importlib.reload(mod)
        lim = mod._RateLimiter()
        assert lim._read_limit == 3
        for _ in range(3):
            assert lim.is_allowed("10.0.0.7") is True
        assert lim.is_allowed("10.0.0.7") is False
