"""검색 결과 병합이 MAC 표기 차이(대소문자·공백)를 같은 장치로 합치는지.

고객 보고(10대 이상에서 같은 MAC 이 두 행으로 보이고 일부는 이름이 빈다)의 조사용 방어다.
조사 기록: doc/dev/INVESTIGATION-search-mac-duplicate-ko.md
"""
import logging
from types import SimpleNamespace

from main_gui import WIZWindow
from WIZMSGHandler import normalize_mac_key

UPPER = b"EC:74:CD:60:07:18"
LOWER = b"ec:74:cd:60:07:18"


def _state(logger=None):
    return SimpleNamespace(
        mac_list=[], mn_list=[], vr_list=[], st_list=[], mode_list=[], detected_list=[],
        logger=logger or logging.getLogger("test_merge"),
    )


def _merge(st, macs, mns, vrs=None, sts=None, modes=None):
    vrs = vrs or [b"1.2.3"] * len(macs)
    sts = sts or [b"OPEN"] * len(macs)
    modes = modes or [b"0"] * len(macs)
    WIZWindow._merge_search_results(st, macs, mns, vrs, sts, modes)


def _aligned(st):
    n = len(st.mac_list)
    return all(len(x) == n for x in (st.mn_list, st.vr_list, st.st_list, st.mode_list, st.detected_list))


def test_normalize_ignores_case_and_space():
    assert normalize_mac_key(b" ec:74:cd:60:07:18 ") == normalize_mac_key("EC:74:CD:60:07:18")


def test_case_variant_is_merged_into_one_row_and_name_filled(caplog):
    st = _state()
    _merge(st, [UPPER], [""])                     # 이름이 빈 부분 응답
    with caplog.at_level(logging.WARNING, logger="test_merge"):
        _merge(st, [LOWER], ["W55RP20-S2E"])      # 표기만 다른 같은 장치
    assert len(st.mac_list) == 1
    assert st.mn_list == ["W55RP20-S2E"]
    assert _aligned(st)
    assert any("[DUP]" in r.message for r in caplog.records)


def test_case_variants_inside_one_batch_are_merged():
    st = _state()
    _merge(st, [UPPER, LOWER], ["", "W55RP20-S2E"])
    assert len(st.mac_list) == 1
    assert st.mn_list == ["W55RP20-S2E"]
    assert _aligned(st)


def test_distinct_devices_are_not_merged():
    st = _state()
    macs = [f"EC:74:CD:60:07:{i:02X}".encode() for i in range(17)]
    _merge(st, macs, ["W55RP20-S2E"] * 17)
    _merge(st, macs, ["W55RP20-S2E"] * 17)        # 재검색해도 그대로
    assert len(st.mac_list) == 17
    assert all(st.detected_list)
    assert _aligned(st)


def test_identical_bytes_merge_without_warning(caplog):
    st = _state()
    _merge(st, [UPPER], ["A"])
    with caplog.at_level(logging.WARNING, logger="test_merge"):
        _merge(st, [UPPER], ["A"])
    assert not [r for r in caplog.records if "[DUP]" in r.message]
