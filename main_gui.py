# -*- coding: utf-8 -*-

import sys
import time
import re
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize, QThread, Qt, QTimer, pyqtSignal, pyqtSlot, QRect
# from PyQt5.QtCore import *
from PyQt5 import QtCore
from PyQt5.QtGui import QIcon, QPixmap
# from PyQt5 import *
from PyQt5 import uic

from WIZMSGHandler import WIZMSGHandler
from FWUploadThread import FWUploadThread
from WIZUDPSock import WIZUDPSock
from WIZ750CMDSET import WIZ750CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from WIZMakeCMD import WIZMakeCMD
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

def resource_path(relative_path):
# Get absolute path to resource, works for dev and for PyInstaller
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Load ui files
main_window = uic.loadUiType(resource_path('gui/wizconfig_gui.ui'))[0]
dialog_onebtn = uic.loadUiType(resource_path('gui/dialog_onebtn.ui'))[0]

dialog_warning_factory = uic.loadUiType(resource_path('gui/dialog_warning_factory.ui'))[0]
dialog_warning_reset = uic.loadUiType(resource_path('gui/dialog_warning_reset.ui'))[0]
exit_dialog = uic.loadUiType(resource_path('gui/dialog_exit.ui'))[0]

class OneBtnDialog(QDialog, dialog_onebtn):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class ExitDialog(QDialog, exit_dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class ResetDialog(QDialog, dialog_warning_reset):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class FactoryDialog(QDialog, dialog_warning_factory):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class WIZWindow(QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # Main icon
        self.setWindowIcon(QIcon(resource_path('gui/main_icon.ico')))

        # Set Button icon 
        self.icon_save = QIcon()
        self.icon_save.addPixmap(QPixmap(resource_path('gui/save_48.ico')), QIcon.Normal, QIcon.Off)
        self.savebtn.setIcon(self.icon_save)
        self.savebtn.setIconSize(QSize(20, 20))

        self.icon_load = QIcon()
        self.icon_load.addPixmap(QPixmap(resource_path('gui/load_48.ico')), QIcon.Normal, QIcon.Off)
        self.loadbtn.setIcon(self.icon_load)
        self.loadbtn.setIconSize(QSize(20, 20))

        self.icon_ping = QIcon()
        self.icon_ping.addPixmap(QPixmap(resource_path('gui/ping_48.ico')), QIcon.Normal, QIcon.Off)
        self.devmanagerbtn.setIcon(self.icon_ping)
        self.devmanagerbtn.setIconSize(QSize(20, 20))

        self.icon_firewall = QIcon()
        self.icon_firewall.addPixmap(QPixmap(resource_path('gui/firewall_48.ico')), QIcon.Normal, QIcon.Off)
        self.firewallbtn.setIcon(self.icon_firewall)
        self.firewallbtn.setIconSize(QSize(20, 20))

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

        # Get Search method 
        if self.broadcast.isChecked():
            # Broadcast
            self.conf_sock = WIZUDPSock(5000, 50001)
            self.conf_sock.open()
        elif self.unicast_mac.isChecked():
            cmd_list = self.wizmakecmd.search(self.search_macaddr)
        elif self.unicast_ip.isChecked():
            # TCP unicast
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            # TCP Client socket open - connect
            self.conf_sock = TCPClient(2, ip_addr, port)
            self.conf_sock.open()
            self.conf_sock.connect()

        self.wiz750cmdObj = WIZ750CMDSET(1)
        self.wiz752cmdObj = WIZ752CMDSET(1)
        self.wizmakecmd = WIZMakeCMD()

        self.mac_list = []
        self.threads = []
        self.curr_mac = None
        self.curr_dev = None

        self.isConnected = False

        ##################### Button Event #####################
        # device select event
        self.list_device.itemClicked.connect(self.devclick)

        # Button event handler
        self.btnsearch.clicked.connect(self.Search)
        self.btnsetting.clicked.connect(self.Setting)

        self.resetbtn.clicked.connect(self.OpenResetDialog)
        self.factorybtn.clicked.connect(self.OpenFactoryDialog)

        # configuration save/load button
        self.savebtn.clicked.connect(self.SaveFile)
        self.loadbtn.clicked.connect(self.LoadFile)

        # self.fwupbtn.clicked.connect(self.FWFileOpen)
        self.fwupbtn.clicked.connect(self.NetworkCheck)

        if sys.platform.lower() == 'win32':
            self.firewallbtn.setEnabled(True)
            self.firewallbtn.clicked.connect(self.OpenFirewall)
            self.devmanagerbtn.clicked.connect(self.OpenDevManager)
        else:
            self.firewallbtn.setEnabled(False)

        self.exitbtn.clicked.connect(self.OpenExitDialog)

        # Menu event
        # self.actionSave.triggered.connect(self.SaveFile)
        # self.actionLoad.triggered.connect(self.LoadFile)
        # self.about_wiz.triggered.connect(self.OpenInfoDialog)

        # State Changed Event 
        self.show_idcode.stateChanged.connect(self.ShowIDcode)
        self.show_connectpw.stateChanged.connect(self.ShowPW)
        self.enable_connect_pw.stateChanged.connect(self.EnablePW)
        self.at_enable.stateChanged.connect(self.EnableATmode)

        self.ip_dhcp.clicked.connect(self.CheckIPalloc)
        self.ip_static.clicked.connect(self.CheckIPalloc)

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

    def CheckIPalloc(self):
        if self.ip_dhcp.isChecked() is True:
            self.network_config.setEnabled(False)
        elif self.ip_dhcp.isChecked() is False:
            self.network_config.setEnabled(True)
    
    def EnableATmode(self):
        if self.at_enable.isChecked() is True:
            self.at_hex1.setEnabled(True)
            self.at_hex2.setEnabled(True)
            self.at_hex3.setEnabled(True)
        elif self.at_enable.isChecked() is False:
            self.at_hex1.setEnabled(False)
            self.at_hex2.setEnabled(False)
            self.at_hex3.setEnabled(False)

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

    def Processing(self):
        # 동작 수행 시 버튼 비활성화 (연속 클릭 방지)
        self.btnsearch.setEnabled(False)
        QTimer.singleShot(1000, lambda: self.btnsearch.setEnabled(True))

    def tcpConnection(self, serverip, port):
        retrynum = 0
        cli_sock = TCPClient(2, serverip, port)
        print('sock state: %r' % (cli_sock.state))

        # 기존 연결 fin 
        if cli_sock.state is not SOCK_CLOSE_STATE:
            cli_sock.shutdown()

        while True:
            if retrynum > 10:
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
        if retrynum > 10:
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

            self.conf_sock = self.tcpConnection(ip_addr, port)

            if self.conf_sock is None:
                self.isConnected = False
                print('TCP connection failed!: %s' % self.conf_sock)
                self.statusbar.showMessage(' TCP connection failed: %s' % ip_addr)
                self.OpenConnectionFailDialog()
            else:
                self.isConnected = True

    def Search(self):
        cmd_list = []
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
        
        ##############################################################
        # Search devices
        if self.isConnected or self.broadcast.isChecked():
            self.statusbar.showMessage(' Searching devices...')
            cmd_list = self.wizmakecmd.search("FF:FF:FF:FF:FF:FF")
            # print(cmd_list)
            wizmsghangler = WIZMSGHandler(self.conf_sock)
            wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
            if self.unicast_ip.isChecked():
                wizmsghangler.sendcommandsTCP()
            else:
                wizmsghangler.sendcommands()
            wizmsghangler.parseresponse()

            dev_name = wizmsghangler.mn_list
            self.mac_list = wizmsghangler.mac_list

            self.all_response = wizmsghangler.rcv_list

            self.devnumber = len(self.mac_list)

            # row length = the number of searched devices
            self.list_device.setRowCount(len(self.mac_list))
            
            # 검색된 장치 mac / name 출력
            for i in range(0, len(self.mac_list)):
                # device = "%s | %s" % (self.mac_list[i].decode(), dev_name[i].decode())
                self.list_device.setItem(i, 0, QTableWidgetItem(self.mac_list[i].decode()))
                self.list_device.setItem(i, 1, QTableWidgetItem(dev_name[i].decode()))

            # 데이터 사이즈에 따라 resize
            self.list_device.resizeColumnsToContents()
            self.list_device.resizeRowsToContents()
            
            # 행/열 크기 조정 disable
            self.list_device.horizontalHeader().setSectionResizeMode(2)
            self.list_device.verticalHeader().setSectionResizeMode(2)

            ## error => # self.statusbar.addPermanentWidget(self.icon_search)
            self.statusbar.showMessage(' Find %d devices' % len(self.mac_list))

            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()

            # TEST: progress bar
            # self.statusbar.addPermanentWidget(self.progressbar)
            # # Remove progress bar
            # self.progressbar.hide()

    def devclick(self):
        # get information for selected device
        for currentQTableWidgetItem in self.list_device.selectedItems():
            # print('Click info:', currentQTableWidgetItem.row(), currentQTableWidgetItem.column(), currentQTableWidgetItem.text())
            self.getdevinfo(currentQTableWidgetItem.row())

    def EnableObject(self):
        self.SelectDev()

        # 버튼 활성화
        self.resetbtn.setEnabled(True)
        self.factorybtn.setEnabled(True)
        self.fwupbtn.setEnabled(True)
        self.btnsetting.setEnabled(True)
        self.savebtn.setEnabled(True)
        self.loadbtn.setEnabled(True)
        self.bootupbtn.setEnabled(True)

        # 창 활성화
        self.general.setEnabled(True)
        self.channel_tab.setEnabled(True)

        self.connect_pw.setEnabled(False)

        ### 포트 수에 따라 설정 탭 활성화
        if self.curr_dev in ONE_PORT_DEV:
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, False)
            self.channel_tab.setTabEnabled(2, False)
            self.channel_tab.setTabEnabled(3, False)
        elif self.curr_dev in TWO_PORT_DEV:
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, True)
            self.channel_tab.setTabEnabled(2, False)
            self.channel_tab.setTabEnabled(3, False)
        
        # MENU 활성화
        self.save_config.setEnabled(True)
        self.load_config.setEnabled(True)

    def FillInfo(self, cmdset_list):
        self.SelectDev()
        # print('FillInfo: cmdset_list', cmdset_list)

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
                self.localip.setText(cmdset_list[i][2:].decode())
                self.localip_addr = cmdset_list[i][2:].decode()
            if b'SM' in cmdset_list[i]: self.subnet.setText(cmdset_list[i][2:].decode())
            if b'GW' in cmdset_list[i]: self.gateway.setText(cmdset_list[i][2:].decode())
            if b'DS' in cmdset_list[i]: self.dns_addr.setText(cmdset_list[i][2:].decode())
            # etc - general
            if b'CP' in cmdset_list[i]: self.enable_connect_pw.setChecked(int(cmdset_list[i][2:].decode()))
            if b'NP' in cmdset_list[i]: self.connect_pw.setText(cmdset_list[i][2:].decode())
            # command mode (AT mode)
            if b'TE' in cmdset_list[i]: self.at_enable.setChecked(int(cmdset_list[i][2:].decode()))
            if b'SS' in cmdset_list[i]:
                self.at_hex1.setText(cmdset_list[i][2:4].decode())
                self.at_hex2.setText(cmdset_list[i][4:6].decode())
                self.at_hex3.setText(cmdset_list[i][6:8].decode())
            # if b'SP' in cmdset_list[i]:   # search code
            if b'DG' in cmdset_list[i]: self.serial_debug.setChecked(int(cmdset_list[i][2:].decode()))
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
            
            # Channel 2 config (For two Port device)
            if self.curr_dev in TWO_PORT_DEV:
                # device info - channel 2
                if b'QS' in cmdset_list[i]: self.ch2_status.setText(cmdset_list[i][2:].decode())
                if b'EN' in cmdset_list[i]: self.ch2_uart_name.setText(cmdset_list[i][2:].decode())
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
                if b'ND' in cmdset_list[i]: self.ch2_pack_char.setText(cmdset_list[i][2:].decode())
                # Inactive timer - channel 2
                if b'RV' in cmdset_list[i]: self.ch2_inact_timer.setText(cmdset_list[i][2:].decode())
                # TCP keep alive - channel 2
                if b'RA' in cmdset_list[i]: 
                    if cmdset_list[i][2:].decode() == '0': self.ch2_keepalive_enable.setChecked(False)
                    elif cmdset_list[i][2:].decode() == '1': self.ch2_keepalive_enable.setChecked(True)
                if b'RS' in cmdset_list[i]: self.ch2_keepalive_initial.setText(cmdset_list[i][2:].decode())
                if b'RE' in cmdset_list[i]: self.ch2_keepalive_retry.setText(cmdset_list[i][2:].decode())
                # reconnection - channel 2
                if b'RR' in cmdset_list[i]: self.ch2_reconnection.setText(cmdset_list[i][2:].decode())
        
    def getdevinfo(self, row_index):
        # print('row: ', row_index)
        self.EnableObject()

        # 선택 장치 정보 출력 
        rcv_data = self.all_response
        # print('rcv_data[%d] ===> %s' % (row_index, rcv_data[row_index]))
        devinfo = rcv_data[row_index].splitlines()
        # print('devinfo %d: %s ' % (row_index, devinfo))
        
        self.FillInfo(devinfo)

    def Dialog_invalid(self):
        dialog = InvalidDialog()
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()
    
    def GetObjectValue(self):
        self.SelectDev()

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
            
        # 'SP' 추가요망
        if self.serial_debug.isChecked() is True: setcmd['DG'] = '1'
        elif self.serial_debug.isChecked() is False: setcmd['DG'] = '0'
        
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
        if self.ch1_keepalive_enable.isChecked() is True: setcmd['KA'] = '1'
        elif self.ch1_keepalive_enable.isChecked() is False: setcmd['KA'] = '0'
        setcmd['KI'] = self.ch1_keepalive_initial.text()
        setcmd['KE'] = self.ch1_keepalive_retry.text()
        # reconnection - channel 1
        setcmd['RI'] = self.ch1_reconnection.text()

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
            if self.ch2_keepalive_enable.isChecked() is True: setcmd['RA'] = '1'
            elif self.ch2_keepalive_enable.isChecked() is False: setcmd['RA'] = '0'
            setcmd['RS'] = self.ch2_keepalive_initial.text()
            setcmd['RE'] = self.ch2_keepalive_retry.text()
            # reconnection - channel 2
            setcmd['RR'] = self.ch2_reconnection.text()

        # print('setcmd:', setcmd)
        return setcmd
        
    def Setting(self):
        self.statusbar.showMessage(' Setting device...')
        # Get each object's value
        setcmd = self.GetObjectValue()
        # self.SelectDev()

        if self.curr_dev in ONE_PORT_DEV:
            print('One port dev setting')
            # Parameter validity check 
            invalid_flag = 0
            setcmd_cmd = list(setcmd.keys())
            for i in range(len(setcmd)):
                if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                    print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                    # Invalid dialog
                    self.OpenDialogInvalid(setcmd.get(setcmd_cmd[i]))
                    invalid_flag += 1
        elif self.curr_dev in TWO_PORT_DEV:
            print('Two port dev setting')
            # Parameter validity check 
            invalid_flag = 0
            setcmd_cmd = list(setcmd.keys())
            for i in range(len(setcmd)):
                if self.wiz752cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                    print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                    # Invalid dialog
                    self.OpenDialogInvalid(setcmd.get(setcmd_cmd[i]))
                    invalid_flag += 1
        # print('invalid flag: %d' % invalid_flag)
        if invalid_flag == 0:
            if self.curr_dev in ONE_PORT_DEV:
                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, list(setcmd.keys()), list(setcmd.values()), 1)
            elif self.curr_dev in TWO_PORT_DEV:
                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, list(setcmd.keys()), list(setcmd.values()), 2)
            # print('set cmdlist: ', cmd_list)

            # socket config
            self.SocketConfig() 

            wizmsghangler = WIZMSGHandler(self.conf_sock)
            wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
            if self.unicast_ip.isChecked():
                wizmsghangler.sendcommandsTCP()
            else:
                wizmsghangler.sendcommands()
            wizmsghangler.parseresponse()

            # self.devclick()
            
            self.statusbar.showMessage(' Set device complete!')
            self.OpenDialogSetOK()

            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()

            self.Search()

    def SelectDev(self):
        # 선택된 장치의 mac addr / name 추출 
        for currentQTableWidgetItem in self.list_device.selectedItems():
            if currentQTableWidgetItem.column() == 0:
                self.curr_mac = currentQTableWidgetItem.text()
                # print('current mac addr:', self.curr_mac)
            elif currentQTableWidgetItem.column() == 1:
                self.curr_dev = currentQTableWidgetItem.text()
                # print('current dev name:', self.curr_dev)
            
            self.statusbar.showMessage(' Current device [%s : %s]' % (self.curr_mac, self.curr_dev))

    # 'FW': firmware upload
    def FWUpdate(self, filename):
        self.SelectDev()
        self.statusbar.showMessage(' Firmware update started. Please wait...')
        mac_addr = self.curr_mac
        print('FWUpdate %s, %s' % (mac_addr, filename))

        self.SocketConfig()

        # FW update
        t_fwup = FWUploadThread(self.conf_sock)
        # t_fwup = FWUploadThread()
        t_fwup.setparam(mac_addr, filename)
        # For 'AB' command Test (boot mode fw update)
        t_fwup.jumpToApp()
        time.sleep(2)
        t_fwup.sendCmd('FW')
        t_fwup.start()
        self.threads.append(t_fwup)

        for thread in self.threads:
            thread.join()   # 쓰레드 종료 대기

        if t_fwup.checkResult() < 0:
            self.OpenFWUerrDialog()
        elif t_fwup.checkResult() > 0:
            self.statusbar.showMessage(' Firmware update complete!')
            self.OpenFWOKDialog()

        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        
        self.Search()

    def FWFileOpen(self):    
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"Firmware file open", "","Binary Files (*.bin);;All Files (*)", options=options)
        if fileName:
            print(fileName)
            self.FWUpdate(fileName)

    def NetworkCheck(self):
        serverip = self.localip_addr
        ping_reponse = os.system("ping " + ("-n 1 " if sys.platform.lower()=="win32" else "-c 1 ") + serverip)
        
        if ping_reponse != 0:
            self.statusbar.showMessage(' Firmware update error occured.')
            self.OpenFWUerrDialog()
            # sys.exit(0)
        else:
            self.statusbar.showMessage(' Firmware update: Select App boot Firmware file. (.bin)')
            self.FWFileOpen()
    
    def Reset(self):
        self.statusbar.showMessage(' Reset device?')
        self.SelectDev()
        mac_addr = self.curr_mac
        cmd_list = self.wizmakecmd.reset(mac_addr)
        print('Reset: %s' % cmd_list)

        self.SocketConfig()

        wizmsghangler = WIZMSGHandler(self.conf_sock)
        wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
        if self.unicast_ip.isChecked():
            wizmsghangler.sendcommandsTCP()
        else:
            wizmsghangler.sendcommands()
        # wizmsghangler.parseresponse()
        self.statusbar.showMessage(' Reset device complete!')

        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()

    def Factory(self):
        self.statusbar.showMessage(' Factory reset?')
        self.SelectDev()
        mac_addr = self.curr_mac
        cmd_list = self.wizmakecmd.factory_reset(mac_addr)
        print('Factory: %s' % cmd_list)

        self.SocketConfig()
        
        wizmsghangler = WIZMSGHandler(self.conf_sock)
        wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
        if self.unicast_ip.isChecked():
            wizmsghangler.sendcommandsTCP()
        else:
            wizmsghangler.sendcommands()
        # wizmsghangler.parseresponse()
        self.statusbar.showMessage(' Device factory reset complete.')

        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        
        self.Search()

    ###########################################################
    ## One button dialog
    def OpenDialogInvalid(self, param):
        dialog = OneBtnDialog()
        dialog.setWindowTitle('Error: Invalid parameter')
        dialog.label.setText('Invalid values. Please input valid value.\n\t%s' % (param))
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()

    def OpenDialogSetOK(self):
        dialog = OneBtnDialog()
        dialog.setWindowTitle('Set devcie OK')
        dialog.label.setText('Devcie configuration complete!')
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()
    
    def OpenFWUerrDialog(self):
        dialog = OneBtnDialog()
        # dialog.resize(450, 110)
        dialog.setMinimumSize(QSize(440, 110))
        # dialog.label.resize(400, 40)
        dialog.label.setMinimumSize(QSize(400, 40))
        dialog.okbtn.setGeometry(QRect(193, 67, 75, 23))
        dialog.setWindowTitle('Error: firmware upload')
        dialog.label.setText('Destination IP is unreachable!\nPlease check if the device is in the same subnet with the PC.')
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()

    def OpenFWOKDialog(self):
        dialog = OneBtnDialog()
        dialog.setWindowTitle('Firmware upload success')
        dialog.label.setText('Firmware update complete!')
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()
    
    def OpenConnectionFailDialog(self):
        dialog = OneBtnDialog()
        dialog.setWindowTitle('Error: Connection failed')
        dialog.label.setText('Network connection failed.\nConnection is refused.')
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.exec_()

    ###########################################################
    ## Two button dialog
    def OpenResetDialog(self):
        dialog = ResetDialog()
        # Reset btn => reset
        dialog.okbtn.clicked.connect(self.Reset)
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.cancelbtn.clicked.connect(dialog.close)
        dialog.exec_()

    def OpenFactoryDialog(self):
        dialog = FactoryDialog()
        # Factory btn => factory reset
        dialog.okbtn.clicked.connect(self.Factory)

        dialog.okbtn.clicked.connect(dialog.close)
        dialog.cancelbtn.clicked.connect(dialog.close)
        dialog.exec_()

    def OpenExitDialog(self):
        dialog = ExitDialog()
        # Reset btn => reset
        dialog.okbtn.clicked.connect(lambda: self.close())

        dialog.okbtn.clicked.connect(dialog.close)
        dialog.cancelbtn.clicked.connect(dialog.close)
        dialog.exec_()

    ########################## MENU
    def SaveFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        # fileName, _ = QFileDialog.getSaveFileName(self,"Configuration Save","","Config File (.cfg);;All Files (*);;Text Files (*.txt)", options=options)
        fileName, _ = QFileDialog.getSaveFileName(self,"Configuration Save","","All Files (*);;Text Files (*.txt)", options=options)
        if fileName:
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

    def LoadFile(self):    
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"Configuration Load", "","All Files (*);;Text Files (*.txt);;ini Files (*.ini)", options=options)
        if fileName:
            print(fileName)
            self.LoadConfig(fileName)

    def LoadConfig(self, data_file):
        cmd_list = []
        self.SelectDev()
        f = open(data_file, 'r')
        for line in f:
            line = re.sub('[\n]', '', line)
            if len(line) > 2:
                cmd_list.append(line.encode())
        # print('LoadConfig: cmdlist', cmd_list)
        self.FillInfo(cmd_list)

    def OpenFirewall(self):
        cmd = 'rundll32.exe shell32.dll, Control_RunDLL FireWall.cpl'
        os.system(cmd)
    
    def OpenDevManager(self):
        cmd = 'rundll32.exe devmgr.dll DeviceManager_Execute'
        os.system(cmd)
            
if __name__=='__main__':
    app = QApplication(sys.argv)
    wizwindow = WIZWindow()
    wizwindow.show()
    app.exec_()
