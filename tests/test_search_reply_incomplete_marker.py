#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검색 응답의 끝부분이 빠졌을 때 목록에 ⓘ 와 안내문을 단다 (기종 무관)."""

import pytest
from PyQt5 import QtGui

from spec_analysis import missing_tail


# ── 순수 함수 ────────────────────────────────────────────────────────────

def test_missing_tail_only_counts_trailing_gap():
    assert missing_tail(["A", "B", "C", "D"], {"A": "1", "B": "2"}) == ["C", "D"]
    assert missing_tail(["A", "B", "C", "D"], {"A": "1", "C": "3", "D": "4"}) == []   # 중간 누락은 세지 않는다
    assert missing_tail(["A", "B", "C"], {"A": "1", "B": "2", "C": "3"}) == []
    assert missing_tail(["A", "B"], {}) == ["A", "B"]


def test_missing_tail_empty_value_counts_as_answered():
    assert missing_tail(["PI", "PP"], {"PI": "", "PP": " "}) == []


# ── 화면 ────────────────────────────────────────────────────────────────

@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


MAC = "00:08:DC:FA:CE:01"
REQ = [["MC", ""], ["VR", ""], ["MN", ""], ["PI", ""], ["PP", ""]]


def _setup_row(win):
    win.mac_list = [MAC.encode()]
    win.list_device.setRowCount(1)
    win.list_device.setItem(0, 0, main_gui_item(MAC))
    win._remember_requested(MAC, [[["MA", ""], ["PW", ""]] + REQ])


def main_gui_item(text):
    from PyQt5.QtWidgets import QTableWidgetItem
    return QTableWidgetItem(text)


def test_truncated_reply_marks_row_with_info_icon_and_tooltip(win):
    _setup_row(win)
    win._check_reply_complete(MAC, {"MC": MAC, "VR": "1.0", "MN": "X"})   # PI, PP 없음
    item = win.list_device.item(0, 0)
    assert not item.icon().isNull()
    tip = item.toolTip()
    assert "PI" in tip and "PP" in tip and "2개" in tip
    assert item.text() == MAC          # MAC 키로 쓰이는 텍스트는 건드리지 않는다


def test_complete_reply_has_no_mark_and_clears_a_previous_one(win):
    _setup_row(win)
    win._check_reply_complete(MAC, {"MC": MAC, "VR": "1.0"})
    assert not win.list_device.item(0, 0).icon().isNull()
    win._check_reply_complete(MAC, {"MC": MAC, "VR": "1.0", "MN": "X", "PI": "", "PP": " "})
    item = win.list_device.item(0, 0)
    assert item.icon().isNull() and item.toolTip() == ""


def test_mark_survives_row_rebuild(win):
    _setup_row(win)
    win._check_reply_complete(MAC, {"MC": MAC})
    win.list_device.setItem(0, 0, main_gui_item(MAC))     # 검색 때 행이 다시 만들어진다
    assert win.list_device.item(0, 0).icon().isNull()
    win._mark_reply_warnings()
    assert not win.list_device.item(0, 0).icon().isNull()


def test_device_without_recorded_request_is_never_flagged(win):
    win.mac_list = [MAC.encode()]
    win.list_device.setRowCount(1)
    win.list_device.setItem(0, 0, main_gui_item(MAC))
    win._check_reply_complete(MAC, {"MC": MAC})
    assert win.list_device.item(0, 0).icon().isNull()


def test_search_path_end_to_end_with_truncating_4port_fake(win):
    """실제 조회 요청 → 4port 가짜 장치(문자열 전부 최대라 1,792B 초과) → getsearch_each_dev."""
    from tests.fake_segcp_device import (
        FW_4PORT, FakeSegcpDevice, profile_from_spec, tool_asked_commands)
    dev = "W55RP20-S2E-4CH"
    prof = profile_from_spec(dev, mac=MAC, fw_version="1.2.4",
                             include=tool_asked_commands(dev, "1.2.4", MAC))
    for c in ("RH", "QH", "GH", "CH"):
        prof[c] = "a" * 63 + "." + "a" * 63
    prof["DH"] = "d" * 19
    prof["PI"] = prof["PP"] = "p" * 63
    for c in ("SD", "DD", "SE", "RD", "RF", "EE", "XD", "XF", "WE", "ZD", "ZF", "YE"):
        prof[c] = "s" * 31
    fake = FakeSegcpDevice(prof, mac=MAC, quirks=FW_4PORT)

    chunks = win.wizmakecmd.search_chunks(MAC, " ", dev, "1.2.4", "OPEN")
    win.mac_list = [MAC.encode()]
    win.list_device.setRowCount(1)
    win.list_device.setItem(0, 0, main_gui_item(MAC))
    win._remember_requested(MAC, chunks)
    body = b"".join(c.encode() + p.encode() + b"\r\n" for c, p in chunks[0][2:])
    reply = fake.build_reply(b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body)

    win.getsearch_each_dev(reply)
    item = win.list_device.item(0, 0)
    assert not item.icon().isNull(), "잘린 응답인데 ⓘ 가 없다"

    # 대조: 같은 장치가 기본값이면 응답이 온전해 표시가 없다
    win.reply_warnings.clear()
    win._mark_reply_warnings()
    ok = FakeSegcpDevice(profile_from_spec(dev, mac=MAC, fw_version="1.2.4",
                         include=tool_asked_commands(dev, "1.2.4", MAC)), mac=MAC, quirks=FW_4PORT)
    win.getsearch_each_dev(ok.build_reply(b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body))
    assert win.list_device.item(0, 0).icon().isNull()
