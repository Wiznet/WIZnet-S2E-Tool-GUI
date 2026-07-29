# Phase 5: DeviceSpec YAML - Research

**Researched:** 2026-05-18
**Domain:** YAML 스키마 설계 + WIZ550 구조체 필드 매핑
**Confidence:** HIGH (모든 핵심 정보 코드베이스에서 직접 확인)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: 스키마 전략 — 별도 WIZ550 스키마**
- `specs/schema/device.wiz550.schema.json` 신규 작성
- `family == "wiz550"` → device.wiz550.schema.json 라우팅
- `validate_schemas.py`에 라우팅 로직 추가 (기존 검증 로직 변경 없음)

**D-02: YAML 최상위 구조**
- `name`, `display_name`, `aliases`, `family: wiz550`, `channels`, `protocol{}`, `ui.sections[]`
- `protocol.handler`, `protocol.port`, `protocol.product_code`, `protocol.config_size`, `protocol.parser`, `protocol.builder`

**D-03: UI 섹션 구조 — `ui.sections` (tabs 아님)**
- 최상위: `ui.sections: list` (id, label, fields, condition)
- field type: `ip`, `text`, `uint16`, `dropdown`, `checkbox`, `readonly`
- `choices`는 정수키 → 문자열값 매핑

**D-04: WIZ550S2E 가변 구조 — `condition` 필드**
- `condition: mqtt` — fw_ver[1] 홀수 AND len >= 232
- `condition: modbus` — fw_ver[1] 짝수 AND len >= 164

**D-05: WIZ550WEB 비활성 필드 — `disabled: true` 마커**
- 비활성 필드: `working_mode`, `remote_ip`, `remote_port`, `local_port`, `at_cmd`

**D-06: 각 YAML 섹션 구성**
- WIZ550SR: network / serial / options
- WIZ550S2E: network / serial / options / mqtt(condition) / modbus(condition)
- WIZ550WEB: network / uart0 / uart1 / options

### Claude's Discretion

- WIZ550SR `data_bits` 표현: `choices: {3: "8-bit"}` 단일 선택 또는 `type: readonly, value: "8-bit"` — 구현자 판단
- baud_rate choices 상한: SR/S2E = 460800bps (인덱스 11까지), WEB = 파서 확인 후 결정
- WIZ550WEB의 UART 파라미터 상세 제약 — WIZ550Profile.parse_web() 반환 필드 기준 작성

### Deferred Ideas (OUT OF SCOPE)

- WIZ550WEB의 UART1 포트 실제 동작 — 실물 장치 확보 후 확인 (UAT-02)
- `device_spec_loader.py`에 WIZ550 YAML 로더 통합 — Phase 6 구현 범위
- 기존 WIZ5xxSR / WIZ1x0SR UI 전체에 DESIGN.md 토큰 소급 적용 — 별도 Phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPEC-01 | `specs/devices/WIZ550SR.yaml` — DeviceSpec 스키마 준수, handler=WIZ550MSGHandler, Network/Serial/Options 위젯 그룹 | WIZ550Profile.py의 `_parse_base_162()` 반환 dict 필드명 전체 확인 완료 |
| SPEC-02 | `specs/devices/WIZ550S2E.yaml` — MQTT/Modbus 조건부 섹션 포함, fw_ver 기반 표시 정책 정의 | `parse_s2e()` 의 MQTT/Modbus 확장 필드명 확인 완료 |
| SPEC-03 | `specs/devices/WIZ550WEB.yaml` — 비활성 필드 명시, UART0/UART1 2채널 위젯 | `parse_web()` 반환 dict 전체 필드명 확인 완료 |
| SPEC-04 | 3개 YAML 모두 스키마 검증 통과 (`uv run python validate_schemas.py`) | validate_schemas.py 라우팅 패턴 분석 완료; WIZ550 전용 스키마 라우팅 추가 방법 확인 |
</phase_requirements>

---

## Summary

Phase 5의 핵심 작업은 두 가지다. (1) WIZ550 전용 JSON Schema 작성, (2) 3개 YAML 파일 작성. 이 두 작업은 WIZ550Profile.py에서 확인한 정확한 필드명을 기반으로 한다.

**모든 필드명은 WIZ550Profile.py에서 직접 검증했다.** [VERIFIED: 코드베이스 직접 읽기] `_parse_base_162()` 함수의 반환 dict 키, `parse_web()` 반환 dict 키, S2E 확장 키가 모두 확인되었으므로 YAML field.id를 이 키와 1:1로 맞추면 Phase 6에서 `dev_info[field.id]`로 바로 값을 조회할 수 있다.

`validate_schemas.py`의 수정은 최소한의 변경으로 가능하다. `validate_all()` 함수 내에서 각 YAML을 로드한 뒤 `family` 값을 확인하여 스키마를 선택하는 분기 단 4~5줄이 전부다. 기존 WIZ750SR 등의 검증 흐름은 건드리지 않는다.

**Primary recommendation:** WIZ550Profile.py 필드명을 YAML field.id의 단일 진실 소스로 사용. YAML 먼저 작성 → 스키마 작성 → validate_schemas.py 수정 → 검증 통과 순서로 진행.

---

## 핵심 발견: WIZ550Profile.py 필드명 완전 목록

> [VERIFIED: WIZ550Profile.py 직접 읽기]

### SR/S2E 공유 기본 162B 필드 (`_parse_base_162` 반환 dict)

```
packet_size       int      (H) — 패킷 크기, UI 불필요
module_type       str(hex) (3s.hex()) — '020000' / '000000' / '010200', UI 불필요
module_name       str      (25s) — 장치 이름, UI 불필요 (장치 식별 용도)
fw_ver            bytes    (3s) — 버전 바이트, UI 불필요 (fw_str 사용)
fw_str            str      — '1.0.0' 형식, readonly 표시용
mac               str      — 'XX:XX:XX:XX:XX:XX', readonly
local_ip          str      — '0.0.0.0', ip
gateway           str      — '0.0.0.0', ip
subnet            str      — '255.255.255.0', ip
working_mode      int      — 0=TCP Client/1=TCP Server/2=UDP, dropdown
state             int      — 내부 상태, UI 불필요
remote_ip         str      — '0.0.0.0', ip
local_port        int      — H (0~65535), uint16
remote_port       int      — H (0~65535), uint16
inactivity        int      — H, uint16 (ms), options 섹션
reconnection      int      — H, uint16 (ms), options 섹션
packing_time      int      — H, uint16, options 섹션 (Phase 5 스코프 외 — 단순 포함)
packing_size      int      — B, uint16로 표현 가능
packing_delimiter bytes    — 4s (미사용 UI)
packing_delimiter_length int — B
packing_data_appendix    int — B
baud_rate         int      — I (4B LE 실제 bps 값), dropdown choices 인덱스 아님 주의
data_bits         int      — B (값: 3=8bit, 실제 비트수 아님)
parity            int      — B (0=None, 1=Odd, 2=Even), dropdown
stop_bits         int      — B (0=1bit, 1=2bit), dropdown
flow_control      int      — B (0=None, 1=XON/XOFF, 2=RTS/CTS), dropdown
pw_setting        str      — 10s, text
pw_connect        str      — 10s, text
dhcp_use          int      — B, checkbox (0=Static, 1=DHCP)
dns_use           int      — B, checkbox
dns_server_ip     str      — ip
dns_domain_name   str      — 50s, text
serial_command    int      — B (at_cmd 플래그), checkbox
serial_trigger    bytes    — 3s (raw, UI 불필요 or readonly)
_proto            str      — 'wiz550', 내부용
```

**주의: `baud_rate`는 실제 bps 정수값 (115200 등)이다. choices의 인덱스 번호가 아님.** Phase 6 UI 빌드에서 choices 역매핑 처리 필요.

### WIZ550S2E 확장 필드

MQTT 확장 (s2e_variant='mqtt'):
```
mqtt_user       str  — 10s, text
mqtt_pw         str  — 10s, text
mqtt_pub_topic  str  — 25s, text     ← CONTEXT.md에는 'publish_topic'으로 표기, 실제는 'mqtt_pub_topic'
mqtt_sub_topic  str  — 25s, text     ← CONTEXT.md에는 'subscribe_topic'으로 표기, 실제는 'mqtt_sub_topic'
s2e_variant     str  — 'mqtt'/'modbus'/'base', 내부용
```

Modbus 확장 (s2e_variant='modbus'):
```
modbus_use      int  — B, checkbox
modbus_mode     int  — B, dropdown (0=RTU, 1=ASCII)
```

### WIZ550WEB 133B 전용 필드 (`parse_web` 반환 dict)

```
packet_size         int     — H, 내부용
module_type         str     — '010200', 내부용
module_name         str     — 25s, 내부용
fw_ver              bytes   — 3s, 내부용
fw_str              str     — readonly
mac                 str     — readonly
local_ip            str     — ip
gateway             str     — ip
subnet              str     — ip
uart0_baud_rate     int     — I (실제 bps), dropdown
uart0_data_bits     int     — B (값 3=8bit), dropdown 또는 readonly
uart0_parity        int     — B, dropdown
uart0_stop_bits     int     — B, dropdown
uart0_flow_control  int     — B, dropdown
uart1_baud_rate     int     — I, dropdown
uart1_data_bits     int     — B, dropdown
uart1_parity        int     — B, dropdown
uart1_stop_bits     int     — B, dropdown
uart1_flow_control  int     — B, dropdown
pw_setting          str     — 10s, text
                            ← pw_connect 없음! (WEB 구조체 미포함)
dhcp_use            int     — B, checkbox
dns_use             int     — B, checkbox
dns_server_ip       str     — ip
dns_domain_name     str     — 50s, text
device_type         str     — 'WIZ550WEB', 내부용
_proto              str     — 'wiz550', 내부용
```

**WEB에는 `pw_connect`, `working_mode`, `remote_ip`, `remote_port`, `local_port`, `at_cmd(serial_command)` 필드 자체가 없다.** 이것들은 YAML에 `disabled: true`로 포함해야 SPEC-03을 충족한다.

---

## Standard Stack

### 기존 인프라 재사용

| 구성요소 | 현재 상태 | Phase 5 사용 |
|----------|-----------|-------------|
| `validate_schemas.py` | jsonschema 4.26.0 [VERIFIED: pip] 사용 중 | 라우팅 분기 4~5줄 추가만 |
| `specs/schema/device.schema.json` | JSON Schema draft-07 | WIZ550 스키마 설계 템플릿 |
| `specs/devices/WIZ750SR.yaml` | 기존 YAML 패턴 | WIZ550 YAML 구조 참조 |

### 의존성

```bash
# 이미 설치됨 (uv 환경)
jsonschema==4.26.0   # validate_schemas.py에서 사용 중 [VERIFIED]
pyyaml               # 이미 사용 중 [VERIFIED]
```

추가 패키지 불필요. Phase 5는 순수 파일 작성 작업.

---

## Architecture Patterns

### 1. device.wiz550.schema.json 구조 설계

기존 `device.schema.json`을 참조하되 `command_groups`, `search_cmd_order`, `overrides`, `fw_constraints` 제거. 핵심 구조:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WIZnet WIZ550 Device Spec",
  "type": "object",
  "required": ["name", "family", "channels", "protocol", "ui"],
  "additionalProperties": false,
  "properties": {
    "name":         {"type": "string"},
    "display_name": {"type": "string"},
    "aliases":      {"type": "array", "items": {"type": "string"}},
    "family":       {"type": "string", "const": "wiz550"},
    "channels":     {"type": "integer", "minimum": 1, "maximum": 2},
    "protocol": {
      "type": "object",
      "required": ["handler", "port", "product_code", "config_size", "parser", "builder"],
      "properties": {
        "handler":      {"type": "string"},
        "port":         {"type": "integer"},
        "product_code": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3},
        "config_size":  {"type": "integer"},
        "parser":       {"type": "string"},
        "builder":      {"type": "string"}
      }
    },
    "ui": {
      "type": "object",
      "required": ["sections"],
      "properties": {
        "sections": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "label", "fields"],
            "properties": {
              "id":        {"type": "string"},
              "label":     {"type": "string"},
              "condition": {"type": "string"},
              "fields":    {"type": "array", "items": {"$ref": "#/definitions/field"}}
            }
          }
        }
      }
    }
  },
  "definitions": {
    "field": {
      "type": "object",
      "required": ["id", "label", "type"],
      "additionalProperties": false,
      "properties": {
        "id":       {"type": "string"},
        "label":    {"type": "string"},
        "type":     {"type": "string", "enum": ["ip","text","uint16","dropdown","checkbox","readonly"]},
        "choices":  {"type": "object"},
        "disabled": {"type": "boolean"},
        "value":    {}
      }
    }
  }
}
```

### 2. validate_schemas.py 라우팅 변경 — 최소 수정

기존 `validate_all()` 함수에서 device YAML 루프 부분만 변경:

```python
# 변경 전
device_schema = json.loads((SCHEMA_DIR / "device.schema.json").read_text(encoding="utf-8"))
# ...
for f in sorted((SPECS_DIR / "devices").glob("*.yaml")):
    data = yaml.safe_load(...)
    jsonschema.validate(instance=data, schema=device_schema)  # 단일 스키마

# 변경 후 (라우팅 추가)
device_schema     = json.loads((SCHEMA_DIR / "device.schema.json").read_text(...))
wiz550_schema     = json.loads((SCHEMA_DIR / "device.wiz550.schema.json").read_text(...))
# ...
for f in sorted((SPECS_DIR / "devices").glob("*.yaml")):
    data = yaml.safe_load(...)
    # family 기반 스키마 선택
    schema = wiz550_schema if data.get("family") == "wiz550" else device_schema
    jsonschema.validate(instance=data, schema=schema)
```

**변경 범위: validate_schemas.py 약 5줄.** 기존 YAML(WIZ750SR 등)은 `family == "one_port"` 이므로 영향 없음. [VERIFIED: 기존 YAML의 family 값 확인]

### 3. YAML 파일 구조 — WIZ550SR.yaml 핵심 패턴

```yaml
name: WIZ550SR
display_name: "WIZ550SR"
aliases:
  - "WIZ550SR"
family: wiz550
channels: 1

protocol:
  handler: WIZ550Searcher    # WIZ550MSGHandler.py 클래스
  port: 6550
  product_code: [0x02, 0x00, 0x00]
  config_size: 162
  parser: parse_sr
  builder: build_sr

ui:
  sections:
    - id: network
      label: "Network"
      fields:
        - {id: mac,          label: "MAC",         type: readonly}
        - {id: dhcp_use,     label: "DHCP",        type: checkbox}
        - {id: local_ip,     label: "IP Address",  type: ip}
        - {id: subnet,       label: "Subnet Mask", type: ip}
        - {id: gateway,      label: "Gateway",     type: ip}
        - {id: dns_server_ip,label: "DNS Server",  type: ip}
        - {id: working_mode, label: "Working Mode",type: dropdown,
           choices: {0: "TCP Client", 1: "TCP Server", 2: "UDP"}}
        - {id: local_port,   label: "Local Port",  type: uint16}
        - {id: remote_ip,    label: "Remote IP",   type: ip}
        - {id: remote_port,  label: "Remote Port", type: uint16}
    - id: serial
      label: "Serial"
      fields:
        - {id: baud_rate, label: "Baud Rate", type: dropdown,
           choices: {300: "300 bps", 600: "600 bps", 1200: "1200 bps",
                     2400: "2400 bps", 4800: "4800 bps", 9600: "9600 bps",
                     19200: "19200 bps", 38400: "38400 bps", 57600: "57600 bps",
                     115200: "115200 bps", 230400: "230400 bps", 460800: "460800 bps"}}
        - {id: data_bits,    label: "Data Bits",   type: readonly, value: "8-bit"}
        - {id: parity,       label: "Parity",      type: dropdown,
           choices: {0: "None", 1: "Odd", 2: "Even"}}
        - {id: stop_bits,    label: "Stop Bits",   type: dropdown,
           choices: {0: "1 bit", 1: "2 bits"}}
        - {id: flow_control, label: "Flow Control",type: dropdown,
           choices: {0: "None", 2: "RTS/CTS"}}
    - id: options
      label: "Options"
      fields:
        - {id: pw_setting,    label: "Search PW",   type: text}
        - {id: pw_connect,    label: "Connect PW",  type: text}
        - {id: serial_command,label: "AT Command",  type: checkbox}
```

### 4. baud_rate choices 설계 주의사항

**baud_rate 필드의 `id: baud_rate`는 실제 bps 정수값을 저장한다.** choices 키도 정수 bps값이어야 Phase 6에서 `dev_info['baud_rate']`를 choices 키로 직접 조회할 수 있다.

```yaml
# 올바른 설계 (choices 키 = 실제 bps값)
choices:
  300: "300 bps"
  9600: "9600 bps"
  115200: "115200 bps"
  460800: "460800 bps"
```

**CONTEXT.md D-03의 choices 예시 (0~11 인덱스)는 WIZ750SR 스타일이다.** WIZ550의 `baud_rate`는 인덱스가 아닌 실제 bps값이므로 choices 키를 bps값으로 설계해야 한다. [VERIFIED: WIZ550Profile.py SR_FORMAT `baud_rate: 'I' (unsigned int 4B LE)`]

### 5. flow_control choices 제약

WIZ550SR은 `flow_control: 1` (XON/XOFF)을 지원하지 않는다. choices에 0(None)과 2(RTS/CTS)만 포함. [VERIFIED: REQUIREMENTS.md PROF-01 "flow_control=None/RTS·CTS만"]

---

## Don't Hand-Roll

| 문제 | 직접 구현 금지 | 사용할 것 | 이유 |
|------|--------------|---------|------|
| YAML 파싱 | 커스텀 파서 | PyYAML (이미 사용 중) | 이미 인프라 완비 |
| JSON Schema 검증 | 수동 검증 코드 | jsonschema 4.26.0 | 이미 validate_schemas.py에서 사용 |
| 스키마 라우팅 | 별도 검증 스크립트 | validate_schemas.py 분기 추가 | 4~5줄로 충분 |

---

## 중요 발견: CONTEXT.md vs. 실제 코드 불일치

### MQTT 필드명 불일치

CONTEXT.md D-04에 명시된 YAML 예시:
```yaml
- {id: publish_topic,   ...}
- {id: subscribe_topic, ...}
```

WIZ550Profile.py parse_s2e() 실제 키:
```python
d['mqtt_pub_topic'] = _cstr_to_str(mqtt_pub)
d['mqtt_sub_topic'] = _cstr_to_str(mqtt_sub)
```

**YAML field.id를 `mqtt_pub_topic`/`mqtt_sub_topic`으로 작성해야 Phase 6에서 `dev_info[field.id]`가 동작한다.** [VERIFIED: WIZ550Profile.py 직접 읽기]

### WIZ550MSGHandler 클래스명 확인

WIZ550MSGHandler.py에는 4개 클래스가 있다:
- `WIZ550Searcher` — DISCOVERY_ALL 브로드캐스트
- `WIZ550Getter` — GET_INFO 유니캐스트
- `WIZ550Setter` — SET_INFO 유니캐스트
- `WIZ550Resetter` — REMOTE_RESET/FACTORY_RESET

`protocol.handler` 필드에 어떤 값을 쓸지는 Phase 6에서 로더가 어떻게 해석하는지에 따라 다르다. 로더가 아직 구현되지 않으므로 (`device_spec_loader.py`가 WIZ550를 인식하지 않음) 대표 클래스명 `WIZ550Searcher` 또는 모듈명 `WIZ550MSGHandler`를 기록하면 Phase 6에서 실제 사용 시 정확히 매핑한다.

---

## Common Pitfalls

### Pitfall 1: baud_rate choices 키를 인덱스로 작성

**무엇이 잘못되는가:** WIZ750SR 스타일(`"0": "300 bps"`, `"1": "600 bps"`)로 choices를 작성하면 Phase 6에서 `dev_info['baud_rate']`(= 115200)을 키로 조회할 때 매칭되지 않음
**근본 원인:** WIZ750SR은 BR 커맨드 응답이 인덱스("12" = 115200)지만, WIZ550은 baud_rate가 실제 bps 정수값
**예방:** choices 키를 실제 bps값으로 작성: `115200: "115200 bps"`
**경보:** Phase 6 QComboBox 값 조회 시 빈 항목이 선택됨

### Pitfall 2: WEB의 pw_connect를 YAML에 포함 시도

**무엇이 잘못되는가:** WIZ550WEB 133B 구조체에는 `pw_connect` 필드가 없음. YAML에 일반 필드로 넣으면 Phase 6에서 `dev_info.get('pw_connect')` → None → 빈칸 표시 → Apply 시 build_web()에 없는 키 전달
**근본 원인:** WEB 구조체가 SR보다 29B 작은 133B. `pw_connect`는 그 차이의 일부
**예방:** WEB YAML의 options 섹션에는 `pw_setting`만 포함. `pw_connect`는 아예 포함하지 않음 (disabled도 아님)
**참조:** WIZ550Profile.py parse_web() 주석 "pw_connect 없음 (WEB 구조체 미포함 — Pitfall 6)"

### Pitfall 3: additionalProperties: false 스키마에서 `value` 필드 누락

**무엇이 잘못되는가:** `type: readonly, value: "8-bit"` 패턴을 사용하는 경우 스키마의 field `$ref`에 `value` 프로퍼티가 없으면 검증 실패
**예방:** device.wiz550.schema.json의 field definitions에 `"value": {}` (any type) 포함

### Pitfall 4: WIZ550WEB disabled 필드를 섹션에 포함 vs 미포함

**무엇이 잘못되는가:** SPEC-03 요구사항은 "비활성 필드가 YAML에 명시적으로 정의됨". 필드를 아예 빠뜨리면 SPEC-03 미충족
**예방:** `working_mode`, `remote_ip`, `remote_port`, `local_port`를 network 섹션에 `disabled: true`로 포함. `serial_command(at_cmd)`를 options 섹션에 `disabled: true`로 포함

### Pitfall 5: validate_schemas.py에서 wiz550 스키마 로드 실패 시 예외 처리 누락

**무엇이 잘못되는가:** `device.wiz550.schema.json` 파일이 없는 상태에서 validate_all()이 FileNotFoundError로 전체 종료
**예방:** wiz550 스키마 파일을 먼저 작성 후 validate_schemas.py 수정, 또는 try/except로 스키마 로드 실패 처리

---

## Code Examples

### WIZ550S2E.yaml 조건부 섹션 패턴

```yaml
# Source: CONTEXT.md D-04 + WIZ550Profile.py parse_s2e() 확인
- id: mqtt
  label: "MQTT"
  condition: mqtt
  fields:
    - {id: mqtt_user,      label: "MQTT Username",     type: text}
    - {id: mqtt_pw,        label: "MQTT Password",     type: text}
    - {id: mqtt_pub_topic, label: "Publish Topic",     type: text}
    - {id: mqtt_sub_topic, label: "Subscribe Topic",   type: text}

- id: modbus
  label: "Modbus"
  condition: modbus
  fields:
    - {id: modbus_use,  label: "Modbus Enable", type: checkbox}
    - {id: modbus_mode, label: "Modbus Mode",   type: dropdown,
       choices: {0: "RTU", 1: "ASCII"}}
```

### WIZ550WEB.yaml disabled 필드 패턴

```yaml
# Source: CONTEXT.md D-05 + WIZ550Profile.py parse_web() 확인
- id: network
  label: "Network"
  fields:
    - {id: mac,          label: "MAC",         type: readonly}
    - {id: dhcp_use,     label: "DHCP",        type: checkbox}
    - {id: local_ip,     label: "IP Address",  type: ip}
    - {id: subnet,       label: "Subnet Mask", type: ip}
    - {id: gateway,      label: "Gateway",     type: ip}
    - {id: dns_server_ip,label: "DNS Server",  type: ip}
    # WEB 구조체에 없는 필드 — disabled: true로 명시 (SPEC-03)
    - {id: working_mode, label: "Working Mode", type: dropdown, disabled: true,
       choices: {0: "TCP Client", 1: "TCP Server", 2: "UDP"}}
    - {id: remote_ip,    label: "Remote IP",   type: ip,     disabled: true}
    - {id: remote_port,  label: "Remote Port", type: uint16, disabled: true}
    - {id: local_port,   label: "Local Port",  type: uint16, disabled: true}
```

### validate_schemas.py 라우팅 변경 패턴

```python
# Source: validate_schemas.py 기존 코드 분석
def validate_all() -> None:
    device_schema = json.loads((SCHEMA_DIR / "device.schema.json").read_text(encoding="utf-8"))
    wiz550_schema = json.loads((SCHEMA_DIR / "device.wiz550.schema.json").read_text(encoding="utf-8"))  # 추가
    cmd_schema = json.loads((SCHEMA_DIR / "command-group.schema.json").read_text(encoding="utf-8"))
    # ...
    for f in sorted((SPECS_DIR / "devices").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        # 추가: family 기반 스키마 선택
        schema = wiz550_schema if data.get("family") == "wiz550" else device_schema
        jsonschema.validate(instance=data, schema=schema)
```

---

## Environment Availability

| 의존성 | 필요 이유 | 사용 가능 | 버전 | 대체 |
|--------|---------|---------|------|------|
| jsonschema | validate_schemas.py 스키마 검증 | ✓ | 4.26.0 | — |
| pyyaml | YAML 파싱 | ✓ | (확인됨) | — |
| pytest | 검증 테스트 | ✓ | 9.0.3 | — |

**Missing dependencies with no fallback:** 없음. 모든 의존성 사용 가능.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `protocol.handler: WIZ550Searcher`를 대표 클래스명으로 사용 | Standard Stack | Phase 6 로더가 다른 키 기대 시 매핑 수정 필요 — 하지만 Phase 6에서 로더 구현 시 이 키를 참조하도록 설계 가능하므로 실질적 위험 낮음 |
| A2 | WIZ550WEB의 uart0/uart1 baud_rate choices 상한을 SR/S2E와 동일한 460800bps로 가정 | YAML 설계 | WEB 장치 실제 스펙이 다를 경우 Phase 8 전 수정 필요. REQUIREMENTS.md PROF-03에 명시 없음 |
| A3 | WIZ550WEB의 data_bits를 SR처럼 8-bit 전용(`type: readonly, value: "8-bit"`)으로 가정 | Claude's Discretion | WEB가 다른 data_bits를 지원하면 dropdown 전환 필요 |

---

## Open Questions

1. **`protocol.handler` 값의 의미**
   - 현재 파악: WIZ550MSGHandler.py에 4개 클래스 존재 (Searcher/Getter/Setter/Resetter)
   - 불명확한 점: Phase 6 로더가 이 문자열을 어떻게 해석하는지 아직 결정 안 됨
   - 권장: `WIZ550MSGHandler` (모듈명)으로 기록, Phase 6에서 실제 매핑 결정
   - **RESOLVED (2026-05-18):** `protocol.handler: WIZ550MSGHandler` (모듈 파일명) 사용.
     WIZ550Searcher는 클래스명이고, Phase 6 로더가 `device_spec_loader.load(device_type)`에서
     device_type을 키로 라우팅하므로 모듈 파일명이 더 적합하다. 06-CONTEXT.md D-06의
     `_build_wiz550_panel()` 패턴과 일치. 플랜에서는 `WIZ550MSGHandler` 사용.

2. **baud_rate choices의 YAML 타입**
   - YAML에서 `115200: "115200 bps"` 형태로 작성 시 키가 정수로 파싱됨
   - Phase 6에서 `dev_info['baud_rate']`(int)와 비교 시 타입 일치 여부 확인 필요
   - 권장: YAML에 정수 키로 작성, Phase 6에서 `int(key)` 비교 처리
   - **RESOLVED (2026-05-18):** YAML 정수 키 115200 == `parse_sr()`/`parse_s2e()` 반환
     `baud_rate` (int, struct 'I' 언패킹) 직접 비교 가능. 타입 불일치 없음.
     실제 choices 값: 300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600,
     115200, 230400, 460800 [VERIFIED: WIZ550Profile.py _parse_base_162 구조체 확인]

---

## Validation Architecture

### 테스트 프레임워크

| 항목 | 값 |
|------|----|
| Framework | pytest 9.0.3 |
| Config file | (없음 — 프로젝트 루트에서 직접 실행) |
| Quick run command | `uv run python validate_schemas.py` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase 5 요구사항 → 테스트 맵

| REQ-ID | 동작 | 테스트 유형 | 자동화 명령 | 파일 존재 |
|--------|------|-----------|------------|---------|
| SPEC-01 | WIZ550SR.yaml 생성 + 스키마 통과 | schema validation | `uv run python validate_schemas.py` | ❌ Wave 0 |
| SPEC-02 | WIZ550S2E.yaml 생성 + 스키마 통과 | schema validation | `uv run python validate_schemas.py` | ❌ Wave 0 |
| SPEC-03 | WIZ550WEB.yaml disabled 필드 존재 확인 | yaml parse + assert | `uv run pytest tests/test_wiz550_spec.py -v` | ❌ Wave 0 |
| SPEC-04 | 3개 모두 validate_schemas.py 전체 통과 | integration | `uv run python validate_schemas.py` | ❌ Wave 0 |

### Sampling Rate

- **파일 작성 완료 시:** `uv run python validate_schemas.py`
- **Wave merge 전:** `uv run pytest tests/ -v`
- **Phase gate:** `validate_schemas.py` 종료 코드 0 확인

### Wave 0 Gaps

- [ ] `tests/test_wiz550_spec.py` — SPEC-03: WEB disabled 필드 존재 검증, YAML 필드명-프로파일 키 1:1 매핑 검증
- [ ] `specs/schema/device.wiz550.schema.json` — 스키마 파일 신규 작성
- [ ] `specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml` — 3개 YAML 신규 작성

---

## Sources

### Primary (HIGH confidence)
- `WIZ550Profile.py` — parse_sr/parse_s2e/parse_web 반환 dict 전체 필드명 직접 확인
- `validate_schemas.py` — 스키마 라우팅 변경 위치 및 패턴 직접 확인
- `specs/schema/device.schema.json` — WIZ550 스키마 설계 템플릿 직접 확인
- `.planning/phases/05-devicespec-yaml/05-CONTEXT.md` — 모든 locked decisions

### Secondary (MEDIUM confidence)
- `WIZ550MSGHandler.py` 클래스명 (WIZ550Searcher 등) — Phase 6 로더 해석 방식은 아직 미결정
- `tests/conftest.py` — data_bits 값 3 = 8-bit 패턴 확인 (fixture에서 `data_bits=3` 사용)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — 기존 인프라 전부 확인, 추가 패키지 없음
- YAML 필드 목록: HIGH — WIZ550Profile.py 코드에서 직접 추출
- Architecture: HIGH — validate_schemas.py 변경 패턴 직접 분석
- baud_rate choices 설계: HIGH — struct format 'I' (실제 bps값) 확인

**Research date:** 2026-05-18
**Valid until:** Phase 4 산출물(WIZ550Profile.py, WIZ550MSGHandler.py) 변경 시 재검토 필요
