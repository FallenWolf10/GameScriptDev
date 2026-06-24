param(
    [string]$Python = "auto",
    [string]$PythonVersion = "3.11",
    [switch]$IncludeOptionalOcr,
    [switch]$IncludeOptionalOpencv
)

$ErrorActionPreference = "Stop"

function Resolve-PythonLauncher {
    param([string]$Requested)

    if ($Requested -ne "auto") {
        return $Requested
    }

    foreach ($candidate in @("py", "python", "python3")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }

    throw "No Python launcher was found. Install Python 3.11 and make 'py', 'python', or 'python3' available on PATH."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\\python.exe"
$pythonLauncher = Resolve-PythonLauncher -Requested $Python

Write-Host "Creating virtual environment with Python $PythonVersion..."
if ($pythonLauncher -eq "py") {
    & $pythonLauncher -$PythonVersion -m venv $venvPath
}
else {
    Write-Host "Using launcher '$pythonLauncher'. Ensure it points to Python $PythonVersion."
    & $pythonLauncher -m venv $venvPath
}

Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

$extras = @("dev")
if ($IncludeOptionalOpencv) {
    $extras += "opencv"
}

$extrasSuffix = ""
if ($extras.Count -gt 0) {
    $extrasSuffix = "[" + ($extras -join ",") + "]"
}
$projectSpec = $repoRoot + $extrasSuffix

Write-Host "Installing project dependencies..."
& $venvPython -m pip install -e $projectSpec

if ($IncludeOptionalOcr) {
    Write-Host "Installing optional OCR Python package..."
    & $venvPython -m pip install pytesseract
    Write-Host "OCR note: Tesseract itself must also be installed and available on PATH."
}

Write-Host "Running startup checks..."
& $venvPython -m game_script_dev doctor --workspace $repoRoot --logs (Join-Path $repoRoot "logs")

Write-Host ""
Write-Host "Setup complete."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run tests with: python -m pytest"
