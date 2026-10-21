"""검색 기본 반복 횟수(max_retry_count)는 1 — Search 한 번에 한 번만 검색한다.

고객 요청으로 기본값을 3 에서 원래 값 1 로 되돌렸다.
코드 기본값(DEFAULTS)·번들 default.yaml·첫 실행 때 복사되는 사용자 설정이 서로 어긋나지 않는지도 본다
(142a93a 이전에는 코드 기본값과 default.yaml 키가 어긋나 있었다).
"""
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import device_search_config as dsc  # noqa: E402
from device_search_config import DeviceSearchConfig  # noqa: E402


def _bundled():
    with open(ROOT / "config" / "device_search_timing.default.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["search"]


def test_code_default_is_one():
    d = DeviceSearchConfig.get_defaults()
    assert d["options"]["max_retry_count"] == 1
    assert d["retry"]["default_max_retry"] == 1


def test_bundled_default_yaml_matches_code():
    s = _bundled()
    d = DeviceSearchConfig.get_defaults()
    assert s["options"]["max_retry_count"] == d["options"]["max_retry_count"] == 1
    assert s["retry"]["default_max_retry"] == d["retry"]["default_max_retry"] == 1


def test_first_run_user_config_gets_one(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # 개발용 legacy config/device_search_timing.yaml 이주 경로 차단
    monkeypatch.setattr(dsc, "_resource_path", lambda rel: os.path.join(str(ROOT), rel))
    cfg = DeviceSearchConfig()
    assert cfg.get_current_values()["max_retry_count"] == 1
    assert (tmp_path / ".wizconfig" / "device_search_timing.yaml").exists()


@pytest.mark.parametrize("saved", [3, 5])
def test_existing_user_choice_is_kept(tmp_path, monkeypatch, saved):
    """이미 저장된 값(예전 기본값 3 포함)은 기본값 변경으로 덮어쓰지 않는다."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dsc, "_resource_path", lambda rel: os.path.join(str(ROOT), rel))
    user_dir = tmp_path / ".wizconfig"
    user_dir.mkdir()
    text = (ROOT / "config" / "device_search_timing.default.yaml").read_text(encoding="utf-8")
    (user_dir / "device_search_timing.yaml").write_text(
        text.replace("max_retry_count: 1\n", "max_retry_count: %d\n" % saved), encoding="utf-8")
    assert DeviceSearchConfig().get_current_values()["max_retry_count"] == saved
