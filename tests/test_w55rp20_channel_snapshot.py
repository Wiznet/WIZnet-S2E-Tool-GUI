#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W55RP20-S2E 2CH/3CH/4CH 채널(CH1~CH3) fill/setcmd 스냅샷.

TASK-W55RP20-CH4-ABSORB 7단계 계획의 2~4단계.

- 2단계: main_gui.py 의 CH1~CH3 fill_devinfo/get_object_value 블록(당시 ~400줄
  순수 미러)을 `channel_field_map`과 교차 검증해 리팩토링 전 동작을 고정.
- 3단계: 그 ~400줄을 channel_field_map(gate=False) 호출로 대체 — 이 테스트가
  diff 없이 통과해 "동작 무변경 리팩토링" 증명(fill 방향, 그리고 당시의
  setcmd gate=False 시나리오).
- 4단계(현재): get_object_value() 의 CH1~CH3 setcmd 호출을 `gate=True`로 전환 —
  "장치가 마지막 GET 에서 실제로 보고한 키(`self._last_ch_dev_data`)만 되돌려
  보낸다"로 바꿔 C1(잔상 인덱스)·C2(SET 게이트 부재)를 막는다. setcmd 관련
  테스트는 이제 `gate=True` + 동일 `dev_data`로 real 코드와 엔진을 대조하고,
  gate 가 실제로 걸러내는지(스테일 콤보 인덱스·미보고 코드 미전송)를 검증하는
  케이스를 추가했다.

장비 없는 상태의 유일한 등가성 심판(계획서 표현) — 실제 main_gui.py 와
channel_field_map 을 **같은 Qt 위젯 이름 규칙**으로 별도 창 두 개에 나란히
적용해 값을 대조한다(가짜 위젯이 아니라 real QComboBox/QLineEdit/QRadioButton).

알려진 의도된 차이(엔진이 모델링하지 않는 것, 버그 아님):
- CH1 의 uart_name(EI) — 2CH 는 애초에 EI 를 조회하지 않아(TASK-W55RP20-CH4-ABSORB
  M1 수정, WIZMakeCMD.cmd_w55rp20_2ch_ch1 에서 EI 제거) dev_data 에 없고, 실제
  fill_devinfo 는 `_apply_uart_interface`의 else 분기(콤보 비활성화 + EN 문자열
  표시)를 타는데 channel_field_map.fill_channel_widgets 는 그 폴백을 모델링하지
  않는다(코드가 dev_data 에 없으면 그냥 건드리지 않음) — 그래서 이 조합만 비교에서
  제외한다.
"""
import pytest

from channel_field_map import (
    OPMODE_RADIOS, _iter_rows,
    build_channel_setcmd, fill_channel_widgets, widget_name,
)

MAC = "00:08:DC:AB:CD:EF"

TIERS = [
    ("W55RP20-S2E-2CH", [1]),
    ("W55RP20-S2E-3CH", [1, 2]),
    ("W55RP20-S2E-4CH", [1, 2, 3]),
]

# 채널 필드별 대표값 — combo 는 모든 콤보가 갖는 최소 항목 수(uart_name=4) 안에서
# 고른다. text30 필드는 별도 시나리오(경계값)에서 다시 다룬다.
FIELD_VALUES = {
    "status": "OPEN",
    "uart_name": "1",
    "opmode": "1",           # tcpserver
    "localport": "5000",
    "remoteip": "192.168.0.77",
    "remoteport": "5001",
    "baud": "12",
    "databit": "1",
    "parity": "0",
    "stopbit": "0",
    "flow": "2",
    "pack_time": "100",
    "pack_size": "10",
    "pack_char": "2D",
    "inact_timer": "60",
    "keepalive_enable": "1",
    "keepalive_initial": "5000",
    "keepalive_retry": "3000",
    "reconnection": "3000",
    "ssl_recv_timeout": "0",
    "modbus_protocol": "0",
    "serial_connection_condition_connect": "hello",
    "serial_connection_condition_disconnect": "bye",
    "ethernet_connection_condition": "net",
}


def _prep(win, dev, ver="1.2.2", status="OPEN"):
    win.curr_mac = MAC
    win.curr_dev = dev
    win.curr_ver = ver
    win.curr_st = status


@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


@pytest.fixture
def ref(qapp):
    """channel_field_map 을 real 위젯에 적용할 두 번째 창(비교 대상)."""
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


def _build_dev_data(channels, skip_ch1_uart_name=False):
    d = {}
    for suffix, codes, kind, opts in _iter_rows():
        for ch in channels:
            if suffix == "uart_name" and ch == 1 and skip_ch1_uart_name:
                continue
            d[codes[ch - 1]] = FIELD_VALUES[suffix]
    return d


def _read_widget(window, ch, suffix, kind, opts):
    if kind == "opmode":
        for name in OPMODE_RADIOS:
            if getattr(window, f"ch{ch}_{name}").isChecked():
                return name
        return None
    w = getattr(window, widget_name(ch, suffix, opts))
    if kind == "combo":
        return w.currentIndex()
    if kind == "checkbox":
        return w.isChecked()
    return w.text()  # text / text30 / label


def _set_widget(window, ch, suffix, kind, opts, value):
    if kind == "opmode":
        getattr(window, f"ch{ch}_{OPMODE_RADIOS[int(value)]}").setChecked(True)
        return
    if kind == "label":
        return  # fill 전용, SET 시나리오엔 없음
    w = getattr(window, widget_name(ch, suffix, opts))
    if kind == "combo":
        w.setCurrentIndex(int(value))
    elif kind == "checkbox":
        w.setChecked(value == "1")
    else:  # text / text30
        w.setText(value)


# ── 1. FILL: dev_data → 위젯 ────────────────────────────────────────

@pytest.mark.parametrize("dev,channels", TIERS)
def test_fill_matches_channel_field_map_reference(win, ref, dev, channels):
    _prep(win, dev)
    _prep(ref, dev)
    skip_ch1_uart_name = (dev == "W55RP20-S2E-2CH")
    dev_data = _build_dev_data(channels, skip_ch1_uart_name)

    # baud 콤보는 fill_devinfo() 의 finally 블록이 부르는 object_config() ->
    # _apply_serial_from_spec() 이 위젯 값이 아니라 dev_profile[mac] 에서 다시
    # 읽어 재구성한다(고속 baud 항목 유무가 FW 버전에 따라 달라지므로) — 실제
    # 운영 흐름과 같이 미리 채워 둬야 한다(WIZ550 쪽 test_wiz550_general_fields.py
    # _load() 헬퍼와 동일 패턴).
    win.dev_profile[MAC] = dict(dev_data)
    win.fill_devinfo(dev_data)
    for ch in channels:
        fill_channel_widgets(ch, dev_data, lambda name, w=ref: getattr(w, name))

    mismatches = []
    for ch in channels:
        for suffix, codes, kind, opts in _iter_rows():
            if suffix == "uart_name" and ch == 1 and skip_ch1_uart_name:
                continue  # 의도된 차이 — 모듈 docstring 참고
            code = codes[ch - 1]
            if code not in dev_data:
                continue
            got = _read_widget(win, ch, suffix, kind, opts)
            want = _read_widget(ref, ch, suffix, kind, opts)
            if got != want:
                mismatches.append(
                    f"ch{ch}.{suffix}({code}): real={got!r} engine={want!r}"
                )
    assert not mismatches, f"{dev}: " + "; ".join(mismatches)


# ── 2. SETCMD: 위젯 → setcmd (기본 시나리오, keepalive on, gate=True) ─

@pytest.mark.parametrize("dev,channels", TIERS)
def test_setcmd_matches_channel_field_map_reference(win, ref, dev, channels):
    _prep(win, dev)
    _prep(ref, dev)
    # gate=True 는 dev_data(장치가 보고한 키)에 있는 코드만 보낸다 — 이 테스트는
    # "정상적으로 전부 보고된 경우" 시나리오이므로 dev_data 에 전 필드를 채워
    # 게이트가 아무것도 걸러내지 않게 한다. 게이트가 실제로 거르는 경우는
    # test_setcmd_gate_blocks_unreported_codes 에서 별도로 본다.
    dev_data = _build_dev_data(channels)
    win._last_ch_dev_data = dev_data

    for ch in channels:
        for suffix, codes, kind, opts in _iter_rows():
            value = FIELD_VALUES[suffix]
            _set_widget(win, ch, suffix, kind, opts, value)
            _set_widget(ref, ch, suffix, kind, opts, value)

    real_setcmd = win.get_object_value()
    expected = {}
    for ch in channels:
        build_channel_setcmd(
            ch, dev_data, lambda name, w=ref: getattr(w, name), expected, gate=True
        )

    channel_codes = {
        codes[ch - 1]
        for ch in channels
        for _suffix, codes, kind, _opts in _iter_rows()
        if kind != "label"
    }
    real_channel_setcmd = {k: v for k, v in real_setcmd.items() if k in channel_codes}
    assert real_channel_setcmd == expected, (
        f"{dev}: diff keys={set(real_channel_setcmd) ^ set(expected)}, "
        f"real={real_channel_setcmd}, engine={expected}"
    )


# ── 3. SETCMD 경계: keepalive off + text30 절단/센티널 (gate=True) ───

@pytest.mark.parametrize("dev,channels", TIERS)
def test_setcmd_keepalive_off_and_text30_boundary(win, ref, dev, channels):
    _prep(win, dev)
    _prep(ref, dev)
    dev_data = _build_dev_data(channels)
    win._last_ch_dev_data = dev_data

    overlong = "A" * 35
    for ch in channels:
        for suffix, codes, kind, opts in _iter_rows():
            if suffix == "keepalive_enable":
                value = "0"
            elif kind == "text30" and suffix == "serial_connection_condition_connect":
                value = overlong
            elif kind == "text30":
                value = ""  # 빈 값 → " " 센티널 확인
            else:
                value = FIELD_VALUES[suffix]
            _set_widget(win, ch, suffix, kind, opts, value)
            _set_widget(ref, ch, suffix, kind, opts, value)

    real_setcmd = win.get_object_value()
    expected = {}
    for ch in channels:
        build_channel_setcmd(
            ch, dev_data, lambda name, w=ref: getattr(w, name), expected, gate=True
        )

    channel_codes = {
        codes[ch - 1]
        for ch in channels
        for _suffix, codes, kind, _opts in _iter_rows()
        if kind != "label"
    }
    real_channel_setcmd = {k: v for k, v in real_setcmd.items() if k in channel_codes}
    assert real_channel_setcmd == expected, (
        f"{dev}: diff keys={set(real_channel_setcmd) ^ set(expected)}, "
        f"real={real_channel_setcmd}, engine={expected}"
    )

    for ch in channels:
        for suffix, codes, kind, _opts in _iter_rows():
            if suffix == "keepalive_initial" or suffix == "keepalive_retry":
                code = codes[ch - 1]
                assert code not in real_setcmd, (
                    f"{dev} ch{ch}: keepalive off인데 {code} 가 전송됨(잔상)"
                )


# ── 4. SETCMD 게이트: 미보고 코드·잔상 인덱스 차단 (C1/C2, 4단계 핵심) ─

@pytest.mark.parametrize("dev,channels", TIERS)
def test_setcmd_gate_blocks_unreported_codes(win, dev, channels):
    """C1(잔상 인덱스)+C2(SET 게이트 부재) 재현·차단 확인.

    시나리오: 이전에 선택했던 다른 장치가 남긴 콤보 인덱스가 위젯에 그대로 있고
    (예: uart_name=2), 지금 장치는 구버전 FW라 채널 확장 커맨드를 아예 안
    보고했다(dev_data 에 해당 채널 코드가 하나도 없음) — WIZMakeCMD 의
    "하위 버전은 기본 명령으로만 구성" 분기가 실제로 만드는 상황과 같다.
    gate=True 라면 이 채널의 코드는 하나도 setcmd 에 들어가면 안 된다.
    """
    ch = channels[-1]  # 이 장치의 "가장 확장된" 채널 — 잔상이 가장 잘 드러난다
    _prep(win, dev)
    win._last_ch_dev_data = {}  # 구버전 FW: 이 채널 코드 전혀 미보고

    for suffix, codes, kind, opts in _iter_rows():
        value = FIELD_VALUES[suffix]
        _set_widget(win, ch, suffix, kind, opts, value)  # 잔상 시뮬레이션

    real_setcmd = win.get_object_value()
    leaked = {codes[ch - 1] for _s, codes, kind, _o in _iter_rows() if kind != "label"}
    sent = leaked & set(real_setcmd)
    assert not sent, f"{dev} ch{ch}: 미보고 채널인데 전송됨(C1/C2 재발) — {sent}"


@pytest.mark.parametrize("dev,channels", TIERS)
def test_setcmd_gate_passes_only_reported_codes(win, dev, channels):
    """부분 보고 — dev_data 에 있는 코드만 정확히 통과하는지(전체도 아니고 0개도 아님)."""
    ch = channels[-1]
    _prep(win, dev)
    # 이 채널에서 딱 하나(GL/QL 계열 로컬포트)만 보고됐다고 가정
    reported_suffix = "localport"
    codes_by_suffix = {s: codes for s, codes, _k, _o in _iter_rows()}
    reported_code = codes_by_suffix[reported_suffix][ch - 1]
    win._last_ch_dev_data = {reported_code: FIELD_VALUES[reported_suffix]}

    for suffix, codes, kind, opts in _iter_rows():
        _set_widget(win, ch, suffix, kind, opts, FIELD_VALUES[suffix])

    real_setcmd = win.get_object_value()
    all_codes = {codes[ch - 1] for _s, codes, kind, _o in _iter_rows() if kind != "label"}
    sent_from_channel = all_codes & set(real_setcmd)
    assert sent_from_channel == {reported_code}, (
        f"{dev} ch{ch}: {reported_code} 하나만 보고됐는데 {sent_from_channel} 가 전송됨"
    )
