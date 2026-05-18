---
phase: 4
slug: protocol-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini (Wave 0에서 생성) |
| **Quick run command** | `uv run pytest tests/test_wiz550_profile.py tests/test_wiz550_handler.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_wiz550_profile.py tests/test_wiz550_handler.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | PROTO-02 | — | N/A | unit | `uv run pytest tests/test_wiz550_handler.py::test_header_constants -x` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | PROTO-03 | T-XOR | 매 패킷 신규 키 생성 | unit | `uv run pytest tests/test_wiz550_handler.py::test_xor_roundtrip -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | PROTO-05 | — | N/A | unit | `uv run pytest tests/test_wiz550_handler.py::test_discovery_parse_sr -x` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 1 | PROTO-04 | — | N/A | unit | `uv run pytest tests/test_wiz550_handler.py::test_get_info_length_parse -x` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | PROF-01 | T-BUF | len 검증 후 파싱 | unit | `uv run pytest tests/test_wiz550_profile.py::test_sr_roundtrip -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | PROF-02 | T-BUF | len 검증 후 가변 분기 | unit | `uv run pytest tests/test_wiz550_profile.py::test_s2e_base_variant -x` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 2 | PROF-03 | T-BUF | len 검증 후 파싱 | unit | `uv run pytest tests/test_wiz550_profile.py::test_web_roundtrip -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/` 디렉토리 생성
- [ ] `tests/conftest.py` — 공통 픽스처 (더미 바이트 생성 헬퍼)
- [ ] `tests/test_wiz550_handler.py` — PROTO-02, 03, 05, D-08 커버 (stub 형태)
- [ ] `tests/test_wiz550_profile.py` — PROF-01~03 커버 (stub 형태)
- [ ] pytest 설치 확인: `uv add pytest --dev`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DISCOVERY_ALL 실 장치 응답 수신 | PROTO-01, PROTO-06 | 실 WIZ550 하드웨어 필요 | WIZ550SR 장치를 동일 LAN에 연결 후 WIZ550Searcher 실행, search_done 시그널 수신 확인 |
| SET_INFO 실 장치 설정 적용 | PROTO-04 | 실 장치 필요 | WIZ550Setter 실행 후 장치 설정 변경 확인 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
