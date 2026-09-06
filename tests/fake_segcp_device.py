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

응답 목적지
    펌웨어는 응답을 보낸 쪽 포트로 **브로드캐스트**한다
    (segcp.c:1443 `sendto(..., "\\xFF\\xFF\\xFF\\xFF", destport)`, WIZ750SR 은 :1241).
    설정툴은 포트 5000 소켓을 닫지 않고 거듭 만들어 여러 개가 겹쳐 있는데, Windows 는
    유니캐스트를 가장 먼저 바인드된 소켓 하나에만 주고 브로드캐스트는 전부에 준다
    (2026-09-03 실측). 그래서 유니캐스트로 답하면 실기기에서는 안 나던 "no response" 가
    난다. 단독 실행은 펌웨어대로 브로드캐스트(reply_broadcast=True) 가 기본이고,
    pytest 는 루프백이라 유니캐스트를 쓴다.

설정툴은 개별 장치 조회도 브로드캐스트로 뿌리므로, 같은 망에 장치가 여럿이면
**남의 MAC 앞으로 온 요청도 전부 받는다.** 그것을 무시하는 것은 정상 동작이지
오류가 아니다 — classify() 가 그 둘을 구분해서 알려준다.

기본값은 무해한 쪽이다. 거부(ER)·리부트·DNS 지연은 전부 꺼져 있고, 필요한 시험만
FirmwareQuirks 로 켠다. 수동 시험 중에 없던 오류가 생기지 않게 하려는 것이다.

단순화한 것
    - SET 커맨드는 값을 저장만 하고 응답에 싣지 않는다 (펌웨어와 같다)
    - MA 가 자기 MAC 이거나 FF:FF:FF:FF:FF:FF 일 때만 답한다. PW 값은 검사하지 않는다
    - 모르는 커맨드는 응답에서 이름째 빠진다 (펌웨어의 되감기 segcp.c:708~712 와 같은 효과)

기본 프로파일 PROFILE_WIZ752_MEASURED 는 2026-09-01 장비 00:08:DC:84:14:27
(VR 2.1.0dev) 의 검색 응답 dict 를 그대로 옮긴 것이다. 64개 커맨드 요청에 531B,
Remote host 를 IP 로 바꾸면 515B 가 나와 실측과 일치한다.

단독 실행 (설정툴 GUI 를 가짜 장치에 붙여 볼 때)

    uv run python -m tests.fake_segcp_device --bind 0.0.0.0 --port 50001
    uv run python -m tests.fake_segcp_device --count 5          # 5대 동시
    uv run python -m tests.fake_segcp_device -vv                # 남의 요청까지 전부 표시

설정툴은 255.255.255.255:50001 로 브로드캐스트하므로 같은 PC 에서 0.0.0.0:50001 에
바인드하면 응답기가 그 요청을 받는다. 가짜 장치의 MAC 은 00:08:DC:FA:CE:01 부터라
같은 망의 실기기와 섞여도 구분된다.
"""

from __future__ import annotations

import argparse
import re
import socket
import threading
import time
from dataclasses import dataclass, replace
from typing import Optional

CRLF = b"\r\n"
BROADCAST_MAC = b"\xff" * 6
BROADCAST_MAC_STR = "FF:FF:FF:FF:FF:FF"
DEFAULT_REPLY_BUF_SIZE = 512   # CONFIG_BUF_SIZE (WIZ752SR-12x common.h:52)
FAKE_MAC = "00:08:DC:FA:CE:01"
TCP_SERVER_MODE = "1"          # common.h:78
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# 펌웨어가 쓰는 오류 이름 (segcp.c:46 tbSEGCPERR). 접두어 ER 은 응답 줄에 붙는다.
SEGCP_ERRORS = ("NULL", "NOTAVAIL", "NOPARAM", "IGNORED",
                "NOCOMMAND", "INVALIDPARAM", "NOPRIVILEGE")

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


@dataclass(frozen=True)
class FirmwareQuirks:
    """펌웨어 판별로 달라지는 동작. 근거가 있는 것만 둔다.

    기본값 = 지금까지 가짜 장치가 하던 동작(무해한 쪽). 시험이 필요한 것만 켠다.
    """

    reply_buf_size: int = DEFAULT_REPLY_BUF_SIZE
    """응답 버퍼 크기. 넘긴 양은 overflow_events 에 남는다."""

    truncate_reply: bool = False
    """상한이 들어간 펌웨어. 버퍼 크기 - 1 에서 잘라 보낸다."""

    shared_domain: bool = True
    """RH·QH 가 같은 dns_domain_name[40] 을 쓴다 (ConfigData.h:126, 2026-09-01 양방향 실측).
    한 패킷 안에서는 뒤에 오는 쪽이 이긴다."""

    domain_field_size: int = 40
    """`strcpy(dns_domain_name, param)` 의 대상 크기. 넘으면 NUL 자리를 뺀 만큼만 남는다."""

    er_in_tool_mode: bool = True
    """거부 시 ER 줄을 응답에 싣는다. fix/user-io-and-segcp 는 이것이 AT 모드 안으로
    들어가 설정툴 모드에서는 ER 이 생성되지 않는다(부작용)."""

    abort_on_error: bool = True
    """거부 시 proc_SEGCP 가 즉시 return 한다 — 뒤 커맨드와 SV/RT 가 통째로 스킵된다
    (segcp.c:1365 `return ret`). 브랜치 71b1add 가 이것을 없앴다."""

    reboot_sec: float = 0.0
    """RT 를 받은 뒤 응답하지 않는 시간. 0 이면 리부트를 흉내 내지 않는다."""

    dns_block_sec: float = 0.0
    """부팅 시 도메인 해석으로 do_segcp() 가 멈추는 시간 (main.c 의 process_dns()).
    채널0(OP)이 TCP Server 가 아니고 Remote host 가 도메인일 때만 걸린다."""


# 시험 장비 84:14:27 에 올라가 있는 빌드.
FW_752_2_1_0DEV = FirmwareQuirks()

# 담당자 수정본 브랜치 fix/user-io-and-segcp (ab2a782).
# 3번(패킷 중단) 수정으로 설정툴 모드에서 ER 이 사라지고 뒤 커맨드는 처리된다.
FW_752_FIX_BRANCH = FirmwareQuirks(er_in_tool_mode=False, abort_on_error=False)

# 7번(응답 상한)까지 들어간 가정.
FW_752_WITH_REPLY_CAP = replace(FW_752_FIX_BRANCH, truncate_reply=True)


@dataclass
class Verdict:
    """요청 하나를 어떻게 처리했는지. 정상 트래픽과 진짜 이상을 구분하려고 둔다."""

    kind: str                          # answered / other-device / malformed / rebooting
    answered: bool
    note: str
    target_mac: Optional[str] = None


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


def bytes_to_mac(mac6: bytes) -> str:
    return ":".join(f"{b:02X}" for b in mac6)


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
                 quirks: FirmwareQuirks = FW_752_2_1_0DEV,
                 reply_buf_size: Optional[int] = None, mode: Optional[str] = None,
                 drop_first: int = 0, reply_broadcast: bool = False,
                 verbose: int = 0):
        # reply_buf_size / mode 는 quirks 로 옮기기 전의 이름. 둘 다 받아 준다.
        if reply_buf_size is not None:
            quirks = replace(quirks, reply_buf_size=reply_buf_size)
        if mode is not None:
            if mode not in ("overflow", "truncate"):
                raise ValueError(f"unknown mode {mode!r}")
            quirks = replace(quirks, truncate_reply=(mode == "truncate"))
        self.quirks = quirks

        self.profile = dict(profile)
        self.profile['MC'] = mac
        self.mac = mac
        self.mac6 = mac_to_bytes(mac)
        self.bind = bind
        self._port = port
        self.drop_first = drop_first      # 처음 N개 요청을 응답 없이 버린다 (유실 시험)
        self.reply_broadcast = reply_broadcast   # True = 펌웨어처럼 브로드캐스트로 응답
        self.verbose = int(verbose)

        # 거부할 커맨드: {커맨드: 오류이름}. 오류이름은 SEGCP_ERRORS 중 하나.
        # 기본은 비어 있다 — 아무것도 거부하지 않는다.
        self.reject: dict[str, str] = {}

        self.requests: list[bytes] = []
        self.replies: list[bytes] = []
        self.overflow_events: list[tuple[int, int]] = []   # (요청 순번, 초과 바이트)
        self.field_overflows: list[tuple[str, int, int]] = []  # (커맨드, 준 길이, 필드 크기)
        self.verdicts: list[Verdict] = []
        self.dropped = 0
        self.saved = False
        self.reboots = 0

        self._unresponsive_until = 0.0
        self._explained_other_device = False
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ── 판정 (상태를 바꾸지 않는다) ────────────────────────────────────

    def classify(self, request: bytes) -> Verdict:
        """요청 하나를 어떻게 처리할지. 로그 문구도 여기서 정한다."""
        parsed = parse_request(request)
        if parsed is None:
            head = bytes(request[:16])
            return Verdict("malformed", False,
                           f"SEGCP 형식이 아님 (MA/PW 헤더 없음) {head!r}")
        mac6 = parsed[0]
        target = bytes_to_mac(mac6)
        if mac6 not in (self.mac6, BROADCAST_MAC):
            return Verdict("other-device", False,
                           f"{target} 앞으로 온 브로드캐스트 — 내 것이 아니라 넘김",
                           target_mac=target)
        if self._rebooting():
            left = self._unresponsive_until - time.monotonic()
            return Verdict("rebooting", False,
                           f"리부트/DNS 해석 중 — {left:.1f}s 남음 (do_segcp 정지)",
                           target_mac=target)
        return Verdict("answered", True, f"{len(parsed[2])}개 커맨드", target_mac=target)

    def _rebooting(self) -> bool:
        return time.monotonic() < self._unresponsive_until

    # ── 응답 생성 (네트워크 없이 시험 가능) ────────────────────────────

    def build_reply(self, request: bytes) -> Optional[bytes]:
        """요청 한 개에 대한 응답 바이트. 무시할 요청이면 None.

        overflow_events 에 초과량을 기록한다. 인덱스는 지금까지 받은 요청 수 기준.
        """
        verdict = self.classify(request)
        if not verdict.answered:
            return None
        mac6, code, cmds = parse_request(request)   # type: ignore[misc]

        body = b""
        reboot = False
        for cmd, param in cmds:
            if cmd in self.reject:
                err = self.reject[cmd]
                if self.quirks.er_in_tool_mode:
                    body += f"ER{err}:{cmd}".encode() + CRLF
                if self.quirks.abort_on_error:
                    # segcp.c:1365 `return ret` — 뒤 커맨드도 SV/RT 도 처리되지 않는다
                    reboot = False
                    break
                continue
            if cmd == "SV":
                self.saved = True
            elif cmd == "RT":
                reboot = True
            elif param == "":
                if cmd in self.profile:
                    body += cmd.encode() + self.profile[cmd].encode() + CRLF
            else:
                self._store(cmd, param)

        reply = b"MA" + self.mac6 + CRLF + b"PW" + code + CRLF + body

        written = len(reply) + 1   # 펌웨어는 NUL 까지 기록한다
        overflow = written - self.quirks.reply_buf_size
        if overflow > 0:
            self.overflow_events.append((len(self.requests), overflow))
        if self.quirks.truncate_reply:
            reply = reply[:self.quirks.reply_buf_size - 1]

        if reboot:
            self._schedule_reboot()
        return reply

    def _store(self, cmd: str, param: str) -> None:
        """SET 값을 장치에 반영한다. 도메인은 한 필드를 공유하고 길이 제한이 있다."""
        if cmd in ("RH", "QH") and not _IPV4.match(param):
            size = self.quirks.domain_field_size
            if len(param) >= size:
                self.field_overflows.append((cmd, len(param), size))
                param = param[:size - 1]
            if self.quirks.shared_domain:
                self.profile["RH"] = param
                self.profile["QH"] = param
                return
        elif cmd in ("RH", "QH") and self.quirks.shared_domain:
            # IP 를 넣으면 도메인 사용이 꺼지고 양쪽이 같이 바뀐다 (segcp.c:941/959)
            self.profile["RH"] = param
            self.profile["QH"] = param
            return
        self.profile[cmd] = param

    def _schedule_reboot(self) -> None:
        """RT 이후 무응답 창. 도메인을 쓰는 채널0 클라이언트면 부팅 DNS 해석이 더 붙는다."""
        q = self.quirks
        window = q.reboot_sec
        if q.dns_block_sec and self._boot_dns_blocks():
            window += q.dns_block_sec
        self.reboots += 1
        if window > 0:
            self._unresponsive_until = time.monotonic() + window

    def _boot_dns_blocks(self) -> bool:
        """main.c 는 while(1) 전에 process_dns() 를 돌린다 — 채널0 이 TCP Server 가
        아니고 도메인을 쓸 때만. DNS 결과는 채널0 remote_ip 에만 쓴다."""
        if self.profile.get("OP") == TCP_SERVER_MODE:
            return False
        host = self.profile.get("RH", "")
        return bool(host.strip()) and not _IPV4.match(host)

    # ── 서버 ──────────────────────────────────────────────────────────

    def reply_target(self, addr) -> tuple[str, int]:
        """응답을 보낼 곳. 펌웨어와 같게 하려면 보낸 쪽 포트로 브로드캐스트."""
        if self.reply_broadcast:
            return ("255.255.255.255", addr[1])
        return (addr[0], addr[1])

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
        self._thread = threading.Thread(target=self._serve, name=f"fake-segcp-{self.mac}", daemon=True)
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
            self._log(1, f"#{idx} req {len(data)}B  → 버림 ({self.dropped}/{self.drop_first}, 유실 시험)")
            return

        verdict = self.classify(data)
        self.verdicts.append(verdict)
        if not verdict.answered:
            if verdict.kind == "other-device":
                # 설정툴이 모든 요청을 브로드캐스트하므로 늘 생기는 정상 트래픽이다.
                # 매번 찍으면 오류처럼 보여서 -vv 에서만 낱개로 보여 준다.
                if not self._explained_other_device:
                    self._explained_other_device = True
                    self._log(1, f"#{idx} req {len(data)}B  → {verdict.note} "
                                 f"(설정툴이 브로드캐스트하므로 정상. 이후 같은 건 -vv 에서만 표시)")
                else:
                    self._log(2, f"#{idx} req {len(data)}B  → {verdict.note}")
            else:
                self._log(1, f"#{idx} req {len(data)}B  → {verdict.note}")
            return

        reply = self.build_reply(data)
        if reply is None:
            return
        self.replies.append(reply)
        over = [o for i, o in self.overflow_events if i == idx]
        note = f"  ⚠ 버퍼 초과 +{over[0]}B" if over else ""
        target = self.reply_target(addr)
        self._log(1, f"#{idx} req {len(data)}B ({verdict.note}) from {addr[0]}:{addr[1]}"
                     f"  → reply {len(reply)}B to {target[0]}:{target[1]}{note}")
        try:
            assert self._sock is not None
            self._sock.sendto(reply, target)
        except OSError as e:
            self._log(1, f"#{idx} sendto 실패: {e}")

    def _log(self, level: int, msg: str) -> None:
        if self.verbose >= level:
            print(f"[fake-segcp {self.mac}] {msg}", flush=True)

    def summary(self) -> str:
        kinds = {}
        for v in self.verdicts:
            kinds[v.kind] = kinds.get(v.kind, 0) + 1
        parts = [f"요청 {len(self.requests)}", f"응답 {len(self.replies)}"]
        for k, label in (("other-device", "남의 것"), ("malformed", "형식 오류"),
                         ("rebooting", "리부트 중")):
            if kinds.get(k):
                parts.append(f"{label} {kinds[k]}")
        if self.overflow_events:
            parts.append(f"버퍼 초과 {len(self.overflow_events)}")
        if self.field_overflows:
            parts.append(f"필드 초과 {len(self.field_overflows)}")
        return " / ".join(parts)


def make_device_fleet(count: int, profile: dict[str, str], *,
                      first_mac: str = FAKE_MAC, **kwargs) -> list[FakeSegcpDevice]:
    """MAC 이 1씩 증가하는 가짜 장치 여러 대. 검색이 N대를 다 잡는지 볼 때 쓴다."""
    base = int(first_mac.replace(":", ""), 16)
    fleet = []
    for i in range(count):
        raw = f"{base + i:012X}"
        mac = ":".join(raw[j:j + 2] for j in range(0, 12, 2))
        fleet.append(FakeSegcpDevice(profile, mac=mac, **kwargs))
    return fleet


def _main() -> None:
    ap = argparse.ArgumentParser(description="가짜 WIZ752SR-12x SEGCP 응답기")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=50001)
    ap.add_argument("--mac", default=FAKE_MAC, help="첫 장치의 MAC (--count 는 여기서 1씩 증가)")
    ap.add_argument("--count", type=int, default=1, help="동시에 띄울 가짜 장치 수")
    ap.add_argument("--mode", choices=("overflow", "truncate"), default="overflow",
                    help="overflow=현재 FW / truncate=응답 상한이 들어간 FW")
    ap.add_argument("--buf", type=int, default=DEFAULT_REPLY_BUF_SIZE, help="응답 버퍼 크기 (기본 512)")
    ap.add_argument("--domain", default=None,
                    help="RH/QH 에 넣을 도메인 (기본: 실측 프로파일의 test-server-01.local)")
    ap.add_argument("--reboot-sec", type=float, default=0.0,
                    help="RT 이후 무응답 시간. 기본 0 = 리부트를 흉내 내지 않음")
    ap.add_argument("--dns-block-sec", type=float, default=0.0,
                    help="부팅 DNS 해석 지연. 채널0 이 TCP Server 가 아니고 도메인일 때만 적용")
    ap.add_argument("--unicast-reply", action="store_true",
                    help="응답을 보낸 쪽 주소로 유니캐스트 (기본은 펌웨어처럼 브로드캐스트)")
    ap.add_argument("-v", "--verbose", action="count", default=1,
                    help="-v 기본(내 요청만) / -vv 남의 요청까지 전부")
    args = ap.parse_args()

    profile = PROFILE_WIZ752_MEASURED
    if args.domain:
        profile = profile_with_remote_host(profile, args.domain)
    quirks = FirmwareQuirks(reply_buf_size=args.buf,
                            truncate_reply=(args.mode == "truncate"),
                            reboot_sec=args.reboot_sec,
                            dns_block_sec=args.dns_block_sec)

    if args.count > 1 and args.port != 0:
        # 한 포트를 여러 장치가 공유해야 설정툴의 브로드캐스트를 모두가 받는다.
        # 같은 주소에 여러 소켓을 여는 것은 SO_REUSEADDR 로 가능하지만 유니캐스트
        # 배달이 한 소켓에만 가므로, 여러 대는 브로드캐스트 응답에서만 의미가 있다.
        print("[fake-segcp] 주의: --count 는 브로드캐스트 응답(기본)에서만 정상 동작한다",
              flush=True)

    fleet = make_device_fleet(args.count, profile, first_mac=args.mac,
                              bind=args.bind, port=args.port, quirks=quirks,
                              reply_broadcast=not args.unicast_reply,
                              verbose=args.verbose)
    for dev in fleet:
        dev.start()
    print(f"[fake-segcp] listening {args.bind}:{fleet[0].port}  "
          f"mac={', '.join(d.mac for d in fleet)}  mode={args.mode} buf={args.buf}  "
          f"reply={'broadcast' if fleet[0].reply_broadcast else 'unicast'}  (Ctrl+C 로 종료)",
          flush=True)
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for dev in fleet:
            dev.stop()
            print(f"[fake-segcp {dev.mac}] {dev.summary()}", flush=True)


if __name__ == "__main__":
    _main()
