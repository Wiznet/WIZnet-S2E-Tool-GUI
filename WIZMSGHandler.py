#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket
import time
import struct
import binascii
import select
import sys
import codecs
from WIZ750CMDSET import WIZ750CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from wizsocket.TCPClient import TCPClient
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

exitflag = 0

OP_SEARCHALL = 1
OP_GETCOMMAND = 2
OP_SETCOMMAND = 3
OP_SETFILE = 4
OP_GETFILE = 5
OP_FWUP = 6


def timeout_func():
    #	print('timeout')
    global exitflag
    exitflag = 1


class WIZMSGHandler(QThread):
    search_result = pyqtSignal(int)
    set_result = pyqtSignal(int)

    searched_data = pyqtSignal(bytes)

    def __init__(self, udpsock, cmd_list, what_sock, op_code, timeout):
        QThread.__init__(self)

        self.sock = udpsock
        self.msg = bytearray(1024)
        self.size = 0

        try:
            self.inputs = [self.sock.sock]
        except Exception as e:
            print('socket error:', e)
            self.terminate()

        self.outputs = []
        self.errors = []
        self.opcode = None
        self.iter = 0
        self.dest_mac = None
        self.isvalid = False
        # self.timer1 = None
        self.istimeout = False
        self.reply = ''
        self.setting_pw_wrong = False

        self.mac_list = []
        self.mode_list = []
        self.mn_list = []
        self.vr_list = []
        self.getreply = []
        self.rcv_list = []
        self.st_list = []

        self.what_sock = what_sock
        self.cmd_list = cmd_list
        self.opcode = op_code

        self.timeout = timeout

        self.wiz750cmdObj = WIZ750CMDSET(1)

    def timeout_func(self):
        self.istimeout = True

    def makecommands(self):
        self.size = 0

        try:
            for cmd in self.cmd_list:
                # print('cmd[0]: %s, cmd[1]: %s' % (cmd[0], cmd[1]))
                try:
                    self.msg[self.size:] = str.encode(cmd[0])
                except Exception as e:
                    print('[ERROR] makecommands() encode:', cmd[0], e)
                self.size += len(cmd[0])
                if cmd[0] is "MA":
                    # sys.stdout.write('cmd[1]: %r\r\n' % cmd[1])
                    cmd[1] = cmd[1].replace(":", "")
                    # print(cmd[1])
                    # hex_string = cmd[1].decode('hex')
                    try:
                        hex_string = codecs.decode(cmd[1], 'hex')
                    except Exception as e:
                        print('[ERROR] makecommands() decode:',
                              cmd[0], cmd[1], e)

                    self.msg[self.size:] = hex_string
                    self.dest_mac = hex_string
                    # self.dest_mac = (int(cmd[1], 16)).to_bytes(6, byteorder='big') # Hexadecimal string to hexadecimal binary
                    # self.msg[self.size:] = self.dest_mac
                    self.size += 6
                else:
                    try:
                        self.msg[self.size:] = str.encode(cmd[1])
                    except Exception as e:
                        print('[ERROR] makecommands() encode param:',
                              cmd[0], cmd[1], e)
                    self.size += len(cmd[1])
                if not "\r\n" in cmd[1]:
                    self.msg[self.size:] = str.encode("\r\n")
                    self.size += 2

                    # print(self.size, self.msg)
        except Exception as e:
            print('[ERROR] WIZMSGHandler makecommands(): %r' % e)

    def sendcommands(self):
        self.sock.sendto(self.msg)

    def sendcommandsTCP(self):
        self.sock.write(self.msg)

    def check_parameter(self, cmdset):
        # print('check_parameter()', cmdset, cmdset[:2], cmdset[2:])
        try:
            if b'MA' not in cmdset:
                # print('check_parameter() OK', cmdset, cmdset[:2], cmdset[2:])
                if self.wiz750cmdObj.isvalidparameter(cmdset[:2].decode(), cmdset[2:].decode()):
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            print('[ERROR] WIZMSGHandler check_parameter(): %r' % e)

    # def parseresponse(self):
    def run(self):
        try:
            self.makecommands()
            if self.what_sock == 'udp':
                self.sendcommands()
            elif self.what_sock == 'tcp':
                self.sendcommandsTCP()
        except Exception as e:
            print('[ERROR] WIZMSGHandler thread: %r' % e)

        readready, writeready, errorready = select.select(
            self.inputs, self.outputs, self.errors, self.timeout)

        replylists = None
        self.getreply = []
        self.mac_list = []
        self.mn_list = []
        self.vr_list = []
        self.st_list = []
        self.rcv_list = []
        # print('readready value: ', len(readready), readready)

        # Pre-search / Single search
        if self.timeout < 2:
            for sock in readready:
                if sock == self.sock.sock:
                    data = self.sock.recvfrom()
                    self.searched_data.emit(data)
                    replylists = data.splitlines()
                    # print('replylists', replylists)
                    self.getreply = replylists
        else:
            while True:
                self.iter += 1
                # sys.stdout.write("iter count: %r " % self.iter)

                for sock in readready:
                    if sock == self.sock.sock:
                        data = self.sock.recvfrom()

                        #! check if data reduplication
                        if data in self.rcv_list:
                            replylists = []
                        else:
                            self.rcv_list.append(data)  # received data backup
                            replylists = data.splitlines()
                            # print('replylists', replylists)
                            self.getreply = replylists

                        if self.opcode is OP_SEARCHALL:
                            try:
                                for i in range(0, len(replylists)):
                                    if b'MC' in replylists[i]:
                                        if self.check_parameter(replylists[i]):
                                            self.mac_list.append(replylists[i][2:])
                                    if b'MN' in replylists[i]:
                                        if self.check_parameter(replylists[i]):
                                            self.mn_list.append(replylists[i][2:])
                                    if b'VR' in replylists[i]:
                                        if self.check_parameter(replylists[i]):
                                            self.vr_list.append(replylists[i][2:])
                                    if b'OP' in replylists[i]:
                                        if self.check_parameter(replylists[i]):
                                            self.mode_list.append(replylists[i][2:])
                                    if b'ST' in replylists[i]:
                                        if self.check_parameter(replylists[i]):
                                            self.st_list.append(replylists[i][2:])
                            except Exception as e:
                                print(
                                    '[ERROR] WIZMSGHandler makecommands(): %r' % e)
                        elif self.opcode is OP_FWUP:
                            for i in range(0, len(replylists)):
                                if b'MA' in replylists[i][:2]:
                                    dest_mac = self.dest_mac
                                    reply_mac = replylists[i][2:]
                                    # self.isvalid = True
                                else:
                                    self.isvalid = False
                                # sys.stdout.write("%r\r\n" % replylists[i][:2])
                                if b'FW' in replylists[i][:2]:
                                    # sys.stdout.write('self.isvalid is True\r\n')
                                    param = replylists[i][2:].split(b':')
                                    self.reply = replylists[i][2:]
                        elif self.opcode is OP_SETCOMMAND:
                            for i in range(0, len(replylists)):
                                if b'AP' in replylists[i][:2]:
                                    if replylists[i][2:] == b' ':
                                        self.setting_pw_wrong = True
                                    else:
                                        self.setting_pw_wrong = False

                readready, writeready, errorready = select.select(
                    self.inputs, self.outputs, self.errors, 1)

                if not readready or not replylists:
                    break

            if self.opcode is OP_SEARCHALL:
                self.msleep(500)
                # print('Search device:', self.mac_list)
                self.search_result.emit(len(self.mac_list))
                # return len(self.mac_list)
            if self.opcode is OP_SETCOMMAND:
                self.msleep(500)
                # print(self.rcv_list)
                if len(self.rcv_list) > 0:
                    # print('OP_SETCOMMAND: rcv_list:', len(self.rcv_list[0]), self.rcv_list[0])
                    if self.setting_pw_wrong:
                        self.set_result.emit(-3)
                    else:
                        self.set_result.emit(len(self.rcv_list[0]))
                else:
                    self.set_result.emit(-1)
            elif self.opcode is OP_FWUP:
                return self.reply
            # sys.stdout.write("%s\r\n" % self.mac_list)


class DataRefresh(QThread):
    resp_check = pyqtSignal(int)

    def __init__(self, sock, cmd_list, what_sock, interval):
        QThread.__init__(self)

        self.sock = sock
        self.msg = bytearray(1024)
        self.size = 0

        self.inputs = [self.sock.sock]
        self.outputs = []
        self.errors = []

        self.iter = 0
        self.dest_mac = None
        self.reply = ''

        self.mac_list = []
        self.rcv_list = []

        self.what_sock = what_sock
        self.cmd_list = cmd_list
        self.interval = interval * 1000

    def makecommands(self):
        self.size = 0

        for cmd in self.cmd_list:
            self.msg[self.size:] = str.encode(cmd[0])
            self.size += len(cmd[0])
            if cmd[0] is "MA":
                cmd[1] = cmd[1].replace(":", "")
                hex_string = codecs.decode(cmd[1], 'hex')

                self.msg[self.size:] = hex_string
                self.dest_mac = hex_string
                self.size += 6
            else:
                self.msg[self.size:] = str.encode(cmd[1])
                self.size += len(cmd[1])
            if not "\r\n" in cmd[1]:
                self.msg[self.size:] = str.encode("\r\n")
                self.size += 2

    def sendcommands(self):
        self.sock.sendto(self.msg)

    def sendcommandsTCP(self):
        self.sock.write(self.msg)

    def run(self):
        try:
            self.makecommands()
            if self.what_sock == 'udp':
                self.sendcommands()
            elif self.what_sock == 'tcp':
                self.sendcommandsTCP()
        except Exception as e:
            print(e)

        replylists = None

        checknum = 0

        while True:
            print('Refresh', checknum)
            self.rcv_list = []
            readready, writeready, errorready = select.select(
                self.inputs, self.outputs, self.errors, 2)

            self.iter += 1
            # sys.stdout.write("iter count: %r " % self.iter)

            for sock in readready:
                if sock == self.sock.sock:
                    data = self.sock.recvfrom()
                    self.rcv_list.append(data)  # 수신 데이터 저장
                    replylists = data.splitlines()
                    # print('replylists', replylists)

            checknum += 1
            self.resp_check.emit(checknum)
            if self.interval == 0:
                break
            else:
                self.msleep(self.interval)
            self.sendcommands()
