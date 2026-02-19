"""
tests/test_vpp_publisher.py
============================
Unit tests for VPPPublisher and OpenADREvent.
"""

from __future__ import annotations

import json

import pytest

from src.interfaces.vpp_publisher import OpenADREvent, SiteCapacity, VPPPublisher


def _site(site_id: str = "CL-001", available_kw: float = 30.0, soc: float = 75.0) -> SiteCapacity:
    return SiteCapacity(site_id=site_id, soc_pct=soc, max_power_kw=50.0, available_kw=available_kw)


class TestVPPPublisher:

    def test_register_site_increments_n_sites(self):
        vpp = VPPPublisher()
        vpp.register_site(_site("CL-001"))
        vpp.register_site(_site("CL-002"))
        assert vpp.n_sites == 2

    def test_remove_site_decrements_n_sites(self):
        vpp = VPPPublisher()
        vpp.register_site(_site("CL-001"))
        vpp.remove_site("CL-001")
        assert vpp.n_sites == 0

    def test_aggregate_flex_sums_available_kw(self):
        vpp = VPPPublisher()
        vpp.register_site(_site("A", available_kw=20.0))
        vpp.register_site(_site("B", available_kw=30.0))
        assert vpp.aggregate_flex_kw() == pytest.approx(50.0)

    def test_fleet_avg_soc_empty(self):
        vpp = VPPPublisher()
        assert vpp.fleet_avg_soc() == pytest.approx(0.0)

    def test_fleet_avg_soc_multiple(self):
        vpp = VPPPublisher()
        vpp.register_site(_site("A", soc=80.0))
        vpp.register_site(_site("B", soc=60.0))
        assert vpp.fleet_avg_soc() == pytest.approx(70.0)

    def test_publish_event_below_threshold_returns_none(self):
        vpp = VPPPublisher(min_flex_kw=100.0)
        vpp.register_site(_site("A", available_kw=5.0))
        event = vpp.publish_event()
        assert event is None

    def test_publish_event_above_threshold_returns_event(self):
        vpp = VPPPublisher(min_flex_kw=10.0)
        vpp.register_site(_site("A", available_kw=50.0))
        event = vpp.publish_event()
        assert event is not None
        assert isinstance(event.event_id, str)

    def test_open_adr_event_json_parseable(self):
        vpp = VPPPublisher(min_flex_kw=5.0)
        vpp.register_site(_site("A", available_kw=25.0))
        event = vpp.publish_event()
        assert event is not None
        data = json.loads(event.to_json())
        assert data["objectType"] == "EVENT"
        assert "intervals" in data
        assert len(data["targets"]) == 1

    def test_empty_fleet_publish_returns_none(self):
        vpp = VPPPublisher(min_flex_kw=10.0)
        assert vpp.publish_event() is None


class TestOpenADREvent:

    def test_event_has_unique_ids(self):
        e1 = OpenADREvent()
        e2 = OpenADREvent()
        assert e1.event_id != e2.event_id

    def test_event_json_contains_required_fields(self):
        event = OpenADREvent(targets=[{"type": "RESOURCE_NAME", "values": ["site-1"]}])
        payload = json.loads(event.to_json())
        assert payload["programID"] == "BESSAI-VPP-001"
        assert "intervalPeriod" in payload
