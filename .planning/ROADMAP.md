# Roadmap: WIZ550SR/S2E/WEB 장치 지원

> Milestone: v1.6.3-wiz550  
> Phase numbering continues from v1.6.3 GSD (Phases 1~3 완료)

## Overview

WIZ550SR / WIZ550S2E / WIZ550WEB 세 장치를 기존 GUI 툴에 통합한다.
UDP 포트 6550 + XOR 암호화 + 바이너리 Config 구조체 기반 프로토콜을 구현하고,
DeviceSpec YAML로 UI를 정의하며, TFTP 방식 펌웨어 업로드까지 포함한다.

## Phases

**Phase Numbering:**
- Integer phases (4, 5, 6, 7, 8): Planned milestone work
- Phases 1~3 completed in prior milestone (v1.6.3 Device Module Architecture)

- [x] **Phase 4: Protocol Engine** — WIZ550MSGHandler.py + WIZ550Profile.py 신규 구현 (completed 2026-05-18)
- [x] **Phase 5: DeviceSpec YAML** — specs/devices/ WIZ550SR/S2E/WEB.yaml 3개 작성 (completed 2026-05-18)
- [ ] **Phase 6: GUI Integration** — main_gui.py 검색·설정·Apply·Reset 연결
- [ ] **Phase 7: TFTP FW Upload** — tftpy 기반 로컬 서버 + op_code 0xD1 전송
- [ ] **Phase 8: Release** — v1.6.3 빌드·서명·릴리즈

## Phase Details

### Phase 4: Protocol Engine

**Goal**: WIZ550 계열 전용 UDP 핸들러와 Config 구조체 파서를 구현하여 검색·설정 읽기·쓰기·리셋 패킷을 정확히 송수신한다

**Depends on**: Nothing (새 파일 신규 구현)

**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06, PROF-01, PROF-02, PROF-03

**Success Criteria** (what must be TRUE):
  1. `WIZ550MSGHandler.py`가 UDP 6550으로 DISCOVERY_ALL 브로드캐스트를 전송하고 응답을 수신하여 장치 타입(SR/S2E/WEB)을 판별한다
  2. `WIZ550Profile.py`가 SR 162B / S2E 164B·232B / WEB 133B 구조체를 올바르게 파싱하고 재빌드한다 (왕복 테스트)
  3. XOR 암호화/복호화가 원본 Java 구현과 동일하게 동작한다
  4. QThread 기반으로 동작하며 시그널로 결과를 전달한다

**Plans**: 3 plans

Plans:
- [x] 04-00-PLAN.md — Wave 0 테스트 스텁 (tests/ 디렉토리 + conftest.py + stub 파일)
- [x] 04-01-PLAN.md — WIZ550MSGHandler.py 구현 (4개 QThread + 헬퍼 함수)
- [x] 04-02-PLAN.md — WIZ550Profile.py 구현 (SR/S2E/WEB 구조체 파서/빌더)

### Phase 5: DeviceSpec YAML

**Goal**: WIZ550SR, WIZ550S2E, WIZ550WEB 세 장치의 DeviceSpec YAML을 작성하여 UI 위젯 매핑과 필드 제약을 정의한다

**Depends on**: Phase 4 (handler class명 확정 필요)

**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04

**Success Criteria** (what must be TRUE):
  1. `specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml` 3개 파일 존재
  2. 3개 모두 `specs/schema/device.wiz550.schema.json` 검증 통과 (`validate_schemas.py` 전체 통과)
  3. WIZ550WEB 비활성 필드(working_mode, remote_ip 등)가 YAML에 명시적으로 정의됨

**Plans**: 2 plans

Plans:
- [x] 05-00-PLAN.md — Wave 0: WIZ550 스키마 + 테스트 스텁 + validate_schemas.py 라우팅
- [x] 05-01-PLAN.md — Wave 1: WIZ550SR/S2E/WEB.yaml 3개 작성

### Phase 6: GUI Integration

**Goal**: main_gui.py가 WIZ550 장치를 검색 목록에 표시하고, 장치 선택 시 설정을 읽어 UI에 표시하며, Apply/Reset/FactoryReset을 정확히 전송한다

**Depends on**: Phase 4, Phase 5

**Requirements**: UI-01, UI-02, UI-03, UI-04

**UI Implementation Approach** (Auto Layout — see 06-CONTEXT.md):

- WIZ550 설정 패널: .ui 파일 수정 없이 **Python 코드로 동적 생성** (장치 3종 분기 대응)
- 레이아웃: QVBoxLayout + QHBoxLayout 계층 (QGridLayout 최소화)
- 간격: DESIGN.md 토큰 — xs=8px(행 간격), md=16px(패널 여백)
- 색상: Apply 버튼 #cc785c, 성공 #5db872, 오류 #c64545 (신규 UI 요소에만 적용)

**Success Criteria** (what must be TRUE):
  1. 검색 시 WIZ550 장치가 기존 장치 목록에 함께 표시된다 (MAC, IP, 장치명, FW 버전)
  2. WIZ550 장치 선택 시 해당 설정이 UI 탭에 올바르게 표시된다
  3. Apply 후 SET_INFO 응답(0xC0/0x55)을 수신하면 성공 메시지가 표시된다
  4. Reset / Factory Reset이 정상 동작한다
  5. 기존 WIZ5xxSR / WIZ1x0SR 검색·설정에 회귀가 없다

**Plans**: TBD

### Phase 7: TFTP FW Upload

**Goal**: WIZ550 장치에 펌웨어를 TFTP 방식으로 업로드한다. 로컬 TFTP 서버를 구동하고 op_code 0xD1 패킷을 전송하여 장치가 능동적으로 파일을 수신하게 한다

**Depends on**: Phase 4, Phase 6

**Requirements**: FW-01, FW-02, FW-03, FW-04

**Success Criteria** (what must be TRUE):
  1. `tftpy` 라이브러리로 로컬 TFTP 서버가 구동되고 FW 파일이 서빙된다
  2. op_code 0xD1 패킷이 올바른 바이트 레이아웃으로 전송된다 (서버 IP/포트/파일명 포함)
  3. 업로드 완료(0xD2 응답) 또는 타임아웃 시 결과가 사용자에게 표시된다
  4. QProgressBar 또는 상태 메시지로 진행 상황이 표시된다

**Plans**: TBD

### Phase 8: Release

**Goal**: v1.6.3 공개 릴리즈 — 빌드·서명·GitHub Release 게시

**Depends on**: Phase 7

**Requirements**: (없음 — 구현 완료 확인 + 릴리즈 절차)

**Success Criteria** (what must be TRUE):
  1. `build.ps1` 빌드 성공 (미서명 + 서명본)
  2. GitHub Release에 v1.6.3 태그 + 릴리즈 노트 게시
  3. Wiki v1.6.3 업데이트 (WIZ550 장치 지원 내용 포함)

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 4. Protocol Engine | 3/3 | Complete    | 2026-05-18 |
| 5. DeviceSpec YAML | 0/2 | Pending | — |
| 6. GUI Integration | 0/TBD | Pending | — |
| 7. TFTP FW Upload | 0/TBD | Pending | — |
| 8. Release | 0/TBD | Pending | — |

---

*Prior milestone (v1.6.3 Device Module Architecture) phases:*

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema Definition | 1/1 | Complete | 2026-05-13 |
| 2. Module Metadata | 1/1 | Complete | 2026-05-15 |
| 3. Loader Integration | 1/1 | Complete | 2026-05-15 |
