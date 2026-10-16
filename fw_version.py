# -*- coding: utf-8 -*-
"""펌웨어 버전 문자열의 숫자부 추출 — 버전 비교의 단일 기준.

버전 비교는 **숫자부만** 가지고 한다. `dev` / `rc` / `beta` / `A` 같은 접미사는
정식 출시 전이거나 배포 구분 표기일 뿐이고, 기능은 같은 번호의 정식판과 동일하다.
접두어(`VR2.1.0`, `v1.4.5`)와 빌드 메타(`1.2.2_custom_20260825`)도 같은 이유로 무시한다.

`packaging.version.Version(문자열)` 을 그대로 쓰면 안 된다. PEP 440 이 `dev`/`a`/`b`/`rc` 를
사전 릴리즈로 정식 해석해서 `1.1.8dev` 가 `1.1.8` 보다 작아지고(`1.4.5A` 도 `1.4.5a0` 으로
읽혀 `1.4.5` 보다 작다), 접두어가 붙은 문자열은 `InvalidVersion` 이 난다. 그러면 같은 기능을 가진
펌웨어가 `min_version` 게이트에서 조용히 막히거나(접미사), 게이트가 통째로 사라진다(접두어).

이 모듈이 세 곳이 따로 갖고 있던 파서를 하나로 모은다:
- `WIZMakeCMD._safe_version` / `version_compare` — 기능 게이트
- `device_spec_loader._parse_version` — DeviceSpec `min_version`
- `fw_boot_compat` — FW from Git 의 Boot↔App 호환 판정
"""
import re

from packaging.version import Version

_NUMERIC = re.compile(r"\d+(?:\.\d+)*")


def numeric_part(raw):
    """문자열에서 처음 나오는 `숫자(.숫자)*` 덩어리. 없으면 None."""
    if raw is None:
        return None
    m = _NUMERIC.search(str(raw))
    return m.group(0) if m else None


def parse(raw):
    """숫자부만 담은 `Version`. 숫자부가 없으면 None."""
    part = numeric_part(raw)
    return Version(part) if part is not None else None


def parse_triple(raw):
    """`(major, minor, patch)` 정수 튜플. major.minor 도 못 읽으면 None.

    patch 가 없으면 0, 4번째 이후 성분은 버린다(`1.2.2.9` → `(1, 2, 2)`).
    구간 경계 비교처럼 자릿수가 고정된 판단에 쓴다.
    """
    part = numeric_part(raw)
    if part is None:
        return None
    nums = [int(x) for x in part.split(".")]
    if len(nums) < 2:
        return None
    return tuple((nums + [0])[:3])
