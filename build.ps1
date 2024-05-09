$_version = Get-Content .\version -Raw
$_version = $_version.Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Output "$target_bin_name"

pyinstaller.exe -w -F -n $target_bin_name --add-data=".\\gui\\*":".\\gui" .\main_gui.py