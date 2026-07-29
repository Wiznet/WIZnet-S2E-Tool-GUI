---
phase: 05-devicespec-yaml
reviewed: 2026-05-18T15:35:00Z
depth: quick
files_reviewed: 6
files_reviewed_list:
  - specs/schema/device.wiz550.schema.json
  - validate_schemas.py
  - tests/test_wiz550_spec.py
  - specs/devices/WIZ550SR.yaml
  - specs/devices/WIZ550S2E.yaml
  - specs/devices/WIZ550WEB.yaml
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-18T15:35:00Z
**Depth:** quick (+ WIZ550Profile.py 교차 검증)
**Files Reviewed:** 6
**Status:** issues_found

## Summary

WIZ550SR/S2E/WEB DeviceSpec YAML 3개 파일과 스키마, 검증 스크립트, 테스트를 검토했다.
WIZ550Profile.py와 field.id 교차 검증을 수행하여 실제 dict 키 불일치를 발견했다.

크리티컬 이슈는 없다. 경고 3건은 모두 field.id 불일치 또는 스키마 허점으로 Phase 6에서
UI 렌더링 시 KeyError 또는 잘못된 데이터 바인딩으로 이어질 수 있다.

---

## Warnings

### WR-01: WIZ550WEB.yaml — `serial_command` disabled 필드가 parse_web() 반환 dict에 없음

**File:** `specs/devices/WIZ550WEB.yaml:145`
**Issue:**
WEB YAML에 `serial_command` 필드가 `disabled:true`로 포함되어 있으나, `WIZ550Profile.parse_web()` 반환 dict에는 `serial_command` 키가 존재하지 않는다 (WEB 구조체에 없음 — `WEB_FORMAT` 참조).
YAML 주석도 이를 인식하고 있지만, `test_web_no_pw_connect` 같은 방어 테스트가 `serial_command`에 대해서는 없다.

Phase 6에서 `disabled` 필드를 포함한 모든 field.id에 대해 UI 빌더가 parse_web() dict를 조회할 경우 KeyError 또는 빈 값 표시가 발생한다.

**Fix:**
disabled 필드는 parse 결과와 무관하게 표시 전용으로 처리하는 UI 빌더 계약을 Phase 6 설계에 명시적으로 정의해야 한다. 또는 `serial_command`를 WEB YAML에서 완전히 제거하고 필요시 주석으로만 남긴다.

테스트에 다음을 추가하여 YAML 명세를 고정:
```python
def test_web_serial_command_disabled_not_in_parse():
    """serial_command는 disabled:true 이지만 parse_web() dict에 없다."""
    data = _load_yaml(WEB_YAML)
    disabled_ids = {f["id"] for s in data["ui"]["sections"] for f in s["fields"] if f.get("disabled")}
    assert "serial_command" in disabled_ids
    # 빌더에게 'disabled' 필드는 parse 결과 없어도 ok 임을 문서화
```

---

### WR-02: 스키마 `choices` 타입이 integer key를 허용하지 않음

**File:** `specs/schema/device.wiz550.schema.json:62`
**Issue:**
스키마에서 `choices`는 `"additionalProperties": {"type": "string"}` 로 정의되어 있다.
그런데 YAML에서 choices 키를 정수로 작성하면 (`300: "300 bps"`) PyYAML이 정수 키로 파싱하고,
jsonschema는 object property key를 문자열로만 인식한다.

실제 테스트에서 `validate_schemas.py`가 통과하는지 확인이 필요하다.
YAML `choices` 블록의 키는 `"0"`, `"1"` 등 문자열로 쿼트해야 스키마와 일치한다.
현재 WIZ550SR.yaml:51~84 등 모든 choices 키가 인용부호 없이 작성되어 있다.

**Fix:**
스키마에서 choices를 integer key 허용으로 완화하거나, YAML choices 키를 명시적으로 문자열로 쿼트:
```yaml
# 현재 (잠재적 문제)
choices:
  300: "300 bps"

# 수정
choices:
  "300": "300 bps"
```
또는 스키마에서:
```json
"choices": {
  "type": "object"
}
```
(additionalProperties 제약 없이 — key 타입은 JSON에서 항상 string이므로 jsonschema 통과 여부는 런타임 확인 필요)

---

### WR-03: `test_wiz550sr_schema_valid` — validate_schemas.py 전체 실행으로 SR만 검증 보장 안 됨

**File:** `tests/test_wiz550_spec.py:30`
**Issue:**
`test_wiz550sr_schema_valid`, `test_wiz550s2e_schema_valid`, `test_wiz550web_schema_valid` 세 테스트가 모두 동일하게 `validate_schemas.py` 전체를 실행한다. 즉, 세 테스트 중 하나만 실패해도 나머지 둘도 같은 이유로 실패하고, 개별 YAML 어느 것이 문제인지 격리하지 못한다.

또한 `SPEC-04 test_validate_schemas_all_pass`와 완전 중복이다 (동일 subprocess 호출).

**Fix:**
각 YAML별 스키마 검증을 단위 테스트로 분리:
```python
import jsonschema, json

def _get_schema(name="device.wiz550.schema.json"):
    schema_path = Path(__file__).parent.parent / "specs" / "schema" / name
    return json.loads(schema_path.read_text(encoding="utf-8"))

def test_wiz550sr_schema_valid():
    data = _load_yaml(SR_YAML)
    schema = _get_schema()
    jsonschema.validate(instance=data, schema=schema)  # 예외 없으면 통과
```
이렇게 하면 실패 시 어느 YAML이 문제인지 즉시 식별 가능하고 SPEC-04와 중복이 제거된다.

---

## Info

### IN-01: WIZ550S2E `product_code` — S2E 판별 불확실성 문서화 필요

**File:** `specs/devices/WIZ550S2E.yaml:17`
**Issue:**
`product_code: [0x00, 0x00, 0x00]` 은 "전부 0"으로, WIZ550SR의 `[0x02, 0x00, 0x00]`과 구분은 되지만
실제 S2E 장치의 module_type 값이 이것이 맞는지 Java 원본 대조 여부가 YAML 주석에 언급되어 있지 않다.
WIZ550Profile.build_s2e() 내 주석 `'000000'`과는 일치한다.

**Fix:** 주석에 Java 원본 참조 또는 실물 확인 여부를 한 줄 기재.

---

### IN-02: `test_wiz550s2e_schema_valid` 에 `result.stderr` 누락

**File:** `tests/test_wiz550_spec.py:72`
**Issue:**
`test_wiz550sr_schema_valid`(37행)는 `assert` 메시지에 `result.stderr`를 포함하나,
`test_wiz550s2e_schema_valid`(72행)는 `result.stderr`가 빠져 있어 실패 시 오류 원인 파악이 어렵다.

**Fix:**
```python
# 72행
assert result.returncode == 0, f"validate_schemas.py failed:\n{result.stdout}\n{result.stderr}"
```

---

### IN-03: WIZ550WEB YAML `disabled` 필드가 `test_web_disabled_fields` 에서 `local_port` 검증 위치가 options 섹션이 아닌 network 섹션

**File:** `tests/test_wiz550_spec.py:118`
**Issue:**
`required_disabled` 셋에 `local_port`가 포함되어 있으나 WIZ550WEB.yaml에서 `local_port`는 network 섹션(48행)에 있고 `serial_command`는 options 섹션(145행)에 있다. 테스트 자체는 섹션 구분 없이 전체를 스캔하므로 현재는 통과하지만, 섹션별 위치 검증이 없어 향후 YAML 구조 변경 시 잘못된 섹션에 들어가도 감지 못한다.

**Fix (선택적):** info 수준으로 즉각 수정 필요는 없으나, 섹션별 필드 위치 검증 테스트를 추가하면 구조 무결성이 강화된다.

---

_Reviewed: 2026-05-18T15:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick + cross-file (WIZ550Profile.py 교차 검증)_
