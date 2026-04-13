"""
tests/test_market_adapter_global.py
=====================================
BEP-0200 Sprint C — Tests para todos los Market Adapters (Latam + USA + Europe).

Cubre 7 adapters: SEN, COES, XM, CENACE, CAISO, ERCOT, ENTSO-E.
Usa mock HTTP para no depender de APIs externas.

Run con:
    pytest tests/test_market_adapter_global.py -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE = "2026-03-12"


def _make_response(data, status_code: int = 200):
    """Helper: mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.return_value = None
    if isinstance(data, str):
        resp.text = data
        resp.json.side_effect = json.JSONDecodeError("not json", "", 0)
    else:
        resp.text = json.dumps(data)
        resp.json.return_value = data
    return resp


# ---------------------------------------------------------------------------
# Registry: verify all 7 markets are registered
# ---------------------------------------------------------------------------

class TestMarketAdapterRegistry:
    def test_all_markets_registered(self):
        from src.core.market_adapter import MarketAdapterRegistry
        markets = MarketAdapterRegistry.available_markets()
        expected = {"SEN", "COES", "XM", "CENACE", "CAISO", "ERCOT", "ENTSOE"}
        assert expected.issubset(set(markets)), f"Missing: {expected - set(markets)}"

    def test_registry_returns_correct_type(self):
        from src.core.market_adapter import (
            CAISOAdapter,
            ENTSOEAdapter,
            ERCOTAdapter,
            MarketAdapterRegistry,
        )
        MarketAdapterRegistry.reset()
        assert isinstance(MarketAdapterRegistry.get("CAISO"), CAISOAdapter)
        assert isinstance(MarketAdapterRegistry.get("ERCOT"), ERCOTAdapter)
        assert isinstance(MarketAdapterRegistry.get("ENTSOE"), ENTSOEAdapter)
        MarketAdapterRegistry.reset()

    def test_unknown_market_raises_value_error(self):
        from src.core.market_adapter import MarketAdapterRegistry
        MarketAdapterRegistry.reset()
        with pytest.raises(ValueError, match="Unknown market"):
            MarketAdapterRegistry.get("NORDPOOL")

    def test_all_adapters_have_market_id(self):
        from src.core.market_adapter import MarketAdapterRegistry
        MarketAdapterRegistry.reset()
        for mkt in ["SEN", "COES", "XM", "CENACE", "CAISO", "ERCOT", "ENTSOE"]:
            adapter = MarketAdapterRegistry.get(mkt)
            assert adapter.market_id == mkt, f"{mkt}: market_id mismatch"
        MarketAdapterRegistry.reset()


# ---------------------------------------------------------------------------
# SpotPrice & DispatchRules dataclass sanity
# ---------------------------------------------------------------------------

class TestDataStructures:
    def test_spot_price_to_dict_has_all_keys(self):
        from src.core.market_adapter import SpotPrice
        sp = SpotPrice(hour=10, price_usd_mwh=55.0, node="TEST", market="SEN", date=_DATE)
        d = sp.to_dict()
        assert set(d.keys()) == {"hour", "price_usd_mwh", "price_clp_kwh", "node", "market", "date"}

    def test_spot_price_clp_conversion(self):
        from src.core.market_adapter import SpotPrice
        sp = SpotPrice(hour=0, price_usd_mwh=100.0, node="X", market="SEN", date=_DATE)
        assert sp.price_clp_kwh == pytest.approx(95.0, rel=0.01)

    def test_dispatch_rules_defaults(self):
        from src.core.market_adapter import DispatchRules
        dr = DispatchRules()
        assert dr.min_soc_pct == 10.0
        assert dr.max_soc_pct == 95.0
        assert dr.grid_frequency_hz in (50.0, 60.0)


# ---------------------------------------------------------------------------
# SEN — Chile (duck curve always returns 24 prices)
# ---------------------------------------------------------------------------

class TestSENAdapter:
    def setup_method(self):
        from src.core.market_adapter import SENAdapter
        self.adapter = SENAdapter()

    def test_returns_24_hourly_prices(self):
        prices = self.adapter.get_spot_prices(_DATE, "Maitencillo")
        assert len(prices) == 24

    def test_prices_are_non_negative(self):
        prices = self.adapter.get_spot_prices(_DATE, "Polpaico")
        assert all(p.price_usd_mwh >= 0 for p in prices)

    def test_market_id_is_sen(self):
        assert self.adapter.market_id == "SEN"

    def test_ancillary_services_contain_csf(self):
        services = self.adapter.get_ancillary_services()
        ids = [s.service_id for s in services]
        assert "CSF" in ids

    def test_provides_8_nodes(self):
        zones = self.adapter.get_market_zones()
        assert len(zones) == 8


# ---------------------------------------------------------------------------
# COES — Peru (mock + fallback)
# ---------------------------------------------------------------------------

class TestCOESAdapter:
    def setup_method(self):
        from src.core.market_adapter import COESAdapter
        self.adapter = COESAdapter()

    def test_fallback_on_api_error_returns_24_prices(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "LIMA_SUR")
        assert len(prices) == 24

    def test_live_data_parsed_correctly(self):
        mock_data = [{"hora": h + 1, "precio": 38.5 + h * 0.5, "barra": "LIMA_SUR"}
                     for h in range(24)]
        with patch("src.core.market_adapter._http_get", return_value=_make_response(mock_data)):
            prices = self.adapter.get_spot_prices(_DATE, "LIMA_SUR")
        assert len(prices) == 24
        assert prices[0].price_usd_mwh == pytest.approx(38.5, rel=0.01)

    def test_dispatch_frequency_is_60hz(self):
        assert self.adapter.get_dispatch_rules().grid_frequency_hz == 60.0

    def test_country_is_peru(self):
        assert self.adapter.country == "Peru"


# ---------------------------------------------------------------------------
# XM — Colombia (mock + fallback)
# ---------------------------------------------------------------------------

class TestXMAdapter:
    def setup_method(self):
        from src.core.market_adapter import XMAdapter
        self.adapter = XMAdapter()

    def test_fallback_returns_24_prices(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "BOGOTA")
        assert len(prices) == 24

    def test_cop_usd_conversion(self):
        """120000 COP/kWh → ~28.57 USD/MWh at 4200 COP/USD."""
        mock_data = {
            "Items": [{"Hour": h + 1, "Values": {"PrecioOfertaBolsaEscasez": 120000.0}}
                      for h in range(24)]
        }
        with patch("src.core.market_adapter._http_get", return_value=_make_response(mock_data)):
            prices = self.adapter.get_spot_prices(_DATE, "BOGOTA")
        expected_usd = 120000.0 * 1000 / 4200.0
        assert prices[0].price_usd_mwh == pytest.approx(expected_usd, rel=0.01)

    def test_bimodal_peak_hours(self):
        rules = self.adapter.get_dispatch_rules()
        assert 9 in rules.peak_hours and 19 in rules.peak_hours


# ---------------------------------------------------------------------------
# CENACE — Mexico (mock + fallback)
# ---------------------------------------------------------------------------

class TestCENACEAdapter:
    def setup_method(self):
        from src.core.market_adapter import CENACEAdapter
        self.adapter = CENACEAdapter()

    def test_fallback_returns_24_prices(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "MEXTRA-115")
        assert len(prices) == 24

    def test_mxn_usd_conversion(self):
        """900 MXN/MWh → 50 USD/MWh at 18 MXN/USD."""
        mock_data = {"Resultados": [{"Hora": str(h + 1), "PML": 900.0} for h in range(24)]}
        with patch("src.core.market_adapter._http_get", return_value=_make_response(mock_data)):
            prices = self.adapter.get_spot_prices(_DATE, "MEXTRA-115")
        assert prices[0].price_usd_mwh == pytest.approx(900.0 / 18.0, rel=0.01)

    def test_frequency_60hz(self):
        assert self.adapter.get_dispatch_rules().grid_frequency_hz == 60.0


# ---------------------------------------------------------------------------
# CAISO — California (mock + fallback)
# ---------------------------------------------------------------------------

class TestCAISOAdapter:
    def setup_method(self):
        from src.core.market_adapter import CAISOAdapter
        self.adapter = CAISOAdapter()

    def test_fallback_returns_24_prices(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "TH_NP15_GEN-APND")
        assert len(prices) == 24

    def test_duck_curve_peak_covers_15_to_21(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "TH_NP15_GEN-APND")
        # Peak hour (18h) should have higher price than off-peak (3h)
        assert prices[18].price_usd_mwh > prices[3].price_usd_mwh

    def test_live_data_5min_to_hourly_avg(self):
        """Mock 12 × 5-min intervals per hour (2 hours worth)."""
        report_data = []
        for h in range(24):
            for interval in range(12):
                ts = f"2026-03-12T{h:02d}:05:00-0000"
                report_data.append({"INTERVAL_START_GMT": ts, "VALUE": 50.0 + h})
        mock_data = {
            "OASISReport": {
                "MessagePayload": {
                    "RTO": {"REPORT_DATA": report_data}
                }
            }
        }
        with patch("src.core.market_adapter._http_get", return_value=_make_response(mock_data)):
            prices = self.adapter.get_spot_prices(_DATE, "TH_NP15_GEN-APND")
        assert len(prices) == 24
        assert prices[10].price_usd_mwh == pytest.approx(60.0, rel=0.01)

    def test_max_daily_cycles_3(self):
        rules = self.adapter.get_dispatch_rules()
        assert rules.max_daily_cycles == 3

    def test_zones_include_np15_and_sp15(self):
        zones = self.adapter.get_market_zones()
        assert "TH_NP15_GEN-APND" in zones
        assert "TH_SP15_GEN-APND" in zones

    def test_ancillary_services_include_regulation(self):
        services = {s.service_id for s in self.adapter.get_ancillary_services()}
        assert "REG_UP" in services
        assert "REG_DN" in services

    def test_currency_is_usd(self):
        assert self.adapter.get_dispatch_rules().currency == "USD"


# ---------------------------------------------------------------------------
# ERCOT — Texas (mock + fallback)
# ---------------------------------------------------------------------------

class TestERCOTAdapter:
    def setup_method(self):
        from src.core.market_adapter import ERCOTAdapter
        self.adapter = ERCOTAdapter()

    def test_fallback_returns_24_prices(self):
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "HB_NORTH")
        assert len(prices) == 24

    def test_high_peak_amp_for_texas_scarcity(self):
        """Texas scarcity events → peak price >> base."""
        with patch("src.core.market_adapter._http_get", return_value=None):
            prices = self.adapter.get_spot_prices(_DATE, "HB_NORTH")
        peak_price = max(p.price_usd_mwh for p in prices)
        # With peak_amp=80, peak should exceed base (40)
        assert peak_price > 40.0

    def test_live_data_15min_aggregated(self):
        """4 intervals of 15 min per hour → hourly average."""
        rows = [
            ["deliveryDate", "deliveryHour", "deliveryInterval", "spp"]  # header
        ]
        for h in range(24):
            for interval in range(4):
                rows.append(["2026-03-12", str(h + 1), str(interval + 1), str(42.0 + h)])
        mock_data = {"data": rows}
        with patch("src.core.market_adapter._http_get", return_value=_make_response(mock_data)):
            prices = self.adapter.get_spot_prices(_DATE, "HB_NORTH")
        assert len(prices) == 24
        assert prices[5].price_usd_mwh == pytest.approx(47.0, rel=0.01)

    def test_max_daily_cycles_4(self):
        assert self.adapter.get_dispatch_rules().max_daily_cycles == 4

    def test_ercot_hubs_include_west(self):
        assert "HB_WEST" in self.adapter.get_market_zones()

    def test_ancillary_ecrs_and_rrs(self):
        svc_ids = {s.service_id for s in self.adapter.get_ancillary_services()}
        assert "ECRS" in svc_ids
        assert "RRS" in svc_ids


# ---------------------------------------------------------------------------
# ENTSO-E — Europe (mock XML + fallback)
# ---------------------------------------------------------------------------

_ENTSOE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument
    xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
  <TimeSeries>
    <Period>
      <resolution>PT60M</resolution>
      <Point><position>1</position><price.amount>80.00</price.amount></Point>
      <Point><position>2</position><price.amount>78.00</price.amount></Point>
      <Point><position>3</position><price.amount>75.00</price.amount></Point>
      <Point><position>4</position><price.amount>72.00</price.amount></Point>
      <Point><position>5</position><price.amount>70.00</price.amount></Point>
      <Point><position>6</position><price.amount>69.00</price.amount></Point>
      <Point><position>7</position><price.amount>72.00</price.amount></Point>
      <Point><position>8</position><price.amount>85.00</price.amount></Point>
      <Point><position>9</position><price.amount>95.00</price.amount></Point>
      <Point><position>10</position><price.amount>100.00</price.amount></Point>
      <Point><position>11</position><price.amount>98.00</price.amount></Point>
      <Point><position>12</position><price.amount>96.00</price.amount></Point>
      <Point><position>13</position><price.amount>94.00</price.amount></Point>
      <Point><position>14</position><price.amount>93.00</price.amount></Point>
      <Point><position>15</position><price.amount>92.00</price.amount></Point>
      <Point><position>16</position><price.amount>95.00</price.amount></Point>
      <Point><position>17</position><price.amount>102.00</price.amount></Point>
      <Point><position>18</position><price.amount>110.00</price.amount></Point>
      <Point><position>19</position><price.amount>108.00</price.amount></Point>
      <Point><position>20</position><price.amount>100.00</price.amount></Point>
      <Point><position>21</position><price.amount>92.00</price.amount></Point>
      <Point><position>22</position><price.amount>85.00</price.amount></Point>
      <Point><position>23</position><price.amount>82.00</price.amount></Point>
      <Point><position>24</position><price.amount>78.00</price.amount></Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""


class TestENTSOEAdapter:
    def setup_method(self):
        from src.core.market_adapter import ENTSOEAdapter
        self.adapter = ENTSOEAdapter()

    def test_fallback_without_token(self):
        """Without token, should silently use duck curve fallback."""
        import os
        saved = os.environ.pop("BESSAI_ENTSOE_TOKEN", None)
        try:
            with patch("src.core.market_adapter._http_get", return_value=None):
                prices = self.adapter.get_spot_prices(_DATE, "DE-LU")
            assert len(prices) == 24
        finally:
            if saved:
                os.environ["BESSAI_ENTSOE_TOKEN"] = saved

    def test_xml_parsing_with_mock_token(self):
        """Parse synthetic XML and verify EUR→USD conversion."""
        import os
        os.environ["BESSAI_ENTSOE_TOKEN"] = "FAKE_TOKEN"
        os.environ["BESSAI_EUR_USD_RATE"] = "1.08"
        try:
            mock_resp = _make_response(_ENTSOE_XML)
            with patch("src.core.market_adapter._http_get", return_value=mock_resp):
                prices = self.adapter.get_spot_prices(_DATE, "DE-LU")
            assert len(prices) == 24
            # Hour 0 = position 1: 80 EUR × 1.08 = 86.4 USD/MWh
            assert prices[0].price_usd_mwh == pytest.approx(80.0 * 1.08, rel=0.01)
        finally:
            os.environ.pop("BESSAI_ENTSOE_TOKEN", None)
            os.environ.pop("BESSAI_EUR_USD_RATE", None)

    def test_all_eu_zones_registered(self):
        zones = self.adapter.get_market_zones()
        for zone in ["DE-LU", "FR", "ES", "GB", "PT"]:
            assert zone in zones, f"Zone {zone} missing from ENTSO-E adapter"

    def test_frequency_50hz(self):
        assert self.adapter.get_dispatch_rules().grid_frequency_hz == 50.0

    def test_ancillary_includes_fcr_and_afrr(self):
        svc = {s.service_id for s in self.adapter.get_ancillary_services()}
        assert "FCR" in svc
        assert "aFRR" in svc

    def test_peak_hours_day_profile(self):
        rules = self.adapter.get_dispatch_rules()
        # EU industrial: peak 8-20
        assert 8 in rules.peak_hours
        assert 15 in rules.peak_hours
        assert 3 not in rules.peak_hours  # off-peak at 3 AM


# ---------------------------------------------------------------------------
# Cross-adapter: all 7 adapters share a contract
# ---------------------------------------------------------------------------

ALL_MARKETS = ["SEN", "COES", "XM", "CENACE", "CAISO", "ERCOT", "ENTSOE"]


@pytest.mark.parametrize("market_id", ALL_MARKETS)
def test_all_adapters_fallback_returns_24_prices(market_id):
    """Every adapter must return exactly 24 SpotPrice objects when API fails."""
    import os

    from src.core.market_adapter import MarketAdapterRegistry
    # Ensure ENTSO-E token missing to trigger fallback
    os.environ.pop("BESSAI_ENTSOE_TOKEN", None)
    MarketAdapterRegistry.reset()
    adapter = MarketAdapterRegistry.get(market_id)
    with patch("src.core.market_adapter._http_get", return_value=None):
        prices = adapter.get_spot_prices(_DATE)
    assert len(prices) == 24, f"{market_id}: expected 24 prices, got {len(prices)}"
    assert all(p.price_usd_mwh >= 0 for p in prices), f"{market_id}: negative prices found"
    MarketAdapterRegistry.reset()


@pytest.mark.parametrize("market_id", ALL_MARKETS)
def test_all_adapters_have_ancillary_services(market_id):
    """All adapters must expose at least 2 ancillary services."""
    from src.core.market_adapter import MarketAdapterRegistry
    MarketAdapterRegistry.reset()
    adapter = MarketAdapterRegistry.get(market_id)
    services = adapter.get_ancillary_services()
    assert len(services) >= 2, f"{market_id}: too few ancillary services"
    MarketAdapterRegistry.reset()


@pytest.mark.parametrize("market_id", ALL_MARKETS)
def test_all_adapters_dispatch_rules_valid(market_id):
    """Dispatch rules must be internally consistent."""
    from src.core.market_adapter import MarketAdapterRegistry
    MarketAdapterRegistry.reset()
    adapter = MarketAdapterRegistry.get(market_id)
    rules = adapter.get_dispatch_rules()
    assert 0 <= rules.min_soc_pct < rules.max_soc_pct <= 100
    assert rules.max_daily_cycles >= 1
    assert rules.grid_frequency_hz in (50.0, 60.0)
    MarketAdapterRegistry.reset()
