# Phase 7: TFTP FW Upload - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>

## Phase Boundary

WIZ550 장치에 펌웨어를 TFTP 방식으로 업로드한다.
- op_code 0xD1 (FIRMWARE_UPLOAD_INIT) 패킷 전송 → 장치가 능동적으로 TFTP 서버에서 파일 수신
- op_code 0xD2 (FIRMWARE_UPLOAD_DONE) 응답 처리
- 내장 tftpy 서버 방식과 외부 TFTP 서버 수동 방식 둘 다 지원

</domain>

<decisions>

## Implementation Decisions

### TFTP 서버 방식

- **D-01**: **방식 C — 내장 tftpy + 외부 TFTP 수동 입력 둘 다 지원**
  - 별도 `WIZ550FW Upload` 다이얼로그 창 사용 (탭 2개 구조)
  - **탭 1 "자동 (내장 TFTP)"**: 파일 선택 → tftpy 로컬 서버 자동 구동 → 0xD1 전송
  - **탭 2 "수동 (외부 TFTP)"**: 서버 IP / 포트 / 파일명 직접 입력 → 0xD1만 전송

- **D-02**: 내장 tftpy 모드에서 포트 69 바인딩 실패 시 → **오류 메시지 표시 후 중단**
  - 자동 fallback 없음. "Port 69 requires Administrator privileges" 안내.
  - 사용자가 수동 탭으로 전환하거나 외부 TFTP 서버를 사용하도록 유도.

- **D-03**: 수동 탭에서 서버 IP는 현재 선택된 NIC IP를 자동 채움 (편집 가능)
  - 기본 포트: 69

### 비밀번호 처리

- **D-04**: 0xD1 패킷의 `set_pw_len` / `set_pw[16]` 필드 — **다이얼로그에 pw 입력 필드 추가**
  - 선택적 입력 (비워두면 pw_len=0, pw=zeros)
  - WIZ550이 실제로 비밀번호를 사용하는지 추후 실장치 테스트로 확인 필요
  - 현재는 입력 가능하게 만들어두고 필요 시 제거

### 코드 구조

- **D-05**: FW 업로더 QThread → **별도 `WIZ550FWUploadThread.py`** 파일 생성
  - `FWUploadThread.py` 패턴 참조하되, tftpy 서버 기반으로 완전히 다른 구현
  - `WIZ550MSGHandler.py`에는 0xD1 패킷 빌더 함수만 추가 (이미 OP_FW_UPLOAD=0xD1 상수 존재)

- **D-06**: `event_upload_clicked()` 분기 — WIZ550 장치 선택 시 전용 다이얼로그 실행
  - 기존 패턴: `_proto == 'wiz550'` 체크 → `upload_wiz550()` 호출 (새 함수)
  - 기존 WIZ1x0SR 처리 (`return` 후 미지원 메시지)와 동일 위치에 분기 추가

### 진행 표시

- **D-07**: **tftpy 콜백 활용**
  - 전송 시작 시: QProgressBar 애니메이션 시작 (indeterminate)
  - tftpy completion callback에서 완료 감지 → 100% 점프
  - 0xD2 응답 수신 또는 타임아웃 시 결과 메시지 표시

### Claude's Discretion

- 다이얼로그 정확한 위젯 배치 (QTabWidget, 버튼 배치 등) — Phase 6 D-02~D-04 디자인 토큰 따름
- 0xD2 응답 수신 소켓 구현 방식 (WIZ550FWUploadThread 내부에서 UDP 리슨)
- 타임아웃 값 (시작: 30초 권장)
- tftpy 정확한 콜백 API 사용법 (리서처가 조사)

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 프로토콜 분석 (필수 선행 독서)
- `~/.claude/docs/WIZnet-S2E-Tool-GUI/research/2026-05-14-wiz550-protocol-analysis.md` §3.5.7 firmware_upload() — 0xD1 패킷 레이아웃 (86바이트 구조, server_port LE 엔디안 주의)
- `~/.claude/docs/WIZnet-S2E-Tool-GUI/research/2026-05-14-wiz550-protocol-analysis.md` §10.6 FW 업로드 실제 메커니즘

### 0xD1 패킷 구조 (오프셋 기준)
```
offset 7~12:  dst_mac_address[6]
offset 13:    set_pw_len[1]
offset 14~29: set_pw[16]
offset 30~33: server_ip[4]
offset 34~35: server_port[2] (LE — LSB first)
offset 36~85: file_name[50] (0 패딩)
총 86바이트 (header 7 + payload 79)
```

### 기존 코드 패턴 (참조 구현)
- `WIZ550MSGHandler.py` — OP_FW_UPLOAD=0xD1 상수, XOR 암호화 헬퍼 (`_build_packet()`, `_encrypt()`)
- `FWUploadThread.py` — QThread 패턴, uploading_size/upload_result/error_flag 시그널 구조
- `main_gui.py` `event_upload_clicked()` (line ~1250) — WIZ1x0SR 분기 패턴 (WIZ550 분기 추가 위치)
- `main_gui.py` `event_setting_clicked()` / `event_reset_clicked()` — `_proto == 'wiz550'` 분기 패턴

### Requirements
- `.planning/REQUIREMENTS.md` §FW — FW-01~04

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets
- `WIZ550MSGHandler.py::_build_packet()` + `_encrypt()` — 0xD1 패킷 빌드에 재사용 가능
- `WIZ550MSGHandler.py::OP_FW_UPLOAD = 0xD1` 상수 이미 정의됨
- `main_gui.py::localip_addr` — 현재 NIC IP (수동 탭 서버 IP 자동채움에 사용)
- `main_gui.py::dev_profile[mac]['_proto']` — WIZ550 장치 감지
- Phase 6 D-02~D-05 디자인 토큰 — 다이얼로그 위젯에 동일 적용

### Established Patterns
- WIZ550 버튼 라우팅: `_proto == 'wiz550'` 체크 → 전용 함수 호출
- QThread 시그널: `uploading_size(int)`, `upload_result(int)`, `error_flag(int)` (FWUploadThread 패턴)
- `event_upload_clicked()` — 기존 WIZ1x0SR "미지원" 분기가 있는 위치 (새 WIZ550 분기 추가)

### Integration Points
- `event_upload_clicked()` in `main_gui.py` — WIZ550 분기 추가 지점
- `WIZ550FWUploadThread.py` 신규 파일 (FWUploadThread.py와 병렬 구조)
- `WIZ550MSGHandler.py` — 0xD1 패킷 빌더 함수 추가 (build_fw_upload_pkt)
- 다이얼로그 클래스: 별도 `wiz550_fw_dialog.py` 또는 `main_gui.py` 내 클래스

</code_context>

<specifics>

## Specific Ideas

- Java 원본 툴은 외부 TFTP 서버를 전제로 했음 — 내장 tftpy는 현장 편의를 위한 개선
- 포트 69 실패 안내 메시지: "Port 69 requires Administrator privileges. Please use external TFTP mode."
- tftpy 콜백: `tftpy.TftpServer` listen 시 completionCallback 또는 progressHook 인자로 완료 감지

</specifics>

<deferred>

## Deferred Ideas

- WIZ550 비밀번호 필드 실제 동작 여부 — 실장치 테스트 후 필드 유지 또는 제거 결정
- tftpy 내 전송 진행률 % 실시간 표시 — 콜백 API가 지원하면 추후 개선
- 포트 69 자동 fallback (고포트) — 오류 메시지 방식으로 결정, 추후 사용자 요청 시 추가 가능

</deferred>

---

*Phase: 07-tftp-fw-upload*
*Context gathered: 2026-05-19*
