---
phase: "04-protocol-engine"
plan: "01"
subsystem: "WIZ550 UDP 프로토콜 핸들러"
tags: [protocol, udp, qthread, xor, wiz550]
dependency_graph:
  requires:
    - "WIZ1x0MSGHandler.py 패턴 (기존)"
    - "utils.py logger"
  provides:
    - "WIZ550MSGHandler.py"
    - "tests/test_wiz550_handler.py"
    - "tests/conftest.py"
    - "pytest.ini"
  affects:
    - "Phase 6 (GUI 통합) — main_gui.py가 WIZ550Searcher/Getter/Setter/Resetter import"
    - "Phase 4 Plan 02 — WIZ550Profile.py가 _parse_get_info_reply에서 임포트됨"
tech_stack:
  added:
    - pytest 9.0.3 (dev)
  patterns:
    - QThread + pyqtSignal (WIZ1x0MSGHandler 패턴 이식)
    - socket + select.select 논블로킹 수신
    - try-finally 소켓 닫기
    - XOR 암호화: 매 패킷 신규 랜덤 키 (D-06)
    - struct 없이 bytearray 직접 조립 (헤더/패킷 빌더)
key_files:
  created:
    - WIZ550MSGHandler.py
    - tests/test_wiz550_handler.py
    - tests/conftest.py
    - pytest.ini
  modified: []
decisions:
  - "QThread 4개 클래스 통합 구현 (Task 1, 2 동시): 헬퍼 함수와 QThread를 단일 파일에서 관리"
  - "Searcher timeout=15.0s, Getter/Setter/Resetter timeout=5.0s (D-05 세부 분리)"
  - "_parse_get_info_reply: payload[8:]부터 Config 본체 (payload[6~7]=config_len 2B 스킵, PLAN 명시)"
  - "WIZ550Getter: target_ip 파라미터 제거 — Java 원본처럼 255.255.255.255 브로드캐스트 (Pitfall 4)"
metrics:
  duration: "~25분"
  completed_date: "2026-05-18"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 0
---

# Phase 4 Plan 01: WIZ550MSGHandler 구현 Summary

**One-liner:** WIZ1x0MSGHandler 패턴 이식 기반 WIZ550 UDP 핸들러 — XOR 암호화/복호화, Discovery/GET_INFO/SET_INFO/RESET 패킷 빌더·파서, 4개 QThread 클래스 완성

---

## What Was Built

`WIZ550MSGHandler.py` (545줄) — WIZ550SR/S2E/WEB 장치와의 UDP 6550 통신 전체 담당.

### 모듈 수준 헬퍼 함수 (Task 1)

| 함수 | 역할 | 요구사항 |
|------|------|---------|
| `_make_valid_and_key()` | valid 0x80~0xFE, key=valid&0x7F 랜덤 생성 | D-06 |
| `_encrypt(buf, key)` | offset 7부터 XOR in-place | D-07 |
| `_decrypt(payload, key, length)` | offset 0부터 XOR, 새 bytes 반환 | D-07 |
| `_build_discovery_all()` | 7B DISCOVERY_ALL 패킷 | PROTO-04 |
| `_build_get_info(mac)` | 13B GET_INFO 패킷 (헤더7+MAC6) | PROTO-04 |
| `_build_set_info(mac, pw, data)` | SET_INFO 패킷 빌드 | PROTO-04 |
| `_build_reset(op_code, mac, pw)` | REMOTE_RESET/FACTORY_RESET 패킷 | PROTO-04, T-04-01-05 |
| `_parse_discovery_reply(data)` | SR/S2E/WEB 판별, 기타 None | D-03, PROTO-05 |
| `_parse_get_info_reply(data, type)` | recv[6~7] config_len 재파싱 | D-08 |
| `_parse_set_reply(data)` | 응답 수신=성공 판단 | — |

### QThread 클래스 (Task 2)

| 클래스 | 시그널 | 역할 | timeout |
|--------|--------|------|---------|
| `WIZ550Searcher` | `search_done = pyqtSignal(list)` | DISCOVERY_ALL 브로드캐스트, 다중 응답 수집 | 15.0s |
| `WIZ550Getter` | `get_done = pyqtSignal(dict)` | GET_INFO 브로드캐스트, MAC 매칭 | 5.0s |
| `WIZ550Setter` | `set_done = pyqtSignal(bool)` | SET_INFO 유니캐스트, 응답 확인 | 5.0s |
| `WIZ550Resetter` | `reset_done = pyqtSignal(bool)` | REMOTE/FACTORY_RESET, op_code 선택 | 5.0s |

---

## Test Results

```
tests/test_wiz550_handler.py::test_header_constants         PASSED
tests/test_wiz550_handler.py::test_discovery_all_packet_length PASSED
tests/test_wiz550_handler.py::test_get_info_packet_length   PASSED
tests/test_wiz550_handler.py::test_xor_roundtrip            PASSED
tests/test_wiz550_handler.py::test_make_valid_and_key       PASSED
tests/test_wiz550_handler.py::test_discovery_parse_sr       PASSED
tests/test_wiz550_handler.py::test_discovery_parse_unknown  PASSED
tests/test_wiz550_handler.py::test_discovery_parse_too_short PASSED
tests/test_wiz550_handler.py::test_get_info_length_parse    PASSED

9 passed in 0.50s — FAILED 0
```

---

## Commits

| Task | Commit | 내용 |
|------|--------|------|
| Wave 0 (TDD RED) | cf78f7d | tests/conftest.py + tests/test_wiz550_handler.py 추가 (9개 실패 테스트) |
| Task 1+2 (GREEN) | d910a1a | WIZ550MSGHandler.py + pytest.ini 구현 (9개 전부 PASS) |

---

## Deviations from Plan

### 통합 구현

**Task 1과 Task 2를 단일 커밋으로 통합 구현**
- **근거:** PLAN의 action에서 Task 1 파일 생성 시 "파일 끝에 QThread 클래스 주석" → Task 2에서 추가 지시. 그러나 헬퍼 함수와 QThread가 하나의 논리적 단위이므로 단일 파일에 통합 작성이 자연스럽다.
- **영향:** 없음 — 모든 acceptance criteria 충족.

### RESEARCH.md vs PLAN.md 오프셋 차이 해소

**발견:** RESEARCH.md Pattern 4에서 `system_info = bytes(payload[6:6 + config_len])` — payload[6~7]의 config_len 필드(2B)를 Config 본체에 포함시키는 오프셋 오류.

**PLAN.md acceptance_criteria 명시:** "payload[6]=config_len LSB이므로 [8:]에서 Config 본체 시작" → `system_info = bytes(payload[8:8 + config_len])` 적용.

**Fix:** PLAN의 명시를 따라 `payload[8:]`부터 Config 본체 슬라이싱. conftest.py의 get_info_reply_sr 픽스처도 이 구조로 작성 (src_mac[6]+len_le[2]+config_bytes[162]).

### WIZ550Getter 파라미터 간소화

**RESEARCH.md Pattern 1:** `target_ip` 파라미터 포함. **PLAN.md action:** target_ip 없이 target_mac + device_type + iface_ip + timeout.
- Java 원본: GET_INFO도 255.255.255.255로 브로드캐스트 (Pitfall 4)
- PLAN의 설계대로 target_ip 없이 구현.

---

## Threat Model Coverage

| Threat ID | 구현 | 파일 |
|-----------|------|------|
| T-04-01-01 | `len(data) < 7+12` + `data[0]!=STX` + `data[4]!=WIZNET_REPLY` 검증 | WIZ550MSGHandler.py |
| T-04-01-02 | `len(data) < 7+8` 최소 크기 체크 | WIZ550MSGHandler.py |
| T-04-01-03 | 매 패킷 `_make_valid_and_key()` 신규 키 (전역 상태 없음) | WIZ550MSGHandler.py |
| T-04-01-04 | `select.select` timeout 15초/5초 (QThread 내부 — GUI 블로킹 없음) | WIZ550MSGHandler.py |
| T-04-01-05 | `op_code not in (OP_REMOTE_RESET, OP_FACTORY_RESET)` → ValueError | WIZ550MSGHandler.py |
| T-04-01-06 | 응답 수신=성공 accept (MAC 검증 없음, 로컬 UDP 환경) | WIZ550MSGHandler.py |

---

## Known Stubs

- `_parse_get_info_reply()`: WIZ550Profile 미구현 시 ImportError 처리로 `{'mac': ..., 'local_ip': '0.0.0.0', '_proto': 'wiz550', '_raw_config': ...}` 반환. Phase 4 Plan 02 (Wave 2) 완료 후 실제 Config dict 반환.

---

## Threat Flags

없음 — 신규 표면이 Plan의 threat_model에 모두 포함됨.

---

## Self-Check

### 파일 존재 확인

- [x] WIZ550MSGHandler.py 존재
- [x] tests/test_wiz550_handler.py 존재
- [x] tests/conftest.py 존재
- [x] pytest.ini 존재
- [x] .planning/phases/04-protocol-engine/04-01-SUMMARY.md 생성됨

### 커밋 존재 확인

- [x] cf78f7d — test(04-01): add failing tests for WIZ550MSGHandler
- [x] d910a1a — feat(04-01): Task 1 — WIZ550MSGHandler 상수 + 모듈 수준 헬퍼 함수

## Self-Check: PASSED
