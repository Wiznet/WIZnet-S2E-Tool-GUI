#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550 미지원 기능 위젯 가시성 게이팅 계약(YAML 구동) 자동 검증.

실장 없이 검증 가능한 spec 레벨 테스트. main_gui._apply_common_gating() 이 아래 결정을
widget_overrides.visible 로부터 읽어 양쪽 경로(일반/wiz550)에서 적용한다.
(override 없으면 기본 보임=True → 장치 전환 시 anti-stale 복원)

FW 근거 (research/2026-06-02-wiz550-series-characteristics.md, doc/dev/WIZ550-serial-fw-reference-ko.md):
- WIZ550SR 구조체: MQTT(4)/PPPoE/modbus/uart_interface 필드 전부 없음 → 4개 숨김
- WIZ550S2E: MQTT·Modbus 지원 → 그 둘은 보임 / uart_interface·PPPoE 없음 → 숨김
"""

from device_spec_loader import load_device

GATED = ("ch0_mqttclient", "ch0_modbus_protocol", "ch0_uart_name", "ip_pppoe")


def _visible(device: str, name: str):
    """widget_override 의 visible 결정값. override 없으면 None(=기본 보임)."""
    spec = load_device(device)
    wo = spec.ui_config.widget_overrides.get(name)
    return wo.visible if wo is not None else None


def test_sr_hides_all_unsupported():
    """WIZ550SR 은 4개 미지원 위젯을 모두 숨긴다 (visible=False)."""
    for name in GATED:
        assert _visible("WIZ550SR", name) is False, f"WIZ550SR: {name} 가 숨김(False) 이어야 함"


def test_s2e_shows_mqtt_modbus():
    """WIZ550S2E 는 MQTT·Modbus 위젯을 숨기지 않는다 (지원 기능)."""
    assert _visible("WIZ550S2E", "ch0_mqttclient") is not False, "S2E: MQTT 위젯 숨기면 안 됨"
    assert _visible("WIZ550S2E", "ch0_modbus_protocol") is not False, "S2E: Modbus 위젯 숨기면 안 됨"


def test_s2e_hides_uart_iface_and_pppoe():
    """WIZ550S2E 는 uart_interface·PPPoE 위젯을 숨긴다 (구조체 미존재)."""
    assert _visible("WIZ550S2E", "ch0_uart_name") is False, "S2E: uart_interface 위젯 숨겨야 함"
    assert _visible("WIZ550S2E", "ip_pppoe") is False, "S2E: PPPoE 위젯 숨겨야 함"
