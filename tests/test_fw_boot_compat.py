#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FW from Git — WIZ750SR 계열 Boot↔App 호환 판정.

W7500 계열 Boot 는 버전 정보를 갖고 있지 않아 읽을 수 없다(담당자 확인 2026-10-15).
Boot 가 마지막으로 써진 시점의 App 버전으로 부르는 이름뿐이라, 실행 중인 App 버전에서
추측한다. 확정되는 이동만 막고(비활성), 불확실한 이동은 경고 후 진행시킨다.

  확실히 됨   1.4 -> 1.3, 같은 세대
  확실히 안됨 1.2 -> 1.4, 1.4 -> 1.2
  불확실      1.3 -> 1.4, 1.3 -> 1.2, 모르는 세대
  1.2 는 단종이라 1.2 에서 출발하는 이동은 (막히는 1.4 외) 같은 세대여도 경고하고
  ISP tool 을 권한다 (담당자 Theo 2026-10-15).
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
    ("1.4.5", "1.4"),
    ("v1.3.3", "1.3"),
    ("1.2.4A", "1.2"),
    ("1.4.2dev", "1.4"),
    ("v1.3.3_DIK", "1.3"),
    ("  1.2.9", "1.2"),
    ("", None),
    (None, None),
    ("abc", None),
])
def test_generation(version, expected):
    assert generation(version) == expected


@pytest.mark.parametrize("current, target, expected", [
    # 확실히 됨
    ("1.4.2", "v1.3.3", OK),
    # 확실히 안됨
    ("1.2.9", "v1.4.5", BLOCK),
    ("1.4.5", "v1.2.9", BLOCK),
    # 불확실 — Boot 가 1.2 인지 1.3 인지 모른다
    ("1.3.3", "v1.4.5", WARN),
    ("1.3.1", "v1.2.9", WARN),
    # 같은 세대는 Boot 와의 관계가 바뀌지 않는다
    ("1.4.2", "v1.4.5", OK),
    ("1.3.3", "v1.3.0", OK),
    # 1.2 는 단종 — Boot 가 1.2 로 확정이라 App 만 올리면 이후가 위험해진다
    ("1.2.4", "v1.3.3", WARN),
    ("1.2.4", "v1.2.9", WARN),
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
    ("1.5.0", "v1.4.5"),    # 모르는 현재 세대
    ("1.4.5", "v1.5.0"),    # 모르는 대상 세대
    ("", "v1.4.5"),         # 현재 버전을 모름
    (None, "v1.4.5"),
    ("1.4.5", "latest"),    # 대상 태그를 읽을 수 없음
    # 호환표가 보증하는 최신(known_max)을 넘으면 같은 세대여도 근거가 없다.
    # Boot 가 1.4 이상으로 올라가면 표가 낡으므로 새 Boot/App 이 나올 때까지 경고.
    ("1.4.5", "v1.4.6"),
    ("1.4.6", "v1.4.5"),
    ("1.5.0", "v1.5.1"),
])
def test_unknown_is_warn(current, target):
    assert judge(RULE, current, target)["result"] == WARN


def test_no_rule_means_ok():
    assert judge(None, "1.2.4", "v1.4.5")["result"] == OK


def test_judge_carries_generations_and_docs_url():
    r = judge(RULE, "1.2.9", "v1.4.5")
    assert (r["from"], r["to"]) == ("1.2", "1.4")
    assert r["docs_url"] == RULE["docs_url"]


def test_config_rule_shape():
    assert RULE["docs_url"].startswith("https://docs.wiznet.io/")
    assert RULE["known_max"] == "1.4.5"     # 호환표의 Boot V1.3 상한
    assert RULE["isp_recommend_from"] == ["1.2"]
    assert set(RULE["transitions"].values()) <= {OK, WARN, BLOCK}
    for key in RULE["transitions"]:
        src, dst = key.split(">")
        assert generation(src) == src and generation(dst) == dst


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


def _make_dialog(qapp, monkeypatch, current_version, family=None):
    fam = family or next(f for f in _families() if f["id"] == "wiz750sr")
    dlg = fw_git_dialog.FWGitDialog(
        None, "WIZ750SR", fam,
        {"asset_pattern": "WIZ750SR*.bin", "extract_file": None},
        _FakeFetcher(["v1.4.5", "v1.3.3", "v1.2.9"]), ".",
        current_version=current_version,
    )
    dlg._fetch_thread.wait(2000)
    qapp.processEvents()
    return dlg


def _enabled(dlg):
    model = dlg._combo.model()
    return [model.item(i).isEnabled() for i in range(dlg._combo.count())]


def test_dialog_blocks_incompatible_but_still_lists_it(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch, "1.2.4")
    assert dlg._combo.count() == 3                  # 최신도 목록에는 보인다
    assert _enabled(dlg) == [False, True, True]     # 1.4.5 만 선택 불가
    assert dlg._combo.currentIndex() == 1           # 선택 가능한 첫 항목으로 이동
    assert dlg._btn_dl.isEnabled()


def test_dialog_warns_on_uncertain_move(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch, "1.3.3")
    assert _enabled(dlg) == [True, True, True]
    assert dlg._combo.currentIndex() == 0           # v1.4.5, 불확실
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
    dlg = _make_dialog(qapp, monkeypatch, "1.2.4")
    assert dlg._combo.currentIndex() == 1           # v1.3.3
    shown = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: None)

    def _capture(parent, title, text, *a, **k):
        shown.append(text)
        return fw_git_dialog.QMessageBox.No

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning", _capture)
    dlg._on_download()
    assert len(shown) == 1 and "ISP tool" in shown[0]


def test_dialog_certain_move_has_no_prompt(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch, "1.4.2")
    dlg._combo.setCurrentIndex(1)                   # v1.3.3: 확실히 됨
    started = []
    monkeypatch.setattr(dlg, "_begin_download", lambda: started.append(1))

    def _no_prompt(*a, **k):
        raise AssertionError("확실히 되는 이동에서 경고창이 떴다")

    monkeypatch.setattr(fw_git_dialog.QMessageBox, "warning", _no_prompt)
    dlg._on_download()
    assert started == [1]


def test_dialog_unknown_current_version_warns_everything(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch, "")
    assert _enabled(dlg) == [True, True, True]
    assert dlg._compat["result"] == WARN


def test_dialog_without_rule_is_untouched(qapp, monkeypatch):
    fam = {"id": "x", "repo": "a/b"}
    dlg = _make_dialog(qapp, monkeypatch, "1.2.4", family=fam)
    assert _enabled(dlg) == [True, True, True]
    assert dlg._combo.currentIndex() == 0
    assert dlg._compat["result"] == OK
