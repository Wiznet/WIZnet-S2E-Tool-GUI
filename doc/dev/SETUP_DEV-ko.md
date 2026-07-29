# WIZnet S2E Tool GUI — 개발 환경 설정 가이드

> **이 문서 하나만 보고 따라하면 됩니다.**  
> 모든 명령어는 **PowerShell** (관리자 권한 불필요) 기준입니다.

| 파트 | 내용 | 소요시간 |
|------|------|--------|
| **파트 A** | 소스 수정 후 직접 실행 | 약 20분 |
| **파트 B** | EXE 파일 빌드 환경 추가 | 약 60분 추가 |

소스를 수정하고 바로 실행해 보는 것이 목적이라면 **파트 A만으로 충분합니다.**

---

## 파트 A — 소스 수정 및 실행 환경

### A-1. Python 3.12 설치 확인

PowerShell을 열고 아래 명령을 실행합니다.

```powershell
python --version
```

**✅ 성공:** `Python 3.12.x` 가 출력되면 [A-2](#a-2-uv-설치)로 건너뜁니다.

**❌ 없거나 다른 버전인 경우:**

1. https://www.python.org/downloads/release/python-3129/ 접속
2. 페이지 하단 "Files" 목록에서 **Windows installer (64-bit)** 클릭하여 다운로드
3. 설치 프로그램 실행 — 첫 화면에서 **"Add python.exe to PATH"를 반드시 체크**한 뒤 Install Now

설치 완료 후 터미널을 **닫고 새로 열어서** 다시 확인합니다.

```powershell
python --version
```

**✅ 성공:** `Python 3.12.x` 출력

---

### A-2. uv 설치

`uv`는 Python 패키지·가상 환경을 빠르게 관리하는 도구입니다. 아래 명령을 그대로 붙여넣습니다.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 **터미널을 완전히 닫고 새로 열기** (PATH가 적용되어야 합니다).

```powershell
uv --version
```

**✅ 성공:** `uv 0.x.x` 형태로 출력

> **❌ `uv : 이 시스템에서 스크립트를 실행할 수 없습니다` 오류가 나는 경우:**  
> 아래 명령 실행 후 터미널을 닫고 새로 열어서 재시도합니다.
> ```powershell
> Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

### A-3. Git 설치 확인

```powershell
git --version
```

**✅ 이미 있음:** `git version x.x.x` 가 출력되면 [A-4](#a-4-소스-코드-받기)로 건너뜁니다.

**❌ 없는 경우:**

```powershell
winget install --id Git.Git -e --source winget
```

설치 후 터미널을 닫고 새로 열어서 확인합니다.

```powershell
git --version
```

**✅ 성공:** `git version x.x.x` 출력

---

### A-4. 소스 코드 받기

```powershell
git clone https://github.com/Wiznet/WIZnet-S2E-Tool-GUI.git
cd WIZnet-S2E-Tool-GUI
```

> **Git 없이 ZIP으로 받는 경우**  
> https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/archive/refs/heads/master.zip  
> 다운로드 후 압축 해제 → 터미널에서 해당 폴더 안으로 이동

---

### A-5. 패키지 설치

아래 두 명령을 순서대로 실행합니다.

```powershell
uv venv --python 3.12
uv pip install -r requirements.txt
```

설치 완료 후 정상 여부를 확인합니다.

```powershell
uv run python -c "import PyQt5; import yaml; print('OK')"
```

**✅ 성공:** `OK` 출력

---

### A-6. 실행 확인

```powershell
uv run python main_gui.py
```

**✅ 성공:** GUI 창이 열리면 파트 A 완료입니다.

소스를 수정한 뒤에도 같은 명령(`uv run python main_gui.py`)으로 실행하면 수정 내용이 즉시 반영됩니다.

> **실행 로그 확인**  
> 실행 중 로그는 아래 경로에 자동 저장됩니다.
> ```
> C:\Users\<사용자명>\.wizconfig\wizconfig.log
> ```
> 별도 PowerShell 창에서 실시간으로 볼 수도 있습니다.
> ```powershell
> Get-Content "$env:USERPROFILE\.wizconfig\wizconfig.log" -Wait -Tail 50
> ```

---

## 파트 B — EXE 빌드 환경 추가

> **⚠️ `pip install pyinstaller`를 쓰지 않는 이유**  
> 표준 PyInstaller로 만든 EXE는 바이러스 백신이 악성코드로 오탐하는 문제가 있습니다.  
> 이 프로젝트는 직접 컴파일한 bootloader를 사용하여 이 문제를 방지합니다.

### B-1. Visual C++ Build Tools 설치

bootloader 컴파일에 C++ 컴파일러가 필요합니다.

1. https://visualstudio.microsoft.com/visual-cpp-build-tools/ 접속
2. **"Build Tools 다운로드"** 클릭 → 설치 프로그램 실행
3. **"C++ 빌드 도구"** 워크로드 선택 → 오른쪽 상세 목록은 기본값 유지 → **설치** 클릭
4. 설치 완료 후 터미널을 **완전히 닫고 새로 열기**

```powershell
cl
```

**✅ 성공:** `Microsoft (R) C/C++ Optimizing Compiler Version ...` 으로 시작하는 메시지 출력

> **❌ `cl : 이 용어는 cmdlet...` 오류가 나는 경우:**  
> 시작 메뉴에서 **"x64 Native Tools Command Prompt for VS 2022"** 를 검색해서 실행합니다.  
> 그 창 안에서 `powershell` 을 입력하고 Enter.  
> 이후 B-2부터의 **모든 명령을 그 PowerShell 창에서** 실행합니다.

---

### B-2. PyInstaller 소스 받기

**WIZnet-S2E-Tool-GUI 폴더 안**에서 실행합니다. (`cd WIZnet-S2E-Tool-GUI` 가 되어 있는 상태)

```powershell
git clone --branch v6.17.0 https://github.com/pyinstaller/pyinstaller.git _pyinstaller_src
```

**✅ 성공:** `_pyinstaller_src` 폴더가 생성됨

---

### B-3. bootloader 컴파일

```powershell
cd _pyinstaller_src\bootloader
uv run python .\waf all
cd ..\..
```

완료까지 수 분 소요됩니다. 완료 후 파일 생성 여부를 확인합니다.

```powershell
Test-Path "_pyinstaller_src\PyInstaller\bootloader\Windows-64bit-intel\run.exe"
```

**✅ 성공:** `True` 출력

---

### B-4. PyInstaller 설치

```powershell
uv pip install .\_pyinstaller_src
```

설치 확인:

```powershell
uv run python -c "import PyInstaller; print(PyInstaller.__version__)"
```

**✅ 성공:** `6.17.0` 출력

---

### B-5. 소스 정리 (선택)

더 이상 필요 없으므로 삭제해도 됩니다.

```powershell
Remove-Item -Recurse -Force _pyinstaller_src
```

---

### B-6. EXE 빌드

```powershell
.\build.ps1
```

빌드 완료 후 `dist\` 폴더 안에 EXE 파일이 생성됩니다.

```
dist\wizconfig_s2e_tool_<버전>.exe
```

---

## 오류 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `uv : 이 시스템에서 스크립트를 실행할 수 없습니다` | 실행 정책 차단 | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` 실행 후 터미널 재시작 |
| `ModuleNotFoundError: No module named 'PyQt5'` | venv 미활성화 | `python` 대신 반드시 `uv run python main_gui.py` 로 실행 |
| `git: command not found` | Git 미설치 | A-3 단계 참고 |
| `cl : 이 용어는 cmdlet...` | Visual C++ 경로 미적용 | "x64 Native Tools Command Prompt for VS 2022" 에서 PowerShell 실행 후 재시도 |
| 백신이 빌드된 EXE를 삭제·격리함 | 표준 PyInstaller bootloader 사용 | B-3 단계(bootloader 컴파일) 누락 여부 확인 |
| 빌드 후 EXE 실행 시 바로 종료 | 오류 메시지 확인 불가 | `uv run python main_gui.py` 로 터미널에서 직접 실행하여 로그 확인 |

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | [개발자 가이드 (시작 순서)](DEV_GUIDE-ko.md) |
| 1 | **환경 세팅 & 실행 — 현재 문서** |
| 2 | [코드 구조](ARCHITECTURE-ko.md) |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | [새 장치 추가](ADD_DEVICE-ko.md) |
| 5 | [테스트](TESTING-ko.md) |
| 6 | [빌드 & 배포](RELEASE-ko.md) |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
