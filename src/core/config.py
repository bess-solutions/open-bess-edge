"""
src/core/config.py
==================
Centralised configuration for BESSAI Edge Gateway.

All settings are loaded from environment variables (12-Factor App).
Defaults are provided for optional values; required values will raise
a ``ValidationError`` at startup if missing, making misconfiguration
immediately visible.

Usage
-----
    from src.core.config import get_settings

    cfg = get_settings()
    print(cfg.SITE_ID)
    print(cfg.INVERTER_IP)

In application code that needs a module-level reference::

    from src.core.config import settings   # lazy — resolved at first access
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Accepts IPv4, IPv6 (simplified), Docker service names and DNS hostnames
# A hostname label: starts/ends with alnum, may contain hyphens.
_HOST_RE = re.compile(
    r"^("
    r"(?:\d{1,3}\.){3}\d{1,3}"                        # IPv4
    r"|(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}"   # IPv6 (simplified)
    r"|(?:[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"  # optional domain labels
    r"[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"   # final label (allows hyphens)
    r")$"
)


class Settings(BaseSettings):
    """
    Application-wide settings resolved from environment variables.

    Pydantic-Settings reads variables using the exact field names
    (case-insensitive on most platforms).  A ``.env`` file placed at
    ``config/.env`` is also auto-loaded when present.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / "config" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Site identity
    # ------------------------------------------------------------------
    SITE_ID: str = Field(
        ...,
        description="Unique identifier for this edge installation site.",
        examples=["SITE-CL-001"],
    )

    # ------------------------------------------------------------------
    # Inverter / BESS device connection
    # ------------------------------------------------------------------
    INVERTER_IP: str = Field(
        ...,
        description="IPv4, IPv6 address or DNS hostname of the inverter Modbus endpoint.",
        examples=["192.168.1.100", "modbus-simulator"],
    )

    @field_validator("INVERTER_IP", mode="before")
    @classmethod
    def validate_inverter_host(cls, v: object) -> str:
        """Accept IPv4, IPv6, or a DNS hostname (e.g. Docker service names)."""
        s = str(v).strip()
        if not _HOST_RE.match(s):
            raise ValueError(
                f"INVERTER_IP must be a valid IP address or hostname, got: {s!r}"
            )
        return s

    INVERTER_PORT: int = Field(
        default=502,
        ge=1,
        le=65535,
        description="TCP port for Modbus communication (default 502).",
    )

    # ------------------------------------------------------------------
    # Driver profile
    # ------------------------------------------------------------------
    DRIVER_PROFILE_PATH: str = Field(
        default="registry/huawei_sun2000.json",
        description=(
            "Relative or absolute path to the JSON device profile.  "
            "Path is resolved relative to the project root."
        ),
    )

    # ------------------------------------------------------------------
    # Safety / watchdog
    # ------------------------------------------------------------------
    WATCHDOG_TIMEOUT: int = Field(
        default=5,
        ge=1,
        description="Seconds between watchdog heartbeat writes.",
    )

    # ------------------------------------------------------------------
    # GCP Cloud Integration
    # ------------------------------------------------------------------
    GCP_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID. Required in production.",
    )
    GCP_PUBSUB_TOPIC: Optional[str] = Field(
        default=None,
        description="GCP Pub/Sub topic name for telemetry. Required in production.",
    )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://otel-collector:4317",
        description="OTLP gRPC endpoint for OpenTelemetry export.",
    )
    OTEL_SERVICE_NAME: str = Field(
        default="bessai-edge-gateway",
        description="Service name reported in distributed traces.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    # ------------------------------------------------------------------
    # Health & Metrics HTTP server
    # ------------------------------------------------------------------
    HEALTH_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port for the /health and /metrics HTTP server.",
    )

    # ------------------------------------------------------------------
    # Derived helpers (not environment variables)
    # ------------------------------------------------------------------
    @property
    def inverter_ip_str(self) -> str:
        """Return the inverter host as a plain string for pymodbus."""
        return self.INVERTER_IP

    @property
    def driver_profile_abs(self) -> Path:
        """Resolve the driver profile path relative to the project root."""
        root = Path(__file__).resolve().parents[2]
        p = Path(self.DRIVER_PROFILE_PATH)
        return p if p.is_absolute() else (root / p)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton ``Settings`` instance.

    Cached via ``lru_cache`` so that environment variables are parsed
    only once per process.  In tests, call ``get_settings.cache_clear()``
    before patching environment variables.
    """
    return Settings()  # type: ignore[call-arg]


class _LazySettings:
    """
    Proxy that resolves ``get_settings()`` on first attribute access.

    This lets application modules write ``from src.core.config import settings``
    without triggering a ``Settings()`` parse at import time (which would
    fail if no ``.env`` file exists, e.g. in unit tests).
    """

    _instance: Optional[Settings] = None

    def _resolve(self) -> Settings:
        if self._instance is None:
            self._instance = get_settings()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._resolve(), name)


#: Module-level lazy singleton — safe to import even without a .env file.
#: Resolves to the real Settings object on first attribute access.
settings: Settings = _LazySettings()  # type: ignore[assignment]
