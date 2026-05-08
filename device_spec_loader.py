"""
device_spec_loader.py
YAML 스펙 파일 → DeviceSpec 구조체 빌드

설계 원칙:
  - Descriptive Layer: 커맨드/값에 min_version → 로더가 FW 버전 기준 필터링
  - Prescriptive Layer: ui.widget_overrides → 파생 규칙으로 못 잡는 예외만 명시
  - 캐시: (device_name, fw_version) 키로 load_device 결과 보관
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SPECS_DIR = Path(__file__).parent / "specs"
COMMANDS_DIR = SPECS_DIR / "commands"
DEVICES_DIR = SPECS_DIR / "devices"

# ---------------------------------------------------------------------------
# 모듈 레벨 캐시
# ---------------------------------------------------------------------------

_spec_cache: dict[tuple[str, str], DeviceSpec] = {}   # (name, fw_ver) → spec
_alias_cache: dict[str, str | None] = {}               # MN_UPPER → spec_name


# ---------------------------------------------------------------------------
# 데이터 구조체
# ---------------------------------------------------------------------------

@dataclass
class CmdEntry:
    cmd: str
    description: str
    regex: str
    values: dict[str, str]      # fw_version 기준 필터링 완료된 상태
    access: str                 # "RO" / "RW" / "WO"
    ui: dict[str, Any] | None

    def is_readable(self) -> bool:
        return self.access in ("RO", "RW")

    def is_writable(self) -> bool:
        return self.access in ("RW", "WO")

    def is_valid(self, value: str) -> bool:
        """values가 있으면 키 존재 여부로 검사, 없으면 regex."""
        if self.values:
            return value in self.values
        if not self.regex:
            return True
        if self.cmd == "RH":
            return True  # 도메인명 허용
        return bool(re.match(self.regex, value))

    def get_display(self, value: str) -> str:
        return self.values.get(value, value)


@dataclass
class FWConfig:
    upload_supported: bool = False
    config_port: int = 50001
    upload_port_from_response: bool = False
    hw_version_field: str = "VR"
    new_hw_major_versions: list[int] = field(default_factory=list)
    new_fw_effective_size: int = 0
    old_fw_max_size: int = 0
    version_specific: list[dict] = field(default_factory=list)


@dataclass
class UITabConfig:
    tab_id: str
    label: str
    groups: list[str]


@dataclass
class WidgetOverride:
    """
    파생 규칙으로 결정할 수 없는 위젯 상태 예외 선언.
    None = 파생 규칙에 맡김 / bool = 명시적 강제.
    tooltip = 비활성 상태일 때 호버 메시지 (None이면 표시 안 함).
    """
    visible: bool | None = None
    enabled: bool | None = None
    tooltip: str | None = None


@dataclass
class UIConfig:
    tabs: list[UITabConfig]
    widget_overrides: dict[str, WidgetOverride] = field(default_factory=dict)


@dataclass
class DeviceSpec:
    name: str
    display_name: str
    aliases: list[str]
    family: str
    channels: int
    cmdset: dict[str, CmdEntry]     # fw_version 기준 필터 완료
    search_cmd_list: list[str]      # cmdset에 없는 항목 자동 제외
    fw_config: FWConfig
    ui_config: UIConfig


# ---------------------------------------------------------------------------
# 버전 유틸
# ---------------------------------------------------------------------------

def _parse_version(ver_str: str | None):
    """packaging.version.Version 반환. 파싱 실패 시 None."""
    if not ver_str:
        return None
    try:
        from packaging.version import Version
        return Version(str(ver_str))
    except Exception:
        return None


def _check_version_condition(fw_ver: Any, condition: str) -> bool:
    """'VR < 1.2.1' 형태의 조건 문자열 평가."""
    try:
        from packaging.version import Version
        parts = condition.split()
        if len(parts) == 3 and parts[0] == "VR":
            op, cmp_ver = parts[1], Version(parts[2])
            return {
                "<":  fw_ver <  cmp_ver,
                "<=": fw_ver <= cmp_ver,
                ">":  fw_ver >  cmp_ver,
                ">=": fw_ver >= cmp_ver,
                "==": fw_ver == cmp_ver,
            }.get(op, False)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# 로더 내부 헬퍼
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _filter_values(raw_values: dict, fw_ver=None) -> dict[str, str]:
    """
    values dict 파싱 + min_version 필터링.

    각 항목 형태:
      "0": "300"                              → 항상 포함
      "16": {value: "1M", min_version: "1.2.1"} → fw_ver >= 1.2.1 일 때만 포함
    """
    result: dict[str, str] = {}
    for k, v in raw_values.items():
        if isinstance(v, dict):
            min_ver = _parse_version(v.get("min_version"))
            if min_ver is not None and fw_ver is not None and fw_ver < min_ver:
                continue
            result[str(k)] = str(v.get("value", ""))
        else:
            result[str(k)] = str(v)
    return result


def _load_command_group(group_name: str) -> dict[str, CmdEntry]:
    """commands/<group>.yaml → {cmd: CmdEntry}."""
    path = COMMANDS_DIR / f"{group_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Command group not found: {path}")
    raw = _load_yaml(path)
    return {
        cmd: CmdEntry(
            cmd=cmd,
            description=spec.get("description", ""),
            regex=spec.get("regex", ""),
            values=spec.get("values", {}) or {},
            access=spec.get("access", "RW"),
            ui=spec.get("ui"),
        )
        for cmd, spec in raw.items()
    }


def _apply_overrides(
    cmdset: dict[str, CmdEntry],
    overrides: dict,
    fw_ver=None,
) -> None:
    """
    device overrides를 cmdset에 적용.

    커맨드 수준 min_version:
      fw_ver < min_version → 해당 커맨드를 cmdset에서 제거 (version-gate)

    values 수준 min_version:
      _filter_values()가 항목별 필터링 처리
    """
    for cmd, ovr in overrides.items():
        if not isinstance(ovr, dict):
            continue

        # 커맨드 수준 version-gate
        cmd_min_ver = _parse_version(ovr.get("min_version"))
        if cmd_min_ver is not None and fw_ver is not None:
            if fw_ver < cmd_min_ver:
                cmdset.pop(cmd, None)
                continue

        if cmd in cmdset:
            entry = cmdset[cmd]
            if "regex" in ovr:
                entry.regex = ovr["regex"]
            if "values" in ovr:
                entry.values = _filter_values(ovr["values"], fw_ver)
        else:
            cmdset[cmd] = CmdEntry(
                cmd=cmd,
                description=ovr.get("description", ""),
                regex=ovr.get("regex", ""),
                values=_filter_values(ovr.get("values", {}), fw_ver),
                access=ovr.get("access", "RW"),
                ui=ovr.get("ui"),
            )


def _parse_widget_overrides(raw: dict, fw_ver=None) -> dict[str, WidgetOverride]:
    """
    ui.widget_overrides YAML 파싱.

    YAML 형태:
      tcp_timeout:
        enabled: {min_version: "1.2.0"}   # fw_ver >= 1.2.0 이면 True
      ch1_ssl_tcpclient:
        enabled: false                     # 항상 False (다른 함수에 위임 선언)
    """
    result: dict[str, WidgetOverride] = {}
    for name, wo in raw.items():
        if not isinstance(wo, dict):
            continue

        visible: bool | None = wo.get("visible")

        enabled_raw = wo.get("enabled")
        if isinstance(enabled_raw, dict):
            min_ver = _parse_version(enabled_raw.get("min_version"))
            if min_ver is not None and fw_ver is not None:
                enabled: bool | None = (fw_ver >= min_ver)
            else:
                enabled = True
        elif isinstance(enabled_raw, bool):
            enabled = enabled_raw
        else:
            enabled = None

        tooltip: str | None = wo.get("tooltip")

        result[name] = WidgetOverride(visible=visible, enabled=enabled, tooltip=tooltip)
    return result


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def load_device(device_name: str, fw_version: str | None = None) -> DeviceSpec:
    """
    DeviceSpec 반환. (device_name, fw_version) 조합으로 캐싱.
    동일 조합은 YAML 파싱 1회만 수행.
    """
    key = (device_name, fw_version or "")
    if key not in _spec_cache:
        _spec_cache[key] = _load_device_impl(device_name, fw_version)
    return _spec_cache[key]


def _load_device_impl(device_name: str, fw_version: str | None) -> DeviceSpec:
    path = DEVICES_DIR / f"{device_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Device spec not found: {path}")

    dev = _load_yaml(path)
    fw_ver = _parse_version(fw_version)

    # 1. 커맨드 그룹 병합
    cmdset: dict[str, CmdEntry] = {}
    for group in dev.get("command_groups", []):
        cmdset.update(_load_command_group(group))

    # 2. device-level overrides (min_version 필터 포함)
    if "overrides" in dev:
        _apply_overrides(cmdset, dev["overrides"], fw_ver)

    # 3. version_specific overrides (하위 호환 — 기존 YAML 지원)
    fw_raw = dev.get("fw_constraints", {})
    if fw_ver and "version_specific" in fw_raw:
        for rule in fw_raw["version_specific"]:
            if _check_version_condition(fw_ver, rule.get("condition", "")):
                _apply_overrides(cmdset, rule.get("overrides", {}), fw_ver)

    # 4. search_cmd_list — cmdset에서 제거된 커맨드(version-gate) 자동 반영
    raw_order: list[str] = dev.get("search_cmd_order", [])
    if not raw_order:
        raw_order = [c for c, e in cmdset.items() if e.is_readable()]
    search_cmd_list = [c for c in raw_order if c in cmdset]

    # 5. FWConfig
    fw_config = FWConfig(
        upload_supported=fw_raw.get("upload_supported", False),
        config_port=fw_raw.get("config_port", 50001),
        upload_port_from_response=fw_raw.get("upload_port_from_response", False),
        hw_version_field=fw_raw.get("hw_version_field", "VR"),
        new_hw_major_versions=fw_raw.get("new_hw_major_versions", []),
        new_fw_effective_size=fw_raw.get("new_fw_effective_size", 0),
        old_fw_max_size=fw_raw.get("old_fw_max_size", 0),
        version_specific=fw_raw.get("version_specific", []),
    )

    # 6. UIConfig (widget_overrides는 fw_ver 반영)
    ui_raw = dev.get("ui", {})
    tabs = [
        UITabConfig(tab_id=t["id"], label=t["label"], groups=t.get("groups", []))
        for t in ui_raw.get("tabs", [])
    ]
    widget_overrides = _parse_widget_overrides(
        ui_raw.get("widget_overrides", {}), fw_ver
    )
    ui_config = UIConfig(tabs=tabs, widget_overrides=widget_overrides)

    return DeviceSpec(
        name=dev["name"],
        display_name=dev.get("display_name", dev["name"]),
        aliases=dev.get("aliases", [dev["name"]]),
        family=dev.get("family", "one_port"),
        channels=dev.get("channels", 1),
        cmdset=cmdset,
        search_cmd_list=search_cmd_list,
        fw_config=fw_config,
        ui_config=ui_config,
    )


def detect_device(mn_value: str) -> str | None:
    """MN 응답값으로 spec_name 감지. alias_cache로 반복 파일 I/O 방지."""
    mn_upper = mn_value.strip().upper()
    if mn_upper in _alias_cache:
        return _alias_cache[mn_upper]
    result = None
    for yaml_file in DEVICES_DIR.glob("*.yaml"):
        dev = _load_yaml(yaml_file)
        for alias in dev.get("aliases", []):
            if alias.upper() == mn_upper:
                result = dev["name"]
                break
        if result:
            break
    _alias_cache[mn_upper] = result
    return result


def list_devices() -> list[str]:
    return [_load_yaml(f)["name"] for f in sorted(DEVICES_DIR.glob("*.yaml"))]


# ---------------------------------------------------------------------------
# 단독 실행 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== 지원 장비 목록 ===")
    for name in list_devices():
        print(f"  {name}")

    print("\n=== WIZ107SR 스펙 로드 ===")
    spec = load_device("WIZ107SR", "3.0.0")
    print(f"  cmdset ({len(spec.cmdset)}): {list(spec.cmdset.keys())}")
    print(f"  DB values: {spec.cmdset['DB'].values}")
    print(f"  BR values: {spec.cmdset['BR'].values}")

    print("\n=== WIZ750SR — FW 1.1.0 (TR 미지원) ===")
    s = load_device("WIZ750SR", "1.1.0")
    print(f"  TR in search_cmd_list: {'TR' in s.search_cmd_list}")

    print("\n=== WIZ750SR — FW 1.2.0 (TR 지원) ===")
    s = load_device("WIZ750SR", "1.2.0")
    print(f"  TR in search_cmd_list: {'TR' in s.search_cmd_list}")

    print("\n=== W55RP20-S2E — FW 1.0.0 (BR 0-15) ===")
    s = load_device("W55RP20-S2E", "1.0.0")
    print(f"  BR count: {len(s.cmdset['BR'].values)}, last: {s.cmdset['BR'].values.get(str(len(s.cmdset['BR'].values)-1))}")

    print("\n=== W55RP20-S2E — FW 1.2.1 (BR 0-19) ===")
    s = load_device("W55RP20-S2E", "1.2.1")
    print(f"  BR count: {len(s.cmdset['BR'].values)}, last: {s.cmdset['BR'].values.get(str(len(s.cmdset['BR'].values)-1))}")

    print("\n=== detect_device 테스트 ===")
    print(f"  'WIZ107SR' → {detect_device('WIZ107SR')}")
    print(f"  'IP20'     → {detect_device('IP20')}")
    print(f"  'unknown'  → {detect_device('unknown')}")
