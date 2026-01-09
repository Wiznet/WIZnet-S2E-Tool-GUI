# WIZnet S2E Tool v2.0 테스트 가이드

## 📋 목차

1. [환경 준비](#환경-준비)
2. [Phase 1-A 테스트](#phase-1-a-테스트)
3. [예상 결과](#예상-결과)
4. [문제 해결](#문제-해결)

---

## 환경 준비

### 1. Python 버전 확인
```bash
python --version
# 출력 예: Python 3.8.x 이상
```

### 2. 의존성 설치
```bash
cd d:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI
pip install packaging
```

### 3. 프로젝트 구조 확인
```bash
dir /b
```

**예상 출력**:
```
config/
core/
scripts/
tests/
REFACTORING_PROGRESS.md
TESTING_GUIDE.md
(기타 기존 파일들...)
```

---

## Phase 1-A 테스트

### 테스트 1: JSON 설정 파일 검증

**목적**: JSON 데이터 구조가 올바른지 확인

```bash
python scripts/validate_config.py --verbose
```

**예상 출력**:
```
[*] Validating WIZnet S2E Configuration...

[INFO] [OK] Loaded config from config\devices\devices_sample.json
Validating Schema Version...
[INFO] [OK] Schema version: 2.0.0

Validating Command Sets...
[INFO]   Validating command set: common
[INFO]   Validating command set: wiz75x_extended
[INFO]   Validating command set: security_base
[INFO] [OK] All 3 command sets valid

Validating Device Models...
[INFO]   Validating device model: WIZ750SR
[INFO]   Validating device model: W55RP20-S2E
[INFO]   Validating device model: W55RP20-S2E-2CH
[INFO]   Validating device model: IP20
[INFO] [OK] All 4 models valid

Validating Inheritance Chain...
[INFO] [OK] No circular inheritance detected

============================================================
[STATS] Configuration Statistics
============================================================
  Command Sets:   3
  Total Commands: 53
  Device Models:  4

  Device Models:
    - WIZ750SR             (ONE_PORT)
    - W55RP20-S2E          (SECURITY_ONE_PORT)
    - W55RP20-S2E-2CH      (SECURITY_TWO_PORT)
    - IP20                 (SECURITY_ONE_PORT)
============================================================

============================================================
[PASS] Validation PASSED
   0 warning(s)
============================================================
```

**성공 기준**:
- ✅ `[PASS] Validation PASSED`
- ✅ `0 warning(s)`
- ✅ 4개 장치 모델 로드
- ✅ 3개 명령어 세트 로드

---

### 테스트 2: Core 라이브러리 기능 테스트

**목적**: UI 없이 Core 라이브러리가 정상 작동하는지 확인

```bash
python tests/test_registry.py
```

**예상 출력**:
```
============================================================
WIZnet S2E Device Registry Test
============================================================

[*] Testing DeviceRegistry.load_from_file()...
[OK] Loaded 4 device models
[OK] Loaded 3 command sets

[*] Testing DeviceRegistry.get_model()...
[OK] WIZ750SR             - 36 commands, category: ONE_PORT
[OK] W55RP20-S2E          - 51 commands, category: SECURITY_ONE_PORT
[OK] W55RP20-S2E-2CH      - 53 commands, category: SECURITY_TWO_PORT
[OK] IP20                 - 51 commands, category: SECURITY_ONE_PORT

[*] Testing command inheritance...
[OK] WIZ750SR has 36 commands
[OK]   - MC (MAC address) inherited from common
[OK]   - TR (TCP Retransmission) from wiz75x_extended
[OK] W55RP20-S2E has 51 commands
[OK]   - OP extended with SSL/MQTT options
[OK]   - SD (Send Data at Connection) specific to W55RP20

[*] Testing firmware version support...
[OK] WIZ750SR v1.0.0: MB command = False
[OK] WIZ750SR v1.4.4: MB command = True
[OK] Firmware version override working correctly

[*] Testing command validation...
[OK] LI validation: '192.168.1.1' = True, '999.999.999.999' = False
[OK] MC validation: '00:08:DC:12:34:56' = True, 'invalid-mac' = False
[OK] BR option '12' = '115200'

[*] Testing UI generation hints...
[OK] Found 7 UI groups:
      advanced: 6 commands
      data_packing: 3 commands
      device_info: 4 commands
      gpio: 3 commands
      network: 9 commands
      security: 3 commands
      serial: 5 commands

============================================================
[PASS] All tests passed!
============================================================
```

**성공 기준**:
- ✅ `[PASS] All tests passed!`
- ✅ 모든 테스트 항목에 `[OK]` 표시
- ✅ 상속 테스트 통과 (common → wiz75x_extended)
- ✅ 펌웨어 버전별 명령어 테스트 통과 (MB 명령어)
- ✅ 검증 테스트 통과 (IP, MAC, Baud rate)

---

### 테스트 3: Python 인터랙티브 테스트

**목적**: Python 콘솔에서 직접 Core 라이브러리 사용

```bash
python
```

Python 콘솔에서:

```python
# 1. 레지스트리 로드
from core import DeviceRegistry

registry = DeviceRegistry('config/devices/devices_sample.json')
print(f"Loaded {len(registry.list_models())} models")

# 2. 특정 모델 가져오기
model = registry.get_model('WIZ750SR')
print(f"{model.display_name}: {len(model.commands)} commands")

# 3. 명령어 가져오기
cmd = model.get_command('LI')  # Local IP
print(f"Command: {cmd.name}")
print(f"Pattern: {cmd.pattern}")
print(f"UI Widget: {cmd.ui_widget}")

# 4. 값 검증
print(cmd.validate('192.168.1.1'))    # True
print(cmd.validate('999.999.999.999'))  # False

# 5. Baud rate 옵션
br_cmd = model.get_command('BR')
print(br_cmd.get_option_label('12'))  # '115200'

# 6. 펌웨어 버전별 명령어
cmds_v1_0_0 = model.get_commands_for_version('1.0.0')
cmds_v1_4_4 = model.get_commands_for_version('1.4.4')
print(f"v1.0.0: MB = {'MB' in cmds_v1_0_0}")  # False
print(f"v1.4.4: MB = {'MB' in cmds_v1_4_4}")  # True

# 종료
exit()
```

**예상 출력**:
```python
Loaded 4 models
WIZ750SR: 36 commands
Command: Local IP address
Pattern: ^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$
UI Widget: ip
True
False
115200
v1.0.0: MB = False
v1.4.4: MB = True
```

---

## 예상 결과

### ✅ 성공 시나리오

1. **테스트 1 (검증)**: `[PASS] Validation PASSED`, 0 warnings
2. **테스트 2 (Core)**: `[PASS] All tests passed!`
3. **테스트 3 (인터랙티브)**: 모든 명령어 정상 실행

### ❌ 실패 시나리오 예시

#### 문제 1: `ModuleNotFoundError: No module named 'packaging'`
**원인**: packaging 라이브러리 미설치

**해결**:
```bash
pip install packaging
```

#### 문제 2: `FileNotFoundError: Config file not found`
**원인**: 잘못된 경로

**해결**:
```bash
# 현재 디렉토리 확인
cd d:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI

# 파일 존재 확인
dir config\devices\devices_sample.json
```

#### 문제 3: `UnicodeEncodeError`
**원인**: Windows 콘솔 인코딩 문제 (이미 수정됨)

**확인**:
```bash
python scripts/validate_config.py
```
이모지(`✅`, `❌` 등)가 아닌 `[OK]`, `[ERROR]` 형태로 출력되어야 함

---

## 상세 테스트 항목

### 📝 체크리스트

**Phase 1-A 완료 확인**:

- [ ] 파일 존재 확인
  - [ ] `config/schemas/device_model_schema.json`
  - [ ] `config/devices/devices_sample.json`
  - [ ] `core/device_registry.py`
  - [ ] `core/models/command.py`
  - [ ] `scripts/validate_config.py`
  - [ ] `tests/test_registry.py`

- [ ] 검증 테스트 통과
  - [ ] `python scripts/validate_config.py` → PASS
  - [ ] 4개 장치 모델 로드
  - [ ] 3개 명령어 세트 로드
  - [ ] 0 errors, 0 warnings

- [ ] Core 테스트 통과
  - [ ] `python tests/test_registry.py` → PASS
  - [ ] 상속 테스트 통과
  - [ ] 펌웨어 버전 테스트 통과
  - [ ] 검증 테스트 통과
  - [ ] UI 힌트 테스트 통과

- [ ] 인터랙티브 테스트
  - [ ] Python에서 `from core import DeviceRegistry` 성공
  - [ ] 모델 로드 성공
  - [ ] 명령어 가져오기 성공
  - [ ] 값 검증 성공

---

## 문제 해결

### Windows 경로 문제

**증상**: `FileNotFoundError` 발생

**해결**:
```bash
# 절대 경로 사용
python -c "import os; print(os.path.abspath('config/devices/devices_sample.json'))"

# 또는 스크립트 내에서 경로 확인
python -c "from pathlib import Path; print(Path('config/devices/devices_sample.json').exists())"
```

### Python 버전 문제

**증상**: `SyntaxError` 또는 `ImportError`

**해결**:
```bash
# Python 3.8 이상 필요
python --version

# 여러 버전 설치된 경우
py -3.8 tests/test_registry.py
# 또는
python3.8 tests/test_registry.py
```

### Import 문제

**증상**: `ModuleNotFoundError: No module named 'core'`

**해결**:
```bash
# 프로젝트 루트에서 실행
cd d:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI

# PYTHONPATH 설정 (Windows CMD)
set PYTHONPATH=%CD%
python tests/test_registry.py

# PowerShell
$env:PYTHONPATH = $PWD
python tests/test_registry.py
```

---

## 빠른 테스트 (한 줄 명령어)

### Windows CMD
```bash
cd d:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI && python scripts/validate_config.py && python tests/test_registry.py
```

### PowerShell
```powershell
cd d:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI; python scripts/validate_config.py; python tests/test_registry.py
```

**예상 소요 시간**: 약 5-10초

**성공 시**: 두 테스트 모두 `[PASS]` 출력

---

## 다음 단계

테스트가 모두 통과하면 **Phase 1-B (Adapter 구현)** 로 진행 가능합니다.

### Phase 1-B 미리보기:
- BaseAdapter 인터페이스 정의
- QtAdapter 구현
- 기존 UI와 연결

---

**작성일**: 2026-01-07
**버전**: v2.0.0
**Phase**: 1-A 완료
