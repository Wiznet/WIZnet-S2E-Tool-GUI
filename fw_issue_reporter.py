"""
FW from Git 이 지원하지 않는 장치를 만났을 때 이슈로 남기는 유틸리티.
GUI 의존 없는 순수 로직 모듈.

동작 규칙
  1. 같은 장치에 대한 이슈를 먼저 검색한다.
  2. open 이슈가 있으면        -> 댓글로 발생 사실만 덧붙인다.
  3. closed 이슈만 있으면      -> 아무것도 하지 않는다. (이미 처리된 건)
  4. 아무것도 없으면           -> 새 이슈를 등록한다.

인증
  이슈 검색은 익명으로 가능하지만 등록·댓글은 토큰이 필요하다.
  gh CLI 가 인증된 상태면 그것으로 처리하고, 없으면 내용이 채워진
  GitHub 페이지 URL 을 돌려줘서 사용자가 직접 제출하도록 한다.
"""
import os
import platform
import shutil
import subprocess
from urllib.parse import quote

import requests

TITLE_PREFIX = "[FW from Git] Unsupported device"

# 결과 action 값
ACT_CREATED = "created"          # 새 이슈 등록됨
ACT_COMMENTED = "commented"      # 기존 open 이슈에 댓글 추가
ACT_SKIPPED_CLOSED = "skipped"   # closed 이슈가 있어 아무것도 안 함
ACT_MANUAL = "manual"            # 토큰 없음 -> 사용자가 브라우저로 제출
ACT_ERROR = "error"


class FWIssueReporter:
    API_BASE = "https://api.github.com"

    def __init__(self, repo: str, tool_version: str = "", logger=None):
        self.repo = repo
        self.tool_version = tool_version
        self.logger = logger

    # ------------------------------------------------------------------ 공개 API

    def report_unsupported(self, device_name: str, fw_version: str = "") -> dict:
        """
        미지원 장치 1건을 보고한다. 네트워크·인증 실패는 예외로 던지지 않고
        action=error 로 돌려준다. 설정 툴 본류 동작을 막지 않기 위함이다.
        """
        title = f"{TITLE_PREFIX}: {device_name}"
        body = self._build_body(device_name, fw_version)

        try:
            existing = self._search_issue(title)
        except Exception as e:
            self._log(f"issue search failed: {e}")
            return self._manual(title, body, reason="issue search failed")

        if existing and existing["state"] == "closed":
            return {
                "action": ACT_SKIPPED_CLOSED,
                "url": existing["html_url"],
                "message": "A closed issue already covers this - nothing reported.",
            }

        gh = self._gh_path()
        if not gh:
            return self._manual(title, body, existing=existing)

        try:
            if existing:
                self._gh(gh, ["issue", "comment", str(existing["number"]),
                              "--repo", self.repo, "--body", self._comment_body()])
                return {
                    "action": ACT_COMMENTED,
                    "url": existing["html_url"],
                    "message": "Added a comment to the existing issue.",
                }
            url = self._gh(gh, ["issue", "create", "--repo", self.repo,
                                "--title", title, "--body", body]).strip()
            return {
                "action": ACT_CREATED,
                "url": url,
                "message": "Reported a new issue.",
            }
        except Exception as e:
            self._log(f"issue write failed: {e}")
            return self._manual(title, body, existing=existing, reason=str(e))

    # ------------------------------------------------------------------ 내부

    def _search_issue(self, title: str):
        """
        제목이 정확히 일치하는 이슈를 찾는다. open 을 우선 반환하고,
        없으면 closed 를 반환한다. 하나도 없으면 None.
        """
        q = f'repo:{self.repo} is:issue in:title "{TITLE_PREFIX}"'
        resp = requests.get(
            f"{self.API_BASE}/search/issues",
            params={"q": q, "per_page": 100},
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        resp.raise_for_status()
        items = [i for i in resp.json().get("items", [])
                 if i.get("title", "").strip() == title]
        if not items:
            return None
        for i in items:
            if i.get("state") == "open":
                return i
        return items[0]

    def _build_body(self, device_name: str, fw_version: str) -> str:
        return (
            f"A device with no firmware source information was found in "
            f"`FW from Git`.\n\n"
            f"| Item | Value |\n| --- | --- |\n"
            f"| Device | `{device_name}` |\n"
            f"| Device FW | `{fw_version or '-'}` |\n"
            f"| Config Tool | `{self.tool_version or '-'}` |\n"
            f"| OS | `{platform.system()} {platform.release()}` |\n\n"
            f"`config/fw_sources.json` has no firmware source for this device, "
            f"so the download was stopped instead of guessing one.\n\n"
            f"Information needed to register it:\n"
            f"- Firmware source (repository releases or a documentation page)\n"
            f"- Asset file name pattern\n"
            f"- For archives, the binary file name to extract\n"
        )

    def _comment_body(self) -> str:
        return (
            f"Seen again. "
            f"(Config Tool `{self.tool_version or '-'}`, "
            f"{platform.system()} {platform.release()})"
        )

    def _manual(self, title: str, body: str, existing=None, reason: str = "") -> dict:
        """토큰이 없거나 API 쓰기에 실패했을 때 사용자가 직접 제출할 URL 을 만든다."""
        if existing:
            url = existing["html_url"]
            msg = "An issue already exists. Opening it in your browser."
        else:
            url = (f"https://github.com/{self.repo}/issues/new"
                   f"?title={quote(title)}&body={quote(body)}")
            msg = "Opening the GitHub issue form - please review and submit."
        if reason:
            msg += f" ({reason})"
        return {"action": ACT_MANUAL, "url": url, "message": msg}

    @staticmethod
    def _gh_path():
        """PATH 또는 GH_PATH 환경변수에서 인증된 gh CLI 를 찾는다. 없으면 None."""
        gh = os.environ.get("GH_PATH") or shutil.which("gh")
        if not gh or not os.path.isfile(gh):
            return None
        try:
            r = subprocess.run([gh, "auth", "status"], capture_output=True,
                               timeout=10, text=True,
                               encoding="utf-8", errors="replace")
            return gh if r.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _gh(gh: str, args: list) -> str:
        r = subprocess.run([gh] + args, capture_output=True, timeout=30,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "gh command failed")
        return r.stdout

    def _log(self, msg: str):
        if self.logger:
            self.logger.warning(f"[FWIssueReporter] {msg}")
