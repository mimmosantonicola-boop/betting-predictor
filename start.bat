@echo off
echo ============================================
echo   Betting Predictor — Starting Services
echo ============================================
echo.

if not exist "mirofish" (
    echo [ERROR] MiroFish not found. Run setup.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Copy latest .env to MiroFish
copy ".env" "mirofish\.env" >nul

echo [1/3] Starting MiroFish backend (http://localhost:5001)...
start "MiroFish Backend" cmd /k "cd /d %~dp0mirofish && uv run python backend\run.py"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Betting API server (http://localhost:5050)...
start "Betting API" cmd /k "cd /d %~dp0 && python api_server.py"

timeout /t 2 /nobreak >nul

echo [3/3] Starting frontend (http://localhost:3000)...
start "MiroFish Frontend" cmd /k "cd /d %~dp0mirofish && npm run dev"

timeout /t 5 /nobreak >nul

echo.
echo ============================================
echo   All services starting...
echo.
echo   Betting Dashboard: http://localhost:3000/betting
echo   MiroFish UI:       http://localhost:3000
echo   Betting API:       http://localhost:5050
echo   MiroFish API:      http://localhost:5001
echo.
echo   Close the 3 terminal windows to stop.
echo ============================================
pause
