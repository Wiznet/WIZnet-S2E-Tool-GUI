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

# Supported devices
ONE_PORT_DEV = ['WIZ750SR', 'WIZ750SR-100', 'WIZ750SR-105', 'WIZ750SR-110', 'WIZ107SR', 'WIZ108SR', 'WIZ2000']
TWO_PORT_DEV = ['WIZ752SR-12x', 'WIZ752SR-120','WIZ752SR-125']

BAUDRATES = [300, 600, 1200, 1800, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200, 230400, 460800]
# not use UI / EI (UART interface(Code))
# for pre-search
cmd_getinfo = ['MC','VR','MN','ST','IM','OP','LI','SM','GW']

# Command for each device
cmd_ch1 = ['MC','VR','MN','UN','ST','IM','OP','DD','CP','PO','DG','KA','KI','KE','RI','LI','SM','GW','DS','PI','PP','DX','DP','DI','DW','DH','LP','RP','RH','BR','DB','PR','SB','FL','IT','PT','PS','PD','TE','SS','NP','SP']
cmd_added = ['SC', 'TR']  # f/w version 1.2.0 or later
cmd_ch2 = ['QS','QO','QH','QP','QL','RV','RA','RE','RR','EN','RS','EB','ED','EP','ES','EF','E0','E1','NT','NS','ND']

cmd_gpio = ['CA','CB','CC','CD','GA','GB','GC','GD']

### CMD list
cmd_1p_default = cmd_ch1
cmd_1p_advanced = cmd_ch1 + cmd_added
cmd_2p_default = cmd_ch1 + cmd_ch2

def version_compare(version1, version2):
    def normalize(v):
        # return [x for x in re.sub(r'(\.0+)*$','',v).split('.')]
        return [x for x in re.sub(r'(\.0+\.[dev])*$','',v).split('.')]
    obj1 = normalize(version1)
    obj2 = normalize(version2)
    return (obj1 > obj2) - (obj1 < obj2)
    # if return value < 0: version2 upper than version1

class WIZMakeCMD:
    def presearch(self, mac_addr, idcode):
        cmd_list = []
        # Search All Devices on the network
        # 장치 검색 시 필요 정보 Get
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
        for cmd in cmd_getinfo:
            cmd_list.append([cmd, ""])
        return cmd_list

    def search(self, mac_addr, idcode, devname, version):
        cmd_list = []
        # Search All Devices on the network
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
        
        if devname in ONE_PORT_DEV or "750" in devname or "WIZ2000" in devname:

            if '750' in devname and version_compare('1.2.0', version) <= 0:
                for cmd in cmd_1p_advanced:
                    cmd_list.append([cmd, ""])
            else:
                for cmd in cmd_1p_default:
                    cmd_list.append([cmd, ""])
        elif devname in TWO_PORT_DEV or "752" in devname:
            for cmd in cmd_2p_default:
                cmd_list.append([cmd, ""])
        else: 
            pass
            
        return cmd_list

    def get_gpiovalue(self, mac_addr, idcode):
        cmd_list = []
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
        for cmd in cmd_gpio:
            cmd_list.append([cmd, ""])
        return cmd_list
    
    def get_value(self, mac_addr, idcode, filename):
        # 파일의 command들에 대한 정보를 가져옴
        cmd_list = []
        f = open(filename, 'r')
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
        for line in f:
#			print len(line), line.decode('hex')
            if len(line) > 2 :
                cmd_list.append([line[:2], ""])
        f.close()
        return cmd_list

    def set_value(self, mac_addr, idcode, filename):
        # 파일에서 cmd/parameter set 정보를 불러옴
        cmd_list = []
        f = open(filename, 'r')
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
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
    def getcommand(self, macaddr, idcode, command_list):
        cmd_list = []    # 초기화
        cmd_list.append(["MA", macaddr])
        cmd_list.append(["PW", idcode])
        # cmd_list.append(["MC", ""])
        for i in range(len(command_list)):
            cmd_list.append([command_list[i], ""]) 
        # cmd_list.append(["RT", ""])
        return cmd_list

    # Set device
    def setcommand(self, macaddr, idcode, command_list, param_list, devname, version):
        cmd_list = []
        try:
            # print('Macaddr: %s' % macaddr)
            cmd_list.append(["MA", macaddr])
            cmd_list.append(["PW", idcode])
            for i in range(len(command_list)):
                cmd_list.append([command_list[i], param_list[i]]) 

            if devname in ONE_PORT_DEV or "750" in devname or "2000" in devname:
                if '750' in devname and version_compare('1.2.0', version) <= 0:
                    for cmd in cmd_1p_advanced:
                        cmd_list.append([cmd, ""])
                else:
                    for cmd in cmd_1p_default:
                        cmd_list.append([cmd, ""])
            elif devname in TWO_PORT_DEV or "752" in devname:
                # for cmd in cmd_2p_default:
                #     cmd_list.append([cmd, ""])
                # for WIZ752SR-12x
                for cmd in cmd_ch2:
                    cmd_list.append([cmd, ""])
            cmd_list.append(["SV", ""]) # save device setting
            cmd_list.append(["RT", ""]) # Device reboot
            return cmd_list
        except Exception as e:
            sys.stdout.write('%r\r\n' % e)            

    def reset(self, mac_addr, idcode):
        cmd_list = []
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
        cmd_list.append(["RT", ""])	
        return cmd_list
    
    def factory_reset(self, mac_addr, idcode):
        cmd_list = []
        cmd_list.append(["MA", mac_addr])
        cmd_list.append(["PW", idcode])
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

        