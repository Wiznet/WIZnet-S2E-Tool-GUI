#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 WIZ1x0SR 장치의 동작을 고정한다.

`dev/feat-wiz1x0-direct-1461` 이 실장비 없이 develop 에 들어가 있다. 그 경로를
장비 없이 돌리려고 만든 응답기이고, 여기서는 그 응답기가 설정툴이 이해하는 형태로
말하는지 확인한다.
"""

from tests.fake_wiz1x0_device import DEFAULT_BOARD, PACKET_SIZE, FakeWiz1x0Device
from WIZ1x0Profile import BOARD_INFO_SIZE, build_find, build_sett, parse_imin

MAC = "00:08:DC:1A:00:01"


# ── 1. 검색(FIND/IMIN) ──────────────────────────────────────────────────

def test_find_reply_is_a_complete_imin_packet():
    dev = FakeWiz1x0Device(mac=MAC)
    reply = dev.build_reply(build_find())
    assert reply is not None
    assert reply[:4] == b"IMIN"
    assert len(reply) == PACKET_SIZE == 4 + BOARD_INFO_SIZE
    parsed = parse_imin(reply)
    assert parsed is not None, "설정툴이 응답을 해석하지 못한다"
    assert parsed["mac"] == MAC
    assert parsed["ip"] == DEFAULT_BOARD["ip"]


def test_default_board_is_not_filtered_out_as_wiz120sr():
    """설정툴은 PPPoE_ID 첫 바이트가 1~9면 WIZ120SR 로 보고 목록에서 뺀다."""
    dev = FakeWiz1x0Device(mac=MAC)
    reply = dev.build_reply(build_find())
    assert not (1 <= reply[4 + 103] <= 9), "기본 장치가 WIZ120SR 로 걸러진다"
    assert parse_imin(reply) is not None


def test_short_or_unknown_request_is_not_answered():
    dev = FakeWiz1x0Device(mac=MAC)
    assert dev.build_reply(b"FI") is None
    assert dev.build_reply(b"NOPE") is None
    assert dev.classify(b"NOPE").kind == "unsupported"
    assert dev.classify(b"SETT" + b"\x00" * 10).kind == "malformed"


# ── 2. 설정(SETT/SETC) ──────────────────────────────────────────────────

def test_sett_applies_the_new_board_and_answers_setc():
    dev = FakeWiz1x0Device(mac=MAC)
    new_board = dict(DEFAULT_BOARD, mac=MAC, ip="192.168.7.99", myport=6000)
    reply = dev.build_reply(build_sett(new_board))
    assert reply[:4] == b"SETC"
    assert dev.board["ip"] == "192.168.7.99"
    assert dev.board["myport"] == 6000
    assert dev.reboots == 1
    later = parse_imin(dev.build_reply(build_find()))
    assert later["ip"] == "192.168.7.99", "이후 검색에도 반영된다"


def test_setc_can_carry_the_board_so_the_tool_can_refresh_from_it():
    """설정툴은 SETC 가 163B 이상이면 그것을 파싱해 프로파일을 갱신한다."""
    dev = FakeWiz1x0Device(mac=MAC)
    reply = dev.build_reply(build_sett(dict(DEFAULT_BOARD, mac=MAC, ip="10.0.0.7")))
    assert len(reply) >= 4 + BOARD_INFO_SIZE
    assert parse_imin(b"IMIN" + reply[4:])["ip"] == "10.0.0.7"


def test_short_setc_exercises_the_tools_fallback_path():
    """짧은 SETC 도 성공이다. 설정툴은 그때 보낸 값으로 프로파일을 갱신한다.
    실장비가 어느 쪽인지는 확인하지 못해 양쪽을 다 시험한다."""
    dev = FakeWiz1x0Device(mac=MAC, setc_carries_board=False)
    reply = dev.build_reply(build_sett(dict(DEFAULT_BOARD, mac=MAC)))
    assert reply == b"SETC"


def test_factory_reset_restores_the_default_board():
    dev = FakeWiz1x0Device(mac=MAC)
    dev.build_reply(build_sett(dict(DEFAULT_BOARD, mac=MAC, ip="10.0.0.7")))
    dev.factory_reset()
    assert dev.board["ip"] == DEFAULT_BOARD["ip"]


# ── 3. 설정툴 스레드와 왕복 ─────────────────────────────────────────────

def test_searcher_thread_finds_the_fake_device(qapp, monkeypatch):
    """브로드캐스트 검색(UDP 1460 → 5001) 왕복. 실장비 포트를 건드리지 않게 옮겨 쓴다."""
    import WIZ1x0MSGHandler as H
    monkeypatch.setattr(H, "WIZ1X0_SEARCH_PORT", 14600)
    monkeypatch.setattr(H, "WIZ1X0_SEARCH_SPORT", 15001)
    with FakeWiz1x0Device(mac=MAC, bind="0.0.0.0", port=14600, serve_direct=False):
        th = H.WIZ1x0Searcher(repeat=2, timeout=0.5)
        found = []
        th.search_done.connect(found.append)
        th.run()
    assert found and found[0], "검색 스레드가 장치를 못 찾았다"
    macs = [mac for mac, _ in found[0]]
    assert MAC in macs, macs


def test_direct_searcher_thread_finds_the_device_over_tcp(qapp, monkeypatch):
    """직접-IP 검색(TCP 1461). develop 에 들어갔지만 실장비 검증이 없던 경로다."""
    import WIZ1x0MSGHandler as H
    monkeypatch.setattr(H, "WIZ1X0_DIRECT_PORT", 14610)
    with FakeWiz1x0Device(mac=MAC, bind="127.0.0.1", port=0, direct_port=14610):
        th = H.WIZ1x0DirectSearcher("127.0.0.1", timeout=1.5)
        found = []
        th.search_done.connect(found.append)
        th.run()
    assert found and found[0], "직접 검색이 장치를 못 찾았다"
    mac, parsed = found[0][0]
    assert mac == MAC
    assert parsed["ip"] == DEFAULT_BOARD["ip"]


def test_direct_searcher_emits_once_even_when_nothing_answers(qapp, monkeypatch):
    """계약: 어떤 경로에서도 정확히 1회 emit. 응답이 없어도 UI 가 멈추면 안 된다."""
    import WIZ1x0MSGHandler as H
    monkeypatch.setattr(H, "WIZ1X0_DIRECT_PORT", 14611)   # 아무도 안 듣는 포트
    th = H.WIZ1x0DirectSearcher("127.0.0.1", timeout=0.5)
    found = []
    th.search_done.connect(found.append)
    th.run()
    assert found == [[]], f"1회 emit 계약 위반: {found}"


def test_setter_thread_reports_success_on_setc(qapp, monkeypatch):
    import WIZ1x0MSGHandler as H
    monkeypatch.setattr(H, "WIZ1X0_SEARCH_PORT", 14602)
    monkeypatch.setattr(H, "WIZ1X0_SEARCH_SPORT", 15002)
    board = dict(DEFAULT_BOARD, mac=MAC, ip="192.168.7.61")
    with FakeWiz1x0Device(mac=MAC, bind="0.0.0.0", port=14602, serve_direct=False) as dev:
        th = H.WIZ1x0Setter("127.0.0.1", board, timeout=1.5)
        done = []
        th.set_done.connect(lambda ok, resp: done.append((ok, resp)))
        th.run()
        assert dev.reboots == 1, "장치가 설정을 받고 리부트했다"
    assert done and done[0][0] is True, f"설정 실패로 보고됨: {done}"
    assert done[0][1][:4] == b"SETC"
