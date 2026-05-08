"""
GitHub 릴리즈에서 펌웨어를 조회·다운로드·추출하는 유틸리티.
GUI 의존 없는 순수 로직 모듈.
"""
import datetime
import fnmatch
import json
import os
import zipfile
from pathlib import Path

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
            if fnmatch.fnmatch(name, pattern):
                return asset
        return None

    def download_and_extract(
        self, asset: dict, dest_dir: str, extract_file
    ):
        """
        asset 다운로드 후 .bin 경로와 파일 크기를 (str, int) 로 반환.

        extract_file=None  → 다운로드 파일 그대로 사용
        extract_file="App_linker.bin" → zip 에서 해당 파일 추출
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
            match = next(
                (n for n in names if Path(n).name == extract_file), None
            )
            if match is None:
                os.remove(asset_path)
                raise FileNotFoundError(
                    f"{extract_file} not found in zip ({asset['name']})"
                )
            bin_path = os.path.join(dest_dir, f"fwgit_{ts}_{extract_file}")
            with zf.open(match) as src, open(bin_path, "wb") as dst:
                dst.write(src.read())

        os.remove(asset_path)   # zip 추출 후 즉시 삭제
        return bin_path, os.path.getsize(bin_path)
