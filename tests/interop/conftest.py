"""
tests/interop/conftest.py
=========================
Pytest configuration for the BESSAI interoperability test suite.

Provides:
- asyncio_mode = "auto" scoped to this directory (avoids deprecated event_loop fixture)
- A module-scoped `driver` fixture that defaults to SimulatorDriver
  (or whatever class is passed via --driver-class CLI option)

Usage::

    # Cat-A contract tests (no hardware):
    pytest tests/interop/ -v

    # With real hardware:
    pytest tests/interop/ --driver-class="src.drivers.modbus_driver.UniversalDriver" \\
        --driver-args='{"host":"192.168.1.100","port":502}' -v
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from src.drivers.simulator_driver import SimulatorDriver

# ---------------------------------------------------------------------------
# pytest-asyncio: auto mode for this directory
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Force asyncio_mode=auto for all tests in this directory."""
    config.addinivalue_line("markers", "asyncio: mark test as async (handled by pytest-asyncio)")


# ---------------------------------------------------------------------------
# Shared driver fixture (module-scoped — connect once per module)
# ---------------------------------------------------------------------------


def _load_driver_from_config(config: pytest.Config) -> Any:
    """Load driver from CLI options or fall back to SimulatorDriver."""
    driver_class_path: str | None = config.getoption("--driver-class", default=None)
    driver_args_raw: str = config.getoption("--driver-args", default="{}")

    if driver_class_path is None:
        return SimulatorDriver()

    module_path, class_name = driver_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    kwargs: dict[str, Any] = json.loads(driver_args_raw)
    return cls(**kwargs)


@pytest.fixture(scope="module")
def driver(request: pytest.FixtureRequest) -> Any:
    """
    Provide the DataProvider driver under test.

    Defaults to SimulatorDriver (Category A — no hardware required).
    Override via CLI: --driver-class and --driver-args.
    """
    return _load_driver_from_config(request.config)
