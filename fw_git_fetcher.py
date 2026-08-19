"""
공개 배포처에서 펌웨어를 조회·다운로드·추출하는 유틸리티.
GUI 의존 없는 순수 로직 모듈.

배포처 종류는 family 의 source_type 으로 구분한다.
  github_release (기본) — GitHub 릴리즈 API
  docs_html               — docs.wiznet.io 제품 페이지의 Firmware 링크 파싱
                            (저장소가 비공개이거나 릴리즈가 없는 구형 제품용)
두 종류 모두 아래 형태의 release dict 로 정규화되어 이후 처리가 동일하다.
  {"tag_name", "published_at", "assets": [{"name", "browser_download_url", "size"}]}
"""
import datetime
import fnmatch
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import requests


class FWGitFetcher:
    API_BASE = "https://api.github.com"

    def __init__(self, config_path: str):
        """
        config_path: resource_path("config/fw_sources.json") 로 전달받음.
        로드 실패 시 예외를 caller로 전파.
        """
        with open(config_path, encoding="utf-8") as f:
            self._sources = json.load(f)

    def find_device(self, device_name: str):
        """
        device_name 을 name_pattern(fnmatch)으로 찾아
        (family_dict, device_dict) 반환. 없으면 (None, None).
        """
        for fam in self._sources.get("families", []):
            for dev in fam.get("devices", []):
                if fnmatch.fnmatch(device_name, dev["name_pattern"]):
                    return fam, dev
        return None, None

    def find_family_by_id(self, family_id: str):
        """
        family id로 (family_dict, device_dict) 반환. devices[0] 사용.
        없으면 (None, None).
        """
        for fam in self._sources.get("families", []):
            if fam.get("id") == family_id:
                devices = fam.get("devices", [])
                return fam, devices[0] if devices else None
        return None, None

    def find_all_devices(self, device_name: str) -> list:
        """매칭되는 모든 (family, device) 쌍 반환 — 복수 repo 지원용."""
        results = []
        for fam in self._sources.get("families", []):
            for dev in fam.get("devices", []):
                if fnmatch.fnmatch(device_name, dev["name_pattern"]):
                    results.append((fam, dev))
        return results

    def supported_devices(self) -> list:
        """경고 다이얼로그용 name_pattern 목록"""
        result = []
        for fam in self._sources.get("families", []):
            for dev in fam.get("devices", []):
                result.append(dev["name_pattern"])
        return result

    def get_releases(self, repo: str) -> list:
        """
        GitHub API /repos/{repo}/releases — 최신 20개.
        네트워크·HTTP 오류 시 예외 전파.
        """
        url = f"{self.API_BASE}/repos/{repo}/releases?per_page=20"
        resp = requests.get(
            url,
            timeout=15,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_releases_for(self, family: dict) -> list:
        """
        family 의 source_type 에 맞는 배포처에서 release 목록을 가져온다.
        source_type 이 없으면 github_release 로 간주(기존 설정 호환).
        """
        stype = family.get("source_type", "github_release")
        if stype == "github_release":
            return self.get_releases(family["repo"])
        if stype == "docs_html":
            return self._get_releases_docs_html(family)
        raise ValueError(f"Unknown source_type: {stype}")

    def _get_releases_docs_html(self, family: dict) -> list:
        """
        docs.wiznet.io 제품 페이지에서 펌웨어 zip 링크를 긁어 release 목록으로 변환.

        페이지가 최신 버전을 위에 두므로 문서 등장 순서를 그대로 유지한다.
        link_pattern(fnmatch, 파일명 기준)으로 펌웨어만 골라내고,
        exclude_asset_keywords 로 구형 묶음 파일 등을 제외한다.
        """
        docs_url = family["docs_url"]
        resp = requests.get(docs_url, timeout=15)
        resp.raise_for_status()

        link_pattern = family.get("link_pattern", "*.zip")
        exclude = [k.lower() for k in family.get("exclude_asset_keywords", [])]
        ver_re = family.get("version_regex")

        releases, seen = [], set()
        for href in re.findall(r'href=["\']([^"\']+\.zip)["\']', resp.text, re.I):
            url = urljoin(docs_url, href)
            name = os.path.basename(url)
            if name.lower() in seen:
                continue
            # 문서 페이지는 버전마다 대소문자 표기가 섞여 있어 소문자로 맞춰 비교한다
            if not fnmatch.fnmatch(name.lower(), link_pattern.lower()):
                continue
            if any(k in name.lower() for k in exclude):
                continue
            seen.add(name.lower())
            releases.append({
                "tag_name": self._docs_version_label(name, ver_re),
                "published_at": "",
                "assets": [{
                    "name": name,
                    "browser_download_url": url,
                    "size": 0,
                }],
            })
        return releases

    @staticmethod
    def _docs_version_label(filename: str, ver_re):
        """파일명에서 버전 표기를 뽑는다. 실패하면 파일명을 그대로 쓴다."""
        if ver_re:
            m = re.search(ver_re, filename, re.I)
            if m:
                return "v" + ".".join(g for g in m.groups() if g)
        return Path(filename).stem

    def find_asset(self, release: dict, device: dict, family: dict):
        """
        asset_pattern 글로브 매칭 + exclude_asset_keywords(대소문자 무시) 필터.
        반환: asset dict 또는 None.
        """
        exclude = [k.lower() for k in family.get("exclude_asset_keywords", [])]
        pattern = device["asset_pattern"]
        for asset in release.get("assets", []):
            name = asset["name"]
            if any(k in name.lower() for k in exclude):
                continue
            # 압축 없이 bin 을 그대로 쓰는 제품은 여기가 마지막 관문이라
            # 부트로더·병합본 표기를 애셋 단계에서도 본다. zip 애셋은
            # 이름에 이 표기가 없고 내부 선택에서 다시 걸러진다.
            if device.get("extract_file") is None and self.is_non_app_name(name):
                continue
            if fnmatch.fnmatch(name, pattern):
                return asset
        return None

    # 앱이 아닌 이미지(부트로더 / 부트+앱 병합본)를 가려내는 표기.
    # 제품·버전마다 앱 파일명 규칙이 달라 "앱 이름" 은 고정할 수 없다.
    #   App_main_linker / WIZ5XXSR-RP_main_linker_V108 / App_linker ...
    # 그래서 확실히 배제할 수 있는 쪽에 규칙을 건다.
    #   boot          부트로더 (Boot.bin, WIZ750SRv145_incl_boot.bin)
    #   all           관습적으로 병합본을 뜻함 (W7500x_Application_All.bin)
    #                 install/small 같은 오탐을 막으려고 토큰 경계를 요구한다
    #   merge/incl    병합본 (Boot-App_linker_Merged.bin, *_incl_boot.bin)
    # main_gui.firmware_file_open() 이 파일명에 BOOT 가 있으면 거부하는 것의 확장.
    NON_APP_PATTERNS = (
        re.compile(r"boot", re.I),
        re.compile(r"(?:^|[_\-. ])all(?:[_\-. ]|$)", re.I),
        re.compile(r"merge", re.I),
        re.compile(r"(?:^|[_\-. ])incl(?:[_\-. ]|$)", re.I),
    )

    @classmethod
    def is_non_app_name(cls, name: str) -> bool:
        """파일명만으로 '앱 이미지가 아니다' 라고 볼 수 있는지."""
        base = Path(name).name
        return any(p.search(base) for p in cls.NON_APP_PATTERNS)

    @classmethod
    def _pick_app_binary(cls, names, pattern, asset_path):
        """
        zip 안에서 글로브에 맞는 파일 중 앱 이미지 하나를 고른다.

        후보가 여럿이면 부트로더·병합본으로 보이는 것을 걸러낸다.
        그래도 하나로 좁혀지지 않으면 추측하지 않고 예외를 던진다 —
        잘못 고르면 다른 이미지를 장치에 그대로 굽게 된다.
        """
        cands = [n for n in names if fnmatch.fnmatch(Path(n).name, pattern)]
        if len(cands) > 1:
            filtered = [n for n in cands if not cls.is_non_app_name(n)]
            if filtered:
                cands = filtered
        if not cands:
            return None
        if len(cands) > 1:
            os.remove(asset_path)
            raise RuntimeError(
                "zip 안에서 펌웨어 파일을 하나로 특정하지 못했습니다: "
                + ", ".join(Path(n).name for n in cands)
            )
        return cands[0]

    def download_and_extract(
        self, asset: dict, dest_dir: str, extract_file
    ):
        """
        asset 다운로드 후 .bin 경로와 파일 크기를 (str, int) 로 반환.

        extract_file=None  → 다운로드 파일 그대로 사용
        extract_file="App_linker.bin" → zip 에서 해당 파일 추출
        extract_file="*.bin" → 글로브 매칭(버전마다 파일명이 바뀌는 구형 제품용)
        """
        os.makedirs(dest_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        asset_path = os.path.join(dest_dir, f"fwgit_{ts}_{asset['name']}")

        resp = requests.get(
            asset["browser_download_url"], stream=True, timeout=60
        )
        resp.raise_for_status()
        with open(asset_path, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)

        if extract_file is None:
            return asset_path, os.path.getsize(asset_path)

        with zipfile.ZipFile(asset_path) as zf:
            names = zf.namelist()
            if any(ch in extract_file for ch in "*?["):
                match = self._pick_app_binary(names, extract_file, asset_path)
            else:
                match = next(
                    (n for n in names if Path(n).name == extract_file), None
                )
            if match is None:
                os.remove(asset_path)
                raise FileNotFoundError(
                    f"{extract_file} not found in zip ({asset['name']})"
                )
            bin_path = os.path.join(dest_dir, f"fwgit_{ts}_{Path(match).name}")
            with zf.open(match) as src, open(bin_path, "wb") as dst:
                dst.write(src.read())

        os.remove(asset_path)   # zip 추출 후 즉시 삭제
        return bin_path, os.path.getsize(bin_path)
