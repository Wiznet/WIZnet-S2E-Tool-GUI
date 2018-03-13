#!/usr/bin/python

import re
import sys
import io
import time
import logging
import threading
import getopt
import os
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
import binascii
from WIZMSGHandler import WIZMSGHandler
from WIZUDPSock import WIZUDPSock
from wizsocket.TCPClient import TCPClient

OP_SEARCHALL = 1
OP_SETIP = 2
OP_CHECKIP = 3
OP_FACTORYRESET = 4
OP_GETDETAIL = 5
OP_FWUP = 6

SOCK_CLOSE_STATE = 1
SOCK_OPENTRY_STATE = 2
SOCK_OPEN_STATE = 3
SOCK_CONNECTTRY_STATE = 4
SOCK_CONNECT_STATE = 5

idle_state = 1
datasent_state = 2

class FWUploadThread(threading.Thread):
    # initialization
    def __init__(self, conf_sock):
    # def __init__(self):
        threading.Thread.__init__(self)

        self.dest_mac = None
        self.bin_filename = None
        self.fd = None
        self.data = None
        self.client = None
        self.timer1 = None
        self.istimeout = 0
        self.serverip = None
        self.serverport = None

        self.sentbyte = 0

        self.resultflag = 0

        # UDP
        # conf_sock = WIZUDPSock(5000, 50001)
        # conf_sock.open()
        self.sockinfo = '%s' % conf_sock
        self.wizmsghangler = WIZMSGHandler(conf_sock)

    def setparam(self, dest_mac, binaryfile):
        self.dest_mac = dest_mac
        self.bin_filename = binaryfile
        self.fd = open(self.bin_filename, "rb")
        self.data = self.fd.read(-1)
        self.remainbytes = len(self.data)
        self.curr_ptr = 0 

        sys.stdout.write("Firmware file size: %r\n\n" % len(self.data))

    def myTimer(self):
        # sys.stdout.write('timer1 timeout\r\n')
        self.istimeout = 1

    def checkResult(self):
        return self.resultflag

    def jumpToApp(self):
        cmd_list = []
        # boot mode change: App boot mode
        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", " "])
        cmd_list.append(["AB", ""])
        self.wizmsghangler.makecommands(cmd_list, OP_FWUP)
        if 'TCP' in self.sockinfo:
            self.wizmsghangler.sendcommandsTCP()
        elif 'UDP' in self.sockinfo:
            self.wizmsghangler.sendcommands()

    # def run(self):
    def sendCmd(self, command):
        cmd_list = []
        self.resp = None

        # Send FW UPload request message
        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", " "])
        cmd_list.append([command, str(len(self.data))])
        # sys.stdout.write("cmd_list: %s\r\n" % cmd_list)
        self.wizmsghangler.makecommands(cmd_list, OP_FWUP)

        # if no reponse from device, retry for several times.
        for i in range(3):
            if 'TCP' in self.sockinfo:
                self.wizmsghangler.sendcommandsTCP()
            elif 'UDP' in self.sockinfo:
                self.wizmsghangler.sendcommands()
            self.resp = self.wizmsghangler.parseresponse()
            if self.resp is not '':
                break
            time.sleep(2)

    def run(self):
        self.resultflag = 0

        if self.resp is not '':
            resp = self.resp.decode('utf-8')
            # print('resp', resp)
            params = resp.split(':')
            sys.stdout.write('Dest IP: %s, Dest Port num: %r\r\n' % (params[0], int(params[1])))
            self.serverip = params[0]
            self.serverport = int(params[1])

        else:
            print('No response from device. Check the network or device status.')
            self.resultflag = -1
            sys.exit(0)

        try:
            self.client = TCPClient(2, params[0], int(params[1]))
        except:
            pass

        self.retrycheck = 0
        try:
            # sys.stdout.write("%r\r\n" % self.client.state)
            while True:
                
                if self.retrycheck > 10:
                    break

                self.retrycheck += 1
                if self.client.state is SOCK_CLOSE_STATE:
                    if self.timer1 is not None:
                        self.timer1.cancel()
                    cur_state = self.client.state
                    try:
                        self.client.open()
                        # sys.stdout.write('1 : %r\r\n' % self.client.getsockstate())
                        # sys.stdout.write("%r\r\n" % self.client.state)
                        if self.client.state is SOCK_OPEN_STATE:
                            sys.stdout.write('[%r] is OPEN\r\n' % (self.serverip))
                            # sys.stdout.write('[%r] client.working_state is %r\r\n' % (self.serverip, self.client.working_state))
                            time.sleep(0.5)
                    except Exception as e:
                        sys.stdout.write('%r\r\n' % e)

                elif self.client.state is SOCK_OPEN_STATE:
                    cur_state = self.client.state
                    # time.sleep(2)
                    try:
                        self.client.connect()
                        # sys.stdout.write('2 : %r' % self.client.getsockstate())
                        if self.client.state is SOCK_CONNECT_STATE:
                            sys.stdout.write('[%r] is CONNECTED\r\n' % (self.serverip))
                            # sys.stdout.write('[%r] client.working_state is %r\r\n' % (self.serverip, self.client.working_state))
                            # time.sleep(1)
                    except Exception as e:
                        sys.stdout.write('%r\r\n' % e)

                elif self.client.state is SOCK_CONNECT_STATE:
                    # if self.client.working_state == idle_state:
                        # sys.stdout.write('3 : %r' % self.client.getsockstate())
                    try:
                        while self.remainbytes is not 0:
                            if self.client.working_state == idle_state:
                                if self.remainbytes >= 1024:
                                    msg = bytearray(1024)
                                    msg[:] = self.data[self.curr_ptr:self.curr_ptr+1024]
                                    self.client.write(msg)
                                    self.sentbyte = 1024
                                    # sys.stdout.write('1024 bytes sent from at %r\r\n' % (self.curr_ptr))
                                    sys.stdout.write('[%s] 1024 bytes sent from at %r\r\n' % (self.serverip, self.curr_ptr))
                                    self.curr_ptr += 1024
                                    self.remainbytes -= 1024
                                else :
                                    msg = bytearray(self.remainbytes)
                                    msg[:] = self.data[self.curr_ptr:self.curr_ptr+self.remainbytes]
                                    self.client.write(msg)
                                    # sys.stdout.write('Last %r byte sent from at %r \r\n' % (self.remainbytes, self.curr_ptr))
                                    sys.stdout.write('[%s] Last %r byte sent from at %r \r\n' % (self.serverip, self.remainbytes, self.curr_ptr))
                                    self.curr_ptr += self.remainbytes
                                    self.remainbytes = 0
                                    self.sentbyte = self.remainbytes

                                self.client.working_state = datasent_state

                                self.timer1 = threading.Timer(2.0, self.myTimer)
                                self.timer1.start()
                            elif self.client.working_state == datasent_state:
                                # sys.stdout.write('4 : %r' % self.client.getsockstate())
                                response = self.client.readbytes(2)
                                if response is not None:
                                    if int(binascii.hexlify(response), 16):
                                        self.client.working_state = idle_state
                                        self.timer1.cancel()
                                        self.istimeout = 0
                                    else:
                                        print('ERROR: No response from device. Stop FW upload...')
                                        self.client.close()
                                        sys.exit(0)

                                if self.istimeout is 1:
                                    self.istimeout = 0
                                    self.client.working_state = idle_state
                                    self.client.close()
                                    self.resultflag = -1
                                    sys.exit(0)

                    except Exception as e:
                        sys.stdout.write('%r\r\n' % e)
                        response = ""
                    break
            
            print('retrycheck: %d' % self.retrycheck)
            if self.retrycheck > 10:
                sys.stdout.write('Device [%s] firmware upload fail.\r\n' % (self.dest_mac))
                self.resultflag = -1
            else:
                sys.stdout.write('Device [%s] firmware upload success!\r\n' % (self.dest_mac))
                self.resultflag = 1
            # send FIN packet 
            time.sleep(2.5)
            self.client.shutdown()
        except (KeyboardInterrupt, SystemExit):
            sys.stdout.write('%r\r\n' % e)
        finally:
            pass

if __name__=='__main__':

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hm:b:")
    except getopt.GetoptError:
        sys.stdout.write('Invalid syntax. Refer to below\r\n')
        sys.stdout.write('FWUpload.py -m <WIZ750SR mac address> -b <binary filename>\r\n)')
        sys.exit(0)

    for opt, arg in opts:
        if opt == '-h':
            sys.stdout.write('Valid syntax\r\n')
            sys.stdout.write('FWUpload.py -m <WIZ750SR mac address, format - xx:xx:xx:xx:xx:xx> -b <binary filename>\r\n')
            sys.stdout.write('  -m <WIZ750SR mac address>\r\n')
            sys.stdout.write('      mac address format is \"xx:xx:xx:xx:xx:xx\"\r\n')
            sys.stdout.write('  -b <binary filename>\r\n')
            sys.stdout.write('      binary filename is starting \"\\" and contains the whole path\r\n')
            sys.exit(0)
        elif opt in ("-m"):
            dst_mac = arg
            sys.stdout.write('Destination Mac: %r\r\n' % dst_mac)
        elif opt in ("-b"):
            bin_filename = arg
            sys.stdout.write('Filename to upload: %r\r\n' % bin_filename)

    FUObj = FWUpload(logging.DEBUG)
    # FUObj.setparam("00:08:dc:52:db:0b", "/home/javakys/localrepositories/WIZ750SR/Projects/S2E_App/bin/W7500x_S2E_App.bin")
    # FUObj.setparam("00:08:dc:1d:6a:4a", "/home/javakys/Downloads/W7500x_S2E_App.bin")
    FUObj.setparam(dst_mac, bin_filename)
    FUObj.run()