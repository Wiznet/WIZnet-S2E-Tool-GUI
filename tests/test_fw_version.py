# -*- coding: utf-8 -*-
"""펌웨어 버전 파서 통일 (`fw_version`) — 세 소비자가 같은 숫자부를 읽는다.

규칙: **버전 비교는 숫자부만 가지고 한다.** `dev`/`rc`/`beta`/`A` 는 정식판과 같은 번호다.

통일 전에는 파서가 셋이었고 서로 어긋났다(2026-10-16 실측, WIZ750SR 의 `TR`(min_version 1.2.0)):

    입력          통일 전 DeviceSpec      통일 후
    1.2.0dev     TR 없음 (1.2.0.dev0)     TR 있음
    1.2.0A       TR 없음 (1.2.0a0)        TR 있음
    1.2.0rc1     TR 없음                  TR 있음
    abc          TR 있음 (fail-open)      TR 없음 (가장 오래된 FW 로 본다)

`1.2.0A` 는 실제 펌웨어가 쓰는 표기다(750SR `segcp.c`: "Stable version for support users prior to v1.2.0").
`BUG-DEVICESPEC-VERSION-FAILOPEN`, `BUG-VERSION-DEV-SUFFIX` 계열.
"""
import pytest

import fw_boot_compat
import fw_version
from device_spec_loader import _parse_device_version, _parse_version, load_device
from WIZMakeCMD import _safe_version, version_compare

# 실제로 보이는 모양 + 접두어/접미사/메타 변형
READABLE = [
    ("1.2.2", "1.2.2"),
    ("1.2.2.9", "1.2.2.9"),
    ("1.4", "1.4"),
    ("v1.4.5", "1.4.5"),
    ("VR2.1.0", "2.1.0"),
    ("VR2.1.0dev", "2.1.0"),
    ("1.1.8dev", "1.1.8"),
    ("1.1.0-beta", "1.1.0"),
    ("1.1.0rc1", "1.1.0"),
    ("1.4.5A", "1.4.5"),
    ("1.2.5_GreenCS", "1.2.5"),
    ("1.3.3XXX", "1.3.3"),
    ("1.2.2_custom_build_20260825", "1.2.2"),
    ("2.1.0-dev.20260825", "2.1.0"),
    ("1.4.5 Develop", "1.4.5"),
    ("1.0+abc123", "1.0"),
]
UNREADABLE = ["", " ", None, "abc", "no-digits-here", "BOOT"]


@pytest.mark.parametrize("raw, numeric", READABLE)
def test_numeric_part(raw, numeric):
    assert fw_version.numeric_part(raw) == numeric


@pytest.mark.parametrize("raw", UNREADABLE)
def test_unreadable_has_no_numeric_part(raw):
    assert fw_version.numeric_part(raw) is None
    assert fw_version.parse(raw) is None
    assert fw_version.parse_triple(raw) is None


@pytest.mark.parametrize("raw, numeric", READABLE)
def test_all_consumers_read_the_same_numeric_part(raw, numeric):
    """기능 게이트·DeviceSpec·Boot 호환 판정이 같은 숫자를 본다 — 어긋나던 것이 이 시험이 막는 대상."""
    expected = fw_version.parse(raw)
    assert str(expected) == str(_safe_version(raw)) == str(_parse_version(raw)) == str(_parse_device_version(raw))
    triple = fw_boot_compat._parse(raw)
    if triple is not None:
        assert triple == tuple((list(expected.release) + [0, 0])[:3])


def test_one_numeric_component_is_not_a_boot_compat_version():
    """`5` 같은 한 자리는 Boot 호환 구간을 정할 수 없다 — 다른 파서와 달리 None."""
    assert fw_version.parse("5") is not None
    assert fw_version.parse_triple("5") is None
    assert fw_boot_compat._parse("5") is None


def test_triple_pads_and_truncates():
    assert fw_version.parse_triple("1.4") == (1, 4, 0)
    assert fw_version.parse_triple("1.2.2.9") == (1, 2, 2)     # 4번째 성분은 버린다


@pytest.mark.parametrize("dev, release", [
    ("1.2.0dev", "1.2.0"), ("1.2.0A", "1.2.0"), ("1.2.0rc1", "1.2.0"), ("1.2.0-beta", "1.2.0"),
])
def test_suffixed_versions_equal_release(dev, release):
    assert version_compare(dev, release) == 0
    assert _parse_device_version(dev) == _parse_version(release)


# ── DeviceSpec 게이트 (실제 spec 으로) ───────────────────────────────────────

def _has_tr(version):
    return "TR" in load_device("WIZ750SR", version).cmdset      # TR: min_version 1.2.0


@pytest.mark.parametrize("version", [
    "1.2.0", "1.2.0dev", "1.2.0A", "1.2.0rc1", "1.2.0-beta", "VR1.2.0", "1.3.3XXX", "1.2.5_GreenCS",
])
def test_spec_gate_opens_for_same_number_as_release(version):
    assert _has_tr(version)


def test_spec_gate_stays_closed_below_min_version():
    assert not _has_tr("1.1.9")
    assert not _has_tr("1.1.9dev")


@pytest.mark.parametrize("version", ["abc", "BOOT", "no-digits-here"])
def test_spec_gate_fails_closed_for_unreadable_reported_version(version):
    """장치가 값을 보고했는데 숫자가 없으면 가장 오래된 FW 로 본다 — 예전에는 모든 게이트가 풀렸다(fail-open)."""
    assert not _has_tr(version)


@pytest.mark.parametrize("version", [None, ""])
def test_spec_without_reported_version_applies_no_gate(version):
    """버전을 모르는 호출(목록 조회 등)은 게이트를 걸지 않는다 — 이 동작은 유지."""
    assert _has_tr(version)
    assert _parse_device_version(version) is None


def test_garbage_condition_value_means_no_condition():
    """YAML 의 min_version 이 비었거나 못 읽는 값이면 조건이 없는 것으로 본다(장치 버전 쪽과 정책이 다르다)."""
    assert _parse_version(None) is None
    assert _parse_version("") is None
    assert _parse_version("latest") is None
