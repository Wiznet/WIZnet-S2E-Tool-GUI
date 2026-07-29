---
phase: 06-gui-integration
plan: "02"
subsystem: ui
tags: [pyqt5, wiz550, dynamic-panel, yaml, gui-integration]

# Dependency graph
requires:
  - phase: 06-01
    provides: "search_pre() WIZ550Searcher + _merge_wiz550_results + _binary_proto 필터"
  - phase: 04-protocol-engine
    provides: WIZ550Getter QThread + get_done 시그널
  - phase: 05-devicespec-yaml
    provides: WIZ550SR/S2E/WEB YAML specs (ui.sections)
provides:
  - "_show_wiz550_panel(): generalTab ↔ WIZ550 동적 패널 전환"
  - "_build_wiz550_panel(device_type): YAML sections → QGroupBox → rows 동적 빌드"
  - "_make_wiz550_field_widget(field): 타입별 위젯 생성"
  - "fill_devinfo_wiz550(d): GET_INFO dict → 위젯 값 채우기 (WR-01 가드)"
  - "_on_wiz550_get_done(): GET_INFO 완료 콜백 (B-02 Stage 2)"
  - "get_clicked_devinfo() wiz550 분기: B-02 Stage 1 패널 빌드 + Getter 시작"
affects:
  - 06-03

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "yaml.safe_load(Path(...).read_text()) 직접 사용 — device_spec_loader 우회 (W-3)"
    - "2단계 패널 빌드 분리 (B-02): Stage 1=구조 빌드, Stage 2=GET_INFO 완료 후 값 채우기"
    - "_wiz550_last_type 캐시로 동일 타입 재선택 시 재빌드 스킵 (T-06-02-03)"
    - "setParent(None)으로 이전 패널 QWidget 해제 (메모리 누수 방지)"

key-files:
  created: []
  modified:
    - main_gui.py

key-decisions:
  - "B-02: 패널 빌드(Stage 1)와 값 채우기(Stage 2) 2단계 분리 — GET_INFO 완료 전 패널 구조 선점"
  - "B-03: generalTab.parentWidget() + layout() None 체크 + logger.error fallback으로 AttributeError 예방"
  - "W-1: fw_version 키 통일 (fw_ver 아님) — Discovery dict 키와 일치"
  - "W-3: yaml.safe_load() 직접 사용 — device_spec_loader.load() pseudo-code 불사용"
  - "WR-01: if field_id not in d: continue 가드 — disabled 필드 KeyError 방지"
  - "_on_wiz550_get_done()을 fill_devinfo_wiz550() 바로 위 메서드 블록에 통합 배치"

requirements-completed:
  - UI-02

# Metrics
duration: 30min
completed: 2026-05-18
---

# Phase 06 Plan 02: WIZ550 설정 패널 동적 빌드 Summary

**YAML sections 기반 QGroupBox 동적 빌드 + WIZ550Getter 2단계 연결로 WIZ550SR/S2E/WEB 설정 패널 UI-02 요구사항 완료**

## Performance

- **Duration:** 30 min
- **Started:** 2026-05-18T20:53:00Z
- **Completed:** 2026-05-18T21:23:58Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

### Task 1: 4개 메서드 추가 (line 3407~3583)

| 메서드 | 라인 | 설명 |
|--------|------|------|
| `_show_wiz550_panel(show)` | 3407 | generalTab/channel_tab ↔ WIZ550 패널 전환 (D-01, D-07) |
| `_build_wiz550_panel(device_type)` | 3419 | YAML → QScrollArea > QGroupBox > rows 동적 빌드 (D-06, W-3) |
| `_make_wiz550_field_widget(field)` | 3493 | 타입별(readonly/checkbox/dropdown/ip/uint16) 위젯 생성 |
| `fill_devinfo_wiz550(d)` | 3531 | dict → 위젯 값 채우기, WR-01 가드 포함 |
| `_on_wiz550_get_done(cfg, mac, dtype)` | 3565 | GET_INFO 완료 콜백 (B-02 Stage 2) |

### Task 2: get_clicked_devinfo() 확장 + __init__ 초기화

| 항목 | 라인 | 설명 |
|------|------|------|
| `__init__` 초기화 | 892~893 | `_wiz550_container = None`, `_wiz550_field_widgets = {}` |
| wiz550 분기 | 3263~3304 | `_proto == 'wiz550'` → Stage 1 패널 빌드 + WIZ550Getter 시작 |

## 핵심 설계 구현 확인

### B-02: 2단계 패널 빌드 분리

- **Stage 1** (`get_clicked_devinfo`): `_build_wiz550_panel(device_type)` 호출 → QScrollArea 구조 생성 → 레이아웃에 삽입
- **Stage 2** (`_on_wiz550_get_done`): `fill_devinfo_wiz550(cfg)` 호출 → GET_INFO 완료 후 위젯에 값 채우기

### B-03: None 체크 구현

```python
parent_widget = self.generalTab.parentWidget()
if parent_widget is None or parent_widget.layout() is None:
    self.logger.error("[WIZ550] wiz550_container 삽입 실패: ...")
    return
```

### W-1: fw_version 키 통일

```python
fw_version = d.get('fw_version', b'\x00\x00\x00')  # fw_ver 아님
```

### WR-01: 가드 구현

```python
for field_id, widget in self._wiz550_field_widgets.items():
    if field_id not in d:
        continue  # disabled 필드 또는 WEB 미지원 필드
```

### condition 처리 (mqtt/modbus)

```python
if condition == 'mqtt'   and not has_mqtt:   continue
if condition == 'modbus' and not has_modbus: continue
```

### 컨테이너 캐싱 전략

```python
if (self._wiz550_container is None
        or getattr(self, '_wiz550_last_type', None) != device_type):
    # 재빌드 (타입 변경 or 최초)
```

## Task Commits

1. **Task 1+2: WIZ550 설정 패널 빌드 시스템 구현** - `5455ca8` (feat)

## Files Created/Modified

- `main_gui.py` — 5개 메서드 추가 + get_clicked_devinfo() wiz550 분기 + __init__ 초기화

## Decisions Made

- B-02 2단계 분리: Stage 1(구조 빌드) / Stage 2(GET_INFO 완료 후 fill) — Pitfall 5 방지
- B-03 None 체크: 런타임 AttributeError 예방
- _on_wiz550_get_done()을 fill_devinfo_wiz550() 바로 다음에 배치 — 코드 응집도 향상
- TASKS.md / TCPMulticastScanner.py는 reset --soft 복구 과정에서 staged된 이전 변경사항 — 커밋에 함께 포함됨

## Deviations from Plan

**1. [Rule 3 - Blocking] 워크트리 베이스 커밋 불일치**

- **Found during:** 초기 브랜치 체크
- **Issue:** ACTUAL_BASE(78bd3f9)가 EXPECTED(8c26f2f)와 달라 `git reset --soft` 실행 → staged 파일 발생
- **Fix:** `git checkout 8c26f2fbe101d1b6f764329bf8a3ff0ccfad89df -- .`로 YAML/tests/planning 파일 복구 후 정상 진행
- **Impact:** TASKS.md + TCPMulticastScanner.py가 커밋에 함께 포함됨 (기능에 영향 없음)

## Known Stubs

없음 — 모든 메서드가 실제 로직으로 구현됨 (스텁/placeholder 없음)

## Threat Flags

없음 — 계획서 threat_model T-06-02-01~04 모두 mitigate 완료:
- T-06-02-03: `_wiz550_last_type` 캐시 + `setParent(None)` 구현
- T-06-02-04: B-03 None 체크 + `logger.error` + `return` 구현
- T-06-02-01/02: accept 처리 (네트워크 내부 도구, safe_load 사용)

## Self-Check: PASSED

- `_show_wiz550_panel` 존재: line 3407 FOUND
- `_build_wiz550_panel` 존재: line 3419 FOUND
- `_make_wiz550_field_widget` 존재: line 3493 FOUND
- `fill_devinfo_wiz550` 존재: line 3531 FOUND
- `_on_wiz550_get_done` 존재: line 3565 FOUND
- `_wiz550_container = None` (__init__): line 892 FOUND
- wiz550 분기 (get_clicked_devinfo): line 3263 FOUND
- 커밋 5455ca8: FOUND
- pytest tests/test_wiz550_gui.py: 1 passed, 5 xfailed
- pytest tests/ -x: 28 passed, 5 xfailed

---
*Phase: 06-gui-integration*
*Completed: 2026-05-18*
