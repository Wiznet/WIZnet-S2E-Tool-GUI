#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_wiz550_handler.py — WIZ550MSGHandler 단위 테스트

Wave 0: 테스트 스텁 (XFAIL) — Wave 1 구현 후 PASS로 전환됨.
커버 요구사항: PROTO-02, PROTO-03, PROTO-05, D-08(recv[6~7] 재파싱)
"""
import pytest

# Wave 0: WIZ550MSGHandler 미구현 → 모든 테스트 XFAIL
# Wave 1 완료 후 이 import가 성공해야 GREEN 전환 가능
try:
    from WIZ550MSGHandler import (
        _build_discovery_all,
        _build_get_info,
        _build_set_info,
        _build_reset,
        _encrypt,
        _decrypt,
        _make_valid_and_key,
        _parse_discovery_reply,
        _parse_get_info_reply,
        _parse_set_reply,
        WIZ550_PORT,
        STX,
        OP_DISCOVERY_ALL,
        OP_GET_INFO,
        OP_SET_INFO,
        OP_REMOTE_RESET,
        OP_FACTORY_RESET,
        WIZNET_REQUEST,
        WIZNET_REPLY,
        WIZ550Searcher,
        WIZ550Getter,
        WIZ550Setter,
        WIZ550Resetter,
    )
    _MODULE_AVAILABLE = True
except ImportError:
    _MODULE_AVAILABLE = False

skip_if_missing = pytest.mark.skipif(
    not _MODULE_AVAILABLE,
    reason="WIZ550MSGHandler 미구현 (Wave 1 대기)"
)


# ─────────────────────────────────────────────────────────────
# PROTO-02: 7바이트 헤더 빌드 + 파싱 왕복
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_header_constants():
    """상수값 확인: STX=0xA5, PORT=6550, REQUEST=0xAA, REPLY=0x55"""
    assert STX == 0xA5
    assert WIZ550_PORT == 6550
    assert WIZNET_REQUEST == 0xAA
    assert WIZNET_REPLY == 0x55
    assert OP_DISCOVERY_ALL == 0xA1
    assert OP_GET_INFO      == 0xB0
    assert OP_SET_INFO      == 0xC0
    assert OP_REMOTE_RESET  == 0xE0
    assert OP_FACTORY_RESET == 0xF0


@skip_if_missing
def test_discovery_all_packet_length():
    """DISCOVERY_ALL 패킷은 정확히 7B (payload 없음, PROTO-02)"""
    pkt = _build_discovery_all()
    assert isinstance(pkt, bytes)
    assert len(pkt) == 7
    assert pkt[0] == STX           # STX
    assert pkt[3] == OP_DISCOVERY_ALL
    assert pkt[4] == WIZNET_REQUEST


@skip_if_missing
def test_get_info_packet_length():
    """GET_INFO 패킷은 7B 헤더 + 6B payload = 13B (PROTO-02, PROTO-04)"""
    mac = "00:08:DC:AB:CD:EF"
    pkt = _build_get_info(mac)
    assert isinstance(pkt, bytes)
    assert len(pkt) == 7 + 6  # 헤더 + MAC 6B
    assert pkt[0] == STX
    assert pkt[3] == OP_GET_INFO


# ─────────────────────────────────────────────────────────────
# PROTO-03: XOR 암호화/복호화 왕복
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_xor_roundtrip():
    """encrypt 후 decrypt하면 원본과 동일해야 함 (PROTO-03, D-06, D-07)"""
    original = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A'
    key = 0x42  # 임의 키
    buf = bytearray(7) + bytearray(original)  # 7B 헤더 + payload
    _encrypt(buf, key)
    # 헤더 7B는 변경 없어야 함
    assert buf[:7] == bytearray(7)
    # payload XOR 후 다름
    encrypted_payload = bytes(buf[7:])
    assert encrypted_payload != original
    # decrypt 왕복
    decrypted = _decrypt(bytes(buf[7:]), key, len(original))
    assert decrypted == original


@skip_if_missing
def test_make_valid_and_key():
    """valid는 0x80~0xFE 범위, key=valid&0x7F (D-06)"""
    for _ in range(20):
        valid, key = _make_valid_and_key()
        assert 0x80 <= valid <= 0xFE, f"valid={valid:#04x} 범위 초과"
        assert key == (valid & 0x7F)
        assert 0x00 <= key <= 0x7E


# ─────────────────────────────────────────────────────────────
# PROTO-05: Discovery 응답 장치 타입 판별
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_discovery_parse_sr(discovery_reply_sr):
    """product_code=[0x02,0x00,0x00] → WIZ550SR (D-03, PROTO-05)"""
    result = _parse_discovery_reply(discovery_reply_sr)
    assert result is not None
    assert result['device_type'] == 'WIZ550SR'
    assert result['mac'] == '00:08:DC:AB:CD:EF'
    assert result['_proto'] == 'wiz550'


@skip_if_missing
def test_discovery_parse_unknown():
    """알 수 없는 product_code → None 반환 (D-03 무시 정책)"""
    header = bytes([0xA5, 0x01, 0x00, 0xA1, 0x55, 0x0C, 0x00])
    unknown_product = bytes([0xFF, 0xFF, 0xFF])
    fw_ver          = bytes([0x01, 0x00, 0x01])
    mac             = bytes([0x00, 0x08, 0xDC, 0x00, 0x00, 0x01])
    pkt = header + unknown_product + fw_ver + mac
    result = _parse_discovery_reply(pkt)
    assert result is None


@skip_if_missing
def test_discovery_parse_too_short():
    """12B 미만 payload → None 반환 (길이 검증, ASVS V5)"""
    result = _parse_discovery_reply(b'\xA5' * 10)
    assert result is None


# ─────────────────────────────────────────────────────────────
# D-08: GET_INFO recv[6~7] MSB 버그 우회
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_get_info_length_parse(get_info_reply_sr):
    """
    GET_INFO 응답 파싱 시 config_len을 recv[6~7]에서 직접 추출 (D-08).
    반환 dict에 'local_ip', 'mac' 키 포함 — 162B SR 파싱 성공 확인.
    """
    result = _parse_get_info_reply(get_info_reply_sr, 'WIZ550SR')
    assert isinstance(result, dict)
    assert len(result) > 0, "빈 dict — 파싱 실패"
    assert 'local_ip' in result
    assert 'mac' in result
    assert result['local_ip'] == '192.168.0.100'
    assert result['mac'] == '00:08:DC:AB:CD:EF'
