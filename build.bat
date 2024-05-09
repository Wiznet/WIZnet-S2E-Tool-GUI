@echo off
REM Read version from file
set /p _version=<version
REM Trim any whitespace
for /f "tokens=*" %%a in ("%_version%") do set _version=%%a
REM Define target binary name
set target_bin_name=wizconfig_s2e_tool_%_version%
echo %target_bin_name%

REM Run PyInstaller with the specified parameters
pyinstaller.exe -w -F -n %target_bin_name% --add-data=".\\gui\\*;.\\gui" .\main_gui.py