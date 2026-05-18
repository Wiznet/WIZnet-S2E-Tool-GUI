#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/conftest.py — Phase 4 공통 픽스처

WIZ550 프로토콜 테스트용 더미 패킷 생성 헬퍼.
"""

import struct
import pytest


# ─────────────────────────────────────────────────────────────────
# 공통 상수 (WIZ550MSGHandler와 동기화)
# ─────────────────────────────────────────────────────────────────
STX            = 0xA5
WIZNET_REQUEST = 0xAA
WIZNET_REPLY   = 0x55
OP_DISCOVERY   = 0xA1
OP_GET_INFO    = 0xB0
WIZ550_PORT    = 6550


def _make_header(op_code: int, direction: int, payload_len: int, unicast: bool = False) -> bytes:
    """
    7B 헤더 생성 (암호화 없음 — valid bit7=0).
    direction: WIZNET_REQUEST(0xAA) 또는 WIZNET_REPLY(0x55)
    """
    buf = bytearray(7)
    buf[0] = STX
    buf[1] = 0x00              # valid: bit7=0 → 암호화 없음
    buf[2] = 0x01 if unicast else 0x00
    buf[3] = op_code
    buf[4] = direction
    buf[5] = payload_len & 0xFF
    buf[6] = (payload_len >> 8) & 0xFF
    return bytes(buf)


# ─────────────────────────────────────────────────────────────────
# SR 162B 구조체 — test_get_info_length_parse 픽스처용
# ─────────────────────────────────────────────────────────────────
SR_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'B'    # working_mode [51]
    'B'    # state [52]
    '4s'   # remote_ip[4] [53~56]
    'H'    # local_port LE [57~58]
    'H'    # remote_port LE [59~60]
    'H'    # inactivity LE [61~62]
    'H'    # reconnection LE [63~64]
    'H'    # packing_time LE [65~66]
    'B'    # packing_size [67]
    '4s'   # packing_delimiter[4] [68~71]
    'B'    # packing_delimiter_length [72]
    'B'    # packing_data_appendix [73]
    'I'    # baud_rate 4B LE [74~77]
    'B'    # data_bits [78]
    'B'    # parity [79]
    'B'    # stop_bits [80]
    'B'    # flow_control [81]
    '10s'  # pw_setting[10] [82~91]
    '10s'  # pw_connect[10] [92~101]
    'B'    # dhcp_use [102]
    'B'    # dns_use [103]
    '4s'   # dns_server_ip[4] [104~107]
    '50s'  # dns_domain_name[50] [108~157]
    'B'    # serial_command [158]
    '3s'   # serial_trigger[3] [159~161]
)
SR_SIZE = 162
assert struct.calcsize(SR_FORMAT) == SR_SIZE


def _make_sr_config_bytes() -> bytes:
    """
    테스트용 WIZ550SR 162B Config 더미 데이터 생성.
    local_ip=192.168.0.100, mac=00:08:DC:AB:CD:EF, baud_rate=115200
    """
    return struct.pack(
        SR_FORMAT,
        162,                            # packet_size
        bytes([0x02, 0x00, 0x00]),      # module_type = SR
        b'WIZ550SR\x00' + b'\x00' * 16,  # module_name (25B)
        bytes([1, 0, 0]),               # fw_ver 1.0.0
        bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF]),  # mac
        bytes([192, 168, 0, 100]),      # local_ip
        bytes([192, 168, 0, 1]),        # gateway
        bytes([255, 255, 255, 0]),      # subnet
        0,                              # working_mode
        0,                              # state
        bytes([0, 0, 0, 0]),            # remote_ip
        5000,                           # local_port
        5000,                           # remote_port
        0,                              # inactivity
        3000,                           # reconnection
        0,                              # packing_time
        0,                              # packing_size
        b'\x00' * 4,                   # packing_delimiter
        0,                              # packing_delimiter_length
        0,                              # packing_data_appendix
        115200,                         # baud_rate
        3,                              # data_bits (8-bit)
        0,                              # parity
        0,                              # stop_bits
        0,                              # flow_control
        b'\x00' * 10,                  # pw_setting
        b'\x00' * 10,                  # pw_connect
        0,                              # dhcp_use
        0,                              # dns_use
        bytes([0, 0, 0, 0]),            # dns_server_ip
        b'\x00' * 50,                  # dns_domain_name
        0,                              # serial_command
        b'\x00' * 3,                   # serial_trigger
    )


@pytest.fixture
def get_info_reply_sr() -> bytes:
    """
    GET_INFO(0xB0) 응답 더미 패킷 (암호화 없음).

    구조 (WIZ550MSGHandler._parse_get_info_reply 기대값):
      7B 헤더
      6B src_mac
      2B config_len (= 162, LE)
      162B system_info (SR Config)
    총 = 7 + 6 + 2 + 162 = 177B
    """
    config_bytes = _make_sr_config_bytes()
    config_len   = len(config_bytes)  # 162

    # payload: src_mac[6] + config_len[2] + config_data[162]
    src_mac  = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    len_le   = struct.pack('<H', config_len)   # 2B LE
    payload  = src_mac + len_le + config_bytes

    header = _make_header(OP_GET_INFO, WIZNET_REPLY, len(payload))
    return header + payload
