#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket
import time
import struct
import binascii
import select
import sys

TIMEOUT=10
MAXBUFLEN = 1024

idle_state = 1

CLOSE_STATE = 1
OPENTRY_STATE = 2
OPEN_STATE = 3
CONNECTTRY_STATE = 4
CONNECT_STATE = 5
# CLOSE_STATE = 1
# OPENTRY_STATE = 2
# OPEN_STATE = 3
# LISTEN_STATE = 4
# ACCEPT_STATE = 5

class TCPServer:
	def __init__(self, timeout, ipaddr, portnum):
		import logging
		logging.basicConfig(level=logging.DEBUG)
		self.logger = logging.getLogger()
		
		self.ip_addr = ipaddr
		self.port = portnum
		self.sock = 0
		self.rcvbuf = bytearray(MAXBUFLEN)
		self.buflen = 0
		self.rcvd = ""
		self.state = CLOSE_STATE
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

	def open(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.setblocking(0)
		# sys.stdout.write('socket.socket() called\r\n')
		self.sock.bind((self.ip_addr, self.port))
		print('<TCP Server> Bind')
		self.sock.listen(0)	# 연결 가능한 client 수 (0: 무제한?)
		print('<TCP Server> Listen')

		self.connection_list.append(self.sock)
		self.state = OPEN_STATE
		return OPEN_STATE
	
	# block method, 수신대기 => send / recv
	# def accept(self):
	def connect(self):
		print('Waiting for connection...')
		self.cli_sock, self.cli_addr = self.sock.accept()
		self.connection_list.append(self.cli_sock)
		print('<TCP Server> Accept client:', self.cli_addr)

		self.state = CONNECT_STATE
		return CONNECT_STATE

	def readline(self):
		# self.logger.debug("readline() called\r\n")
		
		if self.buflen > 0:
			index = self.rcvbuf.find("\r", 0, self.buflen)
			for i in range(0, self.buflen):
				self.logger.debug("[%d]" % i)
				self.logger.debug("%d" % self.rcvbuf[0])
			
			if index != -1:
#				self.logger.debug("3 buflen: %d\r\n" % self.buflen)
				retval = self.rcvbuf[0:index+1]
				self.rcvbuf[0:] = self.rcvbuf[index+1:]
				self.buflen -= index+1
#				self.logger.debug("4 buflen: %d\r\n" % self.buflen)
#				self.logger.debug("1. start time: %r\r\n" % self.time)
#				self.logger.debug("1. readline: %r" % retval)
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
					self.state = CLOSE_STATE
					self.working_state = idle_state
					self.buflen = 0
					return ""
					
				# print('tmpbuf:', tmpbuf)
#				self.logger.debug("tmpbuf: %s\r\n" % tmpbuf)
				self.rcvbuf[self.buflen:] = tmpbuf
#				self.logger.debug("1 buflen: %d\r\n" % self.buflen)
				self.buflen += len(tmpbuf)
#				self.logger.debug("2 buflen: %d\r\n" % self.buflen)
			
				index = self.rcvbuf.find("\r", 0, self.buflen)
				if index != -1:
#					sys.stdout.write("index %d\r\n" % index)
					retval = self.rcvbuf[0:index+1]
					self.rcvbuf[0:] = self.rcvbuf[index+1:]
					self.buflen -= index+1
					self.time = time.time()	
#					self.logger.debug("2. start time: %r\r\n" % self.time)
#					self.logger.debug("2. readline: %r" % retval)
					return retval
			
		cur_time = time.time()
#		self.logger.debug("start time: %r\r\n" % self.time)
#		self.logger.debug("cur time: %r\r\n" % cur_time)
#		self.logger.debug("time interval: %r\r\n" % (cur_time - self.time))
#		self.logger.debug("buf: %r\r\n" % self.rcvbuf[0:self.buflen])
			
		if((cur_time - self.time) > 2.0):
			if(self.buflen > 0):
				retval = self.rcvbuf[0:self.buflen]
				self.buflen = 0
				self.time = time.time()
				return retval
			self.time = time.time()
			
		return ""	
				
	def write(self, data):
		# self.sock.send(data)
		self.cli_sock.send(data)
		
	def close(self):
		if self.sock is not 0:
		    self.sock.close()
		self.state = CLOSE_STATE
