# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import pytest
from src.core.ot_modbus_guard import OTModbusGuard, GuardPolicy


def test_modbus_guard_normal_dispatch():
    guard = OTModbusGuard(shared_secret="secret-key")
    res = guard.inspect_power_setpoint(power_kw=1500.0, slave_id=1, client_ip="192.168.1.50")
    assert res.allowed is True
    assert res.sanitized_value == 1500.0


def test_modbus_guard_rejects_out_of_bounds():
    guard = OTModbusGuard()
    res = guard.inspect_power_setpoint(power_kw=99999.0, slave_id=1, client_ip="192.168.1.50")
    assert res.allowed is False
    assert res.violation_code == "OVER_CAPACITY_ATTACK"


def test_modbus_guard_critical_dispatch_hmac():
    guard = OTModbusGuard(shared_secret="secure-bess-key")
    # Dispatch > 2.5 MW requires HMAC
    token = guard.generate_hmac(-3500.0)
    res_valid = guard.inspect_power_setpoint(power_kw=-3500.0, slave_id=1, client_ip="192.168.1.50", auth_token=token)
    assert res_valid.allowed is True

    # Invalid token rejected
    res_invalid = guard.inspect_power_setpoint(power_kw=-3500.0, slave_id=1, client_ip="192.168.1.50", auth_token="fake-token")
    assert res_invalid.allowed is False
    assert res_invalid.violation_code == "UNAUTHENTICATED_DISPATCH"
