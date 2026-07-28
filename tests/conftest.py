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

import os

os.environ.setdefault("SITE_ID", "TEST-SITE-ID")
os.environ.setdefault("INVERTER_IP", "127.0.0.1")

import subprocess
import sys
import time
import urllib.request

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


@pytest.fixture(scope="session", autouse=True)
def auto_generate_test_models():
    """Auto-generate dummy ONNX models for testing."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    try:
        from scripts import generate_all_test_onnx

        generate_all_test_onnx.main()
    except Exception as e:
        print(f"Warning: could not auto-generate test models: {e}", file=sys.stderr)


@pytest.fixture(scope="session", autouse=True)
def start_demo_server(auto_generate_test_models):
    """Start demo_server.py in a background process during the test session."""
    proc = subprocess.Popen([sys.executable, "demo_server.py"])
    # Wait for server to boot up
    for _ in range(20):
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=0.5) as _:
                break
        except Exception:
            time.sleep(0.5)
    yield
    proc.terminate()
    proc.wait()
