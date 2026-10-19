"""4CH 조회 목록에 PPPoE ID/Password(PI/PP)가 실려 PPPoE 탭이 채워지는지.

8af6975 가 SET 경로와 UI 만 넣고 조회 목록을 빠뜨려, 입력·저장은 되는데 재검색하면
입력칸이 비어 보였다. 2CH 는 FW 미확인이라 조회하지 않는다.
"""
import pytest

from WIZMakeCMD import WIZMakeCMD

MAC = "00:08:DC:11:22:33"


def _asked(devname, version="1.2.3"):
    chunks = WIZMakeCMD().search_chunks(MAC, " ", devname, version, "OPEN")
    return [c for ch in chunks for c, _ in ch[2:]]


def test_4ch_asks_pppoe_id_and_password():
    asked = _asked("W55RP20-S2E-4CH")
    assert "PI" in asked and "PP" in asked


@pytest.mark.parametrize("devname", ["W55RP20-S2E-2CH", "W55RP20-S2E"])
def test_other_w55rp20_do_not_ask_pppoe(devname):
    asked = _asked(devname)
    assert "PI" not in asked and "PP" not in asked


def test_4ch_old_fw_fallback_does_not_ask_pppoe():
    """FW<1.1.8 은 채널 확장 없이 기본 목록으로만 조회한다(기존 동작 유지)."""
    asked = _asked("W55RP20-S2E-4CH", version="1.1.0")
    assert "PI" not in asked
