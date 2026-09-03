#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_version_compare.py — WIZMakeCMD 버전 비교 단위 테스트

규칙: **버전 비교는 숫자부만 가지고 한다.**
`dev` / `rc` / `beta` 는 정식 출시 전이라는 표기일 뿐이고 기능은 같은 번호의
정식판과 동일하다. 접두어와 빌드 메타도 같은 이유로 무시한다.

이 테스트는 현재 동작을 못 박아 두기 위한 것이다. `_safe_version` 이
`Version(v)` 를 그대로 쓰는 형태로 되돌아가면 여기서 잡힌다 — PEP 440 은
`1.1.8dev` 를 `1.1.8.dev0` 으로 해석해 `1.1.8` 보다 작다고 보며,
`InvalidVersion` 을 내지 않으므로 폴백 경로로도 잡히지 않는다.
"""
import pytest

from WIZMakeCMD import _safe_version, version_compare


# ─────────────────────────────────────────────────────────────────
# 숫자부 추출
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    # 정식 표기는 그대로
    ("1.2.2", "1.2.2"),
    ("1.2.2.9", "1.2.2.9"),
    ("4.06", "4.6"),            # packaging 이 선행 0 을 정규화한다
    # 사전 릴리즈 접미사 — PEP 440 이 인식하는 토큰
    ("1.1.8dev", "1.1.8"),
    ("2.1.0dev", "2.1.0"),
    ("1.1.0-beta", "1.1.0"),
    ("1.1.0rc1", "1.1.0"),
    ("1.2.2.9-dev", "1.2.2.9"),
    ("1.0.post1", "1.0"),
    ("1.0+abc123", "1.0"),
    # PEP 440 이 못 읽는 접미사
    ("1.2.2wiz", "1.2.2"),
    ("1.2.2wiznet", "1.2.2"),
    ("1.2.2_custom_build_20260825", "1.2.2"),
    ("2.1.0-dev.20260825", "2.1.0"),
    # 접두어가 붙은 경우
    ("VR2.1.0dev", "2.1.0"),
    ("v1.2.3", "1.2.3"),
])
def test_safe_version_extracts_numeric_part(raw, expected):
    assert str(_safe_version(raw)) == expected


@pytest.mark.parametrize("raw", ["", " ", None, "no-digits-here"])
def test_safe_version_without_digits_falls_back_to_zero(raw):
    assert str(_safe_version(raw)) == "0"


# ─────────────────────────────────────────────────────────────────
# dev 접미사는 정식판과 동일하게 취급된다 (이 수정의 핵심)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dev, release", [
    ("1.0.8dev", "1.0.8"),
    ("1.1.8dev", "1.1.8"),
    ("1.2.0dev", "1.2.0"),
    ("1.2.1dev", "1.2.1"),
    ("1.4.4dev", "1.4.4"),
    ("2.1.0dev", "2.1.0"),
    ("1.1.0-beta", "1.1.0"),
    ("1.1.0rc1", "1.1.0"),
])
def test_dev_suffix_equals_release(dev, release):
    assert version_compare(dev, release) == 0
    assert version_compare(release, dev) == 0


# ─────────────────────────────────────────────────────────────────
# 실제 기능 게이트 기준값과의 비교
#
# 코드에서 쓰이는 기준값: 1.0.8 / 1.1.8 / 1.2.0 / 1.2.1 / 1.4.4
# dev 펌웨어가 게이트를 통과해야 한다.
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("version, gate", [
    ("1.1.8dev", "1.1.8"),      # W55RP20 계열 SD/DD/SE
    ("1.2.1dev", "1.2.1"),      # W55RP20 baud 상한
    ("1.2.0dev", "1.2.0"),      # WIZ750SR advanced 커맨드
    ("1.4.4dev", "1.4.4"),      # WIZ750SR Modbus(MB)
    ("1.0.8dev", "1.0.8"),      # WIZ5XXSR Modbus(PO)
    ("2.1.0dev", "1.1.8"),      # 상위 버전 dev
])
def test_dev_firmware_passes_feature_gate(version, gate):
    assert version_compare(version, gate) >= 0


def test_lower_version_still_blocked():
    """게이트를 여는 방향의 수정이므로, 낮은 버전은 여전히 막혀야 한다."""
    assert version_compare("1.1.7", "1.1.8") < 0
    assert version_compare("1.1.7dev", "1.1.8") < 0
    assert version_compare("1.0.9", "1.2.1") < 0


# ─────────────────────────────────────────────────────────────────
# version_compare 계약
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("a, b, expected", [
    ("1.2.3", "1.2.3", 0),
    ("1.2.4", "1.2.3", 1),
    ("1.2.3", "1.2.4", -1),
    ("1.10.0", "1.9.0", 1),        # 자릿수 비교가 아니라 숫자 비교
    ("1.2.3.9", "1.2.3", 1),
    ("4.06", "4.6", 0),
])
def test_version_compare_returns_sign(a, b, expected):
    assert version_compare(a, b) == expected


@pytest.mark.parametrize("a, b", [("", "1.2.3"), ("1.2.3", ""), ("", "")])
def test_version_compare_with_empty_returns_zero(a, b):
    """빈 문자열이 들어오면 비교하지 않고 0 을 돌려준다 (기존 계약 유지)."""
    assert version_compare(a, b) == 0


# ─────────────────────────────────────────────────────────────────
# 회귀 대조 — 정식 표기는 수정 전후 판정이 같아야 한다
#
# 이 수정은 게이트를 여는 방향이라, 사전 릴리즈가 아닌 버전에서 판정이
# 하나라도 달라지면 실기기 동작이 바뀐다. 수정 전 구현을 여기에 재현해
# 전수 대조한다.
# ─────────────────────────────────────────────────────────────────

# 코드에서 실제로 쓰이는 게이트 기준값
_GATES = ["1.0.8", "1.1.8", "1.2.0", "1.2.1", "1.4.4"]

# 실제 유통되는 정식 버전 표기
_RELEASE_VERSIONS = [
    "1.0.5", "1.0.6", "1.0.8", "1.0.9", "1.1.0", "1.1.1", "1.1.8",
    "1.2.0", "1.2.1", "1.2.2", "1.2.3", "1.3.0", "1.4.0", "1.4.2",
    "1.4.4", "1.4.5", "2.1.0", "4.06", "4.05", "1.2.2wiz",
]


def _legacy_safe_version(v):
    """수정 전 구현 — `Version(v)` 를 그대로 쓰고 실패했을 때만 숫자 추출."""
    import re
    from packaging.version import Version, InvalidVersion
    try:
        return Version(v)
    except InvalidVersion:
        m = re.match(r'[\d.]+', v)
        return Version(m.group(0).rstrip('.')) if m else Version("0")


def _legacy_compare(a, b):
    if not a or not b:
        return 0
    x, y = _legacy_safe_version(a), _legacy_safe_version(b)
    return 0 if x == y else (-1 if x < y else 1)


@pytest.mark.parametrize("version", _RELEASE_VERSIONS)
@pytest.mark.parametrize("gate", _GATES)
def test_release_versions_have_no_regression(version, gate):
    """정식 표기는 수정 전후 판정이 동일해야 한다 (양방향)."""
    assert version_compare(version, gate) == _legacy_compare(version, gate)
    assert version_compare(gate, version) == _legacy_compare(gate, version)


@pytest.mark.parametrize("version, gate", [(g + "dev", g) for g in _GATES])
def test_prerelease_verdict_actually_changed(version, gate):
    """반대로 사전 릴리즈는 판정이 바뀌어야 한다 — 이 수정의 목적."""
    assert _legacy_compare(version, gate) == -1     # 전: 차단
    assert version_compare(version, gate) == 0      # 후: 동일 취급
