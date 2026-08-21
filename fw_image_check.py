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
            return UNKNOWN, "No vector table on this MCU family - skipped"
        app_start = cfg.get("app_start")
        if app_start is None:
            return UNKNOWN, "No fw_image profile - nothing to check against"
        if len(data) < 8:
            return NOT_APP, "File is shorter than 8 bytes"

        sp = struct.unpack_from("<I", data, 0)[0]
        rst = struct.unpack_from("<I", data, 4)[0] & ~1
        where = f"SP=0x{sp:08X} ResetH=0x{rst:08X}"

        if self._stage2[0] is not None and (sp, rst) == self._stage2:
            return NOT_APP, f"{where} - starts with RP2040 stage2 (bootloader or merged image)"

        sram = cfg.get("sram")
        if sram and not (sram[0] <= sp <= sram[1]):
            return NOT_APP, f"{where} - stack pointer outside SRAM range"

        flash_end = cfg.get("flash_end")
        if rst < app_start:
            return NOT_APP, f"{where} - reset handler below APP start (0x{app_start:08X})"
        if flash_end is not None and rst > flash_end:
            return NOT_APP, f"{where} - reset handler outside flash range"
        return APP, f"{where} - APP region (0x{app_start:08X}+)"

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
                "reason": "No firmware image validation info is registered for this device.",
                "detail": (f"{name}\nWithout fw_image.profile there is no way "
                           f"to tell whether this is an APP image."),
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
                "reason": "This looks like a bootloader or a merged image.",
                "detail": f"{name}\nThe file name contains boot/all/merge/incl.",
            }

        if by_name == by_vec:
            if by_name == APP:
                return {"result": OK, "reason": "", "detail": vec_detail}
            return {
                "result": BLOCK,
                "reason": "Not an APP image. This is a bootloader or a boot+app merged image.",
                "detail": f"{name}\n{vec_detail}",
            }

        # 이름과 벡터가 어긋남 — 어느 쪽도 믿지 않는다
        return {
            "result": BLOCK,
            "reason": "File name and binary layout disagree.",
            "detail": (f"{name}\n"
                       f"By file name : {'APP' if by_name == APP else 'not APP'}\n"
                       f"By binary    : {'APP' if by_vec == APP else 'not APP'}\n"
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
