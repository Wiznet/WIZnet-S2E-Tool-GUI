# -*- coding: utf-8 -*-
"""4CH PPPoE ID/Password(PI/PP)는 각 63자까지 — 64자 이상은 spec 단계에서 막는다.

4CH 담당자 확인(2026-10-19): SET 의 PI/PP 는 각 최대 63자다. 64자 이상이면 FW 가
ERINVALIDPARAM 을 세우고 같은 요청의 SV(저장)까지 취소한다. NP 와 같은 구조라
(test_np_length_limit.py) 툴이 보내기 전에 막아야 다른 설정이 함께 버려지지 않는다.
"""
from device_spec_loader import load_device

DEVICE = "W55RP20-S2E-4CH"


def test_pi_pp_accept_up_to_63_chars():
    cmdset = load_device(DEVICE).cmdset
    for cmd in ("PI", "PP"):
        assert cmdset[cmd].is_valid("")
        assert cmdset[cmd].is_valid("a" * 63)


def test_pi_pp_reject_64_chars_or_more():
    cmdset = load_device(DEVICE).cmdset
    for cmd in ("PI", "PP"):
        assert not cmdset[cmd].is_valid("a" * 64)
        assert not cmdset[cmd].is_valid("a" * 200)


def test_control_device_without_limit_still_accepts_long_pi():
    """제한은 4CH override 로만 걸린다. WIZ107SR 의 PI 길이는 이번 확인 범위가 아니다."""
    assert load_device("WIZ107SR").cmdset["PI"].is_valid("a" * 64)


def test_4ch_reply_buffer_is_declared():
    assert load_device(DEVICE).fw_config.config_buf_size == 2048


# ── UI: 입력칸 자체가 상한을 넘기지 못한다 ─────────────────────────────────────
import pytest  # noqa: E402


@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


def _select(win, devname, ver="1.2.5"):
    win.curr_dev, win.curr_ver, win.curr_st = devname, ver, "OPEN"
    win._apply_text_length_limits()


def _type(widget, text):
    widget.clear()
    widget.insert(text)          # 사용자가 입력하는 것과 같은 경로(maxLength 적용)
    return widget.text()


def test_ui_4ch_pppoe_id_and_password_stop_at_63(win):
    _select(win, "W55RP20-S2E-4CH")
    assert len(_type(win.pppoe_id, "a" * 80)) == 63
    assert len(_type(win.pppoe_pw, "b" * 80)) == 63


def test_ui_np_stops_at_9_on_limited_devices(win):
    for dev in ("W55RP20-S2E-4CH", "WIZ750SR", "WIZ752SR-12x", "WIZ5XXSR-RP"):
        _select(win, dev)
        assert len(_type(win.connect_pw, "x" * 20)) == 9, dev


def test_ui_limit_is_released_on_a_device_without_the_cap(win):
    """4CH 를 고른 뒤 WIZ107SR 로 바꾸면 4CH 의 63자 상한이 남아 있지 않다."""
    _select(win, "W55RP20-S2E-4CH")
    _select(win, "WIZ107SR", ver="4.06")
    assert len(_type(win.pppoe_id, "a" * 80)) == 80
    assert len(_type(win.connect_pw, "x" * 20)) == 20


# ── 원격 호스트 도메인: FW dns_domain_name[128] → 127자 (4port segcp.c 확인) ──

@pytest.mark.parametrize("cmd", ["RH", "QH", "GH", "CH"])
def test_4ch_remote_host_accepts_127_rejects_128(cmd):
    from device_spec_loader import load_device
    e = load_device("W55RP20-S2E-4CH").cmdset[cmd]
    dom127 = "a" * 63 + "." + "a" * 63          # 레이블 63자 규칙을 지킨 127자
    assert len(dom127) == 127 and e.is_valid(dom127)
    assert not e.is_valid(dom127 + "a")
    assert e.is_valid("192.168.0.1")
