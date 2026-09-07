#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec 에서 가짜 장치를 만든다 — 장비 없이 여러 기종을 시험하기 위해.

`specs/devices/*.yaml` 15종 중 12종이 같은 SEGCP(50001) 프로토콜을 쓴다. 차이는
커맨드 목록과 값 범위뿐이고 그건 전부 spec 에 있다. 프로파일을 spec 에서 만들면
기종마다 손으로 dict 를 적지 않아도 된다.

무엇을 검증할 수 있고 무엇을 못 하는지 분명히 해 둔다.

  할 수 있다   설정툴 자신의 코드 경로 — 파싱·화면 배선·크기·게이팅·오류 처리
  할 수 없다   우리가 만든 spec 이 실장치와 같은지. 그건 실기기나 FW 소스가 답한다
               (그래서 아래 실측 대조 시험이 있다)
"""

import pytest

from device_spec_loader import load_device
from tests.fake_segcp_device import (
    PROFILE_WIZ752_MEASURED, FakeSegcpDevice, profile_from_spec, tool_asked_commands,
)
from WIZMakeCMD import WIZMakeCMD
from WIZMSGHandler import parse_reply_lines

MAC = "00:08:DC:FA:CE:01"

# SEGCP(50001) 로 말하는 기종. WIZ550 3종은 바이너리 프로토콜이라 여기 없다.
SEGCP_DEVICES = [
    "WIZ752SR-12x", "WIZ750SR", "WIZ750SR-1xx", "WIZ107SR", "WIZ108SR",
    "WIZ510SSL", "WIZ5XXSR-RP", "WIZ5XXSR-RP_E-SAVE",
    "W55RP20-S2E", "W55RP20-S2E-2CH", "W232N", "IP20",
]


@pytest.mark.parametrize("device", SEGCP_DEVICES)
def test_generated_profile_answers_every_searchable_command(device):
    spec = load_device(device)
    prof = profile_from_spec(device, mac=MAC)
    missing = [c for c in spec.search_cmd_list if c not in prof]
    assert missing == [], f"{device}: 조회 목록에 있는데 값이 없다 — {missing}"


@pytest.mark.parametrize("device", SEGCP_DEVICES)
def test_generated_values_satisfy_their_own_spec(device):
    """만들어 낸 값이 그 커맨드의 regex/values 를 통과해야 한다. 아니면 툴이 거부할 값을
    장치가 돌려주는 셈이 되어 시험이 거짓말을 한다."""
    spec = load_device(device)
    prof = profile_from_spec(device, mac=MAC)
    bad = [(c, v) for c, v in prof.items()
           if c in spec.cmdset and not spec.cmdset[c].is_valid(v)]
    assert bad == [], f"{device}: spec 을 만족하지 않는 값 — {bad}"


@pytest.mark.parametrize("device", SEGCP_DEVICES)
def test_reply_to_the_tools_own_search_request_fits_the_device_buffer(device):
    """기종별로 설정툴이 실제 보내는 조회에 대한 응답이 장치 버퍼에 들어가는지.
    752 에서 터진 것과 같은 초과가 다른 기종에도 있는지 장비 없이 미리 본다.
    버퍼 크기를 모르는 기종(config_buf_size=0)은 판정하지 않는다."""
    spec = load_device(device)
    if not spec.fw_config.config_buf_size:
        pytest.skip(f"{device}: 응답 버퍼 크기 미상")
    ver = prof_ver(device)
    prof = profile_from_spec(device, mac=MAC, fw_version=ver,
                             include=tool_asked_commands(device, ver, MAC))
    dev = FakeSegcpDevice(prof, mac=MAC)
    for chunk in WIZMakeCMD().search_chunks(MAC, " ", device, ver, "OPEN"):
        body = b"".join(c.encode() + b"\r\n" for c, _ in chunk[2:])
        request = b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body
        dev.build_reply(request)
    assert dev.overflow_events == [], (
        f"{device}: 응답이 버퍼({spec.fw_config.config_buf_size}B)를 넘긴다 — {dev.overflow_events}")


def prof_ver(device):
    return {"WIZ107SR": "4.06", "WIZ108SR": "4.06"}.get(device, "1.2.4")


def test_measured_752_profile_covers_what_the_spec_asks_for():
    """실측 프로파일과 spec 이 어긋나면 둘 중 하나가 틀린 것이다. spec 이 요구하는 커맨드를
    실장치가 돌려주지 않았다면 spec drift 다 — 장비 없이 잡을 수 있는 몇 안 되는 것."""
    spec = load_device("WIZ752SR-12x", "2.1.0dev")
    missing = [c for c in spec.search_cmd_list if c not in PROFILE_WIZ752_MEASURED]
    assert missing == [], f"spec 이 요구하는데 실장치 응답에 없던 커맨드 — {missing}"


def test_spec_driven_device_serves_the_tool_end_to_end():
    """설정툴이 만든 요청 그대로 넣어 응답이 파싱되는지 — 한 기종으로 왕복 확인."""
    device = "WIZ5XXSR-RP"
    prof = profile_from_spec(device, mac=MAC, fw_version="1.1.1",
                             include=tool_asked_commands(device, "1.1.1", MAC))
    dev = FakeSegcpDevice(prof, mac=MAC)
    chunks = WIZMakeCMD().search_chunks(MAC, " ", device, "1.1.1", "OPEN")
    assert len(chunks) == 1, "1포트 장치는 한 번에 묻는다"
    body = b"".join(c.encode() + b"\r\n" for c, _ in chunks[0][2:])
    reply = dev.build_reply(b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n" + body)
    prof = parse_reply_lines(reply)
    assert prof["MC"] == MAC
    assert prof["MN"]
    for cmd, _ in chunks[0][2:]:
        assert cmd in prof, f"{cmd} 응답 없음"


def test_spec_validation_rejects_a_value_the_device_would_not_accept():
    """spec 검증을 켜면 범위 밖 값에 ER 을 돌려준다 — 툴이 오류를 사용자에게
    알리는 경로를 장비 없이 시험할 수 있다."""
    dev = FakeSegcpDevice(profile_from_spec("WIZ752SR-12x", mac=MAC), mac=MAC,
                          validate_with_spec="WIZ752SR-12x")
    req = (b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n"
           + b"BR99\r\nMC\r\n")          # BR 상한은 13 (WIZ752SR)
    prof = parse_reply_lines(dev.build_reply(req))
    assert prof["ER"] == "INVALIDPARAM:BR"
    assert "MC" not in prof, "현재 FW 는 에러 뒤를 처리하지 않는다"


def test_spec_validation_accepts_a_value_in_range():
    dev = FakeSegcpDevice(profile_from_spec("WIZ752SR-12x", mac=MAC), mac=MAC,
                          validate_with_spec="WIZ752SR-12x")
    req = (b"MA" + bytes.fromhex(MAC.replace(":", "")) + b"\r\nPW \r\n"
           + b"BR13\r\nMC\r\n")
    prof = parse_reply_lines(dev.build_reply(req))
    assert "ER" not in prof
    assert prof["MC"] == MAC
    assert dev.profile["BR"] == "13"


# ── spec 드리프트 — 장비 없이 잡히는 것 ─────────────────────────────────

# 설정툴이 spec 에 없는 커맨드를 묻는 기종 (2026-09-07 실측). WIZMakeCMD 의 하드코딩
# 목록과 specs/devices/*.yaml 이 따로 논다. 고치면 xpass 로 알려 준다.
_SPEC_DRIFT = {
    "WIZ752SR-12x": 9, "WIZ750SR": 7, "WIZ750SR-1xx": 7, "WIZ510SSL": 3,
    "WIZ5XXSR-RP": 5, "WIZ5XXSR-RP_E-SAVE": 5, "W55RP20-S2E": 3,
    "W55RP20-S2E-2CH": 3, "W232N": 3, "IP20": 3,
}


@pytest.mark.parametrize("device", [
    pytest.param(d, marks=pytest.mark.xfail(
        strict=True, reason=f"spec 이 모르는 커맨드 {_SPEC_DRIFT[d]}개를 묻는다 — TASKS search_cmd_order 드리프트"))
    if d in _SPEC_DRIFT else d
    for d in SEGCP_DEVICES
])
def test_tool_only_asks_commands_the_spec_knows_about(device):
    """설정툴이 묻는 커맨드는 그 기종 spec 에 정의돼 있어야 한다.

    어긋나면 spec 기반 게이팅(`'X' in spec.cmdset`)이 전부 그 커맨드를 없는 것으로 본다.
    실기기 없이 잡히는 몇 안 되는 결함이라 기종별로 걸어 둔다."""
    spec = load_device(device, prof_ver(device))
    asked = tool_asked_commands(device, prof_ver(device), MAC)
    unknown = [c for c in asked if c not in spec.cmdset]
    assert unknown == [], f"{device}: spec 이 모르는 커맨드를 묻는다 — {unknown}"
