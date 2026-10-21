#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""세 계열을 한 번에 띄우는 묶음이 실제로 다 응답하는지 확인한다.

따로 띄우다 하나를 빠뜨려 "검색해도 안 잡힌다" 가 됐던 일이 있어서, 묶음이
계열마다 제대로 서는지를 못 박아 둔다.
"""

from tests.fake_fleet import build_fleet
from tests.fake_segcp_device import FakeSegcpDevice
from tests.fake_wiz1x0_device import FakeWiz1x0Device
from tests.fake_wiz550_device import FakeWiz550Device


def test_default_fleet_has_one_of_each_family():
    fleet = build_fleet(bind="127.0.0.1")
    kinds = [type(d).__name__ for d in fleet]
    assert kinds.count("FakeSegcpDevice") == 1
    assert kinds.count("FakeWiz550Device") == 1
    assert kinds.count("FakeWiz1x0Device") == 1


def test_counts_are_honoured():
    fleet = build_fleet(segcp=3, w550=2, w1x0=0, bind="127.0.0.1")
    kinds = [type(d).__name__ for d in fleet]
    assert kinds.count("FakeSegcpDevice") == 3
    assert kinds.count("FakeWiz550Device") == 2
    assert kinds.count("FakeWiz1x0Device") == 0


def test_every_family_answers_its_own_protocol():
    """묶음의 각 장치가 자기 계열 요청에 답한다 — 포트를 열지 않고 프로토콜만 확인."""
    from WIZ1x0Profile import build_find, parse_imin
    from WIZ550MSGHandler import _build_discovery_all, _parse_discovery_reply
    from WIZMSGHandler import parse_reply_lines

    for dev in build_fleet(bind="127.0.0.1"):
        if isinstance(dev, FakeSegcpDevice):
            req = b"MA\xff\xff\xff\xff\xff\xff\r\nPW \r\nMC\r\nMN\r\n"
            prof = parse_reply_lines(dev.build_reply(req))
            assert prof["MC"] == dev.mac and prof["MN"]
        elif isinstance(dev, FakeWiz550Device):
            info = _parse_discovery_reply(dev.build_reply(_build_discovery_all()))
            assert info and info["mac"] == dev.mac
        elif isinstance(dev, FakeWiz1x0Device):
            parsed = parse_imin(dev.build_reply(build_find()))
            assert parsed and parsed["mac"] == dev.mac
        else:
            raise AssertionError(f"모르는 장치 종류: {type(dev).__name__}")


def test_fleet_binds_and_releases_its_ports():
    """포트를 잡았다 놓는지 — 두 번 연속 띄울 수 있어야 한다."""
    for _ in range(2):
        fleet = build_fleet(segcp=1, w550=1, w1x0=1, bind="127.0.0.1")
        for dev in fleet:
            dev._port = 0                       # 시험 중에는 실제 포트를 잡지 않는다
            if isinstance(dev, FakeWiz1x0Device):
                dev._direct_port = 0
            dev.start()
        assert all(d.port > 0 for d in fleet)
        for dev in fleet:
            dev.stop()
