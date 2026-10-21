#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_analysis — 스펙만으로 계산하는 길이·응답 크기 (설계 A1).

핵심 약속: 모르는 것은 None/unbounded 로 드러내고 **추정하지 않는다**.
"""

import pytest

from device_spec_loader import CmdEntry, list_devices, load_device
from spec_analysis import (
    REPLY_HEADER_BYTES, REPLY_LINE_OVERHEAD, audit_spec, entry_max_len,
    max_width, worst_case_reply_size,
)


def _entry(regex="", values=None, access="RW"):
    return CmdEntry(cmd="XX", description="", regex=regex, values=values or {},
                    access=access, ui=None)


# ── max_width ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pattern,expected", [
    (r"^.{0,63}$", 63),
    (r"^.{0,9}$", 9),
    (r"^[0-9]{1,5}$", 5),
    (r"^(\d{1,3}\.){3}\d{1,3}$", 15),
])
def test_max_width_bounded(pattern, expected):
    assert max_width(pattern) == expected


@pytest.mark.parametrize("pattern", [
    r"^.*$",            # 상한 없음
    r"^.+$",
    r"^.{0,}$",
    r"^abc",            # 뒤가 열려 있다(re.match)
    r"abc$",            # 앞이 열려 있다
    "",
    None,
    r"^(unclosed$",     # 잘못된 정규식 — 예외 대신 None
])
def test_max_width_unknown_is_none_not_guess(pattern):
    assert max_width(pattern) is None


def test_entry_max_len_prefers_values_over_regex():
    e = _entry(regex=r"^.{0,99}$", values={"0": "a", "10": "b"})
    assert entry_max_len(e) == 2
    assert entry_max_len(None) is None


# ── worst_case_reply_size ───────────────────────────────────────────────

class _FakeSpec:
    def __init__(self, cmdset, search_cmd_list):
        self.cmdset = cmdset
        self.search_cmd_list = search_cmd_list


def test_reply_size_model_and_unbounded_are_reported():
    spec = _FakeSpec(
        {"AA": _entry(values={"0": "x", "12": "y"}),   # 1~2자
         "BB": _entry(regex=r"^.{0,5}$"),              # 0~5자
         "CC": _entry(regex=r"^.*$")},                 # 모름
        ["AA", "BB", "CC"])
    est = worst_case_reply_size(spec)
    ov = REPLY_LINE_OVERHEAD
    assert est.maximum == REPLY_HEADER_BYTES + (ov + 2) + (ov + 5) + (ov + 0)
    assert est.minimum == REPLY_HEADER_BYTES + (ov + 1) + (ov + 0) + (ov + 0)
    assert est.unbounded == ["CC"]


def test_reply_size_undefined_command_counts_as_unbounded():
    est = worst_case_reply_size(_FakeSpec({}, ["ZZ"]))
    assert est.unbounded == ["ZZ"]


# ── 실제 스펙 ────────────────────────────────────────────────────────────

def test_4ch_spec_width_of_known_caps():
    spec = load_device("W55RP20-S2E-4CH")
    assert entry_max_len(spec.cmdset["PI"]) == 63
    assert entry_max_len(spec.cmdset["PP"]) == 63
    assert entry_max_len(spec.cmdset["NP"]) == 9


def test_4ch_unbounded_commands_are_listed_not_hidden():
    """스펙만으로는 길이를 모르는 명령이 남는다 — 그것이 사람이 채울 목록(H-3)이다.
    목록이 비면 누군가 전부 채운 것이니 이 시험을 갱신하라."""
    est = worst_case_reply_size(load_device("W55RP20-S2E-4CH"))
    assert est.unbounded, "스펙에 길이 상한이 전부 생겼다면 H-3 이 해소된 것 — 이 시험을 고칠 때"
    assert "MN" in est.unbounded


@pytest.mark.parametrize("device", list_devices())
def test_audit_runs_on_every_spec_and_never_raises(device):
    spec = load_device(device)
    findings = audit_spec(spec)
    assert all(f.level in ("error", "warn", "info") for f in findings)
    # 조회 목록은 cmdset 안에서만 만들어지므로 미정의 명령 오류가 나오면 로더가 깨진 것
    assert not [f for f in findings if f.code == "SEARCH_CMD_UNDEFINED"]


@pytest.mark.parametrize("device", list_devices())
def test_known_bound_never_exceeds_declared_buffer(device):
    """알려진 길이만으로 이미 버퍼를 넘으면 스펙이 틀렸다 (코드로 확정 가능한 오류)."""
    spec = load_device(device)
    errors = [f for f in audit_spec(spec) if f.level == "error"]
    assert errors == [], f"{device}: {errors}"


def test_audit_flags_missing_buffer_size():
    spec = load_device("IP20")
    assert spec.fw_config.config_buf_size == 0
    assert "NO_BUF_SIZE" in {f.code for f in audit_spec(spec)}
