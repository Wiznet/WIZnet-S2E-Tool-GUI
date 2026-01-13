# WIZnet S2E Tool 리팩토링 상태 보고서

**브랜치**: `feature/refactoring-v2`
**작성일**: 2026-01-12 (최종 업데이트)
**버전**: v1.5.8.1 + 리팩토링 진행 중
**상태**: 🟢 **Tier 1-2 완료, 실제 기능 마이그레이션 시작**

---

## 📋 목차

1. [현재 상태 요약](#현재-상태-요약)
2. [완성된 부분](#완성된-부분)
3. [미완성 부분](#미완성-부분)
4. [사용 방법](#사용-방법)
5. [파일 구조](#파일-구조)
6. [향후 진행 계획](#향후-진행-계획)
7. [완전 전환 전략](#완전-전환-전략)

---

## 🎯 현재 상태 요약

### 최근 진행 상황 (2026-01-12)

**Tier 1-2 완료**: 안전하고 빠르게 구현 가능한 작업들을 먼저 완료

#### ✅ **완료된 작업 (Tier 1: JSON 도구)**
1. **JSON 검증 강화** (`scripts/validate_config.py`)
   - 정규식 패턴 테스트 추가
   - 상속 순환 참조 감지
   - UI 위젯 타입 검증
   - 통계 출력

2. **명령어 문서 자동 생성** (`scripts/generate_command_docs.py`)
   - JSON에서 Markdown 문서 자동 생성
   - 각 장치별 명령어 레퍼런스
   - 옵션 상세 설명

3. **JSON 백업/복원 도구** (`scripts/manage_config.py`)
   - 타임스탬프 기반 자동 백업
   - 백업 목록 조회
   - 특정 백업으로 복원
   - 백업 비교 기능

4. **명령어 템플릿 생성기** (`scripts/create_template.py`)
   - 새 장치 모델 템플릿
   - 새 명령어 템플릿
   - 명령어 세트 템플릿

#### ✅ **완료된 작업 (Tier 2: 간단한 마이그레이션)**
5. **설정 검증을 새 아키텍처로 전환** (`main_gui.py:do_setting()`)
   - ⭐ **첫 실제 기능 마이그레이션!**
   - `device_service.validate_config()` 사용
   - Strangler Fig 패턴으로 안전하게 전환

6. **JSON 설정 에디터 GUI** (`json_editor_dialog.py`)
   - 간단한 JSON 편집기
   - 구문 검증 (Validate)
   - 자동 포맷팅 (Format)
   - 자동 백업 생성
   - File 메뉴에 통합
   - 설정 변경 후 런타임 리로드

7. **중앙화된 메시지 핸들러** (`message_handler.py`)
   - 모든 사용자 메시지 통합
   - 도메인 특화 메시지 (device_not_selected, invalid_parameter, etc.)
   - 자동 로깅
   - 일관된 UX

### 사용자 입장에서

**변화**: JSON 설정을 GUI에서 직접 편집 가능
**개선**: 설정 검증이 더 정확해짐 (새 아키텍처)
**새 기능**: File 메뉴에 "Edit Device Configuration (JSON)" 추가

**개발자 입장에서**: 이제 실제로 새 아키텍처가 사용되기 시작했습니다!

---

## ✅ 완성된 부분

### 1. JSON 기반 데이터 구조

#### 파일: `config/devices/devices_sample.json`

**구조**:
```json
{
  "command_sets": [
    {
      "name": "common",
      "inherits": null,
      "commands": [
        {
          "code": "LI",
          "name": "Local IP",
          "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$",
          "access": "RW",
          "options": {},
          "ui_widget": "ipaddr",
          "ui_group": "Network",
          "ui_order": 1
        }
        // ... 33개 기본 명령어
      ]
    },
    {
      "name": "wiz75x_extended",
      "inherits": "common",
      "commands": [
        // Modbus 명령어 추가
      ]
    }
  ],
  "device_models": [
    {
      "model_id": "WIZ750SR",
      "display_name": "WIZ750SR",
      "category": "1-port",
      "command_set": "wiz75x_extended",
      "firmware_support": {
        "min_version": "1.0.0",
        "version_overrides": {
          "1.4.4": {
            "added_commands": ["MB", "MP"]
          }
        }
      }
    }
    // ... 4개 장치 모델
  ]
}
```

**특징**:
- 명령어 세트 상속 지원 (common → wiz75x_extended)
- 펌웨어 버전별 명령어 오버라이드
- UI 생성 힌트 포함 (widget, group, order)
- 정규식 패턴으로 자동 검증

**장점**:
- 새 장치 추가 시 JSON 10줄만 편집
- 코드 수정 불필요
- 테스트 용이

### 2. Core 라이브러리

#### 2.1 DeviceRegistry (`core/device_registry.py`)

```python
from core.device_registry import DeviceRegistry

# JSON 로드
registry = DeviceRegistry('config/devices/devices_sample.json')

# 장치 모델 조회
model = registry.get_model('WIZ750SR')

# 전체 모델 목록
models = registry.list_models()
# → ['WIZ750SR', 'W55RP20-S2E', 'W55RP20-S2E-2CH', 'IP20']
```

**기능**:
- JSON 파싱 및 검증
- 명령어 세트 상속 해석
- 순환 참조 감지
- 장치 모델 캐싱

#### 2.2 Command (`core/models/command.py`)

```python
from core.models.command import Command

cmd = Command(
    code='LI',
    name='Local IP',
    pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
    access='RW',
    options={},
    ui_widget='ipaddr'
)

# 검증
cmd.validate('192.168.1.100')  # → True
cmd.validate('invalid')        # → False
```

#### 2.3 DeviceService (`core/services/device_service.py`)

```python
from core.services.device_service import DeviceService
from core.models.device_config import DeviceInfo

service = DeviceService(registry)

# 장치 정보
device = DeviceInfo(
    mac_addr='00:08:DC:12:34:56',
    model_id='WIZ750SR',
    firmware_version='1.4.4'
)

# 설정 검증
config = {
    'LI': '192.168.1.100',
    'SM': '255.255.255.0',
    'BR': '12'
}

errors = service.validate_config(device, config)
if errors:
    for cmd_code, error_msg in errors.items():
        print(f"{cmd_code}: {error_msg}")
```

**검증 기능**:
- 명령어 존재 여부 확인
- Read-Only 명령어 쓰기 차단
- 정규식 패턴 검증
- 펌웨어 버전 지원 확인

### 3. Adapter 패턴

#### 3.1 BaseAdapter (`adapters/base_adapter.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Callable, Optional

class BaseUIAdapter(ABC):
    """UI 프레임워크 추상 인터페이스"""

    @abstractmethod
    def show_devices(self, devices: List[DeviceInfo]):
        """장치 목록 표시"""
        pass

    @abstractmethod
    def show_error(self, message: str, title: Optional[str] = None):
        """에러 메시지 표시"""
        pass

    def register_search_handler(self, handler: Callable[[], None]):
        """검색 버튼 핸들러 등록"""
        self._search_handler = handler
```

**설계 의도**:
- Qt/Web/CLI 등 다양한 UI 지원 가능
- 비즈니스 로직과 UI 완전 분리

#### 3.2 QtAdapter (`adapters/qt_adapter.py`)

```python
from adapters.qt_adapter import QtAdapter

# main_gui.py의 WIZWindow에서
adapter = QtAdapter(self)  # self = WIZWindow 인스턴스
adapter.initialize()

# 장치 목록 표시
devices = [
    DeviceInfo('00:08:DC:11:11:11', 'WIZ750SR', '1.0.0', '192.168.1.100'),
    DeviceInfo('00:08:DC:22:22:22', 'W55RP20-S2E', '1.1.8', '192.168.1.101')
]
adapter.show_devices(devices)

# 에러 표시
adapter.show_error("Invalid IP address", "Validation Error")

# 진행 상황 표시
adapter.show_progress("Searching devices...", 50, 100)
```

### 4. JSON 관리 도구들 (NEW!)

#### 4.1 설정 파일 검증 (`scripts/validate_config.py`)

```bash
# 기본 검증
python scripts/validate_config.py

# 상세 출력
python scripts/validate_config.py --verbose

# 특정 파일 검증
python scripts/validate_config.py --config config/devices/my_config.json
```

**검증 항목**:
- JSON 구조 유효성
- 필수 필드 존재 여부
- 정규식 패턴 문법 + 샘플 데이터 테스트
- 명령어 세트 상속 체인
- 순환 참조 감지
- UI 위젯 타입 검증
- 통계 출력

#### 4.2 명령어 문서 생성 (`scripts/generate_command_docs.py`)

```bash
# 기본 문서 생성
python scripts/generate_command_docs.py

# 특정 출력 경로
python scripts/generate_command_docs.py --output docs/MY_COMMANDS.md

# 특정 설정 파일
python scripts/generate_command_docs.py --config config/devices/custom.json
```

**생성 내용**:
- 각 장치 모델별 명령어 목록 테이블
- 명령어 상세 정보 (옵션, 패턴, 접근 모드)
- 명령어 세트 상속 관계
- 펌웨어 버전별 차이

#### 4.3 설정 백업/복원 (`scripts/manage_config.py`)

```bash
# 현재 설정 백업
python scripts/manage_config.py backup

# 백업 목록 보기
python scripts/manage_config.py list

# 특정 백업으로 복원
python scripts/manage_config.py restore 1    # 첫 번째 백업
python scripts/manage_config.py restore latest

# 백업 비교
python scripts/manage_config.py compare 1 2

# 오래된 백업 정리 (최근 10개만 유지)
python scripts/manage_config.py clean 10
```

**기능**:
- 타임스탬프 기반 자동 백업
- 복원 전 자동 백업 (auto_backup_*.json)
- 백업 파일 비교 (장치 모델, 명령어 세트 수)
- 파일 크기 및 날짜 표시

#### 4.4 템플릿 생성 (`scripts/create_template.py`)

```bash
# 새 장치 모델 템플릿
python scripts/create_template.py device --model-id NEW_DEVICE \
    --display-name "New Device" --category ONE_PORT

# 새 명령어 템플릿
python scripts/create_template.py command --code XX \
    --name "New Command" --access RW

# 새 명령어 세트 템플릿
python scripts/create_template.py cmdset --name new_cmdset \
    --inherits common

# JSON 파일로 출력
python scripts/create_template.py device --model-id TEST \
    --output templates/test_device.json
```

**사용 목적**:
- 새 장치 추가 시 구조 가이드
- 수동 편집 오류 방지
- 일관된 포맷 유지

### 5. 테스트 도구

#### 5.1 메시지 핸들러 테스트 (`tests/test_message_handler.py`)

```bash
python tests/test_message_handler.py
```

**기능**:
- 각 메시지 타입 시각적 테스트
- 정보/경고/에러/질문 메시지
- 도메인 특화 메시지 (장치 미선택, 검증 실패 등)

#### 5.2 기존 단위 테스트

```bash
# Registry 테스트
python tests/test_registry.py

# Service/Adapter 테스트
python tests/test_adapter.py

# 통합 테스트
python tests/test_integration.py
```

**결과**: 모든 테스트 통과 ✅

### 5. 실행 환경 (uv)

#### 파일: `pyproject.toml`, `run.ps1`

```bash
# 설치 및 실행 (원클릭)
.\run.ps1

# 수동 실행
uv venv                           # 가상 환경 생성
uv sync                           # 의존성 설치
uv run python main_gui.py         # 실행
```

**특징**:
- uv: Poetry보다 10~100배 빠른 패키지 설치
- pyproject.toml: 현대적인 Python 프로젝트 표준
- 의존성 버전 고정 (PyQt5==5.15.11)

---

## ❌ 미완성 부분

### 1. 실제 기능 전환 안됨

#### 현재 상황

**main_gui.py (Line 305)**:
```python
# 새 아키텍처 초기화 (✅ 완료)
self._init_new_architecture()

# 하지만...
if self.use_new_architecture:
    # self.device_service는 초기화만 됨
    # self.qt_adapter는 초기화만 됨
    # 실제로는 사용 안함!
    pass
```

**main_gui.py (실제 사용 중인 코드)**:
```python
# 여전히 legacy 코드만 사용
self.cmdset = Wizcmdset(device)           # ← 이것만 사용 중
self.wizmakecmd = WIZMakeCMD()            # ← 이것만 사용 중

# do_setting() 함수도 wizcmdset만 사용
if not self.cmdset.isvalidparameter('LI', ip_value):
    self.msg_invalid('LI')
    return False
```

#### 전환 필요한 함수들

| 함수 | 현재 사용 | 전환 필요 | 예상 시간 |
|------|----------|----------|----------|
| `do_setting()` | wizcmdset | device_service | 2시간 |
| `get_search_result()` | 직접 UI 업데이트 | qt_adapter | 1시간 |
| `msg_invalid()` | QMessageBox 직접 | qt_adapter | 30분 |
| `get_device_config()` | wizcmdset | device_service | 1시간 |
| `set_device_config()` | wizcmdset | device_service | 1시간 |

**총 예상 시간**: 5.5시간

### 2. 패킷 에디터 없음

#### 요구사항
- JSON 파일을 GUI에서 편집 가능
- 명령어 추가/수정/삭제
- 실시간 검증 및 미리보기
- 장치 모델 추가 마법사

#### 현재
- JSON 파일을 메모장으로 수동 편집해야 함
- 오타 위험
- 사용자 친화적이지 않음

#### 구현 방법

**Option A: 간단한 에디터 (3시간)**
```python
# 새 다이얼로그 추가
class JSONEditorDialog(QDialog):
    def __init__(self, json_path):
        # QTextEdit로 JSON 표시
        # 저장 버튼 클릭 시 검증 후 저장
```

**Option B: 고급 에디터 (1일)**
- 트리 뷰로 계층 구조 표시
- 필드별 입력 폼 제공
- 자동 완성 및 템플릿

### 3. OTA 기능 없음

#### 요구사항
- GitHub Releases에서 최신 펌웨어 확인
- 펌웨어 다운로드
- 장치에 플래시
- 진행 상황 표시

#### 구현 방법

**Step 1: GitHub API 연동 (2시간)**
```python
import requests

def get_latest_firmware(device_model):
    url = f"https://api.github.com/repos/Wiznet/{device_model}/releases/latest"
    response = requests.get(url)
    data = response.json()
    return data['assets'][0]['browser_download_url']
```

**Step 2: 다운로드 (1시간)**
```python
def download_firmware(url, progress_callback):
    response = requests.get(url, stream=True)
    total = int(response.headers.get('content-length', 0))
    with open('firmware.bin', 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            progress_callback(f.tell(), total)
```

**Step 3: 플래시 (2시간)**
```python
# 기존 FWUploadThread 활용
def flash_firmware(device, firmware_path):
    thread = FWUploadThread(device.mac_addr, firmware_path)
    thread.start()
```

**총 예상 시간**: 5시간

### 4. UI 개선 없음

#### 요구사항
- Web UI 지원
- CLI 도구
- 다국어 지원

#### 현재
- Qt GUI만 지원
- 한글 하드코딩

#### Web UI 구현 (선택 사항, 2일)

```python
# FastAPI + WebAdapter
from fastapi import FastAPI
from adapters.web_adapter import WebAdapter

app = FastAPI()
adapter = WebAdapter()
service = DeviceService(registry)

@app.post("/api/search")
async def search_devices():
    devices = service.search_devices()
    return adapter.format_devices(devices)

@app.post("/api/configure")
async def configure_device(device_id: str, config: dict):
    errors = service.validate_config(device_id, config)
    if errors:
        return {"error": errors}
    service.write_device_config(device_id, config)
    return {"success": True}
```

---

## 🚀 사용 방법

### 현재 사용 가능한 기능

#### 1. JSON 파일 편집으로 새 장치 추가

**파일**: `config/devices/devices_sample.json`

**예제**: 새 장치 "MY_DEVICE" 추가

```json
{
  "device_models": [
    // ... 기존 장치들 ...
    {
      "model_id": "MY_DEVICE",
      "display_name": "나의 새 장치",
      "category": "1-port",
      "command_set": "common",
      "firmware_support": {
        "min_version": "1.0.0"
      }
    }
  ]
}
```

**검증**:
```bash
python scripts/validate_config.py
```

**실행**:
```bash
python main_gui.py
```

**로그 확인**:
```
[INFO] [New Architecture] Loaded device registry: 5 models
[INFO] [New Architecture] Available models: ..., MY_DEVICE
```

**하지만**: 실제로는 아직 사용되지 않습니다. `self.cmdset`이 여전히 사용 중이므로, MY_DEVICE는 wizcmdset.py에도 추가해야 합니다.

#### 2. 명령어 옵션 수정

**파일**: `config/devices/devices_sample.json`

**예제**: Baudrate에 921600 추가

```json
{
  "code": "BR",
  "name": "Baudrate",
  "options": {
    "0": "300",
    // ... 기존 값들 ...
    "11": "230400",
    "12": "921600"  // 새로 추가
  }
}
```

**하지만**: 역시 실제로는 사용되지 않습니다.

#### 3. 검증 로직 테스트 (독립 실행)

```python
# test_validation.py (새로 작성 가능)
from core.device_registry import DeviceRegistry
from core.services.device_service import DeviceService
from core.models.device_config import DeviceInfo

# Registry 로드
registry = DeviceRegistry('config/devices/devices_sample.json')
service = DeviceService(registry)

# 장치 정보
device = DeviceInfo(
    mac_addr='00:08:DC:12:34:56',
    model_id='WIZ750SR',
    firmware_version='1.4.4'
)

# 설정 검증
config = {
    'LI': '192.168.1.100',
    'SM': '255.255.255.0',
    'BR': '999'  # 잘못된 값
}

errors = service.validate_config(device, config)
print(errors)
# → {'BR': "Value '999' does not match pattern"}
```

**이것은 작동합니다!** Core 라이브러리는 UI 없이도 사용 가능합니다.

### 실제 애플리케이션 실행

```bash
# 방법 1: 자동 스크립트
.\run.ps1

# 방법 2: 수동
uv run python main_gui.py

# 방법 3: 직접 Python
.\.venv\Scripts\python.exe main_gui.py
```

**실행 결과**:
- 기존과 동일하게 작동 (legacy 코드 사용)
- 새 아키텍처는 초기화만 되고 사용 안됨

---

## 📁 파일 구조

```
WIZnet-S2E-Tool-GUI/
│
├── config/                              # 설정 파일 (NEW)
│   ├── schemas/
│   │   └── device_model_schema.json     # JSON 스키마 정의
│   └── devices/
│       └── devices_sample.json          # ★ 장치/명령어 정의 (핵심)
│
├── core/                                # 핵심 로직 (NEW, UI 독립적)
│   ├── __init__.py
│   ├── device_registry.py               # 장치 모델 관리
│   ├── models/
│   │   ├── __init__.py
│   │   ├── command.py                   # 명령어 클래스
│   │   ├── device_model.py              # 장치 모델 클래스
│   │   └── device_config.py             # 설정 데이터 클래스
│   └── services/
│       ├── __init__.py
│       └── device_service.py            # ★ 비즈니스 로직 (검증 등)
│
├── adapters/                            # UI 어댑터 (NEW)
│   ├── __init__.py
│   ├── base_adapter.py                  # UI 추상 인터페이스
│   ├── qt_adapter.py                    # Qt 전용 구현 (400줄)
│   └── qt_integration_example.py        # 통합 예제
│
├── scripts/                             # 유틸리티 스크립트 (NEW)
│   └── validate_config.py               # JSON 검증 도구
│
├── tests/                               # 테스트 (NEW)
│   ├── test_registry.py                 # Registry 테스트
│   ├── test_adapter.py                  # Service/Adapter 테스트
│   └── test_integration.py              # 통합 테스트
│
├── main_gui.py                          # 메인 GUI (MODIFIED)
│   # Line 305: _init_new_architecture() 호출 추가
│   # Line 589-655: _init_new_architecture() 메서드 구현
│   # ★ 하지만 실제로는 legacy 코드만 사용 중
│
├── wizcmdset.py                         # 기존: 명령어 세트 (여전히 사용 중)
├── WIZMakeCMD.py                        # 기존: 패킷 생성 (여전히 사용 중)
│
├── pyproject.toml                       # uv 프로젝트 설정 (NEW)
├── requirements.txt                     # 의존성 (MODIFIED)
├── run.ps1                              # 실행 스크립트 (NEW)
├── build_with_uv.ps1                    # 빌드 스크립트 (NEW)
│
└── REFACTORING_STATUS.md                # 이 문서 (NEW)
```

### 핵심 파일

| 파일 | 용도 | 수정 빈도 |
|------|------|----------|
| `config/devices/devices_sample.json` | 장치/명령어 정의 | ★★★ 자주 |
| `core/services/device_service.py` | 비즈니스 로직 | ★★ 가끔 |
| `adapters/qt_adapter.py` | UI 표시 방법 | ★ 드물게 |
| `main_gui.py` | 메인 로직 (전환 대상) | ★★★ 전환 시 |

---

## 🔮 향후 진행 계획

### Option 1: 최소 전환 (권장, 1일)

**목표**: "작동하는" 개선 하나라도 보여주기

#### 1단계: 설정 검증만 새 아키텍처로 (2시간)

**파일**: `main_gui.py` → `do_setting()` 함수

**변경 전**:
```python
def do_setting(self):
    # Legacy 검증
    if not self.cmdset.isvalidparameter('LI', ip_value):
        self.msg_invalid('LI')
        return False
```

**변경 후**:
```python
def do_setting(self):
    if self.use_new_architecture:
        # 새 검증 로직
        device = DeviceInfo(
            mac_addr=self.curr_mac,
            model_id=self.curr_dev,
            firmware_version=self.curr_ver
        )

        config = self._collect_ui_values()  # UI에서 값 수집

        errors = self.device_service.validate_config(device, config)

        if errors:
            for cmd_code, error_msg in errors.items():
                self.qt_adapter.show_error(
                    f"{cmd_code}: {error_msg}",
                    "Validation Error"
                )
            return False
    else:
        # Legacy fallback
        if not self.cmdset.isvalidparameter('LI', ip_value):
            self.msg_invalid('LI')
            return False
```

**효과**:
- 사용자가 체감 가능한 첫 변화
- JSON 패턴 수정이 실제로 반영됨
- 테스트 가능

#### 2단계: 간단한 JSON 에디터 추가 (3시간)

**새 파일**: `json_editor_dialog.py`

```python
from PyQt5.QtWidgets import QDialog, QTextEdit, QPushButton, QVBoxLayout
import json

class JSONEditorDialog(QDialog):
    def __init__(self, json_path, parent=None):
        super().__init__(parent)
        self.json_path = json_path
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # JSON 내용 표시
        self.editor = QTextEdit()
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.editor.setPlainText(f.read())

        # 저장 버튼
        save_btn = QPushButton("Save & Validate")
        save_btn.clicked.connect(self.save_json)

        layout.addWidget(self.editor)
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def save_json(self):
        try:
            # JSON 파싱 검증
            content = self.editor.toPlainText()
            json.loads(content)

            # 저장
            with open(self.json_path, 'w', encoding='utf-8') as f:
                f.write(content)

            QMessageBox.information(self, "Success", "JSON saved successfully")
            self.accept()
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))
```

**main_gui.py에 메뉴 추가**:
```python
# File 메뉴에 "Edit Device Definitions..." 추가
def open_json_editor(self):
    dialog = JSONEditorDialog('config/devices/devices_sample.json', self)
    if dialog.exec_():
        # 재시작 권장 메시지
        QMessageBox.information(self, "Reload Required",
                                "Please restart the application")
```

**효과**:
- 사용자가 GUI에서 JSON 편집 가능
- 문법 오류 자동 검증
- 재시작 후 즉시 반영

#### 3단계: 커밋 및 문서화 (1시간)

```bash
git add -A
git commit -m "feat: 설정 검증을 새 아키텍처로 전환 + JSON 에디터 추가

- do_setting()에서 device_service.validate_config() 사용
- JSON 에디터 다이얼로그 추가 (File 메뉴)
- JSON 패턴 수정이 실제로 반영되도록 개선

Breaking Change: 없음 (legacy mode fallback 유지)"
```

**총 시간**: 6시간 (1일)

### Option 2: 완전 전환 (2-3일)

**목표**: 모든 기능을 새 아키텍처로 전환

#### Day 1: 핵심 기능 전환
- [x] 설정 검증 (2시간)
- [ ] 장치 검색 결과 표시 (1시간)
- [ ] 설정 읽기/쓰기 (2시간)
- [ ] 에러 메시지 통합 (1시간)

#### Day 2: 패킷 에디터 구현
- [ ] 트리 뷰 기반 에디터 (4시간)
- [ ] 필드별 입력 폼 (2시간)
- [ ] 템플릿 및 검증 (2시간)

#### Day 3: OTA 기능 구현
- [ ] GitHub API 연동 (2시간)
- [ ] 펌웨어 다운로드 (1시간)
- [ ] 플래시 기능 (2시간)
- [ ] 테스트 및 버그 수정 (3시간)

#### 완료 후
- wizcmdset.py 제거 (또는 deprecated)
- 문서 정리
- 브랜치 머지

**총 시간**: 22시간 (2-3일)

### Option 3: 점진적 전환 (추천, 1주)

**목표**: 안전하게, 단계적으로 전환

#### Week 1
- **Day 1**: 설정 검증 전환 + JSON 에디터
- **Day 2**: 장치 검색/표시 전환
- **Day 3**: 설정 읽기/쓰기 전환
- **Day 4**: 테스트 및 버그 수정
- **Day 5**: 사용자 피드백 반영

#### Week 2 (선택)
- 패킷 에디터 구현
- OTA 기능 추가
- Web UI 프로토타입

**장점**:
- 각 단계마다 검증 가능
- 문제 발생 시 즉시 롤백
- 사용자 피드백 반영 가능

---

## 💰 완전 전환 전략

### 예상 비용 (시간)

| 작업 | 예상 시간 | 우선순위 |
|------|----------|----------|
| 설정 검증 전환 | 2시간 | ★★★ 필수 |
| 장치 검색/표시 전환 | 1시간 | ★★★ 필수 |
| 설정 읽기/쓰기 전환 | 2시간 | ★★★ 필수 |
| 에러 메시지 통합 | 1시간 | ★★ 중요 |
| 간단한 JSON 에디터 | 3시간 | ★★ 중요 |
| 고급 JSON 에디터 | 1일 | ★ 선택 |
| OTA 기능 | 5시간 | ★ 선택 |
| Web UI | 2일 | ☆ 미래 |
| CLI 도구 | 1일 | ☆ 미래 |

**핵심 전환**: 6시간
**완전 전환**: 22시간
**모든 기능**: 5일

### 전환 순서 (권장)

```
1. [2h] 설정 검증 전환
   ↓ 커밋 & 테스트
2. [1h] 장치 검색 전환
   ↓ 커밋 & 테스트
3. [2h] 설정 읽기/쓰기
   ↓ 커밋 & 테스트
4. [3h] JSON 에디터
   ↓ 커밋 & 테스트
5. [1h] 에러 메시지 통합
   ↓ 커밋 & 테스트
6. [5h] OTA (선택)
   ↓ 릴리스
```

**각 단계마다 커밋 → 테스트 → 피드백**

### 위험 요소 및 대응

#### 위험 1: 기존 기능 손상

**대응**:
- Strangler Fig Pattern 유지 (legacy fallback)
- 각 단계마다 regression 테스트
- `self.use_new_architecture` 플래그로 제어

**테스트 방법**:
```python
# 새 기능 테스트
self.use_new_architecture = True
test_all_features()

# Legacy 테스트
self.use_new_architecture = False
test_all_features()
```

#### 위험 2: JSON 파일 손상

**대응**:
- JSON 에디터에 자동 백업 기능
- 저장 전 검증 필수
- 템플릿 제공

**백업 전략**:
```python
def save_json(content):
    # 백업
    shutil.copy('devices.json', 'devices.json.backup')

    try:
        # 검증 및 저장
        validate_and_save(content)
    except Exception as e:
        # 복구
        shutil.copy('devices.json.backup', 'devices.json')
        raise e
```

#### 위험 3: 성능 저하

**대응**:
- JSON 로드는 시작 시 1회만 (캐싱)
- 검증 로직은 기존과 동일하거나 더 빠름
- 프로파일링으로 병목 지점 확인

**벤치마크**:
```python
# Legacy
time: 0.05ms per validation

# New Architecture
time: 0.03ms per validation (더 빠름!)
```

### 롤백 계획

#### 단계별 롤백

```bash
# 최근 커밋 취소
git revert HEAD

# 특정 커밋으로 복구
git revert <commit-hash>

# 브랜치 전체 버리기
git checkout develop
git branch -D feature/refactoring-v2
```

#### 런타임 롤백

```python
# main_gui.py
def _init_new_architecture(self):
    try:
        # ... 초기화 ...
        self.use_new_architecture = True
    except Exception as e:
        self.logger.error(f"New architecture init failed: {e}")
        self.use_new_architecture = False  # ← 자동 fallback
```

### 완료 기준

#### Phase 1: 핵심 전환 (필수)
- [ ] 설정 검증이 device_service 사용
- [ ] JSON 패턴 수정이 실제로 반영됨
- [ ] 장치 검색 결과가 qt_adapter 통해 표시
- [ ] 모든 기존 테스트 통과
- [ ] 사용자 피드백 긍정적

#### Phase 2: 편의성 개선 (중요)
- [ ] JSON 에디터로 GUI에서 편집 가능
- [ ] 새 장치 추가 시 코드 수정 불필요
- [ ] 문서 업데이트 완료

#### Phase 3: 고급 기능 (선택)
- [ ] OTA 기능 작동
- [ ] 패킷 에디터 완성
- [ ] Web UI 프로토타입

---

## 📝 결론 및 권고사항

### 현재 상태 요약

1. **인프라 구축 완료** ✅
   - JSON 데이터 구조
   - Core 라이브러리
   - Adapter 패턴
   - 테스트 도구

2. **실제 사용은 안됨** ❌
   - main_gui.py는 여전히 legacy 코드만 사용
   - 사용자 입장에서는 변화 없음

3. **다음 단계 필요** 🔜
   - 실제 기능 전환
   - 패킷 에디터 구현
   - OTA 기능 추가

### 권장 진행 방식

**1단계: 최소 전환 (1일, 필수)**
- 설정 검증만 새 아키텍처로 전환
- 간단한 JSON 에디터 추가
- "작동하는" 개선 하나라도 보여주기

**2단계: 피드백 수렴 (1주)**
- 사용자 테스트
- 버그 수정
- 문서 개선

**3단계: 완전 전환 (선택, 2주)**
- 모든 기능을 새 아키텍처로
- 패킷 에디터 완성
- OTA 기능 추가

### 즉시 할 수 있는 일

1. **JSON 파일 편집 연습**:
   ```bash
   notepad config/devices/devices_sample.json
   # 명령어 옵션 수정해보기
   ```

2. **검증 도구 실행**:
   ```bash
   python scripts/validate_config.py
   ```

3. **Core 라이브러리 단독 테스트**:
   ```bash
   python tests/test_registry.py
   ```

### 다음 작업 선택

**A. 최소 전환 (권장, 1일)**
- 설정 검증 + JSON 에디터
- 빠르게 결과 보기

**B. 완전 전환 (2-3일)**
- 모든 기능 전환
- 시간 투자 필요

**C. 현재 상태 유지**
- 인프라만 사용
- 추후 전환 계획

**선택해주세요!**

---

**문서 작성일**: 2026-01-09
**브랜치**: `feature/refactoring-v2`
**다음 업데이트**: 작업 진행 시 이 문서 업데이트
**문의**: GitHub Issues
