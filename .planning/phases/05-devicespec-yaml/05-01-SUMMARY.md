---
phase: 05-devicespec-yaml
plan: "01"
subsystem: devicespec-yaml
tags: [yaml, devicespec, wiz550, schema, validation]
dependency_graph:
  requires:
    - specs/schema/device.wiz550.schema.json (Wave 0, 05-00)
    - validate_schemas.py (Wave 0, 05-00 wiz550 라우팅)
    - tests/test_wiz550_spec.py (Wave 0, 05-00 스텁)
  provides:
    - specs/devices/WIZ550SR.yaml (SPEC-01)
    - specs/devices/WIZ550S2E.yaml (SPEC-02)
    - specs/devices/WIZ550WEB.yaml (SPEC-03)
  affects:
    - Phase 6 _build_wiz550_panel(): 이 YAML들을 로드하여 UI 동적 생성
    - device_spec_loader.py: WIZ550 YAML 로더 추가 시 이 파일 참조
tech_stack:
  added: []
  patterns:
    - WIZ550 binary protocol DeviceSpec YAML (ui.sections 구조)
    - field.id = WIZ550Profile.parse_*() 반환 dict 키 1:1 매핑
    - baud_rate choices 키 = 실제 bps 정수값 (인덱스 아님)
    - condition 필드 = Phase 6 분기 키 ("mqtt" | "modbus")
    - disabled:true = WEB 구조체에 없는 필드 명시 (SPEC-03)
key_files:
  created:
    - specs/devices/WIZ550SR.yaml
    - specs/devices/WIZ550S2E.yaml
    - specs/devices/WIZ550WEB.yaml
  modified: []
decisions:
  - "baud_rate choices 키 = 실제 bps 정수값 (D-03 override: D-03 예시는 인덱스 기반이나 WIZ550Profile.py struct 'I' 언패킹 결과가 bps int이므로 choices 키도 bps int)"
  - "WIZ550WEB product_code = [0x01, 0x02, 0x00] (WIZ550Profile.py WEB_FORMAT module_type hex='010200' 기준)"
  - "WIZ550WEB uart0/uart1 flow_control: XON/XOFF(1) 포함 3가지 choices (Assumption A2 — 실물 확인 전 포함이 안전)"
  - "serial_command = D-05의 at_cmd와 동일 필드 (CONTEXT.md 표기 불일치 — WIZ550Profile 실제 키명 serial_command 우선)"
metrics:
  duration: "~22 min"
  completed: "2026-05-18T10:52:33Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase 05 Plan 01: WIZ550 DeviceSpec YAML 3종 작성 Summary

**한 줄 요약:** WIZ550SR/S2E/WEB 3종 DeviceSpec YAML 작성 — field.id = WIZ550Profile.parse_*() 반환 dict 키 1:1 매핑, baud_rate choices 키 = 실제 bps 정수값, validate_schemas.py + pytest 10개 테스트 전체 PASS.

---

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | WIZ550SR.yaml 작성 (SPEC-01) | 8236293 | specs/devices/WIZ550SR.yaml (+ Wave 0 인프라 파일) |
| 2 | WIZ550S2E.yaml 작성 (SPEC-02) | 12662b0 | specs/devices/WIZ550S2E.yaml |
| 3 | WIZ550WEB.yaml 작성 + 전체 검증 통과 (SPEC-03/04) | 98e1a19 | specs/devices/WIZ550WEB.yaml |

---

## What Was Built

### Task 1: WIZ550SR.yaml (SPEC-01)

WIZ550SR 단일 채널 S2E 장치 DeviceSpec:

- **섹션 3개:** network(10 fields) / serial(5 fields) / options(6 fields)
- **총 field 수:** 21개 (active) + UI 관련 내부 필드 제외
- **핵심 제약 준수:**
  - `baud_rate choices` 키 = 실제 bps 정수값 (300~460800, 12개)
  - `flow_control choices` = {0: None, 2: RTS/CTS} — XON/XOFF(1) 제외 (PROF-01)
  - `data_bits`: `type: readonly, value: "8-bit"` — SR은 8-bit 전용
  - `inactivity`, `reconnection` options 섹션 포함

### Task 2: WIZ550S2E.yaml (SPEC-02)

WIZ550S2E 가변 구조(162~232B) DeviceSpec:

- **섹션 5개:** network / serial / options / mqtt(condition) / modbus(condition)
- **조건부 섹션:** `condition: mqtt` (fw_ver[1] 홀수 AND len>=232), `condition: modbus` (fw_ver[1] 짝수 AND len>=164)
- **MQTT field.id:** `mqtt_pub_topic`, `mqtt_sub_topic` (publish_topic/subscribe_topic 아님 — RESEARCH.md Pitfall 확인)
- `product_code: [0x00, 0x00, 0x00]` (S2E 식별자)

### Task 3: WIZ550WEB.yaml (SPEC-03)

WIZ550WEB 2채널 133B 구조 DeviceSpec:

- **섹션 4개:** network / uart0 / uart1 / options
- **disabled:true 필드 5개 (SPEC-03):** working_mode, remote_ip, remote_port, local_port, serial_command
- **pw_connect 없음:** WEB 구조체 미포함 (RESEARCH.md Pitfall 2 준수)
- **uart0_*/uart1_* 별도 섹션:** parse_web() 실제 키명과 1:1 매핑
- `product_code: [0x01, 0x02, 0x00]` (WIZ550Profile.py module_type hex='010200' 기준)
- `config_size: 133`, `channels: 2`

---

## Verification Results

```
=== validate_schemas.py 결과 (Task 3 완료 후) ===
  OK  WIZ550SR.yaml
  OK  WIZ550S2E.yaml
  OK  WIZ550WEB.yaml
  (기존 YAML 13개도 모두 OK)
All schemas valid.
종료 코드: 0

=== pytest tests/test_wiz550_spec.py -v ===
tests/test_wiz550_spec.py::test_wiz550sr_schema_valid PASSED
tests/test_wiz550_spec.py::test_wiz550sr_field_ids_match_profile PASSED
tests/test_wiz550_spec.py::test_wiz550s2e_schema_valid PASSED
tests/test_wiz550_spec.py::test_wiz550s2e_conditional_sections PASSED
tests/test_wiz550_spec.py::test_wiz550s2e_mqtt_field_ids PASSED
tests/test_wiz550_spec.py::test_wiz550web_schema_valid PASSED
tests/test_wiz550_spec.py::test_web_disabled_fields PASSED
tests/test_wiz550_spec.py::test_web_no_pw_connect PASSED
tests/test_wiz550_spec.py::test_web_uart0_uart1_sections PASSED
tests/test_wiz550_spec.py::test_validate_schemas_all_pass PASSED
10 passed in 3.62s
```

---

## Deviations from Plan

### Auto-fixed Issues

없음.

### 계획 vs 실행 차이

**1. [계획 조정] WIZ550WEB product_code 불일치 해소**
- **발견:** PLAN.md Task 3 action 본문에 `[0x01, 0x02, 0x00]`로 명시, CRITICAL_NOTES에는 `[0x01, 0x00, 0x00]`으로 명시 — 충돌
- **해소:** WIZ550Profile.py WEB_FORMAT module_type 실제 값 `'010200'`(hex) = `[0x01, 0x02, 0x00]` 기준 적용 (코드베이스 단일 진실 소스)
- **영향:** CRITICAL_NOTES의 `[0x01, 0x00, 0x00]`은 오기로 판단, PLAN.md Task 3 본문의 값이 정확

**2. [Wave 0 파일 처리] 워크트리에 Wave 0 산출물 수동 checkout**
- **발견:** 워크트리가 master의 78bd3f9 커밋 기반 — Wave 0 커밋(98d7a4c, 35d2576)이 master 최신에만 있었음
- **해소:** `git checkout master -- specs/schema/ validate_schemas.py tests/test_wiz550_spec.py`로 Wave 0 파일 가져온 후 Task 1 커밋에 포함
- **영향:** Task 1 커밋에 Wave 0 인프라 파일(3 schema files + validate_schemas.py + test file)이 함께 포함됨

---

## Known Stubs

없음 — 3개 YAML 모두 실제 field.id와 구조 데이터로 완성됨.

---

## Threat Flags

없음 — YAML 파일은 UI 구조 정의 전용. 실제 자격증명/비밀번호 값 없음.

---

## Self-Check: PASSED

- [x] specs/devices/WIZ550SR.yaml 존재 확인
- [x] specs/devices/WIZ550S2E.yaml 존재 확인
- [x] specs/devices/WIZ550WEB.yaml 존재 확인
- [x] 커밋 8236293 존재 확인
- [x] 커밋 12662b0 존재 확인
- [x] 커밋 98e1a19 존재 확인
- [x] validate_schemas.py 종료 코드 0 확인
- [x] pytest 10개 테스트 전체 PASS 확인
- [x] WIZ550SR.yaml: baud_rate choices에 115200 키 포함 (bps 정수값 확인)
- [x] WIZ550SR.yaml: flow_control choices에 1 키 없음 (XON/XOFF 제외 확인)
- [x] WIZ550S2E.yaml: mqtt_pub_topic, mqtt_sub_topic 포함
- [x] WIZ550WEB.yaml: disabled:true 필드 5개 포함
- [x] WIZ550WEB.yaml: pw_connect 없음
