param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "The GameScriptDev Operator Application must be built on Windows."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = $venvPython
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python was not found at '$Python'. Create .venv and install the project with the 'package' extra."
}

$specPath = Join-Path $repoRoot "packaging\GameScriptDev.spec"
$distPath = Join-Path $repoRoot "dist"
$workPath = Join-Path $repoRoot "build"

& $Python -c "import PyInstaller, webview"
if ($LASTEXITCODE -ne 0) {
    throw "Packaging dependencies are missing. Install the project with the 'package' extra."
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $distPath `
    --workpath $workPath `
    $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$executable = Join-Path $distPath "GameScriptDev\GameScriptDev.exe"
$dashboardIndex = Join-Path $distPath "GameScriptDev\_internal\game_script_dev\dashboard\static\index.html"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "The expected Operator Application executable was not produced."
}
if (-not (Test-Path -LiteralPath $dashboardIndex -PathType Leaf)) {
    throw "The packaged dashboard assets were not produced."
}

Write-Host "Operator Application proof built at: $executable"
