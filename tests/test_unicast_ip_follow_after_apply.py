#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TCP unicast 모드에서 Local IP 를 바꿔 Apply 한 뒤 접속 IP(search_ipaddr)가 따라가는가.

`BUG-UNICAST-IP-CHANGE-FAILS` 의 0e53dcd 는 "Apply 성공 뒤 dev_clicked() 가 SET 응답의
새 LI 로 search_ipaddr 을 옮긴다"에 기댄다. 그런데 SET 응답의 GET 확인 쿼리에 LI 가
없는 기종이 있다 — WIZ752SR-12x 의 `cmd_2p_setconfirm = ["MC"] + cmd_ch2` (WIZMakeCMD.py:104).
이 기종은 응답에 LI 가 없어 dev_profile LI 가 옛 값으로 남고, 접속 IP 도 옛 값에 머문다.

소켓 없이 설정툴의 실제 do_setting() → get_setting_result() → dev_clicked() 를 그대로 태운다.
WIZMSGHandler 만 가짜로 갈아 끼워, FakeSegcpDevice.build_reply() 가 만든 SET 응답 바이트를
set_result 시그널로 돌려준다(와이어 인코딩은 실제 WIZMakeCMD.setcommand() 결과 그대로).

기대 동작(수정 후): 보낸 LI 를 보관했다가 응답에 LI 가 없으면 그 값으로 채운다.
- test_premise_*              : 지금도 통과 — 전제(응답에 LI 가 없다/있다)를 고정한다.
- test_750_*                  : 지금도 통과 — 0e53dcd 가 LI 를 묻는 기종에서 제대로 따라감을 고정.
- test_752_*                  : 지금은 실패(xfail strict) — 수정이 들어가면 XPASS 로 바뀌어 알려준다.
"""
from types import SimpleNamespace

import pytest

from tests.fake_segcp_device import (
    PROFILE_WIZ752_MEASURED,
    FakeSegcpDevice,
    mac_to_bytes,
)
from WIZMSGHandler import parse_reply_lines

MAC = "00:08:DC:84:14:27"
OLD_IP = "192.168.7.21"
NEW_IP = "192.168.7.99"


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for s in self.slots:
            s(*args)


def _make_fake_handler(device, sent):
    """WIZMSGHandler 대역: 생성 때 받은 cmd_list 를 장치에 먹이고 응답을 시그널로 준다."""

    class FakeHandler:
        verbose_wire_log = False   # get_setting_result 가 클래스 속성으로 읽는다

        def __init__(self, sock, cmd_list, mode, opcode, timeout, *a, **kw):
            self.cmd_list = cmd_list
            self.rcv_list = []
            self.set_result = _Signal()
            sent.append(cmd_list)

        def start(self):
            # do_setting() 과 같은 방식: 앞 두 개(MA/PW 헤더)를 빼고 와이어에 싣는다.
            body = b"".join(c.encode() + p.encode() + b"\r\n" for c, p in self.cmd_list[2:])
            req = b"MA" + mac_to_bytes(MAC) + b"\r\nPW \r\n" + body
            reply = device.build_reply(req)
            if reply is None:
                self.set_result.emit(-1)
                return
            self.rcv_list = [reply]
            self.set_result.emit(len(reply))

    return FakeHandler


@pytest.fixture
def win(qapp, monkeypatch):
    import main_gui

    w = main_gui.WIZWindow()
    # 모달 팝업이 시험을 멈추지 않게 한다.
    for name in ("msg_set_success", "msg_set_warning", "msg_set_error",
                 "msg_setting_pw_error", "show_msgbox"):
        monkeypatch.setattr(w, name, lambda *a, **k: None)
    monkeypatch.setattr(w, "socket_config", lambda: None)

    def _invalid(value=None, *a, **k):
        raise AssertionError(f"do_setting 이 값 검증에서 막혔다(시험 배선 오류): {value!r}")

    monkeypatch.setattr(w, "msg_invalid", _invalid)
    yield w
    w.close()


def _setup(win, monkeypatch, devname, ver):
    """검색을 마친 장치를 TCP unicast 로 선택해 둔 상태를 만든다."""
    import main_gui
    from PyQt5.QtWidgets import QTableWidgetItem

    prof = dict(PROFILE_WIZ752_MEASURED)
    prof.update({"MC": MAC, "MN": devname, "VR": ver, "LI": OLD_IP, "TR": "8", "SC": "00"})
    device = FakeSegcpDevice(prof, mac=MAC)

    sent = []
    monkeypatch.setattr(main_gui, "WIZMSGHandler", _make_fake_handler(device, sent))

    win.curr_mac, win.curr_dev, win.curr_ver, win.curr_st = MAC, devname, ver, "OPEN"
    win.dev_data[MAC] = [devname, ver, "OPEN"]
    win.dev_profile[MAC] = dict(prof)
    win.list_device.setRowCount(1)
    win.list_device.setItem(0, 0, QTableWidgetItem(MAC))
    win.list_device.selectRow(0)
    win.fill_devinfo(win.dev_profile[MAC])

    win.unicast_ip.setChecked(True)
    win.search_ipaddr.setText(OLD_IP)
    return device, sent


def _apply_new_ip(win):
    win.localip.setText(NEW_IP)   # 사용자가 Local IP 를 고친다 (타이핑은 접속 IP 를 건드리지 않아야 한다)
    assert win.search_ipaddr.text() == OLD_IP, "타이핑이 접속 IP 를 미리 바꿨다 (0e53dcd 회귀)"
    win.do_setting()


def _sent_has_li_query(sent):
    """Apply 가 보낸 요청의 GET 확인 쿼리에 LI 가 있었나(= 응답에 LI 가 올 수 있나)."""
    li_cmds = [c for c, p in sent[-1] if c == "LI"]
    # 첫 번째는 SET LI=<새값>, 두 번째부터가 확인 쿼리(param == "")
    return any(c == "LI" and p == "" for c, p in sent[-1])


# ── 전제 고정 (지금도 통과) ──────────────────────────────────────────────

def test_premise_752_confirm_query_has_no_li(win, monkeypatch):
    _, sent = _setup(win, monkeypatch, "WIZ752SR-12x", "2.1.0")
    _apply_new_ip(win)
    assert sent, "do_setting 이 요청을 만들지 못했다(시험 배선 오류)"
    assert not _sent_has_li_query(sent), "752 확인 쿼리에 LI 가 생겼다 — 이 시험의 전제가 바뀜"


def test_premise_750_confirm_query_has_li(win, monkeypatch):
    _, sent = _setup(win, monkeypatch, "WIZ750SR", "1.2.5")
    _apply_new_ip(win)
    assert _sent_has_li_query(sent), "750SR 확인 쿼리에 LI 가 없다 — 이 시험의 전제가 바뀜"


# ── 750SR: 0e53dcd 가 의도대로 동작 (지금도 통과) ─────────────────────────

def test_750_search_ip_follows_new_li_after_apply(win, monkeypatch):
    _setup(win, monkeypatch, "WIZ750SR", "1.2.5")
    _apply_new_ip(win)
    assert win.dev_profile[MAC]["LI"] == NEW_IP
    assert win.search_ipaddr.text() == NEW_IP


# ── 752: SET 응답에 LI 가 없는 기종 (수정 전에는 실패) ────────────────────

_FIX_PENDING = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,   # 배선 오류(AttributeError 등)가 xfail 로 가려지지 않게
    reason="WIZ752SR-12x SET 응답에 LI 가 없어 dev_profile/search_ipaddr 가 옛 IP 로 남는다 "
           "(수정 방향: 보낸 LI 보관 → 응답에 없으면 채움)",
)


@_FIX_PENDING
def test_752_dev_profile_li_is_updated_after_apply(win, monkeypatch):
    _setup(win, monkeypatch, "WIZ752SR-12x", "2.1.0")
    _apply_new_ip(win)
    assert win.dev_profile[MAC]["LI"] == NEW_IP


@_FIX_PENDING
def test_752_search_ip_follows_new_li_after_apply(win, monkeypatch):
    _setup(win, monkeypatch, "WIZ752SR-12x", "2.1.0")
    _apply_new_ip(win)
    assert win.search_ipaddr.text() == NEW_IP


@_FIX_PENDING
def test_752_local_ip_box_keeps_new_value_after_apply(win, monkeypatch):
    """fill_devinfo 가 옛 LI 로 Local IP 칸을 되돌리면 사용자는 적용 결과를 오해한다."""
    _setup(win, monkeypatch, "WIZ752SR-12x", "2.1.0")
    _apply_new_ip(win)
    assert win.localip.text() == NEW_IP
