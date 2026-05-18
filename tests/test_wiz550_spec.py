"""
tests/test_wiz550_spec.py — Phase 5 WIZ550 DeviceSpec YAML 검증 테스트

SPEC-01: WIZ550SR.yaml 스키마 + 필드명 검증
SPEC-02: WIZ550S2E.yaml 스키마 + 조건부 섹션 검증
SPEC-03: WIZ550WEB.yaml disabled 필드 존재 검증
SPEC-04: validate_schemas.py 전체 통과 (subprocess)
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SPECS_DIR = Path(__file__).parent.parent / "specs" / "devices"
SR_YAML   = SPECS_DIR / "WIZ550SR.yaml"
S2E_YAML  = SPECS_DIR / "WIZ550S2E.yaml"
WEB_YAML  = SPECS_DIR / "WIZ550WEB.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"{path.name} not yet created")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ── SPEC-01 ──────────────────────────────────────────────────────────────────

def test_wiz550sr_schema_valid():
    """WIZ550SR.yaml 이 validate_schemas.py 검증을 통과한다."""
    _load_yaml(SR_YAML)
    result = subprocess.run(
        [sys.executable, "validate_schemas.py"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent
    )
    assert result.returncode == 0, f"validate_schemas.py failed:\n{result.stdout}\n{result.stderr}"


def test_wiz550sr_field_ids_match_profile():
    """WIZ550SR YAML field.id 가 WIZ550Profile.parse_sr() 반환 dict 키와 일치한다."""
    data = _load_yaml(SR_YAML)
    all_field_ids = {
        f["id"]
        for section in data["ui"]["sections"]
        for f in section["fields"]
        if not f.get("disabled")
    }
    # parse_sr 반환 dict 의 UI 관련 키 (내부용 제외)
    # inactivity/reconnection: WIZ550Profile._parse_base_162() 반환 필드 — options 섹션에 포함
    expected_ui_keys = {
        "mac", "local_ip", "gateway", "subnet", "working_mode",
        "remote_ip", "local_port", "remote_port",
        "baud_rate", "data_bits", "parity", "stop_bits", "flow_control",
        "pw_setting", "pw_connect", "dhcp_use", "dns_use",
        "dns_server_ip", "serial_command",
        "inactivity", "reconnection",
    }
    missing = expected_ui_keys - all_field_ids
    assert not missing, f"SR YAML 에서 누락된 field.id: {missing}"


# ── SPEC-02 ──────────────────────────────────────────────────────────────────

def test_wiz550s2e_schema_valid():
    """WIZ550S2E.yaml 이 validate_schemas.py 검증을 통과한다."""
    _load_yaml(S2E_YAML)
    result = subprocess.run(
        [sys.executable, "validate_schemas.py"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent
    )
    assert result.returncode == 0, f"validate_schemas.py failed:\n{result.stdout}"


def test_wiz550s2e_conditional_sections():
    """WIZ550S2E.yaml 에 condition=mqtt 섹션과 condition=modbus 섹션이 존재한다."""
    data = _load_yaml(S2E_YAML)
    conditions = {s.get("condition") for s in data["ui"]["sections"]}
    assert "mqtt" in conditions, "S2E YAML 에 condition=mqtt 섹션 없음"
    assert "modbus" in conditions, "S2E YAML 에 condition=modbus 섹션 없음"


def test_wiz550s2e_mqtt_field_ids():
    """WIZ550S2E YAML MQTT 섹션의 field.id 가 parse_s2e() 반환 키와 일치한다."""
    data = _load_yaml(S2E_YAML)
    mqtt_section = next(
        (s for s in data["ui"]["sections"] if s.get("condition") == "mqtt"), None
    )
    assert mqtt_section is not None
    mqtt_ids = {f["id"] for f in mqtt_section["fields"]}
    assert "mqtt_pub_topic" in mqtt_ids, "mqtt_pub_topic 없음 (publish_topic 이면 오류)"
    assert "mqtt_sub_topic" in mqtt_ids, "mqtt_sub_topic 없음 (subscribe_topic 이면 오류)"
    assert "mqtt_user" in mqtt_ids
    assert "mqtt_pw" in mqtt_ids


# ── SPEC-03 ──────────────────────────────────────────────────────────────────

def test_wiz550web_schema_valid():
    """WIZ550WEB.yaml 이 validate_schemas.py 검증을 통과한다."""
    _load_yaml(WEB_YAML)
    result = subprocess.run(
        [sys.executable, "validate_schemas.py"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent
    )
    assert result.returncode == 0, f"validate_schemas.py failed:\n{result.stdout}"


def test_web_disabled_fields():
    """WIZ550WEB YAML 에 disabled:true 필드 5개가 명시적으로 포함된다 (SPEC-03)."""
    data = _load_yaml(WEB_YAML)
    disabled_ids = {
        f["id"]
        for section in data["ui"]["sections"]
        for f in section["fields"]
        if f.get("disabled") is True
    }
    required_disabled = {"working_mode", "remote_ip", "remote_port", "local_port", "serial_command"}
    missing = required_disabled - disabled_ids
    assert not missing, f"WEB YAML 에서 disabled:true 미포함 필드: {missing}"


def test_web_no_pw_connect():
    """WIZ550WEB YAML 에 pw_connect 필드가 없다 (WEB 구조체 미포함, Pitfall 2)."""
    data = _load_yaml(WEB_YAML)
    all_ids = {f["id"] for s in data["ui"]["sections"] for f in s["fields"]}
    assert "pw_connect" not in all_ids, "WEB YAML 에 pw_connect 포함됨 — 구조체에 없음"


def test_web_uart0_uart1_sections():
    """WIZ550WEB YAML 에 uart0 섹션과 uart1 섹션이 존재한다."""
    data = _load_yaml(WEB_YAML)
    section_ids = {s["id"] for s in data["ui"]["sections"]}
    assert "uart0" in section_ids, "WEB YAML 에 uart0 섹션 없음"
    assert "uart1" in section_ids, "WEB YAML 에 uart1 섹션 없음"


# ── SPEC-04 ──────────────────────────────────────────────────────────────────

def test_validate_schemas_all_pass():
    """validate_schemas.py 전체가 종료 코드 0 으로 통과한다."""
    result = subprocess.run(
        [sys.executable, "validate_schemas.py"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent
    )
    assert result.returncode == 0, (
        f"validate_schemas.py 실패:\n{result.stdout}\n{result.stderr}"
    )
