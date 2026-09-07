# ==============================================================================
# Open BESS Edge — Production Industrial Edge Gateway Container
# Multi-arch support for x86_64 and ARM64 (IPC Advantech / Siemens / Raspberry Pi CM4)
# ==============================================================================

FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    EDGE_CONFIG_PATH=/app/config/edge_config.yaml

WORKDIR /app

# Instalar dependencias esenciales de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar manifiesto y código fuente para instalación
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir .

# Copiar configuración y datos
COPY config/ ./config/
COPY data/ ./data/

# Usuario sin privilegios por seguridad en subestación
RUN useradd -u 1001 -m bessedge && chown -R bessedge:bessedge /app
USER bessedge

EXPOSE 502/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "from src.config import load_config; load_config()" || exit 1

ENTRYPOINT ["python", "-m", "src.edge_node"]
