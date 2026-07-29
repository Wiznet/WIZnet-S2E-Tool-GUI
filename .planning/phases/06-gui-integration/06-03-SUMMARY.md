---
phase: 06-gui-integration
plan: "03"
subsystem: ui
tags: [pyqt5, wiz550, apply, reset, factory-reset, gui-routing]

# Dependency graph
requires:
  - phase: 06-02
    provides: "_on_wiz550_get_done / _wiz550_field_widgets / fill_devinfo_wiz550"
  - phase: 04-protocol-engine
    provides: "WIZ550Setter / WIZ550Resetter / OP_REMOTE_RESET / OP_FACTORY_RESET"
provides:
  - "fill_setinfo_wiz550(): _wiz550_field_widgets → dict (UI-03)"
  - "apply_wiz550(): 비밀번호 입력 → Profile 빌드 → WIZ550Setter 시작"
  - "_on_wiz550_set_done(): 성공 #5db872 / 오류 #c64545 표시 (D-05)"
  - "reset_wiz550(op_code): REMOTE_RESET / FACTORY_RESET 전송 (UI-04)"
  - "_on_wiz550_reset_done(): Reset 결과 표시"
  - "Apply/Reset/FactoryReset 버튼 → wiz550 전용 흐름 라우팅"
affects:
  - 06-04

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_proto == 'wiz550' 조건으로 버튼 라우팅 격리 (T-06-03-04)"
    - "WIZ550Profile.build_sr/s2e/web 빌더 dict dispatch"
    - "QTimer.singleShot(3000) statusbar 색상 자동 복구"
    - "lambda 클로저로 reset_done.connect에 op_name 전달"

key-files:
  created: []
  modified:
    - main_gui.py

key-decisions:
  - "_proto == 'wiz550' 조건 체크로 기존 WIZ5xxSR/WIZ1x0SR 흐름 완전 격리 (T-06-03-04)"
  - "WIZ550Setter/Resetter/OP_* 는 이미 최상위 import — 메서드 내 재import 불필요 (단 WIZ550Profile은 함수 내 import)"
  - "event_factory_option_clicked 수정 C는 return 없이 else 분기로 기존 코드 보존"

requirements-completed:
  - UI-03
  - UI-04

# Metrics
duration: 20min
completed: 2026-05-18
---

# Phase 06 Plan 03: WIZ550 Apply/Reset/FactoryReset 흐름 Summary

**비밀번호 다이얼로그 + WIZ550Profile 빌드 + WIZ550Setter/Resetter 연결로 UI-03/UI-04 요구사항 완료**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-18T13:45:00Z
- **Completed:** 2026-05-18T14:05:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

### Task 1: 5개 메서드 추가

| 메서드 | 라인 | 설명 |
|--------|------|------|
| `fill_setinfo_wiz550()` | 3602 | _wiz550_field_widgets → dict (QLabel 건너뜀, uint16 int 변환) |
| `apply_wiz550()` | 3631 | 비밀번호 입력 → Profile 빌드 → WIZ550Setter 시작 |
| `_on_wiz550_set_done(success)` | 3691 | 성공 #5db872 / 오류 #c64545, 3초 후 색상 복구 |
| `reset_wiz550(op_code)` | 3713 | REMOTE_RESET(0xE0)/FACTORY_RESET(0xF0) 전송 |
| `_on_wiz550_reset_done(success, op_name)` | 3756 | Reset 결과 메시지 표시 |

### Task 2: Apply/Reset/FactoryReset 버튼 라우팅

| 함수 | 라인 | 수정 내용 |
|------|------|-----------|
| `event_setting_clicked` | 1194 | `_proto == 'wiz550'` → `apply_wiz550()` + return (기존 WIZ1x0SR/WIZ5xx 앞에 삽입) |
| `event_reset_clicked` | 1205 | `_proto == 'wiz550'` → `reset_wiz550(OP_REMOTE_RESET)` + return |
| `event_factory_option_clicked` | 1224 | settings 분기 내 `_proto == 'wiz550'` → `reset_wiz550(OP_FACTORY_RESET)` else 기존 |

## 핵심 설계 구현 확인

### T-06-03-04: 기존 흐름 격리

```python
# event_setting_clicked 예시
if (hasattr(self, 'curr_mac') and self.curr_mac
        and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
    self.apply_wiz550()
    return
# 기존 WIZ1x0SR / WIZ5xxSR 코드 영향 없음
```

### D-05 색상 적용 (_on_wiz550_set_done)

```python
self.statusbar.setStyleSheet("QStatusBar { color: #5db872; }")  # 성공
self.statusbar.setStyleSheet("QStatusBar { color: #c64545; }")  # 오류
QTimer.singleShot(3000, lambda: self.statusbar.setStyleSheet(""))  # 3초 후 복구
```

### reset_wiz550 호출 3개 확인 (W-2)

- `def reset_wiz550(self, op_code: int = None):` — 정의 (line 3713)
- `self.reset_wiz550(op_code=OP_REMOTE_RESET)` — event_reset_clicked (line 1209)
- `self.reset_wiz550(op_code=OP_FACTORY_RESET)` — event_factory_option_clicked (line 1232)

## Task Commits

1. **Task 1+2: WIZ550 Apply/Reset/FactoryReset 흐름 구현** — `e4d8726` (feat)

## Files Created/Modified

- `main_gui.py` — 5개 메서드 추가 + 3개 버튼 함수 라우팅 수정 (189줄 순증가)

## Decisions Made

- `_proto == 'wiz550'` 조건으로 기존 WIZ5xxSR/WIZ1x0SR 흐름 완전 격리
- WIZ550Setter/Resetter/OP_* 는 파일 최상위 import 이미 존재 — 메서드 내 재import 없이 직접 사용
- WIZ550Profile(build_sr/s2e/web)은 함수 내 지연 import (선택적 의존성)
- event_factory_option_clicked는 return 없이 if/else 분기 — 기존 firmware 분기 보존

## Deviations from Plan

**1. [Rule 3 - Blocking] 워크트리 베이스 커밋 불일치 (재발)**

- **Found during:** 초기 브랜치 체크
- **Issue:** ACTUAL_BASE(78bd3f9)가 EXPECTED(0549a82)와 달라 `git reset --soft` 실행 후 파일 복구 필요
- **Fix:** `git checkout 0549a82 -- .`로 모든 파일 복구 후 정상 진행
- **Impact:** 기능에 영향 없음

## Known Stubs

없음 — 모든 메서드가 실제 로직으로 구현됨

## Threat Flags

없음 — 계획서 threat_model T-06-03-01~04 모두 처리:
- T-06-03-01: accept (로컬 네트워크 내부 UDP, WIZ550 원본 프로토콜 설계)
- T-06-03-02: mitigate — try/except로 build 오류 캐치, 전송 차단 구현
- T-06-03-03: mitigate — 비밀번호 다이얼로그, 취소 시 return 구현
- T-06-03-04: mitigate — `_proto == 'wiz550'` + `return` 격리 구현

## Self-Check: PASSED

- `fill_setinfo_wiz550` 존재: line 3602 FOUND
- `apply_wiz550` 존재: line 3631 FOUND
- `_on_wiz550_set_done` 존재: line 3691 FOUND
- `reset_wiz550` 존재: line 3713 FOUND
- `_on_wiz550_reset_done` 존재: line 3756 FOUND
- apply_wiz550 참조 2개 (정의+호출): FOUND
- reset_wiz550 참조 3개 (정의+Reset+Factory): FOUND
- #5db872 / #c64545: FOUND
- 커밋 e4d8726: FOUND
- pytest tests/ -x: 28 passed, 5 xfailed (PASSED)

---
*Phase: 06-gui-integration*
*Completed: 2026-05-18*
