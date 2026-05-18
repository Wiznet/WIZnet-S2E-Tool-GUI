---
phase: "04-protocol-engine"
plan: "02"
subsystem: "WIZ550 Config 구조체 파서/빌더"
tags: [profile, struct, wiz550, tdd, wave-2]
dependency_graph:
  requires:
    - "WIZ1x0Profile.py 패턴 (기존)"
    - "tests/conftest.py (Wave 0 픽스처 — sr_bytes 등 추가됨)"
    - "WIZ550MSGHandler.py (Wave 1 결과)"
  provides:
    - "WIZ550Profile.py (SR/S2E/WEB 구조체 파서/빌더)"
    - "tests/conftest.py (sr_bytes/web_bytes/s2e_*_bytes 픽스처 5개 추가)"
  affects:
    - "Phase 6 (GUI 통합) — main_gui.py에서 parse_sr/s2e/web import"
    - "WIZ550MSGHandler._parse_get_info_reply — WIZ550Profile import 완성"
tech_stack:
  added: []
  patterns:
    - "struct.pack/unpack + assert calcsize (WIZ1x0Profile 패턴 이식)"
    - "_parse_base_162 공유 헬퍼 (D-02: SR과 S2E가 동일 162B 기본 구조 공유)"
    - "D-04 이중 판별: 데이터 길이 우선 + fw_ver[1] 홀짝 검증 (S2E 가변)"
    - "Pitfall 3: baud_rate='I' (unsigned), port='H' (unsigned)"
    - "Pitfall 6: WEB 구조체에 pw_connect 없음"
key_files:
  created:
    - WIZ550Profile.py
  modified:
    - tests/conftest.py
decisions:
  - "parse_s2e/build_s2e를 Task 1 파일에 통합 구현 — SR/WEB/S2E 세 함수군이 하나의 논리 단위"
  - "conftest.py에 sr_bytes/web_bytes/s2e_base/modbus/mqtt 픽스처 5개 추가 (Wave 0에서 누락됨)"
  - "fw_ver[1] 오프셋 확인: SR_FORMAT 상 offset 31 (0-indexed) — struct pack 순서로 검증"
metrics:
  duration: "~30분"
  completed_date: "2026-05-18T11:59:11Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 4 Plan 02: WIZ550Profile 구현 Summary

**One-liner:** struct.pack/unpack 기반 WIZ550SR/S2E/WEB 3종 Config 162B/133B 파서/빌더 — D-04 이중 판별로 S2E base/modbus/mqtt 가변 구조 지원

---

## What Was Built

`WIZ550Profile.py` (228줄) — WIZ550SR/S2E/WEB Config bytes ↔ Python dict 변환 전담.

### 공개 API

| 함수 | 역할 | 요구사항 |
|------|------|---------|
| `parse_sr(data)` | WIZ550SR 162B → dict | PROF-01 |
| `build_sr(d)` | dict → WIZ550SR 162B | PROF-01 |
| `parse_s2e(data)` | WIZ550S2E 162~232B → dict, 3종 변형 판별 | PROF-02 |
| `build_s2e(d)` | dict → WIZ550S2E (s2e_variant에 따라 162/164/232B) | PROF-02 |
| `parse_web(data)` | WIZ550WEB 133B → dict (pw_connect 없음) | PROF-03 |
| `build_web(d)` | dict → WIZ550WEB 133B | PROF-03 |

### 내부 헬퍼 (D-02)

`_parse_base_162(data)` — SR과 S2E가 공유하는 기본 162B 구조 파싱. 코드 중복 없이 SR/S2E 공유.

### 구조체 상수 (import 시점 검증)

| 상수 | 크기 | assert |
|------|------|--------|
| SR_FORMAT | 162B | `assert struct.calcsize(SR_FORMAT) == 162` |
| WEB_FORMAT | 133B | `assert struct.calcsize(WEB_FORMAT) == 133` |
| MQTT_FORMAT | 70B | `assert struct.calcsize(MQTT_FORMAT) == 70` |
| MODBUS_FORMAT | 2B | `assert struct.calcsize(MODBUS_FORMAT) == 2` |

### S2E 가변 구조 (D-04 이중 판별)

```
len(data) >= 232 AND fw_ver[1] % 2 != 0 → mqtt (70B 확장)
len(data) >= 164 AND fw_ver[1] % 2 == 0 → modbus (2B 확장)
기본 → base (162B)
```

데이터 길이가 주방어선 — fw_ver[1] 홀짝은 검증용 보조 조건.

---

## Test Results

```
tests/test_wiz550_handler.py  9 passed  (Wave 1 핸들러 — PASS 유지)
tests/test_wiz550_profile.py  8 passed  (PROF-01/02/03 전부 PASS)
─────────────────────────────────────────
17 passed, 0 failed in 0.49s
```

### 개별 테스트

| 테스트 | 결과 | 요구사항 |
|--------|------|---------|
| test_sr_parse_returns_dict | PASSED | PROF-01 |
| test_sr_roundtrip | PASSED | PROF-01 |
| test_sr_parse_too_short | PASSED | T-04-02-01, ASVS V5 |
| test_s2e_base_variant | PASSED | PROF-02, D-04 |
| test_s2e_modbus_variant | PASSED | PROF-02, D-04 |
| test_s2e_mqtt_variant | PASSED | PROF-02, D-04 |
| test_web_parse_returns_dict | PASSED | PROF-03 |
| test_web_roundtrip | PASSED | PROF-03 |

---

## Commits

| Task | Commit | 내용 |
|------|--------|------|
| Wave 0/1 복원 (선행) | `16bb8a4` | WIZ550MSGHandler.py, pytest.ini, tests/__init__.py, tests/test_wiz550_handler.py (42a71cd에서 복원) |
| Task 1+2 (통합) | `374e1d5` | WIZ550Profile.py, tests/conftest.py, tests/test_wiz550_profile.py |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] conftest.py에 sr_bytes 등 픽스처 누락**
- **Found during:** Task 1 TDD RED 준비
- **Issue:** Wave 0 conftest.py에 `get_info_reply_sr` 픽스처만 있고, `sr_bytes`, `web_bytes`, `s2e_base_bytes`, `s2e_modbus_bytes`, `s2e_mqtt_bytes` 5개 픽스처가 없었음. 테스트 수집 단계에서 fixture not found 오류 발생 필연적.
- **Fix:** conftest.py에 WEB_FORMAT, MQTT_FORMAT, MODBUS_FORMAT 상수 및 5개 픽스처 추가.
- **Files modified:** tests/conftest.py
- **Commit:** 374e1d5

**2. [Rule 3 - Blocking] 워크트리에 Wave 0/1 파일 부재**
- **Found during:** 실행 시작 시
- **Issue:** 워크트리 브랜치(`worktree-agent-a11d34211d71a8de7`)에 `tests/`, `WIZ550MSGHandler.py`, `pytest.ini`가 없었음. 베이스 커밋 42a71cd에는 파일이 존재하지만 워킹트리에 체크아웃되지 않은 상태.
- **Fix:** `git show 42a71cd:{파일}` 로 4개 파일 추출 후 워킹트리에 복원. 별도 커밋(16bb8a4)으로 기록.
- **Files modified:** WIZ550MSGHandler.py, pytest.ini, tests/__init__.py, tests/test_wiz550_handler.py
- **Commit:** 16bb8a4

### 통합 구현

Task 1(SR/WEB)과 Task 2(S2E)를 단일 파일·커밋으로 구현했다.
- 근거: SR/WEB/S2E 함수군은 동일 파일 내에서 `_parse_base_162()` 헬퍼를 공유하는 단일 논리 단위임. 분리하면 헬퍼 중복 또는 순환 참조가 발생한다.
- 영향: 없음 — 두 Task의 acceptance criteria 모두 충족.

---

## Threat Model Coverage

| Threat ID | 구현 | 파일 |
|-----------|------|------|
| T-04-02-01 | `len(data) < SR_SIZE/WEB_SIZE` + `try: unpack ... except struct.error: return {}` | WIZ550Profile.py |
| T-04-02-02 | `len(data) >= SIZE + EXT_SIZE` 조건 먼저, fw_ver[1] 홀짝 검증 보조. 확장 파싱 실패 시 base fallback | WIZ550Profile.py |
| T-04-02-03 | import 시점 `assert calcsize == SIZE` + 빌드 시점 `assert len(raw) == SIZE` | WIZ550Profile.py |
| T-04-02-04 | 최소 크기 사전 체크로 struct.unpack 호출 전 보호 | WIZ550Profile.py |
| T-04-02-05 | `errors='replace'` (accept 결정) | WIZ550Profile.py |

---

## Known Stubs

없음 — 모든 함수가 실제 데이터를 처리하며 테스트 왕복 검증 통과.

---

## Threat Flags

없음 — 신규 네트워크 엔드포인트 없음. 신규 표면이 plan의 threat_model에 모두 포함됨.

---

## Self-Check

### 파일 존재 확인

- [x] WIZ550Profile.py 존재 — 228줄
- [x] tests/conftest.py 수정됨 (sr_bytes 등 픽스처 5개 추가)
- [x] .planning/phases/04-protocol-engine/04-02-SUMMARY.md 생성됨

### 커밋 존재 확인

- [x] 16bb8a4 — chore(04-02): restore Wave 0/1 artifacts
- [x] 374e1d5 — feat(04-02): Task 1 — WIZ550Profile SR/WEB/S2E 구현

### 테스트 결과

- [x] `uv run pytest tests/ -v` → 17 passed, 0 failed

## Self-Check: PASSED
