# WIZnet S2E Configuration Tool - 실행 가이드

## 📋 목차
1. [실행 환경 분석](#실행-환경-분석)
2. [uv를 이용한 실행 방법](#uv를-이용한-실행-방법)
3. [기존 Poetry 방식 (참고)](#기존-poetry-방식-참고)
4. [문제 해결](#문제-해결)

---

## 🔍 실행 환경 분석

### 기존 환경
- **Python 버전**: Python 3.9 이상
- **패키지 관리**: Poetry (기존)
- **의존성**:
  - PyQt5 (GUI 프레임워크)
  - ifaddr (네트워크 인터페이스)
  - requests (HTTP 통신)
- **빌드 도구**: PyInstaller (Windows 실행 파일 생성)

### 현재 시스템
- Python 3.12.6 설치됨
- uv 0.7.19 설치됨 ✅

---

## 🚀 uv를 이용한 실행 방법

### 1. uv가 설치되어 있는지 확인

```bash
uv --version
```

**설치되지 않았다면**:
```bash
pip install uv
```

또는 공식 설치 방법:
- Windows: https://docs.astral.sh/uv/getting-started/installation/

### 2. 가상 환경 생성 (선택 사항, 권장)

```bash
# 가상 환경 생성
uv venv

# 가상 환경 활성화 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 가상 환경 활성화 (Windows CMD)
.venv\Scripts\activate.bat
```

### 3. 의존성 설치

```bash
# requirements.txt 기반 설치
uv pip install -r requirements.txt
```

또는 pyproject.toml이 있다면:
```bash
uv pip install -e .
```

### 4. 애플리케이션 실행

#### 방법 A: 자동 스크립트 사용 (권장)

**PowerShell**:
```powershell
.\run.ps1
```

**CMD**:
```cmd
.\run.bat
```

#### 방법 B: 수동 실행

```bash
# 가상 환경 없이
python main_gui.py

# 가상 환경 활성화 후
python main_gui.py

# uv run 사용
uv run python main_gui.py
```

### 5. 실행 파일 빌드 (Windows .exe)

**PyInstaller로 빌드** (권장):
```powershell
.\build_with_uv.ps1
```

빌드 완료 후 실행 파일 위치:
```
dist\wizconfig_s2e_tool_1.5.8.1.exe
```

---

## 📦 기존 Poetry 방식 (참고)

### Poetry 설치
```bash
pip install poetry
```

### 의존성 설치
```bash
poetry install
```

### 실행
```bash
poetry run python main_gui.py
```

### 빌드
```bash
poetry run pyinstaller [옵션] main_gui.py
```

---

## 🔧 문제 해결

### 1. Python 버전 문제

**증상**: `Python 3.9 이상이 필요합니다` 에러

**해결**:
```bash
# 현재 Python 버전 확인
python --version

# Python 3.9 이상 설치 필요
```

### 2. PyQt5 설치 실패

**증상**: `ERROR: Could not build wheels for PyQt5`

**해결**:
```bash
# Visual C++ Build Tools 설치 필요 (Windows)
# 또는 미리 빌드된 wheel 사용
uv pip install PyQt5 --only-binary :all:
```

### 3. ifaddr 모듈 없음

**증상**: `ModuleNotFoundError: No module named 'ifaddr'`

**해결**:
```bash
uv pip install ifaddr
```

### 4. 가상 환경 활성화 안됨 (PowerShell)

**증상**: `cannot be loaded because running scripts is disabled`

**해결**:
```powershell
# PowerShell 실행 정책 변경 (관리자 권한)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 5. 새 아키텍처 초기화 실패

**증상**: 로그에 `[New Architecture] Init failed` 표시

**원인**: config 파일 경로 문제

**해결**:
```bash
# config 디렉토리 구조 확인
dir config\devices\

# devices_sample.json이 있는지 확인
```

**예상 로그 (정상)**:
```
[INFO] Start configuration tool (version: V1.5.8.1)
[INFO] [New Architecture] Loaded device registry: 4 models
[INFO] [New Architecture] QtAdapter initialized
[INFO] [New Architecture] Available models: WIZ750SR, W55RP20-S2E, W55RP20-S2E-2CH, IP20
```

### 6. uv 명령어 없음

**증상**: `'uv' is not recognized`

**해결**:
```bash
# uv 설치
pip install uv

# 또는 공식 설치 방법 사용
# https://docs.astral.sh/uv/
```

---

## 📊 실행 환경 비교

| 방식 | 속도 | 설치 | 호환성 |
|------|------|------|--------|
| **uv (권장)** | ⚡ 매우 빠름 | 간단 | Python 3.9+ |
| Poetry | 보통 | 보통 | Python 3.7+ |
| pip + venv | 느림 | 간단 | 모든 버전 |

---

## 🎯 권장 실행 방법 (요약)

### 개발 환경
```bash
# 1. 가상 환경 생성
uv venv

# 2. 가상 환경 활성화
.venv\Scripts\Activate.ps1  # PowerShell

# 3. 의존성 설치
uv pip install -r requirements.txt

# 4. 실행
python main_gui.py
```

### 빠른 테스트
```bash
# 자동 스크립트 사용
.\run.ps1  # PowerShell
```

### 배포용 빌드
```bash
# PyInstaller 빌드
.\build_with_uv.ps1
```

---

## 📚 관련 문서

- [uv 공식 문서](https://docs.astral.sh/uv/)
- [PyQt5 문서](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [PyInstaller 문서](https://pyinstaller.org/)
- [새 아키텍처 가이드](FINAL_SUMMARY.md)
- [테스트 가이드](TESTING_GUIDE.md)

---

**작성일**: 2026-01-08
**버전**: v1.5.8.1
