---
phase: "04-protocol-engine"
verified: "2026-05-18T12:17:51Z"
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "WIZ550SR 장치를 실제 네트워크에 연결하고 DISCOVERY_ALL 브로드캐스트가 장치를 탐지하는지 확인한다"
    expected: "search_done 시그널에 device_type='WIZ550SR' 장치 dict가 포함된 list 수신"
    why_human: "실제 UDP 브로드캐스트 동작은 물리 장치 없이 검증 불가. WIZ550Searcher.run()이 소켓 I/O를 수행하므로 자동화 테스트 범위 초과"
  - test: "WIZ550SR 장치에 GET_INFO 요청 후 WIZ550Getter.get_done 시그널에 올바른 설정 dict가 수신되는지 확인한다"
    expected: "local_ip, mac, baud_rate 키가 포함된 dict 수신. local_ip가 장치 실제 IP와 일치"
    why_human: "실제 장치 응답 기반 D-08(recv[6~7] 재파싱) 동작 확인은 단위 테스트 픽스처로 대체됨. 실 장치로 최종 확인 필요"
  - test: "WIZ550Setter.set_done 시그널에 True 수신 및 장치 설정 반영 확인"
    expected: "SET_INFO 전송 후 set_done.emit(True) 수신. 장치 재부팅 후 변경된 설정 GET_INFO로 재확인"
    why_human: "설정 쓰기는 실제 장치 없이 검증 불가. WIZ550Setter는 소켓 I/O QThread"
---

# Phase 4: Protocol Engine Verification Report

**Phase Goal:** WIZ550 계열 전용 UDP 핸들러와 Config 구조체 파서를 구현하여 검색·설정 읽기·쓰기·리셋 패킷을 정확히 송수신한다
**Verified:** 2026-05-18T12:17:51Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WIZ550MSGHandler.py가 존재하며 4개 QThread 클래스를 export한다 (D-01) | VERIFIED | `WIZ550MSGHandler.py` 543줄 존재. `WIZ550Searcher`, `WIZ550Getter`, `WIZ550Setter`, `WIZ550Resetter` 4개 QThread 클래스 확인. import 성공 |
| 2 | DISCOVERY_ALL(0xA1) 패킷이 정확히 7B이고 STX=0xA5로 시작한다 (PROTO-02) | VERIFIED | `_build_discovery_all()` 반환값 7B, `pkt[0]==0xA5`, `pkt[3]==0xA1`, `pkt[4]==0xAA` 동작 확인. pytest PASSED |
| 3 | XOR 암호화/복호화 왕복 테스트(test_xor_roundtrip)가 PASSED 상태다 (D-06, D-07) | VERIFIED | `_encrypt(buf, key)` offset 7부터 in-place. `_decrypt` 복원 검증. pytest PASSED. `_make_valid_and_key()` 20회 반복: valid 0x80~0xFE, key=valid&0x7F 확인 |
| 4 | Discovery 응답에서 product_code[0~2]로 SR/S2E/WEB을 판별하고 기타는 None 반환한다 (D-03, PROTO-05) | VERIFIED | `_parse_discovery_reply` 구현. product_code=[0x02,0x00,0x00]→WIZ550SR, [0x00,0x00,0x00]→WIZ550S2E, [0x01,0x02,0x00]→WIZ550WEB, 기타→None. pytest PASSED |
| 5 | GET_INFO 응답의 config_len을 recv[6~7]에서 직접 파싱한다 (D-08 MSB 버그 우회) | VERIFIED | `_parse_get_info_reply`에서 `config_len = (payload[6]&0xFF) + ((payload[7]&0xFF)<<8)` 구현. system_info는 payload[8:]부터. D-08 동작 확인 (local_ip=192.168.0.100, mac=00:08:DC:AB:CD:EF) |
| 6 | 소켓 설정: SO_BROADCAST, SO_RCVBUF=1MB, Searcher 타임아웃 15초, 기타 5초 (D-05) | VERIFIED | 4개 QThread 모두 `SO_BROADCAST`, `SO_RCVBUF=1024*1024`. `WIZ550Searcher.__init__` timeout=15.0, Getter/Setter/Resetter timeout=5.0 |
| 7 | WIZ550Profile.py가 존재하며 parse_sr/build_sr, parse_s2e/build_s2e, parse_web/build_web 6개 공개 함수를 export한다 (D-02) | VERIFIED | `WIZ550Profile.py` 228줄 존재. 6개 함수 import 성공. `_parse_base_162` 내부 헬퍼로 SR/S2E 코드 공유 |
| 8 | parse_sr(162B)/parse_web(133B) 왕복 검증 및 parse_s2e 3종 변형 판별이 통과한다 (PROF-01~03) | VERIFIED | test_sr_roundtrip PASSED. test_web_roundtrip PASSED. test_s2e_base_variant/modbus/mqtt PASSED. WEB dict에 pw_connect 없음(Pitfall 6 준수) |
| 9 | struct.calcsize(SR_FORMAT)==162, struct.calcsize(WEB_FORMAT)==133가 import 시점에 통과한다 | VERIFIED | `import WIZ550Profile` 시 assert 통과 확인. SR_SIZE=162, WEB_SIZE=133, MQTT_SIZE=70, MODBUS_SIZE=2 |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/__init__.py` | pytest 패키지 인식 | VERIFIED | 파일 존재 |
| `tests/conftest.py` | 공통 픽스처 sr_bytes/s2e_*/web_bytes/discovery_reply_sr/get_info_reply_sr | VERIFIED | 6개 @pytest.fixture 정의 확인 |
| `tests/test_wiz550_handler.py` | PROTO-02/03/05/D-08 테스트 9개 | VERIFIED | 9개 test_ 함수, 전부 PASSED |
| `tests/test_wiz550_profile.py` | PROF-01/02/03 테스트 8개 | VERIFIED | 8개 test_ 함수, 전부 PASSED |
| `WIZ550MSGHandler.py` | WIZ550Searcher/Getter/Setter/Resetter QThread + 헬퍼 함수 + 상수 | VERIFIED | 543줄, 4개 QThread, 10개 헬퍼 함수, 상수 완비 |
| `WIZ550Profile.py` | SR/S2E/WEB 구조체 파서/빌더 | VERIFIED | 228줄, parse_sr/build_sr/parse_s2e/build_s2e/parse_web/build_web + SR_FORMAT assert |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `WIZ550MSGHandler._parse_get_info_reply` | `WIZ550Profile::parse_sr/parse_s2e/parse_web` | `from WIZ550Profile import parse_sr, parse_s2e, parse_web` (line 269) | VERIFIED | 동적 import로 연결. ImportError 처리로 Wave 2 이전 graceful degradation |
| `WIZ550Searcher.run()` | `search_done.emit(list)` | `pyqtSignal(list)` | VERIFIED | line 312: `search_done = pyqtSignal(list)`, line 370: `self.search_done.emit(result_list)` |
| `WIZ550Getter.run()` | `get_done.emit(dict)` | `pyqtSignal(dict)` | VERIFIED | line 380: `get_done = pyqtSignal(dict)`, line 426: `self.get_done.emit(result)` |
| `parse_s2e` | `_parse_base_162` | 내부 헬퍼 호출 (D-02) | VERIFIED | `_parse_base_162` line 152, `parse_s2e`에서 호출 확인 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `WIZ550Searcher.run()` | `results` dict | UDP socket `recvfrom` + `_parse_discovery_reply` | Yes — real UDP 수신, product_code 기반 파싱 | FLOWING (단위 테스트 검증, 실제 소켓 I/O는 human needed) |
| `WIZ550Getter.run()` | `result` dict | `_parse_get_info_reply` → `WIZ550Profile.parse_sr/s2e/web` | Yes — struct.unpack 기반 실제 파싱, 왕복 테스트 PASS | FLOWING |
| `parse_sr(data)` | `fields` | `struct.unpack(SR_FORMAT, data[:SR_SIZE])` | Yes — 162B struct 언팩, 왕복 검증 통과 | FLOWING |
| `parse_s2e(data)` | `d` + variant ext | `_parse_base_162` + MQTT/MODBUS struct 언팩 | Yes — 3종 변형 모두 테스트 PASS | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_build_discovery_all()` → 7B 패킷 | python assert `len(pkt)==7`, `pkt[0]==0xA5`, `pkt[3]==0xA1` | OK | PASS |
| XOR `_encrypt`/`_decrypt` 왕복 | python roundtrip 검증 | `decrypted == original` | PASS |
| `parse_sr` → `build_sr` → 원본 일치 | python roundtrip 검증 162B | `rebuilt == bytes(buf2)` | PASS |
| `_build_get_info('00:08:DC:AB:CD:EF')` → 13B | python assert `len(pkt)==13` | OK | PASS |
| `parse_s2e` 232B(fw[1]=1) → mqtt | python 검증 | `s2e_variant=='mqtt'` | PASS |
| `parse_s2e` 164B(fw[1]=0) → modbus | python 검증 | `s2e_variant=='modbus'` | PASS |
| D-08: `_parse_get_info_reply` recv[6~7] 재파싱 | python 검증 | `local_ip=='192.168.0.100'`, `mac=='00:08:DC:AB:CD:EF'` | PASS |
| `WIZ550Searcher(timeout=15.0)` timeout 기본값 | grep | `timeout: float = 15.0` in `__init__` | PASS |
| 실제 장치 UDP 통신 (Searcher/Getter/Setter/Resetter) | N/A | 물리 장치 필요 | SKIP — human_needed |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROTO-01 | 04-01-PLAN | UDP 포트 6550 송수신 소켓, SO_BROADCAST, SO_RCVBUF 1MB, 타임아웃 15초 | SATISFIED | `WIZ550_PORT=6550`, `SO_BROADCAST`, `SO_RCVBUF=1024*1024`, Searcher timeout=15.0s |
| PROTO-02 | 04-00, 04-01-PLAN | 7바이트 고정 헤더 파싱/생성 | SATISFIED | `_build_header_with_payload`, `_build_discovery_all` 7B 검증 PASS |
| PROTO-03 | 04-00, 04-01-PLAN | XOR 암호화/복호화 | SATISFIED | `_encrypt`/`_decrypt`, `_make_valid_and_key`, test_xor_roundtrip PASSED |
| PROTO-04 | 04-01-PLAN | op_code 핸들링 (0xA1/0xB0/0xC0/0xE0/0xF0) | SATISFIED | `_build_discovery_all`/`_build_get_info`/`_build_set_info`/`_build_reset` 구현 확인 |
| PROTO-05 | 04-00, 04-01-PLAN | Discovery 응답 장치 타입 판별 | SATISFIED | `_parse_discovery_reply`, product_code SR/S2E/WEB 판별, test_discovery_parse_sr PASSED |
| PROTO-06 | 04-01-PLAN | QThread 기반 비동기 수신, pyqtSignal 발신 | SATISFIED | 4개 QThread 클래스, search_done/get_done/set_done/reset_done pyqtSignal 확인 |
| PROF-01 | 04-00, 04-02-PLAN | WIZ550SR 162B 구조체 | SATISFIED | `parse_sr`/`build_sr`, test_sr_roundtrip PASSED |
| PROF-02 | 04-00, 04-02-PLAN | WIZ550S2E 가변 구조체 (162~232B, fw_ver[1] 기반) | SATISFIED | `parse_s2e`, D-04 이중 판별, test_s2e_*_variant PASSED |
| PROF-03 | 04-00, 04-02-PLAN | WIZ550WEB 133B 구조체 | SATISFIED | `parse_web`/`build_web`, pw_connect 없음, test_web_roundtrip PASSED |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `WIZ550MSGHandler.py` | 267~443 | `_parse_get_info_reply` 함수 끝부분 `return {}` (ImportError 처리 후 도달 불가 dead code) | Info | WIZ550Profile 정상 import 시 도달하지 않는 코드. 기능 영향 없음 |

**해설:** `_parse_get_info_reply`의 마지막 `return {}`(line 443 부근)는 `try-except ImportError` 블록 이후에 위치하나, `try` 블록 내에서 device_type 불일치 시 도달 가능한 경로이기도 하다. Blocker 아님.

### Human Verification Required

#### 1. WIZ550 장치 실제 검색 동작 확인

**Test:** WIZ550SR/S2E/WEB 장치를 동일 네트워크에 연결 후 앱에서 검색 실행
**Expected:** 장치가 장치 목록에 표시되며 device_type과 MAC이 올바르게 출력됨
**Why human:** UDP 브로드캐스트 동작과 실제 장치 응답 파싱은 물리 장치 없이 검증 불가. QThread의 소켓 I/O는 자동화 단위 테스트 범위 초과

#### 2. GET_INFO (설정 읽기) 실제 동작 확인

**Test:** 검색된 WIZ550SR 장치를 선택하고 설정 읽기 트리거
**Expected:** WIZ550Getter가 GET_INFO 패킷을 전송하고 get_done 시그널에 실제 장치 설정 dict 수신. local_ip, mac, baud_rate 필드가 장치 실제 값과 일치
**Why human:** D-08(recv[6~7] 재파싱) 동작을 실제 장치 응답으로 최종 확인해야 함. 단위 테스트는 픽스처 바이트로 검증함

#### 3. SET_INFO (설정 쓰기) 실제 동작 확인

**Test:** UI 필드 변경 후 Apply → WIZ550Setter 실행 → set_done.emit(True) 수신 → 장치 재부팅 후 GET_INFO로 변경 설정 재확인
**Expected:** set_done(True) 수신, 재부팅 후 변경값이 GET_INFO 응답에 반영됨
**Why human:** 설정 쓰기 성공 여부는 실제 장치 없이 검증 불가

### Gaps Summary

갭 없음 — 9개 must-have 전부 verified, 17개 테스트 전부 PASSED.

자동화로 검증 불가한 실제 장치 통신 3건에 대해 human verification이 필요하다.

---

_Verified: 2026-05-18T12:17:51Z_
_Verifier: Claude (gsd-verifier)_
