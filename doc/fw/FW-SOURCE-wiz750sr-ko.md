# WIZ750SR 펌웨어 소스 정리 — SEGCP 설정 프로토콜 (설정툴 개발자용)

작성: 2026-10-20. 코드 수정·커밋·push 없음(읽기 전용 조사).

표기 규칙

- `[소스]` 직접 읽은 사실(커밋 2426dd6 기준). `[추정]` 읽은 것에서의 추론. `[git]` 이력 검색(`git log -S`) 결과.
- 담당자 발언·실기기 측정은 이 문서에 없다. 모르면 "미확인".
- 경로 약어: `S` = `Projects/S2E_App/src`, `B` = `Projects/S2E_Boot/src`, `segcp.c` = `S/Configuration/segcp.c`. 툴 쪽은 이 저장소 루트 기준(`specs/...`).

---

## 0. 핵심 요약 (먼저 읽을 것)

| # | 발견 | 근거 |
| --- | --- | --- |
| 1 | 네트워크(UDP/TCP) 모드에서 오류가 나도 뒤 명령은 계속 처리되고, 응답에 ER 줄은 없다. 그러나 요청 안에 오류가 하나라도 있으면 SV/RT/EX/FR/FW 가 통째로 취소된다(이미 바뀐 RAM 값은 롤백 안 됨). 알 수 없는 명령·VR/MN/MC(자기 OUI) SET 도 오류로 친다. | segcp.c:96, 1180-1193 |
| 2 | 응답 길이 검사가 전혀 없다. `gSEGCPREP[512]`. 툴 검색 목록 37개는 최악 413바이트(여유 있음)지만, GET 가능한 62개 전부를 한 요청에 담으면 최악 624 / 현실치 573 으로 512 를 넘는다. | segcp.c:630-639, common.h:68, 아래 §3 |
| 3 | `RH`(원격 호스트) 칸은 `dns_domain_name[49]` 인데 SET 은 `strcpy` 무검사. 49~63자를 보내면 오류 없이 옆 필드(`tcp_rcr_val`, `serial_command`, `serial_trigger`, user_io 등)를 덮는다. 툴 스펙은 128자까지 허용 중. | ConfigData.h:74, segcp.c:836-838, base.yaml:176 |
| 4 | 읽기/쓰기 권한 구분이 사실상 없다. `SEGCP_PRIVILEGE_SET`(0x80) 이 검사 마스크에 들어 있어, MA 를 `FF:FF:FF:FF:FF:FF` 로 보내도 SET/SV/RT 가 통과한다. `ERNOPRIVILEGE` 는 네트워크 경로에서 도달 불가. | segcp.h:97-100, segcp.c:641, 1232-1233 |
| 5 | UDP 응답은 항상 `255.255.255.255`(브로드캐스트), 목적 포트는 요청의 출발 포트. 또 MA 다음 줄에 `PW` 가 없거나 검색암호가 틀리면 응답이 아예 없다. | segcp.c:1245-1254 |

스펙(`specs/`)과 어긋난 점: 9건(+참고 3건) — §9.

---

## 1. 기준

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 저장소 | `https://github.com/Wiznet/WIZ750SR` (공개) | clone |
| 기본 브랜치 | `master` | `git branch -a` (`origin/HEAD -> origin/master`) |
| 읽은 커밋 | `2426dd66036848f4b085e9994a607480b75da1b0`, 2025-10-20 13:26:55 +0900, "Ver 1.4.5 - improve check mbtcp packet length" | `git log -1` |
| 최신 태그 | `v1.4.5` = `0b327bec1abd9a1e41cd2b7b0d68cdbb074b0465` (2025-10-13). 읽은 커밋은 태그보다 1커밋 뒤(`v1.4.5-1-g2426dd6`) | `git describe` |
| 두 커밋 차이 | `Modbus/mbtcp.c` 와 바이너리뿐. `segcp.c` 는 동일 | `git show --stat HEAD` |
| 읽은 App 버전 | MAJOR 1 / MINOR 4 / MAINT 5, `STR_VERSION_STATUS "Stable"` | common.h:10-15 |
| 다른 브랜치 | `BootV1.2`, `DIK`, `Develop`, `dev/modbus`, `TriggerCode` 등 존재. **읽지 않음(미확인)** | `git branch -a` |
| 태그 목록 | v1.1.0 ~ v1.4.5 (v1.2.x/v1.3.x 혼재) | `git tag` |

[소스] 이 저장소는 보드 하나를 `W7500x_board.h` 의 `DEVICE_BOARD_NAME` 으로 골라 빌드한다(W7500x_board.h:17-24). 커밋된 기본값은 `WIZ750SR`(:20). `WIZ750SR_1xx`, `WIZ750SR_T1L`, `W7500P_S2E`, `W7500_S2E` 는 같은 소스에서 매크로만 다르다(:41-97). 따라서 "WIZ750SR-1xx 소스"는 별도로 없고, 명령 집합은 §7 의 빌드 옵션 차이만 있다. 실제 배포 바이너리가 어떤 값으로 빌드됐는지는 **미확인**.

---

## 2. 프로토콜

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 포트 | UDP 50001, TCP 50001(listen). 펌웨어 업로드는 TCP 50002 | deviceHandler.h:12-13, segcp.c:1270, 1372-1379 |
| 소켓 | UDP = HW 소켓 1, TCP = HW 소켓 2, 데이터 = 소켓 0 | common.h:23-29 |
| 소켓 버퍼 | 소켓0 TX/RX 4KB, 소켓1~6 각 2KB | main.c:370-371 |
| 요청 버퍼 | `gSEGCPREQ[CONFIG_BUF_SIZE]` = **512** | common.h:68, segcp.c:32 |
| 응답 버퍼 | `gSEGCPREP[CONFIG_BUF_SIZE]` = **512** | segcp.c:33 |
| 데이터 경로 버퍼 | `g_send_buf[DATA_BUF_SIZE]`, `g_recv_buf[DATA_BUF_SIZE]` = **2048**. SEGCP 와 별개(시리얼↔이더넷 중계용). UART 수신 링버퍼는 `SEG_DATA_BUF_SIZE` 4096 | common.h:67, main.c:125-126, seg.h:15 |
| 같은 512 버퍼 공유자 | 검색암호가 비어 있으면 설정 웹서버가 `gSEGCPREQ/REP` 를 버퍼로 쓴다 | main.c:273-275, 커밋 6692556 메시지 |
| 요청 형식 | `MA` + MAC 6바이트 + CRLF(10바이트) → `PW` + 검색암호 + CRLF → 명령들(CRLF 구분). MAC 은 `FF`×6(브로드캐스트) 또는 장치 MAC | segcp.c:241-251, 1230-1252 |
| 응답 형식 | 요청의 `MA…`+`PW…` 줄을 그대로 앞에 붙이고, 이어 GET 응답(`명령 2자 + 값 + CRLF`)을 요청 순서대로 | segcp.c:1238-1252, 330-331, 637 |
| 요청 파싱 | `strtok(req, "\r\n")` 로 줄 분할. 줄의 앞 2글자를 명령표와 **접두 비교**(`strncmp`), 나머지가 값 | segcp.c:317, 228 |
| GET/SET 구분 | 값이 빈 줄(`MC\r\n`)이면 GET, 값이 있으면 SET | segcp.c:328, 641 |
| 요청 끝 처리 | 마지막 바이트를 무조건 NUL 로 덮는다(끝이 `\n` 이라고 가정) | segcp.c:1229, 1324 |
| 비밀번호 | `PW` 값이 `pw_search` 와 같아야 처리. 빈 검색암호는 `PW ` + 공백(`SEGCP_NULL`)로 보낸다. 틀리면 **무응답** | segcp.c:1247 |
| MAC 불일치 | 무응답 | segcp.c:1234 |
| 유니캐스트 응답 | UDP 는 **항상 브로드캐스트**: `sendto(..., "\xFF\xFF\xFF\xFF", destport)` — 요청이 유니캐스트여도 응답은 255.255.255.255:요청 출발포트 | segcp.c:1254 |
| TCP 응답 | 연결된 소켓으로 `send` | segcp.c:1349 |
| TCP 유지 | 연결 후 15초마다 keep-alive 송신(TCP 유니캐스트 검색용) | segcp.h:102, segcp.c:1313-1317, 1481-1494 |
| 처리 시점 | `do_segcp()` 가 메인 루프마다 UDP→TCP 순서로 1회씩. DHCP/DNS 진행 중에도 호출 | segcp.c:84-94, main.c:285, 462, 530 |
| 응답이 먼저, 동작은 나중 | 응답 `sendto` 는 `proc_SEGCP_udp` 안에서 끝난 뒤, `do_segcp()` 가 SV/RT/FW 를 수행한다 | segcp.c:1254 → 96-213 |
| TCP 검색은 App·Boot 둘 다 | Boot 도 `__USE_APPBOOT_TCP_SEARCH__` 로 TCP 지원 | B/Configuration/segcp.c:58-60, W7500x_board.h:36 |

[소스] 권한: `gSEGCPPRIVILEGE` 는 MA 가 `FF`×6 이면 `0x80`(SET|READ), 장치 MAC 이면 `0x88`(SET|WRITE) 로 정해진다(segcp.c:1232-1233). 그런데 GET 이 아닌 SET·SV·RT 등의 검사식이 `gSEGCPPRIVILEGE & (SEGCP_PRIVILEGE_SET|SEGCP_PRIVILEGE_WRITE)` 이고 `SET`=0x80 이므로(segcp.h:97-100, segcp.c:559, 641) 0x80 만 있어도 참이다. [추정] 따라서 네트워크 경로에서 `ERNOPRIVILEGE`(segcp.c:1171) 는 나오지 않는다. 시리얼(AT) 모드는 처음부터 WRITE 권한(segcp.c:1402).

---

## 3. 응답 길이 보호

### 3.1 검사 유무

[소스] **없다.** 확인한 경로:

- 응답 쓰기: `proc_SEGCP` 의 GET 분기는 `sprintf(trep, …)` + `strcat(trep, "\r\n")` 으로 `trep` 를 계속 전진시킨다. `gSEGCPREP` 끝(512)과의 비교 구문 없음(segcp.c:333-639).
- 요청 읽기: `recvfrom(SEGCP_UDP_SOCK, treq, len, …)` 의 `len` 은 소켓 수신 대기량(`getSn_RX_RSR`)이고 512 상한 없음(segcp.c:1224-1228). TCP 도 동일(:1319-1323). ioLibrary 는 길이 인자를 패킷 크기에만 맞춘다(`ioLibrary/Ethernet/socket.c:501-508`, 코드 주석 "Need to packet length check").
- 송신: `sendto` 는 길이를 **소켓 TX 크기(2KB)** 로만 자른다(socket.c:404-405). 512 와 무관.
- `memset(trep, 0, sizeof(trep))` 의 `trep` 는 포인터라 4바이트만 지운다(segcp.c:316, `char * trep` 선언 :298). 응답 영역 전체를 비우는 코드는 아니다. 길이는 `strlen` 으로 구하므로 NUL 종단에 의존한다(segcp.c:1254).
- 보호 매크로(`#if`)로 감싼 길이 검사도 못 찾음(`grep BUF_SIZE` 전수 확인: segcp.c 에서는 배열 선언 두 줄뿐).

[추정] 512 를 넘으면 `gSEGCPREP` 뒤 메모리를 덮는다. 뒤에 무엇이 있는지는 링커 맵이 저장소에 없어 **미확인**(§10 Q3).

### 3.2 최악 응답 크기

모델: 응답 = 헤더(MA 10 + PW줄 `4+PW길이`) + Σ(명령 2 + 값 + CRLF 2). 검색암호 없음이면 PW줄 5 → 헤더 15. 검색암호 9자면 헤더 23.

| 가정한 값 최대 길이 | 명령 |
| --- | --- |
| 17 | MC |
| 21 | DH(`module_name`14 + `-` + 6) |
| 15 | LI SM GW DS |
| 14 | MN |
| 11 (실제 `1.4.5`=5. 접미 "A"/"dev"/사용자정의 대비 과대) | VR |
| 10 | UN(`RS-232/TTL`, `RS-422/485`) |
| 9 | NP SP |
| 7 | ST(`CONNECT`) |
| 6 | SS |
| 5 | KI KE RI LP RP IT PT FP |
| 48 (정상 SET 가정) | RH (도메인 모드. IP 모드는 15) |
| 18 / 31 | FD / FH |
| 4 | DP(3030), GA GB GC GD |
| 3 | PS TR |
| 2 | BR PD SC |
| 1 | 그 외 |

| 요청한 GET 집합 | 개수 | 최악(검색암호 없음) | 현실치 | 512 초과 |
| --- | --- | --- | --- | --- |
| 툴 검색 목록(`search_cmd_order`, WIZ750SR.yaml:12-49) | 37 | **413** (검색암호 9자면 +8 = 421) | 339 | 아니오 |
| 위 + GA GB GC GD CA CB CC CD | 45 | 465 (+8 = 473) | - | 아니오 |
| 위 + EC MB UI | 48 | 480 (+8 = 488) | - | 아니오(여유 24) |
| 표에 있는 GET 가능 62개 전부 | 62 | **624** | 573 | **예** |

- 계산 [추정]: 값 길이 가정은 위 표, 계산은 `Σ(4+len)+15`. 실측 아님.
- GET 가능 62개 = 표 76개에서 NOTAVAIL/NOPARAM(LG ER MA PW FW BU) 6, 동작 명령(SV EX RT FR K! AB) 6, 부작용 명령(RX FS) 2 를 뺀 수.
- 검색 목록만으로는 여유가 있지만, 향후 명령(EC·MB·GPIO 등)을 더 얹으면 480 대까지 간다. RH 도메인이 49자 이상으로 들어가 있으면(§4) 그 길이만큼 더 늘어난다.

---

## 4. 문자열 필드 — 칸 크기와 SET 검사

구조체: `DevConfig` 는 `__attribute__((packed))`(ConfigData.h:103-116). 아래 "최대 글자 수" 는 NUL 1칸을 뺀 값.

| 명령 | 칸 | 크기 | 최대 글자 수 | 검사 | SET 동작 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| MN | `module_name` | 15 | (SET 불가) | - | `ERIGNORED` | ConfigData.h:106, segcp.c:649-651 |
| DH | `module_name` (MN 과 같은 칸) | 15 | **14** | 있음 | 초과 시 `ERINVALIDPARAM`(거부). 정상이면 `module_name` 을 **덮어씀**. 첫 글자 공백이면 비움 | segcp.c:801-814 |
| NP | `pw_connect` | 10 | **9** | 있음 | 초과 시 거부. 첫 글자 공백이면 비움 | ConfigData.h:68, segcp.c:930-940 |
| SP | `pw_search` | 10 | **9** | 있음 | 초과 시 거부. 첫 글자 공백이면 비움 | ConfigData.h:69, segcp.c:941-951 |
| RH (도메인) | `dns_domain_name` | 49 | **48** | **없음** (`strcpy`) | 49자 이상이면 오류 없이 뒤 필드 덮어씀. 64자 이상이면 스택 `param[64]` 도 넘침(§4.1) | ConfigData.h:74, segcp.c:836-838 |
| RH (IP) | `remote_ip[4]` | 4 | IP 7~15자 | `is_ipaddr` | 실패하면 위 도메인 분기로 감 | util.c:8-48, segcp.c:826-839 |
| PW(요청 줄) | 임시 `tpar` | UDP 64 / TCP 33 | UDP 63 / TCP 32 | **없음**(`\r` 까지 복사) | 길면 스택 넘침 | segcp.c:254-262, 1216, 1287 |
| MC | `mac[6]` | 6 | 17(`XX:XX:XX:XX:XX:XX`) | `is_macaddr` | 구분자 `.:-` 허용. 자기 MAC 이 `00:08:DC` 로 시작하면 `ERIGNORED` | util.c:77-104, segcp.c:645-648 |
| PI PP DI DW | (없음) | - | 무제한 | 없음 | 받기만 하고 버림(no-op) | segcp.c:755-800 |
| FD FH | 상수 문자열 | - | - | - | SET `ERINVALIDPARAM`. GET 은 `device.wizwiki.net` / `/wiz750sr/fw/W7500x_S2E_App.bin` | segcp.c:536-556, 1086-1096, ConfigData.h:18-19 |

"공백으로 비우기": NP/SP/DH/RH 는 값의 **첫 글자가 공백**이면 빈 문자열로 처리한다(segcp.c:805, 837, 937, 948). 따라서 공백으로 시작하는 비밀번호는 저장할 수 없고 "지우기"가 된다. [소스]

### 4.1 입력 파서의 고정 크기 버퍼

- `parse_SEGCP` 가 값을 `strcpy(param, &pmsg[2])` 로 복사한다. 호출자의 `param[SEGCP_PARAM_MAX*2]` = 64바이트(segcp.c:270, 311, segcp.h:16). 값이 64자 이상이면 스택 넘침. 길이 검사 없음. [소스]
- 그래서 RH 의 실제 위험 구간은 두 겹이다. 49~63자: 오류 없이 `DevConfig` 안 이웃 필드 손상(뒤따르는 필드: `tcp_rcr_val`, `serial_command`, `serial_command_echo`, `serial_trigger[3]`, 그다음 `user_io_info`). 64자 이상: 스택 넘침. [소스+추정: 필드 순서는 ConfigData.h:67-79, 손상 결과는 추정]
- 공장 초기화 코드도 `memset(dns_domain_name, 0, 50)` 으로 49칸 배열에 50바이트를 쓴다(ConfigData.c:112). 직후 `tcp_rcr_val` 을 8 로 다시 채우므로(:115) 영향은 없다. [소스]

### 4.2 숫자 필드의 입력 검사 특성 (툴이 알아둘 것)

- `atol`/`atoi` 사용 필드(KI KE RI LP RP IT PT PS BR TR MB CA~CD FP)는 **숫자가 아닌 문자열도 0 으로 읽어 통과**한다. 예: `BR` 값 `x` → 0(300bps). 자릿수 검사는 BR(≤2자)·PS(≤3자)·TR(≤3자)·MB(≤2자)에만 있다. [소스] segcp.c:697-711, 816-824, 842-846, 887-901, 1110-1113, 1141-1148
- 상한: KI KE RI LP RP IT PT 는 0~65535(`> 0xFFFF` 거부, 음수는 uint32 변환으로 거부). PS 0~255, TR 1~255, BR 0~14, MB 0~2, DG 0~4. [소스]
- 1자리 열거형(IM OP CP DG KA DB PR SB FL TE EC)은 `is_hex(*param)` 로 검사한다. `is_hex` 는 구현이 틀려서, 숫자 `0`-`9` 외에 ASCII `Q`~`` ` ``(0x51~0x60)가 0~15 로 해석된다(예: `IM` 값 `R` → 1). 소문자 `a`~`f` 는 16 이상이라 거부. 툴이 숫자만 보내면 영향 없다. [소스] util.c:63-74
- IP: `is_ipaddr` 는 길이 7~15, 숫자와 `.` 만, 각 옥텟 ≤255, 점 ≤4개만 본다. 옥텟 개수는 안 센다(예: `1.2.3....`). 점이 4개면 `ret_ip[4]` 에 한 바이트 넘쳐 쓴다. 툴 스펙의 IP 정규식이 더 엄격하므로 툴 경유 입력은 문제없다. [소스] util.c:18-47
- 16진 필드: PD 정확히 2자 hex, SS 정확히 6자 hex(둘 다 대소문자 허용). SC 는 `str_to_hex` 로 1바이트 hex 로 읽는다(`11`→DTR=1,DSR=1). 1자만 보내면 `str_to_hex` 가 실패하는데도 검사를 통과하고 직전 명령이 남긴 `tmp_byte` 를 쓴다. [소스] segcp.c:902-929, 1036-1049, util.c:107-130

---

## 5. 오류 처리

### 5.1 설정툴(UDP/TCP) 모드 결론

| 질문 | 답 | 근거 |
| --- | --- | --- |
| 오류 후 뒤 명령도 처리하나 | **예.** 오류 시 즉시 반환하는 코드는 `opmode == DEVICE_AT_MODE`(시리얼)일 때만 실행된다. 네트워크 요청은 `strtok` 로 다음 줄로 계속 간다 | segcp.c:1180-1193 |
| 응답에 ER 줄이 실리나 | **아니오.** `ERINVALIDPARAM:BR` 형태의 줄은 AT 모드 블록 안에서만 만든다 | segcp.c:1182-1186 |
| 오류가 나면 SV/RT 는 | **취소된다.** 오류 비트(0x8000)가 `ret` 에 한 번이라도 서면 `do_segcp` 의 처리 블록(`SWITCH/FACTORY/SAVE/ERASE/FWUP/REBOOT`)을 통째로 건너뛴다 | segcp.c:96, 84-94 |
| 취소 범위 | SV 뿐 아니라 RT, EX, FR, K!, AB, FW, BU 모두. 응답은 이미 나갔으므로 툴은 "응답은 왔는데 저장 안 됨" 으로 본다 | segcp.c:1254 → 96 |
| 이미 처리한 SET 은 | **롤백 없음.** `dev_config` RAM 에 이미 반영되어 즉시 동작에 쓰이고(OP 는 소켓 종료까지 수행: segcp.c:666), 이후 별도 요청의 SV 로 저장될 수 있다 | segcp.c:652-668 등 |
| 한 요청 안 GET 응답은 | 오류·SV·RT·EX·FR·AB 처리 **이전**에 이미 쓰인 응답은 **남는다**. **이후** GET 응답은 쓰이지 않는다 | segcp.c:630-639 |

GET 응답이 사라지는 원리 [소스]: `ret` 는 요청 한 개 안에서 누적된다(segcp.c:300 선언, 각 case 에서 `|=`). 각 GET 끝에서 `ret & (ERR|REBOOT|SWITCH|SAVE)` 가 참이면 방금 쓴 2글자 명령 자리를 되돌리고 NUL 을 쓴다(`trep -= 2; *trep = 0`, :630-634). 한 번 참이 되면 그 뒤 모든 GET 이 같은 이유로 버려진다. 앞선 응답은 지우지 않는다. 마스크에 `FWUP`(0x40)·`FACTORY`(0x08) 단독은 없으나 FR 은 `REBOOT` 를 같이 세우므로(:589, 593) 동일하게 작동한다.

권고 순서 [추정]: 한 요청에서 `GET…` → `SET…` → `SV` → `RT` 순으로 보내야 GET 응답이 살아남는다. SET 중 하나라도 오류면 SV 가 취소되므로, 저장 성공 여부는 응답이 아니라 **재조회(GET)로 확인**해야 한다(ER 줄이 없어서 원인도 알 수 없다).

### 5.2 오류를 만드는 입력 (SV 취소 유발)

| 입력 | 오류 | 근거 |
| --- | --- | --- |
| 형식·범위 위반 SET | `ERINVALIDPARAM` | §4.2 |
| VR, MN SET | `ERIGNORED` | segcp.c:649-651 |
| MC SET (자기 MAC 이 `00:08:DC…`) | `ERIGNORED`. 툴이 전체 설정에 `MC` 를 섞어 보내면 SV 가 취소된다 | segcp.c:646 |
| 읽기 전용 SET (UN ST LG ER MA EX SV RT FR PW UI AB) | `ERNOTAVAIL`. 즉 `SV` 에 값을 붙여 보내면 오류 | segcp.c:1150-1163 |
| S0 S1 RX FS FD FH SET | `ERINVALIDPARAM` | segcp.c:1058-1071, 1086-1096 |
| GET: LG ER MA PW | `ERNOTAVAIL` | segcp.c:471-475 |
| GET: FW, BU | `ERNOPARAM` | segcp.c:476-477, 619 |
| GET: GA~GD 인데 해당 I/O 가 꺼져 있음 | `ERNOTAVAIL` | segcp.c:485-486 |
| 명령표에 없는 명령(예: 다른 기종 전용 명령) | `ERNOCOMMAND`(응답 줄 없음) | segcp.c:1174-1177 |
| GPIO 명령인데 `__USE_USERS_GPIO__` 미정의 | `ERNOCOMMAND` | segcp.c:624-627, 1164-1166 |

AT(시리얼) 모드의 오류: 첫 오류에서 중단하고 `ER…:명령` 줄을 쓴 뒤 UART 수신 버퍼를 비운다(segcp.c:1180-1192). 시리얼 요청 버퍼는 `segcp_req[64]` 로 줄 하나가 63자까지(segcp.c:1395-1399).

---

## 6. 빈 값 GET, 미구현 명령

### 6.1 빈 값 GET 응답 모양

[소스] 값이 비어 있으면 **공백 한 글자**(`SEGCP_NULL = ' '`, segcp.h:57)를 값으로 보낸다. 즉 `NP`+공백+CRLF.

| 명령 | 비었을 때 | 근거 |
| --- | --- | --- |
| NP SP | `pw_*[0]==0` → 공백 | segcp.c:464, 468 |
| RH | `dns_use` 켜짐 & 도메인 비음 → 공백 (IP 모드는 항상 점표기) | segcp.c:437 |
| DH | `module_name[0]==0` → 공백, 아니면 `이름-XXXXXX` | segcp.c:422-423 |
| PI PP DI DW | 항상 공백(no-op) | segcp.c:400, 405, 414, 419 |
| FD FH | 매크로 미정의 시 공백 | segcp.c:540, 551 |

주의 [소스]: `RH` 에 공백을 SET 하면 IP 로 해석되지 않아 `dns_use = ENABLE` 이 되고 도메인이 비워진다(segcp.c:826-838). 이후 GET 은 공백.

### 6.2 미구현·no-op 명령

| 명령 | GET | SET | 근거 |
| --- | --- | --- | --- |
| DD | `0` | 0/1 검사만, 저장 안 함 | segcp.c:365, 670-675 |
| PO | `0` | 0/1 검사만, 저장 안 함 | segcp.c:367, 676-681 |
| DX | `0` | 아무것도 안 함(항상 성공) | segcp.c:408, 773-777 |
| DP | `3030`(상수) | 아무것도 안 함 | segcp.c:411, 778-782 |
| PI PP DI DW | 공백 | 아무것도 안 함 | segcp.c:755-800 |
| UE | `0` | 0/1 검사만 | segcp.c:607-609, 1104-1108 |
| FC FP | 현재값 | 저장(FC 0/1, FP ≤65535) | segcp.c:528-534, 1073-1083 |
| FD FH | 상수 | `ERINVALIDPARAM` | 위 §6.1 |
| FS | **GET 이 동작 실행**(서버 FW 업데이트 플래그 켜고 소켓 종료) | `ERINVALIDPARAM` | segcp.c:516-526, 1069-1071 |
| RX | GET 이 UART 수신 버퍼 flush 후 `FLUSH` | `ERINVALIDPARAM` | segcp.c:510-514, 1064-1066 |
| LG ER MA PW | `ERNOTAVAIL` | `ERNOTAVAIL` | §5.2 |
| FW BU | `ERNOPARAM` | 크기 검사 후 업로드 준비(응답에 `FW<ip>:<port>` / `BU…`) | segcp.c:952-984, 1116-1139 |

SET 이 아닌 **GET 형식으로 동작하는 명령**(값 없이 보냄): `SV EX RT FR AB K!` 와 `FS RX`. 이들은 값을 붙이면 `ERNOTAVAIL` 이 된다. 특히 `K!`(명령표 문자열)는 권한 검사 없이 `ERASE_EEPROM | REBOOT` 를 세워 **MAC 과 설정 섹터를 지우고 재부팅**한다(segcp.c:604-606). `FR` 은 정상 권한이면 공장 초기화+재부팅, 단 `local_port == 1` 이면 `K!` 와 같은 삭제(segcp.c:583-600). [소스]

---

## 7. 명령 목록과 빌드 옵션별 차이

명령표: App 76개(segcp.c:38-45, segcp.h:20-27), Boot 58개(B/Configuration/segcp.c:32-37).
"태그"는 해당 명령의 `case` 를 처음 추가한 커밋을 담은 가장 이른 태그([git], `git log -S"case SEGCP_xx"`). 표시 없는 것은 v1.1.0 이전부터 있음(추정).

| 명령 | GET 값 | SET 검사 | Boot | 비고 |
| --- | --- | --- | --- | --- |
| MC | MAC `XX:XX:XX:XX:XX:XX` | §4 | O | 아래 §8 MAC 저장 주의 |
| VR | 버전 문자열 | ERIGNORED | O | §8 |
| MN | `module_name` | ERIGNORED | O | |
| IM | 0/1 | 0~1 | O | |
| OP | 0~3 | 0~3, 바꾸면 데이터 소켓 종료 | O | Boot 은 소켓 종료 없음 |
| DD PO DX DP DI DW PI PP | §6.2 | no-op | O | |
| CP | 0/1 | 0~1 | O | |
| DG | 0~4 | 0~4 (`SEG_DEBUG_ALL`=4) | O (SET 은 0~1만) | seg.h:44-50, B segcp.c:504 |
| KA | 0/1 | 0~1 | O | |
| KI KE RI | 정수 | 0~65535 | O | |
| LI SM GW DS | 점표기 | `is_ipaddr` | O | |
| DH | `이름-XXXXXX` | §4 (module_name 덮어씀) | O | Boot GET 은 소문자 hex |
| LP RP | 정수 | 0~65535 | O | |
| RH | IP 또는 도메인 | §4 | O | |
| BR | 0~14 | 0~14 (`baud_460800`=14) | O | 추가 2018-02(주석) |
| DB PR SB | 0/1, 0~2, 0/1 | 0~1, 0~2, 0~1 | O | 9비트(2) 거부 |
| FL | 0~4 | 0~4. RS-422/485 일 때 3·4 아니면 **0 으로 바꿔 저장(오류 없음)** | O | segcp.c:862-886 |
| IT PT | 정수 | 0~65535 | O | IT 단위는 **초**(§9 #4) |
| PS | 0~255 | 0~255 | O | |
| PD | 2자 hex | 2자 hex. `00` 이면 delimiter_length=0 | O | |
| TE | 0/1 | 0~1 | O | |
| SS | 6자 hex | 6자 hex | O | |
| NP SP | 문자열/공백 | §4 | O | |
| LG ER MA PW | `ERNOTAVAIL` | `ERNOTAVAIL` | O | MA/PW 는 요청 머리말 |
| FW | `ERNOPARAM` | 크기 검사 후 업로드 준비 | O | 상한 §8 |
| SV EX RT FR K! AB | 동작 | `ERNOTAVAIL` | O | AB: App `ST_BOOT` 저장+재부팅 / Boot `ST_OPEN` 저장+재부팅. AB v1.1.1 |
| UN | 문자열 `RS-232/TTL`/`RS-422/485` | `ERNOTAVAIL` | O | |
| UI | 0/1 | `ERNOTAVAIL` | O | |
| ST | `BOOT/OPEN/CONNECT/UPGRADE/ATMODE/UDP` | `ERNOTAVAIL` | O | segcp.c:35 |
| EC | 0/1 | 0~1 | O | |
| UE | `0` | 0~1 | O | |
| SC | 2자리 `DTR,DSR` | §4.2 | O | Boot 은 핀 초기화 없음. v1.1.0 |
| TR | 1~255 | 1~255 | O | **v1.2.0** |
| GA GB GC GD | I/O 값(디지털 0/1, 아날로그 ≤4자리) | 0/1. **디지털 출력 핀이 아니면 `ERINVALIDPARAM`** | X | `__USE_USERS_GPIO__`. v1.1.0 |
| CA CB CC CD | 0~2(`type<<1 | dir`) | 0~2, 3(아날로그 출력) 거부 | X | `__USE_USERS_GPIO__` |
| S0 S1 | 핀 상태 | `ERINVALIDPARAM` | X | v1.1.0 |
| RX | `FLUSH`(부작용) | `ERINVALIDPARAM` | X | |
| FS FC FP FD FH | §6.2 | | X | `FWUP_SERVER_*` 상수 |
| BU | `ERNOPARAM` | AppBoot 이미지 크기 ≤ 28KB(`DEVICE_BOOT_SIZE`) | X | **v1.2.0** |
| MB | 0~2 | 0~2(`MODBUS_NONE/RTU/ASCII`) | X | **v1.4.4** (2025-09-24, "Add Modbus RTU / ASCII") |

### 7.1 `#if` / 빌드 옵션

| 옵션 | 정의 위치 | 영향 | 근거 |
| --- | --- | --- | --- |
| `DEVICE_BOARD_NAME` | W7500x_board.h:17-24 | 보드별 옵션 묶음 선택. 기본 `WIZ750SR` | |
| `__USE_USERS_GPIO__` | 알려진 보드 전부 정의(:33, 47, 61, 76, 90). **마지막 `else`(알 수 없는 보드, :98-110)에는 없음** | 없으면 GA~GD·CA~CD 가 GET/SET 모두 `ERNOCOMMAND`. 공장값의 user_io 도 달라짐 | segcp.c:478, 987, ConfigData.c:123-133 |
| `__USE_APPBACKUP_AREA__` | 알려진 보드에서 모두 **주석 처리**(:31, 45, 59, 74, 88, 101). 보드 미정의 분기(:112)만 켜짐 | 켜면 VR 값 끝에 `A`(예 `1.4.5A`), App 50KB+백업 50KB, FW 상한 51200, `FS` 서버 업데이트 가능. 끄면 App 100KB, FW 상한 102400 | segcp.c:342-346, 954-958, deviceHandler.h:22-26 |
| `__USE_SAFE_SAVE__` | 알려진 보드 전부 정의 | SV 시 쓰고→읽어 비교→최대 5회 재시도, **매 시도 후 1초 대기** → SV 처리 최소 1초 이상 블록 | ConfigData.c:187-213, ConfigData.h:22-23 |
| `__USE_DSR_DTR_DEFAULT__` | 전부 주석 처리 | 공장값 SC 가 `11`(켜짐) vs `00` | ConfigData.c:89-95 |
| `__USE_UART_IF_SELECTOR__` | WIZ750SR, W7500P_S2E 만 정의 | UART 인터페이스를 핀으로 판별. 아니면 고정(`UART_IF_DEFAULT`) | W7500x_board.h:28, 43 |
| `__USE_TCPCONNECT_STATUS_PIN__` | WIZ750SR_1xx, T1L 만 | 상태 핀이 TCP 연결 표시 | W7500x_board.h:65, 80 |
| `__USE_APPBOOT_TCP_SEARCH__` | 전부 | Boot 의 TCP 검색 | |
| `STR_VERSION_STATUS` | common.h:15 (`"Stable"`) | `Stable`→접미 없음, `Develop`→`dev`, 그 외 문자열→그대로 붙임 | segcp.c:340-357 |
| `FWUP_SERVER_DOMAIN/BINPATH` | ConfigData.h:18-19 | FD/FH GET 값 | |

[소스] 위 중 WIZ750SR 과 WIZ750SR_1xx 에서 SEGCP 명령 **집합**을 가르는 옵션은 없다(둘 다 GPIO 정의). 차이는 핀 매핑(W7500x_board.h:143-218)과 UART IF 선택뿐이다.

### 7.2 Boot 가 App 과 다른 점

- 명령표가 짧다: GA~GD CA~CD S0 S1 RX FS FC FP FD FH BU MB 없음(B/Configuration/segcp.c:32-37). 이들은 Boot 에서 `ERNOCOMMAND`.
- DG SET 이 0~1 만(B segcp.c:504). VR 은 `Develop`→`dev`, 그 외는 접미 없이 숫자만(:248-257). DH GET 은 소문자 hex(:325).
- Boot 의 `do_segcp` 에는 UART(AT) 명령 처리가 없고, 오류 줄(`ER…`)을 만드는 블록도 주석 처리되어 있다. [소스] B/Configuration/segcp.c:50-127 (`do_segcp`), 같은 파일 `proc_SEGCP` 끝부분의 `/* if(ret & SEGCP_RET_ERR) … */` 블록
- 오류 비트가 있으면 `else if(segcp_ret)` 에 못 들어가 SV/RT/FW 가 취소되는 구조는 App 과 같다(B segcp.c:62-66).
- 메모리 배치와 버전은 §8.

---

## 8. Boot/App 구조, 버전, 설정 저장

### 8.1 구조

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 칩 | W7500P (Cortex-M0), 내장 플래시 IROM 0x00000000~0x3FFFF(256KB) | S2E_App/W7500x_S2E.uvprojx:21, 251-255 |
| Boot | 0x0000 부터 28KB(`DEVICE_BOOT_SIZE`) | deviceHandler.h:21, 28 |
| App | 0x7000 부터. 100KB(백업 미사용) 또는 50KB+백업50KB(`__USE_APPBACKUP_AREA__`) | deviceHandler.h:22-26, 33, 39 |
| 설정 저장 | 데이터 플래시: MAC = DAT0 `0x3FE00`, 설정 = DAT1 `0x3FF00`. 각 256바이트 | deviceHandler.h:43-44, flashHandler.h:26-31 |
| 플래시 단위 | 섹터 256B, 블록 4KB. 설정 쓰기는 섹터 지우기 → 쓰기 | flashHandler.h:17-18, storageHandler.c:80-85, 127-130 |
| `DevConfig` 크기 | 250바이트(packed 필드 합) — 칸 256B 안에 들어감 | [추정] ConfigData.h:27-116 를 합산(23+18+28+9+82+8+7+74+1 = 250) |
| Boot→App 점프 | App 첫 워드가 `0xFFFFFFFF` 가 아니고, `state != ST_BOOT`, 부트 진입 핀이 아니면 점프 | B/main.c:204-241 |
| Boot 에 머무는 경우 | App 없음, 부트 핀 Low, 또는 App 의 `AB` 명령(상태 `ST_BOOT` 저장 후 재부팅) | B/main.c:226-236, segcp.c:610-616 |
| Boot 진입 후 | RAM 상태 `ST_BOOT` → `ST` GET = `BOOT` | B/main.c:248 |
| Boot 의 버전 | Boot 도 `S/common.h`, `S/Configuration/ConfigData.c` 를 컴파일에 포함(include path `..\S2E_App\src`). 즉 Boot 의 `VR` 은 **Boot 를 빌드한 시점의 common.h** 값 | B/W7500x_S2E.uvproj:382, 603-605 |
| Boot/App 호환 | README: Boot 1.2 + App 1.2.x/1.3.x 동작, Boot 1.3 + App 1.2.x **동작 안 함** | README.md "Caution" |

### 8.2 버전 문자열

[소스] App `VR` = `fw_ver` 3바이트를 `%d.%d.%d` 로 찍는다. `fw_ver` 는 부팅 때 매크로로 덮는다(ConfigData.c:165-167). 접미: `Stable`+백업영역 미사용 → 없음(`1.4.5`), 백업영역 사용 → `A`, `Develop` → `dev`, 그 외 → `STR_VERSION_STATUS` 그대로(segcp.c:339-358). 읽은 소스는 `1.4.5` 를 낸다. README 의 "latest F/W version" 은 `v1.4.0` 으로 낡아 있다(README.md "latest F/W version(Boot v1.4)"). [소스]

### 8.3 설정 저장 방식

- `SV` → `save_DevConfig_to_storage`: 구조체 전체(250B)를 DAT1 섹터에 쓴다. `__USE_SAFE_SAVE__` 면 읽어 비교하고 다르면 최대 5회 재시도하며 매번 1초 대기(ConfigData.c:185-214). 플래시 쓰기 전후로 `flash_update_start/end` 호출(segcp.c:112-114).
- 부팅 때 `packet_size` 가 `0x0000` 또는 `0xFFFF` 면 공장값을 만들어 기록(ConfigData.c:160-163). `K!`/`FR(local_port=1)` 이 설정 섹터를 지운 뒤 재부팅하면 이 경로로 공장값이 된다. [소스]
- **MAC**: 부팅 때 설정 로드 직후 DAT0 의 MAC 6바이트로 `mac` 을 덮어쓴다(ConfigData.c:157-158). App 안에서 `write_storage(STORAGE_MAC…)` 를 호출하는 곳이 **없다**(grep 결과: App 은 읽기와 `erase_storage(STORAGE_MAC)` 뿐). Boot 은 DAT0 이 비었을 때(`FF`) UART 로 "INPUT FIRST MAC?" 를 받아 기록한다(B/main.c:500-523). [소스] 그러므로 [추정] 네트워크로 `MC` 를 바꾸고 `SV` 해도 재부팅하면 DAT0 의 MAC 으로 돌아간다(미검증).
- FW 업로드 크기 상한: 백업 미사용 `0x19000`=102400B(`DEVICE_FWUP_SIZE & 0x19000`), 백업 사용 `0xC800`=51200B(`& 0x0FFFF`). 주석은 "64KByte" 라고 되어 있으나 계산값은 51200(segcp.c:954-958).

---

## 9. 툴 스펙과의 대조

대상: `specs/devices/WIZ750SR.yaml`, `specs/devices/WIZ750SR-1xx.yaml`(`command_groups`: base, retransmit, gpio, ddns, pppoe — 둘 다 같음), `specs/commands/*.yaml`. 두 장치 yaml 의 `overrides` 는 NP·BR 에 한해 동일(WIZ750SR.yaml:61-86, 1xx:63-85; WIZ750SR.yaml 만 `TR.min_version` 추가).

### 9.1 어긋난 점 (9건)

| # | 명령 | FW (파일:줄) | 스펙 (파일:줄) | 방향 | 영향 |
| --- | --- | --- | --- | --- | --- |
| 1 | RH | 도메인 칸 49 → 안전 최대 48자, 검사 없음 (ConfigData.h:74, segcp.c:836-838) | 최대 128자 허용. 주석이 "FW DNS_DOMAIN_SIZE와 일치" 라 적혀 있으나 750SR 에는 해당 안 됨 (base.yaml:173-176). 장치 override 없음 (WIZ750SR.yaml:61-86) | **스펙이 느슨** | 49자 이상은 FW 가 오류 없이 이웃 필드 손상. 64자 이상은 스택 넘침(§4.1) |
| 2 | SP | `pw_search[10]` → 최대 9자, 초과 시 거부 (ConfigData.h:69, segcp.c:941-944) | `regex: ""` 무제한 (base.yaml:459-471). NP 만 override (WIZ750SR.yaml:64-65, 1xx:66-67) | **스펙이 누락** | 10자 이상 SP 는 거부 → SV 전체 취소(조용한 실패) |
| 3 | BR | 0~14, 14=460800. 보드가 460800 테이블을 갖고 있음 (segcp.c:844, uartHandler.h:76, uartHandler.c:51) | 0~13 (WIZ750SR.yaml:70-71, 1xx:69-70). base 는 0~15 (base.yaml:246) | 스펙이 엄격(14 빠짐) — **의도된 값, 어긋남 아님** | 제품 사양이 230400 까지("Up to 230kbps", docs.wiznet.io)라 0~13 이 맞다. 2026-07-15 담당자 확인으로 확정(`research/2026-07-15-security-device-baudrate-spec-verification.md`, 메모리 `fw_br_baudrate_limits`). FW 능력(14까지)과 제품 사양은 별개. 참고: base 의 15(921600)는 FW 가 거부하므로 override 가 없는 기종에선 반대로 느슨 |
| 4 | IT | 단위 **초**: `seg_timer_sec` 에서 증가 (seg.c:1740-1745, ConfigData.c:66 주석 "sec") | 라벨 "(ms)" (base.yaml:385, 393) | **단위 표기 불일치** | 값 범위(0~65535)는 일치. 사용자가 ms 로 오해 |
| 5 | TR | 1~255 전부 허용 (segcp.c:1110-1113) | `2[0-5][0-5]` 정규식 때문에 206~209, 216~219, 226~229, 236~239, 246~249 (20개 값) 거부 (retransmit.yaml:16) | **스펙이 엄격(정규식 오류)** | 해당 값을 툴에서 입력 불가. `^(25[0-5]|2[0-4][0-9]|…)` 로 고쳐야 함 |
| 6 | DH | GET `이름-XXXXXX`, SET 은 `module_name`(≤14, 초과 거부)을 덮어씀 (segcp.c:421-424, 801-814) | "DDNS Domain Host", `regex: ""` 무제한 (ddns.yaml:85-97). 750SR 은 ddns 그룹 포함 (WIZ750SR.yaml:58) | **의미 불일치 + 길이 누락** | 화면에 노출되지 않아(주석 WIZ750SR.yaml:55-57) 현재 영향 작음. SET 하면 장치 이름이 바뀜 |
| 7 | MB | v1.4.4+ 에서 GET/SET 0~2 (segcp.c:621-623, 1141-1148, [git] v1.4.4) | 750SR 그룹에 modbus 없음 (WIZ750SR.yaml:51-59). 정의는 modbus.yaml:22-35 에만 | **스펙이 누락** | 1.4.4 이상 장비의 Modbus 모드를 툴이 모름 |
| 8 | FL | RS-422/485 인터페이스(`UN`=`RS-422/485`)에서는 3·4 이외 값을 **0 으로 바꿔 저장**하고 오류 없음 (segcp.c:870-880) | 0~4 조건 없음 (base.yaml:318) | **스펙이 조건 누락** | 485 모델에서 1·2 를 골라도 0 으로 저장됨 → 재조회 값이 달라 보임 |
| 9 | GA~GD | SET 은 해당 핀이 **디지털 출력**일 때만. 아니면 `ERINVALIDPARAM` → SV 취소 (segcp.c:993-999) | 0~1, 조건 없음 (gpio.yaml:76-130) | **스펙이 조건 누락** | 입력 핀 값을 저장 흐름에 섞어 보내면 SV 취소 |

### 9.2 참고 (어긋남으로 세지 않음)

| # | 내용 | 근거 |
| --- | --- | --- |
| a | FW 에서 no-op 인 DD DX DP DI DW PI PP 를 스펙(ddns.yaml, pppoe.yaml)은 일반 RW 로 정의. DP 는 스펙이 1~65535 로 검사하지만 FW 는 아무 값이나 받고 버림. 750SR 은 UI 에 노출 안 함 | segcp.c:755-800, ddns.yaml:43-54 |
| b | 스펙 정규식은 FW 보다 대체로 엄격하다(IP 4옥텟, 포트 선행 0 불가, 숫자만). FW 는 비숫자 문자열을 0 으로 읽어 통과시키므로 툴 검증이 사실상 유일한 방어선 | §4.2, base.yaml:93, 162 |
| c | UI, AB, BU, EC 외 FC FP FD FH UE K! RX FS 는 스펙에 정의가 없거나 750SR 그룹에 없다(툴이 쓰지 않으면 무해). `K!`·`FS`·`RX` 는 값 없이 보내면 FW 가 즉시 동작하므로 검색 목록에 실수로 넣으면 안 된다 | segcp.c:510-526, 604-606 |

### 9.3 일치 확인된 것

| 항목 | FW | 스펙 |
| --- | --- | --- |
| 설정 포트 50001 | deviceHandler.h:12 | WIZ750SR.yaml:90 |
| 버퍼 512, "FW 가 응답 길이를 대조 안 함" | common.h:68, §3.1 | WIZ750SR.yaml:91-93 |
| NP 최대 9자 | ConfigData.h:68, segcp.c:931 | WIZ750SR.yaml:64-65 (`^.{0,9}$`) |
| "ER 문자열 없이 SAVE 전체 스킵(조용히 실패)" | segcp.c:96, 1180 | WIZ750SR.yaml:63 주석 |
| TR 은 1.2.0 이상 | [git] TR case 도입 = v1.2.0 | WIZ750SR.yaml:66-68 |
| IM OP DB PR SB CP KA TE DG EC 범위, KI KE RI IT PT LP RP 0~65535, PS 0~255, PD SS 형식, CA~CD 0~2, SC 두 자리 | §4.2 | base.yaml, gpio.yaml, retransmit.yaml 해당 항목 |

---

## 10. 담당자에게 물어볼 것 (소스만으로 결론이 안 나는 것, 5개)

**Q1. `RH` 도메인 길이를 FW 에서 검사할 계획이 있는가?**
- 근거: `dns_domain_name[49]`(ConfigData.h:74), `strcpy` 무검사(segcp.c:838).
- 선택지: (a) FW 수정 예정 → 툴은 수정 버전부터 한도를 풀어도 됨 / (b) 수정 계획 없음 → 툴이 WIZ750SR 계열에서 RH 도메인을 48자로 제한 (스펙 §9.1 #1 수정).

**Q2. ~~WIZ750SR 계열에서 BR 14(460800)를 지원 대상으로 봐도 되는가?~~ — 질문하지 않는다.** 2026-07-15 에 "750 계열은 230k 까지"로 담당자 확인이 끝났다(위 §9.1 #3). 아래는 작성 당시 기록이다.
- 근거: FW 는 14 까지 받고 테이블에도 있음(segcp.c:844, uartHandler.c:51). 스펙은 0~13(WIZ750SR.yaml:70-71). 하드웨어/클록상 실제 동작 여부는 소스로 알 수 없다.
- 선택지: (a) 지원 → 스펙에 14 추가 / (b) 미지원(보증 안 함) → 현행 유지하고 사유를 스펙에 주석.

**Q3. 512바이트를 넘는 요청·응답이 실제로 어떤 메모리를 덮는가? 현장에서 관찰된 증상이 있는가?**
- 근거: 길이 검사 없음(§3.1). `gSEGCPREQ/REP` 는 전역 배열이지만(segcp.c:32-33) 링커 맵·배치는 저장소에 없다. 웹서버도 같은 버퍼를 쓴다(main.c:275).
- 선택지: (a) 맵 파일 제공 → 툴이 허용 최대 요청/응답 길이를 정함 / (b) 512 미만을 계약으로 두고 툴이 요청 분할(예: GET 40개 이하씩).

**Q4. 배포되는 바이너리는 어떤 `DEVICE_BOARD_NAME` 과 `__USE_APPBACKUP_AREA__` 로 빌드되는가? 그리고 Boot 의 `VR` 은 무엇을 보여주는가?**
- 근거: 보드별 매크로(W7500x_board.h:17-24), 백업영역을 켜면 `VR` 이 `1.4.5A`(segcp.c:342-346), Boot 은 빌드 시점 common.h 값을 씀(§8.1). 실제 릴리즈 빌드 설정은 소스에 없다.
- 선택지: (a) 모두 백업 미사용·WIZ750SR/1xx 별 빌드 → 툴은 `A` 접미를 고려할 필요 없음 / (b) 구버전 호환 이미지 유통 → 툴의 버전 비교가 접미(`A`, `dev`)를 숫자만 비교하도록 보장해야 함.

**Q5. `MA=FF:FF:FF:FF:FF:FF` 요청으로도 SET/SV/RT 가 통과하는 것(READ/WRITE 구분 없음)과, `K!`·`FS`·`RX` 가 권한 검사 없이 GET 형식으로 동작하는 것은 의도인가?**
- 근거: segcp.h:97-100 + segcp.c:559, 641, 1232-1233 / segcp.c:510-526, 604-606.
- 선택지: (a) 의도(호환 유지) → 툴은 현행대로 두되 위험 명령을 검색 경로에서 제외 / (b) 수정 예정 → 수정 후에는 "읽기 전용 MA 로 SET 하면 `ERNOPRIVILEGE`"가 되므로 툴이 쓰기 시 MAC 지정으로 보내야 함.

---

## 부록 A. 툴 구현 시 바로 쓸 규칙 (위 사실에서 도출, [추정] 포함)

1. 요청은 항상 `MA…` + `PW…`(검색암호 없으면 `PW ` 공백) 로 시작. PW 가 없거나 틀리면 응답이 없다.
2. 응답 줄 수는 보낸 GET 수보다 적을 수 있다. 줄 단위로 명령 2글자를 키로 매칭하고, 없는 명령은 "오류 또는 뒤에서 잘림" 으로 구분 불가하므로 재조회한다.
3. 요청 순서: GET → SET → SV → RT. SET 에 오류가 섞이면 SV 가 취소되므로 저장 후 재조회로 검증.
4. 보내지 말 것: VR/MN SET, MC SET(자기 OUI 가 00:08:DC 면 오류), 읽기 전용 명령 SET, `SV`/`RT` 에 값 붙이기, 명령표에 없는 명령.
5. 입력 길이: NP·SP 9자, DH 14자, RH 48자 이하로 툴에서 막는다.
6. 응답 합계를 512 이하로: 검색 37개는 안전, 62개 전부는 불가.
7. `K!` `FS` `RX` `FR` `AB` 는 값 없이 보내면 즉시 동작한다.

## 부록 B. 조사에서 확인하지 못한 것

- 링커 맵(512 버퍼 뒤 메모리), 실기기 동작, 배포 바이너리 빌드 옵션.
- 다른 브랜치(`Develop`, `BootV1.2`, `dev/modbus`, `DIK` 등)와 v1.2.x·v1.3.x 태그의 소스(명령 도입 시점은 `git log -S` 로 App `segcp.c` 만 추적).
- docs.wiznet.io 의 명령 매뉴얼과의 대조.
- 이 저장소의 툴 코드(`WIZMakeCMD.py`, `wizcmdset.py`)와의 대조(요청에 따라 `specs/` 만 대조).
- `SV` 중 최대 5초 블록 시 워치독(`WDT_Start`, main.c:271)과의 상호작용.
