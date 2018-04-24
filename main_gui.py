# -*- coding: utf-8 -*-

import sys
import time
import re
import os
import subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize, QThread, Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5 import uic
import ifaddr

from WIZMSGHandler import *
from FWUploadThread import FWUploadThread
from WIZUDPSock import WIZUDPSock
from WIZ750CMDSET import WIZ750CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from WIZMakeCMD import *
from wizsocket.TCPClient import TCPClient

OP_SEARCHALL = 1
OP_GETCOMMAND = 2
OP_SETCOMMAND = 3
OP_SETFILE = 4
OP_GETFILE = 5
OP_FWUP = 6

SOCK_CLOSE_STATE = 1
SOCK_OPENTRY_STATE = 2
SOCK_OPEN_STATE = 3
SOCK_CONNECTTRY_STATE = 4
SOCK_CONNECT_STATE = 5

ONE_PORT_DEV = ['WIZ750SR', 'WIZ750SR-100', 'WIZ750SR-105', 'WIZ750SR-110', 'WIZ107SR', 'WIZ108SR']
TWO_PORT_DEV = ['WIZ752SR-12x', 'WIZ752SR-120','WIZ752SR-125']

VERSION = '0.5.0 beta'

def resource_path(relative_path):
# Get absolute path to resource, works for dev and for PyInstaller
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Load ui files
main_window = uic.loadUiType(resource_path('gui/wizconfig_gui.ui'))[0]

class WIZWindow(QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle('WIZnet S2E Configuration Tool ' + VERSION)

        # Main icon
        self.setWindowIcon(QIcon(resource_path('gui/icon.ico')))
        self.SetBtnIcon()

        self.wiz750cmdObj = WIZ750CMDSET(1)
        self.wiz752cmdObj = WIZ752CMDSET(1)
        self.wizmakecmd = WIZMakeCMD()

        self.mac_list = []
        self.vr_list = []
        self.threads = []
        self.curr_mac = None
        self.curr_dev = None
        self.curr_ver = None

        self.isConnected = False
        self.set_reponse = None
        self.wizmsghandler = None

        # device select event
        self.list_device.itemClicked.connect(self.DevClicked)

        ## Button event
        self.btnsearch.clicked.connect(self.PreSearch)
        self.btnsetting.clicked.connect(self.Setting)
        self.resetbtn.clicked.connect(self.ResetPopUp)
        self.factorybtn.clicked.connect(self.FactoryPopUp)

        # configuration save/load button
        self.savebtn.clicked.connect(self.SaveFileDialog)
        self.loadbtn.clicked.connect(self.LoadFileDialog)

        self.fwupbtn.clicked.connect(self.UpdateBtnClicked)
        self.exitbtn.clicked.connect(self.ExitPopUp)

        # State Changed Event 
        self.show_idcode.stateChanged.connect(self.ShowIDcode)
        self.show_connectpw.stateChanged.connect(self.ShowPW)
        self.show_idcodeinput.stateChanged.connect(self.IDcodeInput)
        self.enable_connect_pw.stateChanged.connect(self.EnablePW)
        self.at_enable.stateChanged.connect(self.EnableATmode)
        self.ch1_keepalive_enable.stateChanged.connect(self.EnableKeepAlive)
        self.ch2_keepalive_enable.stateChanged.connect(self.EnableKeepAlive)

        self.ip_dhcp.clicked.connect(self.IPAllocEvent)
        self.ip_static.clicked.connect(self.IPAllocEvent)

        # Event: OP mode
        self.ch1_tcpclient.clicked.connect(self.OPmodeEvent)
        self.ch1_tcpserver.clicked.connect(self.OPmodeEvent)
        self.ch1_tcpmixed.clicked.connect(self.OPmodeEvent)
        self.ch1_udp.clicked.connect(self.OPmodeEvent)

        self.ch2_tcpclient.clicked.connect(self.OPmodeEvent)
        self.ch2_tcpserver.clicked.connect(self.OPmodeEvent)
        self.ch2_tcpmixed.clicked.connect(self.OPmodeEvent)
        self.ch2_udp.clicked.connect(self.OPmodeEvent)

        # Event: Search method
        self.broadcast.clicked.connect(self.SearchMethodEvent)
        self.unicast_ip.clicked.connect(self.SearchMethodEvent)
        self.unicast_mac.clicked.connect(self.SearchMethodEvent)

        self.pgbar = QProgressBar()
        self.statusbar.addPermanentWidget(self.pgbar)

        # progress thread
        self.th_search = ThreadProgress()
        self.th_search.change_value.connect(self.valueChanged)

        # check if device selected
        self.list_device.itemSelectionChanged.connect(self.IfDevSelected)

        # Menu event
        self.actionSaveconfig.triggered.connect(self.SaveFileDialog)
        self.actionLoadconfig.triggered.connect(self.LoadFileDialog)
        self.about_wiz.triggered.connect(self.ProgramInfo)

        # Network setup menu
        self.getNetInfo()
        self.netconfig_menu.triggered[QAction].connect(self.NetSelected)

        # Tab changed
        self.generalTab.currentChanged.connect(self.TabChanged)

        # data refresh
        self.refresh_no.clicked.connect(self.GetRefreshTime)
        self.refresh_1s.clicked.connect(self.GetRefreshTime)
        self.refresh_5s.clicked.connect(self.GetRefreshTime)
        self.refresh_10s.clicked.connect(self.GetRefreshTime)
        self.refresh_30s.clicked.connect(self.GetRefreshTime)

        # gpio config
        self.gpioa_config.currentIndexChanged.connect(self.CheckGPIO)
        self.gpiob_config.currentIndexChanged.connect(self.CheckGPIO)
        self.gpioc_config.currentIndexChanged.connect(self.CheckGPIO)
        self.gpiod_config.currentIndexChanged.connect(self.CheckGPIO)

    def TabChanged(self):
        # self.SelectedDev()
        if self.generalTab.currentIndex() == 0:
            if self.datarefresh is not None:
                if self.datarefresh.isRunning():
                    self.datarefresh.terminate()
        elif self.generalTab.currentIndex() == 1:
            self.CheckGPIO()
            self.GetRefreshTime()

    def NetSelected(self, netifs):
        print('NetSelected() %s: %s' % (netifs.text(), self.ifs_list[netifs.text()]))

    def valueChanged(self, value):
        self.pgbar.show()
        self.pgbar.setValue(value)

    def IfDevSelected(self):
        if len(self.list_device.selectedItems()) == 0:
            self.DisableObject()
        else:
            self.EnableObject()
    
    ### Get adapter list (ing)
    def getNetInfo(self):
        self.netconfig_menu = QMenu('Network config', self)
        self.menuOption.addMenu(self.netconfig_menu)

        adapters = ifaddr.get_adapters() 
        self.ifs_list = {}
        self.net_list = []
        
        for adapter in adapters:
            print("Interface:", adapter.nice_name)
            
            for ip in adapter.ips:
                if len(ip.ip) > 6:
                    ipv4_addr = ip.ip
                    if ipv4_addr == '127.0.0.1':
                        pass
                    else:
                        self.ifs_list[adapter.nice_name] = ipv4_addr

                        # get network interface list
                        self.net_list.append(adapter.nice_name)
                        netconfig = QAction(adapter.nice_name, self)
                        self.netconfig_menu.addAction(netconfig)
                else:
                    ipv6_addr = ip.ip
        # print('net list: ', self.ifs_list)

    def DisableObject(self):
        self.resetbtn.setEnabled(False)
        self.factorybtn.setEnabled(False)
        self.fwupbtn.setEnabled(False)
        self.btnsetting.setEnabled(False)
        self.savebtn.setEnabled(False)
        self.loadbtn.setEnabled(False)

        self.generalTab.setEnabled(False)
        self.channel_tab.setEnabled(False)
    
    def EnableObject(self):
        self.SelectedDev()

        # 버튼 활성화
        self.resetbtn.setEnabled(True)
        self.factorybtn.setEnabled(True)
        self.fwupbtn.setEnabled(True)
        self.btnsetting.setEnabled(True)
        self.savebtn.setEnabled(True)
        self.loadbtn.setEnabled(True)

        # 창 활성화
        self.generalTab.setEnabled(True)
        self.generalTab.setTabEnabled(0, True)
        self.generalTab.setTabEnabled(1, True)
        self.refresh_grp.setEnabled(True)
        self.exp_gpio.setEnabled(True)

        self.channel_tab.setEnabled(True)
        self.EnablePW()

        # device's port number check
        if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev:
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, False)
            self.channel_tab.setTabEnabled(2, False)
            self.channel_tab.setTabEnabled(3, False)
        elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, True)
            self.channel_tab.setTabEnabled(2, False)
            self.channel_tab.setTabEnabled(3, False)
        
        # enable menu
        self.save_config.setEnabled(True)
        self.load_config.setEnabled(True)

        self.OPmodeEvent()
        self.IPAllocEvent()
        self.EnableATmode()
        self.EnableATmode()
        self.EnableKeepAlive()

        self.CheckGPIO()

    def CheckGPIO(self):
        if self.gpioa_config.currentIndex() == 1: self.gpioa_set.setEnabled(True)
        else: self.gpioa_set.setEnabled(False)
        if self.gpiob_config.currentIndex() == 1: self.gpiob_set.setEnabled(True)
        else: self.gpiob_set.setEnabled(False)
        if self.gpioc_config.currentIndex() == 1: self.gpioc_set.setEnabled(True)
        else: self.gpioc_set.setEnabled(False)
        if self.gpiod_config.currentIndex() == 1: self.gpiod_set.setEnabled(True)
        else: self.gpiod_set.setEnabled(False)

    def IPAllocEvent(self):
        if self.ip_dhcp.isChecked() is True:
            self.network_config.setEnabled(False)
        elif self.ip_dhcp.isChecked() is False:
            self.network_config.setEnabled(True)

    def EnableKeepAlive(self):
        if self.ch1_keepalive_enable.isChecked() is True:
            self.ch1_keepalive_initial.setEnabled(True)
            self.ch1_keepalive_retry.setEnabled(True)
        elif self.ch1_keepalive_enable.isChecked() is False:
            self.ch1_keepalive_initial.setEnabled(False)
            self.ch1_keepalive_retry.setEnabled(False)

        if self.ch2_keepalive_enable.isChecked() is True:
            self.ch2_keepalive_initial.setEnabled(True)
            self.ch2_keepalive_retry.setEnabled(True)
        elif self.ch2_keepalive_enable.isChecked() is False:
            self.ch2_keepalive_initial.setEnabled(False)
            self.ch2_keepalive_retry.setEnabled(False)
    
    def EnableATmode(self):
        if self.at_enable.isChecked() is True:
            self.at_hex1.setEnabled(True)
            self.at_hex2.setEnabled(True)
            self.at_hex3.setEnabled(True)
        elif self.at_enable.isChecked() is False:
            self.at_hex1.setEnabled(False)
            self.at_hex2.setEnabled(False)
            self.at_hex3.setEnabled(False)

    def IDcodeInput(self):
        if self.show_idcodeinput.isChecked() is True:
            self.searchcode_input.setEchoMode(QLineEdit.Normal)
        elif self.show_idcodeinput.isChecked() is False:
            self.searchcode_input.setEchoMode(QLineEdit.Password)

    def ShowIDcode(self):
        if self.show_idcode.isChecked() is True:
            self.searchcode.setEchoMode(QLineEdit.Normal)
        elif self.show_idcode.isChecked() is False:
            self.searchcode.setEchoMode(QLineEdit.Password)

    def ShowPW(self):
        if self.show_connectpw.isChecked() is True:
            self.connect_pw.setEchoMode(QLineEdit.Normal)
        elif self.show_connectpw.isChecked() is False:
            self.connect_pw.setEchoMode(QLineEdit.Password)

    def EnablePW(self):
        if self.enable_connect_pw.isChecked() is True:
            self.connect_pw.setEnabled(True)
        elif self.enable_connect_pw.isChecked() is False:
            self.connect_pw.setEnabled(False)

    def OPmodeEvent(self):
        if self.ch1_tcpclient.isChecked() is True:
            self.ch1_remote.setEnabled(True)
        elif self.ch1_tcpserver.isChecked() is True:
            self.ch1_remote.setEnabled(False)
        elif self.ch1_tcpmixed.isChecked() is True:
            self.ch1_remote.setEnabled(True)
        elif self.ch1_udp.isChecked() is True:
            self.ch1_remote.setEnabled(True)

        if self.ch2_tcpclient.isChecked() is True:
            self.ch2_remote.setEnabled(True)
        elif self.ch2_tcpserver.isChecked() is True:
            self.ch2_remote.setEnabled(False)
        elif self.ch2_tcpmixed.isChecked() is True:
            self.ch2_remote.setEnabled(True)
        elif self.ch2_udp.isChecked() is True:
            self.ch2_remote.setEnabled(True)

    def SearchMethodEvent(self):
        if self.broadcast.isChecked() is True:
            pass
        elif self.unicast_ip.isChecked() is True:
            self.search_ipaddr.setEnabled(True)
            self.search_port.setEnabled(True)
            self.search_macaddr.setEnabled(False)
        elif self.unicast_mac.isChecked() is True:
            self.search_macaddr.setEnabled(True)
            self.search_ipaddr.setEnabled(False)
            self.search_port.setEnabled(False)

    def tcpConnection(self, serverip, port):
        retrynum = 0
        cli_sock = TCPClient(2, serverip, port)
        print('sock state: %r' % (cli_sock.state))

        # 기존 연결 fin 
        if cli_sock.state is not SOCK_CLOSE_STATE:
            cli_sock.shutdown()

        while True:
            if retrynum > 6:
                break
            retrynum += 1

            if cli_sock.state is SOCK_CLOSE_STATE:
                cli_sock.shutdown()
                cur_state = cli_sock.state
                try:
                    cli_sock.open()
                    if cli_sock.state is SOCK_OPEN_STATE:
                        print('[%r] is OPEN' % (serverip))
                    time.sleep(0.5)
                except Exception as e:
                    sys.stdout.write('%r\r\n' % e)
            elif cli_sock.state is SOCK_OPEN_STATE:
                cur_state = cli_sock.state
                try:
                    cli_sock.connect()
                    if cli_sock.state is SOCK_CONNECT_STATE:
                        print('[%r] is CONNECTED' % (serverip))
                except Exception as e:
                    sys.stdout.write('%r\r\n' % e)
            elif cli_sock.state is SOCK_CONNECT_STATE:
                break
        if retrynum > 6:
            sys.stdout.write('Device [%s] TCP connection failed.\r\n' % (serverip))
            return None
        else:
            sys.stdout.write('Device [%s] TCP connected\r\n' % (serverip))
            return cli_sock

    def SocketConfig(self):
        # Broadcast
        if self.broadcast.isChecked() or self.unicast_mac.isChecked():
            self.conf_sock = WIZUDPSock(5000, 50001)
            self.conf_sock.open()

        # TCP unicast
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            print('unicast: ip: %r, port: %r' % (ip_addr, port))

            ## network check
            net_response = self.NetworkCheck(ip_addr)

            if net_response == 0:
                self.conf_sock = self.tcpConnection(ip_addr, port)

                if self.conf_sock is None:
                    self.isConnected = False
                    print('TCP connection failed!: %s' % self.conf_sock)
                    self.statusbar.showMessage(' TCP connection failed: %s' % ip_addr)
                    self.ConnectionFailPopUp()
                else:
                    self.isConnected = True
            else:
                self.statusbar.showMessage(' Network unreachable: %s' % ip_addr)
                self.NetworkNotConnected(ip_addr)

    # expansion GPIO config
    def RefreshGPIO(self, mac_addr):
        if self.wizmsghandler is not None and self.wizmsghandler.isRunning():
            self.wizmsghandler.wait()
        else:
            for thread in self.threads:
                thread.terminate()
            ##
            cmd_list = []
            if self.isConnected or self.broadcast.isChecked():
                # if len(self.searchcode_input.text()) == 0: 
                if not self.searchcode_input.text():
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.get_gpiovalue(mac_addr, self.code)
                # print('RefreshGPIO', cmd_list)

                if self.unicast_ip.isChecked():
                    self.datarefresh = DataRefresh(self.conf_sock, cmd_list, 'tcp', self.intv_time)
                else:
                    self.datarefresh = DataRefresh(self.conf_sock, cmd_list, 'udp', self.intv_time)
                self.threads.append(self.datarefresh)
                self.datarefresh.resp_check.connect(self.UpdateGPIO)
                self.datarefresh.start()
        
    def GetRefreshTime(self):
        self.SelectedDev()

        if self.refresh_no.isChecked() is True: 
            self.intv_time = 0
        elif self.refresh_1s.isChecked() is True: 
            self.intv_time = 1
        elif self.refresh_5s.isChecked() is True: 
            self.intv_time = 5
        elif self.refresh_10s.isChecked() is True: 
            self.intv_time = 10
        elif self.refresh_30s.isChecked() is True: 
            self.intv_time = 30
        
        self.RefreshGPIO(self.curr_mac)

    def UpdateGPIO(self, num):
        if num == 0:
            pass
        else:
            if not self.datarefresh.rcv_list:
                pass
            else:
                resp = self.datarefresh.rcv_list[0]
                cmdset_list = resp.splitlines()

                ## Expansion GPIO
                for i in range(len(cmdset_list)):
                    if num < 3:
                        if b'CA' in cmdset_list[i]: self.gpioa_config.setCurrentIndex(int(cmdset_list[i][2:]))
                        if b'CB' in cmdset_list[i]: self.gpiob_config.setCurrentIndex(int(cmdset_list[i][2:]))
                        if b'CC' in cmdset_list[i]: self.gpioc_config.setCurrentIndex(int(cmdset_list[i][2:]))
                        if b'CD' in cmdset_list[i]: self.gpiod_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            
                    if b'GA' in cmdset_list[i]: self.gpioa_get.setText(cmdset_list[i][2:].decode())
                    if b'GB' in cmdset_list[i]: self.gpiob_get.setText(cmdset_list[i][2:].decode())
                    if b'GC' in cmdset_list[i]: self.gpioc_get.setText(cmdset_list[i][2:].decode())
                    if b'GD' in cmdset_list[i]: self.gpiod_get.setText(cmdset_list[i][2:].decode())

    def PreSearch(self):
        if self.wizmsghandler is not None and self.wizmsghandler.isRunning():
            self.wizmsghandler.wait()
            print('wait')
        else:
            cmd_list = []
            self.code = " "
            self.all_response = None
            self.pgbar.setFormat('Searching..')
            self.pgbar.setRange(0, 100)
            self.th_search.start()
            self.Processing()

            # List table initial
            self.list_device.clear()
            while self.list_device.rowCount() > 0:
                self.list_device.removeRow(0)
            item = QTableWidgetItem()
            item.setText("Mac addr")
            self.list_device.setHorizontalHeaderItem(0, item)
            item = QTableWidgetItem()
            item.setText("Name")
            self.list_device.setHorizontalHeaderItem(1, item)
            
            self.SocketConfig()
            # print('search: conf_sock: %s' % self.conf_sock)
            
            # Search devices
            if self.isConnected or self.broadcast.isChecked():
                self.statusbar.showMessage(' Searching devices...')

                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.presearch("FF:FF:FF:FF:FF:FF", self.code)
                # print(cmd_list)

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SEARCHALL, 3)
                else:
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SEARCHALL, 3)
                self.wizmsghandler.search_result.connect(self.getSearchResult)
                self.wizmsghandler.start()


    def Processing(self):
        self.btnsearch.setEnabled(False)
        # QTimer.singleShot(1500, lambda: self.btnsearch.setEnabled(True))
        QTimer.singleShot(4500, lambda: self.pgbar.hide())

    def SingleSearch(self, dev_info_list):
        cmd_list = []
        self.eachdev_info = []

        self.code = " "
        # self.all_response = None
        self.pgbar.setFormat('Search for each device...')
        self.SocketConfig()

        # Search devices
        if self.isConnected or self.broadcast.isChecked():
            self.statusbar.showMessage(' Get each device information...')

            if len(self.searchcode_input.text()) == 0: self.code = " "
            else: self.code = self.searchcode_input.text()

            # dev_info => [mac_addr, name, version]
            for dev_info in dev_info_list:
                # print('dev_info', dev_info)
                cmd_list = self.wizmakecmd.search(dev_info[0], self.code, dev_info[1], dev_info[2])
                # print(cmd_list)
                th_name = "dev_%s" % dev_info[0]
                if self.unicast_ip.isChecked(): 
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SEARCHALL, 2)
                else: 
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SEARCHALL, 1)
                th_name.searched_data.connect(self.getSingleSearch)
                th_name.start()
                th_name.wait()

    def getSingleSearch(self, dev_data):
        # print('getSingleSearch', dev_data)
        if dev_data is not None:
            self.eachdev_info.append(dev_data)
            # print('eachdev_info', self.eachdev_info)
            self.all_response = self.eachdev_info
        else:
            pass

    def getSearchResult(self, devnum):
        # init info
        self.dev_name = None
        self.mac_list = None
        self.vr_list = None

        if self.wizmsghandler.isRunning():
            self.wizmsghandler.wait()
        if devnum >= 0:
            self.btnsearch.setEnabled(True)

            if devnum == 0:
                print('No device.')
            else:
                self.mac_list = self.wizmsghandler.mac_list
                self.dev_name = self.wizmsghandler.mn_list
                self.vr_list = self.wizmsghandler.vr_list

                self.all_response = self.wizmsghandler.rcv_list
            
                # row length = the number of searched devices
                self.list_device.setRowCount(len(self.mac_list))
                
                for i in range(0, len(self.mac_list)):
                    # device = "%s | %s" % (self.mac_list[i].decode(), self.dev_name[i].decode())
                    self.list_device.setItem(i, 0, QTableWidgetItem(self.mac_list[i].decode()))
                    self.list_device.setItem(i, 1, QTableWidgetItem(self.dev_name[i].decode()))

                # resize for data
                self.list_device.resizeColumnsToContents()
                self.list_device.resizeRowsToContents()
                
                # row/column resize diable
                self.list_device.horizontalHeader().setSectionResizeMode(2)
                self.list_device.verticalHeader().setSectionResizeMode(2)

            self.statusbar.showMessage(' Find %d devices' % devnum)

            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()

            self.get_dev_list()
            # self.GetDevProfile()
        else: 
            print('search error')

    def get_dev_list(self):
        # basic_data = None
        self.searched_dev = []
        self.dev_data = {}
        
        print(self.mac_list, self.dev_name, self.vr_list)
        for i in range(len(self.mac_list)):
            # name = 'dev%d' % i
            self.searched_dev.append([self.mac_list[i].decode(), self.dev_name[i].decode(), self.vr_list[i].decode()])
            self.dev_data[self.mac_list[i].decode()] = [self.dev_name[i].decode(), self.vr_list[i].decode()]

        # print('searched_dev', self.searched_dev)
        self.SingleSearch(self.searched_dev)

    def DevClicked(self):
        dev_info = []
        if self.generalTab.currentIndex() == 1:
            self.CheckGPIO()
            self.GetRefreshTime()
        for currentItem in self.list_device.selectedItems():
            # print('Click info:', currentItem, currentItem.row(), currentItem.column(), currentItem.text(), self.list_device.selectedItems()[0].row())
            self.getdevinfo(currentItem.row())
    
    def ObjectConfig(self):
        if 'WIZ752' in self.curr_dev:
            self.tcp_timeout.setEnabled(False)
            self.generalTab.setTabEnabled(1, False)
        else:
            self.tcp_timeout.setEnabled(True)
            self.generalTab.setTabEnabled(1, True)

    def FillInfo(self, cmdset_list):
        self.SelectedDev()
        # print('FillInfo: cmdset_list', cmdset_list)
        self.ObjectConfig()

        for i in range(len(cmdset_list)):
            # device info (RO)
            if b'VR' in cmdset_list[i]: self.fw_version.setText(cmdset_list[i][2:].decode())
            # device info - channel 1
            if b'ST' in cmdset_list[i]: self.ch1_status.setText(cmdset_list[i][2:].decode())
            if b'UN' in cmdset_list[i]: self.ch1_uart_name.setText(cmdset_list[i][2:].decode())
            # Network - general
            if b'IM' in cmdset_list[i]: 
                if cmdset_list[i][2:].decode() == '0': self.ip_static.setChecked(True)
                elif cmdset_list[i][2:].decode() == '1': self.ip_dhcp.setChecked(True)
            if b'LI' in cmdset_list[i]: 
                if 'VALID' in cmdset_list[i][2:].decode():
                    pass
                else:
                    self.localip.setText(cmdset_list[i][2:].decode())
                    self.localip_addr = cmdset_list[i][2:].decode()
            if b'SM' in cmdset_list[i]: self.subnet.setText(cmdset_list[i][2:].decode())
            if b'GW' in cmdset_list[i]: self.gateway.setText(cmdset_list[i][2:].decode())
            if b'DS' in cmdset_list[i]: self.dns_addr.setText(cmdset_list[i][2:].decode())
            # TCP transmisstion retry count
            if b'TR' in cmdset_list[i]: 
                if cmdset_list[i][2:].decode() == '0':
                    self.tcp_timeout.setText('8')
                else:
                    self.tcp_timeout.setText(cmdset_list[i][2:].decode())
            # etc - general
            if b'CP' in cmdset_list[i]: 
                self.enable_connect_pw.setChecked(int(cmdset_list[i][2:].decode()))
            if b'NP' in cmdset_list[i]: 
                if cmdset_list[i][2:].decode() == ' ':
                    self.connect_pw.setText(None)
                else:
                    self.connect_pw.setText(cmdset_list[i][2:].decode())
            # command mode (AT mode)
            if b'TE' in cmdset_list[i]: self.at_enable.setChecked(int(cmdset_list[i][2:].decode()))
            if b'SS' in cmdset_list[i]:
                self.at_hex1.setText(cmdset_list[i][2:4].decode())
                self.at_hex2.setText(cmdset_list[i][4:6].decode())
                self.at_hex3.setText(cmdset_list[i][6:8].decode())
            # search id code
            if b'SP' in cmdset_list[i]:
                if cmdset_list[i][2:].decode() == ' ':
                    pass
            # Debug msg - for test
            if b'DG' in cmdset_list[i]: 
                if int(cmdset_list[i][2:].decode()) < 2:
                    self.serial_debug.setCurrentIndex(int(cmdset_list[i][2:]))
                elif cmdset_list[i][2:].decode() == '4':
                    self.serial_debug.setCurrentIndex(2)

            # Network - channel 1
            if b'OP' in cmdset_list[i]:
                if cmdset_list[i][2:].decode() == '0': 
                    self.ch1_tcpclient.setChecked(True)
                elif cmdset_list[i][2:].decode() == '1': 
                    self.ch1_tcpserver.setChecked(True)
                elif cmdset_list[i][2:].decode() == '2': 
                    self.ch1_tcpmixed.setChecked(True)
                elif cmdset_list[i][2:].decode() == '3': 
                    self.ch1_udp.setChecked(True)
            if b'LP' in cmdset_list[i]: self.ch1_localport.setText(cmdset_list[i][2:].decode())
            if b'RH' in cmdset_list[i]: self.ch1_remoteip.setText(cmdset_list[i][2:].decode())
            if b'RP' in cmdset_list[i]: self.ch1_remoteport.setText(cmdset_list[i][2:].decode())
            # serial - channel 1
            if b'BR' in cmdset_list[i]: self.ch1_baud.setCurrentIndex(int(cmdset_list[i][2:]))
            if b'DB' in cmdset_list[i]: 
                if (len(cmdset_list[i][2:]) > 2): pass 
                else: 
                    self.ch1_databit.setCurrentIndex(int(cmdset_list[i][2:]))
            if b'PR' in cmdset_list[i]: self.ch1_parity.setCurrentIndex(int(cmdset_list[i][2:]))
            if b'SB' in cmdset_list[i]: self.ch1_stopbit.setCurrentIndex(int(cmdset_list[i][2:]))
            if b'FL' in cmdset_list[i]: self.ch1_flow.setCurrentIndex(int(cmdset_list[i][2:]))
            if b'PT' in cmdset_list[i]: self.ch1_pack_time.setText(cmdset_list[i][2:].decode())
            if b'PS' in cmdset_list[i]: self.ch1_pack_size.setText(cmdset_list[i][2:].decode())
            if b'PD' in cmdset_list[i]: self.ch1_pack_char.setText(cmdset_list[i][2:].decode())
            # Inactive timer - channel 1
            if b'IT' in cmdset_list[i]: self.ch1_inact_timer.setText(cmdset_list[i][2:].decode())
            # TCP keep alive - channel 1
            if b'KA' in cmdset_list[i]: 
                if cmdset_list[i][2:].decode() == '0': self.ch1_keepalive_enable.setChecked(False)
                elif cmdset_list[i][2:].decode() == '1': self.ch1_keepalive_enable.setChecked(True)
            if b'KI' in cmdset_list[i]: self.ch1_keepalive_initial.setText(cmdset_list[i][2:].decode())
            if b'KE' in cmdset_list[i]: self.ch1_keepalive_retry.setText(cmdset_list[i][2:].decode())
            # reconnection - channel 1
            if b'RI' in cmdset_list[i]: self.ch1_reconnection.setText(cmdset_list[i][2:].decode())
            
            # Status pin
            # status_phy / status_dtr || status_tcpst / status_dsr
            if b'SC' in cmdset_list[i]: 
                if cmdset_list[i][2:].decode()[0:1] == '0':
                    self.status_phy.setChecked(True)
                elif cmdset_list[i][2:].decode()[0:1] == '1':
                    self.status_dtr.setChecked(True)
                if cmdset_list[i][2:].decode()[1:2] == '0':
                    self.status_tcpst.setChecked(True)
                elif cmdset_list[i][2:].decode()[1:2] == '1':
                    self.status_dsr.setChecked(True)


            # Channel 2 config (For two Port device)
            if self.curr_dev in TWO_PORT_DEV:
                # device info - channel 2
                if b'QS' in cmdset_list[i]: self.ch2_status.setText(cmdset_list[i][2:].decode())
                if b'EN' in cmdset_list[i]: 
                    if 'OPEN' in cmdset_list[i][2:].decode():
                        pass
                    else:
                        self.ch2_uart_name.setText(cmdset_list[i][2:].decode())
                # Network - channel 2
                if b'QO' in cmdset_list[i]: 
                    if cmdset_list[i][2:].decode() == '0': self.ch2_tcpclient.setChecked(True)
                    elif cmdset_list[i][2:].decode() == '1': self.ch2_tcpserver.setChecked(True)
                    elif cmdset_list[i][2:].decode() == '2': self.ch2_tcpmixed.setChecked(True)
                    elif cmdset_list[i][2:].decode() == '3': self.ch2_udp.setChecked(True)
                if b'QL' in cmdset_list[i]: self.ch2_localport.setText(cmdset_list[i][2:].decode())
                if b'QH' in cmdset_list[i]: self.ch2_remoteip.setText(cmdset_list[i][2:].decode())
                if b'QP' in cmdset_list[i]: self.ch2_remoteport.setText(cmdset_list[i][2:].decode())
                # serial - channel 2
                if b'EB' in cmdset_list[i]: 
                    if (len(cmdset_list[i][2:]) > 4):
                        pass 
                    else:
                        self.ch2_baud.setCurrentIndex(int(cmdset_list[i][2:]))
                if b'ED' in cmdset_list[i]: 
                    if (len(cmdset_list[i][2:]) > 2):   
                        pass 
                    else:
                        self.ch2_databit.setCurrentIndex(int(cmdset_list[i][2:]))
                if b'EP' in cmdset_list[i]: self.ch2_parity.setCurrentIndex(int(cmdset_list[i][2:]))
                if b'ES' in cmdset_list[i]: self.ch2_stopbit.setCurrentIndex(int(cmdset_list[i][2:]))
                if b'EF' in cmdset_list[i]: 
                    if (len(cmdset_list[i][2:]) > 2):   
                        pass
                    else:
                        self.ch2_flow.setCurrentIndex(int(cmdset_list[i][2:]))
                if b'NT' in cmdset_list[i]: self.ch2_pack_time.setText(cmdset_list[i][2:].decode())
                if b'NS' in cmdset_list[i]: self.ch2_pack_size.setText(cmdset_list[i][2:].decode())
                if b'ND' in cmdset_list[i]: 
                    if (len(cmdset_list[i][2:]) > 2):
                        pass
                    else:
                        self.ch2_pack_char.setText(cmdset_list[i][2:].decode())
                # Inactive timer - channel 2
                if b'RV' in cmdset_list[i]: self.ch2_inact_timer.setText(cmdset_list[i][2:].decode())
                # TCP keep alive - channel 2
                if b'RA' in cmdset_list[i]: 
                    if cmdset_list[i][2:].decode() == '0': self.ch2_keepalive_enable.setChecked(False)
                    elif cmdset_list[i][2:].decode() == '1': self.ch2_keepalive_enable.setChecked(True)

                if b'RS' in cmdset_list[i]: 
                    # exception
                    if b'-232' in cmdset_list[i][2:]:
                        pass
                    else:
                        self.ch2_keepalive_initial.setText(cmdset_list[i][2:].decode())

                if b'RE' in cmdset_list[i]: self.ch2_keepalive_retry.setText(cmdset_list[i][2:].decode())
                # reconnection - channel 2
                if b'RR' in cmdset_list[i]: self.ch2_reconnection.setText(cmdset_list[i][2:].decode())
        
    def getdevinfo(self, row_index):
        self.EnableObject()
        self.rcv_data = self.all_response
        devinfo = self.rcv_data[row_index].splitlines()
        # print('devinfo %d: %s ' % (row_index, devinfo))
        self.FillInfo(devinfo)
    
    def getSettinginfo(self, row_index):
        self.rcv_data[row_index] = self.set_reponse[0]
        # print('getSettinginfo set_response', self.set_reponse)

    # get each object's value for setting
    def GetObjectValue(self):
        self.SelectedDev()

        setcmd = {}
        # Network - general
        setcmd['LI'] = self.localip.text()
        setcmd['SM'] = self.subnet.text()
        setcmd['GW'] = self.gateway.text()
        if self.ip_static.isChecked() is True: setcmd['IM'] = '0'
        elif self.ip_dhcp.isChecked() is True: setcmd['IM'] = '1'
        setcmd['DS'] = self.dns_addr.text()
        # etc - general
        if self.enable_connect_pw.isChecked() is True: 
            setcmd['CP'] = '1'
            setcmd['NP'] = self.connect_pw.text()
        elif self.enable_connect_pw.isChecked() is False: setcmd['CP'] = '0'
        # command mode (AT mode)
        if self.at_enable.isChecked() is True: 
            setcmd['TE'] = '1'
            setcmd['SS'] = self.at_hex1.text() + self.at_hex2.text() + self.at_hex3.text()
        elif self.at_enable.isChecked() is False: setcmd['TE'] = '0'
            
        # search id code: max 8 bytes
        if len(self.searchcode.text()) == 0: setcmd['SP'] = ' '
        else: setcmd['SP'] = self.searchcode.text()

        # Debug msg 
        if self.serial_debug.currentIndex() == 2: setcmd['DG'] = '4'
        else: setcmd['DG'] = str(self.serial_debug.currentIndex())

        # Network - channel 1
        if self.ch1_tcpclient.isChecked() is True: setcmd['OP'] = '0'
        elif self.ch1_tcpserver.isChecked() is True: setcmd['OP'] = '1'
        elif self.ch1_tcpmixed.isChecked() is True: setcmd['OP'] = '2'
        elif self.ch1_udp.isChecked() is True: setcmd['OP'] = '3'
        setcmd['LP'] = self.ch1_localport.text()
        setcmd['RH'] = self.ch1_remoteip.text()
        setcmd['RP'] = self.ch1_remoteport.text()
        # serial - channel 1
        setcmd['BR'] = str(self.ch1_baud.currentIndex())
        setcmd['DB'] = str(self.ch1_databit.currentIndex())
        setcmd['PR'] = str(self.ch1_parity.currentIndex())
        setcmd['SB'] = str(self.ch1_stopbit.currentIndex())
        setcmd['FL'] = str(self.ch1_flow.currentIndex())
        setcmd['PT'] = self.ch1_pack_time.text()
        setcmd['PS'] = self.ch1_pack_size.text()
        setcmd['PD'] = self.ch1_pack_char.text()
        # Inactive timer - channel 1
        setcmd['IT'] = self.ch1_inact_timer.text()
        # TCP keep alive - channel 1
        if self.ch1_keepalive_enable.isChecked() is True: 
            setcmd['KA'] = '1'
            setcmd['KI'] = self.ch1_keepalive_initial.text()
            setcmd['KE'] = self.ch1_keepalive_retry.text()
        elif self.ch1_keepalive_enable.isChecked() is False: 
            setcmd['KA'] = '0'
        setcmd['KI'] = self.ch1_keepalive_initial.text()
        setcmd['KE'] = self.ch1_keepalive_retry.text()
        # reconnection - channel 1
        setcmd['RI'] = self.ch1_reconnection.text()

         # Status pin
        if self.status_phy.isChecked() is True: upper_val = '0'
        elif self.status_dtr.isChecked() is True: upper_val = '1'
        if self.status_tcpst.isChecked() is True: lower_val = '0'
        elif self.status_dsr.isChecked() is True: lower_val = '1'
        setcmd['SC'] = upper_val + lower_val

        if 'WIZ750' in self.curr_dev: 
            if version_compare('1.2.0', self.curr_ver) <= 0:
                setcmd['TR'] = self.tcp_timeout.text()
            else:
                pass
        elif 'WIZ752' in self.curr_dev:
            pass

        # Expansion GPIO
        if 'WIZ750' in self.curr_dev:
            setcmd['CA'] = str(self.gpioa_config.currentIndex())
            setcmd['CB'] = str(self.gpiob_config.currentIndex())
            setcmd['CC'] = str(self.gpioc_config.currentIndex())
            setcmd['CD'] = str(self.gpiod_config.currentIndex())
            if self.gpioa_config.currentIndex() == 1:
                setcmd['GA'] = str(self.gpioa_set.currentIndex())
            if self.gpiob_config.currentIndex() == 1: 
                setcmd['GB'] = str(self.gpiob_set.currentIndex())
            if self.gpioc_config.currentIndex() == 1: 
                setcmd['GC'] = str(self.gpioc_set.currentIndex())
            if self.gpiod_config.currentIndex() == 1: 
                setcmd['GD'] = str(self.gpiod_set.currentIndex())
        elif 'WIZ752' in self.curr_dev:
            pass
          
        # for channel 2
        if self.curr_dev in TWO_PORT_DEV:
            # device info - channel 2
            if self.ch2_tcpclient.isChecked() is True: setcmd['QO'] = '0'
            elif self.ch2_tcpserver.isChecked() is True: setcmd['QO'] = '1'
            elif self.ch2_tcpmixed.isChecked() is True: setcmd['QO'] = '2'
            elif self.ch2_udp.isChecked() is True: setcmd['QO'] = '3'
            setcmd['QL'] = self.ch2_localport.text()
            setcmd['QH'] = self.ch2_remoteip.text()
            setcmd['QP'] = self.ch2_remoteport.text()
            # serial - channel 2
            setcmd['EB'] = str(self.ch2_baud.currentIndex())
            setcmd['ED'] = str(self.ch2_databit.currentIndex())
            setcmd['EP'] = str(self.ch2_parity.currentIndex())
            setcmd['ES'] = str(self.ch2_stopbit.currentIndex())
            setcmd['EF'] = str(self.ch2_flow.currentIndex())
            setcmd['NT'] = self.ch2_pack_time.text()
            setcmd['NS'] = self.ch2_pack_size.text()
            setcmd['ND'] = self.ch2_pack_char.text()
            # Inactive timer - channel 2
            setcmd['RV'] = self.ch2_inact_timer.text()
            # TCP keep alive - channel 2
            if self.ch2_keepalive_enable.isChecked() is True: 
                setcmd['RA'] = '1'
                setcmd['RS'] = self.ch2_keepalive_initial.text()
                setcmd['RE'] = self.ch2_keepalive_retry.text()
            elif self.ch2_keepalive_enable.isChecked() is False:
                setcmd['RA'] = '0'
            # reconnection - channel 2
            setcmd['RR'] = self.ch2_reconnection.text()
        # print('setcmd:', setcmd)
        return setcmd
        
    def Setting(self):
        self.set_reponse = None

        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.DevNotSelected()
        else:
            self.statusbar.showMessage(' Setting device...')
            setcmd = self.GetObjectValue()
            # self.SelectedDev()

            if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev:
                print('One port dev setting')
                # Parameter validity check 
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.InvalidPopUp(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
                print('Two port dev setting')
                # Parameter validity check 
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz752cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.InvalidPopUp(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            # print('invalid flag: %d' % invalid_flag)
            if invalid_flag > 0:
                pass
            elif invalid_flag == 0:
                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, self.code, list(setcmd.keys()), list(setcmd.values()), self.curr_dev, self.curr_ver)
                # print('set cmdlist: ', cmd_list)

                # socket config
                self.SocketConfig() 

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
                else:
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
                self.wizmsghandler.set_result.connect(self.SetResult)
                self.wizmsghandler.start()

    def SetResult(self, resp_len):
        if resp_len > 100:
            self.statusbar.showMessage(' Set device complete!')

            # complete pop-up
            self.SetOKPopUp()
            
            if self.isConnected and self.unicast_ip.isChecked():
                print('close socket')
                self.conf_sock.shutdown()

            # Set -> get info
            self.set_reponse = self.wizmsghandler.rcv_list
            # print('setting response: ', self.list_device.selectedItems()[0].row(), len(self.set_reponse[0]), self.set_reponse)
            self.getSettinginfo(self.list_device.selectedItems()[0].row())
        elif resp_len < 0:
            print('Setting: no response from device.')
            self.statusbar.showMessage(' Setting: no response from device.')
            self.SetFailPopUp()
        elif resp_len < 50:
            print('Warning: setting is did not well.')
            self.statusbar.showMessage(' Warning: setting is did not well.')
            self.SetWarningPopUp()

    def SelectedDev(self):
        # 선택된 장치 정보 get
        for currentItem in self.list_device.selectedItems():
            if currentItem.column() == 0:
                self.curr_mac = currentItem.text()
                self.curr_ver = self.dev_data[self.curr_mac][1]
                # print('current mac addr:', self.curr_mac)
            elif currentItem.column() == 1:
                self.curr_dev = currentItem.text()
                # print('current dev name:', self.curr_dev)
            self.statusbar.showMessage(' Current device [%s : %s], %s' % (self.curr_mac, self.curr_dev, self.curr_ver))

    def UpdateResult(self, result):
        if result < 0:
            # self.statusbar.showMessage(' Firmware update failed.')
            self.FWUpFailPopUp()
        elif result > 0:
            self.statusbar.showMessage(' Firmware update complete!')
            print('FW Update OK')
            self.pgbar.setValue(8)
            self.FWUploadOKPopUp()
        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        self.pgbar.hide()

    def UpdateError(self, error):
        self.t_fwup.terminate()
        if error == -1:
            self.statusbar.showMessage(' Firmware update failed. No response from device.')
        elif error == -3:
            self.statusbar.showMessage(' Firmware update error.')
        # self.FWUpFailPopUp()

    # 'FW': firmware upload
    def FWUpdate(self, filename, filesize):
        self.pgbar.setFormat('Uploading..')
        # self.pgbar.setRange(0, filesize)
        self.pgbar.setValue(0)
        self.pgbar.setRange(0, 8)
        self.pgbar.show()

        self.SelectedDev()
        self.statusbar.showMessage(' Firmware update started. Please wait...')
        mac_addr = self.curr_mac
        print('FWUpdate %s, %s' % (mac_addr, filename))
        self.SocketConfig()

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        # FW update
        self.t_fwup = FWUploadThread(self.conf_sock, mac_addr, self.code, filename)
        self.t_fwup.uploading_size.connect(self.pgbar.setValue)
        self.t_fwup.upload_result.connect(self.UpdateResult)
        self.t_fwup.error_flag.connect(self.UpdateError)
        try:
            self.t_fwup.start()
        except Exception:
            print('fw uplooad error')
            self.UpdateResult(-1)

    def FWFileOpen(self):    
        fname, _ = QFileDialog.getOpenFileName(self, 'Firmware file open', '', 'Binary Files (*.bin);;All Files (*)')

        if fname:
            fileName = fname
            # # get path
            # path = fileName.split('/')
            # dirpath = ''
            # for i in range(len(path) - 1):
            #     dirpath += (path[i] + '/')
            # # print('dirpath:', dirpath)
            # print(fileName)

            # get file size
            self.fd = open(fileName, "rb")
            self.data = self.fd.read(-1)
            self.filesize = len(self.data)
            print('FWFileOpen: filesize: ', self.filesize)
            self.fd.close()
            # upload start
            self.FWUpdate(fileName, self.filesize)

    def NetworkCheck(self, dst_ip):
        self.statusbar.showMessage(' Checking the network...')
        # serverip = self.localip_addr
        serverip = dst_ip
        do_ping = subprocess.Popen("ping " + ("-n 1 " if sys.platform.lower()=="win32" else "-c 1 ") + serverip, 
                                    stdout=None, stderr=None, shell=True)
        ping_response = do_ping.wait()
        # print('ping_response', ping_response)
        return ping_response

    def UploadNetCheck(self):
        response = self.NetworkCheck(self.localip_addr)
        if response == 0:
            self.statusbar.showMessage(' Firmware update: Select App boot Firmware file. (.bin)')
            self.FWFileOpen()
        else:
            self.statusbar.showMessage(' Firmware update warning!')
            self.FWUpErrPopUp(self.localip_addr)

    def UpdateBtnClicked(self):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.DevNotSelected()
        else:
            if self.unicast_ip.isChecked() and self.isConnected:
                self.FWFileOpen()
            else:
                self.UploadNetCheck()
    
    def Reset(self):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.DevNotSelected()
        else:
            self.statusbar.showMessage(' Reset device?')
            self.SelectedDev()
            mac_addr = self.curr_mac
            
            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()

            cmd_list = self.wizmakecmd.reset(mac_addr, self.code)
            # print('Reset: %s' % cmd_list)

            self.SocketConfig()

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            self.wizmsghandler.start()
            
            self.statusbar.showMessage(' Reset device complete!')

            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()

    def Factory(self):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.DevNotSelected()
        else:
            self.statusbar.showMessage(' Factory reset?')
            self.SelectedDev()
            mac_addr = self.curr_mac

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()
            cmd_list = self.wizmakecmd.factory_reset(mac_addr, self.code)
            # print('Factory: %s' % cmd_list)

            self.SocketConfig()
            
            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            
            self.wizmsghandler.start()

            # Check the response
            self.statusbar.showMessage(' Device factory reset complete.')

            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()

    def ProgramInfo(self):
        msgbox = QMessageBox(self)
        msgbox.setTextFormat(Qt.RichText)
        text = "<div style=text-align:center><font size=5 color=darkblue>About WIZnet-S2E-Tool-GUI</font>" \
                + "<br><a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI'><font color=darkblue size=4>* Github repository</font></a>" \
                + "<br><br><font size=4 color=black>Version " + VERSION \
                + "<br><br><font size=5 color=black>WIZnet website</font><br>" \
                + "<a href='http://www.wiznet.io/'><font color=black>WIZnet Official homepage</font></a>"  \
                + "<br><a href='https://forum.wiznet.io/'><font color=black>WIZnet Forum</font></a>" \
                + "<br><a href='https://wizwiki.net/'><font color=black>WIZnet Wiki</font></a>" \
                + "<br><br>2018 WIZnet Co.</font><br></div>" 
        msgbox.about(self, "About WIZnet-S2E-Tool-GUI", text)

    def InvalidPopUp(self, params):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Invalid parameter")
        msgbox.setText("Invalid parameter.\nPlease check the values.")
        msgbox.setInformativeText(params)
        msgbox.exec_()

    def DevNotSelected(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning")
        msgbox.setText("Device is not selected.")
        msgbox.exec_()

    def SetWarningPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Setting")
        msgbox.setText("Setting did not well.\nPlease check the device or check the firmware version.")
        msgbox.exec_()

    def SetFailPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Setting Failed")
        msgbox.setText("Setting failed.\nNo response from device.")
        msgbox.exec_()

    def SetOKPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Setting success", "Devcie configuration complete!", QMessageBox.Yes)
    
    def FWUpErrPopUp(self, dst_ip):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Firmware upload")
        msgbox.setText("Destination IP is unreachable: %s\nPlease check if the device is in the same subnet with the PC." % dst_ip)
        msgbox.exec_()

    def FWUpFailPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setWindowTitle("Error: Firmware upload")
        msgbox.setText("Firmware update failed.\nPlease check the device's status.")
        msgbox.exec_()

    def FWUploadOKPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Firmware upload success", "Firmware update complete!", QMessageBox.Yes)
    
    def ConnectionFailPopUp(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setWindowTitle("Error: Connection failed")
        msgbox.setText("Network connection failed.\nConnection is refused.")
        msgbox.exec_()

    def NetworkNotConnected(self, dst_ip):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Network")
        msgbox.setText("Destination IP is unreachable: %s\nPlease check the network status." % dst_ip)
        msgbox.exec_()

    def ResetPopUp(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Reset", "Do you really want to reset the device?", QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.Reset()

    def FactoryPopUp(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Factory Reset", "Do you really want to factory reset the selected device?\nAll settings will get the factory default values.", QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.Factory()

    def ExitPopUp(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Exit", "Do you really close this program?", QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.close()

    def SaveFileDialog(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Configuration Save","WIZCONF.cfg","Config File (*.cfg);;Text Files (*.txt);;All Files (*)")

        if fname:
            fileName = fname
            print(fileName)
            self.SaveConfig(fileName)

    def SaveConfig(self, filename):
        setcmd = self.GetObjectValue()
        # print('SaveConfig: setcmd', setcmd)
        set_list = list(setcmd.keys())

        f = open(filename, 'w+')
        for cmd in set_list:
            cmdset = '%s%s\n' % (cmd, setcmd.get(cmd))
            f.write(cmdset)
        f.close()

        self.statusbar.showMessage(' Configuration is saved to \'%s\'.' % filename)

    def LoadFileDialog(self):    
        fname, _ = QFileDialog.getOpenFileName(self, "Configuration Load", "WIZCONF.cfg","Config File (*.cfg);;Text Files (*.txt);;All Files (*)")
        
        if fname:
            fileName = fname
            print(fileName)
            self.LoadConfig(fileName)

    def LoadConfig(self, data_file):
        cmd_list = []
        self.SelectedDev()
        f = open(data_file, 'r')
        for line in f:
            line = re.sub('[\n]', '', line)
            if len(line) > 2:
                cmd_list.append(line.encode())
        # print('LoadConfig: cmdlist', cmd_list)
        self.FillInfo(cmd_list)

    def SetBtnIcon(self):
        # Set Button icon 
        self.icon_save = QIcon()
        self.icon_save.addPixmap(QPixmap(resource_path('gui/save_48.ico')), QIcon.Normal, QIcon.Off)
        self.savebtn.setIcon(self.icon_save)
        self.savebtn.setIconSize(QSize(40, 40))

        self.icon_load = QIcon()
        self.icon_load.addPixmap(QPixmap(resource_path('gui/load_48.ico')), QIcon.Normal, QIcon.Off)
        self.loadbtn.setIcon(self.icon_load)
        self.loadbtn.setIconSize(QSize(40, 40))

        self.icon_search = QIcon()
        self.icon_search.addPixmap(QPixmap(resource_path('gui/search_48.ico')), QIcon.Normal, QIcon.Off)
        self.btnsearch.setIcon(self.icon_search)
        self.btnsearch.setIconSize(QSize(40, 40))
        
        self.icon_setting = QIcon()
        self.icon_setting.addPixmap(QPixmap(resource_path('gui/setting_48.ico')), QIcon.Normal, QIcon.Off)
        self.btnsetting.setIcon(self.icon_setting)
        self.btnsetting.setIconSize(QSize(40, 40))

        self.icon_upload = QIcon()
        self.icon_upload.addPixmap(QPixmap(resource_path('gui/upload_48.ico')), QIcon.Normal, QIcon.Off)
        self.fwupbtn.setIcon(self.icon_upload)
        self.fwupbtn.setIconSize(QSize(40, 40))

        self.icon_reset = QIcon()
        self.icon_reset.addPixmap(QPixmap(resource_path('gui/reset_48.ico')), QIcon.Normal, QIcon.Off)
        self.resetbtn.setIcon(self.icon_reset)
        self.resetbtn.setIconSize(QSize(40, 40))

        self.icon_factory = QIcon()
        self.icon_factory.addPixmap(QPixmap(resource_path('gui/factory_48.ico')), QIcon.Normal, QIcon.Off)
        self.factorybtn.setIcon(self.icon_factory)
        self.factorybtn.setIconSize(QSize(40, 40))

        self.icon_exit = QIcon()
        self.icon_exit.addPixmap(QPixmap(resource_path('gui/exit_48.ico')), QIcon.Normal, QIcon.Off)
        self.exitbtn.setIcon(self.icon_exit)
        self.exitbtn.setIconSize(QSize(40, 40))
            
class ThreadProgress(QThread):
    change_value = pyqtSignal(int)

    def __init__(self, parent=None):
        # QThread.__init__(self)
        super().__init__()
        self.cnt = 1
      
    def run(self):
        self.cnt = 1
        while self.cnt <= 100:
            self.cnt += 1
            self.change_value.emit(self.cnt)
            self.msleep(15)  

    def __del__(self):
        print('thread: del')
        self.wait()

if __name__=='__main__':
    app = QApplication(sys.argv)
    wizwindow = WIZWindow()
    wizwindow.show()
    app.exec_()
