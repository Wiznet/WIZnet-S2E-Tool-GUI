# Phase 5: DeviceSpec YAML - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>

## Phase Boundary

`specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml` 3개 파일을 작성한다.
각 YAML은 Phase 6 `_build_wiz550_panel(device_type)` 함수의 데이터 소스로 사용된다:
- 프로토콜 메타데이터 (핸들러 클래스, 포트, product_code, 파서/빌더 함수명)
- UI 섹션 + 필드 전체 정의 (field_id, label, type, choices, condition, disabled)

WIZ550 장치는 text-command 기반이 아니므로 기존 `command_groups` / `search_cmd_order` 구조는 사용하지 않는다.
별도 WIZ550 전용 스키마를 작성하고 `validate_schemas.py`에 라우팅 로직을 추가하여 SPEC-04를 충족한다.

</domain>

<decisions>

## Implementation Decisions

### D-01: 스키마 전략 — 별도 WIZ550 스키마

- 기존 `device.schema.json`은 `family`(enum) + `command_groups`(minItems:1) 필수 — WIZ550과 구조적 불일치
- **결정**: `specs/schema/device.wiz550.schema.json` 신규 작성
  - `name`, `display_name`, `aliases`, `protocol`, `ui.sections` 필드 검증
  - `command_groups`, `search_cmd_order`, `overrides` 포함하지 않음
- `validate_schemas.py`에 라우팅 추가:
  ```python
  # YAML의 family 또는 파일명으로 스키마 선택
  # family == "wiz550" → device.wiz550.schema.json
  # 기타 → device.schema.json (기존)
  ```
- 기존 YAML(WIZ750SR.yaml 등) 검증 로직 변경 없음

### D-02: YAML 최상위 구조

```yaml
name: WIZ550SR
display_name: "WIZ550SR"
aliases:
  - "WIZ550SR"
family: wiz550          # WIZ550 전용 스키마로 라우팅
channels: 1

protocol:
  handler: WIZ550MSGHandler  # WIZ550MSGHandler.py의 클래스 참조
  port: 6550
  product_code: [0x02, 0x00, 0x00]  # DISCOVERY_ALL 응답 필터 기준
  config_size: 162          # WIZ550SR 구조체 크기 (바이트)
  parser: parse_sr           # WIZ550Profile.py 함수명
  builder: build_sr

ui:
  sections:
    - id: network
      label: "Network"
      fields: [...]
```

### D-03: UI 섹션 구조 — `ui.sections` (tabs 아님)

- 06-CONTEXT.md D-06의 `spec.sections.items()` 코드와 일치
- 최상위: `ui.sections: list` (id, label, fields, condition)
- 각 필드: `{id, label, type, choices, disabled}` 구조
  ```yaml
  fields:
    - id: local_ip
      label: "Local IP"
      type: ip
    - id: dhcp
      label: "DHCP"
      type: checkbox
    - id: baud_rate
      label: "Baud Rate"
      type: dropdown
      choices:
        0: "300 bps"
        1: "600 bps"
        2: "1200 bps"
        3: "2400 bps"
        4: "4800 bps"
        5: "9600 bps"
        6: "19200 bps"
        7: "38400 bps"
        8: "57600 bps"
        9: "115200 bps"
        10: "230400 bps"
        11: "460800 bps"
  ```

**field type 목록 (WIZ550 스키마에 정의):**

| type | 위젯 | 비고 |
|------|------|------|
| `ip` | IP 주소 4옥텟 | QLineEdit + validator |
| `text` | 자유 입력 | QLineEdit |
| `uint16` | 0~65535 정수 | QSpinBox |
| `dropdown` | 선택지 목록 | QComboBox + choices |
| `checkbox` | 참/거짓 | QCheckBox |
| `readonly` | 읽기 전용 표시 | QLabel |

### D-04: WIZ550S2E 가변 구조 — `condition` 필드

MQTT(232B) / Modbus(164B) / 기본(162B) 세 변형을 단일 `WIZ550S2E.yaml`에 표현:

```yaml
# WIZ550S2E.yaml
protocol:
  product_code: [0x00, 0x00, 0x00]
  config_size: 162   # 기본 크기; 실제 크기는 런타임에 응답 길이로 판별
  parser: parse_s2e
  builder: build_s2e

ui:
  sections:
    # ... (network, serial, options — SR과 동일)
    - id: mqtt
      label: "MQTT"
      condition: mqtt          # fw_ver[1] % 2 != 0 AND len >= 232
      fields:
        - {id: mqtt_user, label: "MQTT Username", type: text}
        - {id: mqtt_pw,   label: "MQTT Password", type: text}
        - {id: publish_topic,   label: "Publish Topic",   type: text}
        - {id: subscribe_topic, label: "Subscribe Topic", type: text}
    - id: modbus
      label: "Modbus"
      condition: modbus        # fw_ver[1] % 2 == 0 AND len >= 164
      fields:
        - {id: modbus_use,  label: "Modbus Enable", type: checkbox}
        - {id: modbus_mode, label: "Modbus Mode",   type: dropdown,
           choices: {0: "RTU", 1: "ASCII"}}
```

Phase 6에서 `section.condition` 필드를 읽어 `fw_ver` 기반 show/hide 결정.

### D-05: WIZ550WEB 비활성 필드 — `disabled: true` 마커

WIZ550WEB 133B 구조체에 없는 필드 (working_mode, remote_ip, remote_port, local_port, at_cmd)를 YAML에 `disabled: true`로 포함. SPEC-03 "명시적으로 정의됨" 요구사항 충족.

```yaml
# WIZ550WEB.yaml 예시
- id: working_mode
  label: "Working Mode"
  type: dropdown
  disabled: true      # WEB 구조체에 없음 — Phase 6에서 회색 처리
  choices:
    0: "TCP Client"
    1: "TCP Server"
```

WIZ550WEB에서 비활성화되는 필드 목록:
- `working_mode`, `remote_ip`, `remote_port`, `local_port`, `at_cmd`

WIZ550WEB 전용 추가:
- UART0 섹션 + UART1 섹션 분리 (2채널 시리얼)
- `protocol.config_size: 133`

### D-06: 각 YAML의 섹션 구성

**WIZ550SR.yaml:**
- network (mac_address, local_ip, subnet_mask, gateway, dns_server, dhcp, working_mode, remote_ip, local_port, remote_port)
- serial (baud_rate, data_bits, parity, stop_bits, flow_control)
- options (pw_setting, pw_connect, at_cmd)

**WIZ550S2E.yaml:**
- network, serial, options (SR과 동일)
- mqtt (condition: mqtt) — 4개 필드
- modbus (condition: modbus) — 2개 필드

**WIZ550WEB.yaml:**
- network (mac, ip, gw, sn, dhcp, dns + disabled 필드 5개)
- uart0 (baud_rate, data_bits, parity, stop_bits, flow_control, dtr, dsr)
- uart1 (동일)
- options (pw_setting, pw_connect, at_cmd disabled)

### Claude's Discretion

- WIZ550SR `data_bits` 드롭다운: 8-bit만 가능 — `choices: {3: "8-bit"}` 단일 선택 또는 `type: readonly, value: "8-bit"` 중 구현자 판단
- baud_rate choices 상한: SR/S2E = 460800 bps (11개), WEB = 장치 스펙 확인 후 결정
- WIZ550WEB의 UART 파라미터 상세 제약 (data_bits 범위 등) — WIZ550Profile.parse_web() 반환 필드 기준으로 작성

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SPEC — Phase 5 범위 REQ-IDs: SPEC-01, SPEC-02, SPEC-03, SPEC-04

### Existing Schema & YAML Pattern
- `specs/schema/device.schema.json` — 기존 스키마 구조 참조 (WIZ550 스키마 설계 기준)
- `specs/devices/WIZ750SR.yaml` — 기존 YAML 작성 패턴 참조
- `validate_schemas.py` — 스키마 검증 로직 수정 위치 (라우팅 추가)

### Phase 4 산출물 (구현 완료 — 반드시 읽을 것)
- `WIZ550MSGHandler.py` — 핸들러 클래스명 확인 (WIZ550Searcher/Getter/Setter/Resetter)
- `WIZ550Profile.py` — parse_sr()/parse_s2e()/parse_web() 반환 dict 필드명 확인 (YAML field id와 일치시킬 것)

### Phase 6 컨텍스트 (UI 빌드 코드 패턴)
- `.planning/phases/06-gui-integration/06-CONTEXT.md` — D-06: `_build_wiz550_panel()` 코드 패턴 (`spec.sections.items()`, `field.label`, `_make_field_widget(field)`)

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets
- `validate_schemas.py` — 기존 검증 구조 그대로 재사용; `family == "wiz550"` 분기만 추가
- `specs/schema/device.schema.json` — WIZ550 스키마의 JSON Schema $schema, title 패턴 참조

### Established Patterns
- 기존 YAML: `name`, `display_name`, `aliases`, `family`, `channels`, `ui.tabs` 구조
- WIZ550 YAML: 동일하게 `name`, `display_name`, `aliases`, `family: wiz550` 사용 + `protocol` 블록 추가 + `ui.sections` 구조 사용
- WIZ750SR.yaml의 `ui.tabs.groups` → WIZ550에서 `ui.sections.fields`로 대응

### Integration Points
- Phase 6에서 `device_spec_loader.py`에 WIZ550 YAML 로드 함수 추가 (또는 별도 `wiz550_spec_loader.py`)
- `validate_schemas.py`에서 `specs/devices/*.yaml` 순회 시 `family` 기준 스키마 라우팅

</code_context>

<specifics>

## Specific Ideas

- `WIZ550Profile.parse_sr()` 반환 dict 키명과 YAML `field.id`가 정확히 일치해야 Phase 6에서 `dev_info[field.id]`로 값 채우기 가능 → WIZ550Profile.py를 반드시 읽어 필드명 확인
- `condition` 값: `"mqtt"` 또는 `"modbus"` (문자열 상수) — Phase 6에서 이 값으로 분기

</specifics>

<deferred>

## Deferred Ideas

- WIZ550WEB의 UART1 포트가 실제 장치에서 어떻게 동작하는지 — 실물 장치 확보 후 확인 (UAT-02)
- `device_spec_loader.py`에 WIZ550 YAML 로더 통합 — Phase 6 구현 범위
- 기존 WIZ5xxSR / WIZ1x0SR UI 전체에 DESIGN.md 토큰 소급 적용 — 별도 UI 정리 Phase

</deferred>

---

*Phase: 05-devicespec-yaml*
*Context gathered: 2026-05-18*
