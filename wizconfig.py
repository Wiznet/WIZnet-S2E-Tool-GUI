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

BAUDRATES = [300, 600, 1200, 1800, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200, 230400]

class WIZMakeCMD:
    def search(self):
        cmd_list = []
        # Search All Devices on the network
        # 장치 검색 시 필요 정보 Get
        cmd_list.append(["MA", "FF:FF:FF:FF:FF:FF"])
        cmd_list.append(["PW", " "])
        cmd_list.append(["MC", ""])
        cmd_list.append(["LI", ""])    # IP address
        cmd_list.append(["VR", ""])
        cmd_list.append(["MN", ""])
        cmd_list.append(["RH", ""])
        cmd_list.append(["RP", ""])
        cmd_list.append(["OP", ""]) # Network operation mode
        cmd_list.append(["IM", ""]) # IP address allocation method(Static/DHCP)
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
    def setcommand(self, macaddr, command_list, param_list):
        cmd_list = []
        try:
            # print('Macaddr: %s' % macaddr)
            cmd_list.append(["MA", macaddr])
            cmd_list.append(["PW", " "])
            for i in range(len(command_list)):
                cmd_list.append([command_list[i], param_list[i]]) 
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

if __name__ == '__main__':
    wizmakecmd = WIZMakeCMD()

    wizarg = WIZArgParser()
    args = wizarg.config_arg()

    # wiz750cmdObj = WIZ750CMDSET(1)
    wiz752cmdObj = WIZ752CMDSET(1)

    conf_sock = WIZUDPSock(5000, 50001)
    conf_sock.open()
    wizmsghangler = WIZMSGHandler(conf_sock)

    # FUObj = FWUpload(logging.DEBUG)

    cmd_list = []
    setcmd = {}
    op_code = OP_SEARCHALL
    # print(args)

    if args.search or args.clear:
        if len(sys.argv) is not 2:
            print('Invalid argument. Please refer to %s -h\n' % sys.argv[0])
            sys.exit(0)
    else:
        if len(sys.argv) < 3:
            print('Invalid argument. Please refer to %s -h\n' % sys.argv[0])
            sys.exit(0)

    if args.clear:
        print('Mac list clear')
        f = open('mac_list.txt', 'w')
        f.close()

    ## single or all device set
    elif args.macaddr or args.all or args.search or args.multiset:
        if args.macaddr:
            mac_addr = args.macaddr
            if wiz752cmdObj.isvalidparameter("MC", mac_addr) is False :
                sys.stdout.write("Invalid Mac address!\r\n")
                sys.exit(0)
        
        op_code = OP_SETCOMMAND
        print('Devcie configuration start...\n')
        # General config
        
        if args.alloc: setcmd['IM'] = args.alloc
        if args.ip:  setcmd['LI'] = args.ip
        if args.subnet: setcmd['SM'] = args.subnet
        if args.gw: setcmd['GW'] = args.gw
        if args.dns: setcmd['DS'] = args.dns
        
        # Channel 0 config
        if args.nmode0:  setcmd['OP'] = args.nmode0
        if args.port0: setcmd['LP'] = args.port0
        if args.rip0: setcmd['RH'] = args.rip0
        if args.rport0: setcmd['RP'] = args.rport0

        if args.baud0: setcmd['BR'] = str(BAUDRATES.index(args.baud0))
        if args.data0: setcmd['DB'] = args.data0
        if args.parity0: setcmd['PR'] = args.parity0
        if args.stop0: setcmd['SB'] = args.stop0
        if args.flow0: setcmd['FL'] = args.flow0
        if args.time0: setcmd['PT'] = args.time0
        if args.size0: setcmd['PS'] = args.size0
        if args.char0: setcmd['PD'] = args.char0

        if args.it: setcmd['IT'] = args.it
        if args.ka: setcmd['KA'] = args.ka
        if args.ki: setcmd['KI'] = args.ki
        if args.ke: setcmd['KE'] = args.ke
        if args.ri: setcmd['RI'] = args.ri

        # Channel 1 config
        if args.nmode1:  setcmd['QO'] = args.nmode1
        if args.port1: setcmd['QL'] = args.port1
        if args.rip1: setcmd['QH'] = args.rip1
        if args.rport1: setcmd['QP'] = args.rport1

        if args.baud1: setcmd['EB'] = str(BAUDRATES.index(args.baud1))
        if args.data1: setcmd['ED'] = args.data1
        if args.parity1: setcmd['EP'] = args.parity1
        if args.stop1: setcmd['ES'] = args.stop1
        if args.flow1: setcmd['EF'] = args.flow1
        if args.time1: setcmd['NT'] = args.time1
        if args.size1: setcmd['NS'] = args.size1
        if args.char1: setcmd['ND'] = args.char1

        if args.rv: setcmd['RV'] = args.rv
        if args.ra: setcmd['RA'] = args.ra
        if args.rs: setcmd['RS'] = args.rs
        if args.re: setcmd['RE'] = args.re
        if args.rr: setcmd['RR'] = args.rr
        
        # Configs
        if args.cp: setcmd['CP'] = args.cp
        if args.np: setcmd['NP'] = args.np
        if args.sp: setcmd['SP'] = args.sp
        if args.dg: setcmd['DG'] = args.dg            
        
        # Command mode switch settings
        if args.te: setcmd['TE'] = args.te
        if args.ss: setcmd['SS'] = args.ss
        ######################################################
        # print('%d, %s' % (len(setcmd), setcmd))
        # Check parameter
        setcmd_cmd = list(setcmd.keys())
        for i in range(len(setcmd)):
            # print('%r , %r' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
            if wiz752cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                sys.stdout.write("%s\nInvalid parameter: %s \nPlease refer to %s -h\r\n" % ('#'*25, setcmd.get(setcmd_cmd[i]), sys.argv[0]))
                sys.exit(0)
        ######################################################
        # ALL devices config
        if args.all or args.multiset:
            if not os.path.isfile('mac_list.txt'):
                print('There is no mac_list.txt file. Please search devices first from \'-s/--search\' option.')
                sys.exit(0)
            f = open('mac_list.txt', 'r')
            mac_list = f.readlines()
            if len(mac_list) is 0:
                print('There is no mac address. Please search devices from \'-s/--search\' option.')
                sys.exit(0)
            f.close()
            # Check parameter
            if args.multiset:
                host_ip = args.multiset
                # print('Host ip: %s\n' % host_ip)
                if wiz752cmdObj.isvalidparameter("LI", host_ip) is False:
                    sys.stdout.write("Invalid IP address!\r\n")
                    sys.exit(0)
            
            for i in range(len(mac_list)):
                mac_addr = re.sub('[\r\n]', '', mac_list[i])
                # print(mac_addr)
                if args.fwfile:
                    op_code = OP_FWUP
                    print('[All] Device FW upload: device %d, %s' % (i+1, mac_addr))

                    ## no thread
                    # FUObj.setparam(mac_addr, args.fwfile)
                    # FUObj.run()
                    # time.sleep(1)
                    ## threading
                    fwup_name = 't%d_fwup' % (i)
                    fwup_name = FWUploadThread()
                    fwup_name.setparam(mac_addr, args.fwfile)
                    fwup_name.start()
                else: 
                    if args.multiset:
                        op_code = OP_SETCOMMAND
                        time.sleep(1)
                        dst_port = '5000'                            
                        lastnumindex = host_ip.rfind('.')
                        lastnum = int(host_ip[lastnumindex + 1:])
                        target_ip = host_ip[:lastnumindex + 1] + str(lastnum + i)
                        target_gw = host_ip[:lastnumindex + 1] + str(1)
                        print('[All] Set IP for devices %s -> %s' % (mac_addr, target_ip))
                        setcmd['LI'] = target_ip
                        setcmd['GW'] = target_gw
                        setcmd['LP'] = dst_port
                        setcmd['OP'] = '1'
                        cmd_list = wizmakecmd.setcommand(mac_addr, list(setcmd.keys()), list(setcmd.values()))
                        get_cmd_list = wizmakecmd.getcommand(mac_addr, list(setcmd.keys()))
                    elif args.setfile:
                        op_code = OP_SETFILE
                        print('[Setfile] Device [%s] Config from \'%s\' file.' % (mac_addr, args.setfile))
                        cmd_list = wizmakecmd.set_value(mac_addr, args.setfile)
                    elif args.getfile:
                        op_code = OP_GETFILE
                        cmd_list = wizmakecmd.get_value(mac_addr, args.getfile)
                    else:
                        if args.reset:
                            print('[All] Reset devices %d: %s' % (i+1, mac_addr))
                            cmd_list = wizmakecmd.reset(mac_addr)
                        elif args.factory:
                            print('[All] Factory reset devices %d: %s' % (i+1, mac_addr))
                            cmd_list = wizmakecmd.factory_reset(mac_addr)
                        else:
                            op_code = OP_SETCOMMAND
                            print('[All] Setting devcies %d: %s' % (i+1, mac_addr))
                            cmd_list = wizmakecmd.setcommand(mac_addr, list(setcmd.keys()), list(setcmd.values()))
                            get_cmd_list = wizmakecmd.getcommand(mac_addr, list(setcmd.keys()))

                    # print('<ALL> op_code %d, cmd_list: %s\n' % (op_code, cmd_list))
                    wizmsghangler.makecommands(cmd_list, op_code)
                    wizmsghangler.sendcommands()
                    # Set 명령 시 응답 처리 불필요
                    if not args.multiset:
                        wizmsghangler.parseresponse()
                    if args.getfile:
                        print('[All][Getfile] Get device [%s] info from \'%s\' commands\n' % (mac_addr, args.getfile))
                        wizmsghangler.get_filelog(mac_addr)
                # get config log
                # wizmsghangler.makecommands(get_cmd_list, OP_GETCOMMAND)
                # wizmsghangler.sendcommands()
                # wizmsghangler.parseresponse()
                
                # wizmsghangler.get_log() 

        ######################################################    
        # Single device config
        else:
            if args.fwfile:
                op_code = OP_FWUP
                print('Device %s Firmware upload' % mac_addr)
                # FUObj.setparam(mac_addr, args.fwfile)
                # FUObj.run()
                t_fwup = FWUploadThread()
                t_fwup.setparam(mac_addr, args.fwfile)
                t_fwup.start()
            elif args.search:
                op_code = OP_SEARCHALL
                print('Start to Search devices...')
                cmd_list = wizmakecmd.search()
            elif args.reset:
                print('Device %s Reset' % mac_addr)
                cmd_list = wizmakecmd.reset(mac_addr)
            elif args.factory:
                print('Device %s Factory reset' % mac_addr)
                cmd_list = wizmakecmd.factory_reset(mac_addr)
            elif args.setfile:
                op_code = OP_SETFILE
                print('[Setfile] Device [%s] Config from \'%s\' file.' % (mac_addr, args.setfile))
                cmd_list = wizmakecmd.set_value(mac_addr, args.setfile)
            elif args.getfile:
                op_code = OP_GETFILE
                print('[Getfile] Get device [%s] info from \'%s\' commands\n' % (mac_addr, args.getfile))
                cmd_list = wizmakecmd.get_value(mac_addr, args.getfile)
            else:   
                print('* Single devcie config: %s' % mac_addr)
                cmd_list = wizmakecmd.setcommand(mac_addr, list(setcmd.keys()), list(setcmd.values()))
                get_cmd_list = wizmakecmd.getcommand(mac_addr, list(setcmd.keys()))
            # print(get_cmd_list)
                    
        if args.all or args.multiset:
            if not args.fwfile:
                print('\nDevice configuration complete!')
        else:
            # print('<SINGLE> op_code %d, cmd_list: %s' % (op_code, cmd_list))
            wizmsghangler.makecommands(cmd_list, op_code)
            wizmsghangler.sendcommands()
            devnum = wizmsghangler.parseresponse()

    if args.search:
        print('\nSearch result: ' + str(devnum) + ' devices are detected')
        # print(wizmsghangler.mac_list)
        dev_name = wizmsghangler.devname
        mac_list = wizmsghangler.mac_list
        wizmakecmd.set_maclist(mac_list, dev_name)
        print('\nRefer to \'mac_list.txt\' file')
    elif not args.all:
        if op_code is OP_GETFILE:
            wizmsghangler.get_filelog(mac_addr)
        elif op_code is OP_SETFILE:
            print('\nDevice configuration from \'%s\' complete!' % args.setfile)
        elif args.multiset or args.factory or args.reset:
            pass
        elif op_code is OP_SETCOMMAND:
            print('\nDevice configuration complete!\n')

            # print('get_cmd_list: %s' % get_cmd_list)
            wizmsghangler.makecommands(get_cmd_list, OP_GETCOMMAND)
            wizmsghangler.sendcommands()
            wizmsghangler.parseresponse()
            
            wizmsghangler.get_log()
            

        