#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 SEGCP 장치의 동작을 고정한다.

이 파일은 설정툴이 아니라 **시험 도구 자체**를 시험한다. 가짜 장치가 실기기와
다르게 굴면 그 위에서 돌린 시험 결과가 전부 무의미해지기 때문이다.

기본값은 무해한 쪽으로 둔다 — 거부·리부트·DNS 지연은 전부 꺼져 있고, 시험이
필요할 때만 FirmwareQuirks 로 켠다. 단독 실행(수동 시험) 중에 없던 오류가
생기지 않게 하려는 것이다.
"""

import time

from tests.fake_segcp_device import (
    FW_752_2_1_0DEV, FW_752_FIX_BRANCH, PROFILE_WIZ752_MEASURED,
    FakeSegcpDevice, FirmwareQuirks, make_device_fleet, profile_with_remote_host,
)
from WIZMakeCMD import WIZMakeCMD
from WIZMSGHandler import parse_reply_lines

MAC = "00:08:DC:FA:CE:01"
OTHER_MAC = "00:08:DC:84:14:27"


def req(mac, pairs, code=" "):
    """MA + PW + (커맨드, 값) 목록을 SEGCP 요청 바이트로."""
    out = b"MA" + bytes.fromhex(mac.replace(":", "")) + b"\r\n" + b"PW" + code.encode() + b"\r\n"
    for cmd, val in pairs:
        out += cmd.encode() + val.encode() + b"\r\n"
    return out


def get(mac, cmds):
    return req(mac, [(c, "") for c in cmds])


# ── 1. 로그: 정상 트래픽과 진짜 이상을 구분한다 ──────────────────────────

def test_request_addressed_to_another_device_is_reported_as_normal_traffic():
    """설정툴은 모든 요청을 255.255.255.255 로 뿌린다. 남의 MAC 앞으로 온 요청을 받는 것은
    정상이지 오류가 아니다. 어느 장치 앞으로 온 것인지도 알려준다."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    verdict = dev.classify(get(OTHER_MAC, ["MC", "VR"]))
    assert verdict.answered is False
    assert verdict.kind == "other-device"
    assert verdict.target_mac == OTHER_MAC
    assert "오류" not in verdict.note and "mismatch" not in verdict.note.lower()
    assert OTHER_MAC in verdict.note


def test_malformed_request_is_reported_separately_from_normal_traffic():
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    verdict = dev.classify(b"hello world\r\n")
    assert verdict.answered is False
    assert verdict.kind == "malformed"
    assert verdict.target_mac is None


def test_broadcast_and_own_mac_are_answered():
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    for mac in (MAC, "FF:FF:FF:FF:FF:FF"):
        v = dev.classify(get(mac, ["MC"]))
        assert v.answered is True and v.kind == "answered", mac


# ── 2. RH/QH 는 장치에서 한 필드다 (2026-09-01 양방향 실측) ───────────────

def test_second_domain_in_the_same_packet_wins_like_the_real_device():
    """FW 의 dns_domain_name[40] 은 하나뿐이고 RH·QH 핸들러가 둘 다 거기 쓴다.
    한 패킷에 RH 가 앞, QH 가 뒤라 뒤가 이긴다."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    dev.build_reply(req(MAC, [("RH", "test-server-01.local"), ("QH", "192.168.11.3")]))
    assert dev.profile["RH"] == "192.168.11.3"
    assert dev.profile["QH"] == "192.168.11.3"

    dev.build_reply(req(MAC, [("RH", "192.168.11.3"), ("QH", "test-server-01.local")]))
    assert dev.profile["RH"] == "test-server-01.local"
    assert dev.profile["QH"] == "test-server-01.local"


def test_shared_domain_can_be_turned_off_for_a_device_that_keeps_two():
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC,
                          quirks=FirmwareQuirks(shared_domain=False))
    dev.build_reply(req(MAC, [("RH", "a.local"), ("QH", "b.local")]))
    assert dev.profile["RH"] == "a.local" and dev.profile["QH"] == "b.local"


def test_domain_longer_than_the_field_is_cut_at_the_field_boundary():
    """`strcpy(dns_domain_name, param)` 에 경계가 없다. char[40] 이므로 NUL 자리를 빼면 39자."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    long_domain = "x" * 50 + ".local"
    dev.build_reply(req(MAC, [("RH", long_domain)]))
    assert len(dev.profile["RH"]) == 39
    assert dev.profile["RH"] == long_domain[:39]
    assert dev.field_overflows == [("RH", len(long_domain), 40)]


# ── 3. 거부(ER) — 기본은 꺼져 있고 시험이 켠다 ─────────────────────────────

def test_by_default_nothing_is_rejected():
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC)
    prof = parse_reply_lines(dev.build_reply(req(MAC, [("BR", "99"), ("MC", "")])))
    assert "ER" not in prof
    assert prof["MC"] == MAC


def test_rejected_command_emits_ER_line_and_stops_the_rest_of_the_packet():
    """현재 FW: 에러가 나면 `ERINVALIDPARAM:BR` 을 쓰고 proc_SEGCP 가 즉시 return 한다.
    그래서 뒤에 붙은 조회도 SV/RT 도 처리되지 않는다(설정이 통째로 무산)."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, quirks=FW_752_2_1_0DEV)
    dev.reject = {"BR": "INVALIDPARAM"}
    reply = dev.build_reply(req(MAC, [("LP", "5000"), ("BR", "99"), ("QL", "6001"), ("SV", ""), ("MC", "")]))
    prof = parse_reply_lines(reply)
    assert prof["ER"] == "INVALIDPARAM:BR"
    assert "MC" not in prof, "에러 뒤 커맨드는 처리되지 않는다"
    assert dev.profile["LP"] == "5000", "에러 앞 커맨드는 반영된다"
    assert dev.profile["QL"] == "5001", "에러 뒤 SET 도 반영되지 않는다 (기본값 5001 그대로)"
    assert dev.saved is False, "SV 가 스킵돼 저장되지 않는다"


def test_fixed_branch_drops_ER_in_tool_mode_and_keeps_processing():
    """fix/user-io-and-segcp: 오류 응답이 AT 모드 안으로 들어가 설정툴은 ER 을 못 받는다.
    대신 뒤 커맨드와 SV 는 처리된다. 거부됐는데도 성공으로 보이는 것이 이 수정의 부작용이다."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC, quirks=FW_752_FIX_BRANCH)
    dev.reject = {"BR": "INVALIDPARAM"}
    prof = parse_reply_lines(dev.build_reply(req(MAC, [("BR", "99"), ("QL", "6001"), ("SV", ""), ("MC", "")])))
    assert "ER" not in prof, "설정툴 모드에서는 ER 이 생성되지 않는다"
    assert prof["MC"] == MAC, "뒤 커맨드는 처리된다"
    assert dev.profile["QL"] == "6001", "거부된 커맨드 뒤에도 SET 이 반영된다"
    assert dev.saved is True


# ── 4. SV/RT — 저장과 리부트 ────────────────────────────────────────────

def test_reboot_makes_the_device_unresponsive_for_the_configured_window():
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=MAC,
                          quirks=FirmwareQuirks(reboot_sec=0.4))
    assert dev.build_reply(req(MAC, [("SV", ""), ("RT", ""), ("MC", "")])) is not None
    assert dev.classify(get(MAC, ["MC"])).kind == "rebooting"
    time.sleep(0.45)
    assert dev.classify(get(MAC, ["MC"])).answered is True


def test_boot_dns_window_applies_only_when_channel0_is_not_tcp_server():
    """`main.c` 는 while(1) 진입 전에 process_dns() 를 돌린다. 조건은 채널0 이 TCP Server 가
    아니고 도메인을 쓸 때. 그동안 do_segcp() 가 돌지 않아 검색에 안 잡힌다."""
    quirks = FirmwareQuirks(reboot_sec=0.05, dns_block_sec=0.4)
    domain = profile_with_remote_host(PROFILE_WIZ752_MEASURED, "test-server-02.local")

    server = FakeSegcpDevice(dict(domain, OP="1"), mac=MAC, quirks=quirks)   # 채널0 TCP Server
    server.build_reply(req(MAC, [("RT", "")]))
    time.sleep(0.1)
    assert server.classify(get(MAC, ["MC"])).answered is True, "Server 모드는 DNS 창이 없다"

    client = FakeSegcpDevice(dict(domain, OP="0"), mac=MAC, quirks=quirks)   # 채널0 TCP Client
    client.build_reply(req(MAC, [("RT", "")]))
    time.sleep(0.1)
    assert client.classify(get(MAC, ["MC"])).kind == "rebooting", "도메인 해석 동안 무응답"
    time.sleep(0.4)
    assert client.classify(get(MAC, ["MC"])).answered is True


def test_ip_remote_host_has_no_dns_window():
    quirks = FirmwareQuirks(reboot_sec=0.05, dns_block_sec=0.4)
    ip = profile_with_remote_host(PROFILE_WIZ752_MEASURED, "192.168.11.3")
    dev = FakeSegcpDevice(dict(ip, OP="0"), mac=MAC, quirks=quirks)
    dev.build_reply(req(MAC, [("RT", "")]))
    time.sleep(0.1)
    assert dev.classify(get(MAC, ["MC"])).answered is True


# ── 5. 여러 대 ─────────────────────────────────────────────────────────

def test_device_fleet_gets_distinct_macs_and_names():
    fleet = make_device_fleet(3, PROFILE_WIZ752_MEASURED)
    macs = [d.profile["MC"] for d in fleet]
    assert macs == ["00:08:DC:FA:CE:01", "00:08:DC:FA:CE:02", "00:08:DC:FA:CE:03"]
    assert len(set(macs)) == 3
    for d in fleet:
        assert d.build_reply(get(d.profile["MC"], ["MC"])) is not None
        assert d.classify(get(macs[0], ["MC"])).answered is (d.profile["MC"] == macs[0])


# ── 6. 회귀: 검색 응답 크기가 그대로여야 한다 ────────────────────────────

def test_search_reply_sizes_are_unchanged_by_these_additions():
    """가짜 장치를 손보면서 실측 재현이 깨지지 않았는지 — 여기가 깨지면 다른 시험이 다 무의미하다."""
    dev = FakeSegcpDevice(PROFILE_WIZ752_MEASURED, mac=OTHER_MAC)
    chunks = WIZMakeCMD().search_chunks(OTHER_MAC, " ", "WIZ752SR-12x", "2.1.0dev", "OPEN")
    sizes = [len(dev.build_reply(get(OTHER_MAC, [c for c, _ in ch[2:]]))) for ch in chunks]
    assert sizes == [250, 148, 195]
    assert dev.overflow_events == []
