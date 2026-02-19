#!/usr/bin/env bash
# =============================================================================
# setup_structure.sh
# BESSAI Edge Gateway — Repository scaffold script
# Usage: bash setup_structure.sh [TARGET_DIR]
#
# Creates the full directory and file scaffold for the open-bess-edge project.
# Compatible with bash 4+ on Linux, macOS, and WSL.
# =============================================================================
set -euo pipefail

ROOT="${1:-open-bess-edge}"

echo "🔧  Creating BESSAI Edge Gateway structure at: ${ROOT}"

# ---------------------------------------------------------------------------
# 1. Directory tree
# ---------------------------------------------------------------------------
DIRS=(
  "${ROOT}/src/core"
  "${ROOT}/src/drivers"
  "${ROOT}/src/interfaces"
  "${ROOT}/registry"
  "${ROOT}/config"
  "${ROOT}/tests"
  "${ROOT}/infrastructure/terraform"
  "${ROOT}/infrastructure/docker"
  "${ROOT}/docs"
)

for dir in "${DIRS[@]}"; do
  mkdir -p "${dir}"
  echo "  📁  ${dir}"
done

# ---------------------------------------------------------------------------
# 2. Python package markers
# ---------------------------------------------------------------------------
INITS=(
  "${ROOT}/src/__init__.py"
  "${ROOT}/src/core/__init__.py"
  "${ROOT}/src/drivers/__init__.py"
  "${ROOT}/src/interfaces/__init__.py"
  "${ROOT}/tests/__init__.py"
)

for f in "${INITS[@]}"; do
  touch "${f}"
  echo "  🐍  ${f}"
done

# ---------------------------------------------------------------------------
# 3. Placeholder registry & config files
# ---------------------------------------------------------------------------
cat > "${ROOT}/registry/.gitkeep" <<'EOF'
# Place device JSON registry files here.
# Example: battery_rack_01.json
EOF

cat > "${ROOT}/config/.env.example" <<'EOF'
# Copy to .env and fill in your values
BESS_MODBUS_HOST=192.168.1.100
BESS_MODBUS_PORT=502
GCP_PROJECT_ID=your-gcp-project-id
GCP_PUBSUB_TOPIC=bess-telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
LOG_LEVEL=INFO
EOF
echo "  ⚙️   ${ROOT}/config/.env.example"

# ---------------------------------------------------------------------------
# 4. Root-level placeholders
# ---------------------------------------------------------------------------
touch "${ROOT}/docs/.gitkeep"
touch "${ROOT}/infrastructure/terraform/.gitkeep"
touch "${ROOT}/infrastructure/docker/.gitkeep"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "✅  Structure created successfully!"
echo "    Next steps:"
echo "    1. cd ${ROOT}"
echo "    2. python -m venv .venv && source .venv/bin/activate"
echo "    3. pip install -r requirements.txt"
echo "    4. cp config/.env.example config/.env && edit config/.env"
