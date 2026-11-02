$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuilderPath = Join-Path $ProjectRoot "src\build_monthly_report.py"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"

$Month = (Get-Date).AddMonths(-1).ToString("yyyy-MM")
$LogPath = Join-Path $LogDir ("monthly_report_{0}.log" -f $Month)

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

"==================================================" | Out-File $LogPath -Append -Encoding utf8
"Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $LogPath -Append -Encoding utf8
"Reporting month: $Month" | Out-File $LogPath -Append -Encoding utf8

$ExitCode = 1
try {
    if (-not (Test-Path $BuilderPath)) {
        throw "Report builder not found: $BuilderPath"
    }
    if (-not (Test-Path $PythonExe)) {
        throw "Project Python environment not found. Run scripts\setup_environment.ps1 first."
    }

    Push-Location $ProjectRoot
    try {
        & $PythonExe $BuilderPath --month $Month *>> $LogPath
        $ExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
catch {
    $_ | Out-String | Out-File $LogPath -Append -Encoding utf8
    $ExitCode = 1
}

"Finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $LogPath -Append -Encoding utf8
"Exit code: $ExitCode" | Out-File $LogPath -Append -Encoding utf8

exit $ExitCode
