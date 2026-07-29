# 릴리스 절차 가이드

> 새 버전을 빌드·서명하고 GitHub Release로 배포하는 전체 과정을 설명합니다.  
> 빌드 환경이 아직 없다면 [SETUP_DEV-ko.md](SETUP_DEV-ko.md)를 먼저 진행하세요.

---

## 전체 흐름 한눈에 보기

```
1. 코드 수정 → 커밋
2. version 파일 갱신 → 커밋
3. build.ps1 실행 → EXE 빌드 + 코드 서명
4. master 브랜치로 머지
5. git 태그 생성 (v1.x.x)
6. GitHub Release 생성 + 서명된 EXE 첨부
```

---

## 1. 버전 규칙

버전은 `version` 파일 한 곳에서 관리합니다. 형식은 **4단계 숫자**입니다.

```
1.6.2.6
│ │ │ └─ 빌드/핫픽스 번호
│ │ └─── 패치
│ └───── 마이너 (기능 추가)
└─────── 메이저
```

### 접미사 규칙

| 상황 | 버전 표기 | 예시 |
|------|----------|------|
| 브랜치에서 작업 중 | `-dev` 접미사 | `1.6.3.1-dev` |
| 특정 사이트·고객용 커스텀 빌드 | `-<사이트명>` 접미사 | `1.6.3.1-ACME` |
| master 머지 / 정식 릴리스 | 접미사 제거 | `1.6.3.1` |

> **중요:** 브랜치 개발 중에는 `-dev`를 붙여 정식 릴리스 빌드와 구분하고, master에 머지하거나 릴리스할 때 제거합니다. 특정 사이트·고객 전용 빌드는 `-dev` 대신 사이트명을 접미사로 둘 수 있습니다.

> **⚠️ 표시 길이 제한 (40자):** 버전 문자열은 접미사 포함 **40자를 넘기지 마세요.** 툴 UI에서 장치의 Type/Version을 보여주는 표시 필드(`dev_type`, `fw_version`)가 `maxLength` **40자**로 제한되어 있습니다(읽기 전용, `gui/wizconfig_gui.ui`). 펌웨어·장치 쪽은 더 긴 문자열을 보낼 수 있어도 **받아서 표시하는 쪽이 40자에서 잘립니다.** 사이트명 접미사를 길게 붙일 때 특히 주의하세요.

### 버전 변경 시 순서

버전을 바꾸면 **즉시 커밋하고 빌드**합니다. 순서를 지키세요.

```
코드 수정 → version 파일 변경 → 커밋 → build.ps1
```

---

## 2. EXE 빌드 + 코드 서명

### 기본 빌드 (서명 포함)

```powershell
.\build.ps1
```

`dist\` 폴더에 두 개의 파일이 생성됩니다.

| 파일 | 용도 |
|------|------|
| `wizconfig_s2e_tool_<버전>.exe` | 미서명본 |
| `wizconfig_s2e_tool_<버전>_signed.exe` | **서명본 — 릴리스에 첨부할 파일** |

### 서명 없이 빌드만

코드 서명 인증서가 없는 경우(외부 기여자 등)는 미서명으로 빌드합니다.

```powershell
.\build.ps1 -NoSign
```

> **⚠️ pyinstaller를 직접 호출하지 마세요.** `build.ps1`이 버전 읽기, 구버전 spec 정리, `--add-data` 리소스 포함, 서명까지 모두 처리합니다.

---

## 3. 코드 서명 상세

백신 오탐을 줄이기 위해 EXE에 코드 서명을 적용합니다. `build.ps1`이 자동으로 처리하므로 별도 명령은 필요 없습니다.

### 서명에 사용되는 것

| 항목 | 값 |
|------|-----|
| 인증서 (PFX) | `C:\Users\user\wiznet_codesign.pfx` (자체 서명, 비밀번호 없음, 유효기간 2126년) |
| 서명 도구 | `signtool.exe` (Windows SDK 포함) |
| 타임스탬프 서버 | `http://timestamp.digicert.com` |
| 해시 알고리즘 | SHA256 |

### 다른 인증서로 서명하기

PFX 경로를 파라미터로 넘길 수 있습니다.

```powershell
.\build.ps1 -PfxPath "C:\path\to\your.pfx"
```

> **참고:** 자체 서명 인증서는 "신뢰할 수 있는 게시자"로 등록되지 않아 Windows SmartScreen 경고가 나올 수 있습니다. 이는 정식 CA 인증서를 구매해야 완전히 해결됩니다. 백신 오탐 완화 목적으로는 자체 서명으로 충분합니다.

### 서명 인증서(키) 직접 생성

공용 인증서가 없거나 새로 만들어야 할 때, Windows PowerShell에서 자체 서명 코드서명 인증서를 생성할 수 있습니다.
(과거 문서의 `MakeCert`/`Pvk2Pfx`는 더 이상 권장되지 않으며, 아래 `New-SelfSignedCertificate` 방식이 현재 표준입니다.)

```powershell
# 1) 자체 서명 코드서명 인증서 생성 (현재 사용자 인증서 저장소에 만들어짐)
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=WIZnet Software, O=WIZnet, C=KR" `
    -KeyAlgorithm RSA -KeyLength 2048 `
    -NotAfter (Get-Date).AddYears(100) `
    -CertStoreLocation "Cert:\CurrentUser\My"

# 2) PFX 파일로 내보내기 (무암호 예시 — 빈 비밀번호)
Export-PfxCertificate `
    -Cert $cert `
    -FilePath "C:\Users\user\wiznet_codesign.pfx" `
    -Password (New-Object System.Security.SecureString)
```

> 기존 인증서(`C:\Users\user\wiznet_codesign.pfx`)는 **무암호**로 만들어져 있어 `build.ps1`이 비밀번호 없이 서명합니다. 새로 만들 때도 동일하게 무암호로 두는 것이 build.ps1과 호환됩니다. 암호를 설정했다면 build.ps1 서명 단계에 `/p <암호>`를 추가해야 합니다.

### 공식 서명 vs 외부 서명

현재 빌드는 **누가 서명했는지를 파일명·산출물로 자동 구별하지 않습니다.** 어떤 인증서로 서명하든 출력은 `..._signed.exe`로 동일합니다.

| 구분 | 서명 인증서 주체(CN) |
|------|---------------------|
| WIZnet 공식 빌드 | `CN=WIZnet Software` |
| 외부 기여자 빌드 | 기여자 본인 인증서의 CN |

차이는 EXE 파일 속성 → **디지털 서명** 탭의 서명자 이름에만 나타납니다. **배포용 공식 릴리스는 반드시 WIZnet 인증서로 서명**해야 합니다.

---

## 4. 브랜치 전략

```
dev/fix-*  →  dev/feat-*  →  develop  →  master
```

- **머지는 일반 머지(`--no-ff`)** 를 사용합니다. squash를 쓰면 브랜치 연결이 그래프에서 사라집니다.
- 정식 릴리스는 항상 **master 브랜치** 기준입니다.

---

## 5. GitHub Release 생성

배포 페이지: https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/releases

### 순서

1. **업데이트 코드 커밋 & 푸시** (master 기준)
2. **EXE 빌드 + 서명** (`.\build.ps1`)
3. **태그 생성** — `v1.x.x` 형식 (소문자 `v`)
   ```powershell
   git tag v1.6.3
   git push origin v1.6.3
   ```
4. **GitHub에서 Release 작성**
   - Target: `master` 브랜치
   - Tag: 위에서 만든 `v1.x.x`
   - Description: 변경 사항 작성 (기존 릴리스의 Markdown 형식 참조)
   - **서명된 EXE(`_signed.exe`)를 첨부 파일로 업로드**

> Source code(zip/tar)는 선택된 태그 기준으로 자동 포함됩니다. 서명한 EXE만 수동으로 첨부하면 됩니다.

### Discussion 옵션

Release 생성 시 Discussion 연동은 선택입니다. 이슈·히스토리를 남기려면 체크하는 것이 좋습니다.

---

## 6. 릴리스 후 정리

- `CHANGELOG.md`에 이번 릴리스 변경 사항 정리
- 다음 개발 시작 시 `version`에 `-dev` 접미사를 다시 붙여 작업 시작

---

## 체크리스트

릴리스 직전 빠르게 점검하세요.

- [ ] `version` 파일에서 `-dev` 접미사 제거됨
- [ ] `build.ps1` 실행 → `_signed.exe` 정상 생성
- [ ] master 브랜치로 머지 완료 (`--no-ff`)
- [ ] `v1.x.x` 태그 생성 및 푸시
- [ ] GitHub Release에 **서명본** EXE 첨부
- [ ] CHANGELOG.md 갱신

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | [개발자 가이드 (시작 순서)](DEV_GUIDE-ko.md) |
| 1 | [환경 세팅 & 실행](SETUP_DEV-ko.md) |
| 2 | [코드 구조](ARCHITECTURE-ko.md) |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | [새 장치 추가](ADD_DEVICE-ko.md) |
| 5 | [테스트](TESTING-ko.md) |
| 6 | **빌드 & 배포 — 현재 문서** |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
