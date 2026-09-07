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

# Copiar manifiesto de dependencias e instalar
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copiar código fuente y configuración
COPY config/ ./config/
COPY data/ ./data/
COPY src/ ./src/

# Usuario sin privilegios por seguridad en subestación
RUN useradd -u 1001 -m bessedge && chown -R bessedge:bessedge /app
USER bessedge

EXPOSE 502/tcp 8080/tcp

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "from src.drivers.modbus_client import ModbusBESSClient; print('OK')" || exit 1

ENTRYPOINT ["python", "-m", "src.edge_node"]
