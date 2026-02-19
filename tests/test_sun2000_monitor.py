"""
tests/test_sun2000_monitor.py
================================
Tests for the SUN2000Monitor and SUN2000Telemetry classes.
All tests use mock Modbus clients — no real hardware needed.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.interfaces.sun2000_monitor import (
    InverterState,
    PVStringData,
    SUN2000Monitor,
    SUN2000Telemetry,
    decode_alarm_register,
    _ALARM1_BITS,
    _ALARM2_BITS,
)
from src.interfaces.alert_manager import AlertManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor() -> SUN2000Monitor:
    mgr = AlertManager(site_id="TEST-001", dedup_window_s=0.0)
    mon = SUN2000Monitor(host="127.0.0.1", site_id="TEST-001", alert_mgr=mgr)
    return mon


class TestInverterState:
    def test_from_raw_running(self):
        assert InverterState.from_raw(256) == InverterState.GRID_CONNECTED

    def test_from_raw_fault(self):
        assert InverterState.from_raw(512) == InverterState.FAULT

    def test_from_raw_unknown(self):
        assert InverterState.from_raw(9999) == InverterState.UNKNOWN

    def test_from_raw_standby(self):
        assert InverterState.from_raw(0) == InverterState.STANDBY


class TestPVStringData:
    def test_power_calculation(self):
        pv = PVStringData(string_id=1, voltage_v=360.0, current_a=5.5)
        assert abs(pv.power_w - 1980.0) < 0.01

    def test_zero_current_zero_power(self):
        pv = PVStringData(1, 400.0, 0.0)
        assert pv.power_w == 0.0


class TestDecodeAlarmRegister:
    def test_no_alarms_zero_register(self):
        alarms = decode_alarm_register(0x0000, _ALARM1_BITS)
        assert alarms == []

    def test_single_alarm_bit0(self):
        alarms = decode_alarm_register(0x0001, _ALARM1_BITS)
        assert "High String Input Reverse" in alarms

    def test_multiple_alarms(self):
        # bits 0 + 2 + 3 set
        raw = 0b0001101
        alarms = decode_alarm_register(raw, _ALARM1_BITS)
        assert "High String Input Reverse" in alarms
        assert "Grounding Error" in alarms
        assert "Low Insulation Resistance" in alarms

    def test_alarm2_arc_fault(self):
        raw = 0b10   # bit 1 = DC Arc Fault
        alarms = decode_alarm_register(raw, _ALARM2_BITS)
        assert "DC Arc Fault" in alarms


class TestSUN2000Telemetry:
    def _make(self, **kwargs) -> SUN2000Telemetry:
        defaults = dict(
            site_id="TEST-001",
            state=InverterState.GRID_CONNECTED,
            active_alarms=[],
            pv_strings=[PVStringData(1, 350.0, 5.0), PVStringData(2, 348.0, 4.8)],
            pv_total_power_kw=3.42,
            ac_voltage_v=230.0,
            ac_power_kw=3.35,
            ac_frequency_hz=50.0,
            temperature_c=38.5,
            daily_energy_kwh=12.5,
            total_energy_kwh=1250.0,
            batt_soc_pct=72.5,
            batt_power_kw=-2.5,
            batt_temperature_c=26.0,
        )
        return SUN2000Telemetry(**{**defaults, **kwargs})

    def test_is_safe_no_alarms(self):
        tel = self._make()
        assert tel.is_safe

    def test_is_not_safe_fault_state(self):
        tel = self._make(state=InverterState.FAULT)
        assert not tel.is_safe

    def test_is_not_safe_critical_alarm(self):
        tel = self._make(active_alarms=["DC Arc Fault"])
        assert not tel.is_safe

    def test_to_dict_structure(self):
        tel = self._make()
        d = tel.to_dict()
        assert "pv" in d and "strings" in d["pv"]
        assert "ac" in d
        assert "battery" in d
        assert "energy" in d
        assert d["state"] == "GRID_CONNECTED"

    def test_to_dict_pv_strings_count(self):
        tel = self._make()
        d = tel.to_dict()
        assert len(d["pv"]["strings"]) == 2
        assert d["pv"]["strings"][0]["id"] == 1

    def test_to_dict_battery_none_when_not_connected(self):
        tel = self._make(batt_soc_pct=None, batt_power_kw=None, batt_temperature_c=None)
        d = tel.to_dict()
        assert d["battery"]["soc_pct"] is None

    def test_ac_power_rounded(self):
        tel = self._make(ac_power_kw=3.14159)
        d = tel.to_dict()
        assert d["ac"]["power_kw"] == 3.142

    def test_site_id_propagated(self):
        tel = self._make(site_id="CL-IQUIQUE-01")
        assert tel.to_dict()["site_id"] == "CL-IQUIQUE-01"
