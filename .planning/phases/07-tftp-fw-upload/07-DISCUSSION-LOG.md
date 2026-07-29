# Phase 7: TFTP FW Upload - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 07-tftp-fw-upload
**Areas discussed:** TFTP 서버 방식, 포트 전략, 비밀번호 처리, 코드 배치, 진행 표시

---

## TFTP 서버 방식

| Option | Description | Selected |
|--------|-------------|----------|
| 방식 A — 내장 tftpy 원스텝 | 파일 선택만 → 자동 구동 + 0xD1 전송 | |
| 방식 B — 외부 TFTP 수동 | IP/포트/파일명 입력, 0xD1만 전송 | |
| 방식 C — 둘 다 지원 | 다이얼로그 탭 2개 구조 | ✓ |

**User's choice:** 방식 C — "둘 다 해보는 건 어떨까?"
**Notes:** 처음에 외부 TFTP 프로그램 방식을 제안. Java 원본도 외부 서버 방식이었음을 공유한 후, 두 방식 모두 지원하는 방향으로 결정.

---

## 다이얼로그 UI 레이아웃

| Option | Description | Selected |
|--------|-------------|----------|
| 단일 다이얼로그 + 탭 2개 | 탭1=내장 TFTP, 탭2=수동 | ✓ |
| 메인 창 없이 직접 처리 | 다이얼로그 없이 파일 선택 후 바로 실행 | |

**User's choice:** 탭 구조 다이얼로그 OK
**Notes:** Server IP는 현재 NIC IP 자동 채움.

---

## 포트 69 실패 처리

| Option | Description | Selected |
|--------|-------------|----------|
| 고포트 자동 fallback | 69 실패 시 7069 등 자동 선택 | |
| 오류 메시지 표시 | 관리자 권한 안내 후 중단 | ✓ |

**User's choice:** 실패 시 오류 메시지
**Notes:** fallback 없음. 사용자가 수동 탭으로 전환하거나 외부 TFTP 서버 사용하도록 유도.

---

## 비밀번호 처리

| Option | Description | Selected |
|--------|-------------|----------|
| pw_len=0 고정 | 비밀번호 없는 장치로 간주 | |
| 다이얼로그에 pw 필드 추가 | 선택적 입력, 추후 수정 가능 | ✓ |

**User's choice:** 다이얼로그에 pw 필드 추가
**Notes:** "설정 적용때는 pw 반드시 물어보기는 하던데..." — 확실하지 않아 일단 추가하고 실장치 테스트 후 결정.

---

## 코드 배치

| Option | Description | Selected |
|--------|-------------|----------|
| WIZ550MSGHandler.py에 추가 | 기존 WIZ550 QThread들과 같은 파일 | |
| 별도 WIZ550FWUploadThread.py | FWUploadThread.py 패턴 추종 | ✓ |

**User's choice:** 별도 WIZ550FWUploadThread.py

---

## 진행 표시

| Option | Description | Selected |
|--------|-------------|----------|
| indeterminate 애니메이션 | setRange(0,0), 완료 시 100% 점프 | |
| tftpy 콜백 활용 | completion callback 감지 → 100% | ✓ |

**User's choice:** tftpy 콜백 활용
**Notes:** 전송 중 실시간 % 표시는 어렵지만 완료 감지는 가능.

---

## Claude's Discretion

- 다이얼로그 정확한 위젯 배치
- 0xD2 응답 수신 소켓 구현 방식
- 타임아웃 값
- tftpy 콜백 API 상세 사용법

## Deferred Ideas

- WIZ550 비밀번호 필드 실제 동작 여부 — 실장치 테스트 후 결정
- 포트 69 자동 fallback — 필요 시 향후 추가
