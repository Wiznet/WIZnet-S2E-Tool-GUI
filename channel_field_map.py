# -*- coding: utf-8 -*-
"""멀티채널(CH1~CH3) 필드 ↔ 프로토콜 코드 매핑 — 단일 진실 소스.

W55RP20-S2E 2CH/3CH/4CH의 채널별 커맨드는 CH1을 기준으로 2글자 코드만
치환된 순수 미러다 (펌웨어 segcp.c 기준). 이 모듈은 그 매핑을 테이블
하나로 선언하고, fill(수신값→위젯)과 setcmd(위젯→전송값) 양방향 루프를
제공한다.

설계 원칙:
- 위젯 접근은 lookup(name) 콜러블 주입 — Qt 없이 fake로 단위 테스트 가능
- gate=True 시 "장치가 보고한 키만 되돌려 보낸다" (C1 잔상 인덱스 +
  C2 SET 버전 게이트 부재를 한 곳에서 해결)
- gate=False 시 기존(동료 브랜치) 동작과 등가 — 스냅샷 비교용
"""

# 채널 번호 범위 (CH0은 레거시 경로 유지 — 이 모듈 범위 밖)
CH_MIN = 1
CH_MAX = 3

# kind 종류:
#   combo    - QComboBox: currentIndex <-> setCurrentIndex(int)
#   text     - QLineEdit: text <-> setText
#   checkbox - QCheckBox: isChecked("1"/"0") <-> setChecked
#   text30   - QLineEdit, 30자 절단 + 빈 값은 " " 센티널
#   label    - fill 전용 (SET 없음, 예: 채널 status)
#   opmode   - 라디오 7개 그룹 (전용 핸들러)
#
# 행: (위젯 접미사, (CH1코드, CH2코드, CH3코드), kind[, opts])
# opts: {"when": 접미사}  → 해당 체크박스가 켜졌을 때만 SET에 포함
#       {"widget": 템플릿} → 위젯 이름이 "ch{ch}_{suffix}" 관례를 벗어날 때
CH_FIELD_MAP = [
    ("status",            ("QS", "GS", "CS"), "label"),
    ("uart_name",         ("EI", "WI", "YI"), "combo"),
    ("opmode",            ("AO", "TO", "JO"), "opmode"),
    ("localport",         ("QL", "GL", "CL"), "text"),
    ("remoteip",          ("QH", "GH", "CH"), "text"),
    ("remoteport",        ("AP", "TP", "JP"), "text"),
    ("baud",              ("EB", "WB", "YB"), "combo"),
    ("databit",           ("ED", "WD", "YD"), "combo"),
    ("parity",            ("EP", "WP", "YP"), "combo"),
    ("stopbit",           ("ES", "WS", "YS"), "combo"),
    ("flow",              ("EF", "WF", "YF"), "combo"),
    ("pack_time",         ("AT", "TT", "JT"), "text"),
    ("pack_size",         ("NS", "HS", "US"), "text"),
    ("pack_char",         ("ND", "HD", "UD"), "text"),
    ("inact_timer",       ("RV", "XV", "ZV"), "text"),
    ("keepalive_enable",  ("RA", "XA", "ZA"), "checkbox"),
    ("keepalive_initial", ("RS", "XS", "ZS"), "text", {"when": "keepalive_enable"}),
    ("keepalive_retry",   ("RE", "XE", "ZE"), "text", {"when": "keepalive_enable"}),
    ("reconnection",      ("RR", "XR", "ZR"), "text"),
    ("ssl_recv_timeout",  ("RO", "XO", "ZO"), "text",
     {"widget": "lineedit_ch{ch}_ssl_recv_timeout"}),
    ("modbus_protocol",   ("EO", "WO", "YO"), "combo"),
    ("serial_connection_condition_connect",    ("RD", "XD", "ZD"), "text30"),
    ("serial_connection_condition_disconnect", ("RF", "XF", "ZF"), "text30"),
    ("ethernet_connection_condition",          ("EE", "WE", "YE"), "text30"),
]

# 리스트 순서 == 프로토콜 값 (0~6). 펌웨어 opmode enum 기준.
OPMODE_RADIOS = [
    "tcpclient",       # 0
    "tcpserver",       # 1
    "tcpmixed",        # 2
    "udp",             # 3
    "ssl_tcpclient",   # 4
    "mqttclient",      # 5
    "mqtts_client",    # 6
]


def widget_name(ch, suffix, opts=None):
    """행의 위젯 objectName. 기본 관례는 ch{ch}_{suffix}."""
    template = (opts or {}).get("widget", "ch{ch}_{suffix}")
    return template.format(ch=ch, suffix=suffix)


def _iter_rows():
    for row in CH_FIELD_MAP:
        suffix, codes, kind = row[0], row[1], row[2]
        opts = row[3] if len(row) > 3 else {}
        yield suffix, codes, kind, opts


# ── SET 방향: 위젯 → setcmd ──────────────────────────────────────

def _extract_opmode(ch, lookup):
    for val, name in enumerate(OPMODE_RADIOS):
        if lookup(f"ch{ch}_{name}").isChecked():
            return str(val)
    return None  # 어떤 라디오도 안 눌림 → 키 생략 (기존 동작과 동일)


def _extract(widget, kind):
    if kind == "combo":
        return str(widget.currentIndex())
    if kind == "text":
        return widget.text()
    if kind == "checkbox":
        return "1" if widget.isChecked() else "0"
    if kind == "text30":
        data = widget.text()
        if len(data) > 30:
            data = data[:30]
            widget.setText(data)  # 기존 동작: 절단값을 위젯에도 반영
        return data if data else " "
    return None


def build_channel_setcmd(ch, dev_data, lookup, setcmd, gate=True):
    """ch(1~3)번 채널의 SET 명령을 setcmd(dict)에 채운다.

    gate=True: dev_data(장치가 마지막으로 보고한 값)에 있는 코드만 전송.
               미보고 키 생략 → 잔상 인덱스/미지원 커맨드 전송 원천 차단.
    gate=False: 기존 동작 등가 (전 필드 무조건 전송) — 스냅샷 비교용.
    """
    for suffix, codes, kind, opts in _iter_rows():
        if kind == "label":
            continue  # fill 전용
        cmd = codes[ch - 1]
        if gate and cmd not in dev_data:
            continue
        when = opts.get("when")
        if when is not None:
            if not lookup(widget_name(ch, when)).isChecked():
                continue  # 예: keepalive off면 RS/RE 생략 (기존 동작)
        if kind == "opmode":
            val = _extract_opmode(ch, lookup)
            if val is not None:
                setcmd[cmd] = val
            continue
        setcmd[cmd] = _extract(lookup(widget_name(ch, suffix, opts)), kind)
    return setcmd


# ── fill 방향: dev_data → 위젯 ───────────────────────────────────

def _apply_opmode(ch, value, lookup):
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return
    if 0 <= idx < len(OPMODE_RADIOS):
        lookup(f"ch{ch}_{OPMODE_RADIOS[idx]}").setChecked(True)


def _apply(widget, kind, value):
    if kind == "combo":
        try:
            widget.setCurrentIndex(int(value))
        except (TypeError, ValueError):
            pass  # 비정수 응답은 무시 (기존 try/except 동작 유지)
    elif kind in ("text", "label"):
        widget.setText(value)
    elif kind == "checkbox":
        widget.setChecked(value == "1")
    elif kind == "text30":
        if value == " ":
            widget.clear()  # " " 센티널 = 빈 값 (기존 동작)
        else:
            widget.setText(value)


def fill_channel_widgets(ch, dev_data, lookup):
    """장치 응답(dev_data)을 ch(1~3)번 채널 위젯에 반영한다."""
    for suffix, codes, kind, opts in _iter_rows():
        cmd = codes[ch - 1]
        if cmd not in dev_data:
            continue
        if kind == "opmode":
            _apply_opmode(ch, dev_data[cmd], lookup)
            continue
        _apply(lookup(widget_name(ch, suffix, opts)), kind, dev_data[cmd])
