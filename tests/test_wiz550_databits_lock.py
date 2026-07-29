#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550 data_bits 잠금 계약(YAML 구동) 자동 검증 — BUG-W550-5.

실장 없이 검증 가능한 spec 레벨 테스트:
- WIZ550SR: FW가 8 고정(DATA7BIT_ENABLE=0) → ch0_databit widget_override enabled=False
- WIZ550S2E: FW가 7·8 지원 → override 없음(=활성), data_bits 필드는 dropdown 7/8

UI 실동작(콤보 회색화/저장 왕복)은 실장(S2E 연결됨)에서 별도 확인.
FW 근거: doc/dev/WIZ550-serial-fw-reference-ko.md
"""

from pathlib import Path

import yaml

from device_spec_loader import load_device

ROOT = Path(__file__).resolve().parent.parent


def _databits_field(device: str) -> dict:
    """WIZ550 device YAML 의 serial 섹션에서 data_bits 필드 dict 반환."""
    data = yaml.safe_load((ROOT / "specs" / "devices" / f"{device}.yaml").read_text(encoding="utf-8"))
    for sec in data["ui"]["sections"]:
        for fld in sec.get("fields", []):
            if fld.get("id") == "data_bits":
                return fld
    raise AssertionError(f"{device}: data_bits 필드 없음")


def test_wiz550sr_databits_locked():
    """WIZ550SR 은 ch0_databit override enabled=False (8 고정)."""
    spec = load_device("WIZ550SR")
    wo = spec.ui_config.widget_overrides.get("ch0_databit")
    assert wo is not None, "WIZ550SR: ch0_databit widget_override 가 없음"
    assert wo.enabled is False, f"WIZ550SR: ch0_databit enabled 가 {wo.enabled} (False 여야 함)"


def test_wiz550s2e_databits_unlocked():
    """WIZ550S2E 는 ch0_databit override 없음(=기본 활성)."""
    spec = load_device("WIZ550S2E")
    wo = spec.ui_config.widget_overrides.get("ch0_databit")
    assert wo is None or wo.enabled is not False, "WIZ550S2E: data_bits 가 잠기면 안 됨 (FW 7/8 지원)"


def test_wiz550sr_yaml_databits_readonly():
    """WIZ550SR YAML data_bits 는 readonly 8-bit (FW 8 고정과 일치)."""
    fld = _databits_field("WIZ550SR")
    assert fld["type"] == "readonly"
    assert "8" in str(fld.get("value", ""))


def test_wiz550s2e_yaml_databits_dropdown_7_8():
    """WIZ550S2E YAML data_bits 는 dropdown 7/8 (FW 7·8 지원과 일치)."""
    fld = _databits_field("WIZ550S2E")
    assert fld["type"] == "dropdown", f"S2E data_bits type 이 {fld['type']} (dropdown 여야 함)"
    keys = {int(k) for k in fld["choices"].keys()}
    assert keys == {7, 8}, f"S2E data_bits choices 가 {keys} (7,8 여야 함)"
