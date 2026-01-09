@echo off
REM Read version from file
set /p _version=<version
REM Trim any whitespace
for /f "tokens=*" %%a in ("%_version%") do set _version=%%a
REM Define target binary name
set target_bin_name=wizconfig_s2e_tool_%_version%
echo %target_bin_name%

REM Run PyInstaller with the specified parameters
@REM pyinstaller -w -F -n wizconfig_s2e_tool_1.5.5.1 --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" .\main_gui.py
@REM poetry run pyinstaller  -w -F --clean --log-level DEBUG -n %target_bin_name% --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" --paths="D:\\user\\util\\installed\\python3.9\\Lib\\site-packages" .\main_gui.py
@REM poetry run pyinstaller  -w -F --clean -n %target_bin_name% --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" .\main_gui.py
@REM auto-py-to-exe
poetry run pyinstaller --noconfirm --onefile --windowed --icon "D:/user/src/github/WIZnet-S2E-Tool-GUI/gui/icon.ico" --name "wizconfig_s2e_tool_1.5.5.3" --clean --add-data "D:/user/src/github/WIZnet-S2E-Tool-GUI/gui;gui/" --add-data "D:/user/src/github/WIZnet-S2E-Tool-GUI/version;."  "D:/user/src/github/WIZnet-S2E-Tool-GUI/main_gui.py"