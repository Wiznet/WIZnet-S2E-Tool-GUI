# `FR`(공장 초기화) 명령과 툴 "Factory default firmware"(`FR0`) — 펌웨어 소스 근거

작성: 2026-10-21 · 방법: 로컬 FW 저장소 clone 을 읽기만 함(빌드·실행·push 없음).

**표기**: `[소스]` 직접 읽음(저장소·커밋·`파일:줄`) / `[전언]` 담당자 구두 전언(소스로 확인 못 함) / `[추정]` 읽은 것에서의 추론 / `미확인`.

## 1. 결론

1. **현재 읽은 모든 FW 에서 `FR` 은 값 없이 보내야 동작한다.** 값을 붙인 `FR0` 는 SET 분기로 가서 `ERNOTAVAIL` 이 되고 초기화는 실행되지 않는다. `[소스]`
2. 툴의 **Factory default firmware 메뉴(`FR` + `"0"`)는 이 FW 들에서 무동작**이다. `[소스]`
3. `"0"` 은 **예전 모델에서 EEPROM 영역을 지우는 옵션**이었고 W55RP20 에서는 쓰지 않는다. `[전언]` 이 값을 받는 FW 소스는 로컬 clone·GitHub 공개 저장소 어디에도 없어 **소스로 확인하지 못했다.** `미확인`
4. 툴 쪽 단서: 2019-04-08 `f584d55` 의 `main_gui.py` 에 `# WIZ2000: setting or factory two options`, `# WIZ2000: factory reset option` 주석이 있다. 두 메뉴 구조와 `"0"` 은 **WIZ2000 용**으로 만들어진 것이다. `[소스]`(툴) · WIZ2000 FW 소스는 로컬·GitHub 에 없다. `미확인`

## 2. 펌웨어 코드 — 같은 구조가 전 계열에서 반복된다

`parse_SEGCP` 가 명령 2글자 뒤를 `param` 으로 자르고, `if(*param == 0)` 이면 **GET 분기**, 아니면 **SET 분기**다.

| 저장소 / 커밋 | `*param == 0` | GET 의 `case SEGCP_FR` | SET 의 `case SEGCP_FR` |
| --- | --- | --- | --- |
| WIZ5XXSR-RP-C `d815ea6` (2024-06-21) App | `segcp.c:318` | `:513-523` | `:1249` → `ERR_NOTAVAIL` |
| WIZ750SR `b0a17b2` (2024-12-27) App | `segcp.c:327` | `:582-596` | `:1145` → `ERR_NOTAVAIL` |
| WIZ752SR-12x `0207e95` (2019-09-20) App | `segcp.c:309` | `:654` | `:1341` |
| W55RP20-S2E `upstream/4port` `20236fe` (2026-08-13) | — | `:768` | `:2486` |
| W55RP20-S2E `main` `44f0393` | `:299` | `:516` | `:1374` |

(경로: 5XXSR-RP `port/app/configuration/src/`, 750SR `Projects/S2E_App/src/Configuration/`, 752SR `Projects/App/src/Configuration/`, W55RP20 `port/app/configuration/src/`. 각 저장소 Boot 쪽에도 같은 구조가 있다.)

W55RP20-S2E 는 1CH·2CH·4port·GreenCS·NICOM·SPI·Platypus 등 로컬 모든 브랜치를 `git grep "case SEGCP_FR"` 로 훑었고 전부 GET/SET 두 곳뿐이다.

### 2-1. GET 분기(값 없음) = 동작 `[소스]`
`WIZ5XXSR-RP-C segcp.c:513-523` (750SR·752SR·W55RP20 동일):
```
case SEGCP_FR:
    if(권한 SET|WRITE) {
        // #20161110 Hidden option, Local port number [1] + FR cmd => K! (EEPROM Erase)
        if(local_port == 1)  ret |= SEGCP_RET_ERASE_EEPROM | SEGCP_RET_REBOOT;
        else                 ret |= SEGCP_RET_FACTORY | SEGCP_RET_REBOOT;
    } else ret |= SEGCP_RET_ERR_NOPRIVILEGE;
```
- 공장 초기화 처리: `device_set_factory_default()` = `set_DevConfig_to_factory_value()` + `save_DevConfig_to_storage()` (`deviceHandler.c:54-58`, `segcp.c:121-122`). 설정 구조체를 공장값으로 채워 저장할 뿐이다.
- EEPROM 지우기 처리: `erase_storage(STORAGE_MAC); erase_storage(STORAGE_CONFIG);` (`segcp.c:131-132`). **MAC 과 설정 섹터를 지운다.**

### 2-2. SET 분기(값 있음) = 거부 `[소스]`
`WIZ5XXSR-RP-C segcp.c:1247-1253`:
```
case SEGCP_SV: case SEGCP_RT: case SEGCP_FR: case SEGCP_PW: case SEGCP_UI:
    ret |= SEGCP_RET_ERR_NOTAVAIL;
```
오류 비트가 서면 같은 요청의 SV/RT/FR 처리가 통째로 취소된다(5XXSR-RP `segcp.c:111` — `segcp_ret_handler` 가 오류 비트가 서 있으면 처리 블록을 건너뜀).

### 2-3. 이력: 750SR 에서 `FR` 값은 처음부터 없었다 `[소스]`
- WIZ750SR `7c9d63d`(2016-05-16, v1.0.0dev): GET `FR` 은 무조건 공장 초기화, SET `FR` 은 `ERR_NOTAVAIL`. 같은 파일에 `case SEGCP_K1:`(`K!`) 이 `ERASE_EEPROM | REBOOT`.
- WIZ750SR `6f1e841`(2016-12-05, v1.1.0stable): "Hidden option" 추가 — `local_port == 1` 이면 `FR` 이 `ERASE_EEPROM`.
- 태그 v1.1.0 · v1.2.0 · v1.3.0 · v1.4.0 · v1.4.5 의 `segcp.c` 에서 SET `FR` 모두 `ERR_NOTAVAIL`.
- WIZ752SR-12x `fe49e5d`(2018-02-02, Initial commit)부터 같은 구조.
- 즉 750SR(107/108SR 호환 계열)에서 EEPROM 지우기는 `K!` 또는 "로컬 포트 1 + `FR`" 이고 **`FR0` 형태는 한 번도 없었다.**

## 3. 107/108SR
- 107SR·108SR 전용 FW 저장소는 GitHub(`Wiznet` 조직 검색: WIZ107SR, WIZ108SR, 107SR)과 로컬에 **없다.** `미확인`
- `Wiznet/WIZ750SR` README 는 "Software and Hardware compatible with WIZ107/108SR S2E Module"(`README.md:42`)이라고 적는다. 750SR 소스가 근거가 되는 범위는 여기까지다. `[소스]` 107/108 의 `FR` 동작 자체는 이 소스로 단정하지 않는다.
- 이 저장소의 `107_108_config/sec.py:121-127`(VB.NET 원본 변환)는 공장 초기화 패킷을 `PW…\r\nFR\r\nRT\r\n` 로 **값 없는 `FR`** 을 보낸다. `[소스]`(툴)
- 원본 CLI 툴 `Wiznet/WIZnet-S2E-Tool`(`WIZMakeCMD.py:119-123`, `wiz75x_loopback_test.py:132`)도 `["FR", ""]` 만 쓴다. `FR0` 사용처는 없다. `[소스]`

## 4. 툴 쪽 (이 저장소)
- `"0"` 도입: 2019-03-07 `0663e2e`(최초 import)에 `factory_reset(…, param)` 가 이미 있고, `f584d55`(2019-04-08)에서 `do_factory_reset(mode)` 가 `'setting'` → `""`, `'firmware'` → `"0"` 으로 호출한다. 커밋 메시지·주석에 `"0"` 의미 설명은 없다.
- 현재: `main_gui.py:7218-7225` 가 같은 호출을 한다. firmware 메뉴 활성 조건은 `spec.family in ("security", "security_two_port")`(`main_gui.py:1932-1943`, 커밋 `e52ab7b` 2026-05-08 에 하드코딩 `SECURITY_DEVICE` 목록에서 spec 기반으로 전환).
- 활성 기종: IP20, W232N, W55RP20-S2E(1CH), 2CH, 4CH, WIZ510SSL, WIZ5XXSR-RP(+E-SAVE). **WIZ2000 spec 은 이 저장소에 없다**(`specs/devices/`).
- 성공 판정: `factory_result`(`main_gui.py:7152`)는 응답 바이트가 있으면 "Factory reset complete!" 를 띄운다. `FR0` 요청의 헤더(MA/PW) 응답으로도 성공 팝업이 뜰 수 있다. `[추정]`(코드만 읽음, 실기기 미확인)

## 5. 남은 확인
| # | 항목 | 방법 |
| --- | --- | --- |
| 1 | `"0"` 을 받던 모델·FW 이름 | 담당자에게 서면(메일·메신저 캡처)으로 확인해 이 문서에 출처 추가 |
| 2 | 그 FW 의 소스 | 담당자에게 저장소 위치 확인 (로컬·GitHub 공개분에는 없음) |
| 3 | 현재 기종에서 `FR0` 응답 | 실기기에서 `FR0` 를 보내 응답(`ER` 여부) 확인 — 시험서 규칙상 사용자 승인 후 |

## 6. W55RP20 계열 판별 (2026-10-21, 담당자 확인: 오래된 모델 담당자는 없음)

대상: W55RP20-S2E(1CH), 2CH, 4CH(=`upstream/4port`). 3CH(GreenCS)는 공식 제품이 아니라 제외하되 소스는 같은 구조라 함께 확인했다.

### 6-1. 두 메뉴가 보내는 것과 FW 결과 `[소스]`
| 툴 메뉴 | 전송 바이트 | `parse_SEGCP` 결과 | 분기 | FW 결과 |
| --- | --- | --- | --- | --- |
| Factory default settings | `FR\r\n` | `*param == 0` | GET (`case SEGCP_FR`) | `ret \|= SEGCP_RET_FACTORY \| SEGCP_RET_REBOOT` → `device_set_factory_default()` → 재부팅 |
| Factory default firmware | `FR0\r\n` | `param = "0"` (`strcpy(param, &pmsg[2])`) | SET (`case SEGCP_FR` 가 `SV RT PW` 와 같은 묶음) | `ret \|= SEGCP_RET_ERR_NOTAVAIL` → **아무것도 실행하지 않음**, 같은 요청의 후속 처리도 취소 |

- 같은 판별을 `upstream/4port`(`20236fe`) `segcp.c:489`(GET/SET 판별), `:768-778`(GET FR), `:2486`(SET FR), `:377-440`(`parse_SEGCP`), `:290`(`SEGCP_RET_FACTORY`), `main`(`44f0393`) `:299/:516/:1374`, `upstream/2Port`(`78517ea`), `upstream/GreenCS`(`29ce076`) `:316` 에서 확인했다. 파서의 특수 처리(`*param = 1`)는 `OC LC PK` 에만 있고 `FR` 과 무관하다(`:418-430`).
- `FR` 이 값을 받는 분기가 이 계열 어느 브랜치에도 없다. `FR0` 이 공장 초기화로 해석될 경로는 없다.

### 6-2. 공장 초기화가 실제로 하는 일 (4port) `[소스]`
- `device_set_factory_default()` = `set_DevConfig_to_factory_value()` + `save_DevConfig_to_storage()` (`deviceHandler.c:41-44`). 채널 수(`DEVICE_UART_CNT`)만큼 반복해 각 채널을 공장값(예: 로컬 포트 `5000 + ch`, `ConfigData.c:88-100`)으로 되돌리고 저장한다.
- 뒤이어 `SEGCP_RET_REBOOT` 처리로 재부팅한다(`segcp.c:340` 부근).

### 6-3. 판정
- **실제 공장 초기화를 수행하는 것은 `Factory default settings`(`FR`) 하나뿐이다.**
- **`Factory default firmware`(`FR0`)는 이 계열에서 아무 일도 하지 않는다.** 담당자 전언("0 은 예전 모델의 EEPROM 지우기, W55RP20 에서는 쓰지 않음")과 소스가 일치한다.
- 남길 것: **settings 만.** firmware 메뉴는 W55RP20 계열에서 숨기거나 비활성이 맞다.

### 6-4. 남기는 settings 쪽의 주의점 `[소스]`
- GET 분기의 숨은 옵션: **CH1 로컬 포트가 `1` 이면 `FR` 이 공장 초기화가 아니라 MAC·설정 섹터 삭제 + 재부팅**이 된다(`4port segcp.c:771-772`, 조건은 `network_connection[0].local_port == 1`). 1CH·2CH 는 `network_connection.local_port == 1`.
- 이 값이 `1` 인 장치에서 `Factory default settings` 를 누르면 MAC 이 지워진다. 팝업은 "모든 설정이 초기화된다"고만 말한다. 방어 필요 여부는 사용자 결정이다(현재 툴은 이 조건을 검사하지 않는다 — `main_gui.py:7200-7227`).
- 공장 초기화 후 장치 IP·포트가 공장값으로 돌아가므로 재검색이 필요하다(시험서 C8-2).

### 6-5. 툴 변경 시 대상 (미적용)
- `main_gui.py:1932-1943` 가 firmware 메뉴를 `spec.family in ("security", "security_two_port")` 로 켠다. W55RP20-S2E, 2CH, 4CH 가 여기 들어간다.
- 같은 family 의 IP20, W232N, WIZ510SSL 은 이 계열이 아니라 소스로 판정하지 못했다. WIZ5XXSR-RP 는 5XXSR-RP-C 소스에서 SET `FR` 이 `NOTAVAIL` 임을 확인했다(§2). 따라서 기종 조건을 W55RP20 계열만으로 좁힐지 family 전체로 할지는 사용자 결정이다.
