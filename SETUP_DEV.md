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
> `requirements.txt` 에 PyInstaller 포함 모든 패키지가 버전 고정으로 명시되어 있습니다.

설치 확인:

```powershell
uv run python -c "import PyQt5; import PyInstaller; print('OK')"
```

`OK` 가 출력되면 완료.

---

## 6. 디버깅 모드로 실행

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

## 7. PyInstaller로 EXE 빌드 (bootloader 포함)

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

빌드가 완료되면 `dist\` 폴더 안에 EXE가 생성됩니다.

```
dist\wizconfig_s2e_tool_1.5.8.3.16.exe
```

> **bootloader 직접 컴파일이 필요한 경우** (백신 오탐 회피 목적)
> 아래 명령어로 소스에서 빌드합니다. Visual C++ Build Tools가 필요합니다.
> https://visualstudio.microsoft.com/visual-cpp-build-tools/ 설치 후:
>
> ```powershell
> uv pip download pyinstaller --no-deps -d pyinst_src
> # 다운로드된 .whl 압축 해제 → PyInstaller\bootloader\ 폴더에서
> uv run python ./waf all
> uv pip install pyinstaller --no-binary pyinstaller
> ```

---

## 8. 자주 발생하는 오류

| 증상 | 원인 | 해결 |
|------|------|------|
| `uv : 이 시스템에서 스크립트를 실행할 수 없습니다` | 실행 정책 차단 | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError: No module named 'PyQt5'` | venv 미활성화 | `uv run python main_gui.py` 로 실행 (직접 `python` 아님) |
| `git: command not found` | Git 미설치 | 3번 단계 참고 |
| 빌드 후 EXE 실행 시 바로 종료 | 콘솔 창 없어서 오류 확인 불가 | `uv run python main_gui.py` 로 터미널에서 직접 실행해서 로그 확인 |
