#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가짜 WIZnet 장치를 구성 파일 하나로 한 번에 띄운다.

계열마다 포트가 달라 따로 띄우면 창을 셋 열어야 한다. 그러다 하나를 빠뜨리면
"검색해도 안 잡힌다" 로 이어진다(2026-09-07 실제로 그랬다). 여기서 한 번에 세운다.

    segcp  UDP 50001            WIZ752SR-12x 등 텍스트 프로토콜 (12기종)
    w550   UDP 6550             WIZ550SR / WIZ550S2E / WIZ550WEB
    w1x0   UDP 1460 + TCP 1461  WIZ1x0SR

구성은 `config/fake_fleet.yaml` 에 있다. 항목별 옵션은 그 파일의 주석 참조.

설정툴 쪽 주의:
  - WIZ550 검색은 항상 돈다
  - **WIZ1x0 검색은 "WIZ1x0SR Search" 체크박스를 켜야 돈다.** 안 켜면 묻지도 않는다
  - 직접-IP 검색(TCP 1461)은 IP Address 모드 + 그 체크박스 + IP 입력이 있어야 돈다

실행

    uv run python -m tests.fake_fleet
    uv run python -m tests.fake_fleet --only segcp
    uv run python -m tests.fake_fleet --config 내구성.yaml
"""

from __future__ import annotations

import argparse
import dataclasses
import threading
from pathlib import Path

import yaml

from tests.fake_segcp_device import PROFILE_WIZ752_MEASURED, FirmwareQuirks
from tests.fake_segcp_device import make_device_fleet as make_segcp_fleet
from tests.fake_segcp_device import profile_from_spec, profile_with_remote_host, tool_asked_commands
from tests.fake_wiz1x0_device import make_device_fleet as make_1x0_fleet
from tests.fake_wiz550_device import PRODUCT_CODES
from tests.fake_wiz550_device import make_device_fleet as make_550_fleet

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "fake_fleet.yaml"
FAMILIES = ("segcp", "w550", "w1x0")

# 항목마다 받아들이는 키. 오타를 조용히 흘리지 않으려고 명시한다.
_COMMON_KEYS = {"family", "count", "port", "mac", "bind", "verbose"}
_FAMILY_KEYS = {
    "segcp": _COMMON_KEYS | {"device", "fw_version", "remote_host", "quirks"},
    "w550": _COMMON_KEYS | {"type", "fw", "password"},
    "w1x0": _COMMON_KEYS | {"direct_port", "ip", "setc_carries_board"},
}
_QUIRK_KEYS = {f.name for f in dataclasses.fields(FirmwareQuirks)}


def load_fleet_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    """YAML 구성을 읽는다."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _check_keys(entry: dict, allowed: set, where: str) -> None:
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise ValueError(f"{where}: 모르는 항목 {unknown} — 오타이거나 지원하지 않는 설정이다. "
                         f"쓸 수 있는 것: {sorted(allowed)}")


def _quirks_from(raw: dict | None) -> FirmwareQuirks:
    if not raw:
        return FirmwareQuirks()
    _check_keys(raw, _QUIRK_KEYS, "quirks")
    return FirmwareQuirks(**raw)


def _segcp_profile(entry: dict, mac: str) -> dict:
    """프로파일 결정. device 를 주면 spec 에서, 아니면 실측 752 프로파일."""
    device = entry.get("device")
    if device:
        ver = str(entry.get("fw_version") or "1.2.4")
        profile = profile_from_spec(device, mac=mac, fw_version=ver,
                                    include=tool_asked_commands(device, ver, mac))
    else:
        profile = dict(PROFILE_WIZ752_MEASURED)
    host = entry.get("remote_host")
    if host:
        profile = profile_with_remote_host(profile, str(host))
    return profile


def build_fleet_from_config(config: dict) -> list:
    """구성대로 가짜 장치를 만든다(아직 띄우지는 않는다)."""
    defaults = config.get("defaults") or {}
    devices: list = []

    for i, raw in enumerate(config.get("devices") or []):
        entry = dict(defaults, **(raw or {}))
        family = entry.get("family")
        where = f"devices[{i}]"
        if not family:
            raise ValueError(f"{where}: family 가 없다. {list(FAMILIES)} 중 하나여야 한다")
        if family not in FAMILIES:
            raise ValueError(f"{where}: 모르는 family {family!r}. {list(FAMILIES)} 중 하나여야 한다")
        _check_keys(entry, _FAMILY_KEYS[family], where)

        count = int(entry.get("count", 1))
        if count <= 0:
            continue
        common = {"bind": str(entry.get("bind", "0.0.0.0")),
                  "verbose": int(entry.get("verbose", 1))}

        if family == "segcp":
            mac = str(entry.get("mac", "00:08:DC:FA:CE:01"))
            devices += make_segcp_fleet(
                count, _segcp_profile(entry, mac), first_mac=mac,
                port=int(entry.get("port", 50001)),
                quirks=_quirks_from(entry.get("quirks")),
                reply_broadcast=True, **common)
        elif family == "w550":
            fw = tuple(int(x) for x in str(entry.get("fw", "1.2.0")).split("."))
            model = str(entry.get("type", "WIZ550SR"))
            if model not in PRODUCT_CODES:
                raise ValueError(f"{where}: 모르는 type {model!r}. {sorted(PRODUCT_CODES)} 중 하나")
            devices += make_550_fleet(
                count, model, first_mac=str(entry.get("mac", "00:08:DC:55:00:01")),
                port=int(entry.get("port", 6550)), fw_version=fw,
                password=str(entry.get("password", "")), **common)
        else:                                   # w1x0
            devices += make_1x0_fleet(
                count, first_mac=str(entry.get("mac", "00:08:DC:1A:00:01")),
                first_ip=str(entry.get("ip", "192.168.7.60")),
                port=int(entry.get("port", 1460)),
                direct_port=int(entry.get("direct_port", 1461)),
                setc_carries_board=bool(entry.get("setc_carries_board", True)),
                **common)
    return devices


def build_fleet(*, segcp: int = 1, w550: int = 1, w1x0: int = 1,
                w550_type: str = "WIZ550SR", bind: str = "0.0.0.0",
                verbose: int = 1) -> list:
    """구성 파일 없이 기본 묶음을 만든다 (시험·스크립트용)."""
    entries = []
    if segcp:
        entries.append({"family": "segcp", "count": segcp, "port": 50001})
    if w550:
        entries.append({"family": "w550", "count": w550, "type": w550_type, "port": 6550})
    if w1x0:
        entries.append({"family": "w1x0", "count": w1x0, "port": 1460, "direct_port": 1461})
    return build_fleet_from_config({"defaults": {"bind": bind, "verbose": verbose},
                                    "devices": entries})


def _kind_of(dev) -> str:
    return type(dev).__name__.replace("Fake", "").replace("Device", "")


def _main() -> None:
    ap = argparse.ArgumentParser(description="가짜 WIZnet 장치 묶음")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                    help=f"구성 YAML (기본: {DEFAULT_CONFIG_PATH})")
    ap.add_argument("--only", choices=FAMILIES, help="한 계열만 띄운다")
    ap.add_argument("--bind", help="구성의 bind 를 덮어쓴다")
    ap.add_argument("-v", "--verbose", action="count", default=0,
                    help="구성의 verbose 를 덮어쓴다 (-vv 는 남의 요청까지)")
    args = ap.parse_args()

    try:
        config = load_fleet_config(args.config)
    except FileNotFoundError:
        raise SystemExit(f"[fake-fleet] 구성 파일이 없다: {args.config}")
    except yaml.YAMLError as e:
        raise SystemExit(f"[fake-fleet] 구성 파일을 읽지 못했다: {e}")

    if args.only:
        config = dict(config, devices=[d for d in (config.get("devices") or [])
                                       if (d or {}).get("family") == args.only])
    if args.bind or args.verbose:
        defaults = dict(config.get("defaults") or {})
        if args.bind:
            defaults["bind"] = args.bind
        if args.verbose:
            defaults["verbose"] = args.verbose
        config = dict(config, defaults=defaults)

    try:
        devices = build_fleet_from_config(config)
    except ValueError as e:
        raise SystemExit(f"[fake-fleet] 구성 오류 — {e}")

    if not devices:
        raise SystemExit("[fake-fleet] 띄울 장치가 없다. 구성의 devices 를 확인할 것")

    started = []
    try:
        for dev in devices:
            dev.start()
            started.append(dev)
    except OSError as e:
        for dev in started:
            dev.stop()
        raise SystemExit(f"[fake-fleet] 포트를 열지 못했다: {e}\n"
                         f"  같은 포트를 쓰는 가짜 장치가 이미 떠 있는지 확인할 것")

    print(f"[fake-fleet] {len(started)}대 시작  (구성: {args.config})", flush=True)
    for dev in started:
        extra = f" + tcp {dev.direct_port}" if _kind_of(dev) == "Wiz1x0" else ""
        print(f"  {_kind_of(dev):6s} {dev.mac}  udp {dev.port}{extra}", flush=True)
    print("[fake-fleet] 설정툴에서 검색하면 잡힌다. "
          "WIZ1x0 은 'WIZ1x0SR Search' 체크박스를 켜야 검색된다. (Ctrl+C 로 종료)", flush=True)
    try:
        while True:
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for dev in started:
            dev.stop()
            print(f"[fake-fleet] {dev.mac}: {dev.summary()}", flush=True)


if __name__ == "__main__":
    _main()
