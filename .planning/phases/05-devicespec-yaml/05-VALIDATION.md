---
phase: 5
slug: devicespec-yaml
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + validate_schemas.py |
| **Config file** | pytest.ini (기존 Phase 4에서 생성됨) |
| **Quick run command** | `uv run python validate_schemas.py` |
| **Full suite command** | `uv run pytest tests/test_wiz550_spec.py -v` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python validate_schemas.py`
- **After every plan wave:** Run `uv run pytest tests/test_wiz550_spec.py -v`
- **Before `/gsd-verify-work`:** Full suite must be green + validate_schemas.py 종료 코드 0
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-00-01 | 00 | 0 | SPEC-04 | — | N/A | setup | `uv run python validate_schemas.py` | ❌ W0 | ⬜ pending |
| 5-01-01 | 01 | 1 | SPEC-01 | — | N/A | schema | `uv run python validate_schemas.py` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 1 | SPEC-02 | — | N/A | schema | `uv run python validate_schemas.py` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | 1 | SPEC-03 | — | N/A | unit | `uv run pytest tests/test_wiz550_spec.py::test_web_disabled_fields -v` | ❌ W0 | ⬜ pending |
| 5-01-04 | 01 | 1 | SPEC-04 | — | N/A | integration | `uv run python validate_schemas.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `specs/schema/device.wiz550.schema.json` — WIZ550 전용 JSON 스키마 파일
- [ ] `tests/test_wiz550_spec.py` — SPEC-03 (WEB disabled 필드 존재), SPEC-01~04 (YAML 필드명-프로파일 1:1 매핑) 검증 stub
- [ ] `validate_schemas.py` — `family == "wiz550"` 라우팅 분기 추가

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
