# =============================================================================
# BESSAI Edge Gateway — Multi-stage Dockerfile
# =============================================================================
# Stage 1: builder  — installs dependencies into an isolated venv
# Stage 2: runtime  — minimal image with only the venv copied in
#
# Design decisions:
#   * python:3.11-slim for a balance of size and compatibility.
#   * Non-root user (bess) for security.
#   * PYTHONDONTWRITEBYTECODE + PYTHONUNBUFFERED for clean container logs.
#   * Health-check via a lightweight Python import probe.
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

# Install build tools needed for native extensions (pymodbus, cryptography …)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency manifest first to leverage Docker layer cache
COPY requirements.txt .

# Create isolated virtual environment and install deps
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

LABEL maintainer="ingenieria@bess-solutions.cl" \
      org.opencontainers.image.title="BESSAI Edge Gateway" \
      org.opencontainers.image.description="Industrial BESS gateway — NTSyCS compliant" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.licenses="Apache-2.0"

# Runtime-only system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Security: run as non-root
RUN groupadd --gid 1001 bess && \
    useradd  --uid 1001 --gid bess --shell /bin/sh --create-home bess

# Copy venv from builder (not the whole /build folder)
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application source
COPY --chown=bess:bess src/       ./src/
COPY --chown=bess:bess registry/  ./registry/
COPY --chown=bess:bess config/    ./config/

USER bess

# Activate venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Lightweight liveness probe: verify the package is importable
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from src.core.config import settings; print('OK')" || exit 1

ENTRYPOINT ["python", "-m", "src.core.main"]
