"""
tests/test_integration_modbus.py
====================================
Integration-level tests for Modbus register decoding pipeline.
Uses fully mocked ModbusTcpClient to simulate a real SUN2000 device.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.drivers.luna2000_driver import BatteryMode, LUNADriver
from src.interfaces.sun2000_monitor import (
    _ALARM1_BITS,
    _ALARM2_BITS,
    InverterState,
    SUN2000Monitor,
    decode_alarm_register,
)

# ---------------------------------------------------------------------------
# Realistic SUN2000 register dataset (12:00 sunny day, 60% SOC)
# ---------------------------------------------------------------------------

REGISTER_MAP: dict[int, list[int]] = {
    # Inverter state: GRID_CONNECTED (256)
    32089: [256],
    # PV1: 360V, 8.50A
    32016: [3600],    # 3600 * 0.1 = 360.0 V
    32017: [850],     # 850 * 0.01 = 8.50 A  (INT16 positive)
    # PV2: 355V, 8.20A
    32018: [3550],
    32019: [820],
    # PV total power: 5.94 kW → INT32 = 5940 → 0x00001734
    32064: [0x0000, 5940],
    # AC voltage: 230.5V
    32069: [2305],    # 2305 * 0.1 = 230.5 V
    # AC power: 5.80 kW → INT32 = 5800
    32080: [0x0000, 5800],
    # Frequency: 50.01 Hz
    32085: [5001],    # 5001 * 0.01 = 50.01 Hz
    # Temperature: 42.3°C → INT16 = 423
    32087: [423],
    # Daily energy: 28.50 kWh → UINT32 = 2850 * 0.01
    32114: [0x0000, 2850],
    # Total energy: 5280.00 kWh → UINT32 = 528000
    32106: [0x0008, 0x1000],  # 0x00081000 = 528384 * 0.01 = 5283.84 kWh
    # No alarms
    32008: [0x0000],
    32009: [0x0000],
    # LUNA2000: SOC 60%, -3kW discharging, 25°C
    37760: [600],                  # 60.0%
    37765: [0xFFFF, 0xF448],       # -3000 * 0.001 = -3.0 kW
    37752: [250],                  # 25.0°C
    # LUNA2000 full telemetry
    37761: [970],                  # SOH 97.0%
    37762: [88],                   # 88 cycles
    37758: [0x0000, 14000],        # 14.0 kWh
    37800: [4750],                 # 475.0 V
    37801: [0xFFCE],               # -50 * 0.1 = -5.0 A (discharging)
    47086: [0],                    # MAX_SELF_CONSUMPTION
}


def _mock_client(reg_map: dict[int, list[int]] | None = None) -> MagicMock:
    rmap = reg_map or REGISTER_MAP
    client = MagicMock()

    def _read(address, count, slave=3):
        r = MagicMock()
        r.isError.return_value = False
        r.registers = rmap.get(address, [0] * count)
        return r

    client.read_holding_registers.side_effect = _read
    client.write_register.return_value = MagicMock(isError=lambda: False)
    client.connect.return_value = True
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestModbusRegisterDecoding:
    """Validate full register → physical value decoding pipeline."""

    def setup_method(self):
        self.mon = SUN2000Monitor(host="127.0.0.1", site_id="INT-TEST")
        self.mon._client = _mock_client()

    def test_inverter_state_running(self):
        raw = self.mon._read(32089, 1)[0]
        assert InverterState.from_raw(raw) == InverterState.GRID_CONNECTED

    def test_pv1_voltage(self):
        raw = self.mon._read(32016, 1)[0]
        voltage = raw * 0.1
        assert abs(voltage - 360.0) < 0.01

    def test_pv1_current(self):
        raw = self.mon._read(32017, 1)[0]
        current = self.mon._i16(raw) * 0.01
        assert abs(current - 8.50) < 0.01

    def test_ac_power_int32(self):
        regs = self.mon._read(32080, 2)
        power_kw = self.mon._i32(*regs) * 0.001
        assert abs(power_kw - 5.80) < 0.001

    def test_temperature_int16(self):
        raw = self.mon._read(32087, 1)[0]
        temp = self.mon._i16(raw) * 0.1
        assert abs(temp - 42.3) < 0.01

    def test_daily_energy_uint32(self):
        regs = self.mon._read(32114, 2)
        energy = self.mon._u32(*regs) * 0.01
        assert abs(energy - 28.50) < 0.01

    def test_no_alarms_decoded(self):
        a1 = self.mon._read(32008, 1)[0]
        a2 = self.mon._read(32009, 1)[0]
        alarms = (decode_alarm_register(a1, _ALARM1_BITS) +
                  decode_alarm_register(a2, _ALARM2_BITS))
        assert alarms == []


class TestLUNARegisters:
    """Validate LUNA2000 register decoding."""

    def setup_method(self):
        self.drv = LUNADriver(host="127.0.0.1", slave_id=3)
        self.drv._client = _mock_client()

    def test_soc_reads_60_percent(self):
        raw = self.drv._read_regs(37760, 1)[0]
        assert abs(raw * 0.1 - 60.0) < 0.01

    def test_battery_power_discharging(self):
        regs = self.drv._read_regs(37765, 2)
        power = self.drv._to_int32(*regs) * 0.001
        assert power < 0, "discharging should be negative"
        assert abs(power - (-3.0)) < 0.001

    def test_temperature_positive(self):
        raw = self.drv._read_regs(37752, 1)[0]
        temp = self.drv._to_int16(raw) * 0.1
        assert abs(temp - 25.0) < 0.01

    def test_mode_write_is_called(self):
        self.drv._write_reg(47086, int(BatteryMode.TIME_OF_USE))
        self.drv._client.write_register.assert_called_once()
        call_kwargs = self.drv._client.write_register.call_args
        # address is first positional arg or 'address' kwarg
        args = call_kwargs.args
        kwargs = call_kwargs.kwargs
        addr = args[0] if args else kwargs.get("address")
        assert addr == 47086


class TestAlarmRegisterEdgeCases:
    """Edge cases for alarm bitmask decoding."""

    def test_all_alarm1_bits_set(self):
        alarms = decode_alarm_register(0xFFFF, _ALARM1_BITS)
        assert len(alarms) == len(_ALARM1_BITS)

    def test_alarm_names_are_strings(self):
        alarms = decode_alarm_register(0xFFFF, _ALARM2_BITS)
        for a in alarms:
            assert isinstance(a, str)
