@echo off
REM build.bat - Wrapper to call build.ps1
REM This ensures build.ps1 is the single source of truth for build commands

powershell.exe -ExecutionPolicy Bypass -File "%~dp0build.ps1"
