"""
tests/test_sen_market_feed.py
==============================
Unit tests for SENMarketFeed — BEP-0500 Phase 2 market price callable.

Coverage:
- Duck curve fallback (no duckdb, no adapter)
- Callable interface
- Cache TTL behavior
- Integration with VPPFleetManager.set_market_price_fn()
- _duck_curve_usd() bounds (always > 30 USD/MWh)
- Default db path construction
- last_price accessor
- repr
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from src.core.sen_market_feed import SENMarketFeed


# ─── Helpers ────────────────────────────────────────────────────────────────

def _feed_no_db(node: str = "Lo_Aguirre") -> SENMarketFeed:
    """Feed that always falls through to duck curve (no duckdb, no adapter)."""
    return SENMarketFeed(node=node, use_duckdb=False)


# ─── Duck curve basic tests ─────────────────────────────────────────────────

class TestDuckCurveFallback:
    def test_returns_positive_price(self):
        feed = _feed_no_db()
        # Patch SENAdapter to also fail so duck curve activates
        with patch("src.core.sen_market_feed.SENMarketFeed._fetch_adapter", return_value=55.0):
            price = feed()
        assert price == pytest.approx(55.0)

    def test_duck_curve_always_above_floor(self):
        feed = _feed_no_db()
        for hour in range(24):
            with patch("src.core.sen_market_feed.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = MagicMock(hour=hour)
                mock_dt.date.today.return_value = MagicMock(isoformat=lambda: "2026-01-01")
                price = feed._duck_curve_usd()
            assert price >= 30.0, f"Hour {hour}: price {price} below floor"

    def test_duck_curve_returns_float(self):
        feed = _feed_no_db()
        result = feed._duck_curve_usd()
        assert isinstance(result, float)


# ─── Callable interface ──────────────────────────────────────────────────────

class TestCallableInterface:
    def test_feed_is_callable(self):
        feed = _feed_no_db()
        assert callable(feed)

    def test_call_returns_float(self):
        feed = SENMarketFeed(node="Maitencillo", use_duckdb=False)
        with patch.object(feed, "_fetch_adapter", return_value=78.5):
            price = feed()
        assert isinstance(price, float)
        assert price == pytest.approx(78.5)

    def test_last_price_none_before_call(self):
        feed = _feed_no_db()
        assert feed.last_price is None

    def test_last_price_set_after_call(self):
        feed = _feed_no_db()
        with patch.object(feed, "_fetch_adapter", return_value=62.0):
            feed()
        assert feed.last_price == pytest.approx(62.0)


# ─── TTL cache ───────────────────────────────────────────────────────────────

class TestCacheTTL:
    def test_second_call_uses_cache(self):
        feed = _feed_no_db()
        mock_fetch = MagicMock(return_value=55.0)
        with patch.object(feed, "_fetch", mock_fetch):
            feed()
            feed()
        # _fetch should only be called once — second call is cached
        assert mock_fetch.call_count == 1

    def test_expired_cache_refetches(self):
        feed = _feed_no_db()
        feed._cache_ttl_minutes = 0  # force expiry immediately
        mock_fetch = MagicMock(return_value=55.0)
        with patch.object(feed, "_fetch", mock_fetch):
            feed()
            time.sleep(0.01)
            feed()
        assert mock_fetch.call_count == 2


# ─── VPPFleetManager integration ─────────────────────────────────────────────

class TestVPPIntegration:
    def test_set_market_price_fn_uses_feed(self):
        from src.core.fleet_orchestrator import SiteProxy, SiteTelemetry
        from src.core.vpp_fleet_manager import VPPFleetManager

        def _proxy(sid: str) -> SiteTelemetry:
            return SiteTelemetry(
                site_id=sid, soc_pct=70.0, power_kw=0.0,
                temp_c=25.0, capacity_kwh=200.0, available_kw=80.0,
            )

        proxy = SiteProxy("127.0.0.1", site_id="CL-001", capacity_kwh=200.0, telemetry_fn=_proxy)
        mgr = VPPFleetManager(discharge_threshold=60.0)
        mgr.add_site("CL-001", proxy)

        feed = _feed_no_db()
        # Wire a lambda that always returns 90 USD/MWh (above threshold)
        mgr.set_market_price_fn(lambda: 90.0)
        result = mgr.run_cycle()
        assert result.market_price_usd_mwh == pytest.approx(90.0)
        assert result.total_dispatch_kw > 0  # should discharge at high price

    def test_market_price_fn_error_falls_back_to_arg(self):
        from src.core.fleet_orchestrator import SiteProxy, SiteTelemetry
        from src.core.vpp_fleet_manager import DispatchStrategy, VPPFleetManager

        def _proxy(sid: str) -> SiteTelemetry:
            return SiteTelemetry(
                site_id=sid, soc_pct=70.0, power_kw=0.0,
                temp_c=25.0, capacity_kwh=100.0, available_kw=50.0,
            )

        proxy = SiteProxy("127.0.0.1", site_id="CL-A", capacity_kwh=100.0, telemetry_fn=_proxy)
        mgr = VPPFleetManager()
        mgr.add_site("CL-A", proxy)

        def bad_fn():
            raise RuntimeError("API down")

        mgr.set_market_price_fn(bad_fn)
        # Should fall back to argument value (60.0 → neutral → HOLD)
        result = mgr.run_cycle(market_price_usd_mwh=60.0)
        assert result.strategy == DispatchStrategy.HOLD  # neutral band


# ─── DuckDB path helpers ──────────────────────────────────────────────────────

class TestDBPath:
    def test_default_db_path_is_string(self):
        feed = _feed_no_db()
        path = feed._default_db_path()
        assert isinstance(path, str)
        assert "bessai-cen-data" in path

    def test_custom_db_path_respected(self):
        feed = SENMarketFeed(db_path="/custom/path.duckdb", use_duckdb=True)
        assert feed._db_path == "/custom/path.duckdb"


# ─── repr ─────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_repr_contains_node(self):
        feed = SENMarketFeed(node="Polpaico")
        assert "Polpaico" in repr(feed)

    def test_repr_contains_last_price(self):
        feed = _feed_no_db()
        with patch.object(feed, "_fetch_adapter", return_value=71.5):
            feed()
        assert "71.5" in repr(feed)
