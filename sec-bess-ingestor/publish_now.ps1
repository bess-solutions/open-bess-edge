#!/usr/bin/env pwsh
<#
.SYNOPSIS
    publish_now.ps1 — Publica el sistema completo a open-bess-edge
    Ejecutar UNA SOLA VEZ con el GITHUB_TOKEN correcto.

.DESCRIPTION
    Este script orquesta el flujo completo:
      1. Corre el pipeline agresivo de scraping + análisis + reportes + BEPs
      2. Publica TODOS los archivos al repo open-bess-edge via GitHub API
      3. Abre automáticamente un Pull Request con toda la información

.PARAMETER Token
    GitHub Personal Access Token con scope 'repo'.
    Si no se pasa, se usa $env:GITHUB_TOKEN.

.EXAMPLE
    .\publish_now.ps1 -Token "ghp_xxxxxxxxxxxxxxxxxxxx"
    .\publish_now.ps1                         # usa $env:GITHUB_TOKEN
#>

param(
    [string]$Token = $env:GITHUB_TOKEN,
    [switch]$SkipScrape,           # Usar datos de scraping ya existentes
    [switch]$Concurrency16,        # Máxima agresividad (16 workers async)
    [switch]$DryRun                # Simular sin publicar (para testing)
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "  sec-bess-ingestor — Pipeline Completo + Publicación" -ForegroundColor Cyan
Write-Host "======================================================`n" -ForegroundColor Cyan

# ── Verificar token ────────────────────────────────────────────────────────────
if (-not $Token -and -not $DryRun) {
    Write-Host "ERROR: GITHUB_TOKEN no configurado." -ForegroundColor Red
    Write-Host "Uso: .\publish_now.ps1 -Token 'ghp_xxxx'"
    Write-Host "     o: `$env:GITHUB_TOKEN = 'ghp_xxxx'; .\publish_now.ps1"
    Write-Host ""
    Write-Host "Generá un token en: https://github.com/settings/tokens/new?scopes=repo"
    exit 1
}

if ($Token) {
    $env:GITHUB_TOKEN = $Token
    Write-Host "[OK] GITHUB_TOKEN configurado (${Token.Substring(0,8)}...)" -ForegroundColor Green
}

$concurrencyFlag = if ($Concurrency16) { "--concurrency 16" } else { "--concurrency 8" }
$publishFlag     = if ($DryRun)        { ""               } else { "--no-dry-run"    }

# ── PASO 1: Scraping agresivo ──────────────────────────────────────────────────
if (-not $SkipScrape) {
    Write-Host "`n[1/5] Scraping agresivo (SEC.cl + coordinador + bcn + minenergia + cne)..." -ForegroundColor Yellow
    Invoke-Expression "python cli.py scrape --aggressive --bess-only $concurrencyFlag"
    if ($LASTEXITCODE -ne 0) { Write-Host "WARN: scrape completó con warnings (normal si algunos servidores rechazaron)" -ForegroundColor Yellow }
} else {
    Write-Host "`n[1/5] Scraping omitido (--SkipScrape)" -ForegroundColor Gray
}

# ── PASO 2: Análisis de brechas ────────────────────────────────────────────────
Write-Host "`n[2/5] Analizando brechas normativas..." -ForegroundColor Yellow
python cli.py analyze
if ($LASTEXITCODE -ne 0) { throw "analyze falló" }

# ── PASO 3: Reporte Markdown ───────────────────────────────────────────────────
Write-Host "`n[3/5] Generando reporte y resumen ejecutivo..." -ForegroundColor Yellow
python cli.py report
if ($LASTEXITCODE -ne 0) { throw "report falló" }

# ── PASO 4: BEPs para brechas críticas ────────────────────────────────────────
Write-Host "`n[4/5] Generando BEPs normativos (BEP-0400+)..." -ForegroundColor Yellow
python scripts/bep_generator.py
if ($LASTEXITCODE -ne 0) { Write-Host "WARN: bep_generator completó con advertencias" -ForegroundColor Yellow }

# ── PASO 5: Publicar TODO al repo open-bess-edge ──────────────────────────────
Write-Host "`n[5/5] Publicando al repo open-bess-edge..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "  [DRY-RUN] Simulando publicación..." -ForegroundColor Gray
    python cli.py publish-all
} else {
    python cli.py publish-all --no-dry-run
    if ($LASTEXITCODE -ne 0) { throw "publish-all falló" }
}

# ── Resumen final ──────────────────────────────────────────────────────────────
Write-Host "`n======================================================" -ForegroundColor Green
Write-Host "   PIPELINE COMPLETADO" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Archivos generados:" -ForegroundColor White
Write-Host "  data/reports/gap_analysis_*.md    (reporte completo)" -ForegroundColor Gray
Write-Host "  data/reports/gap_summary_*.md     (resumen ejecutivo)" -ForegroundColor Gray
Write-Host "  data/beps/BEP-04*.md              (BEPs normativos)" -ForegroundColor Gray
Write-Host "  data/raw/sec_aggressive_*.json    (datos SEC crudos)" -ForegroundColor Gray
Write-Host ""
Write-Host "Repo abierto: https://github.com/bess-solutions/open-bess-edge/pulls" -ForegroundColor Cyan
Write-Host ""
