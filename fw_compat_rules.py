# -*- coding: utf-8 -*-
"""FW from Git 호환표(`config/fw_compat.json`)의 읽기와 검증.

호환표는 규칙이 모인 하나의 문서다. 이 모듈은 문서를 읽어 검증하고, family 별 규칙을
`fw_boot_compat.judge()` 에 넘겨 준다. 판정 자체는 `fw_boot_compat.py` 가 한다.

기준은 exe 에 번들된 사본이다. 번들 사본은 인터넷이 없어도 항상 있다.
문서가 틀렸으면(읽을 수 없거나 형식 위반) 규칙이 없는 것으로 다룬다 — 제약 없음.
번들 사본은 시험이 매번 검증하므로 현실에서는 일어나지 않아야 하는 경우다.

원격 갱신(`fw_compat_update.py`)이 받아 둔 사본이 사용자 폴더에 있으면, 검증을 통과하고
revision 이 번들보다 **클 때만** 번들 대신 쓴다. 툴을 새로 받아 번들이 더 새로워지면 낡은
사본은 저절로 무시된다.

문서 형식:
    schema_version     형식 버전. 이 모듈이 아는 값(SCHEMA_VERSION)과 같아야 한다.
    revision           규칙을 바꿀 때마다 올리는 정수. 더 큰 revision 이 이긴다.
    min_tool_version   이 문서를 해석할 수 있는 가장 낮은 툴 버전.
    families           {family id: 규칙}  — 규칙의 의미는 fw_boot_compat.judge() 참고.
"""
import json
import logging
import os
import sys

from fw_version import parse, parse_triple

_log = logging.getLogger(__name__)

CACHE_FILENAME = "fw_compat_cache.json"

SCHEMA_VERSION = 1
RESULTS = ("ok", "warn", "block")
BUNDLED_RELATIVE = os.path.join("config", "fw_compat.json")


def bundled_path():
    """개발 환경과 PyInstaller 둘 다에서 번들 사본의 경로."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, BUNDLED_RELATIVE)


def validate(doc, tool_version=None):
    """문서의 형식 위반 목록. 비어 있으면 문제없다.

    tool_version 이 주어지면 `min_tool_version` 도 확인한다(이 문서를 해석할 수 없는 구형 툴을 거른다).
    """
    errors = []
    if not isinstance(doc, dict):
        return ["문서가 객체(dict)가 아니다"]

    schema = doc.get("schema_version")
    if not isinstance(schema, int) or isinstance(schema, bool):
        errors.append("schema_version 이 정수가 아니다")
    elif schema != SCHEMA_VERSION:
        errors.append(f"schema_version {schema} 은 이 툴이 아는 {SCHEMA_VERSION} 이 아니다")

    rev = doc.get("revision")
    if not isinstance(rev, int) or isinstance(rev, bool) or rev < 1:
        errors.append("revision 이 1 이상의 정수가 아니다")

    min_tool = doc.get("min_tool_version")
    if parse(min_tool) is None:
        errors.append("min_tool_version 이 버전 문자열이 아니다")
    elif tool_version is not None:
        current = parse(tool_version)
        if current is not None and current < parse(min_tool):
            errors.append(f"툴 {tool_version} 은 이 문서의 min_tool_version {min_tool} 보다 낮다")

    families = doc.get("families")
    if not isinstance(families, dict):
        errors.append("families 가 객체가 아니다")
        return errors
    for fid, rule in families.items():
        errors.extend(f"{fid}: {e}" for e in _validate_rule(rule))
    return errors


def _validate_rule(rule):
    if not isinstance(rule, dict):
        return ["규칙이 객체가 아니다"]
    errors = []

    epochs = rule.get("epochs")
    if not isinstance(epochs, dict) or not epochs:
        errors.append("epochs 가 비어 있거나 객체가 아니다")
        epochs = {}
    starts = []
    for name, start in epochs.items():
        triple = parse_triple(start)
        if triple is None:
            errors.append(f"epochs[{name}] 시작 버전을 읽을 수 없다: {start!r}")
        else:
            starts.append(triple)
    if starts != sorted(starts):
        errors.append("epochs 가 시작 버전 오름차순이 아니다")
    if len(set(starts)) != len(starts):
        errors.append("epochs 에 같은 시작 버전이 둘 이상 있다")

    transitions = rule.get("transitions", {})
    if not isinstance(transitions, dict):
        errors.append("transitions 가 객체가 아니다")
        transitions = {}
    for key, result in transitions.items():
        src, sep, dst = str(key).partition(">")
        if not sep or src not in epochs or dst not in epochs:
            errors.append(f"transitions[{key}] 의 구간 이름이 epochs 에 없다")
        if result not in RESULTS:
            errors.append(f"transitions[{key}] 값 {result!r} 은 {RESULTS} 중 하나여야 한다")

    isp = rule.get("isp_recommend_from", [])
    if not isinstance(isp, list) or any(name not in epochs for name in isp):
        errors.append("isp_recommend_from 은 epochs 에 있는 구간 이름의 목록이어야 한다")

    known_max = rule.get("known_max")
    if known_max is not None and parse_triple(known_max) is None:
        errors.append(f"known_max 를 읽을 수 없다: {known_max!r}")

    docs_url = rule.get("docs_url", "")
    if not isinstance(docs_url, str):
        errors.append("docs_url 이 문자열이 아니다")
    return errors


def cache_path():
    """원격에서 받아 둔 사본의 위치 — 로그·설정과 같은 사용자 폴더."""
    return os.path.join(os.path.expanduser("~"), ".wizconfig", CACHE_FILENAME)


def read_cache_file(path):
    """저장된 사본 파일의 내용(dict). 없거나 읽을 수 없으면 None."""
    data = load_file(path) if os.path.isfile(path) else None
    return data if isinstance(data, dict) else None


def load_bundled():
    """번들 사본. 읽을 수 없으면 빈 dict."""
    return load_file(bundled_path()) or {}


def load_file(path):
    """JSON 파일을 읽는다. 읽을 수 없으면 None."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        _log.error("[compat] 호환표를 읽지 못함 %s: %s", path, e)
        return None


_current = None            # (문서, 출처) — 출처는 "bundled" / "cache" / 시험용 이름
_tool_version = None


def set_tool_version(version):
    """`min_tool_version` 확인에 쓸 툴 버전을 알려 준다(없으면 그 확인을 건너뛴다)."""
    global _tool_version
    _tool_version = version


def _select():
    """번들과 저장된 사본 중 쓸 것을 고른다. (문서, 출처)"""
    bundled = load_file(bundled_path())
    errors = validate(bundled, _tool_version) if bundled is not None else ["파일 없음"]
    if errors:
        _log.error("[compat] 번들 호환표가 올바르지 않아 규칙 없이 동작한다: %s", errors)
        bundled = {}
    best, source = bundled, "bundled"

    meta = read_cache_file(cache_path())
    cached = meta.get("doc") if meta else None
    if cached is not None:
        problems = validate(cached, _tool_version)
        if problems:
            _log.warning("[compat] 저장된 호환표가 올바르지 않아 무시: %s", problems)
        elif cached["revision"] > (bundled or {}).get("revision", 0):
            best, source = cached, "cache"
    return best, source


def current_doc():
    """지금 판정에 쓰는 문서. 검증을 통과한 문서만 돌려주고, 없으면 None.

    한 번 고르면 `reload()` 전까지 바뀌지 않는다 — 열려 있는 화면의 판정이 도중에 달라지지 않게.
    """
    global _current
    if _current is None:
        _current = _select()
    return _current[0] or None


def reload():
    """다음 판정부터 번들·저장된 사본을 다시 고르게 한다(화면을 열 때 부른다)."""
    reset_for_tests()


def reset_for_tests(doc=None, source="test"):
    """시험이 문서를 바꿔 끼우거나 다시 읽게 한다."""
    global _current
    _current = None if doc is None else (doc, source)


def get_rule(family_id, doc=None):
    """family id 의 규칙. 규칙이 없으면 None(제약 없음)."""
    doc = doc if doc is not None else current_doc()
    if not doc:
        return None
    return (doc.get("families") or {}).get(family_id)


def describe(doc=None):
    """로그·화면 표시용 한 줄: 어떤 호환표로 판정했는가."""
    if doc is None:
        current_doc()
        doc, source = _current if _current else ({}, "none")
    else:
        source = "given"
    if not doc:
        return "compat table: none"
    return f"compat table rev {doc.get('revision')} ({doc.get('updated', '?')}, {source})"
