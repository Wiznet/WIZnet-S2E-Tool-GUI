#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 SEGCP 장치 — W7500 계열(WIZ750SR/WIZ752SR) 설정 프로토콜의 UDP 응답기.

테스트 전용이다. 실기기 없이 설정툴의 요청/응답 경로를 돌려 보기 위해 만들었다.

펌웨어(WIZ752SR-12x master `0207e95`) 의 응답 경로를 흉내 낸다.

    요청   MA(2) + MAC(6) + CRLF, PW + code + CRLF, 이후 커맨드(2) + 값 + CRLF 반복
    응답   MA + MAC + CRLF, PW + code + CRLF, 이후 GET 한 커맨드마다 커맨드(2) + 값 + CRLF
    버퍼   gSEGCPREP[CONFIG_BUF_SIZE] = 512. 펌웨어는 길이를 대조하지 않고
           strlen 만큼 sendto 한다 (segcp.c:1443). 응답 + NUL 이 버퍼를 넘긴 만큼
           인접 메모리를 밟는다. 여기서는 그 초과량을 overflow_events 에 기록한다.

모드
    "overflow"  현재 펌웨어. 넘쳐도 전부 보낸다
    "truncate"  상한이 들어간 펌웨어 가정. 버퍼 크기 - 1 에서 잘라 보낸다

응답 목적지
    펌웨어는 응답을 보낸 쪽 포트로 **브로드캐스트**한다
    (segcp.c:1443 `sendto(..., "\xFF\xFF\xFF\xFF", destport)`, WIZ750SR 은 :1241).
    설정툴은 포트 5000 소켓을 닫지 않고 거듭 만들어 여러 개가 겹쳐 있는데, Windows 는
    유니캐스트를 가장 먼저 바인드된 소켓 하나에만 주고 브로드캐스트는 전부에 준다
    (2026-09-03 실측). 그래서 유니캐스트로 답하면 실기기에서는 안 나던 "no response" 가
    난다. 단독 실행은 펌웨어대로 브로드캐스트(reply_broadcast=True) 가 기본이고,
    pytest 는 루프백이라 유니캐스트를 쓴다.

단순화한 것
    - SET 커맨드는 값을 저장만 하고 응답에 싣지 않는다 (ER/응답 에코 없음)
    - MA 가 자기 MAC 이거나 FF:FF:FF:FF:FF:FF 일 때만 답한다. PW 값은 검사하지 않는다
    - 모르는 커맨드는 응답에서 이름째 빠진다 (펌웨어의 되감기 segcp.c:708~712 와 같은 효과)

기본 프로파일 PROFILE_WIZ752_MEASURED 는 2026-09-01 장비 00:08:DC:84:14:27
(VR 2.1.0dev) 의 검색 응답 dict 를 그대로 옮긴 것이다. 64개 커맨드 요청에 531B,
Remote host 를 IP 로 바꾸면 515B 가 나와 실측과 일치한다.

단독 실행 (설정툴 GUI 를 가짜 장치에 붙여 볼 때)

    uv run python -m tests.fake_segcp_device --bind 0.0.0.0 --port 50001

설정툴은 255.255.255.255:50001 로 브로드캐스트하므로 같은 PC 에서 0.0.0.0:50001 에
바인드하면 응답기가 그 요청을 받는다. 가짜 장치의 MAC 은 00:08:DC:FA:CE:01 이라
같은 망의 실기기와 섞여도 구분된다.
"""

from __future__ import annotations

import argparse
import socket
import threading
from typing import Optional

CRLF = b"\r\n"
BROADCAST_MAC = b"\xff" * 6
DEFAULT_REPLY_BUF_SIZE = 512   # CONFIG_BUF_SIZE (WIZ752SR-12x common.h:52)
FAKE_MAC = "00:08:DC:FA:CE:01"

# 2026-09-01 실측 (장비 84:14:27, VR 2.1.0dev, 설정툴 1.6.2.20-dev, 응답 531B)
PROFILE_WIZ752_MEASURED: dict[str, str] = {
    'MC': '00:08:DC:84:14:27', 'VR': '2.1.0dev', 'MN': 'WIZ752SR-12x',
    'UN': 'RS-232/TTL', 'ST': 'OPEN', 'IM': '0', 'OP': '1', 'CP': '0',
    'DG': '1', 'KA': '1', 'KI': '7000', 'KE': '5000', 'RI': '3000',
    'LI': '192.168.7.21', 'SM': '255.255.255.0', 'GW': '192.168.7.1',
    'DS': '8.8.8.8', 'PI': ' ', 'PP': ' ', 'DX': '0', 'DP': '3030',
    'DI': ' ', 'DW': ' ', 'DH': 'WIZ752SR-12x-841427', 'LP': '5000',
    'RP': '5000', 'RH': 'test-server-01.local', 'BR': '12', 'DB': '1',
    'PR': '0', 'SB': '0', 'FL': '0', 'IT': '0', 'PT': '0', 'PS': '0',
    'PD': '00', 'TE': '1', 'SS': '2B2B2B', 'NP': ' ', 'SP': ' ',
    'QS': 'OPEN', 'QO': '0', 'QH': 'test-server-01.local', 'QP': '5001',
    'QL': '5001', 'RV': '0', 'RA': '1', 'RE': '5000', 'RR': '3000',
    'EN': 'RS-232/TTL', 'RS': '7000', 'EB': '13', 'ED': '1', 'EP': '0',
    'ES': '0', 'EF': '0', 'E0': '1', 'E1': '1', 'NT': '0', 'NS': '0',
    'ND': '00', 'S0': '0', 'S1': '1', 'SC': '00',
    # User I/O 는 검색 응답에 없고 DataRefresh 가 따로 묻는다(cmd_gpio_4pin).
    # 실측 프로파일에 없어서 기본값을 둔다 — 없으면 User I/O 탭이 비어 보인다.
    'CA': '0', 'CB': '0', 'CC': '0', 'CD': '0',
    'GA': '0', 'GB': '0', 'GC': '0', 'GD': '0',
}


def profile_with_remote_host(base: dict[str, str], host: str) -> dict[str, str]:
    """RH/QH 를 같은 값으로 바꾼 사본. 장치는 도메인을 하나만 저장해 양쪽에 돌려준다."""
    prof = dict(base)
    prof['RH'] = host
    prof['QH'] = host
    return prof


def profile_with_domain(base: dict[str, str], length: int) -> dict[str, str]:
    """길이가 정확히 length 인 도메인을 RH/QH 에 넣은 사본."""
    if length < 1:
        raise ValueError("length must be >= 1")
    stem = "d" * max(1, length - 6) + ".local"
    return profile_with_remote_host(base, stem[:length].ljust(length, "x"))


def expected_reply_len(profile: dict[str, str], cmds: list[str]) -> int:
    """응답 크기 모델: 15 + Σ(커맨드 2B + 값 + CRLF 2B). 실측 5점과 오차 0 (2026-09-01)."""
    return 15 + sum(4 + len(profile[c]) for c in cmds if c in profile)


def mac_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def parse_request(req: bytes) -> Optional[tuple[bytes, bytes, list[tuple[str, str]]]]:
    """요청을 (MAC 6B, PW 코드, [(cmd, param), ...]) 로 푼다. 형식이 아니면 None."""
    if len(req) < 10 or req[:2] != b"MA" or req[8:10] != CRLF:
        return None
    mac6 = req[2:8]
    lines = req[10:].split(CRLF)
    if not lines or lines[0][:2] != b"PW":
        return None
    code = lines[0][2:]
    cmds = []
    for line in lines[1:]:
        if len(line) < 2:
            continue
        cmds.append((line[:2].decode("ascii", errors="replace"),
                     line[2:].decode("ascii", errors="replace")))
    return mac6, code, cmds


class FakeSegcpDevice:
    """UDP 응답기. with 문 또는 start()/stop() 으로 쓴다."""

    def __init__(self, profile: dict[str, str], *, mac: str = FAKE_MAC,
                 bind: str = "127.0.0.1", port: int = 0,
                 reply_buf_size: int = DEFAULT_REPLY_BUF_SIZE,
                 mode: str = "overflow", drop_first: int = 0,
                 reply_broadcast: bool = False, verbose: bool = False):
        if mode not in ("overflow", "truncate"):
            raise ValueError(f"unknown mode {mode!r}")
        self.reply_broadcast = reply_broadcast   # True = 펌웨어처럼 255.255.255.255:보낸포트 로 응답
        self.profile = dict(profile)
        self.profile['MC'] = mac
        self.mac6 = mac_to_bytes(mac)
        self.bind = bind
        self._port = port
        self.reply_buf_size = reply_buf_size
        self.mode = mode
        self.drop_first = drop_first      # 처음 N개 요청을 응답 없이 버린다 (유실 시험)
        self.verbose = verbose

        self.requests: list[bytes] = []
        self.replies: list[bytes] = []
        self.overflow_events: list[tuple[int, int]] = []   # (요청 순번, 초과 바이트)
        self.dropped = 0

        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ── 순수 로직 (네트워크 없이 시험 가능) ─────────────────────────────

    def build_reply(self, request: bytes) -> Optional[bytes]:
        """요청 한 개에 대한 응답 바이트. 무시할 요청이면 None.

        overflow_events 에 초과량을 기록한다. 인덱스는 지금까지 받은 요청 수 기준.
        """
        parsed = parse_request(request)
        if parsed is None:
            return None
        mac6, code, cmds = parsed
        if mac6 not in (self.mac6, BROADCAST_MAC):
            return None

        body = b""
        for cmd, param in cmds:
            if param == "":
                if cmd in self.profile:
                    body += cmd.encode() + self.profile[cmd].encode() + CRLF
            else:
                self.profile[cmd] = param
        reply = b"MA" + self.mac6 + CRLF + b"PW" + code + CRLF + body

        written = len(reply) + 1   # 펌웨어는 NUL 까지 기록한다
        overflow = written - self.reply_buf_size
        if overflow > 0:
            self.overflow_events.append((len(self.requests), overflow))
        if self.mode == "truncate":
            reply = reply[:self.reply_buf_size - 1]
        return reply

    def reply_target(self, addr) -> tuple[str, int]:
        """응답을 보낼 곳. 펌웨어와 같게 하려면 보낸 쪽 포트로 브로드캐스트."""
        if self.reply_broadcast:
            return ("255.255.255.255", addr[1])
        return (addr[0], addr[1])

    # ── 서버 ──────────────────────────────────────────────────────────

    @property
    def port(self) -> int:
        if self._sock is None:
            return self._port
        return self._sock.getsockname()[1]

    def start(self) -> "FakeSegcpDevice":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind((self.bind, self._port))
        self._sock.settimeout(0.05)
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="fake-segcp", daemon=True)
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

    def __enter__(self) -> "FakeSegcpDevice":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle(data, addr)

    def _handle(self, data: bytes, addr) -> None:
        idx = len(self.requests)
        self.requests.append(data)
        if self.dropped < self.drop_first:
            self.dropped += 1
            self._log(f"#{idx} req {len(data)}B  → dropped ({self.dropped}/{self.drop_first})")
            return
        reply = self.build_reply(data)
        if reply is None:
            self._log(f"#{idx} req {len(data)}B  → ignored (MAC mismatch or bad format)")
            return
        self.replies.append(reply)
        over = [o for i, o in self.overflow_events if i == idx]
        note = f"  OVERFLOW +{over[0]}B" if over else ""
        parsed = parse_request(data)
        ncmd = len(parsed[2]) if parsed else 0
        target = self.reply_target(addr)
        self._log(f"#{idx} req {len(data)}B ({ncmd} cmds) from {addr[0]}:{addr[1]}  → reply {len(reply)}B to {target[0]}:{target[1]}{note}")
        try:
            assert self._sock is not None
            self._sock.sendto(reply, target)
        except OSError as e:
            self._log(f"#{idx} sendto failed: {e}")

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[fake-segcp {self.profile['MC']}] {msg}", flush=True)


def _main() -> None:
    ap = argparse.ArgumentParser(description="가짜 WIZ752SR-12x SEGCP 응답기")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=50001)
    ap.add_argument("--mac", default=FAKE_MAC)
    ap.add_argument("--mode", choices=("overflow", "truncate"), default="overflow")
    ap.add_argument("--buf", type=int, default=DEFAULT_REPLY_BUF_SIZE,
                    help="응답 버퍼 크기 (기본 512)")
    ap.add_argument("--domain", default=None,
                    help="RH/QH 에 넣을 도메인 (기본: 실측 프로파일의 test-server-01.local)")
    ap.add_argument("--unicast-reply", action="store_true",
                    help="응답을 보낸 쪽 주소로 유니캐스트 (기본은 펌웨어처럼 브로드캐스트)")
    args = ap.parse_args()

    profile = PROFILE_WIZ752_MEASURED
    if args.domain:
        profile = profile_with_remote_host(profile, args.domain)
    dev = FakeSegcpDevice(profile, mac=args.mac, bind=args.bind, port=args.port,
                          reply_buf_size=args.buf, mode=args.mode,
                          reply_broadcast=not args.unicast_reply, verbose=True)
    dev.start()
    print(f"[fake-segcp] listening {args.bind}:{dev.port}  mac={args.mac}  "
          f"mode={args.mode} buf={args.buf}  reply={'broadcast' if dev.reply_broadcast else 'unicast'}"
          f"  (Ctrl+C 로 종료)", flush=True)
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        dev.stop()
        print(f"[fake-segcp] requests={len(dev.requests)} replies={len(dev.replies)} "
              f"overflow_events={dev.overflow_events}", flush=True)


if __name__ == "__main__":
    _main()
