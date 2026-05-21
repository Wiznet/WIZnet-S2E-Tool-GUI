#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wiz550_fw_dialog.py — WIZ550 TFTP FW 업로드 다이얼로그

D-01: 탭 2개 구조 (자동/수동)
D-02: 포트 69 바인딩 실패 시 오류 메시지 후 중단
D-03: 수동 탭 서버 IP = NIC IP 자동채움
D-04: pw 입력 필드 optional
D-07: QProgressBar indeterminate → 완료 100%
UI-SPEC: fw_git_dialog.py 패턴 계승
"""

import os
import socket

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QWidget, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFrame,
    QFileDialog, QMessageBox,
)

from WIZ550FWUploadThread import WIZ550FWUploadThread
from utils import logger


def _is_boot_file(filename: str) -> bool:
    """파일명에 'BOOT' 포함 시 True (대소문자 무관)."""
    return 'BOOT' in os.path.basename(filename).upper()


class WIZ550FWDialog(QDialog):
    def __init__(self, localip_addr: str = "",
                 target_ip: str = "",
                 target_mac: str = "",
                 parent=None):
        super().__init__(parent)
        self._localip_addr  = localip_addr
        self._target_ip     = target_ip
        self._target_mac    = target_mac
        self._upload_thread = None
        self._fw_path       = ""
        self._build_ui()
        self._connect_signals()

    # ── UI 구성 ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("WIZ550 FW Upload")
        self.setFixedWidth(480)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        self.tab_widget = QTabWidget()
        root.addWidget(self.tab_widget)

        self._build_auto_tab()
        self._build_manual_tab()

        self.lbl_status = QLabel("")
        self.lbl_status.setFixedHeight(20)
        root.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_upload = QPushButton("Upload")
        self.btn_upload.setDefault(True)
        self.btn_upload.setFixedWidth(90)
        self.btn_upload.setStyleSheet("""
            QPushButton {
                background-color: #cc785c;
                color: white;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #a9583e;
            }
            QPushButton:disabled {
                background-color: #e6dfd8;
                color: #6c6a64;
            }
        """)
        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.setFixedWidth(90)

        btn_row.addWidget(self.btn_upload)
        btn_row.addWidget(self.btn_cancel)
        root.addLayout(btn_row)

    def _build_auto_tab(self):
        auto_widget = QWidget()
        auto_layout = QVBoxLayout(auto_widget)
        auto_layout.setSpacing(8)
        auto_layout.setContentsMargins(12, 12, 12, 12)

        # FW 파일 선택 행
        file_row = QHBoxLayout()
        lbl_file = QLabel("FW File:")
        lbl_file.setFixedWidth(80)
        self.edit_file = QLineEdit()
        self.edit_file.setReadOnly(True)
        self.edit_file.setPlaceholderText("No file selected")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setFixedWidth(70)
        file_row.addWidget(lbl_file)
        file_row.addWidget(self.edit_file, 1)
        file_row.addWidget(self.btn_browse)
        auto_layout.addLayout(file_row)

        # 비밀번호 행
        pw_row = QHBoxLayout()
        lbl_pw = QLabel("Password:")
        lbl_pw.setFixedWidth(80)
        self.edit_pw = QLineEdit()
        self.edit_pw.setEchoMode(QLineEdit.Password)
        self.edit_pw.setPlaceholderText("Optional")
        pw_row.addWidget(lbl_pw)
        pw_row.addWidget(self.edit_pw, 1)
        auto_layout.addLayout(pw_row)

        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        auto_layout.addWidget(sep)

        # 진행 바 (업로드 중에만 표시)
        self.pgbar_auto = QProgressBar()
        self.pgbar_auto.setRange(0, 100)
        self.pgbar_auto.setValue(0)
        self.pgbar_auto.setVisible(False)
        auto_layout.addWidget(self.pgbar_auto)

        auto_layout.addStretch()
        self.tab_widget.addTab(auto_widget, "자동 (내장 TFTP)")

    def _build_manual_tab(self):
        manual_widget = QWidget()
        manual_layout = QVBoxLayout(manual_widget)
        manual_layout.setSpacing(8)
        manual_layout.setContentsMargins(12, 12, 12, 12)

        # 서버 IP 행
        ip_row = QHBoxLayout()
        lbl_ip = QLabel("Server IP:")
        lbl_ip.setFixedWidth(80)
        self.edit_ip = QLineEdit(self._localip_addr)
        ip_row.addWidget(lbl_ip)
        ip_row.addWidget(self.edit_ip, 1)
        manual_layout.addLayout(ip_row)

        # 포트 행
        port_row = QHBoxLayout()
        lbl_port = QLabel("Port:")
        lbl_port.setFixedWidth(80)
        self.edit_port = QLineEdit("69")
        port_row.addWidget(lbl_port)
        port_row.addWidget(self.edit_port, 1)
        manual_layout.addLayout(port_row)

        # 파일명 행
        fname_row = QHBoxLayout()
        lbl_fname = QLabel("File Name:")
        lbl_fname.setFixedWidth(80)
        self.edit_fname = QLineEdit()
        fname_row.addWidget(lbl_fname)
        fname_row.addWidget(self.edit_fname, 1)
        manual_layout.addLayout(fname_row)

        # 비밀번호 행
        pw_row = QHBoxLayout()
        lbl_pw_m = QLabel("Password:")
        lbl_pw_m.setFixedWidth(80)
        self.edit_pw_manual = QLineEdit()
        self.edit_pw_manual.setEchoMode(QLineEdit.Password)
        self.edit_pw_manual.setPlaceholderText("Optional")
        pw_row.addWidget(lbl_pw_m)
        pw_row.addWidget(self.edit_pw_manual, 1)
        manual_layout.addLayout(pw_row)

        manual_layout.addStretch()
        self.tab_widget.addTab(manual_widget, "수동 (외부 TFTP)")

    # ── 시그널 연결 ───────────────────────────────────────────────────

    def _connect_signals(self):
        self.btn_browse.clicked.connect(self._on_browse)
        self.btn_upload.clicked.connect(self._on_upload)
        self.btn_cancel.clicked.connect(self._on_cancel)

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────

    def _on_browse(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "펌웨어 파일 선택", "", "Binary Files (*.bin);;All Files (*)"
        )
        if not fname:
            return
        if _is_boot_file(fname):
            QMessageBox.warning(
                self, "파일 오류",
                "Cannot upload BOOT firmware file. Please select an APP firmware file only."
            )
            return
        self._fw_path = fname
        self.edit_file.setText(os.path.basename(fname))

    def _on_upload(self):
        valid, err_msg = self._validate_inputs()
        if not valid:
            self._set_status(err_msg, error=True)
            return

        tab = self.tab_widget.currentIndex()
        if tab == 0:
            mode        = 'auto'
            fw_path     = self._fw_path
            server_ip   = ""   # OS 라우팅 프로브로 자동 결정 (target_ip 기준 최적 NIC)
            server_port = 69
            password    = self.edit_pw.text()
        else:
            mode        = 'manual'
            fw_path     = ""
            server_ip   = self.edit_ip.text().strip()
            server_port = int(self.edit_port.text().strip())
            password    = self.edit_pw_manual.text()

        self._set_uploading_state(True)
        self._set_status("Sending firmware upload request...", muted=True)

        self._upload_thread = WIZ550FWUploadThread(
            mode=mode,
            fw_path=fw_path,
            target_ip=self._target_ip,
            target_mac=self._target_mac,
            server_ip=server_ip,
            server_port=server_port,
            password=password,
            iface_ip=self._localip_addr or "",
        )
        self._upload_thread.progress.connect(self._on_progress)
        self._upload_thread.finished.connect(self._on_finished)
        self._upload_thread.error.connect(self._on_error)
        self._upload_thread.start()
        logger.info(f"[WIZ550FW] 업로드 시작 mode={mode} target={self._target_ip}")

    def _on_cancel(self):
        if self._upload_thread is not None and self._upload_thread.isRunning():
            self._upload_thread.stop()
            self._upload_thread.wait(3000)
            self._upload_thread = None
        self.reject()

    # ── 스레드 시그널 핸들러 ──────────────────────────────────────────

    def _on_progress(self, msg: str):
        self._set_status(msg, muted=True)

    def _on_finished(self, success: bool):
        self._set_uploading_state(False)
        if success:
            self._set_status("Upload complete!", success=True)
        else:
            current = self.lbl_status.text()
            progress_msgs = {
                "Sending firmware upload request...",
                "Waiting for device response...",
            }
            if not current or current in progress_msgs:
                self._set_status(
                    "Upload timed out. No response from device. "
                    "Please retry or check the device connection.",
                    error=True,
                )

    def _on_error(self, msg: str):
        self._set_uploading_state(False)
        if "timed out" in msg.lower() or "no response" in msg.lower():
            self._set_status(
                "Upload timed out. No response from device. "
                "Please retry or check the device connection.",
                error=True,
            )
        else:
            self._set_status(msg, error=True)

    # ── 상태 관리 ─────────────────────────────────────────────────────

    def _set_uploading_state(self, uploading: bool):
        """D-07 + UI-SPEC Interaction States."""
        self.btn_upload.setEnabled(not uploading)
        self.tab_widget.setEnabled(not uploading)
        if uploading:
            self.btn_cancel.setText("Stop Upload")
            self.pgbar_auto.setRange(0, 0)   # indeterminate
            self.pgbar_auto.setValue(0)
            self.pgbar_auto.setVisible(True)
        else:
            self.btn_cancel.setText("Close")
            self.pgbar_auto.setRange(0, 100)
            self.pgbar_auto.setValue(100)

    def _set_status(self, msg: str, *, error: bool = False,
                    success: bool = False, muted: bool = False):
        self.lbl_status.setText(msg)
        if error:
            self.lbl_status.setStyleSheet("color: #c64545;")
        elif success:
            self.lbl_status.setStyleSheet("color: #5db872;")
        elif muted:
            self.lbl_status.setStyleSheet("color: #6c6a64;")
        else:
            self.lbl_status.setStyleSheet("")

    # ── 입력 유효성 검증 ──────────────────────────────────────────────

    def _validate_inputs(self) -> tuple:
        tab = self.tab_widget.currentIndex()
        if tab == 0:
            if not self._fw_path:
                return False, "Please select a firmware file."
            if len(os.path.basename(self._fw_path)) > 50:
                return False, "File name is too long (max 50 characters)."
            return True, ""
        else:
            ip_text    = self.edit_ip.text().strip()
            port_text  = self.edit_port.text().strip()
            fname_text = self.edit_fname.text().strip()
            try:
                socket.inet_aton(ip_text)
            except OSError:
                return False, "Invalid server IP address."
            try:
                port = int(port_text)
                if not (1 <= port <= 65535):
                    raise ValueError
            except ValueError:
                return False, "Port must be between 1 and 65535."
            if not fname_text:
                return False, "Please enter the firmware file name on the TFTP server."
            if len(fname_text) > 50:
                return False, "File name is too long (max 50 characters)."
            return True, ""

    # ── 닫기 안전 정리 ────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._upload_thread is not None and self._upload_thread.isRunning():
            self._upload_thread.stop()
            self._upload_thread.wait(3000)
        event.accept()
