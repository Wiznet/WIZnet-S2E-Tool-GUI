# Requirements: WIZ550SR/S2E/WEB 장치 지원

> Milestone: v1.6.3-wiz550  
> Created: 2026-05-15  
> Status: Active

## Active Requirements

### PROTO — UDP 프로토콜 엔진

- [ ] **PROTO-01**: UDP 포트 6550 송수신 소켓
  - WIZ550 계열은 포트 6550 전용. 기존 WIZ5xxSR(1460), WIZ1x0SR(1460)과 분리
  - SO_BROADCAST 활성화 (브로드캐스트 검색)
  - 수신 버퍼 1MB, 소켓 타임아웃 15초

- [ ] **PROTO-02**: 7바이트 고정 헤더 파싱/생성
  - `[STX=0xA5] [valid] [unicast] [op_code[0]] [op_code[1]=0xAA/0x55] [len_LSB] [len_MSB]`
  - valid: bit7=1 → 암호화됨, bit6~0 = XOR 키
  - length: 리틀엔디안 2바이트

- [ ] **PROTO-03**: XOR 암호화/복호화
  - 암호화 키: `valid & 0x7F` (랜덤 0x80~0xFE에서 하위 7비트)
  - encrypt: 헤더(offset 7) 이후 payload만 XOR
  - decrypt: parse_header가 payload를 [0]으로 shift 후 전체 length에 XOR

- [ ] **PROTO-04**: op_code 핸들링
  - `0xA1` DISCOVERY_ALL: 7바이트 (payload 없음), 브로드캐스트
  - `0xB0` GET_INFO: 6바이트 payload(대상 MAC), 유니캐스트
  - `0xC0` SET_INFO: 23 + config 바이트 payload, 유니캐스트
  - `0xD1` FIRMWARE_UPLOAD_INIT: 79바이트 payload (MAC + pw + TFTP 정보), 유니캐스트
  - `0xE0` REMOTE_RESET: 23바이트 payload, 유니캐스트
  - `0xF0` FACTORY_RESET: 23바이트 payload, 유니캐스트

- [ ] **PROTO-05**: Discovery 응답 장치 타입 판별
  - 응답 payload: product_code[3] + fw_version[3] + mac_address[6] = 12바이트
  - `product_code = [0x02, 0x00, 0x00]` → WIZ550SR
  - `product_code = [0x00, 0x00, 0x00]` → WIZ550S2E
  - `product_code = [0x01, 0x02, 0x00]` → WIZ550WEB
  - 기타 product_code → 무시(WIZ550 계열 아님)

- [ ] **PROTO-06**: QThread 기반 비동기 수신
  - WIZ550MSGHandler가 QThread 상속
  - 수신 완료 시 pyqtSignal 발신
  - 기존 WIZ1x0MSGHandler 패턴 준수

### PROF — Config 구조체 파싱/빌드

- [ ] **PROF-01**: WIZ550SR 162바이트 구조체 (`WIZ550Profile.py`)
  - module_type = [0x02, 0x00, 0x00]
  - 주요 필드: mac, local_ip, gateway, subnet, working_mode, remote_ip, local_port, remote_port, baud_rate(4B LE), data_bits, parity, stop_bits, flow_control, dhcp, dns, pw_setting, pw_connect, at_cmd
  - 제약: data_bits=8만, flow_control=None/RTS·CTS만, baud_rate 300 없음

- [ ] **PROF-02**: WIZ550S2E 가변 구조체 (162B + fw_ver[1]%2 기반 확장)
  - module_type = [0x00, 0x00, 0x00]
  - 기본 162B = WIZ550SR 동일 구조
  - fw_ver[1] 홀수 → MQTT 70B 추가 (총 232B): mqtt_user, mqtt_pw, publish_topic, subscribe_topic
  - fw_ver[1] 짝수 → Modbus 2B 추가 (총 164B): modbus_use, modbus_mode
  - 확장 포함 여부는 GET_INFO 응답 길이(recv[6~7])로 자동 판별

- [ ] **PROF-03**: WIZ550WEB 133바이트 구조체
  - module_type = [0x01, 0x02, 0x00]
  - 구조: mac, ip, gw, sn + UART0/UART1 시리얼(각 7B) + pw_setting, dhcp, dns
  - network_info(working_mode/remote_ip/포트 등) 없음 — 해당 UI 비활성화 처리

### SPEC — DeviceSpec YAML 정의

- [ ] **SPEC-01**: `specs/devices/WIZ550SR.yaml`
  - DeviceSpec 스키마 준수, handler=WIZ550MSGHandler
  - UI 위젯 그룹: Network / Serial / Options (working_mode 포함)

- [ ] **SPEC-02**: `specs/devices/WIZ550S2E.yaml`
  - MQTT/Modbus 탭 또는 조건부 위젯 포함
  - fw_ver 기반 확장 표시 정책 정의

- [ ] **SPEC-03**: `specs/devices/WIZ550WEB.yaml`
  - WIZ550WEB 비활성 필드 명시 (working_mode, remote_ip, at_cmd 등)
  - UART0/UART1 2채널 시리얼 위젯

- [ ] **SPEC-04**: 스키마 검증 통과
  - 3개 YAML 모두 `specs/schema/device.schema.json` 통과
  - `uv run python validate_schemas.py` 전체 통과

### UI — main_gui.py 통합

- [ ] **UI-01**: 검색 라우팅 — UDP 6550 포트 병렬 검색
  - 기존 검색(1460)과 독립적으로 WIZ550MSGHandler 인스턴스 생성
  - 검색 결과를 기존 장치 목록에 통합 표시

- [ ] **UI-02**: 장치 선택 → 설정 읽기
  - WIZ550 장치 선택 시 GET_INFO 전송 → WIZ550Profile 파싱 → UI 채우기
  - 장치 타입(SR/S2E/WEB)에 따라 적절한 탭/필드 표시

- [ ] **UI-03**: Apply → 설정 쓰기
  - UI 필드 수집 → WIZ550Profile 빌드 → SET_INFO 전송
  - 비밀번호 다이얼로그 표시 (기존 PasswordUI 상당 기능)

- [ ] **UI-04**: Reset / Factory Reset
  - REMOTE_RESET (0xE0) / FACTORY_RESET (0xF0) 패킷 전송
  - 비밀번호 포함

### FW — TFTP 펌웨어 업로드

- [ ] **FW-01**: tftpy 기반 로컬 TFTP 서버 구동
  - `tftpy` 패키지 사용 (requirements.txt 추가)
  - 서버 포트: 기본 69 (사용 가능 여부 확인 후 대체 포트 안내)
  - 업로드 완료 또는 타임아웃 시 서버 종료

- [ ] **FW-02**: op_code 0xD1 FW 업로드 시작 패킷 전송
  - payload: dst_mac(6) + pw_len(1) + pw(16) + server_ip(4) + server_port LE(2) + file_name(50)
  - 장치 IP로 유니캐스트 전송 (브로드캐스트 아님)

- [ ] **FW-03**: 업로드 완료 알림 (op_code 0xD2 응답) 처리
  - 완료 응답 수신 또는 타임아웃 시 사용자에게 결과 표시

- [ ] **FW-04**: FW 업로드 UI
  - 파일 선택 다이얼로그 (기존 FW 업로드 UI와 일관성 유지)
  - 프로그레스 표시 (QProgressBar)
  - 오류 시 명확한 메시지 (서버 시작 실패, 타임아웃, 장치 응답 없음)

## Out of Scope

- WIZ550 웹 인터페이스 설정 — 별도 계획 필요
- MQTT Working Mode UI (SPEC 정의만, 전체 MQTT 브로커 테스트 제외)
- 다중 WIZ550 장치 일괄 명령
- WIZ550 이외 신규 장치

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| PROTO-01~06 | Phase 4 | Pending |
| PROF-01~03  | Phase 4 | Pending |
| SPEC-01~04  | Phase 5 | Pending |
| UI-01~04    | Phase 6 | Pending |
| FW-01~04    | Phase 7 | Pending |
