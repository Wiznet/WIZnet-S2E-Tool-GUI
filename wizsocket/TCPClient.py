#!/usr/bin/python

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

class TCPClient:
	def __init__(self, timeout, ipaddr, portnum):
		import logging
		logging.basicConfig(level=logging.DEBUG)
		self.logger = logging.getLogger()
		
		self.dst_ip = ipaddr
		self.dst_port = portnum
		self.src_port = 0
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

	def getsockstate(self):
		return self.sock

	def open(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setblocking(0)
		# sys.stdout.write('socket.socket() called\r\n')
#		self.src_port = src_port
#		self.sock.bind(('', self.src_port))
		self.state = OPEN_STATE
		return OPEN_STATE
			
	def connect(self):
		self.sock.settimeout(10)
		try:
			self.sock.connect((self.dst_ip, self.dst_port))
			self.state = CONNECT_STATE
			return CONNECT_STATE
		except socket.error as msg:
			self.sock.close()
			self.sock = 0
			self.state = CLOSE_STATE
			return CLOSE_STATE

	def readline(self):
#		self.logger.debug("readline() called\r\n")
		
		if self.buflen > 0:
			index = self.rcvbuf.find("\r", 0, self.buflen)
#			for i in range(0, self.buflen):
#				self.logger.debug("[%d]" % i)
#				self.logger.debug("%d" % self.rcvbuf[0])
			
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
				

		inputready, outputready, exceptready = select.select([self.sock], [], [], self.timeout)

		for i in inputready:
			if i == self.sock:
				tmpbuf = ""
				try:
					tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
				except socket.error:
					self.sock = None
					self.state = CLOSE_STATE
					self.working_state = idle_state
					self.buflen = 0
					return ""
					
#				sys.stdout.write("tmpbuf: ")
#				sys.stdout.write(tmpbuf)
#				sys.stdout.flush()
#				self.logger.debug("tmpbuf: %s\r\n" % tmpbuf)
				self.rcvbuf[self.buflen:] = tmpbuf
#				self.logger.debug("1 buflen: %d\r\n" % self.buflen)
				self.buflen += len(tmpbuf)
#				self.logger.debug("2 buflen: %d\r\n" % self.buflen)
			
				index = self.rcvbuf.find(b"\r", 0, self.buflen)
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

	def readbytes(self, length):
		if self.buflen > 0:
			if self.buflen >= length:
				retbuf = self.rcvbuf[:length]
				self.rcvbuf[0:] = self.rcvbuf[length:]
				self.buflen -= length
			else:
				retbuf = self.rcvbuf[:self.buflen]
				self.buflen = 0
		
			return retbuf
		else:
			inputready, outputready, exceptready = select.select([self.sock], [], [], 0)

#		sys.stdout.write("%r\r\n" % inputready)		
#		sys.stdout.write("%r\r\n" % self.sock)
			for i in inputready:
				if i == self.sock:
#					sys.stdout.write("select activated\r\n")
					try:
						tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
					except socket.error:
						self.sock = None
						self.state = CLOSE_STATE
						self.working_state = idle_state
						self.buflen = 0
						return None
						
#					sys.stdout.write("tmpbuf: ")
#					sys.stdout.write(tmpbuf)
#					sys.stdout.flush()
					self.rcvbuf[self.buflen:] = tmpbuf
					self.buflen += len(tmpbuf)
					
# 					if len(self.rcvbuf) > 0:
# 						retval = "%c" % self.rcvbuf[0]
# #						sys.stdout.write("rcvbuf: ")
# #						sys.stdout.write(self.rcvbuf)
# 						self.rcvbuf[0:] = self.rcvbuf[1:]
# #						sys.stdout.write("rcvbuf: ")
# #						sys.stdout.write(self.rcvbuf)
# #						sys.stdout.flush()
# 						self.buflen -= 1
			
						# return retval
			return None


	def read(self):
		if self.buflen > 0:
			retval = "%c" % self.rcvbuf[0]
#			sys.stdout.write("rcvbuf: ")
#			sys.stdout.write(self.rcvbuf)
			self.rcvbuf[0:] = self.rcvbuf[1:]
#			sys.stdout.write("rcvbuf: ")
#			sys.stdout.write(self.rcvbuf)
#			sys.stdout.flush()
			self.buflen -= 1
			
			return retval
		else:
			inputready, outputready, exceptready = select.select([self.sock], [], [], 0)

#		sys.stdout.write("%r\r\n" % inputready)		
#		sys.stdout.write("%r\r\n" % self.sock)
			for i in inputready:
				if i == self.sock:
#					sys.stdout.write("select activated\r\n")
					try:
						tmpbuf = self.sock.recv(MAXBUFLEN - self.buflen)
					except socket.error:
						self.sock = None
						self.state = CLOSE_STATE
						self.working_state = idle_state
						self.buflen = 0
						return ''
						
#					sys.stdout.write("tmpbuf: ")
#					sys.stdout.write(tmpbuf)
#					sys.stdout.flush()
					self.rcvbuf[self.buflen:] = tmpbuf
					self.buflen += len(tmpbuf)
					
					if len(self.rcvbuf) > 0:
						retval = "%c" % self.rcvbuf[0]
#						sys.stdout.write("rcvbuf: ")
#						sys.stdout.write(self.rcvbuf)
						self.rcvbuf[0:] = self.rcvbuf[1:]
#						sys.stdout.write("rcvbuf: ")
#						sys.stdout.write(self.rcvbuf)
#						sys.stdout.flush()
						self.buflen -= 1
			
						return retval
			return ''
		
	def write(self, data):
		self.sock.send(data)
		
	def close(self):
		if self.sock is not 0:
			self.sock.close()
		self.state = CLOSE_STATE
	
	def shutdown(self):
		self.sock.shutdown(1)
		
# if __name__ == '__main__':
# 	client = TCPClient()
#
# 	print(client.state)
#
# 	while True:
#
#
# 		if client.state is CLOSE_STATE:
# 			cur_state = client.state
# 			client.state = client.open(5001)
# 			if client.state != cur_state:
# 				sys.stdout.write('%r\r\n' % client.state)
# #			client.state = OPENTRY_STATE
#
# 		elif client.state is OPEN_STATE:
# 			cur_state = client.state
# 			client.state = client.connect("192.168.11.235", 9000)
# 			if client.state != cur_state:
# 				sys.stdout.write('%r\r\n' % client.state)
#
# 		elif client.state is CONNECT_STATE:
# #			sys.stdout.write("check readline()\r\n")
# #			if inputready:
# 			rcvddata = client.readline()
# #			print rcvddata
# 			if rcvddata != -1 :
# 				sys.stdout.write("%s" % rcvddata)
# #				for i in range(0, len(rcvddata)):
# #					sys.stdout.write("%d " % rcvddata[i])
# #				sys.stdout.write("\r\n")
# 				sys.stdout.flush()
# #				client.write(rcvddata)
#
# 		time.sleep(1)
