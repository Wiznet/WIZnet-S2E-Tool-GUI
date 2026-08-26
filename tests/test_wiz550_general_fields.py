#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550 generalTab 미연결 필드 배선 검증 — BUG-W550-AE / AH / AI.

실장 없이 검증 가능한 UI 왕복 테스트다. 세 필드 모두 "파싱은 되는데 UI 에서 편집이
안 되던" 상태였고, 이 테스트는 위젯 ↔ profile dict 사이 코덱이 값을 잃지 않는지 본다.

  AE  packing_delimiter[4] + packing_delimiter_length  ↔  ch0_pack_char (hex)
  AF  dns_use                                          ↔  wiz550_dns_use (동적 생성)
  AG  dns_domain_name[50]                              ↔  wiz550_dns_domain (동적 생성)
  AH  serial_trigger[3]                                ↔  at_hex1/2/3 (hex 2자씩)
  AI  modbus_use / modbus_mode                         ↔  ch0_modbus_protocol

AF/AG 위젯은 .ui 에 없고 코드로 만든다. 그래서 "장치 전환 시 사라지는가"가 값 왕복만큼
중요하다. 안 숨기면 일반 장치 화면에 WIZ550 전용 칸이 유령으로 남는다.

AI 는 값 왕복뿐 아니라 **event_opmode() 가 콤보를 되돌려도 값이 살아남는지**가 핵심이다.
event_opmode 의 working_mode 제약은 WIZ750SR 계열 규칙이고 WIZ550 구조체에는 없다.
되돌림을 막지 않으면 사용자가 모드를 바꾼 순간 Modbus 가 조용히 꺼진다.

FW 근거: research/2026-06-02-wiz550-series-characteristics.md
  - modbus_mode enum: RTU=0, ASCII=1  (S2E-Modbus 164B variant 전용)
  - serial_trigger factory default: "+++" = 2B 2B 2B
  - packing_delimiter factory default: "----" = 2D×4
"""

import pytest

MAC = "00:08:DC:AB:CD:EF"


def _base_profile(**over) -> dict:
    """fill_devinfo_wiz550 가 요구하는 최소 WIZ550S2E profile dict."""
    d = {
        'device_type': 'WIZ550S2E',
        'module_name': 'WIZ550S2E',
        'fw_str': '1.2.0',
        'fw_ver': bytes([1, 2, 0]),        # minor 짝수 → Modbus 빌드
        'mac': MAC,
        's2e_variant': 'base',
        'dhcp_use': 0,
        'local_ip': '192.168.0.100',
        'subnet': '255.255.255.0',
        'gateway': '192.168.0.1',
        'dns_server_ip': '0.0.0.0',
        'working_mode': 1,                 # TCP Server (event_opmode 가 Modbus 를 켜는 모드)
        'local_port': 5000,
        'remote_ip': '0.0.0.0',
        'remote_port': 5000,
        'baud_rate': 115200,
        'data_bits': 8,
        'parity': 0,
        'stop_bits': 1,
        'flow_control': 0,
        'packing_time': 0,
        'packing_size': 0,
        'packing_delimiter': b'\x00\x00\x00\x00',
        'packing_delimiter_length': 0,
        'inactivity': 0,
        'reconnection': 3000,
        'pw_setting': '',
        'pw_connect': '',
        'dns_use': 0,
        'dns_domain_name': '',
        'serial_command': 1,
        'serial_trigger': b'+++',
    }
    d.update(over)
    return d


@pytest.fixture
def win(qapp):
    """오프스크린 WIZWindow 1개를 테스트마다 새로 만든다.

    show() 는 하지 않는다. 위젯 값 왕복만 보면 되고, 창을 띄우면 헤드리스 CI 에서
    불필요한 리소스를 잡는다.
    """
    import main_gui
    w = main_gui.WIZWindow()
    w.curr_mac = MAC
    yield w
    w.close()


def _self_enabled(w) -> bool:
    """위젯 자신의 enable 플래그만 본다.

    isEnabled() 는 조상이 하나라도 꺼져 있으면 False 다. 이 테스트는 장치를 고르지 않은
    상태라 generalTab/channel_tab 이 꺼져 있어서, isEnabled() 로는 항상 False 가 나와
    검사가 무의미해진다. isEnabledTo(부모) 는 부모까지만 보므로 자신의 플래그가 드러난다.
    """
    return w.isEnabledTo(w.parentWidget())


def _load(win, profile: dict):
    """profile 을 dev_profile 에 넣고 UI 에 채운다 (실제 GET 응답 처리와 같은 경로)."""
    win.dev_profile[MAC] = dict(profile)
    win.fill_devinfo_wiz550(profile)


# ─────────────────────────────────────────────────────────────────
# BUG-W550-AE — packing_delimiter
# ─────────────────────────────────────────────────────────────────

def test_packing_delimiter_shows_hex(win):
    """factory default "----" 는 hex 8자로 보인다."""
    _load(win, _base_profile(packing_delimiter=b'----', packing_delimiter_length=4))
    assert win.ch0_pack_char.text() == "2D2D2D2D"


def test_packing_delimiter_roundtrip(win):
    """4바이트 구분자가 왕복해도 값·길이가 그대로다."""
    _load(win, _base_profile(packing_delimiter=b'----', packing_delimiter_length=4))
    out = win.fill_setinfo_wiz550()
    assert out['packing_delimiter'] == b'----'
    assert out['packing_delimiter_length'] == 4


def test_packing_delimiter_partial_length(win):
    """length 가 4 미만이면 그만큼만 보여주고, 왕복 시 길이도 유지한다.

    구조체는 항상 4바이트를 담지만 유효 바이트 수는 length 필드가 정한다.
    length 를 무시하고 4바이트를 다 보여주면 쓰레기 값이 사용자에게 노출된다.
    """
    _load(win, _base_profile(packing_delimiter=b'\r\n\xff\xff', packing_delimiter_length=2))
    assert win.ch0_pack_char.text() == "0D0A"
    out = win.fill_setinfo_wiz550()
    assert out['packing_delimiter'] == b'\r\n\x00\x00'
    assert out['packing_delimiter_length'] == 2


def test_packing_delimiter_zero_length(win):
    """length 0 이면 빈 칸이고, 왕복해도 0 이다 (구분자 미사용)."""
    _load(win, _base_profile(packing_delimiter=b'\x00' * 4, packing_delimiter_length=0))
    assert win.ch0_pack_char.text() == ""
    out = win.fill_setinfo_wiz550()
    assert out['packing_delimiter_length'] == 0


def test_packing_delimiter_user_edit(win):
    """사용자가 칸에 직접 친 hex 가 그대로 전송값이 된다."""
    _load(win, _base_profile())
    win.ch0_pack_char.setText("0d0a")          # 소문자·구분자 없음
    out = win.fill_setinfo_wiz550()
    assert out['packing_delimiter'] == b'\r\n\x00\x00'
    assert out['packing_delimiter_length'] == 2


def test_packing_delimiter_junk_input_does_not_crash(win):
    """hex 가 아닌 입력·홀수 자리에도 예외 없이 최선 해석한다."""
    _load(win, _base_profile())
    win.ch0_pack_char.setText("zz 2D-2")       # 유효한 건 "2D2" → 홀수라 마지막 버림
    out = win.fill_setinfo_wiz550()
    assert out['packing_delimiter'] == b'-\x00\x00\x00'
    assert out['packing_delimiter_length'] == 1


# ─────────────────────────────────────────────────────────────────
# BUG-W550-AH — serial_trigger
# ─────────────────────────────────────────────────────────────────

def test_serial_trigger_shows_hex(win):
    """factory default "+++" 가 칸마다 2B 로 나뉘어 보인다."""
    _load(win, _base_profile(serial_trigger=b'+++'))
    assert (win.at_hex1.text(), win.at_hex2.text(), win.at_hex3.text()) == ("2B", "2B", "2B")


def test_serial_trigger_roundtrip(win):
    _load(win, _base_profile(serial_trigger=b'+++'))
    assert win.fill_setinfo_wiz550()['serial_trigger'] == b'+++'


def test_serial_trigger_user_edit(win):
    _load(win, _base_profile())
    win.at_hex1.setText("41")
    win.at_hex2.setText("42")
    win.at_hex3.setText("43")
    assert win.fill_setinfo_wiz550()['serial_trigger'] == b'ABC'


def test_serial_trigger_one_char_field_is_not_shifted(win):
    """칸에 한 글자만 있어도 자리가 밀리지 않는다.

    세 칸을 그냥 이어붙이면 "2"+"2B"+"2B" = "22B2B" 가 되어 0x22,0xB2 로 밀린다.
    칸마다 독립된 1바이트이므로 각각 2자로 채워야 한다.
    """
    _load(win, _base_profile())
    win.at_hex1.setText("2")
    win.at_hex2.setText("2B")
    win.at_hex3.setText("2B")
    assert win.fill_setinfo_wiz550()['serial_trigger'] == b'\x02\x2b\x2b'


def test_serial_trigger_empty_field_is_zero(win):
    """빈 칸은 0x00 으로 채운다 (구조체가 3바이트 고정)."""
    _load(win, _base_profile())
    win.at_hex1.setText("2B")
    win.at_hex2.setText("")
    win.at_hex3.setText("")
    assert win.fill_setinfo_wiz550()['serial_trigger'] == b'\x2b\x00\x00'


def test_at_hex_enabled_follows_at_enable(win):
    """serial_command=0 이면 trigger 칸이 잠긴다 (event_atmode 연동)."""
    _load(win, _base_profile(serial_command=0))
    assert not _self_enabled(win.at_hex1)
    _load(win, _base_profile(serial_command=1))
    assert _self_enabled(win.at_hex1)


# ─────────────────────────────────────────────────────────────────
# BUG-W550-AI — modbus_use / modbus_mode
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("use,mode,idx", [
    (0, 0, 0),   # NONE
    (1, 0, 1),   # RTU
    (1, 1, 2),   # ASCII
])
def test_modbus_index_mapping(win, use, mode, idx):
    """콤보 {NONE,RTU,ASCII} ↔ FW {use, mode} 매핑."""
    _load(win, _base_profile(s2e_variant='modbus', modbus_use=use, modbus_mode=mode))
    assert win.ch0_modbus_protocol.currentIndex() == idx
    out = win.fill_setinfo_wiz550()
    assert (out['modbus_use'], out['modbus_mode']) == (use, mode)


def test_modbus_enabled_only_for_modbus_variant(win):
    """variant 가 modbus 가 아니면 콤보를 잠근다.

    build_s2e 가 확장 2B 를 그때만 붙이므로, 잠그지 않으면 사용자가 바꿔도
    아무 일도 안 일어나는 조용한 no-op 가 된다.
    """
    _load(win, _base_profile(s2e_variant='base'))
    assert not _self_enabled(win.ch0_modbus_protocol)
    assert win.ch0_modbus_protocol.toolTip() != ""

    _load(win, _base_profile(s2e_variant='modbus', modbus_use=1, modbus_mode=0))
    assert _self_enabled(win.ch0_modbus_protocol)
    assert win.ch0_modbus_protocol.toolTip() == ""


def test_modbus_not_written_for_non_modbus_variant(win):
    """variant 가 modbus 가 아니면 setinfo 가 modbus 키를 새로 쓰지 않는다.

    profile 에 남아 있던 값을 콤보(NONE)로 덮어쓰면, 잠긴 상태로 Apply 했을 때
    장치의 Modbus 설정이 조용히 꺼진다.
    """
    prof = _base_profile(s2e_variant='base', modbus_use=1, modbus_mode=1)
    _load(win, prof)
    out = win.fill_setinfo_wiz550()
    assert (out['modbus_use'], out['modbus_mode']) == (1, 1)


def test_modbus_survives_working_mode_change(win):
    """working_mode 를 바꿔도 Modbus 값이 살아남는다 (핵심 회귀).

    event_opmode() 는 TCP Client 에서 Modbus 콤보를 NONE 으로 되돌린다.
    그건 WIZ750SR 계열 규칙이고 WIZ550 구조체에는 그런 제약이 없다.
    """
    _load(win, _base_profile(s2e_variant='modbus', modbus_use=1, modbus_mode=1))
    assert win.ch0_modbus_protocol.currentIndex() == 2

    win.ch0_tcpclient.setChecked(True)
    win.event_opmode()

    assert win.ch0_modbus_protocol.currentIndex() == 2, "event_opmode 가 Modbus 값을 지웠다"
    assert win.fill_setinfo_wiz550()['modbus_use'] == 1


def test_modbus_user_change_is_cached(win):
    """사용자가 고른 값이 캐시에 반영되어, 이후 event_opmode 에도 유지된다."""
    _load(win, _base_profile(s2e_variant='modbus', modbus_use=1, modbus_mode=0))
    win.ch0_modbus_protocol.setCurrentIndex(2)
    win.ch0_modbus_protocol.activated.emit(2)   # 사용자 선택과 같은 시그널

    win.ch0_tcpclient.setChecked(True)
    win.event_opmode()

    assert win.ch0_modbus_protocol.currentIndex() == 2
    assert win.fill_setinfo_wiz550()['modbus_mode'] == 1


def test_modbus_flag_cleared_on_generic_device(win):
    """일반 장치로 넘어가면 WIZ550 전용 상태가 꺼진다 (anti-stale).

    _apply_common_gating 이 장치 전환의 단일 리셋 지점이다.
    """
    from device_spec_loader import load_device

    _load(win, _base_profile(s2e_variant='modbus', modbus_use=1, modbus_mode=1))
    assert win._wiz550_modbus_active is True

    win._apply_common_gating(load_device("WIZ750SR"))
    assert win._wiz550_modbus_active is False

    win.ch0_tcpclient.setChecked(True)
    win.event_opmode()
    assert win.ch0_modbus_protocol.currentIndex() == 0, "일반 장치인데 WIZ550 복원이 걸렸다"


# ─────────────────────────────────────────────────────────────────
# 코덱 헬퍼 단위 검증
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,length,expect", [
    (b'\x2b\x2b\x2b', None, "2B2B2B"),
    (b'\x2b\x2b\x2b', 1, "2B"),
    (b'----', 0, ""),
    (b'\x00\xff', None, "00FF"),
    ('not bytes', None, ""),      # 잘못된 타입도 크래시 없이 빈 문자열
    (None, None, ""),
])
def test_bytes_to_hex(win, raw, length, expect):
    assert win._wiz550_bytes_to_hex(raw, length) == expect


@pytest.mark.parametrize("text,expect", [
    ("2B2B2B", b'\x2b\x2b\x2b'),
    ("2b2b", b'\x2b\x2b'),
    ("2B 2B", b'\x2b\x2b'),       # 공백 무시
    ("2B2", b'\x2b'),             # 홀수 자리 → 마지막 글자 버림
    ("zz", b''),
    ("", b''),
    (None, b''),
])
def test_hex_to_bytes(win, text, expect):
    assert win._wiz550_hex_to_bytes(text) == expect


# ─────────────────────────────────────────────────────────────────
# BUG-W550-AF / AG — dns_use / dns_domain_name (동적 생성 위젯)
# ─────────────────────────────────────────────────────────────────

def test_dns_widgets_exist_and_start_hidden(win):
    """위젯이 만들어져 있고, 장치를 고르기 전에는 숨어 있다.

    isVisible() 은 창을 show() 하지 않아서 항상 False 다. 명시적 숨김만 보려면
    isHidden() 을 써야 한다.
    """
    assert win.wiz550_dns_use.isHidden()
    assert win.wiz550_dns_domain.isHidden()


def test_dns_widgets_placed_next_to_dns_server(win):
    """DNS server IP 칸과 같은 레이아웃(gridLayout3)에 붙는다."""
    layout = win.gridLayout3
    placed = {layout.itemAt(i).widget() for i in range(layout.count())}
    assert win.dns_addr in placed
    assert {win.wiz550_dns_use, win.wiz550_dns_domain} <= placed


def test_dns_widgets_shown_for_wiz550(win):
    _load(win, _base_profile(dns_use=1, dns_domain_name='example.com'))
    assert not win.wiz550_dns_use.isHidden()
    assert not win.wiz550_dns_domain.isHidden()


def test_dns_roundtrip(win):
    _load(win, _base_profile(dns_use=1, dns_domain_name='device.wiznet.io'))
    assert win.wiz550_dns_use.isChecked()
    assert win.wiz550_dns_domain.text() == 'device.wiznet.io'
    out = win.fill_setinfo_wiz550()
    assert out['dns_use'] == 1
    assert out['dns_domain_name'] == 'device.wiznet.io'


def test_dns_user_edit(win):
    _load(win, _base_profile(dns_use=0, dns_domain_name=''))
    win.wiz550_dns_use.setChecked(True)
    win.wiz550_dns_domain.setText('mqtt.example.org')
    out = win.fill_setinfo_wiz550()
    assert (out['dns_use'], out['dns_domain_name']) == (1, 'mqtt.example.org')


def test_dns_domain_locked_when_unused(win):
    """dns_use=0 이면 도메인 칸이 잠긴다 (WIZ1x0SR 의 같은 쌍과 동일)."""
    _load(win, _base_profile(dns_use=0))
    assert not _self_enabled(win.wiz550_dns_domain)
    _load(win, _base_profile(dns_use=1, dns_domain_name='a.b'))
    assert _self_enabled(win.wiz550_dns_domain)


def test_dns_domain_maxlength_leaves_room_for_nul(win):
    """구조체가 50B 이고 C 문자열이라 49자까지만 받는다."""
    assert win.wiz550_dns_domain.maxLength() == 49


def test_dns_widgets_hidden_on_generic_device(win):
    """일반 장치로 넘어가면 사라진다 (anti-stale).

    안 숨기면 WIZ750SR 화면에 WIZ550 전용 칸이 그대로 남는다.
    """
    from device_spec_loader import load_device

    _load(win, _base_profile(dns_use=1, dns_domain_name='example.com'))
    assert not win.wiz550_dns_use.isHidden()

    win._apply_common_gating(load_device("WIZ750SR"))
    assert win.wiz550_dns_use.isHidden()
    assert win.wiz550_dns_domain.isHidden()


def test_dns_domain_survives_profile_build_roundtrip(win):
    """UI → build_s2e → parse_s2e 까지 도메인이 살아남는다 (50B 필드 경계 확인)."""
    from WIZ550Profile import build_s2e, parse_s2e

    domain = 'x' * 49
    _load(win, _base_profile(dns_use=1, dns_domain_name=domain))
    out = win.fill_setinfo_wiz550()
    reparsed = parse_s2e(build_s2e(out))
    assert reparsed['dns_use'] == 1
    assert reparsed['dns_domain_name'] == domain


def test_dns_row_does_not_overflow_network_group(win, qapp):
    """DNS 칸을 드러내도 network_config 가 넘치지 않는다 — 레이아웃 회귀.

    generalTab 은 부모 레이아웃 없이 고정 geometry 로 놓여서, 칸을 늘려도 그룹이
    그만큼 커지지 못한다. 라벨 + 도메인칸을 따로 둔 2행 구성은 실측에서 20px 넘쳐
    기존 dns_addr 와 세로로 겹쳤다. 이 테스트가 그 회귀를 잡는다.
    """
    win.resize(1200, 900)
    win.show()
    qapp.processEvents()

    group = win.dns_addr.parentWidget()
    _load(win, _base_profile(dns_use=1, dns_domain_name='device.wiznet.io'))
    group.parentWidget().layout().activate()
    qapp.processEvents()

    need = group.minimumSizeHint().height()
    assert need <= group.height(), (
        f"network_config 가 {need}px 필요한데 {group.height()}px 뿐 — 위젯이 겹친다"
    )

    def _bottom(w):
        return w.geometry().y() + w.geometry().height()

    assert _bottom(win.dns_addr) <= win.wiz550_dns_domain.geometry().y(), (
        "dns_addr 와 도메인 칸이 세로로 겹친다"
    )
    assert _bottom(win.dns_addr) <= win.wiz550_dns_use.geometry().y(), (
        "dns_addr 와 Use DNS 체크박스가 세로로 겹친다"
    )
    win.hide()
