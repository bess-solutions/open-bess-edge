# launch_api.ps1 — Lanza BESSAI standalone API en puerto libre
$env:DASHBOARD_PORT = "8082"
$env:SITE_ID = "SITE-CL-001"

$REPO = "C:\Users\TCI-GECOMP\Desktop\00 SISTEMA AI-BESS\Antigravity Repository\open-bess-edge"
$PYTHON = "$REPO\.venv\Scripts\python.exe"

Set-Location $REPO

Write-Host ""
Write-Host "  [BESSAI] Lanzando API en http://localhost:$env:DASHBOARD_PORT" -ForegroundColor Green
Write-Host "  [BESSAI] Ctrl+C para detener" -ForegroundColor Yellow
Write-Host ""

& $PYTHON standalone_api.py
