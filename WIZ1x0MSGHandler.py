#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ1x0MSGHandler.py — WIZ100SR/WIZ105SR/WIZ110SR 바이너리 프로토콜 핸들러

프로토콜:
  - 검색: UDP 브로드캐스트 255.255.255.255:1460 → 'FIND'(4B)
  - 응답: 'IMIN' + 163바이트 바이너리
  - 설정: UDP unicast/TCP → 'SETT' + 163바이트  (즉시 저장+리부트)
  - 응답: 'SETC' + 163바이트

기존 WIZMSGHandler(UDP:50001, 텍스트 커맨드)와 완전 분리.
"""

import socket
import select
import time
from PyQt5.QtCore import QThread, pyqtSignal

from WIZ1x0Profile import (
    build_find, parse_imin, build_sett,
    BOARD_INFO_SIZE,
)
from utils import logger

WIZ1X0_SEARCH_PORT  = 1460   # 장치 수신 포트 (브로드캐스트)
WIZ1X0_SEARCH_SPORT = 5001   # 응답 수신 포트 (장치 → PC)
WIZ1X0_SET_PORT     = 1461   # TCP 유니캐스트 설정 포트
WIZ1X0_FW_PORT      = 1470   # 펌웨어 업로드 포트 (고정)
PACKET_SIZE         = 4 + BOARD_INFO_SIZE  # 167바이트


class WIZ1x0Searcher(QThread):
    """
    WIZ1x0SR 검색 스레드.

    FIND 브로드캐스트(UDP:1460) × repeat회 반복 → IMIN 응답 수집.
    search_done 시그널: [(mac_str, board_dict), ...]
    """
    search_done = pyqtSignal(list)

    def __init__(self, iface_ip: str = "", repeat: int = 3, timeout: float = 1.0):
        super().__init__()
        self.iface_ip = iface_ip
        self.repeat   = repeat
        self.timeout  = timeout
        self.logger   = logger

    def run(self):
        results = {}   # mac_str → board_dict (중복 MAC 제거)

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # 수신은 항상 INADDR_ANY:5001 — VB6 원본과 동일
            # VB6: LocalHostAddr 미지정 → INADDR_ANY → 모든 인터페이스에서 수신
            # iface_ip로 특정 NIC bind 시 해당 서브넷 외 장치 응답을 수신 못함
            sock.bind(('', WIZ1X0_SEARCH_SPORT))

            find_pkt = build_find()

            for i in range(self.repeat):
                self.logger.info(f"[WIZ1x0] FIND 브로드캐스트 #{i+1}/{self.repeat}")
                try:
                    sock.sendto(find_pkt, ('255.255.255.255', WIZ1X0_SEARCH_PORT))
                except OSError as e:
                    self.logger.error(f"[WIZ1x0] sendto 실패: {e}")
                    continue

                # 응답 수집 (timeout 내 가능한 한 많이)
                deadline = time.time() + self.timeout
                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    ready, _, _ = select.select([sock], [], [], remaining)
                    if not ready:
                        break
                    try:
                        data, addr = sock.recvfrom(512)
                    except OSError:
                        break

                    parsed = parse_imin(data)
                    if parsed is None:
                        self.logger.debug(f"[WIZ1x0] 무시: {addr} len={len(data)}")
                        continue

                    mac = parsed['mac']
                    if mac not in results:
                        self.logger.info(f"[WIZ1x0] 발견: {mac} ({addr[0]}) FW={parsed['appver_str']}")
                        results[mac] = parsed

        except Exception as e:
            self.logger.error(f"[WIZ1x0] Searcher 오류: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        result_list = [(mac, d) for mac, d in results.items()]
        self.logger.info(f"[WIZ1x0] 검색 완료: {len(result_list)}개")
        self.search_done.emit(result_list)


class WIZ1x0Setter(QThread):
    """
    WIZ1x0SR 설정 적용 스레드.

    SETT 전송(UDP unicast) → SETC 응답 확인.
    set_done 시그널: True=성공, False=실패

    ※ SETT 전송 즉시 장치가 저장+리부트됨.
    """
    set_done = pyqtSignal(bool, bytes)  # (성공 여부, SETC 응답 바이너리 or b'')

    def __init__(self, target_ip: str, board_dict: dict, timeout: float = 3.0):
        super().__init__()
        self.target_ip  = target_ip
        self.board_dict = board_dict
        self.timeout    = timeout
        self.logger     = logger

    def run(self):
        sock = None
        success = False
        response = b''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', 0))  # OS 자동 포트

            sett_pkt = build_sett(self.board_dict)
            self.logger.info(f"[WIZ1x0] SETT → {self.target_ip}:{WIZ1X0_SEARCH_PORT}")
            sock.sendto(sett_pkt, (self.target_ip, WIZ1X0_SEARCH_PORT))

            # SETC 응답 대기
            ready, _, _ = select.select([sock], [], [], self.timeout)
            if ready:
                data, _ = sock.recvfrom(512)
                if len(data) >= 4 and data[:4] == b'SETC':
                    self.logger.info("[WIZ1x0] SETC 응답 수신 → 설정 성공")
                    success = True
                    response = data
                else:
                    self.logger.warning(f"[WIZ1x0] 예상치 않은 응답: {data[:4]}")
            else:
                self.logger.warning("[WIZ1x0] SETC 응답 타임아웃")

        except Exception as e:
            self.logger.error(f"[WIZ1x0] Setter 오류: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        self.set_done.emit(success, response)
