#!/usr/bin/python

from PyQt5.QtCore import QThread, pyqtSignal
from wizsocket.TCPClient import TCPClient
from WIZUDPSock import WIZUDPSock
from WIZMakeCMD import SECURITY_DEVICE
from constants import SockState
from utils import logger

import binascii
import codecs
import ipaddress
import select as _select
import time
import threading


def _parse_fw_response(resp: bytes):
    """FW 명령 응답 "IP:PORT" 파싱. 실패 시 None 반환."""
    try:
        text = resp.decode('utf-8').strip()
        ip_str, port_str = text.rsplit(':', 1)
        ipaddress.ip_address(ip_str)   # 유효하지 않으면 ValueError
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError(f"포트 범위 오류: {port}")
        return ip_str, port
    except Exception as e:
        logger.error(f'[FW-2] FW 응답 파싱 실패: {resp!r} → {e}')
        return None


_FW_PACKET_SIZE = 4096   # WIZMSGHandler.PACKET_SIZE 와 동일
_FW_LOOP_TIMEOUT = 0.5   # WIZMSGHandler.loop_select_timeout (OP_FWUP 경로) 와 동일


def _fw_send_cmd(sock, cmd_list: list, what_sock: str, timeout: int) -> bytes | None:
    """FW 업로드 전용 동기 커맨드 전송 (WIZMSGHandler.run() OP_FWUP 경로를 QThread 없이 재현).

    반환:
      bytes  — FW 응답 수신 (non-empty)
      b""    — timeout 또는 응답에 FW 필드 없음
      None   — 소켓 송신 단계에서 예외 발생
    """
    msg = bytearray(_FW_PACKET_SIZE)
    size = 0
    try:
        for cmd in cmd_list:
            msg[size:] = str.encode(cmd[0])
            size += len(cmd[0])
            if cmd[0] == "MA":
                val = cmd[1].replace(":", "")
                hex_bytes = codecs.decode(val, "hex")
                msg[size:] = hex_bytes
                size += 6
            else:
                msg[size:] = str.encode(cmd[1])
                size += len(cmd[1])
            if "\r\n" not in cmd[1]:
                msg[size:] = str.encode("\r\n")
                size += 2
    except Exception as e:
        logger.error(f"[_fw_send_cmd] 패킷 빌드 실패: {e}")
        return None

    try:
        if what_sock == "udp":
            sock.sendto(msg)
        elif what_sock == "tcp":
            sock.write(msg)
    except Exception as e:
        logger.error(f"[_fw_send_cmd] 전송 실패: {e}")
        return None

    reply = b""
    replylists = []
    try:
        raw_sock = sock.sock
        if not raw_sock:
            logger.error("[_fw_send_cmd] sock.sock 미초기화 — open()/connect() 미호출")
            return None
        inputs = [raw_sock]
        readready, _, _ = _select.select(inputs, [], [], timeout)
        while readready:
            for s in readready:
                if s == raw_sock:
                    if what_sock == "udp":
                        data, _addr = sock.recvfrom()
                    else:
                        data = sock.recvfrom()
                    replylists = data.split(b"\r\n")
                    for item in replylists:
                        if b"FW" in item[:2]:
                            reply = item[2:]
            readready, _, _ = _select.select(inputs, [], [], _FW_LOOP_TIMEOUT)
            if not readready or not replylists:
                break
    except Exception as e:
        logger.error(f"[_fw_send_cmd] 수신 실패: {e}")

    return reply


idle_state = 1
datasent_state = 2

FW_PACKET_SIZE = 1024
# FW_PACKET_SIZE = 2048


class FWUploadThread(QThread):
    uploading_size = pyqtSignal(int)
    upload_result = pyqtSignal(int)
    error_flag = pyqtSignal(int)

    def __init__(self, conf_sock, dest_mac, idcode, set_pw, filename, filesize, ipaddr, port, mn_list):
        QThread.__init__(self)

        self.logger = logger

        self.bin_filename = filename
        self.fd = None
        self.data = None
        self.client = None
        self.timer1 = None
        self.istimeout = 0
        self.serverip = None
        self.serverport = None
        self.sentbyte = 0
        self.dest_mac = dest_mac
        self.idcode = idcode
        self.error_noresponse = 0
        self.retrycheck = 0

        self.mn_list = mn_list
        self.set_pw = set_pw

        self.filesize = filesize
        self.remainbytes = self.filesize

        self.conf_sock = conf_sock
        self.sock_type = '%s' % self.conf_sock

        # socket config (for TCP unicast)
        self.ip_addr = ipaddr
        self.port = port

        self.tcp_sock = None

    def setparam(self):
        with open(self.bin_filename, "rb") as f:
            self.data = f.read()
        self.curr_ptr = 0

    def myTimer(self):
        self.logger.info('timer1 timeout')
        self.istimeout = 1

    def jumpToApp(self):
        cmd_list = []
        # boot mode change: App boot mode
        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", self.idcode])
        cmd_list.append(["AB", ""])

        sock_mode = 'TCP' if 'TCP' in self.sock_type else 'UDP'
        self.logger.info(f'[FW-1] AB (App Boot) 명령 전송 → {self.dest_mac} via {sock_mode}')

        self.resp = _fw_send_cmd(self.conf_sock, cmd_list, sock_mode.lower(), 2)
        self.logger.info(f'[FW-1] AB 응답: {repr(self.resp)} (장치 리부팅 중이면 빈 값 정상)')

        self.uploading_size.emit(1)
        self.logger.info('[FW-1] 장치 리부팅 대기 1초...')
        self.msleep(1000)
        self.logger.info('[FW-1] 리부팅 대기 완료')

    def sendCmd(self, command):
        cmd_list = []
        self.resp = None

        # Send FW UPload request message
        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", self.idcode])
        cmd_list.append([command, str(self.filesize)])

        self.logger.debug(f'sendCmd() cmd_list => {cmd_list}')

        sock_mode = 'TCP' if 'TCP' in self.sock_type else 'UDP'

        # if no reponse from device, retry for several times.
        for i in range(4):
            self.logger.info(f'[FW-2] {command} 명령 전송 [{i+1}/4] → {self.dest_mac} via {sock_mode}, filesize={self.filesize}')
            self.resp = _fw_send_cmd(self.conf_sock, cmd_list, sock_mode.lower(), 2)
            self.logger.info(f'[FW-2] {command} 응답: {repr(self.resp)}')
            if self.resp:
                self.logger.info(f'[FW-2] {command} 응답 수신 성공 → retry loop 종료')
                break

        self.msleep(500)
        self.uploading_size.emit(2)

    def run(self):
        self.setparam()
        assert self.data is not None  # setparam()에서 파일 읽어 bytes로 설정됨
        self.logger.info('=' * 60)
        self.logger.info(f'[FW] 펌웨어 업로드 시작')
        self.logger.info(f'[FW] 장치: {self.dest_mac} ({self.mn_list})')
        self.logger.info(f'[FW] 파일: {self.bin_filename} ({self.filesize} bytes)')
        self.logger.info(f'[FW] 소켓: {self.sock_type}')
        self.logger.info('=' * 60)

        # wiz2000/wiz510ssl: not use 'AB' command
        if self.mn_list in SECURITY_DEVICE:
            self.logger.info(f'[FW-1] SECURITY_DEVICE → AB 명령 생략')
        else:
            self.jumpToApp()

        if 'UDP' in self.sock_type:
            self.logger.info('[FW] UDP broadcast 소켓 사용 (FW 프로토콜)')
        elif 'TCP' in self.sock_type:
            self.logger.info('[FW] TCP unicast 소켓 재구성...')
            self.sock_close()
            self.SocketConfig()

        self.sendCmd('FW')

        parsed = None
        if isinstance(self.resp, bytes) and self.resp != b'':
            parsed = _parse_fw_response(self.resp)
            if parsed is not None:
                self.serverip, self.serverport = parsed
                self.logger.info(f'[FW-2] FW 응답 파싱: IP={self.serverip}, Port={self.serverport}')
                self.uploading_size.emit(3)
            else:
                self.logger.error('[FW-2] FAIL: FW 응답 파싱 실패 → 펌웨어 업로드 중단')
                self.error_flag.emit(-1)
                self.error_noresponse = -1
        else:
            self.logger.warning('[FW-2] FAIL: FW 명령 4회 시도 모두 응답 없음 → 장치가 펌웨어 모드로 진입하지 않았을 가능성')
            self.error_flag.emit(-1)
            self.error_noresponse = -1
        try:
            if parsed is not None:
                self.logger.info(f'[FW-3] TCPClient 생성: {self.serverip}:{self.serverport}')
                self.client = TCPClient(2, self.serverip, self.serverport)
        except Exception as e:
            self.logger.error(f'[FW-3] TCPClient 생성 실패: {e}')
            self.error_noresponse = -1
        try:
            if self.error_noresponse < 0:
                pass
            elif self.client is None:
                self.logger.error('[FW-3] client not initialized, aborting')
            else:
                total_chunks = (self.filesize + FW_PACKET_SIZE - 1) // FW_PACKET_SIZE
                self.logger.info(f'[FW-3] TCP connect 시도 시작 (최대 7회) → {self.serverip}:{self.serverport}')
                # print("%r\r\n" % self.client.state)
                while True:
                    if self.retrycheck > 6:
                        self.logger.warning(f'[FW-3] FAIL: TCP connect 7회 실패 → {self.serverip}:{self.serverport} 응답 없음')
                        break

                    self.retrycheck += 1
                    self.logger.info(f'[FW-3] TCP retry {self.retrycheck}/7 → {self.serverip}:{self.serverport}, state={self.client.state}')
                    if self.client.state == SockState.SOCK_CLOSE:
                        if self.timer1 is not None:
                            self.timer1.cancel()
                        # cur_state = self.client.state
                        try:
                            self.client.open()
                            # self.logger.debug('1 : %r' % self.client.getsockstate())
                            # print("%r\r\n" % self.client.state)
                            if self.client.state == SockState.SOCK_OPEN:
                                self.logger.info(f'[FW-3] 소켓 OPEN 완료, 500ms 대기 후 connect 시도...')
                                # print('[%r] client.working_state == %r' % (self.serverip, self.client.working_state))
                                self.msleep(500)
                        except Exception as e:
                            self.logger.error(f'[FW-3] open() 오류: {e}')

                    elif self.client.state == SockState.SOCK_OPEN:
                        self.uploading_size.emit(4)
                        # cur_state = self.client.state
                        self.logger.info(f'[FW-3] TCP connect() 호출 중... ({self.serverip}:{self.serverport})')
                        try:
                            self.client.connect()
                            # self.logger.debug('2 : %r' % self.client.getsockstate())
                            if self.client.state == SockState.SOCK_CONNECT:
                                self.logger.info(f'[FW-3] TCP CONNECTED! → {self.serverip}:{self.serverport}')
                                # print('[%r] client.working_state == %r' % (self.serverip, self.client.working_state))
                            else:
                                self.logger.warning(f'[FW-3] connect() 완료 but state={self.client.state} (기대: SOCK_CONNECT)')
                        except Exception as e:
                            self.logger.error(f'[FW-3] connect() 오류: {e}')

                    elif self.client.state == SockState.SOCK_CONNECT:
                        # if self.client.working_state == idle_state:
                        #    self.logger.debug('3 : %r' % self.client.getsockstate())
                        try:
                            self.uploading_size.emit(5)
                            self.logger.info(f'[FW-4] 데이터 전송 시작: {self.filesize} bytes, ~{total_chunks} 청크 ({FW_PACKET_SIZE}B/청크)')
                            while self.remainbytes != 0:
                                if self.client.working_state == idle_state:
                                    if self.remainbytes >= FW_PACKET_SIZE:
                                        msg = bytearray(FW_PACKET_SIZE)
                                        msg[:] = self.data[self.curr_ptr:self.curr_ptr +
                                                           FW_PACKET_SIZE]
                                        self.client.write(msg)
                                        self.sentbyte = FW_PACKET_SIZE
                                        # print('FW_PACKET_SIZE bytes sent from at %r' % (self.curr_ptr))
                                        self.logger.info(f'[FW-4] 청크 전송: offset={self.curr_ptr}, size={FW_PACKET_SIZE}, 남은={self.remainbytes - FW_PACKET_SIZE}')
                                        self.curr_ptr += FW_PACKET_SIZE
                                        self.remainbytes -= FW_PACKET_SIZE
                                    else:
                                        self.uploading_size.emit(6)
                                        msg = bytearray(self.remainbytes)
                                        msg[:] = self.data[self.curr_ptr:self.curr_ptr +
                                                           self.remainbytes]
                                        self.client.write(msg)
                                        # print('Last %r byte sent from at %r ' % (self.remainbytes, self.curr_ptr))
                                        self.logger.info(f'[FW-4] 마지막 청크 전송: offset={self.curr_ptr}, size={self.remainbytes}')
                                        self.curr_ptr += self.remainbytes
                                        self.remainbytes = 0
                                        self.sentbyte = self.remainbytes

                                    self.client.working_state = datasent_state

                                    self.timer1 = threading.Timer(3.0, self.myTimer)
                                    self.timer1.start()

                                elif self.client.working_state == datasent_state:
                                    # self.logger.debug('4 : %r' % self.client.getsockstate())
                                    response = self.client.readbytes(2)
                                    if response is not None:
                                        if int(binascii.hexlify(response), 16):
                                            self.logger.info(f'[FW-4] 청크 ACK 수신, ptr={self.curr_ptr}')
                                            self.client.working_state = idle_state
                                            if self.timer1 is not None:
                                                self.timer1.cancel()
                                            self.istimeout = 0
                                        else:
                                            self.logger.error(f'[FW-4] FAIL: 장치 오류 응답 (ptr={self.curr_ptr})')
                                            self.client.close()
                                            if self.timer1 is not None:
                                                self.timer1.cancel()
                                            self.upload_result.emit(-1)
                                            self.terminate()

                                    if self.istimeout == 1:
                                        self.logger.warning(f'[FW-4] 청크 ACK timeout (ptr={self.curr_ptr}, 3초 초과)')
                                        self.istimeout = 0
                                        self.client.working_state = idle_state
                                        self.client.close()
                                        if self.timer1 is not None:
                                            self.timer1.cancel()
                                        self.upload_result.emit(-1)
                                        self.terminate()

                                self.uploading_size.emit(7)
                            self.logger.info(f'[FW-4] 데이터 루프 완료: 전송={self.curr_ptr}/{self.filesize} bytes, working_state={self.client.working_state}')
                        except Exception as e:
                            self.logger.error(f'[FW-4] 데이터 전송 예외: {e}')
                            response = ""
                        break

            self.logger.info('retrycheck: %d' % self.retrycheck)

            if self.retrycheck > 6 or self.error_noresponse < 0:
                self.logger.error(f'[FW] FAIL: Device [{self.dest_mac}] firmware upload failed.')
                self.upload_result.emit(-1)
            elif self.error_noresponse >= 0:
                self.uploading_size.emit(8)
                self.logger.info(f'[FW] SUCCESS: Device [{self.dest_mac}] 펌웨어 업로드 완료!')
                self.upload_result.emit(1)
                # send FIN packet
                self.logger.info('[FW] FIN 전송 (500ms 대기 후)...')
                self.msleep(500)
                if self.client is not None:
                    self.client.shutdown()
                    self.logger.info('[FW] client.shutdown() 완료')
                if 'TCP' in self.sock_type and self.conf_sock is not None:
                    self.conf_sock.close()
                    self.logger.info('[FW] conf_sock.close() 완료')
        except Exception as e:
            self.error_flag.emit(-3)
            self.logger.error(f'[FW] 예외 발생: {e}')
        finally:
            if self.timer1 is not None:
                self.timer1.cancel()

    def sock_close(self):
        # 기존 연결 fin
        if self.tcp_sock is not None:
            if self.tcp_sock.state != SockState.SOCK_CLOSE:
                self.tcp_sock.shutdown()
        if self.conf_sock is not None:
            self.conf_sock.close()

    def tcpConnection(self, serverip, port):
        retrynum = 0
        self.tcp_sock = TCPClient(2, serverip, port)
        self.logger.debug('sock state: %r' % (self.tcp_sock.state))

        while True:
            if retrynum > 6:
                break
            retrynum += 1

            if self.tcp_sock.state == SockState.SOCK_CLOSE:
                self.tcp_sock.shutdown()
                # cur_state = self.tcp_sock.state
                try:
                    self.tcp_sock.open()
                    if self.tcp_sock.state == SockState.SOCK_OPEN:
                        self.logger.info('[%r] is OPEN' % (serverip))
                    time.sleep(0.5)
                except Exception as e:
                    self.logger.error(str(e))
            elif self.tcp_sock.state == SockState.SOCK_OPEN:
                # cur_state = self.tcp_sock.state
                try:
                    self.tcp_sock.connect()
                    if self.tcp_sock.state == SockState.SOCK_CONNECT:
                        self.logger.info('[%r] is CONNECTED' % (serverip))
                except Exception as e:
                    self.logger.error(str(e))
            elif self.tcp_sock.state == SockState.SOCK_CONNECT:
                break
        if retrynum > 6:
            self.logger.info('Device [%s] TCP connection failed.' % (serverip))
            return None
        else:
            self.logger.info('Device [%s] TCP connected' % (serverip))
            return self.tcp_sock

    def SocketConfig(self):
        # Broadcast
        if 'UDP' in self.sock_type:
            self.conf_sock = WIZUDPSock(5000, 50001)
            self.conf_sock.open()

        # TCP unicast
        elif 'TCP' in self.sock_type:
            self.logger.info(f'Upload with TCP unicast: ip: {self.ip_addr}, port: {self.port}')
            self.conf_sock = self.tcpConnection(self.ip_addr, self.port)

            if self.conf_sock is None:
                # self.isConnected = False
                self.logger.warning('TCP connection failed!: %s' % self.conf_sock)
                self.error_flag.emit(-2)
                self.terminate()
            else:
                self.isConnected = True
