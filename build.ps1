# build.ps1
# 사용법:
#   .\build.ps1              → 빌드만 (서명 없음)
#   .\build.ps1 -Sign        → 빌드 + 자체 서명 (파일명에 _signed 추가)
#   .\build.ps1 -Sign -PfxPath "C:\my.pfx" -PfxPassword "pw"  → 커스텀 PFX

param(
    [switch]$Sign,
    [string]$PfxPath        = "C:\Users\user\wiznet_codesign.pfx",
    [SecureString]$PfxPassword,
    [string]$SignTool       = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
)

$_version = Get-Content .\version -Raw
$_version = $_version.Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Output "$target_bin_name"

# Run build via uv to use the .venv environment
uv run python -m PyInstaller -w -F -n $target_bin_name --add-data ".\\gui\\*;.\\gui" --add-data ".\\version;.\\" --add-data ".\\config\\*.yaml;.\\config" .\main_gui.py

if (-not $Sign) {
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

# PfxPassword 미입력 시 대화형 입력
if (-not $PfxPassword) {
    $PfxPassword = Read-Host "PFX password" -AsSecureString
}

# SecureString → 평문 (signtool /p 인자용, 호출 후 즉시 해제)
$bstr      = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword)
$plainPwd  = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# 서명용 복사본 생성
Copy-Item $unsigned $signed

& $SignTool sign `
    /f $PfxPath `
    /p $plainPwd `
    /fd SHA256 `
    /tr http://timestamp.digicert.com `
    /td sha256 `
    /d "WIZnet S2E Config Tool" `
    /du "https://github.com/Wiznet/WIZnet-S2E-Tool-GUI" `
    $signed

$plainPwd = $null  # 평문 비밀번호 즉시 해제

if ($LASTEXITCODE -eq 0) {
    Write-Output "Signed build: $signed"
} else {
    Write-Error "Signing failed (exit $LASTEXITCODE)"
    Remove-Item $signed -ErrorAction SilentlyContinue
    exit 1
}
