"""
terminal/comm_handlers.py
UDP / TCP Client / TCP Server / Serial 송수신 QThread 핸들러.
각 핸들러는 독립 스레드로 동작하며 시그널로 UI에 데이터를 전달한다.
UI → 핸들러 전송은 thread-safe deque를 통한 send queue로 처리한다.
"""

import select
import socket
import threading
from collections import deque

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QThread, pyqtSignal


# ──────────────────────────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────────────────────────

def list_serial_ports():
    """사용 가능한 COM 포트 목록 반환."""
    return [p.device for p in serial.tools.list_ports.comports()]


def _encode_escape(text: str) -> bytes:
    """
    Escape 해석: \\r\\n \\t \\xHH → 실제 바이트.
    해석 실패한 시퀀스는 원문 그대로 유지.
    """
    result = bytearray()
    i = 0
    data = text
    while i < len(data):
        if data[i] == '\\' and i + 1 < len(data):
            nxt = data[i + 1]
            if nxt == 'r':
                result.append(0x0D); i += 2; continue
            if nxt == 'n':
                result.append(0x0A); i += 2; continue
            if nxt == 't':
                result.append(0x09); i += 2; continue
            if nxt == '\\':
                result.append(ord('\\')); i += 2; continue
            if nxt == 'x' and i + 3 < len(data):
                try:
                    val = int(data[i + 2:i + 4], 16)
                    result.append(val); i += 4; continue
                except ValueError:
                    pass
        result.append(ord(data[i])); i += 1
    return bytes(result)


# ──────────────────────────────────────────────────────────────
# UDP 핸들러
# ──────────────────────────────────────────────────────────────

class UDPHandler(QThread):
    """
    UDP 단방향/양방향 핸들러.
    - local_port 에 bind → 수신 대기
    - send() 로 remote_ip:remote_port 로 전송
    """
    data_received = pyqtSignal(bytes, str, int)   # data, from_ip, from_port
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)              # 'bound' | 'closed' | 'error'
    stats_updated  = pyqtSignal(int, int)         # tx_bytes, rx_bytes

    def __init__(self, remote_ip: str, remote_port: int, local_port: int = 0, parent=None):
        super().__init__(parent)
        self.remote_ip   = remote_ip
        self.remote_port = remote_port
        self.local_port  = local_port
        self._send_queue = deque()
        self._stop_event = threading.Event()
        self._tx = 0
        self._rx = 0

    def send(self, data: bytes):
        self._send_queue.append(data)

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(('', self.local_port))
            sock.setblocking(False)
            self.status_changed.emit('bound')
        except OSError as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit('error')
            return

        try:
            while not self._stop_event.is_set():
                # 전송
                while self._send_queue:
                    chunk = self._send_queue.popleft()
                    try:
                        sock.sendto(chunk, (self.remote_ip, self.remote_port))
                        self._tx += len(chunk)
                        self.stats_updated.emit(self._tx, self._rx)
                    except OSError as e:
                        self.error_occurred.emit(str(e))

                # 수신
                readable, _, _ = select.select([sock], [], [], 0.05)
                if readable:
                    try:
                        data, addr = sock.recvfrom(4096)
                        if data:
                            self._rx += len(data)
                            self.stats_updated.emit(self._tx, self._rx)
                            self.data_received.emit(data, addr[0], addr[1])
                    except OSError:
                        pass
        finally:
            sock.close()
            self.status_changed.emit('closed')


# ──────────────────────────────────────────────────────────────
# TCP Client 핸들러
# ──────────────────────────────────────────────────────────────

class TCPClientHandler(QThread):
    data_received   = pyqtSignal(bytes)
    connected       = pyqtSignal()
    disconnected    = pyqtSignal(str)   # reason
    error_occurred  = pyqtSignal(str)
    stats_updated   = pyqtSignal(int, int)

    def __init__(self, remote_ip: str, remote_port: int,
                 auto_reconnect: bool = False, reconnect_interval: float = 5.0,
                 parent=None):
        super().__init__(parent)
        self.remote_ip         = remote_ip
        self.remote_port       = remote_port
        self.auto_reconnect    = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self._send_queue = deque()
        self._stop_event = threading.Event()
        self._tx = 0
        self._rx = 0

    def send(self, data: bytes):
        self._send_queue.append(data)

    def stop(self):
        self._stop_event.set()

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((self.remote_ip, self.remote_port))
        except OSError as e:
            sock.close()
            raise e
        sock.setblocking(False)
        return sock

    def run(self):
        while not self._stop_event.is_set():
            try:
                sock = self._connect()
            except OSError as e:
                self.error_occurred.emit(str(e))
                if not self.auto_reconnect:
                    self.disconnected.emit(str(e))
                    return
                # 재연결 대기
                self._stop_event.wait(self.reconnect_interval)
                continue

            self.connected.emit()
            try:
                while not self._stop_event.is_set():
                    # 전송
                    while self._send_queue:
                        chunk = self._send_queue.popleft()
                        try:
                            sock.sendall(chunk)
                            self._tx += len(chunk)
                            self.stats_updated.emit(self._tx, self._rx)
                        except OSError as e:
                            self.error_occurred.emit(str(e))
                            raise e

                    # 수신
                    readable, _, _ = select.select([sock], [], [], 0.05)
                    if readable:
                        try:
                            data = sock.recv(4096)
                        except OSError as e:
                            raise e
                        if not data:
                            raise OSError('connection closed by remote')
                        self._rx += len(data)
                        self.stats_updated.emit(self._tx, self._rx)
                        self.data_received.emit(data)
            except OSError as e:
                self.disconnected.emit(str(e))
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

            if not self.auto_reconnect or self._stop_event.is_set():
                break
            self._stop_event.wait(self.reconnect_interval)

        self.disconnected.emit('stopped')


# ──────────────────────────────────────────────────────────────
# TCP Server 핸들러
# ──────────────────────────────────────────────────────────────

class TCPServerHandler(QThread):
    """
    단일 클라이언트 TCP 서버.
    새 클라이언트 접속 시 기존 연결이 있으면 new_client_request 시그널을 발생시키고
    UI가 응답(accept_new_client 호출 여부)을 결정한다.
    """
    data_received      = pyqtSignal(bytes, str, int)   # data, ip, port
    client_connected   = pyqtSignal(str, int)           # ip, port
    client_disconnected = pyqtSignal(str, int)
    new_client_request = pyqtSignal(str, int)           # 충돌: UI가 결정
    error_occurred     = pyqtSignal(str)
    status_changed     = pyqtSignal(str)                # 'listening' | 'closed' | 'error'
    stats_updated      = pyqtSignal(int, int)

    def __init__(self, local_port: int, parent=None):
        super().__init__(parent)
        self.local_port  = local_port
        self._send_queue = deque()
        self._stop_event = threading.Event()
        self._accept_new = threading.Event()   # UI가 새 클라이언트 수락 여부 설정
        self._reject_new = threading.Event()
        self._pending_client = None            # (sock, addr) 대기 중인 신규 클라이언트
        self._tx = 0
        self._rx = 0

    def send(self, data: bytes):
        self._send_queue.append(data)

    def stop(self):
        self._stop_event.set()

    def accept_new_client(self):
        """UI: 신규 클라이언트 수락 (기존 연결 끊기)."""
        self._accept_new.set()

    def reject_new_client(self):
        """UI: 신규 클라이언트 거절 (기존 연결 유지)."""
        self._reject_new.set()

    def run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('', self.local_port))
            srv.listen(1)
            srv.setblocking(False)
            self.status_changed.emit('listening')
        except OSError as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit('error')
            return

        client_sock = None
        client_addr = None

        try:
            while not self._stop_event.is_set():
                # 신규 연결 수락 확인
                readable, _, _ = select.select([srv], [], [], 0.05)
                if readable:
                    try:
                        new_sock, new_addr = srv.accept()
                        new_sock.setblocking(False)
                    except OSError:
                        continue

                    if client_sock is None:
                        client_sock = new_sock
                        client_addr = new_addr
                        self.client_connected.emit(new_addr[0], new_addr[1])
                    else:
                        # 기존 연결 있음 → UI에 문의
                        self._pending_client = (new_sock, new_addr)
                        self._accept_new.clear()
                        self._reject_new.clear()
                        self.new_client_request.emit(new_addr[0], new_addr[1])
                        # UI 응답 대기 (최대 30초)
                        while not self._accept_new.is_set() and not self._reject_new.is_set():
                            if self._stop_event.is_set():
                                break
                            self.msleep(100)

                        if self._accept_new.is_set():
                            old_addr = client_addr
                            try:
                                client_sock.close()
                            except Exception:
                                pass
                            self.client_disconnected.emit(old_addr[0], old_addr[1])
                            client_sock, client_addr = self._pending_client
                            self.client_connected.emit(client_addr[0], client_addr[1])
                        else:
                            try:
                                self._pending_client[0].close()
                            except Exception:
                                pass
                        self._pending_client = None

                # 기존 클라이언트 데이터 처리
                if client_sock is not None:
                    c_readable, _, c_err = select.select([client_sock], [], [client_sock], 0.0)
                    if c_err:
                        self.client_disconnected.emit(client_addr[0], client_addr[1])
                        client_sock.close()
                        client_sock = None
                        continue
                    if c_readable:
                        try:
                            data = client_sock.recv(4096)
                        except OSError:
                            self.client_disconnected.emit(client_addr[0], client_addr[1])
                            client_sock.close()
                            client_sock = None
                            continue
                        if not data:
                            self.client_disconnected.emit(client_addr[0], client_addr[1])
                            client_sock.close()
                            client_sock = None
                            continue
                        self._rx += len(data)
                        self.stats_updated.emit(self._tx, self._rx)
                        self.data_received.emit(data, client_addr[0], client_addr[1])

                    # 전송
                    while self._send_queue and client_sock is not None:
                        chunk = self._send_queue.popleft()
                        try:
                            client_sock.sendall(chunk)
                            self._tx += len(chunk)
                            self.stats_updated.emit(self._tx, self._rx)
                        except OSError as e:
                            self.error_occurred.emit(str(e))
                            break
        finally:
            if client_sock:
                try:
                    client_sock.close()
                except Exception:
                    pass
            try:
                srv.close()
            except Exception:
                pass
            self.status_changed.emit('closed')


# ──────────────────────────────────────────────────────────────
# Serial 핸들러
# ──────────────────────────────────────────────────────────────

class SerialHandler(QThread):
    data_received  = pyqtSignal(bytes)
    connected      = pyqtSignal()
    disconnected   = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    stats_updated  = pyqtSignal(int, int)

    PARITY_MAP = {
        'None': serial.PARITY_NONE,
        'Even': serial.PARITY_EVEN,
        'Odd':  serial.PARITY_ODD,
        'Mark': serial.PARITY_MARK,
        'Space': serial.PARITY_SPACE,
    }
    STOPBITS_MAP = {
        '1':   serial.STOPBITS_ONE,
        '1.5': serial.STOPBITS_ONE_POINT_FIVE,
        '2':   serial.STOPBITS_TWO,
    }

    def __init__(self, port: str, baudrate: int = 115200,
                 bytesize: int = 8, parity: str = 'None',
                 stopbits: str = '1', parent=None):
        super().__init__(parent)
        self.port      = port
        self.baudrate  = baudrate
        self.bytesize  = bytesize
        self.parity    = self.PARITY_MAP.get(parity, serial.PARITY_NONE)
        self.stopbits  = self.STOPBITS_MAP.get(stopbits, serial.STOPBITS_ONE)
        self._send_queue = deque()
        self._stop_event = threading.Event()
        self._tx = 0
        self._rx = 0

    def send(self, data: bytes):
        self._send_queue.append(data)

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=0.1,
            )
        except serial.SerialException as e:
            self.error_occurred.emit(str(e))
            self.disconnected.emit(str(e))
            return

        self.connected.emit()
        try:
            while not self._stop_event.is_set():
                # 전송
                while self._send_queue:
                    chunk = self._send_queue.popleft()
                    try:
                        ser.write(chunk)
                        self._tx += len(chunk)
                        self.stats_updated.emit(self._tx, self._rx)
                    except serial.SerialException as e:
                        self.error_occurred.emit(str(e))

                # 수신
                try:
                    waiting = ser.in_waiting
                except serial.SerialException:
                    break
                if waiting > 0:
                    try:
                        data = ser.read(waiting)
                    except serial.SerialException as e:
                        self.error_occurred.emit(str(e))
                        break
                    if data:
                        self._rx += len(data)
                        self.stats_updated.emit(self._tx, self._rx)
                        self.data_received.emit(data)
                else:
                    self.msleep(10)
        finally:
            try:
                ser.close()
            except Exception:
                pass
            self.disconnected.emit('closed')
