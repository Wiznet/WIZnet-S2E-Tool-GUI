#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/conftest.py — WIZ550 테스트 공통 픽스처

픽스처 데이터는 WIZ550 프로토콜 명세 기반 최소 유효 바이트 블록이다.
실제 장치 응답과 동일한 크기·구조를 갖도록 struct format 계산으로 검증됨.
"""
import struct
import pytest

# ─────────────────────────────────────────────────────────────
# 크기 상수 (04-RESEARCH.md Pattern 5 기준)
# ─────────────────────────────────────────────────────────────
SR_SIZE = 162
WEB_SIZE = 133
MQTT_EXTENSION_SIZE = 70   # 10+10+25+25
MODBUS_EXTENSION_SIZE = 2  # BB

# ─────────────────────────────────────────────────────────────
# 픽스처 헬퍼
# ─────────────────────────────────────────────────────────────
def _make_base_162(module_type: bytes, fw_ver: bytes = b'\x01\x01\x00') -> bytes:
    """
    SR/S2E 기본 162B 더미 바이트 생성.
    packet_size=162(LE), module_type, module_name(25B), fw_ver(3B), 나머지 0으로 채움.
    """
    buf = bytearray(SR_SIZE)
    # packet_size LE [0~1]
    struct.pack_into('<H', buf, 0, SR_SIZE)
    # module_type [2~4]
    buf[2:5] = module_type[:3]
    # module_name [5~29] — null-terminated ASCII
    name = b'WIZ550TEST\x00' + b'\x00' * 14
    buf[5:30] = name
    # fw_ver [30~32]
    buf[30:33] = fw_ver[:3]
    # mac [33~38] — 더미 MAC 00:08:DC:AB:CD:EF
    buf[33:39] = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    # local_ip [39~42] — 192.168.0.100
    buf[39:43] = bytes([192, 168, 0, 100])
    # gateway [43~46] — 192.168.0.1
    buf[43:47] = bytes([192, 168, 0, 1])
    # subnet [47~50] — 255.255.255.0
    buf[47:51] = bytes([255, 255, 255, 0])
    # baud_rate [74~77] — 115200 LE uint32
    struct.pack_into('<I', buf, 74, 115200)
    # data_bits [78] — 8
    buf[78] = 8
    # stop_bits [80] — 1
    buf[80] = 1
    return bytes(buf)


# ─────────────────────────────────────────────────────────────
# WIZ550SR 픽스처
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def sr_bytes() -> bytes:
    """WIZ550SR 162B 더미 Config 바이트 (module_type=[0x02,0x00,0x00])"""
    return _make_base_162(bytes([0x02, 0x00, 0x00]))


# ─────────────────────────────────────────────────────────────
# WIZ550S2E 픽스처 — 3종 변형
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def s2e_base_bytes() -> bytes:
    """WIZ550S2E 기본 162B (module_type=[0x00,0x00,0x00], fw_ver[1]=짝수(0))"""
    return _make_base_162(bytes([0x00, 0x00, 0x00]), fw_ver=b'\x01\x00\x00')


@pytest.fixture
def s2e_modbus_bytes() -> bytes:
    """WIZ550S2E Modbus 164B (fw_ver[1]=짝수(0), 길이>=164)"""
    base = bytearray(_make_base_162(bytes([0x00, 0x00, 0x00]), fw_ver=b'\x01\x00\x00'))
    # Modbus 확장 2B: modbus_use=1, modbus_mode=0
    ext = struct.pack('<BB', 1, 0)
    return bytes(base) + ext  # 164B


@pytest.fixture
def s2e_mqtt_bytes() -> bytes:
    """WIZ550S2E MQTT 232B (fw_ver[1]=홀수(1), 길이>=232)"""
    base = bytearray(_make_base_162(bytes([0x00, 0x00, 0x00]), fw_ver=b'\x01\x01\x00'))
    # MQTT 확장 70B: mqtt_user(10)+mqtt_pw(10)+pub_topic(25)+sub_topic(25)
    mqtt_user  = b'mqttuser\x00\x00'
    mqtt_pw    = b'mqttpass\x00\x00'
    pub_topic  = b'pub/test\x00' + b'\x00' * 16
    sub_topic  = b'sub/test\x00' + b'\x00' * 16
    ext = mqtt_user + mqtt_pw + pub_topic + sub_topic  # 70B
    assert len(ext) == 70
    return bytes(base) + ext  # 232B


# ─────────────────────────────────────────────────────────────
# WIZ550WEB 픽스처
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def web_bytes() -> bytes:
    """WIZ550WEB 133B 더미 Config 바이트 (module_type=[0x01,0x02,0x00])"""
    buf = bytearray(WEB_SIZE)
    # packet_size LE [0~1]
    struct.pack_into('<H', buf, 0, WEB_SIZE)
    # module_type [2~4]
    buf[2:5] = bytes([0x01, 0x02, 0x00])
    # module_name [5~29]
    buf[5:30] = b'WIZ550WEB\x00' + b'\x00' * 15
    # fw_ver [30~32]
    buf[30:33] = b'\x01\x00\x00'
    # mac [33~38] — 00:08:DC:11:22:33
    buf[33:39] = bytes([0x00, 0x08, 0xDC, 0x11, 0x22, 0x33])
    # local_ip [39~42] — 192.168.0.200
    buf[39:43] = bytes([192, 168, 0, 200])
    # gateway [43~46]
    buf[43:47] = bytes([192, 168, 0, 1])
    # subnet [47~50]
    buf[47:51] = bytes([255, 255, 255, 0])
    # uart0_baud_rate [51~54] — 9600 LE uint32
    struct.pack_into('<I', buf, 51, 9600)
    # uart0_data_bits [55] — 8
    buf[55] = 8
    # uart0_stop_bits [57] — 1
    buf[57] = 1
    # uart1_baud_rate [59~62] — 9600
    struct.pack_into('<I', buf, 59, 9600)
    # uart1_data_bits [63] — 8
    buf[63] = 8
    # uart1_stop_bits [65] — 1
    buf[65] = 1
    return bytes(buf)


# ─────────────────────────────────────────────────────────────
# Discovery 응답 픽스처 (7B 헤더 + 12B payload)
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def discovery_reply_sr() -> bytes:
    """WIZ550SR Discovery 응답 더미 패킷 (19B, 암호화 없음)"""
    # 헤더: STX=0xA5, valid=0x01(암호화 안 됨), unicast=0, op_code=0xA1, REPLY=0x55, len=12 LE
    header = bytes([0xA5, 0x01, 0x00, 0xA1, 0x55, 0x0C, 0x00])
    # payload: product_code[3] + fw_ver[3] + mac[6]
    product_code = bytes([0x02, 0x00, 0x00])  # SR
    fw_ver       = bytes([0x01, 0x00, 0x01])
    mac          = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    return header + product_code + fw_ver + mac  # 19B


@pytest.fixture
def get_info_reply_sr(sr_bytes) -> bytes:
    """
    WIZ550SR GET_INFO 응답 더미 패킷.
    7B 헤더 + payload(src_mac[6] + config_len_LE[2] + sr_bytes[162])
    D-08: recv[6~7]에서 config_len 재파싱 검증용.
    """
    config_data = sr_bytes  # 162B
    config_len  = len(config_data)  # 162
    src_mac     = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    # payload: mac[6] + len_LSB + len_MSB + config[162] = 170B
    payload = src_mac + struct.pack('<H', config_len) + config_data
    payload_len = len(payload)  # 170

    # 헤더: STX, valid=0x01(암호화 없음), unicast=1, op_code=0xB0, REPLY=0x55, len LE
    header = bytearray(7)
    header[0] = 0xA5
    header[1] = 0x01   # valid — 암호화 없음 (bit7=0)
    header[2] = 0x01
    header[3] = 0xB0
    header[4] = 0x55
    header[5] = payload_len & 0xFF
    header[6] = (payload_len >> 8) & 0xFF
    return bytes(header) + payload
