# -*- coding: utf-8 -*-
"""`partial_command_groups` — 그룹에서 커맨드 몇 개만 가져오는 장치 선언.

왜 필요한가. `command_groups` 는 전부-아니면-전무다. 그런데 펌웨어가 그룹의 일부만
가진 기종이 있다. 예를 들어 WIZ5XXSR-RP 펌웨어(`segcp.h` 의 1-UART enum)에는
DDNS 커맨드 중 `DH` 하나만 있고 `DD DX DP DI DW` 는 없다. `ddns` 를 통째로 넣으면
spec 이 펌웨어에 없는 커맨드를 가졌다고 주장하게 된다 — 지금 고치려는 드리프트를
반대 방향으로 다시 만드는 셈이다.

그래서 "이 그룹에서 이것만" 을 장치가 직접 적는다. spec 은 펌웨어 enum 을 따른다.
"""

from __future__ import annotations

import pytest
import yaml

from device_spec_loader import load_device


# ── 로더 동작 ────────────────────────────────────────────────────────────

def test_partial_group_brings_only_the_listed_commands():
    """선언한 커맨드만 들어오고 나머지는 안 들어온다."""
    spec = load_device("WIZ5XXSR-RP")
    assert "DH" in spec.cmdset, "선언한 DH 는 들어와야 한다"
    for cmd in ("DD", "DX", "DP", "DI", "DW"):
        assert cmd not in spec.cmdset, f"{cmd} 는 이 펌웨어에 없다 — 들어오면 안 된다"


def test_partial_group_entry_keeps_the_group_definition():
    """부분으로 가져와도 정의(정규식·표시값)는 그룹 파일 그대로다."""
    rp = load_device("WIZ5XXSR-RP")
    full = load_device("WIZ107SR")          # ddns 를 통째로 쓰는 기종
    assert rp.cmdset["DH"].regex == full.cmdset["DH"].regex
    assert rp.cmdset["DH"].description == full.cmdset["DH"].description


def test_unknown_command_in_partial_group_is_rejected():
    """그룹에 없는 커맨드를 적으면 조용히 무시하지 않고 알린다."""
    from device_spec_loader import _select_partial_commands

    with pytest.raises(ValueError, match="ZZ"):
        _select_partial_commands({"DH": object(), "DD": object()}, ["DH", "ZZ"], "ddns", "TEST")


def test_partial_group_still_checks_module_requirements():
    """부분 include 도 그룹의 requires 를 지킨다 (ddns requires base)."""
    spec = load_device("WIZ5XXSR-RP")
    assert "MC" in spec.cmdset, "base 가 없으면 ddns 의 requires 가 깨진 것"


# ── 기종별 결과 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("device,present,absent", [
    # RP2040 계열: 펌웨어에 DDNS 는 DH 뿐이다
    ("WIZ5XXSR-RP", ["DH", "EC", "PO", "SC", "TR"], ["DD", "DX", "DP", "DI", "DW"]),
    ("WIZ5XXSR-RP_E-SAVE", ["DH", "EC", "PO", "SC", "TR"], ["DD", "DX", "DP", "DI", "DW"]),
    ("W55RP20-S2E", ["DH", "PO", "SC"], ["DX", "DP", "DI", "DW"]),
    ("W232N", ["DH", "PO", "SC"], ["DX", "DP", "DI", "DW"]),
    ("IP20", ["DH", "PO", "SC"], ["DX", "DP", "DI", "DW"]),
    ("WIZ510SSL", ["BA", "DH", "SC"], ["DX", "DP", "DI", "DW"]),
    # W7500 계열: 펌웨어가 DDNS·PPPoE 를 다 가졌으므로 그룹째 넣는다
    ("WIZ752SR-12x", ["DD", "DX", "DP", "DI", "DW", "DH", "PI", "PP", "E0", "E1"], []),
    ("WIZ750SR", ["DD", "DX", "DP", "DI", "DW", "DH", "PI", "PP"], []),
    ("WIZ750SR-1xx", ["DD", "DX", "DP", "DI", "DW", "DH", "PI", "PP"], []),
])
def test_device_cmdset_matches_its_firmware(device, present, absent):
    """2026-09-08 FW `segcp.h` enum 대조 결과가 spec 에 그대로 반영돼 있다."""
    spec = load_device(device)
    missing = [c for c in present if c not in spec.cmdset]
    extra = [c for c in absent if c in spec.cmdset]
    assert missing == [], f"{device}: 펌웨어에 있는데 spec 에 없다 — {missing}"
    assert extra == [], f"{device}: 펌웨어에 없는데 spec 이 가졌다 — {extra}"


def test_partial_declaration_is_documented_in_every_device_that_uses_it():
    """`partial_command_groups` 를 쓰는 파일에는 왜 부분인지 주석이 있어야 한다.

    근거 없이 목록을 줄이면 다음 사람이 되돌린다. 이 프로젝트에서 실제로 겪은 일이다.
    """
    import glob
    import io
    import os

    for path in glob.glob("specs/devices/*.yaml"):
        raw = yaml.safe_load(io.open(path, encoding="utf-8"))
        if not raw or "partial_command_groups" not in raw:
            continue
        text = io.open(path, encoding="utf-8").read()
        head = text.split("partial_command_groups:")[0]
        tail = text.split("partial_command_groups:")[1].split("\n\n")[0]
        assert "#" in (head.rsplit("\n\n", 1)[-1] + tail), (
            f"{os.path.basename(path)}: partial_command_groups 에 근거 주석이 없다")


def test_yaml_shape_is_a_mapping_of_group_to_command_list():
    """선언 모양이 바뀌면 알아채도록 고정한다."""
    import io

    raw = yaml.safe_load(io.open("specs/devices/WIZ5XXSR-RP.yaml", encoding="utf-8"))
    partial = raw["partial_command_groups"]
    assert isinstance(partial, dict)
    for group, cmds in partial.items():
        assert isinstance(group, str)
        assert isinstance(cmds, list) and all(isinstance(c, str) for c in cmds)


# ── PO 의미 충돌 ─────────────────────────────────────────────────────────

def test_no_device_mixes_telnet_and_modbus():
    """같은 `PO` 코드를 두 그룹이 다른 뜻으로 정의한다 — 한 기종이 둘 다 쓰면 안 된다.

    telnet: TCP Raw(0) / Telnet(1).  modbus: Serial(0) / RTU(1) / ASCII(2).
    섞이면 나중에 병합된 쪽이 이겨 조용히 규칙이 바뀐다.
    """
    import glob
    import io
    import os

    for path in glob.glob("specs/devices/*.yaml"):
        raw = yaml.safe_load(io.open(path, encoding="utf-8")) or {}
        used = set(raw.get("command_groups", []) or [])
        used |= set(raw.get("partial_command_groups", {}) or {})
        assert not {"telnet", "modbus"} <= used, (
            f"{os.path.basename(path)}: telnet 과 modbus 를 함께 쓴다 — PO 의 뜻이 충돌한다")


@pytest.mark.parametrize("device,accepts_two", [
    ("WIZ5XXSR-RP", True),      # PO = 시리얼 프로토콜 0~2 (uartHandler.h enum protocol)
    ("W55RP20-S2E", True),
    ("W232N", True),
    ("IP20", True),
    ("WIZ107SR", False),        # PO = TCP Raw / Telnet
    ("WIZ108SR", False),
])
def test_po_accepts_what_the_firmware_accepts(device, accepts_two):
    """PO 는 기종마다 뜻이 달라 허용 범위도 다르다.

    RP2040 계열: `segcp.c:795` 가 `tmp_int > modbus_ascii(2)` 만 거부한다.
    이걸 telnet 정의(`^[0-1]$`)로 검사하면 2 가 없던 거부를 당한다.
    """
    spec = load_device(device)
    entry = spec.cmdset["PO"]
    assert entry.is_valid("0") and entry.is_valid("1")
    assert entry.is_valid("2") is accepts_two
    assert not entry.is_valid("3")


# ── DDNS 탭 게이팅 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("device,opens_tab", [
    ("WIZ107SR", True), ("WIZ108SR", True),
    ("WIZ752SR-12x", False), ("WIZ750SR", False), ("W55RP20-S2E", False),
])
def test_ddns_tab_is_declared_not_inferred_from_dd(device, opens_tab):
    """DDNS/PPPoE 탭을 여는 기종은 장치 YAML 이 직접 선언한다.

    예전 기준은 `'DD' in spec.cmdset` 이었다. 2026-09-08 spec 을 펌웨어 enum 에
    맞추면서 WIZ752SR/WIZ750SR 도 DD 를 가지게 됐다 — 커맨드 보유와 화면 제공은
    다른 문제라 기준을 분리했다.
    """
    spec = load_device(device)
    wo = spec.ui_config.widget_overrides.get("ddns_pppoe_tab")
    assert bool(wo and wo.visible) is opens_tab
    if opens_tab:
        assert "DD" in spec.cmdset, "탭을 여는데 DD 가 없으면 화면이 빈다"
