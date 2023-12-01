#!/usr/bin/python
# -*- coding: utf-8 -*-

import select
import codecs
import os
import re
from utils import logger

from PyQt5.QtCore import QThread, pyqtSignal
from constants import Opcode
from wizcmdset import Wizcmdset

exitflag = 0

# PACKET_SIZE = 1024
# PACKET_SIZE = 2048
PACKET_SIZE = 4096
UDP_PACKET_SIZE = 1460

def timeout_func():
    # print('timeout')
    global exitflag
    exitflag = 1


class WIZMSGHandler(QThread):
    search_result = pyqtSignal(int)
    set_result = pyqtSignal(int)

    searched_data = pyqtSignal(bytes)

    def __init__(self, udpsock, cmd_list, what_sock, op_code, timeout):
        QThread.__init__(self)

        self.logger = logger

        self.sock = udpsock
        self.msg = bytearray(PACKET_SIZE)
        self.size = 0

        try:
            self.inputs = [self.sock.sock]
        except Exception as e:
            self.logger.error('socket error:', e)
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
        self.rcv_all_list = []
        self.what_sock = what_sock
        self.cmd_list = cmd_list
        self.opcode = op_code

        self.timeout = timeout

        self.cmdset = Wizcmdset('WIZ750SR')

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
                    self.logger.error('[ERROR] makecommands() encode:', cmd[0], e)
                self.size += len(cmd[0])
                if cmd[0] == "MA":
                    # sys.stdout.write('cmd[1]: %r\r\n' % cmd[1])
                    cmd[1] = cmd[1].replace(":", "")
                    # print(cmd[1])
                    # hex_string = cmd[1].decode('hex')
                    try:
                        hex_string = codecs.decode(cmd[1], 'hex')
                    except Exception as e:
                        self.logger.error(
                            '[ERROR] makecommands() decode:', cmd[0], cmd[1], e)

                    self.msg[self.size:] = hex_string
                    self.dest_mac = hex_string
                    # self.dest_mac = (int(cmd[1], 16)).to_bytes(6, byteorder='big') # Hexadecimal string to hexadecimal binary
                    # self.msg[self.size:] = self.dest_mac
                    self.size += 6
                else:
                    try:
                        self.msg[self.size:] = str.encode(cmd[1])
                    except Exception as e:
                        self.logger.error(
                            '[ERROR] makecommands() encode param:', cmd[0], cmd[1], e)
                    self.size += len(cmd[1])
                if "\r\n" not in cmd[1]:
                    self.msg[self.size:] = str.encode("\r\n")
                    self.size += 2

                    # print(self.size, self.msg)
        except Exception as e:
            self.logger.error('[ERROR] WIZMSGHandler makecommands(): %r' % e)

    def sendcommands(self):
        total_size = len(self.msg)
        # Update the sz field in the msg
        curr_ptr = 0  # Current position in the data

        while total_size > curr_ptr:
            if total_size - curr_ptr > UDP_PACKET_SIZE:
                # Split the data into PACKET_SIZE chunks
                packet = self.msg[curr_ptr:curr_ptr + UDP_PACKET_SIZE]
                self.sock.sendto(packet)
                curr_ptr += UDP_PACKET_SIZE
            else:
                # Send the remaining data
                packet = self.msg[curr_ptr:]
                self.sock.sendto(packet)
                break  # No more data to send

        #self.logger.info(f"Total {total_size} bytes sent in multiple packets.")


    def sendcommandsTCP(self):
        self.sock.write(self.msg)

    def check_parameter(self, cmdset):
        # print('check_parameter()', cmdset, cmdset[:2], cmdset[2:])
        try:
            if b'MA' not in cmdset:
                # print('check_parameter() OK', cmdset, cmdset[:2], cmdset[2:])
                if self.cmdset.isvalidparameter(cmdset[:2].decode(), cmdset[2:].decode()):
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            self.logger.error('[ERROR] WIZMSGHandler check_parameter(): %r' % e)
    

    def get_list_to_dict(self, list):
        converted_dict = {}
        for item in list:
            try:
                decoded_item = item.decode('utf-8', 'ignore')
                key = decoded_item[:2]
                value = decoded_item[2:]
                converted_dict[key] = value
            except UnicodeDecodeError as e:
                self.logger.error(f"decode error: {e} - ignore key.")
        return converted_dict
    

    def run(self):
        try:
            self.makecommands()
            if self.what_sock == 'udp':
                self.sendcommands()
            elif self.what_sock == 'tcp':
                self.sendcommandsTCP()
        except Exception as e:
            self.logger.error(f'[ERROR] WIZMSGHandler sendcommands: {e}')

        try:
            readready, writeready, errorready = select.select(
                self.inputs, self.outputs, self.errors, self.timeout)
        
            replylists = []
            replyAlllist = []
            self.getreply = []
            self.mac_list = []
            self.mn_list = []
            self.vr_list = []
            self.st_list = []
            self.rcv_list = []
            # print('readready value: ', len(readready), readready)
            if self.timeout < 2:
                # Search each device
                for sock in readready:
                    if sock == self.sock.sock:
                        data = self.sock.recvfrom()
                        self.logger.debug(f'Each-search recv: {data}')
                        self.searched_data.emit(data)
                        # replylists = data.splitlines()
                        replylists = data.split(b"\r\n")
                        # print('replylists', replylists)
                        self.getreply = replylists

            else:
                # Pre search
                while True:
                    self.iter += 1
                    #print(f"iter count: {self.iter}")
                    for sock in readready:
                        if sock == self.sock.sock:
                            data = self.sock.recvfrom()
                            self.logger.debug(f'Pre-search recv: {data}')
                            # self.searched_data.emit(data)

                            # check if data reduplication
                            if data in self.rcv_list:
                                replylists = []
                            else:
                                self.rcv_list.append(data)  # received data backup
                                # replylists = data.splitlines()
                                replylists = re.split(b'\r\n|\x00\n', data)
                                replyAlllist.append(replylists)
                                
                        readready, writeready, errorready = select.select(self.inputs, self.outputs, self.errors, 1)
                    if not readready or not replylists:
                        break       
                pattern_x00 = re.compile(b'\x00{10,}')  # 10개 이상의 연속된 0 바이트
                replyAlllist = [sublist for sublist in replyAlllist if not any(pattern_x00.search(item) for item in sublist)]
                # 모든 리스트를 순회
                for i in range(len(replyAlllist)):
                    current_list = replyAlllist[i]
                    if i < len(replyAlllist) - 1:
                        # 현재 리스트의 마지막 값과 다음 리스트의 첫 번째 값을 합침
                        last_item_current = current_list[-1]
                        first_item_next = replyAlllist[i + 1][0].decode('utf-8', 'ignore')  # bytes를 문자열로 변환
                        combined_item = last_item_current + first_item_next.encode('utf-8')  # 다시 bytes로 변환

                        # 현재 리스트의 나머지 요소와 결합된 요소를 추가
                        self.rcv_all_list.extend(current_list[:-1] + [combined_item])
                    else:
                        # 마지막 리스트는 그대로 추가 (마지막 리스트의 첫 번째 요소는 이미 합쳐졌으므로 제외)
                        self.rcv_all_list.extend(current_list[1:])
                replylists = self.rcv_all_list
                self.getreply = replylists

                if self.opcode == Opcode.OP_SEARCHALL:
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
                        self.logger.error('[ERROR] WIZMSGHandler makecommands(): %r' % e)

                elif self.opcode == Opcode.OP_FWUP:
                    for i in range(0, len(replylists)):
                        if b'MA' in replylists[i][:2]:
                            pass
                            # self.isvalid = True
                        else:
                            self.isvalid = False
                        # sys.stdout.write("%r\r\n" % replylists[i][:2])
                        if b'FW' in replylists[i][:2]:
                            # sys.stdout.write('self.isvalid == True\r\n')
                            # param = replylists[i][2:].split(b':')
                            self.reply = replylists[i][2:]

                elif self.opcode == Opcode.OP_SETCOMMAND:
                    for i in range(0, len(replylists)):
                        if b'AP' in replylists[i][:2]:
                            if replylists[i][2:] == b' ':
                                self.setting_pw_wrong = True
                            else:
                                self.setting_pw_wrong = False

                    readready, writeready, errorready = select.select(
                        self.inputs, self.outputs, self.errors, 1)


                if self.opcode == Opcode.OP_SEARCHALL:
                    self.msleep(500)
                    # print('Search device:', self.mac_list)
                    self.search_result.emit(len(self.mac_list))
                    # return len(self.mac_list)
                if self.opcode == Opcode.OP_SETCOMMAND:
                    self.msleep(500)
                    if len(self.rcv_list) > 0:
                        # print('Opcode.OP_SETCOMMAND: rcv_list:', len(self.rcv_list[0]), self.rcv_list[0])
                        if self.setting_pw_wrong:
                            self.set_result.emit(-3)
                        else:
                            self.set_result.emit(len(self.rcv_list[0]))
                    else:
                        self.set_result.emit(-1)
                elif self.opcode == Opcode.OP_FWUP:
                    return self.reply
                # sys.stdout.write("%s\r\n" % self.mac_list)
        except Exception as e:
            self.logger.error(f'[ERROR] WIZMSGHandler error: {e}')


class DataRefresh(QThread):
    resp_check = pyqtSignal(int)

    def __init__(self, sock, cmd_list, what_sock, interval):
        QThread.__init__(self)
        self.logger = logger

        self.sock = sock
        self.msg = bytearray(PACKET_SIZE)
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
            if cmd[0] == "MA":
                cmd[1] = cmd[1].replace(":", "")
                hex_string = codecs.decode(cmd[1], 'hex')

                self.msg[self.size:] = hex_string
                self.dest_mac = hex_string
                self.size += 6
            else:
                self.msg[self.size:] = str.encode(cmd[1])
                self.size += len(cmd[1])
            if "\r\n" not in cmd[1]:
                self.msg[self.size:] = str.encode("\r\n")
                self.size += 2

    def sendcommands(self):
        self.sock.sendto(self.msg[:self.size])

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
            self.logger.error(str(e))

        # replylists = None
        checknum = 0

        try:
            while True:
                self.rcv_list = []
                readready, writeready, errorready = select.select(
                    self.inputs, self.outputs, self.errors, 2)

                self.iter += 1
                # sys.stdout.write("iter count: %r " % self.iter)

                for sock in readready:
                    self.logger.info(f'DataRefresh: {checknum}')

                    if sock == self.sock.sock:
                        data = self.sock.recvfrom()
                        self.rcv_list.append(data)  # 수신 데이터 저장
                        # replylists = data.splitlines()
                        # replylists = data.split(b"\r\n")
                        # print('replylists', replylists)

                checknum += 1
                self.resp_check.emit(checknum)
                if self.interval == 0:
                    break
                else:
                    self.msleep(self.interval)
                self.sendcommands()
        except Exception as e:
            self.logger.error(f'[ERROR] DataRefresh error: {e}')
