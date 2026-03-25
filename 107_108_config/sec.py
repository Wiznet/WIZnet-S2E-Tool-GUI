"""
107_108_config/sec.py
WIZ107SR / WIZ108SR 프로토콜 핵심 (clsSEC.vb 변환)

커맨드셋 42개, 패킷 빌더(검색/설정/리셋), 응답 파서.
VB.NET 원본 frmMain.CalcSetMsg() + clsSEC.SeachMsgBytes() 충실 변환.

─── 패킷 구조 (공통) ───
 [0..9]  MA prefix : b'MA' + 6-byte MAC + b'\\r\\n'
 [10..] payload    : ASCII 텍스트

─── SET 응답 처리 주의 ───
 VB.NET 원본은 응답 길이를 체크하지 않음.
 IM(IP 모드) 변경 시 WIZ107SR/108SR은 즉시 리부트 → 짧은 응답 가능.
 → 길이 임계값 없이 parse_response() 결과만 사용해야 함.
"""
from __future__ import annotations

import struct

# ── 커맨드 순서 (clsSEC.COMMANDS, 42개) ─────────────────────────────────────
COMMANDS: list[str] = [
    "MC", "VR", "MN", "UN", "ST", "IM", "OP", "DD", "CP", "PO", "DG",
    "KA", "KI", "KE", "RI",
    "LI", "SM", "GW", "DS",
    "PI", "PP",                          # PPPoE ID / Password
    "DX", "DP", "DI", "DW", "DH",       # DDNS
    "LP", "RP", "RH",
    "BR", "DB", "PR", "SB", "FL",
    "IT", "PT", "PS", "PD",
    "TE", "SS",
    "NP", "SP",
]

# BR 인덱스 → baud rate 매핑 (cboBaud.Items 순서)
BAUD_TABLE = [300, 600, 1200, 1800, 2400, 4800, 9600,
              14400, 19200, 38400, 57600, 115200, 230400]

# IM 값 → 이름
IP_MODE_NAME = {"0": "Static", "1": "DHCP", "2": "PPPoE"}

# OP 값 → 이름
OP_MODE_NAME = {"0": "TCP Client", "1": "TCP Server",
                "2": "TCP Mixed",  "3": "UDP"}


# ── MA prefix ────────────────────────────────────────────────────────────────

def make_ma_prefix(mac: str) -> bytes:
    """
    10-byte MA prefix.
    mac: "AA:BB:CC:DD:EE:FF" 또는 "FF:FF:FF:FF:FF:FF" (브로드캐스트)
    반환: b'MA' + 6-byte-MAC + b'\\r\\n'
    """
    parts = [int(x, 16) for x in mac.split(":")]
    return b"MA" + bytes(parts) + b"\r\n"


# ── 검색 패킷 ─────────────────────────────────────────────────────────────────

def search_packet(
    mac: str = "FF:FF:FF:FF:FF:FF",
    pwd: str = " ",
) -> bytes:
    """
    SearchMsg 패킷 (clsSEC.SeachMsgBytes 변환).

    구조: MA-prefix + "PW<pwd>\\r\\n" + 42 GET commands (no value)
    브로드캐스트: mac = "FF:FF:FF:FF:FF:FF"
    유니캐스트  : mac = 대상 장치 MAC
    """
    if not pwd:
        pwd = " "
    lines = [f"PW{pwd}"]
    lines.extend(COMMANDS)
    msg = "\r\n".join(lines) + "\r\n"
    return make_ma_prefix(mac) + msg.encode("ascii")


# ── SET 패킷 ──────────────────────────────────────────────────────────────────

def set_packet(mac: str, fields: dict[str, str], pwd: str = " ") -> bytes:
    """
    SET 패킷 (frmMain.CalcSetMsg 변환).

    구조:
      MA-prefix
      PW<pwd>\\r\\n
      <SET 필드들>      ← fields dict (cmd → value)
      <SearchMsg>       ← 42 GET commands (응답 수신용)
      SV\\r\\n           ← 저장
      RT\\r\\n           ← 재부팅

    VB.NET 원본과 동일하게 SearchMsg + SV + RT 를 항상 말미에 첨부.
    장치는 SearchMsg 응답 후 SV/RT 를 실행함.
    단, IM 변경(IP 모드 전환) 시 즉시 리부트 → 응답이 짧을 수 있음.
    """
    if not pwd:
        pwd = " "
    lines: list[str] = [f"PW{pwd}"]
    for cmd, val in fields.items():
        lines.append(f"{cmd}{val}")
    # SearchMsg (GET all)
    lines.extend(COMMANDS)
    lines.append("SV")
    lines.append("RT")
    msg = "\r\n".join(lines) + "\r\n"
    return make_ma_prefix(mac) + msg.encode("ascii")


# ── 리셋 / 공장초기화 패킷 ───────────────────────────────────────────────────

def reset_packet(mac: str, pwd: str = " ") -> bytes:
    """RT (재부팅) 패킷."""
    if not pwd:
        pwd = " "
    msg = f"PW{pwd}\r\nRT\r\n"
    return make_ma_prefix(mac) + msg.encode("ascii")


def factory_reset_packet(mac: str, pwd: str = " ") -> bytes:
    """FR + RT (공장 초기화 + 재부팅) 패킷."""
    if not pwd:
        pwd = " "
    msg = f"PW{pwd}\r\nFR\r\nRT\r\n"
    return make_ma_prefix(mac) + msg.encode("ascii")


# ── 응답 파서 ─────────────────────────────────────────────────────────────────

def parse_response(data: bytes) -> dict[str, str]:
    """
    장치 응답 바이트 → dict {cmd: value}.

    VB.NET parsingMsg() 변환:
    - 10-byte MA prefix 제거
    - PW 줄 건너뜀
    - 길이 > 2 인 줄만 파싱 (cmd=앞2자, value=나머지)
    - ER 필드 포함 시 dict['ER'] 에 오류 메시지 저장
    """
    result: dict[str, str] = {}
    if not data:
        return result

    # MA prefix 제거
    if len(data) >= 10 and data[:2] == b"MA":
        data = data[10:]

    try:
        msg = data.decode("ascii", errors="replace")
    except Exception:
        return result

    for line in msg.split("\r\n"):
        if len(line) > 2:
            cmd = line[:2]
            val = line[2:]
            result[cmd] = val

    return result


def has_valid_mac(fields: dict[str, str]) -> bool:
    """MC 필드가 유효한 MAC 주소 형식(17자)인지 확인."""
    return len(fields.get("MC", "")) == 17


# ── CalcSetMsg 헬퍼 ───────────────────────────────────────────────────────────

def build_set_fields(
    *,
    im: str,
    li: str, sm: str, gw: str, ds: str,
    pi: str, pp: str,
    lp: str,
    op: str,
    rh: str, rp: str, ri: str,
    cp: str, np_val: str,
    dd: str,
    dx: str, dp: str, di: str, dw: str, dh: str,
    po: str,
    dg: str,
    br: str, db: str, pr: str, sb: str, fl: str,
    pt: str, ps: str, pd: str,
    it: str,
    te: str, ss: str,
    sp: str,
    ka: str, ki: str, ke: str,
) -> dict[str, str]:
    """
    UI 값으로부터 SET 필드 dict 를 구성.
    frmMain.CalcSetMsg() 의 조건부 로직을 그대로 반영.

    반환값은 set_packet(mac, fields) 에 그대로 전달.
    """
    f: dict[str, str] = {}

    # ── IP mode ──
    f["IM"] = im
    if im == "0":          # Static
        f["LI"] = li
        f["SM"] = sm
        f["GW"] = gw
        f["DS"] = ds
    elif im == "2":        # PPPoE
        f["PI"] = pi
        f["PP"] = pp
    # DHCP(im=1): LI/SM/GW/DS 생략 (VB.NET과 동일)

    f["LP"] = lp

    # ── Operation mode ──
    f["OP"] = op
    if op == "0":          # TCP Client
        f["RH"] = rh
        f["RP"] = rp
        f["RI"] = ri
    elif op == "1":        # TCP Server
        f["CP"] = cp
        if cp == "1":
            f["NP"] = np_val
    elif op in ("2", "3"): # Mixed / UDP
        f["RH"] = rh
        f["RP"] = rp
        f["RI"] = ri
        if op == "2":
            f["CP"] = cp
            if cp == "1":
                f["NP"] = np_val

    # ── DDNS ──
    f["DD"] = dd
    if dd == "1":
        f["DX"] = dx
        f["DP"] = dp
        f["DI"] = di
        f["DW"] = dw
        f["DH"] = dh

    # ── Debug ──
    f["DG"] = dg

    # ── Serial ──
    f["BR"] = br
    f["DB"] = db
    f["PR"] = pr
    f["SB"] = sb
    f["FL"] = fl

    # ── Data packing ──
    f["PT"] = pt or "0"
    f["PS"] = ps or "0"
    f["PD"] = pd or "0"

    # ── Options ──
    f["IT"] = it or "0"

    # ── Trigger ──
    f["TE"] = te
    if te == "1":
        f["SS"] = ss   # 6-char hex (2+2+2)
    else:
        f["TE"] = "0"

    # ── Search password ──
    f["SP"] = sp if sp else " "

    # ── Keep alive ──
    f["KA"] = ka
    if ka == "1":
        f["KI"] = ki
        f["KE"] = ke

    # ── Network protocol ──
    f["PO"] = po

    return f
