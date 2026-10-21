# NetTerm3 분석 + 우리 터미널 현황 (다채널 확장 설계의 근거 문서)

작성: 2026-10-20 · 짝 문서: [`DESIGN-terminal-multichannel-ko.md`](DESIGN-terminal-multichannel-ko.md)
상태: **분석만. 코드 변경 없음.** 설계·결정 항목은 짝 문서에 있다.

## 0. 이 문서를 읽는 법

### 0.1 근거 표기

| 표기 | 뜻 |
| --- | --- |
| **[읽음]** | 소스를 직접 읽고 `파일:줄` 로 확인한 사실 |
| **[측정]** | 이 PC 에서 스크립트로 돌려 얻은 수치 (스크립트는 문서 끝 부록) |
| **[추정]** | 읽은 것에서 추론한 것. 작성자 진술이 아니다 |
| **[미확인]** | 확인 수단이 없거나 안 했다 |

NetTerm3 줄 번호는 `NetTerm3-src/<파일>:<줄>` 이다 (압축을 푼 소스 기준). 우리 코드 줄 번호는 저장소 루트 기준 (2026-10-20 작업 트리).

### 0.2 읽은 대상과 안전 처리

| 대상 | 내용 | 해시(SHA-256 앞 16자) |
| --- | --- | --- |
| `NetTerm3-src-20261019.zip` | 소스 21파일(README·csproj 포함) 합계 3,367줄 (`wc -l` [측정]) | `ac20b05afb06d901` |
| `NetTerm3_exe.zip` | `NetTerm3.exe` 1개, 334,455 B [측정] | `2a6b3493d93109ca` |
| `NetTerm3.exe` (압축 해제본) | | `5a59271522c6672f` |

- 압축은 빈 폴더에 풀었고 풀린 폴더 안에서 인터프리터를 돌리지 않았다. 파이썬은 `-I` 로 실행했다. 경로 이탈(`..`) 항목 검사 후 해제.
- **exe 는 실행하지 않았다.** 정적으로 UTF-16 문자열만 대조했다: 화면·로그 문자열 52개 중 소스에 없는 것은 메타데이터 `Assembly Version` 1개뿐 [측정]. 즉 exe 는 이 소스에서 빌드된 것으로 보인다 [추정]. 논리까지 동일하다는 증명은 아니다.
- NetTerm3 의 동작은 전부 **코드 읽기** 기준이다. 돌려 보지 않았다.
- 이 분석은 구조·의도 파악이 목적이다. 결함 감사가 아니다. 다만 우리가 가져다 쓸 때 걸릴 만한 것은 1.8 에 적었다.

## 1. NetTerm3 분석

### 1.1 한눈에

| 항목 | 값 |
| --- | --- |
| 정체 | .NET 8 WPF 데스크톱 터미널. TCP Client / TCP Server / UDP / Serial 세션을 **탭 또는 그리드**로 여러 개 연다 (`README.md:3`, `NetTerm.csproj:4-6,11`) |
| 규모 | C# 14파일 + XAML 5파일 + csproj + README. 가장 큰 파일 `SessionViewModel.cs` 800줄 |
| 의존 | `System.IO.Ports` 8.0.0 하나 (`NetTerm.csproj:16`) |
| 버전 이력 | `dist\`(v1, 시리얼 없음) → `dist2\`(v2, ANSI 해석 없음) → `dist3\`(v3) (`README.md:7-8`). 반복 개량된 도구다 [추정] |
| 4CH 전용 코드 | **0건.** 소스 전체에서 `4ch|channel|macro|wiznet|s2e|w55` 대소문자 무시 검색 결과 없음 [측정] |

핵심 한 줄: NetTerm3 는 "4채널" 을 알지 못한다. **임의 종류의 세션 N개를 한 창에 동시에 띄우는 범용 도구**이고, 4CH 시험은 사용자가 세션 4개를 만들어 쓰는 방식으로 풀린다 [추정].

### 1.2 만든 목적 — 소스가 말해 주는 것과 추정

소스·README 어디에도 "왜 만들었나" 라는 진술은 없다. 아래는 **기능 선택에서 거꾸로 추정한 불편**이다. 실제 동기는 만든 담당자에게 확인해야 한다 [미확인].

| 추정하는 불편 | 이를 겨냥한 것으로 보이는 설계 | 근거 [읽음] |
| --- | --- | --- |
| 도구 하나에 프로토콜당 연결 1개뿐이라 4채널을 한꺼번에 못 본다 | 세션을 프로토콜 무관하게 N개, 탭/그리드 전환, 그리드는 세션 수에 맞춰 자동 배치 | `MainViewModel.cs:8,18`, `MainWindow.xaml:52-132`, `README.md:21` |
| 고속·장시간 시험에서 UI 가 멈추거나 데이터가 사라진다 | 큐 + 50 ms 일괄 반영 + 배압 + 드롭 카운트, "190MB/12초 플러드에도 UI 안 멈춤 확인" | `SessionViewModel.cs:17-20,147-152,577-581`, `README.md:32-39` |
| 보드 재부팅·케이블 빠짐·USB 뽑힘 때마다 수동 재연결 | 세션별 Auto reconnect(3초), 연결 시도 10초 타임아웃, keepalive 로 끊김 감지 | `SessionViewModel.cs:189-269`, `TcpClientSession.cs:7,33`, `Core.cs:87-106`, `README.md:15,18` |
| 쉘이 프롬프트를 다시 그리면 로그가 깨진다 (Zephyr `uart:~$`) | VT100-lite 렌더러가 줄 버퍼에 커서 이동·지우기를 적용 | `AnsiLineRenderer.cs:5-9` |
| 시리얼 속도·흐름제어를 실제 시험하기엔 모자란다 | 921600 baud, RTS/CTS · DTR/DSR(Win32 DCB 직접) · XON/XOFF | `SerialSession.cs:70-71,35-51,251-313` |
| 시험 환경을 다시 만들기 번거롭다 | Save/Load Setup(JSON), 커맨드라인으로 세션 자동 생성·자동 연결 | `Workspace.cs:8-80`, `MainWindow.xaml.cs:35-97`, `README.md:27,41-51` |

주의: 위 표는 "이 도구가 무엇을 풀도록 만들어졌나" 의 추정이다. Zephyr 언급은 W55RP20 펌웨어(Pico SDK 기반)와 맞지 않으므로 작성자가 4CH 외 다른 보드 시험에도 쓴 것으로 보인다 [추정].

### 1.3 기능 목록

| 기능 | 구현 위치 [읽음] | 비고 |
| --- | --- | --- |
| TCP Client (연결 10초 타임아웃, NoDelay, keepalive, Auto reconnect) | `TcpClientSession.cs:24-62` | |
| TCP Server (멀티 클라이언트, 송신은 전원에게 브로드캐스트, 로그에 상대 주소) | `TcpServerSession.cs:44-97,129-154` | 클라이언트별 줄 조립 버퍼 `SessionViewModel.cs:390` |
| UDP (로컬 포트 바인드, 0 = 자동, 원격 host:port 송신, 수신 로그에 송신자 주소) | `UdpSession.cs:24-69,84-118` | Windows ICMP 연결 리셋 무시 `UdpSession.cs:31-32` |
| Serial (포트 목록 새로고침, 1200~921600, 5~8 data bits, parity, 1/1.5/2 stop, 흐름제어 4종, Auto reconnect) | `SerialSession.cs:117-198` | 열면 DTR·RTS 어서트 `:136,139-140`. 수동 RTS/DTR 토글은 의도적으로 없음 `README.md:18` |
| 세션 추가/닫기/이름 변경(더블클릭)/순서 이동(드래그, Ctrl+Shift+←→) | `MainViewModel.cs:33-66`, `MainWindow.xaml.cs:156-215` | |
| 탭 ↔ 그리드 전환 (Ctrl+G) | `MainWindow.xaml:52-132`, `MainWindow.xaml.cs:21-22` | 그리드 열 수 = ceil(sqrt(N)) `MainViewModel.cs:18` |
| 수신 줄 조립 (`\n` 기준, 꼬리는 120 ms 유휴 또는 512 B 에 방출) | `SessionViewModel.cs:422-547` | 스트림(TCP/Serial)만. UDP 는 데이터그램 단위 `UdpSession.cs:59` |
| ANSI 해석 (기본 켬) | `AnsiLineRenderer.cs`, `SessionViewModel.cs:400-414` | 색상은 제거 |
| HEX 보기 (기존 로그 포함 전체 재표시) | `SessionViewModel.cs:61-66,644-669,749-758` | |
| 송신 모드 Text/Hex, 줄끝 None/CR/LF/CRLF, 송신 이력 100개 (↑↓) | `SessionViewModel.cs:271-344`, `SessionView.xaml.cs:163-172` | HEX 입력은 `01 A0 FF`, `01,A0`, `0x01` 허용 `:779-799` |
| 타임스탬프, 자동 스크롤, RX/TX 바이트 카운터 (RX 는 와이어 기준) | `SessionViewModel.cs:68-82,583-589` | |
| 로그 저장 (화면 버퍼 4000줄) / Log to file (실시간 이어쓰기, AutoFlush) | `SessionViewModel.cs:679-747` | |
| 로그 복사 (드래그 다중 선택, Ctrl+C/A, 우클릭 메뉴) | `SessionView.xaml.cs:72-195`, `SessionView.xaml:173-182` | |
| 설정 저장/불러오기 (연결은 자동으로 하지 않음) | `Workspace.cs:58-80`, `MainWindow.xaml.cs:111-154` | |
| 커맨드라인 (`--tcp-client`, `--tcp-server`, `--udp`, `--serial`, `--grid`, `--connect`) | `MainWindow.xaml.cs:38-97` | |

### 1.4 화면 구성

#### 1.4.1 메인 창 (`MainWindow.xaml`)

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [＋ New Session] [Save Setup] [Load Setup]                    [ Tabs | Grid ] │ ← 도구줄 :12-33
├──────────────────────────────────────────────────────────────────────────────┤
│  ● TCP Client 1 ✕ │ ● TCP Client 2 ✕ │ ○ Serial 1 ✕ │                          │ ← 탭 헤더 :54-69
│ ┌──────────────────────────────────────────────────────────────────────────┐ │   (상태 점, 이름, 닫기)
│ │                                                                          │ │
│ │                        SessionView (1.4.2)                               │ │ ← 탭 내용 :70-74
│ │                                                                          │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3 session(s)        Ctrl+T new · Ctrl+W close · Ctrl+G tabs/grid · …         │ ← 상태줄 :35-46
└──────────────────────────────────────────────────────────────────────────────┘
```

- 탭 모드와 그리드 모드는 **같은 `Sessions` 컬렉션을 두 개의 컨트롤이 번갈아 보여 준다** (`Visibility` 바인딩, `MainWindow.xaml:53,79`). 세션이 두 곳에 동시에 그려지지는 않는다.
- 세션 0개면 "No sessions" 안내와 큰 `New Session` 버튼 (`:134-145`).

그리드 모드 (세션 4개 예, `UniformGrid` 열 수 = ceil(sqrt(4)) = 2, `MainWindow.xaml:82`):

```text
┌───────────────────────────────┬───────────────────────────────┐
│ ● TCP Client 1  Connected …  ✕│ ● TCP Client 2  Connected …  ✕│ ← 셀 헤더 :109-126
│ SessionView                   │ SessionView                   │   (드래그 핸들, 더블클릭=이름 변경)
├───────────────────────────────┼───────────────────────────────┤
│ ○ Serial 1  Closed …         ✕│ ● UDP 1  Bound to :5000      ✕│
│ SessionView                   │ SessionView                   │
└───────────────────────────────┴───────────────────────────────┘
  선택된 셀 = 파란 테두리 (Accent) :95-104, 셀 클릭 → Selected 갱신 :202-206
```

#### 1.4.2 세션 패널 (`SessionView.xaml`) — 위에서 아래 4행 (`:111-116`)

```text
┌─ 행0 연결 설정 + 토글 ─────────────────────────────────────────────────────┐
│ Host [192.168.0.10   ] Port [5000] ☐Auto reconnect              [Connect] │ ← 종류별 DataTemplate :8-69
├─ 행1 옵션 / 상태 ──────────────────────────────────────────────────────────┤
│ ☐HEX ☑ANSI ☑Time ☑Scroll ☐Log to file   Connected …   RX 0 B · TX 0 B [Save…][Clear] │ :137-156
├─ 행2 로그 ─────────────────────────────────────────────────────────────────┤
│ [12:00:01.123] RX  hello                                                   │ ← ListBox, Consolas 12, :161-188
│ [12:00:02.004] TX  AT\r\n                                                  │   RX 초록 / TX 노랑 / 오류 빨강 :72-86
├─ 행3 송신 ─────────────────────────────────────────────────────────────────┤
│ [Text▾] [입력창 …………………………………………] [CRLF▾] [Send]                    │ :191-213
└────────────────────────────────────────────────────────────────────────────┘
```

- 종류별 설정 행(행0)은 `ContentControl Content="{Binding}"` + `DataType` 별 `DataTemplate` 로 자동 선택된다 (`SessionView.xaml:132`). 새 세션 종류는 템플릿 하나 추가로 붙는다.
- 연결 중에는 주소·포트·시리얼 설정이 잠긴다 (`IsEnabled="{Binding IsActive, Converter=InvBool}"`). UDP 의 원격 주소/포트만 연결 중에도 편집 가능 (`:38,41`).
- New Session 대화상자는 **종류만 고르는 버튼 4개**. 주소·포트는 세션 패널에서 편집 (`NewSessionDialog.xaml:43-72`, `README.md:51`).

### 1.5 통신 방식 — 채널을 어떻게 구분하나

| 질문 | 답 [읽음] |
| --- | --- |
| 채널(세션)을 무엇으로 구분하나 | **구분하지 않는다.** 세션 하나 = 소켓/포트 하나. 세션끼리 공유하는 상태가 없다. 구분은 사용자가 붙이는 **세션 이름**뿐 (`SessionViewModel.cs:27-28`, `MainViewModel.cs:33-41` 가 "TCP Client 1" 식 자동 이름) |
| 세션 간 연동 | 없다. 전체 전송, 동시 시작/중지, 통합 타임라인 모두 없음. 예외: 명령줄 `--connect` 가 세션을 차례로 시작 (`MainWindow.xaml.cs:88-96`) |
| 한 세션이 여러 상대를 받을 때 | TCP Server 만. 클라이언트별로 `Peer`("ip:port") 라벨과 별도 줄 조립 버퍼 (`TcpServerSession.cs:53,80`, `SessionViewModel.cs:390`). 송신은 전원에게 (`:129-154`) |
| 스레딩 | 소켓/시리얼 읽기 루프는 **async/await Task** (`ReadLoopAsync`, `ClientLoopAsync`, `ReceiveLoopAsync`). UI 스레드로의 전달은 아래 큐 경유. 상태 변경은 `Post()` 로 디스패처 `BeginInvoke(Background)` (`SessionViewModel.cs:346-352`) |
| 수신 버퍼링 | `ConcurrentQueue<LogEntry>` + 50 ms `DispatcherTimer`(Background 우선순위)가 틱당 최대 250건 이동 (`:22,147-152,597-610`). 화면 4000줄 유지 (`:17,635`) |
| 과부하 | 큐가 5000 의 절반 넘으면 읽기 루프가 20 ms 씩 대기 → TCP 흐름제어로 송신측을 늦춤(배압). 그래도 넘치면 드롭하고 "Overloaded — N message(s) dropped" 한 줄 (`:18,375-384,577-581,612-627`) |
| 줄 조립 | `AddRx` 가 피어별 버퍼에 모아 `\n` 완성 시 한 줄. 512 B 도달 또는 120 ms 유휴 시 꼬리 방출 (`:422-547`, `FlushStaleRxBuffers :485-503` 이 매 틱 호출 `:585`) |
| 표시 | `FormatEntry` 가 `[HH:mm:ss.fff] RX peer  내용` 으로 조립 (`:650-669`). 텍스트는 UTF-8 로 디코드하고 제어문자는 `·` (`:760-777`) |
| 송신 | `Encoding.UTF8.GetBytes(입력 + 줄끝)` 또는 Hex 파싱 → `SendCoreAsync` (`:271-290`). 보낸 바이트는 TX 로그 항목 (`TcpClientSession.cs:132-133`) |
| 로그 파일 | 틱마다 같은 문자열을 `StreamWriter` 에 기록 후 Flush. 화면은 16000자로 자르지만 파일은 전체 (`:20,602-606,639-642`) |
| 보호 상수 | 화면 4000줄 · 대기 5000 · 틱당 250 · 줄 표시 16000자 · 세그먼트 512 B · 유휴 방출 120 ms · 재연결 3초 · keepalive 5초 + 2초×3회 (`SessionViewModel.cs:17-20,191,386-387`, `Core.cs:98-102`) |

keepalive 는 5 + 2×3 = 11 초 안팎에 끊김을 감지한다 (계산). README 는 "~10초" 라 쓴다 (`README.md:15`).

### 1.6 코드 구조

```text
App.xaml(색·스타일 전부)                 App.xaml.cs(빈 클래스)
MainWindow.xaml/.cs ──DataContext──▶ MainViewModel (Sessions, Selected, IsGridView)
   │  탭/그리드 두 컨트롤이 Sessions 를 번갈아 표시          │ AddSession/Close/Move/CloseAll
   │  드래그 순서 이동, 단축키, 명령줄, Save/Load Setup       │
   ▼                                                          ▼
SessionView.xaml/.cs  ◀── DataContext ── SessionViewModel (추상, 800줄)
   로그 ListBox · 드래그 선택 · 복사              ├─ TcpClientSession
                                                  ├─ TcpServerSession
Workspace.cs  JSON ⇄ SessionConfig ⇄ 세션         ├─ UdpSession
Core.cs  ObservableObject · RelayCommand ·        └─ SerialSession
         LogEntry · BulkObservableCollection · NetUtil · 변환기
AnsiLineRenderer.cs  (줄 단위 VT100-lite)  ← SessionViewModel.AddRx 가 사용
```

| 파일 | 줄 | 역할 |
| --- | --- | --- |
| `SessionViewModel.cs` | 800 | 세션 공통 전부: 큐·배압·줄 조립·ANSI·HEX·로그 파일·재연결·송신 이력. 하위 클래스는 `StartAsync`/`StopSession`/`SendCoreAsync` 3개만 구현 (`:173-175`) |
| `SerialSession.cs` | 314 | 시리얼 설정 속성, 읽기 루프, DCB 직접 조작(DTR/DSR) |
| `TcpClientSession.cs` · `TcpServerSession.cs` · `UdpSession.cs` | 140 · 155 · 119 | 종류별 연결·읽기·송신 |
| `MainViewModel.cs` | 76 | 세션 컬렉션과 선택/순서/닫기 |
| `MainWindow.xaml(.cs)` | 149 · 229 | 도구줄, 탭/그리드, 드래그, 단축키, 명령줄, 설정 저장 |
| `SessionView.xaml(.cs)` | 214 · 196 | 세션 패널 UI, 드래그 선택, 복사 |
| `Workspace.cs` | 174 | 설정 JSON. `SessionConfig` 는 모든 종류의 필드를 한 클래스에 평평하게 담는다 (`:14-47`) |
| `AnsiLineRenderer.cs` | 155 | CSI `D C K J G H f` 처리, `m`(색) 및 나머지는 제거 (`:110-145`) |
| `Core.cs` | 133 | MVVM 기반 클래스, 배치 추가용 컬렉션 `AddAndTrim` (`:67-85`), 키프얼라이브 |

### 1.7 작성자 의도가 드러나는 특이점

1. **채널 개념을 일부러 넣지 않았다.** 세션은 서로를 모른다. "4채널" 은 사용자가 만든 세션 4개일 뿐이다. 범용성을 얻은 대신 "4개에 한꺼번에 보내기" 같은 채널 간 기능이 없다 [읽음 + 추정].
2. **UI 를 안 막는 것이 최우선이다.** 배압·드롭 카운트·틱당 상한·16000자 절단·`BulkObservableCollection` 의 `Reset` 1회 통지까지, 부하 대응이 코드량의 큰 몫이다 (`SessionViewModel.cs:17-20,577-637`, `Core.cs:67-85`). README 에 플러드 시험 수치(190MB/12초)까지 적었다 (`README.md:39`) [읽음].
3. **데이터를 잃느니 송신측을 늦춘다.** 드롭은 최후 수단이고 먼저 배압을 건다 (`:577-581`) [읽음].
4. **현실의 끊김을 전제로 한다.** keepalive 튜닝(`Core.cs:87-106`), UDP 의 `SIO_UDP_CONNRESET` (`UdpSession.cs:29-32`), 시리얼 읽기 오류 시 재오픈 (`SerialSession.cs:187-197`), 닫기 때 `Task.Run` 으로 Dispose (`:214-219` — "읽기가 걸려 있으면 Dispose 가 막힌다" 주석) [읽음].
5. **하드웨어 맨 아래까지 내려간다.** `System.IO.Ports` 가 지원하지 않는 DTR/DSR 흐름제어를 리플렉션으로 `_handle` 을 꺼내 `SetCommState` 로 직접 설정한다 (`SerialSession.cs:281-313`). 비공개 필드 이름에 의존하므로 .NET 버전이 바뀌면 깨질 수 있다 — 실패 시 로그를 남기고 계속 진행하도록 방어했다 (`:143-150`) [읽음 + 추정].
6. **"시리얼 라인을 마음대로 건드리지 않는다."** 수동 RTS/DTR 토글을 의도적으로 뺐고, "열면 DTR·RTS 어서트(오토리셋 보드 주의)" 를 README 에 경고로 적었다 (`README.md:18`) [읽음].
7. **쉘 출력을 사람이 읽는 줄로 복원한다.** 단순 이스케이프 제거가 아니라 커서 이동·지우기를 시뮬레이트한다 (`AnsiLineRenderer.cs:5-9`) [읽음].
8. **환경 재현성.** 명령줄과 JSON 으로 시험 구성을 통째로 복원. 연결은 자동으로 하지 않는 점이 안전 쪽 선택이다 (`README.md:27`) [읽음].

### 1.8 가져다 쓸 때 걸릴 점 (한계·주의)

| # | 내용 | 근거 |
| --- | --- | --- |
| a | **ANSI 켬(기본)이면 바이너리 검증에 쓸 수 없다.** 수신 바이트를 UTF-8 로 디코드해 문자 단위로 처리하므로 잘못된 UTF-8 은 대체문자로 바뀌고, 다른 제어문자(`< ' '`, `0x7F`)는 버려진다 (`AnsiLineRenderer.cs:15,28-33,90`). 방출은 렌더된 **텍스트를 다시 UTF-8 로 인코딩**한 것이라 (`SessionViewModel.cs:445-453`), ANSI 켠 채 HEX 보기를 해도 **와이어 바이트가 아니다**. 바이트 카운터만 와이어 기준이다 (`:425,588-589`). 4CH 에서 데이터 무결성을 보려면 ANSI 를 꺼야 한다 | 읽음 + 추론 |
| b | 채널 간 기능 없음: 전체 전송·동시 연결·통합 타임라인·매크로·주기 전송 | 1.5 |
| c | 장치 연동 없음 (SEGCP 로 설정을 읽어 세션을 채우는 기능 없음) | 1.1 |
| d | 텍스트는 UTF-8 고정. 다른 인코딩 선택 없음 | `SessionViewModel.cs:284,762` |
| e | `SessionConfig` 가 종류별 필드를 한 클래스에 평평하게 나열 → 종류가 늘수록 비대해진다 | `Workspace.cs:14-47` |
| f | 시험 코드 없음 (소스 21파일 중 테스트 없음) | `wc -l`·파일 목록 |
| g | WPF/.NET 8 이라 우리 PyQt5 코드에 **이식할 수 없고 개념만 가져온다** | — |

## 2. 우리 터미널 현황

### 2.1 정체와 이력

- Hercules 를 대체하려고 2026-04-24 에 추가됐다. 커밋 `1bbe45c` 제목 "터미널 유틸리티 패널 추가 (Hercules 대체)" [읽음].
- 구성: `terminal/` 6개 모듈 2,331줄 [측정]. 메인 창 오른쪽에 붙는 `Qt.Tool` 창이다 (`terminal/terminal_panel.py:43`).
- 설계서(`(내부 작업 문서)/plans/terminal-utility-design.md`)는 "QDockWidget", "연결 프로파일 저장/불러오기 ✅", "세션 컬러 배지 ✅" 를 완료로 적었으나 **현재 코드와 다르다**: 패널은 `QWidget(Qt.Tool)` 이고, `terminal_settings.py` 는 매크로만 저장한다 (연결 프로파일·창 위치 저장/복원 메서드는 정의만 있고 호출하는 곳이 없다 — 저장소 전체 `grep` [측정]). TASKS.md:979 에도 "터미널 연결 프로파일 기능 확장" 이 미완 항목으로 있다 [읽음]. 즉 설계서는 낡았다.
- 터미널 쪽 시험은 **0건**이다 (`tests/` 에서 `terminal` 언급 파일 없음 [측정]). 리팩터링 전에 특성화 시험이 필요하다.

### 2.2 구조

```text
main_gui.py (WIZWindow)
  │  _terminal_panel = TerminalPanel(self)             main_gui.py:888
  │  툴바 버튼/메뉴 Ctrl+T → _toggle_terminal           :779-785, :8754
  │  장치 목록 우클릭 "Open in Terminal"                 :8787-8824
  │  moveEvent/resizeEvent → follow_main()              :8779-8785
  ▼
TerminalPanel (QWidget, Qt.Tool)                       terminal_panel.py:25
  ├─ 툴바: 전역 Line End · Export/Import All · 📌 · ✕    :132-174
  ├─ QTabWidget  ← 고정 4개: UDP | TCP Client | TCP Server | Serial   :112-123
  │     각 탭 = BaseProtocolTab 하위 클래스 1개          protocol_tabs.py:191
  │        ├ 연결 설정 그룹 (프로토콜별 필드)
  │        ├ ReceiveDisplay (수신창)                     receive_display.py:97
  │        └ SendWidget (입력·Escape·줄끝·주기 전송)      protocol_tabs.py:40
  │        └ _handler = 프로토콜별 QThread               comm_handlers.py
  └─ MacroPanel (F1~F12 슬롯, 전역 1개)                  :127-130, macro_panel.py:161
        └ MacroRunner(QThread) → send_requested(bytes) ─▶ TerminalPanel._dispatch_send
```

데이터 흐름: 핸들러 스레드(select 50 ms 폴링) → `data_received` 시그널 → 탭의 `ReceiveDisplay.append_rx` (deque 에 적재) → 50 ms `QTimer` 가 한꺼번에 HTML 로 렌더 (`receive_display.py:112-115,240-289`). 송신은 UI → `handler.send()` (deque 에 적재) → 핸들러 루프가 비움 (`comm_handlers.py:81-82,100-109`).

### 2.3 단일 채널 가정이 박힌 곳

| # | 위치 [읽음] | 가정 | 다채널에서의 문제 |
| --- | --- | --- | --- |
| 1 | `terminal_panel.py:34-37,115-123` | 프로토콜 탭이 **정확히 4개, 프로토콜당 1개**로 하드코딩 (`TAB_UDP..TAB_SERIAL`, `self.tab_udp` 등 고정 속성) | TCP Client 를 2개 이상 만들 수 없다. 4채널 = 같은 프로토콜 4개가 흔하다 |
| 2 | `terminal_panel.py:99,229,235,201-212`, `main_gui.py:8809-8814` | 4개 탭을 **튜플/딕셔너리로 반복 나열**하는 곳이 6군데 (시그널 연결 `:179-184`, 닫기, 전역 줄끝, 자동 채우기, 매크로 전송, 그리고 main_gui) | 세션 수를 바꾸려면 전부 고쳐야 한다 |
| 3 | `terminal_panel.py:201-212` | 매크로 전송 대상 = **현재 탭 하나** (`tabs.currentIndex()`) | 여러 채널에 보낼 방법이 없다 |
| 4 | `terminal_panel.py:214-222,193-194` | TCP Client 와 TCP Server 를 동시에 연결하면 경고 (규칙). 이유는 설계서에 "다중 연결 규칙: TCP Client+Server 동시 불가" 라고만 있고 **사유 없음** [미확인] | 채널마다 모드가 다른 4CH(예: CH1 서버 모드 장치 ↔ 툴 클라이언트, CH2 클라이언트 모드 장치 ↔ 툴 서버)를 동시에 못 본다 |
| 5 | `terminal_panel.py:234-260`, `main_gui.py:8826-8879` | 장치 자동 채우기가 **채널 0 의 키만** 쓴다 (`OP LP BR DB PR SB LI`). 4CH 의 채널 1~3 코드(`QL GL CL` 등, `channel_field_map.py:31-57`)는 안 읽는다. 연결된 탭이 하나라도 있으면 아예 건너뛴다 (`terminal_panel.py:235-238`) | "Open in Terminal" 이 4CH 에서 채널 0 만 채운다 |
| 6 | `terminal_panel.py:127-130`, `macro_panel.py:303-307` | 매크로 패널 **1개**, F1~F12 가 `Qt.ApplicationShortcut` | 패널이 둘이면 F 키가 모호해진다 → 매크로는 공용 1개 유지가 맞다 |
| 7 | `protocol_tabs.py:287,368,450,586`, `:112-114`, `receive_display.py:204-209` | 탭/수신창마다 `QShortcut`(Ctrl+K, Ctrl+Return, Ctrl+↑↓, Ctrl+F, Ctrl+L, Ctrl+=/+/-) 을 **기본 컨텍스트(창 전체)** 로 등록 | 지금은 보이는 탭이 하나뿐이라 문제없지만 두 개 이상이 동시에 보이면 **모호(ambiguous)해져 아무것도 안 눌린다** — 아래 2.5 측정 |
| 8 | `protocol_tabs.py:233-238`, `terminal_panel.py:97-101` | 닫을 때 탭마다 `stop()` 후 `wait(2000)` 을 **순서대로** | 최악 채널당 2초 × 4 = 8초 UI 정지 (추론). TCP 연결 시도는 소켓 타임아웃 5초라 (`comm_handlers.py:159`) 정지 요청이 늦게 먹을 수 있다 |
| 9 | `terminal_panel.py:45,59` | 창 최소 폭 400, 붙일 때 폭 ≥ 480. 메인 창 폭 950 (`gui/wizconfig_gui.ui:15`) | 4개를 가로로 나란히 놓을 폭이 없다 (2×2 면 최소 약 800~1000 px 필요 [추정]) |
| 10 | `terminal_settings.py` (파일 전체 55줄) | 저장되는 것은 매크로뿐 | 세션 구성(몇 개, 종류, 주소)을 저장·복원하지 못한다 |

### 2.4 NetTerm3 대비 기능 격차 (4CH 시험에 의미 있는 것 위주)

| 기능 | NetTerm3 | 우리 터미널 | 격차 영향 |
| --- | --- | --- | --- |
| 같은 종류 세션 여러 개 | ○ | ✕ (프로토콜당 1개) | **핵심** |
| 동시 표시(그리드) | ○ | ✕ (탭만) | **핵심** |
| 매크로 / 주기 전송 / 이스케이프 입력 | ✕ | ○ (F1~F12, 딜레이, 주기 전송, `\r\n\xHH`) | 우리가 앞섬 — 유지해야 한다 |
| 여러 채널에 한 번에 송신 | ✕ | ✕ | 새로 필요 |
| 시리얼 흐름제어 | RTS/CTS · DTR/DSR · XON/XOFF | **없음** (`protocol_tabs.py:540-586` 필드에 없음, `SerialHandler` 인자에도 없음 `comm_handlers.py:400-402`) | 4CH 는 채널별 흐름제어(EF 등)가 있어 시험하려면 필요 |
| 시리얼 자동 재연결 | ○ | ✕ (TCP Client 만 `protocol_tabs.py:357-366`) | USB 시리얼 뽑힘·장치 재부팅 시 불편 |
| 수신 줄 조립 | ○ (TCP/Serial) | ✕ — 도착 조각마다 시각을 붙여 이어 붙인다 (`receive_display.py:247-269`) | 채널 간 로그 비교가 어렵다 |
| HEX 보기 | ○ (전체 전환) | 부분: ASCII 가 아닌 바이트만 `[HH]` 인라인 (`receive_display.py:52-56`). 인코딩 인자는 받지만 쓰지 않는다 (`:38-39,262`) | 바이너리 시험 불편 |
| 로그 실시간 파일 기록 | ○ | ✕ (화면 텍스트 Save All 뿐 `receive_display.py:379-393`) | 장시간 4채널 시험에 필요 |
| 과부하 보호 | 큐 상한 + 배압 + 드롭 표시 | **없음** — `_buf` deque 무제한 (`:101`), 한 번에 전부 렌더 (`:243-245`) | 아래 2.5 측정 |
| 설정 저장/복원 | JSON 전체 | 매크로만 | 세션 구성 복원 필요 |
| 타임스탬프 | 절대 | 절대 · 경과 · 직전 대비 (`receive_display.py:291-301`) | 우리가 앞섬 |
| 검색(Ctrl+F)·글꼴 확대 | ✕ | ○ | 유지 |
| 장치 연동 (Open in Terminal) | ✕ | ○ (채널 0 한정) | 4채널로 확장 필요 |
| UDP 수신 송신자 표시 | ○ | ✕ — 핸들러는 `from_ip, from_port` 를 올리지만 탭이 버린다 (`protocol_tabs.py:301`) | 소소함 |
| TCP Server 다중 클라이언트 | ○ | 1개 + 신규 접속 시 모달 질문 (`comm_handlers.py:274`, `protocol_tabs.py:501-512`) | 채널 여럿이 모달에 막힐 수 있음 |

### 2.5 확장 시 걸림돌 — 측정한 것

측정은 모두 오프스크린 Qt(`QT_QPA_PLATFORM=offscreen`)에서 우리 실제 위젯을 그대로 써서 했다. 실제 화면 렌더 비용이 빠져 있으므로 **절대값이 아니라 상대 비교**로만 읽어야 한다. 이 PC 한 대 기준이다.

**(1) 단축키가 모호해진다 [측정].** `ReceiveDisplay`(Ctrl+L)와 `MacroPanel`(F1)을 한 창에 나란히 넣고 키 이벤트를 보냈다.

| 같은 창에 보이는 개수 | Ctrl+L 로 지워진 수신창 | F1 로 실행된 매크로 패널 |
| --- | --- | --- |
| 1 (대조군) | 1 | 1 |
| 2 | **0** | **0** |
| 4 | **0** | **0** |

대조군이 동작하므로 시험 배선은 맞다. 둘 이상이면 **둘 다 죽는다**. 해법 후보를 같은 방식으로 재 보았다: 단축키를 `Qt.WidgetWithChildrenShortcut` 컨텍스트로 두면 4개가 보여도 **포커스가 있는 패널 하나만** 반응했다 (2번째 패널에 포커스 → `[2]`). 기본 `WindowShortcut` 은 `[]` [측정]. → 다채널화하려면 탭/수신창/송신창의 단축키 컨텍스트를 바꿔야 하고, F1~F12 매크로는 패널을 하나만 두어야 한다.

**(2) 수신창 렌더 부하 [측정].** 한 번의 `_flush()` 가 UI 스레드를 잡는 시간 (1 KiB 조각, 80자 줄):

| 수신창 수 × 쌓인 양 | 한 번 flush |
| --- | --- |
| 1 × 64 KiB | 55 ms |
| 4 × 64 KiB | 210 ms |
| 1 × 512 KiB | 352 ms |
| 4 × 512 KiB | 1,490 ms |
| 1 × 2 MiB | 1,446 ms |
| 4 × 2 MiB | 6,431 ms |

대략 **0.7~0.9 ms/KiB, 양에 비례** (정상 상태에서는 50 ms 마다 비우므로 쌓이는 양이 작다). 외삽 [추정]: 4채널이 모두 921600 baud 8N1 로 쉬지 않고 쏟아내면 (약 92 KB/s × 4 ≈ 360 KB/s) UI 스레드의 약 1/4 을 수신창 렌더에 쓴다. 문제는 평균이 아니라 **상한이 없다**는 점이다: `_buf` 가 무제한이라 한 번 밀리면 1~6초 멈출 수 있고, 일시정지(⏸) 중에는 계속 쌓인다 (`receive_display.py:101,241-242`). 4채널은 이 위험을 4배로 만든다.

**(3) 송신 지연이 50 ms 폴링에 묶여 있다 [읽음 + 측정].** 핸들러 루프는 "송신 큐 비우기 → `select(..., 0.05)`" 순서라서 (`comm_handlers.py:100-112,184-197`), 루프가 `select` 에서 자고 있는 동안 들어온 송신은 최대 50 ms 기다린다. 루프백에서 TCP Client 핸들러 4개에 거의 동시에 `send()` 한 결과 [측정, 60회]:

| 항목 | 값 |
| --- | --- |
| `send()` → 상대 수신 지연 | 중앙 25~29 ms, p90 56 ms, 최대 약 64 ms |
| 4채널 도착 시각 편차(최대−최소), 핸들러를 **같은 순간에** 시작 | 중앙 0.2 ms, 최대 0.6 ms |
| 같은 편차, 핸들러를 **제각각 시각에** 시작 | **중앙 31 ms, 최대 32 ms** |

편차가 시작 시각(위상)에 좌우된다는 점이 중요하다: 핸들러마다 고정 주기 폴링이라 위상이 맞으면 거의 동시에, 어긋나면 최대 50 ms 까지 벌어진다. 실사용은 채널을 제각각 연결하므로 후자에 가깝다 [추정]. "4채널 동시 송신"을 시험하려는 목적이라면 이 지터는 시험 결과를 흐릴 수 있다. 해결은 송신 시 폴링을 깨우는 것 (소켓 쌍/이벤트) — 짝 문서 §6.4.

**(4) 종료 정지 [읽음, 추론].** (2.3 #8) 병렬 `stop()` 후 `wait()` 로 바꾸면 해결된다.

**(5) 이미 있는 위험 한 가지.** `fix(terminal): TCPClientHandler run() 중간 emit 제거 — QThread GC 크래시 수정` (커밋 `658f2f8`) — 핸들러 객체 수명을 잘못 다루면 크래시가 난 전례가 있다. 세션을 동적으로 만들고 지우는 설계에서는 핸들러가 끝나기 전에 참조를 놓지 않도록 해야 한다 [읽음].

### 2.6 그대로 재사용 가능한 것

- **핸들러(`comm_handlers.py`)는 인스턴스별로 독립이다.** 모듈 수준 상태가 없다 (함수 `list_serial_ports`, `_encode_escape` 는 순수). 같은 종류를 여러 개 만들어도 서로 간섭하지 않는다 [읽음]. 4개 동시 동작은 위 (3)의 시험에서 실제로 확인됐다 (TCP Client 4개).
- **`BaseProtocolTab` 하위 클래스가 이미 "세션 위젯"이다.** 연결 설정 + 수신창 + 송신창 + 핸들러를 갖고 `connection_state_changed` 시그널을 낸다 (`protocol_tabs.py:191-238`). 고정돼 있는 것은 `TerminalPanel` 이 4개를 속성으로 쥐고 있는 방식이다. 세션 위젯 자체를 크게 고칠 필요는 없다 [읽음 + 추정].
- 매크로 시퀀스·이스케이프 인코딩·주기 전송·타임스탬프 3모드·검색은 NetTerm3 에 없는 우리 자산이다.
- main_gui 와의 접점은 3곳뿐이다: 생성(`:888`), 토글/따라가기(`:8754-8785`), 장치 자동 채우기(`:8797-8879`). 다른 곳에서 `terminal` 을 쓰지 않는다 [읽음].

### 2.7 기존 동작 중 확인이 필요한 것 (이번 범위 밖, 다채널화할 때 같이 정해야 함)

| 항목 | 내용 | 근거 |
| --- | --- | --- |
| TCP Server 탭 자동 채우기 포트 | 장치가 TCP Client 모드일 때 툴이 listen 할 포트는 장치의 **원격 포트**(RP, 채널별 AP/TP/JP)여야 맞아 보이는데, 코드는 장치의 **로컬 포트(LP)** 를 넣는다 (`terminal_panel.py:244-246`, `protocol_tabs.py:518-519`, `main_gui.py:8873`). 의도인지 오류인지 모르겠다 | 읽음 + 추론, **[미확인]** |
| 혼합 모드(OP=2) 매핑 | 장치 Mixed 를 툴 TCP Server 탭(= 'TCP Client' 문자열)으로 보낸다 (`main_gui.py:8830-8835`, `terminal_panel.py:254-258`). Mixed 는 서버+클라이언트 양쪽이라 선택이 임의적 | 읽음 |
| 서버 탭 신규 접속 대기 | 주석은 "최대 30초" 라고 하나 코드는 응답이 올 때까지 무한 대기 (`comm_handlers.py:306-310`) | 읽음 |
| `TCPClientHandler` 끝에서 `disconnected` 중복 방출 가능 | 자동 재연결 켠 상태에서 끊김 시 한 번, 루프 종료 시 한 번 (`:208-211,223`) | 읽음 |

## 3. 이 문서가 설계에 넘기는 결론

1. **NetTerm3 의 해법은 "채널" 이 아니라 "세션 N개 + 그리드"** 이고 우리 코드도 그 방향으로 가장 적게 고칠 수 있다 (세션 위젯이 이미 있다).
2. **그대로 가져오면 안 되는 것**: 채널 간 기능이 없다는 점(전체 전송), ANSI 기본 켬(바이너리 시험에 부적합).
3. **먼저 막아야 하는 위험**: 단축키 모호(측정됨), 수신창 무제한 적재, 폴링 송신 지연·편차, 시험 0건, 종료 지연.
4. **사람이 확인할 것**: 4CH 담당자가 실제로 어떻게 시험하는지(시리얼 쪽도 PC 에 4개 연결하는지), TCP Client/Server 동시 불가 규칙의 사유, 2.7 항목.

## 부록. 측정 스크립트 (스크래치, 저장소 밖)

| 스크립트 | 무엇을 | 사용한 우리 코드 |
| --- | --- | --- |
| `shortcut_ambiguity.py` | Ctrl+L / F1 모호성 | `terminal/receive_display.py`, `terminal/macro_panel.py` |
| `shortcut_ctx_and_bench.py` | 컨텍스트별 단축키 + flush 시간 | `terminal/receive_display.py` |
| `tx_latency.py` | TCP Client 4개 송신 지연·편차 | `terminal/comm_handlers.py` |

세 스크립트 모두 `QT_QPA_PLATFORM=offscreen`, 저장소 파일을 수정하지 않는다. 필요하면 요청 시 `tests/` 용으로 정리할 수 있다.
