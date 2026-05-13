# Phase 1 Context: Schema Definition

**Created:** 2026-05-13  
**Phase:** 1 — Schema Definition  
**Status:** Decisions complete, ready to plan

---

## Decisions

### Decision 1: 스키마 검증 도구 — `jsonschema` Python 패키지

**결정:** `jsonschema` (PyPI) 사용.  
**근거:** Python 표준 JSON Schema 구현체. 외부 CLI 도구 없이 `device_spec_loader.py` 내에서 직접 호출 가능. Phase 3 loader integration과 자연스럽게 연결됨.  
**의존성:** `requirements.txt`에 `jsonschema` 추가 필요 (Phase 3 착수 전 확인).

---

### Decision 2: 스키마 엄격도 — core strict + ui flexible

**결정:** 핵심 구조 필드는 `additionalProperties: false`(엄격), `ui` 내부 필드는 `additionalProperties: true`(유연).

**엄격 적용 대상 (device.schema.json):**
- `name`, `family`, `channels`, `command_groups` — 필수, enum 검증
- `search_cmd_order` — optional, 타입 검증
- `overrides` — optional, 구조 검증

**유연 적용 대상:**
- `ui` 내부 (탭 구조, 위젯 힌트, `widget_overrides`) — `additionalProperties: true`
- 커맨드 `ui` 필드 내부 (`label`, `min`, `max`, `tooltip`, `password`, `null` 등)

---

#### 사용자 우려 기록 (원문 보존)

> "내가 이쪽에 잘 모르긴 하지만.. 완성이 되면 사내 개발자들이 쓰면서 문제가 최소한으로만 있어야 해. 신뢰성이 별로 없으면 아예 안쓸 거거든.."

**이 우려에 대한 판단 근거:**

신뢰성을 두 종류의 오류로 분리해서 보면:

| 오류 종류 | 예시 | 툴 영향 |
|---------|------|--------|
| **core 오류** | 없는 command_group 참조, 잘못된 family 값 | 장치 검색/설정 자체 파손 — 치명적 |
| **ui 오류** | ui 필드 오타, 알 수 없는 ui 키 | 위젯 하나 이상하게 표시 — 동작은 유지 |

`core strict`는 치명적 오류를 모두 걸러냅니다. 즉 **툴의 동작 신뢰성은 core strict만으로 보장됩니다.**

반면 `full strict (ui 포함)`은 에디터가 새 ui 힌트 필드를 추가할 때마다 스키마 선수정 의존성이 생깁니다. 개발자가 "멀쩡한 파일이 스키마 오류"를 반복 경험하면 스키마 검증 자체에 대한 신뢰가 무너집니다 — 사용자가 우려한 상황의 반대 방향으로 역효과가 납니다.

**결론:** core strict + ui flexible이 사내 개발자 신뢰성 확보에 더 적합하다. ui internals 스키마는 에디터 개발과 병행해서 점진적으로 추가한다.

---

### Decision 3: meta: 블록 — Phase 1 스키마에 optional로 선정의

**결정:** `command-group.schema.json`에 `meta:` 블록을 Phase 1에서 `optional`로 정의.  
**포함 필드:** `id`, `name`, `category`, `description`, `requires`, `conflicts`  
**근거:** 현재 YAML 파일들은 `meta:` 없이도 유효하게 통과. Phase 2에서 추가 시 스키마 재수정 없이 바로 유효성 검증 가능. 데이터 계약을 한 번에 확립.

---

## Constraints (researcher/planner 인수인계)

1. `jsonschema` 패키지를 추가해야 하므로 `requirements.txt` 수정 필요 — Phase 1에서는 스키마 파일만 생성, loader 연동은 Phase 3
2. Phase 1 산출물은 `specs/schema/device.schema.json`과 `specs/schema/command-group.schema.json` 두 파일만
3. 기존 `specs/devices/*.yaml` 전체, `specs/commands/*.yaml` 전체가 스키마 통과해야 함 — 파일 수정 없이
4. `ui: null` (security.yaml의 UF 커맨드)이 유효한 케이스 — 스키마에서 허용해야 함
5. `password: true` (security.yaml QP 커맨드의 ui 내부) — ui flexible이므로 별도 정의 불필요

## Out of Scope (이 Phase에서 하지 않음)

- `device_spec_loader.py` 수정 — Phase 3
- `meta:` 블록 실제 추가 — Phase 2
- `jsonschema` 패키지 설치/의존성 실제 추가 — Phase 3 착수 전

---

## Next

`/gsd-plan-phase 1` — Phase 1 계획 수립
