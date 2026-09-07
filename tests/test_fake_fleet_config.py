#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 장치 묶음을 YAML 로 기술하고 한 번에 띄운다.

계열마다 포트가 달라 따로 실행하면 창을 셋 열어야 하고, 하나를 빠뜨리면
"검색해도 안 잡힌다" 가 된다. 구성 파일 하나로 묶는다.
"""

import textwrap

import pytest
import yaml

from tests.fake_fleet import DEFAULT_CONFIG_PATH, build_fleet_from_config, load_fleet_config


def cfg(text):
    return yaml.safe_load(textwrap.dedent(text))


# ── 1. 기본 구성 파일 ───────────────────────────────────────────────────

def test_shipped_config_file_exists_and_loads():
    """저장소에 기본 구성이 들어 있어야 한다 — 사용자가 바로 띄울 수 있게."""
    assert DEFAULT_CONFIG_PATH.exists(), f"{DEFAULT_CONFIG_PATH} 없음"
    fleet = build_fleet_from_config(load_fleet_config(DEFAULT_CONFIG_PATH))
    kinds = [type(d).__name__ for d in fleet]
    assert "FakeSegcpDevice" in kinds
    assert "FakeWiz550Device" in kinds
    assert "FakeWiz1x0Device" in kinds


def test_shipped_config_uses_the_real_ports_the_tool_talks_to():
    fleet = build_fleet_from_config(load_fleet_config(DEFAULT_CONFIG_PATH))
    ports = {type(d).__name__: d._port for d in fleet}
    assert ports["FakeSegcpDevice"] == 50001
    assert ports["FakeWiz550Device"] == 6550
    assert ports["FakeWiz1x0Device"] == 1460


# ── 2. 구성 해석 ────────────────────────────────────────────────────────

def test_count_creates_that_many_devices_with_increasing_macs():
    fleet = build_fleet_from_config(cfg("""
        devices:
          - family: segcp
            count: 3
            mac: "00:08:DC:FA:CE:01"
    """))
    assert [d.mac for d in fleet] == ["00:08:DC:FA:CE:01", "00:08:DC:FA:CE:02", "00:08:DC:FA:CE:03"]


def test_defaults_apply_to_every_device_and_entry_wins():
    fleet = build_fleet_from_config(cfg("""
        defaults:
          bind: 127.0.0.1
          verbose: 2
        devices:
          - family: w550
            verbose: 0
          - family: w1x0
    """))
    by = {type(d).__name__: d for d in fleet}
    assert by["FakeWiz550Device"].verbose == 0, "항목이 defaults 를 이긴다"
    assert by["FakeWiz1x0Device"].verbose == 2
    assert all(d.bind == "127.0.0.1" for d in fleet)


def test_segcp_entry_can_pick_a_device_spec():
    """spec 이름을 주면 그 기종의 커맨드 목록으로 응답한다 — 12기종을 구성으로 고른다."""
    fleet = build_fleet_from_config(cfg("""
        devices:
          - family: segcp
            device: WIZ5XXSR-RP
            fw_version: "1.1.1"
    """))
    prof = fleet[0].profile
    assert prof["MN"] == "WIZ5XXSR-RP"
    assert "QH" not in prof, "1포트 기종에 채널1 커맨드가 있으면 안 된다"


def test_segcp_entry_without_a_spec_uses_the_measured_752_profile():
    fleet = build_fleet_from_config(cfg("devices: [{family: segcp}]"))
    assert fleet[0].profile["MN"] == "WIZ752SR-12x"
    assert fleet[0].profile["QH"], "2포트라 채널1 값이 있다"


def test_segcp_quirks_are_applied():
    fleet = build_fleet_from_config(cfg("""
        devices:
          - family: segcp
            quirks:
              reboot_sec: 1.5
              dns_block_sec: 2.0
              shared_domain: false
    """))
    q = fleet[0].quirks
    assert q.reboot_sec == 1.5 and q.dns_block_sec == 2.0 and q.shared_domain is False


def test_w550_entry_can_pick_the_model_and_firmware():
    fleet = build_fleet_from_config(cfg("""
        devices:
          - family: w550
            type: WIZ550WEB
            fw: "1.3.0"
            password: secret
    """))
    dev = fleet[0]
    assert dev.device_type == "WIZ550WEB"
    assert dev.fw_version == bytes((1, 3, 0))
    assert dev.password == "secret"


def test_w1x0_entry_sets_the_reported_ip():
    fleet = build_fleet_from_config(cfg("""
        devices:
          - family: w1x0
            ip: 192.168.7.77
    """))
    assert fleet[0].board["ip"] == "192.168.7.77"


# ── 3. 구성 오류는 분명하게 ─────────────────────────────────────────────

def test_unknown_family_names_the_offending_entry():
    with pytest.raises(ValueError, match="w999"):
        build_fleet_from_config(cfg("devices: [{family: w999}]"))


def test_missing_family_is_rejected():
    with pytest.raises(ValueError, match="family"):
        build_fleet_from_config(cfg("devices: [{count: 2}]"))


def test_unknown_option_is_rejected_rather_than_silently_ignored():
    """오타가 조용히 무시되면 왜 안 되는지 알 수 없다."""
    with pytest.raises(ValueError, match="reboot_secs"):
        build_fleet_from_config(cfg("""
            devices:
              - family: segcp
                quirks: {reboot_secs: 1}
        """))


def test_empty_config_gives_an_empty_fleet():
    assert build_fleet_from_config(cfg("devices: []")) == []
