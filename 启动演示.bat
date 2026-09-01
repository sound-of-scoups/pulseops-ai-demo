@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Starting FastAPI backend...
start "PulseOps Backend" /D "%~dp0backend" powershell -NoExit -ExecutionPolicy Bypass -Command "$env:PYTHONPATH=(Get-Location).Path; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/3] Starting Vue frontend...
start "PulseOps Frontend" /D "%~dp0frontend" powershell -NoExit -ExecutionPolicy Bypass -Command "npm run dev -- --host 127.0.0.1"

echo [3/3] Opening frontend...
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173/"
echo Done. Keep both PowerShell windows open while using the demo.
pause
