# W55RP20-S2E 펌웨어 소스 (4port 이외 브랜치) — SEGCP 설정 프로토콜 정리 (설정툴 개발자용)

작성: 2026-10-20 · 방법: 공개 저장소를 전체 이력으로 clone 해 읽기만 함(빌드·실행 없음) · 코드·커밋·push 변경 없음.
대상: `https://github.com/WIZnet-ioNIC/W55RP20-S2E` 의 `main`(1포트) · `2Port` · `GreenCS`(3채널 커스텀) · `WIZ145SR`. `4port` 는 이미 정리했으므로 **대조 기준**으로만 쓴다.

**표기**
- 출처 태그: `[소스]` 직접 읽은 것(브랜치@커밋은 근거 열에 이름으로, 커밋은 아래 1절 표) / `[추정]` 읽은 것에서의 추론 / `미확인` 읽지 못했거나 소스만으로 결론 불가.
- 담당자 발언·실기기 측정은 근거로 쓰지 않는다. 다만 우리 기록의 담당자 전언을 소스와 **비교**하는 곳은 "전언" 이라고 명시한다.
- 근거 `브랜치:파일:줄`. 파일 약칭:

| 약칭 | 실제 경로 |
| --- | --- |
| `segcp.c` / `segcp.h` | `port/app/configuration/src/segcp.c` / `.../inc/segcp.h` |
| `common.h` | `port/app/configuration/inc/common.h` |
| `ConfigData.h` | `port/app/configuration/inc/ConfigData.h` |
| `board.h` | `port/app/board/inc/WIZnet_board.h` |
| `uartHandler.h` / `uartHandler.c` | `port/app/platform_handler/inc/` / `.../src/` |
| `seg.c` / `seg.h` | `port/app/serial_to_ethernet/src/seg.c` / `.../inc/seg.h` |
| `SSLInterface.h` | `port/app/mbedtls/inc/SSLInterface.h` |
| `w5x00_spi.c` / `deviceHandler.c` | `port/app/ioLibrary_Driver/src/w5x00_spi.c` / `port/app/platform_handler/src/deviceHandler.c` |
| `CMakeLists.txt` | 저장소 루트 |
| `base.yaml` 등 스펙 | 설정툴 저장소 `specs/commands/*.yaml`, `specs/devices/*.yaml` |

---

## 0. 먼저 볼 것 — 전언과 소스가 다른 점, 핵심 발견

**전언(우리 기록) 대 소스**

| 전언 | 소스 결과 |
| --- | --- |
| main/2Port/GreenCS: 응답 길이 검사 없음 | **맞음.** 세 브랜치 `proc_SEGCP` 에 `CONFIG_BUF_SIZE` 비교가 없다(`grep` 결과 `CONFIG_BUF_SIZE` 는 선언·`uart_get_commandline` 뿐). 4port 의 `SEGCP_REPLY_HEADROOM` 은 세 브랜치 어디에도 없다 `[소스]` |
| main/2Port/GreenCS: 저장 길이 검사 없음 | **부분적으로 틀림.** `DH`(≤19) · `NP`(≤9) · `SP`(≤9) 세 개는 세 브랜치 모두 검사한다(`param_len > sizeof(...)-1`). 검사가 **없는** 것은 원격 호스트(RH/QH/GH), MQTT 7개, 접속 데이터(SD/DD/SE·RD/RF/EE·XD/XF/WE) 다. 3절 |
| 응답 버퍼 2048 | **맞음.** `common.h` CONFIG_BUF_SIZE 2048 (main:49 · 2Port:50 · GreenCS:52) |
| 최악 응답 main ≈1,597 / 2Port ≈1,986(여유 61) / GreenCS ≈2,390 | **일치(오차 -10 ~ +5B).** 우리 계산 1,588~1,596 / 1,976~1,984 / 2,387~2,395. 5절 |

**핵심 발견 (중요도 순)**

1. **128자 원격 호스트가 이웃 필드를 0 으로 지운다.** RH/QH/GH 는 `strcpy` 로 `dns_domain_name[128]` 에 쓰는데 검사가 없어, 128자를 넣으면 NUL 이 칸 밖 1바이트를 덮는다. 이 칸은 구조체 마지막 멤버라 다음 바이트는 이웃 필드의 첫 바이트다: main 은 `network_option.dhcp_use`(→0=Static), 2Port 의 RH 는 `network_connection[1].working_mode`(→0=TCP Client). **툴 스펙은 128자까지 허용한다**(`base.yaml:176`). `[소스]`+구조체 배치 `[추정]`. 3·7절
2. **GreenCS 는 정상 값으로도 응답 버퍼를 넘긴다**(2,387~2,395B > 2,048). 보호가 없어 `gSEGCPREP` 뒤 메모리를 덮는다. 뒤에 무엇이 있는지는 링커 맵이 필요해 미확인. 2Port 는 여유가 64~72B 뿐이다. 5절
3. **오류 하나가 저장 전체를 취소한다** — 4port 와 동일 동작. UDP(설정툴) 모드는 뒤 명령을 계속 처리하고 ER 줄을 싣지 않으며, 오류 비트가 하나라도 서면 `SV`/`RT` 가 실행되지 않는다. 스펙에 길이 상한이 없는 `DH`·`SP`·(IP20/W232N 의) `NP` 가 이 경로로 저장 실패를 만든다. 4·7절
4. **2Port·GreenCS 의 명령표 끝이 NULL 이 아니라 문자열 `"0"`** 이다(main·4port 는 NULL). 표에 없는 명령을 파싱하면 표 밖 메모리를 읽는다. 2Port:segcp.c:57, GreenCS:segcp.c:66. 3절
5. **GreenCS 는 baud 상한이 921600** (표 16개, 1M~8M 없음). 툴 스펙 BR/EB 는 0~19(FW≥1.2.1)라 16~19 를 보내면 거부+저장 취소. main 은 반대로 인덱스 20 까지 받는다. 7절

스펙과 어긋난 점은 7절에 **15건**.

---

## 1. 브랜치별 기준 · 보드 · UART 수

| 브랜치 | 기준 커밋 (HEAD) | segcp.c 마지막 변경 | 보고 버전(VR) | 계통 |
| --- | --- | --- | --- | --- |
| `main` | `e9145de` 2026-06-22 "Readme update" | `261ab82` 2026-02-04 (baud 1M~8M) | 1.2.3 Stable — `common.h:12,17` | 기준선 |
| `2Port` | `78517ea` 2026-05-19 "Sync V1.2.3" | `8350ffa` 2026-02-04 | **1.2.2** (커밋 메시지는 V1.2.3) — `2Port:common.h:12` | main 과 `686f3c6`(2025-11-11)에서 갈라짐, +14커밋 |
| `GreenCS` | `b431688` 2026-09-14 "terminate CH2 socket…" | `b431688` | 1.2.5, 문자열 `1.2.5_GreenCS` — `GreenCS:common.h:12,17`, `GreenCS:segcp.c:346` | main 과 `686f3c6`에서 갈라짐, +21커밋. 2Port 의 후손이 **아니다**(공통 조상 `baf5876` 2026-01-13) |
| `WIZ145SR` | `6627fd6` 2026-09-28 "Offer the whole serial range…" | `6627fd6` | 1.2.3 | **`4port` 의 조상.** `git diff WIZ145SR 4port -- port/app/configuration` 이 비어 있다 = 설정 프로토콜 코드는 4port@716a3b0 과 동일 |
| (기준) `4port` | `716a3b0` 2026-10-19 | `6627fd6` | 1.2.3 | — |

**WIZ145SR 브랜치는 4port 와 SEGCP 가 같다.** 차이는 `mbtimer.c`, `PPPoE.c/.h` 3파일뿐(4port 가 +3커밋: `ff05cfa` `0df81d8` `716a3b0`). 아래 2~6절의 "4port" 열은 WIZ145SR 에도 그대로 적용된다 `[소스]`.

| 브랜치 | 빌드 보드 (`DEVICE_BOARD_NAME`) | `DEVICE_UART_CNT` | 기본 이름(MN) | 근거 |
| --- | --- | --- | --- | --- |
| `main` | 기본 **W55RP20_S2E**, 선택지 WIZ5XXSR_RP / W232N / IP20 / PLATYPUS_S2E | **1** (보드 무관 한 줄) | W55RP20-S2E (W232N→`W232N`, IP20→`IP20`, WIZ5XXSR_RP→`WIZ5XXSR-RP`) | `main:CMakeLists.txt:35-39,44-60`, `main:board.h:35-46` |
| `2Port` | 기본 W55RP20_S2E, 선택지 동일 | **2** | `W55RP20-S2E-2CH` (W232N/IP20 은 자기 이름 그대로) | `2Port:CMakeLists.txt:35-39`, `2Port:board.h:38,45` |
| `GreenCS` | 기본 W55RP20_S2E, 선택지 동일 | **3** | UART 수로 결정: 4→`-4CH`, **3→`W55RP20-S2E-3CH`**, 그 외 `-2CH` | `GreenCS:board.h:45,53-59` |
| `WIZ145SR`/`4port` | 기본 W55RP20_S2E | W55RP20_S2E 만 **4**, 그 외 보드 2 | `W55RP20-S2E-4CH` (임시 — 주석에 원래 `WIZ145SR`) | `4port:board.h:84,100-102` |

- `[소스]` IP20·W232N 은 이 저장소 코드의 **보드 선택지**다(`main:CMakeLists.txt:50-58`). 툴 스펙 `IP20.yaml:16`·`W232N.yaml:16` 의 "이 기종의 FW 소스가 없다"는 이 브랜치군에는 해당하지 않는다. 단 기본 빌드는 W55RP20_S2E 이고, IP20/W232N 을 실제로 어떤 UART 수·핀으로 출하하는지는 `미확인`.
- `[소스]` 2Port 의 핀 정의는 `W55RP20_S2E/W232N/IP20/PLATYPUS` 블록에 DATA1 까지 있고(`2Port:board.h:91-115`), `WIZ5XXSR_RP` 블록(`:61-69`)은 DATA0 만 있다 → WIZ5XXSR_RP 로 2Port 가 빌드되는지 `미확인`.
- 소켓 번호: SEGCP UDP/TCP 소켓이 main 1/2, 2Port·GreenCS 2/3, 4port 5/6 (`common.h:26-27` · `:27-28` · `:37-38`). 모든 브랜치 W5500 소켓 버퍼 2KB×8 (`w5x00_spi.c:233`).

---

## 2. 버퍼 · 응답 길이 보호

| 항목 | main | 2Port | GreenCS | 4port / WIZ145SR (기준) |
| --- | --- | --- | --- | --- |
| `CONFIG_BUF_SIZE` | 2048 (`common.h:49`) | 2048 (`:50`) | 2048 (`:52`) | 2048 (`:62`) |
| `SEGCP_PARAM_MAX` | 256 (`segcp.h:24`) | 256 (`:24`) | 256 (`:24`) | 256 (`:24`) |
| 요청 토큰 상한 `SEGCP_PARAM_MAX*2` | 지역 `param[512]` 에 **무제한 `strcpy`** (`segcp.c:257`) → 513자 이상 토큰이 스택을 덮음 | 같음 (`:272`) | 같음 (`:281`) | 511자 초과 토큰은 UNKNOWN (`:440`) |
| `PW` 토큰 파싱 | `uint8_t i` 루프에 상한 없음 (`:230`) | 같음 (`:245`) | 같음 (`:254`) | `SEGCP_PARAM_MAX-1` 로 제한 |
| 응답 길이 검사 | **없음** | **없음** | **없음** | 명령 처리 **전에** `응답길이 > 2048-256` 이면 IGNORED 로 중단 (`:486`, `segcp.h:29`) |
| 응답 버퍼 초기화 | `memset(trep,0,sizeof(trep))` — `trep` 가 포인터라 **4바이트만** (`:293`) | 같음 (`:308`) | 같음 (`:317`) | `memset(segcp_rep,0,CONFIG_BUF_SIZE)` (`:480`) |
| 수신 길이 한도 | `recvfrom/recv` 길이를 소켓 수신량 그대로 사용 (`:1438`,`:1533`) | 같음 (`:1746`,`:1844`) | 같음 (`:2327`,`:2425`) | `CONFIG_BUF_SIZE-1` 로 자름 (`:2710`) |
| 송신 | `sendto/send(…, 14+strlen(PW)+strlen(본문))` — 길이 검사 없음 (`:1472`,`:1563`) | 같음 (`:1780`,`:1874`) | 같음 (`:2361`,`:2455`) | 같음 |
| 명령표 종결 | NULL `0` (`:71`) | **문자열 `"0"`** (`:57`) | **문자열 `"0"`** (`:66`) | NULL `0` (`:200`) |

- `[소스]` 응답은 `sprintf(trep, …)` 후 `strcat(trep, "\r\n")` 로 `gSEGCPREP[2048]` 에 이어 쓴다(`main:segcp.c:306,661`). 상한이 없으므로 합계가 2048 을 넘으면 `gSEGCPREP` 바로 뒤 메모리를 쓴다. 뒤에 무엇이 있는지는 `미확인`(링커 맵 필요, 질문 1).
- `[소스]` 응답 시작 오프셋은 `10(MA 줄) + 2 + len(PW값) + 2` (`main:segcp.c:1454-1469`)이라 본문에 쓸 수 있는 양은 2048 보다 15~23B 적다. 툴 모델의 `15` 가 이것이다.
- `[소스]` `ioLibrary sendto` 는 길이를 TxMAX(2048) 로 자르고 MTU(1472) 검사는 없다(`ioLibrary_Driver@b981401 Ethernet/socket.c:532-533`, 네 브랜치 모두 같은 서브모듈 커밋 — clone 안은 비어 있어 raw 로 받아 읽음). 1,472B 넘는 UDP 가 W5500 에서 실제로 어떻게 되는지는 `미확인`(칩 동작).
- `[소스]` 2Port·GreenCS 의 `"0"` 종결: `parse_SEGCP` 의 `for (pcmd = tbSEGCPCMD; *pcmd != 0; …)`(`segcp.c:210`) 는 NULL 을 기다리므로 표 마지막 `"0"` 다음 메모리까지 `strncmp` 한다. 표 밖에서 무엇을 만나는지(`tbSEGCPERR` 등 인접 데이터) `미확인`; 요청이 `0` 으로 시작하면 마지막 항목과 일치한다.

---

## 3. 문자열 필드 칸 크기 · SET 길이 검사 (4port 와 다른 점만)

칸 크기는 네 브랜치 **동일**하다 `[소스]` `ConfigData.h:10-17,43,51,69,84,102-120` (4port 만 `pppoe_id/pw[64]` 추가). 다른 것은 **저장 방식**이다.

| 필드 (명령) | 칸 → 최대 글자 | main · 2Port · GreenCS | 4port |
| --- | --- | --- | --- |
| 장치 이름 (DH) | `device_name[20]` → 19 | **검사함** `param_len > sizeof-1` → INVALIDPARAM (main:789, 2Port:929, GreenCS:1058) | `segcp_store_string` (`:370`) |
| 연결 비밀번호 (NP) | `pw_connect[10]` → 9 | **검사함** (main:949, 2Port:1223, GreenCS:1352) | 〃 |
| 검색 비밀번호 (SP) | `pw_search[10]` → 9 | **검사함** (main:960, 2Port:1234, GreenCS:1363) | 〃 |
| 원격 호스트 (RH, 2Port+ QH, GreenCS+ GH) | `dns_domain_name[128]` → 127 | **검사 없음, `strcpy`** (main:822,828 · 2Port:978,984,995,1001 · GreenCS:1107,1113,1124,1130,1853,1859). IPv4 형식이면 그 텍스트도 이 칸에 복사 | 〃 store_string, 128자↑ 거부 |
| MQTT 7개 (QU QP QC PU U0 U1 U2) | 각 `[128]` → 127 | **검사 없음, `sprintf("%s")`** (main:1048-1100 · 2Port:1331-1384 · GreenCS:1460-1513). 채널별 배열이 아니라 `mqtt_option[0]` 하나만 쓴다 | store_string (`__USE_MQTT__` 보드만) |
| 접속 데이터 (SD DD SE · 2Port+ RD RF EE · GreenCS+ XD XF WE) | 각 `[32]` → 31 | **검사 없음, `sprintf`** (main:1318-1334 · 2Port:1602-1642 · GreenCS:1732-1772,2016-2030) | store_string |
| 숫자·열거 | — | 모두 길이·범위 검사 있음(`param_len != 1`, `> 0xFFFF` 등). 단 `atoi/atol` 이라 `abc`→0 으로 통과(예: QK 는 범위 검사 없음, main:1069) | 같음 |

- `[소스]` **넘친 글자가 가는 곳.** `dns_domain_name` 은 `struct __network_connection` 의 마지막 멤버(`ConfigData.h:61-70`)라 128자 입력의 NUL 이 다음 배열 원소의 `working_mode` 또는 `network_option.dhcp_use` 를 0 으로 만든다(구조체가 `packed` 이므로 패딩 없음, `ConfigData.h:61-70,171-186`). MQTT 필드는 다음 필드로, 접속 데이터 `[ch][32]` 는 다음 채널 행으로 넘친다. 범위는 요청 토큰 최대 511자까지(2절 `param[512]`).
- `[추정]` 위 결과로 **응답 최대치는 칸 크기가 아니다.** 검사가 없는 칸에 300자를 넣은 뒤 GET 하면 `%s` 가 300자(+이웃 필드 문자열)를 돌려주므로, 5절의 "정상 값 최악"보다 큰 응답을 값 하나로 만들 수 있다.
- `[소스]` SET 은 응답 줄을 만들지 않는다(OC/LC/PK 성공 시만 `XX\r\n`, main:1170-1172). 문자열 빈 값은 공백 1칸 `SEGCP_NULL=' '`(`segcp.h:102`) 규칙은 4port 와 같다.

---

## 4. 오류 처리 (설정툴 = UDP 모드)

| 동작 | main | 2Port | GreenCS | 4port (기준) |
| --- | --- | --- | --- | --- |
| 오류 뒤 뒤쪽 명령 | **계속 처리**. 단 `opmode==AT_MODE \|\| get_uart_spi_if()` 이면 중단(main:1397) — SPI 인터페이스 모드에서는 UDP 요청도 중단 | 계속. AT 모드만 중단(2Port:1706) | 계속(GreenCS:2287) | 계속(`:2557`) |
| ER 줄 | UDP 에는 안 실림(AT/SPI 모드만 `ERxxx:CMD` 후 중단) | 〃 (AT 만) | 〃 | 〃 |
| 오류 비트가 서면 SV/RT 등 | `segcp_ret_handler` 가 **아무것도 안 함** (main:130) | 2Port:141 | GreenCS:150 | `:286` |
| 이미 쓴 SET | RAM 에만 반영된 채 남음(저장 안 됨) | 〃 | 〃 | 〃 |
| 플래그(ERR/REBOOT/SWITCH/SAVE) 뒤 GET | 그 GET 줄이 **지워진다**(`trep -= 2; *trep = 0`, main:655) | 2Port:755 | GreenCS:882 | `:1071` |
| 표에 없는 명령 | 파싱 UNKNOWN → NOCOMMAND 오류(main:1393) → 위 규칙 전부 적용 | 같음 | 같음 | `:2553` |
| 미구현(표엔 있고 case 없음) | GET→공백 1칸(`default`, main:648-652), SET→**조용히 무시**(NOCOMMAND 주석 처리, main:1385-1387) | 같음 | 같음 | 같음 |
| 헤드룸 초과 | 해당 없음(검사 자체 없음) | 〃 | 〃 | IGNORED 로 중단 + SV/RT 취소 |

- `[소스]` 결과적으로 툴의 `SET… → 확인 GET → SV → RT` 한 요청은 SET 중 **한 건이라도** 거부되면 확인 GET 이 전부 사라지고(`MC` 도 없음) 저장되지 않는다. 4port 와 동일 동작이며 이 브랜치군에서는 길이 초과(DH/NP/SP)와 범위 위반, 표에 없는 명령이 그 원인이다.
- `[소스]` 읽기 전용 명령 SET(`UN ST MA EX SV RT FR PW UI` 등)은 NOTAVAIL 오류(main:1374-1383). 2Port 의 `UI` 는 NOTAVAIL 이지만 **GreenCS 의 `UI`·`EI`·`WI` 는 읽기/쓰기**다(`GreenCS:segcp.c:1812,1820,2033`, 값 `UART_IF_RS485_REVERSE` 이하).
- `[소스]` 2Port·GreenCS 의 `OP`/`AO` SET 은 성공 시 **모든 채널의 소켓을 끊는다**(2Port:790-791 · 801-802, GreenCS 는 CH2 소켓까지 :917-919 · 929-931). 저장 전에 이미 연결이 끊긴다.
- `[소스]` `RT` 는 handler 에서 `device_reboot()`(main:181-187). `FR` 은 `local_port==1` 이면 설정 지우기(main:525).

---

## 5. 최악 응답 크기 검증 (툴 모델 `15 + Σ(4 + 값길이)`)

**방법.** 툴이 보내는 GET 목록(`WIZMakeCMD.py`: `cmd_security_base`(48) + `SO UF` + `SD DD SE` [+ 채널 확장] + `search()` 가 덧붙이는 `PO`(`_modbus_command`, `WIZMakeCMD.py:323-326`))의 각 값을 FW 칸 크기·printf 형식으로 채운다. 모든 목록 명령이 세 브랜치 명령표에 있음을 스크립트로 확인했다 `[소스]`(없으면 NOCOMMAND 로 저장 취소).
가정: MC 17, VR 실제 문자열(5/5/13), MN 19, DH `MN(19)-12hex`=32, RH/QH/GH 127, MQTT 7개 127, 접속 데이터 31, 포트·타이머 5, IP 15, UN 10, ST 7, PS 4, NP/SP 9. 헤더는 `MA 줄 10 + "PW"+값+CRLF`: 검색 비밀번호 공백이면 15, 9자면 23.

| 브랜치 | 질의 명령 수 | 우리 계산 (PW=공백 / PW 9자) | 2048 대비 여유 | 전언 | 차이 |
| --- | --- | --- | --- | --- | --- |
| main | 54 | 1,588 / 1,596 | +460 / +452 | ≈1,597 (여유 450) | -9 / -1 |
| 2Port | 78 | 1,976 / 1,984 | +72 / +64 | ≈1,986 (여유 61) | -10 / -2 |
| GreenCS | 105 | 2,387 / 2,395 | **-339 / -347** | ≈2,390 (343 초과) | -3 / +5 |

- 결론: 전언 3개 모두 소스에서 재현된다(≤0.6%). 남는 오차는 헤더 PW 값 길이와 VR 문자열 가정 정도.
- 4port 의 `1792`(=2048-256) 선과 비교하면 main 은 여유(1,596 < 1,792), 2Port 는 **1,792 를 넘는다**(1,976~1,984), GreenCS 는 2048 도 넘는다. 그러나 이 세 브랜치는 선 자체가 없으니 "넘으면 버린다"가 아니라 "넘으면 덮는다"다.
- `[추정]` 요청 쪽도 같다: 툴 SET+확인 GET 요청은 `gSEGCPREQ[2048]` 에 들어가야 하고(UDP 1,472B 한도 내), 질의 54~105개 × 4B 는 충분히 작다.
- 검증은 GET 형식을 일부러 바꿔(VR 길이·PW 길이) 총합이 움직이는지로 확인했다. 스크립트: 세션 스크래치패드 `calc_reply.py` · `check_tables.py`.

---

## 6. 보드 옵션 차이 — SSL/TLS · MQTT

| 항목 | main · 2Port · GreenCS | 4port / WIZ145SR |
| --- | --- | --- |
| `__USE_S2E_OVER_TLS__` | **모든 보드에서 켜짐** (`board.h:31`) | W55RP20_S2E(=4CH/WIZ145SR 보드)만 꺼짐, 나머지 보드는 켜짐 (`4port:board.h:38-41`) |
| `__USE_MQTT__` | **매크로가 없다.** MQTT 코드·구조체·명령은 항상 빌드된다(세 브랜치에서 `grep` 0건) | 같은 조건으로 W55RP20_S2E 만 꺼짐 (`4port:board.h:40`) |
| 해당 명령 GET | 실제 값(예: `QU`=사용자 이름) 또는 비었으면 공백 1칸 | 꺼진 보드는 `default` → 공백 1칸 |
| `OP` 허용 범위 | 0~6 (`> MQTTS_CLIENT_MODE` 거부, main:688) | 꺼진 보드는 별도 처리(4port 문서 참조) |
| 인증서 업로드 `OC/LC/PK` | `#ifdef __USE_S2E_OVER_TLS__` 안에서 처리(main:1123-1289) | 〃 |

- `[소스]` 따라서 main/2Port/GreenCS 에서 툴 스펙의 `security`·`mqtt` 그룹은 FW 와 맞는 구성이다. 4CH 와 달리 "SSL/MQTT 꺼짐, 공백 1칸" 처리는 필요 없다.
- `[소스]` MQTT 설정은 채널 수와 무관하게 **한 벌**(`mqtt_option[0]`)이다 — 2Port·GreenCS 도 `QU…U2/QO/QK` 가 채널 0 만 가리킨다(2Port:segcp.c:630-693). 채널 1 전용 MQTT 명령은 없다.

---

## 7. 툴 스펙과의 대조 (어긋난 점 15건)

스펙은 설정툴 저장소(`specs/`), FW 는 위 브랜치. 둘 다 근거를 적는다.

| # | 명령 | 스펙 쪽 | FW 쪽 | 영향 |
| --- | --- | --- | --- | --- |
| 1 | RH / QH (GH) 길이 | 128자까지 허용 `base.yaml:176`, `w55rp20_two_port.yaml:82` (4CH 만 127 로 고침) | 칸 `[128]`, 검사 없는 `strcpy`: 128자 입력 → 이웃 필드 첫 바이트를 0 으로 (main:822,828 · 2Port:978-1001 · GreenCS:1107-1130). 3절 | **스펙이 해로운 입력을 허용.** 127 로 낮춰야 함 |
| 2 | DH | 상한 없음 `ddns.yaml:85-88` (`regex: ""`), 네 기종 override 없음 | 19자 초과 → INVALIDPARAM (main:789 · 2Port:929 · GreenCS:1058) | 20자 이상 입력 시 **저장 전체 취소** |
| 3 | SP | 상한 없음 `base.yaml:459`, 네 기종 override 없음 | 9자 초과 → INVALIDPARAM (main:960 · 2Port:1234 · GreenCS:1363) | 〃 |
| 4 | NP | `W55RP20-S2E.yaml:85`, `-2CH.yaml:34` 에는 9자 override 있음. **`IP20.yaml`·`W232N.yaml` 에는 없음** (override 는 BR·OP 뿐, `IP20.yaml:29-`, `W232N.yaml:29-`) | 9자 초과 거부 (main:949), IP20/W232N 은 같은 소스의 보드 선택지 (`main:CMakeLists.txt:50-58`) | 두 기종만 10자 이상에서 저장 실패(`ae0226b` 가 고친 증상) |
| 5 | MQTT QU QP QC PU U0 U1 U2 | 상한 없음 `security.yaml:102,114,127,151,163,175,187` | 칸 128, **검사 없음**(sprintf) → 128자↑ 이웃 필드 덮음 (main:1048-1100) | 오염. 127 상한 필요 |
| 6 | SO (2Port 의 RO) | 상한 없음 `security.yaml:25`, `w55rp20_two_port.yaml:294` | 60000 초과 거부 `SSL_RECV_MAX_TIMEOUT 60000` (`SSLInterface.h:33`, main:1037) | 60001↑ 입력 시 저장 취소 |
| 7 | TR | 정규식 `2[0-5][0-5]` 라 206~209, 216~219, 226~229, 236~239, 246~249 (20개)가 **거부** `retransmit.yaml:16` | 1~255 모두 허용 (`param_len>3`, `<1`, `>0xFF`; main:1008-1014) | 스펙 버그(받아야 할 값을 막음) |
| 8 | FL (2Port EF) | 0~4 자유 `base.yaml:315` | UART 인터페이스가 RS-422/485 이면 3·4 가 아닌 값은 **오류 없이 0 으로 바뀐다** (main:877-883; 2Port·GreenCS 동일 구조) | SET 성공인데 GET 값이 다름. 스펙은 `UN`/`UI` 와 연동 안 함 |
| 9 | PS (NS, HS…) | 0~255 `base.yaml:358` | `param_len>4 && tmp_int > SEG_DATA_BUF_SIZE/2`=2048 (main:915, `seg.h:18` 4096) | 스펙이 더 좁음(무해) |
| 10 | SD DD SE (RD RF EE) | 최대 30자 `w55rp20_ext.yaml:22,34,46`, `w55rp20_two_port.yaml:323,335,347` | 칸 `[32]` → 31자 (`ConfigData.h:13`) | 스펙이 1 좁음(무해). 31자는 FW 가 받는다 |
| 11 | RH/RP (QH/AP) 표시 조건 | `OP∈{0,2,3}` 에서만 `base.yaml:186,199`; 2CH `QH/AP` 는 `AO∈{0,2,3,4}` `w55rp20_two_port.yaml:91,104` | FW 는 OP 4(SSL)·5(MQTT)·6(MQTTS) 도 `remote_ip/remote_port` 로 연결한다 (`seg.c:511,699,884`) | UI 가 이 모드에서 호스트·포트 입력을 숨김 |
| 12 | MB | `modbus` 그룹에 `MB` 정의 `modbus.yaml:22`, `W55RP20-S2E.yaml:73`·`-2CH.yaml:22` 가 그룹 전체 포함. 주석은 "enum 에 전부 있다"(`W55RP20-S2E.yaml:70`) | **명령표에 `MB` 없음**(main:64-71, 2Port:47-57, GreenCS:47-66) → 보내면 NOCOMMAND 로 저장 취소 | 현재 툴은 `PO` 만 보낸다(`WIZMakeCMD.py:323-326`)라 실해 없음. 주석은 사실 아님 |
| 13 | GA GB GC GD · CA CB CC CD | `gpio` 그룹을 RW 로 포함 `W55RP20-S2E.yaml:74`, `gpio.yaml:16,76` | `__USE_USERS_GPIO__` 가 주석 처리(`board.h:33`) → GET 은 공백 1칸, SET 은 조용히 무시. GC/GD/CC/CD 는 `#ifdef` 안에도 case 가 없다(main:452-472,1338-1373) | 화면에 값이 있는 것처럼 보이지만 동작 없음 |
| 14 | BR / EB 범위 | `[0-9]\|1[0-9]` (0~19, 16~19 는 FW≥1.2.1) `W55RP20-S2E.yaml:89`, `-2CH.yaml:36`, `IP20.yaml:34` | main: `> baud_max`(=20) 라 **20 까지 받는다**(main:840, `baud_table` 은 20칸 `uartHandler.c:31`, OOB 읽기 `deviceHandler.c:407`). 2Port: `>= baud_max` 0~19 (2Port:1012). **GreenCS: 0~15 만**(`> baud_921600`, GreenCS:1141,1156; ch2 `>= baud_max`=16, :1878; `uartHandler.h:23-24`, 표 16칸 `uartHandler.c:29`). W232N: 0~13 (main:836) = 스펙 `W232N.yaml:31` 과 일치 | GreenCS 에 16~19 를 보내면 거부+저장 취소. main 의 20 은 툴이 안 보냄 |
| 15 | IP20 / W232N 메타 | `fw_constraints` 에 `config_buf_size` 없음(`IP20.yaml:68-70`, `W232N.yaml:59-61`; 1ch·2CH 는 2048). 주석 "FW 소스가 없다" `IP20.yaml:16`, `W232N.yaml:16` | 같은 소스·같은 `CONFIG_BUF_SIZE 2048` (`main:common.h:49`) | 크기 경고 기준 누락, 주석 부정확 |

**일치 확인(어긋나지 않음) — 중복 방지용으로 한 줄씩**: OP 0~6 · IM · CP · KA · TE · EC (0/1) · DB 0~1 · PR 0~2 · SB 0~1 · PD 2 hex · SS 6 hex · PO/MB(EO) 0~2 · DG 0~4 · RC 0~2 · CE 0~1 · QO 0~2 · KI/KE/RI/IT/PT 0~65535. (근거: main:685-933 의 `param_len`/`>` 검사, `SEG_DEBUG_ALL=4` `seg.h:56`.)

---

## 8. 담당자에게 물어야 할 것 (소스만으로 결론 안 나는 것, 5개)

1. **`gSEGCPREP` 뒤에는 무엇이 있나?** 근거: 선언만 `main:segcp.c:38-40`(`gSEGCPREQ`, `gSEGCPREP`, `tpar` 순) 있고 `.bss` 배치는 링커가 정한다. 2Port/GreenCS 빌드의 map 파일에서 `gSEGCPREP` 다음 심볼과, GreenCS 정상 값 응답(2,387~2,395B)이 넘치는 339~347B 가 어디에 닿는지. 선택지: (a) `gSEGCPREQ`/`tpar` 등 SEGCP 버퍼 (b) 다른 모듈 전역 (c) 보호된 빈 영역. 답에 따라 툴이 GreenCS·2Port 에서 막아야 하는 선이 달라진다.
2. **4port 의 두 보호(`SEGCP_REPLY_HEADROOM`, `segcp_store_string`)와 파서 경계(`4port:segcp.c:440,480`)를 main/2Port/GreenCS 에 이식할 계획이 있나?** 근거: 2Port 정상값 최악 1,976~1,984B, GreenCS 2,387~2,395B(5절), 128자 호스트가 `dhcp_use` 를 지움(3절). 선택지: (a) 전 브랜치 이식 (b) 4port 전용 유지 (c) main·2Port 만(GreenCS 는 비공식이라 제외). 계획에 따라 툴의 `config_buf_size` 경고 기준과 입력 상한을 브랜치별로 둘지 정한다.
3. **2Port·GreenCS 명령표 끝이 `"0"`(문자열)인 것은 의도인가?** 근거: `2Port:segcp.c:57`, `GreenCS:segcp.c:66`; main·4port 는 NULL. 표에 없는 명령(예: 4CH 전용 `PI` 를 2CH 에 보낼 때)을 파싱하면 표 밖을 읽는다. 선택지: (a) 실수 — 수정 예정 (b) 우연히 인접 데이터의 NULL 에서 멈추도록 알고 있음. (a)면 툴은 "표 밖 명령 금지"를 더 엄격히 지켜야 한다.
4. **GreenCS 의 baud 상한 921600 은 의도인가?** 근거: `GreenCS:uartHandler.h:23-24`(`baud_max` 가 921600 바로 뒤), `uartHandler.c:29`; main/2Port 는 1M~8M 지원(`261ab82`, `8350ffa`). 선택지: (a) 하드웨어/클럭 제약으로 의도 (b) 아직 이식 안 됨. 툴 스펙은 FW≥1.2.1 이면 16~19 를 허용하므로 (b) 라면 곧 맞아지고 (a) 면 GreenCS 에는 버전이 아니라 브랜치 조건이 필요하다.
5. **`DH`·`SP` 20자 이상 거부(main:789,960)가 의도된 응답인가, 아니면 자르기를 기대하나?** 근거: 오류 비트가 서면 같은 요청의 `SV` 가 취소된다(4절). 선택지: (a) 거부가 맞음 — 툴이 9/19자 상한을 걸면 끝 (b) 잘라 저장하도록 변경 예정. 4port 는 `store_string` 이 거부로 통일했다.

---

## 9. 미확인

| 항목 | 이유 |
| --- | --- |
| 응답 초과 시 덮이는 대상 · 증상 | 링커 맵·실기기 필요(질문 1) |
| 1,472B 초과 UDP 가 W5500 에서 전송되는지 | 소프트웨어는 2048 로만 자름(`socket.c:532`), 칩 동작은 소스 밖 |
| IP20 / W232N / WIZ5XXSR_RP / PLATYPUS 보드를 이 브랜치들에서 실제 어떤 UART 수·핀으로 빌드하는지 | 기본 빌드만 읽음. 보드별 핀 블록은 `board.h` 에 있으나 빌드는 안 해 봄 |
| `SEGCP_PRIVILEGE_READ`(0x00)·`SET`(0x80) 구조 때문에 브로드캐스트 MA 도 쓰기 권한 판정을 통과하는지 | 이 문서 범위 밖, 읽지 않음 |
| 그 외 브랜치 (`Develop` `Platypus` `SPI` `NICOM` `Yes` `OTA_test` `2socket_1serial` `woosinenc_2_socket` `modular_test_Lihan`) | 요청 범위 밖, 읽지 않음 |
| 2Port 1.2.2 대 "Sync V1.2.3" 표기 | `common.h:12` 값만 확인, 어느 쪽이 의도인지 모름 |
