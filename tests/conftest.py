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


# ─────────────────────────────────────────────────────────────────
# WEB 133B 구조체 — test_web_roundtrip 픽스처용
# ─────────────────────────────────────────────────────────────────
WEB_FORMAT = (
    '<'
    'H'    # packet_size LE [0~1]
    '3s'   # module_type[3] [2~4]
    '25s'  # module_name[25] [5~29]
    '3s'   # fw_ver[3] [30~32]
    '6s'   # mac[6] [33~38]
    '4s'   # local_ip[4] [39~42]
    '4s'   # gateway[4] [43~46]
    '4s'   # subnet[4] [47~50]
    'I'    # uart0_baud_rate 4B LE [51~54]
    'B'    # uart0_data_bits [55]
    'B'    # uart0_parity [56]
    'B'    # uart0_stop_bits [57]
    'B'    # uart0_flow_control [58]
    'I'    # uart1_baud_rate 4B LE [59~62]
    'B'    # uart1_data_bits [63]
    'B'    # uart1_parity [64]
    'B'    # uart1_stop_bits [65]
    'B'    # uart1_flow_control [66]
    '10s'  # pw_setting[10] [67~76]
    'B'    # dhcp_use [77]
    'B'    # dns_use [78]
    '4s'   # dns_server_ip[4] [79~82]
    '50s'  # dns_domain_name[50] [83~132]
)
WEB_SIZE = 133
assert struct.calcsize(WEB_FORMAT) == WEB_SIZE

MQTT_FORMAT = '<10s10s25s25s'
MQTT_SIZE = 70
MODBUS_FORMAT = '<BB'
MODBUS_SIZE = 2


def _make_web_config_bytes() -> bytes:
    """
    테스트용 WIZ550WEB 133B Config 더미 데이터 생성.
    uart0_baud_rate=9600, uart1_baud_rate=115200
    """
    return struct.pack(
        WEB_FORMAT,
        133,                            # packet_size
        bytes([0x01, 0x02, 0x00]),      # module_type = WEB
        b'WIZ550WEB\x00' + b'\x00' * 15,  # module_name (25B)
        bytes([1, 0, 0]),               # fw_ver 1.0.0
        bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF]),  # mac
        bytes([192, 168, 0, 100]),      # local_ip
        bytes([192, 168, 0, 1]),        # gateway
        bytes([255, 255, 255, 0]),      # subnet
        9600,                           # uart0_baud_rate
        3,                              # uart0_data_bits
        0,                              # uart0_parity
        0,                              # uart0_stop_bits
        0,                              # uart0_flow_control
        115200,                         # uart1_baud_rate
        3,                              # uart1_data_bits
        0,                              # uart1_parity
        0,                              # uart1_stop_bits
        0,                              # uart1_flow_control
        b'\x00' * 10,                  # pw_setting
        0,                              # dhcp_use
        0,                              # dns_use
        bytes([0, 0, 0, 0]),            # dns_server_ip
        b'\x00' * 50,                  # dns_domain_name
    )


# ─────────────────────────────────────────────────────────────────
# WIZ550Profile 테스트용 픽스처
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sr_bytes() -> bytes:
    """WIZ550SR 162B Config 더미 데이터"""
    return _make_sr_config_bytes()


@pytest.fixture
def web_bytes() -> bytes:
    """WIZ550WEB 133B Config 더미 데이터"""
    return _make_web_config_bytes()


@pytest.fixture
def s2e_base_bytes() -> bytes:
    """WIZ550S2E 162B 기본 변형 (확장 없음)"""
    # SR과 동일 구조, module_type만 S2E
    raw = list(_make_sr_config_bytes())
    # module_type[2~4]: bytes[2]=0x00, [3]=0x00, [4]=0x00 (S2E)
    raw[2] = 0x00
    raw[3] = 0x00
    raw[4] = 0x00
    return bytes(raw)


@pytest.fixture
def s2e_modbus_bytes() -> bytes:
    """WIZ550S2E 164B Modbus 변형 (fw_ver[1]=짝수=0, +2B Modbus 확장)"""
    base = list(_make_sr_config_bytes())
    # module_type = S2E
    base[2] = 0x00
    base[3] = 0x00
    base[4] = 0x00
    # fw_ver[1] = 0 (짝수) → fw_ver은 offset 30~32
    base[31] = 0  # fw_ver[1] = 0 (짝수)
    # Modbus 확장 2B: modbus_use=1, modbus_mode=0
    ext = struct.pack(MODBUS_FORMAT, 1, 0)
    return bytes(base) + ext


@pytest.fixture
def s2e_mqtt_bytes() -> bytes:
    """WIZ550S2E 232B MQTT 변형 (fw_ver[1]=홀수=1, +70B MQTT 확장)"""
    base = list(_make_sr_config_bytes())
    # module_type = S2E
    base[2] = 0x00
    base[3] = 0x00
    base[4] = 0x00
    # fw_ver[1] = 1 (홀수) → offset 31
    base[31] = 1  # fw_ver[1] = 1 (홀수)
    # MQTT 확장 70B
    mqtt_user = b'mqttuser\x00\x00'         # 10B
    mqtt_pw   = b'mqttpass\x00\x00'         # 10B
    pub_topic = b'sensor/data\x00' + b'\x00' * 13  # 25B
    sub_topic = b'cmd/device\x00' + b'\x00' * 14   # 25B
    ext = struct.pack(MQTT_FORMAT, mqtt_user, mqtt_pw, pub_topic, sub_topic)
    return bytes(base) + ext


@pytest.fixture
def get_info_reply_sr() -> bytes:
    """
    GET_INFO(0xB0) 응답 더미 패킷 (암호화 없음).

    실제 프로토콜 구조 (RESEARCH Pattern 4 기준):
      7B 헤더
      6B src_mac
      162B system_info  ← packet_size H(2B)가 system_info[0:2] == config_len
    총 = 7 + 6 + 162 = 175B

    config_len은 별도 필드가 아니라 system_info[0:2](= packet_size)에서 읽음.
    파서: config_len = payload[6:8], system_info = payload[6:6+config_len]
    """
    config_bytes = _make_sr_config_bytes()  # 162B, [0:2] = packet_size = 162

    # payload: src_mac[6] + system_info[162]
    # system_info[0:2] = packet_size = 162 이 곧 config_len 역할
    src_mac = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    payload = src_mac + config_bytes

    header = _make_header(OP_GET_INFO, WIZNET_REPLY, len(payload))
    return header + payload


# ─────────────────────────────────────────────────────────────────
# PyQt5 GUI 테스트용 QApplication 픽스처 (Phase 6 — Wave 0)
# ─────────────────────────────────────────────────────────────────
import sys

@pytest.fixture(scope="session")
def qapp():
    """
    세션 전체에서 재사용하는 QApplication 인스턴스.
    pytest-qt 없이 순수 PyQt5로 구성.
    이미 QApplication이 존재하면 재사용한다.
    """
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # 세션 종료 시 app을 명시적으로 종료하지 않음 — pytest 종료 시 자동 해제
