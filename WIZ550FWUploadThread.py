#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550FWUploadThread.py — WIZ550 TFTP 펌웨어 업로드 QThread

흐름 (auto 모드):
  1. tmpdir 생성 + FW 파일 복사 (원본명 + canonical명 둘 다)
  2. tftpy.TftpServer 구동 (별도 threading.Thread)
  3. 단일 UDP 소켓 bind(0) — 에페머럴 포트
  4. 0xD1 FW_UPLOAD_INIT 전송 (같은 소켓)
  5. 0xD2 FW_UPLOAD_DONE 수신 대기 (같은 소켓, 최대 30초)
  6. 서버 stop + 정리 + finished 시그널

소켓 전략: Java 원본(DatagramSocket 랜덤포트)과 동일.
  0xD2 응답은 port 6550이 아닌 0xD1 소스포트(에페머럴)로 옴.
  _wait_d2()가 bind(0)+_send_fw_init()+수신을 단일 소켓으로 처리.

파일명 전략:
  FW from Git 다운로드 파일은 "fwgit_YYYYMMDD_HHMMSS_<canonical>.bin" 형식.
  장치 펌웨어가 TFTP GET 시 canonical 이름을 하드코딩할 수 있으므로
  tmpdir에 원본명과 canonical 이름 둘 다 복사해 TFTP 서버에 노출.
"""

import logging
import os
import re
import select
import shutil
import socket
import tempfile
import threading
import time

import tftpy
from PyQt5.QtCore import QThread, pyqtSignal

from WIZ550MSGHandler import build_fw_upload_pkt, WIZ550_PORT
from utils import logger

# tftpy 내부 로그를 같은 레벨로 연결
_tftpy_log = logging.getLogger('tftpy')
_tftpy_log.setLevel(logging.DEBUG)
for _h in logger.handlers:
    _tftpy_log.addHandler(_h)


def _is_fw_done_reply(data: bytes) -> bool:
    """0xD2 FW_UPLOAD_DONE 응답 확인: STX + op=0xD2 + reply=0x55."""
    return (len(data) >= 7
            and data[0] == 0xA5
            and data[3] == 0xD2
            and data[4] == 0x55)


def _canonical_name(fw_filename: str) -> str | None:
    """
    "fwgit_YYYYMMDD_HHMMSS_<name>" → "<name>" 반환.
    패턴 불일치 시 None.
    """
    m = re.match(r'^fwgit_\d{8}_\d{6}_(.+)$', fw_filename)
    return m.group(1) if m else None


class WIZ550FWUploadThread(QThread):
    progress = pyqtSignal(str)   # 상태 메시지 (UI lbl_status 연결용)
    finished = pyqtSignal(bool)  # True=성공, False=실패/중단
    error    = pyqtSignal(str)   # 오류 메시지

    def __init__(self, mode: str, fw_path: str, target_ip: str, target_mac: str,
                 server_ip: str, server_port: int, password: str = "",
                 iface_ip: str = "", tftp_fname: str = ""):
        super().__init__()
        self.mode        = mode          # 'auto' | 'manual'
        self.fw_path     = fw_path
        self.target_ip   = target_ip
        self.target_mac  = target_mac
        self.server_ip   = server_ip
        self.server_port = server_port
        self.password    = password
        self.iface_ip    = iface_ip
        # manual 모드: 다이얼로그에서 입력한 TFTP 파일명
        # auto 모드: _run_auto()에서 canonical 이름으로 덮어씀
        self._tftp_fname = tftp_fname

        self._stop_event = threading.Event()
        self._server     = None     # tftpy.TftpServer 인스턴스
        self._d2_sock    = None     # 0xD1 전송 + 0xD2 수신 공용 소켓

    def run(self):
        try:
            if self.mode == 'auto':
                self._run_auto()
            else:
                self._run_manual()
        except Exception as e:
            logger.error(f"[WIZ550FW] 예외: {e}", exc_info=True)
            self.error.emit(str(e))
            self.finished.emit(False)

    # ── auto 모드 ──────────────────────────────────────────────────

    def _run_auto(self):
        fw_filename = os.path.basename(self.fw_path)
        canonical   = _canonical_name(fw_filename)

        tmpdir = tempfile.mkdtemp(prefix='wiz550fw_')
        logger.debug(f"[WIZ550FW] tmpdir: {tmpdir}")

        # 원본명으로 복사
        shutil.copy2(self.fw_path, os.path.join(tmpdir, fw_filename))
        logger.debug(f"[WIZ550FW] TFTP serving: {fw_filename}")

        # canonical 이름으로도 복사 (장치가 파일명 하드코딩 시 대비)
        if canonical and canonical != fw_filename:
            shutil.copy2(self.fw_path, os.path.join(tmpdir, canonical))
            logger.debug(f"[WIZ550FW] TFTP also serving as: {canonical}")

        try:
            self._server = tftpy.TftpServer(tftproot=tmpdir)
        except Exception as e:
            self.error.emit(f"TFTP 서버 초기화 실패: {e}")
            self.finished.emit(False)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return

        listen_thread = threading.Thread(
            target=self._server.listen,
            args=(self.server_ip, self.server_port),
            daemon=True,
            name="tftpy-listen",
        )
        try:
            listen_thread.start()
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return

        # 서버 시작 대기 — is_running Event로 확인
        if not self._server.is_running.wait(timeout=3.0):
            if not listen_thread.is_alive():
                self.error.emit(
                    "Port 69 requires Administrator privileges. "
                    "Please use the manual tab with an external TFTP server."
                )
            else:
                self.error.emit("TFTP 서버 시작 타임아웃")
            self.finished.emit(False)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return

        logger.info(
            f"[WIZ550FW] TFTP 서버 기동 완료 — "
            f"{self.server_ip or '0.0.0.0'}:{self.server_port}"
        )
        self.progress.emit(
            f"TFTP server ready ({self.server_ip or '0.0.0.0'}:{self.server_port})"
        )

        self.progress.emit("Sending firmware upload request...")
        # _wait_d2가 소켓 생성·bind·0xD1 전송·0xD2 수신을 단일 소켓으로 처리
        success = self._wait_d2()

        self._server.stop(now=True)
        listen_thread.join(timeout=3)
        shutil.rmtree(tmpdir, ignore_errors=True)

        self.finished.emit(success)

    # ── manual 모드 ───────────────────────────────────────────────

    def _run_manual(self):
        self.progress.emit("Sending firmware upload request...")
        success = self._wait_d2()
        self.finished.emit(success)

    # ── 핵심: 단일 소켓으로 전송 + 수신 ──────────────────────────

    def _send_fw_init(self):
        """self._d2_sock (이미 bind됨)으로 0xD1 전송."""
        if self.mode == 'auto':
            fw_filename = os.path.basename(self.fw_path)
        else:
            # manual 모드: 다이얼로그에서 입력한 파일명
            fw_filename = getattr(self, '_manual_fname', '')

        pkt = build_fw_upload_pkt(
            target_mac=self.target_mac,
            server_ip=self.server_ip,
            server_port=self.server_port,
            file_name=fw_filename,
            password=self.password,
        )
        local_port = self._d2_sock.getsockname()[1]
        logger.info(
            f"[WIZ550FW] 0xD1 전송 → {self.target_ip}:{WIZ550_PORT} "
            f"src_port={local_port} ({len(pkt)}B)"
        )
        logger.debug(
            f"[WIZ550FW] 0xD1 상세: server={self.server_ip}:{self.server_port} "
            f"file='{fw_filename}' mac={self.target_mac} pw_len={len(self.password)}"
        )
        self._d2_sock.sendto(pkt, (self.target_ip, WIZ550_PORT))

    def _wait_d2(self, timeout_sec: float = 30.0) -> bool:
        """
        에페머럴 소켓 bind(0) → 0xD1 전송 → 0xD2 수신 대기.

        Java 원본과 동일: 단일 DatagramSocket으로 전송+수신.
        0xD2는 0xD1 소스포트(에페머럴)로 응답해 옴.
        """
        self._d2_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._d2_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._d2_sock.bind(('', 0))
        except OSError as e:
            self._d2_sock.close()
            self._d2_sock = None
            self.error.emit(
                f"Socket bind failed entirely — cannot receive device response: {e}"
            )
            return False

        local_addr = self._d2_sock.getsockname()
        logger.debug(f"[WIZ550FW] D2 소켓 bind 완료: {local_addr}")

        # 0xD1 전송 — 같은 소켓의 에페머럴 소스포트로 장치 응답이 돌아옴
        try:
            self._send_fw_init()
        except Exception as e:
            self._d2_sock.close()
            self._d2_sock = None
            self.error.emit(f"0xD1 전송 실패: {e}")
            return False

        self.progress.emit("Waiting for device response...")
        logger.info(f"[WIZ550FW] 0xD2 대기 시작 (최대 {timeout_sec}초)")

        self._d2_sock.setblocking(False)
        deadline = time.time() + timeout_sec
        pkt_count = 0
        try:
            while not self._stop_event.is_set():
                remaining = deadline - time.time()
                if remaining <= 0:
                    logger.warning(
                        f"[WIZ550FW] 0xD2 대기 타임아웃 (수신된 패킷 {pkt_count}개)"
                    )
                    return False
                ready, _, _ = select.select([self._d2_sock], [], [], min(remaining, 1.0))
                if not ready:
                    continue
                data, addr = self._d2_sock.recvfrom(512)
                pkt_count += 1
                hex_head = data[:8].hex(' ') if len(data) >= 8 else data.hex(' ')
                logger.debug(
                    f"[WIZ550FW] UDP 수신 #{pkt_count} ← {addr} "
                    f"len={len(data)} head=[{hex_head}]"
                )
                if _is_fw_done_reply(data):
                    logger.info(f"[WIZ550FW] 0xD2 (FW_UPLOAD_DONE) 수신 ← {addr}")
                    self.progress.emit("Device acknowledged upload complete")
                    return True
                else:
                    logger.debug(
                        f"[WIZ550FW] 0xD2 아님 — op=0x{data[3]:02X} "
                        f"reply=0x{data[4]:02X} (무시)"
                        if len(data) >= 5 else
                        f"[WIZ550FW] 짧은 패킷 {len(data)}B (무시)"
                    )
        finally:
            self._d2_sock.close()
            self._d2_sock = None
        return False

    # ── 외부 중단 ─────────────────────────────────────────────────

    def stop(self):
        """다이얼로그 'Stop Upload' 버튼에서 호출."""
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.stop(now=True)
            except Exception:
                pass
