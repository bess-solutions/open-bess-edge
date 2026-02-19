"""
src/interfaces/onnx_dispatcher.py
==================================
BESSAI Edge Gateway — ONNX Runtime Dispatch Policy Engine.

Loads a pre-trained ONNX model that maps edge telemetry to a dispatch target.

Input features (in order):
    [soc_pct, power_kw, temp_c, hour_of_day]

Output:
    dispatch_target_kw  — signed float (+ = charge, - = discharge)

Modes:
    - **Normal**:    Model loaded → ONNX inference.
    - **Fallback**:  Model missing / load error → returns None, let
                     SafetyGuard take over (deterministic rules).

This follows the Graceful Degradation principle from the BESSAI v2.0 roadmap:
    DRL → ONNX offline → MILP → safety rules → Black Start

Usage::

    async with ONNXDispatcher(model_path="models/dispatch_policy.onnx") as dispatcher:
        target_kw = dispatcher.infer(soc_pct=75.0, power_kw=50.0,
                                     temp_c=28.5, hour_of_day=14)
        if target_kw is not None:
            # AI-assisted dispatch
            apply_dispatch(target_kw)
        else:
            # Fallback: safety guard decides
            pass
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

from .metrics import ONNX_DISPATCH_COMMANDS_TOTAL, ONNX_INFERENCE_MS

try:
    import onnxruntime as ort  # type: ignore[import-untyped]
    _ONNX_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ONNX_AVAILABLE = False

__all__ = ["ONNXDispatcher", "DispatchResult"]

log = structlog.get_logger(__name__)

# Expected input feature names in the ONNX model
_INPUT_FEATURES = ["soc_pct", "power_kw", "temp_c", "hour_of_day"]


class DispatchResult:
    """Result from ONNX inference.

    Attributes:
        target_kw:     Recommended dispatch power in kW (+ charge, - discharge).
        inference_ms:  Wall-clock time of inference in milliseconds.
        model_path:    Which model produced this result.
    """
    __slots__ = ("target_kw", "inference_ms", "model_path")

    def __init__(self, target_kw: float, inference_ms: float, model_path: str) -> None:
        self.target_kw = target_kw
        self.inference_ms = inference_ms
        self.model_path = model_path

    def __repr__(self) -> str:
        return (
            f"DispatchResult(target_kw={self.target_kw:.2f}, "
            f"inference_ms={self.inference_ms:.2f})"
        )


class ONNXDispatcher:
    """Loads an ONNX model and provides real-time dispatch inference.

    Parameters:
        model_path: Path to the ``.onnx`` file. Relative paths are resolved
                    from the repository root.
        site_id:    Site identifier used in Prometheus labels.
    """

    def __init__(
        self,
        model_path: str | Path = "models/dispatch_policy.onnx",
        site_id: str = "unknown",
    ) -> None:
        self.model_path = Path(model_path)
        self.site_id = site_id
        self._session: Optional[ort.InferenceSession] = None  # type: ignore[name-defined]
        self._input_name: Optional[str] = None
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Context manager (async-compatible but synchronous internally)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ONNXDispatcher":
        self._load()
        return self

    async def __aexit__(self, *_: object) -> None:
        self._session = None
        self._loaded = False

    def _load(self) -> None:
        """Attempt to load the ONNX model. Logs warning on failure."""
        if not _ONNX_AVAILABLE:
            log.warning("onnx_dispatcher.onnxruntime_not_installed")
            return

        if not self.model_path.exists():
            log.warning(
                "onnx_dispatcher.model_not_found",
                path=str(self.model_path),
            )
            return

        try:
            opts = ort.SessionOptions()
            opts.log_severity_level = 3  # suppress verbose ort logs
            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            self._loaded = True
            log.info(
                "onnx_dispatcher.model_loaded",
                path=str(self.model_path),
                input_name=self._input_name,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("onnx_dispatcher.load_error", error=str(exc), path=str(self.model_path))

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def infer(
        self,
        soc_pct: float,
        power_kw: float,
        temp_c: float,
        hour_of_day: float,
    ) -> Optional[DispatchResult]:
        """Run ONNX inference and return dispatch recommendation.

        Returns ``None`` if the model is not loaded (fallback mode).
        """
        if not self._loaded or self._session is None:
            log.debug("onnx_dispatcher.fallback_mode", site_id=self.site_id)
            return None

        features = np.array(
            [[soc_pct, power_kw, temp_c, hour_of_day]], dtype=np.float32
        )

        t0 = time.perf_counter()
        try:
            outputs = self._session.run(None, {self._input_name: features})
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            target_kw = float(outputs[0].flatten()[0])

            # Update Prometheus metrics
            ONNX_INFERENCE_MS.labels(site_id=self.site_id).set(elapsed_ms)
            ONNX_DISPATCH_COMMANDS_TOTAL.labels(site_id=self.site_id).inc()

            log.debug(
                "onnx_dispatcher.inference",
                target_kw=round(target_kw, 2),
                inference_ms=round(elapsed_ms, 2),
                soc_pct=soc_pct,
                site_id=self.site_id,
            )
            return DispatchResult(
                target_kw=target_kw,
                inference_ms=elapsed_ms,
                model_path=str(self.model_path),
            )
        except Exception as exc:  # noqa: BLE001
            log.error("onnx_dispatcher.inference_error", error=str(exc), site_id=self.site_id)
            return None

    @property
    def is_loaded(self) -> bool:
        """True if the ONNX model is loaded and ready for inference."""
        return self._loaded
