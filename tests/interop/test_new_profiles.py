"""
tests/interop/test_new_profiles.py
===================================
BESSAI Edge Gateway — Interoperability tests for new hardware registry profiles.

Validates schema completeness and data integrity for the three new profiles:
  - registry/solaredge_storedge.json
  - registry/byd_battery_box.json
  - registry/tesla_powerwall3.json

These tests use structural validation only (no real hardware needed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTRY_DIR = Path(__file__).parent.parent.parent / "registry"

REQUIRED_TOP_LEVEL_KEYS = {
    "$schema",
    "profile_version",
    "device",
    "connection",
    "bessai_mapping",
    "safety_limits",
    "interop_certification",
}

REQUIRED_DEVICE_KEYS = {
    "manufacturer",
    "model",
    "description",
    "firmware_reference",
    "protocol",
}

REQUIRED_BESSAI_MAPPING_KEYS = {
    "soc_pct",
    "active_power_kw",
    "temp_c",
}

REQUIRED_SAFETY_KEYS = {
    "soc_min_pct",
    "soc_max_pct",
}

VALID_PROTOCOLS = {
    "ModbusTCP",
    "ModbusRTU",
    "CAN",
    "HTTP_REST",
    "SunSpec",
    "MQTT",
    "OPC_UA",
    "DNP3",
}

VALID_CERT_STATUSES = {
    "experimental_community",
    "community_validated",
    "manufacturer_certified",
}


def load_profile(filename: str) -> dict:
    """Load a registry profile JSON and return as dict."""
    path = REGISTRY_DIR / filename
    assert path.exists(), f"Registry profile not found: {path}"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parametrized fixtures
# ---------------------------------------------------------------------------

NEW_PROFILES = [
    "solaredge_storedge.json",
    "byd_battery_box.json",
    "tesla_powerwall3.json",
]

ALL_PROFILES = [p.name for p in REGISTRY_DIR.glob("*.json") if not p.name.startswith("TEMPLATE")]


# ---------------------------------------------------------------------------
# Tests: Structure validation
# ---------------------------------------------------------------------------


class TestRegistrySchemaCompleteness:
    """Tests that profiles have all required top-level fields."""

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_required_top_level_keys(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        missing = REQUIRED_TOP_LEVEL_KEYS - set(profile.keys())
        assert not missing, f"{profile_file}: Missing top-level keys: {missing}"

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_device_section_complete(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        device = profile.get("device", {})
        missing = REQUIRED_DEVICE_KEYS - set(device.keys())
        assert not missing, f"{profile_file}: Missing device keys: {missing}"

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_bessai_mapping_complete(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        mapping = profile.get("bessai_mapping", {})
        missing = REQUIRED_BESSAI_MAPPING_KEYS - set(mapping.keys())
        assert not missing, f"{profile_file}: Missing bessai_mapping keys: {missing}"

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_safety_limits_present(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        safety = profile.get("safety_limits", {})
        missing = REQUIRED_SAFETY_KEYS - set(safety.keys())
        assert not missing, f"{profile_file}: Missing safety_limits keys: {missing}"

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_profile_version_format(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        version = profile.get("profile_version", "")
        parts = version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"{profile_file}: profile_version must be semver (e.g. '2.0.0'), got: '{version}'"
        )


# ---------------------------------------------------------------------------
# Tests: Data integrity
# ---------------------------------------------------------------------------


class TestRegistryDataIntegrity:
    """Tests that numeric values are within sensible engineering ranges."""

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_soc_limits_valid_range(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        safety = profile.get("safety_limits", {})
        soc_min = safety.get("soc_min_pct", -1)
        soc_max = safety.get("soc_max_pct", -1)
        assert 0.0 <= soc_min < soc_max <= 100.0, (
            f"{profile_file}: Invalid SoC range: min={soc_min}, max={soc_max}"
        )

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_protocol_is_known(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        protocol = profile.get("device", {}).get("protocol", "")
        assert protocol in VALID_PROTOCOLS, (
            f"{profile_file}: Unknown protocol '{protocol}'. Valid: {VALID_PROTOCOLS}"
        )

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_certification_status_valid(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        status = profile.get("interop_certification", {}).get("status", "")
        assert status in VALID_CERT_STATUSES, (
            f"{profile_file}: Invalid certification status '{status}'. Valid: {VALID_CERT_STATUSES}"
        )

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_manufacturer_not_empty(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        manufacturer = profile.get("device", {}).get("manufacturer", "")
        assert len(manufacturer) >= 2, f"{profile_file}: manufacturer too short: '{manufacturer}'"

    @pytest.mark.parametrize("profile_file", NEW_PROFILES)
    def test_schema_url_present(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        schema = profile.get("$schema", "")
        assert schema.startswith("https://bessai.io/schemas/"), (
            f"{profile_file}: $schema should start with 'https://bessai.io/schemas/', got: '{schema}'"
        )


# ---------------------------------------------------------------------------
# Tests: All profiles (regression guard)
# ---------------------------------------------------------------------------


class TestAllProfiles:
    """Regression tests that all existing profiles still pass basic structural checks."""

    @pytest.mark.parametrize("profile_file", ALL_PROFILES)
    def test_valid_json_parseable(self, profile_file: str) -> None:
        """Every profile in registry/ must be valid JSON."""
        profile = load_profile(profile_file)
        assert isinstance(profile, dict), f"{profile_file}: Profile is not a JSON object"

    @pytest.mark.parametrize("profile_file", ALL_PROFILES)
    def test_has_device_section(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        assert "device" in profile, f"{profile_file}: Missing 'device' section"

    @pytest.mark.parametrize("profile_file", ALL_PROFILES)
    def test_has_manufacturer_and_model(self, profile_file: str) -> None:
        profile = load_profile(profile_file)
        device = profile.get("device", {})
        assert device.get("manufacturer"), f"{profile_file}: 'device.manufacturer' is empty"
        assert device.get("model"), f"{profile_file}: 'device.model' is empty"
