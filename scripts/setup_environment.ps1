$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

if (-not (Test-Path $Requirements)) {
    throw "requirements.txt not found: $Requirements"
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating project virtual environment..."
    Push-Location $ProjectRoot
    try {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv .venv
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        }
        else {
            throw "Python 3 was not found. Install Python 3.11 or newer."
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Virtual environment creation failed."
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment Python was not created."
}

Write-Host "Installing project dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed."
}

Write-Host "Checking project imports..."
& $VenvPython -c "import pandas, openpyxl, duckdb, pytest, streamlit, plotly; print('PASS: All project packages imported.')"
if ($LASTEXITCODE -ne 0) {
    throw "Project import check failed."
}

Write-Host "PASS: Project environment is ready."
