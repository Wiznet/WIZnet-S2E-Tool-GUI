---
phase: 7
reviewers: [gemini, codex]
reviewed_at: 2026-05-20T09:10:00+09:00
plans_reviewed:
  - 07-00-PLAN.md
  - 07-01-PLAN.md
  - 07-02-PLAN.md
  - 07-03-PLAN.md
---

# Cross-AI Plan Review — Phase 7: TFTP FW Upload

> Reviewed by: Gemini CLI (0.1.9), Codex CLI (0.118.0 / gpt-5.4)
> Claude CLI skipped — same runtime as orchestrator (CLAUDE_CODE_ENTRYPOINT=claude-vscode)

---

## Gemini Review

### Plan 07-00 (Wave 0, TDD Stubs)

**Summary**
This plan establishes a solid foundation by following TDD. It defines the expected outcomes and public APIs before implementation code is written. This "red-state" plan correctly sets the stage for subsequent development waves.

**Strengths**
- TDD approach: defining tests first clarifies requirements and provides clear "done" criteria
- Good coverage: stubs cover packet construction, server setup, response parsing, and UI logic
- Edge case considered: `test_boot_file_rejected` shows foresight into potential user errors
- Environment sanity check: `test_tftp_server_tempdir` verifies the tftpy dependency

**Concerns**
- `MEDIUM` Incomplete failure path testing: no stubs for 30-second timeout or malformed 0xD2 response
- `LOW` Missing manual mode test: no test stub for the manual upload path

**Suggestions**
- Add `test_wait_for_d2_response_timeout` to simulate and verify timeout logic
- Add `test_parse_invalid_d2_reply` to ensure the parser handles incorrect data
- Consider `test_manual_upload_path_sends_correct_packet` to cover second tab logic

**Risk Assessment**: **LOW** — Primary risk is incomplete coverage for un-tested scenarios like timeouts.

---

### Plan 07-01 (Wave 1, Backend Core)

**Summary**
This plan details the core backend logic in a QThread. It correctly identifies key technical details like endianness and graceful thread termination. However, it contains significant risks related to race conditions and incorrect network assumptions.

**Strengths**
- Clear separation of concerns: packet creation in WIZ550MSGHandler, orchestration in WIZ550FWUploadThread
- Correct PyQt threading model: QThread with signals is idiomatic
- Explicit error handling: OSError for port 69 caught with user-friendly message
- Critical detail awareness: `struct.pack('<H', ...)` for little-endian is correctly identified

**Concerns**
- `HIGH` Race condition in server startup: `is_running.wait(3.0)` is not robust — if the TFTP server fails to bind within 3 seconds for any reason, the main logic proceeds to send 0xD1, leading to immediate failure
- `HIGH` Incorrect socket binding logic: The fallback to `('', 0)` is a critical logic flaw — WIZnet devices send 0xD2 to UDP port 6550. If binding to 6550 fails, the upload cannot succeed. The fallback is useless because the device won't know the ephemeral port
- `MEDIUM` PyInstaller compatibility: adding tftpy to requirements.txt doesn't confirm it bundles correctly; some libraries require hidden import hooks
- `LOW` Insecure temporary directory: potential for serving files outside intended directory if TFTP root isn't isolated

**Suggestions**
- Use `threading.Event()` set after server successfully binds; main thread should wait on this event
- Remove the `('', 0)` fallback; if port 6550 binding fails, emit error and terminate immediately
- Use `tempfile.TemporaryDirectory()` context manager with explicit tftproot setting
- Add a sub-task to verify pyinstaller bundles tftpy correctly

**Risk Assessment**: **HIGH** — Race condition and flawed socket binding logic are fundamental defects preventing reliable operation.

---

### Plan 07-02 (Wave 2, UI Dialog)

**Summary**
This plan outlines a well-thought-out UI dialog addressing both automatic and manual modes. Good state management, input validation, and graceful cleanup. Primary concerns are multi-homed network interfaces and robust thread management on exit.

**Strengths**
- Good UX design: two-tab structure caters to both novice and advanced users
- State management: `_set_uploading_state` provides centralized UI mode management
- Input validation: proactively validates IP addresses and filenames
- Graceful cleanup: `closeEvent` stops background thread

**Concerns**
- `MEDIUM` Ambiguous IP address selection: on hosts with multiple interfaces (Ethernet, Wi-Fi, VPN), `localip_addr` might not be on the same network as the WIZnet device
- `MEDIUM` Unreliable thread shutdown: `wait(3000)` fixed timeout may not be sufficient if thread is stuck on a network socket
- `LOW` Naive filename check: `'BOOT' in filename.upper()` is too broad — `my_reboot_fw.bin` would be false-positively rejected

**Suggestions**
- Use `QComboBox` to list all available non-loopback IPv4 addresses, auto-selecting the one on the same subnet as target device
- Use `QThread.wait()` (blocks until run() fully exits) instead of fixed-timeout wait for robust cleanup
- Make boot file check more specific: `filename.upper().startswith('BOOT')` or use regex

**Risk Assessment**: **MEDIUM** — IP selection and thread cleanup issues directly impact user experience and application stability.

---

### Plan 07-03 (Wave 3, Integration + Checkpoint)

**Summary**
This final plan covers integration into the main application with a formal verification checkpoint. The approach is logical and ensures the feature is correctly wired into the existing UI flow with regression testing.

**Strengths**
- Targeted integration: correctly identifies `event_upload_clicked` as entry point with `_proto=='wiz550'` isolation
- Verification-oriented: formal checkpoint with test execution, visual verification, and regression checks
- Process adherence: VALIDATION.md update demonstrates good project discipline

**Concerns**
- `MEDIUM` Ambiguous pre-condition check: `upload_wiz550()` "checks dev_profile" but doesn't specify what specifically
- `LOW` Vague regression plan: "regression check for WIZ5xxSR/WIZ1x0SR upload paths" lacks concrete checklist

**Suggestions**
- Specify the exact check: e.g., verify `dev_profile['fw_ver']` is not a bootloader-only version
- Add a concrete regression checklist: select WIZ107SR → click Upload → verify old dialog; select WIZ550SR → click Upload → verify new dialog

**Risk Assessment**: **LOW** — Concerns are primarily about adding clarity; the fundamental approach is sound.

---

## Codex Review

> Codex explored the actual codebase (main_gui.py, WIZ550MSGHandler.py, FWUploadThread.py, conftest.py) before reviewing.

### Plan 07-00

**Summary**
Wave 0 방향은 맞지만, 현재 저장소의 테스트 관례와 조금 어긋납니다. 이 repo는 이미 `xfail` 기반 GUI 스텁 패턴과 `qapp` fixture를 갖고 있어서, `ImportError` 기반 RED보다는 수집 가능한 스텁 테스트로 가는 편이 안정적입니다.

**Strengths**
- 테스트를 먼저 깔아 Phase 경계를 분명히 하려는 점은 좋습니다
- 패킷 빌드, TFTP 서버, 완료 응답, 다이얼로그 구조, boot 파일 차단까지 핵심 요구사항을 넓게 커버합니다
- GUI 테스트는 현재 `tests/conftest.py:289`의 `qapp` fixture를 재사용할 수 있어 기반은 이미 있습니다

**Concerns**
- `MEDIUM` `ImportError`를 RED 상태의 수단으로 쓰면 테스트 수집 자체가 깨져 이후 Wave 진행 신호가 흐려집니다. 이 repo는 `tests/test_wiz550_gui.py`에서 `xfail` 스텁 패턴을 사용합니다
- `MEDIUM` `test_tftp_server_tempdir must PASS`는 `requirements.txt`에 아직 `tftpy`가 없어서 환경 의존적입니다
- `LOW` `test_dialog_tabs`는 단순 탭 개수만 보면 의미가 약합니다. 탭별 필수 위젯/기본값 검증이 빠질 수 있습니다
- `LOW` `test_boot_file_rejected`만으로는 자동/수동 탭 모두에서 동일하게 차단되는지 보장되지 않습니다

**Suggestions**
- Wave 0는 `xfail(strict=False)` 스텁으로 통일하고, import 실패를 의도하지 말고 "구현 전"을 명시하세요
- `tftpy` 의존 테스트는 Wave 1 이후 GREEN으로 전환하거나, `importorskip("tftpy")`를 써서 환경 노이즈를 줄이세요
- `test_dialog_tabs`는 탭 이름, 기본 포트 69, 서버 IP 자동채움까지 같이 보도록 올리세요

**Risk Assessment**: **MEDIUM** — 방향은 좋지만, 지금 형태 그대로면 테스트가 설계 문서 역할만 하고 실제 개발 신호로는 약할 가능성이 큽니다.

---

### Plan 07-01

**Summary**
핵심 기능 대부분이 이 Wave에 몰려 있어 실질적으로 Phase 성공을 좌우하는 계획입니다. `build_fw_upload_pkt()` 추가는 자연스럽고, 별도 `WIZ550FWUploadThread.py` 분리도 타당합니다. 다만 소켓 바인딩 전략, 스레드/서버 수명주기, PyQt signal 이름 충돌 가능성 같은 구현 리스크가 큽니다.

**Strengths**
- `WIZ550MSGHandler.py`에 이미 `OP_FW_UPLOAD = 0xD1`와 `_build_header_with_payload()`가 있어 패킷 빌더 추가 지점이 명확합니다
- 79B payload와 LE 포트 인코딩을 명시한 점은 좋습니다
- 자동/수동 경로를 스레드 내부에서 분리한 구조는 UI를 단순화합니다
- `stop()`과 서버 종료를 계획에 넣은 점은 리소스 누수 방지 측면에서 좋습니다

**Concerns**
- `HIGH` `finished(bool)` signal 이름은 `QThread.finished()`와 충돌 소지가 큽니다. 연결 코드에서 매우 혼란스럽고 버그를 만들기 쉽습니다
- `HIGH` `_wait_d2()`를 별도 소켓으로 `6550` 또는 `('',0)`에 bind하는 전략은 응답이 실제로 어느 소켓으로 돌아오는지 명확하지 않습니다. `D1`을 보낸 소켓과 다른 소켓에서 기다리면 `0xD2`를 놓칠 수 있습니다
- `HIGH` `bind 6550 실패 시 ephemeral port fallback`은 성공 가능성이 불명확합니다. 장치가 고정 포트나 송신 소스 포트 중 어디로 응답하는지 계획에 근거가 없습니다
- `MEDIUM` `Port 69 requires Administrator privileges...`는 Windows에서는 일반적으로 성립하지 않는 진단입니다. 실패 원인을 잘못 안내할 수 있습니다
- `MEDIUM` `tftpy==0.8.7` 추가만으로는 배포 경로가 닫히지 않습니다. PyInstaller 번들링 확인이 빠져 있습니다
- `MEDIUM` payload 빌더에 대한 backend validation이 없습니다. 파일명 50B 초과, 비ASCII, 잘못된 IP/port가 UI를 우회하면 조용히 잘릴 수 있습니다

**Suggestions**
- `finished(bool)`는 `upload_done(bool)` 또는 `result(bool, str)` 같은 별도 이름으로 바꾸세요
- `D1` 송신과 `D2` 대기는 같은 UDP socket lifecycle에서 처리하도록 명시하세요
- `6550 fallback to ephemeral`는 근거가 없으면 제거하고, 실제 프로토콜에 맞는 단일 수신 전략을 선택하세요
- 포트 69 오류 메시지는 "port bind failed" 수준으로 일반화하고 실제 `OSError` 내용을 포함하세요
- `build_fw_upload_pkt()`는 UI 검증과 별개로 MAC/IP/port/filename 길이를 자체 검증해 방어적으로 만드세요
- PyInstaller smoke check를 최소한 checkpoint 항목으로 넣으세요

**Risk Assessment**: **HIGH** — 패킷 포맷 자체는 단순하지만, 응답 수신 경로와 동시성 설계가 틀리면 기능이 "가끔 실패"하는 형태로 남을 위험이 큽니다.

---

### Plan 07-02

**Summary**
UI 범위는 적절하고 과도하지 않습니다. 자동/수동 2탭, 선택적 비밀번호, 상태 표시까지 목표와 잘 맞습니다. 다만 파일명/boot 파일 검증 규칙과 업로드 중 상태 전이 정의가 아직 느슨합니다.

**Strengths**
- 2탭 구조는 사용자 결정사항과 정확히 맞습니다
- `QProgressBar`를 indeterminate 후 완료 시 100%로 처리하는 방식은 구현 복잡도를 낮춥니다
- `closeEvent`에서 `stop()`과 `wait()`를 호출하는 계획은 안전합니다
- 수동 탭의 서버 IP 기본값과 포트 기본값이 명확합니다

**Concerns**
- `MEDIUM` `_is_boot_file(filename): 'BOOT' in filename.upper()`는 오탐이 큽니다. 예를 들어 `reboot_fix.bin` 같은 이름도 차단될 수 있습니다
- `MEDIUM` `socket.inet_aton()`은 검증이 다소 느슨합니다. 표현식에 따라 예상보다 관대한 입력을 통과시킬 수 있습니다
- `MEDIUM` 자동 탭의 파일 선택 시 실제 TFTP 서빙 basename과 표시 이름이 어떻게 연결되는지 계획에 없습니다. 장치가 요청할 파일명과 tempdir 내 파일명이 반드시 일치해야 합니다
- `LOW` 업로드 중 탭 전환/입력 수정 허용 여부가 명확하지 않습니다

**Suggestions**
- boot 파일 차단은 basename 기준의 더 엄격한 규칙으로 정의하세요
- IP 검증은 `ipaddress.ip_address()` 같은 stricter parser를 고려하세요
- 업로드 시작 시 두 탭의 입력 위젯을 잠그고, 완료/실패 시 해제하는 상태 규칙을 넣으세요
- 자동 탭은 선택 파일을 tempdir에 복사할 때 실제 서빙 파일명과 packet의 `file_name[50]` 값이 같다는 점을 명시하세요

**Risk Assessment**: **MEDIUM** — 기능 범위는 적절하지만, 입력 검증 규칙이 느슨하면 장치 측 실패를 사용자가 이해하기 어려운 형태로 맞을 수 있습니다.

---

### Plan 07-03

**Summary**
통합 방향은 현재 `main_gui.py`의 WIZ550 분기 패턴과 잘 맞습니다. 실제로 setting/reset은 이미 `_proto == 'wiz550'` 조건으로 분기하고 있어 upload도 같은 방식으로 붙이는 것이 자연스럽습니다. 다만 현재 `event_upload_clicked()`가 로컬 IP 존재 여부를 먼저 보는 구조라, WIZ550 경로에서 어떤 사전조건을 유지할지 더 명확해야 합니다.

**Strengths**
- `main_gui.py:1206-1244`의 기존 WIZ550 분기 패턴과 일관됩니다
- 별도 `upload_wiz550()` 진입점을 두는 것은 유지보수상 좋습니다
- 기존 WIZ5xx/WIZ1x0 업로드 경로 회귀 확인을 checkpoint에 넣은 점은 중요합니다

**Concerns**
- `MEDIUM` 현재 `event_upload_clicked()`는 `localip_addr` 없으면 바로 경고 후 종료합니다. WIZ550 수동 탭은 이 제약이 꼭 필요하지 않을 수 있는데, 계획상 정책이 모호합니다
- `MEDIUM` `curr_mac` 캐시만 믿고 다이얼로그를 열면 선택 상태와 내부 상태가 어긋난 경우 잘못된 장치에 붙을 수 있습니다
- `MEDIUM` 자동화 검증이 부족합니다. 라우팅이 바뀌는 핵심 UI 진입점인데 테스트는 backend/dialog 쪽에 치우쳐 있습니다

**Suggestions**
- WIZ550 경로에서 `localip_addr`가 필수인지 정책을 먼저 확정하세요. 자동 탭만 필수라면 다이얼로그 내부에서 검사하는 편이 더 자연스럽습니다
- `upload_wiz550()` 진입 직전에 현재 선택 장치를 재확인하거나 `selected_devinfo()`에 준하는 동기화를 하세요
- `event_upload_clicked()` 라우팅 테스트를 하나 추가하세요

**Risk Assessment**: **MEDIUM** — 구조적으로는 맞지만, 진입 조건과 상태 동기화가 불명확하면 통합 후 현장 버그가 생기기 쉽습니다.

---

## Consensus Summary

### Agreed Strengths (2개 AI 모두 동의)
- 2탭 구조(자동/수동)는 D-01 결정사항과 정확히 맞으며 사용자 시나리오를 잘 커버한다
- `WIZ550MSGHandler.py`의 기존 패킷 빌더 패턴 재사용은 자연스럽다
- QThread 시그널 기반 비동기 처리 구조는 PyQt5 이디엄을 준수한다
- closeEvent에서 스레드 정리 계획은 안전하다
- main_gui.py의 기존 `_proto == 'wiz550'` 분기 패턴과의 일관성이 좋다

### Agreed Concerns (2개 AI 모두 독립적으로 제기)

| 심각도 | 이슈 | Plans |
|--------|------|-------|
| **HIGH** | `_wait_d2()` 별도 소켓 바인딩 전략 — 0xD2 응답 유실 위험 (D1 송신 소켓과 D2 수신 소켓 분리) | 07-01 |
| **HIGH** | TFTP 서버 시작 race condition — `is_running.wait(3.0)` 불충분 | 07-01 |
| **MEDIUM** | `_is_boot_file()` 과도한 오탐 — `reboot_fix.bin` 등 정상 파일 차단 가능 | 07-02 |
| **MEDIUM** | tftpy PyInstaller 번들링 미검증 — 패키지 배포 실패 가능 | 07-01 |

### Divergent Views

| 이슈 | Gemini | Codex |
|------|--------|-------|
| Wave 0 TDD 전략 | ImportError RED는 괜찮음 (LOW risk) | xfail 스텁 패턴이 더 적합 (MEDIUM risk) — repo 관례와 불일치 |
| `finished` signal 이름 | 언급 없음 | **HIGH**: `QThread.finished()`와 이름 충돌 가능 |
| 다중 NIC 환경 | MEDIUM: localip_addr 선택 문제 | 언급 없음 |
| Port 69 오류 메시지 | 적절함 | MEDIUM: Windows에서 실제로 성립하지 않는 진단일 수 있음 |

### 우선 해결 권고 (실행 전)

**Codex가 발견한 추가 HIGH risk (Gemini 미발견):**
- `finished = pyqtSignal(bool)` 이름을 `upload_done` 또는 `upload_finished`로 변경 — `QThread.finished()` 내장 시그널과의 혼동 방지

**양쪽 모두 동의하는 핵심 수정 3가지:**
1. `_wait_d2()` 소켓 전략 — D1 송신 소켓과 동일 lifecycle에서 D2 대기, 또는 WIZ550 프로토콜 실장치 검증 후 포트 전략 확정
2. `('', 0)` fallback 제거 — 의미 없는 fallback 대신 명확한 실패 처리
3. `_is_boot_file()` 로직 강화 — basename 기반 더 엄격한 패턴 매칭

---

*Review generated: 2026-05-20*
*Reviewer count: 2 (gemini, codex)*
