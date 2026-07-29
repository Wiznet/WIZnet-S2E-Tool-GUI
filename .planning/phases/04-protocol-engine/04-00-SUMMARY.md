---
phase: "04-protocol-engine"
plan: "00"
subsystem: "test-infrastructure"
tags: [pytest, tdd, wiz550, wave-0]
dependency_graph:
  requires: []
  provides:
    - tests/conftest.py (WIZ550 공통 픽스처 7개)
    - tests/test_wiz550_handler.py (PROTO-02/03/05/D-08 스텁)
    - tests/test_wiz550_profile.py (PROF-01/02/03 스텁)
  affects:
    - 04-01-PLAN.md (Wave 1 Handler 구현 후 SKIPPED → PASS 전환)
    - 04-02-PLAN.md (Wave 2 Profile 구현 후 SKIPPED → PASS 전환)
tech_stack:
  added:
    - pytest==9.0.3 (uv pip install pytest — pyproject.toml 없어 uv add 불가, pip로 대체)
  patterns:
    - skipif 기반 SKIPPED 스텁 패턴 (ImportError 시 전체 파일 건너뜀)
    - conftest.py 공통 픽스처 (sr_bytes, web_bytes 등)
key_files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_wiz550_handler.py
    - tests/test_wiz550_profile.py
  modified: []
decisions:
  - "pytest 설치: uv add 대신 uv pip install 사용 — pyproject.toml 없는 프로젝트 구조"
  - "XFAIL 대신 skipif 사용 — ImportError 시 수집 단계 오류 없이 깔끔한 SKIP 처리"
  - "테스트 파일에 pixture 파라미터 선언만으로 conftest.py 픽스처 자동 주입됨"
metrics:
  duration: "7m"
  completed_date: "2026-05-18T02:40:38Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 0
---

# Phase 4 Plan 00: Wave 0 테스트 인프라 구축 Summary

**One-liner:** pytest 기반 WIZ550 테스트 스텁 4파일 생성 — Wave 1/2 구현 후 즉시 PASS 전환 가능한 SKIPPED 상태 인프라

## What Was Built

Wave 0 목표인 테스트 인프라를 완전히 구축했다. `tests/` 디렉토리 아래 4개 파일을 생성하여 pytest가 정상 수집하고 모든 테스트가 깔끔하게 SKIPPED 되는 상태를 달성했다.

- **tests/__init__.py**: 빈 파일, pytest 패키지 인식용
- **tests/conftest.py**: WIZ550 공통 픽스처 7개 (sr_bytes/s2e_*/web_bytes/discovery_reply_sr/get_info_reply_sr), SR_SIZE=162, WEB_SIZE=133 상수 포함
- **tests/test_wiz550_handler.py**: 9개 테스트 — PROTO-02(헤더 빌드), PROTO-03(XOR 왕복), PROTO-05(Discovery 파싱), D-08(recv[6~7] 재파싱) 커버
- **tests/test_wiz550_profile.py**: 8개 테스트 — PROF-01(SR 162B 왕복), PROF-02(S2E 가변), PROF-03(WEB 133B 왕복) 커버

## Verification Results

```
17 tests collected
17 skipped (WIZ550MSGHandler/WIZ550Profile 미구현)
exit code: 5 (no tests ran — 정상)
```

Wave 1(04-01) 완료 후 `test_wiz550_handler.py` 9개가 PASS로 전환된다.
Wave 2(04-02) 완료 후 `test_wiz550_profile.py` 8개가 PASS로 전환된다.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: tests/ + conftest.py | `c2f85ec` | tests/__init__.py, tests/conftest.py |
| Task 2: 테스트 스텁 2파일 | `986a107` | tests/test_wiz550_handler.py, tests/test_wiz550_profile.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest 미설치**
- **Found during:** Task 1 검증
- **Issue:** `uv run pytest --version` 실패 — pytest 패키지 없음
- **Fix:** `uv pip install pytest` 로 설치 (pyproject.toml 없어 `uv add --dev` 불가)
- **Files modified:** 없음 (환경 설치)
- **Commit:** Task 1 커밋 전 해결

**2. [Rule 1 - Bug] SR_SIZE 상수 공백 불일치**
- **Found during:** Task 1 acceptance criteria 검증
- **Issue:** `SR_SIZE  = 162` (공백 2개) → `grep "SR_SIZE = 162"` 미매칭
- **Fix:** `SR_SIZE = 162` (공백 1개)로 수정
- **Files modified:** tests/conftest.py
- **Commit:** Task 1 커밋 (수정 후 포함)

### 계획 대비 테스트 수 차이

플랜 명세는 handler 7개, profile 6개를 요구했으나 실제로는 handler 9개, profile 8개를 생성했다. 플랜 스펙의 `test_discovery_parse_unknown`, `test_discovery_parse_too_short`, `test_sr_parse_too_short` 등이 플랜 본문에 포함되어 있어 모두 구현한 결과다. 테스트 수가 더 많은 것은 충분 조건 충족.

## Known Stubs

없음 — 이 플랜의 산출물 자체가 스텁 파일이며 의도된 것이다. Wave 1/2 구현 후 PASS로 전환 예정.

## Threat Flags

없음 — 테스트 파일은 프로덕션 네트워크 접근 없음. conftest.py 픽스처는 순수 메모리 바이트 생성.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| tests/__init__.py | FOUND |
| tests/conftest.py | FOUND |
| tests/test_wiz550_handler.py | FOUND |
| tests/test_wiz550_profile.py | FOUND |
| 04-00-SUMMARY.md | FOUND |
| commit c2f85ec | FOUND |
| commit 986a107 | FOUND |
