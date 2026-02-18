param(
    [string]$PythonExe = ".\env\Scripts\python.exe",
    [string]$AppName = "Task-Automation-Studio 1.0.0"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

& $PythonExe -m pip install -e .[dev]

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "$AppName" `
    --collect-all PySide6 `
    --collect-all shiboken6 `
    src/task_automation_studio/desktop_entry.py

Write-Host "Build completed. EXE path: dist\$AppName\$AppName.exe"
