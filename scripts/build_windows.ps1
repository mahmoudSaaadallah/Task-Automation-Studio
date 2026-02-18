param(
    [string]$PythonExe = ".\env\Scripts\python.exe",
    [string]$AppName = "Task-Automation-Studio 1.0.0",
    [string]$SpecFile = ".\Task-Automation-Studio 1.0.0.spec"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

& $PythonExe -m pip install -e .[dev]

if (-not (Test-Path $SpecFile)) {
    throw "Spec file not found: $SpecFile"
}

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    "$SpecFile"

Write-Host "Build completed. EXE path: dist\$AppName\$AppName.exe"
