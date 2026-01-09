# 새 아키텍처 실용 가이드

## 📋 목차
1. [새 아키텍처란?](#새-아키텍처란)
2. [기존 vs 신규 비교](#기존-vs-신규-비교)
3. [실제 사용 시나리오](#실제-사용-시나리오)
4. [파일 구조](#파일-구조)
5. [마이그레이션 가이드](#마이그레이션-가이드)

---

## 🎯 새 아키텍처란?

### 핵심 개념
**"명령어와 장치 정보를 JSON 파일로 분리하여, 코드 수정 없이 설정만으로 새 장치를 추가할 수 있게 만들었습니다."**

### 현재 상태
- ✅ 새 아키텍처 구현 완료
- ✅ 기존 코드와 병행 실행 (Strangler Fig Pattern)
- ✅ `main_gui.py` 실행 시 자동으로 새 아키텍처 초기화
- ⚠️ 아직 대부분의 기능은 기존 코드 사용 중

---

## 📊 기존 vs 신규 비교

### 시나리오 1: 새 장치 모델 추가

#### **기존 방식 (wizcmdset.py 수정)**
```python
# wizcmdset.py 파일을 열어서...

class Wizcmdset:
    def __init__(self, device):
        # 1. 새 장치 이름 추가
        if device == "NEW_DEVICE":
            self.cmdset = {
                'VR': ['Version', 'RO', {}, 'ipaddr'],
                'MN': ['Product', 'RO', {}, 'ipaddr'],
                'LI': ['Local IP', 'RW', {}, 'ipaddr'],
                'SM': ['Subnet', 'RW', {}, 'ipaddr'],
                # ... 30개 이상의 명령어를 일일이 타이핑
            }

    # 2. 검증 함수 수정
    def isvalidparameter(self, cmdname, param):
        if cmdname == 'LI':
            # IP 검증 로직을 직접 구현
            if not self._validate_ip(param):
                return False
        # ... 각 명령어마다 검증 로직 추가

    # 3. UI 생성 정보 수정
    def get_ui_info(self, cmdname):
        # 각 명령어의 UI 위젯 정보를 하드코딩
        pass
```

**문제점**:
- 100줄 이상의 코드 수정 필요
- 오타나 실수 가능성 높음
- 테스트 어려움
- 다른 개발자가 이해하기 어려움

#### **신규 방식 (JSON 편집)**
```json
// config/devices/devices_sample.json 파일 편집

{
  "device_models": [
    {
      "model_id": "NEW_DEVICE",
      "display_name": "New WIZ Device",
      "category": "1-port",
      "command_set": "common",  // 기존 명령어 세트 재사용!
      "firmware_support": {
        "min_version": "1.0.0"
      }
    }
  ]
}
```

**장점**:
- 10줄 정도만 추가
- JSON 문법 오류는 자동 검증
- 기존 명령어 세트 재사용 가능
- 바로 테스트 가능

---

### 시나리오 2: 설정 값 검증

#### **기존 방식**
```python
# main_gui.py의 do_setting() 함수

def do_setting(self):
    ip = self.ip_input.text()

    # 1. wizcmdset으로 검증
    if not self.cmdset.isvalidparameter('LI', ip):
        # 2. 직접 에러 메시지 표시
        self.msg_invalid('LI')
        return False

    # 3. 명령어 패킷 생성
    cmd = self.wizmakecmd.make_command('LI', ip)

    # 4. 전송
    self.send_packet(cmd)
```

**문제점**:
- UI 코드와 검증 로직이 섞여있음
- 테스트하려면 UI를 띄워야 함
- 검증 로직 재사용 불가능

#### **신규 방식 (아직 미적용, 예제)**
```python
# 신규 방식으로 전환 시

def do_setting(self):
    # 1. 설정 값 수집
    config = {
        'LI': self.ip_input.text(),
        'SM': self.subnet_input.text(),
        'BR': self.baudrate_combo.currentData()
    }

    # 2. 장치 정보 생성
    device = DeviceInfo(
        mac_addr=self.curr_mac,
        model_id=self.curr_dev,
        firmware_version=self.curr_ver
    )

    # 3. 검증 (UI 독립적)
    errors = self.device_service.validate_config(device, config)

    if errors:
        # 4. 에러 표시 (Adapter를 통해)
        for cmd_code, error_msg in errors.items():
            self.qt_adapter.highlight_invalid_field(cmd_code, error_msg)
        return False

    # 5. 전송 (기존 방식 사용)
    for cmd_code, value in config.items():
        cmd = self.wizmakecmd.make_command(cmd_code, value)
        self.send_packet(cmd)
```

**장점**:
- 검증 로직을 UI 없이 테스트 가능
- 다른 UI (Web, CLI)에서도 동일한 검증 로직 사용
- 에러 메시지가 JSON에 정의되어 일관성 유지

---

### 시나리오 3: 펌웨어 버전별 명령어 지원

#### **기존 방식**
```python
# wizcmdset.py

class Wizcmdset:
    def get_commands(self, firmware_version):
        # 버전 비교를 직접 구현
        commands = self.base_commands.copy()

        if self._version_compare(firmware_version, '1.4.4') >= 0:
            # Modbus 명령어 추가
            commands['MB'] = ['Modbus', 'RW', {...}, 'combo']
            commands['MP'] = ['Modbus Port', 'RW', {...}, 'ipport']

        if self._version_compare(firmware_version, '1.1.8') >= 0:
            # 보안 명령어 추가
            commands['SD'] = ['MQTT SSL', 'RW', {...}, 'combo']
            # ... 10개 이상 추가

        return commands
```

**문제점**:
- 버전별 명령어 추가가 코드로 하드코딩됨
- 새 버전 나올 때마다 코드 수정 필요

#### **신규 방식**
```json
// config/devices/devices_sample.json

{
  "device_models": [
    {
      "model_id": "WIZ750SR",
      "firmware_support": {
        "version_overrides": {
          "1.4.4": {
            "added_commands": ["MB", "MP"],
            "description": "Modbus support added"
          },
          "1.1.8": {
            "added_commands": ["SD", "DD", "SE", "PN", "EC"],
            "description": "Security features added"
          }
        }
      }
    }
  ]
}
```

**사용 예시**:
```python
# 펌웨어 1.0.0
commands = service.get_commands_for_device('WIZ750SR', '1.0.0')
# → 36개 명령어 (기본)

# 펌웨어 1.4.4
commands = service.get_commands_for_device('WIZ750SR', '1.4.4')
# → 38개 명령어 (MB, MP 추가)

# 펌웨어 1.1.8
commands = service.get_commands_for_device('WIZ750SR', '1.1.8')
# → 43개 명령어 (보안 기능 추가)
```

**장점**:
- 버전 정보를 JSON에서 관리
- 코드 수정 없이 새 버전 지원 가능
- 버전별 차이를 한눈에 파악 가능

---

## 📁 파일 구조

### 새로 추가된 파일

```
WIZnet-S2E-Tool-GUI/
│
├── config/                          # 설정 파일 (새로 추가)
│   ├── schemas/
│   │   └── device_model_schema.json # JSON 구조 정의
│   └── devices/
│       └── devices_sample.json      # ★ 여기서 장치/명령어 정의
│
├── core/                            # 핵심 로직 (새로 추가)
│   ├── device_registry.py           # 장치 모델 관리
│   ├── models/
│   │   ├── command.py               # 명령어 클래스
│   │   ├── device_model.py          # 장치 모델 클래스
│   │   └── device_config.py         # 설정 데이터 클래스
│   └── services/
│       └── device_service.py        # ★ 비즈니스 로직 (검증 등)
│
├── adapters/                        # UI 어댑터 (새로 추가)
│   ├── base_adapter.py              # UI 추상 인터페이스
│   └── qt_adapter.py                # Qt 전용 구현
│
├── main_gui.py                      # 기존 파일 (65줄 추가)
│   # _init_new_architecture() 메서드 추가
│   # self.device_service, self.qt_adapter 사용 가능
│
└── [기존 파일들...]
    ├── wizcmdset.py                 # 기존: 명령어 세트 (아직 사용 중)
    ├── WIZMakeCMD.py                # 기존: 패킷 생성 (아직 사용 중)
    └── ...
```

---

## 🔧 실제 사용 시나리오

### 시나리오 A: 새 장치 "W55RP20-S2E-4CH" 추가

**요구사항**: 4채널 Serial 지원하는 새 장치 추가

**방법**:

1. `config/devices/devices_sample.json` 편집:

```json
{
  "device_models": [
    // ... 기존 장치들 ...
    {
      "model_id": "W55RP20-S2E-4CH",
      "display_name": "W55RP20 S2E 4-Channel",
      "category": "4-port",
      "command_set": "w55rp20_extended",  // 기존 W55RP20 명령어 재사용
      "base_model": "W55RP20-S2E",        // 기본 모델 상속
      "firmware_support": {
        "min_version": "1.0.0",
        "added_commands": {
          "1.0.0": {
            "added_commands": ["C3", "C4"],  // 채널 3, 4 명령어만 추가
            "description": "4-channel support"
          }
        }
      }
    }
  ]
}
```

2. 검증:
```bash
python scripts/validate_config.py
```

3. 실행:
```bash
python main_gui.py
```

4. 로그 확인:
```
[INFO] [New Architecture] Loaded device registry: 5 models
[INFO] [New Architecture] Available models: ..., W55RP20-S2E-4CH
```

**소요 시간**: 5분
**코드 수정**: 0줄

---

### 시나리오 B: IP 주소 검증 로직 수정

**요구사항**: IP 주소가 사설 IP 대역(192.168.x.x, 10.x.x.x)인지 추가 검증

**기존 방식**: `wizcmdset.py`의 `isvalidparameter()` 함수 수정 필요 (50줄+)

**신규 방식**:

1. `config/devices/devices_sample.json`에서 검증 패턴 수정:

```json
{
  "command_sets": [
    {
      "name": "common",
      "commands": [
        {
          "code": "LI",
          "name": "Local IP",
          "pattern": "^(192\\.168\\.|10\\.)\\d{1,3}\\.\\d{1,3}$",  // 사설 IP만 허용
          "access": "RW",
          "ui_widget": "ipaddr"
        }
      ]
    }
  ]
}
```

2. 즉시 적용됨 (재시작만 하면 됨)

**소요 시간**: 1분
**코드 수정**: 0줄

---

### 시나리오 C: 명령어 옵션 값 추가

**요구사항**: Baudrate에 921600 옵션 추가

**기존 방식**: `wizcmdset.py`에서 하드코딩된 딕셔너리 수정

**신규 방식**:

```json
{
  "commands": [
    {
      "code": "BR",
      "name": "Baudrate",
      "options": {
        "0": "300",
        "1": "600",
        "2": "1200",
        // ... 기존 옵션들 ...
        "12": "921600"  // 새 옵션 추가
      }
    }
  ]
}
```

**소요 시간**: 30초
**코드 수정**: 0줄

---

## 🚀 마이그레이션 가이드

### 현재 상태 확인

```python
# main_gui.py 실행 시 로그 확인

if self.use_new_architecture:
    print("✅ 새 아키텍처 사용 중")
    print(f"모델 수: {len(self.device_service.list_device_models())}")
else:
    print("⚠️ Legacy mode 사용 중")
```

### 기능별 전환 방법

#### 1단계: 설정 검증만 새 아키텍처로 전환

**파일**: `main_gui.py`의 `do_setting()` 함수

```python
def do_setting(self):
    # 기존 방식 (현재)
    if not self.cmdset.isvalidparameter('LI', ip_value):
        self.msg_invalid('LI')
        return False

    # 새 방식으로 전환 (추가)
    if self.use_new_architecture:
        device = DeviceInfo(
            mac_addr=self.curr_mac,
            model_id=self.curr_dev,
            firmware_version=self.curr_ver
        )
        config = {'LI': ip_value, 'SM': subnet_value, ...}
        errors = self.device_service.validate_config(device, config)

        if errors:
            for cmd_code, error_msg in errors.items():
                self.qt_adapter.highlight_invalid_field(cmd_code, error_msg)
            return False
    else:
        # Legacy 검증
        if not self.cmdset.isvalidparameter('LI', ip_value):
            self.msg_invalid('LI')
            return False
```

**효과**:
- 검증 로직이 UI 독립적으로 작동
- 테스트 가능
- 다른 UI에서도 재사용 가능

#### 2단계: 장치 정보 표시 전환

**파일**: `main_gui.py`의 `get_search_result()` 함수

```python
def get_search_result(self):
    # 장치 검색 후...

    if self.use_new_architecture:
        # 새 방식: Adapter를 통해 표시
        devices = []
        for dev_info in search_results:
            devices.append(DeviceInfo(
                mac_addr=dev_info['mac'],
                model_id=dev_info['model'],
                firmware_version=dev_info['version'],
                ip_addr=dev_info['ip']
            ))

        self.qt_adapter.show_devices(devices)
    else:
        # Legacy 방식
        for row, dev_info in enumerate(search_results):
            self.list_device.setItem(row, 0, QTableWidgetItem(dev_info['mac']))
            # ... 나머지 UI 업데이트
```

**효과**:
- UI 업데이트 로직 분리
- 장치 정보를 데이터 클래스로 표준화

#### 3단계: 완전 전환

모든 기능을 새 아키텍처로 전환 후:

```python
# wizcmdset.py 제거
# WIZMakeCMD.py는 네트워크 계층으로 남김

# main_gui.py
self.device_service = DeviceService(registry)
self.qt_adapter = QtAdapter(self)
# self.cmdset 삭제
```

---

## 🧪 테스트 방법

### 1. 설정 파일 검증
```bash
python scripts/validate_config.py
```

### 2. Core 로직 테스트
```bash
python tests/test_registry.py
python tests/test_adapter.py
```

### 3. 통합 테스트
```bash
python tests/test_integration.py
```

### 4. 실제 애플리케이션 테스트
```bash
python main_gui.py
# 로그에서 [New Architecture] 확인
```

---

## 📝 자주 묻는 질문

### Q1: 기존 코드가 깨지나요?
**A**: 아니요. 새 아키텍처는 기존 코드와 병행 실행됩니다. `self.use_new_architecture` 플래그로 제어합니다.

### Q2: 언제 완전히 전환하나요?
**A**: 선택 사항입니다. 현재는:
- 새 아키텍처: 자동 초기화됨, 사용 가능한 상태
- 기존 코드: 여전히 메인 로직 담당

기능별로 천천히 전환하거나, 그대로 유지해도 됩니다.

### Q3: JSON 수정하면 바로 적용되나요?
**A**: 네, 애플리케이션을 재시작하면 JSON이 다시 로드됩니다.

### Q4: 성능이 느려지나요?
**A**: 아니요. JSON 로드는 시작 시 1회만 수행되고, 검증 로직은 기존과 동일하거나 더 빠릅니다.

### Q5: 어떤 파일을 수정하면 되나요?
**장치/명령어 추가**: `config/devices/devices_sample.json`
**UI 커스터마이징**: `adapters/qt_adapter.py`
**비즈니스 로직 추가**: `core/services/device_service.py`
**검증 로직**: JSON의 `pattern` 필드 수정

---

## 🎯 요약

### 핵심 메시지
**"JSON 편집으로 새 장치 추가, 코드 수정은 거의 불필요"**

### 실용적 가이드라인

| 작업 | 기존 방식 | 신규 방식 | 시간 절감 |
|------|----------|----------|----------|
| 새 장치 추가 | 100줄 코드 수정 | 10줄 JSON 추가 | 90% ↓ |
| 명령어 옵션 추가 | 코드 수정 필요 | JSON 1줄 수정 | 95% ↓ |
| 검증 로직 수정 | 함수 재작성 | JSON pattern 수정 | 80% ↓ |
| 펌웨어 버전 지원 | 조건문 추가 | JSON override 추가 | 70% ↓ |

### 지금 바로 할 수 있는 일

1. **새 장치 추가 테스트**:
   - `config/devices/devices_sample.json` 열기
   - 마지막 장치 복사해서 이름만 바꾸기
   - `python scripts/validate_config.py` 실행
   - `python main_gui.py` 실행해서 로그 확인

2. **검증 로직 커스터마이징**:
   - JSON에서 `LI` 명령어의 `pattern` 필드 수정
   - 재시작 후 IP 입력 테스트

3. **기존 기능 유지하면서 실험**:
   - `self.use_new_architecture` 플래그는 기본 True
   - 문제 생기면 자동으로 legacy mode로 fallback
   - 안전하게 실험 가능

---

**작성일**: 2026-01-09
**버전**: v1.5.8.1 + New Architecture v2.0
**문의**: GitHub Issues
