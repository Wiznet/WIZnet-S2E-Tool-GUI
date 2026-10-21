# -*- coding: utf-8 -*-
"""호환표 원격 갱신 — 번들이 기준, 검증 통과한 더 큰 revision 만 받아들인다.

네트워크는 쓰지 않는다. `fetch` 자리에 가짜를 넣어 서버의 응답(성공·304·오류·깨진 본문)을 흉내 낸다.
사용자 폴더의 실제 사본은 conftest 의 autouse 픽스처가 임시 경로로 바꿔 둔다.
"""
import copy
import json
import os
import threading

import pytest

import fw_boot_compat
import fw_compat_rules as rules
import fw_compat_update as upd
from device_search_config import DeviceSearchConfig

TOOL = "1.6.2.24-dev3"


@pytest.fixture
def bundled():
    return rules.load_bundled()


@pytest.fixture
def cache():
    return rules.cache_path()          # conftest 가 임시 경로로 바꿔 둔다


def newer(bundled, revision=None, **rule_changes):
    doc = copy.deepcopy(bundled)
    doc["revision"] = revision if revision is not None else bundled["revision"] + 1
    doc["updated"] = "2099-01-01"
    doc["families"]["wiz750sr"].update(rule_changes)
    return doc


class Fetch:
    """가짜 서버. 응답을 하나 주고, 받은 요청을 기록한다."""

    def __init__(self, status=200, body=b"", etag='"v1"', exc=None):
        self.status, self.body, self.etag, self.exc = status, body, etag, exc
        self.calls = []

    def __call__(self, url, etag=None, timeout=None):
        self.calls.append((url, etag, timeout))
        if self.exc:
            raise self.exc
        return self.status, self.body, self.etag


def serving(doc, **kw):
    return Fetch(body=json.dumps(doc).encode("utf-8"), **kw)


def run(cache, fetch, bundled, now=1000.0, **kw):
    return upd.refresh(cache_path=cache, fetch=fetch, tool_version=TOOL, bundled_doc=bundled,
                       now=lambda: now, **kw)


# ── 받아들이는 경우 ──────────────────────────────────────────────────────

def test_newer_valid_document_is_cached(cache, bundled):
    doc = newer(bundled)
    assert run(cache, serving(doc), bundled) == upd.UPDATED

    saved = rules.read_cache_file(cache)
    assert saved["doc"]["revision"] == doc["revision"]
    assert saved["etag"] == '"v1"'
    assert saved["checked_at"] == 1000.0
    assert not os.path.exists(cache + ".tmp")       # 반쯤 쓰인 파일을 남기지 않는다


def test_cached_document_is_used_after_reload(cache, bundled):
    run(cache, serving(newer(bundled, known_max="9.9.9")), bundled)
    rules.reload()
    assert rules.get_rule("wiz750sr")["known_max"] == "9.9.9"
    assert "cache" in rules.describe()


def test_update_changes_the_judgement_from_the_next_decision(cache, bundled):
    """갱신된 규칙이 실제 판정에 반영된다 — 1.3.3 → 1.4 를 막는 새 규칙."""
    before = fw_boot_compat.judge(rules.get_rule("wiz750sr"), "1.3.3", "v1.4.5")["result"]
    assert before == "ok"

    tr = dict(bundled["families"]["wiz750sr"]["transitions"], **{"1.3.3>1.4": "block"})
    run(cache, serving(newer(bundled, transitions=tr)), bundled)

    assert rules.get_rule("wiz750sr")["transitions"]["1.3.3>1.4"] == "ok"      # 이미 고른 문서는 그대로
    rules.reload()
    assert fw_boot_compat.judge(rules.get_rule("wiz750sr"), "1.3.3", "v1.4.5")["result"] == "block"


# ── 받아들이지 않는 경우 ─────────────────────────────────────────────────

def test_same_revision_is_ignored(cache, bundled):
    """번들과 revision 이 같으면 내용이 달라도 바꾸지 않는다 — 바꾸려면 revision 을 올려야 한다."""
    doc = newer(bundled, revision=bundled["revision"], known_max="9.9.9")
    assert run(cache, serving(doc), bundled) == upd.UNCHANGED
    assert "doc" not in (rules.read_cache_file(cache) or {})
    rules.reload()
    assert rules.get_rule("wiz750sr")["known_max"] == bundled["families"]["wiz750sr"]["known_max"]


def test_older_remote_does_not_replace_a_newer_cache(cache, bundled):
    run(cache, serving(newer(bundled, revision=5, known_max="5.0.0")), bundled, now=1000.0)
    result = run(cache, serving(newer(bundled, revision=3, known_max="3.0.0")), bundled, now=1000.0 + 7200)
    assert result == upd.UNCHANGED
    assert rules.read_cache_file(cache)["doc"]["revision"] == 5


@pytest.mark.parametrize("body", [
    pytest.param(b"{ not json", id="broken-json"),
    pytest.param(b"[1, 2]", id="not-an-object"),
    pytest.param(b"\xff\xfe\x00", id="not-utf8"),
    pytest.param(b" " * (upd.MAX_BYTES + 1), id="oversized"),
])
def test_garbage_body_is_rejected(cache, bundled, body):
    assert run(cache, Fetch(body=body), bundled) == upd.REJECTED
    assert rules.read_cache_file(cache) is None


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version=2),
    lambda d: d.pop("revision"),
    lambda d: d.update(min_tool_version="99.0.0"),
    lambda d: d["families"]["wiz750sr"]["transitions"].update({"1.2>1.4": "maybe"}),
    lambda d: d["families"]["wiz750sr"].update(epochs={}),
])
def test_invalid_document_is_rejected_even_if_revision_is_higher(cache, bundled, mutate):
    doc = newer(bundled, revision=50)
    mutate(doc)
    assert run(cache, serving(doc), bundled) == upd.REJECTED
    assert rules.read_cache_file(cache) is None


def test_document_needing_a_newer_tool_is_ignored(cache, bundled):
    doc = newer(bundled)
    doc["min_tool_version"] = "9.0.0"
    assert run(cache, serving(doc), bundled) == upd.REJECTED


# ── 네트워크 실패는 조용하다 ─────────────────────────────────────────────

@pytest.mark.parametrize("fetch", [
    Fetch(exc=TimeoutError("timed out")),
    Fetch(exc=ConnectionError("offline")),
    Fetch(exc=OSError("DNS")),
    Fetch(status=404),
    Fetch(status=500),
    Fetch(status=403),
])
def test_network_failures_never_raise_and_change_nothing(cache, bundled, fetch):
    assert run(cache, fetch, bundled) == upd.ERROR
    assert rules.read_cache_file(cache) is None


def test_plain_http_is_refused():
    with pytest.raises(ValueError):
        upd.http_fetch("http://raw.githubusercontent.com/x/y/master/config/fw_compat.json")


def test_url_is_https_and_fixed():
    assert upd.URL.startswith("https://raw.githubusercontent.com/Wiznet/WIZnet-S2E-Tool-GUI/")
    assert upd.URL.endswith("/config/fw_compat.json")


# ── 재확인 억제와 조건부 요청 ────────────────────────────────────────────

def test_recently_checked_is_skipped_without_asking(cache, bundled):
    run(cache, serving(newer(bundled)), bundled, now=1000.0)
    fetch = serving(newer(bundled, revision=99))
    assert run(cache, fetch, bundled, now=1000.0 + 60) == upd.SKIPPED
    assert fetch.calls == []
    assert run(cache, fetch, bundled, now=1000.0 + upd.MIN_INTERVAL_SEC + 1) == upd.UPDATED
    assert len(fetch.calls) == 1


def test_not_modified_keeps_the_cache_and_sends_the_etag(cache, bundled):
    run(cache, serving(newer(bundled, revision=5), etag='"abc"'), bundled, now=1000.0)
    fetch = Fetch(status=304)
    assert run(cache, fetch, bundled, now=1000.0 + 7200) == upd.UNCHANGED
    assert fetch.calls[0][1] == '"abc"'
    saved = rules.read_cache_file(cache)
    assert saved["doc"]["revision"] == 5 and saved["checked_at"] == 1000.0 + 7200


def test_no_etag_is_sent_when_there_is_no_usable_cache(cache, bundled):
    fetch = serving(newer(bundled))
    run(cache, fetch, bundled)
    assert fetch.calls[0][1] is None


# ── 번들과 저장된 사본 중 고르기 ─────────────────────────────────────────

def _put_cache(cache, doc):
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"doc": doc, "etag": '"x"', "checked_at": 1.0}, f)


def test_cache_older_than_bundled_is_ignored(cache, bundled):
    """툴을 새로 받아 번들이 더 새로워지면 낡은 사본은 저절로 무시된다."""
    _put_cache(cache, newer(bundled, revision=max(bundled["revision"] - 1, 1), known_max="0.1.0"))
    rules.reload()
    assert rules.get_rule("wiz750sr")["known_max"] == bundled["families"]["wiz750sr"]["known_max"]
    assert "bundled" in rules.describe()


def test_invalid_cache_is_ignored(cache, bundled):
    doc = newer(bundled, revision=70)
    doc["schema_version"] = 99
    _put_cache(cache, doc)
    rules.reload()
    assert "bundled" in rules.describe()


def test_broken_cache_file_is_ignored(cache, bundled):
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        f.write("{ truncated")
    rules.reload()
    assert "bundled" in rules.describe()
    assert rules.get_rule("wiz750sr") is not None


def test_selection_is_frozen_until_reload(cache, bundled):
    rules.get_rule("wiz750sr")
    _put_cache(cache, newer(bundled, known_max="9.9.9"))
    assert rules.get_rule("wiz750sr")["known_max"] != "9.9.9"
    rules.reload()
    assert rules.get_rule("wiz750sr")["known_max"] == "9.9.9"


def test_cache_requiring_a_newer_tool_is_ignored_by_the_selector(cache, bundled):
    doc = newer(bundled, known_max="9.9.9")
    doc["min_tool_version"] = "99.0.0"
    _put_cache(cache, doc)
    rules.set_tool_version(TOOL)
    try:
        rules.reload()
        assert rules.get_rule("wiz750sr")["known_max"] != "9.9.9"
    finally:
        rules.set_tool_version(None)


# ── 백그라운드와 설정 ───────────────────────────────────────────────────

def test_background_refresh_runs_off_the_caller_thread(cache, bundled):
    caller = threading.get_ident()
    seen = {}
    done = threading.Event()

    def fetch(url, etag=None, timeout=None):
        seen["thread"] = threading.get_ident()
        return 200, json.dumps(newer(bundled)).encode("utf-8"), '"e"'

    t = upd.refresh_in_background(tool_version=TOOL, on_done=lambda r: (seen.update(result=r), done.set()),
                                  cache_path=cache, fetch=fetch, bundled_doc=bundled)
    assert done.wait(5)
    t.join(5)
    assert seen["thread"] != caller and seen["result"] == upd.UPDATED
    assert t.daemon


def test_auto_update_setting_defaults_to_on(tmp_path):
    cfg = DeviceSearchConfig(str(tmp_path / "t.yaml"))
    assert cfg.is_fw_compat_auto_update() is True


def test_auto_update_setting_can_be_turned_off(tmp_path):
    path = tmp_path / "t.yaml"
    path.write_text("fw_compat:\n  auto_update: false\n", encoding="utf-8")
    assert DeviceSearchConfig(str(path)).is_fw_compat_auto_update() is False


def test_user_config_without_the_key_keeps_working(tmp_path):
    """이 항목이 생기기 전에 만들어진 사용자 설정 파일에도 기본값(켬)이 채워진다."""
    path = tmp_path / "t.yaml"
    path.write_text("version: '1.0'\nschema_version: 1\n", encoding="utf-8")
    assert DeviceSearchConfig(str(path)).is_fw_compat_auto_update() is True
