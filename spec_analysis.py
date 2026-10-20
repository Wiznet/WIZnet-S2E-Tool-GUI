#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스펙(DeviceSpec)만 보고 계산할 수 있는 것 — 장치·화면·네트워크와 무관한 순수 함수.

설계: doc/dev/DESIGN-spec-driven-verification-ko.md (A1, C-1~C-3).

여기서 "코드가 확인해도 충분한 것"만 다룬다. 펌웨어가 실제로 그 한도를 지키는지,
스펙의 버퍼 크기가 맞는지는 코드로 알 수 없다(사람 확인, H-1). 그래서 모든 계산은
"스펙이 말하는 값 기준"이고, 모르는 것은 None 으로 돌려 **추정하지 않는다**.
"""

import re
from dataclasses import dataclass

try:  # 비공개 API — 파이썬 버전이 바뀌면 깨질 수 있어 한 곳에 가둔다
    from re import _parser as _re_parser  # Python 3.11+
except ImportError:  # pragma: no cover - 프로젝트는 3.12 고정
    import sre_parse as _re_parser

# 응답 한 줄 = 명령 2자 + 값 + CRLF, 응답 머리(MC 등 고정부)는 15B.
# 752 계열 실측 5점과 오차 0 으로 맞춘 모델(tests/fake_segcp_device.py 와 같은 가정).
REPLY_HEADER_BYTES = 15
REPLY_LINE_OVERHEAD = 4

# 정규식에서 상한 없는 반복(`*`, `+`, `{n,}`)은 getwidth() 가 이 값 이상으로 돌려준다.
_UNBOUNDED = getattr(_re_parser, "MAXREPEAT", 2 ** 32 - 1)


def max_width(pattern):
    """정규식이 받아들이는 문자열의 최대 길이. 상한이 없거나 계산 못 하면 None.

    `re.match` 로 쓰이므로(앞에서부터 일치) `$` 가 없으면 뒤는 무엇이든 붙을 수 있다 —
    그 경우도 None 이다. 길이 상한은 `^.{0,N}$` 처럼 양끝이 고정된 것만 인정한다.
    """
    if not pattern:
        return None
    if not (pattern.startswith("^") and pattern.endswith("$")):
        return None
    try:
        hi = _re_parser.parse(pattern).getwidth()[1]
    except (re.error, RecursionError, OverflowError):
        return None
    return None if hi >= _UNBOUNDED else int(hi)


def entry_max_len(entry):
    """CmdEntry 값의 최대 길이. 모르면 None.

    values 가 있으면 가능한 값 중 가장 긴 키, 없으면 정규식 폭.
    """
    if entry is None:
        return None
    if entry.values:
        return max(len(k) for k in entry.values)
    return max_width(entry.regex)


def entry_min_len(entry):
    """CmdEntry 값의 최소 길이(공장 기본 상태에 가까운 하한). 모르면 0."""
    if entry is not None and entry.values:
        return min(len(k) for k in entry.values)
    return 0


@dataclass
class ReplyEstimate:
    """명령 묶음에 대한 응답 크기 추정. 단위는 바이트."""
    minimum: int
    maximum: int
    unbounded: list   # 최대 길이를 알 수 없어 maximum 에 0 으로 들어간 명령


def worst_case_reply_size(spec, cmds=None):
    """`cmds`(기본: 조회 목록)에 대한 응답 크기의 [하한, 상한].

    길이를 모르는 명령은 상한 계산에서 값 0 으로 두고 `unbounded` 에 따로 적는다 —
    즉 `maximum` 은 "알려진 것만의 상한"이지 안전 보증이 아니다. 호출자는 `unbounded`
    가 비어 있을 때만 상한을 신뢰해야 한다.
    """
    cmds = list(spec.search_cmd_list if cmds is None else cmds)
    lo = hi = REPLY_HEADER_BYTES
    unbounded = []
    for c in cmds:
        entry = spec.cmdset.get(c)
        mx = entry_max_len(entry)
        if mx is None:
            unbounded.append(c)
            mx = 0
        lo += REPLY_LINE_OVERHEAD + entry_min_len(entry)
        hi += REPLY_LINE_OVERHEAD + mx
    return ReplyEstimate(minimum=lo, maximum=hi, unbounded=unbounded)


def missing_tail(requested, answered):
    """요청한 조회(GET) 명령 중 응답에서 **끝에서부터 이어서** 빠진 명령 목록.

    절단과 앞 명령의 오류는 둘 다 뒤쪽 GET 을 통째로 지우므로 빠진 것이 끝에 붙어 있다.
    중간에만 빠진 명령은 그 기종이 원래 답하지 않는 명령일 가능성이 높아 세지 않는다.
    값이 빈 응답(`PI` 만 오거나 공백 한 칸)은 답한 것이다 — `answered` 에 키가 있으면 된다.
    """
    out = []
    for cmd in reversed(list(requested)):
        if cmd in answered:
            break
        out.append(cmd)
    out.reverse()
    return out


@dataclass
class Finding:
    level: str      # "error" | "warn" | "info"
    code: str
    message: str
    cmds: tuple = ()


def audit_spec(spec):
    """스펙 하나의 점검 목록. 사람이 채워야 할 빈칸을 드러내는 것이 목적이다."""
    out = []
    est = worst_case_reply_size(spec)
    buf = spec.fw_config.config_buf_size

    if not buf:
        out.append(Finding(
            "warn", "NO_BUF_SIZE",
            "fw_constraints.config_buf_size 미기재 — 응답 크기 판정을 하지 않는다(사람 확인 H-1)."))
    elif est.unbounded:
        out.append(Finding(
            "info", "SIZE_PARTIAL",
            f"길이를 모르는 명령 {len(est.unbounded)}개 — 상한 {est.maximum}B 는 안전 보증이 아니다.",
            tuple(est.unbounded)))
    elif est.maximum > buf:
        out.append(Finding(
            "error", "SIZE_OVER",
            f"스펙상 최악 응답 {est.maximum}B > 버퍼 {buf}B.", ()))
    else:
        out.append(Finding(
            "info", "SIZE_OK",
            f"스펙상 최악 응답 {est.maximum}B ≤ 버퍼 {buf}B (여유 {buf - est.maximum}B)."))

    missing = [c for c in spec.search_cmd_list if c not in spec.cmdset]
    if missing:
        out.append(Finding("error", "SEARCH_CMD_UNDEFINED",
                           "조회 목록에 있으나 스펙에 정의 없는 명령.", tuple(missing)))

    # 쓸 수 있는 문자열 명령 중 길이를 모르는 것 — 길이 사고(NP/PI/PP 류)의 후보
    writable_unknown = [
        c for c, e in spec.cmdset.items()
        if e.is_writable() and not e.values and entry_max_len(e) is None]
    if writable_unknown:
        out.append(Finding(
            "warn", "WRITABLE_LEN_UNKNOWN",
            "쓰기 가능한데 길이 상한을 스펙에서 알 수 없는 명령(사람 확인 H-3).",
            tuple(sorted(writable_unknown))))
    return out
