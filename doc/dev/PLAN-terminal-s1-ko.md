# 터미널 S1 선행 수정 5건 — 착수 계획서

작성: 2026-10-21 · 상태: **계획만 (코드 수정 없음)** — 사용자가 S1 착수를 승인한 뒤에 시작한다 · 짝 문서: [`DESIGN-terminal-multichannel-ko.md`](DESIGN-terminal-multichannel-ko.md) §8 (S1 선행 행), [`DESIGN-terminal-guard-hexansi-ko.md`](DESIGN-terminal-guard-hexansi-ko.md) §1 (측정 M6·M8·M17~M22)

근거 표기: [읽음] 코드를 읽음(`파일:줄`) / [측정] 이 PC 에서 스크래치로 잰 것(저장소 미수정, 오프스크린 Qt·루프백) / [추정] / [미확인] / [제안] 내 권고라 결정 대기.

## 0. 한눈에

확장 설계와 별개인 **기존 결함 5건**이다. 각각 독립 커밋 하나로 간다. M17~M19 는 D13(송신 가능 상태 판정)의 전제이므로 S4 전에 끝나야 한다.

| 커밋 | 결함 | 원인 위치 | 권고 수정 | 회귀 시험 | 크기 |
| --- | --- | --- | --- | --- | --- |
| **C1** | 터미널이 열리면 F4/F5/F8 불발 (M6, M20, M22) | `macro_panel.py:303-307`, `terminal_panel.py:43`, `main_gui.py:757-758,769-770,775-777` | 터미널 창 `Qt.Tool` → `Qt.Window` + 매크로 F키 `WindowShortcut` (안 A) | T1 | S |
| **C2** | 서버 신규 접속 문의가 무한 대기, 기존 클라이언트 정지 (M18) | `comm_handlers.py:301-326`, `protocol_tabs.py:501-512` | 30 초 타임아웃 + 기본 거절 + 열린 질문창 닫기 (안 A) | T2 | S |
| **C3** | TCP Server 수신 약 64 KiB/s (M8) | `comm_handlers.py:288,330-338` | 클라이언트 소켓을 같은 `select` 에 넣고 `recv` 를 비울 때까지 반복 (안 A) | T3 | M |
| **C4** | 자동 재접속 뒤 `_handler` 소실 (M17) | `comm_handlers.py:208-211`, `protocol_tabs.py:229-232,400-404` | 핸들러에 `reconnecting` 신호, 최종 `disconnected` 에서만 `_handler` 해제 (안 A) | T4 | M |
| **C5** | 재접속 켠 Connect 실패 시 버튼 갇힘 (M19) | `protocol_tabs.py:370-391` | 접속 시도 중 `Cancel` 활성, 토글은 핸들러 유무로 판단 (안 A) | T5 | S |

**권고 순서: C1 → C2 → C3 → C4 → C5.** C1 은 어느 것과도 독립이라 순서가 자유롭다. C2→C3 와 C4→C5 는 같은 코드 영역을 만지므로 **앞의 것이 먼저**여야 충돌이 작다(§7). 세 묶음 `{C1}` `{C2,C3}` `{C4,C5}` 은 서로 파일 영역이 겹치지 않아 어떤 순서로 해도 된다.

원칙: 각 커밋에 그 커밋의 회귀 시험을 **같이** 넣고, 시험은 **수정 전 코드에서 실패하는 것을 먼저 확인**한다(§8). 수정 범위는 표의 위치로 제한하고 기존 동작은 바꾸지 않는다.

## 1. C1 — 터미널이 열리면 F4/F5/F8 불발

**현상** [측정 M6, 실제 `TerminalPanel`/`MacroPanel` 로 재확인]: 터미널 창이 보이는 동안 메인 창의 F4(적용)·F5(검색)·F8(FW 업로드)이 **터미널 창이 활성이든 메인 창이 활성이든** 동작하지 않는다. 터미널을 숨기면 동작한다. 대조군 F2 는 정상(매크로 슬롯 2 실행). 매크로 F4/F5/F8 도 안 돈다(`fkey_real_panel.py current`: 두 창 모두 메인=[] 매크로=[]).

**원인 위치** [읽음]: 매크로 F1~F12 는 `ApplicationShortcut`(`macro_panel.py:303-307`), 메인 F5 는 `actionDeviceSearch` WindowShortcut(`main_gui.py:757-758`), F4 는 `_action_apply`(`:769-770`), F8 은 `QShortcut`(`:775-777`). 같은 키를 서로 다른 문맥이 잡아 Qt 가 모호하다고 보고 어느 쪽도 발동하지 않는다. `main_gui.py:765-766` 주석이 같은 현상을 F4 로 한 번 겪었다고 적고 있다. 터미널은 `Qt.Tool` 자식 창이다(`terminal_panel.py:43`). [추정] Tool 창이 부모의 WindowShortcut 문맥을 같이 가진다 — Qt 소스는 읽지 않았다.

**수정안 (둘 이내)**

| 안 | 내용 | 측정 | 장점 | 단점 |
| --- | --- | --- | --- | --- |
| **A (권고)** | `terminal_panel.py:43` 의 `Qt.Tool` → `Qt.Window`, `macro_panel.py:306` 의 `ApplicationShortcut` → `WindowShortcut`. 두 곳 + 낡은 주석 2곳(`terminal_panel.py:4,42`)을 고친다 | 터미널 활성: F4/F5/F8 이 매크로 슬롯 4/5/8, 메인 활성: 메인 기능, F2 는 터미널에서만 매크로 [측정 M22, 실제 `TerminalPanel` 로도 동일 `fkey_real_panel.py fixA`] | D17(a)의 의도 그대로(F키는 터미널 창 활성 시에만 매크로). 12 키 모두 유지 | 창 종류가 바뀌는 부작용(작업 표시줄 항목, Alt+Tab, 부모 위 유지, 메인과 붙기/분리 `terminal_panel.py:39-90`)은 **측정하지 못했다** [미확인] — 사람이 봐야 한다 |
| B | `Qt.Tool` 유지, `macro_panel.py:304-307` 에서 4·5·8 번 슬롯의 `QShortcut` 만 만들지 않음 | 메인 F4/F5/F8 이 두 창 어디서나 동작 [측정 M22-B] | 창 동작 불변 | 매크로 4/5/8 번은 F키가 없어짐(클릭만). 터미널 활성 중에도 메인 F5/F4/F8 이 발동. D17(a) 의 "터미널 활성 시 매크로" 와 다름 |

**회귀 시험 (자동) T1** `tests/test_terminal_fkeys.py` — 실제 `TerminalPanel(QMainWindow)` + 메인 모사(`QShortcut` F4/F5/F8, WindowShortcut). 오프스크린. 케이스: {터미널 활성, 메인 활성, 터미널 숨김} × {F2(대조), F4, F5, F8} 12 가지에서 누가 반응하는지 단언(터미널 활성 → 매크로 슬롯 idx, 메인 활성/숨김 → 메인 hit). 수정 전 코드에서 F4/F5/F8 6 케이스(터미널 활성 3 + 메인 활성 3)가 실패해야 한다(위 현상). 한계: 메인은 `main_gui` 를 띄우지 않고 같은 선언 방식으로 모사한 것이다.

**사람이 확인 (H13)**: 실제 앱에서 ① 터미널을 열고 메인 창 F5(검색)·F4(적용)·F8(FW) 이 동작 ② 터미널 창에서 F1~F12 가 매크로 슬롯을 실행 ③ 안 A 면 작업 표시줄 항목 수, Alt+Tab, 터미널이 메인 위에 남는지, 붙기/분리 드래그, 메인 최소화·복원.

**독립 커밋** `fix(terminal): 터미널 창이 열려 있어도 메인 F4/F5/F8 이 동작하도록 단축키 문맥 정리`. 시험 T1 포함.

**의존/충돌**: 다른 커밋과 파일 영역이 겹치지 않는다. 확장 설계의 S2 "단축키 컨텍스트" 항목은 이 커밋으로 끝난 것이 되므로 S2 에서 제외한다. `main_gui.py` 는 건드리지 않는다.

## 2. C2 — 서버 신규 접속 문의 무한 대기

**현상** [측정 M18]: TCP Server 에 클라이언트가 붙어 있을 때 두 번째 접속이 오면 문의를 띄운다. UI 가 응답하지 않으면 **기존 클라이언트의 수신·송신이 멈춘다**(문의 후 1·5·10·20·32 s 모두 새 수신 0, 기준 첫 수신 1).

**원인 위치** [읽음]: 대기 루프 `comm_handlers.py:307-310` 에 타임아웃이 없다. 주석은 "최대 30초"(`:306`)라고 적혀 있어 의도와 구현이 다르다. 이 루프가 서버 메인 루프(`:286`)를 막으므로 기존 클라이언트 처리(`:329-362`)가 통째로 멈춘다. UI 는 `QMessageBox.question` 모달(`protocol_tabs.py:501-512`)이라 사용자가 답할 때까지 열려 있다. 늦은 응답은 다음 문의에서 이벤트를 `clear()`(`:303-304`)하므로 오염되지 않는다 [읽음].

**수정안 (둘 이내)**

| 안 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A (권고)** | 대기 루프에 30 초 데드라인을 둔다(상수 `NEW_CLIENT_PROMPT_TIMEOUT = 30`). 시간 초과 시 **거절**(기존 연결 유지)하고 `new_client_timeout(ip, port)` 신호를 낸다. 탭은 질문창을 인스턴스로 들고 있다가 이 신호에 닫고 이벤트 줄 `New client {ip}:{port} rejected: no answer in 30 s` 를 남긴다 | 변경이 작다(핸들러 약 8줄 + 탭 약 10줄). 주석과 구현이 일치 | 질문이 떠 있는 최대 30 초 동안은 기존 클라이언트 수신이 여전히 멈춘다 |
| B | 대기를 메인 루프 안의 상태(`pending`)로 바꿔 질문 중에도 기존 클라이언트 수신·송신을 계속한다 | 정지가 없다 | 루프 구조 변경 — C3(수신 루프 수정)와 같은 곳이라 두 커밋을 사실상 합쳐야 한다 |

권고: C2 는 A 로 작게 하고, 질문 중 수신을 계속하는 B 는 C3 이후 필요하면 따로 판단한다 [제안].

**회귀 시험 (자동) T2** `tests/test_terminal_server_prompt.py` — 루프백. 서버 핸들러 + 클라이언트 2개. ① 두 번째 접속 후 UI 가 답하지 않으면 31 초 안에 거절되고(시험은 상수를 monkeypatch 로 0.5 초로 줄인다) 기존 클라이언트 수신이 재개 ② 두 번째 소켓이 닫혀 있음 ③ `new_client_timeout` 신호 1회 ④ `accept_new_client()`/`reject_new_client()` 정상 경로 회귀 ⑤ 기존 클라이언트가 없을 때는 문의 없이 즉시 수락. `defect12.py (2)` 를 승격한다. 수정 전 코드에서 ①이 실패(32 s 동안 0).

**사람이 확인**: 실제 앱에서 두 번째 접속을 만들어 질문창이 뜨고 방치하면 30 초 뒤 **닫히며** 이벤트 줄이 남는지, 답하면 즉시 반영되는지(문구는 영어 확정 때 H16 에서 함께 본다).

**독립 커밋** `fix(terminal): TCP Server 신규 접속 문의에 30초 제한 추가`. T2 포함.

**의존/충돌**: `comm_handlers.py` 의 `TCPServerHandler.run`(301-326)과 `protocol_tabs.py` 서버 탭(501-512). C3 와 같은 함수라 **C2 먼저**(작은 변경), C3 는 그 위에 얹는다. 질문창 인스턴스화는 D13 의 서버 상태 표시와 겹치지 않는다.

## 3. C3 — TCP Server 수신 약 64 KiB/s

**현상** [측정 M8]: 서버 핸들러 수신이 루프백 최대 속도에서 약 64 KiB/s 에서 멈춘다(TCP Client 핸들러는 49~96 MiB/s). 담당자 부하(M21)와 대조 [계산]: 460800 baud 채널당 약 43 KiB/s 는 한계 64 KiB/s 의 약 2/3(여유 약 1.5배)이고, 921600 baud(약 90 KiB/s)는 한계를 넘는다. 상대는 TCP 배압을 받는다.

**원인 위치** [읽음]: 루프가 신규 접속용 `select([srv], [], [], 0.05)`(`comm_handlers.py:288`)에서 **50 ms 를 기다린 뒤** 클라이언트를 `select(..., 0.0)`(`:330`)로 한 번 확인하고 `recv(4096)` 을 한 번만 한다(`:338`). 루프당 4096 B × 초당 약 20 회 ≈ 80 KiB/s 가 이론 상한이고 측정은 약 64 KiB/s.

**수정안 (둘 이내)**

| 안 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A (권고)** | 한 번의 `select` 에 `srv` 와 클라이언트 소켓을 함께 넣고(`select([srv, client], [], [client], 0.05)`), 클라이언트가 읽기 가능하면 `recv(65536)` 을 막힐 때까지 반복(루프당 상한 예: 256 KiB, 송신 큐 굶김 방지). 오류·끊김 처리(`:331-348`)는 그대로 | 수신 때문에 기다리지 않는다. D19 `Fast send wake` 가 같은 `select` 에 wake 소켓을 얹기 쉬워진다 | 루프 구조가 바뀌어 C2 와 영역이 겹친다(C2 먼저) |
| B | 구조 유지, `recv(4096)` → `recv(65536)` 한 줄 + 데이터가 있었으면 다음 루프에서 `select` 대기를 건너뜀 | 한 줄 | 처리량은 늘지만(이론 약 1.3 MiB/s) 50 ms 대기 구조가 남고 근본 해결이 아님 |

**회귀 시험 (자동) T3** `tests/test_terminal_server_throughput.py` — 루프백. ① 클라이언트가 2 MiB 를 `sendall` → 3 초 안에 전부 수신, 순서·내용 해시 일치(수정 전 약 190 KiB 만 받아 실패) ② 수신 중 `stop()`→`wait()` 가 2 초 안에 끝남 ③ 클라이언트 끊김·재접속 이벤트 회귀 ④ 수신 중에도 송신 큐가 내보내짐(굶김 없음) ⑤ 문의 경로(C2) 회귀. `rx_throughput.py` 를 승격한다. 임계 "3 초 안에 2 MiB"는 CI 부하를 고려한 느슨한 시작값(수정 후 기대치는 수 MiB/s 이상) [제안].

**사람이 확인 (H8, 실기기)**: 921600 baud 4채널 동시 수신에서 서버 세션 처리량과 화면 체감(UI 부하는 가드 §4.6 의 합산 예산 참고). 담당자 장비가 필요하다.

**독립 커밋** `fix(terminal): TCP Server 세션 수신이 루프당 4 KiB 로 묶이던 것을 해소`. T3 포함.

**의존/충돌**: **C2 이후**. 같은 함수 `TCPServerHandler.run` 의 `:288`, `:330-338`, `:354-362` 를 고친다. S4 의 송신 깨우기 옵션(D19)이 같은 `select` 를 다시 만지므로 이 커밋에서 `select` 를 한 곳으로 모아 두면 S4 가 작아진다.

## 4. C4 — 자동 재접속 뒤 `_handler` 소실

**현상** [측정 M17]: 자동 재접속을 켠 TCP Client 가 끊긴 뒤 재접속하면 화면은 "연결됨"인데 **Send 가 조용히 무시되고(TX 줄도 없다) Disconnect 를 눌러도 스레드가 멈추지 않는다**(`_handler` 가 None).

**원인 위치** [읽음]: 재접속 모드에서 연결이 끊기면 핸들러가 `disconnected` 를 낸다(`comm_handlers.py:208-211`) — 스레드는 계속 돌아 재접속한다. 탭의 `_on_disconnected`(`protocol_tabs.py:400-404`)가 `_set_disconnected()` 를 부르고, 이것이 `self._handler = None` 으로 만든다(`:229-232`). 재접속하면 `connected` 가 다시 나가 `_on_connected` 가 화면만 "연결됨"으로 바꾸고 `_handler` 는 되살리지 않는다. 그 결과 `_on_send`(`:220-223`)의 `if self._handler:` 가 거짓, `_do_disconnect`(`:406-408`)와 `stop()`(`:234-238`)도 아무것도 못 한다. `terminal_panel.py:100` 의 종료 처리도 `tab.stop()` 이라 스레드가 남을 수 있다 [추정, 종료 시 영향은 미측정]. 최종 `disconnected` 는 스레드 끝(`:223`)에서 한 번 더 나가므로 "스레드가 아직 돌고 있는지"로 구분하는 안은 쓸 수 없다 [읽음].

**수정안 (둘 이내)**

| 안 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A (권고)** | 핸들러에 `reconnecting = pyqtSignal(str)` 을 더하고 `:210` 에서 `disconnected` 대신 이것을 낸다. `disconnected` 는 스레드가 끝날 때(`:223`) **한 번만**. 탭은 `reconnecting` 에서 `_connected=False` 로 화면만 갱신하고 `_handler` 는 유지, `_set_disconnected()`(핸들러 해제)는 최종 `disconnected` 에서만 호출. 핸들러는 끊김 때 `_send_queue.clear()` 로 재접속 뒤 오래된 데이터가 쏟아지는 것을 막는다 | 의미가 명확하다(끊김-재시도 vs 끝). 다른 탭에 영향 없음 | 신호가 하나 늘어난다 |
| B | 핸들러 신호는 그대로 두고 `_set_disconnected()` 에서 `_handler = None` 을 빼고 `QThread.finished` 로 해제 | 신호 추가 없음 | `_set_disconnected` 는 UDP/Server/Serial 탭도 공유(`:229-232`)라 영향 범위가 넓다 |

**회귀 시험 (자동) T4** `tests/test_terminal_reconnect.py` — 로컬 리스너 + 오프스크린 `TCPClientTab`. ① 연결 → 서버가 닫음 → 재접속 수락 → Send 가 상대에 도달하고 `_handler` 가 None 이 아님 ② Disconnect 후 3 초 안에 스레드 종료, 버튼 `Connect` ③ 재접속 대기 중에 보낸 데이터가 재접속 뒤 나가지 않음(큐 비움) ④ **자동 재접속 끔** 경로 회귀: 끊기면 `_handler=None`, 버튼 `Connect` ⑤ `stop()` 이 재접속 대기 중에도 스레드를 끝냄. `defect12.py (1)` 승격. 수정 전 코드에서 ①②가 실패(M17). 한계: UDP/Server/Serial 탭의 `_set_disconnected` 경로 회귀는 UDP·Server 는 루프백으로, Serial 은 실제 COM 이 없어 자동 시험이 어렵다 [미확인].

**사람이 확인 (H14)**: 실기기에서 장치를 껐다 켜거나 케이블을 뽑아 재접속시킨 뒤 Send 가 장치에 닿는지, Disconnect 가 멈추는지.

**독립 커밋** `fix(terminal): 자동 재접속 TCP Client 가 재접속 뒤에도 송신·중지가 되도록 핸들러 유지`. T4 포함.

**의존/충돌**: `comm_handlers.py` 의 `TCPClientHandler`(131-223)와 `protocol_tabs.py` 의 `BaseProtocolTab._set_disconnected`(229-232)·`TCPClientTab._on_disconnected`(400-404). **C5 가 같은 탭 영역이라 C4 먼저.** D13 의 송신 가능 판정(S4)이 "재접속 대기 = 송신 불가"를 쓰므로 이 `reconnecting` 신호가 그 전제가 된다. 큐 비움은 D13 확정(큐 누적 제거)의 앞당긴 부분이다.

## 5. C5 — 재접속 켠 Connect 실패 시 버튼 갇힘

**현상** [측정 M19]: 자동 재접속을 켠 채 응답 없는 대상에 Connect 하면 버튼이 `Connecting...` + 비활성에서 4 초 뒤에도 그대로이고 스레드는 재시도 중이다. 오류 이벤트는 `WinError 10061` 한 줄뿐. **UI 로는 멈출 방법이 없다.**

**원인 위치** [읽음]: `_do_connect` 가 버튼을 `Connecting...` 으로 바꾸고 비활성화한다(`protocol_tabs.py:389-390`). 재접속 켠 연결 실패는 `disconnected` 를 내지 않고 대기만 반복하므로(`comm_handlers.py:174-180`) `_on_connected`(`:393-395`) 나 최종 `_on_disconnected`(`:400-402`) 외에는 버튼이 되살아날 길이 없다. 토글은 `self._connected` 로 연결/해제를 판단(`:371`)해 접속 시도 중에는 해제를 못 부른다.

**수정안 (둘 이내)**

| 안 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A (권고)** | `_do_connect` 가 버튼을 `Cancel`(활성)로 바꾸고, `_toggle_connection` 은 `self._handler is not None` 이면 해제(취소)를 부른다. 취소 클릭 후에는 `Cancelling...`(비활성)로 두었다가 최종 `disconnected` 에서 `Connect` 로 복귀. 접속 중 5 초 소켓 타임아웃(`comm_handlers.py:159`)이 있어 취소가 최대 5 초 걸릴 수 있다 | 변경이 탭 안에서 끝난다. 재접속을 끈 경우의 5 초 접속 대기에도 취소가 생긴다 | 재시도 횟수·다음 시도까지 시간 표시(`Retry 3 · next in 5 s`)는 이 커밋에 없다 |
| B | A + 핸들러가 실패 때마다 `reconnecting`(C4 의 신호)을 내 탭이 `Reconnecting...` 과 재시도 정보를 표시 | 상태가 눈에 보인다 | C4 에 의존하고 표시 문구가 늘어난다(D16 영어 문구 사전과 함께 S4 에서 하는 편이 낫다) |

권고: C5 는 A(최소), B 는 S4 의 표시 개선으로 넘긴다 [제안].

**회귀 시험 (자동) T5** `tests/test_terminal_connect_cancel.py` — 오프스크린 `TCPClientTab` + 닫힌 로컬 포트(연결 거부). ① 재접속 켠 Connect 후 1 초 안에 버튼이 `Cancel`·활성 ② 클릭하면 취소되어 스레드 종료, 버튼 `Connect`·활성, `_handler` None ③ 접속 중(`_connect` 를 0.3 초 지연으로 대체)에 취소 ④ 재접속을 끈 경로 회귀(거부 → `Connect` 복귀). `defect3.py` 승격. 수정 전 코드에서 ①이 실패(비활성). 실제 5 초 타임아웃(응답 없는 주소)은 시험에서 지연 대체로 모사한다.

**사람이 확인 (H14)**: 실제로 응답 없는 IP 로 Connect 하고 `Cancel` 을 눌러 몇 초 안에 `Connect` 로 돌아오는지, 문구가 이해되는지.

**독립 커밋** `fix(terminal): 재접속 켠 TCP Client 접속 시도 중에 취소할 수 있게 함`. T5 포함.

**의존/충돌**: **C4 이후.** `protocol_tabs.py` 의 `TCPClientTab._toggle_connection`(370-374)·`_do_connect`(376-391)·`_on_disconnected`(400-404)가 C4 와 같은 영역. Serial 탭은 같은 패턴(`Opening...` 비활성, `:620-621`)이라 같은 문제가 생길 수 있으나 이번 범위가 아니다 [읽음, 측정 안 함].

## 6. 공통: 시험 환경과 순서

- 시험은 `tests/` 에 `uv run pytest` 로 돈다. Qt 시험은 파일 맨 위에서 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` 후 `QApplication` 을 한 번 만든다(`tests/conftest.py` 에는 Qt 설정이 없음 [읽음]). 포트는 `bind(("127.0.0.1", 0))` 로 받아 충돌을 피한다. 모든 대기는 데드라인이 있는 폴링(`processEvents` + 짧은 sleep)이고 무한 대기를 쓰지 않는다.
- 스크래치 원형이 이미 있다: C1 `fkey_real_panel.py`·`fkey_ctx_variant2.py`, C2/C4 `defect12.py`, C3 `rx_throughput.py`, C5 `defect3.py`. 시험으로 승격할 때는 출력 대신 단언으로 바꾼다.
- **수정 전 실패 확인** 절차: 시험을 먼저 추가하고 현행 코드에서 돌려 실패(= 결함 재현)를 확인한 뒤 수정한다. 실패하지 않는 시험은 결함을 못 잡는 시험이다.
- 흔들림(flaky) 위험: 오프스크린 포커스·타이밍. 키 시험(T1)은 `activateWindow` 후 `processEvents` 를 두 번 돌리고 재시도 한 번을 허용한다 [제안]. 흔들리면 사람 확인으로 돌린다.

## 7. 충돌·의존 지도

| 파일 | C1 | C2 | C3 | C4 | C5 |
| --- | --- | --- | --- | --- | --- |
| `terminal/macro_panel.py` (303-307) | ● | | | | |
| `terminal/terminal_panel.py` (4, 42-43) | ● | | | | |
| `terminal/comm_handlers.py` `TCPServerHandler.run` (286-362) | | ● 301-326 | ● 288, 330-338, 354-362 | | |
| `terminal/comm_handlers.py` `TCPClientHandler` (131-223) | | | | ● 208-211, 신호 정의 | |
| `terminal/protocol_tabs.py` 서버 탭 (501-512) | | ● | | | |
| `terminal/protocol_tabs.py` `BaseProtocolTab._set_disconnected` (229-232) | | | | ● | |
| `terminal/protocol_tabs.py` `TCPClientTab` (370-408) | | | | ● 400-404 | ● 370-391 |
| `main_gui.py` | | | | | |

- **같은 영역(순서 필수)**: C2→C3, C4→C5. 서로 다른 묶음 사이는 충돌 없음.
- **후속 단계와의 관계**: C2·C4·C5 는 D13(S4)의 전제, C3 는 M21 부하 근거로 우선순위 높음, C1 은 S2 의 단축키 항목을 흡수.
- `main_gui.py` 는 다섯 커밋 모두 건드리지 않으므로 초기화 순서(`__init__`)의 위험이 없다.
- 프로젝트 규칙: 결함을 고치는 커밋이 생기면 `TASKS.md`(`[x]` + 커밋 해시)와 `BUGS.md`(전역, ID·한 줄)를 같이 갱신한다. 코드 변경이 있는 단계에서 `s2egui` 가 한다.

## 8. 코드가 확인할 것 / 사람이 확인할 것

| 구분 | 항목 | 어디서 |
| --- | --- | --- |
| 코드(자동) | T1 단축키 12 케이스, T2 문의 타임아웃·정상 경로, T3 수신 처리량·무결성·종료 시간, T4 재접속 후 송신·중지·큐 비움·비재접속 회귀, T5 취소 | `uv run pytest tests/test_terminal_*.py` |
| 코드(자동) | 각 시험이 수정 전 코드에서 **실패**하는지 | 커밋 전 1회 |
| 사람 | 실제 앱 F4/F5/F8·F1~F12, 안 A 면 창 동작(작업 표시줄·Alt+Tab·부모 위·붙기/분리) | H13 |
| 사람 | 질문창이 방치 30 초 뒤 닫히는지, 이벤트 줄 문구 | C2 |
| 사람(실기기) | 921600 baud 4채널 동시 수신 처리량·UI 체감 | H8 |
| 사람(실기기) | 장치 재부팅·케이블 분리 후 재접속에서 Send·Disconnect, 응답 없는 IP 에서 Cancel | H14 |

## 9. 착수 전에 사용자가 정할 것

1. **S1 착수 승인** — 이 계획서대로 코드 수정을 시작해도 되는가(지금은 하지 않는다).
2. **C1 안 A 와 B** — A 는 창 종류가 바뀌어 작업 표시줄·Alt+Tab 동작을 눈으로 확인해야 한다. A 를 해 보고 거슬리면 B 로 되돌릴 수 있다(두 곳 되돌리기). 권고는 A.
3. **C2 안 A 와 B** — 30 초 동안 기존 클라이언트가 멈추는 것을 허용하는가. 권고는 A 로 먼저 고치고 필요하면 B.
4. **커밋 순서** — C1 → C2 → C3 → C4 → C5 권고. 고속 수신이 급하면 C3 를 먼저 해도 되지만 C2 와의 충돌이 커진다.
5. (선택) 시험을 `tests/` 에 두는 파일 이름과 위치.
