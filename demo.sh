#!/bin/bash
# demo.sh - Open BESS Edge Demo Kit
# SPDX-License-Identifier: Apache-2.0

echo "🔋 Open BESS Edge v1.0 — Demo Kit Setup"
echo "======================================"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 no está instalado en el sistema."
    exit 1
fi

# Create venv if nonexistent
if [ ! -d ".venv" ]; then
    echo "📦 Creando entorno virtual (.venv)..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "📥 Instalando dependencias del gateway y del servidor MCP..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r mcp_server/requirements.txt

# Start demo Modbus TCP and API simulator in background
echo "⚡ Iniciando el simulador en segundo plano..."
python demo_server.py &
SIM_PID=$!

# Let the simulator boot
sleep 2

# Start MCP Server in foreground
echo "🔌 Iniciando el Servidor MCP (stdio)..."
echo "======================================"
echo "✅ Servidor ejecutándose en stdio. Conecta con Claude Desktop usando:"
echo "   { 'mcpServers': { 'open-bess-edge': { 'command': 'python', 'args': ['$(pwd)/mcp_server/server.py'] } } }"
echo "======================================"

python mcp_server/server.py

# Cleanup on exit
kill $SIM_PID 2>/dev/null
