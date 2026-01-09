# Phase 1-B 구현 가이드 및 테스트

## 📋 목차

1. [Phase 1-B 개요](#phase-1-b-개요)
2. [구현된 컴포넌트](#구현된-컴포넌트)
3. [테스트 방법](#테스트-방법)
4. [통합 가이드](#통합-가이드)
5. [아키텍처 설명](#아키텍처-설명)
6. [다음 단계](#다음-단계)

---

## Phase 1-B 개요

**목표**: Core와 UI 사이에 Adapter 계층 구현

**완료된 작업**:
- ✅ BaseAdapter 추상 인터페이스 정의
- ✅ QtAdapter PyQt5 구현
- ✅ DeviceService 비즈니스 로직 계층
- ✅ 통합 가이드 및 예제
- ✅ 테스트 스크립트

**핵심 원칙**:
- Dependency Inversion: Core는 UI를 모름
- Separation of Concerns: 각 계층은 명확한 책임
- Testability: UI 없이 독립적으로 테스트 가능

---

## 구현된 컴포넌트

### 1. BaseAdapter (추상 인터페이스)

**위치**: [adapters/base_adapter.py](adapters/base_adapter.py)

**역할**: 모든 UI 어댑터가 구현해야 하는 표준 인터페이스

**주요 메서드**:

#### Core → UI (데이터 표시)
```python
def show_devices(devices: List[DeviceInfo])
def show_device_config(config: DeviceConfig, model: DeviceModel)
def show_error(message: str, title: Optional[str] = None)
def show_warning(message: str, title: Optional[str] = None)
def show_info(message: str, title: Optional[str] = None)
def show_progress(message: str, value: Optional[int], maximum: Optional[int])
def hide_progress()
```

#### UI → Core (이벤트 등록)
```python
def register_search_handler(handler: Callable[[], None])
def register_configure_handler(handler: Callable[[DeviceInfo], None])
def register_apply_handler(handler: Callable[[DeviceInfo, Dict[str, str]], None])
def register_upload_handler(handler: Callable[[DeviceInfo, str], None])
```

#### UI 상태 관리
```python
def enable_ui(enabled: bool)
def update_command_fields(model: DeviceModel, firmware_version: str)
def validate_fields(model: DeviceModel) -> bool
```

#### 필드 조작
```python
def set_field_value(command_code: str, value: str)
def get_field_value(command_code: str) -> Optional[str]
def highlight_invalid_field(command_code: str, error_message: str)
def clear_field_highlights()
```

---

### 2. QtAdapter (PyQt5 구현)

**위치**: [adapters/qt_adapter.py](adapters/qt_adapter.py)

**역할**: BaseAdapter를 PyQt5로 구현

**특징**:
- QTableWidget으로 장치 목록 표시
- QLineEdit/QComboBox로 설정 입력
- QMessageBox로 메시지 표시
- QProgressBar로 진행 상황 표시
- Qt 시그널/슬롯 자동 연결

**예제 사용**:
```python
from adapters.qt_adapter import QtAdapter

# WIZWindow에서 초기화
self.qt_adapter = QtAdapter(self)
self.qt_adapter.initialize()

# 장치 표시
devices = [...]
self.qt_adapter.show_devices(devices)

# 에러 표시
self.qt_adapter.show_error("Connection failed", "Network Error")

# 이벤트 핸들러 등록
def on_search():
    print("Search button clicked")

self.qt_adapter.register_search_handler(on_search)
```

---

### 3. DeviceService (비즈니스 로직)

**위치**: [core/services/device_service.py](core/services/device_service.py)

**역할**: UI 독립적인 비즈니스 로직

**주요 기능**:

#### 장치 조회
```python
service = DeviceService()

# 모든 모델 목록
models = service.list_device_models()

# 특정 모델 가져오기
model = service.get_device_model('WIZ750SR')

# 펌웨어 버전별 명령어
commands = service.get_commands_for_device('WIZ750SR', '1.4.4')
```

#### 설정 검증 (완전 구현)
```python
device = DeviceInfo(
    mac_addr='00:08:DC:12:34:56',
    model_id='WIZ750SR',
    firmware_version='1.0.0'
)

config = {
    'LI': '192.168.1.100',
    'SM': '255.255.255.0',
    'BR': '12'  # 115200
}

# 검증
errors = service.validate_config(device, config)

if errors:
    for cmd_code, error_msg in errors.items():
        print(f"{cmd_code}: {error_msg}")
else:
    print("Config is valid")
```

**검증 기능**:
- ✅ 명령어 존재 확인
- ✅ 읽기 전용 명령어 쓰기 차단
- ✅ 정규식 패턴 검증 (IP, MAC, Baud rate 등)
- ✅ 펌웨어 버전별 명령어 지원 확인

#### 장치 작업 (Placeholder)
```python
# Phase 2에서 완전 구현 예정
service.search_devices(on_complete=lambda devices: print(devices))
service.read_device_config(device, on_complete=lambda cfg, mdl: print(cfg))
service.write_device_config(device, config)
```

---

## 테스트 방법

### 테스트 1: Adapter & Service 테스트

**실행**:
```bash
python tests/test_adapter.py
```

**예상 출력**:
```
============================================================
WIZnet S2E Adapter & Service Layer Test
============================================================

[*] Testing DeviceService...
[OK] Service has 4 device models
[OK] Got model: WIZ750SR
[OK] WIZ750SR v1.0.0 has 36 commands

[*] Testing configuration validation...
[OK] Valid config passed validation
[OK] Invalid IP detected correctly
[OK] Read-only command write blocked
[OK] Unknown command detected

[*] Testing firmware version support in service...
[OK] WIZ750SR v1.0.0: MB = False
[OK] WIZ750SR v1.4.4: MB = True
[OK] Firmware version support working in service

[*] Testing adapter interface...
[OK] Adapter show_devices() works
[OK] Adapter message methods work
[OK] Adapter event handler registration works

============================================================
[PASS] All 4 tests passed!
============================================================
```

**성공 기준**:
- ✅ DeviceService 기능 동작
- ✅ 설정 검증 동작 (유효/무효 구분)
- ✅ 펌웨어 버전별 명령어 동작
- ✅ Adapter 인터페이스 동작

---

### 테스트 2: Python 인터랙티브 테스트

**실행**:
```bash
python
```

**Python 콘솔**:
```python
# 1. Service 초기화
from core.services.device_service import DeviceService
from core.models.device_config import DeviceInfo

service = DeviceService()
print(f"Models: {service.list_device_models()}")
# 출력: Models: ['WIZ750SR', 'W55RP20-S2E', 'W55RP20-S2E-2CH', 'IP20']

# 2. 모델 조회
model = service.get_device_model('WIZ750SR')
print(f"{model.display_name}: {len(model.commands)} commands")
# 출력: WIZ750SR: 36 commands

# 3. 설정 검증
device = DeviceInfo(
    mac_addr='00:08:DC:12:34:56',
    model_id='WIZ750SR',
    firmware_version='1.0.0'
)

valid_config = {'LI': '192.168.1.100', 'BR': '12'}
invalid_config = {'LI': '999.999.999.999'}

print(service.validate_config(device, valid_config))
# 출력: {}

print(service.validate_config(device, invalid_config))
# 출력: {'LI': 'Invalid value for Local IP address'}

# 4. 펌웨어 버전별 명령어
cmds_v1_0 = service.get_commands_for_device('WIZ750SR', '1.0.0')
cmds_v1_4 = service.get_commands_for_device('WIZ750SR', '1.4.4')

print(f"v1.0.0 has MB: {'MB' in cmds_v1_0}")  # False
print(f"v1.4.4 has MB: {'MB' in cmds_v1_4}")  # True

exit()
```

---

### 테스트 3: Mock Adapter 테스트

**코드**:
```python
from adapters.base_adapter import BaseUIAdapter
from core.models.device_config import DeviceInfo

class MockAdapter(BaseUIAdapter):
    def __init__(self):
        self.messages = []

    def show_devices(self, devices):
        self.messages.append(f"Showing {len(devices)} devices")

    def show_error(self, message, title=None):
        self.messages.append(f"Error: {message}")

    # ... (다른 추상 메서드 구현)

# 테스트
adapter = MockAdapter()

devices = [DeviceInfo('00:08:DC:11:11:11', 'WIZ750SR', '1.0.0')]
adapter.show_devices(devices)

print(adapter.messages)
# 출력: ['Showing 1 devices']
```

---

## 통합 가이드

### 옵션 1: 점진적 통합 (권장)

**장점**: 기존 코드 깨지지 않음, 안전하게 전환

**단계**:

#### 1. Adapter 초기화
[main_gui.py](main_gui.py)의 `WIZWindow.__init__()`에 추가:

```python
# 기존 초기화 코드 후에...

# Core 레지스트리 초기화
try:
    from core.device_registry import DeviceRegistry, set_global_registry
    config_path = 'config/devices/devices_sample.json'
    registry = DeviceRegistry(config_path)
    set_global_registry(registry)
    self.logger.info(f"[New Architecture] Loaded {len(registry.list_models())} models")
except Exception as e:
    self.logger.warning(f"[New Architecture] Could not load registry: {e}")

# Adapter 초기화
try:
    from adapters.qt_adapter import QtAdapter
    from core.services.device_service import DeviceService

    self.qt_adapter = QtAdapter(self)
    self.device_service = DeviceService()
    self.qt_adapter.initialize()

    self.logger.info("[New Architecture] QtAdapter initialized")
    self.use_new_architecture = True
except Exception as e:
    self.logger.warning(f"[New Architecture] Adapter init failed: {e}")
    self.use_new_architecture = False
```

#### 2. 이벤트 핸들러 등록 (선택적)

```python
if self.use_new_architecture:
    # Search handler
    def on_search():
        self.logger.info("[New Architecture] Search via adapter")
        # 아직은 기존 코드 호출
        self.search_pre()

    self.qt_adapter.register_search_handler(on_search)

    # 나중에 점진적으로 새 아키텍처로 전환
    # self.device_service.search_devices(...)
```

#### 3. 검증 로직 마이그레이션 (예제)

**기존 코드**:
```python
def validate_ip(self, value):
    if not self.cmdset.isvalidparameter('LI', value):
        self.msg_invalid('LI')
        return False
    return True
```

**새 코드**:
```python
def validate_ip(self, value):
    if self.use_new_architecture:
        model = self.device_service.get_device_model(self.current_device_model)
        command = model.get_command('LI')
        if not command.validate(value):
            self.qt_adapter.highlight_invalid_field('LI', 'Invalid IP address')
            return False
    else:
        # 기존 로직 유지
        if not self.cmdset.isvalidparameter('LI', value):
            self.msg_invalid('LI')
            return False
    return True
```

---

### 옵션 2: 새 프로젝트에 적용

**새 프로젝트**나 **완전히 새로 시작하는 경우**:

```python
from PyQt5.QtWidgets import QApplication, QMainWindow
from adapters.qt_adapter import QtAdapter
from core.services.device_service import DeviceService

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 1. Adapter 초기화
        self.adapter = QtAdapter(self)
        self.service = DeviceService()

        # 2. 이벤트 핸들러 등록
        self.adapter.register_search_handler(self.on_search)
        self.adapter.register_configure_handler(self.on_configure)

        # 3. Adapter 초기화
        self.adapter.initialize()

    def on_search(self):
        """검색 버튼 클릭"""
        def on_complete(devices):
            self.adapter.show_devices(devices)

        self.service.search_devices(on_complete=on_complete)

    def on_configure(self, device):
        """설정 읽기"""
        def on_complete(config, model):
            self.adapter.show_device_config(config, model)

        self.service.read_device_config(device, on_complete=on_complete)

if __name__ == '__main__':
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec_()
```

---

## 아키텍처 설명

### 계층 구조

```
┌─────────────────────────────────────────────────────┐
│                   UI Layer (Qt)                      │
│               main_gui.py (WIZWindow)                │
│  • QTableWidget, QLineEdit, QComboBox, etc.         │
│  • 표시만 담당, 비즈니스 로직 없음                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Adapter Layer                       │
│            QtAdapter (qt_adapter.py)                 │
│  • Core ↔ UI 변환                                   │
│  • Qt 위젯 조작                                      │
│  • 이벤트 핸들링                                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                 Service Layer                        │
│         DeviceService (device_service.py)            │
│  • 비즈니스 로직                                      │
│  • 장치 검색/설정/검증                                │
│  • UI 독립적                                         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                   Core Layer                         │
│  DeviceRegistry, DeviceModel, Command                │
│  • 데이터 모델                                        │
│  • 검증 로직                                          │
│  • 펌웨어 버전 관리                                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                   Data Layer                         │
│          devices_sample.json (JSON)                  │
│  • 명령어 세트 정의                                   │
│  • 장치 모델 정의                                     │
│  • UI 힌트                                           │
└─────────────────────────────────────────────────────┘
```

### 데이터 흐름

#### 장치 검색 (Device Search)
```
User Click
    ↓
UI (btn_search.clicked)
    ↓
Adapter.register_search_handler()
    ↓
Service.search_devices()
    ↓
Core (DeviceRegistry, DeviceModel)
    ↓
Service → Adapter (callback)
    ↓
Adapter.show_devices()
    ↓
UI (QTableWidget updated)
```

#### 설정 검증 (Validation)
```
User Input
    ↓
Adapter.get_field_value('LI')
    ↓
Service.validate_config(device, {'LI': value})
    ↓
Core.Command.validate(value)  # 정규식 검증
    ↓
Service → Adapter (validation result)
    ↓
Adapter.highlight_invalid_field('LI', 'Invalid IP')
    ↓
UI (QLineEdit red border)
```

---

## 다음 단계

### Phase 2-A: 네트워크 계층 마이그레이션 (예정)

**목표**: WIZMakeCMD/WIZMSGHandler를 Core로 이동

**작업**:
1. `core/services/network_service.py` 생성
2. 패킷 생성 로직 Core로 이동
3. 패킷 파싱 로직 Core로 이동
4. UDP/TCP 통신 추상화
5. DeviceService에서 network_service 사용

**예상 코드**:
```python
class NetworkService:
    def send_command(self, device: DeviceInfo, command: Command, value: str):
        packet = self._build_packet(device, command, value)
        response = self._send_udp(packet)
        return self._parse_response(response)

    def search_all_devices(self) -> List[DeviceInfo]:
        packet = self._build_search_packet()
        responses = self._broadcast_udp(packet)
        return [self._parse_device_info(r) for r in responses]
```

---

### Phase 2-B: 실제 UI 통합 (예정)

**목표**: main_gui.py에서 Adapter를 실제로 사용

**작업**:
1. WIZWindow.__init__()에 Adapter 초기화
2. 검색 기능을 Adapter를 통해 호출
3. 설정 읽기/쓰기를 Service를 통해 처리
4. wizcmdset.py 의존성 점진적 제거

---

### Phase 3: 암호화 및 OTA (예정)

**목표**: 설정 파일 암호화 및 OTA 기능

**작업**:
1. Fernet 암호화 구현
2. devices.enc 생성/로드
3. OTA 서비스 구현 (GitHub releases API)
4. 펌웨어 다운로드 및 업로드

---

### Phase 4: Web UI (선택)

**목표**: 웹 브라우저에서 접근 가능한 UI

**작업**:
1. `adapters/web_adapter.py` 구현
2. FastAPI 서버
3. WebSocket 실시간 업데이트
4. 모바일 반응형 UI

---

## 요약

**Phase 1-B 완료 사항**:
- ✅ BaseAdapter 추상 인터페이스 (18개 메서드)
- ✅ QtAdapter PyQt5 구현 (400줄)
- ✅ DeviceService 비즈니스 로직 (250줄)
- ✅ 통합 가이드 및 예제
- ✅ 테스트 스크립트 (4개 테스트 통과)

**핵심 가치**:
1. **관심사 분리**: Core, Service, Adapter, UI 계층 명확히 분리
2. **테스트 가능성**: UI 없이 독립적으로 테스트 가능
3. **확장성**: 새 UI 프레임워크 지원 용이 (Web, CLI, etc.)
4. **점진적 마이그레이션**: 기존 코드와 공존 가능
5. **SOLID 원칙**: DIP, SRP, OCP 준수

**다음 단계**: Phase 2 (네트워크 계층 마이그레이션 또는 실제 UI 통합)

---

**작성일**: 2026-01-07
**버전**: v2.0.0
**Phase**: 1-B 완료
