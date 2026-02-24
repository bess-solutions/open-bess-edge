"""
tests/conftest.py
=================
Root conftest for the BESSAI Edge Gateway test suite.

Registers the --driver-class and --driver-args CLI options used by
the interop test suite (tests/interop/test_driver_contract.py).

Having this in conftest.py (rather than in the test module) ensures
pytest loads the option registration BEFORE any test collection,
which prevents the 'no option named --driver-class' error when the
interop tests are executed by themselves.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI options for the interop test suite."""
    # Guard against being called multiple times (e.g. in pytest-xdist)
    try:
        parser.addoption(
            "--driver-class",
            action="store",
            default=None,
            help=(
                "Dotted path to driver class, e.g. 'src.drivers.simulator_driver.SimulatorDriver'"
            ),
        )
        parser.addoption(
            "--driver-args",
            action="store",
            default="{}",
            help="JSON dict of constructor kwargs for the driver class",
        )
    except ValueError:
        # Already registered (e.g. called from the test module as well)
        pass
