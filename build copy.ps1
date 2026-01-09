$_version = Get-Content .\version -Raw
$_version = $_version.Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Output "$target_bin_name"

# pyinstaller.exe -w -F -n $target_bin_name --add-data=".\\gui\\*":".\\gui":".\\version" .\main_gui.py
# C:\Users\user\AppData\Local\pypoetry\Cache\virtualenvs\wiznet-s2e-tool-gui-euVlqKdK-py3.9\Scripts\pyinstaller.exe -w -F -n $target_bin_name --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" .\main_gui.py
# $_version = Get-Content .\version -Raw ; $_version = $_version.Trim() ; $target_bin_name = "wizconfig_s2e_tool_$_version" ; Write-Output "$target_bin_name" ; pyinstaller.exe -w -F -n $target_bin_name --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" --hidden-import=ifaddr .\main_gui.py
pyinstaller.exe -w -F -n $target_bin_name --add-data=".\\gui\\*":".\\gui" --add-data=".\\version":".\\" .\main_gui.py