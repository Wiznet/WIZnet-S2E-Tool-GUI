# Phase 4: Protocol Engine - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>

## Phase Boundary

WIZ550MSGHandler.py + WIZ550Profile.py 신규 구현.
UDP 6550 + XOR 암호화 + SR/S2E/WEB 바이너리 구조체 파싱/빌드.
main_gui.py 연결은 Phase 6 범위 — 이 Phase는 순수 핸들러/프로파일 모듈만.

</domain>

<decisions>

## Implementation Decisions

### QThread 클래스 분할

- **D-01**: `WIZ550MSGHandler.py`에 4개의 QThread 클래스 구현
  - `WIZ550Searcher` — DISCOVERY_ALL(0xA1) 브로드캐스트, 다중 응답 수집, `search_done = pyqtSignal(list)` 발신
  - `WIZ550Getter` — GET_INFO(0xB0) 유니캐스트, 단일 Config 응답, `get_done = pyqtSignal(dict)` (or `pyqtSignal(bytes)`) 발신
  - `WIZ550Setter` — SET_INFO(0xC0) 유니캐스트, `set_done = pyqtSignal(bool)` 발신
  - `WIZ550Resetter` — REMOTE_RESET(0xE0) / FACTORY_RESET(0xF0), op_code 파라미터로 구분, `reset_done = pyqtSignal(bool)` 발신
  - 근거: SetInfo와 Reset을 의미상 분리. Reset은 "쓰기 없는 명령"이라 Setter와 개념적으로 다름.

### Profile 파일 구조

- **D-02**: 단일 파일 `WIZ550Profile.py`에 SR/S2E/WEB 모두 구현
  - 공개 함수: `parse_sr()`, `build_sr()`, `parse_s2e()`, `build_s2e()`, `parse_web()`, `build_web()`
  - 내부 헬퍼: `_parse_base_162()` — SR과 S2E가 공유하는 기본 162B 구조 파싱
  - 근거: SR과 S2E가 기본 162B struct를 공유 → 공통 헬퍼를 파일 내부에서 자연스럽게 공유. WIZ1x0Profile.py 패턴과 일치.

### Discovery 필터 전략

- **D-03**: DISCOVERY_ALL(0xA1) 브로드캐스트 후 응답 product_code[0~2]로 필터링
  - `product_code = [0x02, 0x00, 0x00]` → WIZ550SR
  - `product_code = [0x00, 0x00, 0x00]` → WIZ550S2E
  - `product_code = [0x01, 0x02, 0x00]` → WIZ550WEB
  - 기타 product_code → 무시 (WIZ550 계열 아님)
  - 근거: 원본 Java 구현 동일 방식. A2(product_code 검색)는 패킷 3배로 불필요.

### WIZ550S2E 가변 구조 판별

- **D-04**: 이중 판별 — 데이터 길이 우선 + fw_ver[1] 홀짝 검증
  - `len(payload) >= 232` AND `fw_ver[1] % 2 != 0` → MQTT 232B 구조
  - `len(payload) >= 164` AND `fw_ver[1] % 2 == 0` → Modbus 164B 구조
  - 기본(162B) → S2E 확장 없음 처리
  - 근거: 데이터 길이가 주방어선(트런케이션 오파싱 방지), fw_ver은 검증용.

### 기타 확정 사항

- **D-05**: UDP 포트 6550 전용 소켓 (SO_BROADCAST 활성화, 수신 버퍼 1MB, 타임아웃 15초)
- **D-06**: XOR 암호화 키 = 랜덤 `0x80 + random.randint(0, 0x7E)` 매 패킷 생성, 키 = `valid & 0x7F`
- **D-07**: encrypt: offset 7부터 XOR (헤더 7B 스킵). decrypt: parse 후 offset 0부터 XOR.
- **D-08**: Getter 응답 길이 파싱: recv[6~7] 재파싱 (원본 Java parse_header의 MSB 버그 우회)

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Protocol Specification (원본 분석)

- `~/.claude/docs/WIZnet-S2E-Tool-GUI/research/2026-05-14-wiz550-protocol-analysis.md` — WIZ550 전체 프로토콜 완전 분석. 헤더 구조, XOR 알고리즘, op_code 목록, Config 구조체 바이트맵 포함. 반드시 읽을 것.

### Existing Handler Pattern (참조 구현)

- `WIZ1x0MSGHandler.py` — WIZ1x0SR 핸들러 패턴: Searcher/Setter QThread 분리, socket+select 방식, 시그널 발신
- `WIZ1x0Profile.py` — WIZ1x0SR 구조체 파서 패턴: STRUCT_FORMAT 문자열, struct.pack/unpack, parse/build 함수 쌍

### Requirements

- `.planning/REQUIREMENTS.md` §PROTO, §PROF — Phase 4 범위 REQ-ID: PROTO-01~06, PROF-01~03

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `WIZ1x0MSGHandler.py:33` `WIZ1x0Searcher(QThread)` — select 루프 + 타임아웃 패턴 그대로 참조
- `WIZ1x0MSGHandler.py:115` `WIZ1x0Setter(QThread)` — unicast send + select 응답 대기 패턴 참조
- `WIZ1x0Profile.py:33` `STRUCT_FORMAT` 정의 방식 + `assert struct.calcsize() == SIZE` 검증 패턴 참조
- `utils.py` `logger` — 기존 로거 모듈 재사용 (`from utils import logger`)

### Established Patterns

- QThread 클래스: `__init__` 파라미터 받아 저장 → `run()`에서 실행 → 시그널 발신
- socket.socket + socket.SO_BROADCAST + select.select + sock.recvfrom 조합 (subprocess 없음)
- 소켓: `try-finally`로 반드시 닫기
- 응답 MAC 기반 중복 제거: `results = {}` dict + `if mac not in results`

### Integration Points

- Phase 6에서 main_gui.py가 `from WIZ550MSGHandler import WIZ550Searcher, WIZ550Getter, WIZ550Setter, WIZ550Resetter` import
- main_gui.py의 `search_pre()` 함수에 `WIZ550Searcher` 인스턴스 생성 + `search_done` 시그널 연결 추가 (WIZ1x0Searcher와 동일 방식)

</code_context>

<specifics>

## Specific Ideas

- WIZ1x0Profile.py의 `assert struct.calcsize(STRUCT_FORMAT) == BOARD_INFO_SIZE` 패턴을 SR/S2E/WEB 각 struct에도 적용
- `parse_s2e()` 내부에서 MQTT/Modbus 분기를 명확한 주석과 함께 처리

</specifics>

<deferred>

## Deferred Ideas

- WIZ550 FW 업로드 (TFTP) — Phase 7에서 별도 구현
- WIZ550 장치별 DeviceSpec YAML — Phase 5에서 구현
- main_gui.py 통합 — Phase 6에서 구현

</deferred>

---

*Phase: 04-protocol-engine*
*Context gathered: 2026-05-15*
