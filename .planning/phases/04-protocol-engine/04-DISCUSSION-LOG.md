# Phase 4: Protocol Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 04-protocol-engine
**Areas discussed:** QThread 클래스 분할 방식, Profile 파일 구조, Discovery 필터 전략, WIZ550S2E 가변 구조 처리

---

## QThread 클래스 분할 방식

| Option | Description | Selected |
|--------|-------------|----------|
| A: 3클래스 Searcher/Getter/Setter | Setter가 SetInfo+Reset+FactoryReset 처리 | |
| B: 4클래스 Searcher/Getter/Setter/Resetter | Reset 전용 클래스 분리 | ✓ |
| C: 2클래스 Searcher/Accessor | 가장 단순, Getter/Setter 구분 없음 | |

**User's choice:** B — 4클래스 분리
**Notes:** 처음 선택지 설명이 불충분해 상세 설명을 추가 요청. SetInfo와 Reset을 "쓰기"와 "명령"으로 의미 분리.

---

## Profile 파일 구조

| Option | Description | Selected |
|--------|-------------|----------|
| 단일 파일 WIZ550Profile.py | SR/S2E/WEB 함수 통합, _parse_base_162() 공유 | ✓ |
| 장치별 분리 3파일 + 공통 헬퍼 | WIZ550SRProfile.py / WIZ550S2EProfile.py / WIZ550WEBProfile.py + _wiz550_base.py | |

**User's choice:** 단일 파일 WIZ550Profile.py
**Notes:** SR과 S2E가 기본 162B struct 공유 → 단일 파일이 자연스러운 코드 공유. 처음 설명이 불충분해 상세 비교 요청.

---

## Discovery 필터 전략

| Option | Description | Selected |
|--------|-------------|----------|
| A1 브로드캐스트 + product_code 필터 | DISCOVERY_ALL 후 응답에서 SR/S2E/WEB 선별 | ✓ |
| A2 product_code 검색 (3회 반복) | WIZ550만 정밀 타겟, 패킷 3배 증가 | |

**User's choice:** A1 브로드캐스트 + product_code 필터
**Notes:** 원본 Java 구현과 동일 방식. UDP 포트 6550은 1460과 완전 분리라 기존 핸들러와 충돌 없음.

---

## WIZ550S2E 가변 구조 처리

| Option | Description | Selected |
|--------|-------------|----------|
| fw_ver[1] 홀짝 + 데이터 길이 이중 판별 | 데이터 길이 우선, fw_ver 검증 | ✓ |
| fw_ver[1] 홀짝만 | 단순하지만 트런케이션 오파싱 가능성 | |
| 데이터 길이만 | 가장 단순, 설정 정보 소실 | |

**User's choice:** fw_ver[1] 홀짝 + 데이터 길이 이중 판별
**Notes:** 데이터 길이가 주방어선, fw_ver은 검증용. 두 조건 모두 일치해야 MQTT로 판단.

---

## Claude's Discretion

- 없음 — 모든 영역 사용자가 직접 결정

## Deferred Ideas

- WIZ550 FW 업로드 (TFTP) → Phase 7
- DeviceSpec YAML → Phase 5
- main_gui.py 통합 → Phase 6
