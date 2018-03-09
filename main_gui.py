# -*- coding: utf-8 -*-

import sys
import time
import re
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QSize, QThread, Qt, QTimer, pyqtSignal, pyqtSlot
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

OP_SEARCHALL = 1
OP_GETCOMMAND = 2
OP_SETCOMMAND = 3
OP_SETFILE = 4
OP_GETFILE = 5
OP_FWUP = 6

ONE_PORT_DEV = ['WIZ750SR', 'WIZ750SR-100', 'WIZ750SR-105', 'WIZ750SR-110', 'WIZ107SR', 'WIZ108SR']
TWO_PORT_DEV = ['WIZ752SR-12x', 'WIZ752SR-120','WIZ752SR-125']

def resource_path(relative_path):
# """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

p_mainwindow = resource_path('gui/wizconfig_gui.ui')
p_invalid = resource_path('gui/dialog_invalid.ui')
p_factory = resource_path('gui/dialog_warning_factory.ui')
p_reset = resource_path('gui/dialog_warning_reset.ui')
p_info = resource_path('gui/version_info.ui')
p_exit = resource_path('gui/dialog_exit.ui')
p_fwuperr = resource_path('gui/dialog_fwup_error.ui')
p_fwupok = resource_path('gui/dialog_fwup_complete.ui')

main_window = uic.loadUiType(p_mainwindow)[0]
dialog_invalid = uic.loadUiType(p_invalid)[0]
dialog_warning_factory = uic.loadUiType(p_factory)[0]
dialog_warning_reset = uic.loadUiType(p_reset)[0]
info_dialog = uic.loadUiType(p_info)[0]
exit_dialog = uic.loadUiType(p_exit)[0]
fwuperr_dialog = uic.loadUiType(p_fwuperr)[0]
fwupok_dialog = uic.loadUiType(p_fwupok)[0]

# class TaskThread(QThread):
#     def __init__(self):
#         QThread.__init__(self)

#     def on_progress(self, progress):
#         self.statusbar.addPermanentWidget(self.progressbar)
#         self.progressbar.setValue(progress)

#         # Remove progress bar
#         # self.progressbar.hide()
class FWupOKDialog(QDialog, fwupok_dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class FWErrorDialog(QDialog, fwuperr_dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class ExitDialog(QDialog, exit_dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

class InfoDialog(QDialog, info_dialog):
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

class InvalidDialog(QDialog, dialog_invalid):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

# QThread
class ProgressThread(QThread):

    threadEvent = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__()
        self.n = 0
        self.main = parent
        self.isRun = False

    def run(self):
        while self.isRun:
            print('Thread: ' + str(self.n))
            # threadEvent 이벤트 발생
            self.threadEvent.emit(self.n)
            self.n += 1
            self.sleep(1)
###########################################           

class WIZWindow(QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowIcon(QIcon(resource_path('gui/main_icon.ico')))

        self.conf_sock = WIZUDPSock(5000, 50001)
        self.conf_sock.open()
        self.wizmsghangler = WIZMSGHandler(self.conf_sock)

        self.wiz750cmdObj = WIZ750CMDSET(1)
        self.wiz752cmdObj = WIZ752CMDSET(1)
        self.wizmakecmd = WIZMakeCMD()

        self.mac_list = []
        self.threads = []
        self.curr_mac = None
        self.curr_dev = None

        # device select event
        self.list_device.itemClicked.connect(self.devclick)

        # Button event handler
        self.btnsearch.clicked.connect(self.Search)
        self.btnsetting.clicked.connect(self.Setting)

        self.resetbtn.clicked.connect(self.OpenResetDialog)
        self.factorybtn.clicked.connect(self.OpenFactoryDialog)

        # self.fwupbtn.clicked.connect(self.FWFileOpen)
        self.fwupbtn.clicked.connect(self.NetworkCheck)

        if sys.platform.lower() == 'win32':
            self.firewallbtn.setEnabled(True)
            self.firewallbtn.clicked.connect(self.OpenFirewall)
            self.devmanagerbtn.clicked.connect(self.OpenDevManager)
        else:
            self.firewallbtn.setEnabled(False)

        self.exitbtn.clicked.connect(self.OpenExitDialog)

        # state changed event
        self.show_idcode.stateChanged.connect(self.ShowIDcode)
        self.show_connectpw.stateChanged.connect(self.ShowPW)
        self.enable_connect_pw.stateChanged.connect(self.EnablePW)
        self.at_enable.stateChanged.connect(self.EnableATmode)
        self.ip_dhcp.clicked.connect(self.CheckOPmode)
        self.ip_static.clicked.connect(self.CheckOPmode)

        # Menu event
        # self.actionSave.triggered.connect(self.SaveFile)
        # self.actionLoad.triggered.connect(self.LoadFile)
        # self.about_wiz.triggered.connect(self.OpenInfoDialog)

        # configuration save/load button
        self.savebtn.clicked.connect(self.SaveFile)
        self.loadbtn.clicked.connect(self.LoadFile)

        # OP mode event
        self.ch1_tcpclient.clicked.connect(self.OPmodeEvent)
        self.ch1_tcpserver.clicked.connect(self.OPmodeEvent)
        self.ch1_tcpmixed.clicked.connect(self.OPmodeEvent)
        self.ch1_udp.clicked.connect(self.OPmodeEvent)
        
        #############################################
        # Button icon set
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
        #############################################
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
        #############################################

    ## QThread 테스트
    #########################################################
        # self.testbtn1.clicked.connect(self.threadStart)
        # self.testbtn2.clicked.connect(self.threadStop)
        # 쓰레드 인스턴스 생성
        self.th = ProgressThread(self)
        # 쓰레드 이벤트 연결
        self.th.threadEvent.connect(self.threadEventHandler)

    ## QThread Test 
    @pyqtSlot()
    def threadStart(self):
        if not self.th.isRun:
            print('Main: Thread start')
            self.th.isRun = True
            self.th.start()
            # Progress bar
            self.statusbar.addPermanentWidget(self.progressbar)
            self.GetProgress()
    
    @pyqtSlot()
    def threadStop(self):
        if self.th.isRun:
            print('Main: Thread Stop')
            self.th.isRun = False
            # Remove progress bar
            self.progressbar.hide()
    
    # 쓰레드 이벤트 핸들러
    # 장식자에 파라미터 자료형을 명시
    @pyqtSlot(int)
    def threadEventHandler(self, n):
        print('Main: threadEvent(self,' + str(n) + ')')
    #########################################################
    def CheckOPmode(self):
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

    def GetProgress(self):
        self.completed = 0
        while self.completed < 100:
            self.completed += 0.001
            self.progressbar.setValue(self.completed)

    def Processing(self):
        # 어떤 동작을 수행중일 때는 버튼 비활성화
        self.btnsearch.setEnabled(False)
        QTimer.singleShot(1000, lambda: self.btnsearch.setEnabled(True))

    def Search(self):
        cmd_list = []

        self.Processing()

        # Broadcasting: Search All Devices on the network
        cmd_list = self.wizmakecmd.search_broadcast()

        self.statusbar.showMessage(' Searching devices...')
 
        # print(cmd_list)
        wizmsghangler = WIZMSGHandler(self.conf_sock)
        wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
        wizmsghangler.sendcommands()
        wizmsghangler.parseresponse()

        dev_name = wizmsghangler.mn_list
        mac_list = wizmsghangler.mac_list

        self.all_response = wizmsghangler.rcv_list

        # row length = the number of searched devices
        self.list_device.setRowCount(len(mac_list))
        
        # 검색된 장치 mac / name 출력
        for i in range(0, len(mac_list)):
            # device = "%s | %s" % (mac_list[i].decode(), dev_name[i].decode())
            self.list_device.setItem(i, 0, QTableWidgetItem(mac_list[i].decode()))
            self.list_device.setItem(i, 1, QTableWidgetItem(dev_name[i].decode()))

        # 데이터 사이즈에 따라 resize
        self.list_device.resizeColumnsToContents()
        self.list_device.resizeRowsToContents()
        
        # 행/열 크기 조정 disable
        self.list_device.horizontalHeader().setSectionResizeMode(2)
        self.list_device.verticalHeader().setSectionResizeMode(2)

        ## error => # self.statusbar.addPermanentWidget(self.icon_search)
        self.statusbar.showMessage(' Find %d devices' % len(mac_list))

        #### TEST: progress bar
        self.statusbar.addPermanentWidget(self.progressbar)
        self.GetProgress()
        # Remove progress bar
        self.progressbar.hide()

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
                    self.Dialog_invalid()
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
                    self.Dialog_invalid()
                    invalid_flag += 1
        # print('invalid flag: %d' % invalid_flag)
        if invalid_flag == 0:
            if self.curr_dev in ONE_PORT_DEV:
                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, list(setcmd.keys()), list(setcmd.values()), 1)
            elif self.curr_dev in TWO_PORT_DEV:
                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, list(setcmd.keys()), list(setcmd.values()), 2)
            print('set cmdlist: ', cmd_list)

            wizmsghangler = WIZMSGHandler(self.conf_sock)
            wizmsghangler.makecommands(cmd_list, OP_SETCOMMAND)
            wizmsghangler.sendcommands()
            wizmsghangler.parseresponse()
            
            self.statusbar.showMessage(' Set device complete!')

    def SelectDev(self):
        # 선택된 장치의 mac addr / name 추출 
        for currentQTableWidgetItem in self.list_device.selectedItems():
            if currentQTableWidgetItem.column() == 0:
                # mac_addr = currentQTableWidgetItem.text()
                self.curr_mac = currentQTableWidgetItem.text()
                # print('current mac addr:', self.curr_mac)
                # return mac_addr
            elif currentQTableWidgetItem.column() == 1:
                self.curr_dev = currentQTableWidgetItem.text()
                # print('current dev name:', self.curr_dev)
            
            self.statusbar.showMessage(' Current device [%s : %s]' % (self.curr_mac, self.curr_dev))

    def FWUpdate(self, filename):
        self.SelectDev()
        self.statusbar.showMessage(' Firmware update started. Please wait...')
        mac_addr = self.curr_mac
        print('FWUpdate %s, %s' % (mac_addr, filename))
        # FW update
        t_fwup = FWUploadThread()
        t_fwup.setparam(mac_addr, filename)
        t_fwup.jumpToApp()
        time.sleep(2)
        t_fwup.start()        
        self.threads.append(t_fwup)

        for thread in self.threads:
            thread.join()   # 쓰레드 종료 대기

        self.statusbar.showMessage(' Firmware update complete!')

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

        self.wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
        self.wizmsghangler.sendcommands()

        self.statusbar.showMessage(' Device reset device OK')

    def Factory(self):
        self.statusbar.showMessage(' Factory reset?')
        self.SelectDev()
        mac_addr = self.curr_mac
        cmd_list = self.wizmakecmd.factory_reset(mac_addr)
        print('Factory: %s' % cmd_list)
        
        self.wizmsghangler.makecommands(cmd_list, OP_SEARCHALL)
        self.wizmsghangler.sendcommands()

        self.statusbar.showMessage(' Device factory reset  OK')

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

    def OpenFWUerrDialog(self):
        dialog = FWErrorDialog()
        dialog.okbtn.clicked.connect(dialog.close)
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

    def OpenInfoDialog(self):
        dialog = InfoDialog()
        dialog.okbtn.clicked.connect(dialog.close)
        dialog.textBrowser.setAttribute(Qt.WA_TranslucentBackground)
        dialog.exec_()

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

    
    

