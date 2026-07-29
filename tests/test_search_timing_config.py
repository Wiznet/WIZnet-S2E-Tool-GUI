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


# ─────────────────────────────────────────────────────────────────
# P3: 로드 시 검증(validate) — 범위/enum 위반 교정
# ─────────────────────────────────────────────────────────────────

def test_out_of_range_value_reset_to_default(tmp_path):
    """범위 위반 값(손편집·구버전)은 로드 시 기준값으로 복귀 + 복귀 목록 기록."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "search:\n  phase1:\n    broadcast_timeout_sec: 999.0\n",
        encoding="utf-8",
    )
    cfg = DeviceSearchConfig(config_path=str(bad))
    v = cfg.get_phase1_broadcast_timeout()
    assert v != 999.0
    assert 0.5 <= v <= 10.0
    assert any("broadcast_timeout_sec" in r[0] for r in cfg.last_resets)


def test_invalid_enum_level_reset(tmp_path):
    """logging.level enum 위반 시 기준값으로 복귀."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("logging:\n  level: BOGUS\n", encoding="utf-8")
    cfg = DeviceSearchConfig(config_path=str(bad))
    assert any("logging.level" in r[0] for r in cfg.last_resets)


def test_valid_config_no_resets():
    """정상(번들 default) 설정은 복귀가 발생하지 않는다."""
    cfg = DeviceSearchConfig(config_path=str(_bundled_default_path()))
    assert cfg.last_resets == []


# ─────────────────────────────────────────────────────────────────
# P4: 스키마 마이그레이션 엔진
# ─────────────────────────────────────────────────────────────────

def test_legacy_config_migrates_without_crash(tmp_path):
    """schema_version 없는 legacy 설정 → 현재 버전, 무crash + 튜닝값 보존."""
    legacy = tmp_path / "legacy.yaml"
    # active_preset 비활성 — 개별 튜닝값이 살아있는 시나리오
    legacy.write_text(
        "active_preset: ''\n"
        "search:\n  phase1:\n    broadcast_timeout_sec: 5.0\n",
        encoding="utf-8",
    )
    cfg = DeviceSearchConfig(config_path=str(legacy))
    # 모든 무인자 접근자가 KeyError 없이 동작 (fill 불변식)
    for name in _zero_arg_accessors(cfg):
        getattr(cfg, name)()
    # legacy 튜닝값 보존
    assert cfg.get_phase1_broadcast_timeout() == 5.0


def test_migration_runs_registered_steps_in_order(tmp_path):
    """등록 step이 버전 순서대로 적용된다 (가상 시나리오로 빈 엔진을 검증)."""
    cfg = DeviceSearchConfig(config_path=str(_bundled_default_path()))
    calls = []

    def s2(c):
        calls.append(2)
        c["marker"] = "v2"
        return c

    def s3(c):
        calls.append(3)
        c["marker"] = "v3"
        return c

    cfg._MIGRATIONS = {2: s2, 3: s3}  # 인스턴스 오버라이드로 엔진만 검증
    result = cfg._migrate(
        {"schema_version": 1, "marker": "start"},
        {"schema_version": 3},
        tmp_path / "noexist.yaml",
    )
    assert calls == [2, 3]
    assert result["marker"] == "v3"
    assert result["schema_version"] == 3


def test_downgrade_backs_up_and_uses_reference(tmp_path):
    """미래 버전 설정(다운그레이드)은 백업 후 기준값으로 대체된다."""
    user = tmp_path / "future.yaml"
    user.write_text(
        "schema_version: 99\n"
        "search:\n  phase1:\n    broadcast_timeout_sec: 7.0\n",
        encoding="utf-8",
    )
    cfg = DeviceSearchConfig(config_path=str(user))
    assert (tmp_path / "future.yaml.v99.bak").exists()  # 원본 백업
    assert cfg.get_phase1_broadcast_timeout() != 7.0     # 기준값으로 대체


# ─────────────────────────────────────────────────────────────────
# P5: 검증 교정 영속화 (반복 방지)
# ─────────────────────────────────────────────────────────────────

def test_reset_persists_corrected_config(tmp_path):
    """검증 위반 교정분이 파일에 저장되고 원본은 .invalid.bak로 백업된다."""
    f = tmp_path / "u.yaml"
    f.write_text(
        "active_preset: ''\n"
        "search:\n  phase1:\n    broadcast_timeout_sec: 999.0\n",
        encoding="utf-8",
    )
    cfg = DeviceSearchConfig(config_path=str(f))
    assert cfg.last_resets  # 위반 감지

    # config_path 인스턴스는 자동 저장을 하지 않으므로 수동 호출로 영속화 검증
    cfg.config_file_path = f
    cfg._persist_after_reset()

    assert (tmp_path / "u.yaml.invalid.bak").exists()
    reloaded = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert reloaded["search"]["phase1"]["broadcast_timeout_sec"] != 999.0
