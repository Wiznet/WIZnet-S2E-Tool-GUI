#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket
import time
import select
import sys
sys.path.append('..')

from constants import SockState
from utils import logger, socket_exception_handler

TIMEOUT = 10
MAXBUFLEN = 1024

idle_state = 1

SockState.SOCK_CLOSE = 10
SockState.SOCK_OPENTRY = 11
SockState.SOCK_OPEN = 12
SockState.SOCK_CONNECTTRY = 13
SockState.SOCK_CONNECT = 14


class TCPServer:
    def __init__(self, timeout, ipaddr, portnum, logger=logger):
        self.logger = logger

        self.ip_addr = ipaddr
        self.port = portnum
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

        self.connection_list = []
        self.cli_sock = None
        self.cli_addr = None

    def getsockstate(self):
        return self.sock

    @socket_exception_handler(logger)
    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        # sys.stdout.write('socket.socket() called\r\n')
        self.sock.bind((self.ip_addr, self.port))
        print("<TCP Server> Bind")
        self.sock.listen(0)  # 연결 가능한 client 수 (0: 무제한?)
        print("<TCP Server> Listen")

        self.connection_list.append(self.sock)
        self.state = SockState.SOCK_OPEN
        return SockState.SOCK_OPEN

    # block method, 수신대기 => send / recv
    @socket_exception_handler(logger)
    def connect(self):
        print("Waiting for connection...")
        self.cli_sock, self.cli_addr = self.sock.accept()
        self.connection_list.append(self.cli_sock)
        print("<TCP Server> Accept client:", self.cli_addr)

        self.state = SockState.SOCK_CONNECT
        return SockState.SOCK_CONNECT

    @socket_exception_handler(logger)
    def readline(self):
        if self.buflen > 0:
            index = self.rcvbuf.find("\r", 0, self.buflen)
            # for i in range(0, self.buflen):
                # self.logger.debug("[%d]" % i)
                # self.logger.debug("%d" % self.rcvbuf[0])

            if index != -1:
                retval = self.rcvbuf[0: index + 1]
                self.rcvbuf[0:] = self.rcvbuf[index + 1:]
                self.buflen -= index + 1
                self.time = time.time()
                return retval

        inputready, outputready, exceptready = select.select([self.cli_sock], [], [], self.timeout)

        for i in inputready:
            if i == self.cli_sock:
                tmpbuf = ""
                try:
                    tmpbuf = self.cli_sock.recv(MAXBUFLEN - self.buflen)
                except socket.error:
                    self.cli_sock = None
                    self.state = SockState.SOCK_CLOSE
                    self.working_state = idle_state
                    self.buflen = 0
                    return ""

                self.rcvbuf[self.buflen:] = tmpbuf
                self.buflen += len(tmpbuf)

                index = self.rcvbuf.find("\r", 0, self.buflen)
                if index != -1:
                    retval = self.rcvbuf[0: index + 1]
                    self.rcvbuf[0:] = self.rcvbuf[index + 1:]
                    self.buflen -= index + 1
                    self.time = time.time()
                    return retval

        cur_time = time.time()

        if (cur_time - self.time) > 2.0:
            if self.buflen > 0:
                retval = self.rcvbuf[0: self.buflen]
                self.buflen = 0
                self.time = time.time()
                return retval
            self.time = time.time()

        return ""

    @socket_exception_handler(logger)
    def write(self, data):
        self.cli_sock.send(data)

    @socket_exception_handler(logger)
    def close(self):
        if self.sock != 0:
            self.sock.close()
        self.state = SockState.SOCK_CLOSE
