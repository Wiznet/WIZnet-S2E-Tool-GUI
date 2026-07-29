# 새 장치 추가하기

> 새로운 WIZnet S2E 장치를 Configuration Tool에 추가하는 방법을 설명합니다.  
> 대부분의 경우 **YAML 파일 하나만 추가하면** 됩니다. 코드 수정은 최소화되도록 설계되어 있습니다.  
> 전체 구조를 먼저 이해하려면 [ARCHITECTURE-ko.md](ARCHITECTURE-ko.md)를 참고하세요.

---

## 핵심 개념

이 프로젝트는 **DeviceSpec YAML** 기반으로 장치를 정의합니다.

```
specs/
├── devices/    ← 장치별 정의 (이 폴더에 새 파일 추가)
├── commands/   ← 여러 장치가 공유하는 커맨드 그룹
└── schema/     ← YAML 구조를 검증하는 JSON Schema
```

새 장치를 추가한다는 것은 대부분 **`specs/devices/<장치명>.yaml` 파일을 만드는 것**입니다.  
장치가 보내는 검색 응답값(MN)을 보고 `device_spec_loader.py`가 자동으로 해당 YAML을 찾아 UI를 구성합니다.

---

## 1단계. command_groups 조합 정하기

새 장치가 어떤 커맨드를 지원하는지에 따라 공유 커맨드 그룹을 조합합니다.

| 그룹 | 내용 |
|------|------|
| `base` | 모든 장치 공통 (MAC, IP, Baud rate 등) — **필수** |
| `retransmit` | TCP 재전송/타임아웃 옵션 |
| `gpio` | User I/O 핀 제어 (WIZ750SR 등) |
| `security` | SSL/TLS, MQTT 보안 |
| `ddns` | DDNS 설정 (WIZ107/108SR) |
| `pppoe` | PPPoE 설정 |
| `modbus` | Modbus 파라미터 |
| `telnet` | Telnet 옵션 |
| `two_port` | 2포트 공통 커맨드 |
| `w55rp20_ext` | W55RP20 계열 확장 (MQTT, SSL 인증서) |
| `w55rp20_two_port` | W55RP20 2채널 전용 |

> `base`는 거의 항상 포함합니다. 나머지는 장치 기능에 맞게 선택합니다.

---

## 2단계. device YAML 작성

`specs/devices/<장치명>.yaml` 파일을 만듭니다. 아래는 실제 `WIZ750SR.yaml`을 단순화한 템플릿입니다.

```yaml
name: WIZ_NEW_DEVICE          # 규범적 장치명 (파일명과 동일하게)
display_name: "WIZ New"       # UI에 표시될 이름
aliases:                      # 장치 MN 응답값 — 자동 감지에 사용
  - "WIZ_NEW_DEVICE"
  - "ALT-NAME"                # 같은 장치의 다른 응답값이 있으면 추가
family: one_port              # one_port | security | two_port | security_two_port
channels: 1                   # 포트 수 (2포트 장치는 2)

command_groups:               # 1단계에서 정한 조합
  - base
  - retransmit

overrides:                    # 장치 특화 값 (선택)
  BR:                         # 예: Baud rate 범위가 다른 경우
    regex: "^([0-9]|1[0-3])$"
    values:
      "0": "300"
      "13": "230400"
  TR:                         # 예: 특정 FW 버전 이상에서만 지원하는 커맨드
    min_version: "1.2.0"

fw_constraints:               # 펌웨어 업로드 설정 (선택)
  upload_supported: true
  config_port: 50001

ui:                           # UI 탭/그룹 구성
  tabs:
    - id: network
      label: "Network"
      groups:
        - device_info
        - ip_mode
        - op_mode
    - id: serial
      label: "Serial"
      groups:
        - serial_info
        - serial_params
        - data_packing
```

### 필수 최상위 키

| 키 | 의미 |
|-----|------|
| `name` | 규범적 장치명. 파일명과 일치시킵니다 |
| `family` | `one_port` / `security` / `two_port` / `security_two_port` 중 하나 — 기능 범위 결정 |
| `channels` | 포트 수 (1 또는 2) |
| `command_groups` | 사용할 커맨드 그룹 목록 |

### 자주 쓰는 선택 키

| 키 | 의미 |
|-----|------|
| `display_name` | UI 표시 이름 |
| `aliases` | 장치 MN 응답값과 매칭 (자동 감지) |
| `overrides` | 커맨드 값(regex/values)이나 `min_version`을 장치별로 변경 |
| `fw_constraints` | 펌웨어 업로드 포트·크기 등 |
| `ui` | 탭·그룹 레이아웃, `widget_overrides`로 위젯별 가시성 제어 |

---

## 3단계. overrides로 장치 특화

같은 커맨드라도 장치마다 값 범위가 다를 수 있습니다. `overrides`에 명시하면 `base` 그룹의 기본값을 덮어씁니다.

- **값 범위 변경** — Baud rate 최대값이 다른 경우 `BR`의 `regex`와 `values`를 재정의
- **FW 버전 게이트** — 특정 펌웨어 이상에서만 지원하는 커맨드는 `min_version` 지정. 장치 FW가 이보다 낮으면 해당 커맨드가 UI에서 자동 제외됩니다

---

## 4단계. 스키마 검증

작성한 YAML이 올바른 구조인지 검증합니다.

```powershell
uv run python validate_schemas.py
```

- `specs/devices/*.yaml` → `device.schema.json` 기준 검증
- `specs/commands/*.yaml` → `command-group.schema.json` 기준 검증
- 여러 그룹에 같은 커맨드 코드가 중복 정의되면 경고

**종료 코드 `0` = 모두 통과**, `1` = 하나 이상 실패.

---

## 5단계. 실행 확인

```powershell
uv run python main_gui.py
```

장치를 검색하면 `aliases`의 MN 값으로 자동 감지되어, 작성한 YAML의 탭 구성대로 UI가 나타납니다.

---

## 코드 수정이 필요한 경우

대부분 YAML만으로 충분하지만, 기존 family로 표현되지 않는 **완전히 새로운 동작**이 필요하면 코드도 손봐야 합니다.

| 파일 | 수정이 필요한 경우 |
|------|------------------|
| `WIZMakeCMD.py` | 장치 타입 분류 리스트(`ONE_PORT_DEV` 등)에 하드코딩된 곳 — 점진적으로 `load_device()` 기반으로 이전 중 |
| `main_gui.py` | 특정 장치 전용 UI 분기 (예: WIZ107/108SR DDNS 탭, W232N/IP20 가시성 제어) |
| `specs/commands/` | 기존 그룹에 없는 **새 커맨드 그룹**이 필요한 경우 신규 YAML 추가 |

> **원칙:** 새 장치가 기존 family(one_port/security/two_port/security_two_port) 중 하나에 속하면, `specs/devices/`에 YAML만 추가해도 `load_device()`가 자동으로 처리합니다.

---

## 커맨드 그룹 YAML 구조 (참고)

`specs/commands/`의 커맨드 그룹을 새로 만들거나 수정할 때 참고하세요. 각 커맨드 블록은 다음 구조입니다.

```yaml
meta:
  id: base
  name: "Base Commands"
  requires: []          # 의존하는 다른 그룹
  conflicts: []         # 함께 쓸 수 없는 그룹

MC:                     # 커맨드 코드
  description: "MAC address"
  regex: "^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$"
  values: {}            # 선택지 매핑 (key → 표시명)
  access: RO            # RO(읽기) / RW(읽기쓰기) / WO(쓰기전용 명령)
  ui:
    tab: network
    group: device_info
    widget: label       # label / combobox / radiogroup / lineedit 등
    label: "MAC Address"
    order: 1
```

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | [개발자 가이드 (시작 순서)](DEV_GUIDE-ko.md) |
| 1 | [환경 세팅 & 실행](SETUP_DEV-ko.md) |
| 2 | [코드 구조](ARCHITECTURE-ko.md) |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | **새 장치 추가 — 현재 문서** |
| 5 | [테스트](TESTING-ko.md) |
| 6 | [빌드 & 배포](RELEASE-ko.md) |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
