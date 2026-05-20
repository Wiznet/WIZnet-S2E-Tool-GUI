---
phase: 7
slug: tftp-fw-upload
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-19
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | 없음 — Wave 0에서 tests/test_wiz550_fw.py 생성 |
| **Quick run command** | `uv run pytest tests/test_wiz550_fw.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_wiz550_fw.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | FW-01 | — | N/A | unit | `uv run pytest tests/test_wiz550_fw.py::test_tftp_server_tempdir -x` | ✅ | ✅ green |
| 7-01-02 | 01 | 0 | FW-02 | T-7-02 | server_port LE 검증 | unit | `uv run pytest tests/test_wiz550_fw.py::test_build_fw_upload_pkt -x` | ✅ | ✅ green |
| 7-01-03 | 01 | 0 | FW-03 | — | N/A | unit | `uv run pytest tests/test_wiz550_fw.py::test_parse_fw_done_reply -x` | ✅ | ✅ green |
| 7-01-04 | 01 | 0 | FW-04 | — | N/A | unit | `uv run pytest tests/test_wiz550_fw.py::test_dialog_tabs -x` | ✅ | ✅ green |
| 7-02-01 | 02 | 1 | FW-01 | T-7-01 | OSError 포트 69 → 사용자 안내 후 중단 | manual | — (실행 환경 의존) | ✅ | ✅ green |
| 7-02-02 | 00 | 0 | FW-02 | T-7-03 | BOOT 파일명 업로드 거부 | unit | `uv run pytest tests/test_wiz550_fw.py::test_boot_file_rejected -x` | ✅ | ✅ green |
| 7-03-01 | 03 | 2 | FW-03 | — | N/A | unit | `uv run pytest tests/test_wiz550_fw.py -x -q` | ✅ | ✅ green |
| 7-04-01 | 04 | 2 | FW-04 | — | N/A | unit | `uv run pytest tests/test_wiz550_fw.py -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Note (7-02-02 정정):** `test_boot_file_rejected`는 Plan 00(Wave 0)에서 스텁이 작성되고 Plan 02(Wave 2) 구현 완료 후 GREEN으로 전환된다. Plan 열은 스텁 작성 위치(00), Wave 열은 스텁이 속한 Wave(0)를 기준으로 한다.

---

## Wave 0 Requirements

- [x] `tests/test_wiz550_fw.py` — FW-01~04 커버 (stubs 포함)
  - `test_build_fw_upload_pkt` — 86바이트 레이아웃 + server_port LE(`struct.pack('<H', 69)`) 검증
  - `test_tftp_server_tempdir` — tempfile.mkdtemp() + TftpServer 초기화 성공 (실제 bind 없이)
  - `test_parse_fw_done_reply` — 0xD2 응답 헤더 파싱 (7B 헤더 체크: 0xA5, op_code[0]=0xD2, op_code[1]=0x55)
  - `test_dialog_tabs` — WIZ550FWDialog QTabWidget 탭 2개 확인 (qapp fixture 필요)
  - `test_boot_file_rejected` — 파일명에 'BOOT' 포함 시 업로드 거부 로직 (스텁은 Wave 0에서 작성, GREEN은 Wave 2 wiz550_fw_dialog.py 구현 후)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 포트 69 권한 오류 메시지 표시 | FW-01 (D-02) | 실행 환경(관리자/비관리자)에 따라 결과 다름 | 비관리자 환경에서 자동 탭 클릭 → "Port 69 requires Administrator privileges" 메시지 확인 |
| 비관리자 환경 OSError → D-02 error signal 전달 | FW-01 (D-02) | OSError는 tftpy listen() 내부에서 발생하며 is_running.wait() False + listen_thread.is_alive() False 조합으로 감지됨 | 비관리자 환경에서 자동 탭 Upload → WIZ550FWUploadThread.error 시그널이 "Port 69 requires Administrator privileges..." 메시지를 emit하고 lbl_status에 표시되는지 확인. is_running.wait(3.0) 타임아웃 경로가 올바르게 동작함을 확인. |
| 실장치 TFTP 업로드 완료 | FW-01, FW-02, FW-03 | WIZ550 실장치 필요 | WIZ550 연결 후 자동 탭에서 FW 파일 선택 → Upload → 진행 표시 → 완료 메시지 확인 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved — 2026-05-20
