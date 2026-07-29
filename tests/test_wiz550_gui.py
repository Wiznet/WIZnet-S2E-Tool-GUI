#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_wiz550_gui.py — Phase 6 GUI Integration 단위 테스트

Wave 0: 모든 GUI 연동 테스트는 xfail(strict=False) 스텁으로 시작.
        Wave 1~3 구현 완료 시 마커를 제거하여 GREEN으로 전환.

Nyquist 상태 (Wave 0 완료 후):
  - nyquist_compliant: true
  - tests/test_wiz550_handler.py: 이미 존재 (Phase 4 산출물)
  - tests/test_wiz550_gui.py: 이 파일 (Phase 6 Wave 0 신규)

Req Coverage:
  UI-01: test_merge_wiz550_results, test_search_each_dev_filters_wiz550
  UI-02: test_build_panel_sections, test_disabled_field_widget
  UI-03: test_setinfo_roundtrip
  UI-04: test_wiz550_resetter_opcodes
"""

import pytest
import struct

# ─────────────────────────────────────────────────────────────────
# UI-01: 검색 결과 병합 + search_each_dev 필터
# ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=False, reason="Wave 1 구현 전 스텁")
def test_merge_wiz550_results(qapp):
    """
    _merge_wiz550_results 호출 후 dev_profile에 _proto='wiz550' 장치가 추가된다.
    Wave 1 구현 후: MainWindow 인스턴스를 생성하고 _merge_wiz550_results를 직접 호출.
    """
    # TODO (Wave 1): from main_gui import WIZwindow 후 실제 테스트 구현
    pytest.xfail("Wave 1 구현 전")


@pytest.mark.xfail(strict=False, reason="Wave 1 구현 전 스텁")
def test_search_each_dev_filters_wiz550(qapp):
    """
    search_each_dev()가 _proto='wiz550' 장치를 dev_info_list에서 제외한다.
    Wave 1 구현 후: dev_profile에 wiz550 장치 추가 → search_each_dev 호출 → 해당 MAC 제외 확인.
    """
    pytest.xfail("Wave 1 구현 전")


# ─────────────────────────────────────────────────────────────────
# UI-02: 패널 빌드 + disabled 필드
# ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=False, reason="Wave 2 구현 전 스텁")
def test_build_panel_sections(qapp):
    """
    _build_wiz550_panel('WIZ550SR') → 3개 QGroupBox
    _build_wiz550_panel('WIZ550WEB') → 4개 QGroupBox (network/uart0/uart1/options)
    Wave 2 구현 후: QGroupBox 자식 위젯 수 검증.
    """
    pytest.xfail("Wave 2 구현 전")


@pytest.mark.xfail(strict=False, reason="Wave 2 구현 전 스텁")
def test_disabled_field_widget(qapp):
    """
    WIZ550WEB disabled:true 필드(working_mode, remote_ip 등)의 위젯이
    isEnabled() == False 인지 확인 (WR-01 해소).
    Wave 2 구현 후: _make_wiz550_field_widget({'id': 'working_mode', 'type': 'dropdown', 'disabled': True, 'choices': {}}) → isEnabled() == False.
    """
    pytest.xfail("Wave 2 구현 전")


# ─────────────────────────────────────────────────────────────────
# UI-03: 설정 쓰기 왕복 테스트
# ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=False, reason="Wave 3 구현 전 스텁")
def test_setinfo_roundtrip(qapp):
    """
    parse_sr(raw_bytes) → fill_devinfo_wiz550() → fill_setinfo_wiz550() → build_sr(d)
    결과가 원본 raw_bytes와 동일한지 확인 (왕복 테스트).
    Wave 3 구현 후: WIZ550SR 162B 더미 패킷으로 검증.
    """
    pytest.xfail("Wave 3 구현 전")


# ─────────────────────────────────────────────────────────────────
# UI-04: Resetter op_code 상수 검증 (즉시 PASS 가능)
# ─────────────────────────────────────────────────────────────────

def test_wiz550_resetter_opcodes():
    """
    WIZ550Resetter가 OP_REMOTE_RESET(0xE0) / OP_FACTORY_RESET(0xF0) 상수를 보유한다.
    GUI 없이 import만으로 검증 가능 — xfail 없이 즉시 PASS.
    """
    from WIZ550MSGHandler import OP_REMOTE_RESET, OP_FACTORY_RESET, WIZ550Resetter
    assert OP_REMOTE_RESET  == 0xE0, f"OP_REMOTE_RESET 오류: {hex(OP_REMOTE_RESET)}"
    assert OP_FACTORY_RESET == 0xF0, f"OP_FACTORY_RESET 오류: {hex(OP_FACTORY_RESET)}"
    # WIZ550Resetter 기본 op_code 확인
    import inspect
    sig = inspect.signature(WIZ550Resetter.__init__)
    default_op = sig.parameters['op_code'].default
    assert default_op == OP_REMOTE_RESET, \
        f"WIZ550Resetter 기본 op_code 오류: {hex(default_op)}"
