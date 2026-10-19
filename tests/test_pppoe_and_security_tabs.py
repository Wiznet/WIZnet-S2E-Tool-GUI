#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W55RP20-S2E-4CH PPPoE 추가(REQ-W55RP20-4PORT-FW-SYNC) 관련 회귀 테스트.

세 가지를 고정한다:
1. `_has_pppoe_support()`/`_should_show_ddns_pppoe_tab()` — IM 에 PPPoE(2)가 있는 기종만
   True (WIZ107SR/108SR 는 기존 그대로, W55RP20-S2E-4CH 는 이번에 추가, 750SR 은 여전히 False).
2. `_security_op_values()` 기반 mqtt_tab/certificate_tab 노출 — OP 에 4/5/6 이 없는 기종
   (4CH)은 숨고, 있는 기종(1CH/WIZ510SSL)은 그대로 뜬다.
3. `general_tab_config()` 를 실제로 호출했을 때 generalTab 의 탭 구성이 위와 일치한다
   (ddns_pppoe_tab 이 SECURITY_DEVICE 분기에서도 통일 관리되는지 — BUG-UNICAST-IP-CHANGE-FAILS
   조사 중 발견한 사각, 이전엔 SECURITY_DEVICE 는 이 탭을 전혀 건드리지 않았다).
"""
import pytest


@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


def _tab_names(win):
    return {win.generalTab.widget(i).objectName() for i in range(win.generalTab.count())}


def _set_device(win, devname, ver="1.2.5", status="OPEN"):
    win.curr_dev, win.curr_ver, win.curr_st = devname, ver, status


@pytest.mark.parametrize("devname,expected", [
    ("WIZ107SR", True),
    ("WIZ108SR", True),
    ("W55RP20-S2E-4CH", True),
    ("W55RP20-S2E", False),
    ("WIZ750SR", False),
])
def test_has_pppoe_support(win, devname, expected):
    _set_device(win, devname)
    assert win._has_pppoe_support() is expected
    # 탭 가시성도 같은 근거라 같이 고정한다 (이 네 기종 모두 PPPoE 여부 == 탭 여부).
    assert win._should_show_ddns_pppoe_tab() is expected


@pytest.mark.parametrize("devname,wants_mqtt_cert", [
    ("W55RP20-S2E", True),
    ("WIZ510SSL", True),
    ("W55RP20-S2E-4CH", False),
])
def test_security_op_values_gate_mqtt_cert(win, devname, wants_mqtt_cert):
    _set_device(win, devname)
    op_vals = win._security_op_values()
    has_mqtt = bool({'5', '6'} & op_vals)
    has_cert = bool({'4', '6'} & op_vals)
    assert has_mqtt is wants_mqtt_cert
    assert has_cert is wants_mqtt_cert


@pytest.mark.parametrize("devname,expect_ddns_pppoe,expect_mqtt_cert", [
    ("WIZ107SR", True, False),           # DDNS/PPPoE 탭 있음, SECURITY_DEVICE 아님
    ("W55RP20-S2E-4CH", True, False),    # 이번에 PPPoE 탭 생김, SSL/MQTT 는 여전히 없음
    ("W55RP20-S2E", False, True),        # PPPoE 없음, SSL/MQTT 는 있음(SECURITY_DEVICE)
    ("WIZ750SR", False, False),          # 둘 다 없음, SECURITY_DEVICE 도 아님
])
def test_general_tab_config_tab_set(win, devname, expect_ddns_pppoe, expect_mqtt_cert):
    _set_device(win, devname)
    win.general_tab_config()
    names = _tab_names(win)
    assert ("ddns_pppoe_tab" in names) is expect_ddns_pppoe
    assert ("mqtt_tab" in names) is expect_mqtt_cert
    assert ("certificate_tab" in names) is expect_mqtt_cert


def test_switching_from_wiz107_to_4ch_tab_follows(win):
    """직전 장치(WIZ107SR)가 열어 둔 ddns_pppoe_tab 이, SECURITY_DEVICE(4CH)로 바꿔도
    뗐다 붙였다가 제대로 되는지 — 한쪽만 테스트해선 안 보이는 '남은 상태' 버그를 잡는다."""
    _set_device(win, "WIZ107SR")
    win.general_tab_config()
    assert "ddns_pppoe_tab" in _tab_names(win)

    _set_device(win, "W55RP20-S2E-4CH")
    win.general_tab_config()
    names = _tab_names(win)
    assert "ddns_pppoe_tab" in names   # 4CH 도 PPPoE 탭을 쓰므로 유지(같은 이유로 남아 있어도 정답)
    assert "mqtt_tab" not in names
    assert "certificate_tab" not in names


def test_switching_from_wiz510ssl_to_4ch_drops_mqtt_cert(win):
    """직전 장치(WIZ510SSL)가 연 mqtt/certificate 탭이 4CH 로 바꾸면 반드시 떨어져야 한다
    — 이걸 빼먹으면 SET 불가 모드가 화면엔 남아 사용자가 고를 수 있어 보인다."""
    _set_device(win, "WIZ510SSL")
    win.general_tab_config()
    assert {"mqtt_tab", "certificate_tab"} <= _tab_names(win)

    _set_device(win, "W55RP20-S2E-4CH")
    win.general_tab_config()
    names = _tab_names(win)
    assert "mqtt_tab" not in names
    assert "certificate_tab" not in names


def test_has_full_ddns_support_uses_dx_command_not_device_name(win):
    """has_ddns 판단은 "WIZ107"/"WIZ108" 이름 문자열이 아니라 DX 커맨드 유무로 한다
    (2026-10-14, PPPoE 판단(IM/PI/PP)과는 별개 기준). 4CH 는 partial_command_groups
    로 DH만 받고 DX는 없다(W55RP20-S2E-4CH.yaml) — 이 차이로 107/108 과 갈린다.
    DD는 쓰지 않는다 — connection_events 그룹의 DD(Send Data at Disconnection)와
    코드가 충돌해 4CH 에도 True 로 잘못 나온다."""
    _set_device(win, "WIZ107SR")
    assert win._has_full_ddns_support() is True
    _set_device(win, "WIZ108SR")
    assert win._has_full_ddns_support() is True
    _set_device(win, "W55RP20-S2E-4CH")
    assert win._has_full_ddns_support() is False
    _set_device(win, "W55RP20-S2E-2CH")
    assert win._has_full_ddns_support() is False


def test_ddns_pppoe_tab_groups_visible_for_4ch_vs_wiz107(win):
    """s2egui2 검증으로 발견: 4CH 가 탭을 열면 배선 없는 group_ddns/group_network_protocol
    도 같이 보였다. PPPoE 그룹만 보이고 나머지 둘은 숨어야 한다."""
    # 창을 띄우지 않은 상태라 isVisible() 은 항상 False다 — setVisible() 로 명시 지정한
    # 상태만 보는 isHidden() 으로 확인한다.
    _set_device(win, "W55RP20-S2E-4CH")
    win.general_tab_config()
    assert not win.group_pppoe.isHidden()
    assert win.group_network_protocol.isHidden()
    assert win.group_ddns.isHidden()

    _set_device(win, "WIZ107SR")
    win.general_tab_config()
    assert not win.group_pppoe.isHidden()
    assert not win.group_network_protocol.isHidden()
    assert not win.group_ddns.isHidden()


def test_pppoe_fields_load_for_4ch(win):
    """fill_devinfo 가 4CH 에서도 PI/PP 를 pppoe_id/pppoe_pw 로 읽어 오는지."""
    _set_device(win, "W55RP20-S2E-4CH")
    win.fill_devinfo({"MN": "W55RP20-S2E-4CH", "VR": "1.2.3", "PI": "myacct", "PP": "mypass"})
    assert win.pppoe_id.text() == "myacct"
    assert win.pppoe_pw.text() == "mypass"


def test_pppoe_fields_save_for_4ch_not_for_2ch(win):
    """get_object_value 가 4CH 에서는 IM=2/PI/PP 를 담고, 2CH 에서는 안 담는지
    (ip_pppoe 가 이전 장치에서 체크된 채로 남아 있어도 2CH 는 보내면 안 된다)."""
    win.list_device.setRowCount(0)  # selected_devinfo() 가 curr_dev/curr_ver 를 건드리지 않게
    _set_device(win, "W55RP20-S2E-4CH")
    win.ip_pppoe.setChecked(True)
    win.pppoe_id.setText("myacct")
    win.pppoe_pw.setText("mypass")
    setcmd = win.get_object_value()
    assert setcmd["IM"] == "2"
    assert setcmd["PI"] == "myacct"
    assert setcmd["PP"] == "mypass"

    _set_device(win, "W55RP20-S2E-2CH")
    setcmd = win.get_object_value()  # ip_pppoe 는 여전히 체크된 상태(위젯은 공유)
    assert setcmd.get("IM") != "2"
    assert "PI" not in setcmd
    assert "PP" not in setcmd
