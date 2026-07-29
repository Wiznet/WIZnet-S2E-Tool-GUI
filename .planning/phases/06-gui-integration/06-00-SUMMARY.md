---
phase: 06-gui-integration
plan: "00"
subsystem: test-infrastructure
tags: [pytest, pyqt5, gui-test, wave-0, nyquist]
dependency_graph:
  requires:
    - "04-protocol-engine (WIZ550MSGHandler, WIZ550Profile)"
    - "05-devicespec-yaml (YAML 3종)"
  provides:
    - "tests/test_wiz550_gui.py — UI-01~04 단위 테스트 스텁 6개"
    - "tests/conftest.py — qapp 픽스처 (PyQt5 QApplication 세션 스코프)"
  affects:
    - "tests/ 전체 (conftest.py 공유 픽스처)"
tech_stack:
  added:
    - "pytest.ini — testpaths=tests, pythonpath=."
  patterns:
    - "xfail(strict=False) 스텁 패턴 — Wave 0 nyquist 충족"
    - "QApplication.instance() 재사용 가드 패턴"
key_files:
  created:
    - "tests/test_wiz550_gui.py"
    - "tests/__init__.py"
    - "pytest.ini"
    - "WIZ550MSGHandler.py (worktree 의존성)"
    - "WIZ550Profile.py (worktree 의존성)"
  modified:
    - "tests/conftest.py (qapp 픽스처 추가)"
decisions:
  - "test_wiz550_resetter_opcodes는 WIZ550MSGHandler.py import만으로 즉시 PASS — QApplication 불필요"
  - "pytest.ini를 worktree에 추가 (Rule 3: blocking issue — testpaths 미설정 시 수집 실패)"
  - "WIZ550MSGHandler.py, WIZ550Profile.py를 worktree에 복사 (Rule 3: test_wiz550_resetter_opcodes 의존성)"
  - "test_wiz550_handler.py는 메인 저장소에만 존재 — nyquist_compliant: true (Wave 0에서 재생성 불필요)"
metrics:
  duration: "~30분"
  completed: "2026-05-18T12:02:39Z"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase 6 Plan 00: Wave 0 테스트 인프라 구축 Summary

**One-liner:** PyQt5 QApplication 픽스처 + UI-01~04 xfail 스텁 6개로 Wave 0 Nyquist 충족 (1 PASS + 5 XFAIL)

## What Was Built

Phase 6 GUI Integration Wave 0 — 테스트 인프라 구축 완료.

Wave 1~3의 모든 태스크가 자동화된 verify 커맨드(`uv run pytest tests/test_wiz550_gui.py -x`)를 가지려면 테스트 파일이 먼저 존재해야 한다 (Nyquist 규칙). 이 플랜에서 해당 인프라를 구축했다.

## Task Summary

### Task 1: tests/ 디렉토리 초기화 + conftest.py에 qapp 픽스처 추가

- **tests/__init__.py** 생성 (빈 파일)
- **tests/conftest.py** 생성:
  - Phase 4 공통 픽스처 (`_make_header`, `_make_sr_config_bytes`, `_make_web_config_bytes`, `sr_bytes`, `web_bytes`, `s2e_*_bytes`, `get_info_reply_sr`) 포함
  - **qapp 픽스처** 추가 (line 289): `@pytest.fixture(scope="session")`, `QApplication.instance()` 재사용 가드
- **test_wiz550_handler.py 존재 확인**: 메인 저장소(`d:/user/Documents/.../tests/test_wiz550_handler.py`)에 존재 확인 — nyquist_compliant: true (Wave 0에서 별도 스텁 생성 불필요)
- **커밋**: `f4da138`

### Task 2: test_wiz550_gui.py — UI-01~04 테스트 스텁 6개 작성

- **tests/test_wiz550_gui.py** 생성: 6개 테스트 함수
  | 함수명 | Req ID | 마커 | 상태 |
  |--------|--------|------|------|
  | test_merge_wiz550_results | UI-01 | xfail(strict=False) | XFAIL |
  | test_search_each_dev_filters_wiz550 | UI-01 | xfail(strict=False) | XFAIL |
  | test_build_panel_sections | UI-02 | xfail(strict=False) | XFAIL |
  | test_disabled_field_widget | UI-02 | xfail(strict=False) | XFAIL |
  | test_setinfo_roundtrip | UI-03 | xfail(strict=False) | XFAIL |
  | test_wiz550_resetter_opcodes | UI-04 | 없음 | PASS |

- **pytest.ini** 추가 (Rule 3 — blocking 방지): `testpaths = tests, pythonpath = .`
- **pytest 실행 결과**: `1 passed, 5 xfailed in 0.72s`
- **커밋**: `555221d`

## pytest 실행 결과

```
tests/test_wiz550_gui.py::test_merge_wiz550_results XFAIL
tests/test_wiz550_gui.py::test_search_each_dev_filters_wiz550 XFAIL
tests/test_wiz550_gui.py::test_build_panel_sections XFAIL
tests/test_wiz550_gui.py::test_disabled_field_widget XFAIL
tests/test_wiz550_gui.py::test_setinfo_roundtrip XFAIL
tests/test_wiz550_gui.py::test_wiz550_resetter_opcodes PASSED
======================== 1 passed, 5 xfailed in 0.72s =========================
```

## Nyquist Compliance

| 파일 | 상태 | 비고 |
|------|------|------|
| tests/test_wiz550_handler.py | 메인 저장소에 존재 | Phase 4 산출물, Wave 0 재생성 불필요 |
| tests/test_wiz550_gui.py | 이 플랜에서 생성 | 6개 스텁 수집 성공 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest.ini 없음 — 테스트 수집 불가**

- **Found during:** Task 2
- **Issue:** 워크트리 브랜치(`8ca6861`)에는 pytest.ini가 없어 `uv run pytest tests/` 실행 시 testpaths를 찾지 못함
- **Fix:** pytest.ini를 워크트리에 추가 (`testpaths = tests, pythonpath = .`)
- **Files modified:** `pytest.ini`
- **Commit:** `555221d`

**2. [Rule 3 - Blocking] WIZ550MSGHandler.py, WIZ550Profile.py 없음 — test_wiz550_resetter_opcodes PASS 불가**

- **Found during:** Task 2
- **Issue:** 워크트리 브랜치에는 WIZ550MSGHandler.py, WIZ550Profile.py가 없어 `from WIZ550MSGHandler import ...` import 실패
- **Fix:** 메인 저장소에서 두 파일을 워크트리로 복사
- **Files modified:** `WIZ550MSGHandler.py`, `WIZ550Profile.py` (신규 추가)
- **Commit:** `555221d`

**3. [Rule 3 - Blocking] tests/ 디렉토리 없음 — 파일 생성 불가**

- **Found during:** Task 1
- **Issue:** 워크트리 브랜치 베이스(`8ca6861`)에 tests/ 폴더가 없음 (master에서 Phase 4 이후 추가됨)
- **Fix:** `mkdir -p tests/` 후 `tests/__init__.py`, `tests/conftest.py` 직접 생성
- **Files modified:** `tests/__init__.py`, `tests/conftest.py`
- **Commit:** `f4da138`

## Known Stubs

모든 xfail 스텁은 의도적인 것으로, Wave 1~3 구현 완료 시 제거 예정:

| 파일 | 테스트 | Wave | 사유 |
|------|--------|------|------|
| tests/test_wiz550_gui.py | test_merge_wiz550_results | Wave 1 | _merge_wiz550_results 미구현 |
| tests/test_wiz550_gui.py | test_search_each_dev_filters_wiz550 | Wave 1 | search_each_dev 분기 미구현 |
| tests/test_wiz550_gui.py | test_build_panel_sections | Wave 2 | _build_wiz550_panel 미구현 |
| tests/test_wiz550_gui.py | test_disabled_field_widget | Wave 2 | _make_wiz550_field_widget 미구현 |
| tests/test_wiz550_gui.py | test_setinfo_roundtrip | Wave 3 | fill_devinfo_wiz550/fill_setinfo_wiz550 미구현 |

## Commits

| Hash | Message |
|------|---------|
| `f4da138` | chore(06-00): tests/ 인프라 초기화 + conftest.py에 qapp 픽스처 추가 |
| `555221d` | test(06-00): UI-01~04 테스트 스텁 6개 작성 + pytest.ini + 의존 모듈 추가 |

## Self-Check: PASSED

- [x] tests/test_wiz550_gui.py 존재
- [x] tests/conftest.py에 qapp 픽스처 존재 (line 289)
- [x] pytest 수집: 6개 테스트
- [x] test_wiz550_resetter_opcodes: PASS
- [x] xfail 5개: XFAIL 상태
- [x] 커밋 f4da138 존재
- [x] 커밋 555221d 존재
