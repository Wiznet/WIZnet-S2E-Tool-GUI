# 테스트 실행 가이드

> 자동화 테스트(pytest)와 수동 검증 스크립트, 장치 시뮬레이터 사용법을 설명합니다.  
> 개발 환경이 없다면 [SETUP_DEV-ko.md](SETUP_DEV-ko.md)를 먼저 진행하세요.

---

## 두 종류의 테스트

이 프로젝트에는 성격이 다른 두 종류의 테스트가 있습니다.

| 종류 | 위치 | 실행 방식 |
|------|------|----------|
| **자동화 테스트** | `tests/` 폴더 | `pytest`로 자동 수집·실행 |
| **수동 검증 스크립트** | 프로젝트 루트의 `test_*.py` | `python` 으로 개별 실행 |

> **중요:** `pytest.ini`에 `testpaths = tests`로 설정되어 있어, **`pytest`는 `tests/` 폴더만 수집합니다.** 루트에 있는 `test_*.py`들은 pytest가 자동으로 실행하지 않습니다 (의도된 설계).

---

## 1. 자동화 테스트 (pytest)

### 실행

```powershell
uv run pytest
```

`tests/` 폴더의 모든 테스트가 수집·실행됩니다. 현재 대부분 WIZ550 계열 프로토콜·스펙 검증입니다.

### tests/ 폴더 구성

| 파일 | 검증 대상 |
|------|----------|
| `conftest.py` | 공통 픽스처 (WIZ550 더미 패킷, `qapp` QApplication 등) |
| `test_wiz550_handler.py` | `WIZ550MSGHandler` — 헤더 상수, 패킷 길이, XOR 암복호화, 검색 파싱 |
| `test_wiz550_profile.py` | `WIZ550Profile` — SR/S2E/WEB 바이너리 파싱·빌드 왕복 |
| `test_wiz550_spec.py` | DeviceSpec YAML + `validate_schemas.py` 검증 |
| `test_wiz550_fw.py` | 펌웨어 업로드 패킷·TFTP |
| `test_wiz550_gui.py` | GUI 통합 (검색 결과 병합, 패널 구성 등) |

> 일부 테스트는 `@pytest.mark.xfail` 또는 `skipif`로 표시되어 있습니다. 구현 진행 중이거나 장비가 필요한 항목입니다.

### 특정 파일/테스트만 실행

```powershell
uv run pytest tests/test_wiz550_handler.py          # 한 파일만
uv run pytest tests/test_wiz550_handler.py -v        # 자세한 출력
uv run pytest -k xor                                  # 이름에 'xor' 포함된 테스트만
```

---

## 2. YAML 스키마 검증

DeviceSpec YAML이 올바른 구조인지 검증합니다. 새 장치를 추가했다면 반드시 실행하세요.

```powershell
uv run python validate_schemas.py
```

- `specs/devices/*.yaml`, `specs/commands/*.yaml`을 각각 JSON Schema로 검증
- 종료 코드 `0` = 통과, `1` = 실패

자세한 내용은 [ADD_DEVICE-ko.md](ADD_DEVICE-ko.md) 참고.

---

## 3. 수동 검증 스크립트 (루트)

장비 없이 로직을 빠르게 확인하는 독립 실행 스크립트입니다. pytest로 수집되지 않으므로 직접 실행합니다.

| 스크립트 | 용도 | 실행 |
|---------|------|------|
| `test_wiz107sr.py` | WIZ107SR/108SR 커맨드셋·파싱 검증 (가상 패킷) | `uv run python test_wiz107sr.py` |
| `test_cmdset_design.py` | CMDSET 설계(타입·상속·호환성) 검증 | `uv run python test_cmdset_design.py` |
| `test_decimal_yaml.py` | 검색 설정 YAML의 Decimal 처리 검증 | `uv run python test_decimal_yaml.py` |
| `test_table_border.py` | PyQt5 테이블 헤더 경계선 시각 비교 (GUI 창) | `uv run python test_table_border.py` |

---

## 4. UDP 장치 시뮬레이터

실제 장비 없이 검색·수신 로직을 테스트하는 송신/수신 도구 쌍입니다.

### 송신 (장치 모의)

`localhost:50002`로 장치 응답 패킷을 보냅니다.

```powershell
uv run python test_udp_sender.py            # 기본 시나리오 (멀티패킷)
uv run python test_udp_sender.py 2          # 시나리오 번호 지정
uv run python test_udp_sender.py all        # 전체 시나리오
```

시나리오: 단일 패킷 / 멀티패킷+MQTT / 중복 패킷 / DoS 패킷.

### 수신 (검증)

`localhost:50002`에서 수신하여 패킷 수·크기·MD5·중복/DoS 필터를 검증합니다.

```powershell
uv run python test_udp_receiver.py                  # 기본
uv run python test_udp_receiver.py --timeout 1      # 타임아웃 지정
uv run python test_udp_receiver.py --log recv.log   # 로그 파일 저장
```

> 보통 수신기를 먼저 실행해 대기시킨 뒤, 다른 터미널에서 송신기를 실행합니다.

---

## 요약

| 목적 | 명령 |
|------|------|
| 자동화 테스트 전체 | `uv run pytest` |
| 특정 테스트 | `uv run pytest -k <키워드>` |
| YAML 스키마 검증 | `uv run python validate_schemas.py` |
| 장치별 로직 검증 | `uv run python test_<대상>.py` |
| UDP 시뮬레이션 | `test_udp_receiver.py` + `test_udp_sender.py` |

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | [개발자 가이드 (시작 순서)](DEV_GUIDE-ko.md) |
| 1 | [환경 세팅 & 실행](SETUP_DEV-ko.md) |
| 2 | [코드 구조](ARCHITECTURE-ko.md) |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | [새 장치 추가](ADD_DEVICE-ko.md) |
| 5 | **테스트 — 현재 문서** |
| 6 | [빌드 & 배포](RELEASE-ko.md) |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
