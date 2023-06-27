#!/usr/bin/python

import codecs
import threading
import select
import os

from PyQt5 import QtCore
from utils import logger

# from wizsocket.TCPClient import TCPClient
# from WIZUDPSock import WIZUDPSock
# from WIZMSGHandler import WIZMSGHandler

SOCK_CLOSE_STATE = 11
SOCK_OPENTRY_STATE = 12
SOCK_OPEN_STATE = 13
SOCK_CONNECTTRY_STATE = 14
SOCK_CONNECT_STATE = 15

idle_state = 1
datasent_state = 2

DELIMITER = "\r\n"

# PACKET_SIZE = 1200
PACKET_SIZE = 1024
# PACKET_SIZE = 2048


class certificatethread(QtCore.QThread):
    uploading_size = QtCore.pyqtSignal(int)
    upload_result = QtCore.pyqtSignal(int)
    error_flag = QtCore.pyqtSignal(int)

    def __init__(self, sock, dest_mac, idcode, set_pw, filename, ipaddr, port, dev_name, cmd):
        QtCore.QThread.__init__(self)

        self.logger = logger

        self.dest_mac = None
        self.bin_cert_name = filename
        self.fd = None
        self.data = None
        self.client = None
        self.timer1 = None
        self.istimeout = 0
        self.serverip = ipaddr
        self.serverport = port
        self.sentbyte = 0
        self.dest_mac = dest_mac
        self.idcode = idcode
        self.error_noresponse = 0
        self.retrycheck = 0

        self.header = bytearray(128)
        self.header_size = 0

        self.msg = bytearray(PACKET_SIZE)
        self.size = 0

        self.sock = sock
        self.what_sock = '%s' % self.sock

        try:
            self.inputs = [self.sock.sock]
        except Exception as e:
            print('socket error:', e)
            self.terminate()

        self.outputs = []
        self.errors = []

        # device name
        self.dev_name = dev_name
        self.set_pw = set_pw
        # self.cert = cert
        self.cmd = cmd
        self.curr_ptr = 0

        # self.cert_size = len(self.cert)
        self.remainbytes = 0
        self.filesize = 0

        self.ip_addr = ipaddr
        self.port = port

        self.cli_sock = None

    def setparam(self):
        # Read file data
        self.fd = open(self.bin_cert_name, "rb")
        self.data = self.fd.read(-1)
        self.remainbytes = len(self.data)
        self.filesize = len(self.data)
        print('remainbytes:', self.remainbytes)
        self.curr_ptr = 0
        self.fd.close()

    def myTimer(self):
        # print('timer1 timeout\r\n')
        self.istimeout = 1

    def make_header_commands(self):
        cmd_list = []

        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", self.idcode])

        try:
            for cmd in cmd_list:
                # print('cmd[0]: %s, cmd[1]: %s' % (cmd[0], cmd[1]))
                try:
                    self.msg[self.size:] = str.encode(cmd[0])
                except Exception as e:
                    self.logger.error('[ERROR] make_header_commands() encode:', cmd[0], e)
                self.size += len(cmd[0])
                if cmd[0] == "MA":
                    # print('cmd[1]: %r' % cmd[1])
                    cmd[1] = cmd[1].replace(":", "")
                    # print(cmd[1])
                    # hex_string = cmd[1].decode('hex')
                    try:
                        hex_string = codecs.decode(cmd[1], 'hex')
                    except Exception as e:
                        self.logger.error('[ERROR] make_header_commands() decode:', cmd[0], cmd[1], e)

                    self.msg[self.size:] = hex_string
                    self.dest_mac = hex_string
                    # self.dest_mac = (int(cmd[1], 16)).to_bytes(6, byteorder='big') # Hexadecimal string to hexadecimal binary
                    # self.msg[self.size:] = self.dest_mac
                    self.size += 6
                else:
                    try:
                        self.msg[self.size:] = str.encode(cmd[1])
                    except Exception as e:
                        self.logger.error('[ERROR] make_header_commands() encode param:', cmd[0], cmd[1], e)
                    self.size += len(cmd[1])
                if DELIMITER not in cmd[1]:
                    self.msg[self.size:] = str.encode(DELIMITER)
                    self.size += 2

                    # print(self.size, self.msg)
        except Exception as e:
            self.logger.error(f'[ERROR] WIZMSGHandler make_header_commands(): {str(e)}')

    #     self.msleep(500)
    #     self.uploading_size.emit(2)

    def add_get_command(self):
        try:
            cmd = self.cmd + DELIMITER
            self.msg[self.size:] = str.encode(cmd)
            self.size += len(cmd)
        except Exception as e:
            self.logger.error(str(e))

    def run(self):
        self.setparam()
        self.logger.info(f'Certificate upload start: {self.dev_name}')

        self.make_header_commands()

        try:
            if self.error_noresponse < 0:
                self.logger.error(f'error_noresponse: {self.error_noresponse}')
                pass
            else:
                # print("%r" % self.client.state)
                self.logger.info(f"Header: size: {self.size}, msg: {self.msg}")
                try:
                    additional_size = 0
                    if self.curr_ptr == 0:
                        # header + getcmd + delemiter
                        additional_size = self.size + len(self.cmd) + len(DELIMITER)
                    # print('check size:', PACKET_SIZE - additional_size)

                    if self.filesize < PACKET_SIZE - additional_size:
                        self.logger.info(f"Certificate file size: {self.filesize}")
                        # for WIZ510SSL
                        cmdset = self.cmd + self.data.decode() + DELIMITER
                        self.msg[self.size:] = str.encode(cmdset)
                        self.size += len(cmdset)

                        self.add_get_command()

                        self.sock.sendto(self.msg)
                        self.logger.info('[%s] [%d] bytes sent' % (self.serverip, self.size))
                        self.remainbytes = 0
                    else:
                        while self.remainbytes != 0:
                            if self.remainbytes >= PACKET_SIZE - additional_size:
                                # WIZ510SSL
                                msg = bytearray(PACKET_SIZE)
                                if self.curr_ptr == 0:
                                    # first packet: command + packet
                                    # msg[:] = self.header + self.cmd.encode() + self.data[PACKET_SIZE - len(self.header) - len(self.cmd)]
                                    msg = self.msg
                                    if self.cmd == "UP":
                                        # MA/PW/cmd/size/bin
                                        datasize = PACKET_SIZE - self.size - len(self.cmd) - len(str(self.filesize)) - len(DELIMITER)
                                        msg[self.size:] = str.encode(self.cmd + str(self.filesize) + DELIMITER) + self.data[self.curr_ptr:self.curr_ptr + datasize]
                                    else:
                                        datasize = PACKET_SIZE - self.size - len(self.cmd)
                                        msg[self.size:] = self.cmd.encode() + self.data[self.curr_ptr:self.curr_ptr + datasize]
                                    # print("[1] msg:", msg)
                                    self.sock.sendto(msg)
                                    self.sentbyte = PACKET_SIZE
                                    # print('PACKET_SIZE bytes sent from at %r' % (self.curr_ptr))
                                    self.logger.info('[1] %d bytes sent from at %r' % (PACKET_SIZE, self.curr_ptr))
                                    self.curr_ptr += datasize
                                    self.remainbytes -= datasize
                                else:
                                    msg[:] = self.data[self.curr_ptr:self.curr_ptr + PACKET_SIZE]
                                    # print("[2] msg:", msg)
                                    self.sock.sendto(msg)
                                    self.sentbyte = PACKET_SIZE
                                    # print('PACKET_SIZE bytes sent from at %r' % (self.curr_ptr))
                                    self.logger.info('[2] %d bytes sent from at %r' % (PACKET_SIZE, self.curr_ptr))
                                    self.curr_ptr += PACKET_SIZE
                                    self.remainbytes -= PACKET_SIZE
                            else:
                                self.uploading_size.emit(6)
                                msg = bytearray(self.remainbytes + 4)
                                msg[:] = self.data[
                                    self.curr_ptr:self.curr_ptr + self.remainbytes] + str.encode(self.cmd + DELIMITER)
                                # self.client.write(msg)
                                # print("[3] msg:", msg)
                                self.sock.sendto(msg)
                                # print('Last %r byte sent from at %r' % (self.remainbytes, self.curr_ptr))
                                self.logger.info('[3] Last %r byte sent from at %r' % (self.remainbytes, self.curr_ptr))
                                self.curr_ptr += self.remainbytes
                                self.remainbytes = 0
                                self.sentbyte = self.remainbytes

                        self.timer1 = threading.Timer(2.0, self.myTimer)
                        self.timer1.start()

                    self.uploading_size.emit(7)

                    # Check response
                    if self.remainbytes == 0:
                        replylists = []

                        readready, writeready, errorready = select.select(
                            self.inputs, self.outputs, self.errors, 2)
                        # print('readready value: ', len(readready), readready)

                        for sock in readready:
                            if sock == self.sock.sock:
                                data = self.sock.recvfrom()
                                self.msleep(10)
                                replylists = data.split(DELIMITER.encode())
                                self.logger.debug('replylists:', replylists)

                                if self.cmd.encode() in replylists:
                                    self.uploading_size.emit(8)
                                    self.logger.info('Device [%s] upload success!' % (self.dest_mac))
                                    self.upload_result.emit(1)
                                else:
                                    self.upload_result.emit(-1)
                        if len(replylists) == 0:
                            self.upload_result.emit(-2)

                        self.uploading_size.emit(8)

                except Exception as e:
                    self.logger.error(str(e))
                self.msleep(1)
        except Exception as e:
            self.error_flag.emit(-3)
            self.logger.error(str(e))
        finally:
            pass
