@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Betting Predictor — Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.11 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found.
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js found.

:: Check uv
uv --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] uv not found. Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] Failed to install uv. Please install manually:
        echo   https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
)
echo [OK] uv found.

:: Check .env
if not exist ".env" (
    echo.
    echo [SETUP] Creating .env from template...
    copy ".env.example" ".env"
    echo.
    echo  !! IMPORTANT !!
    echo  Open .env and fill in your API keys before continuing:
    echo    - LLM_API_KEY  (Groq key from https://console.groq.com)
    echo    - FOOTBALL_DATA_API_KEY  (from https://www.football-data.org)
    echo.
    notepad .env
    echo Press any key after saving your .env file...
    pause >nul
)

:: Download MiroFish if not present
if not exist "mirofish" (
    echo.
    echo [SETUP] Downloading MiroFish...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/666ghj/MiroFish/archive/refs/heads/main.zip' -OutFile 'mirofish.zip'"
    if errorlevel 1 (
        echo [ERROR] Failed to download MiroFish. Check your internet connection.
        pause
        exit /b 1
    )
    echo [SETUP] Extracting MiroFish...
    powershell -Command "Expand-Archive -Path 'mirofish.zip' -DestinationPath '.' -Force"
    rename "MiroFish-main" "mirofish"
    del "mirofish.zip"
    echo [OK] MiroFish downloaded.
) else (
    echo [OK] MiroFish already present.
)

:: Apply patches
echo.
echo [SETUP] Applying patches to MiroFish...
call apply_patches.bat
if errorlevel 1 (
    echo [ERROR] Patching failed.
    pause
    exit /b 1
)
echo [OK] Patches applied.

:: Create data directory
if not exist "data" mkdir data
if not exist "mirofish\data" mkdir mirofish\data

:: Copy env to MiroFish backend
copy ".env" "mirofish\.env" >nul

:: Install Python dependencies for our pipeline
echo.
echo [SETUP] Installing Python pipeline dependencies...
pip install requests beautifulsoup4 lxml pandas python-dotenv aiohttp apscheduler pydantic >nul 2>&1
echo [OK] Python dependencies installed.

:: Install MiroFish backend
echo.
echo [SETUP] Installing MiroFish backend (this may take a few minutes)...
cd mirofish
uv sync >nul 2>&1
if errorlevel 1 (
    echo [WARN] uv sync failed, trying pip install...
    pip install -r backend\requirements.txt >nul 2>&1
)
cd ..
echo [OK] Backend dependencies installed.

:: Install MiroFish frontend
echo.
echo [SETUP] Installing MiroFish frontend...
cd mirofish
npm install >nul 2>&1
cd ..
echo [OK] Frontend dependencies installed.

echo.
echo ============================================
echo   Setup complete!
echo   Run start.bat to launch the app.
echo   Then open http://localhost:3000
echo ============================================
pause
