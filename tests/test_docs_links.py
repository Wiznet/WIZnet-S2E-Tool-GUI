#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개발 문서(README + doc/dev/*.md)의 무결성 자동 검증.

- 로컬 마크다운 링크 / 이미지 링크가 실제 존재하는 파일을 가리키는지 확인
- 개발 문서 시리즈(doc/dev)가 공통 "개발 문서 목차" footer를 갖는지 확인

수동 grep 검증을 대체하는 회귀 테스트. 문서를 옮기거나 링크를 고칠 때
경로가 깨지면 여기서 즉시 잡힌다.

실행: uv run pytest tests/test_docs_links.py -v
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "doc" / "dev"

# 검증 대상: 루트 README + 개발 문서 시리즈
DOC_FILES = [ROOT / "README.md"] + sorted(DEV_DIR.glob("*.md"))

# [text](url) 및 ![alt](url) 의 url 부분을 캡처 (인라인 링크 기준)
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# 로컬 파일이 아닌 링크(외부 URL / 페이지 내 앵커)는 검사 제외
_SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def _local_link_targets(md_path: Path):
    """md 파일에서 로컬 파일을 가리키는 링크 URL 목록을 추출."""
    text = md_path.read_text(encoding="utf-8")
    targets = []
    for match in _LINK_RE.finditer(text):
        url = match.group(1).strip()
        if url.startswith(_SKIP_PREFIXES):
            continue
        # 선택적 title 제거:  [t](path "title")  → path
        url = url.split()[0]
        # 앵커 제거:  path#section  → path
        url = url.split("#")[0]
        if url:
            targets.append(url)
    return targets


def test_doc_set_is_discovered():
    """검증 대상 문서가 실제로 수집됐는지 (빈 목록 방지)."""
    assert (ROOT / "README.md").exists()
    assert DEV_DIR.is_dir(), f"개발 문서 디렉토리 없음: {DEV_DIR}"
    assert len(list(DEV_DIR.glob("*.md"))) >= 1


@pytest.mark.parametrize("md_path", DOC_FILES, ids=lambda p: p.name)
def test_local_links_resolve(md_path: Path):
    """모든 로컬 마크다운/이미지 링크가 실제 파일을 가리킨다."""
    broken = []
    for url in _local_link_targets(md_path):
        target = (md_path.parent / url).resolve()
        if not target.exists():
            broken.append(url)
    assert not broken, f"{md_path.name} 의 깨진 링크: {broken}"


@pytest.mark.parametrize(
    "md_path", sorted(DEV_DIR.glob("*.md")), ids=lambda p: p.name
)
def test_dev_docs_have_toc_footer(md_path: Path):
    """개발 문서 시리즈는 모두 공통 '개발 문서 목차' footer를 갖는다."""
    text = md_path.read_text(encoding="utf-8")
    assert "개발 문서 목차" in text, f"{md_path.name} 에 '개발 문서 목차' footer 없음"
