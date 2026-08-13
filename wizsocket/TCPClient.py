#!/usr/bin/python

import socket
import time
import select

import sys

sys.path.append("..")

from constants import SockState
from utils import logger, socket_exception_handler

TIMEOUT = 10
# MAXBUFLEN = 1024
MAXBUFLEN = 2048

idle_state = 1


class TCPClient:
    def __init__(self, timeout, ipaddr, portnum, logger=logger):
        self.logger = logger

        self.dst_ip = ipaddr
        self.dst_port = portnum
        self.src_port = 0
        self.sock = 0
        self.rcvbuf = bytearray(MAXBUFLEN)
        self.buflen = 0
        self.rcvd = ""
        self.state = SockState.SOCK_CLOSE
        self.timeout = timeout
        self.time = time.time()
        self.retrycount = 0
        self.working_state = idle_state
        self.str_list = []

    def getsockstate(self):
        return self.sock

    @socket_exception_handler(logger)
    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(0)
        self.state = SockState.SOCK_OPEN
        return SockState.SOCK_OPEN

    @socket_exception_handler(logger)
    def connect(self):
        self.sock.settimeout(3)
        try:
            self.sock.connect((self.dst_ip, self.dst_port))
            self.state = SockState.SOCK_CONNECT
            return SockState.SOCK_CONNECT
        except socket.error as err:
            self.logger.error(err)
            self.sock.close()
            self.sock = 0
            self.state = SockState.SOCK_CLOSE
            return SockState.SOCK_CLOSE

    @socket_exception_handler(logger)
    def readline(self):
        # self.logger.debug("readline() called\r\n")

        if self.buflen > 0:
            index = self.rcvbuf.find("\r", 0, self.buflen)

            if index != -1:
                retval = self.rcvbuf[0 : index + 1]
                self.rcvbuf[0:] = self.rcvbuf[index + 1 :]
                self.buflen -= index + 1
                self.time = time.time()
                return retval

        inputready, outputready, exceptready = select.select(
            [self.sock], [], [], self.timeout
        )

        for i in inputready:
            if i == self.sock:
                tmpbuf = ""
                try:
                    tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
                except socket.error:
                    self.sock = None
                    self.state = SockState.SOCK_CLOSE
                    self.working_state = idle_state
                    self.buflen = 0
                    return ""

                self.rcvbuf[self.buflen :] = tmpbuf
                self.buflen += len(tmpbuf)
                index = self.rcvbuf.find(b"\r", 0, self.buflen)
                if index != -1:
                    retval = self.rcvbuf[0 : index + 1]
                    self.rcvbuf[0:] = self.rcvbuf[index + 1 :]
                    self.buflen -= index + 1
                    self.time = time.time()
                    return retval

        cur_time = time.time()

        if (cur_time - self.time) > 2.0:
            if self.buflen > 0:
                retval = self.rcvbuf[0 : self.buflen]
                self.buflen = 0
                self.time = time.time()
                return retval
            self.time = time.time()

        return ""

    @socket_exception_handler(logger)
    def readbytes(self, length):
        if self.buflen > 0:
            if self.buflen >= length:
                retbuf = self.rcvbuf[:length]
                self.rcvbuf[0:] = self.rcvbuf[length:]
                self.buflen -= length
            else:
                retbuf = self.rcvbuf[: self.buflen]
                self.buflen = 0

            return retbuf
        else:
            inputready, outputready, exceptready = select.select([self.sock], [], [], 0)

            for i in inputready:
                if i == self.sock:
                    # sys.stdout.write("select activated\r\n")
                    try:
                        tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
                    except socket.error:
                        self.sock = None
                        self.state = SockState.SOCK_CLOSE
                        self.working_state = idle_state
                        self.buflen = 0
                        return None

                    self.rcvbuf[self.buflen :] = tmpbuf
                    self.buflen += len(tmpbuf)

            # return retval
            return None

    @socket_exception_handler(logger)
    def read(self):
        if self.buflen > 0:
            retval = "%c" % self.rcvbuf[0]
            self.rcvbuf[0:] = self.rcvbuf[1:]
            self.buflen -= 1

            return retval
        else:
            inputready, outputready, exceptready = select.select([self.sock], [], [], 0)
            for i in inputready:
                if i == self.sock:
                    try:
                        tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
                    except socket.error:
                        self.sock = None
                        self.state = SockState.SOCK_CLOSE
                        self.working_state = idle_state
                        self.buflen = 0
                        return ""

                    self.rcvbuf[self.buflen :] = tmpbuf
                    self.buflen += len(tmpbuf)

                    if len(self.rcvbuf) > 0:
                        retval = "%c" % self.rcvbuf[0]
                        self.rcvbuf[0:] = self.rcvbuf[1:]
                        self.buflen -= 1

                        return retval
            return ""

    @socket_exception_handler(logger)
    def write(self, data):
        self.sock.send(data)

    @socket_exception_handler(logger)
    def recvfrom(self):
        """(data, addr) 튜플 반환 — WIZUDPSock.recvfrom()과 동일 계약.

        WIZMSGHandler 등이 UDP/TCP 소켓을 다형적으로 다루며
        `data, addr = sock.recvfrom()`으로 언팩하므로 반환 형태가
        일치해야 한다. 과거에는 data 단독 반환이라 TCP 검색 경로에서
        "too many values to unpack" 크래시 발생 (issue #67 실기기 검증
        중 발견 — bytes를 변수 2개에 언팩 시도).
        """
        data, addr = self.sock.recvfrom(2048)
        return data, addr

    def close(self):
        if self.sock != 0:
            self.sock.close()
        self.state = SockState.SOCK_CLOSE

    def shutdown(self):
        if self.sock != 0:
            self.sock.shutdown(1)
