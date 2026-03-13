@echo off
chcp 65001 >nul
title Bot Restart Tool

echo ================================================
echo Bot Restart Tool
echo ================================================
echo.

echo [1/4] Stopping bot processes...
taskkill /F /IM python.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Bot processes stopped
) else (
    echo [INFO] No running bot processes found
)
echo.

echo [2/4] Waiting for processes to exit...
timeout /t 2 /nobreak >nul
echo [OK] Wait complete
echo.

echo [3/4] Validating Python syntax...
python -m py_compile src/core/onebot_client.py src/core/http_server.py src/core/command_system.py src/core/connection_lifecycle.py src/core/message_router.py src/core/event_handlers.py src/utils/config.py src/utils/config_loader.py 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Syntax validation failed!
    echo.
    echo Running detailed syntax check...
    python -m py_compile src/core/onebot_client.py
    python -m py_compile src/core/http_server.py
    python -m py_compile src/core/command_system.py
    python -m py_compile src/core/connection_lifecycle.py
    python -m py_compile src/core/message_router.py
    python -m py_compile src/core/event_handlers.py
    python -m py_compile src/utils/config.py
    python -m py_compile src/utils/config_loader.py
    echo.
    echo ================================================
    echo [FAILED] Bot restart aborted due to syntax errors!
    echo ================================================
    echo.
    pause
    exit /b 1
)
echo [OK] Syntax validation passed
echo.

echo [4/4] Starting bot...
start "" "start_en.bat"
echo [OK] Bot started
echo.

echo ================================================
echo [SUCCESS] Bot restart complete!
echo ================================================
echo.

timeout /t 3 /nobreak >nul
exit