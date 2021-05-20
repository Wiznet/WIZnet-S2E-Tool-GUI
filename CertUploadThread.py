#!/usr/bin/python

import binascii
import sys
import time
import logging
import threading

from PyQt5 import QtCore
from wizsocket.TCPClient import TCPClient
from WIZUDPSock import WIZUDPSock
from WIZMSGHandler import WIZMSGHandler

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()

OP_SEARCHALL = 1
OP_SETIP = 2
OP_CHECKIP = 3
OP_FACTORYRESET = 4
OP_GETDETAIL = 5
OP_CERTUP = 6

SOCK_CLOSE_STATE = 11
SOCK_OPENTRY_STATE = 12
SOCK_OPEN_STATE = 13
SOCK_CONNECTTRY_STATE = 14
SOCK_CONNECT_STATE = 15

idle_state = 1
datasent_state = 2

PACKET_SIZE = 1024
# PACKET_SIZE = 2048

class CertUploadThread(QtCore.QThread):
    uploading_size = QtCore.pyqtSignal(int)
    upload_result = QtCore.pyqtSignal(int)
    error_flag = QtCore.pyqtSignal(int)

    def __init__(self, conf_sock, dest_mac, idcode, set_pw, cert, ipaddr, port, dev_name, mode_cmd):
        QtCore.QThread.__init__(self)

        self.dest_mac = None
        # self.bin_cert_name = cert_name
        self.fd = None
        self.data = None
        self.client = None
        self.timer1 = None
        self.istimeout = 0
        self.serverip = None
        self.serverport = None
        self.sentbyte = 0
        self.dest_mac = dest_mac
        self.idcode = idcode
        self.error_noresponse = 0
        self.retrycheck = 0

        # device name
        self.dev_name = dev_name
        self.set_pw = set_pw
        self.cert = cert
        self.mode_cmd = mode_cmd
        self.curr_ptr = 0

        self.cert_size = len(self.cert)
        self.remainbytes = self.cert_size

        self.conf_sock = conf_sock
        self.what_sock = '%s' % self.conf_sock

        # socket config (for TCP unicast)
        self.ip_addr = ipaddr
        self.port = port

        self.cli_sock = None

    def setparam(self):
        self.fd = open(self.bin_cert_name, "rb")
        self.data = self.fd.read(-1)
        self.curr_ptr = 0
        self.fd.close()

    def myTimer(self):
        # sys.stdout.write('timer1 timeout\r\n')
        self.istimeout = 1

    def sendCmd(self, command):
        cmd_list = []
        self.resp = None

        # Send certificate upload request message
        cmd_list.append(["MA", self.dest_mac])
        cmd_list.append(["PW", self.idcode])
        if 'WIZ510SSL' in self.dev_name:
            cmd_list.append(["AP", self.set_pw.decode()])
        cmd_list.append([command, str(self.cert_size)])

        print('sendCmd() cmd_list ===> ', cmd_list)

        if 'TCP' in self.what_sock:
            self.wizmsghangler = WIZMSGHandler(
                self.conf_sock, cmd_list, 'tcp', OP_CERTUP, 2)
        elif 'UDP' in self.what_sock:
            self.wizmsghangler = WIZMSGHandler(
                self.conf_sock, cmd_list, 'udp', OP_CERTUP, 2)
        sys.stdout.write("sendCmd(): %s\r\n" % cmd_list)

        # if no reponse from device, retry for several times.
        for i in range(4):
            # self.resp = self.wizmsghangler.parseresponse()
            self.resp = self.wizmsghangler.run()
            if self.resp is not '':
                break
            self.msleep(1)

        self.msleep(500)
        self.uploading_size.emit(2)

    def run(self):
        # self.setparam()
        print('=======>> certificate upload', self.dev_name)

        if 'UDP' in self.what_sock:
            pass
        elif 'TCP' in self.what_sock:
            self.sock_close()
            self.SocketConfig()

        self.sendCmd(self.mode_cmd)

        if self.resp is not '' and self.resp is not None:
            resp = self.resp.decode('utf-8')
            # print('resp', resp)
            params = resp.split(':')
            sys.stdout.write('Dest IP: %s, Dest Port num: %r\r\n' %
                             (params[0], int(params[1])))
            self.serverip = params[0]
            self.serverport = int(params[1])

            self.uploading_size.emit(3)
        else:
            print('No response from device. Check the network or device status.')
            self.error_flag.emit(-1)
            self.error_noresponse = -1
        try:
            self.client = TCPClient(2, params[0], int(params[1]))
        except:
            pass
        try:
            if self.error_noresponse < 0:
                pass
            else:
                # sys.stdout.write("%r\r\n" % self.client.state)
                while True:
                    if self.retrycheck > 6:
                        break

                    self.retrycheck += 1
                    if self.client.state is SOCK_CLOSE_STATE:
                        if self.timer1 is not None:
                            self.timer1.cancel()
                        # cur_state = self.client.state
                        try:
                            self.client.open()
                            # sys.stdout.write('1 : %r\r\n' % self.client.getsockstate())
                            # sys.stdout.write("%r\r\n" % self.client.state)
                            if self.client.state is SOCK_OPEN_STATE:
                                sys.stdout.write(
                                    '[%r] is OPEN\r\n' % (self.serverip))
                                # sys.stdout.write('[%r] client.working_state is %r\r\n' % (self.serverip, self.client.working_state))
                                self.msleep(500)
                        except Exception as e:
                            sys.stdout.write('%r\r\n' % e)

                    elif self.client.state is SOCK_OPEN_STATE:
                        self.uploading_size.emit(4)
                        # cur_state = self.client.state
                        try:
                            self.client.connect()
                            # sys.stdout.write('2 : %r' % self.client.getsockstate())
                            if self.client.state is SOCK_CONNECT_STATE:
                                sys.stdout.write(
                                    '[%r] is CONNECTED\r\n' % (self.serverip))
                                # sys.stdout.write('[%r] client.working_state is %r\r\n' % (self.serverip, self.client.working_state))
                        except Exception as e:
                            sys.stdout.write('%r\r\n' % e)

                    elif self.client.state is SOCK_CONNECT_STATE:
                        # if self.client.working_state == idle_state:
                            # sys.stdout.write('3 : %r' % self.client.getsockstate())
                        try:
                            self.uploading_size.emit(5)
                            while self.remainbytes is not 0:
                                if self.client.working_state == idle_state:
                                    if self.remainbytes >= PACKET_SIZE:
                                        msg = bytearray(PACKET_SIZE)
                                        msg[:] = self.data[self.curr_ptr:self.curr_ptr +
                                                           PACKET_SIZE]
                                        self.client.write(msg)
                                        self.sentbyte = PACKET_SIZE
                                        # sys.stdout.write('PACKET_SIZE bytes sent from at %r\r\n' % (self.curr_ptr))
                                        sys.stdout.write('[%s] PACKET_SIZE bytes sent from at %r\r\n' % (
                                            self.serverip, self.curr_ptr))
                                        self.curr_ptr += PACKET_SIZE
                                        self.remainbytes -= PACKET_SIZE
                                    else:
                                        self.uploading_size.emit(6)
                                        msg = bytearray(self.remainbytes)
                                        msg[:] = self.data[self.curr_ptr:self.curr_ptr +
                                                           self.remainbytes]
                                        self.client.write(msg)
                                        # sys.stdout.write('Last %r byte sent from at %r \r\n' % (self.remainbytes, self.curr_ptr))
                                        sys.stdout.write('[%s] Last %r byte sent from at %r \r\n' % (
                                            self.serverip, self.remainbytes, self.curr_ptr))
                                        self.curr_ptr += self.remainbytes
                                        self.remainbytes = 0
                                        self.sentbyte = self.remainbytes

                                    self.client.working_state = datasent_state

                                    self.timer1 = threading.Timer(
                                        2.0, self.myTimer)
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
                                            print('ERROR: No response from device. Stop certificate upload...')
                                            self.client.close()
                                            self.upload_result.emit(-1)
                                            self.terminate()

                                    if self.istimeout is 1:
                                        self.istimeout = 0
                                        self.client.working_state = idle_state
                                        self.client.close()
                                        self.upload_result.emit(-1)
                                        self.terminate()

                                self.uploading_size.emit(7)

                        except Exception as e:
                            sys.stdout.write('%r\r\n' % e)
                            response = ""
                        break

            print('retrycheck: %d' % self.retrycheck)

            if self.retrycheck > 6 or self.error_noresponse < 0:
                sys.stdout.write(
                    'Device [%s] firmware upload fail.\r\n' % (self.dest_mac))
                self.upload_result.emit(-1)
            elif self.error_noresponse >= 0:
                self.uploading_size.emit(8)
                sys.stdout.write(
                    'Device [%s] firmware upload success!\r\n' % (self.dest_mac))
                self.upload_result.emit(1)
                # send FIN packet
                self.msleep(500)
                self.client.shutdown()
                if 'TCP' in self.what_sock:
                    self.conf_sock.shutdown()
        except Exception as e:
            self.error_flag.emit(-3)
            sys.stdout.write('%r\r\n' % e)
        finally:
            pass

    def sock_close(self):
        # 기존 연결 fin
        if self.cli_sock is not None:
            if self.cli_sock.state is not SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()
        if self.conf_sock is not None:
            self.conf_sock.shutdown()

    def tcpConnection(self, serverip, port):
        retrynum = 0
        self.cli_sock = TCPClient(2, serverip, port)
        print('sock state: %r' % (self.cli_sock.state))

        while True:
            if retrynum > 6:
                break
            retrynum += 1

            if self.cli_sock.state is SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()
                # cur_state = self.cli_sock.state
                try:
                    self.cli_sock.open()
                    if self.cli_sock.state is SOCK_OPEN_STATE:
                        print('[%r] is OPEN' % (serverip))
                    time.sleep(0.5)
                except Exception as e:
                    sys.stdout.write('%r\r\n' % e)
            elif self.cli_sock.state is SOCK_OPEN_STATE:
                # cur_state = self.cli_sock.state
                try:
                    self.cli_sock.connect()
                    if self.cli_sock.state is SOCK_CONNECT_STATE:
                        print('[%r] is CONNECTED' % (serverip))
                except Exception as e:
                    sys.stdout.write('%r\r\n' % e)
            elif self.cli_sock.state is SOCK_CONNECT_STATE:
                break
        if retrynum > 6:
            sys.stdout.write(
                'Device [%s] TCP connection failed.\r\n' % (serverip))
            return None
        else:
            sys.stdout.write('Device [%s] TCP connected\r\n' % (serverip))
            return self.cli_sock

    def SocketConfig(self):
        # Broadcast
        if 'UDP' in self.what_sock:
            self.conf_sock = WIZUDPSock(5000, 50001)
            self.conf_sock.open()

        # TCP unicast
        elif 'TCP' in self.what_sock:
            print('upload_unicast: ip: %r, port: %r' %
                  (self.ip_addr, self.port))

            self.conf_sock = self.tcpConnection(self.ip_addr, self.port)

            if self.conf_sock is None:
                # self.isConnected = False
                print('TCP connection failed!: %s' % self.conf_sock)
                self.error_flag.emit(-3)
                self.terminate()
            else:
                self.isConnected = True
