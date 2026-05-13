# Project Milestones: WIZnet S2E Tool GUI

[Entries in reverse chronological order - newest first]

## v1.6.2.1 DeviceSpec + FW from Git + Terminal (Shipped: 2026-05-11)

**Delivered:** DeviceSpec YAML 기반 장치 프로파일 리팩토링 + GitHub FW 다운로드 + 터미널 패널

**Phases completed:** — (pre-GSD)

**Key accomplishments:**
- DeviceSpec YAML (`specs/devices/*.yaml`) 기반 UI 빌드 시스템 전환
- GitHub Releases에서 FW 선택·다운로드·업로드 다이얼로그 (`fw_git_dialog.py`)
- 터미널 유틸리티 패널 신규 (`terminal/` 6모듈)
- WIZMSGHandler.run() 직접 호출 제거 (QThread 설계 위반 수정)
- Wiki v1.6.2.1 업데이트 완료

**Git range:** `e419528` → `78bd3f9`

**What's next:** v1.7 — 유지보수 + 구조 개선 + 신규 기능

---

## v1.6.1 WIZ1x0SR 바이너리 프로토콜 (Shipped: 2026-04-03)

**Delivered:** WIZ100/105/110SR 바이너리 프로토콜 완전 지원

**Key accomplishments:**
- FIND/IMIN/SETT/SETC 바이너리 프로토콜 (UDP:1460)
- WIZ1x0Profile.py + WIZ1x0MSGHandler.py 신규
- 전용 3탭 설정 UI
- 실 장치 테스트 프로토콜 버그 8건 수정

---

## v1.6.0.1 DDNS hotfix (Shipped: 2026-04-01)

**Delivered:** DDNS 서버 목록 수정 + PPPoE 버그 수정

---

## v1.6.0 WIZ107SR/108SR 전면 지원 (Shipped: 2026-03-26)

**Delivered:** WIZ107SR/108SR 장치 완전 지원 + 107_108_config 독립 툴

**Key accomplishments:**
- cmd_107sr 42개 커맨드
- DDNS/PPPoE 탭 전용 UI
- 107_108_config/ 독립 모듈

---

## v1.5.9 검색 개선 (Shipped: 2026-03-09)

**Delivered:** 누적 검색 + 고급 검색 옵션 + 진행바 개선

---
