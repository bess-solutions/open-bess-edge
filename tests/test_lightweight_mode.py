# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_lightweight_mode.py
================================
Unit tests for ``src.core.lightweight_mode``.

Covers:
  - LightweightModeManager forced / env-var activation
  - should_enable() for optional and always-active components
  - Unknown component warnings (no crash)
  - status_dict() output shape
  - Module-level convenience helpers: is_lightweight_active(), should_enable_component()
"""

from __future__ import annotations

import os

import pytest
from src.core.lightweight_mode import (
    _ALWAYS_ACTIVE,
    _OPTIONAL_COMPONENTS,
    LightweightModeManager,
    is_lightweight_active,
    should_enable_component,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lwm(force: bool = False, env_val: str | None = None) -> LightweightModeManager:
    """Build a manager, optionally injecting BESSAI_LIGHTWEIGHT into env."""
    if env_val is not None:
        os.environ["BESSAI_LIGHTWEIGHT"] = env_val
    else:
        os.environ.pop("BESSAI_LIGHTWEIGHT", None)
    try:
        return LightweightModeManager(force_active=force)
    finally:
        os.environ.pop("BESSAI_LIGHTWEIGHT", None)


# ---------------------------------------------------------------------------
# Activation logic
# ---------------------------------------------------------------------------

class TestActivation:
    def test_inactive_by_default(self):
        lwm = _lwm()
        assert not lwm.is_active

    def test_force_active(self):
        lwm = _lwm(force=True)
        assert lwm.is_active

    @pytest.mark.parametrize("val", ["1", "true", "True", "TRUE", "yes", "on", "YES"])
    def test_env_truthy_activates(self, val: str):
        lwm = _lwm(env_val=val)
        assert lwm.is_active

    @pytest.mark.parametrize("val", ["0", "false", "no", "off", "", "FALSE"])
    def test_env_falsy_stays_inactive(self, val: str):
        lwm = _lwm(env_val=val)
        assert not lwm.is_active

    def test_disabled_set_empty_when_inactive(self):
        lwm = _lwm()
        assert len(lwm.disabled_components) == 0

    def test_disabled_set_populated_when_active(self):
        lwm = _lwm(force=True)
        assert lwm.disabled_components == _OPTIONAL_COMPONENTS


# ---------------------------------------------------------------------------
# should_enable()
# ---------------------------------------------------------------------------

class TestShouldEnable:
    # --- inactive mode: everything enabled ---

    def test_optional_enabled_when_inactive(self):
        lwm = _lwm()
        for comp in _OPTIONAL_COMPONENTS:
            assert lwm.should_enable(comp), f"{comp} should be enabled in normal mode"

    def test_always_active_enabled_when_inactive(self):
        lwm = _lwm()
        for comp in _ALWAYS_ACTIVE:
            assert lwm.should_enable(comp)

    # --- active / lightweight mode ---

    def test_optional_disabled_when_active(self):
        lwm = _lwm(force=True)
        for comp in _OPTIONAL_COMPONENTS:
            assert not lwm.should_enable(comp), f"{comp} should be disabled in lightweight mode"

    def test_always_active_never_disabled(self):
        lwm = _lwm(force=True)
        for comp in _ALWAYS_ACTIVE:
            assert lwm.should_enable(comp), f"{comp} must ALWAYS be active"

    def test_safety_guard_always_on(self):
        lwm = _lwm(force=True)
        assert lwm.should_enable("safety_guard")

    def test_modbus_driver_always_on(self):
        lwm = _lwm(force=True)
        assert lwm.should_enable("modbus_driver")

    def test_opentelemetry_off_in_lightweight(self):
        lwm = _lwm(force=True)
        assert not lwm.should_enable("opentelemetry")

    def test_vpp_publisher_off_in_lightweight(self):
        lwm = _lwm(force=True)
        assert not lwm.should_enable("vpp_publisher")

    def test_fl_client_off_in_lightweight(self):
        lwm = _lwm(force=True)
        assert not lwm.should_enable("fl_client")

    # --- unknown component ---

    def test_unknown_component_does_not_raise(self):
        """Unknown components log a warning but should NOT raise an exception."""
        lwm = _lwm()
        result = lwm.should_enable("totally_unknown_module")
        # In inactive mode, unknown components are still enabled (not in disabled set)
        assert result is True

    def test_unknown_component_disabled_in_lightweight(self):
        """Unknown components not in _OPTIONAL_COMPONENTS are NOT disabled
        in lightweight mode — they pass through (returning True).
        This is by design: only known optional components are gated."""
        lwm = _lwm(force=True)
        result = lwm.should_enable("totally_unknown_module")
        # Unknown = not in _OPTIONAL_COMPONENTS → not in disabled set → True
        assert result is True


# ---------------------------------------------------------------------------
# status_dict()
# ---------------------------------------------------------------------------

class TestStatusDict:
    def test_keys_present(self):
        lwm = _lwm()
        sd = lwm.status_dict()
        assert "lightweight_mode" in sd
        assert "disabled_components" in sd
        assert "always_active" in sd

    def test_inactive_state(self):
        lwm = _lwm()
        sd = lwm.status_dict()
        assert sd["lightweight_mode"] is False
        assert sd["disabled_components"] == []

    def test_active_state_disabled_list(self):
        lwm = _lwm(force=True)
        sd = lwm.status_dict()
        assert sd["lightweight_mode"] is True
        assert set(sd["disabled_components"]) == _OPTIONAL_COMPONENTS

    def test_always_active_list_sorted(self):
        lwm = _lwm()
        sd = lwm.status_dict()
        always = sd["always_active"]
        assert always == sorted(always)

    def test_disabled_list_sorted_when_active(self):
        lwm = _lwm(force=True)
        sd = lwm.status_dict()
        disabled = sd["disabled_components"]
        assert disabled == sorted(disabled)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

class TestModuleHelpers:
    def test_is_lightweight_active_false_by_default(self):
        os.environ.pop("BESSAI_LIGHTWEIGHT", None)
        assert not is_lightweight_active()

    @pytest.mark.parametrize("val", ["1", "yes", "true", "on"])
    def test_is_lightweight_active_true(self, val: str):
        os.environ["BESSAI_LIGHTWEIGHT"] = val
        try:
            assert is_lightweight_active()
        finally:
            os.environ.pop("BESSAI_LIGHTWEIGHT", None)

    def test_should_enable_component_all_when_inactive(self):
        os.environ.pop("BESSAI_LIGHTWEIGHT", None)
        for comp in list(_OPTIONAL_COMPONENTS) + list(_ALWAYS_ACTIVE):
            assert should_enable_component(comp)

    def test_should_enable_component_always_active_returns_true(self):
        os.environ["BESSAI_LIGHTWEIGHT"] = "1"
        try:
            for comp in _ALWAYS_ACTIVE:
                assert should_enable_component(comp)
        finally:
            os.environ.pop("BESSAI_LIGHTWEIGHT", None)

    def test_should_enable_component_optional_returns_false_in_lightweight(self):
        os.environ["BESSAI_LIGHTWEIGHT"] = "1"
        try:
            for comp in _OPTIONAL_COMPONENTS:
                assert not should_enable_component(comp)
        finally:
            os.environ.pop("BESSAI_LIGHTWEIGHT", None)


# ---------------------------------------------------------------------------
# Property immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_disabled_components_is_frozenset(self):
        lwm = _lwm(force=True)
        assert isinstance(lwm.disabled_components, frozenset)

    def test_cannot_mutate_disabled_components(self):
        lwm = _lwm(force=True)
        with pytest.raises((AttributeError, TypeError)):
            lwm.disabled_components.add("new_component")  # type: ignore[attr-defined]
