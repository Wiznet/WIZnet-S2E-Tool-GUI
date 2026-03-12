# WIZnet S2E Tool GUI — 개발 환경 설정 가이드 (Windows 11)

> 이 문서는 **디버깅 실행 + 빌드(PyInstaller 포함)** 환경을 처음부터 세팅하는 방법을 담고 있습니다.
> 모든 명령어는 **PowerShell** (관리자 권한 불필요) 기준입니다.

---

## 1. 사전 확인

PowerShell을 열고 Python 버전을 확인합니다.

```powershell
python --version
```

`Python 3.12.x` 가 출력되면 OK. 없으면 아래 링크에서 설치합니다.
https://www.python.org/downloads/release/python-3129/
(설치 시 **"Add python.exe to PATH"** 체크 필수)

---

## 2. uv 설치

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 **터미널을 완전히 닫고 새로 열기** (PATH 적용).

```powershell
uv --version
```

`uv x.x.x` 가 출력되면 OK.

---

## 3. Git 설치 (없는 경우만)

```powershell
winget install --id Git.Git -e --source winget
```

설치 후 터미널을 다시 열고 확인합니다.

```powershell
git --version
```

---

## 4. 프로젝트 클론

```powershell
git clone https://github.com/Wiznet/WIZnet-S2E-Tool-GUI.git
cd WIZnet-S2E-Tool-GUI
git checkout dev/feat-search-methods
```

> **Git 없이 ZIP으로 받는 경우**
> https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/archive/refs/heads/dev/feat-search-methods.zip
> 다운로드 후 압축 해제 → 해당 폴더로 이동

---

## 5. 가상 환경 생성 및 패키지 설치

```powershell
uv venv --python 3.12
uv pip install -r requirements.txt
```

> `uv venv` 실행 시 Python 3.12가 자동으로 감지되거나 없으면 자동 다운로드됩니다.

설치 확인:

```powershell
uv run python -c "import PyQt5; import yaml; print('OK')"
```

`OK` 가 출력되면 완료.

---

## 6. PyInstaller 설치 (custom bootloader 직접 컴파일)

> **`pip install pyinstaller` 사용 금지** — 이 프로젝트는 직접 컴파일한 custom bootloader를 사용합니다.

### 6-1. 사전 준비: Visual C++ Build Tools 설치

https://visualstudio.microsoft.com/visual-cpp-build-tools/
→ "C++ build tools" 워크로드 선택 → 설치

설치 완료 후 PowerShell을 **새로 열고** 확인:

```powershell
cl
```

`Microsoft (R) C/C++ Optimizing Compiler` 로 시작하는 메시지가 나오면 OK.
(안 되면 "x64 Native Tools Command Prompt for VS" 에서 PowerShell을 열 것)

### 6-2. PyInstaller 소스 클론

**WIZnet-S2E-Tool-GUI 폴더 안에서** 실행합니다 (uv가 .venv를 자동 감지).

```powershell
git clone --branch v6.17.0 https://github.com/pyinstaller/pyinstaller.git _pyinstaller_src
```

### 6-3. bootloader 컴파일

```powershell
cd _pyinstaller_src\bootloader
uv run python .\waf all
cd ..\..
```

완료되면 `_pyinstaller_src\PyInstaller\bootloader\Windows-64bit-intel\` 에 `run.exe`, `runw.exe` 등이 생성됩니다.

### 6-4. 컴파일된 bootloader 포함 설치

```powershell
uv pip install .\_pyinstaller_src
```

### 6-5. 소스 삭제 (선택)

```powershell
Remove-Item -Recurse -Force _pyinstaller_src
```

### 6-6. 설치 확인

```powershell
uv run python -c "import PyInstaller; print(PyInstaller.__version__)"
```

`6.17.0` 이 출력되면 완료.

---

## 7. 디버깅 모드로 실행

```powershell
uv run python main_gui.py
```

실행 중 로그는 아래 경로에 자동 저장됩니다.

```
C:\Users\<사용자명>\.wizconfig\wizconfig.log
```

로그 파일 실시간 확인 (별도 PowerShell 창에서):

```powershell
Get-Content "$env:USERPROFILE\.wizconfig\wizconfig.log" -Wait -Tail 50
```

---

## 8. PyInstaller로 EXE 빌드

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

빌드가 완료되면 `dist\` 폴더 안에 EXE가 생성됩니다.

```
dist\wizconfig_s2e_tool_1.5.8.3.16.exe
```

---

## 9. 자주 발생하는 오류

| 증상 | 원인 | 해결 |
|------|------|------|
| `uv : 이 시스템에서 스크립트를 실행할 수 없습니다` | 실행 정책 차단 | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError: No module named 'PyQt5'` | venv 미활성화 | `uv run python main_gui.py` 로 실행 (직접 `python` 아님) |
| `git: command not found` | Git 미설치 | 3번 단계 참고 |
| 빌드 후 EXE 실행 시 바로 종료 | 콘솔 창 없어서 오류 확인 불가 | `uv run python main_gui.py` 로 터미널에서 직접 실행해서 로그 확인 |
