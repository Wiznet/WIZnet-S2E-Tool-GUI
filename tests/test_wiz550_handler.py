#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_wiz550_handler.py — WIZ550MSGHandler 단위 테스트

Phase 4 Plan 01 — PROTO-02, PROTO-03, PROTO-05, D-08 검증

테스트 커버리지:
  - test_header_constants       : 상수 값 검증 (PROTO-02)
  - test_discovery_all_packet_length : DISCOVERY_ALL 패킷 7B (PROTO-04)
  - test_get_info_packet_length : GET_INFO 패킷 13B (PROTO-04)
  - test_xor_roundtrip          : XOR encrypt/decrypt 왕복 (PROTO-03, D-06, D-07)
  - test_make_valid_and_key     : valid 범위 + key 관계 검증 (D-06)
  - test_discovery_parse_sr     : SR product_code 판별 (PROTO-05, D-03)
  - test_discovery_parse_unknown: 미지 product_code → None (D-03)
  - test_discovery_parse_too_short: 짧은 패킷 → None (T-04-01-01)
  - test_get_info_length_parse  : recv[6~7] config_len 재파싱 (D-08)
"""

import pytest


# ─────────────────────────────────────────────────────────────────
# 상수 테스트 (PROTO-02)
# ─────────────────────────────────────────────────────────────────

def test_header_constants():
    """STX, PORT, REQUEST/REPLY, OP_* 상수가 정확한 값인지 검증"""
    from WIZ550MSGHandler import (
        STX, WIZ550_PORT, WIZNET_REQUEST, WIZNET_REPLY,
        OP_DISCOVERY_ALL, OP_GET_INFO, OP_SET_INFO,
        OP_REMOTE_RESET, OP_FACTORY_RESET,
    )
    assert STX == 0xA5
    assert WIZ550_PORT == 6550
    assert WIZNET_REQUEST == 0xAA
    assert WIZNET_REPLY == 0x55
    assert OP_DISCOVERY_ALL == 0xA1
    assert OP_GET_INFO == 0xB0
    assert OP_SET_INFO == 0xC0
    assert OP_REMOTE_RESET == 0xE0
    assert OP_FACTORY_RESET == 0xF0


# ─────────────────────────────────────────────────────────────────
# 패킷 빌더 테스트 (PROTO-04)
# ─────────────────────────────────────────────────────────────────

def test_discovery_all_packet_length():
    """DISCOVERY_ALL 패킷은 정확히 7B이고 STX=0xA5, [3]=0xA1, [4]=0xAA"""
    from WIZ550MSGHandler import _build_discovery_all, STX, WIZNET_REQUEST, OP_DISCOVERY_ALL
    pkt = _build_discovery_all()
    assert len(pkt) == 7, f"DISCOVERY_ALL 패킷은 7B여야 함, 실제: {len(pkt)}B"
    assert pkt[0] == STX
    assert pkt[3] == OP_DISCOVERY_ALL
    assert pkt[4] == WIZNET_REQUEST
    # 브로드캐스트: unicast 필드 = 0x00
    assert pkt[2] == 0x00, "DISCOVERY_ALL은 브로드캐스트(unicast=0x00)여야 함"
    # payload 없음: length = 0
    assert pkt[5] == 0x00
    assert pkt[6] == 0x00


def test_get_info_packet_length():
    """GET_INFO 패킷은 정확히 13B (헤더7 + MAC6)"""
    from WIZ550MSGHandler import _build_get_info
    pkt = _build_get_info("00:08:DC:AB:CD:EF")
    assert len(pkt) == 13, f"GET_INFO 패킷은 13B여야 함, 실제: {len(pkt)}B"


# ─────────────────────────────────────────────────────────────────
# XOR 암호화 테스트 (PROTO-03, D-06, D-07)
# ─────────────────────────────────────────────────────────────────

def test_xor_roundtrip():
    """
    _encrypt 후 _decrypt → 원본 payload 복원.
    헤더 7B는 encrypt 후에도 불변이어야 함 (D-07).
    """
    from WIZ550MSGHandler import _encrypt, _decrypt, _make_valid_and_key

    # 더미 payload
    original_payload = bytes(range(16))  # 0x00~0x0F
    header = bytearray(7)  # 7B 헤더 더미
    buf = header + bytearray(original_payload)

    original_header = bytes(buf[:7])

    valid, key = _make_valid_and_key()
    _encrypt(buf, key)

    # 헤더 7B 불변 확인
    assert bytes(buf[:7]) == original_header, "encrypt 후 헤더 7B가 변경됨"

    # payload 암호화됨 (key가 0이 아니면 달라야 함)
    if key != 0:
        assert bytes(buf[7:]) != original_payload, "key!=0인데 payload가 암호화되지 않음"

    # 복호화 → 원본 복원
    decrypted = _decrypt(bytes(buf[7:]), key, len(original_payload))
    assert decrypted == original_payload, "decrypt 후 원본과 불일치"


def test_make_valid_and_key():
    """
    _make_valid_and_key: valid ∈ [0x80, 0xFE], key = valid & 0x7F (D-06).
    20회 반복하여 범위 검증.
    """
    from WIZ550MSGHandler import _make_valid_and_key

    for _ in range(20):
        valid, key = _make_valid_and_key()
        assert 0x80 <= valid <= 0xFE, f"valid 범위 오류: {valid:#04x}"
        assert key == (valid & 0x7F), f"key 계산 오류: key={key}, valid&0x7F={valid & 0x7F}"
        assert 0x00 <= key <= 0x7E, f"key 범위 오류: {key:#04x}"


# ─────────────────────────────────────────────────────────────────
# Discovery 응답 파싱 테스트 (PROTO-05, D-03)
# ─────────────────────────────────────────────────────────────────

def _make_discovery_reply(product_code: bytes, fw_ver: bytes, mac: bytes,
                           encrypt: bool = False) -> bytes:
    """
    테스트용 Discovery 응답 패킷 빌드.
    7B 헤더 + 12B payload (product_code[3] + fw_ver[3] + mac[6])
    """
    payload = product_code + fw_ver + mac
    assert len(payload) == 12

    if encrypt:
        # valid bit7=1, key=0x01 (간단히 고정)
        valid = 0x81
        key = 0x01
        payload = bytes(b ^ key for b in payload)
    else:
        valid = 0x00  # bit7=0 → 암호화 없음

    header = bytearray(7)
    header[0] = 0xA5       # STX
    header[1] = valid
    header[2] = 0x00       # 브로드캐스트 응답
    header[3] = 0xA1       # OP_DISCOVERY_ALL
    header[4] = 0x55       # WIZNET_REPLY
    header[5] = len(payload) & 0xFF
    header[6] = (len(payload) >> 8) & 0xFF
    return bytes(header) + payload


def test_discovery_parse_sr():
    """
    product_code=[0x02,0x00,0x00] → WIZ550SR 판별,
    반환 dict에 device_type, mac, _proto 포함 (D-03)
    """
    from WIZ550MSGHandler import _parse_discovery_reply

    mac = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    pkt = _make_discovery_reply(
        product_code=bytes([0x02, 0x00, 0x00]),
        fw_ver=bytes([1, 0, 0]),
        mac=mac,
    )
    result = _parse_discovery_reply(pkt)
    assert result is not None, "SR 응답이 None 반환됨"
    assert result['device_type'] == 'WIZ550SR'
    assert result['mac'] == '00:08:DC:AB:CD:EF'
    assert result['_proto'] == 'wiz550'


def test_discovery_parse_unknown():
    """
    product_code=[0xFF,0xFF,0xFF] (WIZ550 계열 아님) → None 반환 (D-03)
    """
    from WIZ550MSGHandler import _parse_discovery_reply

    pkt = _make_discovery_reply(
        product_code=bytes([0xFF, 0xFF, 0xFF]),
        fw_ver=bytes([1, 0, 0]),
        mac=bytes([0x00, 0x08, 0xDC, 0x01, 0x02, 0x03]),
    )
    result = _parse_discovery_reply(pkt)
    assert result is None, f"미지 product_code에서 None 아닌 값 반환: {result}"


def test_discovery_parse_too_short():
    """
    10B 패킷 (< 19B 최소) → None 반환 (T-04-01-01)
    """
    from WIZ550MSGHandler import _parse_discovery_reply

    pkt = bytes(10)  # 최소 길이 미충족
    result = _parse_discovery_reply(pkt)
    assert result is None, "짧은 패킷에서 None 아닌 값 반환됨"


# ─────────────────────────────────────────────────────────────────
# GET_INFO 파싱 테스트 (D-08 — recv[6~7] 재파싱)
# ─────────────────────────────────────────────────────────────────

def test_get_info_length_parse(get_info_reply_sr):
    """
    _parse_get_info_reply(get_info_reply_sr, 'WIZ550SR') →
    비어있지 않은 dict, mac과 _proto 포함 (D-08)

    WIZ550Profile 미구현 시 ImportError fallback: _raw_config 포함 dict 반환.
    WIZ550Profile 구현 완료 후: local_ip='192.168.0.100' 반환.
    """
    from WIZ550MSGHandler import _parse_get_info_reply

    result = _parse_get_info_reply(get_info_reply_sr, 'WIZ550SR')
    assert isinstance(result, dict), "결과가 dict가 아님"
    assert len(result) > 0, "결과 dict가 비어있음"
    # mac 필드는 fallback과 WIZ550Profile 모두 반환해야 함
    assert 'mac' in result, f"'mac' 키 없음. 반환값: {result}"
    assert result['mac'] == '00:08:DC:AB:CD:EF', f"mac 불일치: {result['mac']}"
