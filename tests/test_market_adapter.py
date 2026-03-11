# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_market_adapter.py
==============================
Test suite for MarketAdapter protocol and all market implementations.
"""
from __future__ import annotations

import pytest
from src.core.market_adapter import (
    CENACEAdapter,
    COESAdapter,
    DispatchRules,
    MarketAdapter,
    MarketAdapterRegistry,
    SENAdapter,
    SpotPrice,
    XMAdapter,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_registry():
    """Clear the adapter registry cache between tests."""
    MarketAdapterRegistry.reset()
    yield
    MarketAdapterRegistry.reset()


# ── SpotPrice tests ───────────────────────────────────────────────────────────

class TestSpotPrice:

    def test_clp_conversion(self):
        sp = SpotPrice(hour=12, price_usd_mwh=50.0, node="Maitencillo", market="SEN")
        # 50 USD/MWh * (1/1000) * 950 = 47.5 CLP/kWh
        expected = 50.0 / 1000 * 950.0
        assert abs(sp.price_clp_kwh - expected) < 0.01

    def test_to_dict_keys(self):
        sp = SpotPrice(0, 40.0, "TestNode", "SEN", "2026-03-11")
        d = sp.to_dict()
        assert "hour" in d and "price_usd_mwh" in d and "market" in d


# ── SENAdapter tests ──────────────────────────────────────────────────────────

class TestSENAdapter:

    def test_market_id(self):
        assert SENAdapter().market_id == "SEN"

    def test_country(self):
        assert SENAdapter().country == "Chile"

    def test_get_spot_prices_returns_24(self):
        prices = SENAdapter().get_spot_prices("2026-03-11", "Maitencillo")
        assert len(prices) == 24
        assert all(isinstance(p, SpotPrice) for p in prices)

    def test_spot_prices_duck_curve(self):
        prices = SENAdapter().get_spot_prices("2026-03-11", "Maitencillo")
        morning = [p.price_usd_mwh for p in prices if 0 <= p.hour <= 5]
        evening = [p.price_usd_mwh for p in prices if 18 <= p.hour <= 22]
        # Evening prices should be higher than early morning (Duck Curve)
        assert sum(evening) > sum(morning)

    def test_ancillary_services_has_5(self):
        services = SENAdapter().get_ancillary_services()
        assert len(services) == 5
        ids = {s.service_id for s in services}
        assert ids == {"CSF", "RP", "RSS", "RSB", "AGC"}

    def test_dispatch_rules_structure(self):
        rules = SENAdapter().get_dispatch_rules()
        assert isinstance(rules, DispatchRules)
        assert rules.currency == "CLP"
        assert rules.grid_frequency_hz == 50.0
        assert 0 < rules.min_soc_pct < rules.max_soc_pct < 100

    def test_market_zones_not_empty(self):
        zones = SENAdapter().get_market_zones()
        assert len(zones) >= 5
        assert "Maitencillo" in zones

    def test_to_dict_has_market_id(self):
        d = SENAdapter().to_dict()
        assert d["market_id"] == "SEN"
        assert len(d["zones"]) > 0


# ── Stub adapter tests ────────────────────────────────────────────────────────

class TestStubAdapters:

    @pytest.mark.parametrize("adapter_cls,expected_market,expected_country", [
        (COESAdapter, "COES", "Peru"),
        (XMAdapter, "XM", "Colombia"),
        (CENACEAdapter, "CENACE", "Mexico"),
    ])
    def test_market_id_and_country(self, adapter_cls, expected_market, expected_country):
        a = adapter_cls()
        assert a.market_id == expected_market
        assert a.country == expected_country

    @pytest.mark.parametrize("adapter_cls", [COESAdapter, XMAdapter, CENACEAdapter])
    def test_stub_returns_24_zero_prices(self, adapter_cls):
        prices = adapter_cls().get_spot_prices("2026-03-11")
        assert len(prices) == 24
        assert all(p.price_usd_mwh == 0.0 for p in prices)

    @pytest.mark.parametrize("adapter_cls", [COESAdapter, XMAdapter, CENACEAdapter])
    def test_stub_has_ancillary_services(self, adapter_cls):
        services = adapter_cls().get_ancillary_services()
        assert len(services) >= 1

    @pytest.mark.parametrize("adapter_cls", [COESAdapter, XMAdapter, CENACEAdapter])
    def test_stub_has_dispatch_rules(self, adapter_cls):
        rules = adapter_cls().get_dispatch_rules()
        assert isinstance(rules, DispatchRules)
        assert rules.min_soc_pct >= 5.0

    def test_coes_uses_60hz(self):
        assert COESAdapter().get_dispatch_rules().grid_frequency_hz == 60.0

    def test_xm_uses_cop_currency(self):
        assert XMAdapter().get_dispatch_rules().currency == "COP"

    def test_cenace_uses_mxn(self):
        assert CENACEAdapter().get_dispatch_rules().currency == "MXN"


# ── MarketAdapterRegistry tests ───────────────────────────────────────────────

class TestMarketAdapterRegistry:

    def test_default_returns_sen(self):
        adapter = MarketAdapterRegistry.get()
        assert adapter.market_id == "SEN"

    def test_explicit_coes(self):
        adapter = MarketAdapterRegistry.get("COES")
        assert adapter.market_id == "COES"

    def test_case_insensitive(self):
        adapter = MarketAdapterRegistry.get("xm")
        assert adapter.market_id == "XM"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("BESSAI_MARKET", "CENACE")
        adapter = MarketAdapterRegistry.get()
        assert adapter.market_id == "CENACE"

    def test_unknown_market_raises(self):
        with pytest.raises(ValueError, match="Unknown market"):
            MarketAdapterRegistry.get("UNKNOWN_MARKET")

    def test_registry_is_cached(self):
        a1 = MarketAdapterRegistry.get("SEN")
        a2 = MarketAdapterRegistry.get("SEN")
        assert a1 is a2

    def test_available_markets(self):
        markets = MarketAdapterRegistry.available_markets()
        assert set(markets) >= {"SEN", "COES", "XM", "CENACE"}

    def test_sen_is_market_adapter_subclass(self):
        adapter = MarketAdapterRegistry.get("SEN")
        assert isinstance(adapter, MarketAdapter)
