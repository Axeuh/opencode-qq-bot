@echo off
title Axeuh_home QQ Bot Launcher

echo ============================================================
echo   Axeuh_home QQ Bot Launcher
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Check config file
if not exist "config.yaml" (
    echo [ERROR] Config file config.yaml not found
    pause
    exit /b 1
)

REM Create directories
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "downloads" mkdir downloads

echo [1/4] Checking Python version...
python --version
echo.

echo [2/4] Checking dependencies...
python -c "import aiohttp; import yaml; print('OK: aiohttp ' + aiohttp.__version__); print('OK: PyYAML ' + yaml.__version__)" 2>nul
if errorlevel 1 (
    echo [ERROR] Missing dependencies. Run: pip install -r requirements.txt
    pause
    exit /b 1
)
echo.

echo [3/4] Checking config...
echo OK: Found config.yaml
echo.

echo [4/4] Starting bot...
echo ------------------------------------------------------------
python scripts/run_bot.py

pause
