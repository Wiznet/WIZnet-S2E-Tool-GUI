# -*- coding: utf-8 -*-
"""3CH 는 공식 제품이 아니라 2026-10-19 에 장치 정의(spec)를 제거했다.

고객 요청 커스텀 3CH 장치(MN `W55RP20-S2E-3CH`)가 혹시 검색되더라도 툴이 죽거나
엉뚱한 채널 명령을 보내지 않는지 고정한다. 단 장치 정의가 없어 **설정 값은 거의 보이지 않는다**(의도된 강등).
(3채널이 필요하면 4CH 모델을 전달하고 설정만 3채널로 쓰게 한다 — W55RP20-S2E-4CH.yaml 머리말)
"""
import pytest

from device_spec_loader import detect_device, list_devices
from WIZMakeCMD import WIZMakeCMD

CUSTOM = "W55RP20-S2E-3CH"


def test_3ch_has_no_device_spec():
    assert CUSTOM not in list_devices()
    assert detect_device(CUSTOM) is None


def test_search_does_not_ask_channel_commands_for_the_removed_name():
    """장치 정의가 없으면 조회 목록이 사실상 비어(헤더 + PO) 설정 값이 거의 안 보인다.
    CH2/CH3 명령을 묻지는 않는다. 이 강등은 의도된 결과다 — 3채널 요청은 4CH 로 대응한다.
    이 시험은 그 동작을 바꾸려는 사람이 알아채도록 현재 상태를 고정한다."""
    codes = [c for c, _ in WIZMakeCMD().search("00:08:dc:11:22:33", "0000", CUSTOM, "1.2.2")]
    assert "GS" not in codes and "CS" not in codes
    assert codes[:2] == ["MA", "PW"]


@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


def test_selecting_the_custom_device_does_not_crash(win):
    win.curr_dev, win.curr_ver, win.curr_st = CUSTOM, "1.2.2", "OPEN"
    win.general_tab_config()
    win._apply_text_length_limits()
    assert win._has_pppoe_support() is False
    win.get_object_value()
