# Test script to verify new architecture is working

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Testing New Architecture" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Run with console output (no -w flag)
Write-Host "[*] Running application with console output..." -ForegroundColor Green
Write-Host "[*] Check for '[New Architecture]' logs below:" -ForegroundColor Yellow
Write-Host ""

uv run python main_gui.py

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Look for these log messages above:" -ForegroundColor Cyan
Write-Host "  [INFO] [New Architecture] Loaded device registry: 4 models" -ForegroundColor Green
Write-Host "  [INFO] [New Architecture] QtAdapter initialized" -ForegroundColor Green
Write-Host "  [INFO] [New Architecture] Available models: ..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
