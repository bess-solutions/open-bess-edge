# demo.ps1 - Open BESS Edge Demo Kit (Windows PowerShell)
# SPDX-License-Identifier: Apache-2.0

Write-Host "🔋 Open BESS Edge v1.0 — Demo Kit Setup (Windows)" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green

# Check Python
try {
    $pythonVersion = python --version
    Write-Host "✅ Python detectado: $pythonVersion"
} catch {
    Write-Error "❌ Error: Python no está instalado en el PATH del sistema."
    Exit
}

# Create venv if nonexistent
if (-not (Test-Path -Path ".venv")) {
    Write-Host "📦 Creando entorno virtual (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

# Install dependencies using virtualenv python
Write-Host "📥 Instalando dependencias del gateway y del servidor MCP..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -r mcp_server/requirements.txt

# Start demo simulator in background
Write-Host "⚡ Iniciando el simulador en segundo plano..." -ForegroundColor Yellow
$simJob = Start-Job -ScriptBlock {
    Set-Location $using:PSScriptRoot
    & .\.venv\Scripts\python.exe demo_server.py
}

# Let the simulator boot
Start-Sleep -Seconds 2

# Start MCP Server in foreground
Write-Host "🔌 Iniciando el Servidor MCP (stdio)..." -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host "✅ Servidor ejecutándose en stdio. Conecta con Claude Desktop usando:" -ForegroundColor Cyan
Write-Host "   { 'mcpServers': { 'open-bess-edge': { 'command': 'python', 'args': ['$PSScriptRoot/mcp_server/server.py'] } } }" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Green

& .\.venv\Scripts\python.exe mcp_server/server.py

# Cleanup on exit
Write-Host "Stopping background simulator..."
Stop-Job $simJob
Remove-Job $simJob
