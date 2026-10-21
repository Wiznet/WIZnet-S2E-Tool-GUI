# WIZ550 시리즈 FW 소스 조사 — 설정 프로토콜 (UDP 6550, 바이너리)

> 목적: 설정툴 개발자가 FW 레벨 질문에 바로 답하도록, 공개 저장소 4종의 소스를 읽고 정리한 문서.
> 조사일: 2026-10-20. 코드는 읽기만 했다(실행·빌드·수정 없음). 담당자 발언·실기기 측정은 쓰지 않았다.
> 기존 정리 `research/2026-06-02-wiz550-series-characteristics.md` 를 출발점으로 삼아 **소스로 검증·보완**했다.
> 기존 문서와 같은 내용은 반복하지 않고, 달라진 곳은 §0 에 모았다.

## 표기

- `[소스](커밋)` = 해당 커밋의 소스에서 직접 읽은 사실. `[추정]` = 소스에서 추론했으나 실행·실측으로 확인하지 않음. "미확인" = 근거 없음.
- 인용 형식 `저장소약어:파일:줄`. 약어와 경로 접두는 아래와 같다 (Boot 는 `*_Boot/src/`).

| 약어 | 저장소 | 기준 커밋 | App 경로 접두 |
| --- | --- | --- | --- |
| SR | `Wiznet/WIZ550SR` | `698108d` | `WIZ550SR_App/src/` |
| S2E | `Wiznet/WIZ550S2E` | `26b52e2` | `WIZ550S2E_App/src/` |
| MB | `Wiznet/WIZ550S2E-Modbus` | `c987337` | `WIZ550S2E_App/src/` |
| WEB | `Wiznet/WIZ550web` | `fd7e323` | `WIZ550web_Firmware/WIZ550web_HW_Rev1.0/WIZ550web_App/src/` (Rev1.1 은 `Rev1.1`; 달라지는 줄만 따로 적음) |
| 툴 | 이 저장소 (develop `4cfa9b3`) | — | 루트 |

---

## 0. 먼저 읽을 것 — 기존 기록과 달라진 점·핵심 발견

| # | 내용 | 근거 |
| --- | --- | --- |
| A | **S2E 는 v1.2.0 부터 짝수 minor 도 MQTT 필드(70B)가 있다 → 구조체 232B.** 기존 기록의 "S2E base 162B(+MQTT)" 와 툴의 "minor 홀수=MQTT, 짝수=Modbus" 판별은 S2E v1.2.x 에서 틀린다. 162B 는 v1.1.5 이하와 S2E **Boot** 뿐이다. | [소스](S2E `v1.2.0`) S2E:Configuration/ConfigData.h:113-117, 같은 커밋 common.h MINOR=2. 162B Boot: S2E_Boot:Configuration/ConfigData.h(options 에 mqtt 없음) |
| B | **UDP SET 에는 값 검증이 전혀 없다.** 수신 구조체를 통째로 `memcpy` 해 저장한다(MAC·module_type·packet_size 포함). 범위·길이 검사는 AT 명령 경로에만 있다. | [소스](SR `698108d`) SR:Configuration/ConfigMessage.c:209 |
| C | **S2E 의 `baud_table` 은 AT 명령 검증에만 쓰인다.** UDP SET 으로 온 baud 는 표 확인 없이 `Chip_UART_SetBaud` 로 간다. "표 밖이면 115200 fallback" 은 SR/WEB 에만 해당. | [소스](S2E `26b52e2`) S2E:PlatformHandler/uartHandler.c:55, S2E:ATcmd/atcmd.c:829-831 |
| D | flow_control dead field 재확인: SR·WEB 은 `switch(serial->parity)`, S2E·MB 는 `switch(serial->flow_control)`. 주의: parity=Odd(1) 이 곧 RTS/CTS 를 켠다. | §4.2 |
| E | SR 의 UDP 1460(FIND/IMIN/SETT) 코드는 존재하나 `WIZ1x0SR_CFGTOOL` 이 주석 처리돼 **기본 빌드에서 컴파일되지 않는다.** | [소스](SR `698108d`) SR:common.h:25 |
| F | 비밀번호 검사는 `strcmp(set_pw, pw_setting)` 이고 `set_pw_len` 은 4종 모두 **사용되지 않는다.** 10자 비밀번호는 NUL 이 없어 비교가 옆 필드로 번진다. | §2.5 |
| G | 기존 기록이 SR `state` 근거로 든 `ConfigMessage.c:463,606` 은 6550 경로가 아니다(463 은 설정 소켓 상태, 606 은 비활성 1460 코드). 실제 쓰기는 `S2E.c:657,659,677,689,698`. | [소스](SR) |

---

## 1. 저장소별 기준 커밋·버전·Boot/App 구조

### 1.1 기준점

| 저장소 | HEAD(마스터) | 최신 태그 | App 버전(common.h) | Boot 버전(common.h) | 비고 |
| --- | --- | --- | --- | --- | --- |
| SR | `698108d` 2020-06-08 "Fix" | `1.2.2`(v 없음) = `698108d` | 1.2.2 (`SR:common.h:7-9`) | 101.0.0 (`SR_Boot:common.h:5-7`) | 이전 태그 v1.0.0~v1.2.1. 브랜치 develop 있음 |
| S2E | `26b52e2` 2025-01-02 "Add watchdog" | `v1.3.0` (`75e3344`, 2018-06-08). HEAD 는 v1.3.0 뒤 17커밋 | **1.3.1** (`S2E:common.h:10-12`), `WATCHDOG` 플래그 `S2E:common.h:26` | 101.0.1 (`S2E_Boot:common.h:5-7`) | 태그 `v1.2.2` 의 common.h 는 1.2.1 (태그·버전 불일치). 마지막 App 소스 변경이 2025-01-02 |
| MB | `c987337` 2022-01-07 = 태그 `v1.4.1` | `v1.4.1` (v1.4.0 = 2018-07-17) | 1.4.1 (`MB:common.h:10-12`), `WATCHDOG` 있음 | 101.0.1 | S2E v1.1.x 계통에서 갈라진 별도 저장소(MQTT 없음). 첫 릴리스 2018-07-17 |
| WEB | `fd7e323` 2018-03-23 "Update README.md" | `v2.0.2` (`2d9fd56`, 2018-01-25) | Rev1.0 App **1.1.2**, Rev1.1 App **2.0.1** (`WEB:util/common.h:337-339`) | 101.0.0 (Rev1.0·1.1 모두) | 태그 v2.0.2 의 Rev1.1 common.h 도 2.0.1 (태그·버전 불일치). README: 펌웨어 갱신은 HW Rev1.1/1.2 만 |

[소스] 위 값은 각 커밋의 `git log`, `git for-each-ref refs/tags`, `common.h` 의 `MAJOR_VER/MINOR_VER/MAINTENANCE_VER`.

### 1.2 Boot / App 구조

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 별도 이미지 | 저장소마다 `*_Boot` 와 `*_App` 두 프로젝트. 같은 6550 설정 프로토콜을 **둘 다** 처리한다 | `SR_Boot:main.c:174-186`(Boot 루프에서 `do_udp_config`) |
| Boot 버전 규칙 | Boot 는 `MAJOR_VER=101` 로 고정 → 응답 `fw_ver[0]=101` | 4종 모두 `*_Boot:common.h:5` |
| ">100 = Boot" 규칙 | **툴 쪽 관례일 뿐 FW 어디에도 `fw_ver[0] > 100` 비교가 없다**(4개 저장소 grep). Boot 가 101 로 자신을 알리는 것에 기댄 약속 | [소스] `git grep "fw_ver\[0\] *(>\|<\|==)"` 결과 없음 |
| App 위치 | SR: `APP_BASE 0x08007000`(Boot 28KB). S2E/MB: `APP_BASE 0x6000` | `SR_Boot:common.h:17`, `S2E:common.h:23` |
| Boot → App 점프 | SR: 부트핀 값(SR=1, WEB=0)과 TFTP 결과가 FAIL 이 아니고 App 영역이 비어 있지 않으면 점프 | `SR_Boot:main.c:151-171` |
| App 갱신 흐름 | App 이 `FIRMWARE_UPLOAD_INIT(0xD1)` 수신 → 비밀번호 확인 → TFTP 서버 정보를 저장소 0번에 쓰고 재부팅 → Boot 가 TFTP 로 받고 `FIRMWARE_UPLOAD_DONE(0xD2)` 응답 | `SR:ConfigMessage.c:241-311, 313-350`; `SR_Boot:main.c:60-97` |
| 버전 덮어쓰기 | App 은 로드·SET 마다 `fw_ver` 를 자기 버전으로 덮어쓴다(저장된 값 무시) | `SR:ConfigData.c:98-100`, `SR:ConfigMessage.c:210-212` |
| 구조체 크기가 Boot/App 에서 다르다 | S2E Boot = 162B, S2E App(≥1.2) = 232B. MB Boot = 162B, MB App = 164B. SR·WEB 은 Boot=App | `S2E_Boot:ConfigData.h`(options 에 mqtt 없음), `MB_Boot:ConfigData.h`(modbus 없음) |

[소스] 요약: Boot/App 구분은 `fw_ver[0]` 값(101)으로만 드러난다. Boot 상태의 S2E/MB 는 **162B 로 응답**하므로 길이로 구조를 판별하는 툴 로직(§6 M1)은 Boot 에서는 맞게 동작한다.

---

## 2. 프로토콜

### 2.1 소켓·방향

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 포트 | UDP **6550** (`REMOTE_CLIENT_PORT`). 장치가 이 포트로 bind | `SR:ConfigMessage.h:8`, `SR:ConfigMessage.c:519` |
| 검색 방식 | 요청이 `unicast=0` 이면 장치는 **255.255.255.255:(요청 송신 포트)** 로 브로드캐스트 응답, `unicast!=0` 이면 요청 송신 IP:포트로 응답 | `SR:ConfigMessage.c:131-134, 176-179, 233-236` |
| 6550 외 포트 | UDP 1460(`REMOTE_CLIENT_PORT_EX`)은 SR 에만 있고 **기본 빌드에서 비활성**(§2.7) | `SR:ConfigMessage.h:9`, `SR:common.h:25` |
| 처리 방식 | 메인 루프가 한 번에 헤더 1개만 읽는다(`recvfrom` 7B). 인식 못 한 패킷의 나머지는 비우지 않는다(비우는 코드는 `#if 0`) | `SR:ConfigMessage.c:466-498, 500-516` |

### 2.2 패킷 헤더 (7B, 리틀엔디안)

| 오프셋 | 크기 | 필드 | 값 / 의미 |
| --- | --- | --- | --- |
| 0 | 1 | stx | `0xA5` |
| 1 | 1 | valid | bit7=1 이면 페이로드 XOR 암호화, 키 = `valid & 0x7F` |
| 2 | 1 | unicast | 0=응답을 브로드캐스트, 그 외=요청자에게 유니캐스트 |
| 3 | 1 | op_code[0] | 상위 니블로 분기: `A_` 검색, `B0` GET, `C0` SET, `D_` FW, `E0` 리셋, `F0` 공장초기화 |
| 4 | 1 | op_code[1] | 요청 `0xAA`, 응답 `0x55` (요청이 `0xAA` 가 아니면 무시) |
| 5-6 | 2 | length | 페이로드 바이트 수, LE |

[소스](SR) `SR:ConfigMessage.h:32-38`(구조체), `SR:ConfigMessage.c:470-476`(STX·REQUEST 검사와 분기). 응답 헤더는 요청 헤더를 그대로 재사용하고 `length`·`op_code[1]` 만 바꾼다(`SR:ConfigMessage.c:115-116, 161-162`).
암호화는 헤더를 제외한 페이로드 전체를 같은 키로 XOR(`SR:ConfigMessage.c:14-28`). 응답에도 요청의 `valid` 를 그대로 써서 암호화한다.

### 2.3 op_code 표

| op | 이름 | 요청 페이로드 | 응답 페이로드 | 비밀번호 |
| --- | --- | --- | --- | --- |
| `A0`+x | 검색 | `A1` ALL: 0B, `A2` 제품코드: 7B, `A3` MAC 범위: 12B, `A4` 별칭: 33B, `A5` 혼합: 52B | `product_code[3]+fw_ver[3]+mac[6]` = **12B** | 불필요 |
| `B0` | GET_INFO | `dst_mac[6]` = 6B | `src_mac[6]` + `S2E_Packet` | 불필요 |
| `C0` | SET_INFO | `dst_mac[6]+set_pw_len[1]+set_pw[16]` + `S2E_Packet` | `src_mac[6]` + `S2E_Packet`(저장된 값) | **필요** |
| `D1` | FW 업로드 시작 | `dst_mac[6]+pw_len[1]+pw[16]+server_ip[4]+server_port[2]+file_name[50]` = 79B | `src_mac[6]` | 필요 |
| `D2` | FW 업로드 완료 | (Boot 가 TFTP 후 스스로 송신) | `src_mac[6]` | — |
| `E0` | 리셋 | `dst_mac[6]+pw_len[1]+pw[16]` = 23B | `src_mac[6]` 후 즉시 재부팅 | 필요 |
| `F0` | 공장초기화 | 23B(E0 과 동일) | `src_mac[6]` 후 재부팅 | 필요 |

[소스](SR) 구조체 `SR:ConfigMessage.h:40-131`, 처리 `SR:ConfigMessage.c:30-454`. 검색 응답의 총 크기는 7+12=19B.
검색 필터: ALL 은 무조건 응답, 제품코드(`A2`)는 `module_type` 3바이트 비교, MAC 범위(`A3`)는 **바이트별 독립 비교**(`SR:ConfigMessage.c:69-82`, 사전식 범위가 아님), 별칭(`A4`)은 `strlen(alias)` 만큼만 `module_name` 과 비교(접두 일치, `SR:ConfigMessage.c:94`), 혼합(`A5`)은 조건을 읽기만 하고 **필터링하지 않는다**(`SR:ConfigMessage.c:99-108`).

### 2.4 요청·응답 크기 (바이트, 7B 헤더 별도)

| 기종(구조체) | S2E_Packet | GET 응답 페이로드 | SET 요청 페이로드 | SET 응답 페이로드 |
| --- | --- | --- | --- | --- |
| SR, S2E ≤1.1.x, S2E/MB **Boot** | 162 | 168 | 185 | 168 |
| S2E App ≥1.2.0 (MQTT) | 232 | 238 | 255 | 238 |
| MB App (Modbus) | 164 | 170 | 187 | 170 |
| WEB | 133 | 139 | 156 | 139 |

[소스] 합산은 구조체 정의에서 계산(`SR:ConfigData.h:111-120`, `S2E:ConfigData.h:97-127`, `MB:ConfigData.h:99-123`, `WEB:ConfigData.h:95-118`). 실제 패킷 캡처로 확인한 값은 아니다.

### 2.5 비밀번호 검사

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 비교 방식 | `strcmp(set_info.set_pw, s2e_packet->options.pw_setting)`. 틀리면 **응답 없이 무시**한다(오류 응답 없음) | `SR:ConfigMessage.c:205-206`; S2E/MB `:212`; WEB Rev1.0 `:213` / Rev1.1 `:214` |
| 사용되는 필드 | `pw_setting` 만. `pw_connect`(TCP 데이터 접속용)는 UDP 검사에 쓰이지 않는다 | 같은 줄 |
| `set_pw_len` | 4종 모두 **어디서도 읽지 않는다**(선언만) | [소스] 4개 저장소 grep: 선언 외 사용 0건 |
| 길이 | 요청 `set_pw[16]`, 장치 `pw_setting[10]`. 10자를 꽉 채우면 NUL 이 없어 `strcmp` 가 인접 필드까지 읽는다 | `SR:ConfigData.h:98-99`(pw_setting 다음이 pw_connect), `WEB:ConfigData.h:96-99`(다음이 dhcp_use) |
| 인접 필드 영향 | SR/S2E/MB: 10자 비밀번호의 비교가 `pw_connect[0]` 와 이어진다 → 요청 쪽은 NUL 이므로 `pw_connect` 가 비어 있지 않으면 **불일치**. WEB: 다음 바이트가 `dhcp_use` 라 DHCP 사용 중이면(1) 불일치 | [추정] 구조체가 packed·연속이라는 레이아웃 근거(`__attribute__((packed))`, `SR:ConfigData.h:109`) |
| 출하값 | `pw_setting`="WIZnet", SR/S2E/MB 의 `pw_connect`="WIZnet" | `SR:ConfigData.c:71-72`, `WEB:ConfigData.c:57` |
| 평문 노출 | GET 응답에 `pw_setting`·`pw_connect` 가 그대로 실린다(7비트 XOR 키는 헤더 `valid` 에 있음). 비밀번호 없이 읽을 수 있다 | `SR:ConfigMessage.c:164-168` |

### 2.6 SET 의 저장·재부팅 순서

[소스](SR) 수신 → MAC 비교 → 비밀번호 비교 → 구조체 **통째 복사** → `fw_ver` 3바이트만 자기 값으로 덮어쓰기 → **저장** → 응답 송신 → `NVIC_SystemReset()`.
(`SR:ConfigMessage.c:202-238`; S2E/MB `:209-245`; WEB Rev1.0 `:210-246`.) 저장이 응답보다 먼저이므로 **응답 타임아웃이 곧 미저장은 아니다.** 응답 송신 직후 지연 없이 재부팅한다(SR 의 FW 업로드 경로만 `delay_ms(50)` 있음, `SR:ConfigMessage.c:307`).
`save_*` 는 반환값이 없고 S2E 의 `write_eeprom` 결과(1/0)는 호출부에서 무시한다 → 저장 실패는 응답으로 알 수 없다(`S2E:ConfigData.c:103-112`, `S2E:PlatformHandler/eepromHandler.c:41-66`).
저장 위치: SR 은 EEPROM/플래시 2번 블록(0=FW 업로드 정보, 1=설정), S2E/MB 는 내장 EEPROM 0x200(설정)·0x40(업로드 정보) (`S2E:PlatformHandler/eepromHandler.c:12-23`).
`save_*` 는 `network_info[0].state`(런타임 값)를 0 으로 바꿔 저장한 뒤 복원한다 — SR/S2E/MB 만 해당(`SR:ConfigData.c:103-112`), WEB 은 state 필드가 없다.

### 2.7 SR 의 UDP 1460 (WIZ1x0SR 호환) 코드

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 내용 | `FIND`→`IMIN`, `SETT`→`SETC`, `FIRS`(fw_ver[0]=82 로 표시하고 재부팅) 163B 텍스트 헤더 구조(`CONFIG_MSG`) | `SR:ConfigMessage.h:145-192`, `SR:ConfigMessage.c:524-750` |
| 활성 조건 | `#if defined(WIZ1x0SR_CFGTOOL)` — 정의가 `//#define WIZ1x0SR_CFGTOOL` 로 **주석 처리** | `SR:common.h:25`, `SR_Boot:common.h:20` |
| 빌드 설정 | 이클립스 프로젝트·makefile 에 `-D` 정의 없음 | [소스] `git grep CFGTOOL -- *.cproject *.project makefile*` 결과 없음 |
| 다른 저장소 | S2E/MB/WEB 에는 이 코드 자체가 없다 | [소스] diff |
| 배포 바이너리 | 배포된 바이너리가 이 옵션으로 빌드됐는지는 **미확인**(§7 Q5) | — |

---

## 3. 설정 구조체

### 3.1 `S2E_Packet` 레이아웃 (packed, 리틀엔디안)

SR / S2E / MB 공통 기본부 (162B). `전체 오프셋` 은 `packet_size` 포함 기준이며 툴의 `SR_FORMAT` 주석과 일치한다.

| 오프셋 | 크기 | 필드 | 길이·범위 (FW 주석·코드 기준) |
| --- | --- | --- | --- |
| 0 | 2 | packet_size | 출하 시 `sizeof(S2E_Packet)`, 이후 SET 으로 덮어쓰임 |
| 2 | 3 | module_type | SR `02 00 00`, S2E·MB `00 00 00`, WEB `01 02 00` |
| 5 | 25 | module_name | `NAME_LEN` 25, NUL 종료 가정 |
| 30 | 3 | fw_ver | Major.Minor.Maint, Boot 는 101 |
| 33 | 6 | mac | |
| 39 / 43 / 47 | 4×3 | local_ip / gateway / subnet | |
| 51 | 1 | working_mode | 0 Client, 1 Server, 2 Mixed, 3 UDP, (S2E ≥1.2 만) 4 MQTT |
| 52 | 1 | state | 런타임: 0 끊김, 1 연결, 2 UDP |
| 53 | 4 | remote_ip | |
| 57 / 59 | 2+2 | local_port / remote_port | uint16 |
| 61 / 63 | 2+2 | inactivity / reconnection | uint16 |
| 65 | 2 | packing_time | 0~65535 |
| 67 | 1 | packing_size | 0~255 |
| 68 | 4 | packing_delimiter | |
| 72 | 1 | packing_delimiter_length | 주석 0~4 |
| 73 | 1 | packing_data_appendix | 주석 0~2 |
| 74 | 4 | baud_rate | uint32 (정수 bps 그대로) |
| 78 | 1 | data_bits | 7/8/9 (enum `word_len`) |
| 79 | 1 | parity | 0 none, 1 odd, 2 even |
| 80 | 1 | stop_bits | 1, 2 |
| 81 | 1 | flow_control | 0 none, 1 rts_cts, 2 rs422, 3 rs485 |
| 82 | 10 | pw_setting | `PASS_LEN` 10 |
| 92 | 10 | pw_connect | |
| 102 | 1 | dhcp_use | |
| 103 | 1 | dns_use | |
| 104 | 4 | dns_server_ip | |
| 108 | 50 | dns_domain_name | |
| 158 | 1 | serial_command | AT 모드 사용 여부 |
| 159 | 3 | serial_trigger | 출하 `2B 2B 2B` ("+++") |
| **합계** | **162** | | |

[소스] `SR:ConfigData.h:65-120`. 확장부:

| 기종 | 추가 필드 (오프셋) | 합계 | 근거 |
| --- | --- | --- | --- |
| S2E ≥1.2.0 | mqtt_user[10] 162, mqtt_pw[10] 172, mqtt_publish_topic[25] 182, mqtt_subscribe_topic[25] 207 | **232** | `S2E:ConfigData.h:20-24, 113-117` |
| MB | modbus_use 162, modbus_mode 163 (`RTU=0`, `ASCII=1`) | **164** | `MB:ConfigData.h:21-22, 112-113` |
| WEB | (아래 3.2) | **133** | `WEB:ConfigData.h:109-118` |

### 3.2 WEB (133B) — 소켓·패킹·pw_connect·serial_command 가 없다

| 오프셋 | 크기 | 필드 |
| --- | --- | --- |
| 0~50 | 51 | packet_size, module_type, module_name, fw_ver, mac, local_ip, gateway, subnet (SR 과 동일) |
| 51 | 4+1+1+1+1 | serial_info[0]: baud, data_bits, parity, stop_bits, flow_control |
| 59 | 8 | serial_info[1] (같은 형식) |
| 67 | 10 | pw_setting |
| 77 / 78 | 1 / 1 | dhcp_use / dns_use |
| 79 / 83 | 4 / 50 | dns_server_ip / dns_domain_name |

[소스](WEB `fd7e323`) `network_info`(`WEB:ConfigData.h:115`), `pw_connect`(`:97`), `serial_command`·`serial_trigger`(`:105-106`)가 주석 처리. `serial_info[2]` `:116`. Rev1.0·Rev1.1 의 options 구조는 동일(diff).

### 3.3 출하값(`set_..._to_factory_value`) 차이

| 항목 | SR | S2E / MB | WEB | 근거 |
| --- | --- | --- | --- | --- |
| module_name | "WIZ550SR" | "WIZ550S2E"(MB 도 동일) | "WIZ550web" | `SR:ConfigData.c:28`, `S2E:ConfigData.c:26`, `WEB:ConfigData.c:27` |
| IP / GW | 192.168.77.100 / .77.1 | 192.168.11.100 / .11.1 | 192.168.11.100 / .11.1 | 같은 파일 |
| working_mode | 1 Server | 1 Server | (없음) | |
| 시리얼 | 115200, 8, N, 1, flow 0 | 같음 | 포트 2개 모두 같음 | |
| 설정 초기화 조건(부팅 시) | `packet_size == 0 \|\| 0xFFFF` → 출하값 | `packet_size == 0` 일 때만 | `packet_size == 0 \|\| 0xFFFF` | `SR:ConfigData.c:90`, `S2E:ConfigData.c:93`, `WEB:ConfigData.c:71` |

[소스] 위 마지막 줄의 함의: **SET 으로 `packet_size` 를 0 으로 보내면 다음 부팅에서 출하값으로 되돌아간다**(SR/WEB 은 0xFFFF 도). 툴은 GET 값을 되돌려 보내므로 평소엔 안전하나, 값을 임의 조립하면 위험하다.
공장초기화(`F0`)는 MAC 을 유지한다 — 출하 함수가 MAC 을 쓰지 않는다(`SR:ConfigData.c:22-84`). SR 에는 MAC 이 비정상(00:08:DC 아님)이면 UART 로 MAC 을 입력받는 `check_mac_address()` 가 있고 Boot 가 시작 시 호출한다(`SR:ConfigData.c:229-258`, `SR_Boot:main.c:137`; S2E/MB/WEB 의 ConfigData.h 에는 선언이 없음).

### 3.4 SET 시 검증 유무

| 항목 | UDP 6550 SET | AT 명령 경로(참고) | 근거 |
| --- | --- | --- | --- |
| 수신 길이 | `SO_REMAINSIZE == header.length` 만 확인. **구조체 크기와는 비교하지 않는다** | — | `SR:ConfigMessage.c:193-195` |
| 필드 범위·열거값 | **없음**(통째 복사) | 있음: word 5~8, stop 1~2, flow 0~3, baud 는 표 일치 | `SR:ATcmd/atcmd.c:836-925`(CHK_DGT_RANGE) |
| 문자열 길이 | **없음** | MQTT user/pw/topic 은 `len > LEN-1` 거부 | `S2E:ATcmd/atcmd.c:1115-1118, 1211, 1262` |
| 적용 시점 | 저장 후 재부팅하면 부팅 시 `serial_info_init` 이 열거값을 보정(잘못된 data_bits/stop/parity 는 8/1/none 으로 되돌리고 구조체에도 반영) | | `S2E:uartHandler.c:65-68, 79-82, 96-99`, `SR:uartHandler.c:441-469` |
| 잘못된 baud | **SR/WEB**: 하드웨어는 115200 로 동작하지만 구조체의 baud 값은 **그대로 남아** GET 이 잘못된 값을 돌려준다. **S2E/MB**: 표 검사 없이 분주비 계산(48MHz/(16×baud)) | `SR:uartHandler.c:437-438`(구조체에 되쓰지 않음), `S2E:uartHandler.c:55`, `lpc_chip_11exx/src/uart_11xx.c:139-153`, `S2E` board_sysinit.c:113-117(48MHz) |
| baud=0 | SR/WEB: SR 은 표에 11번째 칸이 0 이라 값 0 이 "유효"로 통과(10개만 초기화된 `baud_table[11]`, `SR:uartHandler.c:72-83`). S2E/MB: `clkin / (baudrate*16)` 에서 0 나눗셈 | [추정] 실제 동작(트랩 여부)은 미확인 |
| 허용 working_mode | 범위 밖이면 SR 은 `s2e_sockclose_process` 의 `default: break` 로 **데이터 소켓을 열지 않는다** | | `SR:S2E/S2E.c:417-434` |

---

## 4. 기종 간 차이와 알려진 FW 버그

### 4.1 기능·필드 비교

| 항목 | SR | S2E (≥1.2) | MB | WEB |
| --- | --- | --- | --- | --- |
| 구조체 크기 | 162 | 232 | 164 | 133 |
| working_mode | 0~3 | 0~4 (4=MQTT) | 0~3 | 없음 |
| 시리얼 포트 | 1 | 1 | 1 | **2** (`serial_info[2]`) |
| pw_connect / serial_command / trigger | 있음 | 있음 | 있음 | **없음** |
| MQTT / Modbus 필드 | 없음 | MQTT 70B | Modbus 2B | 없음 |
| data_bits | 8 고정에 가까움(§4.3) | 7 / 8 | 7 / 8 | 8 / **9** |
| flow_control | **dead**(parity 가 결정) | 정상: none/RTS-CTS/RS422/RS485 | 정상(S2E 와 동일 코드) | **dead**(parity 가 결정) |
| baud 표 | 600~230400 (10값) | 300~230400 (11값, AT 에서만 검사) | 같음 | 600~230400 |
| 칩 / UART | STM32F103 | NXP LPC11E (UART0) | 같음 | STM32F103 ×2 |
| 저장소 | EEPROM(또는 플래시) | 내장 EEPROM | 같음 | EEPROM(블록 크기는 Rev별 조건 정의, 미정리) |
| 6550 처리부 | 공통 | SR 과 거의 동일, `check_mac_address`·`delay_ms(50)`·1460 코드 없음 | S2E 와 **동일 파일** | SR 과 동일(1460 없음, Rev1.1 은 공장초기화 시 IO 초기화 추가 `ConfigMessage.c:438`) |

[소스] 위 항목별 근거: 구조체 §3, 처리부 diff(`ConfigMessage.c` 를 SR↔S2E↔MB↔WEB 로 비교), 칩은 `S2E:PlatformHandler/uartHandler.c`(LPC `Chip_UART_*`)와 `SR:PlatformHandler/uartHandler.c`(STM32 `USART_Init`).
`MB:ConfigMessage.c` 와 `S2E:ConfigMessage.c` 는 **바이트 단위로 동일**하다(diff 결과 없음) — S2E 와 MB 는 `product_code`(`00 00 00`)도 같아 **검색 응답만으로 구분되지 않는다**(`S2E:ConfigData.c:23-25`, MB 동일).

### 4.2 flow_control dead field — 재확인

| 기종 | 코드 | 근거 |
| --- | --- | --- |
| SR | `switch(serial->parity) { case flow_none: ... case flow_rts_cts: ... }` — 주석은 "Flow Control" | [소스](SR `698108d`) `SR:PlatformHandler/uartHandler.c:471-482` (switch 줄 472) |
| WEB Rev1.0 | 동일 오타, case 도 none/rts_cts 두 가지뿐 | [소스](WEB `fd7e323`) `WEB(Rev1.0):PlatformHandler/uartHandler.c:244-255` (switch 줄 245) |
| WEB Rev1.1 | 동일 | `WEB(Rev1.1):PlatformHandler/uartHandler.c:245` |
| S2E | `switch(serial->flow_control)`, `flow_none/rts_cts/rs422/rs485` 4분기 모두 실제 레지스터 설정 | [소스](S2E `26b52e2`) `S2E:PlatformHandler/uartHandler.c:105-126` (rs422 `:114-119`, rs485 `:120-123`) |
| MB | S2E 와 동일 줄 | [소스](MB `c987337`) `MB:PlatformHandler/uartHandler.c:105` (diff 로 S2E 와 동일 확인) |

- **다른 소비처 추적 결과**: `flow_control` 을 읽는 곳은 SR 에서 AT 명령(`SR:ATcmd/atcmd.c:876,922`, `cmdrun.c:873,887`)과 비활성 1460 코드(`SR:ConfigMessage.c:590,695`)뿐이고 하드웨어 설정에는 쓰이지 않는다. WEB 은 추가로 웹 페이지 처리(`WEB:PlatformHandler/userHandler.c:302,530,824,998`)가 값을 읽고 쓰지만 하드웨어 반영은 같은 `serial_info_init` 이다. 매크로(`#define`)로 이를 우회하는 코드는 없었다.
- **효과(숫자 일치에 의한 부작용)**: `parity_odd=1` 과 `flow_rts_cts=1` 의 값이 같아서, SR/WEB 에서는 **parity=Odd 로 설정하면 하드웨어 RTS/CTS 가 켜지고**, parity=None/Even 이면 꺼진다. (Even=2 는 `default` 로 가서 꺼짐.) `flow_control` 값 자체는 저장·GET 만 된다.
- AT 명령은 SR 에서도 flow 를 0~3 으로 받아들인다(`SR:ATcmd/atcmd.c:876`) — 값이 dead 임을 알려 주지 않는다.

### 4.3 data_bits / 7비트 / 9비트

| 기종 | 동작 | 근거 |
| --- | --- | --- |
| SR | `DATA7BIT_ENABLE 0` 이라 7비트 전용 코드 제외. 워드 길이는 기본 8bit이고, `data_bits==8 && parity!=none` 이면 9bit 프레임(8+패리티). 그 외(7, 9 포함)는 8bit 프레임 | [소스] `SR:PlatformHandler/uartHandler.h:23`, `SR:uartHandler.c:484-488` |
| SR 의 7 + 패리티 | `data_bits=7, parity≠none` 이면 워드 길이 8bit + 패리티 사용 → STM32 USART 에서 8bit 프레임에 패리티를 켜면 데이터는 7bit | [추정] STM32 USART 의 M 비트 동작 지식 기반, 소스에는 7/8 구분 코드 없음 |
| S2E / MB | 7·8 지원, 그 외는 8 로 보정 | [소스] `S2E:uartHandler.c:58-69` |
| WEB | 8·9 지원(`word_len9 → USART_WordLength_9b`), 7 은 `default` 로 8 로 보정 | [소스] `WEB:PlatformHandler/uartHandler.c:200-211` (9bit `:204-206`) |

### 4.4 BR(baud) 상한 재확인

| 기종 | 소스상 범위 | 근거 | 비고 |
| --- | --- | --- | --- |
| SR | **600~230400** (300·460800 없음) | [소스] `SR:uartHandler.c:72-83` 표, 사용 `:429-438` | 표 밖 값은 하드웨어를 115200 으로 두되 **저장값은 그대로** |
| WEB | **600~230400** | [소스] `WEB:uartHandler.c:19-30`(Rev1.0·1.1 동일), 사용 `:188-197` | 같은 방식. `atcmd.c:54` 는 `extern uint32_t baud_table[11]` 로 선언돼 정의(10칸)와 불일치 → AT 루프가 표 밖 1칸을 읽음(`WEB(Rev1.1):ATcmd/atcmd.c:54`, 영향 미확인) |
| S2E | **300~230400**은 **AT 명령 경로에서만** 강제 | [소스] 표 `S2E:uartHandler.c:17-29`, AT 검사 `S2E:ATcmd/atcmd.c:829-831,879-881`. UDP 경로 `S2E:uartHandler.c:55` 는 표를 쓰지 않음 | "표 밖 값 → fallback" 은 S2E 에 없다(§6 M5). 460800 은 분주비가 6 으로 계산됨(48MHz/16/460800=6.5→6, 약 8% 오차) [추정] |
| MB | S2E 와 같음 | `MB:atcmd.c:810-812, 860-862`, `MB:uartHandler.c:17` | |

→ 우리 기록 "SR/WEB 600~230400(300 제외), S2E 300~230400" 은 SR/WEB 은 **소스로 확인**, S2E 는 **AT 경로에 한해** 확인(UDP SET 으로는 강제되지 않음).

---

## 5. 길이 보호·고정 크기

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 구조 | 모든 필드 고정 크기(바이너리 packed 구조체). 가변 길이 필드 없음. 문자열은 고정 배열 | §3 |
| 길이 확인 | `SO_REMAINSIZE(수신 잔여) == header.length` 만 확인. 이후 `recvfrom` 은 **로컬 구조체의 `sizeof`** 만큼만 읽는다 | `SR:ConfigMessage.c:148-152, 193-197` |
| 복호화 범위 | 복호화는 **`header.length`(=len) 만큼** 로컬 변수에 XOR 한다 → 길이가 구조체보다 크면 스택을 넘겨 쓴다 | [소스] `SR:ConfigMessage.c:154-155, 199-200`. 로컬 `get_info` 는 6B, `set_info` 는 185B(SR). 암호화 비트가 켜진 경우에 해당 |
| 짧게 보낼 때 | 길이가 짧으면(예: 232B 장치에 164B 본문) `recvfrom` 이 읽은 만큼만 채우고 나머지 `set_info` 는 **초기화되지 않은 스택 값** → 그대로 설정에 복사·저장됨 | [소스] `SR:ConfigMessage.c:187, 209`(`set_info` 초기화 없음) / [추정] 쓰레기 값 내용 |
| 크기 판별 | 응답 헤더 `length` = `6 + sizeof(S2E_Packet)` 이며 FW 가 계산해 채운다(`SR:ConfigMessage.c:161`). `packet_size` 필드는 저장값이라 **신뢰도가 낮다**(SET 이 그대로 덮어쓰고 S2E 는 0 일 때만 재초기화, `S2E:ConfigData.c:93`) | [소스] |
| 문자열 NUL | `pw_setting`·`module_name` 등 배열 끝 NUL 이 보장되지 않는다(10자/25자를 꽉 채우면 NUL 없음). `strcmp` 가 인접 필드로 넘어감(§2.5) | [소스] |
| 최대 패킷 | 최대 SET 요청 7+255=262B(S2E). UDP/소켓 버퍼 한도와의 관계는 미확인 | — |

---

## 6. 툴 구현과 FW 소스의 어긋남

대조 파일: `WIZ550Profile.py`, `WIZ550MSGHandler.py`, `specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml`.
**일치 확인된 것**(어긋남 아님): 헤더 7B·LE 길이·XOR 범위·op_code 값·`0xAA/0x55`·SR 162B/WEB 133B 필드 오프셋 전부·S2E 확장 오프셋(162/172/182/207, 162/163)·`module_type` 3종·SET/RESET 페이로드(6+1+16(+…))·FW 업로드 79B 페이로드·포트 6550·Boot 판별 `fw_ver[0]>100`(관례)·SR/WEB baud 선택지·SR/WEB flow 선택지(dead 취급)·WEB data_bits 읽기 전용.

| # | 항목 | 툴 (근거) | FW 소스 (근거) | 영향 |
| --- | --- | --- | --- | --- |
| M1 | **S2E 구조 판별 규칙** | `len≥232 AND minor 홀수 → MQTT`, `len≥164 AND minor 짝수 → Modbus` (`WIZ550Profile.py:391, 403`; `WIZ550S2E.yaml:44` 주석 "MQTT FW(fw_ver[1] 홀수)") | S2E **v1.2.x(짝수)도 232B + MQTT**(`S2E`@`v1.2.0`:`ConfigData.h:113-117`, common.h MINOR=2). Modbus 는 별도 저장소의 v1.4.x(`MB:common.h:11`) | v1.2.x S2E 가 'modbus' 로 오분류 → `build_s2e` 가 164B 본문 생성 → 장치는 255B 구조체를 기대해 **뒤 68B 가 초기화 안 된 스택값으로 저장**(§5) [추정] |
| M2 | **MQTT 선택 시 길이 강제 전환** | `working_mode==4` 면 variant 를 'mqtt'(232B)로 바꿔 전송 (`main_gui.py:4786-4787`). `WIZ550S2E.yaml:50` 은 S2E 전 변형에 "MQTT" 선택지 노출 | MB·S2E≤1.1.x·Boot 에는 MQTT 필드/상수가 없다(`MB:ConfigData.h` 에 `#define MQTT` 없음). 본문이 구조체보다 길면 복호화가 로컬 변수를 넘어 씀(`SR:ConfigMessage.c:199-200`) | MB/구버전/Boot 장치에서 사용자가 MQTT 를 고르면 **스택 오버런 가능** [소스+추정]. 최소한 MB 에는 MQTT 선택을 막아야 함 |
| M3 | **config 길이를 `packet_size` 로 취함** | `config_len = payload[6..7]`, `system_info = payload[6:6+config_len]` (`WIZ550MSGHandler.py:284, 291`); 주석 "Java MSB 버그 우회" | 헤더 `length`(리틀엔디안, FW 가 `sizeof(reply)` 로 채움 `SR:ConfigMessage.c:161`)가 권위. `packet_size` 는 저장값(출하 시 `sizeof`, SET 으로 덮어쓰임, S2E 는 0 일 때만 재초기화 `S2E:ConfigData.c:93`) | FW 업그레이드·수동 SET 으로 `packet_size` 가 낡으면 길이 오판 → M1 과 같은 경로 [추정]. FW 헤더 length 는 정상이므로 Java 우회가 필요한 이유가 FW 쪽에는 없다 |
| M4 | **S2E flow_control 선택지** | `{0 None, 1 RTS/CTS}` 만 (`WIZ550S2E.yaml:104-106`), 주석은 "0=None,1=RTS/CTS,2=RS422,3=RS485" | S2E/MB 는 RS422(2)·RS485(3)를 **실제로 설정**(`S2E:uartHandler.c:114-123`). SR/WEB 과 달리 정상 필드 | S2E 사용자가 RS422/485 를 설정 불가. 장치에 2/3 가 저장돼 있으면 콤보가 표시 못 함 |
| M5 | **S2E baud 주석·근거** | "baud_table… 460800 은 table 에 없음 → 전송 시 fallback", 근거 파일명 `uartHandler_wiz550s2e.c` (`WIZ550S2E.yaml:62-64`) | 표는 AT 경로 전용, UDP 경로는 표 검사·fallback 없음(`S2E:uartHandler.c:55`). 파일명은 `S2E:PlatformHandler/uartHandler.c` | 선택지(300~230400) 자체는 합리적이나 "fallback" 근거는 S2E 에서 사실이 아님. 문서 오류 |
| M6 | **SR data_bits 8 고정** | 읽기 전용 "8-bit" (`WIZ550SR.yaml:89`, 주석 `:22`) | `data_bits=7`+패리티 시 8bit 워드+패리티 → 하드웨어상 7bit 가능 [추정] (`SR:uartHandler.c:484-488`) | 장치에 7 이 저장돼 있어도 UI 는 8 로 표기 |
| M7 | **WEB data_bits** | 읽기 전용 "8-bit", 주석 "word_len7 case 없음 → 8 fallback = 8 고정" (`WIZ550WEB.yaml:62, 115`) | `word_len9` 는 9bit 로 처리(`WEB:uartHandler.c:204-206`). 8 고정이 아니라 8/9 | 장치에 9 가 있으면 UI 는 8 로 표시하나 읽기 전용이라 값은 그대로 되돌려 전송 |
| M8 | **비밀번호 길이** | `_str_to_cstr(pw, 10)` 로 10자까지 허용(`WIZ550Profile.py:268-269, 454-455`), 로그인 비밀번호는 16자까지 전송(`WIZ550MSGHandler.py:145`) | 10자는 NUL 이 없어 `strcmp` 가 인접 필드로 번짐 (§2.5). 장치 `pw_setting` 은 9자까지가 안전. `set_pw_len` 은 사용 안 됨 | 10자 비밀번호면 SET/리셋이 거부될 수 있음 [추정]. UI 제한 여부는 미확인 |
| M9 | **SET 실패 구분 불가** | 응답 없으면 "타임아웃" (`WIZ550MSGHandler.py:591-592`) | 비밀번호·MAC 불일치는 **응답 없이 무시**(`SR:ConfigMessage.c:202-206`). 저장은 응답보다 먼저(`:215`→`:236`) | 비밀번호 오류/패킷 손실/저장 성공 후 응답 손실을 구분 못 함. 확인하려면 GET 재조회 필요 |
| (문서) | 주석의 파일·줄 인용 | `WIZ550S2E.yaml:64,80` 의 `uartHandler_wiz550s2e.c` 는 존재하지 않는 파일명 | 실제 `S2E:PlatformHandler/uartHandler.c`. 또 `research/2026-06-02-…` 의 `ConfigMessage.c:463,606`(state 근거)은 6550 경로가 아님(§0 G) | 코드 영향 없음 |

> 어긋남 집계: **코드 동작에 영향 9건(M1~M9)** + 문서 인용 오류 1건. 이 중 M1·M2·M3 은 같은 뿌리(S2E 구조 크기를 FW 버전 규칙과 packet_size 로 추정)이다.
> 검증 방법: 모두 소스 대조이며 실기기 확인은 하지 않았다. M1 은 S2E v1.2.x 장치로 GET 한 뒤 `s2e_variant` 값을 로그로 보면 바로 확인된다(`main_gui.py:4822` 가 출력).

---

## 7. 담당자에게 물어볼 것 (소스만으로 결론이 안 나는 것, 5건)

| # | 질문 | 근거 위치 | 선택지 / 결과에 따른 조치 |
| --- | --- | --- | --- |
| Q1 | 현장에 **S2E v1.2.x(MQTT 232B)** 가 실제로 있는가? 있다면 구조 크기를 알릴 공식 방법은 무엇인가(헤더 length 가 맞는가)? | `S2E`@`v1.2.0:ConfigData.h:113-117`, `S2E:ConfigMessage.c:168`(응답 길이) | (a) 헤더 length 로 판별(툴 변경) (b) minor 홀짝 규칙 유지(v1.2.x 는 비지원 선언) (c) module_type 분리 계획 확인 |
| Q2 | S2E/MB 가 **UDP SET 으로 받은 baud 가 300~230400 밖**이면 어떻게 되는가(460800 등)? 상한이 하드웨어 사양인가, AT 검사만의 제약인가? | `S2E:uartHandler.c:55`, `lpc_chip_11exx/src/uart_11xx.c:139-153`, `S2E:ATcmd/atcmd.c:829-831` | (a) 230400 상한 확정 → 툴 현행 유지 (b) 더 높은 값 허용 → 선택지 확장 검토 |
| Q3 | SET 응답은 **저장 성공을 보증**하는가? `write_eeprom` 실패(반환 0) 시 어떻게 되는가? | `S2E:ConfigData.c:103-112`, `S2E:ConfigMessage.c:222→241→245`, `S2E:eepromHandler.c:41-66` | (a) 응답=저장 성공으로 간주 (b) 툴이 SET 후 GET 으로 재확인 |
| Q4 | SR 에서 `data_bits=7`+패리티 설정은 **의도된 7E1/7O1 인가** 아니면 미지원인가? (DATA7BIT 가 꺼져 있는데 8bit 워드+패리티 경로가 남음) | `SR:uartHandler.h:23`, `SR:uartHandler.c:484-488` | (a) 미지원 → 8 고정 유지 (b) 지원 → data_bits 콤보 활성 |
| Q5 | **배포 바이너리**가 어떤 옵션으로 빌드됐는가? 특히 SR 의 `WIZ1x0SR_CFGTOOL`(UDP 1460) 활성 여부와, S2E/MB 의 `WATCHDOG` | `SR:common.h:25`, `S2E:common.h:26` | (a) 비활성이면 1460 은 무시 (b) 활성 제품이 있으면 SR 이 WIZ1x0SR 처럼도 응답하므로 검색에서 중복 가능성 점검 |

---

## 8. 이 조사에서 확인하지 못한 것

- 실기기 동작·패킷 캡처 — 전부 소스 읽기이며 크기 계산은 구조체 정의에서 한 계산.
- `SO_REMAINSIZE` 의 정확한 의미(ioLibrary UDP 수신 시 헤더 8B 포함 여부)는 라이브러리 소스를 따로 보지 않았다. FW 가 `header.length` 와 비교하는 점은 사실이나 반환값 정의는 미확인.
- 배포 바이너리의 빌드 옵션, HW Rev1.2 WEB 펌웨어(저장소에는 Rev1.0/1.1 폴더만 있음).
- WEB 웹 페이지(HTTP) 설정 경로의 입력 검증(`userHandler.c`)은 읽지 않았다.
- AT 명령 전체 범위표는 시리얼 항목(word/stop/flow/baud)과 MQTT 길이만 확인했다.
