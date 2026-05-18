---
phase: 05-devicespec-yaml
plan: "00"
subsystem: schema-validation
tags: [schema, json-schema, pytest, wiz550, validation]
dependency_graph:
  requires: []
  provides:
    - specs/schema/device.wiz550.schema.json
    - tests/test_wiz550_spec.py
    - validate_schemas.py (wiz550 라우팅 추가)
  affects:
    - Wave 1 (05-01): WIZ550SR/S2E/WEB YAML 파일 — 이 스키마로 검증됨
tech_stack:
  added: []
  patterns:
    - JSON Schema draft-07 ($ref + definitions 패턴)
    - family 기반 스키마 라우팅 (validate_schemas.py)
    - pytest.skip으로 YAML 미존재 시 스텁 처리
key_files:
  created:
    - specs/schema/device.wiz550.schema.json
    - tests/test_wiz550_spec.py
  modified:
    - validate_schemas.py
decisions:
  - "wiz550_schema: device.schema.json과 분리 (command_groups 필드 없는 binary protocol 전용)"
  - "family='wiz550' 분기로 스키마 라우팅 — 기존 YAML 검증 흐름 무변경"
  - "field.value: {} (any type) — readonly 필드 value 프로퍼티 Pitfall 3 예방"
metrics:
  duration: "~10 min"
  completed: "2026-05-18T10:40:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 05 Plan 00: WIZ550 스키마 인프라 (Wave 0) Summary

**한 줄 요약:** WIZ550 binary protocol 전용 JSON Schema + validate_schemas.py family 라우팅 + pytest 스텁 10개 구축.

---

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | device.wiz550.schema.json 신규 작성 | 98d7a4c | specs/schema/device.wiz550.schema.json |
| 2 | validate_schemas.py 라우팅 + 테스트 스텁 | 35d2576 | validate_schemas.py, tests/test_wiz550_spec.py |

---

## What Was Built

### Task 1: device.wiz550.schema.json

WIZ550 binary protocol 장치 전용 JSON Schema (draft-07):

- `family: "wiz550"` const 강제 — 기존 device.schema.json의 family enum과 분리
- `additionalProperties: false` — 최상위 + protocol + ui + section + field 모두 적용
- `protocol` 객체 required 6개 필드: handler, port, product_code, config_size, parser, builder
- `ui.sections` 배열 구조 (tabs 아님) — D-03 결정 준수
- field type enum 6개: ip, text, uint16, dropdown, checkbox, readonly
- `field.value: {}` (any type) — `type: readonly, value: "8-bit"` 패턴 지원 (Pitfall 3 예방)
- `choices.additionalProperties: {type: string}` — YAML 정수키 → 문자열값 구조 지원

### Task 2: validate_schemas.py 라우팅

변경 2곳 (총 2줄 추가, 1줄 수정):

1. `wiz550_schema = json.loads(...)` 로드 추가 (device_schema 다음 줄)
2. `schema = wiz550_schema if data.get("family") == "wiz550" else device_schema` 분기

기존 WIZ750SR.yaml 등 (family="one_port")은 device_schema로 라우팅 — 영향 없음.

### Task 2: tests/test_wiz550_spec.py

10개 테스트 스텁 (Wave 1 YAML 작성 전 → SKIP, 작성 후 → PASS 예정):

| 테스트 | SPEC | 현재 상태 | 검증 내용 |
|--------|------|-----------|-----------|
| test_wiz550sr_schema_valid | SPEC-01 | SKIP | SR YAML → validate_schemas.py 통과 |
| test_wiz550sr_field_ids_match_profile | SPEC-01 | SKIP | SR field.id ⊇ parse_sr() 반환 키 21개 |
| test_wiz550s2e_schema_valid | SPEC-02 | SKIP | S2E YAML → validate_schemas.py 통과 |
| test_wiz550s2e_conditional_sections | SPEC-02 | SKIP | mqtt/modbus condition 섹션 존재 |
| test_wiz550s2e_mqtt_field_ids | SPEC-02 | SKIP | mqtt_pub_topic/mqtt_sub_topic 키 확인 |
| test_wiz550web_schema_valid | SPEC-03 | SKIP | WEB YAML → validate_schemas.py 통과 |
| test_web_disabled_fields | SPEC-03 | SKIP | disabled:true 필드 5개 확인 |
| test_web_no_pw_connect | SPEC-03 | SKIP | pw_connect 미포함 확인 (Pitfall 2) |
| test_web_uart0_uart1_sections | SPEC-03 | SKIP | uart0/uart1 섹션 존재 |
| test_validate_schemas_all_pass | SPEC-04 | **PASS** | validate_schemas.py 종료 코드 0 |

---

## Verification Results

```
Wave 0 완료 조건 체크:
1. uv run python validate_schemas.py → 종료 코드 0  [PASS]
2. uv run pytest tests/test_wiz550_spec.py --collect-only → 10개 수집  [PASS]
3. specs/schema/device.wiz550.schema.json에 "const": "wiz550" 포함  [PASS]
4. validate_schemas.py에 wiz550_schema 및 data.get("family") == "wiz550" 포함  [PASS]
5. tests/test_wiz550_spec.py의 expected_ui_keys에 inactivity, reconnection 포함  [PASS]
```

---

## Deviations from Plan

None — 플랜 그대로 실행. 워크트리에 validate_schemas.py / specs/schema / tests/ 파일이
master 브랜치에만 있어서 `git checkout master -- ...` 으로 가져온 뒤 작업 (정상 절차).

---

## Known Stubs

- `tests/test_wiz550_spec.py`의 9개 테스트: Wave 1 YAML 미존재로 pytest.skip 처리.
  WIZ550SR.yaml, WIZ550S2E.yaml, WIZ550WEB.yaml 작성(Wave 1) 후 PASS 전환 예정.

---

## Threat Flags

없음 — 새 네트워크 엔드포인트, 인증 경로, 스키마 변경 없음.
YAML 파싱은 yaml.safe_load 사용 중 (기존 T-05-00-01 mitigate 충족).

---

## Self-Check: PASSED

- [x] specs/schema/device.wiz550.schema.json 존재 확인
- [x] tests/test_wiz550_spec.py 존재 확인
- [x] validate_schemas.py wiz550_schema 포함 확인
- [x] 커밋 98d7a4c 존재 확인
- [x] 커밋 35d2576 존재 확인
