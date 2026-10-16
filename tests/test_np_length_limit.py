# -*- coding: utf-8 -*-
"""NP(연결 비밀번호) 10자 이상은 spec 단계에서 막는다.

FW 의 `pw_connect[10]` 은 NUL 을 빼면 9자까지다. 10자 이상을 SET 하면 FW 가
ERINVALIDPARAM 을 세우고, UDP/TCP 모드는 ER 문자열 없이 SAVE 전체를 건너뛴다 —
NP 하나 때문에 같은 패킷의 정상 필드까지 전부 저장되지 않고, 툴에는 "MA+PW 헤더만 있는
짧은 응답"이 와서 "Device rebooted" 문구만 뜬다(저장도 재부팅도 안 됐는데).
`BUG-UNICAST-IP-CHANGE-FAILS` 조사 중 발견(ae0226b, 0fbe177).

그래서 툴이 보내기 전에 길이를 막아야 한다. 이 시험은 그 사전 차단이 어느 기종에서
빠지지 않게 고정한다.
"""
import pytest

from device_spec_loader import load_device

# pw_connect[10] 을 FW 소스로 확인했거나(750SR 계열, 752SR-12x) 같은 구조인 W55RP20 계열.
LIMITED = [
    "WIZ750SR", "WIZ750SR-1xx", "WIZ752SR-12x",
    "W55RP20-S2E", "W55RP20-S2E-2CH", "W55RP20-S2E-3CH", "W55RP20-S2E-4CH",
    "WIZ5XXSR-RP", "WIZ5XXSR-RP_E-SAVE",
]


@pytest.mark.parametrize("device", LIMITED)
def test_np_accepts_up_to_9_chars(device):
    np_cmd = load_device(device).cmdset["NP"]
    assert np_cmd.is_valid("")
    assert np_cmd.is_valid("a")
    assert np_cmd.is_valid("a" * 9)


@pytest.mark.parametrize("device", LIMITED)
def test_np_rejects_10_chars_or_more(device):
    np_cmd = load_device(device).cmdset["NP"]
    assert not np_cmd.is_valid("a" * 10)
    assert not np_cmd.is_valid("a" * 32)


def test_control_device_without_limit_still_accepts_long_np():
    """제한은 위 기종의 override 로만 걸린다 — base 의 NP 는 길이를 제한하지 않는다.

    이 대조가 깨지면(WIZ107SR 도 막힘) 시험이 override 가 아니라 다른 것을 보고 있다는 뜻이다.
    """
    assert load_device("WIZ107SR").cmdset["NP"].is_valid("a" * 10)
