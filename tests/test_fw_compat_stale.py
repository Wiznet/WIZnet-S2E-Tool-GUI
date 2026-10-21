# -*- coding: utf-8 -*-
"""호환표가 모르는 새 버전을 만났을 때: 최신 호환표를 다시 확인하고, 그래도 없으면 막지 않고 분명히 알린다.

결정(2026-10-16): 새 FW 가 나와도 호환표 갱신은 늦을 수 있다. 호환표에 없는 것은 "안 된다고 아는 것"이
아니라 "모르는 것"이므로 **막지 않고(활성 + [Check Boot])**, 판정 전에 호환표를 한 번 더 확인한 뒤
그래도 없으면 사용자에게 그 사실을 구체적으로 알린다. 수동 Firmware Upload 는 어차피 이 판정 밖이라
막아도 우회되고, 표가 늦은 만큼 사용자가 최신 FW 를 못 쓰게 되는 불이익만 생긴다.

네트워크는 쓰지 않는다. `fw_compat_update.http_fetch` 를 가짜로 바꿔 끼운다.
"""
import copy
import json

import pytest

import fw_boot_compat
import fw_compat_rules as rules
import fw_compat_update as upd
import fw_git_dialog
from tests.test_fw_boot_compat import _enabled, _labels, _make_dialog

TOOL = "1.6.2.24-dev3"
NEW_TAG = "v1.4.6"        # 번들 호환표의 known_max(1.4.5)를 넘는다


@pytest.fixture
def bundled():
    return rules.load_bundled()


class Server:
    """http_fetch 대역. 요청 횟수를 센다."""

    def __init__(self, doc=None, status=200, exc=None, etag='"s1"'):
        self.doc, self.status, self.exc, self.etag = doc, status, exc, etag
        self.calls = 0

    def __call__(self, url, etag=None, timeout=None):
        self.calls += 1
        if self.exc:
            raise self.exc
        body = json.dumps(self.doc).encode("utf-8") if self.doc is not None else b""
        return self.status, body, self.etag


def doc_with_known_max(bundled, known_max, revision=None):
    doc = copy.deepcopy(bundled)
    doc["revision"] = revision or bundled["revision"] + 1
    doc["families"]["wiz750sr"]["known_max"] = known_max
    return doc


@pytest.fixture
def online(monkeypatch):
    """네트워크를 쓸 수 있는 상태로 만들고 서버 대역을 연결한다."""
    rules.set_auto_update(True)
    rules.set_tool_version(TOOL)

    def connect(server):
        monkeypatch.setattr(upd, "http_fetch", server)
        return server

    return connect


# ── judge 가 "호환표가 모름"을 알려 준다 ─────────────────────────────────

def test_judge_reports_beyond_known(bundled):
    rule = rules.get_rule("wiz750sr")
    assert fw_boot_compat.judge(rule, "1.4.5", NEW_TAG)["beyond_known"] is True
    assert fw_boot_compat.judge(rule, "1.4.6", "v1.4.5")["beyond_known"] is True
    assert fw_boot_compat.judge(rule, "1.4.5", "v1.4.4")["beyond_known"] is False
    assert fw_boot_compat.judge(rule, "1.4.5", NEW_TAG)["known_max"] == "1.4.5"


def test_judge_without_rule_is_never_beyond_known():
    result = fw_boot_compat.judge(None, "9.9.9", "10.0.0")
    assert result["beyond_known"] is False and result["result"] == fw_boot_compat.OK


def test_beyond_known_stays_a_warning_not_a_block():
    rule = rules.get_rule("wiz750sr")
    assert fw_boot_compat.judge(rule, "1.4.5", NEW_TAG)["result"] == fw_boot_compat.WARN


# ── 다시 확인할지 판단 ───────────────────────────────────────────────────

def test_no_check_when_auto_update_is_off(monkeypatch):
    server = Server(exc=AssertionError("설정이 꺼져 있으면 네트워크를 쓰면 안 된다"))
    monkeypatch.setattr(upd, "http_fetch", server)
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG) is None
    assert server.calls == 0


def test_no_check_when_nothing_exceeds_known_max(online):
    server = online(Server())
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", "v1.4.5", "v1.3.3") is None
    assert server.calls == 0


def test_no_check_for_a_family_without_a_rule(online):
    server = online(Server())
    assert upd.refresh_if_stale("w55rp20", "9.9.9", "10.0.0") is None
    assert server.calls == 0


def test_check_runs_when_a_release_exceeds_known_max(online, bundled):
    server = online(Server(doc=doc_with_known_max(bundled, "1.4.6")))
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG) == upd.UPDATED
    assert server.calls == 1


def test_check_runs_when_the_device_itself_exceeds_known_max(online, bundled):
    server = online(Server(doc=bundled))
    assert upd.refresh_if_stale("wiz750sr", "1.4.9", "v1.4.5") == upd.UNCHANGED
    assert server.calls == 1


def test_updated_table_is_applied_to_the_very_next_decision(online, bundled):
    online(Server(doc=doc_with_known_max(bundled, "1.4.6")))
    rule = rules.get_rule("wiz750sr")
    assert fw_boot_compat.judge(rule, "1.4.5", NEW_TAG)["beyond_known"] is True

    upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG)

    rule = rules.get_rule("wiz750sr")
    verdict = fw_boot_compat.judge(rule, "1.4.5", NEW_TAG)
    assert verdict["beyond_known"] is False and verdict["result"] == fw_boot_compat.OK


def test_repeated_checks_are_throttled(online, bundled):
    server = online(Server(doc=bundled))
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG) == upd.UNCHANGED
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG) == upd.SKIPPED
    assert server.calls == 1


def test_forced_interval_is_shorter_than_the_normal_one():
    assert upd.FORCED_MIN_INTERVAL_SEC < upd.MIN_INTERVAL_SEC


def test_offline_check_returns_error_without_raising(online):
    online(Server(exc=TimeoutError("timed out")))
    assert upd.refresh_if_stale("wiz750sr", "1.4.5", NEW_TAG) == upd.ERROR


# ── 릴리즈 목록 스레드 ───────────────────────────────────────────────────

class _Fetcher:
    def __init__(self, tags):
        self.tags = tags

    def get_releases_for(self, family):
        return [{"tag_name": t, "published_at": "2026-10-01T00:00:00Z"} for t in self.tags]


def _run_thread(family_id, current, tags):
    thread = fw_git_dialog._FetchReleasesThread(_Fetcher(tags), {"id": family_id}, current)
    got = {}
    thread.done.connect(lambda r: got.setdefault("releases", r))
    thread.error.connect(lambda m: got.setdefault("error", m))
    thread.run()                    # 별도 스레드를 띄우지 않고 그 자리에서 실행한다
    return thread, got


def test_fetch_thread_rechecks_before_handing_over_the_list(online, bundled):
    online(Server(doc=doc_with_known_max(bundled, "1.4.6")))
    thread, got = _run_thread("wiz750sr", "1.4.5", ["v1.4.6", "v1.4.5"])
    assert thread.compat_result == upd.UPDATED
    assert [r["tag_name"] for r in got["releases"]] == ["v1.4.6", "v1.4.5"]


def test_fetch_thread_does_not_touch_the_network_without_a_new_version(online):
    server = online(Server())
    thread, got = _run_thread("wiz750sr", "1.4.5", ["v1.4.5", "v1.4.4"])
    assert thread.compat_result is None and server.calls == 0 and "releases" in got


def test_fetch_thread_still_delivers_the_list_if_the_recheck_blows_up(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("예상 못 한 실패")

    monkeypatch.setattr(upd, "refresh_if_stale", boom)
    thread, got = _run_thread("wiz750sr", "1.4.5", ["v1.4.6"])
    assert "releases" in got and "error" not in got and thread.compat_result is None


# ── 사용자에게 보이는 것 ────────────────────────────────────────────────

def _capture_confirm(dlg, monkeypatch):
    shown = []
    monkeypatch.setattr(
        fw_git_dialog.QMessageBox, "warning",
        lambda parent, title, text, *a, **k: shown.append(text) or fw_git_dialog.QMessageBox.No,
    )
    return shown


def test_unknown_new_version_stays_selectable_and_says_why(qapp, online, bundled, monkeypatch):
    online(Server(doc=bundled))                       # 확인했지만 새 표가 없다 (같은 revision)
    dlg = _make_dialog(qapp, "1.4.5", tags=[NEW_TAG, "v1.4.5", "v1.3.3"])

    assert _enabled(dlg) == [True, True, True]                   # 막지 않는다
    assert "[Check Boot]" in _labels(dlg)[0]
    dlg._update_asset_label(0)
    assert "newer than the compatibility table" in dlg._lbl_asset.text()

    shown = _capture_confirm(dlg, monkeypatch)
    dlg._on_download()
    note = shown[0]
    assert f"rev {bundled['revision']}" in note and "verified up to 1.4.5" in note
    assert "checked for updates just now" in note


def test_message_says_so_when_the_check_could_not_be_done(qapp, online, monkeypatch):
    online(Server(exc=ConnectionError("offline")))
    dlg = _make_dialog(qapp, "1.4.5", tags=[NEW_TAG, "v1.4.5"])
    dlg._update_asset_label(0)
    shown = _capture_confirm(dlg, monkeypatch)
    dlg._on_download()
    assert "could not be completed" in shown[0]


def test_message_says_so_when_it_was_checked_a_few_minutes_ago(qapp, online, bundled, monkeypatch):
    online(Server(doc=bundled))
    _make_dialog(qapp, "1.4.5", tags=[NEW_TAG, "v1.4.5"])        # 첫 창이 확인하고 시각을 남긴다
    dlg = _make_dialog(qapp, "1.4.5", tags=[NEW_TAG, "v1.4.5"])  # 곧바로 연 두 번째 창
    dlg._update_asset_label(0)
    shown = _capture_confirm(dlg, monkeypatch)
    dlg._on_download()
    assert "a few minutes ago" in shown[0]


def test_when_the_table_catches_up_the_warning_disappears(qapp, online, bundled):
    online(Server(doc=doc_with_known_max(bundled, "1.4.6")))
    dlg = _make_dialog(qapp, "1.4.5", tags=[NEW_TAG, "v1.4.5"])
    assert "[Check Boot]" not in _labels(dlg)[0]
    dlg._update_asset_label(0)
    assert "newer than the compatibility table" not in dlg._lbl_asset.text()
    assert dlg._compat["result"] == fw_boot_compat.OK


def test_known_versions_never_show_the_unknown_note(qapp, online):
    server = online(Server())
    dlg = _make_dialog(qapp, "1.4.5", tags=["v1.4.5", "v1.3.3"])
    dlg._update_asset_label(0)
    assert dlg._unknown_version_note() == "" and server.calls == 0
