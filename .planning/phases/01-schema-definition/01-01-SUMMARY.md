---
phase: 01-schema-definition
plan: "01"
subsystem: specs/schema
tags: [json-schema, yaml-validation, device-spec, command-group]
dependency_graph:
  requires: []
  provides:
    - specs/schema/device.schema.json
    - specs/schema/command-group.schema.json
    - validate_schemas.py
  affects:
    - device_spec_loader.py (Phase 3에서 연동 예정)
    - specs/commands/*.yaml (Phase 2에서 meta: 블록 추가 예정)
tech_stack:
  added:
    - jsonschema==4.26.0
  patterns:
    - JSON Schema draft-07 (core strict + ui flexible)
    - patternProperties for dynamic command-code keys
key_files:
  created:
    - specs/schema/device.schema.json
    - specs/schema/command-group.schema.json
    - validate_schemas.py
  modified: []
decisions:
  - "device YAML: additionalProperties:false (최상위) + overrides/fw_constraints/ui는 additionalProperties:true (flexible)"
  - "command-group YAML: patternProperties '^[A-Z0-9]{2}$' + meta optional + ui oneOf[null, object]"
  - "validate_schemas.py를 프로젝트 루트에 배치 (specs/ 내부 아님)"
metrics:
  duration: "~7분"
  completed: "2026-05-13T10:51:48Z"
  tasks_completed: 3
  files_created: 3
  files_modified: 0
---

# Phase 1 Plan 01: Schema Definition Summary

**한 줄 요약:** JSON Schema draft-07 기반 device/command-group YAML 계약 확립 — 22개 YAML 전체 수정 없이 검증 통과

---

## 생성된 파일

| 파일 경로 | 역할 | 커밋 |
|---------|------|------|
| `specs/schema/device.schema.json` | 장치 YAML 구조 계약 | `0d325a0` |
| `specs/schema/command-group.schema.json` | 커맨드 그룹 YAML 구조 계약 | `7feaaf6` |
| `validate_schemas.py` | 전체 YAML 검증 스크립트 | `6a621a2` |

---

## 스키마 구조 요약

### device.schema.json (core strict + ui flexible)

```
required: [name, family, channels, command_groups]
additionalProperties: false  ← 최상위 strict
properties:
  family.enum: [one_port, security, two_port, security_two_port]
  channels: integer, min=1, max=2
  command_groups.items.enum: [base, ddns, gpio, modbus, pppoe,
                               retransmit, security, telnet, two_port, w55rp20_ext]
  overrides: additionalProperties: true  ← flexible (혼합 타입 허용)
  fw_constraints: additionalProperties: true  ← flexible (WIZ107/108SR 특수 필드)
  ui: additionalProperties: true  ← flexible (에디터 진화 허용)
```

### command-group.schema.json (patternProperties + optional meta)

```
additionalProperties: false
properties:
  meta: optional, additionalProperties: false, 6개 필드
    (id, name, category, description, requires, conflicts)
patternProperties:
  "^[A-Z0-9]{2}$":
    required: [description, regex, values, access]
    access.enum: [RO, RW, WO]
    ui: oneOf [null, {type: object, additionalProperties: true}]
      ← WO 커맨드 (SV, RT, FR, EX, UF)의 ui:null 허용
```

---

## validate_schemas.py 실행 결과

```
=== Device YAML ===
  OK  IP20.yaml
  OK  W232N.yaml
  OK  W55RP20-S2E-2CH.yaml
  OK  W55RP20-S2E.yaml
  OK  WIZ107SR.yaml
  OK  WIZ108SR.yaml
  OK  WIZ510SSL.yaml
  OK  WIZ5XXSR-RP.yaml
  OK  WIZ5XXSR-RP_E-SAVE.yaml
  OK  WIZ750SR-1xx.yaml
  OK  WIZ750SR.yaml
  OK  WIZ752SR-12x.yaml

=== Command Group YAML ===
  OK  base.yaml
  OK  ddns.yaml
  OK  gpio.yaml
  OK  modbus.yaml
  OK  pppoe.yaml
  OK  retransmit.yaml
  OK  security.yaml
  OK  telnet.yaml
  OK  two_port.yaml
  OK  w55rp20_ext.yaml

All schemas valid.
```

총 **22개 OK** (12 device + 10 command), 종료 코드 0.

---

## Phase 2에서 사용할 계약 요약 (meta 블록)

Phase 2에서 `specs/commands/*.yaml`에 `meta:` 블록을 추가할 때 스키마 재수정 없이 바로 유효:

```yaml
meta:
  id: "base"                    # type: string
  name: "Base Commands"         # type: string
  category: "network"           # type: string
  description: "..."            # type: string
  requires: []                  # type: array of string
  conflicts: []                 # type: array of string
```

`meta`는 `required`에 포함되지 않으므로 현재 YAML에 없어도 통과.

---

## Phase 3에서 참조할 스키마 파일 경로

```python
# device_spec_loader.py에서 사용할 경로 (Phase 3 구현 시 참조)
SCHEMA_DIR = Path(__file__).parent / "specs" / "schema"
device_schema_path = SCHEMA_DIR / "device.schema.json"
cmd_schema_path = SCHEMA_DIR / "command-group.schema.json"
```

---

## Deviations from Plan

None — 플랜에서 지정한 내용 그대로 구현됨.

유일한 편차: `jsonschema` 설치 시 시스템 Python이 아닌 프로젝트 `.venv` 환경에 설치 필요 (`uv pip install`). 플랜에서는 `pip install`로 명시되어 있었으나 실제 환경이 uv 가상환경이었음. 기능에는 영향 없음.

---

## Known Stubs

없음. 모든 스키마 파일과 검증 스크립트가 완전히 작동함.

---

## Threat Flags

없음. 신규 네트워크 엔드포인트, 인증 경로, 파일 접근 패턴, 스키마 변경 없음. 로컬 개발 도구 (validate_schemas.py)만 추가됨.

---

## Self-Check: PASSED

| 항목 | 결과 |
|-----|------|
| `specs/schema/device.schema.json` 존재 | FOUND |
| `specs/schema/command-group.schema.json` 존재 | FOUND |
| `validate_schemas.py` 존재 | FOUND |
| 커밋 `0d325a0` (device.schema.json) | FOUND |
| 커밋 `7feaaf6` (command-group.schema.json) | FOUND |
| 커밋 `6a621a2` (validate_schemas.py) | FOUND |
| `python validate_schemas.py` 종료 코드 0 | PASS |
| 22개 YAML 전체 OK | PASS |
