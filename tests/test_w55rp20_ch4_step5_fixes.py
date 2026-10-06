#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TASK-W55RP20-CH4-ABSORB 5단계 — 소형 픽스.

계획서(2026-08-12)가 나열한 Critical/Major 후보를 `plans/files/bug_repro.py`로
재확인한 결과:

- **T1(M3, WIZ752 QH 검증 우회)** / **T5b(1CH FL=5 통과)** / **T6(3CH GL='' 전체
  차단 안 됨)** — 전부 **이미 해소됨(재현 안 됨)**. 원인은 이 CH4 작업과 무관한
  2026-08-14 `CmdEntry.is_valid()` 통합(`main_gui._is_valid_setcmd_param()`) —
  DeviceSpec 이 해당 커맨드를 갖고 있으면 그쪽이 우선하고, `bug_repro.py`가 직접
  두드리는 `Wizcmdset.isvalidparameter()`(레거시 폴백)는 이제 그 커맨드들에 한해
  죽은 경로다. 이 파일 대신 `device_spec_loader.load_device(...).cmdset[...].is_valid()`
  로 확인 — 실제 GUI가 쓰는 경로가 이것이다.
- **T3(M2, `_get_expected_min_resp_len` 버전 미반영)** — 실재. 이 파일에서 수정.
- **C3(무로그 채널 강등)** — 실재. 이 파일에서 수정.
- **T4(C1, ch0 UI 잔상)** — `channel_field_map`(CH1~CH3)의 범위 밖(CH_MIN=1)이라
  4단계 gate=True 전환에서 빠졌던 것. 이 파일에서 마저 닫는다.
"""
import pytest

MAC = "00:08:DC:AB:CD:EF"


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


# ── T1/T5b/T6 재확인 — DeviceSpec 경로가 이미 막고 있다(회귀 감시용) ──

@pytest.mark.parametrize("dev,ver,cmd,bad_values", [
    # "192.168.0.1.1" 은 넣지 않는다 — RH/QH 는 IPv4 아니면 도메인으로도 허용하는
    # 설계라(FW: 4옥텟 아니면 dns_domain_name), 점 5개짜리 라벨도 문법상 유효한
    # 도메인이라 통과하는 게 맞다(버그 아님).
    ("WIZ752SR-12x", "2.1.0", "QH", ["not an ip !!"]),
    ("W55RP20-S2E", "1.2.2", "FL", ["5"]),
    ("W55RP20-S2E-3CH", "1.0.5", "GL", [""]),
])
def test_devicespec_path_already_rejects_known_bug_repro_cases(dev, ver, cmd, bad_values):
    from device_spec_loader import load_device, detect_device

    spec = load_device(detect_device(dev) or dev, ver)
    assert cmd in spec.cmdset, f"{dev}: {cmd} 가 spec.cmdset 에 없음 — 레거시 폴백으로 새는 중"
    for bad in bad_values:
        assert not spec.cmdset[cmd].is_valid(bad), (
            f"{dev} {cmd}={bad!r} 가 spec 경로에서도 통과 — T1/T5b/T6 재발"
        )


# ── T3/M2: _get_expected_min_resp_len 버전 미반영 ────────────────────

@pytest.mark.parametrize("dev", ["W55RP20-S2E-3CH", "W55RP20-S2E-4CH"])
def test_expected_min_resp_len_old_fw_matches_base_floor(win, dev):
    """FW<1.1.8 이면 채널 확장 없이 기본 명령만 GET 하므로(WIZMakeCMD.search()와
    동일 기준), 기대 최소 길이도 2CH 와 같은 바닥값이어야 한다.
    안 그러면 구FW 의 정상 응답을 리부트로 오판한다."""
    from WIZMakeCMD import cmd_security_base, cmd_wiz5xxsr_added

    floor = 10 + 5 + len(cmd_security_base + cmd_wiz5xxsr_added) * 5
    old_fw = win._get_expected_min_resp_len(dev, "1.1.7")
    ref_2ch = win._get_expected_min_resp_len("W55RP20-S2E-2CH", "1.1.7")
    assert old_fw == floor == ref_2ch, (
        f"{dev} FW1.1.7 기대최소={old_fw}, 바닥값={floor}, 2CH 기준={ref_2ch} — 불일치"
    )


@pytest.mark.parametrize("dev", ["W55RP20-S2E-3CH", "W55RP20-S2E-4CH"])
def test_expected_min_resp_len_new_fw_unaffected(win, dev):
    """새 FW(>=1.1.8)는 채널 확장 커맨드 전부를 GET 하므로 기존처럼 더 커야 한다
    (이번 수정이 새 FW 쪽을 실수로 낮추지 않았는지 확인)."""
    old_fw = win._get_expected_min_resp_len(dev, "1.1.7")
    new_fw = win._get_expected_min_resp_len(dev, "1.2.2")
    assert new_fw > old_fw


# ── C3: 무로그 채널 강등 — 구FW 로 CH1~CH3 를 못 물을 때 경고 로그 ────

@pytest.mark.parametrize("dev,warn_snippet", [
    ("W55RP20-S2E-2CH", "CH1 확장 커맨드 미지원"),
    ("W55RP20-S2E-3CH", "CH1/2 확장 커맨드 미지원"),
    ("W55RP20-S2E-4CH", "CH1/2/3 확장 커맨드 미지원"),
])
def test_search_warns_on_old_fw_channel_demotion(caplog, dev, warn_snippet):
    import logging
    from WIZMakeCMD import WIZMakeCMD

    with caplog.at_level(logging.WARNING, logger="wizconfig"):
        WIZMakeCMD().search(MAC, " ", dev, "1.1.7", devstatus="OPEN")
    assert any(warn_snippet in rec.message for rec in caplog.records), (
        f"{dev}: 구FW 강등 경고 로그가 없음(C3 재발) — {[r.message for r in caplog.records]}"
    )


@pytest.mark.parametrize("dev", ["W55RP20-S2E-2CH", "W55RP20-S2E-3CH", "W55RP20-S2E-4CH"])
def test_search_no_warning_on_new_fw(caplog, dev):
    """새 FW 는 강등이 아니므로 경고가 없어야 한다(오탐 방지)."""
    import logging
    from WIZMakeCMD import WIZMakeCMD

    with caplog.at_level(logging.WARNING, logger="wizconfig"):
        WIZMakeCMD().search(MAC, " ", dev, "1.2.2", devstatus="OPEN")
    assert not any("확장 커맨드 미지원" in rec.message for rec in caplog.records)


# ── T4/C1 완결: ch0 UI 도 게이트 대상(channel_field_map 범위 밖이라 별도) ──

@pytest.mark.parametrize("dev", [
    "W55RP20-S2E", "W55RP20-S2E-2CH", "W55RP20-S2E-3CH", "W55RP20-S2E-4CH",
])
def test_ch0_ui_gate_blocks_unreported_value(win, dev):
    """장치A(UI=2)를 본 뒤 장치B(이번엔 UI 미보고)로 넘어가도, 위젯에 남은
    잔상 인덱스가 그대로 SET 에 실리면 안 된다."""
    _prep(win, dev)
    win.ch0_uart_name.setCurrentIndex(2)  # 장치 A 가 남긴 잔상
    win._last_ch_dev_data = {}  # 장치 B: UI 미보고

    setcmd = win.get_object_value()
    assert "UI" not in setcmd, f"{dev}: UI 미보고인데 전송됨(C1 재발) — {setcmd.get('UI')}"


@pytest.mark.parametrize("dev", [
    "W55RP20-S2E", "W55RP20-S2E-2CH", "W55RP20-S2E-3CH", "W55RP20-S2E-4CH",
])
def test_ch0_ui_gate_passes_when_reported(win, dev):
    _prep(win, dev)
    win.ch0_uart_name.setCurrentIndex(1)
    win._last_ch_dev_data = {"UI": "1"}

    setcmd = win.get_object_value()
    assert setcmd.get("UI") == "1"
