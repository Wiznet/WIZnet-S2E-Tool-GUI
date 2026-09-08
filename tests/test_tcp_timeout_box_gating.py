# -*- coding: utf-8 -*-
"""TCP timeout 그룹박스 가시성의 전제를 고정한다.

`_apply_serial_from_spec()` 은 `TR` 이 없는 기종에서 `tcp_timeoutbox` 를 통째로 숨긴다.
상자 안에 다른 위젯이 생기면 그것까지 사라지므로, 구성이 바뀌면 알아채야 한다.

배경: WIZ752SR-12x 는 펌웨어에 `TR` 이 없어 입력칸만 숨겨져 있었고 "TCP timeout" 제목의
빈 상자가 남아 있었다(2026-09-08 실기기 확인).
"""

from __future__ import annotations

import io
import re

from device_spec_loader import load_device

UI_PATH = "gui/wizconfig_gui.ui"


def _groupbox_children(name: str) -> list[tuple[str, str]]:
    s = io.open(UI_PATH, encoding="utf-8").read()
    i = s.index(f'<widget class="QGroupBox" name="{name}">')
    depth, j = 0, i
    token = re.compile(r"<widget\b|</widget>")
    while True:
        m = token.search(s, j)
        if m is None:
            break
        if m.group(0) == "</widget>":
            depth -= 1
            if depth == 0:
                j = m.end()
                break
        else:
            depth += 1
        j = m.end()
    return re.findall(r'<widget class="(\w+)" name="(\w+)">', s[i:j])[1:]


def test_tcp_timeout_box_holds_only_the_timeout_widgets():
    """상자를 통째로 숨겨도 다른 것이 딸려 사라지지 않는다."""
    children = _groupbox_children("tcp_timeoutbox")
    assert sorted(n for _, n in children) == ["tcp_timeout", "tcp_timeout_label"], (
        f"tcp_timeoutbox 구성이 바뀌었다 — {children}. "
        "다른 위젯이 들어왔다면 상자째 숨기는 코드를 다시 봐야 한다"
    )


def test_devices_without_tr_are_the_ones_that_hide_the_box():
    """상자를 숨기는 기준은 spec 의 TR 보유 여부다."""
    assert "TR" not in load_device("WIZ752SR-12x").search_cmd_list, "752 는 FW 에 TR 이 없다"
    assert "TR" in load_device("WIZ750SR").search_cmd_list, "750 은 TR 이 있다"
    assert "TR" in load_device("WIZ5XXSR-RP").search_cmd_list, "RP 는 TR 이 있다(2026-09-08 복구)"
