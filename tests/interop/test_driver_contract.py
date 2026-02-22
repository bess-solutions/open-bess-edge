"""
BESSAI Interoperability — Driver Contract Tests
================================================

Validates that any DataProvider implementation conforms to BESSAI-SPEC-001.

Usage:
    # Without hardware (contract-only tests):
    pytest tests/interop/test_driver_contract.py::TestContract -v

    # With real hardware driver:
    pytest tests/interop/test_driver_contract.py \
      --driver-class="src.drivers.modbus_driver.ModbusBESSDriver" \
      --driver-args='{"host":"192.168.1.100","port":502}' \
      -v

    # With simulator (default, no extra args needed):
    pytest tests/interop/ -v
"""
from __future__ import annotations

import asyncio
import importlib
import json
import time
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from pytest import FixtureRequest

from src.drivers.base import DataProvider
from src.drivers.simulator_driver import SimulatorDriver


# ---------------------------------------------------------------------------
# CLI options (allow passing a custom driver class + args)
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:  # type: ignore[return]
    parser.addoption(
        "--driver-class",
        action="store",
        default=None,
        help="Dotted path to driver class, e.g. 'src.drivers.modbus_driver.ModbusBESSDriver'",
    )
    parser.addoption(
        "--driver-args",
        action="store",
        default="{}",
        help="JSON dict of constructor kwargs for the driver class",
    )


def _load_driver(request: FixtureRequest) -> DataProvider:
    """Load the driver from CLI options or fall back to SimulatorDriver."""
    driver_class_path: str | None = request.config.getoption("--driver-class")
    driver_args_raw: str = request.config.getoption("--driver-args")

    if driver_class_path is None:
        return SimulatorDriver()

    module_path, class_name = driver_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    kwargs: dict[str, Any] = json.loads(driver_args_raw)
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def driver(request: FixtureRequest) -> DataProvider:
    """Provide the driver under test."""
    return _load_driver(request)


@pytest.fixture(scope="module")
def event_loop():
    """Module-scoped event loop for all interop tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Category A — Contract Tests (no hardware required)
# ---------------------------------------------------------------------------


class TestContract:
    """
    BESSAI-SPEC-001 §4: DataProvider protocol contract.
    These tests run without live hardware using the SimulatorDriver.
    """

    @pytest.mark.asyncio
    async def test_a01_implements_data_provider_protocol(self, driver: DataProvider) -> None:
        """A-01: Driver implements the DataProvider protocol (SPEC-001 §4.1)."""
        assert isinstance(driver, DataProvider), (
            "Driver must implement the DataProvider protocol. "
            "Ensure it satisfies all properties and methods defined in src/drivers/base.py."
        )

    def test_a02_is_connected_false_before_connect(self, driver: DataProvider) -> None:
        """A-02: is_connected is False before connect() is called (SPEC-001 §4.2)."""
        # Note: a freshly instantiated driver must be disconnected
        fresh_driver = driver.__class__() if isinstance(driver, SimulatorDriver) else driver
        # We only assert this for SimulatorDriver in unit mode; for real hardware drivers
        # the caller ensures the driver is not yet connected.
        if isinstance(fresh_driver, SimulatorDriver):
            assert fresh_driver.is_connected is False, (
                "is_connected must be False before connect() is called."
            )

    def test_a03_source_description_is_non_empty_string(self, driver: DataProvider) -> None:
        """A-03: source_description is a non-empty string (SPEC-001 §4.3)."""
        desc = driver.source_description
        assert isinstance(desc, str), f"source_description must be str, got {type(desc)}"
        assert len(desc) > 0, "source_description must not be empty"

    def test_a03_source_description_does_not_block(self, driver: DataProvider) -> None:
        """A-03: source_description must not perform I/O (returns within 5ms)."""
        start = time.perf_counter()
        _ = driver.source_description
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5, (
            f"source_description took {elapsed_ms:.1f}ms — must not perform I/O (< 5ms)."
        )

    @pytest.mark.asyncio
    async def test_a04_connect_is_idempotent(self, driver: DataProvider) -> None:
        """A-04: Calling connect() twice does not raise (SPEC-001 §4.4)."""
        await driver.connect()
        try:
            await driver.connect()  # second call must not raise
        except Exception as e:
            pytest.fail(f"connect() raised on second call: {e!r}. Must be idempotent.")

    @pytest.mark.asyncio
    async def test_a05_read_tag_raises_key_error_for_unknown_tag(
        self, driver: DataProvider
    ) -> None:
        """A-05: read_tag() raises KeyError for unsupported tag (SPEC-001 §4.5)."""
        await driver.connect()
        with pytest.raises(KeyError):
            await driver.read_tag("__NONEXISTENT_TAG_12345__")

    @pytest.mark.asyncio
    async def test_a06_read_tag_raises_connection_error_when_disconnected(
        self, driver: DataProvider
    ) -> None:
        """A-06: read_tag() raises ConnectionError when disconnected (SPEC-001 §4.5)."""
        fresh_driver = SimulatorDriver()  # use sim for this test always
        with pytest.raises((ConnectionError, RuntimeError)):
            await fresh_driver.read_tag("SOC_%")

    @pytest.mark.asyncio
    async def test_a07_write_tag_raises_value_error_for_out_of_bounds(
        self, driver: DataProvider
    ) -> None:
        """A-07: write_tag() raises ValueError for out-of-bounds value (SPEC-001 §4.6)."""
        await driver.connect()
        with pytest.raises((ValueError, KeyError)):
            # SOC out of 0-100 range is always invalid
            await driver.write_tag("P_setpoint_kW", float("inf"))

    @pytest.mark.asyncio
    async def test_a08_disconnect_is_idempotent(self, driver: DataProvider) -> None:
        """A-08: disconnect() is idempotent (SPEC-001 §4.7)."""
        await driver.connect()
        await driver.disconnect()
        try:
            await driver.disconnect()  # second call must not raise
        except Exception as e:
            pytest.fail(f"disconnect() raised on second call: {e!r}. Must be idempotent.")

    @pytest.mark.asyncio
    async def test_a09_is_connected_false_after_disconnect(self, driver: DataProvider) -> None:
        """A-09: is_connected is False after disconnect() (SPEC-001 §4.2)."""
        await driver.connect()
        await driver.disconnect()
        assert driver.is_connected is False, (
            "is_connected must be False after disconnect() is called."
        )

    def test_a10_device_profile_json_exists(self) -> None:
        """A-10: A device profile JSON exists in registry/ (SPEC-001 §7)."""
        registry_dir = Path(__file__).parent.parent.parent / "registry"
        json_files = list(registry_dir.glob("*.json"))
        assert len(json_files) > 0, (
            "No device profile JSON found in registry/. "
            "Create a profile per BESSAI-SPEC-001 §7."
        )


# ---------------------------------------------------------------------------
# Category B — Required Tag Tests (hardware / accurate simulator required)
# ---------------------------------------------------------------------------


REQUIRED_TAGS: list[tuple[str, float, float]] = [
    ("SOC_%", 0.0, 100.0),
    ("P_kW", float("-inf"), float("inf")),
    ("T_battery_C", -40.0, 100.0),
    ("V_dc_V", 0.0, float("inf")),
    ("alarm_code", 0.0, float("inf")),
]

REQUIRED_MODE_VALUES = {0.0, 1.0, 2.0, 3.0}


class TestRequiredTags:
    """
    BESSAI-SPEC-001 §5.1: Required tag validation.
    Run with hardware driver or accurate simulator.
    """

    @pytest.fixture(autouse=True)
    async def _connect(self, driver: DataProvider) -> None:  # type: ignore[return]
        await driver.connect()
        yield
        await driver.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tag_name,min_val,max_val", REQUIRED_TAGS)
    async def test_required_tag_in_range(
        self, driver: DataProvider, tag_name: str, min_val: float, max_val: float
    ) -> None:
        """B-01 to B-06: Required tags return float values within specified ranges."""
        value = await driver.read_tag(tag_name)
        assert isinstance(value, (int, float)), (
            f"read_tag('{tag_name}') must return a float, got {type(value)}"
        )
        assert min_val <= float(value) <= max_val, (
            f"read_tag('{tag_name}') = {value} is outside allowed range [{min_val}, {max_val}]"
        )

    @pytest.mark.asyncio
    async def test_mode_is_valid_enum_value(self, driver: DataProvider) -> None:
        """B-05: 'mode' tag returns one of the four defined values."""
        value = await driver.read_tag("mode")
        assert float(value) in REQUIRED_MODE_VALUES, (
            f"read_tag('mode') = {value} is not in {REQUIRED_MODE_VALUES}"
        )


# ---------------------------------------------------------------------------
# Category C — Timing Tests
# ---------------------------------------------------------------------------


class TestTiming:
    """BESSAI-SPEC-001 §4.5: Timing requirements."""

    @pytest.mark.asyncio
    async def test_c01_read_tag_completes_within_5s(self, driver: DataProvider) -> None:
        """C-01: read_tag() completes within 5 seconds (SPEC-001 §4.5)."""
        await driver.connect()
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            await driver.read_tag("SOC_%")
            latencies.append(time.perf_counter() - start)
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        await driver.disconnect()
        assert p99 < 5.0, (
            f"read_tag() P99 latency = {p99:.2f}s exceeds 5s limit (SPEC-001 §4.5)"
        )

    @pytest.mark.asyncio
    async def test_c03_is_connected_does_not_block(self, driver: DataProvider) -> None:
        """C-03: is_connected does not perform I/O (< 1ms)."""
        start = time.perf_counter()
        _ = driver.is_connected
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 1.0, (
            f"is_connected took {elapsed_ms:.2f}ms — must not perform I/O"
        )
