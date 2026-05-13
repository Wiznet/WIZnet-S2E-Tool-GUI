---
phase: 1
slug: schema-definition
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | 별도 프레임워크 없음 — Python 스크립트 직접 실행 |
| **Config file** | 없음 |
| **Quick run command** | `python validate_schemas.py` |
| **Full suite command** | `python validate_schemas.py` (동일 — 모든 YAML 파일 검증) |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python validate_schemas.py`
- **After every plan wave:** Run `python validate_schemas.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | SCH-01-a | — | N/A | validation script | `python validate_schemas.py` | ❌ Wave 0 | ⬜ pending |
| 1-01-02 | 01 | 1 | SCH-01-b | — | N/A | validation script | `python validate_schemas.py` | ❌ Wave 0 | ⬜ pending |
| 1-01-03 | 01 | 1 | SCH-01-c | — | N/A | inline check | `python -c "import json; s=json.load(open('specs/schema/command-group.schema.json')); assert 'meta' in s['properties']"` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `specs/schema/` 디렉토리 생성
- [ ] `specs/schema/device.schema.json` 생성
- [ ] `specs/schema/command-group.schema.json` 생성
- [ ] `validate_schemas.py` 생성 (프로젝트 루트)
- [ ] `pip install jsonschema==4.26.0` 실행 (로컬 환경)

---

## Manual-Only Verifications

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
