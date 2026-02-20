"""
tests/test_config.py
=====================
Unit tests for ``src.core.config.Settings`` and ``get_settings``.

Covers:
* Required fields missing → ValidationError at startup.
* All fields present → correct types.
* INVERTER_IP validates IPv4 addresses.
* INVERTER_IP rejects invalid strings.
* INVERTER_PORT clamped to 1-65535.
* DRIVER_PROFILE_PATH default.
* WATCHDOG_TIMEOUT default.
* Derived property inverter_ip_str returns a plain string.
* Singleton behaviour of get_settings().
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# Clear the singleton cache between every test
from src.core import config as config_module


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure each test gets a fresh Settings parse."""
    config_module.get_settings.cache_clear()
    yield
    config_module.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Minimal valid environment
# ---------------------------------------------------------------------------

_VALID_ENV: dict[str, str] = {
    "SITE_ID": "SITE-TEST-001",
    "INVERTER_IP": "192.168.1.100",
    "INVERTER_PORT": "502",
    "DRIVER_PROFILE_PATH": "registry/huawei_sun2000.json",
    "WATCHDOG_TIMEOUT": "5",
}


def _make_settings(**overrides: str) -> config_module.Settings:
    env = {**_VALID_ENV, **overrides}
    with patch.dict(os.environ, env, clear=True):
        # _env_file=None makes pydantic-settings ignore the real config/.env
        # so tests are hermetic even when the file exists on disk.
        return config_module.Settings(_env_file=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Required field validation
# ---------------------------------------------------------------------------


class TestRequiredFields:
    def test_missing_site_id_raises(self) -> None:
        env = {k: v for k, v in _VALID_ENV.items() if k != "SITE_ID"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="SITE_ID"):
                config_module.Settings(_env_file=None)  # type: ignore[call-arg]

    def test_missing_inverter_ip_raises(self) -> None:
        env = {k: v for k, v in _VALID_ENV.items() if k != "INVERTER_IP"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="INVERTER_IP"):
                config_module.Settings(_env_file=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Field types and values
# ---------------------------------------------------------------------------


class TestFieldTypes:
    def test_site_id_is_string(self) -> None:
        s = _make_settings()
        assert isinstance(s.SITE_ID, str)
        assert s.SITE_ID == "SITE-TEST-001"

    def test_inverter_ip_parsed(self) -> None:
        s = _make_settings()
        # Now str type — accepts IPs and hostnames
        assert s.INVERTER_IP == "192.168.1.100"

    def test_inverter_ip_invalid_raises(self) -> None:
        # Invalid: contains characters not valid in IPs or hostnames
        with pytest.raises(ValidationError):
            _make_settings(INVERTER_IP="not an ip!")

    def test_inverter_port_default(self) -> None:
        env = {k: v for k, v in _VALID_ENV.items() if k != "INVERTER_PORT"}
        with patch.dict(os.environ, env, clear=True):
            s = config_module.Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.INVERTER_PORT == 502

    def test_inverter_port_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_settings(INVERTER_PORT="0")

    def test_inverter_port_above_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make_settings(INVERTER_PORT="65536")

    def test_watchdog_timeout_default(self) -> None:
        env = {k: v for k, v in _VALID_ENV.items() if k != "WATCHDOG_TIMEOUT"}
        with patch.dict(os.environ, env, clear=True):
            s = config_module.Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.WATCHDOG_TIMEOUT == 5

    def test_driver_profile_path_default(self) -> None:
        env = {k: v for k, v in _VALID_ENV.items() if k != "DRIVER_PROFILE_PATH"}
        with patch.dict(os.environ, env, clear=True):
            s = config_module.Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.DRIVER_PROFILE_PATH == "registry/huawei_sun2000.json"


# ---------------------------------------------------------------------------
# Derived properties
# ---------------------------------------------------------------------------


class TestDerivedProperties:
    def test_inverter_ip_str_is_string(self) -> None:
        s = _make_settings()
        assert isinstance(s.inverter_ip_str, str)
        assert s.inverter_ip_str == "192.168.1.100"

    def test_driver_profile_abs_is_absolute(self) -> None:
        s = _make_settings()
        assert s.driver_profile_abs.is_absolute()

    def test_driver_profile_abs_resolves_relative(self) -> None:
        s = _make_settings(DRIVER_PROFILE_PATH="registry/test.json")
        assert s.driver_profile_abs.name == "test.json"
        assert s.driver_profile_abs.is_absolute()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_settings_returns_same_instance(self) -> None:
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            s1 = config_module.get_settings()
            s2 = config_module.get_settings()
        assert s1 is s2

    def test_cache_clear_forces_new_instance(self) -> None:
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            s1 = config_module.get_settings()
        config_module.get_settings.cache_clear()
        with patch.dict(os.environ, _VALID_ENV, clear=True):
            s2 = config_module.get_settings()
        # Different parse → different object identity
        assert s1 is not s2
