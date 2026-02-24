# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/lightweight_mode.py
============================
BESSAI Edge Gateway — Lightweight Mode Manager.

Activado con ``BESSAI_LIGHTWEIGHT=1`` en el entorno o .env.

Desactiva componentes no críticos para reducir uso de CPU/RAM en
dispositivos edge con recursos limitados (Raspberry Pi 4, PLCs industriales).

Componentes desactivados en modo lightweight:
    - OpenTelemetry traces (manteniendo solo métricas básicas)
    - AI-IDS full scoring (solo alertas CRITICAL)
    - VPP publisher (mqtt hacia orquestador federado)
    - P2P trading module
    - Logging reducido a WARNING+

Componentes siempre activos (no desactivables):
    - SafetyGuard (crítico para seguridad)
    - ModbusDriver / lectura de hardware
    - CMg Predictor (core de la lógica de arbitraje)
    - ArbitragePolicy / ONNXArbitrageAgent (si está disponible)
    - MQTT publisher principal (telemetría)
    - Dashboard API (solo lectura)

Usage::

    from src.core.lightweight_mode import LightweightModeManager

    lwm = LightweightModeManager()
    if lwm.is_active:
        print("Modo lightweight activo — componentes reducidos")

    if lwm.should_enable("opentelemetry"):
        # Inicializar OpenTelemetry
        setup_otel(...)

    if lwm.should_enable("ai_ids_full"):
        # Inicializar AI-IDS con scoring completo
        ids = AIIDS(mode="full")
    else:
        ids = AIIDS(mode="critical_only")
"""

from __future__ import annotations

import os
import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Components that can be disabled in lightweight mode
# ---------------------------------------------------------------------------

_OPTIONAL_COMPONENTS = frozenset(
    {
        "opentelemetry",       # OpenTelemetry traces and spans
        "ai_ids_full",         # AI-IDS full anomaly scoring (z-score on all signals)
        "vpp_publisher",       # VPP/federated orchestrator MQTT uplink
        "p2p_trading",         # Peer-to-peer energy trading module
        "lca_engine",          # Life Cycle Assessment carbon engine
        "fl_client",           # Federated Learning client
        "debug_logging",       # DEBUG-level log verbosity
    }
)

# Components that are NEVER disabled (safety-critical)
_ALWAYS_ACTIVE = frozenset(
    {
        "safety_guard",
        "modbus_driver",
        "cmg_predictor",
        "arbitrage_policy",
        "mqtt_publisher",
        "dashboard_api",
    }
)

__all__ = ["LightweightModeManager", "is_lightweight_active", "should_enable_component"]


class LightweightModeManager:
    """Manages which components are active based on ``BESSAI_LIGHTWEIGHT`` env var.

    Parameters
    ----------
    env_var:
        Name of the environment variable to check (default: ``BESSAI_LIGHTWEIGHT``).
    force_active:
        If ``True``, force lightweight mode regardless of env var (for testing).

    Attributes
    ----------
    is_active : bool
        ``True`` if lightweight mode is enabled.
    disabled_components : frozenset[str]
        Set of component names that are disabled in this mode.
    """

    def __init__(
        self,
        env_var: str = "BESSAI_LIGHTWEIGHT",
        force_active: bool = False,
    ) -> None:
        raw = os.environ.get(env_var, "0").strip().lower()
        self._active: bool = force_active or raw in {"1", "true", "yes", "on"}
        self._disabled: frozenset[str] = _OPTIONAL_COMPONENTS if self._active else frozenset()

        if self._active:
            log.warning(
                "lightweight_mode.active",
                disabled_components=sorted(self._disabled),
                reason="BESSAI_LIGHTWEIGHT=1 — non-critical components disabled to reduce CPU/RAM usage",
            )
        else:
            log.info("lightweight_mode.inactive", all_components="enabled")

    @property
    def is_active(self) -> bool:
        """Return ``True`` if lightweight mode is active."""
        return self._active

    @property
    def disabled_components(self) -> frozenset[str]:
        """Return the set of component names currently disabled."""
        return self._disabled

    def should_enable(self, component: str) -> bool:
        """Return whether a given component should be initialized.

        Parameters
        ----------
        component:
            Component name. Must be one of :data:`_OPTIONAL_COMPONENTS` keys.
            Safety-critical components (in :data:`_ALWAYS_ACTIVE`) always return ``True``.

        Returns
        -------
        bool
            ``True`` if the component should be initialized, ``False`` if it should be skipped.

        Examples
        --------
        ::

            lwm = LightweightModeManager()
            if lwm.should_enable("opentelemetry"):
                setup_otel()
        """
        if component in _ALWAYS_ACTIVE:
            return True
        if component not in _OPTIONAL_COMPONENTS:
            log.warning(
                "lightweight_mode.unknown_component",
                component=component,
                hint=f"Known optional components: {sorted(_OPTIONAL_COMPONENTS)}",
            )
        return component not in self._disabled

    def status_dict(self) -> dict[str, object]:
        """Return a status dict suitable for the health endpoint.

        Returns
        -------
        dict
            ``{"lightweight_mode": bool, "disabled_components": list[str]}``
        """
        return {
            "lightweight_mode": self._active,
            "disabled_components": sorted(self._disabled),
            "always_active": sorted(_ALWAYS_ACTIVE),
        }


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def is_lightweight_active() -> bool:
    """Return ``True`` if ``BESSAI_LIGHTWEIGHT=1`` is set in the environment."""
    return os.environ.get("BESSAI_LIGHTWEIGHT", "0").strip().lower() in {"1", "true", "yes", "on"}


def should_enable_component(component: str) -> bool:
    """Return whether a component should be enabled.

    Convenience wrapper around ``LightweightModeManager.should_enable`` for
    use without instantiating the manager (reads env var directly).

    Parameters
    ----------
    component:
        Component name string.

    Returns
    -------
    bool
        ``True`` if the component should be initialized.
    """
    if not is_lightweight_active():
        return True
    if component in _ALWAYS_ACTIVE:
        return True
    return component not in _OPTIONAL_COMPONENTS
