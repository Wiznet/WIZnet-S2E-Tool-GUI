#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W55RP20-S2E-3CH/-4CH — 가짜 SEGCP 장치로 실제 UDP 왕복(SW 대체 검증).

3CH/4CH 실기기가 없다. `tests/fake_segcp_device.py`의 spec 기반 가짜 장치로
**설정툴의 실제 코드 경로**(WIZMakeCMD.search_chunks/setcommand, main_gui.fill_devinfo/
get_object_value, device_spec_loader 의 spec 검증)를 진짜 SEGCP 와이어 바이트로
왕복시킨다 — 지금까지의 스냅샷 테스트가 위젯 레벨(real Qt, 그러나 프로토콜 인코딩은
안 봄)이었던 것과 달리, 여기서는 요청/응답 바이트 자체를 만들고 파싱한다.

**할 수 있다**: 설정툴 자신의 코드 경로 전체(검색 요청 생성 → 파싱 → 화면 배선 →
gate=True SET 필터링 → SET 요청 생성 → spec 검증) — 이 CH4 흡수 작업이 건드린
전부. 특히 4단계/5단계에서 고친 gate=True(C1/C2)가 실제 와이어 바이트 레벨에서도
작동하는지 확인한다.

**할 수 없다**: spec 이 실제 3CH/4CH 펌웨어와 100% 같은지(그건 실기기나 FW 소스가
답한다), 타이밍/버퍼 크기 실측(`config_buf_size` 미상이라 건너뜀 — 계획서 3-1/4CH
GET 129개 멀티패킷 이슈는 실기기 검증 대상으로 남는다).
"""
import pytest

from channel_field_map import _iter_rows, widget_name
from tests.fake_segcp_device import FakeSegcpDevice, mac_to_bytes, profile_from_spec
from WIZMakeCMD import WIZMakeCMD
from WIZMSGHandler import parse_reply_lines

MAC = "00:08:DC:FA:CE:04"

TIERS = [
    ("W55RP20-S2E-3CH", 2),  # 이 기종의 "가장 확장된" 채널
    ("W55RP20-S2E-4CH", 3),
]


@pytest.fixture
def win(qapp):
    import main_gui
    w = main_gui.WIZWindow()
    yield w
    w.close()


def _wire_search(dev, devname, ver, status="OPEN"):
    """설정툴이 실제로 만드는 검색 요청을 그대로 와이어 바이트로 보내고 파싱한다."""
    chunks = WIZMakeCMD().search_chunks(MAC, " ", devname, ver, status)
    assert len(chunks) == 1, f"{devname}: 3CH/4CH 는 청크 분할이 없다고 알려져 있음(변경됐나?)"
    body = b"".join(c.encode() + b"\r\n" for c, _ in chunks[0][2:])
    req = b"MA" + mac_to_bytes(MAC) + b"\r\nPW \r\n" + body
    reply = dev.build_reply(req)
    assert reply is not None, f"{devname}: 가짜 장치가 검색 요청을 무시함(시험 설정 오류)"
    return parse_reply_lines(reply)


def _wire_set(dev, devname, ver, status, setcmd):
    """get_object_value() 가 만든 setcmd 를 do_setting() 과 같은 방식으로 와이어에 실어 보낸다."""
    cmd_list = WIZMakeCMD().setcommand(
        MAC, " ", "", list(setcmd.keys()), list(setcmd.values()), devname, ver, status
    )
    body = b"".join(c.encode() + p.encode() + b"\r\n" for c, p in cmd_list[2:])
    req = b"MA" + mac_to_bytes(MAC) + b"\r\nPW \r\n" + body
    reply = dev.build_reply(req)
    return parse_reply_lines(reply) if reply else {}, cmd_list


def _prep(win, devname, ver, status="OPEN"):
    win.curr_mac = MAC
    win.curr_dev = devname
    win.curr_ver = ver
    win.curr_st = status


# ── 신형 FW(>=1.1.8) — 검색→화면 배선→편집→SET→장치 반영, 왕복 전체 ──────

@pytest.mark.parametrize("devname,edit_ch", TIERS)
def test_new_fw_search_edit_set_roundtrip(win, devname, edit_ch):
    ver = "1.2.4"
    prof = profile_from_spec(devname, mac=MAC, fw_version=ver)
    dev = FakeSegcpDevice(prof, mac=MAC, validate_with_spec=devname)

    # 1. 검색 — 설정툴이 실제로 만드는 요청 그대로
    dev_data = _wire_search(dev, devname, ver)
    assert dev_data["MC"] == MAC
    assert dev_data.get("MN")

    # 2. 화면 배선 — 실제 fill_devinfo()
    _prep(win, devname, ver)
    win.dev_profile[MAC] = dict(dev_data)
    win.fill_devinfo(dev_data)

    # 3. 사용자가 이 기종의 가장 확장된 채널 로컬포트를 바꿨다고 가정
    codes_by_suffix = {s: codes for s, codes, _k, _o in _iter_rows()}
    localport_code = codes_by_suffix["localport"][edit_ch - 1]
    localport_widget = getattr(win, widget_name(edit_ch, "localport"))
    localport_widget.setText("6123")

    # 4. SET — 실제 get_object_value() (gate=True 활성)
    setcmd = win.get_object_value()
    assert localport_code in setcmd, (
        f"{devname}: 보고받은 채널의 정상 편집이 gate 에 걸러짐(과잉 차단) — {localport_code}"
    )

    # 5. 와이어로 실어 보내고 장치 spec 검증까지 통과하는지
    reply, _ = _wire_set(dev, devname, ver, "OPEN", setcmd)
    assert "ER" not in reply, f"{devname}: 장치가 SET을 거부함 — {reply}"
    assert dev.saved, f"{devname}: SV 가 전달 안 됨"
    assert dev.profile[localport_code] == "6123", (
        f"{devname}: 장치에 새 값이 반영 안 됨 — {dev.profile.get(localport_code)!r}"
    )


# ── 구형 FW(<1.1.8) — 채널 강등 시나리오, gate=True 가 잔상을 막는지 ──────

@pytest.mark.parametrize("devname", ["W55RP20-S2E-3CH", "W55RP20-S2E-4CH"])
def test_old_fw_channel_demotion_blocks_stale_channel_fields(win, devname):
    """계획서 3-1: FW<1.1.8 는 CH1~CH3 확장 커맨드를 아예 모른다(WIZMakeCMD 자체
    버전 게이트로 검색·SET 둘 다 기본 명령만 구성). 여기에 4/5단계 gate=True 가
    한 겹 더 방어한다 — 검색에서 못 받은 채널 필드값이 위젯에 잔상으로 남아 있어도
    SET 에 실리면 안 된다. 3CH/4CH 전용 spec 으로 검증을 걸어(그 spec 은 CH2/CH3
    커맨드를 알고 있음) 혹시라도 새는 값이 있으면 spec 이 그 값을 걸러 잡아낸다.
    """
    ver = "1.1.7"
    # 이 버전에서 실제로 검색에 응답할 커맨드만 채운 프로파일(기본 명령뿐).
    base_prof = profile_from_spec("W55RP20-S2E", mac=MAC, fw_version=ver)
    dev = FakeSegcpDevice(base_prof, mac=MAC, validate_with_spec=devname)

    dev_data = _wire_search(dev, devname, ver)
    assert dev_data["MC"] == MAC
    # 채널 확장 코드가 애초에 검색 응답에 없어야 한다(WIZMakeCMD 버전 게이트 확인).
    channel_codes = {codes[i] for _s, codes, kind, _o in _iter_rows()
                      for i in range(3) if kind != "label"}
    leaked_in_search = channel_codes & set(dev_data)
    assert not leaked_in_search, f"{devname}: 구FW 검색 응답에 채널 코드가 있음 — {leaked_in_search}"

    _prep(win, devname, ver)
    win.dev_profile[MAC] = dict(dev_data)
    win.fill_devinfo(dev_data)

    # 잔상 시뮬레이션 — 이전에 고른 다른(4채널) 장치 값이 위젯에 남아 있다고 가정.
    for suffix, codes, kind, opts in _iter_rows():
        if kind == "label" or kind == "opmode":
            continue
        for ch in (1, 2, 3):
            w = getattr(win, widget_name(ch, suffix, opts), None)
            if w is None:
                continue
            if kind == "combo":
                w.setCurrentIndex(1)
            elif kind == "checkbox":
                w.setChecked(True)
            else:
                w.setText("99")

    setcmd = win.get_object_value()
    leaked_in_setcmd = channel_codes & set(setcmd)
    assert not leaked_in_setcmd, (
        f"{devname}: 구FW 인데 채널 잔상이 SET 에 실림(C1/C2 재발) — {leaked_in_setcmd}"
    )

    reply, cmd_list = _wire_set(dev, devname, ver, "OPEN", setcmd)
    sent_codes = {c for c, _p in cmd_list[2:]}
    assert not (channel_codes & sent_codes), (
        f"{devname}: WIZMakeCMD.setcommand() 자체 게이트도 채널 코드를 흘림 — "
        f"{channel_codes & sent_codes}"
    )
    assert "ER" not in reply, f"{devname}: 기본 명령만 보냈는데도 장치가 거부함 — {reply}"
    assert dev.saved, f"{devname}: 구FW 축소 SET 도 정상 저장돼야 한다"
