# setup_bootloader.ps1
# Provide PyInstaller with a custom-compiled bootloader (antivirus false-positive mitigation).
# Procedure: doc/dev/SETUP_DEV-ko.md Part B, adapted for *portable* MSVC (no Visual Studio installed).
#
# Two modes (automatic):
#   A) wheels\pyinstaller-*.whl already exists  -> just pip-install it (no compiler needed, seconds)
#   B) no wheel yet                              -> compile bootloader, build a wheel into wheels\, install it
#
# So you only compile ONCE. The resulting wheel in wheels\ is reused forever (and portable to other PCs
# with the same Python ABI / win_amd64).
#
# NOTE: messages are ASCII on purpose. Windows PowerShell 5.1 reads BOM-less .ps1 as the system code
#       page (CP949 here), which would garble Korean text.
#
# Prereq: .venv created via  uv venv --python 3.12
# Run:    .\setup_bootloader.ps1

$ErrorActionPreference = "Stop"
$root     = $PSScriptRoot
$wheelDir = "$root\wheels"
$py       = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error ".venv not found. Run: uv venv --python 3.12"; exit 1 }

# ============================ MODE A: install cached wheel ============================
$wheel = Get-ChildItem "$wheelDir\pyinstaller-*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($wheel) {
    Write-Output "[A] Found cached wheel: $($wheel.Name)"
    Write-Output "    Installing (no compilation needed) ..."
    uv pip install --reinstall-package pyinstaller $wheel.FullName
    & $py -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)"
    Write-Output "Done. Now run .\build.ps1 (or VSCode Ctrl+Shift+B) for a signed build."
    exit 0
}

# ============================ MODE B: compile + build wheel ===========================
Write-Output "[B] No cached wheel found -> compiling bootloader once, then building a reusable wheel."

# --- discover toolchain via Everything (find_build_env.py) ---------------------
# No hard-coded paths: cl.exe / SDK headers / libs / signtool are located through
# the Everything index, so this keeps working wherever MSVC/SDK are installed.
Write-Output "    discovering toolchain via Everything ..."
$be = & $py "$root\find_build_env.py" | ConvertFrom-Json
if (-not $be.ok) { Write-Error "find_build_env.py failed: $($be.reason)"; exit 1 }
$env:PATH    = "$($be.PATH_ADD);$env:PATH"
$env:INCLUDE = $be.INCLUDE
$env:LIB     = $be.LIB
$env:PYI_NO_MSVC_DETECT = "1"   # patched wscript: skip waf autodetect, use env above
Write-Output "    cl       : $($be.CL)"
Write-Output "    signtool : $($be.SIGNTOOL)"

# --- 1) PyInstaller source (clone if missing) ---------------------------------
$src = "$root\_pyinstaller_src"
if (-not (Test-Path "$src\bootloader\wscript")) {
    Write-Output "    cloning PyInstaller v6.17.0 ..."
    git clone --branch v6.17.0 --depth 1 https://github.com/pyinstaller/pyinstaller.git $src
    Write-Warning "Fresh clone: re-apply the wscript NO_MSVC_DETECT patch (configure: PYI_NO_MSVC_DETECT branch + DEST_CPU)."
}

# --- 2) wipe prebuilt bootloaders so the compile is proven --------------------
$btdir  = "$src\PyInstaller\bootloader\Windows-64bit-intel"
$runexe = "$btdir\run.exe"
if (Test-Path $btdir) { Remove-Item "$btdir\*.exe" -Force -ErrorAction SilentlyContinue }

# --- 3) compile bootloader (waf) via main .venv python ------------------------
Write-Output "    compiling bootloader (waf distclean all) ..."
Push-Location "$src\bootloader"
try { & $py .\waf distclean all } finally { Pop-Location }
if (-not (Test-Path $runexe)) { Write-Error "FAILED: $runexe not produced. See waf output above."; exit 1 }
$ri = Get-Item $runexe
Write-Output "    compiled OK: run.exe ($($ri.Length) bytes, $($ri.LastWriteTime))"

# --- 4) build a wheel containing the freshly compiled bootloader --------------
Write-Output "    building wheel into wheels\ ..."
New-Item -ItemType Directory -Force -Path $wheelDir | Out-Null
uv build --wheel --out-dir $wheelDir $src
$wheel = Get-ChildItem "$wheelDir\pyinstaller-*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wheel) { Write-Error "FAILED: wheel not produced in $wheelDir."; exit 1 }
Write-Output "    wheel: $($wheel.Name)"

# --- 5) install the wheel + verify --------------------------------------------
uv pip install --reinstall-package pyinstaller $wheel.FullName
& $py -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)"
Write-Output ""
Write-Output "Done. Wheel cached in wheels\ -- next runs skip compilation entirely."
Write-Output "Now run .\build.ps1 (or VSCode Ctrl+Shift+B) for a signed build."
