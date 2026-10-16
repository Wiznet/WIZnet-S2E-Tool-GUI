# -*- coding: utf-8 -*-
"""호환표(`config/fw_compat.json`)의 원격 갱신.

exe 에 든 호환표가 기준이다. 인터넷이 되면 GitHub 의 같은 파일을 확인해서, **검증을 통과하고
revision 이 더 큰** 경우에만 사용자 폴더(`~/.wizconfig/fw_compat_cache.json`)에 저장한다.
저장된 사본은 다음번 판정부터 쓰인다(`fw_compat_rules.reload()`) — 이미 열린 화면의 판정이
도중에 바뀌지 않게 하려는 것이다.

원칙:
- 실패는 전부 조용하다. 네트워크가 없거나 느리거나 응답이 이상하면 번들 사본을 그대로 쓴다.
- 접속처는 아래 URL 하나이고 HTTPS 만 쓴다. 응답 크기에 상한이 있다.
- 되돌릴 수 없다: revision 은 올라가기만 한다. 잘못된 갱신은 더 큰 revision 으로 고쳐 올린다.
- 끌 수 있다: 설정 `fw_compat.auto_update: false` (`device_search_timing.yaml`).
"""
import json
import logging
import os
import threading
import time

import fw_compat_rules

_log = logging.getLogger(__name__)

URL = "https://raw.githubusercontent.com/Wiznet/WIZnet-S2E-Tool-GUI/master/config/fw_compat.json"
MAX_BYTES = 256 * 1024
TIMEOUT_SEC = 3.0
MIN_INTERVAL_SEC = 3600       # 이 시간 안에 이미 확인했으면 다시 묻지 않는다

# refresh() 결과 코드
UPDATED = "updated"
UNCHANGED = "unchanged"
SKIPPED = "skipped_recently_checked"
REJECTED = "rejected_invalid"
ERROR = "error"


def http_fetch(url, etag=None, timeout=TIMEOUT_SEC):
    """(상태 코드, 본문 바이트, ETag). 네트워크 오류는 예외로 올라간다."""
    if not url.startswith("https://"):
        raise ValueError(f"https 만 허용한다: {url}")
    import requests   # 늦게 불러온다 — 이 모듈을 쓰는 시험·도구가 네트워크 모듈을 끌어오지 않게

    headers = {"If-None-Match": etag} if etag else {}
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as resp:
        body = b""
        if resp.status_code == 200:
            body = resp.raw.read(MAX_BYTES + 1, decode_content=True)
        return resp.status_code, body, resp.headers.get("ETag")


def _write_cache(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)        # 반쯤 쓰인 파일이 남지 않게


def refresh(cache_path=None, fetch=http_fetch, tool_version=None, url=URL,
            now=time.time, min_interval=MIN_INTERVAL_SEC, bundled_doc=None):
    """원격을 한 번 확인한다. 결과 코드를 돌려준다(예외를 올리지 않는다)."""
    path = cache_path or fw_compat_rules.cache_path()
    try:
        meta = fw_compat_rules.read_cache_file(path) or {}
        checked_at = meta.get("checked_at")
        if min_interval and checked_at is not None and now() - checked_at < min_interval:
            return SKIPPED

        bundled = bundled_doc if bundled_doc is not None else fw_compat_rules.load_bundled()
        cached = meta.get("doc") if not fw_compat_rules.validate(meta.get("doc"), tool_version) else None
        baseline = max(
            (d.get("revision", 0) for d in (bundled, cached) if isinstance(d, dict)),
            default=0,
        )

        status, body, etag = fetch(url, meta.get("etag") if cached else None, TIMEOUT_SEC)

        if status == 304:
            meta["checked_at"] = now()
            _write_cache(path, meta)
            return UNCHANGED
        if status != 200:
            _log.info("[compat] 갱신 확인 실패: HTTP %s", status)
            return ERROR
        if len(body) > MAX_BYTES:
            _log.warning("[compat] 원격 호환표가 너무 크다(%d바이트 초과) — 무시", MAX_BYTES)
            return REJECTED

        try:
            doc = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            _log.warning("[compat] 원격 호환표를 읽지 못함 — 무시: %s", e)
            return REJECTED
        errors = fw_compat_rules.validate(doc, tool_version)
        if errors:
            _log.warning("[compat] 원격 호환표가 올바르지 않아 무시: %s", errors)
            return REJECTED

        if doc["revision"] <= baseline:
            # 새 것이 없다는 사실도 기록해 두어, 재시작마다 다시 묻지 않게 한다
            keep = {"doc": meta["doc"], "etag": etag or meta.get("etag")} if cached is not None else {}
            _write_cache(path, {**keep, "checked_at": now()})
            return UNCHANGED

        _write_cache(path, {"doc": doc, "etag": etag, "checked_at": now(), "url": url})
        _log.info("[compat] 호환표 갱신 저장: rev %s (이전 %s) — 다음 판정부터 적용", doc["revision"], baseline)
        return UPDATED
    except Exception as e:      # 네트워크·파일 어떤 실패도 툴 동작을 막지 않는다
        _log.info("[compat] 호환표 갱신 확인을 건너뜀: %s", e)
        return ERROR


def refresh_in_background(tool_version=None, on_done=None, **kwargs):
    """백그라운드 스레드로 refresh() 를 돌린다. 스레드 객체를 돌려준다(시험용)."""
    def _run():
        result = refresh(tool_version=tool_version, **kwargs)
        if on_done:
            on_done(result)

    t = threading.Thread(target=_run, name="fw-compat-refresh", daemon=True)
    t.start()
    return t
