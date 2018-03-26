# -*- coding: utf-8 -*-

## Make Serial command

import socket
import time
import struct
import binascii
import sys
import getopt
import logging
import re
import os
from WIZ750CMDSET import WIZ750CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from WIZUDPSock import WIZUDPSock
from WIZMSGHandler import WIZMSGHandler
from WIZArgParser import WIZArgParser
from FWUploadThread import FWUploadThread
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

OP_SEARCHALL = 1
OP_GETCOMMAND = 2
OP_SETCOMMAND = 3
OP_SETFILE = 4
OP_GETFILE = 5
OP_FWUP = 6

BAUDRATES = [300, 600, 1200, 1800, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200, 230400, 460800]
# not use UI / EI (UART interface(Code))
cmd_oneport = ['MC','VR','MN','UN','ST','IM','OP','DD','CP','PO','DG','KA','KI','KE','RI','LI','SM','GW','DS','PI','PP','DX','DP','DI','DW','DH','LP','RP','RH','BR','DB','PR','SB','FL','IT','PT','PS','PD','TE','SS','NP','SP','TR']
cmd_twoport = ['MC','VR','MN','UN','ST','IM','OP','DD','CP','PO','DG','KA','KI','KE','RI','LI','SM','GW','DS','PI','PP','DX','DP','DI','DW','DH','LP','RP','RH','BR','DB','PR','SB','FL','IT','PT','PS','PD','TE','SS','NP','SP','TR','QS','QO','QH','QP','QL','RV','RA','RE','RR','EN','RS','EB','ED','EP','ES','EF','E0','E1','NT','NS','ND']

class WIZMakeCMD:
    def search_broadcast(self):
        cmd_list = []
        # Search All Devices on the network
        # 장치 검색 시 필요 정보 Get
        cmd_list.append(["MA", "FF:FF:FF:FF:FF:FF"])
        cmd_list.append(["PW", " "])
        # for cmd in cmd_oneport:
        for cmd in cmd_twoport:
            cmd_list.append([cmd, ""])
        return cmd_list

    def search(self, mac_addr):
        cmd_list = []
        # Search All Devices on the network
        # 장치 검색 시 필요 정보 Get
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", " "])
        # for cmd in cmd_oneport:
        for cmd in cmd_twoport:
            cmd_list.append([cmd, ""])
        return cmd_list
    
    def get_value(self, mac_addr, filename):
        # 파일의 command들에 대한 정보를 가져옴
        cmd_list = []
        f = open(filename, 'r')
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", " "])
        for line in f:
#			print len(line), line.decode('hex')
            if len(line) > 2 :
                cmd_list.append([line[:2], ""])
        f.close()
        return cmd_list

    def set_value(self, mac_addr, filename):
        # 파일에서 cmd/parameter set 정보를 불러옴
        cmd_list = []
        f = open(filename, 'r')
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", " "])
        getcmd_list = []
        for line in f:
            if len(line) > 2:
                cmd_list.append([line[:2], line[2:]])
                getcmd_list.append(line[:2])
        for cmd in getcmd_list:
            cmd_list.append([cmd, ""])
        cmd_list.append(["SV", ""])
        cmd_list.append(["RT", ""])
        f.close()
        return cmd_list

    # Get device info
    def getcommand(self, macaddr, command_list):
        cmd_list = []    # 초기화
        cmd_list.append(["MA", macaddr])
        cmd_list.append(["PW", " "])
        # cmd_list.append(["MC", ""])
        for i in range(len(command_list)):
            cmd_list.append([command_list[i], ""]) 
        # cmd_list.append(["RT", ""])
        return cmd_list

    # Set device
    def setcommand(self, macaddr, command_list, param_list, port):
        cmd_list = []
        try:
            # print('Macaddr: %s' % macaddr)
            cmd_list.append(["MA", macaddr])
            cmd_list.append(["PW", " "])
            for i in range(len(command_list)):
                cmd_list.append([command_list[i], param_list[i]]) 
            ################ Set+Get
            if port == 1:
                for cmd in cmd_oneport:
                    cmd_list.append([cmd, ""])
            elif port == 2:
                for cmd in cmd_twoport:
                    cmd_list.append([cmd, ""])
            ################
            cmd_list.append(["SV", ""]) # save device setting
            cmd_list.append(["RT", ""]) # Device reboot
            return cmd_list
        except Exception as e:
            sys.stdout.write('%r\r\n' % e)            

    def reset(self, mac_addr):
        cmd_list = []
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", " "])
        cmd_list.append(["RT", ""])	
        return cmd_list
    
    def factory_reset(self, mac_addr):
        cmd_list = []
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", " "])
        cmd_list.append(["FR", ""])	
        return cmd_list
    
    def set_maclist(self, mac_list, devname):
        try:
            if os.path.isfile('mac_list.txt'):
                f = open('mac_list.txt', 'r+')
            else:
                f = open('mac_list.txt', 'w+')
            data = f.readlines()
            # print('data', data)
        except Exception as e:
            sys.stdout.write(e)
        for i in range(len(mac_list)):
            print('* Device %d: %s [%s] ' % (i+1, mac_list[i].decode(), devname[i].decode()))
            info = "%s\n" % (mac_list[i].decode())
            if info in data:
                # print('===> already in')
                pass
            else:
                print('New Device: %s' % mac_list[i].decode())
                f.write(info)
        f.close()

    def isvalid(self, mac_addr):
        pass

        