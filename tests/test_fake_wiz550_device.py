#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 WIZ550 장치 — 바이너리 프로토콜(UDP 6550) 응답기의 동작을 고정한다.

WIZ550 계열(SR/S2E/WEB)은 SEGCP 텍스트가 아니라 7바이트 헤더 + XOR 암호화 payload 를
쓴다. 실장비가 없어 `dev/fix-wiz550-general-fields` 가 미검증인 채 develop 에 들어가
있고 `BUG-W550-Z` 도 막혀 있다. 그 경로를 장비 없이 돌리려고 만들었다.

응답 헤더는 가짜 장치가 직접 조립한다(설정툴의 요청 빌더를 재사용하지 않는다) —
같은 코드로 만들고 같은 코드로 읽으면 시험이 아무것도 증명하지 못하기 때문이다.
Config 본체(162/133B struct)만 WIZ550Profile 의 빌더를 쓴다. 그건 자료 형식이라
따로 구현하면 중복일 뿐이고, 왕복은 이미 기존 시험이 덮고 있다.
"""

import pytest

from tests.fake_wiz550_device import DEFAULT_CONFIG, FakeWiz550Device
from WIZ550MSGHandler import (
    OP_FACTORY_RESET, OP_REMOTE_RESET, STX, WIZNET_REPLY,
    _build_discovery_all, _build_get_info, _build_reset, _build_set_info,
    _parse_discovery_reply, _parse_get_info_reply, _parse_set_reply,
)

MAC = "00:08:DC:55:00:01"
TYPES = ["WIZ550SR", "WIZ550S2E", "WIZ550WEB"]


# ── 1. 검색(DISCOVERY_ALL) ──────────────────────────────────────────────

@pytest.mark.parametrize("device_type", TYPES)
def test_discovery_reply_is_understood_by_the_tools_parser(device_type):
    dev = FakeWiz550Device(device_type, mac=MAC, fw_version=(1, 2, 0))
    reply = dev.build_reply(_build_discovery_all())
    assert reply is not None
    assert reply[0] == STX and reply[4] == WIZNET_REPLY
    info = _parse_discovery_reply(reply)
    assert info is not None, "설정툴이 응답을 해석하지 못한다"
    assert info["device_type"] == device_type
    assert info["mac"] == MAC
    assert info["fw_str"] == "1.2.0"
    assert info["_proto"] == "wiz550"


def test_discovery_payload_is_encrypted_like_the_real_device():
    """valid 바이트 최상위 비트가 서면 payload 가 valid&0x7F 로 XOR 돼 있어야 한다."""
    dev = FakeWiz550Device("WIZ550SR", mac=MAC)
    reply = dev.build_reply(_build_discovery_all())
    valid = reply[1]
    assert valid & 0x80, "암호화 표시 비트가 서 있어야 한다"
    key = valid & 0x7F
    plain = bytes(b ^ key for b in reply[7:19])
    assert plain[6:12] == bytes.fromhex(MAC.replace(":", "")), "복호화하면 MAC 이 나온다"


def test_bootloader_version_is_reported_as_bootloader():
    """fw_ver[0] 가 100 을 넘으면 부트로더다 (설정툴 판정 규칙)."""
    dev = FakeWiz550Device("WIZ550SR", mac=MAC, fw_version=(101, 2, 0))
    info = _parse_discovery_reply(dev.build_reply(_build_discovery_all()))
    assert info["is_boot"] is True
    assert info["fw_str"] == "Bootloader 1.2.0"


# ── 2. 정보 조회(GET_INFO) ──────────────────────────────────────────────

@pytest.mark.parametrize("device_type", TYPES)
def test_get_info_returns_the_device_configuration(device_type):
    config = dict(DEFAULT_CONFIG, local_ip="192.168.7.55", subnet="255.255.255.0")
    dev = FakeWiz550Device(device_type, mac=MAC, config=config)
    reply = dev.build_reply(_build_get_info(MAC))
    assert reply is not None
    got = _parse_get_info_reply(reply, device_type)
    assert got, f"{device_type}: 파싱 실패"
    assert got["local_ip"] == "192.168.7.55"
    assert got["mac"] == MAC


def test_get_info_for_another_mac_is_ignored():
    dev = FakeWiz550Device("WIZ550SR", mac=MAC)
    verdict = dev.classify(_build_get_info("00:08:DC:55:00:99"))
    assert verdict.answered is False
    assert verdict.kind == "other-device"


def test_config_length_field_matches_the_body_the_tool_reads():
    """설정툴은 payload[6:8] 을 Config 크기로 다시 읽는다(헤더 길이를 믿지 않는다).
    그 값이 본체 길이와 어긋나면 화면이 조용히 비거나 깨진다."""
    for device_type, size in (("WIZ550SR", 162), ("WIZ550S2E", 162), ("WIZ550WEB", 133)):
        dev = FakeWiz550Device(device_type, mac=MAC)
        reply = dev.build_reply(_build_get_info(MAC))
        valid = reply[1]
        key = valid & 0x7F if valid & 0x80 else 0
        payload = bytes(b ^ key for b in reply[7:])
        declared = payload[6] + (payload[7] << 8)
        assert declared == size, f"{device_type}: 선언 {declared} vs 실제 {size}"
        assert len(payload) == 6 + size


# ── 3. 설정(SET_INFO)과 리셋 ────────────────────────────────────────────

def test_set_info_applies_the_new_configuration_and_acknowledges():
    from WIZ550Profile import build_sr
    dev = FakeWiz550Device("WIZ550SR", mac=MAC)
    new_config = dict(DEFAULT_CONFIG, mac=MAC, local_ip="192.168.7.99", baud_rate=9600)
    reply = dev.build_reply(_build_set_info(MAC, "", build_sr(new_config)))
    assert _parse_set_reply(reply) is True
    assert dev.config["local_ip"] == "192.168.7.99"
    assert dev.config["baud_rate"] == 9600
    got = _parse_get_info_reply(dev.build_reply(_build_get_info(MAC)), "WIZ550SR")
    assert got["local_ip"] == "192.168.7.99", "이후 조회에도 반영된다"


def test_set_info_with_wrong_password_is_rejected_when_one_is_set():
    from WIZ550Profile import build_sr
    dev = FakeWiz550Device("WIZ550SR", mac=MAC, password="secret")
    assert dev.build_reply(_build_set_info(MAC, "wrong", build_sr(DEFAULT_CONFIG))) is None
    assert dev.build_reply(_build_set_info(MAC, "secret", build_sr(DEFAULT_CONFIG))) is not None


@pytest.mark.parametrize("op", [OP_REMOTE_RESET, OP_FACTORY_RESET])
def test_reset_is_acknowledged(op):
    dev = FakeWiz550Device("WIZ550SR", mac=MAC)
    assert _parse_set_reply(dev.build_reply(_build_reset(op, MAC, ""))) is True
    assert dev.reboots == 1


def test_factory_reset_restores_defaults():
    from WIZ550Profile import build_sr
    dev = FakeWiz550Device("WIZ550SR", mac=MAC)
    dev.build_reply(_build_set_info(MAC, "", build_sr(dict(DEFAULT_CONFIG, local_ip="10.0.0.9"))))
    assert dev.config["local_ip"] == "10.0.0.9"
    dev.build_reply(_build_reset(OP_FACTORY_RESET, MAC, ""))
    assert dev.config["local_ip"] == DEFAULT_CONFIG["local_ip"]


# ── 4. 설정툴 스레드와 왕복 ─────────────────────────────────────────────

def test_searcher_thread_finds_the_fake_device(qapp, monkeypatch):
    """설정툴의 실제 검색 스레드로 왕복. 파서만이 아니라 소켓·타이밍까지 지난다."""
    import WIZ550MSGHandler as H
    port = 6551                      # 실장비가 쓰는 6550 을 건드리지 않는다
    monkeypatch.setattr(H, "WIZ550_PORT", port)
    with FakeWiz550Device("WIZ550S2E", mac=MAC, bind="0.0.0.0", port=port):
        th = H.WIZ550Searcher(timeout=1.5)
        found = []
        th.search_done.connect(found.append)
        th.run()
    assert found and found[0], "검색 스레드가 장치를 못 찾았다"
    macs = [d["mac"] for d in found[0]]
    assert MAC in macs, macs


def test_getter_thread_reads_the_fake_device_config(qapp, monkeypatch):
    import WIZ550MSGHandler as H
    port = 6552
    monkeypatch.setattr(H, "WIZ550_PORT", port)
    config = dict(DEFAULT_CONFIG, local_ip="192.168.7.77", local_port=5000)
    with FakeWiz550Device("WIZ550SR", mac=MAC, bind="0.0.0.0", port=port, config=config):
        th = H.WIZ550Getter(MAC, "WIZ550SR", timeout=1.5)
        got = []
        th.get_done.connect(got.append)
        th.run()
    assert got and got[0], "조회 스레드가 응답을 못 받았다"
    assert got[0]["local_ip"] == "192.168.7.77"
