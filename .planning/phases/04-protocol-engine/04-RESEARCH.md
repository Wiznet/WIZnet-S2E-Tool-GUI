# Phase 4: Protocol Engine - Research

**Researched:** 2026-05-18
**Domain:** WIZ550 UDP 프로토콜 + 바이너리 Config 구조체 (Python/PyQt5)
**Confidence:** HIGH

---

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01**: `WIZ550MSGHandler.py`에 4개의 QThread 클래스 구현
  - `WIZ550Searcher` — DISCOVERY_ALL(0xA1) 브로드캐스트, `search_done = pyqtSignal(list)` 발신
  - `WIZ550Getter` — GET_INFO(0xB0) 유니캐스트, `get_done = pyqtSignal(dict)` 발신
  - `WIZ550Setter` — SET_INFO(0xC0) 유니캐스트, `set_done = pyqtSignal(bool)` 발신
  - `WIZ550Resetter` — REMOTE_RESET(0xE0)/FACTORY_RESET(0xF0), op_code 파라미터로 구분, `reset_done = pyqtSignal(bool)` 발신
- **D-02**: 단일 파일 `WIZ550Profile.py` — SR/S2E/WEB 모두 구현. `_parse_base_162()` 내부 헬퍼로 공유.
- **D-03**: DISCOVERY_ALL(0xA1) 브로드캐스트 후 `product_code[0~2]`로 장치 타입 필터링
- **D-04**: WIZ550S2E 이중 판별 — 데이터 길이 우선 + fw_ver[1] 홀짝 검증
- **D-05**: UDP 포트 6550, SO_BROADCAST 활성화, 수신 버퍼 1MB, 타임아웃 15초
- **D-06**: XOR 키 = `0x80 + random.randint(0, 0x7E)` 매 패킷, 복호화 키 = `valid & 0x7F`
- **D-07**: encrypt: offset 7부터 XOR (헤더 7B 스킵). decrypt: parse 후 offset 0부터 XOR.
- **D-08**: Getter 응답 길이 파싱: recv[6~7] 재파싱 (원본 Java MSB 버그 우회)

### Claude's Discretion

없음 — 모든 핵심 구현 결정이 CONTEXT.md에서 확정됨.

### Deferred Ideas (OUT OF SCOPE)

- WIZ550 FW 업로드 (TFTP) — Phase 7
- WIZ550 DeviceSpec YAML — Phase 5
- main_gui.py 통합 — Phase 6

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROTO-01 | UDP 포트 6550 송수신 소켓 (SO_BROADCAST, 수신 버퍼 1MB, 타임아웃 15초) | 소켓 설정 패턴 — WIZ1x0MSGHandler 코드 직접 확인 |
| PROTO-02 | 7바이트 고정 헤더 파싱/생성 | 바이트 레이아웃 완전 문서화 (Java 원본 분석) |
| PROTO-03 | XOR 암호화/복호화 | Python bytes 구현 패턴 도출 완료 |
| PROTO-04 | op_code 핸들링 (0xA1/B0/C0/D1/E0/F0) | 각 op_code 바이트 레이아웃 완전 문서화 |
| PROTO-05 | Discovery 응답 장치 타입 판별 | product_code[0~2] 값 테이블 확정 |
| PROTO-06 | QThread 기반 비동기 수신 + pyqtSignal 발신 | WIZ1x0MSGHandler 패턴 직접 재사용 |
| PROF-01 | WIZ550SR 162B 구조체 파싱/빌드 | struct 포맷 문자열 검증 완료 (162B 확인) |
| PROF-02 | WIZ550S2E 가변 구조체 (162B + 확장) | 분기 로직 및 포맷 도출 완료 |
| PROF-03 | WIZ550WEB 133B 구조체 파싱/빌드 | struct 포맷 문자열 검증 완료 (133B 확인) |

</phase_requirements>

---

## Summary

Phase 4는 WIZ550 계열 장치용 UDP 핸들러(`WIZ550MSGHandler.py`)와 Config 구조체 파서(`WIZ550Profile.py`)를 신규 구현하는 단계다. 기존 `WIZ1x0MSGHandler.py`와 `WIZ1x0Profile.py`가 직접 재사용 가능한 패턴을 제공하므로, 이 Phase의 핵심 작업은 패턴 이식 + WIZ550 전용 프로토콜 세부사항 적용이다.

원본 Java 소스(WIZnet_Configuration_Tool)를 완전 분석한 결과, 프로토콜의 모든 바이트 레이아웃과 XOR 암호화 알고리즘이 확정되었다. 특히 `parse_header()`의 MSB 버그(Java 연산자 우선순위 오류로 length 상위 바이트가 항상 0이 됨)와 이를 우회하는 `recv[6~7]` 재파싱 방식이 핵심 구현 포인트다. struct 포맷 문자열은 Python으로 직접 검증하여 SR=162B, WEB=133B임을 확인했다.

Wave 분할 전략: Wave 1에서 `WIZ550MSGHandler.py`(4개 QThread) → Wave 2에서 `WIZ550Profile.py`(3종 구조체) 순서가 적합하다. Profile이 Handler에 의존하지 않고 독립적이므로 병렬 작업도 가능하지만, Handler 먼저 구현하면 Getter 시그널 타입(`pyqtSignal(dict)`)이 확정되어 Profile의 `parse_sr()/parse_s2e()/parse_web()` 반환 타입과 정합성을 맞추기 쉽다.

**Primary recommendation:** WIZ1x0MSGHandler.py의 `select.select` 루프 패턴을 그대로 이식하고, WIZ550 전용 헤더 빌드/파싱 로직만 추가한다.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt5.QtCore.QThread | 기존 설치 | 비동기 UDP 수신 | 기존 WIZ1x0MSGHandler와 동일 패턴 |
| PyQt5.QtCore.pyqtSignal | 기존 설치 | 결과 시그널 발신 | PyQt5 표준 스레드 간 통신 |
| socket (stdlib) | stdlib | UDP 소켓 | WIZ1x0MSGHandler와 동일 |
| select (stdlib) | stdlib | 논블로킹 수신 대기 | WIZ1x0MSGHandler와 동일 |
| struct (stdlib) | stdlib | 바이너리 구조체 pack/unpack | WIZ1x0Profile과 동일 |
| random (stdlib) | stdlib | XOR 키 생성 | D-06 결정 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ipaddress (stdlib) | stdlib | IP 문자열 ↔ bytes 변환 | WIZ1x0Profile에서 이미 사용 |
| time (stdlib) | stdlib | 수신 deadline 계산 | WIZ1x0Searcher 루프 패턴 |

**Installation:** 모든 의존성이 stdlib 또는 기존 PyQt5 설치에 포함. 추가 패키지 설치 불필요.

---

## Architecture Patterns

### Recommended Project Structure

```
WIZ550MSGHandler.py       # 4개 QThread 클래스
WIZ550Profile.py          # 구조체 파서/빌더 (public + 내부 헬퍼)
```

파일 2개, 루트 디렉토리. 기존 `WIZ1x0MSGHandler.py`, `WIZ1x0Profile.py`와 동일 위치.

---

### Pattern 1: WIZ550MSGHandler QThread 구조

**WIZ1x0MSGHandler.py에서 직접 이식 가능한 패턴.**

```python
# Source: WIZ1x0MSGHandler.py (프로젝트 내 검증된 패턴)
class WIZ550Searcher(QThread):
    search_done = pyqtSignal(list)  # [(mac_str, device_dict), ...]

    def __init__(self, iface_ip: str = "", timeout: float = 15.0):
        super().__init__()
        self.iface_ip = iface_ip
        self.timeout = timeout

    def run(self):
        results = {}  # mac_str → device_dict (MAC 기반 중복 제거)
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            bind_ip = self.iface_ip if self.iface_ip else ''
            sock.bind((bind_ip, 0))  # 임시 포트 (응답은 소스 IP:포트로 돌아옴)

            pkt = _build_discovery_all()
            sock.sendto(pkt, ('255.255.255.255', WIZ550_PORT))

            deadline = time.time() + self.timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                ready, _, _ = select.select([sock], [], [], remaining)
                if not ready:
                    break
                data, addr = sock.recvfrom(512)
                info = _parse_discovery_reply(data)
                if info is None:
                    continue
                mac = info['mac']
                if mac not in results:
                    results[mac] = info
        except Exception as e:
            logger.error(f"[WIZ550] Searcher 오류: {e}")
        finally:
            if sock:
                try: sock.close()
                except OSError: pass

        self.search_done.emit(list(results.values()))
```

**WIZ550Getter — GET_INFO 유니캐스트:**

```python
class WIZ550Getter(QThread):
    get_done = pyqtSignal(dict)  # 파싱된 Config dict (parse_sr/s2e/web 반환값)

    def __init__(self, target_ip: str, target_mac: str,
                 device_type: str, iface_ip: str = "", timeout: float = 5.0):
        super().__init__()
        self.target_ip = target_ip
        self.target_mac = target_mac  # "AA:BB:CC:DD:EE:FF"
        self.device_type = device_type  # "WIZ550SR" / "WIZ550S2E" / "WIZ550WEB"
        self.iface_ip = iface_ip
        self.timeout = timeout

    def run(self):
        result = {}
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            bind_ip = self.iface_ip if self.iface_ip else ''
            sock.bind((bind_ip, 0))

            pkt = _build_get_info(self.target_mac)
            sock.sendto(pkt, ('255.255.255.255', WIZ550_PORT))  # Java 원본도 255.255.255.255 사용

            ready, _, _ = select.select([sock], [], [], self.timeout)
            if ready:
                data, _ = sock.recvfrom(1024)
                result = _parse_get_info_reply(data, self.device_type)
        except Exception as e:
            logger.error(f"[WIZ550] Getter 오류: {e}")
        finally:
            if sock:
                try: sock.close()
                except OSError: pass
        self.get_done.emit(result)
```

**WIZ550Setter / WIZ550Resetter — 동일 패턴, set_done/reset_done = pyqtSignal(bool)**

---

### Pattern 2: 헤더 빌드/파싱 (모듈 수준 헬퍼)

```python
# Source: 원본 Java WIZnet_Header.java 완전 분석 결과
import random, struct

WIZ550_PORT = 6550
STX = 0xA5
WIZNET_REQUEST = 0xAA
WIZNET_REPLY   = 0x55

# op_code 상수
OP_DISCOVERY_ALL = 0xA1
OP_GET_INFO      = 0xB0
OP_SET_INFO      = 0xC0
OP_FW_UPLOAD     = 0xD1
OP_REMOTE_RESET  = 0xE0
OP_FACTORY_RESET = 0xF0


def _make_valid_and_key() -> tuple[int, int]:
    """valid 바이트와 XOR 키 생성 (D-06)"""
    valid = 0x80 + random.randint(0, 0x7E)  # 0x80~0xFE
    key = valid & 0x7F
    return valid, key


def _build_header(op_code: int, unicast: bool, payload_len: int) -> bytearray:
    """7바이트 헤더 생성 (payload 미포함)"""
    valid, _ = _make_valid_and_key()
    buf = bytearray(7)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x01 if unicast else 0x00
    buf[3] = op_code
    buf[4] = WIZNET_REQUEST
    buf[5] = payload_len & 0xFF          # length LSB
    buf[6] = (payload_len >> 8) & 0xFF   # length MSB
    return buf


def _encrypt(buf: bytearray, key: int) -> None:
    """encrypt: offset 7부터 XOR (D-07). buf를 in-place 수정."""
    for i in range(7, len(buf)):
        buf[i] ^= key


def _decrypt(payload: bytes, key: int, length: int) -> bytes:
    """decrypt: offset 0부터 length바이트 XOR (D-07). parse_header shift 이후 호출."""
    return bytes(b ^ key for b in payload[:length])


def _build_discovery_all() -> bytes:
    """DISCOVERY_ALL 패킷 7바이트 (payload 없음)"""
    valid, _ = _make_valid_and_key()
    buf = bytearray(7)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x00  # 브로드캐스트
    buf[3] = OP_DISCOVERY_ALL
    buf[4] = WIZNET_REQUEST
    buf[5] = 0x00
    buf[6] = 0x00
    # payload 없으므로 암호화 불필요
    return bytes(buf)
```

---

### Pattern 3: Discovery 응답 파싱 + 장치 타입 판별

```python
# Source: Java ReceiveThread.java + GUI.java treeUpdate() 분석
PRODUCT_CODE_SR  = bytes([0x02, 0x00, 0x00])
PRODUCT_CODE_S2E = bytes([0x00, 0x00, 0x00])
PRODUCT_CODE_WEB = bytes([0x01, 0x02, 0x00])

def _parse_discovery_reply(data: bytes) -> dict | None:
    """
    Discovery 응답 파싱.
    수신 패킷 형식: 7B 헤더 + 12B payload (product_code[3] + fw_version[3] + mac[6])
    parse_header 후 recv[0~11]이 payload가 됨.
    """
    if len(data) < 7 + 12:
        return None
    # 헤더 검증
    if data[0] != STX:
        return None
    if data[4] != WIZNET_REPLY:
        return None

    valid = data[1]
    # payload shift (Java arraycopy 동작 재현)
    payload = data[7:7 + 12]

    # 복호화
    if valid & 0x80:
        key = valid & 0x7F
        payload = _decrypt(payload, key, 12)

    product_code = payload[0:3]
    fw_version   = payload[3:6]
    mac_bytes    = payload[6:12]

    if product_code == PRODUCT_CODE_SR:
        device_type = 'WIZ550SR'
    elif product_code == PRODUCT_CODE_S2E:
        device_type = 'WIZ550S2E'
    elif product_code == PRODUCT_CODE_WEB:
        device_type = 'WIZ550WEB'
    else:
        return None  # 무시 (D-03)

    mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
    fw_str  = f'{fw_version[0]}.{fw_version[1]}.{fw_version[2]}'

    return {
        'device_type':   device_type,
        'product_code':  product_code,
        'fw_version':    fw_version,
        'fw_str':        fw_str,
        'mac':           mac_str,
        'mac_bytes':     mac_bytes,
        '_proto':        'wiz550',
    }
```

---

### Pattern 4: GET_INFO 응답 파싱 (D-08 MSB 버그 우회)

```python
# Source: Java ReceiveThread.java §5.4 분석
def _parse_get_info_reply(data: bytes, device_type: str) -> dict:
    """
    GET_INFO(0xB0) 응답 파싱.

    응답 payload 구조 (parse_header shift 후):
      recv[0~5]  = src_mac_address[6]
      recv[6]    = length LSB  (Config 바이트 배열 크기 — system_info 포함)
      recv[7]    = length MSB
      recv[6~]   = system_info (packet_size[2] + module_type[3] + ... = Config 전체)

    D-08: recv[6~7]에서 직접 length 재파싱 (Java parse_header의 MSB 버그 우회)
    """
    if len(data) < 7 + 8:  # 헤더 7B + MAC 6B + length 2B 최소
        return {}

    valid = data[1]
    total_payload_len = (data[5] & 0xFF) + ((data[6] & 0xFF) << 8)  # 헤더 내 length

    # payload shift
    payload = bytearray(data[7:])

    # 복호화
    if valid & 0x80:
        key = valid & 0x7F
        for i in range(min(len(payload), total_payload_len)):
            payload[i] ^= key

    # recv[6~7]에서 Config 크기 재파싱 (D-08)
    config_len = (payload[6] & 0xFF) + ((payload[7] & 0xFF) << 8)
    src_mac = ':'.join(f'{b:02X}' for b in payload[0:6])

    # system_info: payload[6]부터 config_len 바이트
    system_info = bytes(payload[6:6 + config_len])

    if not system_info:
        return {}

    # system_info[2~4] = module_type → 장치 확정
    from WIZ550Profile import parse_sr, parse_s2e, parse_web
    if device_type == 'WIZ550SR':
        return parse_sr(system_info)
    elif device_type == 'WIZ550S2E':
        return parse_s2e(system_info)
    elif device_type == 'WIZ550WEB':
        return parse_web(system_info)
    return {}
```

---

### Pattern 5: WIZ550Profile struct 포맷 문자열 (검증 완료)

```python
# Source: WIZ550SR_Config.java + WIZ550S2E_Config.java + WIZ550WEB_Config.java 분석
# [VERIFIED: uv run python -c "import struct; print(struct.calcsize(fmt))"]

import struct

# ─────────────────────────────────────────────
# WIZ550SR 162B (모듈 타입 [0x02, 0x00, 0x00])
# ─────────────────────────────────────────────
SR_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'B'    # working_mode [51]
    'B'    # state [52]
    '4s'   # remote_ip[4] [53~56]
    'H'    # local_port LE [57~58]
    'H'    # remote_port LE [59~60]
    'H'    # inactivity LE [61~62]
    'H'    # reconnection LE [63~64]
    'H'    # packing_time LE [65~66]
    'B'    # packing_size [67]
    '4s'   # packing_delimiter[4] [68~71]
    'B'    # packing_delimiter_length [72]
    'B'    # packing_data_appendix [73]
    'I'    # baud_rate 4B LE [74~77]
    'B'    # data_bits [78]
    'B'    # parity [79]
    'B'    # stop_bits [80]
    'B'    # flow_control [81]
    '10s'  # pw_setting[10] [82~91]
    '10s'  # pw_connect[10] [92~101]
    'B'    # dhcp_use [102]
    'B'    # dns_use [103]
    '4s'   # dns_server_ip[4] [104~107]
    '50s'  # dns_domain_name[50] [108~157]
    'B'    # serial_command [158]
    '3s'   # serial_trigger[3] [159~161]
)
SR_SIZE = 162
assert struct.calcsize(SR_FORMAT) == SR_SIZE  # 검증 완료 [VERIFIED]

# ─────────────────────────────────────────────
# WIZ550WEB 133B (모듈 타입 [0x01, 0x02, 0x00])
# ─────────────────────────────────────────────
WEB_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'I'    # uart0_baud_rate 4B LE [51~54]
    'B'    # uart0_data_bits [55]
    'B'    # uart0_parity [56]
    'B'    # uart0_stop_bits [57]
    'B'    # uart0_flow_control [58]
    'I'    # uart1_baud_rate 4B LE [59~62]
    'B'    # uart1_data_bits [63]
    'B'    # uart1_parity [64]
    'B'    # uart1_stop_bits [65]
    'B'    # uart1_flow_control [66]
    '10s'  # pw_setting[10] [67~76]
    'B'    # dhcp_use [77]
    'B'    # dns_use [78]
    '4s'   # dns_server_ip[4] [79~82]
    '50s'  # dns_domain_name[50] [83~132]
)
WEB_SIZE = 133
assert struct.calcsize(WEB_FORMAT) == WEB_SIZE  # 검증 완료 [VERIFIED]

# ─────────────────────────────────────────────
# WIZ550S2E 기본 162B (모듈 타입 [0x00, 0x00, 0x00])
# 확장: fw_ver[1] 홀수 → +70B MQTT, 짝수 → +2B Modbus
# ─────────────────────────────────────────────
S2E_BASE_FORMAT = SR_FORMAT  # 동일 구조 (module_type만 다름)
S2E_BASE_SIZE = 162

MQTT_FORMAT = '<10s10s25s25s'  # mqtt_user/pw/pub_topic/sub_topic
MQTT_SIZE = 70
assert struct.calcsize(MQTT_FORMAT) == MQTT_SIZE  # 검증 필요

MODBUS_FORMAT = '<BB'  # modbus_use, modbus_mode
MODBUS_SIZE = 2
```

---

### Pattern 6: parse_sr() / _parse_base_162() 헬퍼 패턴

```python
# Source: WIZ1x0Profile.py parse_imin() 패턴 기반 (D-02)

def _parse_base_162(data: bytes) -> dict:
    """
    SR/S2E 공유 162B 기본 구조 파싱 내부 헬퍼.
    data는 system_info (packet_size[2] 포함, 총 162B).
    """
    if len(data) < SR_SIZE:
        return {}
    fields = struct.unpack(SR_FORMAT, data[:SR_SIZE])
    (packet_size, module_type, module_name, fw_ver,
     mac, local_ip, gateway, subnet,
     working_mode, state, remote_ip,
     local_port, remote_port, inactivity, reconnection,
     packing_time, packing_size, packing_delimiter,
     packing_delimiter_length, packing_data_appendix,
     baud_rate,
     data_bits, parity, stop_bits, flow_control,
     pw_setting, pw_connect,
     dhcp_use, dns_use, dns_server_ip, dns_domain_name,
     serial_command, serial_trigger) = fields

    return {
        'packet_size':   packet_size,
        'module_type':   module_type.hex(),
        'module_name':   module_name.rstrip(b'\x00').decode('ascii', errors='replace'),
        'fw_ver':        fw_ver,
        'fw_str':        f'{fw_ver[0]}.{fw_ver[1]}.{fw_ver[2]}',
        'mac':           ':'.join(f'{b:02X}' for b in mac),
        'local_ip':      '.'.join(str(b) for b in local_ip),
        'gateway':       '.'.join(str(b) for b in gateway),
        'subnet':        '.'.join(str(b) for b in subnet),
        'working_mode':  working_mode,
        'state':         state,
        'remote_ip':     '.'.join(str(b) for b in remote_ip),
        'local_port':    local_port,
        'remote_port':   remote_port,
        'inactivity':    inactivity,
        'reconnection':  reconnection,
        'packing_time':  packing_time,
        'packing_size':  packing_size,
        'packing_delimiter': packing_delimiter,
        'packing_delimiter_length': packing_delimiter_length,
        'packing_data_appendix':    packing_data_appendix,
        'baud_rate':     baud_rate,
        'data_bits':     data_bits,
        'parity':        parity,
        'stop_bits':     stop_bits,
        'flow_control':  flow_control,
        'pw_setting':    pw_setting.rstrip(b'\x00').decode('ascii', errors='replace'),
        'pw_connect':    pw_connect.rstrip(b'\x00').decode('ascii', errors='replace'),
        'dhcp_use':      dhcp_use,
        'dns_use':       dns_use,
        'dns_server_ip': '.'.join(str(b) for b in dns_server_ip),
        'dns_domain_name': dns_domain_name.rstrip(b'\x00').decode('ascii', errors='replace'),
        'serial_command': serial_command,
        'serial_trigger': serial_trigger,
        '_proto':        'wiz550',
    }


def parse_sr(data: bytes) -> dict:
    """WIZ550SR 162B → dict"""
    d = _parse_base_162(data)
    d['device_type'] = 'WIZ550SR'
    return d


def parse_s2e(data: bytes) -> dict:
    """WIZ550S2E 가변 구조 → dict (D-04 이중 판별)"""
    d = _parse_base_162(data)
    d['device_type'] = 'WIZ550S2E'
    fw_ver = d.get('fw_ver', b'\x00\x00\x00')

    # D-04: 데이터 길이 우선 → fw_ver[1] 홀짝 검증
    if len(data) >= S2E_BASE_SIZE + MQTT_SIZE and (fw_ver[1] % 2 != 0):
        ext = data[S2E_BASE_SIZE:S2E_BASE_SIZE + MQTT_SIZE]
        mqtt_user, mqtt_pw, mqtt_pub, mqtt_sub = struct.unpack(MQTT_FORMAT, ext)
        d['mqtt_user']      = mqtt_user.rstrip(b'\x00').decode('ascii', errors='replace')
        d['mqtt_pw']        = mqtt_pw.rstrip(b'\x00').decode('ascii', errors='replace')
        d['mqtt_pub_topic'] = mqtt_pub.rstrip(b'\x00').decode('ascii', errors='replace')
        d['mqtt_sub_topic'] = mqtt_sub.rstrip(b'\x00').decode('ascii', errors='replace')
        d['s2e_variant']    = 'mqtt'
    elif len(data) >= S2E_BASE_SIZE + MODBUS_SIZE and (fw_ver[1] % 2 == 0):
        ext = data[S2E_BASE_SIZE:S2E_BASE_SIZE + MODBUS_SIZE]
        modbus_use, modbus_mode = struct.unpack(MODBUS_FORMAT, ext)
        d['modbus_use']  = modbus_use
        d['modbus_mode'] = modbus_mode
        d['s2e_variant'] = 'modbus'
    else:
        d['s2e_variant'] = 'base'

    return d
```

---

### Pattern 7: 왕복(Round-Trip) 검증 패턴

```python
# Source: WIZ1x0Profile.py build_sett()의 assert len(raw) == SIZE 패턴 확장

def _verify_round_trip_sr(original_bytes: bytes) -> bool:
    """parse → build → compare. 파싱 손실 없음 검증."""
    parsed = parse_sr(original_bytes)
    rebuilt = build_sr(parsed)
    return rebuilt == original_bytes[:SR_SIZE]
```

---

### Anti-Patterns to Avoid

- **XOR 키를 헤더에서 재사용하지 않기:** 매 패킷 `_make_valid_and_key()`로 새 키 생성 필수.
- **length 파싱을 parse_header에만 의존하지 않기:** Java 원본의 MSB 버그 때문에 GET_INFO 응답은 `recv[6~7]`에서 직접 재파싱.
- **Discovery 응답을 product_code 없이 받지 않기:** 응답이 12B 미만이면 `None` 반환.
- **struct.pack에 Python int를 그냥 넣지 않기:** `baud_rate`는 `'I'` (unsigned int), `local_port/remote_port`는 `'H'` (unsigned short). 범위 초과 시 `struct.error`.
- **WIZ550S2E 분기를 fw_ver[1]만으로 판별하지 않기:** 데이터 길이가 주방어선 (D-04).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 바이너리 구조체 직렬화 | 수동 바이트 조립 | `struct.pack/unpack` | 오프셋 계산 오류, 엔디안 실수 |
| 논블로킹 소켓 대기 | `time.sleep()` 루프 | `select.select()` | CPU 낭비, 타임아웃 정밀도 불량 |
| 스레드 간 결과 전달 | 공유 변수/Queue | `pyqtSignal` | Qt 스레드 안전성 보장 |
| XOR 암호화 | 별도 암호화 라이브러리 | 내장 bytes/bytearray | 단순 XOR — 외부 의존 불필요 |

**Key insight:** 구조체 포맷 문자열의 `assert struct.calcsize() == SIZE` 단언은 구조체 크기 오류를 import 시점에 즉시 탐지한다. WIZ1x0Profile.py 패턴을 그대로 따른다.

---

## Common Pitfalls

### Pitfall 1: Java parse_header MSB 버그 미처리

**What goes wrong:** Java의 `(0x00FF & buffer[index++]<<8)` 는 연산자 우선순위 오류로 length MSB가 항상 0이 됨. Python에서 그대로 재현하면 config 162B가 `length=162`로 파싱되어 별 문제가 없지만, 232B(MQTT)가 `length=232`로 올바르게 파싱될 보장이 없음.

**Why it happens:** Java에서 `buffer[index]`가 int로 승격 후 `<<8` 적용, 그 후 `0x00FF` 마스킹 → 결과 항상 0.

**How to avoid:** D-08 결정대로 GET_INFO 응답에서 header.length를 신뢰하지 않고 recv[6~7]에서 직접 재파싱:

```python
config_len = (payload[6] & 0xFF) + ((payload[7] & 0xFF) << 8)
```

**Warning signs:** GET_INFO 응답 파싱 후 dict가 비어있거나, S2E MQTT 변형이 항상 base로 판별될 때.

---

### Pitfall 2: Windows SO_BROADCAST + SO_RCVBUF 순서

**What goes wrong:** Windows에서 `SO_BROADCAST` 설정 없이 브로드캐스트 전송 시 `PermissionError: [WinError 10013]`. Java는 DatagramSocket 기본값으로 허용하지만 Python socket은 명시 설정 필요.

**Why it happens:** Windows 소켓 기본 정책 차이.

**How to avoid:**

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # 브로드캐스트 전 필수
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)  # 1MB
```

**Warning signs:** `OSError: [WinError 10013]` 또는 장치 응답이 드롭될 때.

---

### Pitfall 3: struct 'I' vs 'H' 부호 처리

**What goes wrong:** baud_rate(4B)를 `'i'`(signed int)로 선언하면 115200 같은 값은 정상이지만 2000000 이상 값에서 음수 반환. 포트를 `'h'`(signed short)로 선언하면 49152 이상에서 음수.

**Why it happens:** Python struct 소문자 = signed, 대문자 = unsigned.

**How to avoid:** baud_rate = `'I'`, port = `'H'`, 모든 raw 바이트 필드 = `'Ns'`.

**Warning signs:** baud_rate가 음수, 포트가 음수로 파싱될 때.

---

### Pitfall 4: Discovery 응답에서 직접 port 미포함 문제

**What goes wrong:** Discovery 응답(12B)에는 IP 주소가 없음 (product_code + fw_version + mac만). GET_INFO 유니캐스트 전송 시 `target_ip`가 필요한데, Discovery 단계에서는 IP를 알 수 없음.

**Why it happens:** 원본 Java 구현에서 GET_INFO는 `"255.255.255.255"`로 브로드캐스트 전송 후 MAC 매칭으로 응답 구별. IP를 모르는 상태에서도 작동.

**How to avoid:** `WIZ550Getter`에서 `target_ip = '255.255.255.255'` 사용 (Java 원본 동일). `target_mac`로 응답을 구별. `iface_ip` 지정 시 해당 NIC 바인딩.

**Warning signs:** Getter가 특정 서브넷에서만 응답을 받지 못할 때.

---

### Pitfall 5: WIZ550S2E MQTT fw_ver[1] 업데이트 누락

**What goes wrong:** SET_INFO 후 응답에서 Config를 다시 파싱할 때 fw_ver[0]는 Java updateFromPanel에서 업데이트되지 않음 (주석 처리됨). fw_ver[1], fw_ver[2]만 UI에서 갱신.

**Why it happens:** Java 원본의 의도적인 주석 처리: `// packet.fw_ver[0] = ...`

**How to avoid:** `build_s2e()`에서 fw_ver[0]는 읽어온 원본값 유지, fw_ver[1~2]만 UI 값으로 갱신.

---

### Pitfall 6: WEB 구조체에 pw_connect 없음

**What goes wrong:** WIZ550WEB Config 133B에는 `pw_connect` 필드가 없음. SR/S2E dict의 `pw_connect` 키를 WEB에도 그대로 참조하면 KeyError.

**Why it happens:** WEB은 연결 비밀번호 기능 없음 (Java GUI txtConnectionPassword 비활성화).

**How to avoid:** `parse_web()` 반환 dict에 `pw_connect` 키 미포함 또는 `''`로 초기화. Phase 6 UI 통합 시 WEB 장치에서 pw_connect 필드 비활성화.

---

## Code Examples

### SET_INFO 패킷 빌드 패턴

```python
# Source: WIZnet_Header.java set_info() + WIZ1x0Profile.py build_sett() 패턴

def _build_set_info(target_mac: str, password: str, config_data: bytes) -> bytes:
    """
    SET_INFO(0xC0) 패킷 빌드.
    payload: dst_mac[6] + pw_len[1] + pw[16] + config_data
    """
    mac_b = bytes(int(x, 16) for x in target_mac.replace('-', ':').split(':'))
    pw_b  = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
    pw_len = len(password.strip())

    payload = mac_b + bytes([pw_len]) + pw_b + config_data
    payload_len = len(payload)

    valid, key = _make_valid_and_key()
    buf = bytearray(7 + payload_len)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x01  # unicast
    buf[3] = OP_SET_INFO
    buf[4] = WIZNET_REQUEST
    buf[5] = payload_len & 0xFF
    buf[6] = (payload_len >> 8) & 0xFF
    buf[7:] = payload

    _encrypt(buf, key)
    return bytes(buf)
```

### REMOTE_RESET / FACTORY_RESET 패킷 빌드

```python
# Source: WIZnet_Header.java reset() / factory_reset() 분석

def _build_reset(op_code: int, target_mac: str, password: str) -> bytes:
    """
    REMOTE_RESET(0xE0) 또는 FACTORY_RESET(0xF0) 패킷 빌드.
    payload 23B: dst_mac[6] + pw_len[1] + pw[16]
    """
    mac_b  = bytes(int(x, 16) for x in target_mac.replace('-', ':').split(':'))
    pw_b   = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
    pw_len = len(password.strip())

    payload = mac_b + bytes([pw_len]) + pw_b  # 6 + 1 + 16 = 23B
    payload_len = len(payload)  # 23

    valid, key = _make_valid_and_key()
    buf = bytearray(7 + payload_len)
    buf[0] = STX
    buf[1] = valid
    buf[2] = 0x01  # unicast
    buf[3] = op_code
    buf[4] = WIZNET_REQUEST
    buf[5] = payload_len & 0xFF
    buf[6] = (payload_len >> 8) & 0xFF
    buf[7:] = payload

    _encrypt(buf, key)
    return bytes(buf)
```

### SET_INFO 응답 파싱

```python
# Source: Java ReceiveThread.java else if(op_code == SET_INFO) 분석
# 응답 payload: src_mac[6] 만 (6B)

def _parse_set_reply(data: bytes) -> bool:
    """SET_INFO 응답 — 성공 여부만 반환 (응답 수신 = 성공)"""
    if len(data) < 7 + 6:
        return False
    if data[0] != STX or data[4] != WIZNET_REPLY:
        return False
    return True
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| 단일 수신 루프 + 콜백 (Java ReceiveThread) | QThread 클래스 분리 (Searcher/Getter/Setter/Resetter) | PyQt5 시그널 기반, 재사용성 증가 |
| Java DatagramSocket 기본 브로드캐스트 허용 | Python SO_BROADCAST 명시 설정 | Windows 필수 |
| Config length Java MSB 버그 허용 | recv[6~7] 직접 재파싱 | MQTT 232B 정확 판별 |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | WIZ550Getter가 `'255.255.255.255'`로 GET_INFO 전송해도 장치가 올바른 NIC으로 응답 | Pattern 2 | 특정 멀티홈 환경에서 응답 미수신 → iface_ip 바인딩으로 완화 | [ASSUMED] |
| A2 | fw_ver[1] 홀짝 기반 S2E 변형 판별이 모든 현장 펌웨어에서 유효 | Pattern 6 | 신규 펌웨어에서 규칙이 바뀔 경우 오파싱 | [ASSUMED: Java 원본 로직 그대로] |
| A3 | MQTT 구조체 포맷 `'<10s10s25s25s'` = 70B | Pattern 5 | 오파싱 → assert로 즉시 탐지 | [VERIFIED: 10+10+25+25=70, struct.calcsize 직접 확인 필요] |

---

## Open Questions

1. **iface_ip 파라미터 필수 여부**
   - What we know: WIZ1x0Searcher는 iface_ip 없이도 동작하되 멀티홈 환경에서 응답 누락 가능
   - What's unclear: WIZ550 환경에서 단일 NIC 사용이 일반적인지 여부
   - Recommendation: `iface_ip` 선택 파라미터(기본값 `""`)로 구현. Phase 6에서 NIC 선택 UI와 연동.

2. **Getter의 get_done 시그널 타입: `pyqtSignal(dict)` vs `pyqtSignal(bytes)`**
   - What we know: D-01에서 `pyqtSignal(dict)` 결정됨 (CONTEXT.md)
   - What's unclear: dict 반환 시 Phase 6에서 필드명 일치 필요 → Profile과 Handler 구현 순서 협의 필요
   - Recommendation: Profile parse 함수 dict 키를 먼저 정의하고 Handler에서 참조.

3. **복수 WIZ550 장치 응답 순서 보장**
   - What we know: MAC 기반 dict로 중복 제거
   - What's unclear: 동시 다수 응답 시 select.select 루프가 모두 수집하는지
   - Recommendation: deadline 기반 루프(WIZ1x0Searcher 동일 패턴)는 15초 내 모든 응답 수집 가능. 충분.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|---------|
| PyQt5 | QThread, pyqtSignal | ✓ | 기존 설치 | — |
| Python stdlib socket/select/struct/random | 전체 | ✓ | stdlib | — |
| Python (uv run) | 개발/검증 | ✓ | 확인됨 | — |

**Missing dependencies:** 없음. Phase 4는 외부 패키지 추가 불필요.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (기존 사용 여부 미확인) |
| Config file | pytest.ini 또는 없음 (Wave 0 생성) |
| Quick run command | `uv run pytest tests/test_wiz550_profile.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROTO-02 | 7B 헤더 빌드 + 파싱 왕복 | unit | `pytest tests/test_wiz550_handler.py::test_header_roundtrip -x` | ❌ Wave 0 |
| PROTO-03 | XOR encrypt/decrypt 왕복 | unit | `pytest tests/test_wiz550_handler.py::test_xor_roundtrip -x` | ❌ Wave 0 |
| PROTO-05 | Discovery 응답 장치 타입 판별 | unit | `pytest tests/test_wiz550_handler.py::test_discovery_parse -x` | ❌ Wave 0 |
| PROF-01 | SR 162B parse→build→parse 왕복 | unit | `pytest tests/test_wiz550_profile.py::test_sr_roundtrip -x` | ❌ Wave 0 |
| PROF-02 | S2E 가변 구조 판별 (base/modbus/mqtt) | unit | `pytest tests/test_wiz550_profile.py::test_s2e_variant -x` | ❌ Wave 0 |
| PROF-03 | WEB 133B parse→build→parse 왕복 | unit | `pytest tests/test_wiz550_profile.py::test_web_roundtrip -x` | ❌ Wave 0 |
| D-08 | Getter recv[6~7] MSB 버그 우회 | unit | `pytest tests/test_wiz550_handler.py::test_get_info_length_parse -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_wiz550_profile.py tests/test_wiz550_handler.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** 전체 테스트 통과 후 `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_wiz550_profile.py` — PROF-01~03 커버
- [ ] `tests/test_wiz550_handler.py` — PROTO-02, 03, 05, D-08 커버
- [ ] `tests/` 디렉토리 + `conftest.py` (공통 픽스처)
- [ ] pytest 설치 확인: `uv add pytest --dev`

---

## Security Domain

> ASVS 적용: 이 Phase는 네트워크 I/O와 암호화를 포함하므로 부분 적용.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | 아니오 | — |
| V3 Session Management | 아니오 | — |
| V4 Access Control | 아니오 | — |
| V5 Input Validation | 예 | Config bytes 길이 검증 (`len(data) < SIZE` 체크) |
| V6 Cryptography | 부분 | XOR은 암호화 강도 없음 — 원본 프로토콜 호환용, 보안 목적 아님 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 잘못된 길이의 패킷 수신 | Spoofing | `len(data) < 최소크기` 체크 후 None 반환 |
| XOR 키 재사용 | 정보 노출 | 매 패킷 `random.randint` 신규 키 생성 (D-06) |
| Config struct 오버플로우 | Tampering | `struct.unpack` 에러 catch + None 반환 |

> XOR 암호화는 평문 보호 효과가 없음 — 원본 Java 프로토콜 호환 목적만. 보안 요구사항으로 취급하지 않음.

---

## Sources

### Primary (HIGH confidence)

- `~/.claude/docs/WIZnet-S2E-Tool-GUI/research/2026-05-14-wiz550-protocol-analysis.md` — Java 원본 13개 파일 완전 분석: 헤더 구조, XOR 알고리즘, 구조체 바이트맵, ReceiveThread 로직 [VERIFIED]
- `WIZ1x0MSGHandler.py` — QThread Searcher/Setter 패턴, socket+select+try-finally, MAC dict 중복 제거 [VERIFIED]
- `WIZ1x0Profile.py` — STRUCT_FORMAT 정의 방식, assert calcsize(), parse/build 함수 쌍 [VERIFIED]
- `utils.py` — `from utils import logger` 사용법 [VERIFIED]

### Secondary (MEDIUM confidence)

- `uv run python -c "struct.calcsize(SR_FORMAT)"` — SR=162B, WEB=133B 직접 검증 [VERIFIED]

### Tertiary (LOW confidence)

없음.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib만 사용, 기존 프로젝트 패턴과 동일
- Architecture: HIGH — Java 원본 완전 분석 + Python WIZ1x0 패턴 직접 검증
- Pitfalls: HIGH — Java 소스 코드에서 직접 버그 발견 및 우회 방식 확인
- Struct 포맷: HIGH — Python struct.calcsize로 직접 검증

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (프로토콜 사양 고정, 빠르게 변하지 않음)
