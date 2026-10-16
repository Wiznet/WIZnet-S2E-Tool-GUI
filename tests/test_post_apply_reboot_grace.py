# -*- coding: utf-8 -*-
"""IP 변경 Apply 직후 재검색이 "Network unreachable" 로 보이지 않게 하는 유예 구간.

IP 변경 Apply 는 장치가 실제로 리부팅해 설정 포트가 잠깐 닫힌다. 그 직후 Device Search 를
누르면 TCP 프로브가 실패해 "Network unreachable" 모달이 떴고, 사용자는 장치 고장으로
오해했다(2026-10-14 보고). `socket_config()` 는 Apply 가 세운 유예 구간(`_reboot_grace_until`)
안에서만 `post_apply_reboot_delay_sec` 만큼 기다린 뒤 프로브를 1회 다시 한다.

실기기 로그로 기본 1.0 초는 짧아 3.0 초로 올려 확인했다(2026-10-15). 그래서 대기 시간이
설정값을 그대로 따르는지, 유예 밖에서는 기다리지 않는지를 고정한다.
"""
import time

import pytest

from device_search_config import DeviceSearchConfig

IP = "192.168.7.21"


@pytest.fixture
def win(qapp, monkeypatch):
    import main_gui

    w = main_gui.WIZWindow()
    w.unicast_ip.setChecked(True)
    w.search_ipaddr.setText(IP)
    w.search_port.setText("5001")
    w.curr_mac = None            # 장치 미선택 → 모달 없이 상태바로만 알린다
    w.isConnected = False
    monkeypatch.setattr(w, "connect_over_tcp", lambda ip, port: object())
    yield w
    w.close()


def _run(win, monkeypatch, probes, delay=2.5):
    """tcp_probe 가 probes 순서대로 답하게 하고, sleep 호출 인자를 모아 돌려준다."""
    import main_gui

    answers = list(probes)
    calls = []
    sleeps = []

    def fake_probe(ip, port, *a, **k):
        calls.append((ip, port))
        return answers.pop(0)

    monkeypatch.setattr(main_gui, "tcp_probe", fake_probe)
    monkeypatch.setattr(main_gui.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(win.timing_config, "get_phase3_post_apply_reboot_delay", lambda: delay)
    win.socket_config()
    return calls, sleeps


def test_grace_window_waits_configured_delay_then_reprobes_once(win, monkeypatch):
    win._reboot_grace_until = time.time() + 30
    calls, sleeps = _run(win, monkeypatch, probes=[1, 0], delay=2.5)

    assert sleeps == [2.5]                    # 설정값 그대로 대기
    assert len(calls) == 2                    # 프로브는 정확히 1회만 더
    assert win.isConnected is True            # 재확인에 성공하면 접속
    assert win._reboot_grace_until == 0.0     # 유예는 한 번 쓰면 끝


def test_grace_window_gives_up_after_one_retry(win, monkeypatch):
    win._reboot_grace_until = time.time() + 30
    calls, sleeps = _run(win, monkeypatch, probes=[1, 1])

    assert len(calls) == 2 and len(sleeps) == 1     # 무한 재시도 아님
    assert win.isConnected is False
    assert "unreachable" in win.statusbar.currentMessage().lower()
    assert win._reboot_grace_until == 0.0


def test_no_wait_outside_grace_window(win, monkeypatch):
    """Apply 와 상관없는 평소 실패는 기다리지 않는다 — 검색이 느려지면 안 된다."""
    win._reboot_grace_until = 0.0
    calls, sleeps = _run(win, monkeypatch, probes=[1])

    assert sleeps == [] and len(calls) == 1
    assert win.isConnected is False


def test_expired_grace_window_does_not_wait(win, monkeypatch):
    win._reboot_grace_until = time.time() - 1
    calls, sleeps = _run(win, monkeypatch, probes=[1])

    assert sleeps == [] and len(calls) == 1


def test_no_wait_when_first_probe_succeeds(win, monkeypatch):
    win._reboot_grace_until = time.time() + 30
    calls, sleeps = _run(win, monkeypatch, probes=[0])

    assert sleeps == [] and len(calls) == 1
    assert win.isConnected is True


def test_reboot_delay_setting_has_default_and_range(tmp_path):
    """사용자 설정(~/.wizconfig)을 건드리지 않도록 임시 사본으로 시험한다."""
    import shutil

    from device_search_config import _bundled_default_path

    path = tmp_path / "timing.yaml"
    shutil.copy(_bundled_default_path(), path)
    cfg = DeviceSearchConfig(str(path))

    assert cfg.get_phase3_post_apply_reboot_delay() == 1.0       # 기본값
    for bad in (-0.1, 5.1):                                       # 범위 0.0~5.0 밖은 거부
        assert cfg.update_config_values({"phase3_post_apply_reboot_delay": bad}) is False
        assert cfg.get_phase3_post_apply_reboot_delay() == 1.0
    assert cfg.update_config_values({"phase3_post_apply_reboot_delay": 3.0}) is True
    assert cfg.get_phase3_post_apply_reboot_delay() == 3.0
