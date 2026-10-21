# WIZ752SR-12x 펌웨어 SEGCP 소스 읽기 노트

설정툴 개발자가 FW 레벨 질문에 바로 답하기 위한 문서다. 코드 수정·커밋·push 는 하지 않았고, 소스는 읽기만 했다.

표기: `[소스]` 직접 읽은 것(커밋 명시), `[추정]` 읽은 것에서의 추론, `미확인` 소스만으로 결론 불가.
근거는 `파일:줄`. 경로 접두 `A:` = `Projects/App/src/`, `B:` = `Projects/Boot/src/`. 줄 번호는 아래 기준 커밋(master) 것이다.
담당자 발언·실기기 측정은 이 문서에 쓰지 않았다(툴 쪽 기록을 인용할 때는 "툴 기록"이라고 밝힌다).

## 1. 기준

| 항목 | 값 |
| --- | --- |
| 저장소 | `https://github.com/Wiznet/WIZ752SR-12x` (공개). 2026-10-20 전체 이력 clone |
| 기본 브랜치 | `master` |
| 기준 커밋 | `0207e95a74b03be0b91c855400b827a92f578bba` (2019-09-20 11:20 +0900, "modify setSn_DHAR offset address") |
| 태그 | `v2.1.0` = `a577088` (2019-07-05). 유일한 태그. `v2.1.0..master` 차이는 README 와 `W7500x_wztoe.h`(setSn_DHAR 오프셋)뿐 — `git diff --stat v2.1.0 master` |
| 소스상 버전 | `2.1.0`, `STR_VERSION_STATUS "Develop"` — `A:common.h:9-13` |
| 별도 브랜치 | `origin/fix/user-io-and-segcp` (tip `ab2a782`, 2026-08-27, 작성자 `theoim`, 커밋 5개). master 에 병합되지 않았다. **이 문서의 사실은 모두 master 기준**이고, 브랜치는 6절·10절에서만 언급한다 |

- [소스] 이 저장소에는 `README.md` 외 프로토콜 문서가 없다. 링크 맵(.map)도 없다(`git ls-files`). 메모리 배치는 미확인.
- [소스] Boot 는 자체 `common.h`·`W7500x_board.h`·`ConfigData` 가 없고 App 쪽을 include 한다 — `Projects/Boot/W7500x_Application.uvproj:370`(IncludePath 에 `..\App\src`), `:579-581`(`..\App\src\Configuration\ConfigData.c` 를 컴파일). 따라서 버퍼 크기·버전 상수는 App 과 같은 헤더에서 온다.

## 2. 프로토콜·버퍼

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 포트 | UDP 50001, TCP 50001 (소켓 2=UDP, 3=TCP). 펌웨어 업로드는 TCP 50002 (소켓 5) | `A:PlatformHandler/deviceHandler.h:12-13`, `A:common.h:22-26`, `A:segcp.c:1459,1565`, `A:deviceHandler.c:374` |
| 요청/응답 버퍼 | `static uint8_t gSEGCPREQ[512]`, `gSEGCPREP[512]`. 툴 기록의 512B 와 **일치** | `A:common.h:52`, `A:segcp.c:29-30`, `B:segcp.c:26-27` |
| 데이터 경로 버퍼 | `DATA_BUF_SIZE 1024` (`g_send_buf/g_recv_buf[채널][1024]`). SEGCP 와 무관한 시리얼↔이더넷 경로 | `A:common.h:51`, `A:main.c:71-72` |
| 소켓 HW 버퍼 | 소켓 0~5 각 TX/RX 2KB | `A:main.c:222-223` |
| UDP 응답 | **항상 브로드캐스트** `255.255.255.255`, 목적 포트는 요청의 출발 포트. 요청이 유니캐스트여도 같다 | `A:segcp.c:1443` (`sendto(..., "\xFF\xFF\xFF\xFF", destport)`) |
| TCP 응답 | 연결된 소켓으로 `send`(유니캐스트). 연결 후 15초마다 keep-alive | `A:segcp.c:1542`, `:113`, `:1500-1510` |
| 요청 형식 | `MA`+MAC 6바이트 raw+`\r\n`(10B) → `PW`+값+`\r\n` → 명령들. 응답 머리는 `MA`+**장치** MAC raw 6B+`\r\n` 과 PW 줄의 에코(10+len+4B) | `A:segcp.c:1419-1443` |
| 무응답 조건 | MA 가 `FF*6` 도 장치 MAC 도 아님 / PW 불일치 / MA·PW 줄 형식 불량 → **아무것도 보내지 않는다**(ER 도 없음) | `A:segcp.c:1421-1423,1436,1451-1455` |
| 권한 | MA=`FF*6` → 읽기 권한(GET 만, SET·SV·RT 는 `ERNOPRIVILEGE`). MA=장치 MAC → 쓰기 권한 | `A:segcp.c:1421-1422`, `:705,1352-1355` |
| 요청 길이 보호 | master 에는 **없다**. `recvfrom(..., len=RX_RSR)` 이 데이터그램 크기만큼 `gSEGCPREQ[512]` 에 복사한다. ioLibrary 는 `min(요청, 데이터그램)` 만 지킨다 | `A:segcp.c:1412-1417`, `ioLibrary/Ethernet/socket.c:449-506` |
| 스택 버퍼 | `param[64]` 에 `strcpy` 로 값을 복사(길이 무검사). UDP `tpar[64]`, **TCP `tpar[33]`** 에 PW 값을 무검사 복사 | `A:segcp.c:244,292,1404,1481`, `:228-231` |

- [소스] 요청 끝 1바이트는 무조건 NUL 로 덮는다(`treq[len-1] = 0`) — `A:segcp.c:1417,1517`. 요청은 `\r\n` 으로 끝나야 마지막 명령이 온전하다.
- [소스] 요청은 `strtok(req, "\r\n")` 으로 쪼갠다(`A:segcp.c:298,1375`). 값에 CR/LF 를 넣을 수 없다.
- [소스] 명령 인식은 앞 2글자 `strncmp` 접두 일치다(`A:segcp.c:200-203`). 표에 없는 명령(예: `TR`, `MB`)은 `ERNOCOMMAND` 가 된다(8절).

## 3. 응답 길이 보호

| 질문 | 답 | 근거 |
| --- | --- | --- |
| 응답이 버퍼를 넘을 때 검사하는가 | **검사 없음.** `sprintf`/`strcat` 로 `gSEGCPREP[512]` 에 무제한 기록하고 `sendto(…, 14+strlen(tpar)+strlen(trep))` 로 strlen 만큼 보낸다. 상한(512)과 비교하는 식이 어디에도 없다 | `A:segcp.c:311-312,701-702,1443,1542` |
| 보내는 크기의 상한 | 소켓 TX 버퍼 2KB — `sendto` 가 `len > getSn_TxMAX` 면 잘라 보낸다. 512B 보호가 아니라 우연한 상한이다 | `ioLibrary/Ethernet/socket.c:404-405`, `A:main.c:222` |
| 응답 버퍼 초기화 | `memset(trep, 0, sizeof(trep))` — `trep` 가 포인터라 **4바이트만** 지운다. 버퍼 전체 초기화가 아니다 | `A:segcp.c:297` |
| 넘친 바이트가 덮는 곳 | `gSEGCPREP` 바로 뒤 정적 변수. 링커 배치는 **미확인**(.map 없음). 툴 기록의 "UART 송신 링버퍼 `txring[0].data`" 는 소스로 검증하지 못했다 | — |

### 최악 응답 크기 계산 (툴 모델 `15 + Σ(4 + 값길이)` 와 일치)

- [소스] 머리 15B = `MA`(2)+MAC(6)+CRLF(2) + `PW`(2)+값(공백 1)+CRLF(2) = 10+5. 줄마다 `2+값+2`. 툴 모델과 같다 — `A:segcp.c:311-312,701,1427-1443`.
- [추정] 값 길이는 소스의 `sprintf` 형식과 칸 크기에서 구한 상한이다. 공장 기본값 기준 "일반"은 `ConfigData.c:29-160` 의 초기값(IP `192.168.11.x`, 모듈명 `WIZ752SR-12x` 12자, VR `2.1.0dev` 8자, DH 는 `이름-MAC뒤3바이트` 19자)을 썼다. 상한은 RH/QH 39자, MN 19자, DH 26자, IP 15자, 포트·시간 5자.

| 조회 묶음 (툴 `WIZMakeCMD.py`) | 명령 수 | 일반 | 상한 | 요청 크기 |
| --- | --- | --- | --- | --- |
| 한 번에 전체 (`cmd_ch1 + cmd_ch2 + SC`) | 62 | 506B | **648B** | 263B |
| 청크1 network (`cmd_2p_chunk_network`) | 24 | 251B | 293B | 111B |
| 청크2 ch0 (`MC` + LP 이후) | 17 | 140B | 195B | 83B |
| 청크3 ch1 (`MC` + `cmd_ch2` + `SC`) | 23 | 187B | 232B | 107B |

- [추정] 한 번에 조회하면 일반값에서도 512B 에 6B 여유뿐이고, 상한에서는 648B 로 확실히 넘친다. 3분할은 소스와 **일치하는 조치**다 — 청크 최대 293B 는 512B 의 57%. 일반값 251/140/187B 는 툴 기록의 실측(약 250/150/195B)과 맞는다.
- [추정] 가장 크게 늘 수 있는 값은 RH/QH(최대 39자 ×2 = 도메인 문자열이 두 줄에 같이 실림), DH(26), MN(19). 도메인이 실제 설정돼 있으면 청크1 이 가장 위험하다.
- [소스] 요청 쪽도 512B 한계다. SET 패킷(값 포함)이 512B 를 넘으면 위 "요청 길이 보호 없음"에 걸린다.

## 4. 문자열 필드

| 명령 | 칸 | 최대 글자 수 | SET 길이 검사 | 근거 |
| --- | --- | --- | --- | --- |
| `RH` / `QH` (도메인) | `dns_domain_name[40]` — **RH·QH 가 한 칸을 공유** | 39 | **없음.** `strcpy(dns_domain_name, param)`. 40자 이상이면 바로 뒤 `tcp_option[0]`(inactivity·keepalive·pw_connect 등)을 조용히 덮어쓴다. 값 자체는 `param[64]` 한도(63자)까지 들어오고, 64자 이상이면 스택 오버플로 | `A:ConfigData.h:64-69`, `A:segcp.c:951,969`, `:292`, `:244` |
| `DH` | `module_name[20]` (= `MN` 의 원천) | 19 | **거부** (`param_len > 19` → `ERINVALIDPARAM`). 저장은 `sscanf("%s")` 라 공백에서 잘린다 | `A:ConfigData.h:22-28`, `A:segcp.c:903-914` |
| `NP` (연결 비밀번호) | `pw_connect[10]` | 9 | **거부** (`> 9` → `ERINVALIDPARAM`). 값이 공백 1개면 삭제, 그 외는 `sscanf("%s")` 라 **공백 앞까지만 저장**(자름) | `A:ConfigData.h:78`, `A:segcp.c:1140-1148` |
| `SP` (검색 비밀번호) | `pw_search[10]` | 9 | **거부** (`> 9`). 저장·공백 처리는 NP 와 같다 | `A:ConfigData.h:33`, `A:segcp.c:1151-1158` |
| `SS` | `serial_trigger[3]` | 16진 6자 | 길이 6·16진 검사 후 변환. **소문자 16진은 값이 틀어진다**(7절) | `A:segcp.c:1133`, `A:util.c:168-190` |
| `PD` / `ND` | `packing_delimiter[0]` | 16진 2자 | 길이 2·16진 검사 (`sscanf %x` 라 소문자 정상) | `A:segcp.c:1092-1108` |
| `MC` | `mac[6]` | `XX:XX:XX:XX:XX:XX` 17자 | 형식 검사. 장치 MAC 이 `00:08:DC` 로 시작하면 `ERIGNORED` | `A:segcp.c:710-711`, `A:util.c:137-165` |
| `PI` `PP` `DI` `DW` | 없음 | — | SET 은 **받고 버린다**(OK 처리, 저장 안 함) | `A:segcp.c:856-901` |
| `FD` / `FH` | 없음(상수 문자열) | — | SET → `ERINVALIDPARAM` | `A:segcp.c:1302-1312` |

- [소스] `segcp.h` 의 `DEVCONF_DOMAIN_MAX 32`, `NAME_MAX 16`, `SEARCHPASS_MAX 8`, `CONNPASS_MAX 8`, `IDPASS_MAX 16` 은 실제 칸 크기(40/20/10/10)와 **다르고**, `DEVCONF_DOMAIN_MAX` 만 `SEGCP_PARAM_MAX`(=32 → 값 버퍼 `*2` = 64)로 쓰인다. 나머지 `DEVCONF_*` 는 참조처가 없다 — `grep` 결과 `segcp.h:9-13,16` 외 사용 없음. 이 상수를 칸 크기로 오해하지 말 것.
- [소스] IP 계열(`LI SM GW DS`, `RH/QH` 의 IP 분기)은 `is_ipaddr` 가 길이 7~15, 숫자·점만, 각 마디 ≤255 를 검사한다(`A:util.c:42-82`). 7~15자의 숫자·점 문자열은 도메인이 아니라 IP 로 취급한다.

## 5. 오류 처리 (설정툴 UDP/TCP 경로, master)

| 질문 | 답 | 근거 |
| --- | --- | --- |
| 오류가 나면 뒤 명령을 처리하는가 | **처리하지 않는다.** 오류 비트가 서면 즉시 `return ret` — 같은 패킷의 남은 명령(SET·GET·SV·RT 포함)은 통째로 건너뛴다. 툴 기록과 **일치** | `A:segcp.c:1362-1373` |
| ER 줄이 응답에 실리는가 | **실린다.** `"<ERxxx>:<명령 2글자>\r\n"` 을 응답 버퍼에 쓰고, 호출부가 그대로 `sendto`/`send` 한다. UDP/TCP 여부와 무관하다. (툴 `WIZ752SR-12x.yaml:83-84` 의 "ER 문자열 없이"와 다름 — 9절 J) | `A:segcp.c:1364-1365`, `:1442-1443` |
| 오류 시 SV/RT 취소 | **취소된다.** 패킷에 오류가 하나라도 있으면 `do_segcp` 가 저장·리부트·모드전환을 실행하지 않는다 | `A:segcp.c:82-87`, `:89-183` (`else if(segcp_ret)` 가 오류일 때 건너뜀) |
| 오류 전의 SET 은 | **이미 RAM 에 반영된 채 남는다**(롤백 없음). 이후 다른 요청의 `SV` 가 그 부분 변경까지 함께 저장한다. 일부 SET 은 즉시 부작용이 있다(`OP`/`QO` 는 해당 채널 소켓 종료) | `A:segcp.c:730,743` |
| 오류 시 시리얼 수신 | `UART_Buffer_Flush` 로 **두 채널의 UART 수신 링버퍼를 모두 비운다**(데이터 유실) | `A:segcp.c:1370-1371` |
| 같은 요청 안 GET 응답이 오류 뒤에 지워지는가 | 오류 **앞**의 GET 줄은 남는다. 오류가 난 GET 은 이름·값이 지워지고 그 자리에 ER 줄이 쓰인다. 오류 **뒤**는 처리 자체가 안 된다 | `A:segcp.c:694-698,1365` |
| 같은 요청 안 GET 응답이 SV/RT 뒤에 지워지는가 | **지워진다.** `ret` 가 누적이라 SV/RT/EX/AB(SAVE·REBOOT·SWITCH 비트)가 한 번 서면 **그 뒤 모든 GET 줄**이 `trep -= 2; *trep = 0` 으로 지워진다. SV/RT **앞**의 GET 은 남는다. SV/RT 뒤의 SET 은 처리된다 | `A:segcp.c:694-698` |
| SV/RT 가 GET 형태인가 | `SV`, `RT` 는 값 없는 줄(`SV\r\n`)이 실행 형태다. 값이 붙으면 `ERNOTAVAIL` | `A:segcp.c:613-624`, `:1339-1345` |
| 권한 없음 | MA=`FF*6` 로 SET 하면 `ERNOPRIVILEGE` | `A:segcp.c:1352-1355` |

- [소스] 개별 오류 종류: `ERNOTAVAIL`(GET 불가·SET 불가 명령), `ERNOPARAM`(`FW` GET), `ERIGNORED`(`VR MN` SET, 장치 MAC 이 WIZnet OUI 일 때 `MC` SET), `ERNOCOMMAND`(표에 없는 명령), `ERINVALIDPARAM`(값 거부), `ERNOPRIVILEGE` — `A:segcp.h:43-58`, `A:segcp.c:46`.
- [소스] 로직 요약: 한 패킷에 SET 수십 개 + `SV` 를 넣으면 **필드 하나만 거부돼도 전체 SV 가 취소**되고 변경은 RAM 에만 남는다. 사전 검증이 곧 툴의 책임이다.
- [소스] **시리얼 AT 모드**(`proc_SEGCP_uart`)도 같은 `proc_SEGCP` 를 쓴다. 입력 버퍼 `segcp_req[64]`, 명령 한 줄씩 — `A:segcp.c:1588-1597`.

## 6. 빈 값 GET, 미구현 명령

### 빈 값 GET 응답

- [소스] 빈 값의 GET 응답은 **공백 한 글자**다. `sprintf(trep, "%c", SEGCP_NULL)` 후 `\r\n` → 예: `NP \r\n`. 해당: `NP SP`, `RH/QH`(`dns_use=ENABLE` 이고 도메인이 비었을 때), `DH`(모듈명 빈 경우), `PI PP DI DW`(항상), `FD FH`(상수 미정의 시) — `A:segcp.c:389,394,403,408,411,432,445,499,503`. SET 에서 지울 때도 공백 한 글자를 보낸다(`param[0] == ' '`).
- [소스] 모양은 4CH 문서(`fw_4ch_string_field_limits.md` 계열)의 "빈 칸 = 공백"과 같다. 다른 모양(빈 문자열, 줄 생략)은 이 FW 에 없다.
- [소스] `RH`/`QH` GET 은 `dns_use == DISABLE` 이면 IP 를, `ENABLE` 이면 **같은 도메인 문자열**을 돌려준다. `dns_use` 가 채널 구분 없이 하나(`ConfigData.h:66`)라 한 채널을 도메인으로 바꾸면 두 채널 GET 이 같이 도메인으로 바뀐다. `QH` 의 빈 값 판정은 `dns_domain_name[1]` 을 본다(`[0]` 아님) — 도메인이 1글자면 `QH` 는 공백으로 보인다(`A:segcp.c:445`, 같은 줄의 RH 는 `[0]`: `:432`).

### 미구현·제한 명령

| 명령 | GET | SET | 근거 |
| --- | --- | --- | --- |
| `DD` `PO` | 항상 `0` | 값 범위(`0~1`) 검사만 하고 **저장 안 함** | `A:segcp.c:341,344,747-758` |
| `DX` | 항상 `0` | 받고 버림 (검사도 없음) | `A:segcp.c:397,874-878` |
| `DP` | 상수 `3030` | 받고 버림 | `A:segcp.c:400`, `A:deviceHandler.h:14` ("Not used") |
| `PI` `PP` `DI` `DW` | 공백 | 받고 버림 | `A:segcp.c:389-408,856-901` |
| `S0 S1 E0 E1` | 현재 핀 값 | `ERINVALIDPARAM` | `A:segcp.c:541-557,1268-1276` |
| `RX` | UART 수신 링버퍼 **플러시 실행** 후 `FLUSH` | `ERINVALIDPARAM` | `A:segcp.c:560-565,1280-1282` |
| `FD` `FH` | 상수(`device.wizwiki.net`, `/wiz750sr/fw/W7500x_S2E_App.bin`) | `ERINVALIDPARAM` | `A:ConfigData.h:19-20`, `A:segcp.c:591-611,1302-1312` |
| `FS` | **HTTP 서버 FW 업데이트를 시작**(권한 검사 없음) | `ERINVALIDPARAM` | `A:segcp.c:568-581` |
| `UN EN UI EI ST QS LG ER MA PW EX SV RT FR AB` | `LG ER MA PW` → `ERNOTAVAIL`, `FW` → `ERNOPARAM`, 나머지는 각자 동작 | 값을 붙이면 `ERNOTAVAIL` | `A:segcp.c:506-512,1326-1345` |
| `K!` | 값 없이 보내면 **MAC·설정 저장소 지우고 리부트**(권한 검사 없음) | `ERNOCOMMAND` | `A:segcp.c:675-677,1347-1349` |
| `EC` `UE` | 에코 설정 / 항상 `0` | `EC` 저장, `UE` 검사만 | `A:segcp.c:672-679,1315-1324` |

- [소스] **GET 형태만으로 실행되는 위험 명령**: `K!`(저장소 삭제), `FS`(원격 업데이트), `RX`(UART 버퍼 비움), `FR`·`AB`(쓰기 권한 필요). 설정툴이 "모든 명령 조회"를 만들 때 이 이름들이 목록에 섞이면 안 된다.
- [소스] 없는 명령(`TR`, `MB` 등)은 접두 일치 실패 → `ERNOCOMMAND` → 5절에 따라 **그 패킷의 나머지 전부가 버려진다**. 목록 정의가 곧 안전장치다.

## 7. 명령 목록과 빌드 옵션

### 7.1 명령 테이블 (App)

`tbSEGCPCMD` — `A:segcp.c:35-44`(95개 + 종료). 순서가 곧 enum 값(`segcp.h:20-30`).

| 그룹 | 명령 | 비고 |
| --- | --- | --- |
| 장치 정보 | `MC VR MN UN EN ST QS UI EI` | RO. `UN`/`EN`=인터페이스 문자열(`RS-232/TTL`·`RS-422/485`), `UI`/`EI`=번호 |
| 네트워크 CH0 / CH1 | `IM`(공통) `OP`/`QO` `LP`/`QL` `RP`/`QP` `RH`/`QH` `RI`/`RR` `LI SM GW DS`(공통) | `RH/QH` 도메인 공유 |
| TCP 옵션 CH0 / CH1 | `KA`/`RA` `KI`/`RS` `KE`/`RE` `IT`/`RV` `CP`·`NP`(CH0 전용) | `CP`·`NP`·`SP` 는 CH0 값만 — 채널1 연결 비밀번호 명령 없음(`tcp_option[1].pw_connect` 는 SEGCP 로 접근 불가) |
| 시리얼 CH0 / CH1 | `BR`/`EB` `DB`/`ED` `PR`/`EP` `SB`/`ES` `FL`/`EF` | |
| 패킹 CH0 / CH1 | `PT`/`NT` `PS`/`NS` `PD`/`ND` | |
| 시리얼 명령 모드 | `TE SS EC` | |
| 보안·표시 | `NP SP DG DH UE` | `DH` 는 호스트명 (4절) |
| 상태 핀 | `SC S0 S1 E0 E1` | |
| 사용자 I/O | `GA~GD CA~CD` | `__USE_USERS_GPIO__` 가 정의된 빌드에서만 |
| 실행 | `SV EX RT FR AB K! FW` | 5·6절 |
| FW 서버 | `FS FC FP FD FH` | |
| 미사용 | `DD PO PI PP DX DP DI DW LG ER` | 6절 |

### 7.2 빌드 옵션별 차이

보드 선택은 `A:W7500x_board.h:14` (`DEVICE_BOARD_NAME WIZ752SR_12x`), 이 보드의 옵션은 `:98-112`.

| 옵션 | WIZ752SR_12x | 영향 | 근거 |
| --- | --- | --- | --- |
| `__USE_USERS_GPIO__` | **정의됨** | `GA~GD`·`CA~CD` GET/SET 동작. 미정의 빌드에서는 두 그룹 모두 `ERNOCOMMAND` | `A:W7500x_board.h:105`, `A:segcp.c:515-537,1198-1243` |
| `__USE_APPBACKUP_AREA__` | **정의됨** | `FW` 크기 상한 `0xC700`(50944B) = `199*256`, 백업 영역 사용, `FS`(HTTP 업데이트) 활성. 미정의면 상한이 달라진다(`& 0x19000`) | `A:W7500x_board.h:102`, `A:deviceHandler.h:23-30`, `A:segcp.c:1163-1167`, `A:flashHandler.h:17` |
| `__USE_UART_IF_SELECTOR__` | 주석 처리 | `UN/EN` 문자열은 `init_uart_if_sel()` 결과. 이 보드에서 실제 값은 **미확인**. 값이 `RS-422/485` 이면 `FL/EF` 가 `3`·`4` 외 입력을 `0` 으로 조용히 바꾼다 | `A:W7500x_board.h:99`, `A:segcp.c:1016-1058`, `A:ConfigData.c:179-185` |
| `__USE_UART_DTR_DSR__` | 주석 처리 | `SC` 공장값 `00` (켜진 보드는 `11`) | `A:W7500x_board.h:104`, `A:ConfigData.c:103-109` |
| `__USE_PHYLINK_CHECK_PIN__` `__USE_STATUS_TCPCONNECT_PIN__` | 정의됨 | 상태 핀 동작(`S0/S1/E0/E1` 값) | `A:W7500x_board.h:102-108` |
| `__USE_EXT_EEPROM__` | 주석 처리 | 설정 저장소가 **내부 플래시 DAT0/DAT1** (8절) | `A:W7500x_board.h:100`, `A:storageHandler.c:25-47` |
| `FWUP_SERVER_DOMAIN` / `FWUP_SERVER_BINPATH` | 정의됨 | `FD`/`FH` GET 이 상수를 돌려줌 | `A:ConfigData.h:19-20`, `A:segcp.c:591-611` |
| `_SEGCP_DEBUG_` | 주석 처리 | 디버그 출력 | `A:segcp.h:6` |

### 7.3 Boot 의 명령 테이블

- [소스] Boot `tbSEGCPCMD` 는 `GA~GD CA~CD SC S0 S1 RX FS FC FP FD FH UI` 가 **빠져 있다**(`B:segcp.c:32-39`). Boot 상태(`ST=BOOT`)에서 이 명령을 조회하면 `ERNOCOMMAND` 가 나고 5절대로 그 뒤가 버려진다.
- [소스] Boot `VR` 는 `"%x.%x.%x"`(16진, `dev` 접미사 없음)이고 App 은 `"%d.%d.%d"` + 빌드가 `Develop` 이면 `dev` 접미사 — `B:segcp.c:269`, `A:segcp.c:321-329`.
- [소스] Boot 의 `AB` 는 App 으로 복귀(`working_state=ST_OPEN`, 저장+리부트), App 의 `AB` 는 Boot 로 진입(`working_state=ST_BOOT`, 저장+리부트) — `B:segcp.c:507-514`, `A:segcp.c:681-686`.

## 8. Boot/App 구조, 버전, 저장 방식

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| 플래시 배치 | Boot 112섹터(28KB, 섹터 256B) → App 199섹터 → App 백업 199섹터. 설정은 DAT0(`DevConfig`), DAT1(`DevConfig_E`), MAC 은 별도 주소 | `A:deviceHandler.h:23-48`, `A:flashHandler.h:17` |
| Boot 기동 | 설정 로드 → MAC 확인 → `fwup_flag` 가 서 있으면 백업→메인 복사 → 메인 영역이 비어 있지 않으면 App 으로 점프. `working_state==ST_BOOT`(App 의 `AB`)면 점프하지 않고 Boot 에 머문다 | `B:main.c:120-232` |
| 점프하지 않으면 | 두 채널 `working_state=ST_BOOT` 로 두고 SEGCP(`do_segcp`)만 돈다 → 툴에서 `ST=BOOT` | `B:main.c:222-226,271` |
| 펌웨어 업로드 | `FW<크기>` 로 시작 → 응답 `FW<IP>:50002` → TCP 50002 로 전송 → App 백업 영역에 기록 → 리부트 → Boot 가 백업→메인 복사 | `A:segcp.c:1161-1195`, `A:segcp.c:117-150`, `B:main.c:132-146` |
| 버전 표기 | `common.h` 의 `MAJOR.MINOR.MAINT`(=2.1.0)가 컴파일 시점 상수. 설정 로드 때마다 저장값을 **덮어쓴다**(저장된 `fw_ver` 는 무의미) | `A:common.h:9-11`, `A:ConfigData.c:48-50,187-189` |
| VR 형식 | App: `"2.1.0dev"`(빌드가 `Develop`일 때) 또는 `"2.1.0"`. Boot: `"2.1.0"`(16진 출력) | `A:segcp.c:321-329`, `B:segcp.c:269` |
| 모듈명 | 공장값 `WIZ752SR-12x`(`DEVICE_ID_DEFAULT`). `MN` GET 은 이 칸, `DH` SET 이 이 칸을 바꾼다. `DH` GET 은 `이름-MAC뒤3바이트(소문자 16진)` | `A:W7500x_board.h:106`, `A:segcp.c:331,410-413` |
| 저장 방식 | `SV` → `save_DevConfig_to_storage` → DAT0 지우고 `DevConfig` 전체 쓰기, DAT1 도 같게. 부팅 시 `packet_size` 가 0 또는 0xFFFF 면 공장값으로 초기화 | `A:ConfigData.c:163-196`, `A:storageHandler.c:89-113` |
| 공장 초기화 | `FR` → 공장값+리부트. **채널0 로컬 포트가 1 이면 `FR` 이 저장소(MAC 포함) 삭제**로 바뀐다(숨은 기능) | `A:segcp.c:654-671` |
| DNS | 부팅 때 `dns_use==ENABLE` 이면 도메인을 해석해 **채널0 `remote_ip` 에만** 넣는다. 채널1 은 해석하지 않는다 | `A:main.c:132,356` |

## 9. 툴 스펙과의 대조

비교 대상: `specs/devices/WIZ752SR-12x.yaml`(이하 `dev.yaml`), `specs/commands/{base,two_port,gpio,ddns,pppoe}.yaml`. 어긋난 점 10건(A~J)이다.

| # | 항목 | 툴 스펙 (파일:줄) | FW 소스 (파일:줄) | 영향 |
| --- | --- | --- | --- | --- |
| A | RH/QH 길이 | `base.yaml:176`, `two_port.yaml:48`: `(?=.{0,128}$)`. 주석 `base.yaml:173` "최대 128바이트, FW DNS_DOMAIN_SIZE 와 일치" | 칸 40바이트 → 39자 (`A:ConfigData.h:68`), SET 무검사 `strcpy` (`A:segcp.c:951,969`) | **40~128자를 보내면 오류 없이 `tcp_option[0]` 이 깨진다.** 허용 상한을 39 로 낮춰야 한다. "128" 은 다른 FW 값 |
| B | RH/QH 독립 여부 | `two_port.yaml:45-51` `QH` 를 `QO` 에 의존하는 독립 항목으로 정의 | 도메인 칸·`dns_use` 가 하나 (`A:ConfigData.h:66-68`), DNS 해석은 채널0 만 (`A:main.c:356`) | CH1 에 도메인을 쓰면 CH0 의 목적지가 바뀌고 CH1 은 해석되지 않는다. QH 도메인 입력은 사실상 지원 안 됨 `[추정]` |
| C | DG 범위 | `base.yaml:334` `^[0-4]$` | `tmp_byte > ENABLE`(1) 이면 거부 (`A:segcp.c:765`) | 2~4 를 보내면 `ERINVALIDPARAM` → 패킷 전체 취소. `dev.yaml` 에 override 없음 |
| D | SP 길이 | `base.yaml:459-460` regex 빈 문자열(길이 제한 없음), `dev.yaml` override 는 `NP` 만 (`dev.yaml:85-86`) | `pw_search[10]` → 10자 이상 거부 (`A:segcp.c:1151-1153`) | 10자 이상 입력 시 패킷 전체 취소. `NP` 와 같은 `^.{0,9}$` 필요 |
| E | NP/SP 공백 | `dev.yaml:86` `^.{0,9}$` (공백 허용) | 선두가 공백 1개면 삭제, 그 외는 `sscanf("%s")` 라 첫 공백 앞까지만 저장 (`A:segcp.c:1146-1147,1157-1158`) | 중간 공백 있는 비밀번호는 잘려 저장(오류 없음), 읽어 오면 짧아져 있다. 공백 금지 권고 |
| F | SS 소문자 | `base.yaml:448` `[0-9a-fA-F]` 허용 | `str_to_hex` 가 소문자 보정 없이 `'A'` 기준 계산 — `toupper` 결과(`str_tmp`)를 쓰지 않음 (`A:util.c:181-185`) | 소문자 `a~f` 를 보내면 오류 없이 **틀린 값**이 저장된다. 대문자로 정규화해 보낼 것 |
| G | GA~GD | `gpio.yaml:52-82` 값 `^[0-1]$`, `access: RW` | GET 은 아날로그 핀이면 ADC 값(여러 자리)을 돌려줌 (`gpioHandler.c` `get_user_io_val`). SET 은 **디지털 출력 핀에서만**, 그 외는 `ERINVALIDPARAM` (`A:segcp.c:1209`). 공장값은 A 핀 아날로그 입력, C·D 출력 (`A:ConfigData.c:137-140`) | 입력/아날로그 핀에 GA/GB 를 SET 하면 패킷 전체 취소. GET 값을 `[0-1]` 로 검증하면 ADC 값이 거부된다 |
| H | DH 의미 | `ddns.yaml:52-57` "DDNS Domain Host", regex 없음 | 752 에서는 호스트명(`module_name`) — GET 은 `이름-MAC3바이트`, SET 은 19자 이하 (`A:segcp.c:410-413,903-914`) | 툴이 752 에서 DH 를 SET 하지 않으므로(`main_gui.py:5944-5952` 는 107/108 만) 현재 문제 없음. GET 값을 DDNS 도메인으로 해석하면 오해 |
| I | DDNS/PPPoE 저장 | `dev.yaml:75-79` `ddns`·`pppoe` 그룹 포함, `ddns.yaml`·`pppoe.yaml` 모두 `RW` | `DX DP DI DW PI PP` SET 은 받고 버림, GET 은 상수 (`A:segcp.c:397-409,856-901`), `DD`/`PO` 도 저장 안 함 (`:747-758`) | 752 에서는 쓸 수 없다. 이 값들을 "변경됨" 으로 비교하면 항상 불일치 |
| J | ER 문자열 | `dev.yaml:83-84` 주석: "UDP/TCP 모드라 ER 문자열 없이 SAVE 전체 스킵(조용히 실패)" | ER 줄은 응답 버퍼에 쓰이고 그대로 송신된다 (`A:segcp.c:1365,1443`). 모드 구분 없음 | 주석이 소스와 다르다. 응답에서 `ERINVALIDPARAM:NP` 같은 줄을 읽을 수 있다 `[추정: 툴 파서가 버리는지는 툴 코드 확인 필요]` |

### 일치 확인한 것 (참고)

| 항목 | 툴 | FW | 판정 |
| --- | --- | --- | --- |
| `BR`/`EB` 범위 | `dev.yaml:88-89`, `two_port.yaml:68`: 0~13 | `baud_230400 = 13` (`A:uartHandler.h:58`), `A:segcp.c:974` | 일치 |
| `FL`/`EF` | `base.yaml:317`, `two_port.yaml:112-115`: 0~4 | `flow_reverserts = 4` (`A:uartHandler.h:77-82`) | 일치 |
| `DB`/`ED` | `[0-1]` | `word_len8 = 1` (`A:uartHandler.h:60-63`), 9비트(2)는 거부 | 일치 |
| `OP`/`QO` `IM` `CP` `KA` `RA` `TE` `PR` `SB` | 범위 | `A:segcp.c` 해당 case | 일치 |
| `PS`/`NS` 0~255, `PT`/`NT`·`IT`·`RV`·`KI`·`KE`·`RI`·`RR`·`RS`·`RE` 0~65535 | | `param_len > 3 || > 0xFF`, `> 0xFFFF` 거부 | 일치 |
| `NP` 길이 | `dev.yaml:86` 9자 | `A:segcp.c:1140` 9자 | 길이는 일치 (공백은 E) |
| `config_buf_size: 512`, "FW 가 응답 길이를 대조하지 않는다" | `dev.yaml:109-111` | 3절 | 일치 |
| `S0 S1 E0 E1` 읽기 전용 | `gpio.yaml:92-106`, `two_port.yaml:168-185` | SET → `ERINVALIDPARAM` (`A:segcp.c:1268-1276`) | 일치 |
| `WIZMakeCMD.py:93,96` 청크 분할 | 3분할 | 3절 계산 | 일치 |

- [소스] 위 일치 항목 중 `CA~CD`(0~2)는 FW 가 `0~3` 중 3(아날로그 출력)만 거부해서 일치하고, `SC` 는 FW 가 한 자리(`1`)도 받아 툴(`^[0-1]{2}$`)이 더 엄격하다 — 문제 없음 (`A:segcp.c:1219-1224,1248-1253`).
- [소스] `LI SM GW DS` 는 FW 가 `1.2.3.4.5`(점 4개) 같은 값도 IP 로 받는다(`A:util.c:68`). 툴 regex 가 더 엄격하므로 문제 없음.
- 미확인: `WIZMakeCMD.py:81-83` 의 "넘친 바이트가 `txring[0].data` 를 덮는다"는 소스로 검증 불가(링크 맵 필요).

## 10. 담당자에게 물어야 할 것 (소스만으로 결론이 안 나는 것)

1. **현장 출하 FW 와 이 공개 소스의 대응.**
   - 근거: 공개 master 소스는 `2.1.0` / `Develop`(`A:common.h:9-13`)이라 `VR` 이 `2.1.0dev` 로 나온다. 마지막 커밋이 2019-09 이고 그 뒤 변경이 없다.
   - 선택지: (a) 출하 FW = 이 master 빌드. (b) 비공개 상위 브랜치가 있다. (c) `fix/user-io-and-segcp`(2026-08, 외부 작성자) 일부가 반영됨.
   - 영향: 이 문서의 5·3절 결론(오류 시 중단, 길이 무검사)이 현장 장치에 그대로 적용되는지가 여기서 갈린다.
2. **CH1 도메인(`QH`)이 사양인가.**
   - 근거: 도메인 칸과 `dns_use` 가 하나(`A:ConfigData.h:66-68`), 부팅 DNS 해석은 채널0 `remote_ip` 에만 쓴다(`A:main.c:356`).
   - 선택지: (a) 의도 — 도메인은 CH0 전용, CH1 은 IP 만. 툴이 `QH` 도메인 입력을 막아야 한다. (b) 버그 — FW 수정 예정. 툴은 현재 `QH` 도메인을 허용한다.
3. **`gSEGCPREP`/`gSEGCPREQ` 의 링크 배치.**
   - 근거: 정적 변수 뒤에 무엇이 오는지는 .map 이 있어야 한다(`A:segcp.c:29-30`). 툴 기록은 `txring[0].data` 라 하지만 소스에서는 확인되지 않는다.
   - 선택지: (a) .map 으로 인접 심볼 확인. (b) 확인 없이 툴의 3분할(상한 293B)을 영구 사양으로 둔다.
4. **`K!`·`FS` 가 권한 검사 없이 GET 형태로 실행되는 것이 의도인가.**
   - 근거: `A:segcp.c:568-581,675-677`. MA=`FF*6`(읽기 권한)에 PW 만 맞으면 저장소 삭제 가능해 보인다. `[추정]`
   - 선택지: (a) 의도(히든 기능). (b) 누락 — 수정 예정. 어느 쪽이든 툴은 이 이름을 조회 목록에 넣지 않으면 된다.
5. **오류 시 패킷 중단 정책을 유지할 것인가.**
   - 근거: master 는 오류 1건에 남은 명령과 SV/RT 를 모두 버린다(`A:segcp.c:1362-1373`, `A:segcp.c:82-87`). `fix/user-io-and-segcp` 의 `71b1add` 는 AT 모드 외에는 계속 처리하도록 바꾼다.
   - 선택지: (a) 유지 — 툴이 필드별 사전 검증(9절 A·C·D·G)을 책임. (b) 변경 — 툴이 응답의 `ER` 줄로 부분 실패를 처리하는 구조로 전환.
