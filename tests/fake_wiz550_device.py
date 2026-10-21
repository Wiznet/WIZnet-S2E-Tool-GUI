#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 WIZ550 장치 — 바이너리 설정 프로토콜(UDP 6550)의 응답기.

시험 전용이다. WIZ550SR / WIZ550S2E / WIZ550WEB 을 실장비 없이 세워 두고 설정툴의
검색·조회·설정·리셋 경로를 돌린다. `dev/fix-wiz550-general-fields` 가 미검증인 채
develop 에 들어가 있고 `BUG-W550-Z`(WEB 라우팅)도 장비가 없어 막혀 있어 만들었다.

프로토콜 (Java 원본 대조로 이식된 WIZ550MSGHandler 기준)

    헤더 7B   STX(0xA5) / valid / unicast / op_code / 방향 / len LSB / len MSB
    방향      요청 0xAA, 응답 0x55
    암호화    valid 최상위 비트가 서면 payload 를 key(=valid & 0x7F)로 XOR
    검색      0xA1  요청 payload 없음 → 응답 12B (product_code[3] + fw_ver[3] + mac[6])
    조회      0xB0  요청 mac[6]      → 응답 mac[6] + Config(162B 또는 133B)
    설정      0xC0  요청 mac[6] + pw_len[1] + pw[16] + Config → 응답 mac[6]
    리셋      0xE0/0xF0  요청 mac[6] + pw_len[1] + pw[16]     → 응답 mac[6]

응답 헤더는 여기서 직접 조립한다. 설정툴의 요청 빌더를 재사용하면 같은 코드로 만들고
같은 코드로 읽는 꼴이라 시험이 아무것도 증명하지 못한다. Config 본체(struct)만
WIZ550Profile 의 빌더를 쓴다 — 그건 자료 형식이라 따로 구현하면 중복이고, 왕복 검증은
tests/test_wiz550_profile.py 가 이미 덮고 있다.

설정툴이 Config 크기를 헤더가 아니라 payload[6:8] 에서 다시 읽는다는 점이 중요하다
(Java 원본의 MSB 버그 우회). 그래서 그 자리에 실제 본체 길이를 넣는다.

단독 실행

    uv run python -m tests.fake_wiz550_device --type WIZ550SR
    uv run python -m tests.fake_wiz550_device --type WIZ550WEB --count 2
"""

from __future__ import annotations

import argparse
import random
import socket
import threading
from dataclasses import dataclass
from typing import Optional

WIZ550_PORT = 6550
STX = 0xA5
WIZNET_REQUEST = 0xAA
WIZNET_REPLY = 0x55

OP_DISCOVERY_ALL = 0xA1
OP_GET_INFO = 0xB0
OP_SET_INFO = 0xC0
OP_FW_UPLOAD = 0xD1
OP_REMOTE_RESET = 0xE0
OP_FACTORY_RESET = 0xF0

PRODUCT_CODES = {
    "WIZ550SR": bytes([0x02, 0x00, 0x00]),
    "WIZ550S2E": bytes([0x00, 0x00, 0x00]),
    "WIZ550WEB": bytes([0x01, 0x02, 0x00]),
}
CONFIG_SIZE = {"WIZ550SR": 162, "WIZ550S2E": 162, "WIZ550WEB": 133}

FAKE_MAC = "00:08:DC:55:00:01"

# 설정툴 화면이 비지 않을 만큼 채운 기본 설정. 값은 WIZ550Profile 의 필드 이름을 따른다.
DEFAULT_CONFIG: dict = {
    "module_name": "WIZ550SR",
    "local_ip": "192.168.7.55",
    "gateway": "192.168.7.1",
    "subnet": "255.255.255.0",
    "working_mode": 0,
    "state": 0,
    "remote_ip": "192.168.7.2",
    "local_port": 5000,
    "remote_port": 5000,
    "inactivity": 0,
    "reconnection": 3000,
    "packing_time": 0,
    "packing_size": 0,
    "packing_delimiter": b"\x00\x00\x00\x00",
    "packing_delimiter_length": 0,
    "packing_data_appendix": 0,
    "baud_rate": 115200,
    "data_bits": 3,
    "parity": 0,
    "stop_bits": 0,
    "flow_control": 0,
    "pw_setting": "",
    "pw_connect": "",
    "dhcp_use": 0,
    "dns_use": 0,
    "dns_server_ip": "8.8.8.8",
    "dns_domain_name": "",
    "serial_command": 0,
    "serial_trigger": b"\x2b\x2b\x2b",
    # WEB 전용 (SR/S2E 에서는 무시된다)
    "uart0_baud_rate": 115200, "uart0_data_bits": 3, "uart0_parity": 0,
    "uart0_stop_bits": 0, "uart0_flow_control": 0,
    "uart1_baud_rate": 115200, "uart1_data_bits": 3, "uart1_parity": 0,
    "uart1_stop_bits": 0, "uart1_flow_control": 0,
}


@dataclass
class Verdict:
    """요청 하나를 어떻게 처리했는지. 정상 트래픽과 진짜 이상을 구분하려고 둔다."""

    kind: str          # answered / other-device / bad-password / malformed / unsupported
    answered: bool
    note: str
    op_code: Optional[int] = None
    target_mac: Optional[str] = None


def mac_to_bytes(mac: str) -> bytes:
    return bytes(int(x, 16) for x in mac.replace("-", ":").split(":"))


def bytes_to_mac(mac6: bytes) -> str:
    return ":".join(f"{b:02X}" for b in mac6)


def parse_request(data: bytes) -> Optional[tuple[int, bytes]]:
    """요청을 (op_code, 복호화된 payload) 로 푼다. 형식이 아니면 None."""
    if len(data) < 7 or data[0] != STX or data[4] != WIZNET_REQUEST:
        return None
    payload_len = data[5] + (data[6] << 8)
    payload = bytearray(data[7:7 + payload_len])
    valid = data[1]
    if valid & 0x80:
        key = valid & 0x7F
        for i in range(len(payload)):
            payload[i] ^= key
    return data[3], bytes(payload)


def build_config_bytes(device_type: str, config: dict, mac: str) -> bytes:
    """Config 본체. 설정툴이 읽는 struct 그대로."""
    from WIZ550Profile import build_s2e, build_sr, build_web

    d = dict(config)
    d["mac"] = mac
    d["module_type"] = PRODUCT_CODES[device_type].hex()
    d.setdefault("packet_size", CONFIG_SIZE[device_type])
    d["packet_size"] = CONFIG_SIZE[device_type]
    if device_type == "WIZ550WEB":
        return build_web(d)
    if device_type == "WIZ550S2E":
        return build_s2e(d)
    return build_sr(d)


class FakeWiz550Device:
    """UDP 6550 응답기. with 문 또는 start()/stop() 으로 쓴다."""

    def __init__(self, device_type: str = "WIZ550SR", *, mac: str = FAKE_MAC,
                 fw_version: tuple = (1, 2, 0), config: Optional[dict] = None,
                 bind: str = "127.0.0.1", port: int = 0, password: str = "",
                 reply_broadcast: bool = False, verbose: int = 0):
        if device_type not in PRODUCT_CODES:
            raise ValueError(f"모르는 기종 {device_type!r}")
        self.device_type = device_type
        self.mac = mac
        self.mac6 = mac_to_bytes(mac)
        self.fw_version = bytes(fw_version[:3])
        self.password = password
        self.bind = bind
        self._port = port
        self.reply_broadcast = reply_broadcast
        self.verbose = int(verbose)

        self._default_config = dict(DEFAULT_CONFIG, **(config or {}))
        self._default_config.setdefault("module_name", device_type)
        self.config = dict(self._default_config)

        self.requests: list[bytes] = []
        self.replies: list[bytes] = []
        self.verdicts: list[Verdict] = []
        self.reboots = 0
        self.factory_resets = 0

        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ── 판정 (상태를 바꾸지 않는다) ────────────────────────────────────

    def classify(self, data: bytes) -> Verdict:
        parsed = parse_request(data)
        if parsed is None:
            return Verdict("malformed", False,
                           f"WIZ550 요청 형식이 아님 {bytes(data[:8])!r}")
        op, payload = parsed
        if op == OP_DISCOVERY_ALL:
            return Verdict("answered", True, "검색(DISCOVERY_ALL)", op_code=op)
        if op not in (OP_GET_INFO, OP_SET_INFO, OP_REMOTE_RESET,
                      OP_FACTORY_RESET, OP_FW_UPLOAD):
            return Verdict("unsupported", False, f"모르는 op_code {op:#04x}", op_code=op)
        if len(payload) < 6:
            return Verdict("malformed", False, f"payload 가 MAC 도 못 담음 {len(payload)}B",
                           op_code=op)
        target = bytes_to_mac(payload[:6])
        if payload[:6] != self.mac6:
            return Verdict("other-device", False,
                           f"{target} 앞으로 온 브로드캐스트 — 내 것이 아니라 넘김",
                           op_code=op, target_mac=target)
        if op in (OP_SET_INFO, OP_REMOTE_RESET, OP_FACTORY_RESET, OP_FW_UPLOAD):
            if not self._password_ok(payload):
                return Verdict("bad-password", False, "설정 비밀번호 불일치",
                               op_code=op, target_mac=target)
        return Verdict("answered", True, f"op {op:#04x}", op_code=op, target_mac=target)

    def _password_ok(self, payload: bytes) -> bool:
        """payload: mac[6] + pw_len[1] + pw[16] + ... 장치에 비밀번호가 없으면 무조건 통과."""
        if not self.password:
            return True
        if len(payload) < 6 + 1 + 16:
            return False
        pw_len = payload[6]
        given = payload[7:7 + 16][:pw_len].decode("ascii", errors="replace")
        return given == self.password

    # ── 응답 생성 ──────────────────────────────────────────────────────

    def build_reply(self, data: bytes) -> Optional[bytes]:
        verdict = self.classify(data)
        if not verdict.answered:
            return None
        op, payload = parse_request(data)   # type: ignore[misc]

        if op == OP_DISCOVERY_ALL:
            body = PRODUCT_CODES[self.device_type] + self.fw_version + self.mac6
        elif op == OP_GET_INFO:
            body = self.mac6 + build_config_bytes(self.device_type, self.config, self.mac)
        elif op == OP_SET_INFO:
            self._apply_config(payload[6 + 1 + 16:])
            body = self.mac6
        elif op in (OP_REMOTE_RESET, OP_FACTORY_RESET):
            self.reboots += 1
            if op == OP_FACTORY_RESET:
                self.factory_resets += 1
                self.config = dict(self._default_config)
            body = self.mac6
        else:                                # OP_FW_UPLOAD
            body = self.mac6
        return self._frame(op, body)

    def _apply_config(self, raw: bytes) -> None:
        """SET_INFO 로 받은 Config 본체를 반영한다. 파싱은 설정툴과 같은 코드로 한다."""
        from WIZ550Profile import parse_s2e, parse_sr, parse_web

        size = CONFIG_SIZE[self.device_type]
        if len(raw) < size:
            self._log(1, f"SET_INFO Config 부족: {len(raw)}B < {size}B — 무시")
            return
        parser = {"WIZ550WEB": parse_web, "WIZ550S2E": parse_s2e}.get(self.device_type, parse_sr)
        parsed = parser(raw[:size])
        if parsed:
            parsed.pop("mac", None)          # MAC 은 장치 고유값이라 바꾸지 않는다
            self.config.update(parsed)

    def _frame(self, op_code: int, body: bytes) -> bytes:
        """7B 헤더 + XOR 암호화 payload. 실장치처럼 매번 새 키를 쓴다."""
        valid = 0x80 + random.randint(0, 0x7E)
        key = valid & 0x7F
        buf = bytearray(7 + len(body))
        buf[0] = STX
        buf[1] = valid
        buf[2] = 0x00
        buf[3] = op_code
        buf[4] = WIZNET_REPLY
        buf[5] = len(body) & 0xFF
        buf[6] = (len(body) >> 8) & 0xFF
        for i, b in enumerate(body):
            buf[7 + i] = b ^ key
        return bytes(buf)

    # ── 서버 ──────────────────────────────────────────────────────────

    @property
    def port(self) -> int:
        if self._sock is None:
            return self._port
        return self._sock.getsockname()[1]

    def start(self) -> "FakeWiz550Device":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind((self.bind, self._port))
        self._sock.settimeout(0.05)
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name=f"fake-550-{self.mac}",
                                        daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "FakeWiz550Device":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle(data, addr)

    def _handle(self, data: bytes, addr) -> None:
        idx = len(self.requests)
        self.requests.append(data)
        verdict = self.classify(data)
        self.verdicts.append(verdict)
        if not verdict.answered:
            level = 2 if verdict.kind == "other-device" else 1
            self._log(level, f"#{idx} req {len(data)}B  → {verdict.note}")
            return
        reply = self.build_reply(data)
        if reply is None:
            return
        self.replies.append(reply)
        target = ("255.255.255.255", addr[1]) if self.reply_broadcast else addr
        self._log(1, f"#{idx} req {len(data)}B ({verdict.note})  → reply {len(reply)}B "
                     f"to {target[0]}:{target[1]}")
        try:
            assert self._sock is not None
            self._sock.sendto(reply, target)
        except OSError as e:
            self._log(1, f"#{idx} sendto 실패: {e}")

    def _log(self, level: int, msg: str) -> None:
        if self.verbose >= level:
            print(f"[fake-550 {self.device_type} {self.mac}] {msg}", flush=True)

    def summary(self) -> str:
        kinds: dict[str, int] = {}
        for v in self.verdicts:
            kinds[v.kind] = kinds.get(v.kind, 0) + 1
        parts = [f"요청 {len(self.requests)}", f"응답 {len(self.replies)}"]
        for k, label in (("other-device", "남의 것"), ("bad-password", "비밀번호 불일치"),
                         ("malformed", "형식 오류"), ("unsupported", "미지원 op")):
            if kinds.get(k):
                parts.append(f"{label} {kinds[k]}")
        if self.reboots:
            parts.append(f"리셋 {self.reboots}")
        return " / ".join(parts)


def make_device_fleet(count: int, device_type: str = "WIZ550SR", *,
                      first_mac: str = FAKE_MAC, **kwargs) -> list[FakeWiz550Device]:
    """MAC 이 1씩 증가하는 가짜 WIZ550 여러 대.

    SEGCP 쪽과 달리 응답을 보낸 쪽 주소로 유니캐스트하므로 출처 포트를 나눌 필요가 없다 —
    설정툴이 MAC 으로 구분한다.
    """
    base = int(first_mac.replace(":", ""), 16)
    fleet = []
    for i in range(count):
        raw = f"{base + i:012X}"
        mac = ":".join(raw[j:j + 2] for j in range(0, 12, 2))
        fleet.append(FakeWiz550Device(device_type, mac=mac, **kwargs))
    return fleet


def _main() -> None:
    ap = argparse.ArgumentParser(description="가짜 WIZ550 장치 (UDP 6550)")
    ap.add_argument("--type", default="WIZ550SR", choices=sorted(PRODUCT_CODES))
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=WIZ550_PORT)
    ap.add_argument("--mac", default=FAKE_MAC)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--fw", default="1.2.0", help="펌웨어 버전 (예: 1.2.0). 100 이상이면 부트로더")
    ap.add_argument("--password", default="", help="설정 비밀번호. 비우면 검사하지 않는다")
    ap.add_argument("-v", "--verbose", action="count", default=1)
    args = ap.parse_args()

    fw = tuple(int(x) for x in args.fw.split("."))
    fleet = make_device_fleet(args.count, args.type, first_mac=args.mac,
                              bind=args.bind, port=args.port, fw_version=fw,
                              password=args.password, verbose=args.verbose)
    for dev in fleet:
        dev.start()
    print(f"[fake-550] listening {args.bind}:{fleet[0].port}  type={args.type}  "
          f"mac={', '.join(d.mac for d in fleet)}  fw={args.fw}  (Ctrl+C 로 종료)", flush=True)
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for dev in fleet:
            dev.stop()
            print(f"[fake-550 {dev.mac}] {dev.summary()}", flush=True)


if __name__ == "__main__":
    _main()
