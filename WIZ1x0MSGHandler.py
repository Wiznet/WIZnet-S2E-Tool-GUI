#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIZ1x0MSGHandler.py — WIZ100SR/WIZ105SR/WIZ110SR 바이너리 프로토콜 핸들러

프로토콜:
  - 검색: UDP 브로드캐스트 255.255.255.255:1460 → 'FIND'(4B)
  - 응답: 'IMIN'(4B) + 159바이트 바이너리 (총 163바이트)
  - 설정: UDP 브로드캐스트 → 'SETT'(4B) + 159바이트  (즉시 저장+리부트)
  - 응답: 'SETC'(4B) + 159바이트
  - 직접-IP: TCP:1461 — 동일 패킷(FIND/SETT)을 TCP로 전송 (VB6 WinsockDirect)

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
WIZ1X0_DIRECT_PORT  = 1461   # 직접-IP 검색/설정 TCP 포트 (VB6 WinsockDirect)
WIZ1X0_SET_PORT     = WIZ1X0_DIRECT_PORT  # (구명칭 호환)
WIZ1X0_FW_PORT      = 1470   # 펌웨어 업로드 포트 (고정)
PACKET_SIZE         = 4 + BOARD_INFO_SIZE  # 4 + 159 = 163바이트


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

            # iface_ip 지정 시 해당 IP로 바인드:
            #   - FIND 브로드캐스트가 반드시 해당 NIC으로 송출됨
            #   - 장치가 IMIN을 src_ip(iface_ip):5001로 돌려보내므로 수신 가능
            # iface_ip 미지정(INADDR_ANY) 시 Windows 라우팅 테이블에 따라
            #   다른 NIC IP가 소스가 될 수 있어 IMIN을 못 받는 경우 있음
            bind_ip = self.iface_ip if self.iface_ip else ''
            sock.bind((bind_ip, WIZ1X0_SEARCH_SPORT))
            self.logger.info(f"[WIZ1x0] bind {bind_ip or 'INADDR_ANY'}:{WIZ1X0_SEARCH_SPORT}")

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


class WIZ1x0DirectSearcher(QThread):
    """WIZ1x0SR 직접-IP 검색 스레드 (TCP:1461).

    VB6 원본 frmSEGConf의 WinsockDirect_Connect/_DataArrival 이식:
    TCP 연결 → 'FIND'(4B) 전송 → 'IMIN'+159B(총 163B) 수신 → 세션 종료.
    UDP 브로드캐스트와 달리 장치 1대만 대상이며 응답도 1회다.

    설계 계약 (issue #67 후속 — pending 플래그 데드락 방지):
      - 모든 경로에서 search_done을 정확히 1회 emit
        (연결 실패/타임아웃/파싱 실패 = 빈 리스트)
      - 소켓은 지역 변수로만 생성·해제 — main_gui의 conf_sock/isConnected를
        절대 건드리지 않는다 (그 둘은 ASCII TCP 경로 전용 게이트)
      - TCP는 스트림이라 163바이트가 분할 도착할 수 있다 → deadline까지 누적

    주의: parse_imin()의 WIZ120SR 필터(byte[103])가 여기에도 적용된다.
    VB6 원본은 Direct 경로에 이 필터가 없었으나(비대칭 버그), 의도적으로
    더 엄격한 쪽을 택했다 — 120SR은 미지원 장치.
    """
    search_done = pyqtSignal(list)

    def __init__(self, target_ip: str, timeout: float = 2.0):
        super().__init__()
        self.target_ip = target_ip
        self.timeout = timeout
        self.logger = logger

    def run(self):
        results = []
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 미설정 시 connect가 OS 기본(수십 초)까지 블록될 수 있다
            sock.settimeout(self.timeout)
            self.logger.info(
                f"[WIZ1x0] direct 검색: {self.target_ip}:{WIZ1X0_DIRECT_PORT}"
            )
            sock.connect((self.target_ip, WIZ1X0_DIRECT_PORT))
            sock.sendall(build_find())

            # 스트림 재조립 — PACKET_SIZE(163B)를 채우거나 deadline까지
            buf = b''
            deadline = time.time() + self.timeout
            while len(buf) < PACKET_SIZE:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                chunk = sock.recv(PACKET_SIZE - len(buf))
                if not chunk:  # 장치가 세션을 닫음
                    break
                buf += chunk

            parsed = parse_imin(buf)
            if parsed is not None:
                self.logger.info(
                    f"[WIZ1x0] direct 발견: {parsed['mac']} "
                    f"({self.target_ip}) FW={parsed['appver_str']}"
                )
                results.append((parsed['mac'], parsed))
            elif buf:
                self.logger.debug(
                    f"[WIZ1x0] direct 응답 파싱 실패: len={len(buf)}"
                )
        except OSError as e:
            # 연결 거부/타임아웃 = 그 IP에 WIZ1x0 없음. 정상 탐색 실패.
            self.logger.info(f"[WIZ1x0] direct 검색 실패 {self.target_ip}: {e}")
        except Exception as e:
            self.logger.error(f"[WIZ1x0] DirectSearcher 오류: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        # 계약: 어떤 경로에서도 정확히 1회 emit (호출측 UI 갱신 보장)
        self.search_done.emit(results)


class WIZ1x0Setter(QThread):
    """
    WIZ1x0SR 설정 적용 스레드.

    SETT 전송(UDP unicast) → SETC 응답 확인.
    set_done 시그널: True=성공, False=실패

    ※ SETT 전송 즉시 장치가 저장+리부트됨.
    """
    set_done = pyqtSignal(bool, bytes)  # (성공 여부, SETC 응답 바이너리 or b'')

    def __init__(self, target_ip: str, board_dict: dict, iface_ip: str = "", timeout: float = 3.0):
        super().__init__()
        self.target_ip  = target_ip
        self.board_dict = board_dict
        self.iface_ip   = iface_ip
        self.timeout    = timeout
        self.logger     = logger

    def run(self):
        sock = None
        success = False
        response = b''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # iface_ip로 바인드: SETT 소스 IP = iface_ip → 장치가 SETC를 iface_ip:5001로 돌려보냄
            # 장치는 자신의 서브넷 기준 라우팅 → iface_ip가 같은 서브넷이어야 SETC 도달 가능
            bind_ip = self.iface_ip if self.iface_ip else ''
            sock.bind((bind_ip, WIZ1X0_SEARCH_SPORT))
            self.logger.info(f"[WIZ1x0] Setter bind {bind_ip or 'INADDR_ANY'}:{WIZ1X0_SEARCH_SPORT}")

            sett_pkt = build_sett(self.board_dict)
            # VB6: WinsockUDP.RemoteHost="255.255.255.255", RemotePort=1460
            self.logger.info(f"[WIZ1x0] SETT → 255.255.255.255:{WIZ1X0_SEARCH_PORT} (target={self.target_ip})")
            sock.sendto(sett_pkt, ('255.255.255.255', WIZ1X0_SEARCH_PORT))

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
