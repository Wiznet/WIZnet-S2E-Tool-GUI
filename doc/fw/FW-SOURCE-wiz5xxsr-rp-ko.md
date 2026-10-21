# WIZ5XXSR-RP-C 펌웨어 소스 — SEGCP 설정 프로토콜 정리 (설정툴 개발자용)

작성: 2026-10-20 · 방법: 공개 저장소를 전체 이력으로 clone 해 읽기만 함(빌드·실행 없음) · 코드·커밋·push 변경 없음.

**표기**
- 출처 태그: `[소스]` 직접 읽은 것(기준 커밋 명시) / `[추정]` 읽은 것에서의 추론 / `미확인` 읽지 못했거나 소스만으로 결론 불가.
- 담당자 발언·실기기 측정은 이 문서에 없다.
- 근거 `파일:줄` 은 저장소 루트 기준 약칭을 쓴다. 따로 적지 않은 `segcp.c` 는 App 쪽이다.

| 약칭 | 실제 경로 |
| --- | --- |
| `segcp.c` / `segcp.h` | `port/app/configuration/src/segcp.c` / `.../inc/segcp.h` |
| `common.h` | `port/app/configuration/inc/common.h` |
| `ConfigData.h` / `ConfigData.c` | `port/app/configuration/inc/ConfigData.h` / `.../src/ConfigData.c` |
| `board.h` | `port/app/board/inc/WIZ5XXSR-RP_board.h` |
| `deviceHandler.h` | `port/app/platform_handler/inc/deviceHandler.h` |
| `boot/segcp.c` | `port/boot/configuration/src/segcp.c` (Boot 쪽은 `boot/` 를 붙인다) |

---

## 1. 기준

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 저장소 | `https://github.com/Wiznet/WIZ5XXSR-RP-C` (README 링크는 `W5XXSR-RP-C` 로 표기) | `README.md:9` |
| 기본 브랜치 | `main` (원격 브랜치: `main`, `Develop`, `PowerSoft_Custom`, `fix/certificate-upload`) | `[소스]` git branch -a |
| 읽은 커밋 | `fd2e58939428cb039b5039359dda666382c81031` · 2026-09-21 14:39:35 +0900 · "Update version information to 1.1.3" | `[소스]` git log -1 |
| 읽은 태그/버전 | 태그 `1.1.3` = 위 커밋. 코드상 App 1.1.3 | `common.h:10-12` |
| 그 외 태그 | `1.0.5`~`1.1.3`, 그리고 `E-SAVE_1.0.0`(2023-11-28 태그, 커밋 `42107e1` 2023-10-17). E-SAVE 커밋은 `main` 의 조상이 아니다(별도 계통) | `[소스]` git merge-base |
| 빌드 보드 | **한 종류뿐**: `DEVICE_BOARD_NAME WIZ5XXSR_RP`, 기본 이름 `"WIZ5XXSR-RP"`, 제품 코드 `04 00 01` | `board.h:24`, `board.h:39`, `ConfigData.c:47-49` |
| 포함 제품 | WIZ500SR-RP, WIZ505SR-RP, WIZ510SR-RP (RP2040 + W5100S) | `getting_started.md:3,28`, `CMakeLists.txt:27` |
| **IP20 / W232N** | **이 저장소에 없다.** 두 이름이 소스·문서 어디에도 안 나온다(`W55RP20` 는 주석 한 줄 `deviceHandler.h:49` 뿐). 같은 보드 계열이라는 근거를 소스에서 찾지 못함 | `[소스]` grep -ri |
| 서브모듈 | ioLibrary_Driver · mbedtls · pico-sdk · pico-extras 는 clone 에 비어 있다. `socket.c` 만 고정 커밋 `ce4a7b6` 에서 raw 로 받아 읽음 | `.gitmodules`, `[소스]` |
| 버전 파일 불일치 | `WIZ5XXSR-RP_c_sdk_version.cmake` 는 1.0.9 로 남아 있다(코드의 1.1.3 과 다름). 펌웨어가 보고하는 값은 `common.h` 쪽 | `WIZ5XXSR-RP_c_sdk_version.cmake:2-6` |

---

## 2. 프로토콜 · 버퍼

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 포트 | SEGCP **50001**(UDP + TCP unicast), 펌웨어 업로드 **50002** | `deviceHandler.h:13-14` |
| 소켓 | W5100S 하드웨어 소켓 4개: DATA=0, CONFIG_UDP=1, CONFIG_TCP=2, DHCP/DNS/FWUP/NTP 공용=3 | `common.h:23-30` |
| 소켓 버퍼 | 소켓당 TX/RX 각 **2 KB** (`memsize` 2 = 2KB) | `port/app/ioLibrary_Driver/src/w5x00_spi.c:199-201` `[소스]` |
| **응답 버퍼** | `gSEGCPREP[CONFIG_BUF_SIZE]`, `CONFIG_BUF_SIZE = 2048` | `segcp.c:46`, `common.h:45` |
| **요청 버퍼** | `gSEGCPREQ[SEGCP_REQ_BUF_SIZE]` = 4096+64 = **4160** (AT 모드 PEM 업로드용으로 키움) | `segcp.c:45`, `common.h:60` |
| 토큰 한도 | `SEGCP_PARAM_MAX = 256`, 명령 2글자, 구분자 `\r\n`. 값 임시 버퍼는 `param[SEGCP_PARAM_MAX*2]` = **512** | `segcp.h:23-25`, `segcp.c:405` |
| 레거시 상수 | `DEVCONF_DOMAIN_MAX 32` 등은 **어디서도 쓰지 않는다**. 도메인 실제 칸은 128B | `segcp.h:17-21`(참조 0건 `[소스]` grep), `ConfigData.h:14` |
| 데이터 경로 버퍼 | `DATA_BUF_SIZE 2048`, UART 링버퍼 `SEG_DATA_BUF_SIZE 4096`, `MQTT_BUF_SIZE 2048`. SEGCP 버퍼와 **별개**. 단 `PS` 상한이 `SEG_DATA_BUF_SIZE/2` 로 연결됨 | `common.h:44,46`, `seg.h:15`, `segcp.c:913` |
| UDP 수신 | 수신 크기를 `SEGCP_REQ_BUF_SIZE-1` 로 제한한 뒤 `recvfrom`. 실제로는 RX 소켓 버퍼 2KB 가 먼저 한계 `[추정]` | `segcp.c:1364-1369` |
| TCP 수신 | `recv` 후 마지막 1바이트를 0 으로 덮음(`treq[len-1]=0`). 크기 제한 없음(RX 2KB 이내라 4160 에 들어감 `[추정]`) | `segcp.c:1464-1465` |
| 처리 순서 | `do_segcp()`: (AT 모드면 UART) → UDP → TCP → `segcp_ret_handler()` | `segcp.c:188-206` |
| 인증 | 요청 첫 줄 `MA` 필수. `FF:FF:FF:FF:FF:FF` = 읽기 권한, 장치 MAC = 쓰기 권한, 그 외는 **응답 없음**. 이어서 `PW` 가 일치해야 처리(불일치도 응답 없음) | `segcp.c:1371-1409` |
| **응답 방식** | UDP 응답은 **항상 브로드캐스트**: `sendto(..., "\xFF\xFF\xFF\xFF", destport)` (목적 포트 = 요청자의 출발 포트). TCP 는 `send()` | `segcp.c:1401`, `segcp.c:1496` |
| 응답 길이 | `14 + strlen(PW값) + strlen(본문)`. PW 가 공백 1자면 헤더 15B (MA줄 10 + PW줄 5) | `segcp.c:1381-1401` |

`[추정]` 툴의 응답 모델 `15 + Σ(4 + 값길이)` 는 위 구조와 일치한다(헤더 15 + 명령마다 `XX`2 + 값 + `\r\n`2).

---

## 3. 응답 길이 보호

| 질문 | 답 | 근거 |
| --- | --- | --- |
| 응답이 버퍼를 넘을 때 검사가 있나 | **없다.** `sprintf` / `strcat` 로 `trep` 에 이어 쓰기만 한다. `CONFIG_BUF_SIZE` 는 `gSEGCPREP` 선언 한 곳에서만 쓰인다. 조건식 자체가 없음 | `segcp.c:46`, `segcp.c:710-711`, `[소스]` grep `CONFIG_BUF_SIZE\|gSEGCPREP` 사용처 4곳(선언+do_segcp 호출 3) |
| 넘으면 | 쓰기가 `gSEGCPREP` 뒤로 넘어간다 `[추정]`(인접 메모리 배치는 `미확인`). 송신만은 `sendto` 가 `getSn_TxMAX` 로 길이를 자른다 | `ioLibrary socket.c:532-533`(`ce4a7b6`), 소켓 TX 2KB |
| 요청 쪽 보호 | UDP 수신 길이 클램프만 있음. 한 요청에 들어가는 **명령 개수·같은 명령 반복에는 제한이 없다** | `segcp.c:1364`, `segcp.c:412-413` |
| 응답 버퍼 초기화 | `memset(trep, 0, sizeof(trep))` — `trep` 는 포인터라 **4바이트만** 지운다(버퍼 전체 아님). 본문 시작 1바이트가 0 이면 `strlen` 이 0 이라 문제는 안 드러남 | `segcp.c:391,409` |

**최악 응답 크기 추정** `[추정]` (각 값의 최대 길이를 소스 형식에서 계산, 스크립트 `calc_resp.py`/`calc2.py`)

| 가정 | 응답 크기 |
| --- | --- |
| 툴 `search_cmd_order` 50개(`specs/devices/WIZ5XXSR-RP.yaml:12-61`) GET, 문자열 필드 8개(RH QU QP QC PU U0 U1 U2)가 모두 127자 | **1479 B** (2048 안, 단 UDP 한 패킷 1472B 를 7B 넘김) |
| 같은 50개, 문자열 필드가 비었거나 짧음(한 글자) | 471 B |
| 표의 GET 가능 64개를 모두 한 번씩, 최대 길이 | 1553 B |
| 127자 필드 GET 하나(`QU` 등)를 반복해 2048 도달 | 16회 반복이면 넘음(요청 약 64B). 툴이 만들 요청은 아님 |

- 각 값 최대 길이 가정: MC 17, MN 19, DH 32(`이름19+'-'+MAC12`), LI/SM/GW/DS 15, KI/KE/RI/IT/PT/LP/RP 5, PS 4, TR 3, QK 10(`uint32`), SO 5, VR 5(`1.1.3`).
- `미확인`: 1472B 를 넘는 UDP 데이터그램을 W5100S 가 단편화해 보내는지(칩 동작·실기기 사항). 소스만으로 결론 불가 → 질문 1.

---

## 4. 문자열 필드 — 칸 크기와 SET 검사

`[소스]` 칸 크기는 `ConfigData.h`, 검사는 `segcp.c`. 구조체는 `packed`, 선언 순서가 곧 메모리 순서(`ConfigData.h:157-174`).

| 명령 | 칸(B) | 최대 글자 | SET 시 길이 검사 | 범위를 넘으면 | 근거 |
| --- | --- | --- | --- | --- | --- |
| `DH` (장치 이름) | `device_name[20]` | **19** | 있음 `param_len > 19` | **거부** `ERINVALIDPARAM` | `ConfigData.h:10,33` · `segcp.c:817` |
| `NP` (연결 암호) | `pw_connect[10]` | **9** | 있음 | **거부** | `ConfigData.h:74` · `segcp.c:940-941` |
| `SP` (검색 암호) | `pw_search[10]` | **9** | 있음 | **거부** | `ConfigData.h:41` · `segcp.c:949-950` |
| `RH` (도메인) | `dns_domain_name[128]` | 127 | **없음** `strcpy` | **덮어씀**: 128자째 NUL 이 다음 필드를 침 | `ConfigData.h:14,59` · `segcp.c:844,852` |
| `QU` 사용자 | `user_name[128]` | 127 | **없음** `sprintf("%s")` | 덮어씀(다음 선언 필드) | `ConfigData.h:18,149` · `segcp.c:1023-1028` |
| `QP` 암호 | `password[128]` | 127 | 없음 | 덮어씀 | `ConfigData.h:19,151` · `segcp.c:1030-1035` |
| `QC` 클라이언트 ID | `client_id[128]` | 127 | 없음 | 덮어씀 | `ConfigData.h:20,150` · `segcp.c:1038-1043` |
| `PU` 발행 토픽 | `pub_topic[128]` | 127 | 없음 | 덮어씀 | `ConfigData.h:17,145` · `segcp.c:1049-1054` |
| `U0` `U1` `U2` 구독 토픽 | 각 `sub_topic_N[128]` | 127 | 없음 | 덮어씀 | `ConfigData.h:146-148` · `segcp.c:1056-1075` |
| `MN` `VR` | — | — | SET 은 `ERIGNORED` | 무시 | `segcp.c:722-725` |
| `OC` `LC` `PK` (PEM) | 임시 `g_temp_buf` 4096, 저장 섹터 4096 | 4095 | `recv_pem` 이 경계 안에서 받음 | 끝 표식 없음/초과 → **거부** | `common.h:52-54` · `segcp.c:130-165,1096-1225` |

덮어씀의 구체적 결과 `[소스+추정]`:
- `RH` 는 `__network_connection` 의 마지막 멤버라 128자째 NUL 이 `DevConfig` 선언 순서상 바로 뒤의 `network_option.dhcp_use` 를 0(정적 IP)으로 바꾼다(`ConfigData.h:59,161-162`, `network_option` 첫 멤버 `dhcp_use` `:63`).
- 토큰 자체가 511자를 넘으면 `parse_SEGCP` 의 `strcpy(param, ...)`(`segcp.c:361`) 가 `param[512]` 스택 배열을 넘는다(길이 검사 없음). 이 경우는 필드가 아니라 스택이다.
- `DH` GET 은 `이름-MAC12자리`(최대 32자)를 돌려주고 SET 은 이름만 받는다. **GET 값을 그대로 SET 하면 19자를 넘어 `ERINVALIDPARAM`** 이 난다(`segcp.c:488-500` 대 `:817`).
- 툴 쪽 기록(`SEGCP_PARAM_MAX` 256, 도메인 128B)은 소스와 일치한다. 단 256 은 토큰 상한이 아니라 선언값이고 실제 임시 버퍼는 512 이며 검사는 없다.

숫자 필드(참고): 5자리 값은 `atol` 후 `> 0xFFFF` 면 거부(`KI KE RI LP RP IT PT`: `segcp.c:757-834,901-910`). `BR` 최대 14(`param_len>2`), `OP` ≤ 6, `PS` ≤ 2048(`param_len ≤ 4`), `TR` 1~255(`param_len ≤ 3`), `SO` ≤ 60000, `QK` 무검사(`atoi`).

---

## 5. 오류 처리 (설정툴 UDP 모드)

| 질문 | 답 | 근거 |
| --- | --- | --- |
| 오류 시 뒤 명령을 계속 처리하나 | **계속 처리한다.** `opmode != DEVICE_AT_MODE` 면 오류 후 `return` 하지 않고 다음 `strtok` 토큰으로 간다 | `segcp.c:1316-1329` |
| ER 줄이 응답에 실리나 | **아니오.** ER 줄(`ERINVALIDPARAM:XX`)은 `opmode == DEVICE_AT_MODE` 일 때만 쓰인다. UDP 요청이라도 장치가 AT 모드(+++ 또는 HW 트리거)이면 ER 줄을 응답에 싣고 **그 자리에서 처리 중단**한다 | `segcp.c:1316-1327`, `seg.c:2222` |
| 오류가 있으면 SV/RT 는 | **취소된다.** `ret` 에 `0x8000` 이 하나라도 있으면 `segcp_ret_handler` 가 SAVE·REBOOT·SWITCH·FACTORY·FWUP 모두 건너뛴다 | `segcp.c:216` (`(segcp_ret & ERR) != ERR` 일 때만 실행), `segcp.c:201-204` |
| 오류 전에 한 SET 은 | RAM(`dev_config`)에는 이미 반영됨. 저장은 안 됨(SV 취소) → 재부팅 전까지 RAM 값과 flash 값이 다름 `[추정]` | `segcp.c:719-1100` |
| 한 요청 안 GET 응답이 지워지나 | **그 명령 *뒤의* GET 이 지워진다.** `ret` 는 요청 안에서 누적되고, GET 마다 `ret & (ERR\|REBOOT\|SWITCH\|SAVE)` 를 검사해 맞으면 자기 응답 `XX…` 를 되돌려 지운다. 앞의 GET 응답은 남는다 | `segcp.c:702-707` |
| `SV` `RT` `EX` 자체는 | 응답 줄 없음(자기 자신도 지움). 정상 처리됐는지 응답으로 알 수 없다 | `segcp.c:591-602,702-707` |
| 권한 오류 | 읽기 권한(MA=FF…)으로 SET → `ERNOPRIVILEGE`(UDP 에서는 SV 취소 효과). `SV EX RT FR` 는 쓰기 권한 필요 | `segcp.c:714,1309-1310` |
| 예외: PEM 업로드 | `OC LC PK` 는 **성공해도 `return ret`** 으로 요청 처리를 끝낸다(뒤 명령 무시). 성공하면 `save_DevConfig_to_storage()` 를 *즉시* 호출한다(앞서 한 SET 이 같이 저장됨, 뒤따른 오류와 무관) | `segcp.c:1105-1137` |
| TCP 오류 합산 | `do_segcp` 가 UDP/TCP 의 `ret` 를 OR 한다. 한쪽 오류가 같은 루프의 다른 쪽 SAVE 도 막는다 `[추정]`(드문 동시 요청) | `segcp.c:201-204` |

`[추정]` 툴이 세트 + `SV` 를 한 요청에 보내면 필드 하나라도 `INVALIDPARAM` 이면 **응답에는 아무 흔적 없이 전체 저장이 취소**된다. 재조회 비교로만 알 수 있다.

---

## 6. 빈 값 GET · 미구현 명령

| 상황 | 응답 | 근거 |
| --- | --- | --- |
| 문자열이 비어 있음 | 값 자리에 **공백 1자(0x20, `SEGCP_NULL`)** → `NP␠\r\n` 형태. 해당: `DH`(이름 빔), `RH`(DNS 사용 + 도메인 빔), `NP`, `SP`, `QU`, `QP`, `QC`, `PU`, `U0`, `U1`, `U2` | `segcp.c:489-490,515-516,548,552,646-683`, `segcp.h:101` (`SEGCP_NULL ' '`) |
| SET 으로 비우기 | 값에 공백 1자를 보내면 빈 문자열로 저장 | `segcp.c:820-821,944,953,1024-1025` |
| 표에는 있는데 GET 분기가 없음 | `default:` → **공백 1자** 응답(오류 아님). 해당: `GA GB GC GD CA CB CC CD`(GPIO 옵션 꺼짐 → 아래 7장), `FW` | `segcp.c:695-699`, `board.h:38` |
| 표에는 있는데 SET 분기가 없음 | `default:` → **조용히 무시(오류 없음)**: `GA GB GC GD CA CB CC CD` | `segcp.c:1304-1306` |
| SET 이 의도적으로 거부 | `S0 S1 RX` → `ERINVALIDPARAM`; `UN ST MA EX SV RT FR PW UI` → `ERNOTAVAIL`; `VR MN` → `ERIGNORED` | `segcp.c:976-983,1293-1303,722-725` |
| 표에 없는 명령(예 `MB`, `SD`, `DD`, `SE`) | `ERNOCOMMAND` → UDP 에서는 응답에 안 나오고 **요청 전체의 SV/RT 취소** | `segcp.c:312-316,1312-1313` |
| 명령 매칭 방식 | 앞 2글자 `strncmp` 로 표를 순서대로 찾는다 | `segcp.c:307-310` |
| GET 인데 부작용 있는 명령 | `RX` GET 은 UART 수신 버퍼를 **비우고** `FLUSH` 를 응답 | `segcp.c:587-590` |

---

## 7. 명령 목록과 빌드 옵션

### 7.1 App 명령표 — 73개 `[소스]`

`segcp.c:69-76` (1-UART 표, `DEVICE_UART_CNT == 1` 일 때 컴파일, `board.h:41`). 2채널 이상 표(`segcp.c:54-66`, 120여 개)는 `#if (DEVICE_UART_CNT > 1)` 쪽이라 **이 빌드에서는 컴파일되지 않는다.** `segcp.h:29-70` 의 `#if 0` 블록도 죽은 코드.

| 분류 | 명령 |
| --- | --- |
| 정보 | MC VR MN ST UN UI |
| 네트워크 | IM OP LI SM GW DS DH LP RP RH RI CP NP |
| 시리얼 | BR DB PR SB FL PO DG PT PS PD IT KA KI KE TE SS SP EC TR |
| 상태핀 | SC S0 S1 (GPIO 옵션과 무관하게 동작) |
| GPIO | GA GB GC GD CA CB CC CD (**표에만 있음**, 아래 참고) |
| SSL | RC CE SO OC LC PK |
| MQTT | QU QP QC QK PU U0 U1 U2 QO |
| 제어 | MA PW SV EX RT FR RX UF FW |

**툴 쪽 "없다고 기록된 19개"** (`CA CB CC CD DD EC GA GB GC GD MB PO S0 S1 SC SD SE TR UI`) 대조 `[소스]`:

| 결과 | 명령 |
| --- | --- |
| 소스에 **있음**(15) | CA CB CC CD EC GA GB GC GD PO S0 S1 SC TR UI |
| 소스에 **없음**(4) | **DD MB SD SE** |

빌드 옵션별 차이:

| 옵션 | 상태 | 영향 | 근거 |
| --- | --- | --- | --- |
| `__USE_USERS_GPIO__` | **꺼짐(주석)** | `GA GB CA CB` 의 GET/SET 분기가 컴파일 안 됨 → GET 공백, SET 무시. 켜도 `GC GD CC CD` 는 분기 자체가 없음. 기본값에서 `user_io_enable=0` | `board.h:38`, `segcp.c:558-575,1253-1288`, `ConfigData.c:146-156` |
| `DEVICE_UART_CNT` | 1 | 위 1-UART 표 | `board.h:41` |
| `__USE_UART_IF_SELECTOR__` | 꺼짐 | 인터페이스는 항상 `UART_IF_DEFAULT = RS-232`(`FL` 3/4 저장 시 로드 때 RS-422 로 바뀜) | `board.h:33`, `uartHandler.h:37`, `ConfigData.c:225-232` |
| `__USE_SAFE_SAVE__` | 켜짐 | 저장 후 읽어 비교, 최대 5회 재시도 | `board.h:34`, `ConfigData.c:239-266` |
| `__USE_DNS_INFINITE_LOOP__` | 켜짐 | DNS 실패 시 무한 재시도(재시도 중에도 `do_segcp()` 가 돈다) | `board.h:31`, `dnsHandler.c:156-161` |
| `__USE_DHCP_INFINITE_LOOP__` | 꺼짐 | DHCP 3회 실패 시 정적 IP 로 | `board.h:30`, `deviceHandler.c:594` |
| `__USE_S2E_OVER_TLS__` `__USE_WATCHDOG__` `__USE_HW_FACTORY_RESET__` `__USE_UART_485_422__` | 켜짐 | — | `board.h:32,35-37` |
| `STR_VERSION_STATUS` | `"Stable"` | `VR` 가 `1.1.3`. `"Develop"` 이면 `1.1.3dev`, 그 외는 문자열을 뒤에 붙임 | `common.h:17`, `segcp.c:430-451` |

### 7.2 Boot 명령표 — 69개 (App 보다 4개 적음)

`boot/segcp.c:60-66`. **`PO SC S0 S1` 이 Boot 표에 없다.** Boot 의 SET 분기 목록에는 MQTT·SSL·`UF` 가 없고(`boot/segcp.c:553-873`), GET 쪽은 `UF` 까지만 있다(`:526`). 표에 이름만 있는 MQTT/SSL 명령은 GET 시 공백(`:530-534`), SET 시 무시(`:875-878`). Boot 에는 요청·응답 버퍼가 모두 2048이고 UDP 수신 길이를 자르지 않는다(`boot/segcp.c:36-37,934`). `[소스]`

### 7.3 `E-SAVE_1.0.0` 태그(커밋 `42107e1`)

`[소스]` git show. 표에 `U3~U9` 가 더 있고 `PO` 가 없다. `U3~U9` 는 `#if (MAX_MESSAGE_HANDLERS==10)` 안, `CONFIG_BUF_SIZE` 도 같은 조건에서만 4096, 아니면 값이 비어 있다(`port/configuration/inc/common.h:51-55`, `.../inc/segcp.h:46-53`). 이 태그의 코드 버전은 1.1.6, `DEV_CONFIG_VER` 104 로 `main`(1.1.3 / 103)과 계통이 다르다. `MAX_MESSAGE_HANDLERS` 정의 위치는 `미확인`.

---

## 8. Boot/App 구조 · 버전 · 저장 · DNS 호출 경로

### 8.1 구조

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 플래시 지도 `[소스]` | Boot 512KB @`0x10000000` · App bank0 512KB @`0x10080000` · FW bin bank1 512KB @`0x10100000` · 설정/인증서 영역은 bank1 뒤(오프셋 `0x180000`)부터 4KB 단위: 설정, RootCA(+0x1000), ClientCert(+0x1000), PrivKey(+0x1000), MAC(+0x1000) | `deviceHandler.h:17-31`, `storageHandler.c:15-103` |
| 주의 | `flashHandler.h:17-43` 의 ASCII 그림은 Parameters 를 `0x101F0000` 로 그렸지만 매크로 값과 다르다. 실제 동작은 매크로 | `flashHandler.h:10-43` vs `deviceHandler.h:31` |
| Boot 동작 `[소스]` | 부트 핀이 눌렸거나 두 뱅크 모두 무효이면 부트로더 SEGCP 모드(상태 `BOOT`). 아니면 `fwup_copy_flag==1` 일 때 bank1→bank0 복사 후 App 으로 점프 | `Boot/Boot_main.c:76,122-147` |
| FW 업데이트 `[소스]` | `FW<크기>` → `device_bank_update()` → 50002 로 업로드 → bank1 에 기록. `UF`=복사 플래그(뱅크 점검이 실패하면 **오류 없이 무시**) | `segcp.c:239-251,1086-1095,1228-1252` |
| Boot/App 구분 | Boot 의 `ST` 는 `BOOT`. `device_mode` 필드는 Boot 도 `DEVICE_APP_MODE` 로 둠(구분에 못 씀) | `Boot_main.c:76`, `boot/ConfigData.c:52` |

### 8.2 버전

| 항목 | 값 | 근거 |
| --- | --- | --- |
| App `VR` | `1.1.3` | `common.h:10-12`, `ConfigData.c:234-236` |
| Boot `VR` | `1.0.9` (`BOOT_*_VER` 를 `fw_ver` 에 넣음) | `boot/common.h:10-12`, `boot/ConfigData.c:34-36,219-221` |
| 형식 | `정수.정수.정수` (+ `dev` 또는 사용자 접미사). `Stable` 이라 접미사 없음 | `segcp.c:430-451` |
| `MN` | `DEVICE_ID_DEFAULT` = `WIZ5XXSR-RP` (사용자가 `DH` 로 바꾸면 바뀜) | `board.h:39`, `ConfigData.c:51-52` |

### 8.3 설정 저장

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 저장 | 4KB 섹터 지운 뒤 `DevConfig` 통째로 쓰고(`SAFE_SAVE` 면 읽어 비교, 최대 5회) | `ConfigData.c:239-266` |
| 저장 시점 | `SV` 처리(`segcp_ret_handler`) 또는 PEM 업로드 성공 즉시 | `segcp.c:228-232,1129,1172,1215` |
| 부팅 로드 | `packet_size` 또는 `devConfigVer`(103) 가 다르면 **공장값으로 초기화 후 저장·재부팅**. 구조체가 바뀐 펌웨어로 올리면 사용자 설정이 사라질 수 있다 | `ConfigData.c:210-223`, `common.h:14` |
| MAC | 별도 영역 `STORAGE_MAC`. `MC` SET 은 OUI 가 `00:08:DC` 면 `ERIGNORED` | `ConfigData.c:202`, `segcp.c:719` |

### 8.4 DNS/DHCP 중 `do_segcp()` 호출 경로 (호출 경로 전체 확인)

`[소스]` 한 단계씩 따라간 결과 — **`process_dns()` 본문에는 `do_segcp()` 가 없지만, 안에서 부르는 헬퍼가 돌린다.**

| 단계 | 위치 | 내용 |
| --- | --- | --- |
| 1 | `App/App_main.c:114-125` | `working_mode != TCP_SERVER_MODE` 이고 `dns_use` 면 `process_dns()` |
| 2 | `dnsHandler.c:138-172` | `process_dns()` → `do { get_ipaddr_from_dns(...) ... } while(ret != TRUE)` (본문에 `do_segcp` 없음) |
| 3 | `dnsHandler.c:151` | 호출: `get_ipaddr_from_dns(domain, remote_ip, DNS_WAIT_TIME*300)` |
| 4 | `dnsHandler.c:174-188` | `get_ipaddr_from_dns()` 안: `do { DNS_run_handler(...); do_segcp(); } while(ret == DNS_RET_RUNNING)` |
| DHCP | `deviceHandler.c:563-606` | `process_dhcp()` 본문이 직접 `do_segcp()` 를 부른다(`:604`), 10ms sleep 으로 응답성 유지 |
| 주 루프 | `App_main.c:154` | `while(1)` 에서 `do_segcp()` → `do_seg()` |

결론: 설정툴 요청은 DHCP 중·DNS 중·주 루프 모두에서 처리된다. (DNS 재시도가 무한 루프 옵션이라 도메인이 안 풀리는 중에도 툴로 고칠 수 있다.)

---

## 9. 툴 스펙과의 대조

대조 대상: `specs/devices/WIZ5XXSR-RP.yaml`(이하 "RP"), `WIZ5XXSR-RP_E-SAVE.yaml`("E-SAVE"), `IP20.yaml`, `W232N.yaml`, `specs/commands/*.yaml`. FW 쪽은 `fd2e589` (E-SAVE 는 태그 `42107e1`).

### 9.1 어긋남 — 11건 (RP 기준 10건 + E-SAVE 1건)

방향: "툴이 더 엄격"=정상 입력이 툴에서 막힘, "툴이 느슨"=툴을 통과한 값을 FW 가 거부하거나 메모리를 훼손.

| # | 항목 | 툴 쪽 (근거) | FW 쪽 (근거) | 방향 · 영향 |
| --- | --- | --- | --- | --- |
| 1 | **MB** | RP/E-SAVE 가 `modbus` 그룹을 넣음 → `MB` 정의 포함 (`WIZ5XXSR-RP.yaml:71`, `commands/modbus.yaml:22-35`). 주석은 "enum 에 전부 있다"(`WIZ5XXSR-RP.yaml:66-68`) | App 표에 `MB` 없음 (`segcp.c:69-76`, `segcp.h:46-55`). 미지 명령 → `ERNOCOMMAND` (`segcp.c:1312-1313`) | MB 를 SET 하면 요청 전체 SV 취소 `[추정]`. `search_cmd_order` 에는 MB 없음(`:12-61`) |
| 2 | **SP** | regex 없음 `""` (`commands/base.yaml:459-470`) | 칸 10B, 9자 초과 거부 (`ConfigData.h:41`, `segcp.c:949-950`) | 툴이 느슨. 10자 이상 → `ERINVALIDPARAM` → SV 취소 |
| 3 | **RH** | `.{0,128}` (`commands/base.yaml:176`, 주석 "최대 128바이트") | 칸 128B, NUL 포함 **127자**, 검사 없음 (`ConfigData.h:14,59`, `segcp.c:844,852`) | 툴이 1자 느슨. 128자 → `dhcp_use` 를 0 으로 침 `[추정]` |
| 4 | **MQTT 문자열** `QU QP QC PU U0 U1 U2` | 전부 regex `""` (`commands/security.yaml:102-197`) | 각 128B, 검사 없음 (`ConfigData.h:17-20,145-151`, `segcp.c:1023-1075`) | 툴이 느슨. 128자 이상 → 인접 필드 훼손 `[추정]`. 상한 **127** 필요 |
| 5 | **DH** | regex `""` (`commands/ddns.yaml:85-97`) | 칸 20B, 19자 초과 거부 (`ConfigData.h:33`, `segcp.c:817`). GET 은 `이름-MAC12` | 툴이 느슨. GET 값을 그대로 SET 하면 24자 이상 → 거부 |
| 6 | **TR** | `^([1-9]\|[1-9][0-9]\|1[0-9][0-9]\|2[0-5][0-5])$` (`commands/retransmit.yaml:16`) | 1~255 (`segcp.c:991-995`) | 툴이 엄격. `2[0-5][0-5]` 라서 206-209, 216-219, 226-229, 236-239, 246-249 (20개) 가 막힘 |
| 7 | **PS** | `0~255` (`commands/base.yaml:358-368`) | `param_len ≤ 4` 이고 값 ≤ 2048 (`segcp.c:913`, `seg.h:15`) | 툴이 엄격. 256~2048 막힘 |
| 8 | **SO** | regex `""` (`commands/security.yaml:25-35`) | `> 60000` 거부 (`segcp.c:1019`, `SSLInterface.h:33`) | 툴이 느슨 |
| 9 | **QK** | regex `""` (`commands/security.yaml:139-149`) | 무검사 `atoi`, `uint32` 저장 (`segcp.c:1046`, `ConfigData.h:152`) | 상한 불명 → 툴 자체 상한 필요. GET 이 `%d` 라 2^31 이상은 음수로 표시 `[추정]` |
| 10 | **GPIO 그룹** `CA CB CC CD GA GB GC GD` | RP 가 `gpio` 그룹 전체 포함, RW 이고 값 목록·UI 있음 (`WIZ5XXSR-RP.yaml:72`, `commands/gpio.yaml:16-130`) | 표에는 있으나 옵션 꺼짐 → GET 공백, SET 무시(오류 없음). `S0 S1` SET 은 `ERINVALIDPARAM` (`segcp.c:695-699,976-979,1304-1306`, `board.h:38`) | UI 에서 설정해도 아무 일도 안 일어남(성공처럼 보임). `SC` 만 실동작 |
| 11 | **E-SAVE** `PO MB` | E-SAVE 도 `modbus` 그룹 (`WIZ5XXSR-RP_E-SAVE.yaml:72`). `config_buf_size` 없음 (`:38-40`) | E-SAVE 태그 표에 `PO`·`MB` 없음, `U3~U9` 있음, `CONFIG_BUF_SIZE` 는 조건부 4096 (`42107e1`: `segcp.h:46-53`, `common.h:51-55`) | 태그 기준으로 불일치. 현재 E-SAVE 출하 기준 소스는 `미확인` (질문 4) |

### 9.2 비교 불가 · 관찰

| 항목 | 내용 |
| --- | --- |
| IP20 / W232N | 소스가 이 저장소에 없어 **대조 불가**. 두 spec 도 "FW 소스 없음"을 명시(`IP20.yaml:16-19`, `W232N.yaml:16-19`). 참고로 두 spec 은 `w55rp20_ext`(SD/DD/SE, `commands/w55rp20_ext.yaml:20-54`)를 쓰는데 이 펌웨어 표에는 SD DD SE 가 없다 → **같은 펌웨어 계통이라고 볼 근거가 소스에서 안 나온다.** BR 범위도 다르다: IP20 0~19(`IP20.yaml:35`), W232N 0~13(`W232N.yaml:32`), 이 FW 는 0~14(`segcp.c:858`) |
| PO | FW 에 있고 범위 0~2 로 spec 과 일치(`segcp.c:896-900`, `modbus.yaml:41-54`). 그러나 RP `search_cmd_order` 에 없다 → 초기값을 어디서 읽는지 툴 코드 `미확인` |
| FL | 범위 0~4 일치. 단 인터페이스가 RS-422/485 이면 3·4 이외 값은 **오류 없이 0 으로 저장**(`segcp.c:884-891`). FL=3/4 저장 후 재부팅하면 로드 시 RS-422 로 바뀌므로(`ConfigData.c:225-228`) 이후 FL=1/2 SET 이 조용히 0 이 될 수 있다 `[추정]` |
| config_buf_size | RP `2048` 은 `common.h:45` 와 일치(`WIZ5XXSR-RP.yaml:122`) |

### 9.3 일치 확인된 항목 (참고)

`IM`(0~1) `OP`(0~6, `MQTTS_CLIENT_MODE`) `BR`(0~14) `DB`(0~1) `PR`(0~2) `SB`(0~1) `DG`(0~4) `PD`(2 hex) `SS`(6 hex) `TE` `CP` `KA` `EC` `RC`(0~2) `CE`(0~1) `QO`(0~2) `NP`(9자) `SC`(2자리 0/1) — spec 과 소스 일치.

---

## 10. 담당자 확인 요청 — 소스만으로 결론이 안 나는 것 (5건)

아래는 "틀렸다"는 지적이 아니라, 파일과 줄을 열어 확인하실 수 있게 적은 검증 절차다.

**1. UDP 응답이 1472B 를 넘을 때 동작**
- 열어볼 곳: `segcp.c:1401`(`sendto`, 길이 `14+…`), `w5x00_spi.c:199-201`(소켓 TX 2KB).
- 사실: 툴이 현재 물어보는 50개 명령에서 문자열 필드를 모두 최대로 채우면 응답이 1479B(`[추정]` 계산)이다. `sendto` 는 2048B 까지는 보낸다(`socket.c:532-533`).
- 모르는 것: W5100S 가 1472B 초과 데이터그램을 단편화해 내보내는지, 수신 쪽 툴이 받을 수 있는지.
- 선택지: (a) 단편화 지원 → 툴이 1479B 응답을 받음 / (b) 미지원 → 툴 쪽에서 문자열 필드 일부 조회를 나눠야 함. 실기기 확인 또는 칩 자료로 답할 수 있는 사람이 필요.

**2. 문자열 필드 길이 상한의 *의도*(127 인가 128 인가)**
- 열어볼 곳: `segcp.c:836-855`(`RH`, `strcpy`), `segcp.c:1023-1075`(MQTT, `sprintf`), `ConfigData.h:14,17-20`(칸 128B).
- 사실: `NP`/`SP`/`DH` 는 `sizeof-1` 검사가 있고 `RH`/MQTT 는 없다.
- 선택지: (a) 의도된 상한은 127(= 칸-1) → 툴을 127자로 제한 / (b) 128자까지 쓸 계획(칸 확대 예정) → 현행 툴은 128로 두되 FW 변경 필요. 다음 릴리즈에 검사를 넣을 예정인지도 같이.

**3. 출하 바이너리의 빌드 옵션이 `board.h` 와 같은가**
- 열어볼 곳: `board.h:38`(`__USE_USERS_GPIO__` 주석 처리), `segcp.c:558-575,1253-1288`.
- 사실: 이 헤더 그대로면 `GA GB CA CB` 는 GET 공백·SET 무시다.
- 소스로 알 수 없는 것: 출하 이미지가 이 옵션으로 빌드됐는지.
- 선택지: (a) 같다 → 툴에서 GPIO 그룹을 숨김 / (b) 다르다(옵션 켠 빌드가 있음) → 그 빌드의 옵션 목록 제공.

**4. 현재 E-SAVE 출하 기준이 되는 소스**
- 열어볼 곳: 태그 `E-SAVE_1.0.0`(커밋 `42107e1`) 의 `port/configuration/inc/common.h:10-18,51-55`, `segcp.h:46-53`.
- 사실: 태그는 코드 버전 1.1.6, `PO`·`MB` 없음, `U3~U9` 있음(조건부), `main`(1.1.3)의 조상이 아니다.
- 선택지: (a) 이 태그가 출하 기준 → 툴 E-SAVE spec 에서 modbus 그룹 제거, `U3~U9` 와 버퍼 4096 반영 / (b) 다른 브랜치/저장소가 기준 → 그 위치 제공. `MAX_MESSAGE_HANDLERS` 가 어디서 정의되는지도 알려주시면 `CONFIG_BUF_SIZE` 를 확정할 수 있다.

**5. IP20 / W232N 의 펌웨어 저장소**
- 열어볼 곳: 이 저장소 전체에서 `IP20`·`W232N` 검색 결과 0건, `getting_started.md:3` 는 WIZ500/505/510SR-RP 만 명시.
- 선택지: (a) 다른 저장소(예: W55RP20 계열)의 파생 → 해당 저장소 위치 제공 / (b) 이 저장소의 별도 브랜치·비공개 포크 → 위치 제공. 툴 spec 의 `SD DD SE` 와 BR 0~19(IP20)는 이 소스로 검증되지 않는다.

---

## 11. 읽은 범위와 한계

- 정독: `segcp.c`(App 전체), `segcp.h`, `common.h`, `ConfigData.h/.c`(주요부), `board.h`, `deviceHandler.h`, `storageHandler.*`, `dnsHandler.c`(138-190), `deviceHandler.c`(563-606), `App_main.c`, `Boot_main.c`, `boot/segcp.c`(표·분기 목록·UDP부).
- 부분: `socket.c`(ioLibrary 고정 커밋 `ce4a7b6` 의 `sendto` 만), `util.c`(`is_ipaddr` 등 일부).
- 미열람: `seg.c`(데이터 경로), `SSLInterface.c`, mbedtls/pico-sdk, `MAX_MESSAGE_HANDLERS` 정의, Boot 의 `OC/LC/PK` 처리 세부.
- 계산 스크립트(작업용, 저장소 밖): `scratchpad/calc_resp.py`, `calc2.py`.
