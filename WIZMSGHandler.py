#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket
import time
import threading
from threading import *
import struct
import binascii
import select
import sys
import codecs
from WIZ750CMDSET import WIZ750CMDSET 
from WIZ752CMDSET import WIZ752CMDSET 

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

class WIZMSGHandler:
    def __init__(self, udpsock):
        self.sock = udpsock
        self.msg = bytearray(1024)
        self.size = 0

        self.inputs = [self.sock.sock]
        self.outputs = []
        self.errors = []
        self.opcode = None
        self.iter = 0
        self.dest_mac = None
        self.isvalid = False
        self.timer1 = None
        self.istimeout = False
        self.reply = ''

        self.mac_list = []
        self.ip_list = []
        self.ip_mode = []
        self.mode_list = []
        self.mn_list = []
        self.vr_list = []

        self.getreply = []

        self.rcv_list = []

        # self.exitflag = None

    def timeout_func(self):
    	# print('timeout')
        # self.exitflag = 1
        self.istimeout = True        

    def getmacaddr(self, index):
        if len(self.mac_list) >= (index + 1):
            mac_addr = self.mac_list[index]
            # print (mac_addr)
            for i in range(5, 1):
                mac_addr[i*2:] = ":" + mac_addr[i*2:]
            # print (mac_addr)
            return mac_addr
        else:
            sys.stdout.write("index is out of range\r\n")
            return None
    
    # Get IP address
    def getipaddr(self, index):
        if len(self.ip_list) >= (index + 1):
            ip_addr = self.ip_list[index]
            print(ip_addr)
            return ip_addr
        else:
            print('getipaddr: index is out of range')
            return None

    def getopmode(self, index):
        if len(self.mode_list) >= (index + 1):
            opmode = self.mode_list[index]
            # print('getopmode:', opmode)
            return opmode
        else:
            print('getopmode: index is out of range')
            return None

    def getipmode(self, index):
        if len(self.ip_mode) >= (index + 1):
            ipmode = self.ip_mode[index]
            # print('getipmode:', ipmode)
            return ipmode
        else:
            print('getipmode: index is out of range')
            return None

    def makecommands(self, cmd_list, op_code):
        self.opcode = op_code
        self.size = 0

        for cmd in cmd_list:
            # print('cmd[0]: %s, cmd[1]: %s' % (cmd[0], cmd[1]))
            self.msg[self.size:] = str.encode(cmd[0])
            self.size += len(cmd[0])
            if cmd[0] is "MA":
                # sys.stdout.write('cmd[1]: %r\r\n' % cmd[1])
                cmd[1] = cmd[1].replace(":", "")
                # print(cmd[1])
                # hex_string = cmd[1].decode('hex')
                hex_string = codecs.decode(cmd[1], 'hex')
                
                self.msg[self.size:] = hex_string
                self.dest_mac = hex_string
                # self.dest_mac = (int(cmd[1], 16)).to_bytes(6, byteorder='big') # Hexadecimal string to hexadecimal binary
                # self.msg[self.size:] = self.dest_mac
                self.size += 6
            else :
                self.msg[self.size:] = str.encode(cmd[1])
                self.size += len(cmd[1])
            if not "\r\n" in cmd[1]:
                self.msg[self.size:] = str.encode("\r\n")
                self.size += 2

#			print(self.size, self.msg)

    def sendcommands(self):
        self.sock.sendto(self.msg)

    def parseresponse(self):
        readready, writeready, errorready = select.select(self.inputs, self.outputs, self.errors, 1)
        
        self.timer1 = Timer(2.0, self.timeout_func)
        self.timer1.start()
        
        # t = Timer(3.0, timeout_func)
        # t.start()
        
        replylists = None
        self.getreply = []
        self.mac_list = []
        self.rcv_list = []

        while True:
            self.iter += 1
            # sys.stdout.write("iter count: %r" % self.iter)

            if self.istimeout is True:
                self.timer1.cancel()
                self.istimeout = False
                break

            # if(exitflag) :
            #     t.cancel()
            #     # exitflag = 0
            
            for sock in readready:
                if sock == self.sock.sock :
                    data = self.sock.recvfrom()
                    self.rcv_list.append(data)      ## 수신 데이터 저장 
                    replylists = data.splitlines()
                    # print('replylists', replylists)
                    self.getreply = replylists

                    if self.opcode is OP_SEARCHALL:
                        for i in range(0, len(replylists)):
                            if b'MC' in replylists[i]: self.mac_list.append(replylists[i][2:])
                            if b'MN' in replylists[i]: self.mn_list.append(replylists[i][2:])
                            if b'VR' in replylists[i]: self.vr_list.append(replylists[i][2:])
                            if b'OP' in replylists[i]: self.mode_list.append(replylists[i][2:])
                            if b'LI' in replylists[i]: self.ip_list.append(replylists[i][2:]) 
                            if b'IM' in replylists[i]: self.ip_mode.append(replylists[i][2:])
                    elif self.opcode is OP_FWUP:
                        for i in range(0, len(replylists)):
                            # sys.stdout.write('%s\r\n' % replylists)
                            # sys.stdout.write("%r\r\n" % replylists[i][:2])
                            if b'MA' in replylists[i][:2]:
                                dest_mac = self.dest_mac
                                reply_mac = replylists[i][2:]
                                # sys.stdout.write('dest_mac: %r\r\n' % dest_mac)
                                # sys.stdout.write('reply_mac: %r\r\n' % reply_mac)
                                # self.isvalid = True
                            else:
                                self.isvalid = False

                            # sys.stdout.write("%r\r\n" % replylists[i][:2])

                            if b'FW' in replylists[i][:2]:
                                # sys.stdout.write('self.isvalid is True\r\n')
                                param = replylists[i][2:].split(b':')
                                self.reply = replylists[i][2:]

                            # sys.stdout.write("%r\r\n" % replylists[i])

                    readready, writeready, errorready = select.select(self.inputs, self.outputs, self.errors, 1)

        if self.opcode is OP_SEARCHALL:
            return len(self.mac_list)
        elif self.opcode is OP_FWUP:
            return self.reply
        # sys.stdout.write("%s\r\n" % self.mac_list)

    def get_log(self):
        if len(self.getreply) > 0:
            print('Configuration result: ')
            # print('getreply: %s' % self.getreply)
            cmdsetObj = WIZ752CMDSET(logging.ERROR)
            for i in range(2, len(self.getreply)):
                getcmd = self.getreply[i][:2]
                cmd = getcmd.decode('utf-8')
                getparam = self.getreply[i][2:]
                param = getparam.decode('utf-8')

                cmd_desc = cmdsetObj.getcmddescription(cmd)
                param_desc = cmdsetObj.getparamdescription(cmd, param)
                conf_info = "    %02d) %s: %-17s | %s: %s\r\n" % (i-1, cmd, param, cmd_desc, param_desc)
                sys.stdout.write('%s' % conf_info)

    def get_filelog(self, macaddr):
        filename = None
        # print('getreply: %s' % self.getreply)
        if self.getreply is None:
            print('No reply from device. exit program.')
            sys.exit(0)

        # cmdsetObj = WIZ752CMDSET(logging.ERROR)
        mac_addr = macaddr.replace(":", "")
        filename = 'getfile_%s.log' % (mac_addr)

        for i in range(0, len(self.getreply)):
            f = open(filename, 'w')
            for i in range(2, len(self.getreply)):
                getcmd = self.getreply[i][:2]
                cmd = getcmd.decode('utf-8')
                if cmd not in cmdsetObj.cmdset:
                    print('Invalid command. Check the command set')
                    exit(0)
                getparam = self.getreply[i][2:]
                param = getparam.decode('utf-8')
                cmd_desc = cmdsetObj.getcmddescription(cmd)
                param_desc = cmdsetObj.getparamdescription(cmd, param)
                # sys.stdout.write("%s\r\n" % self.getreply[i])
                info = "%02d) %s: %-17s | %s: %s\n" % (i-1, cmd, param, cmd_desc, param_desc)
                # info = "%02d) %s: %s\r\n" % (i-1, cmd_desc, param_desc)
                f.write(info)
            f.close()
        
        if filename is not None:
            f = open(filename, 'r')
            readinfo = f.read()
            print(readinfo)       
            
            print('@ Refer to \"%s\" for detail.\n' % filename)
