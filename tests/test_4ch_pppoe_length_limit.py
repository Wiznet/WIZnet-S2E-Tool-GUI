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
