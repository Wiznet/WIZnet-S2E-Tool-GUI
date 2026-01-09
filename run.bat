@echo off
REM WIZnet S2E Configuration Tool - Run Script (uv version)
REM This script uses uv for fast dependency management

echo ========================================
echo WIZnet S2E Configuration Tool
echo ========================================
echo.

REM Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] uv is not installed!
    echo Please install uv first: https://docs.astral.sh/uv/
    echo Or run: pip install uv
    pause
    exit /b 1
)

echo [*] Installing dependencies with uv...
uv pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [*] Starting WIZnet S2E Configuration Tool...
echo.

REM Run the application
uv run python main_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)
