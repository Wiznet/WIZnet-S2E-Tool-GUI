#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ1x0Profile.py — WIZ100SR/WIZ105SR/WIZ110SR 바이너리 프로토콜 변환

typeBoardInfo (163바이트) ↔ Python dict 변환.
VB6 소스(WIZ1xxSR_config_v3.0.2) 기반.

주의사항:
  - 동작 모드 인덱스: 0=Client, 1=Mixed, 2=Server  (WIZ107/108과 역전!)
  - Debug 플래그: debugoff=0 → 디버그 ON, 1 → OFF  (역전!)
  - Baud Rate: HW 레지스터값 (인덱스 아님)
  - SETT 전송 = 즉시 저장 + 리부트
  - WIZ120SR 필터: 응답[103] (PPPoE_ID[17]) 값 1~9이면 제외
"""

import struct

# ─────────────────────────────────────────────
# typeBoardInfo 구조체 (163 bytes, little-endian)
# ─────────────────────────────────────────────
# VB6 Type 선언 순서 그대로:
#   mac[6], bserver, ip[4], subnet[4], gw[4], myport[2], peerip[4], peerport[2]
#   speed, databit, parity, stopbit, flow
#   D_ch, D_size[2], D_time[2], I_time[2], debugoff, AppVer[2]
#   DHCP, UDP, Connect, DNS_Flag, DNS_IP[4], D_SIP[32]
#   SCfg, SCfgStr[3]
#   PPPoE_ID[32], PPPoE_Pass[32]
#   EnTCPPass, TCPPass[8]
#   (padding 4)
# 합계: 6+1+4+4+4+2+4+2 + 1+1+1+1+1 + 1+2+2+2+1+2 + 1+1+1+1+4+32 + 1+3 + 32+32 + 1+8 + 4 = 163
STRUCT_FORMAT = (
    '>'        # big-endian (포트·타이머는 BE, 나머지는 바이트 단위라 무관)
    '6s'       # mac[6]
    'B'        # bserver
    '4s'       # ip[4]
    '4s'       # subnet[4]
    '4s'       # gw[4]
    'H'        # myport (big-endian 2B)
    '4s'       # peerip[4]
    'H'        # peerport (big-endian 2B)
    'B'        # speed (HW 레지스터값)
    'B'        # databit (실제값: 7 or 8)
    'B'        # parity (0=None,1=Odd,2=Even)
    'B'        # stopbit (실제값: 1)
    'B'        # flow (0=None,1=Xon/Xoff,2=CTS/RTS)
    'B'        # D_ch
    'H'        # D_size (big-endian)
    'H'        # D_time (big-endian)
    'H'        # I_time (big-endian)
    'B'        # debugoff  ← 0=ON, 1=OFF (역전!)
    '2s'       # AppVer[2] = [major, minor]
    'B'        # DHCP (0=Static,1=DHCP,2=PPPoE)
    'B'        # UDP
    'B'        # Connect
    'B'        # DNS_Flag
    '4s'       # DNS_IP[4]
    '32s'      # D_SIP[32]  (도메인명)
    'B'        # SCfg
    '3s'       # SCfgStr[3]
    '32s'      # PPPoE_ID[32]
    '32s'      # PPPoE_Pass[32]
    'B'        # EnTCPPass
    '8s'       # TCPPass[8]
    '4s'       # padding
)
BOARD_INFO_SIZE = 163
assert struct.calcsize(STRUCT_FORMAT) == BOARD_INFO_SIZE, \
    f"구조체 크기 오류: {struct.calcsize(STRUCT_FORMAT)} != {BOARD_INFO_SIZE}"

# ─────────────────────────────────────────────
# Baud Rate 매핑 (HW 레지스터값 ↔ bps)
# VB6 Form_Load cboSpeed.ItemData 기준
# ─────────────────────────────────────────────
SPEED_HW_TO_BPS = {
    0xA0: 1200,
    0xD0: 2400,
    0xE8: 4800,
    0xF4: 9600,
    0xFA: 19200,
    0xFD: 38400,
    0xFE: 57600,
    0xFF: 115200,
    0xBB: 230400,
}
SPEED_BPS_TO_HW = {v: k for k, v in SPEED_HW_TO_BPS.items()}
SPEED_BPS_LIST = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400]

# 동작 모드 (WIZ107/108과 인덱스 역전!)
OP_MODE = {0: 'Client', 1: 'Mixed', 2: 'Server'}
OP_MODE_R = {v: k for k, v in OP_MODE.items()}

# IP 할당 방식
IP_ALLOC = {0: 'Static', 1: 'DHCP', 2: 'PPPoE'}
IP_ALLOC_R = {v: k for k, v in IP_ALLOC.items()}

# Parity
PARITY = {0: 'None', 1: 'Odd', 2: 'Even'}
PARITY_R = {v: k for k, v in PARITY.items()}

# Flow Control
FLOW = {0: 'None', 1: 'Xon/Xoff', 2: 'CTS/RTS'}
FLOW_R = {v: k for k, v in FLOW.items()}


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────

def mac_bytes_to_str(mac6: bytes) -> str:
    """b'\\x00\\x08\\xdc...' → '00:08:DC:11:22:33'"""
    return ':'.join(f'{b:02X}' for b in mac6)


def mac_str_to_bytes(mac_str: str) -> bytes:
    """'00:08:DC:11:22:33' → b'\\x00\\x08\\xdc...'"""
    return bytes(int(x, 16) for x in mac_str.replace('-', ':').split(':'))


def ip_bytes_to_str(ip4: bytes) -> str:
    return '.'.join(str(b) for b in ip4)


def ip_str_to_bytes(ip_str: str) -> bytes:
    parts = ip_str.split('.')
    return bytes(int(p) for p in parts)


def cstr_to_str(raw: bytes) -> str:
    """null-terminated bytes → str"""
    return raw.rstrip(b'\x00').decode('ascii', errors='replace')


def str_to_cstr(s: str, length: int) -> bytes:
    """str → null-padded bytes (length 크기)"""
    encoded = s.encode('ascii', errors='replace')
    return encoded[:length].ljust(length, b'\x00')


def appver_to_str(appver: bytes) -> str:
    """AppVer[2] → 'major.minor'"""
    return f'{appver[0]}.{appver[1]}'


# ─────────────────────────────────────────────
# 핵심 변환 함수
# ─────────────────────────────────────────────

def parse_imin(data: bytes) -> dict | None:
    """
    IMIN 응답(167바이트) → dict.

    선두 4바이트 'IMIN' 검증 후 163바이트 파싱.
    WIZ120SR 필터: data[4+103] (PPPoE_ID[17]) 값 1~9이면 None 반환.

    반환 dict 키:
      mac, bserver, ip, subnet, gw, myport, peerip, peerport,
      speed_hw, speed_bps, databit, parity, stopbit, flow,
      D_ch, D_size, D_time, I_time,
      debug_on (bool, UI용 정규화),
      appver, appver_str,
      dhcp, udp, connect, dns_flag, dns_ip, domain,
      scfg, scfg_str,
      pppoe_id, pppoe_pass,
      en_tcppass, tcppass,
      _proto (= 'wiz1x0')
    """
    if len(data) < 4 + BOARD_INFO_SIZE:
        return None
    if data[:4] != b'IMIN':
        return None

    raw = data[4:4 + BOARD_INFO_SIZE]

    # WIZ120SR 필터: raw[103] = PPPoE_ID[17]
    # PPPoE_ID 배열 시작 오프셋:
    #   6+1+4+4+4+2+4+2+1+1+1+1+1+1+2+2+2+1+2+1+1+1+1+4+32+1+3 = 86
    #   PPPoE_ID[17] = raw[86+17] = raw[103]
    wiz120_marker = raw[103]
    if 1 <= wiz120_marker <= 9:
        return None  # WIZ120SR → 제외

    fields = struct.unpack(STRUCT_FORMAT, raw)
    (mac, bserver, ip, subnet, gw, myport, peerip, peerport,
     speed, databit, parity, stopbit, flow,
     d_ch, d_size, d_time, i_time, debugoff, appver,
     dhcp, udp, connect, dns_flag, dns_ip, d_sip,
     scfg, scfg_str,
     pppoe_id, pppoe_pass,
     en_tcppass, tcppass,
     _padding) = fields

    speed_bps = SPEED_HW_TO_BPS.get(speed, 9600)

    return {
        'mac':        mac_bytes_to_str(mac),
        'bserver':    bserver,
        'op_mode':    OP_MODE.get(bserver, 'Client'),
        'ip':         ip_bytes_to_str(ip),
        'subnet':     ip_bytes_to_str(subnet),
        'gw':         ip_bytes_to_str(gw),
        'myport':     myport,
        'peerip':     ip_bytes_to_str(peerip),
        'peerport':   peerport,
        'speed_hw':   speed,
        'speed_bps':  speed_bps,
        'databit':    databit,
        'parity':     parity,
        'parity_str': PARITY.get(parity, 'None'),
        'stopbit':    stopbit,
        'flow':       flow,
        'flow_str':   FLOW.get(flow, 'None'),
        'D_ch':       d_ch,
        'D_size':     d_size,
        'D_time':     d_time,
        'I_time':     i_time,
        'debugoff':   debugoff,
        'debug_on':   (debugoff == 0),   # UI용: True=디버그 ON
        'appver':     appver,
        'appver_str': appver_to_str(appver),
        'dhcp':       dhcp,
        'ip_alloc':   IP_ALLOC.get(dhcp, 'Static'),
        'udp':        udp,
        'connect':    connect,
        'dns_flag':   dns_flag,
        'dns_ip':     ip_bytes_to_str(dns_ip),
        'domain':     cstr_to_str(d_sip),
        'scfg':       scfg,
        'scfg_str':   scfg_str.hex(),    # '001122' 형태
        'pppoe_id':   cstr_to_str(pppoe_id),
        'pppoe_pass': cstr_to_str(pppoe_pass),
        'en_tcppass': en_tcppass,
        'tcppass':    cstr_to_str(tcppass),
        '_proto':     'wiz1x0',
    }


def build_sett(d: dict) -> bytes:
    """
    dict → 'SETT' + 163바이트 패킷.

    dict는 parse_imin() 반환값 또는 UI에서 수집한 값.
    SETT 전송 시 장치가 즉시 저장+리부트됨.
    """
    mac_b     = mac_str_to_bytes(d['mac'])
    bserver   = OP_MODE_R.get(d.get('op_mode', 'Client'), 0)
    ip_b      = ip_str_to_bytes(d['ip'])
    subnet_b  = ip_str_to_bytes(d['subnet'])
    gw_b      = ip_str_to_bytes(d['gw'])
    myport    = int(d['myport'])
    peerip_b  = ip_str_to_bytes(d['peerip'])
    peerport  = int(d['peerport'])

    # Baud Rate: bps → HW 레지스터
    speed_bps = int(d.get('speed_bps', 9600))
    speed_hw  = SPEED_BPS_TO_HW.get(speed_bps, 0xF4)  # 기본 9600

    databit   = int(d.get('databit', 8))
    parity    = PARITY_R.get(d.get('parity_str', 'None'), 0)
    stopbit   = int(d.get('stopbit', 1))
    flow      = FLOW_R.get(d.get('flow_str', 'None'), 0)

    d_ch      = int(d.get('D_ch', 0))
    d_size    = int(d.get('D_size', 0))
    d_time    = int(d.get('D_time', 0))
    i_time    = int(d.get('I_time', 0))

    # debug_on(bool) → debugoff(byte): True=0, False=1 (역전)
    debug_on  = bool(d.get('debug_on', False))
    debugoff  = 0 if debug_on else 1

    appver    = d.get('appver', b'\x00\x00')
    dhcp      = IP_ALLOC_R.get(d.get('ip_alloc', 'Static'), 0)
    udp       = int(d.get('udp', 0))
    connect   = int(d.get('connect', 0))
    dns_flag  = int(d.get('dns_flag', 0))
    dns_ip_b  = ip_str_to_bytes(d.get('dns_ip', '0.0.0.0'))
    d_sip_b   = str_to_cstr(d.get('domain', ''), 32)

    scfg      = int(d.get('scfg', 0))
    scfg_hex  = d.get('scfg_str', '000000')
    scfg_b    = bytes.fromhex(scfg_hex.zfill(6))[:3]

    pppoe_id_b   = str_to_cstr(d.get('pppoe_id', ''), 32)
    pppoe_pass_b = str_to_cstr(d.get('pppoe_pass', ''), 32)

    en_tcppass = int(d.get('en_tcppass', 0))
    tcppass_b  = str_to_cstr(d.get('tcppass', ''), 8)
    padding    = b'\x00' * 4

    raw = struct.pack(
        STRUCT_FORMAT,
        mac_b, bserver, ip_b, subnet_b, gw_b, myport,
        peerip_b, peerport,
        speed_hw, databit, parity, stopbit, flow,
        d_ch, d_size, d_time, i_time, debugoff, appver,
        dhcp, udp, connect, dns_flag, dns_ip_b, d_sip_b,
        scfg, scfg_b,
        pppoe_id_b, pppoe_pass_b,
        en_tcppass, tcppass_b, padding,
    )
    assert len(raw) == BOARD_INFO_SIZE
    return b'SETT' + raw


def build_firs(d: dict) -> bytes:
    """펌웨어 업로드 시작 패킷: 'FIRS' + 163바이트"""
    return b'FIRS' + build_sett(d)[4:]


def build_find() -> bytes:
    """검색 브로드캐스트 패킷"""
    return b'FIND'
