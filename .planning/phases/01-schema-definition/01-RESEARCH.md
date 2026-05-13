# Phase 1: Schema Definition - Research

**Researched:** 2026-05-13
**Domain:** JSON Schema (draft-07) + Python jsonschema 패키지 + WIZnet DeviceSpec YAML 구조 분석
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **스키마 검증 도구:** `jsonschema` Python 패키지
   - `device_spec_loader.py` 내에서 직접 호출 가능
   - Phase 3 loader integration과 자연스럽게 연결됨
   - `requirements.txt`에 `jsonschema` 추가 필요 (Phase 3 착수 전 확인)

2. **스키마 엄격도:** core strict + ui flexible
   - 엄격 적용: `name`, `family`, `channels`, `command_groups` (필수, enum 검증), `search_cmd_order`, `overrides` (optional, 구조 검증)
   - 유연 적용: `ui` 내부 필드 전체 (`additionalProperties: true`)
   - 커맨드 `ui` 필드 내부도 유연 적용

3. **meta: 블록:** Phase 1 스키마에 optional로 선정의
   - 포함 필드: `id`, `name`, `category`, `description`, `requires`, `conflicts`
   - 현재 YAML 파일들은 meta: 없이도 유효하게 통과해야 함

### Deferred Ideas (OUT OF SCOPE)

- `device_spec_loader.py` 수정 — Phase 3
- `meta:` 블록 실제 추가 — Phase 2
- `jsonschema` 패키지 설치/의존성 실제 추가 — Phase 3 착수 전
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCH-01 | 장치 YAML 및 커맨드 YAML JSON Schema 정의 (`specs/schema/device.schema.json`, `specs/schema/command-group.schema.json`) | device/command YAML 전체 구조 분석 완료. 스키마 필드 목록, 타입, enum 값, 특수 케이스 확인됨 |
</phase_requirements>

---

## Summary

이 Phase의 목표는 `specs/devices/*.yaml` 12개 파일과 `specs/commands/*.yaml` 10개 파일을 모두 통과시키는 JSON Schema 2개를 작성하는 것이다. 스키마는 `specs/schema/` 디렉토리에 저장되며, Phase 3에서 `device_spec_loader.py`에 연동된다.

YAML 구조 전체를 직접 읽어 분석한 결과, device YAML의 핵심 필드는 `name`, `family`, `channels`, `command_groups`이며, `search_cmd_order`, `overrides`, `fw_constraints`, `ui`는 optional이다. command YAML은 커맨드 코드를 키로 하는 맵 구조이며, 각 항목은 `description`, `regex`, `values`, `access`, `ui` 필드를 가진다. 가장 주의할 특수 케이스는 `ui: null`(WO 커맨드에서 사용), overrides의 values 항목이 문자열 또는 `{value, min_version}` 객체 두 가지 형태를 가진다는 점이다.

**Primary recommendation:** `jsonschema` 4.26.0으로 JSON Schema draft-07 스키마 2개를 작성하고, 별도 검증 스크립트로 기존 YAML 전체를 검증한다. Phase 1에서는 스키마 파일 생성과 검증 통과 확인만 하고, loader 수정은 Phase 3에서 한다.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| jsonschema | 4.26.0 | JSON Schema draft-07 검증 | PyPI 최신 안정 버전 [VERIFIED: pip index] |
| PyYAML | 6.0.3 | YAML → Python dict 변환 | 이미 requirements.txt에 포함 [VERIFIED: requirements.txt] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | 파일 경로 처리 | 검증 스크립트에서 YAML glob |
| json | stdlib | JSON Schema 파일 읽기/저장 | jsonschema 피드에 dict 전달 |

**Installation:**
```bash
# 검증 스크립트 실행 시 필요 (Phase 3 의존성 추가 전 로컬 테스트용)
pip install jsonschema==4.26.0
```

**Version verification:**
- jsonschema 4.26.0 — 2025년 최신 안정 버전 [VERIFIED: `pip index versions jsonschema`]
- jsonschema는 현재 프로젝트 requirements.txt에 없음 [VERIFIED: requirements.txt]

---

## Architecture Patterns

### Recommended Project Structure

```
specs/
├── schema/
│   ├── device.schema.json          # 신규 (Phase 1 산출물 #1)
│   └── command-group.schema.json   # 신규 (Phase 1 산출물 #2)
├── devices/
│   └── *.yaml                      # 기존 12개 파일 (수정 없음)
└── commands/
    └── *.yaml                      # 기존 10개 파일 (수정 없음)
```

검증 스크립트 위치 제안:
```
specs/validate_schemas.py           # 또는 프로젝트 루트 validate_schemas.py
```

### Pattern 1: device.schema.json 구조 (core strict)

모든 device YAML에서 관찰된 실제 필드를 기반으로 스키마 구성:

**필수 필드 (required):**
- `name` (string)
- `family` (string, enum — 아래 enum 목록 참조)
- `channels` (integer, 1 or 2)
- `command_groups` (array of string)

**Optional 필드:**
- `display_name` (string)
- `aliases` (array of string)
- `search_cmd_order` (array of string)
- `overrides` (object, additionalProperties=true — 커맨드 코드가 키이므로)
- `fw_constraints` (object, additionalProperties=true — 다양한 특수 필드 존재)
- `ui` (object, additionalProperties=true — ui flexible 결정)

**family enum 실측값** [VERIFIED: specs/devices/*.yaml 전체 분석]:
- `"one_port"` — WIZ750SR, WIZ750SR-1xx, WIZ107SR, WIZ108SR
- `"security"` — WIZ5XXSR-RP, WIZ5XXSR-RP_E-SAVE, WIZ510SSL, W55RP20-S2E, W232N, IP20
- `"two_port"` — WIZ752SR-12x
- `"security_two_port"` — W55RP20-S2E-2CH

**channels enum 실측값** [VERIFIED: specs/devices/*.yaml]:
- 1 또는 2

**command_groups 유효 값 목록** [VERIFIED: specs/commands/*.yaml 파일명]:
- `"base"`, `"ddns"`, `"gpio"`, `"modbus"`, `"pppoe"`, `"retransmit"`, `"security"`, `"telnet"`, `"two_port"`, `"w55rp20_ext"`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WIZnet Device Spec",
  "type": "object",
  "required": ["name", "family", "channels", "command_groups"],
  "additionalProperties": false,
  "properties": {
    "name": {"type": "string"},
    "display_name": {"type": "string"},
    "aliases": {"type": "array", "items": {"type": "string"}},
    "family": {
      "type": "string",
      "enum": ["one_port", "security", "two_port", "security_two_port"]
    },
    "channels": {"type": "integer", "minimum": 1, "maximum": 2},
    "search_cmd_order": {"type": "array", "items": {"type": "string"}},
    "command_groups": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["base", "ddns", "gpio", "modbus", "pppoe",
                 "retransmit", "security", "telnet", "two_port", "w55rp20_ext"]
      },
      "minItems": 1
    },
    "overrides": {"type": "object", "additionalProperties": true},
    "fw_constraints": {"type": "object", "additionalProperties": true},
    "ui": {"type": "object", "additionalProperties": true}
  }
}
```

### Pattern 2: command-group.schema.json 구조

command YAML의 실제 구조:
- 최상위: 커맨드 코드(2자 영대문자)를 키로 하는 맵
- 각 커맨드 항목: `description`, `regex`, `values`, `access`, `ui` 보유
- `ui` 필드는 `null`이거나 object — `ui: null`은 WO 커맨드에서 사용 [VERIFIED: base.yaml, security.yaml]
- `values`는 `{}` (빈 dict)이거나 문자열-값 맵
- `meta:` 블록은 optional(Phase 2에서 추가 예정)

**access enum 실측값** [VERIFIED: base.yaml, security.yaml, gpio.yaml 등]:
- `"RO"`, `"RW"`, `"WO"`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WIZnet Command Group",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "meta": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "id":          {"type": "string"},
        "name":        {"type": "string"},
        "category":    {"type": "string"},
        "description": {"type": "string"},
        "requires":    {"type": "array", "items": {"type": "string"}},
        "conflicts":   {"type": "array", "items": {"type": "string"}}
      }
    }
  },
  "patternProperties": {
    "^[A-Z0-9]{2}$": {
      "type": "object",
      "required": ["description", "regex", "values", "access"],
      "additionalProperties": false,
      "properties": {
        "description": {"type": "string"},
        "regex":       {"type": "string"},
        "values":      {"type": "object"},
        "access":      {"type": "string", "enum": ["RO", "RW", "WO"]},
        "ui":          {"oneOf": [{"type": "null"}, {"type": "object", "additionalProperties": true}]}
      }
    }
  }
}
```

**주의:** `additionalProperties: false`와 `patternProperties` 조합 시, JSON Schema draft-07에서는 `patternProperties`에 매칭되는 키는 `additionalProperties` 검사에서 제외됨 [VERIFIED: JSON Schema draft-07 명세]. 즉 커맨드 코드 키와 `meta` 키 둘 다 허용된다.

### Pattern 3: 검증 스크립트

```python
# validate_schemas.py (Phase 1 검증 실행 스크립트)
import json
import yaml
import jsonschema
from pathlib import Path

SPECS_DIR = Path("specs")

def validate_all():
    device_schema = json.loads((SPECS_DIR / "schema/device.schema.json").read_text())
    cmd_schema    = json.loads((SPECS_DIR / "schema/command-group.schema.json").read_text())

    errors = []
    for f in sorted((SPECS_DIR / "devices").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(data, device_schema)
            print(f"  OK  {f.name}")
        except jsonschema.ValidationError as e:
            errors.append(f"FAIL {f.name}: {e.message}")

    for f in sorted((SPECS_DIR / "commands").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(data, cmd_schema)
            print(f"  OK  {f.name}")
        except jsonschema.ValidationError as e:
            errors.append(f"FAIL {f.name}: {e.message}")

    if errors:
        for e in errors: print(e)
        raise SystemExit(1)
    print("All schemas valid.")

validate_all()
```

### Anti-Patterns to Avoid

- **command-group.schema.json에 `additionalProperties: false` 단독 사용:** YAML 파일 최상위는 커맨드 코드(동적 키)가 대부분 — `patternProperties`로 처리해야 함
- **ui 필드에 strict 적용:** `widget_overrides`, `password`, `span`, `depends_on` 등 자유롭게 추가되는 힌트 필드가 많아 스키마 재수정 부담 발생
- **command_groups를 단순 string array로만 검증:** enum으로 specs/commands/ 실제 파일명과 동기화 필요 (잘못된 group 이름 조기 탐지)
- **`values` 필드를 `additionalProperties: false`로 제한:** 커맨드 코드 값 맵은 내용이 장치마다 다르므로 object만 검증

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML → dict 파싱 | 직접 파싱 로직 | `yaml.safe_load()` | 이미 사용 중, 안전한 표준 방식 |
| JSON Schema 검증 | 직접 validate 함수 | `jsonschema.validate()` | draft-07 전체 지원, 오류 메시지 명확 |
| YAML 파일 glob | 수동 파일 목록 | `pathlib.Path.glob("*.yaml")` | 신규 파일 자동 포함 |

**Key insight:** jsonschema 패키지는 `$schema`, `required`, `additionalProperties`, `patternProperties`, `enum`, `oneOf`, `minimum` 등 draft-07 전체를 지원하므로 커스텀 검증 로직이 필요 없다.

---

## Common Pitfalls

### Pitfall 1: `ui: null` 허용 누락

**What goes wrong:** `ui` 필드를 `"type": "object"`로만 정의하면 `ui: null`인 커맨드(SV, RT, FR, EX, UF 등)가 검증 실패.
**Why it happens:** base.yaml과 security.yaml에 WO 커맨드들이 `ui: null`을 명시적으로 사용.
**How to avoid:** command 항목의 ui 필드를 `oneOf: [{"type": "null"}, {"type": "object"}]`로 정의.
**Warning signs:** `SV`, `RT`, `FR`, `EX`(base.yaml), `UF`(security.yaml) 검증 실패.

### Pitfall 2: overrides의 values 혼합 타입

**What goes wrong:** overrides.values 항목이 단순 문자열(`"0": "300"`)과 객체(`"16": {value: "1M", min_version: "1.2.1"}`) 두 형태 혼재 — `additionalProperties: false` 엄격 적용 시 객체 형태가 실패.
**Why it happens:** W55RP20-S2E.yaml, W55RP20-S2E-2CH.yaml의 BR/EB overrides에서 사용.
**How to avoid:** `overrides`는 `additionalProperties: true`로 유연하게 처리(이미 결정됨).
**Warning signs:** W55RP20-S2E.yaml, W55RP20-S2E-2CH.yaml BR override 검증 실패.

### Pitfall 3: patternProperties + additionalProperties 조합 오해

**What goes wrong:** command-group.schema.json에서 최상위를 `additionalProperties: false`만 사용하면 커맨드 코드 키들이 모두 거부됨.
**Why it happens:** draft-07에서 `additionalProperties`는 `properties`와 `patternProperties` 양쪽에 매칭되지 않은 키에만 적용됨. 따라서 `patternProperties`로 커맨드 코드 패턴을 정의하면 정상 작동.
**How to avoid:** `patternProperties: {"^[A-Z0-9]{2}$": {...}}`로 커맨드 코드 처리, `properties.meta`로 meta 블록 처리, `additionalProperties: false` 유지.
**Warning signs:** 모든 커맨드 검증이 "Additional properties not allowed" 오류로 실패.

### Pitfall 4: command_groups enum 누락

**What goes wrong:** 새 장치 YAML에 존재하지 않는 command group 이름이 들어와도 스키마가 통과.
**Why it happens:** command_groups를 단순 `{"type": "array", "items": {"type": "string"}}`로만 정의.
**How to avoid:** `items.enum`에 실제 specs/commands/ 파일명 10개를 열거 — `["base", "ddns", "gpio", "modbus", "pppoe", "retransmit", "security", "telnet", "two_port", "w55rp20_ext"]`.
**Warning signs:** 오탈자 group 이름이 런타임 FileNotFoundError로만 발견됨.

### Pitfall 5: WIZ107SR/108SR의 fw_constraints 특수 필드

**What goes wrong:** `fw_constraints`를 strict하게 정의하면 `hw_version_field`, `new_hw_major_versions`, `new_fw_effective_size`, `old_fw_max_size`, `upload_port_from_response` 등 WIZ107/108SR 전용 필드가 검증 실패.
**Why it happens:** WIZ107SR.yaml, WIZ108SR.yaml에 다른 장치에 없는 펌웨어 업로드 관련 특수 필드 존재.
**How to avoid:** `fw_constraints`는 `additionalProperties: true`로 유연하게 처리.
**Warning signs:** WIZ107SR.yaml, WIZ108SR.yaml 검증 실패.

---

## Code Examples

### 검증 실행 방법

```python
# Source: jsonschema 공식 패턴 [ASSUMED]
import jsonschema

schema = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
data = {"name": "WIZ750SR"}
jsonschema.validate(data, schema)  # 통과 시 None 반환, 실패 시 ValidationError 발생
```

### patternProperties 예시 (command-group)

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "meta": { "..." }
  },
  "patternProperties": {
    "^[A-Z0-9]{2}$": {
      "type": "object",
      "required": ["description", "regex", "values", "access"]
    }
  }
}
```

이 구조에서 `meta`는 `properties`로 명시되어 허용되고, `MC`, `VR` 등 2자 커맨드 코드는 `patternProperties` 패턴에 매칭되어 허용됨. 다른 모든 키는 `additionalProperties: false`에 의해 거부.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 스키마 없이 YAML 로드 | JSON Schema 검증 추가 | Phase 1 (신규) | 잘못된 YAML 조기 탐지 |
| custom Python type-check | jsonschema 표준 검증 | Phase 1 (신규) | 에러 메시지 표준화 |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | jsonschema 4.26.0이 patternProperties + additionalProperties 조합을 draft-07 표준대로 지원함 | Architecture Patterns | 스키마 구조 변경 필요 |
| A2 | YAML 파일에 YAML comment(`#` 라인)는 yaml.safe_load() 파싱 후 dict에 나타나지 않으므로 스키마 검증에 영향 없음 | Architecture Patterns | 낮음 — YAML 표준 동작 |

---

## Open Questions

없음 — 모든 YAML 파일을 직접 읽어 구조를 확인했으므로 불확실한 사항 없음.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | 검증 스크립트 실행 | ✓ | 3.12 (추정) | — |
| PyYAML | YAML 파싱 | ✓ | 6.0.3 | — |
| jsonschema | 스키마 검증 | ✗ | — (미설치) | 없음 — 설치 필요 |

**Missing dependencies with no fallback:**
- `jsonschema` 4.26.0 — 검증 스크립트 실행 전 `pip install jsonschema==4.26.0` 필요 (requirements.txt는 Phase 3에서 추가)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | 별도 프레임워크 없음 — Python 스크립트 직접 실행 |
| Config file | 없음 |
| Quick run command | `python validate_schemas.py` (또는 `uv run python validate_schemas.py`) |
| Full suite command | 동일 — validate_schemas.py가 모든 YAML 파일 검증 |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCH-01-a | device.schema.json이 specs/devices/*.yaml 전체 통과 | 검증 스크립트 | `python validate_schemas.py` | ❌ Wave 0 |
| SCH-01-b | command-group.schema.json이 specs/commands/*.yaml 전체 통과 | 검증 스크립트 | `python validate_schemas.py` | ❌ Wave 0 |
| SCH-01-c | meta: 블록 필드가 스키마에 정의됨 | 스키마 파일 내용 확인 | `python -c "import json; s=json.load(open('specs/schema/command-group.schema.json')); assert 'meta' in s['properties']"` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python validate_schemas.py`
- **Phase gate:** 모든 YAML 파일 통과 확인

### Wave 0 Gaps

- [ ] `specs/schema/` 디렉토리 생성
- [ ] `specs/schema/device.schema.json` 생성
- [ ] `specs/schema/command-group.schema.json` 생성
- [ ] `validate_schemas.py` 생성 (또는 프로젝트 루트)
- [ ] `pip install jsonschema==4.26.0` 실행 (로컬 환경)

---

## Key Data: YAML 구조 완전 분석

### Device YAML 필드 매핑 (12개 파일 전체 분석)

[VERIFIED: specs/devices/*.yaml 전체 직접 읽기]

| 필드 | 타입 | 필수 | 모든 장치에 있음 | 비고 |
|------|------|------|----------------|------|
| `name` | string | YES | YES | — |
| `display_name` | string | NO | 대부분 있음 | 없으면 name과 동일 처리 |
| `aliases` | array of string | NO | 대부분 있음 | 검색 매칭용 |
| `family` | string(enum) | YES | YES | 4종: one_port, security, two_port, security_two_port |
| `channels` | integer | YES | YES | 1 또는 2 |
| `search_cmd_order` | array of string | NO | 일부만 있음 | 없으면 cmdset 자동 생성 |
| `command_groups` | array of string | YES | YES | enum 검증 대상 |
| `overrides` | object | NO | 대부분 있음 | 커맨드별 override |
| `fw_constraints` | object | NO | 대부분 있음 | upload/port 정보 |
| `ui` | object | NO | 모두 있음 | ui flexible 결정 |

### Command YAML 필드 매핑 (10개 파일 전체 분석)

[VERIFIED: specs/commands/*.yaml 전체 직접 읽기]

| 필드 | 타입 | 필수 | 비고 |
|------|------|------|------|
| `description` | string | YES | 설명 텍스트 |
| `regex` | string | YES | 빈 문자열("") 가능 |
| `values` | object | YES | 빈 dict({}) 가능 |
| `access` | string(enum) | YES | "RO", "RW", "WO" |
| `ui` | null or object | YES | WO 커맨드는 null |

**ui 내부 필드 (flexible, 실측값):**
- `tab`, `group`, `widget`, `label`, `order` — 공통
- `depends_on`, `span`, `password`, `tooltip`, `visible`, `enabled` — 선택적

### 커맨드 코드 패턴

모든 커맨드 코드는 2자 영대문자 + 숫자 조합 [VERIFIED: 전체 YAML 파일]:
- 순수 2 영대문자: `MC`, `VR`, `OP`, `BR` 등
- 영자+숫자: `S0`, `S1`, `U0`, `U1`, `U2` 등
- 정규표현식 `^[A-Z0-9]{2}$`로 매칭 가능

---

## Sources

### Primary (HIGH confidence)

- 직접 읽기: `specs/devices/*.yaml` 12개 파일 전체
- 직접 읽기: `specs/commands/*.yaml` 10개 파일 전체
- 직접 읽기: `device_spec_loader.py` — 로더가 실제로 사용하는 필드 확인
- 직접 읽기: `requirements.txt` — 현재 의존성 목록
- 직접 읽기: `.planning/phases/01-schema-definition/01-CONTEXT.md` — 잠금 결정

### Secondary (MEDIUM confidence)

- `pip index versions jsonschema` — 최신 버전 4.26.0 확인 [VERIFIED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 버전 직접 확인, 이미 사용 중인 PyYAML
- Architecture: HIGH — 12개 device YAML, 10개 command YAML 전체 직접 읽어 분석
- Pitfalls: HIGH — 실제 파일에서 특수 케이스 직접 발견 (ui:null, 혼합 values 타입)

**Research date:** 2026-05-13
**Valid until:** 2027-05-13 (YAML 구조 변경 시 재검토)
