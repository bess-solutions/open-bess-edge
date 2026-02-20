"""
tests/test_luna2000_driver.py
================================
Tests for the LUNA2000 battery ESS driver.
All tests use mock Modbus registers — no real hardware needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.drivers.luna2000_driver import (
    BatteryMode,
    LUNADriver,
    LUNATelemetry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_register_mock(values: dict[int, list[int]]):
    """Return a mock Modbus client that returns preset register values."""
    mock = MagicMock()

    def _read(address, count, slave=3):
        result = MagicMock()
        result.isError.return_value = False
        result.registers = values.get(address, [0] * count)
        return result

    mock.read_holding_registers.side_effect = _read
    mock.write_register.return_value = MagicMock(isError=lambda: False)
    mock.connect.return_value = True
    return mock


# Realistic register values for a 10 kWh LUNA2000 at 60% SOC
_LUNA_REGS: dict[int, list[int]] = {
    37752: [0x0106],  # temp = 262 * 0.1 = 26.2°C
    37760: [600],  # SOC = 600 * 0.1 = 60.0%
    37761: [980],  # SOH = 980 * 0.1 = 98.0%
    37762: [123],  # cycles = 123
    37758: [0, 10000],  # capacity = 10000 * 0.001 = 10.0 kWh
    37765: [0xFFFF, 0xD8F0],  # power = INT32(-10000*0.001=-10kW) discharging
    37800: [4800],  # voltage = 4800*0.1 = 480 V
    37801: [0xFFD2],  # current INT16(-46*0.1=-4.6A) discharging
    47086: [0],  # mode = MAX_SELF_CONSUMPTION
}


class TestLUNATelemetry:
    """Unit tests for LUNATelemetry dataclass."""

    def _make_tel(self, **kwargs) -> LUNATelemetry:
        defaults = dict(
            soc_pct=60.0,
            soh_pct=98.0,
            power_kw=-3.0,
            voltage_v=480.0,
            current_a=-6.25,
            temperature_c=26.2,
            cycle_count=123,
            capacity_kwh=10.0,
        )
        return LUNATelemetry(**{**defaults, **kwargs})

    def test_is_discharging_when_negative_power(self):
        tel = self._make_tel(power_kw=-3.0)
        assert tel.is_discharging
        assert not tel.is_charging
        assert not tel.is_idle

    def test_is_charging_when_positive_power(self):
        tel = self._make_tel(power_kw=2.5)
        assert tel.is_charging
        assert not tel.is_discharging

    def test_is_idle_near_zero_power(self):
        tel = self._make_tel(power_kw=0.005)
        assert tel.is_idle

    def test_to_dict_contains_all_keys(self):
        tel = self._make_tel()
        d = tel.to_dict()
        for k in (
            "soc_pct",
            "soh_pct",
            "power_kw",
            "voltage_v",
            "current_a",
            "temperature_c",
            "cycle_count",
            "capacity_kwh",
            "working_mode",
            "is_charging",
            "is_discharging",
            "timestamp",
        ):
            assert k in d, f"missing key: {k}"

    def test_to_dict_rounds_values(self):
        tel = self._make_tel(soc_pct=60.123456)
        d = tel.to_dict()
        # Should be rounded to 1 decimal
        assert d["soc_pct"] == 60.1

    def test_working_mode_name_in_dict(self):
        tel = self._make_tel()
        tel.working_mode = BatteryMode.TIME_OF_USE
        assert tel.to_dict()["working_mode"] == "TIME_OF_USE"


class TestBatteryMode:
    def test_enum_values(self):
        assert BatteryMode.MAX_SELF_CONSUMPTION == 0
        assert BatteryMode.FULLY_CHARGED == 1
        assert BatteryMode.TIME_OF_USE == 2
        assert BatteryMode.REMOTE_DISPATCH == 3


class TestLUNADriverRegisterDecoding:
    """Test INT32/INT16/UINT* decoding helpers."""

    def test_i32_positive(self):
        assert LUNADriver._to_int32(0x0000, 0x2710) == 10000

    def test_i32_negative(self):
        # -10000 in two's complement INT32 = 0xFFFFD8F0
        assert LUNADriver._to_int32(0xFFFF, 0xD8F0) == -10000

    def test_u32(self):
        assert LUNADriver._to_uint32(0x0001, 0x86A0) == 100000

    def test_i16_positive(self):
        assert LUNADriver._to_int16(0x0106) == 262

    def test_i16_negative(self):
        # -46 in INT16 = 0xFFD2
        assert LUNADriver._to_int16(0xFFD2) == -46


class TestLUNADriverAsync:
    """Integration-style tests with mock Modbus client."""

    def _driver_with_mock(self) -> tuple[LUNADriver, MagicMock]:
        drv = LUNADriver(host="127.0.0.1", slave_id=3)
        mock_client = _make_register_mock(_LUNA_REGS)
        drv._client = mock_client
        return drv, mock_client

    def test_read_soc_register_raw(self):
        """Verify _read_regs returns the mocked SOC register."""
        drv, _ = self._driver_with_mock()
        regs = drv._read_regs(37760, 1)
        assert regs == [600]
        assert 600 * 0.1 == 60.0

    def test_read_mode_returns_enum(self):
        """Verify working mode register is read correctly."""
        drv, _ = self._driver_with_mock()
        mode_raw = drv._read_regs(47086, 1)[0]
        mode = BatteryMode(min(mode_raw, 3))
        assert mode == BatteryMode.MAX_SELF_CONSUMPTION
