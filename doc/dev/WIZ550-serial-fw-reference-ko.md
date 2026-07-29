# WIZ550 시리얼(UART) 동작 — 펌웨어 권위 레퍼런스

> **목적:** WIZ550 계열의 시리얼 설정(baud/data/stop/parity/flow)이 펌웨어에서 *실제로* 어떻게 동작하는지를 소스 근거로 1회 정리한다. **매 작업마다 FW 소스를 재분석하지 않기 위한 단일 진실 소스.**
>
> **YAML이 모든 것의 기준**이며, YAML(`specs/devices/WIZ550*.yaml`)은 이 문서의 FW 사실과 일치해야 한다. UI 코드는 YAML에서 파생한다.

## 기준 펌웨어 소스 (provenance)

| 장치 | 소스 위치 | 비고 |
|------|----------|------|
| WIZ550SR | `D:\user\Documents\GitHub\WIZ550SR\WIZ550SR_App\src\PlatformHandler\uartHandler.c` (+ `ConfigData.h`) | 분석 시점 기준. FW 변경 시 본 문서 갱신 필요 |
| WIZ550S2E | `uartHandler_wiz550s2e.c` (+ `ConfigData_wiz550s2e.h`) | 인계받은 S2E 펌웨어 소스 |
| WIZ550WEB | **미확보** | 펌웨어·실장 모두 없음 → 아래 표 "미확인" |

> ⚠️ 이 문서는 위 소스 *그 버전* 기준이다. 펌웨어가 갱신되면 file:line과 결론을 재확인하고 본 문서를 고칠 것.

---

## 핵심 진실표 (SR vs S2E)

| 필드 | WIZ550SR | WIZ550S2E | 비고 |
|------|----------|-----------|------|
| **baud** | {600,1200,2400,4800,9600,19200,38400,57600,115200,**230400**} — **300·460800 없음** | {**300**,600,…,115200,**230400**} — **460800 없음** | 둘 다 최대 230400. SR만 300 제외 |
| **data_bits** | **8 전용** (7-bit 컴파일 제외) | **7·8 지원** | ★ 가장 중요한 차이 |
| **stop_bits** | 1 / 2 | 1 / 2 | 동일 |
| **parity** | None(0) / Odd(1) / Even(2) | None / Odd / Even | 동일 |
| **flow_control** | **DEAD 필드** (적용 안 됨, 아래 버그) | **정상** — None/RTS-CTS/RS422/RS485 | ★ SR은 dead, S2E는 동작 |
| 8bit+parity | → 9-bit 프레임 자동 | (FW 내부 처리) | UI 별도 처리 불필요 |

---

## 상세 근거 (file:line)

### WIZ550SR — `uartHandler.c`
- **baud_table** (72–83): `{600,1200,2400,4800,9600,19200,38400,57600,115200,230400}`. `set` 시 valid 검사(429–430) — 목록에 없는 값(300·460800)은 거부 후 fallback.
- **data_bits** (483–510): 기본 `USART_WordLength_8b`. `data_bits==8 && parity!=none` → `9b`. 7-bit 블록은 `#if (DATA7BIT_ENABLE == 1)`인데 **`uartHandler.h:23` `#define DATA7BIT_ENABLE 0`** → 컴파일 제외. **7 넣어도 무시(8 유지).**
- **stop_bits** (440–451): stop_bit1→1, stop_bit2→2, default→1.
- **parity** (454–468): none/odd/even, default none.
- 🐞 **flow_control 버그** (471–481): `switch(serial->parity)` ← `serial->flow_control`이 아니라 **parity를 잘못 참조.** 따라서 flow_control 필드는 구조체에 저장·전송되지만 **UART HW에 적용되지 않음**(dead field). 실제 HW flow는 parity 값으로 의도치 않게 결정됨.
  - **대응 방침:** config tool은 flow_control 값을 **그대로 전송**(보정하지 않음). FW가 나중에 고쳐지면 UI 보정이 오히려 혼란. → WONTFIX, 주석만 유지.

### WIZ550S2E — `uartHandler_wiz550s2e.c`
- **baud_table[11]** (17–29): `{300,600,1200,2400,4800,9600,19200,38400,57600,115200,230400}`. **300 포함, 460800 없음.**
- **data_bits** (58–69): `word_len7→WLEN7`, `word_len8→WLEN8`, default→8. **7-bit 무조건 지원** (DATA7BIT 가드 없음).
- **stop_bits** (72–82): 1 / 2.
- **parity** (85–100): none/odd/even.
- **flow_control** (105+): `switch(serial->flow_control)` ← **올바름.** flow_none / flow_rts_cts / flow_rs422(/rs485) 동작. **SR과 달리 정상 작동.**

### WIZ550WEB
- **미확인.** 펌웨어 소스·실장 둘 다 없음. profile 파싱은 `uart0_*`/`uart1_*` 이중 UART 키 사용(`WIZ550Profile.parse_web`). 시리얼 제약은 FW 확보 전까지 단정 불가.

---

## YAML 정합 감사 (4단: FW ↔ YAML choices ↔ UI 콤보 ↔ 바이너리)

### WIZ550S2E (`specs/devices/WIZ550S2E.yaml`)

| 필드 | YAML 현재 | FW 사실 | 판정 | 조치 |
|------|----------|---------|:---:|------|
| baud_rate | 300~**460800** (12) | 300~230400 (460800 없음) | ❌ | 460800 제거 (B) |
| data_bits | `readonly "8-bit"` | 7·8 지원 | ❌ | dropdown 7/8 (A) |
| parity | 0/1/2 | none/odd/even | ✅ | — |
| stop_bits | 1/2 | 1/2 | ✅ | — |
| flow_control | None/RTS-CTS (2) | None/RTS-CTS/RS422/RS485 (4) | ⚠️ | 노출 여부 제품 결정 (B) |

> **참고 — UI 동작 현실:** WIZ550 메인 UI(`fill_devinfo_wiz550`)는 YAML `ui.fields`를 읽지 않고 `ch0_*` 위젯을 직접 조작한다. 따라서 S2E data_bits는 이미 콤보(7/8)로 편집 가능 — YAML `readonly` 수정은 **스펙 정합(계약) 교정**이고 동작 변화는 없음. SR data_bits 잠금만 UI 코드 변경(widget_override 적용)이 필요하다.

### WIZ550SR (`specs/devices/WIZ550SR.yaml`)

| 필드 | YAML 현재 | FW 사실 | 판정 |
|------|----------|---------|:---:|
| data_bits | `readonly "8-bit"` | 8 전용 | ✅ (정답) |
| flow_control | BUG NOTE 주석 보유 | dead field | ✅ (문서화됨) |
| baud / parity / stop | (미대조) | {600~230400} 등 | ⏳ B에서 대조 |

---

## 적용 정책 요약 (UI는 이 표를 따른다)

| 장치 | data_bits | flow_control |
|------|-----------|--------------|
| WIZ550SR | **8 고정 → UI 잠금** (`widget_overrides: ch0_databit: enabled:false`) | 값 그대로 전송 (dead, 보정 안 함) |
| WIZ550S2E | **7·8 허용** (잠금 없음) | 정상 — UI 매핑이 FW와 일치해야 (RS422/485 노출은 미정) |
| WIZ550WEB | 미확인 (보류) | 미확인 (보류) |

---

## 관련 문서
- 코드 구조: [ARCHITECTURE-ko.md](ARCHITECTURE-ko.md) (WIZ550 프로토콜 요약)
- 이슈 추적: 프로젝트 루트 `TASKS.md`
