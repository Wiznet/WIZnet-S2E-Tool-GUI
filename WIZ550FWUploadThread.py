#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ550FWUploadThread.py — WIZ550 TFTP 펌웨어 업로드 QThread

흐름 (auto 모드):
  1. tmpdir 생성 + FW 파일 복사
  2. tftpy.TftpServer 구동 (별도 threading.Thread)
  3. 단일 UDP 소켓 bind(0) — 에페머럴 포트
  4. 0xD1 FW_UPLOAD_INIT 전송 (같은 소켓)
  5. 0xD2 FW_UPLOAD_DONE 수신 대기 (같은 소켓, 최대 30초)
  6. 서버 stop + 정리 + finished 시그널

소켓 전략: Java 원본(DatagramSocket 랜덤포트)과 동일.
  0xD2 응답은 port 6550이 아닌 0xD1 소스포트(에페머럴)로 옴.
  _wait_d2()가 bind(0)+_send_fw_init()+수신을 단일 소켓으로 처리.
"""

import os
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


def _is_fw_done_reply(data: bytes) -> bool:
    """0xD2 FW_UPLOAD_DONE 응답 확인: STX + op=0xD2 + reply=0x55."""
    return (len(data) >= 7
            and data[0] == 0xA5
            and data[3] == 0xD2
            and data[4] == 0x55)


class WIZ550FWUploadThread(QThread):
    progress = pyqtSignal(str)   # 상태 메시지 (UI lbl_status 연결용)
    finished = pyqtSignal(bool)  # True=성공, False=실패/중단
    error    = pyqtSignal(str)   # 오류 메시지

    def __init__(self, mode: str, fw_path: str, target_ip: str, target_mac: str,
                 server_ip: str, server_port: int, password: str = "",
                 iface_ip: str = ""):
        super().__init__()
        self.mode        = mode          # 'auto' | 'manual'
        self.fw_path     = fw_path
        self.target_ip   = target_ip
        self.target_mac  = target_mac
        self.server_ip   = server_ip
        self.server_port = server_port
        self.password    = password
        self.iface_ip    = iface_ip

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
            logger.error(f"[WIZ550FW] 예외: {e}")
            self.error.emit(str(e))
            self.finished.emit(False)

    # ── auto 모드 ──────────────────────────────────────────────────

    def _run_auto(self):
        tmpdir = tempfile.mkdtemp(prefix='wiz550fw_')
        fw_filename = os.path.basename(self.fw_path)
        dst = os.path.join(tmpdir, fw_filename)
        shutil.copy2(self.fw_path, dst)

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

        self.progress.emit("Waiting for device response...")
        # _wait_d2가 소켓 생성·bind·0xD1 전송·0xD2 수신을 단일 소켓으로 처리
        success = self._wait_d2()

        self._server.stop(now=True)
        listen_thread.join(timeout=3)
        shutil.rmtree(tmpdir, ignore_errors=True)

        self.finished.emit(success)

    # ── manual 모드 ───────────────────────────────────────────────

    def _run_manual(self):
        self.progress.emit("Sending firmware upload request...")
        self.progress.emit("Waiting for device response...")
        success = self._wait_d2()
        self.finished.emit(success)

    # ── 핵심: 단일 소켓으로 전송 + 수신 ──────────────────────────

    def _send_fw_init(self):
        """self._d2_sock (이미 bind됨)으로 0xD1 전송."""
        fw_filename = os.path.basename(self.fw_path)
        pkt = build_fw_upload_pkt(
            target_mac=self.target_mac,
            server_ip=self.server_ip,
            server_port=self.server_port,
            file_name=fw_filename,
            password=self.password,
        )
        self._d2_sock.sendto(pkt, (self.target_ip, WIZ550_PORT))
        logger.info(f"[WIZ550FW] 0xD1 전송 → {self.target_ip}:{WIZ550_PORT} ({len(pkt)}B)")

    def _wait_d2(self, timeout_sec: float = 30.0) -> bool:
        """
        에페머럴 소켓 bind(0) → 0xD1 전송 → 0xD2 수신 대기.

        Java 원본과 동일: 단일 DatagramSocket으로 전송+수신.
        0xD2는 0xD1 소스포트(에페머럴)로 응답해 옴.
        bind(0) 실패는 OS 자원 고갈 등 극히 예외적 상황이나 예외처리 유지.
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

        # 0xD1 전송 — 같은 소켓의 에페머럴 소스포트로 장치 응답이 돌아옴
        try:
            self._send_fw_init()
        except Exception as e:
            self._d2_sock.close()
            self._d2_sock = None
            self.error.emit(f"0xD1 전송 실패: {e}")
            return False

        self._d2_sock.setblocking(False)
        deadline = time.time() + timeout_sec
        try:
            while not self._stop_event.is_set():
                remaining = deadline - time.time()
                if remaining <= 0:
                    logger.warning("[WIZ550FW] 0xD2 대기 타임아웃")
                    return False
                ready, _, _ = select.select([self._d2_sock], [], [], min(remaining, 1.0))
                if not ready:
                    continue
                data, addr = self._d2_sock.recvfrom(256)
                if _is_fw_done_reply(data):
                    logger.info(f"[WIZ550FW] 0xD2 수신 ← {addr}")
                    return True
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
