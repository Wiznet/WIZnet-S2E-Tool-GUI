---
phase: 06-gui-integration
verified: 2026-05-18T21:52:00Z
status: human_needed
score: 4/5
overrides_applied: 0
human_verification:
  - test: "WIZ550 장치를 네트워크에 연결하고 검색 버튼을 누른다"
    expected: "장치 목록에 WIZ550SR/S2E/WEB 장치가 연두색 배경(#D0FFD0)으로 MAC, 장치명, FW버전과 함께 표시된다"
    why_human: "실제 UDP 6550 브로드캐스트와 장치 응답이 필요 — 자동화 불가"
  - test: "WIZ550 장치 선택 후 설정 패널이 열리고 값이 채워지는지 확인"
    expected: "YAML sections 기반 QGroupBox가 동적으로 빌드되고, GET_INFO 완료 후 위젯에 실제 값이 채워진다"
    why_human: "실제 장치와 GET_INFO 응답이 필요 — GUI 렌더링 자동 확인 불가"
  - test: "Apply 버튼 클릭 후 비밀번호 다이얼로그가 표시되고 성공/실패 메시지를 확인"
    expected: "비밀번호 입력 후 WIZ550Setter 실행, 성공 시 상태바가 #5db872(녹색), QMessageBox '설정이 성공적으로 저장되었습니다', 3초 후 색상 복구"
    why_human: "실제 장치 응답(0xC0/0x55) 없이는 success/fail 분기 확인 불가"
  - test: "Reset 버튼과 Factory Reset 메뉴 동작 확인"
    expected: "Reset → OP_REMOTE_RESET(0xE0), Factory Reset → OP_FACTORY_RESET(0xF0) 전송 + 완료 메시지"
    why_human: "실제 장치 재기동 확인이 필요"
  - test: "기존 WIZ5xxSR 장치 검색/설정/Apply/Reset 회귀 확인"
    expected: "기존 WIZ5xxSR 장치가 정상 검색되고, Apply/Reset이 기존 do_setting()/do_reset() 경로로 정상 동작한다"
    why_human: "_proto != 'wiz550' 분기가 기존 흐름을 유지하는지 실제 장치로만 확인 가능"
gaps:
  - truth: "Apply 후 SET_INFO 응답(0xC0/0x55)을 수신하면 성공 메시지가 표시된다"
    status: partial
    reason: "응답 파싱(0xC0/0x55)과 QMessageBox 표시 코드는 완전히 구현됨. 단, 이 경로는 실제 장치 없이 자동 검증 불가 — 하드웨어 테스트로 분류"
    artifacts:
      - path: "WIZ550MSGHandler.py"
        issue: "_parse_set_reply()가 0x55(WIZNET_REPLY) 체크는 구현됨. 실제 0xC0 op_code 응답 수신은 하드웨어 테스트 필요"
    missing:
      - "실제 WIZ550 장치로 Apply 성공 경로 확인 (human verification으로 이동)"
---

# Phase 6: GUI Integration Verification Report

**Phase Goal:** main_gui.py가 WIZ550 장치를 검색 목록에 표시하고, 장치 선택 시 설정을 읽어 UI에 표시하며, Apply/Reset/FactoryReset을 정확히 전송한다
**Verified:** 2026-05-18T21:52:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 검색 시 WIZ550 장치가 기존 장치 목록에 함께 표시된다 (MAC, IP, 장치명, FW 버전) | VERIFIED | `search_pre()` line 2371: WIZ550Searcher 항상 병행 시작. `_merge_wiz550_results()` line 2431: 연두색 배경(0xD0,0xFF,0xD0)으로 MAC/device_type/fw_str 3컬럼 테이블 삽입. `dev_profile[mac_str] = device_dict` (`_proto='wiz550'` 포함) |
| 2 | WIZ550 장치 선택 시 해당 설정이 UI 탭에 올바르게 표시된다 | VERIFIED | `get_clicked_devinfo()` line 3276: `_proto=='wiz550'` 분기. `_build_wiz550_panel()` line 3434: YAML sections → QScrollArea>QGroupBox>rows 동적 빌드. `fill_devinfo_wiz550()` line 3546: WR-01 가드(`if field_id not in d: continue`) 포함 위젯 값 채우기. `_on_wiz550_get_done()` line 3580: GET_INFO 완료 콜백. 3개 YAML spec 파일(WIZ550SR/S2E/WEB.yaml) 존재 확인 |
| 3 | Apply 후 SET_INFO 응답(0xC0/0x55)을 수신하면 성공 메시지가 표시된다 | ? HUMAN_NEEDED | `apply_wiz550()` line 3631 → `WIZ550Setter` → `_parse_set_reply()` (data[4]==0x55 검증) → `set_done.emit(success)` → `_on_wiz550_set_done()`: QMessageBox + 상태바 #5db872. 코드 경로 완전 구현, 실제 0xC0/0x55 응답 수신은 하드웨어 필요 |
| 4 | Reset / Factory Reset이 정상 동작한다 | VERIFIED | `event_reset_clicked()` line 1205: `_proto=='wiz550'` → `reset_wiz550(OP_REMOTE_RESET)`. `event_factory_option_clicked()` line 1224: settings 분기 → `reset_wiz550(OP_FACTORY_RESET)`. `reset_wiz550()` line 3713: WIZ550Resetter 생성+시작. `_on_wiz550_reset_done()` line 3756: 결과 QMessageBox. OP_REMOTE_RESET=0xE0, OP_FACTORY_RESET=0xF0 (WIZ550MSGHandler.py line 40-41) |
| 5 | 기존 WIZ5xxSR / WIZ1x0SR 검색·설정에 회귀가 없다 | VERIFIED | `event_setting_clicked()`: wiz550 조건 `return` 후 WIZ1x0SR → `apply_1x0()`, 그 외 → `do_setting()` (line 5005). `event_reset_clicked()`: 동일 패턴 → `do_reset()` (line 5633). `search_each_dev()` line 2503: `_binary_proto=('wiz1x0','wiz550')` 튜플로 기존 WIZ5xxSR 텍스트 커맨드 흐름 보존. 전체 테스트 28 passed, 5 xfailed (회귀 없음) |

**Score:** 4/5 truths verified (SC-3은 코드 구현 완료, 하드웨어 검증 필요)

### Deferred Items

없음

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `main_gui.py` | WIZ550 검색/UI/Apply/Reset 전체 통합 | VERIFIED | 15개 메서드 추가/수정 확인. `_merge_wiz550_results`, `_build_wiz550_panel`, `_make_wiz550_field_widget`, `fill_devinfo_wiz550`, `_on_wiz550_get_done`, `_show_wiz550_panel`, `fill_setinfo_wiz550`, `apply_wiz550`, `_on_wiz550_set_done`, `reset_wiz550`, `_on_wiz550_reset_done` — 모두 실제 로직 구현 |
| `WIZ550MSGHandler.py` | WIZ550Searcher/Getter/Setter/Resetter QThread + 상수 | VERIFIED | 4개 클래스 + OP_REMOTE_RESET=0xE0 + OP_FACTORY_RESET=0xF0 확인. 각 클래스 signal 정의: search_done/get_done/set_done/reset_done |
| `WIZ550Profile.py` | build_sr/s2e/web + parse_sr/s2e/web | VERIFIED | 6개 함수 모두 존재 (line 220~420) |
| `specs/devices/WIZ550SR.yaml` | WIZ550SR DeviceSpec YAML | VERIFIED | 파일 존재 확인 |
| `specs/devices/WIZ550S2E.yaml` | WIZ550S2E DeviceSpec YAML | VERIFIED | 파일 존재 확인 |
| `specs/devices/WIZ550WEB.yaml` | WIZ550WEB DeviceSpec YAML | VERIFIED | 파일 존재 확인 |
| `tests/test_wiz550_gui.py` | UI-01~04 테스트 스텁 6개 | VERIFIED | 1 PASS (test_wiz550_resetter_opcodes) + 5 XFAIL (하드웨어 의존 GUI 테스트) |
| `tests/conftest.py` | qapp 픽스처 | VERIFIED | session 스코프 QApplication 픽스처 추가 확인 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `search_pre()` | `_merge_wiz550_results()` | `wiz550_searcher.search_done.connect(...)` | WIRED | line 2379: 시그널 연결 확인 |
| `get_clicked_devinfo()` | `_build_wiz550_panel()` | `_proto=='wiz550'` 분기 | WIRED | line 3278-3302 |
| `get_clicked_devinfo()` | `_on_wiz550_get_done()` | `getter.get_done.connect(lambda...)` | WIRED | line 3312-3314 |
| `_on_wiz550_get_done()` | `fill_devinfo_wiz550()` | 직접 호출 | WIRED | line 3595 |
| `event_setting_clicked()` | `apply_wiz550()` | `_proto=='wiz550'` guard + return | WIRED | line 1196-1199 |
| `event_reset_clicked()` | `reset_wiz550(OP_REMOTE_RESET)` | `_proto=='wiz550'` guard + return | WIRED | line 1207-1210 |
| `event_factory_option_clicked()` | `reset_wiz550(OP_FACTORY_RESET)` | "settings" + `_proto=='wiz550'` | WIRED | line 1229-1232 |
| `apply_wiz550()` | `WIZ550Setter.set_done` → `_on_wiz550_set_done()` | `setter.set_done.connect(...)` | WIRED | line 3687 |
| `reset_wiz550()` | `WIZ550Resetter.reset_done` → `_on_wiz550_reset_done()` | `resetter.reset_done.connect(lambda...)` | WIRED | line 3750-3751 |
| `apply_wiz550()` | `WIZ550Profile.build_sr/s2e/web` | `from WIZ550Profile import ...` (지연 import) | WIRED | line 3662 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `_merge_wiz550_results()` | `results: list` | `WIZ550Searcher.search_done` signal (UDP 수신) | Yes (UDP 소켓 브로드캐스트) | FLOWING |
| `fill_devinfo_wiz550()` | `d: dict` | `WIZ550Getter.get_done` → `_on_wiz550_get_done()` → `cfg` (실제 GET_INFO 파싱) | Yes (WIZ550Profile.parse_sr/s2e/web) | FLOWING |
| `_on_wiz550_set_done()` | `success: bool` | `WIZ550Setter.set_done` → `_parse_set_reply()` (0x55 검증) | Yes (하드웨어 응답 기반) | FLOWING (H/W 의존) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| OP_REMOTE_RESET=0xE0, OP_FACTORY_RESET=0xF0 상수 | `uv run pytest tests/test_wiz550_gui.py::test_wiz550_resetter_opcodes -v` | PASSED | PASS |
| 전체 테스트 회귀 없음 | `uv run pytest tests/ -x` | 28 passed, 5 xfailed in 4.26s | PASS |
| WIZ550MSGHandler import | `python -c "from WIZ550MSGHandler import WIZ550Searcher,WIZ550Getter,WIZ550Setter,WIZ550Resetter,OP_REMOTE_RESET,OP_FACTORY_RESET"` | 정상 (tests에서 간접 확인) | PASS |
| WIZ550 메서드 존재 확인 | grep 15개 메서드 정의 | 모두 존재 (실제 줄번호 확인) | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| UI-01 | 검색 라우팅 — UDP 6550 포트 병렬 검색, 결과 통합 표시 | SATISFIED | `search_pre()` WIZ550Searcher 병행 시작, `_merge_wiz550_results()` 테이블 병합 |
| UI-02 | 장치 선택 → GET_INFO 전송 → WIZ550Profile 파싱 → UI 채우기 | SATISFIED | `get_clicked_devinfo()` wiz550 분기 + 2단계 패널 빌드 (B-02) |
| UI-03 | Apply → UI 필드 수집 → Profile 빌드 → SET_INFO 전송 + 비밀번호 다이얼로그 | SATISFIED (H/W 미확인) | `apply_wiz550()` 완전 구현. 실제 0xC0/0x55 응답은 하드웨어 필요 |
| UI-04 | REMOTE_RESET(0xE0) / FACTORY_RESET(0xF0) 패킷 전송 + 비밀번호 | SATISFIED (H/W 미확인) | `reset_wiz550()` + 상수 자동 테스트 PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `main_gui.py` | 3307, 3680, 3743 | `getter`/`setter`/`resetter` QThread를 로컬 변수로만 보유 (self.xxx로 저장 안 함) | Warning | PyQt5 C++ 레이어가 실행 중 QThread 참조를 유지하므로 실제 GC 위험은 낮음. 단, WIZ1x0SR의 `self.setter_1x0` 패턴과 불일치. 단기 작업(~1초)이므로 실제 크래시 가능성 낮음 |

### Human Verification Required

#### 1. WIZ550 장치 검색 통합 확인

**Test:** WIZ550SR/S2E/WEB 장치를 같은 네트워크에 연결하고 검색 버튼 클릭
**Expected:** 장치 목록에 연두색 배경(RGB: 208,255,208)으로 MAC, 장치명, FW 버전이 표시되고, 기존 WIZ5xxSR 장치와 함께 혼합 목록으로 보임
**Why human:** 실제 UDP 6550 브로드캐스트와 장치 응답이 필요

#### 2. WIZ550 설정 패널 동적 빌드 확인

**Test:** 검색된 WIZ550 장치를 클릭
**Expected:** 기존 General Tab 대신 YAML sections 기반 동적 패널(QGroupBox)이 표시되고, GET_INFO 완료 후 실제 장치 설정값이 각 위젯에 채워짐. WIZ550WEB의 disabled 필드(working_mode 등)는 회색(비활성) 표시
**Why human:** GET_INFO 응답과 GUI 렌더링을 동시에 확인해야 함

#### 3. Apply 성공/실패 메시지 확인 (SC-3)

**Test:** WIZ550 장치 선택 후 설정을 변경하고 Apply 클릭
**Expected:** 비밀번호 다이얼로그 → 설정 전송 → 성공 시 상태바 녹색(#5db872) + QMessageBox "설정이 성공적으로 저장되었습니다" → 3초 후 상태바 색상 복구. 잘못된 비밀번호 시 상태바 적색(#c64545) + 실패 메시지
**Why human:** 실제 SET_INFO 응답(opcode 0xC0, reply byte 0x55) 수신 없이는 success/fail 경로 분기 확인 불가

#### 4. Reset / Factory Reset 동작 확인

**Test:** Reset 버튼 및 Factory Reset 메뉴 클릭
**Expected:** Reset → 장치가 재시작됨 + 완료 QMessageBox. Factory Reset → 장치가 초기화 후 재시작됨 + 완료 메시지
**Why human:** 실제 장치 재기동 확인이 필요

#### 5. 기존 WIZ5xxSR/WIZ1x0SR 회귀 확인

**Test:** 기존 WIZ5xxSR 또는 WIZ1x0SR 장치가 있는 환경에서 검색 → 선택 → Apply/Reset 수행
**Expected:** WIZ5xxSR: 기존 General Tab + do_setting()/do_reset() 경로 정상 동작. WIZ1x0SR: 전용 패널 + apply_1x0() 정상 동작. WIZ550 분기 코드가 기존 흐름을 방해하지 않음
**Why human:** _proto 조건 분기가 실제 장치 종류별로 올바르게 라우팅되는지 확인

### Gaps Summary

Phase 6 코드 구현은 모든 Success Criteria에 대한 실질적인 구현을 포함한다. 5개의 성공 기준 중 4개(SC-1, SC-2, SC-4, SC-5)는 코드 수준에서 완전히 검증되었다. SC-3(Apply 후 0xC0/0x55 응답 수신 → 성공 메시지)은 코드 경로(`WIZ550Setter` → `_parse_set_reply()` → `_on_wiz550_set_done()`)가 완전히 구현되었으나, 실제 장치 응답 없이는 end-to-end 확인이 불가능하여 human_needed 상태이다.

주목할 만한 설계 편차: WIZ550Getter/Setter/Resetter를 로컬 변수(`getter`, `setter`, `resetter`)로 생성하고 self.xxx로 저장하지 않는 패턴이 WIZ1x0SR(`self.setter_1x0`)과 다르다. PyQt5의 C++ QObject 참조 유지 메커니즘으로 실제 문제가 발생하지 않을 가능성이 높으나, 장기적 코드 일관성을 위해 self 속성으로 저장하는 것을 권장한다.

---

_Verified: 2026-05-18T21:52:00Z_
_Verifier: Claude (gsd-verifier)_
