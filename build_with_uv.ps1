# WIZnet S2E Configuration Tool - Build Script (uv version)
# This script builds a standalone Windows executable using PyInstaller and uv

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WIZnet S2E Tool - Build Script (uv)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Read version from file
$_version = (Get-Content .\version -Raw).Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Host "[*] Building version: $_version" -ForegroundColor Green
Write-Host "[*] Target binary: $target_bin_name.exe" -ForegroundColor Green
Write-Host ""

# Check if uv is installed
try {
    $null = Get-Command uv -ErrorAction Stop
} catch {
    Write-Host "[ERROR] uv is not installed!" -ForegroundColor Red
    Write-Host "Please install uv first: https://docs.astral.sh/uv/" -ForegroundColor Yellow
    Write-Host "Or run: pip install uv" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment with uv if not exists
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment with uv..." -ForegroundColor Green
    uv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Install dependencies
Write-Host "[*] Installing dependencies..." -ForegroundColor Green
uv pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install PyInstaller
Write-Host "[*] Installing PyInstaller..." -ForegroundColor Green
uv pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install PyInstaller" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[*] Running PyInstaller..." -ForegroundColor Green
Write-Host ""

# Run PyInstaller with uv
uv run pyinstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --icon "gui/icon.ico" `
    --name $target_bin_name `
    --clean `
    --add-data "gui;gui/" `
    --add-data "version;." `
    --add-data "config;config/" `
    --hidden-import=ifaddr `
    main_gui.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] PyInstaller build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Build completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output: dist\$target_bin_name.exe" -ForegroundColor Cyan
Write-Host ""
