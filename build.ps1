# build.ps1
# 사용법:
#   .\build.ps1                → 빌드 + 서명 둘 다 생성 (기본)
#   .\build.ps1 -NoSign        → 빌드만 (서명 건너뜀)
#   .\build.ps1 -PfxPath "C:\my.pfx"  → 커스텀 PFX로 서명
#
# ── 빌드 환경 경로 (검증: 2026-06-15) ──────────────────────────────────────
#   이 PC는 표준 Windows SDK/VS 미설치. 대신 portable MSVC+SDK 묶음을 사용.
#   루트:  D:\user\src\github\WIZnet-S2E-Tool-GUI\msvc\
#     · cl.exe / link.exe : msvc\VC\Tools\MSVC\14.40.33807\bin\Hostx64\x64
#     · MSVC include/lib   : msvc\VC\Tools\MSVC\14.40.33807\{include, lib\x64}
#     · SDK  include/lib   : msvc\Windows Kits\10\{Include, Lib}\10.0.26100.0
#     · signtool.exe       : msvc\Windows Kits\bin\10.0.28000.0\x64  (← 아래 $SignTool)
#   PyInstaller : 표준 wheel 금지. custom bootloader 컴파일 후 .venv에 설치.
#                 (절차: doc/dev/SETUP_DEV-ko.md 파트 B — 위 MSVC 경로로 INCLUDE/LIB 구성)

param(
    [switch]$NoSign,
    [string]$PfxPath        = "C:\Users\user\wiznet_codesign.pfx",
    # signtool: portable Windows SDK BuildTools(10.0.28000.0) 내 x64 빌드
    [string]$SignTool       = "D:\user\src\github\WIZnet-S2E-Tool-GUI\msvc\Windows Kits\bin\10.0.28000.0\x64\signtool.exe"
)

$_version = Get-Content .\version -Raw
$_version = $_version.Trim()
$target_bin_name = "wizconfig_s2e_tool_$_version"
Write-Output "$target_bin_name"

# 구버전 .spec 파일 정리 (현재 버전 제외)
Get-ChildItem .\*.spec | Where-Object { $_.Name -ne "$target_bin_name.spec" } | Remove-Item -Force
Write-Output "Cleaned up old .spec files"

# Run build via uv to use the .venv environment
# --noupx: UPX 압축 명시적으로 끔 — Defender 등 백신이 UPX 압축 실행파일을
#          악성코드 패킹 패턴으로 오탐하는 사례가 많아 기본값으로 비활성화.
#          (2026-07-15: upx.exe를 PATH에 설치한 뒤 실측 — 켰을 때 32.7MB, 껐을 때 40.7MB.
#           용량 20% 절감보다 오탐 회피를 우선)
uv run python -m PyInstaller -w -F -n $target_bin_name --icon ".\\gui\\icon.ico" --hidden-import jsonschema --noupx --add-data ".\\specs\\*;.\\specs" --add-data ".\\gui\\*;.\\gui" --add-data ".\\version;.\\" --add-data ".\\config\\device_search_timing.default.yaml;.\\config" --add-data ".\\config\\fw_image_defaults.yaml;.\\config" --add-data ".\\config\\*.json;.\\config" .\main_gui.py

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
# signtool: 기본 경로에 없으면 Everything(find_build_env.py)으로 자동 탐색
if (-not (Test-Path $SignTool)) {
    Write-Output "signtool not at default path; discovering via Everything ..."
    $py = "$PSScriptRoot\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }
    try {
        $be = & $py "$PSScriptRoot\find_build_env.py" | ConvertFrom-Json
        if ($be.ok -and $be.SIGNTOOL -and (Test-Path $be.SIGNTOOL)) {
            $SignTool = $be.SIGNTOOL
            Write-Output "  found: $SignTool"
        }
    } catch { }
}
if (-not (Test-Path $SignTool)) {
    Write-Error "signtool.exe not found: $SignTool (Everything auto-discovery also failed)"
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
