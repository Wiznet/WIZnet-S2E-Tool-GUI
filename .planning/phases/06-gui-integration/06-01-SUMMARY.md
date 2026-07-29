---
phase: 06-gui-integration
plan: "01"
subsystem: ui
tags: [pyqt5, wiz550, search, threading, gui-integration]

# Dependency graph
requires:
  - phase: 04-protocol-engine
    provides: WIZ550Searcher QThread + search_done 시그널
  - phase: 05-devicespec-yaml
    provides: DeviceSpec YAML (WIZ550SR/S2E/WEB)
provides:
  - "search_pre()에 WIZ550Searcher 병행 시작 코드"
  - "_merge_wiz550_results() 메서드 — 연두색 배경으로 list_device 테이블에 병합"
  - "search_each_dev() _binary_proto 필터 — wiz550 텍스트 커맨드 파이프라인 제외"
affects:
  - 06-02
  - 06-03

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "WIZ1x0SR 병행 검색 패턴을 WIZ550에 동일하게 적용 (항상 병행 시작, 체크박스 없음)"
    - "_binary_proto 튜플로 바이너리 프로토콜 장치 일괄 필터링"

key-files:
  created: []
  modified:
    - main_gui.py

key-decisions:
  - "WIZ550Searcher는 체크박스 없이 항상 병행 시작 (D-07)"
  - "_binary_proto = ('wiz1x0', 'wiz550') 튜플로 향후 프로토콜 추가 확장성 확보"
  - "WIZ550 장치 배경색: 연두색(0xD0,0xFF,0xD0) — WIZ1x0 하늘색(0xE0,0xF4,0xFF)과 구분"

patterns-established:
  - "새 바이너리 프로토콜 장치 추가 시 _binary_proto 튜플에만 추가하면 search_each_dev 필터 자동 적용"

requirements-completed:
  - UI-01

# Metrics
duration: 7min
completed: 2026-05-18
---

# Phase 06 Plan 01: WIZ550 검색 통합 Summary

**search_pre()에 WIZ550Searcher 항상 병행 시작 + _merge_wiz550_results() 연두색 테이블 병합 + _binary_proto 튜플 필터로 WIZ5xxSR 텍스트 커맨드 오전송 방지**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-18T14:53:00Z
- **Completed:** 2026-05-18T21:00:19Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- WIZ550MSGHandler import 추가 (WIZ550Searcher/Getter/Setter/Resetter/OP_*)
- __init__에 wiz550_searcher/\_wiz550_search_pending 속성 초기화
- search_pre()에 WIZ550Searcher 항상 병행 시작 (isRunning() 체크로 WinError 10048 방지)
- _merge_wiz550_results(): 연두색 배경(D0,FF,D0)으로 list_device에 WIZ550 장치 추가
- search_each_dev(): _binary_proto 튜플('wiz1x0', 'wiz550')로 바이너리 프로토콜 장치 일괄 제외
- 전체 테스트 27개 PASSED (회귀 없음)

## 수정된 함수명과 라인 번호

| 항목 | 라인 | 설명 |
|------|------|------|
| import WIZ550MSGHandler | 16~24 | WIZ550Searcher/Getter/Setter/Resetter/OP_* |
| __init__ 초기화 | 889~890 | wiz550_searcher = None, _wiz550_search_pending = False |
| search_pre() WIZ550Searcher 시작 | 2355~2365 | 항상 병행, isRunning() 가드 |
| _merge_wiz550_results() | 2413~2451 | WIZ550 결과 병합 + 연두색 배경 |
| search_each_dev() 필터 | 2486~2489 | _binary_proto = ('wiz1x0', 'wiz550') |

## WIZ550Searcher 시작 조건

- 항상 병행 시작 (체크박스 없음, D-07 결정)
- `self.wiz550_searcher is None or not self.wiz550_searcher.isRunning()` 조건으로 중복 실행 방지
- `timeout=self.search_pre_wait_time` — WIZ1x0Searcher와 동일한 타임아웃 사용

## _merge_wiz550_results 구현 내용

- WIZ1x0SR 패턴 동일하게 적용
- 기존 mac_list_str()으로 중복 MAC 체크 후 신규만 추가
- `device_dict['mac']` 키 사용 (WIZ550Searcher search_done 시그널 dict 구조)
- `dev_profile[mac_str] = device_dict` — `_proto='wiz550'` 포함 dict 전체 저장
- 연두색 배경(0xD0, 0xFF, 0xD0) — WIZ1x0 하늘색(0xE0, 0xF4, 0xFF)과 구분
- 컬럼: (0) mac, (1) device_type, (2) fw_str

## search_each_dev 필터 변경 내용

**변경 전:**
```python
dev_info_list = [
    d for d in dev_info_list
    if self.dev_profile.get(d[0], {}).get('_proto') != 'wiz1x0'
]
```

**변경 후:**
```python
_binary_proto = ('wiz1x0', 'wiz550')
dev_info_list = [
    d for d in dev_info_list
    if self.dev_profile.get(d[0], {}).get('_proto') not in _binary_proto
]
```

## Task Commits

1. **Task 1: __init__ 초기화 블록에 WIZ550 searcher 속성 추가** - `d22b7f3` (feat)
2. **Task 2: search_pre() + _merge_wiz550_results + search_each_dev 필터** - `f96b6e0` (feat)

## Files Created/Modified

- `main_gui.py` — WIZ550 검색 통합 (import + __init__ + search_pre + _merge_wiz550_results + search_each_dev 필터)

## Decisions Made

- D-07 구현: WIZ550Searcher 체크박스 없이 항상 병행 시작
- _binary_proto 튜플 방식: 향후 새 바이너리 프로토콜 추가 시 튜플에만 추가하면 됨
- test_wiz550_gui.py 파일 미존재 확인 (계획서에 언급됐으나 미생성) → 전체 테스트(27개) PASSED로 대체 검증

## Deviations from Plan

**1. [Rule 1 - Bug] test_wiz550_gui.py 파일 미존재**
- **Found during:** Task 2 검증
- **Issue:** 계획서 verification에 `uv run pytest tests/test_wiz550_gui.py -x` 명시됐으나 파일이 존재하지 않음
- **Fix:** 전체 테스트 `uv run pytest tests/ -x` 실행으로 대체 검증 (27개 PASSED)
- **Files modified:** 없음
- **Verification:** 27 passed in 4.01s

---

**Total deviations:** 1 (테스트 파일 미존재 — 전체 테스트로 대체 검증)
**Impact on plan:** 기능 구현에 영향 없음. 회귀 확인 완료.

## Issues Encountered

- test_wiz550_gui.py 파일이 Phase 4~5에서 생성되지 않음 — 전체 tests/ 디렉토리 실행으로 대체

## Threat Flags

없음 — 계획서 threat_model에 명시된 T-06-01-01/02/03 모두 구현에서 mitigate 완료:
- T-06-01-02: _binary_proto 튜플로 wiz1x0 + wiz550 명시적 제외
- T-06-01-03: isRunning() 체크로 중복 bind(6550) 방지

## Next Phase Readiness

- 06-02 (WIZ550 Getter 통합)를 위한 기반 준비 완료
- dev_profile[mac_str]에 _proto='wiz550' dict가 저장되므로 Getter 라우팅 가능
- 06-03 (설정 패널 동적 생성)을 위한 검색 흐름 완성

---
*Phase: 06-gui-integration*
*Completed: 2026-05-18*
