# website/build.ps1 — BESSAI Website Build v2
# Nuevo sistema: Barlow Condensed + Bloom 3D + Typewriter
# Usage: Run automatically by GitHub Actions (deploy-website.yml)
# Output: website/dist/index.html (fully self-contained)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "BESSAI Website Build v2 — Bloom + Typewriter" -ForegroundColor Cyan
Write-Host ""

# -- Read source files --
$html   = Get-Content "$root\src\index.html"        -Raw -Encoding UTF8
$css1   = Get-Content "$root\src\css\variables.css"  -Raw -Encoding UTF8
$css2   = Get-Content "$root\src\css\base.css"       -Raw -Encoding UTF8
$css3   = Get-Content "$root\src\css\components.css" -Raw -Encoding UTF8
$css4   = Get-Content "$root\src\css\sections.css"   -Raw -Encoding UTF8
$css5   = Get-Content "$root\src\css\responsive.css" -Raw -Encoding UTF8
$js3d   = Get-Content "$root\src\js\universe3d.js"   -Raw -Encoding UTF8
$jsui   = Get-Content "$root\src\js\ui.js"           -Raw -Encoding UTF8

Write-Host "  [OK] Source files read" -ForegroundColor Green

# -- Inline CSS --
$cssAll  = "$css1`n$css2`n$css3`n$css4`n$css5"
$cssBlock = "<style>`n$cssAll`n</style>"

# -- Replace CSS link tags --
$html = $html -replace '(?s)(\s*<link rel="stylesheet" href="css/[^"]+"\s*/>[\r\n]?)+', "`n    $cssBlock`n"

Write-Host "  [OK] CSS inlined" -ForegroundColor Green

# -- Inline universe3d.js (ES module — keep type=module) --
$html = $html -replace '<script type="module" src="js/universe3d\.js"></script>', "<script type=`"module`">`n$js3d`n</script>"

# -- Inline ui.js (classic) --
$html = $html -replace '<script src="js/ui\.js"></script>', "<script>`n$jsui`n</script>"

Write-Host "  [OK] JS inlined" -ForegroundColor Green

# -- Ensure dist/ exists --
$distDir = "$root\dist"
if (-not (Test-Path $distDir)) { New-Item -ItemType Directory $distDir | Out-Null }

# -- Write output (UTF8 no BOM) --
[System.IO.File]::WriteAllText("$distDir\index.html", $html, [System.Text.Encoding]::UTF8)

$sizeKB = [math]::Round((Get-Item "$distDir\index.html").Length / 1KB, 1)
Write-Host "  [OK] dist/index.html written ($sizeKB KB)" -ForegroundColor Green

Write-Host ""
Write-Host "Build complete -> website/dist/" -ForegroundColor Cyan
Write-Host ""
