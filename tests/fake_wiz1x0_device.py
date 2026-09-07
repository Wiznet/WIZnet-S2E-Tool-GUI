#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 WIZ1x0SR 장치 — FIND/IMIN/SETT/SETC 바이너리 프로토콜 응답기.

시험 전용이다. `dev/feat-wiz1x0-direct-1461` 이 실장비 없이 develop 에 들어가 있어
그 경로를 돌려 보려고 만들었다.

프로토콜 (VB6 원본 대조로 이식된 WIZ1x0MSGHandler / WIZ1x0Profile 기준)

    검색      UDP 브로드캐스트 → 1460 으로 'FIND'(4B)
              장치가 보낸 쪽(:5001)으로 'IMIN' + BoardInfo(159B) = 163B
    직접 검색  TCP 1461 접속 후 같은 'FIND' → 같은 163B 를 스트림으로
    설정      UDP 브로드캐스트 → 1460 으로 'SETT' + BoardInfo(159B)
              장치가 'SETC' 로 답하고 저장·리부트한다

BoardInfo 조립은 WIZ1x0Profile.build_sett() 를 쓴다. 163바이트 struct 를 여기서 다시
짜면 중복이고, 왕복 검증은 기존 시험이 덮는다. 대신 패킷 머리(FIND/IMIN/SETT/SETC)와
소켓 동작은 여기서 직접 다룬다 — 그쪽이 시험 대상이다.

**[미확인]** SETC 응답에 BoardInfo 가 실리는지는 실장비로 확인하지 못했다. 설정툴은
양쪽을 다 받아들이므로(163B 이상이면 파싱, 아니면 보낸 값으로 갱신) 기본은 실어 보내고
`setc_carries_board=False` 로 짧은 형태도 시험할 수 있게 뒀다.

WIZ120SR 필터: 설정툴은 `data[4+103]`(PPPoE_ID 첫 바이트)가 1~9면 WIZ120SR 로 보고
목록에서 뺀다. 기본 BoardInfo 는 그 자리를 0 으로 둬 WIZ1x0SR 로 잡히게 한다.

단독 실행

    uv run python -m tests.fake_wiz1x0_device
    uv run python -m tests.fake_wiz1x0_device --count 3 --ip 192.168.7.60
"""

from __future__ import annotations

import argparse
import socket
import threading
from dataclasses import dataclass
from typing import Optional

SEARCH_PORT = 1460        # 장치 수신 (브로드캐스트)
DIRECT_PORT = 1461        # 직접-IP 검색 TCP
BOARD_INFO_SIZE = 159
PACKET_SIZE = 4 + BOARD_INFO_SIZE      # 163

FAKE_MAC = "00:08:DC:1A:00:01"

# build_sett() 가 필수로 요구하는 키 7개를 포함한 기본 설정.
DEFAULT_BOARD: dict = {
    "mac": FAKE_MAC,
    "op_mode": "Client",
    "ip": "192.168.7.60",
    "subnet": "255.255.255.0",
    "gw": "192.168.7.1",
    "myport": 5000,
    "peerip": "192.168.7.2",
    "peerport": 5000,
    "speed_bps": 115200,
    "databit": 8,
    "parity_str": "None",
    "stopbit": 1,
    "flow_str": "None",
    "D_ch": 0, "D_size": 0, "D_time": 0, "I_time": 0,
    "debug_on": False,
    "appver": b"\x04\x06",
    "ip_alloc": "Static",
    "udp": 0, "connect": 0,
    "dns_flag": 0, "dns_ip": "8.8.8.8", "domain": "",
    "scfg": 0, "scfg_str": "2b2b2b",
    "pppoe_id": "", "pppoe_pass": "",
    "en_tcppass": 0, "tcppass": "",
}


@dataclass
class Verdict:
    kind: str          # answered / malformed / unsupported
    answered: bool
    note: str
    command: Optional[bytes] = None


def build_board_bytes(board: dict) -> bytes:
    """BoardInfo 159B. 설정툴이 읽는 struct 그대로."""
    from WIZ1x0Profile import build_sett
    raw = build_sett(board)[4:]
    assert len(raw) == BOARD_INFO_SIZE, f"BoardInfo 크기 {len(raw)}B"
    return raw


class FakeWiz1x0Device:
    """UDP 1460 + TCP 1461 응답기. with 문 또는 start()/stop() 으로 쓴다."""

    def __init__(self, *, mac: str = FAKE_MAC, board: Optional[dict] = None,
                 bind: str = "127.0.0.1", port: int = 0, direct_port: int = 0,
                 setc_carries_board: bool = True, serve_direct: bool = True,
                 verbose: int = 0):
        self.mac = mac
        self._default_board = dict(DEFAULT_BOARD, **(board or {}))
        self._default_board["mac"] = mac
        self.board = dict(self._default_board)
        self.bind = bind
        self._port = port
        self._direct_port = direct_port
        self.setc_carries_board = setc_carries_board
        self.serve_direct = serve_direct
        self.verbose = int(verbose)

        self.requests: list[bytes] = []
        self.replies: list[bytes] = []
        self.verdicts: list[Verdict] = []
        self.reboots = 0

        self._sock: Optional[socket.socket] = None
        self._tcp: Optional[socket.socket] = None
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()

    # ── 판정 ──────────────────────────────────────────────────────────

    def classify(self, data: bytes) -> Verdict:
        if len(data) < 4:
            return Verdict("malformed", False, f"4바이트도 안 됨 ({len(data)}B)")
        cmd = data[:4]
        if cmd == b"FIND":
            return Verdict("answered", True, "검색(FIND)", command=cmd)
        if cmd == b"SETT":
            if len(data) < PACKET_SIZE:
                return Verdict("malformed", False,
                               f"SETT 인데 {len(data)}B — {PACKET_SIZE}B 여야 한다", command=cmd)
            return Verdict("answered", True, "설정(SETT)", command=cmd)
        return Verdict("unsupported", False, f"모르는 커맨드 {bytes(cmd)!r}", command=cmd)

    # ── 응답 생성 ──────────────────────────────────────────────────────

    def build_reply(self, data: bytes) -> Optional[bytes]:
        verdict = self.classify(data)
        if not verdict.answered:
            return None
        if verdict.command == b"FIND":
            return b"IMIN" + build_board_bytes(self.board)
        # SETT — 저장하고 리부트한다
        self._apply(data[4:4 + BOARD_INFO_SIZE])
        self.reboots += 1
        if self.setc_carries_board:
            return b"SETC" + build_board_bytes(self.board)
        return b"SETC"

    def _apply(self, raw: bytes) -> None:
        """받은 BoardInfo 를 반영한다. 파싱은 설정툴과 같은 코드로 한다."""
        from WIZ1x0Profile import parse_imin
        parsed = parse_imin(b"IMIN" + raw)
        if parsed:
            parsed.pop("mac", None)      # MAC 은 장치 고유값이라 바꾸지 않는다
            self.board.update(parsed)
        else:
            self._log(1, "SETT BoardInfo 파싱 실패 — 무시")

    def factory_reset(self) -> None:
        self.board = dict(self._default_board)

    # ── 서버 ──────────────────────────────────────────────────────────

    @property
    def port(self) -> int:
        return self._sock.getsockname()[1] if self._sock else self._port

    @property
    def direct_port(self) -> int:
        return self._tcp.getsockname()[1] if self._tcp else self._direct_port

    def start(self) -> "FakeWiz1x0Device":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind((self.bind, self._port))
        self._sock.settimeout(0.05)
        self._stop.clear()
        self._threads = [threading.Thread(target=self._serve_udp,
                                          name=f"fake-1x0-udp-{self.mac}", daemon=True)]
        if self.serve_direct:
            self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._tcp.bind((self.bind, self._direct_port))
            self._tcp.listen(4)
            self._tcp.settimeout(0.05)
            self._threads.append(threading.Thread(target=self._serve_tcp,
                                                  name=f"fake-1x0-tcp-{self.mac}", daemon=True))
        for t in self._threads:
            t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads = []
        for s in (self._sock, self._tcp):
            if s is not None:
                s.close()
        self._sock = None
        self._tcp = None

    def __enter__(self) -> "FakeWiz1x0Device":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _serve_udp(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle(data, addr, "udp")

    def _serve_tcp(self) -> None:
        assert self._tcp is not None
        while not self._stop.is_set():
            try:
                conn, addr = self._tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve_conn, args=(conn, addr), daemon=True).start()

    def _serve_conn(self, conn: socket.socket, addr) -> None:
        """직접-IP 검색: 접속 → FIND 수신 → 163B 응답 → 종료."""
        with conn:
            conn.settimeout(1.0)
            try:
                data = conn.recv(512)
            except OSError:
                return
            if not data:
                return
            idx = len(self.requests)
            self.requests.append(data)
            verdict = self.classify(data)
            self.verdicts.append(verdict)
            if not verdict.answered:
                self._log(1, f"#{idx} tcp req {len(data)}B  → {verdict.note}")
                return
            reply = self.build_reply(data)
            if reply is None:
                return
            self.replies.append(reply)
            self._log(1, f"#{idx} tcp req {len(data)}B ({verdict.note}) from {addr[0]}"
                         f"  → reply {len(reply)}B")
            try:
                conn.sendall(reply)
            except OSError as e:
                self._log(1, f"#{idx} tcp send 실패: {e}")

    def _handle(self, data: bytes, addr, via: str) -> None:
        idx = len(self.requests)
        self.requests.append(data)
        verdict = self.classify(data)
        self.verdicts.append(verdict)
        if not verdict.answered:
            self._log(2 if verdict.kind == "unsupported" else 1,
                      f"#{idx} {via} req {len(data)}B  → {verdict.note}")
            return
        reply = self.build_reply(data)
        if reply is None:
            return
        self.replies.append(reply)
        self._log(1, f"#{idx} {via} req {len(data)}B ({verdict.note}) from {addr[0]}:{addr[1]}"
                     f"  → reply {len(reply)}B")
        try:
            assert self._sock is not None
            self._sock.sendto(reply, addr)
        except OSError as e:
            self._log(1, f"#{idx} sendto 실패: {e}")

    def _log(self, level: int, msg: str) -> None:
        if self.verbose >= level:
            print(f"[fake-1x0 {self.mac}] {msg}", flush=True)

    def summary(self) -> str:
        kinds: dict[str, int] = {}
        for v in self.verdicts:
            kinds[v.kind] = kinds.get(v.kind, 0) + 1
        parts = [f"요청 {len(self.requests)}", f"응답 {len(self.replies)}"]
        for k, label in (("malformed", "형식 오류"), ("unsupported", "미지원")):
            if kinds.get(k):
                parts.append(f"{label} {kinds[k]}")
        if self.reboots:
            parts.append(f"설정·리부트 {self.reboots}")
        return " / ".join(parts)


def make_device_fleet(count: int, *, first_mac: str = FAKE_MAC,
                      first_ip: str = "192.168.7.60", **kwargs) -> list[FakeWiz1x0Device]:
    """MAC 과 IP 가 1씩 증가하는 가짜 WIZ1x0 여러 대.

    직접-IP 검색(TCP)은 한 포트를 한 대만 열 수 있으므로 두 대 이상이면 첫 대만 연다.
    """
    base_mac = int(first_mac.replace(":", ""), 16)
    a, b, c, d = (int(x) for x in first_ip.split("."))
    fleet = []
    for i in range(count):
        raw = f"{base_mac + i:012X}"
        mac = ":".join(raw[j:j + 2] for j in range(0, 12, 2))
        board = dict(kwargs.pop("board", None) or {}, ip=f"{a}.{b}.{c}.{d + i}")
        fleet.append(FakeWiz1x0Device(mac=mac, board=board,
                                      serve_direct=(i == 0), **kwargs))
    return fleet


def _main() -> None:
    ap = argparse.ArgumentParser(description="가짜 WIZ1x0SR 장치 (UDP 1460 / TCP 1461)")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=SEARCH_PORT)
    ap.add_argument("--direct-port", type=int, default=DIRECT_PORT)
    ap.add_argument("--mac", default=FAKE_MAC)
    ap.add_argument("--ip", default="192.168.7.60", help="장치가 보고할 IP")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--short-setc", action="store_true",
                    help="SETC 를 4바이트만 보낸다 (설정툴의 폴백 경로 시험)")
    ap.add_argument("-v", "--verbose", action="count", default=1)
    args = ap.parse_args()

    fleet = make_device_fleet(args.count, first_mac=args.mac, first_ip=args.ip,
                              bind=args.bind, port=args.port,
                              direct_port=args.direct_port,
                              setc_carries_board=not args.short_setc,
                              verbose=args.verbose)
    for dev in fleet:
        dev.start()
    print(f"[fake-1x0] listening udp {args.bind}:{fleet[0].port} / "
          f"tcp {args.bind}:{fleet[0].direct_port}  "
          f"mac={', '.join(d.mac for d in fleet)}  (Ctrl+C 로 종료)", flush=True)
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for dev in fleet:
            dev.stop()
            print(f"[fake-1x0 {dev.mac}] {dev.summary()}", flush=True)


if __name__ == "__main__":
    _main()
