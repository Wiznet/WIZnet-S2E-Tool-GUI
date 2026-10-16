# -*- coding: utf-8 -*-
"""호환표 문서(`config/fw_compat.json`)의 읽기·검증.

문서는 exe 에 번들되는 기준 사본이고, 형식이 틀리면 규칙 없이(제약 없음) 동작하게 된다.
그래서 번들 사본이 항상 검증을 통과하는지, 검증이 실제로 잘못된 문서를 걸러내는지를 고정한다.
(원격 갱신이 붙으면 같은 검증이 받아 온 문서에도 적용된다.)
"""
import copy
import json
import os
import re
import sys

import pytest

import fw_compat_rules as rules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def doc():
    with open(os.path.join(ROOT, "config", "fw_compat.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _fresh_module_state():
    rules.reset_for_tests()
    yield
    rules.reset_for_tests()


# ── 번들 사본 ────────────────────────────────────────────────────────────

def test_bundled_document_is_valid(doc):
    assert rules.validate(doc) == []


def test_bundled_document_declares_revision_and_schema(doc):
    assert doc["schema_version"] == rules.SCHEMA_VERSION
    assert isinstance(doc["revision"], int) and doc["revision"] >= 1


def test_bundled_path_points_at_the_shipped_file():
    assert os.path.samefile(rules.bundled_path(), os.path.join(ROOT, "config", "fw_compat.json"))


def test_bundled_path_follows_pyinstaller_extraction_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert rules.bundled_path() == os.path.join(str(tmp_path), "config", "fw_compat.json")


def test_build_script_bundles_every_config_json():
    """config/*.json 을 번들하는 줄이 빠지면 exe 에 호환표가 없어 규칙 없이 동작한다."""
    with open(os.path.join(ROOT, "build.ps1"), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r"config\\+\*\.json", text), "build.ps1 에 config 의 *.json 번들 줄이 없다"


# ── 규칙 조회 ────────────────────────────────────────────────────────────

def test_get_rule_for_wiz750sr_and_none_for_others():
    assert rules.get_rule("wiz750sr")["epochs"]["1.3.3"] == "1.3.3"
    for other in ("w55rp20", "wiz550sr", "wiz752sr", "nope", None):
        assert rules.get_rule(other) is None


def test_get_rule_without_document_means_no_constraint():
    assert rules.get_rule("wiz750sr", doc={}) is None


def test_invalid_bundled_document_degrades_to_no_rules(monkeypatch, tmp_path):
    bad = tmp_path / "fw_compat.json"
    bad.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(rules, "bundled_path", lambda: str(bad))
    rules.reset_for_tests()
    assert rules.current_doc() is None
    assert rules.get_rule("wiz750sr") is None


def test_wrong_schema_bundled_document_degrades_to_no_rules(monkeypatch, tmp_path, doc):
    doc["schema_version"] = 99
    bad = tmp_path / "fw_compat.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(rules, "bundled_path", lambda: str(bad))
    rules.reset_for_tests()
    assert rules.current_doc() is None


def test_describe_names_the_revision(doc):
    assert f"rev {doc['revision']}" in rules.describe(doc)
    assert rules.describe({}) == "compat table: none"


# ── 검증이 잘못된 문서를 실제로 거른다 ─────────────────────────────────────

def _mut(doc, fn):
    d = copy.deepcopy(doc)
    fn(d)
    return d


RULE = ["families", "wiz750sr"]


def _rule(d):
    return d["families"]["wiz750sr"]


BAD = {
    "schema_version 이 아는 값이 아님": lambda d: d.update(schema_version=2),
    "schema_version 이 문자열": lambda d: d.update(schema_version="1"),
    "revision 없음": lambda d: d.pop("revision"),
    "revision 0": lambda d: d.update(revision=0),
    "revision 이 bool": lambda d: d.update(revision=True),
    "min_tool_version 이 숫자 아님": lambda d: d.update(min_tool_version="latest"),
    "families 가 목록": lambda d: d.update(families=[]),
    "epochs 비어 있음": lambda d: _rule(d).update(epochs={}),
    "epochs 시작 버전 못 읽음": lambda d: _rule(d)["epochs"].update({"1.4": "abc"}),
    "epochs 내림차순": lambda d: _rule(d).update(epochs={"1.4": "1.4.0", "1.2": "1.2.0"}),
    "epochs 시작 버전 중복": lambda d: _rule(d)["epochs"].update({"1.3.3": "1.3.0"}),
    "transitions 가 없는 구간": lambda d: _rule(d)["transitions"].update({"1.2>9.9": "ok"}),
    "transitions 구분자 없음": lambda d: _rule(d)["transitions"].update({"1.2": "ok"}),
    "transitions 값이 허용 밖": lambda d: _rule(d)["transitions"].update({"1.2>1.4": "maybe"}),
    "isp_recommend_from 이 없는 구간": lambda d: _rule(d).update(isp_recommend_from=["0.9"]),
    "known_max 못 읽음": lambda d: _rule(d).update(known_max="soon"),
    "docs_url 이 숫자": lambda d: _rule(d).update(docs_url=5),
    "규칙이 목록": lambda d: d["families"].update(wiz750sr=[]),
}


@pytest.mark.parametrize("name", list(BAD))
def test_validate_rejects(doc, name):
    errors = rules.validate(_mut(doc, BAD[name]))
    assert errors, f"잘못된 문서를 통과시켰다: {name}"


@pytest.mark.parametrize("not_a_doc", [None, [], "x", 3])
def test_validate_rejects_non_objects(not_a_doc):
    assert rules.validate(not_a_doc)


def test_validate_rejects_tool_older_than_min_tool_version(doc):
    doc["min_tool_version"] = "1.7.0"
    assert rules.validate(doc, tool_version="1.6.2.24-dev3")
    assert rules.validate(doc, tool_version="1.7.0") == []
    assert rules.validate(doc, tool_version="1.8.1") == []


def test_validate_ignores_min_tool_version_when_tool_version_unknown(doc):
    doc["min_tool_version"] = "9.9.9"
    assert rules.validate(doc) == []
