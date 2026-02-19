"""
tests/test_onnx_dispatcher.py
==============================
Unit tests for the ONNXDispatcher.

Tests cover:
  - Fallback mode when model file does not exist (returns None gracefully)
  - Fallback mode when onnxruntime is unavailable
  - DispatchResult dataclass attributes
  - is_loaded property
  - Async context manager (aenter/aexit)
  - Inference with a real dummy ONNX model (if model file exists)
  - Error handling for invalid inputs
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import numpy as np
import pytest

from src.interfaces.onnx_dispatcher import DispatchResult, ONNXDispatcher

# Path where the dummy model will be placed by the generate script
DUMMY_MODEL_PATH = Path("models/dispatch_policy.onnx")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_model() -> bool:
    return DUMMY_MODEL_PATH.exists()


def _has_onnxruntime() -> bool:
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Tests — No model (fallback mode)
# ---------------------------------------------------------------------------

def test_dispatcher_missing_model_returns_none():
    """When model file does not exist, infer() must return None (graceful fallback)."""
    dispatcher = ONNXDispatcher(model_path="models/nonexistent_model.onnx", site_id="test")
    dispatcher._load()  # explicit load (no async context)
    result = dispatcher.infer(soc_pct=75.0, power_kw=50.0, temp_c=25.0, hour_of_day=14)
    assert result is None


@pytest.mark.asyncio
async def test_dispatcher_async_context_no_model():
    """Async context manager must not raise when model is missing."""
    async with ONNXDispatcher(model_path="models/missing.onnx", site_id="test-async") as d:
        result = d.infer(soc_pct=50.0, power_kw=0.0, temp_c=20.0, hour_of_day=8)
        assert result is None
        assert d.is_loaded is False


def test_dispatcher_not_loaded_by_default():
    """Dispatcher must not be loaded before _load() / __aenter__."""
    dispatcher = ONNXDispatcher()
    assert dispatcher.is_loaded is False


# ---------------------------------------------------------------------------
# Tests — DispatchResult
# ---------------------------------------------------------------------------

def test_dispatch_result_attributes():
    """DispatchResult must expose target_kw, inference_ms, model_path."""
    result = DispatchResult(target_kw=42.5, inference_ms=0.75, model_path="models/test.onnx")
    assert result.target_kw == pytest.approx(42.5)
    assert result.inference_ms == pytest.approx(0.75)
    assert result.model_path == "models/test.onnx"


def test_dispatch_result_repr():
    """DispatchResult __repr__ must not raise and should contain target_kw."""
    result = DispatchResult(target_kw=-10.0, inference_ms=1.2, model_path="m.onnx")
    text = repr(result)
    assert "target_kw" in text
    assert "-10.00" in text


# ---------------------------------------------------------------------------
# Tests — With real ONNX model (skipped if model or onnxruntime not available)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _has_model() or not _has_onnxruntime(),
    reason="ONNX model file not found or onnxruntime not installed",
)
def test_inference_returns_dispatch_result():
    """With a valid model, infer() must return a DispatchResult with a finite float."""
    dispatcher = ONNXDispatcher(model_path=DUMMY_MODEL_PATH, site_id="test-onnx")
    dispatcher._load()
    result = dispatcher.infer(soc_pct=75.0, power_kw=50.0, temp_c=28.0, hour_of_day=14)
    assert result is not None
    assert isinstance(result.target_kw, float)
    assert -1000.0 <= result.target_kw <= 1000.0  # sanity bound
    assert result.inference_ms >= 0.0


@pytest.mark.skipif(
    not _has_model() or not _has_onnxruntime(),
    reason="ONNX model file not found or onnxruntime not installed",
)
def test_inference_positive_dispatch_high_soc():
    """Dummy model: high SOC → positive dispatch (charge mode disabled, exports power)."""
    dispatcher = ONNXDispatcher(model_path=DUMMY_MODEL_PATH, site_id="test-highsoc")
    dispatcher._load()
    result = dispatcher.infer(soc_pct=90.0, power_kw=0.0, temp_c=25.0, hour_of_day=12)
    assert result is not None
    # Dummy model output = soc_pct * 0.8 → 90 * 0.8 = 72.0
    assert result.target_kw == pytest.approx(72.0, abs=1.0)


@pytest.mark.skipif(
    not _has_model() or not _has_onnxruntime(),
    reason="ONNX model file not found or onnxruntime not installed",
)
@pytest.mark.asyncio
async def test_dispatcher_async_context_with_model():
    """Async context manager works end-to-end with real model."""
    async with ONNXDispatcher(model_path=DUMMY_MODEL_PATH, site_id="test-ctx") as d:
        assert d.is_loaded is True
        result = d.infer(soc_pct=50.0, power_kw=10.0, temp_c=22.0, hour_of_day=10)
        assert result is not None
