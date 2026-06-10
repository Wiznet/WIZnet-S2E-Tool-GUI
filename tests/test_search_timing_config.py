#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
검색 타이밍 설정(device_search_config) 견고화 테스트.

핵심 불변식(T1): 코드가 읽는 모든 설정 키가 기준에 존재한다.
  접근자(get_*/is_*)는 자동 수집되므로, 새 접근자가 추가되거나
  default.yaml에서 키가 빠지면 이 테스트가 CI에서 차단한다.

설계: plans/2026-06-10-search-timing-config-robustness.md (T1)
"""

import inspect
import yaml
import pytest

from device_search_config import (
    DeviceSearchConfig,
    DecimalSafeLoader,
    _bundled_default_path,
    _user_config_path,
)


def _zero_arg_accessors(cfg):
    """get_*/is_* 중 인자 없이 호출 가능한 접근자를 자동 수집한다.

    수동 목록 유지를 피하기 위함 — 접근자가 늘어도 자동 포함된다.
    """
    out = []
    for name in dir(cfg):
        if not (name.startswith("get_") or name.startswith("is_")):
            continue
        m = getattr(cfg, name)
        if not callable(m):
            continue
        try:
            sig = inspect.signature(m)
        except (TypeError, ValueError):
            continue
        required = [
            p for p in sig.parameters.values()
            if p.default is p.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)
        ]
        if required:  # self는 bound method라 이미 제외됨
            continue
        out.append(name)
    return out


def _leaf_keys(d, prefix=""):
    """중첩 dict의 leaf 키 경로 집합 (예: 'search.phase1.broadcast_timeout_sec')"""
    keys = set()
    for k, v in (d or {}).items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _leaf_keys(v, path)
        else:
            keys.add(path)
    return keys


def test_defaults_cover_all_accessors(tmp_path):
    """DEFAULTS(하드코딩 폴백)만으로 모든 무인자 접근자가 KeyError 없이 동작."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    cfg = DeviceSearchConfig(config_path=str(empty))  # loaded={} → DEFAULTS만

    failed = {}
    for name in _zero_arg_accessors(cfg):
        try:
            getattr(cfg, name)()
        except KeyError as e:
            failed[name] = repr(e)
    assert not failed, f"DEFAULTS에 키 누락 (접근자 KeyError): {failed}"


def test_default_yaml_is_superset_of_defaults():
    """기준 파일(default.yaml)이 코드 DEFAULTS의 모든 leaf 키를 포함한다 (T1 핵심).

    (나) 결정: default.yaml이 기준. DEFAULTS는 폴백.
    폴백에 있는 키가 기준에 없으면 드리프트이므로 차단한다.
    """
    with open(_bundled_default_path(), encoding="utf-8") as f:
        raw = yaml.load(f, Loader=DecimalSafeLoader)

    yaml_keys = _leaf_keys(raw)
    default_keys = _leaf_keys(DeviceSearchConfig.DEFAULTS)
    missing = default_keys - yaml_keys
    assert not missing, f"default.yaml에 누락된 코드 기준 키: {sorted(missing)}"


def test_accessors_on_bundled_default_no_keyerror():
    """번들 default.yaml 단독 로드만으로도 접근자가 무crash (현장 기준 검증)."""
    cfg = DeviceSearchConfig(config_path=str(_bundled_default_path()))

    failed = {}
    for name in _zero_arg_accessors(cfg):
        try:
            getattr(cfg, name)()
        except KeyError as e:
            failed[name] = repr(e)
    assert not failed, f"default.yaml 기준 접근자 KeyError: {failed}"


def test_user_config_path_under_wizconfig():
    """사용자 설정 파일은 ~/.wizconfig/ 아래에 위치한다 (경로 정책)."""
    p = _user_config_path()
    assert p.name == "device_search_timing.yaml"
    assert p.parent.name == ".wizconfig"


def test_bundled_default_exists():
    """번들 기준 파일이 실제로 접근 가능하다 (개발 환경)."""
    assert _bundled_default_path().exists()
