# Phase 7: TFTP FW Upload - Research

**Researched:** 2026-05-19
**Domain:** tftpy TFTP 서버 / PyQt5 QThread / WIZ550 0xD1 패킷 / UDP 수신
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01**: 방식 C — 내장 tftpy + 외부 TFTP 수동 입력 둘 다 지원
  - 별도 `WIZ550 FW Upload` 다이얼로그 창 (탭 2개)
  - 탭 1 "자동 (내장 TFTP)": 파일 선택 → tftpy 로컬 서버 자동 구동 → 0xD1 전송
  - 탭 2 "수동 (외부 TFTP)": 서버 IP / 포트 / 파일명 직접 입력 → 0xD1만 전송

- **D-02**: 포트 69 바인딩 실패 시 → 오류 메시지 표시 후 중단 (자동 fallback 없음)
  - 안내 문자열: "Port 69 requires Administrator privileges. Please use external TFTP mode."

- **D-03**: 수동 탭 서버 IP는 현재 NIC IP(`self.localip_addr`) 자동 채움 (편집 가능). 기본 포트 69.

- **D-04**: 0xD1 패킷 `set_pw_len` / `set_pw[16]` 필드 — 다이얼로그에 pw 입력 필드 추가
  - 선택적 입력 (빈 칸 → pw_len=0, pw=zeros)

- **D-05**: FW 업로더 QThread → 별도 `WIZ550FWUploadThread.py` 파일 생성
  - `FWUploadThread.py` 패턴 참조, tftpy 서버 기반 완전히 다른 구현
  - `WIZ550MSGHandler.py`에 0xD1 패킷 빌더 함수(`build_fw_upload_pkt`) 추가

- **D-06**: `event_upload_clicked()` 분기 — WIZ550 장치 선택 시 전용 다이얼로그 실행
  - 기존 패턴: `_proto == 'wiz550'` 체크 → `upload_wiz550()` 호출

- **D-07**: tftpy 콜백 활용
  - 전송 시작 시: QProgressBar 애니메이션 시작 (indeterminate)
  - 완료 감지 → 100% 점프
  - 0xD2 응답 수신 또는 타임아웃 시 결과 메시지 표시

### Claude's Discretion

- 다이얼로그 정확한 위젯 배치 (QTabWidget, 버튼 배치 등) — Phase 6 D-02~D-04 디자인 토큰 따름
- 0xD2 응답 수신 소켓 구현 방식 (WIZ550FWUploadThread 내부에서 UDP 리슨)
- 타임아웃 값 (시작: 30초 권장)
- tftpy 정확한 콜백 API 사용법

### Deferred Ideas (OUT OF SCOPE)

- WIZ550 비밀번호 필드 실제 동작 여부 — 실장치 테스트 후 유지/제거 결정
- tftpy 내 전송 진행률 % 실시간 표시
- 포트 69 자동 fallback (고포트)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FW-01 | tftpy 기반 로컬 TFTP 서버 구동 (포트 69, 실패 시 안내 후 중단) | tftpy 0.8.7 TftpServer API 완전 확인. listen() / stop() 시그니처 검증 완료. |
| FW-02 | op_code 0xD1 FW 업로드 시작 패킷 전송 (86바이트, LE 서버포트) | 07-CONTEXT.md 오프셋 맵 + WIZ550MSGHandler._build_header_with_payload() 재사용 패턴 확인 |
| FW-03 | 업로드 완료 알림 (0xD2 응답) 처리 또는 타임아웃 | 응답 구조 확인 (src_mac[6], op_code[0]=0xD2, op_code[1]=0x55). UDP select() 루프 패턴 기존 코드에서 확인. |
| FW-04 | FW 업로드 UI (파일 선택, 프로그레스, 오류 메시지) | QTabWidget 2탭 구조, QProgressBar indeterminate 패턴, 기존 firmware_update() UI 패턴 확인 |
</phase_requirements>

---

## Summary

WIZ550 TFTP 펌웨어 업로드는 장치가 TFTP 클라이언트 역할을 한다. 도구가 0xD1(FIRMWARE_UPLOAD_INIT) 패킷으로 "서버 IP/포트/파일명"을 장치에 알려주면, 장치가 직접 TFTP 서버에 접속해 파일을 내려받는다. 도구가 구현해야 하는 것은 (1) tftpy 로컬 TFTP 서버 구동, (2) 0xD1 패킷 전송, (3) 0xD2 완료 응답 수신 대기, 세 가지다.

tftpy 0.8.7은 2026년 2월 배포된 최신 버전으로, `TftpServer(tftproot, upload_open)` 생성 후 `server.listen(ip, port)` 호출이 전부다. `listen()`은 블로킹 루프이므로 반드시 QThread 내부에서 호출해야 한다. `server.stop(now=True)`로 즉시 종료 가능하며 `is_running` threading.Event로 시작 여부를 확인할 수 있다. packethook 파라미터는 0.8.7에 없다(PR #101로 제안되었으나 미병합). 완료 감지는 tftpy 내부 state=None 패턴이나 별도 upload_open 콜백을 통해 한다.

0xD1 패킷은 86바이트 고정이며, WIZ550MSGHandler의 `_build_header_with_payload()` 함수를 직접 재사용할 수 있다. server_port는 리틀엔디안(LSB first)으로 직접 struct.pack('<H', port)를 사용해야 한다. 0xD2 응답은 op_code[0]=0xD2, op_code[1]=0x55, payload=src_mac[6] 구조이며, WIZ550MSGHandler의 UDP 소켓 패턴(`select.select` 루프)으로 수신한다.

**Primary recommendation:** WIZ550FWUploadThread.py 신규 파일 1개 + wiz550_fw_dialog.py 다이얼로그 1개를 만들고, WIZ550MSGHandler.py에 `build_fw_upload_pkt()` 빌더 함수를 추가한다. main_gui.py 수정은 `event_upload_clicked()` 분기 추가 + `upload_wiz550()` 메서드 추가로 최소화한다.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tftpy | 0.8.7 | Python TFTP 서버/클라이언트 | RFC 1350/2347/2348 구현, MIT 라이선스, 2026-02 최신 배포 |
| PyQt5 | 5.15.11 | QThread, QDialog, QTabWidget, QProgressBar | 기존 프로젝트 표준 |
| socket / select | stdlib | UDP 소켓 0xD1 전송 + 0xD2 응답 수신 | 기존 WIZ550MSGHandler 패턴 동일 |
| threading | stdlib | tftpy listen() 블로킹 루프를 QThread 내부에서 별도 threading.Event로 동기화 | tftpy.TftpServer.is_running이 threading.Event |
| struct | stdlib | server_port LE 2바이트 직접 패킹 (`struct.pack('<H', port)`) | 기존 WIZ550 패킷 빌더 패턴 동일 |

**Installation:**
```bash
# requirements.txt에 추가:
tftpy==0.8.7
```
[VERIFIED: pip show tftpy → Version: 0.8.7, Released: 2026-02-04]

---

## Architecture Patterns

### Recommended File Structure

```
WIZ550FWUploadThread.py   # QThread: tftpy 서버 구동 + 0xD1 전송 + 0xD2 수신 대기
wiz550_fw_dialog.py       # QDialog: QTabWidget 2탭 (자동/수동)
WIZ550MSGHandler.py       # build_fw_upload_pkt() 함수 추가 (기존 파일)
main_gui.py               # event_upload_clicked() 분기 + upload_wiz550() 추가 (기존 파일)
```

### Pattern 1: tftpy TftpServer 실제 API (0.8.7)

```python
# Source: C:\Users\user\AppData\Roaming\Python\Python312\site-packages\tftpy\TftpServer.py (직접 읽음)

import tftpy
import threading

# 1. 생성
server = tftpy.TftpServer(tftproot="/path/to/fw/dir")  # tftproot 디렉토리가 존재해야 함

# 2. 별도 스레드(QThread.run 내부)에서 블로킹 listen 호출
server.listen(listenip="192.168.0.100", listenport=69)
# listen()은 stop()이 호출될 때까지 반환하지 않음

# 3. 외부에서 중지 (예: 타임아웃 후)
server.stop(now=True)   # 즉시 중지 — 모든 세션 강제 종료
server.stop(now=False)  # 우아한 중지 — 진행 중 전송 완료 후 종료

# 4. 서버 시작 여부 확인
server.is_running.wait(timeout=2.0)   # is_running: threading.Event
```

**핵심 제약:**
- `TftpServer.__init__`에서 `tftproot` 디렉토리가 존재하지 않으면 `TftpException` 발생
- `listen()` 호출 시 port 바인딩 실패는 `OSError`로 전파됨 (re-raise)
- `listen()` 메서드에 `packethook` 파라미터 없음 (0.8.7 기준) — 완료 감지는 아래 방법 사용
- `upload_open` 콜백: 업로드 요청 시 file-like object 반환 → 서버 사이드 업로드 처리 시 사용 (WIZ550는 다운로드 방향이므로 불필요)

### Pattern 2: tftpy 완료 감지 — 타임아웃 기반 접근

packethook이 없으므로, 0xD2 UDP 응답 수신으로 완료를 감지한다.

```python
# Source: WIZ550MSGHandler.py의 select.select 패턴 참조 (직접 읽음)
import select

def _wait_for_fw_done(sock_udp, timeout_sec: float = 30.0) -> bool:
    """
    WIZ550 포트 6550으로 0xD2(FIRMWARE_UPLOAD_DONE) 응답 대기.
    반환: True=성공, False=타임아웃
    """
    deadline = time.time() + timeout_sec
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return False
        ready, _, _ = select.select([sock_udp], [], [], remaining)
        if not ready:
            return False
        data, _ = sock_udp.recvfrom(256)
        if len(data) >= 7 and data[0] == 0xA5 and data[3] == 0xD2 and data[4] == 0x55:
            return True  # 0xD2 응답 수신
```

### Pattern 3: WIZ550FWUploadThread QThread 구조

```python
# Source: FWUploadThread.py 패턴 + WIZ550MSGHandler.py 패턴 참조 (직접 읽음)
from PyQt5.QtCore import QThread, pyqtSignal
import tftpy, tempfile, os, socket, select, time, threading

class WIZ550FWUploadThread(QThread):
    progress = pyqtSignal(str)   # 상태 메시지
    finished = pyqtSignal(bool)  # True=성공, False=실패
    error = pyqtSignal(str)      # 오류 메시지

    def __init__(self, mode, fw_path, target_ip, target_mac,
                 server_ip, server_port, pw="", iface_ip=""):
        super().__init__()
        self.mode = mode          # 'auto' 또는 'manual'
        self.fw_path = fw_path
        self.target_ip = target_ip
        self.target_mac = target_mac
        self.server_ip = server_ip
        self.server_port = server_port
        self.pw = pw
        self.iface_ip = iface_ip
        self._server = None       # tftpy.TftpServer 인스턴스 보관

    def run(self):
        try:
            if self.mode == 'auto':
                self._run_auto()
            else:
                self._run_manual()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

    def _run_auto(self):
        # 1. tftproot 임시 디렉토리 생성 + FW 파일 복사(또는 심링크)
        tmpdir = tempfile.mkdtemp(prefix='wiz550fw_')
        fw_filename = os.path.basename(self.fw_path)
        dst = os.path.join(tmpdir, fw_filename)
        shutil.copy2(self.fw_path, dst)

        # 2. tftpy 서버 생성
        self._server = tftpy.TftpServer(tftproot=tmpdir)

        # 3. 별도 스레드에서 listen() — QThread.run() 자체가 이미 별도 스레드
        #    listen()이 블로킹이므로 threading.Thread로 한 단계 더 분리
        listen_thread = threading.Thread(
            target=self._server.listen,
            args=(self.server_ip, self.server_port),
            daemon=True
        )
        listen_thread.start()

        # 4. is_running 대기 (서버 준비 확인)
        if not self._server.is_running.wait(timeout=3.0):
            self.error.emit("TFTP 서버 시작 실패")
            self.finished.emit(False)
            return

        # 5. 0xD1 패킷 전송
        self.progress.emit("0xD1 패킷 전송 중...")
        self._send_fw_init()

        # 6. 0xD2 응답 대기
        self.progress.emit("장치 응답 대기 중...")
        success = self._wait_d2()

        # 7. 서버 중지 + 정리
        self._server.stop(now=True)
        shutil.rmtree(tmpdir, ignore_errors=True)

        self.finished.emit(success)
```

### Pattern 4: 0xD1 패킷 빌더 (WIZ550MSGHandler.py에 추가)

```python
# Source: CONTEXT.md 오프셋 맵 + WIZnet_Header.java firmware_upload() 분석 (직접 읽음)
# offset 7~12: dst_mac[6]
# offset 13:   pw_len[1]
# offset 14~29: pw[16]
# offset 30~33: server_ip[4]
# offset 34~35: server_port LE[2]  ← 반드시 리틀엔디안
# offset 36~85: file_name[50]      ← 0 패딩
# 합계: header 7B + payload 79B = 86B

def build_fw_upload_pkt(target_mac: str, server_ip: str, server_port: int,
                        file_name: str, password: str = "") -> bytes:
    """
    FIRMWARE_UPLOAD_INIT(0xD1) 패킷 — 86바이트.
    반환: 완성된 패킷 bytes (XOR 암호화 포함)
    """
    mac_b = _mac_str_to_bytes(target_mac)                        # 6B
    pw_enc = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')  # 16B
    pw_len = min(len(password.strip()), 16)                       # 1B
    ip_b = bytes(int(x) for x in server_ip.split('.'))           # 4B
    port_b = struct.pack('<H', server_port)                       # 2B LE
    fname_b = file_name.encode('ascii', errors='replace')[:50].ljust(50, b'\x00')  # 50B

    payload = mac_b + bytes([pw_len]) + pw_enc + ip_b + port_b + fname_b  # 79B
    return _build_header_with_payload(OP_FW_UPLOAD, unicast=True, payload=payload)
```

### Pattern 5: event_upload_clicked() 분기 추가

```python
# Source: main_gui.py line 1250 event_upload_clicked() 현재 코드 (직접 읽음)
def event_upload_clicked(self):
    # WIZ550 장치 전용 다이얼로그 분기 (Phase 7)
    if (hasattr(self, 'curr_mac') and self.curr_mac
            and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
        self.upload_wiz550()
        return
    # 기존 WIZ1x0SR 처리
    if self.curr_dev == 'WIZ1x0SR':
        self.show_msgbox("Info", "WIZ1x0SR 펌웨어 업로드는 지원되지 않습니다.", QMessageBox.Information)
        return
    # 기존 WIZ5xxSR 처리
    if self.localip_addr is not None:
        self.update_btn_clicked()
    else:
        self.show_msgbox("Warning", "Local IP information could not be found.", QMessageBox.Warning)
```

### Anti-Patterns to Avoid

- **listen()을 메인 스레드에서 직접 호출**: GUI 프리즈 발생. 반드시 QThread.run() 내부에서 호출.
- **tftproot를 FW 파일 경로로 직접 지정**: tftproot는 디렉토리여야 함. 파일명은 별도 `file_name` 필드로 전달.
- **server_port를 빅엔디안으로 패킹**: WIZnet_Header.java 소스가 명시적으로 `data[index++] = (byte) port; data[index++] = (byte)(port >> 8);` (LSB first). `struct.pack('>H', port)` 사용 금지.
- **0xD2 응답을 WIZ550MSGHandler의 기존 수신 소켓으로 수신**: 검색/설정 소켓과 포트가 겹칠 경우 충돌 가능. 별도 UDP 소켓 생성.
- **QThread.terminate() 호출**: 리소스 누수 + tftpy 서버 소켓 미정리. `server.stop(now=True)` → `QThread.wait()` 순서로 처리.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TFTP 서버 구현 | UDP ACK/WRQ/DATA 패킷 직접 구현 | tftpy.TftpServer | RFC 1350 엣지 케이스(재전송, 블록 번호 롤오버, OACK) 직접 구현은 수백 줄 |
| 임시 디렉토리 관리 | os.mkdir + os.unlink 직접 | tempfile.mkdtemp + shutil.rmtree | 예외 발생 시 정리 보장 |
| XOR 암호화 | 별도 구현 | WIZ550MSGHandler._encrypt() 재사용 | 이미 검증된 구현, `_build_header_with_payload()` 내부에서 자동 처리 |

**Key insight:** tftpy의 핵심 가치는 RFC 1350 ACK/재전송 로직이다. 이를 직접 구현하면 WIZ550 장치가 블록 재전송 요청 시 응답 못 하는 현장 버그가 발생한다.

---

## Common Pitfalls

### Pitfall 1: tftproot 디렉토리 비존재
**What goes wrong:** `TftpServer("/nonexistent/path")` 생성 시 `TftpException("The tftproot does not exist.")` 즉시 발생.
**Why it happens:** `__init__`에서 `os.path.exists(self.root)` 검사.
**How to avoid:** `tempfile.mkdtemp()`로 임시 디렉토리 먼저 생성 후 TftpServer 인스턴스 생성.
**Warning signs:** Wave 0 테스트에서 TftpServer 객체 생성 실패.

### Pitfall 2: 포트 69 권한
**What goes wrong:** Windows에서 포트 1~1023 바인딩은 원칙적으로 관리자 권한 필요. `OSError: [WinError 10013]` 발생 가능. (현재 개발 머신은 관리자 실행 중이라 통과되지만, 일반 사용자 실행 시 실패)
**Why it happens:** Windows 소켓 보안 정책 (Well-known port 보호).
**How to avoid:** `listen()` 호출을 try/except OSError로 감싸고, 실패 시 D-02에 따라 "Port 69 requires Administrator privileges" 메시지 표시.
**Warning signs:** 현장에서 일반 사용자 계정으로 실행 시 서버 시작 실패.

### Pitfall 3: server_port 엔디안 오류
**What goes wrong:** `struct.pack('>H', 69)` (빅엔디안) 사용 시 장치가 포트 번호를 잘못 읽어 TFTP 연결 실패.
**Why it happens:** WIZnet_Header.java 원본이 명시적으로 `LSB first, MSB second` 방식으로 구현됨.
**How to avoid:** 반드시 `struct.pack('<H', port)` 사용. 또는 `bytes([port & 0xFF, (port >> 8) & 0xFF])`.
**Warning signs:** 장치가 TFTP 서버에 연결 시도하지 않음 (포트 번호 오인).

### Pitfall 4: listen() 반환 후 QThread 소멸
**What goes wrong:** `server.stop(now=True)` 호출 후 `listen()`이 반환되면 QThread.run()도 종료. 이 시점에 `self._server`에 접근하면 None.
**Why it happens:** listen() → is_running.clear() → QThread.run() 종료.
**How to avoid:** `finished` 시그널 전송은 `stop()` 호출 후, `listen_thread.join()` 완료 후에 emit. 순서: stop(now=True) → listen_thread.join(timeout=2) → finished.emit().

### Pitfall 5: 0xD2 응답 소켓 충돌
**What goes wrong:** WIZ550 검색/설정 소켓과 동일한 bind() 주소를 사용할 경우 `OSError: address already in use`.
**Why it happens:** WIZ550MSGHandler 인스턴스가 이미 WIZ550_PORT(6550) 소켓을 열고 있을 수 있음.
**How to avoid:** WIZ550FWUploadThread 내부에서 `SO_REUSEADDR=1` 설정 후 새 소켓 바인딩. 또는 `('', 0)` bind 후 소스 포트 무관 수신.

### Pitfall 6: FW 파일명 50바이트 초과
**What goes wrong:** 파일명이 50자를 초과하면 silently truncated → 장치가 파일을 찾지 못함.
**Why it happens:** file_name 필드는 50바이트 고정.
**How to avoid:** 파일 선택 시 `os.path.basename(fw_path)[:50]` 적용 + 사용자에게 경고.

---

## Code Examples

### 0xD1 패킷 구조 검증 코드

```python
# Source: CONTEXT.md §0xD1 패킷 구조 + WIZnet_Header.java §3.5.7 (직접 분석)
import struct

def _verify_fw_pkt_layout(pkt: bytes):
    """0xD1 패킷 86바이트 레이아웃 검증용 디버그 출력"""
    assert len(pkt) == 86, f"Expected 86 bytes, got {len(pkt)}"
    assert pkt[0] == 0xA5           # STX
    assert pkt[3] == 0xD1           # op_code = FW_UPLOAD_INIT
    assert pkt[4] == 0xAA           # WIZNET_REQUEST
    # payload length = 79 (LE)
    assert pkt[5] == 79 and pkt[6] == 0
    # offset 34~35: server_port LE
    port = struct.unpack_from('<H', pkt, 34)[0]
    return port
```

### QProgressBar Indeterminate 모드

```python
# Source: PyQt5 QProgressBar API [ASSUMED: 표준 PyQt5 패턴]
pgbar.setRange(0, 0)    # min=max=0 → indeterminate (animating)
pgbar.setValue(0)
pgbar.show()

# 완료 시:
pgbar.setRange(0, 100)
pgbar.setValue(100)
```

### 다이얼로그 파일 선택 패턴 (기존 코드와 일관성)

```python
# Source: main_gui.py firmware_file_open() 패턴 (직접 읽음)
fname, _ = QFileDialog.getOpenFileName(
    self, "펌웨어 파일 선택", "", "Binary Files (*.bin);;All Files (*)"
)
if fname:
    basename = os.path.basename(fname)
    if 'BOOT' in basename.upper():
        # BOOT 파일 업로드 금지 (기존 패턴)
        ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Java 원본 툴: 외부 TFTP 서버 필요 | Python 내장 tftpy 서버 | Phase 7 신규 | 현장에서 별도 TFTP 서버 불필요 |
| FWUploadThread: TCP 파일 전송 방식 | WIZ550FWUploadThread: TFTP 서버 방식 | Phase 7 신규 | WIZ550 전용 프로토콜 적용 |

**Deprecated/outdated:**
- tftpy packethook(server-side): PR #101로 제안되었으나 0.8.7에 미포함 → 완료 감지는 0xD2 응답 수신으로 대체

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | QProgressBar.setRange(0,0)으로 indeterminate 모드 동작 | Code Examples | PyQt5 버전에 따라 다를 수 있으나 확률 낮음 |
| A2 | WIZ550 장치가 TFTP 다운로드 완료 후 반드시 0xD2 응답을 전송 | Common Pitfalls | 실장치 테스트 전까지 미확인. Java 원본 GUI.java에서 receivedPacket(0xD2, ...) → "Success Firmware Uploading" 패턴 확인 [CITED: 2026-05-14-wiz550-protocol-analysis.md §2.1] |
| A3 | tftpy 서버 시작 직후 is_running.wait(3.0)으로 준비 확인 가능 | Architecture Patterns | listen() 내부에서 is_running.set() 호출 확인됨 [VERIFIED: TftpServer.py line 111] — 타임아웃 3초는 충분할 것으로 예상 |
| A4 | 0xD2 응답이 UDP 6550 포트로 전송됨 | Architecture Patterns | 프로토콜 분석 문서 §5.2에서 응답 패킷 op_code 목록 확인 [CITED: 2026-05-14-wiz550-protocol-analysis.md] — 정확한 응답 소켓 포트(6550 vs 기타)는 실장치 확인 필요 |

---

## Open Questions

1. **0xD2 응답의 정확한 소켓 동작**
   - What we know: Java GUI.java에서 ReceiveThread(동일 UDP 소켓)가 0xD2를 수신하여 콜백 호출
   - What's unclear: WIZ550FWUploadThread 내부에서 tftpy 서버와 함께 동일 소켓(WIZ550_PORT=6550)을 사용해야 하는지, 아니면 별도 포트로도 수신 가능한지
   - Recommendation: 안전하게 WIZ550_PORT(6550)에 SO_REUSEADDR 소켓을 열어 수신 대기. 기존 WIZ550MSGHandler 인스턴스와 포트 충돌 여부는 업로드 시 검색 스레드 중지 여부로 결정됨.

2. **tftpy listen() 블로킹 루프를 QThread 내 별도 threading.Thread로 분리해야 하는가?**
   - What we know: QThread.run()은 이미 별도 스레드. listen()을 run() 내부에서 직접 호출 가능.
   - What's unclear: listen() 도중 stop()을 다른 스레드(Qt 메인 스레드)에서 호출해야 하므로 QThread.run()에서 listen()을 직접 실행하면 QThread가 종료되기 전까지 stop() 호출 시점 제어가 가능한지.
   - Recommendation: listen()을 run() 내 `threading.Thread(daemon=True)`로 분리하고, QThread.run()은 0xD2 대기 + 타임아웃 로직을 담당. 정리 순서: stop(now=True) → listen_thread.join(timeout=3) → finished.emit().

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tftpy | FW-01 TFTP 서버 | ✓ (설치됨) | 0.8.7 | 없음 — requirements.txt 추가로 배포 시 포함 |
| PyQt5 | FW-04 UI | ✓ | 5.15.11 | — |
| port 69 (UDP) | FW-01 자동 탭 | ✓ (현재 관리자 실행) | — | D-02: 실패 시 오류 메시지 후 중단, 수동 탭 안내 |
| pytest | Wave 0 테스트 | ✓ | 9.0.3 | — |

**Missing dependencies with no fallback:**
- 없음 — tftpy는 requirements.txt에 추가하면 배포 시 자동 포함됨.

**Missing dependencies with fallback:**
- 포트 69 바인딩 실패: D-02에 따라 오류 메시지 + 수동 탭 안내로 fallback.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | 없음 (pytest.ini / pyproject.toml 없음) |
| Quick run command | `uv run pytest tests/test_wiz550_fw.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FW-01 | TftpServer 생성 + listen 시작 + stop 동작 | unit | `uv run pytest tests/test_wiz550_fw.py::test_tftp_server_start_stop -x` | ❌ Wave 0 |
| FW-02 | build_fw_upload_pkt() → 86바이트, server_port LE 검증 | unit | `uv run pytest tests/test_wiz550_fw.py::test_build_fw_upload_pkt -x` | ❌ Wave 0 |
| FW-03 | 0xD2 응답 파싱 | unit | `uv run pytest tests/test_wiz550_fw.py::test_parse_fw_done_reply -x` | ❌ Wave 0 |
| FW-04 | 다이얼로그 생성 + 탭 2개 존재 | unit | `uv run pytest tests/test_wiz550_fw.py::test_dialog_tabs -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_wiz550_fw.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_wiz550_fw.py` — FW-01~04 커버
  - `test_build_fw_upload_pkt` — 86바이트 레이아웃 + server_port LE 검증
  - `test_tftp_server_tempdir` — tmpdir 생성 + TftpServer 초기화 성공
  - `test_parse_fw_done_reply` — 0xD2 응답 파싱 함수 (7B 헤더 + 6B MAC = 13B)
  - `test_dialog_tabs` — WIZ550FWDialog QTabWidget 탭 2개 (qapp 픽스처 사용)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | 아니오 | — |
| V3 Session Management | 아니오 | — |
| V4 Access Control | 아니오 | — |
| V5 Input Validation | 예 | 서버 IP 유효성 검사 (4옥텟), 포트 범위 1~65535, 파일명 50자 제한 |
| V6 Cryptography | 아니오 (XOR 암호화는 보안 목적 아님) | 기존 WIZ550 XOR 패턴 그대로 사용 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 잘못된 서버 IP 입력 | Tampering | IP 형식 검증 (4옥텟 0~255) + `socket.inet_aton()` 시도 |
| 포트 범위 오류 | Tampering | 1~65535 범위 체크 |
| BOOT 파일 업로드 | Tampering | 파일명에 'BOOT' 포함 시 업로드 거부 (기존 firmware_file_open() 패턴 동일) |

---

## Sources

### Primary (HIGH confidence)

- `C:\Users\user\AppData\Roaming\Python\Python312\site-packages\tftpy\TftpServer.py` — listen(), stop(), __init__ 전체 소스 직접 읽음 [VERIFIED]
- `D:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI\WIZ550MSGHandler.py` — _build_header_with_payload(), _encrypt(), OP_FW_UPLOAD 상수 확인 [VERIFIED]
- `D:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI\FWUploadThread.py` — QThread 시그널 패턴, pyqtSignal 시그니처 [VERIFIED]
- `D:\user\Documents\GitHub\WIZnet-S2E-Tool-GUI\main_gui.py` (line 1250) — event_upload_clicked(), apply_wiz550() 분기 패턴 [VERIFIED]
- `~/.claude/docs/WIZnet-S2E-Tool-GUI/research/2026-05-14-wiz550-protocol-analysis.md` §3.5.7, §10.6 — 0xD1 패킷 오프셋 맵, 0xD2 응답 구조, FW 업로드 실제 메커니즘 [CITED]

### Secondary (MEDIUM confidence)

- [tftpy PyPI 페이지](https://pypi.org/project/tftpy/) — 버전 0.8.7, 2026-02-04 배포 확인 [VERIFIED: pip show tftpy]
- [GitHub PR #101](https://github.com/msoulier/tftpy/pull/101/files) — packethook server-side가 0.8.7에 미포함 확인 [MEDIUM]

### Tertiary (LOW confidence)

- Windows 포트 1~1023 바인딩 관리자 권한 요구 — [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/292450/) 참조 [LOW — 현재 머신에서 비관리자로 포트 69 바인딩 성공하여 모순됨. Windows 버전/설정에 따라 다를 수 있음]

---

## Project Constraints (from CLAUDE.md)

- **main_gui.py 초기화 순서**: `event_upload_clicked()` 내에서 `self.curr_mac`, `self.dev_profile` 참조 시 `__init__` 호출 순서 확인 필요. `self.curr_mac`은 line 527, `self.dev_profile`은 dict 초기화 후 사용 — 이미 Phase 6 분기 패턴과 동일한 패턴 사용.
- **파일 줄수 확인**: 편집 전 `wc -l main_gui.py` 로 현재 줄수 확인.
- **커밋 메시지**: Co-Authored-By 금지.
- **빌드**: `build.ps1` 사용 (Phase 8 해당).
- **TASKS.md**: 버그/TODO 발견 시 즉시 추가.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tftpy 0.8.7 소스 직접 읽음, pip show 확인
- Architecture: HIGH — 기존 WIZ550MSGHandler/FWUploadThread 패턴 직접 읽음
- Pitfalls: HIGH (포트 엔디안, tftproot 존재) / MEDIUM (0xD2 소켓 포트 — 실장치 미확인)

**Research date:** 2026-05-19
**Valid until:** 2026-06-19 (tftpy 0.8.7 안정 버전, 30일)
