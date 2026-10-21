#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 장치가 4port 펌웨어(segcp.c)의 동작을 따르는지.

기대값은 전부 소스 읽기에서 나왔다(실기기 측정 아님). 근거 위치는 FirmwareQuirks 주석.
"""

from tests.fake_segcp_device import (
    FW_4PORT, FW_752_2_1_0DEV, FakeSegcpDevice, profile_from_spec, tool_asked_commands,
)
from WIZMakeCMD import WIZMakeCMD
from WIZMSGHandler import parse_reply_lines

MAC = "00:08:DC:FA:CE:01"
DEV = "W55RP20-S2E-4CH"


def _req(*cmds):
    body = b"".join((c if isinstance(c, str) else c).encode() + b"\r\n" for c in cmds)
    return b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body


def _dev(**kw):
    prof = profile_from_spec(DEV, mac=MAC, fw_version="1.2.4",
                             include=tool_asked_commands(DEV, "1.2.4", MAC))
    return FakeSegcpDevice(prof, mac=MAC, quirks=kw.pop("quirks", FW_4PORT), **kw)


def test_pppoe_id_64_chars_is_rejected_and_save_is_cancelled():
    d = _dev()
    d.build_reply(_req("PI" + "a" * 64, "SV"))
    assert d.profile.get("PI") != "a" * 64
    assert d.saved is False
    assert d.field_rejects == [("PI", 64, 63)]


def test_pppoe_id_63_chars_saves():
    d = _dev()
    d.build_reply(_req("PI" + "a" * 63, "SV"))
    assert d.profile["PI"] == "a" * 63 and d.saved is True


def test_remote_host_127_ok_128_rejected_per_channel_not_shared():
    d = _dev()
    d.build_reply(_req("RH" + "a" * 127, "QH" + "b" * 10))
    assert d.profile["RH"] == "a" * 127 and d.profile["QH"] == "b" * 10   # 채널별 별개 필드
    d.build_reply(_req("GH" + "c" * 128))
    assert d.profile["GH"] != "c" * 128


def test_error_does_not_stop_later_commands_but_cancels_save_and_reboot():
    d = _dev()
    d.build_reply(_req("PI" + "a" * 64, "NP1234", "SV", "RT"))
    assert d.profile["NP"] == "1234"        # 오류 뒤 명령도 RAM 에는 반영된다
    assert d.saved is False and d.reboots == 0


def test_gets_after_a_flag_get_no_reply():
    d = _dev()
    reply = d.build_reply(_req("SV", "MN"))
    assert b"MN" not in reply               # SV 뒤 확인 조회는 답이 없다
    assert b"MN" in d.build_reply(_req("MN"))


def test_empty_string_is_answered_as_one_space():
    d = _dev()
    d.profile["PI"] = ""
    prof_line = [l for l in d.build_reply(_req("PI")).split(b"\r\n") if l.startswith(b"PI")]
    assert prof_line == [b"PI "]


def test_space_clears_string_field():
    d = _dev()
    d.profile["PI"] = "abc"
    d.build_reply(_req("PI "))
    assert d.profile["PI"] == ""


def test_reply_stops_when_body_passes_buffer_minus_headroom():
    """검사는 명령 앞에서만 한다 — 선을 넘기 전 마지막 줄은 들어간다. 이후 명령은 버려진다."""
    d = _dev()
    d.profile["QH"] = "h" * 127
    cmds = ["QH"] * 20                       # 한 줄 131B → 14줄째에서 1792 초과
    reply = d.build_reply(_req(*cmds))
    n_lines = reply.count(b"QH")
    assert n_lines < 20 and d.dropped_cmds == 1
    assert len(reply) - 14 > 2048 - 256 - 1  # 본문이 선을 넘은 직후에 멈춘다
    assert d.overflow_events == []           # 버퍼는 넘지 않는다


def test_752_defaults_unchanged_by_new_quirks():
    """새 동작은 전부 기본 꺼짐 — 기존 기종 시험이 영향받지 않아야 한다."""
    q = FW_752_2_1_0DEV
    assert (q.reply_headroom, q.field_limits, q.err_cancels_save, q.flags_drop_gets,
            q.empty_as_space, q.space_clears_string, q.max_param_len) == (0, {}, False, False,
                                                                           False, False, 0)


def test_tool_search_on_4port_fake_is_not_truncated_with_default_values():
    """기본값 프로파일이면 툴의 전체 조회 응답에 모든 명령이 들어온다."""
    d = _dev()
    asked = tool_asked_commands(DEV, "1.2.4", MAC)
    chunks = WIZMakeCMD().search_chunks(MAC, " ", DEV, "1.2.4", "OPEN")
    got = {}
    for ch in chunks:
        got.update(parse_reply_lines(d.build_reply(_req(*[c for c, _ in ch[2:]]))))
    assert [c for c in asked if c not in got] == []


def test_fleet_config_accepts_the_4port_preset():
    from tests.fake_fleet import _quirks_from
    q = _quirks_from({"preset": "4port", "reboot_sec": 2.0})
    assert q.reply_headroom == 256 and q.reboot_sec == 2.0 and q.field_limits["PI"] == 63


def test_unimplemented_commands_answer_with_one_space_and_ignore_set():
    d = _dev()
    assert b"QU \r\n" in d.build_reply(_req("QU"))
    d.build_reply(_req("QUabc", "SV"))
    assert d.saved is True and d.profile.get("QU") != "abc"      # 오류 없이 무시


def _tool_set_request(cmd, value):
    lst = WIZMakeCMD().setcommand(MAC, " ", "", [cmd], [value], DEV, "1.2.4", "OPEN")
    body = b"".join(c.encode() + p.encode() + b"\r\n" for c, p in lst[2:])
    return b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body


def _fill_all_strings_to_max(d):
    for c in ("RH", "QH", "GH", "CH"):
        d.profile[c] = "a" * 63 + "." + "a" * 63
    d.profile["DH"] = "d" * 19
    d.profile["PI"] = d.profile["PP"] = "p" * 63
    for c in ("SD", "DD", "SE", "RD", "RF", "EE", "XD", "XF", "WE", "ZD", "ZF", "YE"):
        d.profile[c] = "s" * 31


def test_tool_apply_default_config_is_saved_and_rebooted():
    d = _dev()
    reply = d.build_reply(_tool_set_request("NP", "1234"))
    assert d.saved and d.reboots == 1 and b"MC" in reply


def test_tool_apply_with_every_string_at_max_loses_save_but_still_looks_successful():
    """툴이 보내는 'SET + 확인 GET + SV + RT' 에서 확인 GET 응답이 1,792B 를 넘으면 FW 는 SV/RT 를
    버린다. 응답에는 MC 가 있어 툴은 성공(len(MC)==17)으로 판단한다 — 소스 읽기 기반 시나리오.
    이 시험은 FW 동작을 '재현'해 두는 것이지 현 툴이 옳다는 보증이 아니다."""
    d = _dev()
    _fill_all_strings_to_max(d)
    reply = d.build_reply(_tool_set_request("NP", "1234"))
    assert d.profile["NP"] == "1234"          # RAM 에는 반영
    assert d.saved is False and d.reboots == 0  # 저장·재부팅은 안 됨
    assert parse_reply_lines(reply)["MC"] == MAC and len(parse_reply_lines(reply)["MC"]) == 17
