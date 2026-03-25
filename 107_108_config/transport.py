"""
107_108_config/transport.py
UDP / TCP 워커 스레드 (clsSckUDP.vb + clsSckTCP.vb 변환)

VB.NET 원본 설계 충실 변환:
  - 비동기 소켓 수신 → QThread + pyqtSignal
  - 응답 도착 시 data_arrived(bytes) 시그널 emit
  - 응답 길이 체크 없음 (VB.NET 원본 방식)

사용법:
  worker = SearchWorker(src_ip, packet, timeout=3.0)
  worker.data_arrived.connect(on_data)
  worker.finished.connect(on_done)
  worker.start()
"""
from __future__ import annotations

import select
import socket
import time

from PyQt5.QtCore import QThread, pyqtSignal

UDP_PORT = 50001
BROADCAST = "255.255.255.255"


# ── UDP 브로드캐스트 워커 ──────────────────────────────────────────────────────

class UDPWorker(QThread):
    """
    UDP 패킷 전송 후 timeout 초 동안 응답 수신.

    VB.NET의 비동기 sckUDP.DataArrival 이벤트 방식 대신
    QThread 에서 select() 루프로 구현.

    data_arrived: 수신된 raw bytes (MA prefix 포함, 10+payload)
    finished: 타임아웃 후 스레드 종료
    error: 소켓 오류 메시지
    """
    data_arrived = pyqtSignal(bytes)   # 수신 응답 (원본 bytes)
    finished     = pyqtSignal()
    error        = pyqtSignal(str)

    def __init__(
        self,
        src_ip: str,
        packet: bytes,
        timeout: float = 3.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.src_ip  = src_ip
        self.packet  = packet
        self.timeout = timeout
        self._stop   = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # src_ip 가 비어있으면 0.0.0.0 으로 바인딩
            bind_ip = self.src_ip if self.src_ip else "0.0.0.0"
            sock.bind((bind_ip, 0))
            sock.sendto(self.packet, (BROADCAST, UDP_PORT))

            deadline = time.time() + self.timeout
            seen: set[bytes] = set()          # 중복 수신 방지

            while not self._stop:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                rr, _, _ = select.select([sock], [], [], min(remaining, 0.3))
                if not rr:
                    continue
                try:
                    data, _addr = sock.recvfrom(4096)
                    if data and data not in seen:
                        seen.add(data)
                        self.data_arrived.emit(data)
                except OSError:
                    break
        except OSError as e:
            self.error.emit(str(e))
        finally:
            try:
                sock.close()
            except Exception:
                pass
        self.finished.emit()


# ── TCP 유니캐스트 워커 ───────────────────────────────────────────────────────

class TCPWorker(QThread):
    """
    TCP 유니캐스트 검색/설정 워커.
    VB.NET: sckTCP.Connect → sckTCP_Connected → Send → sckTCP_DataArrival

    data_arrived: 수신된 raw bytes
    connected   : TCP 연결 성공
    finished    : 스레드 종료
    error       : 오류 메시지
    """
    data_arrived = pyqtSignal(bytes)
    connected    = pyqtSignal()
    finished     = pyqtSignal()
    error        = pyqtSignal(str)

    def __init__(
        self,
        target_ip: str,
        packet: bytes,
        port: int = UDP_PORT,
        timeout: float = 3.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.target_ip = target_ip
        self.packet    = packet
        self.port      = port
        self.timeout   = timeout
        self._stop     = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.target_ip, self.port))
            self.connected.emit()
            sock.sendall(self.packet)
            sock.settimeout(self.timeout)

            buf = b""
            deadline = time.time() + self.timeout
            while not self._stop:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                rr, _, _ = select.select([sock], [], [], min(remaining, 0.3))
                if not rr:
                    break
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk

            if buf:
                self.data_arrived.emit(buf)

        except OSError as e:
            self.error.emit(str(e))
        finally:
            try:
                sock.close()
            except Exception:
                pass
        self.finished.emit()
