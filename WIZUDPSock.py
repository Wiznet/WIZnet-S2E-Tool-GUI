#!/usr/bin/python

import socket
import time
import struct
import binascii
import select
import sys
import threading
from random import randint

# for command set/get

class WIZUDPSock:
    # def __init__(self, port, peerport):
    def __init__(self, port, peerport, ipaddr=None):
        self.sock = None
        # self.localport = randint(52000, 53000)
        self.localport = 52000
        self.peerport = peerport
        self.ipaddr = ipaddr

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # socket rcv buffer size
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)  # 512 KB
        # print('getsockopt SO_RCVBUF:', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))

        # self.sock.bind(("", self.localport))
        self.sock.bind((self.ipaddr, self.localport))
        self.sock.setblocking(0)

    def sendto(self, msg):
        self.sock.sendto(msg, ("255.255.255.255", self.peerport))
        # self.sock.sendto(msg, ("192.168.50.255", self.peerport))

    def recvfrom(self):
        data, addr = self.sock.recvfrom(2048)
        return data

    def close(self):
        self.sock.close()
