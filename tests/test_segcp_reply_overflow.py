#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WIZ752 검색 응답 512B 초과 — 요청을 나눠 응답 크기를 구조적으로 낮춘다.

배경: TASKS.md `BUG-WIZ752-SEARCH-OVERFLOW`. 2026-08-31~09-01 실측.
장치 응답 버퍼 gSEGCPREP 는 512B 인데 펌웨어가 길이를 대조하지 않는다.
64개 커맨드를 한 번에 물으면 응답이 515~531B 로 넘쳐 인접 메모리를 밟는다.

여기서 고정하는 것
  1. 가짜 장치가 실측(531B/515B)을 재현한다 — 아니면 아래 시험은 의미가 없다
  2. 한 번에 묻는 기존 방식은 초과한다 (문제의 재현)
  3. search_chunks() 가 커맨드를 빠뜨리거나 겹치지 않는다
  4. 청크별 응답이 도메인 39자에서도 버퍼의 3/4 아래다
  5. 핸들러가 청크 응답을 모아 한 번에 emit 하고, 유실 시 한 번 재송신하며,
     끝내 못 받으면 emit 하지 않는다
  6. 잘린 응답의 꼬리 조각을 버리고, 버퍼에 닿은 응답에 경고를 남긴다
"""

import logging

import pytest

from constants import Opcode
from tests.fake_segcp_device import (
    PROFILE_WIZ752_MEASURED, FakeSegcpDevice, expected_reply_len,
    profile_with_domain, profile_with_remote_host,
)
from WIZMakeCMD import WIZMakeCMD, cmd_ch1, cmd_ch2
from WIZMSGHandler import WIZMSGHandler, parse_reply_lines
from WIZUDPSock import WIZUDPSock

MAC = "00:08:DC:84:14:27"
DEV = "WIZ752SR-12x"
VER = "2.1.0dev"
CMDS_64 = cmd_ch1 + cmd_ch2 + ["S0", "S1", "SC"]     # 브랜치 861154c 의 cmd_2p_default
CMDS_EXPECTED = set(cmd_ch1 + cmd_ch2 + ["SC"])     # 분할 후 물어야 하는 것 (S0/S1 은 소비처 없음)
REPLY_BUF = 512


# ── 헬퍼 ────────────────────────────────────────────────────────────────

@pytest.fixture
def local_sock():
    """루프백에 바인드된 설정툴 소켓. peer 는 테스트가 나중에 정한다."""
    s = WIZUDPSock(0, 0, "127.0.0.1", localport=0, peer_ip="127.0.0.1")
    s.open()
    yield s
    s.close()


def request_bytes(sock, cmd_list) -> bytes:
    """production 빌더(makecommands)로 요청 바이트를 만든다."""
    th = WIZMSGHandler(sock, cmd_list, "udp", Opcode.OP_SEARCHALL, 0.1)
    th.makecommands()
    return bytes(th.msg[:th.size])


def run_device_query(dev: FakeSegcpDevice, chunks, *, timeout=0.5, reply_limit=None):
    """핸들러 run() 을 현재 스레드에서 동기 실행하고 emit 된 바이트를 돌려준다."""
    sock = WIZUDPSock(0, dev.port, "127.0.0.1", localport=0, peer_ip="127.0.0.1")
    sock.open()
    try:
        th = WIZMSGHandler.for_device_query(sock, chunks, "udp", timeout, reply_limit=reply_limit)
        got = []
        th.searched_data.connect(got.append)
        th.run()
        return got
    finally:
        sock.close()


def chunks_752():
    return WIZMakeCMD().search_chunks(MAC, " ", DEV, VER, "OPEN")


# ── 1. 가짜 장치 보정 ─────────────────────────────────────────────────

def test_fake_reproduces_measured_531B_reply(local_sock):
    """도메인 20자 프로파일 + 64개 요청 → 실측 531B (2026-09-01)."""
    assert expected_reply_len(PROFILE_WIZ752_MEASURED, CMDS_64) == 531
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    cmd_list = WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]
    reply = dev.build_reply(request_bytes(local_sock, cmd_list))
    assert reply is not None
    assert len(reply) == 531


def test_fake_reproduces_measured_515B_with_ip_remote_host(local_sock):
    """Remote host 를 IP(12자) 로 두면 515B (2026-08-31 실측)."""
    prof = profile_with_remote_host(PROFILE_WIZ752_MEASURED, "192.168.11.3")
    assert expected_reply_len(prof, CMDS_64) == 515
    dev = FakeSegcpDevice(prof, mac=MAC)
    cmd_list = WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]
    assert len(dev.build_reply(request_bytes(local_sock, cmd_list))) == 515


def test_fake_ignores_request_for_other_mac(local_sock):
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    other = WIZMakeCMD().make_header("00:08:DC:00:00:01", " ") + [["MC", ""]]
    assert dev.build_reply(request_bytes(local_sock, other)) is None


# ── 2. 문제의 재현 ─────────────────────────────────────────────────────

def test_single_request_of_64_commands_overflows_device_buffer(local_sock):
    """한 번에 묻는 기존 방식: 531+NUL = 532 를 512 버퍼에 써서 20B 초과."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, reply_buf_size=REPLY_BUF)
    cmd_list = WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]
    dev.build_reply(request_bytes(local_sock, cmd_list))
    assert dev.overflow_events == [(0, 20)]


# ── 3. search_chunks 구성 ──────────────────────────────────────────────

def test_search_chunks_for_two_port_device_covers_every_command_exactly_once():
    chunks = chunks_752()
    assert len(chunks) >= 2
    for ch in chunks:
        assert ch[0][0] == "MA" and ch[1][0] == "PW", "청크마다 MA/PW 헤더"
        assert "MC" in [c for c, _ in ch[2:]], "청크마다 MC (응답 병합 키)"
    body = [c for ch in chunks for c, _ in ch[2:] if c != "MC"]
    assert len(body) == len(set(body)), f"중복 커맨드: {sorted(set(c for c in body if body.count(c) > 1))}"
    assert set(body) | {"MC"} == CMDS_EXPECTED, (
        f"누락 {sorted(CMDS_EXPECTED - set(body) - {'MC'})} / 초과 {sorted(set(body) - CMDS_EXPECTED)}"
    )


def test_search_chunks_for_one_port_device_is_single_chunk_identical_to_search():
    mk = WIZMakeCMD()
    for dev, ver in (("WIZ750SR", "1.2.4"), ("WIZ750SR", "1.0.0"), ("WIZ107SR", "4.06"), ("WIZ5XXSR-RP", "1.1.1")):
        assert mk.search_chunks(MAC, " ", dev, ver, "OPEN") == [mk.search(MAC, " ", dev, ver, "OPEN")]


# ── 4. 청크별 응답 크기 ────────────────────────────────────────────────

@pytest.mark.parametrize("domain_len", [12, 20, 39])
def test_chunked_replies_stay_below_three_quarters_of_buffer(local_sock, domain_len):
    """도메인 39자(구조체 dns_domain_name[40] 상한)에서도 청크당 응답 ≤ 384B."""
    prof = profile_with_domain(PROFILE_WIZ752_MEASURED, domain_len)
    dev = FakeSegcpDevice(prof, mac=MAC, reply_buf_size=REPLY_BUF)
    sizes = [len(dev.build_reply(request_bytes(local_sock, ch))) for ch in chunks_752()]
    assert max(sizes) <= REPLY_BUF * 3 // 4, f"청크 응답 크기 {sizes}"
    assert dev.overflow_events == []


# ── 5. 핸들러: 청크 순차 송신·병합·재송신 ───────────────────────────────

def test_parse_reply_lines_skips_MA_and_maps_command_to_value():
    data = b"MA\x00\x08\xdc\x84\x14\x27\r\nPW \r\nMC00:08:DC:84:14:27\r\nRH\r\nSC00\r\n"
    assert parse_reply_lines(data) == {"PW": " ", "MC": "00:08:DC:84:14:27", "RH": "", "SC": "00"}


def test_handler_merges_chunk_replies_into_one_full_profile():
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC) as dev:
        got = run_device_query(dev, chunks_752())
        assert len(got) == 1, "청크가 몇 개든 emit 은 한 번"
        prof = parse_reply_lines(got[0])
        assert set(prof) >= CMDS_EXPECTED
        assert prof["RH"] == "test-server-01.local"
        assert prof["QH"] == "test-server-01.local"
        assert prof["MC"] == MAC
        assert dev.overflow_events == []
        assert len(dev.requests) == len(chunks_752())


def test_handler_resends_chunk_once_when_reply_is_lost():
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, drop_first=1) as dev:
        got = run_device_query(dev, chunks_752(), timeout=0.3)
        assert len(got) == 1
        assert set(parse_reply_lines(got[0])) >= CMDS_EXPECTED
        assert len(dev.requests) == len(chunks_752()) + 1, "유실 청크 1회 재송신"


def test_handler_emits_nothing_when_a_chunk_stays_unanswered(caplog):
    caplog.set_level(logging.WARNING, logger="wizconfig")
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, drop_first=2) as dev:
        got = run_device_query(dev, chunks_752(), timeout=0.2)
        assert got == [], "반쪽 프로파일로 화면을 채우지 않는다"
        assert "미완료" in caplog.text


# ── 6. 잘림·크기 경고 ─────────────────────────────────────────────────

def test_truncated_reply_tail_fragment_is_dropped_and_warned(caplog):
    """상한 있는 펌웨어가 511B 에서 자르면 마지막 줄이 조각으로 남는다. 값으로 읽으면 안 된다."""
    caplog.set_level(logging.WARNING, logger="wizconfig")
    big = [WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]]
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, mode="truncate") as dev:
        got = run_device_query(dev, big, reply_limit=REPLY_BUF)
        assert len(got) == 1
        data = got[0]
        assert data.endswith(b"\r\n")
        for k, v in parse_reply_lines(data).items():
            if k in PROFILE_WIZ752_MEASURED:
                assert v == PROFILE_WIZ752_MEASURED[k], f"{k} 가 잘린 값으로 들어옴: {v!r}"
        assert "조각" in caplog.text
        assert "[SIZE]" in caplog.text


def test_reply_reaching_buffer_size_logs_size_warning(caplog):
    """구형 펌웨어(초과해도 전부 보냄)에서 531B 가 오면 경고 — 사후 검출."""
    caplog.set_level(logging.WARNING, logger="wizconfig")
    big = [WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]]
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC) as dev:
        got = run_device_query(dev, big, reply_limit=REPLY_BUF)
        assert len(got) == 1 and len(got[0]) == 531
        assert "[SIZE]" in caplog.text and "531" in caplog.text


def test_no_size_warning_without_reply_limit(caplog):
    """버퍼 크기를 모르는 장치에는 경고를 내지 않는다 — 틀린 경고가 없는 것보다 나쁘다."""
    caplog.set_level(logging.WARNING, logger="wizconfig")
    big = [WIZMakeCMD().make_header(MAC, " ") + [[c, ""] for c in CMDS_64]]
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC) as dev:
        run_device_query(dev, big, reply_limit=None)
        assert "[SIZE]" not in caplog.text


# ── 7. spec: 응답 버퍼 크기는 아는 장치에만 적는다 ──────────────────────

@pytest.mark.parametrize("device", ["WIZ752SR-12x", "WIZ750SR", "WIZ750SR-1xx"])
def test_w7500_family_spec_declares_512B_config_buffer(device):
    """W7500 계열 펌웨어의 CONFIG_BUF_SIZE 는 512 (common.h). spec 에 그대로 적는다."""
    from device_spec_loader import load_device
    assert load_device(device).fw_config.config_buf_size == 512


def test_other_device_spec_leaves_config_buffer_unknown():
    """모르는 값은 0(미지정) — 그 장치에는 크기 경고를 내지 않는다."""
    from device_spec_loader import load_device
    assert load_device("WIZ5XXSR-RP").fw_config.config_buf_size == 0


# ── 8. GUI 배선: search_each_dev 가 청크 조회로 전체 프로파일을 채운다 ──────

def test_gui_search_each_dev_fills_full_profile_through_chunks(qapp, monkeypatch):
    """main_gui.search_each_dev → for_device_query → getsearch_each_dev 경로 통합 확인.

    WIZUDPSock 을 루프백 전용으로 바꿔 끼워 가짜 장치에 붙인다. 창은 오프스크린.
    """
    import main_gui

    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC) as dev:
        class LoopbackSock(main_gui.WIZUDPSock):
            def __init__(self, port, peerport, ipaddr=None, localport=52000, peer_ip=None):
                super().__init__(port, dev.port, "127.0.0.1", localport=localport, peer_ip="127.0.0.1")

        monkeypatch.setattr(main_gui, "WIZUDPSock", LoopbackSock)
        w = main_gui.WIZWindow()
        w.broadcast.setChecked(True)
        w.unicast_ip.setChecked(False)
        w.search_wait_time_each = 0.5

        w.search_each_dev([(MAC, DEV, VER, "OPEN")])

        prof = w.dev_profile.get(MAC)
        assert prof is not None, "프로파일이 안 채워짐 — 배선 문제"
        assert set(prof) >= CMDS_EXPECTED
        assert prof["QH"] == "test-server-01.local"
        assert len(dev.requests) == len(chunks_752()), "청크 수만큼 요청"
        assert dev.overflow_events == []


# ── 9. presearch(Phase 1) 경로는 그대로다 — run() 정리 후 회귀 방지 ─────────

def test_presearch_path_still_lists_device(qapp):
    """브로드캐스트 검색(presearch=True)은 분할과 무관. MC/MN/VR/ST 를 목록에 올린다."""
    from WIZMakeCMD import cmd_presearch
    with FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC) as dev:
        sock = WIZUDPSock(0, dev.port, "127.0.0.1", localport=0, peer_ip="127.0.0.1")
        sock.open()
        try:
            cmd_list = WIZMakeCMD().presearch("FF:FF:FF:FF:FF:FF", " ")
            th = WIZMSGHandler(sock, cmd_list, "udp", Opcode.OP_SEARCHALL, 0.5, presearch=True)
            found = []
            th.search_result.connect(found.append)
            th.run()
        finally:
            sock.close()
        assert found == [1]
        assert th.mac_list == [MAC.encode()]
        assert th.mn_list == ["WIZ752SR-12x"]
        assert th.vr_list == [b"2.1.0dev"]
        assert [c for c, _ in cmd_list[2:]] == cmd_presearch


# ── 10. 가짜 장치 응답 목적지 — 펌웨어는 보낸 포트로 브로드캐스트한다 ────────

def test_fake_replies_by_broadcast_to_sender_port_like_firmware():
    """segcp.c:1443 sendto(..., "\xFF\xFF\xFF\xFF", destport). 유니캐스트면 툴의 겹친 포트 5000 소켓 중
    가장 오래된 것만 받아 실기기에서 안 나는 'no response' 가 난다 (2026-09-03 실측)."""
    fw_like = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, reply_broadcast=True)
    assert fw_like.reply_target(("192.168.7.2", 5000)) == ("255.255.255.255", 5000)
    loopback = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    assert loopback.reply_target(("127.0.0.1", 61234)) == ("127.0.0.1", 61234)


def test_fake_profile_has_user_io_defaults_for_datarefresh():
    """DataRefresh 는 CA~CD/GA~GD 를 따로 묻는다. 없으면 User I/O 탭이 비어 보인다."""
    for k in ("CA", "CB", "CC", "CD", "GA", "GB", "GC", "GD"):
        assert k in PROFILE_WIZ752_MEASURED
