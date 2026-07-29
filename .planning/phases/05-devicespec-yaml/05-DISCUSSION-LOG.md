# Phase 5: DeviceSpec YAML - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 05-devicespec-yaml
**Areas discussed:** 스키마 호환 전략, UI 필드 정의 깊이, WIZ550S2E 가변 구조 표현, WIZ550WEB 비활성 필드 처리

---

## 스키마 호환 전략

| Option | Description | Selected |
|--------|-------------|----------|
| device.schema.json 확장 | family enum에 'wiz550' 추가 + command_groups 선택 필드 전환 | |
| **별도 WIZ550 스키마** | specs/schema/device.wiz550.schema.json 신규 작성, validate_schemas.py 라우팅 추가 | ✓ |
| 더미 command_groups 참조 | wiz550_binary.yaml 스텁 생성 후 참조 | |

**User's choice:** 별도 WIZ550 스키마  
**Notes:** 기존 스키마(text-command 기반)와 WIZ550(binary protocol)의 구조적 불일치를 깔끔하게 분리. validate_schemas.py에서 family == "wiz550" 분기로 라우팅.

---

## UI 필드 정의 깊이

| Option | Description | Selected |
|--------|-------------|----------|
| **섹션 + 필드 전체 (권장)** | field_id, label, type, choices 포함. Phase 6는 YAML만 읽으면 어떤 위젯도 생성 가능 | ✓ |
| 섹션 + 필드명/라벨 목록만 | field_id와 label만. 위젯 타입은 Phase 6에서 하드코딩 | |
| 섹션 이름만 | 섹션 이름만. 모든 필드는 Phase 6 하드코딩 | |

**User's choice:** 섹션 + 필드 전체  
**Notes:** Phase 6 `_build_wiz550_panel()`이 YAML을 단일 데이터 소스로 삼아 UI를 생성. 06-CONTEXT.md D-06의 `field.label`, `_make_field_widget(field)` 패턴과 일치.

---

## YAML UI 최상위 구조

| Option | Description | Selected |
|--------|-------------|----------|
| **ui.sections 구조 (권장)** | ui.sections: [{id, label, fields}] — 06-CONTEXT.md D-06과 직접 매핑 | ✓ |
| ui.tabs + groups 기존 패턴 | 기존 YAML과 일관성, tabs 구조 유지 | |

**User's choice:** ui.sections (context 작성자 결정)  
**Notes:** 06-CONTEXT.md에서 `spec.sections.items()` 코드 패턴을 제시하고 있어 sections 구조를 채택.

---

## WIZ550S2E 가변 구조 표현

| Option | Description | Selected |
|--------|-------------|----------|
| **condition 필드 (권장)** | MQTT/Modbus 섹션에 condition: mqtt/modbus. YAML이 자기 설명적 | ✓ |
| 모든 필드 무조건 포함 | 조건 없이 단순. Phase 6에서 fw_ver 판별 로직 하드코딩 필요 | |
| 별도 YAML 3개 | WIZ550S2E / WIZ550S2E_MQTT / WIZ550S2E_Modbus. REQUIREMENTS.md 3파일 명시와 불일치 | |

**User's choice:** condition 필드 (권장)  
**Notes:** 단일 WIZ550S2E.yaml에 세 변형 모두 표현. Phase 6는 section.condition을 읽어 fw_ver 기반으로 show/hide 결정. condition 값: "mqtt" (fw_ver[1] % 2 != 0 AND len >= 232) | "modbus" (fw_ver[1] % 2 == 0 AND len >= 164).

---

## WIZ550WEB 비활성 필드 처리

사전 비교 제시 (상세 장단점 요청에 따라):

| Option | YAML 단순도 | SPEC-03 준수 | 사용자 UX | Phase 6 구현 |
|--------|------------|-------------|---------|-------------|
| 아예 제외 | ✅ 가장 단순 | ❌ 위반 | 필드 없음 | 로직 0개 |
| **disabled: true (권장)** | 중간 | ✅ 준수 | 회색 처리 | disabled 위젯 | 
| hidden_fields 리스트 | ❌ 가장 복잡 | ✅ 준수 | 숨겨짐 | 두 군데 관리 |

**User's choice:** disabled: true 마커 (권장)  
**Notes:** REQUIREMENTS.md SPEC-03 "WIZ550WEB 비활성 필드(working_mode, remote_ip 등)가 YAML에 명시적으로 정의됨" 요구사항을 충족. 비활성화 필드: working_mode, remote_ip, remote_port, local_port, at_cmd.

---

## Claude's Discretion

- WIZ550SR data_bits 드롭다운 (8-bit만 가능) 처리 방식 — 구현자 판단
- baud_rate choices 상한 — WIZ550Profile.py 기준
- WIZ550WEB UART 파라미터 상세 제약 — parse_web() 반환 필드 기준

## Deferred Ideas

- WIZ550WEB UART1 포트 실물 동작 확인 — 실물 장치 확보 후 UAT-02
- device_spec_loader.py WIZ550 통합 — Phase 6 범위
- 기존 WIZ5xxSR/WIZ1x0SR UI 토큰 소급 적용 — 별도 Phase
