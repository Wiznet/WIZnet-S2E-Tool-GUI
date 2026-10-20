#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FW 소스 대조(2026-10-20, doc/fw/FW-SOURCE-*.md)로 확인된 입력 길이 상한이 스펙에 있는지.

기대값은 각 FW 의 칸 크기 - 1 (NUL 자리)이다. 이 상한을 넘으면 검사 없는 strcpy 는 이웃 필드를 덮고,
검사 있는 쪽은 INVALIDPARAM 으로 같은 요청의 SV 를 취소한다. 실기기 측정이 아니라 소스 읽기 기반이다.
"""

import pytest

from device_spec_loader import load_device

MQTT = ("QU", "QP", "QC", "PU", "U0", "U1", "U2")


def _domain(n):
    """레이블 63자 이하 규칙을 지키는 길이 n 의 도메인."""
    k = -(-(n + 1) // 64)                       # 필요한 레이블 수
    total = n - (k - 1)                          # 점을 뺀 글자 수
    sizes = [total // k + (1 if i < total % k else 0) for i in range(k)]
    out = ".".join("a" * z for z in sizes)
    assert len(out) == n and all(1 <= z <= 63 for z in sizes), (n, sizes)
    return out


# 기종 → {명령: 최대 글자 수}
EXPECT = {
    "WIZ750SR": {"RH": 48, "SP": 9},
    "WIZ750SR-1xx": {"RH": 48, "SP": 9},
    "WIZ752SR-12x": {"RH": 39, "QH": 39, "SP": 9},
    "WIZ5XXSR-RP": {"RH": 127, "SP": 9, **{c: 127 for c in MQTT}},
    "WIZ5XXSR-RP_E-SAVE": {"RH": 127, "SP": 9, **{c: 127 for c in MQTT}},
    "W55RP20-S2E": {"RH": 127, "SP": 9, **{c: 127 for c in MQTT}},
    "W55RP20-S2E-2CH": {"RH": 127, "QH": 127, "SP": 9, **{c: 127 for c in MQTT}},
    "IP20": {"RH": 127, "SP": 9, "NP": 9, **{c: 127 for c in MQTT}},
    "W232N": {"RH": 127, "SP": 9, "NP": 9, **{c: 127 for c in MQTT}},
    "W55RP20-S2E-4CH": {"RH": 127, "QH": 127, "GH": 127, "CH": 127, "SP": 9, "NP": 9, "PI": 63, "PP": 63},
}
CASES = [(d, c, n) for d, caps in EXPECT.items() for c, n in caps.items()]


@pytest.mark.parametrize("device,cmd,n", CASES)
def test_cap_accepts_exactly_n_and_rejects_one_more(device, cmd, n):
    entry = load_device(device).cmdset[cmd]
    if cmd in ("RH", "QH", "GH", "CH"):
        ok, bad = _domain(n), _domain(n + 1)
    else:
        ok, bad = "x" * n, "x" * (n + 1)
    assert entry.is_valid(ok), f"{device} {cmd}: {n}자는 통과해야 한다"
    assert not entry.is_valid(bad), f"{device} {cmd}: {n + 1}자는 FW 칸을 넘는다 — 막아야 한다"


@pytest.mark.parametrize("device", ["WIZ750SR", "WIZ5XXSR-RP", "W55RP20-S2E", "W55RP20-S2E-4CH"])
def test_domain_cap_still_accepts_an_ip_address(device):
    assert load_device(device).cmdset["RH"].is_valid("192.168.0.1")


@pytest.mark.parametrize("value", ["1", "9", "99", "199", "200", "205", "206", "209", "216", "219", "246", "249", "250", "255"])
def test_tr_accepts_every_firmware_value_1_to_255(value):
    """정규식 `2[0-5][0-5]` 가 206~209 등 20개를 막던 스펙 버그 (750SR·5XXSR-RP·W55RP20 모두 FW 는 1~255)."""
    assert load_device("W55RP20-S2E").cmdset["TR"].is_valid(value)


@pytest.mark.parametrize("value", ["0", "256", "300", "", "abc"])
def test_tr_still_rejects_out_of_range(value):
    assert not load_device("W55RP20-S2E").cmdset["TR"].is_valid(value)


def test_dh_is_left_alone_because_get_value_is_longer_than_set_limit():
    """DH 의 GET 은 `이름-MAC` 이라 SET 상한(19)보다 길다. 한 규칙으로 못 묶어 상한을 걸지 않았다(담당자 질문)."""
    for dev in ("W55RP20-S2E", "WIZ5XXSR-RP", "W55RP20-S2E-4CH"):
        spec = load_device(dev)
        if "DH" in spec.cmdset:
            assert spec.cmdset["DH"].is_valid("W55RP20-S2E-2CH-FACE01")
