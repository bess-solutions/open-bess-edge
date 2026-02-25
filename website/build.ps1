# website/build.ps1 — Build self-contained dist/index.html
# Usage: .\website\build.ps1
# Output: website/dist/index.html (fully self-contained)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n🔨 BESSAI Website Build`n" -ForegroundColor Cyan

# ── Read source files ──────────────────────────────────────
$html  = Get-Content "$root\src\index.html"      -Raw -Encoding UTF8
$base  = Get-Content "$root\src\css\base.css"    -Raw -Encoding UTF8
$lay   = Get-Content "$root\src\css\layout.css"  -Raw -Encoding UTF8
$resp  = Get-Content "$root\src\css\responsive.css" -Raw -Encoding UTF8
$i18n  = Get-Content "$root\src\js\i18n.js"     -Raw -Encoding UTF8
$main  = Get-Content "$root\src\js\main.js"      -Raw -Encoding UTF8
$esStr = Get-Content "$root\i18n\es.json"        -Raw -Encoding UTF8

Write-Host "  ✓ Source files read" -ForegroundColor Green

# ── Inject default ES strings inline ─────────────────────
# Escape backticks/dollar signs for PowerShell string
$esStrEscaped = $esStr -replace '\\', '\\' -replace '`', '``'

$inlineI18nSetup = @"

/* i18n inline bootstrap */
(function(){
  const ES_STRINGS = $esStr;
  document.addEventListener('DOMContentLoaded', function(){
    I18N.init(ES_STRINGS);
    BESSAI.init();
  });
})();
"@

# ── Build inline CSS block ─────────────────────────────────
$cssBlock = "<style>`n$base`n$lay`n$resp`n</style>"

# ── Build inline JS block ──────────────────────────────────
$jsBlock = "<script>`n$i18n`n$main`n$inlineI18nSetup`n</script>"

# ── Replace placeholders ───────────────────────────────────
$out = $html -replace '<!-- BUILD:CSS -->', $cssBlock
$out = $out  -replace '<!-- BUILD:JS -->',  $jsBlock

# ── Ensure dist/ exists ────────────────────────────────────
$distDir = "$root\dist"
if (-not (Test-Path $distDir)) { New-Item -ItemType Directory $distDir | Out-Null }

# ── Copy assets ───────────────────────────────────────────
$assetsDir = "$distDir\assets"
if (-not (Test-Path $assetsDir)) { New-Item -ItemType Directory $assetsDir | Out-Null }
Copy-Item "$root\src\assets\*" $assetsDir -Force

# ── Copy i18n JSONs (for runtime lang switch fetch) ───────
$i18nDist = "$distDir\i18n"
if (-not (Test-Path $i18nDist)) { New-Item -ItemType Directory $i18nDist | Out-Null }
Copy-Item "$root\i18n\*.json" $i18nDist -Force

# ── Write output ───────────────────────────────────────────
[System.IO.File]::WriteAllText("$distDir\index.html", $out, [System.Text.Encoding]::UTF8)

$size = [math]::Round((Get-Item "$distDir\index.html").Length / 1KB, 1)
Write-Host "  ✓ dist/index.html written ($size KB)" -ForegroundColor Green
Write-Host "  ✓ assets/ and i18n/ copied" -ForegroundColor Green
Write-Host "`n✅ Build complete → website/dist/`n" -ForegroundColor Cyan
