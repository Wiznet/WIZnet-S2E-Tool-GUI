---
phase: 6
slug: gui-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (기존 tests/ 디렉토리) |
| **Config file** | pytest.ini |
| **Quick run command** | `uv run pytest tests/test_wiz550_gui.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_wiz550_gui.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-00-01 | 00 | 0 | UI-01~04 | — | N/A | setup | `uv run pytest tests/test_wiz550_gui.py -x` | ❌ W0 | ⬜ pending |
| 6-01-01 | 01 | 1 | UI-01 | — | N/A | unit | `uv run pytest tests/test_wiz550_gui.py::test_merge_wiz550_results -x` | ❌ W0 | ⬜ pending |
| 6-01-02 | 01 | 1 | UI-01 | — | N/A | unit | `uv run pytest tests/test_wiz550_gui.py::test_search_each_dev_filters_wiz550 -x` | ❌ W0 | ⬜ pending |
| 6-02-01 | 02 | 2 | UI-02 | — | N/A | unit | `uv run pytest tests/test_wiz550_gui.py::test_build_panel_sections -x` | ❌ W0 | ⬜ pending |
| 6-02-02 | 02 | 2 | UI-02 | — | N/A | unit | `uv run pytest tests/test_wiz550_gui.py::test_disabled_field_widget -x` | ❌ W0 | ⬜ pending |
| 6-03-01 | 03 | 3 | UI-03 | — | N/A | unit | `uv run pytest tests/test_wiz550_gui.py::test_setinfo_roundtrip -x` | ❌ W0 | ⬜ pending |
| 6-03-02 | 03 | 3 | UI-04 | — | N/A | unit | `uv run pytest tests/test_wiz550_handler.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_wiz550_gui.py` — UI-01~04 단위 테스트 스텁 (PyQt5 QApplication 픽스처 포함)
- [ ] `tests/conftest.py` 확장 — `qapp` 픽스처 추가 (pytest-qt 또는 수동 QApplication)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WIZ550 장치 실 검색 목록 표시 | UI-01 | 실물 장치 필요 | UAT-01 (TASKS.md) |
| 설정 읽기/쓰기 UI 왕복 | UI-02, UI-03 | 실물 장치 필요 | UAT-02, UAT-03 (TASKS.md) |
| FactoryReset 동작 | UI-04 | 실물 장치 필요 | UAT-01~03 완료 후 수행 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
