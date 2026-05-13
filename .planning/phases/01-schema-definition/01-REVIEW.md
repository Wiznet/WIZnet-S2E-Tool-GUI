---
phase: 01-schema-definition
reviewed: 2026-05-13T10:57:00Z
depth: quick
files_reviewed: 3
files_reviewed_list:
  - specs/schema/device.schema.json
  - specs/schema/command-group.schema.json
  - validate_schemas.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-13T10:57:00Z
**Depth:** quick
**Files Reviewed:** 3
**Status:** issues_found

## Summary

스키마 정의 3개 파일을 quick depth로 검토했다. 하드코딩 비밀값·위험 함수·디버그 아티팩트는 검출되지 않았다. 보안 위협은 없으나, 두 가지 잠재적 버그(중복 커맨드 코드 `DD`, YAML 파싱 에러 미처리)와 사소한 품질 개선 사항 1건을 발견했다.

---

## Warnings

### WR-01: 커맨드 코드 `DD`가 두 그룹에서 충돌 — 의미가 다름

**File:** `specs/schema/command-group.schema.json` (schema 정의) / 실제 충돌 파일: `specs/commands/ddns.yaml`, `specs/commands/w55rp20_ext.yaml`

**Issue:**
동일한 2자 코드 `DD`가 두 command-group 파일에 서로 다른 의미로 정의되어 있다.

- `ddns.yaml` → `DD`: "DDNS Enable" (0/1 checkbox)
- `w55rp20_ext.yaml` → `DD`: "Send Data at Disconnection" (최대 30자 문자열)

`command-group.schema.json`의 `patternProperties`는 각 파일 내부만 검증하며, 파일 간 코드 충돌을 감지하지 못한다. `device_spec_loader.py` 등 로더가 두 그룹을 병합할 때 어느 `DD` 정의가 살아남는지는 구현 의존적이며, 잘못된 커맨드가 전송될 경우 장치 동작 오류로 이어진다.

현재 어떤 디바이스도 `ddns`와 `w55rp20_ext`를 동시에 참조하지 않아 런타임 충돌은 발생하지 않지만, 향후 디바이스 추가 시 무증상 버그가 될 수 있다.

**Fix:**
`device.schema.json`에 `command_groups` 조합 제약을 명시하거나, `validate_schemas.py`에 그룹 간 코드 중복 검사를 추가하라.

```python
# validate_schemas.py — validate_all() 끝에 추가
print("\n=== Cross-group Duplicate Command Codes ===")
group_commands: dict[str, list[str]] = {}
for f in sorted((SPECS_DIR / "commands").glob("*.yaml")):
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    codes = [k for k in data if k != "meta"]
    group_commands[f.stem] = codes

all_codes: dict[str, list[str]] = {}  # code -> [group, ...]
for group, codes in group_commands.items():
    for code in codes:
        all_codes.setdefault(code, []).append(group)

dup_errors = False
for code, groups in all_codes.items():
    if len(groups) > 1:
        print(f"  WARN  '{code}' defined in multiple groups: {groups}")
        dup_errors = True
if not dup_errors:
    print("  OK  No duplicate codes across groups")
```

---

### WR-02: `validate_schemas.py` — YAML 파싱 에러 미처리로 전체 스크립트 크래시 가능

**File:** `validate_schemas.py:37` (devices 루프), `validate_schemas.py:46` (commands 루프)

**Issue:**
`yaml.safe_load()`는 잘못된 YAML 구문에 대해 `yaml.YAMLError`를 던진다. 현재 코드는 이를 잡지 않아, YAML 한 파일이 파싱 실패하면 `validate_all()` 전체가 중단되고 나머지 파일 검증 결과가 출력되지 않는다. CI 환경에서 오류 원인 파악이 어려워진다.

```python
# 현재 (WR-02)
data = yaml.safe_load(f.read_text(encoding="utf-8"))
try:
    jsonschema.validate(instance=data, schema=device_schema)
```

**Fix:**
`yaml.safe_load` 호출을 `try/except yaml.YAMLError`로 감싸라.

```python
try:
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
except yaml.YAMLError as e:
    errors.append(f"FAIL {f.name}: YAML parse error: {e}")
    print(f"  FAIL {f.name}: YAML parse error: {e}")
    continue
try:
    jsonschema.validate(instance=data, schema=device_schema)
    print(f"  OK  {f.name}")
except jsonschema.ValidationError as e:
    errors.append(f"FAIL {f.name}: {e.message}")
    print(f"  FAIL {f.name}: {e.message}")
```

---

## Info

### IN-01: `command-group.schema.json` — `values` 프로퍼티에 `additionalProperties` 미지정

**File:** `specs/schema/command-group.schema.json:57-60`

**Issue:**
`values` 필드는 `type: object`로만 선언되어 있고 내부 값 타입이 미제약이다. 현재 모든 실제 YAML은 `{"0": "string", "1": "string"}` 형태를 따르지만, 스키마가 이를 강제하지 않아 잘못된 값 맵(예: 숫자 키, 중첩 객체)이 검증을 통과한다. 의도된 유연성이면 주석으로 명시하는 것이 좋다.

**Fix:**
의도적 유연성이라면 description에 명시하라.

```json
"values": {
  "type": "object",
  "description": "Allowed value map. Keys are string representations of valid values, mapped to display labels. Empty object ({}) for free-form or no-predefined-value commands.",
  "additionalProperties": {"type": "string"}
}
```

단, WO 커맨드 등 특수 케이스가 있으면 `oneOf`로 분기 처리가 필요할 수 있다.

---

_Reviewed: 2026-05-13T10:57:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
