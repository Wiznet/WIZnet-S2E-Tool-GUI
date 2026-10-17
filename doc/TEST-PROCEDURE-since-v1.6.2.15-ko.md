# v1.6.2.15 이후 변경 사항 — 변경 목록과 시험 절차서

> 대상: v1.6.2.15(2026-08-28 릴리즈) 이후 `develop` 에만 있는 변경 (병합 제외 약 100커밋).
> 용도: 담당자가 아닌 동료가 이 문서만 보고 시험하고 결과를 기록한다.
> 변경 내역의 영문 정본은 `CHANGELOG.md` 의 `[Unreleased]` 항목이다.

---

## 0. 시험 전에

### 0-1. 시험 대상 확인

| 항목 | 방법 | 기록 |
| --- | --- | --- |
| 실행 방식 | 소스 `uv run python main_gui.py` 또는 빌드된 exe | |
| 커밋 | `git log --oneline -1` | |
| 버전 | 툴 About 창 / `version` 파일 | |

> exe 로 시험하려면 담당자에게 최신 `develop` 빌드를 요청한다. 담당자의 마지막 빌드(`1.6.2.24-dev3`)는
> 이 목록의 일부(호환표 원격 갱신·재확인 등)를 포함하지 않는다.

### 0-2. 장비 구분

시험은 세 단계다. 가진 장비에 맞춰 가능한 데까지 한다. 못 한 항목은 "미시험"으로 두고 사유를 적는다.

| 단계 | 필요한 것 | 범위 |
| --- | --- | --- |
| A. 자동 시험 | PC 만 | 코드 수준 회귀 |
| B. 가짜 장치 | PC 만 | 검색·설정·Apply 흐름 (장치 12기종 + WIZ550 + WIZ1x0) |
| C. 실기기 | 해당 장치 + 같은 서브넷 | 실제 동작 확인 |

### 0-3. 결과 기록 방법

각 시험의 `결과` 칸에 **PASS / FAIL / 미시험** 중 하나를 적고, FAIL 이면 화면 캡처와 로그를 남긴다.

- 로그 위치: `C:\Users\<사용자>\.wizconfig\logs\` (`wizconfig.log`)
- 설정 파일: `C:\Users\<사용자>\.wizconfig\device_search_timing.yaml`
- 시험 중 오류 팝업이 뜨면 문구를 그대로 옮겨 적는다.

---

## 1. 변경 목록 (시험 ID 대응)

| 영역 | 변경 | 시험 ID |
| --- | --- | --- |
| W55RP20-S2E-4CH | 채널 #2·#3 탭, DTR/DSR, Serial interface 선택, 채널별 도메인 입력, PPPoE, SSL/MQTT 탭 숨김 | C1, C2, C3 |
| W55RP20-S2E-3CH | 준비 단계 (실기기 미검증) | B3 |
| 설정 저장 | W55RP20 에서 Apply 가 저장되지 않던 문제(SC) | C2 |
| 설정 저장 | NP(연결 비밀번호) 10자 이상 시 저장 전체 실패 → 9자 상한 | C4 |
| unicast | Local IP 입력이 접속 IP 를 미리 바꿔 Apply 실패 | C5 |
| unicast | ping.exe 제거(콘솔창 깜빡임·거짓양성 방지) | C6 |
| Apply 이후 | Post-Apply Reboot Delay, 완료 창 리부팅 안내 | C5, B4 |
| 고급 옵션 | Advanced Search Options 에 지연·타임아웃·로그레벨·Verbose Wire Log 노출 | B4 |
| WIZ1x0SR | 직접-IP 검색(TCP:1461) | B2, C7 |
| WIZ752SR-12x | User I/O 탭·GPIO·완료 팝업·편집 중 값 덮어쓰기·응답 분할 | C8 |
| WIZ550 | DNS·packing delimiter·serial trigger·Modbus 필드 편집 | C9 |
| FW from Git | WIZ750SR Boot↔App 호환 경고·차단, 호환표 재확인 | B5, C10 |
| FW from Git | 배포처 추가(5종), 미지원 안내, 이미지 검증, IP 대역 확인 | B6, C11 |
| 기타 | 커스텀 FW 버전 접미사, CSV Protocol 컬럼, F4 중복, TCP timeout 박스, Escape 힌트, IP20 고속 baud | B7 |
| 내부 | 소켓 재생성 방지, 크래시 방어, 버전 파서 통일 | A1, C12 |

---

## 2. A 단계 — 자동 시험 (PC 만)

### A1. 전체 pytest

```powershell
cd D:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

- **다른 프로그램(특히 가짜 장치)을 켠 채 돌리지 않는다.** 포트가 겹쳐 멈춘다. 단독 실행.
- 기대: `818 passed` 부근 (xfail/skip 일부 정상). `failed` 가 0.

| 결과 | 비고 |
| --- | --- |
| | |

---

## 3. B 단계 — 가짜 장치로 시험 (PC 만)

### 준비

터미널 1 에서 가짜 장치 묶음을 띄운다. 시험하는 동안 켜 둔다.

```powershell
uv run python -m tests.fake_fleet
```

터미널 2 에서 툴을 띄운다: `uv run python main_gui.py`

- 가짜 장치는 WIZ752SR-12x(UDP 50001), WIZ550SR(UDP 6550), WIZ1x0SR(UDP 1460 + TCP 1461)이다.
- 툴의 네트워크 어댑터는 **가짜 장치가 도는 PC 의 NIC** 를 고른다.
- WIZ1x0SR 은 **"WIZ1x0SR Search" 체크박스를 켜야** 검색된다.

### B1. 기본 검색·설정 왕복

| 단계 | 기대 |
| --- | --- |
| 1. Search 클릭 | 목록에 WIZ752SR-12x, WIZ550SR 이 나타난다 |
| 2. WIZ752SR-12x 선택 | 설정값이 채워지고 **User I/O 탭**이 보인다 |
| 3. 값 하나 변경(예: 채널0 Baud) 후 F4 | "Device configuration complete!" 팝업이 **반드시** 뜬다 |
| 4. 다시 Search 후 같은 장치 선택 | 변경한 값이 유지된다 |

| 결과 | 비고 |
| --- | --- |
| | |

### B2. WIZ1x0SR 직접-IP 검색

| 단계 | 기대 |
| --- | --- |
| 1. 검색 모드를 **IP Address** 로 | IP 입력칸이 활성화된다 |
| 2. "WIZ1x0SR Search" 체크 + 가짜 장치 IP(`192.168.7.60`) 입력 후 Search | 상태바에 "not supported" 가 아닌 실제 검색 안내, 목록에 WIZ1x0SR 표시 |
| 3. 체크를 끄고 다시 Search | 상태바에 체크를 켜라는 안내 |
| 4. 없는 IP 를 넣고 Search 연타 | 앱이 멈추지 않고, 중복 검색이 쌓이지 않는다 |

| 결과 | 비고 |
| --- | --- |

### B3. 3CH (준비 단계 — 정식 지원 아님)

가짜 장치 구성(`config/fake_fleet.yaml`)에서 3CH 를 지정해 띄우면 Channel #2 탭이 보이는 정도까지 확인한다.
**실기기 검증이 없으므로 실패해도 결함으로 단정하지 않고 기록만 한다.**

| 결과 | 비고 |
| --- | --- |

### B4. Advanced Search Options 와 Reboot Delay

메뉴: **Options → Advanced Search Options**

| 단계 | 기대 |
| --- | --- |
| 1. 다이얼로그를 연다 | 아래 항목이 보인다: "Device Query Timing (Phase 3)" 그룹의 **Post-Apply Reboot Delay**(0.0~5.0, 기본 1.0) · **SET Response Delay** · **SET Response Timeout** · **SET Response Timeout (WIZ5XXSR-RP)**, "TCP Settings" 그룹의 **Scan Timeout**, "Debug / Experimental" 그룹의 **Log Level** · **Verbose Wire Log** |
| 2. **SET Response Timeout** 을 `5` 로 바꾸고 확인 | 다시 열었을 때 `5` 가 유지된다 |
| 3. 범위 밖 값(예: Reboot Delay `9`) 입력 | 거부되거나 범위로 보정된다 (저장 후 재시작해도 범위 안) |
| 4. **Verbose Wire Log** 를 켜고 Search → 설정 Apply | `wizconfig.log` 에 `[WIRE]` 로 시작하는 요청/응답 바이트 줄이 생긴다 |
| 5. Verbose 를 끄고 같은 동작 | `[WIRE]` 줄이 더 생기지 않는다 |
| 6. Options → Log Level 을 DEBUG 로 | 이후 로그에 DEBUG 줄이 나온다 (재시작 불필요) |
| 7. **Restore Defaults** 버튼 | 값이 기본값으로 돌아간다 |

| 결과 | 비고 |
| --- | --- |

### B5. FW from Git — WIZ750SR 호환 경고 (네트워크 필요)

버튼: **Firmware Upload ▾ → FW from Git**. 장치를 WIZ750SR 로 선택한 상태에서 연다.
(WIZ750SR 가짜 장치는 `device: WIZ750SR`, `fw_version` 을 지정해 띄운다.)

| 현재 App | 대상 | 기대 |
| --- | --- | --- |
| 1.2.x | 1.4.x | 목록에 보이되 **선택 불가** |
| 1.4.x | 1.2.x | 목록에 보이되 **선택 불가** |
| 1.3.0~1.3.2 | 1.3.3 이상 | **선택 불가** |
| 1.3.3 | 1.4.x | **경고 없이 통과** |
| 1.3.x | 1.2.x | 경고 확인 창 |
| (임의) | 호환표에 없는 더 새 버전 | 막지 않고 "호환표보다 새 버전" 안내 표시 |

- 위 경고가 보이지 않으면 호환표 로딩 실패다. 로그의 `[FW]` 줄을 첨부한다.
- 호환표 **원격 갱신**(GitHub 의 `config/fw_compat.json` 확인)은 그 파일이 master 에 올라가기 전에는 동작하지 않는다
  (지금 404). 이 항목은 시험 대상이 아니다.

| 결과 | 비고 |
| --- | --- |

### B6. FW from Git — 배포처·미지원·이미지 검증 (네트워크 필요)

| 단계 | 기대 |
| --- | --- |
| 1. WIZ5XXSR-RP / WIZ752SR-12x / WIZ107SR / WIZ108SR 각각 FW from Git 열기 | **해당 제품의** 릴리즈 목록이 나온다 (다른 제품 펌웨어가 나오면 FAIL) |
| 2. WIZ510SSL / WIZ5XXSR-RP_E-SAVE / W55RP20-S2E-2CH 선택 | "FW from Git 을 지원하지 않습니다" + 사유, Firmware Upload 안내. **이슈 등록 제안은 없다** |
| 3. 등록되지 않은 임의 장치 | 다른 제품 펌웨어로 대체되지 않고 중단 안내 |
| 4. 장치 IP 와 PC IP 가 **다른 대역**인 상태에서 FW from Git / 파일 선택 | 업로드 전에 "대역 불일치" 경고가 나온다 |
| 5. 병합본(Boot+App) 이미지를 로컬 파일로 선택 | 차단되고 사유가 표시된다 |

| 결과 | 비고 |
| --- | --- |

### B7. 기타 소형 변경

| 항목 | 방법 | 기대 | 결과 |
| --- | --- | --- | --- |
| 커스텀 FW 접미사 | 가짜 장치 `fw_version: "1.2.5_GreenCS"` 로 띄워 Search | 예외 없이 검색·설정 진행 | |
| CSV Protocol 컬럼 | WIZ550/WIZ1x0 검색 → CSV 저장 → 다시 열기 | `Protocol` 컬럼이 있고 로드 후에도 바이너리 장치로 인식 | |
| 구 CSV | `Protocol` 컬럼 없는 옛 CSV 열기 | 정상 로드 | |
| F4 중복 | 실행 로그 확인 | `Ambiguous shortcut overload: F4` 가 없다 | |
| TCP timeout 박스 | WIZ752SR-12x 선택 | 빈 "TCP timeout" 상자가 남지 않는다 | |
| Escape 힌트 | 터미널 패널에서 Escape 체크 토글 | 입력창 안내·툴팁이 ON/OFF 에 맞게 바뀐다 | |
| About | About 창 | `(BETA - 4CH)` 표기가 없다 | |
| 소켓 | Search 를 5회 이상 반복 후 Apply | 매번 완료 팝업이 뜬다 | |

---

## 4. C 단계 — 실기기 시험

장치가 없는 항목은 "미시험". 시험 전 **장치 설정을 백업**(툴의 CSV 저장 또는 화면 캡처)해 둔다.

### C1. W55RP20-S2E-4CH — 화면 구성 (동료 확인 이력 있음)

| 단계 | 기대 |
| --- | --- |
| 1. Search → 4CH 선택 | Channel #0~#3 탭이 모두 보인다 |
| 2. 각 채널에서 Flow control 목록 확인 | **DTR/DSR** 이 선택지에 있다 |
| 3. Serial interface | 읽기전용이 아니라 TTL / RS-232 / RS-422 / RS-485 / RS-485 Reverse 선택 가능 |
| 4. 각 채널 Remote host 에 도메인(`test.example.com`) 입력 | 입력이 거부되지 않는다 |
| 5. 탭 목록 | **SSL/MQTT(certificate) 탭이 없다**, PPPoE 탭은 있다 (DDNS/Network Protocol 그룹은 PPPoE 탭에서 숨김) |

| 결과 | 비고 |
| --- | --- |

### C2. W55RP20 — Apply 가 저장되는지 (SC 수정)

| 단계 | 기대 |
| --- | --- |
| 1. 채널0 Baud 와 채널1 Baud 를 바꾼다 | |
| 2. F4(Apply) | 완료 팝업이 뜬다 (예전에는 성공 메시지 없이 저장 안 됨) |
| 3. 장치 재검색 후 선택 | 변경한 값이 **그대로 남아 있다** |
| 4. 장치 전원을 껐다 켠 뒤 다시 확인 | 값이 유지된다 (플래시에 저장됨) |

| 결과 | 비고 |
| --- | --- |

### C3. 4CH — 값 범위 (FW 문서 기준)

| 필드 | 범위 확인 |
| --- | --- |
| OP / AO / TO / JO | 0~3 (SSL/MQTT 선택지 없음) |
| Flow control | 0~5 |
| Keep-alive (KI/KE) · 재접속 (RS/RE) · 비활성 (XS/XE) | 최소 1000 ms |

범위 밖 값을 넣으면 Apply 전에 입력 오류로 막히는지 본다.

| 결과 | 비고 |
| --- | --- |

### C4. NP(연결 비밀번호) 길이

대상: WIZ750SR / WIZ750SR-1xx / WIZ752SR-12x / W55RP20 / WIZ5XXSR-RP

| 단계 | 기대 |
| --- | --- |
| 1. NP 에 9자 입력 후 Apply | 정상 저장 |
| 2. NP 에 10자 이상 입력 | 입력이 막히거나 오류로 안내되고, **다른 설정까지 같이 실패하지 않는다** |
| 3. 이후 다른 값(Baud 등) 변경 후 Apply | 정상 저장 |

| 결과 | 비고 |
| --- | --- |

### C5. TCP unicast + Local IP 변경 (고객 긴급 건)

대상: WIZ750SR (고객 기기와 동일 계열). **같은 서브넷, 사용 가능한 여유 IP 하나 필요.**

| 단계 | 기대 |
| --- | --- |
| 1. 검색 모드를 **TCP unicast** 로 하고 장치 IP 입력 후 Search | 장치가 목록에 나온다 |
| 2. 장치 선택 → Local IP 칸을 **새 IP 로 타이핑**(아직 Apply 안 함) | 접속 대상(검색 IP)이 **바뀌지 않는다** |
| 3. F4(Apply) | 완료 팝업이 뜬다. 창에 **리부팅 대기 안내**가 있다 (예전에는 Apply 실패) |
| 4. 바로 Search | 리부팅 중에 "unreachable" 로 오인되지 않는다 (Post-Apply Reboot Delay 1초 기본) |
| 5. 몇 초 뒤 새 IP 로 Search | 장치가 새 IP 로 나타난다 |
| 6. Local IP 를 원래대로 돌려놓는다 | |

| 결과 | 비고 |
| --- | --- |

### C6. ping.exe 제거

| 단계 | 기대 |
| --- | --- |
| 1. TCP unicast 검색을 반복 | **검은 콘솔창이 깜빡이지 않는다** |
| 2. 같은 서브넷의 **존재하지 않는 IP** 로 unicast 검색 | 빠르게 "연결 안 됨" 으로 판정된다 (거짓 성공 없음) |
| 3. 작업 관리자에서 `ping.exe` | 검색 중 생성되지 않는다 |

| 결과 | 비고 |
| --- | --- |

### C7. WIZ1x0SR 실기기

B2 와 같은 절차를 실기기로. 추가로 직접-IP 검색 후 설정 변경·Apply 가 정상인지 본다.

| 결과 | 비고 |
| --- | --- |

### C8. WIZ752SR-12x

| 단계 | 기대 |
| --- | --- |
| 1. 장치 선택 | **User I/O 탭**이 보인다 |
| 2. User I/O 탭을 연 채 10초 이상 대기 | GPIO 현재값이 갱신된다 |
| 3. GPIO 출력 콤보를 High 로 바꾸고 **15초 기다린 뒤** F4 | 선택값이 **Low 로 되돌아가지 않고** High 가 전송된다 |
| 4. 설정 변경 Apply | 완료 팝업이 뜬다 |
| 5. TCP timeout 영역 | 빈 상자가 없다 |
| 6. 도메인(19자 이상)을 Remote host 에 넣고 Search 반복 | 검색·조회가 멈추거나 무응답이 되지 않는다 |

| 결과 | 비고 |
| --- | --- |

### C9. WIZ550 (SR / S2E / WEB)

| 필드 | 방법 | 기대 |
| --- | --- | --- |
| DNS 사용 / 도메인 | 체크 후 도메인 입력, Apply, 재검색 | 값 유지 (WIZ550 에서만 보임) |
| Packing delimiter | 1~4바이트 hex 입력 | 길이만큼만 표시·유지 |
| Serial trigger | 3칸에 `2B 2B 2B` 입력 | `2B2B2B` 로 유지 |
| Modbus | Modbus 빌드(164B)에서 콤보 변경 | 유지. 그 외 빌드는 콤보가 잠겨 있다 |

| 결과 | 비고 |
| --- | --- |

### C10. FW from Git — WIZ750SR 실기기

B5 의 표를 실제 장치의 App 버전으로 확인한다. **실제 업로드는 하지 않는다**(Boot 호환이 깨지면 ISP tool 로 전체 재기록이 필요하다).
목록의 선택 가능/불가 표시와 경고 문구만 본다.

| 결과 | 비고 |
| --- | --- |

### C11. FW from Git — 업로드 사전 점검

| 단계 | 기대 |
| --- | --- |
| 1. 장치와 PC 가 다른 대역 | 업로드 시작 전에 "대역 불일치" 로 안내되고 **FW 명령이 전송되지 않는다**(장치가 대기 모드로 빠지지 않음) |
| 2. 같은 대역에서 WIZ550SR/S2E/WEB 로 FW from Git | 이미지 검증을 통과한 뒤 업로드가 시작된다 |

> 실제 펌웨어 업로드는 장치 복구 수단이 있을 때만 한다.

| 결과 | 비고 |
| --- | --- |

### C12. IP20 검색 안정성 (Win11)

고객이 Win11 에서 IP20 검색 중 앱이 통째로 닫히는 문제를 보고했다. 원인은 확정되지 않았고 방어 코드만 들어갔다.

| 단계 | 기대 |
| --- | --- |
| 1. Win11 PC, IP20 장치 연결 | |
| 2. Search 를 30회 이상 반복 (장치를 끄고 켜기, 케이블 뽑기 포함) | 앱이 닫히지 않는다 |
| 3. 비정상 종료가 있으면 | `wizconfig.log` 마지막 줄(예외 기록)을 첨부 |

| 결과 | 비고 |
| --- | --- |

### C13. IP20 고속 Baud

FW 1.2.1 이상 IP20 에서 Baud 에 1M / 2M / 4M / 8M 이 선택되는지, Apply 후 유지되는지 확인.

| 결과 | 비고 |
| --- | --- |

---

## 5. 알려진 한계 — 결함으로 보고하지 않는다

- **3CH** 는 준비 단계다. 실기기 검증이 없다.
- 호환표 **원격 갱신**은 `config/fw_compat.json` 이 master 에 올라가기 전까지 동작하지 않는다.
- FW from Git 에는 3CH/4CH 용 공개 FW 이미지가 없다(공개 릴리즈에 없음). 4CH 장치에서 "미지원" 안내가 나오는 것이 정상이다.
- 프리셋 값이 Advanced 설정과 어긋나는 문제(`BUG-PRESET-OVERRIDE`)는 아직 고치지 않았다.
- 장치가 응답 일부만 돌려주는 경우(짧은 응답)를 "Device rebooted" 로 안내하는 동작은 이대로 둔다.
- IP20 Win11 크래시의 근본 원인은 미확정이다.

## 6. 결과 요약

| 단계 | 총 항목 | PASS | FAIL | 미시험 |
| --- | --- | --- | --- | --- |
| A | 1 | | | |
| B | 7 | | | |
| C | 13 | | | |

시험자 / 일시 / 장비 구성:

FAIL 항목은 화면 캡처, 로그(`wizconfig.log`), 재현 단계를 담당자에게 전달한다.
