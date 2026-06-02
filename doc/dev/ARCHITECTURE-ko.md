# 아키텍처 개요

> 신규 개발자가 코드 구조를 빠르게 파악하기 위한 지도입니다.  
> 구체적인 함수 위치는 줄번호 대신 **함수·클래스 이름으로 Grep** 하세요 (줄번호는 금방 낡습니다).

---

## 한 문장 요약

WIZnet S2E Configuration Tool은 **PyQt5 GUI**로, 네트워크 상의 WIZnet 직렬-이더넷 장치를 **검색 → 설정 조회/변경 → 펌웨어 업로드** 하는 도구입니다. 장치 계열마다 통신 프로토콜이 달라, **3종의 프로토콜 핸들러**와 **YAML 기반 장치 스펙**으로 분기를 처리합니다.

---

## 진입점과 메인 클래스

| 항목 | 위치 |
|------|------|
| 진입점 | `main_gui.py` 의 `if __name__ == "__main__"` |
| 메인 윈도우 | `class WIZWindow(QMainWindow, main_window)` |
| UI 정의 | `gui/wizconfig_gui.ui` (`uic.loadUiType`으로 런타임 로드) |

`WIZWindow`가 거의 모든 것을 오케스트레이션합니다 (`main_gui.py`, 약 7,680줄). 검색·설정·펌웨어 업로드 흐름이 모두 이 클래스의 메서드로 연결됩니다.

> UI 객체 이름이 곧 `self.<이름>` 변수가 됩니다. UI 수정은 [QT_DESIGNER-ko.md](QT_DESIGNER-ko.md) 참고.

---

## 핵심 파일 지도

| 파일 | 역할 |
|------|------|
| `main_gui.py` | 메인 GUI. `WIZWindow` 클래스가 전체 흐름 제어 |
| `WIZMakeCMD.py` | ASCII 커맨드 리스트 생성 (`presearch`/`search`/`setcommand`) |
| `wizcmdset.py` | 커맨드 메타데이터 저장소 + `DeviceStatus` enum |
| `constants.py` | `Opcode`(OP_SEARCHALL/GETCOMMAND/SETCOMMAND/FWUP), `SockState` enum |
| `device_spec_loader.py` | YAML 장치 스펙 로더 (`load_device`, `detect_device`) |
| `WIZMSGHandler.py` | **일반 ASCII** 장치 메시지 처리 QThread |
| `WIZ1x0MSGHandler.py` | **WIZ100/105/110SR 바이너리** 프로토콜 QThread |
| `WIZ550MSGHandler.py` | **WIZ550 계열 XOR 바이너리** 프로토콜 QThread |
| `WIZ1x0Profile.py` | WIZ1x0SR 163바이트 프로필 파싱/빌드 |
| `WIZ550Profile.py` | WIZ550 SR/S2E/WEB 바이너리 프로필 파싱/빌드 |
| `FWUploadThread.py` | 일반 장치 펌웨어 업로드 (ASCII + TFTP 클라이언트) |
| `WIZ550FWUploadThread.py` | WIZ550 펌웨어 업로드 (TFTP 서버 구동) |
| `WIZUDPSock.py` | UDP 소켓 래퍼 |

---

## 코드 길찾기 — 코드 안 읽고 찾기

> `main_gui.py`는 7,680줄, 클래스 하나(`WIZWindow`)입니다. **전부 읽지 마세요.**  
> 아래 규칙으로 필요한 부분만 Grep해서 점프하는 게 정석입니다.

### 함수 네이밍 컨벤션

함수 이름의 접두사·접미사만 보면 역할이 보입니다. "검색 코드 어디?" → `search`로 Grep.

| 패턴 | 역할 | 예시 |
|------|------|------|
| `do_search*` / `search_*` | 장치 검색 시작·처리 | `do_search_normal`, `search_pre`, `search_each_dev` |
| `get_*` | 스레드 응답을 받는 콜백 | `get_search_result`, `get_setting_result` |
| `fill_devinfo_*` | 장치 → 폼 (읽어온 값 표시) | `fill_devinfo_wiz550`, `fill_devinfo_1x0` |
| `fill_setinfo_*` | 폼 → 장치 (보낼 값 수집) | `fill_setinfo_wiz550`, `fill_setinfo_1x0` |
| `apply_*` | 설정 적용(쓰기) 실행 | `apply_wiz550`, `apply_1x0` |
| `event_*` | UI 이벤트 핸들러 (24개) | `event_ip_alloc`, `event_keepalive`, `event_fw_from_git` |
| `cert_*` | 인증서 업로드 관련 | `cert_object_config`, `cert_result` |
| `*_wiz550` / `*_1x0` | 해당 장치 계열 전용 | 접미사로 장치 분기 구분 |

> **활용 예:** "WIZ550 설정 적용이 어떻게 되지?" → `apply_wiz550` Grep → 거기서 시작해 호출되는 함수만 따라가면 됩니다. 7,680줄을 처음부터 읽을 일은 없습니다.

### "이거 하려면 어디?" 빠른 매핑

| 하고 싶은 것 | 고칠 곳 | 코드 읽기 |
|------|--------|:---:|
| 버튼·라벨 글자, 화면 배치 변경 | `gui/wizconfig_gui.ui` (Qt Designer) | 거의 없음 |
| 콤보박스 항목 (Baud rate 등) 변경 | `specs/devices/*.yaml`, `specs/commands/*.yaml` | 없음 |
| 새 장치 지원 추가 | `specs/devices/<장치>.yaml` | 적음 |
| 검색 타이밍·재시도 횟수 | `config/*.yaml` + `device_search_config.py` | 적음 |
| 특정 버튼 눌렀을 때 동작 | `main_gui.py`의 `event_*` 함수 | 해당 함수만 |
| 장치로 보내는 커맨드 내용 | `WIZMakeCMD.py` (`setcommand`/`search`) | 해당 함수만 |
| 빌드·서명·배포 | `build.ps1` ([RELEASE](RELEASE-ko.md)) | 없음 |

### 핵심 데이터가 어디 담기나

상태가 어디 사는지 알면 코드 흐름이 보입니다. 모두 `WIZWindow`의 인스턴스 속성입니다.

| 속성 | 담는 것 |
|------|--------|
| `self.dev_profile` | MAC 주소 → 장치 정보 dict (`_proto` 등 분기 키 포함) |
| `self.mac_list` / `mn_list` / `vr_list` / `st_list` | 검색된 장치들의 MAC / 모델명 / 버전 / 상태 목록 (인덱스로 짝맞춤) |
| `self.curr_dev` / `curr_mac` / `curr_ver` | 현재 선택된 장치의 모델명 / MAC / 버전 |
| `self.detected_list` | 누적 검색 모드에서 유지되는 이전 결과 |
| `self.cmdset` | 현재 장치의 커맨드셋 |

### 2글자 커맨드 코드 사전

코드 곳곳에 나오는 `MC`, `OP` 같은 2글자 코드는 장치 설정 항목입니다. 자주 보는 것:

| 코드 | 의미 | | 코드 | 의미 |
|:---:|------|---|:---:|------|
| `MC` | MAC 주소 | | `BR` | Baud rate |
| `VR` | 펌웨어 버전 | | `DB` | 데이터 비트 |
| `MN` | 모델명 | | `PR` | 패리티 |
| `ST` | 동작 상태 | | `SB` | 스톱 비트 |
| `IM` | IP 할당 방식 (Static/DHCP) | | `FL` | 흐름 제어 |
| `LI` | 로컬 IP | | `OP` | 네트워크 동작 모드 |
| `SM` | 서브넷 마스크 | | `LP` | 로컬 포트 |
| `GW` | 게이트웨이 | | `RH` | 원격 호스트 IP |
| `DS` | DNS 서버 | | `RP` | 원격 포트 |

> 전체 목록과 정의는 `specs/commands/base.yaml`(공통) + 각 그룹 YAML에 있습니다.

---

## 장치 계열별 프로토콜 분기

이 프로젝트의 핵심 복잡도입니다. **장치 계열마다 통신 방식이 다릅니다.**

| 핸들러 | 담당 장치 | 프로토콜 |
|--------|----------|----------|
| `WIZMSGHandler` | WIZ750SR, WIZ752SR, WIZ107/108SR, W7500-S2E 등 | **ASCII 텍스트** 커맨드 (`MC`, `VR`, `OP`...), UDP 50001 / TCP |
| `WIZ1x0MSGHandler` | WIZ100SR, WIZ105SR, WIZ110SR | **바이너리** — UDP 1460 브로드캐스트 → `FIND`/`IMIN` 163바이트 |
| `WIZ550MSGHandler` | WIZ550SR / S2E / WEB | **XOR 암호화 바이너리** — UDP 6550, 7바이트 헤더 + op_code |

분기는 장치 클릭 시점(`dev_clicked` 등)에 장치 프로필의 `_proto` 값으로 결정됩니다. 일반 장치는 `WIZMSGHandler`, WIZ1x0/WIZ550은 전용 핸들러로 라우팅됩니다.

### 일반 ASCII 프로토콜 요약 (`WIZMSGHandler`)

가장 많은 장치가 쓰는 방식입니다 (WIZ750SR, WIZ752SR, WIZ107/108SR, W7500-S2E, W55RP20 계열 등).

- 전송: UDP `50001` (브로드캐스트/유니캐스트) 또는 TCP
- 커맨드: **2글자 ASCII 코드** — `MC`(MAC), `VR`(버전), `MN`(모델명), `OP`(동작 모드), `IM`(IP 할당), `BR`(Baud rate) 등
- 검색: 브로드캐스트 MAC `FF:FF:FF:FF:FF:FF` + 조회 커맨드 묶음 전송 → 장치가 ASCII로 응답
- 설정: `WIZMakeCMD.setcommand()`가 만든 `[['MA','...'],['OP','1'],...]` 리스트를 전송
- 수신 패킷 최대 4096B, 비정상 응답 대비 멀티패킷 수집 상한 200청크
- 커맨드 정의·검증 규칙은 `wizcmdset.py` + `device_spec_loader.py`(YAML)

### WIZ1x0SR 프로토콜 요약 (`WIZ1x0MSGHandler`)

WIZ100SR / WIZ105SR / WIZ110SR 전용 바이너리 프로토콜입니다. 일반 ASCII 방식과 완전히 분리되어 있습니다.

- 전송: UDP 브로드캐스트 `255.255.255.255:1460`(장치 수신), 응답은 PC의 `5001` 포트로 수신
- 검색: `FIND`(4B) → 응답 `IMIN` + 163바이트 바이너리 (총 167B)
- 설정: `SETT` + 163바이트 → 응답 `SETC` + 163바이트 (**즉시 저장 후 리부트**)
- TCP 설정 포트 `1461`, 펌웨어 업로드 포트 `1470` 고정
- 163바이트 프로필 파싱/빌드는 `WIZ1x0Profile.py`
- 검색/설정을 `WIZ1x0Searcher` / `WIZ1x0Setter` 스레드가 담당

### WIZ550 프로토콜 요약 (`WIZ550MSGHandler`)

- 7바이트 헤더: `[STX=0xA5][valid][unicast][op_code][0xAA/0x55][len_LSB][len_MSB]`
- `valid`의 최상위 비트가 1이면 페이로드 XOR 암호화 (key = `valid & 0x7F`)
- op_code: `0xA1`(검색) / `0xB0`(읽기) / `0xC0`(쓰기) / `0xE0`(리셋) / `0xF0`(팩토리 리셋)
- 검색/조회/설정을 각각 `WIZ550Searcher` / `WIZ550Getter` / `WIZ550Setter` 스레드가 담당

---

## 흐름 1: 장치 검색 (3단계)

```
Phase 1  search_pre()
           └ WIZMakeCMD.presearch()로 명령 생성
           └ WIZMSGHandler(QThread) 시작 → 브로드캐스트
                        │ search_result 시그널 (장치 수)
                        ▼
Phase 2  get_search_result()
           └ 핸들러에서 mac_list / mn_list / vr_list / st_list 추출
                        │
                        ▼
Phase 3  get_dev_list() → search_each_dev()
           └ 장치별 상세 정보 조회
             - TCP unicast: 순차 처리
             - UDP broadcast: 장치별 소켓 병렬 처리
                        │ searched_data 시그널 (장치별 응답)
                        ▼
                  getsearch_each_dev()  → 테이블 갱신
```

- `WIZMSGHandler`는 `QThread`이며 `search_result(int)`, `set_result(int)`, `searched_data(bytes)` 시그널을 emit합니다.
- Phase 3의 메인 스레드 블로킹은 **의도된 설계**입니다 (장치별 응답을 원자적으로 처리하기 위함).
- 누적 검색 모드는 이전 결과를 유지하며 재시도 횟수를 추적합니다.

---

## 흐름 2: 설정 적용 (Apply)

### 일반 장치

```
Apply 클릭
  └ 폼 값 수집 (fill_setinfo_*)
  └ WIZMakeCMD.setcommand(mac, idcode, pw, cmd_list, param_list, devname, version)
       → ASCII 커맨드 리스트 반환  예: [['MA','...'],['OP','1'],...]
  └ WIZMSGHandler(OP_SETCOMMAND) 시작
       │ set_result 시그널
       ▼
  get_setting_result()  → 성공/실패 표시
```

### WIZ550 장치

```
Apply 클릭
  └ 비밀번호 입력
  └ 폼 값 수집 (fill_setinfo_wiz550)
  └ WIZ550Profile.build_sr() / build_s2e() / build_web()
       → 바이너리 설정 패킷 생성
  └ WIZ550Setter(QThread) 시작 → 0xC0 쓰기
       │ set_done 시그널
       ▼
  _on_wiz550_set_done()
```

핵심 차이: 일반 장치는 **ASCII 커맨드 리스트**, WIZ550은 **바이너리 프로필 패킷**.

---

## 흐름 3: DeviceSpec 기반 UI 구성

장치를 클릭하면 해당 장치의 YAML 스펙을 읽어 UI를 동적으로 구성합니다.

```
장치 클릭
  └ detect_device(MN값)      → specs/devices/<장치>.yaml 자동 매핑
  └ load_device(name, fw_ver) → DeviceSpec 반환 ((name, fw_ver) 캐싱)
       └ command_groups 병합 (specs/commands/*.yaml)
       └ overrides 적용 + FW 버전별 커맨드 필터링
       └ ui.tabs / widget_overrides → 탭·위젯 구성
```

- 새 장치 추가는 대부분 YAML 한 개로 끝납니다 → [ADD_DEVICE-ko.md](ADD_DEVICE-ko.md)
- `load_device()`는 `(device_name, fw_version)` 튜플로 캐싱하여 같은 조합은 1회만 파싱합니다.

---

## 흐름 4: 펌웨어 업로드

| | 일반 장치 (`FWUploadThread`) | WIZ550 (`WIZ550FWUploadThread`) |
|---|---|---|
| 트리거 | ASCII `FW` 커맨드 → 응답에서 `IP:PORT` 파싱 | `0xD1` FW_UPLOAD_INIT 바이너리 |
| 전송 | TFTP **클라이언트**로 장치에 전송 | 로컬에 TFTP **서버** 구동 (tftpy), 장치가 받아감 |
| 완료 | 상태 응답 확인 | `0xD2` FW_UPLOAD_DONE 수신 대기 |

WIZ550 방식은 TFTP 서버를 띄우므로 방화벽 규칙 추가가 필요합니다.

---

## 보조 스레드 정리

모든 네트워크 작업은 GUI 블로킹을 피하기 위해 `QThread`로 분리됩니다.

| 스레드 | 역할 |
|--------|------|
| `WIZMSGHandler` | 일반 장치 검색/조회/설정 |
| `WIZ1x0Searcher` / `WIZ1x0Setter` | WIZ1x0SR 검색/설정 |
| `WIZ550Searcher` / `WIZ550Getter` / `WIZ550Setter` | WIZ550 검색/조회/설정 |
| `FWUploadThread` / `WIZ550FWUploadThread` | 펌웨어 업로드 |
| `VersionCheckThread` | GitHub Release 최신 버전 확인 |

---

## 개발 문서 목차

> **굵게** 표시된 항목이 지금 보고 있는 문서입니다.

| 단계 | 문서 |
|:---:|------|
| — | [개발자 가이드 (시작 순서)](DEV_GUIDE-ko.md) |
| 1 | [환경 세팅 & 실행](SETUP_DEV-ko.md) |
| 2 | **코드 구조 — 현재 문서** |
| 3 | [UI 수정 (Qt Designer)](QT_DESIGNER-ko.md) |
| 4 | [새 장치 추가](ADD_DEVICE-ko.md) |
| 5 | [테스트](TESTING-ko.md) |
| 6 | [빌드 & 배포](RELEASE-ko.md) |

[← 프로젝트 홈 · 사용자 가이드](../../README.md)
