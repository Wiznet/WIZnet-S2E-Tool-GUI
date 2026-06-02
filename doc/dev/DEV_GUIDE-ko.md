# 개발자 가이드 — 시작 순서

> 소스를 직접 빌드하고 이해하고 싶은 개발자를 위한 길잡이입니다.  
> 아래 순서대로 따라가면 됩니다. 각 단계는 별도 문서로 연결됩니다.

---

## 읽는 순서

| 단계 | 무엇을 하나 | 여기서 얻는 것 | 문서 |
|:---:|------|------|------|
| **1** | 환경 세팅 & 실행 | Python·uv 설치, 소스 받기, GUI 실행까지 | [SETUP_DEV-ko.md](SETUP_DEV-ko.md) |
| **2** | 코드 구조 파악 | 진입점, 장치별 프로토콜 분기, 4대 데이터 흐름 | [ARCHITECTURE-ko.md](ARCHITECTURE-ko.md) |
| **3** | UI 수정 | Qt Designer로 화면 레이아웃 변경 | [QT_DESIGNER-ko.md](QT_DESIGNER-ko.md) |
| **4** | 새 장치 추가 | DeviceSpec YAML로 새 장치 지원 | [ADD_DEVICE-ko.md](ADD_DEVICE-ko.md) |
| **5** | 테스트 | pytest, 스키마 검증, UDP 시뮬레이터 | [TESTING-ko.md](TESTING-ko.md) |
| **6** | 빌드 & 배포 | EXE 빌드, 코드 서명, GitHub Release | [RELEASE-ko.md](RELEASE-ko.md) |

---

## 목적별 빠른 안내

- **일단 돌려보고 싶다** → 1단계만 하면 됩니다.
- **코드를 고치고 싶다** → 1 → 2 순서로. 그다음 고칠 영역에 따라 3(UI) 또는 4(장치).
- **수정한 걸 배포까지 하고 싶다** → 5(테스트) → 6(빌드·배포).

> **필수는 1·2단계**입니다. 3~6은 하려는 작업에 따라 골라 보면 됩니다.

---

## 그 외

- **사용자 매뉴얼**(툴 사용법)은 [README](../../README.md) 상단의 Wiki 링크를 참고하세요. 이 가이드는 *개발*용입니다.
- 이슈 추적은 `TASKS.md`가 단일 진실 소스입니다.

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | **개발자 가이드 (시작 순서) — 현재 문서** |
| 1 | [환경 세팅 & 실행](SETUP_DEV-ko.md) |
| 2 | [코드 구조](ARCHITECTURE-ko.md) |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | [새 장치 추가](ADD_DEVICE-ko.md) |
| 5 | [테스트](TESTING-ko.md) |
| 6 | [빌드 & 배포](RELEASE-ko.md) |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
