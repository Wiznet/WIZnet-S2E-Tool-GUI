#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TASK-W55RP20-CH4-ABSORB 6단계 — fw_sources.json 의 3CH/4CH 처리.

merge-risk 조사(2026-08-12)가 지적한 갭: `name_pattern`이 정확 일치(fnmatch,
와일드카드 없음)라 `W55RP20-S2E-3CH`/`-4CH`는 어떤 항목에도 안 걸려 "FW from Git"
다이얼로그가 이유 없이 미지원으로만 뜬다. `gh release view`로 실제 릴리즈
(v1.2.2/v1.2.3) 애셋을 확인한 결과 3CH/4CH 전용 이미지가 없음을 확인
(2026-09-28) — 2CH 와 같은 패턴으로 `unsupported`에 명시적으로 등재해
사유를 안내한다.
"""
from fw_git_fetcher import FWGitFetcher

CONFIG = "config/fw_sources.json"


def test_3ch_4ch_not_matched_as_base_w55rp20():
    """3CH/4CH 가 base 'W55RP20-S2E' name_pattern 에 잘못 걸려서
    (베이스 이미지를 잘못 권하는 것을) 방지 — fnmatch 정확 일치라 원래도
    안 걸리지만, 회귀 감시로 고정."""
    fetcher = FWGitFetcher(CONFIG)
    for dev in ("W55RP20-S2E-3CH", "W55RP20-S2E-4CH"):
        fam, entry = fetcher.find_device(dev)
        assert fam is None and entry is None, (
            f"{dev} 가 {entry!r} 에 매칭됨 — 3CH/4CH 전용 릴리즈 없이 베이스 이미지를 권할 위험"
        )


def test_3ch_4ch_marked_unsupported_with_reason():
    """미지원 이유가 명시돼 있어야 한다(이유 없는 침묵은 이슈 등록을 유도해 헛수고가 된다)."""
    fetcher = FWGitFetcher(CONFIG)
    for dev in ("W55RP20-S2E-3CH", "W55RP20-S2E-4CH"):
        reason = fetcher.find_unsupported(dev)
        assert reason, f"{dev}: unsupported 사유가 비어 있음"


def test_2ch_still_unsupported_unaffected():
    """3CH/4CH 항목 추가가 기존 2CH 처리를 건드리지 않았는지."""
    fetcher = FWGitFetcher(CONFIG)
    assert fetcher.find_unsupported("W55RP20-S2E-2CH")
