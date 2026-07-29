# WIZnet S2E Tool GUI

## What This Is

WIZnet S2E(Serial-to-Ethernet) 모듈 설정 GUI 도구. UDP 브로드캐스트로 네트워크상의 WIZnet 장치를 검색하고, 네트워크·시리얼·보안 설정을 읽고 쓰며, 펌웨어를 업로드한다. Windows 현장 엔지니어를 주 대상으로 한다.

## Core Value

현장 엔지니어가 WIZnet S2E 장치를 네트워크로 검색·설정할 수 있는 신뢰할 수 있는 도구.

## Requirements

### Validated

- ✓ UDP 브로드캐스트 장치 검색 — v1.0~
- ✓ 장치 설정 읽기/쓰기 (Network, Serial, Options) — v1.0~
- ✓ 펌웨어 업로드 (FTP 방식) — v1.0~
- ✓ WIZ107SR / WIZ108SR 전면 지원 (cmd_107sr, DDNS/PPPoE/PO) — v1.6.0
- ✓ WIZ1x0SR 바이너리 프로토콜 지원 (FIND/IMIN/SETT/SETC, UDP:1460) — v1.6.1
- ✓ DeviceSpec YAML 기반 장치 프로파일 시스템 — v1.6.2.1
- ✓ GitHub Releases에서 펌웨어 다운로드·업로드 (FW from Git) — v1.6.2.1
- ✓ 터미널 유틸리티 패널 (Hercules 대체) — v1.6.2.1
- ✓ 누적 검색 / 고급 검색 옵션 / 진행바 — v1.5.9
- ✓ JSON Schema (device/command-group) + command YAML meta: 블록 + DeviceSpec.module_meta — GSD v1.6.3 (2026-05-15)
- ✓ WIZ550 DeviceSpec YAML 3개 (WIZ550SR/S2E/WEB) + device.wiz550.schema.json + validate 라우팅 — Validated in Phase 05 (2026-05-18)

### Active

- [ ] WIZ550SR 검색·설정 지원 (UDP 6550, XOR 암호화, 바이너리 프로토콜)
- [ ] WIZ550S2E 검색·설정 지원 (232B 구조체)
- [ ] WIZ550WEB 검색·설정 지원 (133B 구조체)
- [ ] WIZ550 FW 업로드 (TFTP 방식 — 로컬 TFTP 서버 + op_code 0xD1)

## Current Milestone: v1.6.3 WIZ550SR/S2E/WEB 장치 지원

**Goal:** WIZ550SR / WIZ550S2E / WIZ550WEB 세 장치를 검색·설정·FW업로드할 수 있도록 통합하여 공개 릴리즈한다.

**Target features:**
- WIZ550MSGHandler.py (UDP 6550 + XOR 암호화 + op_code 처리)
- WIZ550Profile.py (162B/232B/133B 구조체 파싱·빌드)
- specs/devices/ YAML 3개 (WIZ550SR, WIZ550S2E, WIZ550WEB)
- main_gui.py 통합 (검색·설정·Apply·공장초기화 라우팅)
- FW 업로드 TFTP (로컬 서버 구동 + 장치에 업로드 패킷 전송)

### Out of Scope

- 웹 UI — 설계 미정, 우선순위 낮음
- Qt6 마이그레이션 — 현재 PyQt5 유지
- 다중 장비 일괄 명령 — 아이디어 수준

## Context

- **Tech stack**: Python 3.x + PyQt5, pyinstaller 패키징, Windows 주 타깃
- **장치 프로토콜**: 텍스트 커맨드(WIZ5xxSR 계열) / 바이너리(WIZ1x0SR 계열) 두 갈래
- **DeviceSpec**: `specs/devices/*.yaml` — 장치별 커맨드셋·UI 위젯·범위 정의
- **refactored/**: 독립 저장소 — 차세대 PyQt5 아키텍처 병렬 개발 중
- **코드 규모**: `main_gui.py` ~7014줄, 루트 .py 27개, terminal/ 서브패키지

## Constraints

- **Tech**: Python + PyQt5 유지 (Qt6 불가)
- **Protocol**: WIZnet 독자 UDP 프로토콜 — 하위 호환 필수
- **Build**: `build.ps1`만 허용, pyinstaller 직접 호출 금지
- **Signing**: 자체 서명 인증서 `wiznet_codesign.pfx` (DigiCert 타임스탬프)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| DeviceSpec YAML 기반 프로파일 | 장치별 하드코딩 제거, 신규 장치 추가 용이 | ✓ Good (v1.6.2.1 완료) |
| WIZMSGHandler.run() 직접 호출 제거 | QThread 설계 위반 수정, _fw_send_cmd() 추출 | ✓ Good (c715255) |
| main_gui.py 줄번호 맵 폐기 | stale 원인 — Grep으로 즉시 확인 원칙 | ✓ Good (2026-05-12) |
| GSD 도입 (.planning/) | STATE.md 강제 읽기로 전파 문제 해결 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-15 — GSD v1.6.3 완료 (Schema+Meta+Loader), WIZ550SR 마일스톤 시작*
