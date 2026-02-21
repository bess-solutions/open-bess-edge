# ADR-0001: Use pydantic-settings for Configuration Management

## Status
✅ Accepted — 2026-02-19

## Context

The BESSAI Edge Gateway requires robust configuration management that:
- Validates all settings at startup (fail-fast principle)
- Supports multiple sources: environment variables, `.env` files, defaults
- Is type-safe — incorrect types should raise clear errors, not silently fail
- Follows [12-Factor App](https://12factor.net/config) principles for cloud portability

Alternatives considered:
- **`python-dotenv` only**: loads `.env` but no validation or type coercion
- **`dynaconf`**: powerful but complex API, heavy dependency
- **`configparser` / `json`**: manually parsed, no type safety
- **`environ-config`**: lighter, but less integration with the Pydantic ecosystem we already use

## Decision

Use **`pydantic-settings`** (`BaseSettings`) as the single source of truth for configuration.

Key implementation details:
- `Settings` class inherits from `BaseSettings`
- Validation at import time — if `SITE_ID` is missing, the program refuses to start
- `@lru_cache` singleton pattern via `get_settings()` — avoids re-parsing `.env` on every call
- `_LazySettings` proxy for modules imported without a configured environment (tests)
- `INVERTER_IP` uses `str` + regex validator (not `IPvAnyAddress`) to accept DNS hostnames in Docker environments (e.g., `modbus-simulator`)

## Consequences

### Positive
- **Type safety**: wrong config types raise `ValidationError` with clear messages at startup
- **12-Factor compliant**: all config via env vars, no hardcoded values in code
- **Testable**: `conftest.py` injects test env vars; tests never need a `.env` file
- **Pydantic ecosystem consistency**: same validation paradigm as the rest of the codebase (telemetry models)
- **IDE support**: full autocomplete on `settings.SITE_ID`, `settings.INVERTER_PORT`, etc.

### Negative
- **Dependency on pydantic-settings**: adds ~500KB to the install footprint
- **Learning curve**: developers unfamiliar with Pydantic's Settings API may need documentation

### Neutral
- Configuration format is strictly env-var based; YAML/TOML config files would require a different approach
