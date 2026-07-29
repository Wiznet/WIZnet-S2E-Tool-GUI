#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_wiz550_fw.py — Phase 7 TFTP FW Upload 테스트 스텁

Wave 0: RED 상태. 후속 구현 완료 후 GREEN 전환.
"""

import struct
import tempfile
import os
import pytest

import tftpy  # 설치 확인 (pip show tftpy → 0.8.7)


# ─────────────────────────────────────────────────────────────────
# FW-02: 0xD1 패킷 빌더 — 86바이트 레이아웃 + server_port LE 검증
# ─────────────────────────────────────────────────────────────────

def test_build_fw_upload_pkt():
    """
    build_fw_upload_pkt() → 86B, offset[3]=0xD1, offset[34:36]=LE(69).
    RED: WIZ550MSGHandler에 함수 미구현 상태.
    """
    from WIZ550MSGHandler import build_fw_upload_pkt

    pkt = build_fw_upload_pkt(
        target_mac="00:08:DC:AB:CD:EF",
        server_ip="192.168.0.100",
        server_port=69,
        file_name="app.bin",
        password="",
    )
    assert len(pkt) == 86, f"Expected 86 bytes, got {len(pkt)}"
    assert pkt[0] == 0xA5, "STX mismatch"
    assert pkt[3] == 0xD1, "op_code must be 0xD1 (FW_UPLOAD)"
    # payload는 XOR 암호화 — valid 바이트로 key 추출 후 복호화
    key = pkt[1] & 0x7F if pkt[1] & 0x80 else 0
    dec = bytes(b ^ key for b in pkt[7:])   # 복호화 payload 79B
    port = struct.unpack_from('<H', dec, 27)[0]  # payload 내 server_port offset
    assert port == 69, f"server_port LE 오류: expected 69, got {port}"


# ─────────────────────────────────────────────────────────────────
# FW-01: tftpy TftpServer 초기화 — tmpdir + 인스턴스 생성
# ─────────────────────────────────────────────────────────────────

def test_tftp_server_tempdir():
    """
    tempfile.mkdtemp() + TftpServer(tftproot=tmpdir) 생성 성공.
    listen() 호출 없이 객체 생성만 검증.
    """
    tmpdir = tempfile.mkdtemp(prefix='wiz550fw_test_')
    try:
        server = tftpy.TftpServer(tftproot=tmpdir)
        assert server is not None
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────
# FW-03: 0xD2 완료 응답 파싱
# ─────────────────────────────────────────────────────────────────

def test_parse_fw_done_reply():
    """
    _is_fw_done_reply(data) → True (0xD2/0x55 헤더 인식).
    RED: WIZ550FWUploadThread에 함수 미구현 상태.
    """
    from WIZ550FWUploadThread import _is_fw_done_reply

    # 7B 헤더 (0xD2 응답) + 6B src_mac = 13B
    header = bytes([0xA5, 0x00, 0x01, 0xD2, 0x55, 0x06, 0x00])
    src_mac = bytes([0x00, 0x08, 0xDC, 0xAB, 0xCD, 0xEF])
    pkt = header + src_mac
    assert _is_fw_done_reply(pkt) is True

    # 다른 op_code → False
    not_done = bytes([0xA5, 0x00, 0x01, 0xB0, 0x55, 0x06, 0x00]) + src_mac
    assert _is_fw_done_reply(not_done) is False


# ─────────────────────────────────────────────────────────────────
# FW-04: 다이얼로그 탭 2개 존재
# ─────────────────────────────────────────────────────────────────

def test_dialog_tabs(qapp):
    """
    WIZ550FWDialog(localip_addr) 생성 → QTabWidget.count() == 2.
    RED: wiz550_fw_dialog.py 미구현 상태.
    """
    from wiz550_fw_dialog import WIZ550FWDialog

    dlg = WIZ550FWDialog(localip_addr="192.168.0.100")
    assert dlg.tab_widget.count() == 2, "탭 2개 필요 (자동/수동)"
    dlg.close()


# ─────────────────────────────────────────────────────────────────
# FW-02 보안: BOOT 파일 업로드 거부
# ─────────────────────────────────────────────────────────────────

def test_boot_file_rejected():
    """
    파일명에 'BOOT' 포함 시 _is_boot_file() → True (업로드 거부 대상).
    RED: wiz550_fw_dialog.py 미구현 상태.
    """
    from wiz550_fw_dialog import _is_boot_file

    assert _is_boot_file("WIZ550SR_BOOT_v1.bin") is True
    assert _is_boot_file("WIZ550SR_APP_v1.bin") is False
    assert _is_boot_file("boot_upgrade.bin") is True   # 대소문자 무관
    assert _is_boot_file("app.bin") is False
