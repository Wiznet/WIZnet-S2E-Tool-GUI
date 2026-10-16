# -*- coding: utf-8 -*-
"""`.github/scripts/check_compat_table.py` — known_max 가 낡았는지 알리는 점검의 판정 로직.

네트워크 부분(최신 릴리즈 조회)은 시험하지 않고, "무엇을 낡았다고 보는가"와 보고서 내용만 고정한다.
워크플로 파일이 읽을 수 있는 YAML 이고 필요한 권한만 요청하는지도 본다.
"""
import importlib.util
import os

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, ".github", "scripts", "check_compat_table.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "fw-compat-watch.yml")

spec = importlib.util.spec_from_file_location("check_compat_table", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

COMPAT = {"revision": 3, "families": {"wiz750sr": {"known_max": "1.4.5"}}}
SOURCES = {"families": [{"id": "wiz750sr", "repo": "Wiznet/WIZ750SR"},
                        {"id": "w55rp20", "repo": "WIZnet-ioNIC/W55RP20-S2E"}]}
REPO = "Wiznet/WIZ750SR"


def test_newer_release_is_reported():
    stale = chk.find_stale(COMPAT, SOURCES, {REPO: "v1.4.6"})
    assert stale == [{"family": "wiz750sr", "repo": REPO, "latest": "v1.4.6",
                      "known_max": "1.4.5", "revision": 3}]


@pytest.mark.parametrize("latest", ["v1.4.5", "1.4.5", "v1.4.4", "v1.3.3"])
def test_same_or_older_release_is_not_reported(latest):
    assert chk.find_stale(COMPAT, SOURCES, {REPO: latest}) == []


@pytest.mark.parametrize("latest", [None, "", "latest", "nightly"])
def test_unknown_or_unreadable_latest_is_skipped_not_crashed(latest):
    assert chk.find_stale(COMPAT, SOURCES, {REPO: latest}) == []


def test_missing_repo_in_sources_is_skipped():
    assert chk.find_stale(COMPAT, {"families": []}, {REPO: "v9.9.9"}) == []


def test_only_families_with_a_rule_are_checked():
    """규칙이 없는 family(w55rp20)는 최신이 얼마든 알릴 대상이 아니다."""
    stale = chk.find_stale(COMPAT, SOURCES, {REPO: "v1.4.5", "WIZnet-ioNIC/W55RP20-S2E": "v9.0.0"})
    assert stale == []


def test_known_max_is_never_modified():
    before = {"revision": 3, "families": {"wiz750sr": {"known_max": "1.4.5"}}}
    chk.find_stale(before, SOURCES, {REPO: "v1.4.6"})
    assert before["families"]["wiz750sr"]["known_max"] == "1.4.5"


def test_report_tells_the_maintainer_what_to_do():
    stale = chk.find_stale(COMPAT, SOURCES, {REPO: "v1.4.6"})
    report = chk.render_report(stale)
    assert "v1.4.6" in report and "1.4.5" in report
    assert "config/fw_compat.json" in report and "revision" in report and "master" in report
    assert "never raised automatically" in report
    assert "v1.4.6" in chk.render_title(stale)


def test_report_has_no_tool_attribution():
    """공개 이슈에 들어갈 글이다 — 도구 흔적이 없어야 한다."""
    text = chk.render_report(chk.find_stale(COMPAT, SOURCES, {REPO: "v1.4.6"})) + chk.render_title(
        chk.find_stale(COMPAT, SOURCES, {REPO: "v1.4.6"}))
    assert "claude" not in text.lower() and "anthropic" not in text.lower()


def test_current_repo_tables_are_consistent_with_each_other():
    """실제 호환표의 family 가 fw_sources.json 에 저장소로 등록돼 있어야 점검이 동작한다."""
    import json
    with open(os.path.join(ROOT, "config", "fw_compat.json"), encoding="utf-8") as f:
        compat = json.load(f)
    with open(os.path.join(ROOT, "config", "fw_sources.json"), encoding="utf-8") as f:
        sources = json.load(f)
    repos = {fam["id"]: fam.get("repo") for fam in sources["families"]}
    for family_id in compat["families"]:
        assert repos.get(family_id), f"{family_id}: fw_sources.json 에 repo 가 없다"


# ── 워크플로 ─────────────────────────────────────────────────────────────

@pytest.fixture
def workflow():
    with open(WORKFLOW, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_workflow_is_valid_yaml_with_schedule_and_manual_trigger(workflow):
    on = workflow.get("on", workflow.get(True))        # PyYAML 이 키 on 을 True 로 읽는 경우가 있다
    assert "schedule" in on and "workflow_dispatch" in on


def test_workflow_requests_only_the_permissions_it_needs(workflow):
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}


def test_workflow_does_not_write_to_the_repository(workflow):
    text = open(WORKFLOW, encoding="utf-8").read()
    for forbidden in ("git push", "git commit", "gh pr ", "contents: write"):
        assert forbidden not in text


def test_workflow_only_opens_an_issue_when_something_is_stale(workflow):
    steps = workflow["jobs"]["watch"]["steps"]
    issue_step = next(s for s in steps if "issue" in s.get("name", "").lower())
    assert "stale == 'true'" in issue_step["if"]
