# -*- coding: utf-8 -*-
"""한 기종에 포함된 커맨드 그룹들이 같은 2글자 코드를 중복 정의하지 않는다.

`DeviceSpec.cmdset` 은 코드(`DD` 등)를 키로 하는 dict 라서, 두 그룹이 같은 코드를 가지면
뒤의 것이 앞의 것을 조용히 덮어쓴다. 4CH PPPoE 작업(bb87fee) 중 DDNS 의 `DD`(Enable)와
connection_events 의 `DD`(Send Data at Disconnection)가 코드를 공유한다는 것을 발견했다 —
그래서 4CH 에 DDNS 그룹 가시성을 `DD` 로 판단하면 True 로 잘못 나왔다.

그룹 파일 전체에는 같은 코드가 여럿 있어도(예: two_port 와 w55rp20_two_port) 한 기종이
둘을 같이 포함하지 않으면 문제가 없다. 이 시험은 **기종 단위**로 본다. 지금은 겹침이 0건이고,
새 그룹이나 기종을 추가하다 겹치면 여기서 바로 드러난다.
"""
import glob
import os

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUPS = {}
for _p in glob.glob(os.path.join(ROOT, "specs", "commands", "*.yaml")):
    with open(_p, encoding="utf-8") as _f:
        _d = yaml.safe_load(_f) or {}
    _cmds = _d.get("commands", _d)
    GROUPS[os.path.splitext(os.path.basename(_p))[0]] = (
        {k for k in _cmds if k != "meta"} if isinstance(_cmds, dict) else set()
    )

DEVICES = sorted(glob.glob(os.path.join(ROOT, "specs", "devices", "*.yaml")))


def _codes_by_group(device_yaml):
    with open(device_yaml, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    src = {g: set(GROUPS[g]) for g in (d.get("command_groups") or [])}
    for g, picked in (d.get("partial_command_groups") or {}).items():
        src[f"{g}(partial)"] = set(picked)
    return src


@pytest.mark.parametrize("device_yaml", DEVICES, ids=lambda p: os.path.basename(p)[:-5])
def test_device_includes_no_duplicate_command_codes(device_yaml):
    owners = {}
    for group, codes in _codes_by_group(device_yaml).items():
        for code in codes:
            owners.setdefault(code, []).append(group)
    dups = {c: g for c, g in owners.items() if len(g) > 1}
    assert not dups, f"같은 커맨드 코드를 둘 이상의 그룹이 정의한다(뒤가 앞을 덮어씀): {dups}"


def test_known_cross_group_code_overlaps_stay_mutually_exclusive_per_device():
    """DD/PO 처럼 그룹 파일끼리는 겹치지만, 한 기종이 둘을 함께 들이지는 않는다는 전제 확인."""
    seen = {}
    for g, codes in GROUPS.items():
        for c in codes:
            seen.setdefault(c, set()).add(g)
    overlapping = {c: gs for c, gs in seen.items() if len(gs) > 1}
    assert "DD" in overlapping and overlapping["DD"] == {"ddns", "w55rp20_ext"}
    for device_yaml in DEVICES:
        full = {g for g in _codes_by_group(device_yaml) if "(partial)" not in g}
        for code, gs in overlapping.items():
            assert len(gs & full) <= 1, (
                f"{os.path.basename(device_yaml)}: {code} 를 정의하는 {sorted(gs & full)} 를 함께 포함"
            )
