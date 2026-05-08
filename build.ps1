# build.ps1
# 사용법:
#   .\build.ps1                → 빌드 + 서명 둘 다 생성 (기본)
#   .\build.ps1 -NoSign        → 빌드만 (서명 건너뜀)
#   .\build.ps1 -PfxPath "C:\my.pfx"  → 커스텀 PFX로 서명

param(
    [switch]$NoSign,
    [string]$PfxPath        = "C:\Users\user\wiznet_codesign.pfx",
    [string]$SignTool       = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
)

$_version = Get-Content .\version -Raw
$_version = $_version.Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Output "$target_bin_name"

# 구버전 .spec 파일 정리 (현재 버전 제외)
Get-ChildItem .\*.spec | Where-Object { $_.Name -ne "$target_bin_name.spec" } | Remove-Item -Force
Write-Output "Cleaned up old .spec files"

# Run build via uv to use the .venv environment
uv run python -m PyInstaller -w -F -n $target_bin_name --add-data ".\\gui\\*;.\\gui" --add-data ".\\version;.\\" --add-data ".\\config\\*.yaml;.\\config" --add-data ".\\config\\*.json;.\\config" .\main_gui.py

if ($NoSign) {
    Write-Output "Build complete (unsigned): dist\$target_bin_name.exe"
    exit 0
}

# ── 서명 단계 ──────────────────────────────────────────────────────────────
$unsigned = "dist\$target_bin_name.exe"
$signed   = "dist\${target_bin_name}_signed.exe"

if (-not (Test-Path $unsigned)) {
    Write-Error "Build output not found: $unsigned"
    exit 1
}
if (-not (Test-Path $PfxPath)) {
    Write-Error "PFX not found: $PfxPath"
    exit 1
}
if (-not (Test-Path $SignTool)) {
    Write-Error "signtool.exe not found: $SignTool"
    exit 1
}

# 서명용 복사본 생성
Copy-Item $unsigned $signed

& $SignTool sign `
    /f $PfxPath `
    /fd SHA256 `
    /tr http://timestamp.digicert.com `
    /td sha256 `
    /d "WIZnet S2E Config Tool" `
    /du "https://github.com/Wiznet/WIZnet-S2E-Tool-GUI" `
    $signed


if ($LASTEXITCODE -eq 0) {
    Write-Output "Signed build: $signed"
} else {
    Write-Error "Signing failed (exit $LASTEXITCODE)"
    Remove-Item $signed -ErrorAction SilentlyContinue
    exit 1
}
