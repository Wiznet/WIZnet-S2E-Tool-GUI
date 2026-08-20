"""
펌웨어 이미지가 해당 장치의 APP 이미지가 맞는지 검사한다.
GUI 의존 없는 순수 로직 모듈.

두 가지를 각각 판정한 뒤 대조한다.
  이름 검사  파일명의 boot / all / merge / incl 표기
  벡터 검사  ARM Cortex-M 벡터 테이블의 SP / Reset Handler 주소

둘이 어긋나면 어느 쪽도 믿지 않고 차단한다. 잘못 고르면 장치에 다른 이미지를
그대로 굽게 되고 되돌리기 어렵다.

기준값은 config/fw_image_defaults.yaml, 장치별 지정은 각 장치 YAML 의
fw_image 블록이며 개별 키가 프로파일 값을 덮어쓴다.
"""
import os
import struct

import yaml

# 판정 결과
APP = "app"
NOT_APP = "not_app"        # 부트로더 또는 부트+앱 병합본
UNKNOWN = "unknown"        # 판정 근거 없음

# 최종 결론
OK = "ok"
BLOCK = "block"


class FWImageChecker:
    def __init__(self, defaults_path: str, logger=None):
        self.logger = logger
        with open(defaults_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        self._defaults = cfg.get("defaults", {})
        self._profiles = cfg.get("profiles", {})
        sig = cfg.get("rp2040_stage2_signature", {})
        self._stage2 = (sig.get("sp"), sig.get("reset"))

    # ------------------------------------------------------------ 설정 해석

    def resolve(self, device_fw_image) -> dict:
        """
        장치 YAML 의 fw_image 블록을 기준값과 합쳐 최종 설정을 만든다.
        우선순위: 개별 키 > profile > defaults.
        fw_image 가 없으면 profile 미지정 상태를 그대로 돌려준다.
        """
        merged = dict(self._defaults)
        block = dict(device_fw_image or {})
        profile_name = block.pop("profile", None)
        if profile_name:
            merged.update(self._profiles.get(profile_name, {}))
        merged.update(block)
        merged["profile"] = profile_name
        return merged

    # ------------------------------------------------------------ 개별 판정

    @staticmethod
    def verdict_by_name(filename: str, non_app_checker) -> str:
        """파일명 표기로 본 판정. non_app_checker 는 FWGitFetcher.is_non_app_name."""
        return NOT_APP if non_app_checker(os.path.basename(filename)) else APP

    def verdict_by_vector(self, data: bytes, cfg: dict) -> tuple:
        """
        벡터 테이블로 본 판정. (verdict, 설명) 반환.
        cfg 에 app_start 가 없으면 판정하지 않는다.
        """
        if not cfg.get("vector_check", True):
            return UNKNOWN, "이 계열은 벡터 테이블이 없어 검사하지 않음"
        app_start = cfg.get("app_start")
        if app_start is None:
            return UNKNOWN, "프로파일이 지정되지 않아 검사 기준이 없음"
        if len(data) < 8:
            return NOT_APP, "파일이 8바이트 미만"

        sp = struct.unpack_from("<I", data, 0)[0]
        rst = struct.unpack_from("<I", data, 4)[0] & ~1
        where = f"SP=0x{sp:08X} ResetH=0x{rst:08X}"

        if self._stage2[0] is not None and (sp, rst) == self._stage2:
            return NOT_APP, f"{where} — RP2040 stage2 로 시작(부트로더 또는 병합본)"

        sram = cfg.get("sram")
        if sram and not (sram[0] <= sp <= sram[1]):
            return NOT_APP, f"{where} — SP 가 SRAM 범위 밖"

        flash_end = cfg.get("flash_end")
        if rst < app_start:
            return NOT_APP, f"{where} — Reset Handler 가 APP 시작(0x{app_start:08X}) 앞"
        if flash_end is not None and rst > flash_end:
            return NOT_APP, f"{where} — Reset Handler 가 플래시 범위 밖"
        return APP, f"{where} — APP 영역(0x{app_start:08X}+)"

    # ------------------------------------------------------------ 종합

    def check(self, filepath: str, device_fw_image, non_app_checker) -> dict:
        """
        업로드 전 최종 판정.
        반환: {"result": ok|block, "reason": str, "detail": str}
        """
        cfg = self.resolve(device_fw_image)
        name = os.path.basename(filepath)

        if cfg.get("vector_check", True) and cfg.get("app_start") is None:
            return {
                "result": BLOCK,
                "reason": "이 장치의 펌웨어 이미지 검증 정보가 등록되어 있지 않습니다.",
                "detail": (f"{name}\n검증 기준(fw_image.profile)이 없어 APP 이미지인지 "
                           f"확인할 수 없습니다."),
            }

        by_name = self.verdict_by_name(filepath, non_app_checker)
        by_vec, vec_detail = self.verdict_by_vector(self._read_head(filepath), cfg)
        self._log(f"{name}: name={by_name} vector={by_vec} ({vec_detail})")

        if by_vec == UNKNOWN:
            # 8051 처럼 벡터가 없는 계열 — 이름 검사 결과를 그대로 쓴다
            if by_name == APP:
                return {"result": OK, "reason": "", "detail": vec_detail}
            return {
                "result": BLOCK,
                "reason": "부트로더 또는 병합 이미지로 보입니다.",
                "detail": f"{name}\n파일명에 boot/all/merge/incl 표기가 있습니다.",
            }

        if by_name == by_vec:
            if by_name == APP:
                return {"result": OK, "reason": "", "detail": vec_detail}
            return {
                "result": BLOCK,
                "reason": "APP 이미지가 아닙니다. 부트로더 또는 부트+앱 병합본입니다.",
                "detail": f"{name}\n{vec_detail}",
            }

        # 이름과 벡터가 어긋남 — 어느 쪽도 믿지 않는다
        return {
            "result": BLOCK,
            "reason": "파일명과 바이너리 구조의 판정이 서로 다릅니다.",
            "detail": (f"{name}\n"
                       f"파일명 판정 : {'APP' if by_name == APP else 'APP 아님'}\n"
                       f"바이너리 판정: {'APP' if by_vec == APP else 'APP 아님'}\n"
                       f"{vec_detail}"),
        }

    @staticmethod
    def _read_head(path: str, n: int = 8) -> bytes:
        try:
            with open(path, "rb") as f:
                return f.read(n)
        except OSError:
            return b""

    def _log(self, msg: str):
        if self.logger:
            self.logger.info(f"[FWImageCheck] {msg}")
