"""
WIZ107SR / WIZ108SR 기능 테스트
장비 없이 가상 응답 패킷으로 커맨드셋/파싱/검증 로직을 검증합니다.

실행:
    uv run python test_wiz107sr.py
    또는
    python test_wiz107sr.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wizcmdset import Wizcmdset
from WIZMakeCMD import WIZMakeCMD, cmd_107sr, ONE_PORT_DEV

# ============================================================
# 가상 장치 응답 패킷 (실제 장치가 반환하는 형태)
# ============================================================

# WIZ107SR - Static IP, DDNS 활성화, PPPoE 설정 포함
MOCK_WIZ107SR_FULL = (
    b"MA00:08:DC:11:22:33\r\n"
    b"PW \r\n"
    b"MC00:08:DC:11:22:33\r\n"
    b"VR1.4.4\r\n"
    b"MNWIZ107SR\r\n"
    b"UNRS-232\r\n"
    b"STAPP\r\n"
    b"IM0\r\n"            # Static IP
    b"OP1\r\n"            # TCP Server
    b"DD1\r\n"            # DDNS Enable
    b"CP0\r\n"
    b"PO0\r\n"            # TCP Raw (Telnet off)
    b"DG0\r\n"
    b"KA0\r\n"
    b"KI7000\r\n"
    b"KE5000\r\n"
    b"RI3000\r\n"
    b"LI192.168.1.100\r\n"
    b"SM255.255.255.0\r\n"
    b"GW192.168.1.1\r\n"
    b"DS8.8.8.8\r\n"
    b"PI pppoe_user\r\n"   # PPPoE ID
    b"PP pppoe_pass\r\n"   # PPPoE Password
    b"DX0\r\n"            # DDNS Server Index: DynDNS
    b"DP80\r\n"           # DDNS Server Port
    b"DI ddns_user\r\n"   # DDNS User ID
    b"DW ddns_pass\r\n"   # DDNS Password
    b"DH myhome.dyndns.org\r\n"  # DDNS Domain Host
    b"LP5000\r\n"
    b"RP5000\r\n"
    b"RH192.168.1.200\r\n"
    b"BR6\r\n"            # 9600 bps
    b"DB1\r\n"            # 8-bit
    b"PR0\r\n"            # NONE parity
    b"SB0\r\n"            # 1-bit stop
    b"FL0\r\n"            # NONE flow
    b"IT0\r\n"
    b"PT0\r\n"
    b"PS0\r\n"
    b"PD00\r\n"
    b"TE0\r\n"
    b"SS 2B2B2B\r\n"
    b"NP \r\n"
    b"SP \r\n"
)

# WIZ107SR - DHCP, 9-bit 데이터비트, 230400 보율
MOCK_WIZ107SR_9BIT = (
    b"MA00:08:DC:AA:BB:CC\r\n"
    b"PW \r\n"
    b"MC00:08:DC:AA:BB:CC\r\n"
    b"VR1.0.0\r\n"
    b"MNWIZ107SR\r\n"
    b"STAPP\r\n"
    b"IM1\r\n"            # DHCP
    b"OP0\r\n"            # TCP Client
    b"DD0\r\n"            # DDNS Disabled
    b"PO0\r\n"
    b"BR13\r\n"           # 230400 bps (최대)
    b"DB2\r\n"            # 9-bit
    b"PR0\r\n"
    b"SB0\r\n"
    b"FL0\r\n"
    b"LI0.0.0.0\r\n"
    b"SM0.0.0.0\r\n"
    b"GW0.0.0.0\r\n"
    b"DS0.0.0.0\r\n"
    b"LP5000\r\n"
    b"RP5000\r\n"
    b"RH0.0.0.0\r\n"
    b"IT0\r\n"
    b"KA0\r\n"
    b"KI7000\r\n"
    b"KE5000\r\n"
    b"RI3000\r\n"
    b"PT0\r\n"
    b"PS0\r\n"
    b"PD00\r\n"
    b"TE0\r\n"
    b"SS2B2B2B\r\n"
    b"NP \r\n"
    b"SP \r\n"
)

# WIZ108SR - PPPoE 모드
MOCK_WIZ108SR_PPPOE = (
    b"MA00:08:DC:DD:EE:FF\r\n"
    b"PW \r\n"
    b"MC00:08:DC:DD:EE:FF\r\n"
    b"VR2.0.0\r\n"
    b"MNWIZ108SR\r\n"
    b"STAPP\r\n"
    b"IM2\r\n"            # PPPoE
    b"OP0\r\n"
    b"DD0\r\n"
    b"PO1\r\n"            # Telnet
    b"PI my_pppoe_id\r\n"
    b"PP my_pppoe_pw\r\n"
    b"BR12\r\n"           # 115200
    b"DB1\r\n"
    b"PR0\r\n"
    b"SB0\r\n"
    b"FL0\r\n"
    b"LI0.0.0.0\r\n"
    b"SM0.0.0.0\r\n"
    b"GW0.0.0.0\r\n"
    b"DS0.0.0.0\r\n"
    b"LP5000\r\n"
    b"RP5000\r\n"
    b"RH0.0.0.0\r\n"
    b"IT0\r\n"
    b"KA0\r\n"
    b"KI7000\r\n"
    b"KE5000\r\n"
    b"RI3000\r\n"
    b"PT0\r\n"
    b"PS0\r\n"
    b"PD00\r\n"
    b"TE0\r\n"
    b"SS2B2B2B\r\n"
    b"NP \r\n"
    b"SP \r\n"
)


def parse_response(raw: bytes) -> dict:
    """응답 패킷을 커맨드 딕셔너리로 파싱 (main_gui.py의 search_each_dev 로직과 동일)"""
    profile = {}
    for line in raw.split(b"\r\n"):
        if len(line) < 2 or line[:2] == b"MA":
            continue
        cmd = line[:2].decode("utf-8", errors="replace")
        param = line[2:].decode("utf-8", errors="replace").strip()
        profile[cmd] = param
    return profile


# ============================================================
# 테스트 케이스
# ============================================================

def test_cmdset_wiz107sr():
    """WIZ107SR cmdset 기본 검증"""
    print("\n[TEST] wizcmdset - WIZ107SR cmdset")
    cs = Wizcmdset("WIZ107SR")

    # 필수 커맨드 존재 확인
    required = ["DD", "PO", "PI", "PP", "DX", "DP", "DI", "DW", "DH", "IM", "DB", "BR"]
    for cmd in required:
        assert cs.isvalidcommand(cmd), f"FAIL: '{cmd}' 커맨드가 WIZ107SR cmdset에 없음"
        print(f"  [OK] {cmd}: {cs.getcmddescription(cmd)}")

    # IM: PPPoE(2) 허용 확인
    assert cs.isvalidparameter("IM", "2"), "FAIL: IM=2 (PPPoE)가 허용되지 않음"
    assert not cs.isvalidparameter("IM", "3"), "FAIL: IM=3이 허용되어서는 안 됨"
    print("  [OK] IM: 0/1/2 허용, 3 거부")

    # DB: 9-bit(2) 허용 확인
    assert cs.isvalidparameter("DB", "2"), "FAIL: DB=2 (9-bit)가 허용되지 않음"
    assert not cs.isvalidparameter("DB", "3"), "FAIL: DB=3이 허용되어서는 안 됨"
    print("  [OK] DB: 0/1/2 허용, 3 거부")

    # BR: 최대 index 13 (230400) 허용, 14 거부
    assert cs.isvalidparameter("BR", "13"), "FAIL: BR=13 (230400)이 허용되지 않음"
    assert not cs.isvalidparameter("BR", "14"), "FAIL: BR=14 (460800)이 WIZ107SR에서 허용되어서는 안 됨"
    print("  [OK] BR: 0-13 허용, 14 거부")

    # DD: DDNS Enable 검증
    assert cs.isvalidparameter("DD", "0"), "FAIL: DD=0"
    assert cs.isvalidparameter("DD", "1"), "FAIL: DD=1"
    assert not cs.isvalidparameter("DD", "2"), "FAIL: DD=2가 허용되어서는 안 됨"
    print("  [OK] DD: 0/1 허용, 2 거부")

    # PO: TCP Raw/Telnet 검증
    assert cs.isvalidparameter("PO", "0"), "FAIL: PO=0"
    assert cs.isvalidparameter("PO", "1"), "FAIL: PO=1"
    assert not cs.isvalidparameter("PO", "2"), "FAIL: PO=2가 허용되어서는 안 됨"
    print("  [OK] PO: 0/1 허용, 2 거부")

    print("  => PASS")


def test_cmdset_wiz108sr():
    """WIZ108SR cmdset - WIZ107SR과 동일해야 함"""
    print("\n[TEST] wizcmdset - WIZ108SR cmdset")
    cs = Wizcmdset("WIZ108SR")
    assert cs.isvalidcommand("DD"), "FAIL: WIZ108SR에 DD 없음"
    assert cs.isvalidcommand("PO"), "FAIL: WIZ108SR에 PO 없음"
    assert cs.isvalidparameter("IM", "2"), "FAIL: WIZ108SR IM=2 불가"
    assert cs.isvalidparameter("DB", "2"), "FAIL: WIZ108SR DB=2 불가"
    assert not cs.isvalidparameter("BR", "14"), "FAIL: WIZ108SR BR=14 허용되어서는 안 됨"
    print("  => PASS")


def test_wiz750sr_not_affected():
    """WIZ750SR cmdset은 변경되어서는 안 됨"""
    print("\n[TEST] wizcmdset - WIZ750SR 영향 없음 확인")
    cs = Wizcmdset("WIZ750SR")
    assert not cs.isvalidcommand("DD"), "FAIL: WIZ750SR에 DD가 있으면 안 됨"
    assert not cs.isvalidparameter("IM", "2"), "FAIL: WIZ750SR IM=2 허용되어서는 안 됨"
    assert not cs.isvalidparameter("DB", "2"), "FAIL: WIZ750SR DB=2 허용되어서는 안 됨"
    assert cs.isvalidparameter("BR", "14"), "FAIL: WIZ750SR BR=14 허용되어야 함"
    print("  => PASS")


def test_cmd_107sr_list():
    """cmd_107sr 리스트에 DD, PO가 포함되어야 함"""
    print("\n[TEST] WIZMakeCMD - cmd_107sr 커맨드 목록")
    assert "DD" in cmd_107sr, "FAIL: cmd_107sr에 DD 없음"
    assert "PO" in cmd_107sr, "FAIL: cmd_107sr에 PO 없음"
    assert "PI" in cmd_107sr, "FAIL: cmd_107sr에 PI 없음"
    assert "PP" in cmd_107sr, "FAIL: cmd_107sr에 PP 없음"
    assert "DX" in cmd_107sr, "FAIL: cmd_107sr에 DX 없음"
    assert "DH" in cmd_107sr, "FAIL: cmd_107sr에 DH 없음"
    print(f"  cmd_107sr ({len(cmd_107sr)}개): {cmd_107sr}")
    print("  => PASS")


def test_search_cmd_wiz107sr():
    """WIZMakeCMD.search()가 WIZ107SR에 cmd_107sr을 사용하는지 확인"""
    print("\n[TEST] WIZMakeCMD.search() - WIZ107SR 커맨드 목록")
    mk = WIZMakeCMD()
    cmd_list = mk.search("00:08:DC:11:22:33", "", "WIZ107SR", "1.4.4")
    cmds = [c[0] for c in cmd_list]
    assert "DD" in cmds, f"FAIL: search 결과에 DD 없음. cmds={cmds}"
    assert "PO" in cmds, f"FAIL: search 결과에 PO 없음. cmds={cmds}"
    assert "PI" in cmds, f"FAIL: search 결과에 PI 없음"
    assert "PP" in cmds, f"FAIL: search 결과에 PP 없음"
    print(f"  search 커맨드 {len(cmds)}개 확인")
    print("  => PASS")


def test_search_cmd_wiz108sr():
    """WIZMakeCMD.search()가 WIZ108SR에도 동일하게 적용되는지 확인"""
    print("\n[TEST] WIZMakeCMD.search() - WIZ108SR 커맨드 목록")
    mk = WIZMakeCMD()
    cmd_list = mk.search("00:08:DC:AA:BB:CC", "", "WIZ108SR", "2.0.0")
    cmds = [c[0] for c in cmd_list]
    assert "DD" in cmds, "FAIL: WIZ108SR search에 DD 없음"
    assert "PO" in cmds, "FAIL: WIZ108SR search에 PO 없음"
    print("  => PASS")


def test_parse_wiz107sr_full():
    """MOCK_WIZ107SR_FULL 응답 파싱 검증"""
    print("\n[TEST] 응답 파싱 - WIZ107SR Full (DDNS 활성화)")
    profile = parse_response(MOCK_WIZ107SR_FULL)

    assert profile.get("MN") == "WIZ107SR", f"FAIL: MN={profile.get('MN')}"
    assert profile.get("IM") == "0", f"FAIL: IM={profile.get('IM')}"
    assert profile.get("DD") == "1", f"FAIL: DD={profile.get('DD')}"
    assert profile.get("PO") == "0", f"FAIL: PO={profile.get('PO')}"
    assert profile.get("DX") == "0", f"FAIL: DX={profile.get('DX')}"
    assert profile.get("DH") == "myhome.dyndns.org", f"FAIL: DH={profile.get('DH')}"
    assert profile.get("BR") == "6", f"FAIL: BR={profile.get('BR')}"
    assert profile.get("DB") == "1", f"FAIL: DB={profile.get('DB')}"
    print(f"  파싱된 커맨드 {len(profile)}개")
    print(f"  DDNS: DD={profile['DD']}, DH={profile['DH']}, DX={profile['DX']}")
    print("  => PASS")


def test_parse_wiz107sr_9bit():
    """MOCK_WIZ107SR_9BIT 응답 파싱 검증"""
    print("\n[TEST] 응답 파싱 - WIZ107SR 9-bit, 230400bps")
    profile = parse_response(MOCK_WIZ107SR_9BIT)

    assert profile.get("IM") == "1", f"FAIL: IM={profile.get('IM')} (DHCP 예상)"
    assert profile.get("BR") == "13", f"FAIL: BR={profile.get('BR')} (230400 예상)"
    assert profile.get("DB") == "2", f"FAIL: DB={profile.get('DB')} (9-bit 예상)"
    assert profile.get("DD") == "0", f"FAIL: DD={profile.get('DD')} (DDNS Disabled 예상)"

    # wizcmdset 검증
    cs = Wizcmdset("WIZ107SR")
    assert cs.isvalidparameter("BR", profile["BR"]), f"FAIL: BR={profile['BR']} 유효하지 않음"
    assert cs.isvalidparameter("DB", profile["DB"]), f"FAIL: DB={profile['DB']} 유효하지 않음"
    print(f"  BR=13 (230400), DB=2 (9-bit) 유효성 검증 통과")
    print("  => PASS")


def test_parse_wiz108sr_pppoe():
    """MOCK_WIZ108SR_PPPOE 응답 파싱 검증"""
    print("\n[TEST] 응답 파싱 - WIZ108SR PPPoE + Telnet")
    profile = parse_response(MOCK_WIZ108SR_PPPOE)

    assert profile.get("MN") == "WIZ108SR", f"FAIL: MN={profile.get('MN')}"
    assert profile.get("IM") == "2", f"FAIL: IM={profile.get('IM')} (PPPoE 예상)"
    assert profile.get("PO") == "1", f"FAIL: PO={profile.get('PO')} (Telnet 예상)"
    assert "PI" in profile, "FAIL: PI 없음"
    assert "PP" in profile, "FAIL: PP 없음"

    cs = Wizcmdset("WIZ108SR")
    assert cs.isvalidparameter("IM", profile["IM"]), f"FAIL: IM={profile['IM']} 유효하지 않음"
    assert cs.isvalidparameter("PO", profile["PO"]), f"FAIL: PO={profile['PO']} 유효하지 않음"
    print(f"  PPPoE(IM=2), Telnet(PO=1) 유효성 검증 통과")
    print("  => PASS")


def test_setcommand_wiz107sr():
    """WIZMakeCMD.setcommand()가 DD, PO를 포함하는지 확인"""
    print("\n[TEST] WIZMakeCMD.setcommand() - WIZ107SR")
    mk = WIZMakeCMD()
    # 간단한 설정값
    commands = ["IM", "DD", "PO", "BR", "DB"]
    params = ["0", "1", "0", "6", "1"]
    cmd_list = mk.setcommand(
        "00:08:DC:11:22:33", "", "", commands, params, "WIZ107SR", "1.4.4"
    )
    cmds = [c[0] for c in cmd_list]

    # SET 후 GET 커맨드 목록에 DD, PO 포함 확인
    assert "DD" in cmds, f"FAIL: setcommand에 DD 없음"
    assert "PO" in cmds, f"FAIL: setcommand에 PO 없음"
    # SV(Save), RT(Reboot) 확인
    assert "SV" in cmds, "FAIL: SV 없음"
    assert "RT" in cmds, "FAIL: RT 없음"
    print(f"  setcommand 총 {len(cmds)}개 커맨드")
    print("  => PASS")


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    tests = [
        test_cmdset_wiz107sr,
        test_cmdset_wiz108sr,
        test_wiz750sr_not_affected,
        test_cmd_107sr_list,
        test_search_cmd_wiz107sr,
        test_search_cmd_wiz108sr,
        test_parse_wiz107sr_full,
        test_parse_wiz107sr_9bit,
        test_parse_wiz108sr_pppoe,
        test_setcommand_wiz107sr,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  *** {e}")
            failed += 1
        except Exception as e:
            print(f"  *** ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"결과: {passed}개 통과 / {failed}개 실패")
    print('='*50)
    sys.exit(0 if failed == 0 else 1)
