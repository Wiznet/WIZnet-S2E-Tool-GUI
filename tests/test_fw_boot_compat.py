#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FW from Git — WIZ750SR 계열 Boot↔App 호환 판정.

W7500 계열 Boot 는 버전 정보를 갖고 있지 않아 읽을 수 없다(담당자 확인 2026-10-15).
실행 중인 App 버전으로 Boot 를 추측하되, 구간은 인터럽트 재매핑(ISR) 주소가 바뀌는
지점으로 나눈다(펌웨어 태그별 실측: v1.3.0~v1.3.2 0x1FD00, v1.3.3~ 0x7D00).

  구간  1.2 | 1.3.0(1.3.0~1.3.2) | 1.3.3 | 1.4(1.4.0~)
  비활성  1.2→1.3.3 이상, 1.3.0→1.3.3 이상, 1.4→1.2, 1.4→1.3.0
          (1.2·1.3.0~1.3.2 는 1.3.2 까지만 올릴 수 있다 — 사용자 확정 2026-10-16)
  통과    1.3.3↔1.4, 같은 구간(1.2 제외)  (1.3.3 과 1.4.x 는 ISR 규약이 같다)
  경고    그 외 구간 이동 — Boot 에 따라 갈린다. 1.2 는 단종이라 1.2 에서 출발하면
          같은 구간이어도 경고하고 ISP tool 을 권한다 (담당자 Theo 2026-10-15)
  BOOT 상태(복구 중)에서는 현재 버전이 저장된 값이라 비활성을 경고로 낮춘다.
"""
import json

import pytest

import fw_git_dialog
from fw_boot_compat import BLOCK, OK, WARN, generation, judge

CONFIG = "config/fw_sources.json"


def _families():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)["families"]


RULE = next(f for f in _families() if f["id"] == "wiz750sr")["boot_compat"]


@pytest.mark.parametrize("version, expected", [
    ("1.2.4", "1.2"),
    ("1.2.4A", "1.2"),
    ("1.3.0", "1.3.0"),
    ("1.3.2", "1.3.0"),
    ("v1.3.3", "1.3.3"),
    ("v1.3.3_DIK", "1.3.3"),
    ("1.4.0", "1.4"),
    ("1.4.5", "1.4"),
    ("1.4.2dev", "1.4"),
    ("  1.2.9", "1.2"),
    ("1.1.0", None),    # 첫 구간보다 낮으면 모른다
    ("", None),
    (None, None),
    ("abc", None),
])
def test_generation(version, expected):
    assert generation(version, RULE) == expected


def test_generation_without_epochs_falls_back_to_major_minor():
    assert generation("1.4.5") == "1.4"
    assert generation("v1.3.3") == "1.3"


@pytest.mark.parametrize("current, target, expected", [
    # 1.2 출발 — 단종, 같은 구간이어도 경고
    ("1.2.4", "v1.2.9", WARN),
    ("1.2.4", "v1.3.0", WARN),
    ("1.2.4", "v1.3.3", BLOCK),     # 1.3.2 까지만 — 사용자 확정 2026-10-16
    ("1.2.9", "v1.4.5", BLOCK),
    # 1.3.0~1.3.2 출발
    ("1.3.1", "v1.2.9", WARN),
    ("1.3.1", "v1.3.2", OK),
    ("1.3.1", "v1.3.3", BLOCK),     # ISR 0x1FD00 → 0x7D00, 사용자 확정 2026-10-16
    ("1.3.2", "v1.4.0", BLOCK),
    # 1.3.3 출발
    ("1.3.3", "v1.2.9", WARN),
    ("1.3.3", "v1.3.2", WARN),
    ("1.3.3", "v1.4.5", OK),        # 같은 ISR 규약(0x7D00) — 사용자 확정 2026-10-16
    # 1.4.x 출발
    ("1.4.0", "v1.2.9", BLOCK),
    ("1.4.0", "v1.3.2", BLOCK),     # 2026-10-15 EVB 사고: 1.4.0 → 1.3.2 후 검색 안 됨
    ("1.4.0", "v1.3.3", OK),
    ("1.4.2", "v1.4.5", OK),
    ("1.4.5", "v1.4.0", OK),
])
def test_judge_matrix(current, target, expected):
    assert judge(RULE, current, target)["result"] == expected


@pytest.mark.parametrize("current, expected", [
    ("1.2.4", True),
    ("1.3.3", False),
    ("1.4.5", False),
    ("", False),
])
def test_isp_recommended_only_from_discontinued_generation(current, expected):
    assert judge(RULE, current, "v1.3.3")["isp_recommended"] is expected


@pytest.mark.parametrize("current, target", [
    ("1.5.0", "v1.4.5"),    # 모르는 현재 버전
    ("1.4.5", "v1.5.0"),    # 모르는 대상 버전
    ("", "v1.4.5"),         # 현재 버전을 모름
    (None, "v1.4.5"),
    ("1.4.5", "latest"),    # 대상 태그를 읽을 수 없음
    # 호환표가 보증하는 최신(known_max)을 넘으면 같은 구간이어도 근거가 없다.
    # Boot 가 1.4 이상으로 올라가면 표가 낡으므로 새 Boot/App 이 나올 때까지 경고.
    ("1.4.5", "v1.4.6"),
    ("1.4.6", "v1.4.5"),
    ("1.5.0", "v1.5.1"),
])
def test_unknown_is_warn(current, target):
    assert judge(RULE, current, target)["result"] == WARN


def test_no_rule_means_ok():
    assert judge(None, "1.2.4", "v1.4.5")["result"] == OK


def test_judge_carries_versions_and_docs_url():
    r = judge(RULE, "1.2.9", "v1.4.5")
    assert (r["from"], r["to"]) == ("1.2", "1.4")
    assert (r["current"], r["target"]) == ("1.2.9", "v1.4.5")
    assert r["docs_url"] == RULE["docs_url"]


@pytest.mark.parametrize("current, target, expected", [
    # 복구 중(BOOT 상태)이라 화면의 현재 버전은 실제로 돌던 App 이 아니다.
    # 비활성이면 복구용 업로드를 툴이 막아 버린다.
    ("1.3.2", "v1.4.5", WARN),      # 사고 난 장치를 1.4.5 로 되살리기
    ("1.4.0", "v1.3.2", WARN),
    ("1.2.4", "v1.4.5", WARN),
    # 비활성이 아니던 판정은 그대로
    ("1.4.0", "v1.3.3", OK),
    ("1.3.3", "v1.4.5", OK),
])
def test_boot_mode_never_blocks(current, target, expected):
    assert judge(RULE, current, target, in_boot_mode=True)["result"] == expected


def test_boot_mode_flag_only_when_a_block_was_relaxed():
    assert judge(RULE, "1.3.2", "v1.4.5", in_boot_mode=True)["boot_mode_relaxed"] is True
    assert judge(RULE, "1.4.0", "v1.3.3", in_boot_mode=True)["boot_mode_relaxed"] is False
    assert judge(RULE, "1.3.2", "v1.4.5")["boot_mode_relaxed"] is False


def test_config_rule_shape():
    assert RULE["docs_url"].startswith("https://docs.wiznet.io/")
    assert RULE["known_max"] == "1.4.5"     # 호환표의 Boot V1.3 상한
    assert RULE["isp_recommend_from"] == ["1.2"]
    assert set(RULE["transitions"].values()) <= {OK, WARN, BLOCK}
    names = list(RULE["epochs"])
    assert names == ["1.2", "1.3.0", "1.3.3", "1.4"]
    for key in RULE["transitions"]:
        src, dst = key.split(">")
        assert src in names and dst in names


def test_epochs_follow_isr_address_boundaries():
    """구간 경계는 펌웨어 태그별 ISR 주소가 바뀌는 지점(1.3.0, 1.3.3)이어야 한다."""
    assert RULE["epochs"]["1.3.0"] == "1.3.0"
    assert RULE["epochs"]["1.3.3"] == "1.3.3"


def test_only_wiz750sr_family_has_rule():
    """다른 제품은 Boot/App 쌍 개념이 달라 이 규칙이 걸리면 안 된다."""
    for fam in _families():
        assert ("boot_compat" in fam) == (fam["id"] == "wiz750sr"), fam["id"]


# ── 다이얼로그 ───────────────────────────────────────────────────────

class _FakeFetcher:
    def __init__(self, tags):
        self._tags = tags

    def get_releases_for(self, family):
        return [{"tag_name": t, "published_at": "2025-01-01T00:00:00Z"}
                for t in self._tags]

    def find_asset(self, release, device_spec, family):
        return {"name": f"WIZ750SR{release['tag_name']}.bin",
                "browser_download_url": "", "size": 0}


def _make_dialog(qapp, current_version, family=None, tags=None, in_boot=False):
    fam = family or next(f for f in _families() if f["id"] == "wiz750sr")
    dlg = fw_git_dialog.FWGitDialog(
        None, "WIZ750SR", fam,
        {"asset_pattern": "WIZ750SR*.bin", "extract_file": None},
        _FakeFetcher(tags or ["v1.4.5", "v1.3.3", "v1.2.9"]), ".",
        current_version=current_version,
        device_in_boot=in_boot,
    )
    dlg._fetch_thread.wait(2000)
    qapp.processEvents()
    return dlg


def _enabled(dlg):
    model = dlg._combo.model()
    return [model.item(i).isEnabled() for i in range(dlg._combo.count())]


def test_dialog_blocks_incompatible_but_still_lists_it(qapp):
    dlg = _make_dialog(qapp, "1.2.4")
    assert dlg._combo.count() == 3                  # 최신도 목록에는 보인다
    assert _enabled(dlg) == [False, False, True]    # 1.3.3 이상은 선택 불가(1.3.2 까지만)
    assert dlg._combo.currentIndex() == 2           # 선택 가능한 첫 항목으로 이동
    assert dlg._btn_dl.isEnabled()


def test_dialog_blocks_the_evb_accident(qapp):
    """1.4.0 이 돌던 장치에 1.3.2 를 올려 검색이 안 된 사고가 다시 나면 안 된다."""
    dlg = _make_dialog(qapp, "1.4.0", tags=["v1.4.5", "v1.3.3", "v1.3.2"])
    assert _enabled(dlg) == [True, True, False]


def test_dialog_warns_on_uncertain_move(qapp, monkeypatch):
    dlg = _make_dialog(qapp, "1.3.3")
    assert _enabled(dlg) == [True, True, True]
    assert dlg._combo.currentIndex() == 0           # v1.4.5, 같은 ISR 규약이라 확실
    dlg._combo.setCurrentIndex(2)                   # v1.2.9: 1.3.3 → 1.2 는 불확실
    assert dlg._btn_dl.isEnabled()

    started = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: started.append(1))
    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning",
                        lambda *a, **k: fw_git_dialog.QMessageBox.No)
    dlg._on_download()
    assert started == []                            # 경고에서 No → 다운로드 안 함

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning",
                        lambda *a, **k: fw_git_dialog.QMessageBox.Yes)
    dlg._on_download()
    assert started == [1]


def test_dialog_from_discontinued_app_recommends_isp_tool(qapp, monkeypatch):
    dlg = _make_dialog(qapp, "1.2.4")
    assert dlg._combo.currentIndex() == 2           # v1.2.9
    shown = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: None)

    def _capture(parent, title, text, *a, **k):
        shown.append(text)
        return fw_git_dialog.QMessageBox.No

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning", _capture)
    dlg._on_download()
    assert len(shown) == 1 and "ISP tool" in shown[0]


def test_dialog_certain_move_has_no_prompt(qapp, monkeypatch):
    dlg = _make_dialog(qapp, "1.4.2")
    dlg._combo.setCurrentIndex(1)                   # v1.3.3: 확실히 됨
    started = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: started.append(1))

    def _no_prompt(*a, **k):
        raise AssertionError("확실히 되는 이동에서 경고창이 떴다")

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning", _no_prompt)
    dlg._on_download()
    assert started == [1]


def test_dialog_boot_mode_keeps_everything_selectable(qapp, monkeypatch):
    """복구 중에는 저장된 버전이 1.3.2 여도 1.4.5 를 올릴 수 있어야 한다."""
    dlg = _make_dialog(qapp, "1.3.2", in_boot=True)
    assert _enabled(dlg) == [True, True, True]
    assert dlg._combo.currentIndex() == 0           # v1.4.5 (원래는 비활성)
    assert dlg._btn_dl.isEnabled()

    shown = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: None)

    def _capture(parent, title, text, *a, **k):
        shown.append(text)
        return fw_git_dialog.QMessageBox.No

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning", _capture)
    dlg._on_download()
    assert len(shown) == 1 and "Boot mode" in shown[0]


def test_dialog_unknown_current_version_warns_everything(qapp):
    dlg = _make_dialog(qapp, "")
    assert _enabled(dlg) == [True, True, True]
    assert dlg._compat["result"] == WARN


def test_dialog_without_rule_is_untouched(qapp):
    fam = {"id": "x", "repo": "a/b"}
    dlg = _make_dialog(qapp, "1.2.4", family=fam)
    assert _enabled(dlg) == [True, True, True]
    assert dlg._combo.currentIndex() == 0
    assert dlg._compat["result"] == OK


# ── 2026-10-16 사용자 확정·실기기 확인 규칙을 한 표로 고정 ──────────────────────

# 원칙: "반드시 되는 것"은 통과, "반드시 안 되는 것"은 비활성, 나머지는 활성 + [Check Boot].
# 열: 대상 구간 1.2 / 1.3.0 / 1.3.3 / 1.4.  (대표 버전으로 판정)
_EPOCH_SAMPLE = {"1.2": "v1.2.9", "1.3.0": "v1.3.2", "1.3.3": "v1.3.3", "1.4": "v1.4.5"}
_CURRENT_SAMPLE = {"1.2": "1.2.4", "1.3.0": "1.3.1", "1.3.3": "1.3.3", "1.4": "1.4.2"}
FULL_MATRIX = {
    # 현재 구간: (→1.2, →1.3.0, →1.3.3, →1.4)
    "1.2":   (WARN, WARN, BLOCK, BLOCK),
    "1.3.0": (WARN, OK, BLOCK, BLOCK),
    "1.3.3": (WARN, WARN, OK, OK),
    "1.4":   (BLOCK, BLOCK, OK, OK),
}


@pytest.mark.parametrize("src", list(FULL_MATRIX))
def test_full_epoch_matrix(src):
    """16 칸 전부. 한 칸이라도 바꾸면 이 시험이 알려준다 — 바꾸는 쪽이 사용자 확정을 확인할 것."""
    got = tuple(
        judge(RULE, _CURRENT_SAMPLE[src], _EPOCH_SAMPLE[dst])["result"]
        for dst in ("1.2", "1.3.0", "1.3.3", "1.4")
    )
    assert got == FULL_MATRIX[src]


def test_nothing_crosses_the_isr_boundary_as_ok_from_the_1_3_0_side():
    """0x1FD00 세대(1.3.0~1.3.2)에서 0x7D00 세대(1.3.3~)로 가는 이동은 어디서도 통과가 아니다."""
    for dst in ("v1.3.3", "v1.4.0", "v1.4.5"):
        assert judge(RULE, "1.3.1", dst)["result"] != OK
        assert judge(RULE, "1.2.4", dst)["result"] != OK


def test_isp_tool_is_recommended_only_when_leaving_discontinued_1_2():
    assert judge(RULE, "1.2.4", "v1.3.2")["isp_recommended"] is True
    assert judge(RULE, "1.2.4", "v1.3.3")["isp_recommended"] is True   # 비활성이어도 안내는 ISP
    assert judge(RULE, "1.3.1", "v1.3.2")["isp_recommended"] is False


# ── 실제 GitHub 릴리즈 태그 목록(Wiznet/WIZ750SR, 2026-10-16)으로 본 다이얼로그 ─────────

REAL_TAGS = [
    "v1.4.5", "v1.4.4", "v1.4.3", "v1.4.2", "v1.4.1", "v1.4.0", "v1.2.9", "v1.3.3",
    "v1.2.8", "v1.3.2", "v1.3.1", "v1.3.0", "v1.2.6", "v1.2.5", "v1.2.4", "v1.2.3",
    "v1.2.2-2", "v1.2.2-1", "v1.2.1", "v1.2.1-1", "v1.2.0", "v.1.1.2", "v1.1.2-1",
    "v1.1.1", "v1.1.0",
]


def _labels(dlg):
    return [dlg._combo.itemText(i) for i in range(dlg._combo.count())]


def test_real_tags_from_1_4_5_in_app_state(qapp):
    """2026-10-16 EVB(Boot 1.4.x) 화면: 1.3.3 이상은 열려 있고 1.3.2 이하는 비활성."""
    dlg = _make_dialog(qapp, "1.4.5", tags=REAL_TAGS)
    by_tag = dict(zip(REAL_TAGS, _enabled(dlg)))
    for tag in ("v1.4.5", "v1.4.0", "v1.3.3"):
        assert by_tag[tag] is True
    for tag in ("v1.3.2", "v1.3.1", "v1.3.0", "v1.2.9", "v1.2.5"):
        assert by_tag[tag] is False
    assert dlg._combo.currentIndex() == 0


def test_real_tags_label_the_ones_we_cannot_judge(qapp):
    """`v.1.1.2` 처럼 구간이 없는 아주 오래된 태그는 막지 않고 [Check Boot] 로 보여 준다."""
    dlg = _make_dialog(qapp, "1.4.5", tags=REAL_TAGS)
    labels = dict(zip(REAL_TAGS, _labels(dlg)))
    assert "[Check Boot]" in labels["v.1.1.2"]
    assert "[Check Boot]" in labels["v1.1.0"]
    assert "Boot incompatible" in labels["v1.3.2"]
    assert "[Check Boot]" not in labels["v1.3.3"] and "Boot incompatible" not in labels["v1.3.3"]


def test_boot_state_unblocks_but_labels_every_relaxed_item(qapp):
    """BOOT 상태: 막힘이 풀리되 풀린 항목마다 [Check Boot] 가 붙어 경고가 사라지지 않는다."""
    dlg = _make_dialog(qapp, "1.4.5", tags=REAL_TAGS, in_boot=True)
    labels = dict(zip(REAL_TAGS, _labels(dlg)))
    assert all(_enabled(dlg))
    for tag in ("v1.3.2", "v1.3.1", "v1.3.0", "v1.2.9"):
        assert "[Check Boot]" in labels[tag]
        assert "Boot incompatible" not in labels[tag]
    for tag in ("v1.4.5", "v1.3.3"):
        assert "[Check Boot]" not in labels[tag]


def test_boot_state_selected_relaxed_item_shows_orange_notice(qapp):
    dlg = _make_dialog(qapp, "1.4.5", tags=["v1.4.5", "v1.3.2"], in_boot=True)
    dlg._combo.setCurrentIndex(1)
    dlg._update_asset_label(1)
    assert "unverified" in dlg._lbl_asset.text()
    assert "b36b00" in dlg._lbl_asset.styleSheet()
    assert dlg._btn_dl.isEnabled()
