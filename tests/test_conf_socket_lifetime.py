#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""설정 소켓(포트 52000)의 수명 — 쌓이면 응답을 못 받는다.

`BUG-CONF-SOCK-PILEUP`. `socket_config()` 가 이전 소켓을 닫지 않고 새로 만들어
한 세션에 여러 개가 겹쳐 바인드된다(`WIZUDPSock` 의 첫 인자 `port` 는 쓰이지 않고
`localport` 기본값 52000 으로 바인드된다 — 2026-09-07 확인). Windows 는 같은 주소에 겹친 소켓 중
**가장 먼저 바인드된 것에만 유니캐스트를 배달**하고 브로드캐스트는 전부에 준다
(2026-09-03 실측). 그래서 나중에 만든 소켓으로 요청을 보내면 응답을 못 받는다.

실기기에서는 가려진다 — W7500 펌웨어가 응답을 브로드캐스트하기 때문이다
(`segcp.c:1443`). 가짜 장치를 유니캐스트로 답하게 두었더니 드러났다.
RP2040 계열이 유니캐스트로 답한다면 실기기에서도 같은 증상이 난다 [미확인].
"""

import pytest

from constants import Opcode
from tests.fake_segcp_device import PROFILE_WIZ752_MEASURED, FakeSegcpDevice
from WIZMakeCMD import WIZMakeCMD
from WIZMSGHandler import WIZMSGHandler, parse_reply_lines

MAC = "00:08:DC:FA:CE:01"


@pytest.fixture
def window(qapp, monkeypatch):
    """오프스크린 설정툴. 소켓은 루프백으로 돌려 실장비를 건드리지 않는다."""
    import main_gui

    holder = {}

    made = []

    class LoopbackSock(main_gui.WIZUDPSock):
        def __init__(self, port, peerport, ipaddr=None, localport=52000, peer_ip=None):
            super().__init__(port, holder.get("peer_port", peerport), "127.0.0.1",
                             localport=localport, peer_ip="127.0.0.1")
            made.append(self)

    monkeypatch.setattr(main_gui, "WIZUDPSock", LoopbackSock)
    w = main_gui.WIZWindow()
    w.broadcast.setChecked(True)
    w.unicast_ip.setChecked(False)
    w._loopback_holder = holder
    yield w
    # 이 시험이 만든 소켓을 **전부** 닫는다. 하나라도 남으면 같은 주소에 겹쳐 바인드된 채로
    # 다음 시험의 유니캐스트를 가로챈다 — 고치려는 버그가 시험 사이로 새는 셈이다.
    for sock in made:
        try:
            sock.close()
        except Exception:
            pass


def ask(sock, timeout=0.6):
    """conf_sock 으로 검색 한 번. 응답 프로파일 dict 또는 빈 dict."""
    th = WIZMSGHandler(sock, WIZMakeCMD().presearch("FF:FF:FF:FF:FF:FF", " "),
                       "udp", Opcode.OP_SEARCHALL, timeout, presearch=True)
    th.run()
    return parse_reply_lines(b"".join(th.rcv_list)) if th.rcv_list else {}


# ── 1. 소켓이 쌓이지 않는다 ─────────────────────────────────────────────

def test_repeated_socket_config_keeps_one_socket(window):
    """같은 조건으로 여러 번 불러도 설정 소켓은 하나여야 한다."""
    window.socket_config()
    first = window.conf_sock
    for _ in range(4):
        window.socket_config()
    assert window.conf_sock is first, "부를 때마다 새 소켓을 만든다"
    assert first.sock is not None, "재사용하려면 열려 있어야 한다"


def test_socket_config_closes_the_old_socket_when_the_bind_changes(window):
    """바인드 조건이 달라지면 이전 것을 닫고 새로 만든다 — 겹쳐 두지 않는다."""
    window.socket_config()
    old = window.conf_sock
    window.selected_eth = "127.0.0.1"
    window.socket_config()
    assert window.conf_sock is not old, "조건이 바뀌면 새 소켓이어야 한다"
    assert old.sock is None, "이전 소켓이 닫히지 않았다 — 겹쳐 바인드된 채로 남는다"


# ── 2. 그래서 응답이 도착한다 ───────────────────────────────────────────

def test_unicast_reply_reaches_the_current_socket_after_reconfigure(window):
    """이 시험이 이 버그의 본체다.

    장치가 유니캐스트로 답할 때, socket_config() 를 여러 번 부른 뒤에도 응답을
    받아야 한다. 소켓이 쌓이면 응답은 가장 먼저 바인드된(아무도 안 읽는) 소켓으로 간다.
    """
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, bind="127.0.0.1") as dev:
        window._loopback_holder["peer_port"] = dev.port
        for _ in range(4):
            window.socket_config()
        profile = ask(window.conf_sock)
    assert dev.replies, "가짜 장치가 응답을 보내지 않았다 — 시험 설정 오류"
    assert profile.get("MC") == MAC, "응답이 현재 소켓으로 오지 않았다 (소켓 쌓임)"


def test_broadcast_reply_would_have_hidden_the_bug(window):
    """실기기가 브로드캐스트로 답해 이 결함이 가려졌다는 것을 못 박아 둔다.
    같은 조건에서 브로드캐스트 응답이면 쌓여 있어도 도착한다."""
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, bind="127.0.0.1",
                         reply_broadcast=False) as dev:
        window._loopback_holder["peer_port"] = dev.port
        window.socket_config()
        assert ask(window.conf_sock).get("MC") == MAC


# ── 3. GPIO 주기 갱신이 설정 소켓을 물지 않는다 ─────────────────────────

def test_gpio_refresh_uses_its_own_socket(window):
    """DataRefresh 가 conf_sock 을 공유하면 socket_config() 가 그 소켓을 닫을 때
    돌고 있던 갱신이 죽는다. 개별 조회처럼 전용 소켓을 쓴다."""
    window.socket_config()
    window.curr_dev = "WIZ752SR-12x"
    window.curr_ver = "2.1.0dev"
    window.intv_time = 0
    window.refresh_gpio(MAC)
    assert window.datarefresh is not None, "DataRefresh 가 만들어지지 않았다"
    try:
        assert window.datarefresh.sock is not window.conf_sock, "설정 소켓을 공유한다"
    finally:
        window.datarefresh.terminate()
        window.datarefresh.wait(500)
        window._close_datarefresh_sock()


def test_closing_the_conf_socket_twice_is_harmless(window):
    """정리 경로가 여러 곳에 있어 두 번 닫힐 수 있다. 예외로 번지면 안 된다."""
    window.socket_config()
    window._close_conf_sock()
    window._close_conf_sock()
    assert window.conf_sock is None
