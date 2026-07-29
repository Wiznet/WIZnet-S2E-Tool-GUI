#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_wiz550_profile.py — WIZ550Profile 단위 테스트

Wave 0: 테스트 스텁 (XFAIL) — Wave 2 구현 후 PASS로 전환됨.
커버 요구사항: PROF-01 (SR 162B), PROF-02 (S2E 가변), PROF-03 (WEB 133B)
"""
import pytest

try:
    from WIZ550Profile import (
        parse_sr,
        build_sr,
        parse_s2e,
        build_s2e,
        parse_web,
        build_web,
        SR_SIZE,
        WEB_SIZE,
    )
    _MODULE_AVAILABLE = True
except ImportError:
    _MODULE_AVAILABLE = False

skip_if_missing = pytest.mark.skipif(
    not _MODULE_AVAILABLE,
    reason="WIZ550Profile 미구현 (Wave 2 대기)"
)


# ─────────────────────────────────────────────────────────────
# PROF-01: WIZ550SR 162B 왕복 테스트
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_sr_parse_returns_dict(sr_bytes):
    """parse_sr()가 dict를 반환하고 기본 필드를 포함 (PROF-01)"""
    result = parse_sr(sr_bytes)
    assert isinstance(result, dict)
    assert result.get('device_type') == 'WIZ550SR'
    assert 'mac' in result
    assert 'local_ip' in result
    assert 'baud_rate' in result
    assert result['_proto'] == 'wiz550'


@skip_if_missing
def test_sr_roundtrip(sr_bytes):
    """parse_sr() → build_sr() → 원본과 동일 (PROF-01, 왕복 검증)"""
    parsed  = parse_sr(sr_bytes)
    rebuilt = build_sr(parsed)
    assert isinstance(rebuilt, bytes)
    assert len(rebuilt) == SR_SIZE
    assert rebuilt == sr_bytes[:SR_SIZE]


@skip_if_missing
def test_sr_parse_too_short():
    """162B 미만 → 빈 dict 반환, 예외 없음 (ASVS V5 입력 검증)"""
    result = parse_sr(b'\x00' * 100)
    assert isinstance(result, dict)
    assert len(result) == 0


# ─────────────────────────────────────────────────────────────
# PROF-02: WIZ550S2E 가변 구조 판별 (D-04)
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_s2e_base_variant(s2e_base_bytes):
    """162B S2E → s2e_variant='base' (PROF-02, D-04)"""
    result = parse_s2e(s2e_base_bytes)
    assert result.get('s2e_variant') == 'base'
    assert result.get('device_type') == 'WIZ550S2E'


@skip_if_missing
def test_s2e_modbus_variant(s2e_modbus_bytes):
    """164B S2E(fw_ver[1]=짝수) → s2e_variant='modbus' (PROF-02, D-04)"""
    result = parse_s2e(s2e_modbus_bytes)
    assert result.get('s2e_variant') == 'modbus'
    assert 'modbus_use' in result
    assert result['modbus_use'] == 1


@skip_if_missing
def test_s2e_mqtt_variant(s2e_mqtt_bytes):
    """232B S2E(fw_ver[1]=홀수) → s2e_variant='mqtt' (PROF-02, D-04)"""
    result = parse_s2e(s2e_mqtt_bytes)
    assert result.get('s2e_variant') == 'mqtt'
    assert 'mqtt_user' in result
    assert result['mqtt_user'] == 'mqttuser'


# ─────────────────────────────────────────────────────────────
# PROF-03: WIZ550WEB 133B 왕복 테스트
# ─────────────────────────────────────────────────────────────
@skip_if_missing
def test_web_parse_returns_dict(web_bytes):
    """parse_web()가 dict를 반환하고 WEB 전용 필드 포함 (PROF-03)"""
    result = parse_web(web_bytes)
    assert isinstance(result, dict)
    assert result.get('device_type') == 'WIZ550WEB'
    assert 'uart0_baud_rate' in result
    assert 'uart1_baud_rate' in result
    # WEB에는 pw_connect 없음 (RESEARCH.md Pitfall 6)
    assert 'remote_ip' not in result or result.get('remote_ip') is None


@skip_if_missing
def test_web_roundtrip(web_bytes):
    """parse_web() → build_web() → 원본과 동일 (PROF-03, 왕복 검증)"""
    parsed  = parse_web(web_bytes)
    rebuilt = build_web(parsed)
    assert isinstance(rebuilt, bytes)
    assert len(rebuilt) == WEB_SIZE
    assert rebuilt == web_bytes[:WEB_SIZE]
