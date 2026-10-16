#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boot/App 호환표(`config/fw_compat.json`)의 `known_max` 가 낡았는지 확인한다.

각 family 의 펌웨어 저장소에서 최신 릴리즈를 읽어, 호환표가 확인한 최신 버전(`known_max`)보다 새로우면
사람이 호환표를 확인해야 한다고 알린다. `known_max` 를 자동으로 올리지는 않는다 — 검증되지 않은 버전이
"알려진 버전"이 되면 안전장치가 사라지기 때문이다.

GitHub Actions(`.github/workflows/fw-compat-watch.yml`)가 주기적으로 실행해 이슈를 연다.
로컬에서: python .github/scripts/check_compat_table.py [--out report.md]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fw_version import parse_triple  # noqa: E402

COMPAT = os.path.join(ROOT, "config", "fw_compat.json")
SOURCES = os.path.join(ROOT, "config", "fw_sources.json")


def find_stale(compat_doc, sources_doc, latest_by_repo):
    """호환표가 아직 확인하지 못한 새 릴리즈 목록.

    latest_by_repo: {저장소: 최신 릴리즈 태그}. 태그를 모르거나 읽을 수 없는 family 는 건너뛴다.
    반환: [{"family", "repo", "latest", "known_max", "revision"}]
    """
    repos = {f.get("id"): f.get("repo") for f in sources_doc.get("families", [])}
    stale = []
    for family_id, rule in (compat_doc.get("families") or {}).items():
        repo = repos.get(family_id)
        latest = latest_by_repo.get(repo) if repo else None
        latest_v = parse_triple(latest)
        known_v = parse_triple(rule.get("known_max"))
        if latest_v is None or known_v is None:
            continue
        if latest_v > known_v:
            stale.append({
                "family": family_id, "repo": repo, "latest": latest,
                "known_max": rule.get("known_max"), "revision": compat_doc.get("revision"),
            })
    return stale


def render_title(stale):
    names = ", ".join(f"{s['family']} {s['latest']}" for s in stale)
    return f"FW compatibility table needs review: {names}"


def render_report(stale):
    lines = [
        "A newer firmware release exists than the Boot/App compatibility table has verified.",
        "",
        "| Family | Latest release | Table verified up to | Table revision |",
        "| --- | --- | --- | --- |",
    ]
    for s in stale:
        lines.append(f"| `{s['family']}` ([{s['repo']}](https://github.com/{s['repo']}/releases)) "
                     f"| `{s['latest']}` | `{s['known_max']}` | {s['revision']} |")
    lines += [
        "",
        "Until the table is updated, the tool does not block these versions; it marks them "
        "`[Check Boot]` and says the version is newer than the table.",
        "",
        "To resolve:",
        "",
        "1. Check whether the new release changes the Boot/App interface "
        "(for example the interrupt remap address, as happened in v1.3.3).",
        "2. Edit `config/fw_compat.json`: update `known_max` (and `epochs` / `transitions` if the "
        "compatibility changed), bump `revision`, set `updated`.",
        "3. Merge to `master`. Running tools pick up the higher `revision` automatically.",
        "",
        "`known_max` is intentionally never raised automatically.",
    ]
    return "\n".join(lines) + "\n"


def fetch_latest(repo, token=None):
    """저장소의 최신 정식 릴리즈 태그. 못 읽으면 None."""
    import requests

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(f"https://api.github.com/repos/{repo}/releases/latest",
                        headers=headers, timeout=15)
    if resp.status_code != 200:
        print(f"[warn] {repo}: HTTP {resp.status_code}", file=sys.stderr)
        return None
    return resp.json().get("tag_name")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="보고서(마크다운)를 쓸 파일")
    args = ap.parse_args(argv)

    with open(COMPAT, encoding="utf-8") as f:
        compat = json.load(f)
    with open(SOURCES, encoding="utf-8") as f:
        sources = json.load(f)

    token = os.environ.get("GITHUB_TOKEN")
    repos = {f.get("repo") for f in sources.get("families", []) if f.get("id") in (compat.get("families") or {})}
    latest = {repo: fetch_latest(repo, token) for repo in sorted(r for r in repos if r)}
    stale = find_stale(compat, sources, latest)

    if stale:
        report = render_report(stale)
        print(report)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(report)
    else:
        print("Compatibility table is up to date with the latest releases:", latest)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"stale={'true' if stale else 'false'}\n")
            if stale:
                f.write(f"title={render_title(stale)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
