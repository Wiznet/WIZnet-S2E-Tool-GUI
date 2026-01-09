# WIZnet S2E Configuration Tool - Run Script (uv version)
# This script uses uv for fast dependency management

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WIZnet S2E Configuration Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
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

Write-Host "[*] Syncing dependencies with uv..." -ForegroundColor Green
# uv sync는 .venv를 자동으로 찾아서 사용
uv sync

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to sync dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[*] Starting WIZnet S2E Configuration Tool..." -ForegroundColor Green
Write-Host ""

# uv run은 .venv를 자동으로 사용
uv run python main_gui.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Application exited with error code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}
