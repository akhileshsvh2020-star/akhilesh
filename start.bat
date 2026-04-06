@echo off
title PDF2Word Launcher
echo ================================
echo  Starting PDF2Word App...
echo ================================

:: ── Install Python deps ─────────────────────────────────────────────────────
echo Installing Python dependencies from requirements.txt...
cd /d %~dp0backend
pip install -r requirements.txt --quiet

:: ── Validate .env exists ───────────────────────────────────────────────────
if not exist "%~dp0backend\.env" (
    echo.
    echo  ERROR: backend\.env not found!
    echo  Copy backend\.env.example to backend\.env and fill in your keys.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo.
    echo  ERROR: .env not found in project root!
    echo  Copy .env.example to .env and fill in your VITE_API_KEY.
    echo.
    pause
    exit /b 1
)

:: ── Start Python backend ───────────────────────────────────────────────────
start "Backend (port 8000)" cmd /k "cd /d %~dp0backend && python api.py"

:: Wait for backend to boot
timeout /t 3 /nobreak >nul

:: ── Start Vite frontend ────────────────────────────────────────────────────
start "Frontend (port 5173)" cmd /k "cd /d %~dp0 && npm run dev"

:: Open browser
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo  Both servers are running!
echo   - Backend:  http://localhost:8000
echo   - Frontend: http://localhost:5173
echo   - Health:   http://localhost:8000/health
echo.
echo  Close the two server windows to stop everything.
pause
