#!/usr/bin/python

import socket
import time
import struct
import binascii
import select
import sys
import threading

# for command set/get
class WIZUDPSock:
	def __init__(self, port, peerport):
		self.sock = None
		self.localport = port
		self.peerport = peerport
		
	def open(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		# self.sock.bind(("", self.localport))
		self.sock.setblocking(0)
		
	def sendto(self, msg):
		self.sock.sendto(msg, ("255.255.255.255", self.peerport))		
		
	def recvfrom(self):
		data, addr = self.sock.recvfrom(2048)
		return data
		
	def close(self):
		self.sock.close()
