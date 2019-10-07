# -*- coding: utf-8 -*-

import sys
import time
import re
import os
import subprocess
import base64
# import ssl
# from urllib.parse import urlsplit
# from tkinter import Tk

# need to install package
from PyQt5.QtWidgets import QAction, QMainWindow, QApplication, QProgressBar, \
                QMenu, QTableWidgetItem, QInputDialog, QMessageBox, QFileDialog, QLineEdit
from PyQt5.QtCore import QSize, QThread, Qt, QTimer, pyqtSignal, QFileInfo
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5 import uic
import ifaddr

from WIZMSGHandler import WIZMSGHandler, DataRefresh
from FWUploadThread import FWUploadThread
from WIZUDPSock import WIZUDPSock
from WIZ750CMDSET import WIZ750CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from WIZ2000CMDSET import WIZ2000CMDSET
from WIZMakeCMD import WIZMakeCMD, version_compare, ONE_PORT_DEV, TWO_PORT_DEV
from wizsocket.TCPClient import TCPClient
# from CertUploadThread import CertUploadThread

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

VERSION = 'V1.1.0'

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

        # GUI font size init
        self.midfont = None
        self.smallfont = None
        self.btnfont = None
        
        self.gui_init()

        # Main icon
        self.setWindowIcon(QIcon(resource_path('gui/icon.ico')))
        self.set_btn_icon()

        self.wiz750cmdObj = WIZ750CMDSET(1)
        self.wiz752cmdObj = WIZ752CMDSET(1)
        self.wiz2000cmdObj = WIZ2000CMDSET(1)
        self.wizmakecmd = WIZMakeCMD()

        self.dev_profile = {}
        self.searched_devnum = None
        # init search option
        self.retry_search_num = 1
        self.search_wait_time = 3

        # check if use setting password 
        self.use_setting_pw = False
        # self.entered_set_pw = ''  # setting pw bak
        self.encoded_setting_pw = ''
        self.curr_setting_pw = '' # setting pw value
    
        self.mac_list = []
        self.dev_name = []
        self.vr_list = []
        self.st_list = []
        self.threads = []
        self.curr_mac = None
        self.curr_dev = None
        self.curr_ver = None
        self.curr_st = None

        self.search_pre_wait_time = 3
        self.search_wait_time_each = 1
        self.search_retry_flag = False
        self.search_retrynum = 0

        # last selected firmware file name/size (include path)
        self.fw_filename = None
        self.fw_filesize = None

        self.saved_path = None
        self.selected_eth = None
        self.cli_sock = None

        self.isConnected = False
        self.set_reponse = None
        self.wizmsghandler = None

        self.datarefresh = None

        # Tab information save
        self.userio_tab_text = self.generalTab.tabText(2)
        self.wiz2000_tab_text = self.generalTab.tabText(3)
        self.wiz2000_cloud_tab_text = self.generalTab.tabText(4)
        self.wiz2000_certificate_text = self.generalTab.tabText(5)
        self.ch1_tab_text = self.channel_tab.tabText(1)

        # Initial tab
        self.generalTab.removeTab(5)
        self.generalTab.removeTab(4)
        self.generalTab.removeTab(3)
        self.generalTab.removeTab(2)
        self.channel_tab.removeTab(1)   # default: 1 channel

        # Initial factory reset toolbutton
        self.init_btn_factory()

        # device select event
        self.list_device.itemClicked.connect(self.dev_clicked)

        # Button event
        self.btn_search.clicked.connect(self.do_search_normal)

        # WIZ2000: need setting password (setting, reset, upload, factory)
        self.btn_setting.clicked.connect(self.event_setting_clicked)
        self.btn_reset.clicked.connect(self.event_reset_clicked)

        # factory reset
        # WIZ2000: setting or factory two options
        self.btn_factory.clicked.connect(self.event_factory_setting)
        self.btn_factory.triggered[QAction].connect(self.event_factory_option_clicked)

        # for certificate management
        self.btn_cert_update.clicked.connect(self.event_certificate_clicked)
        # self.btn_cert_server_run.clicked.connect(self.get_certificate_from_server)
        self.btn_cert_save_file.clicked.connect(self.dialog_save_certificate)
        self.btn_cert_load_file.clicked.connect(self.dialog_load_certificate)
        self.btn_cert_clear.clicked.connect(self.clear_certificate)
        # device certificate update
        self.btn_device_cert_update.clicked.connect(self.btn_cert_update_clicked)
        # self.btn_cert_copy_clipboard.clicked.connect(self.btn_cert_copy_clipboard_clicked)
        self.certificate_detail.textChanged.connect(self.event_cert_changed)

        # configuration save/load button
        self.btn_saveconfig.clicked.connect(self.dialog_save_file)
        self.btn_loadconfig.clicked.connect(self.dialog_load_file)

        self.btn_upload.clicked.connect(self.update_btn_clicked)
        self.btn_exit.clicked.connect(self.msg_exit)

        # State Changed Event 
        self.show_idcode.stateChanged.connect(self.event_idcode)
        self.show_connectpw.stateChanged.connect(self.event_passwd)
        self.show_idcodeinput.stateChanged.connect(self.event_input_idcode)
        self.enable_connect_pw.stateChanged.connect(self.event_passwd_enable)
        self.at_enable.stateChanged.connect(self.event_atmode)
        self.ch1_keepalive_enable.stateChanged.connect(self.event_keepalive)
        self.ch2_keepalive_enable.stateChanged.connect(self.event_keepalive)
        self.ip_dhcp.clicked.connect(self.event_ip_alloc)
        self.ip_static.clicked.connect(self.event_ip_alloc)

        # Event: setting password
        self.enable_setting_pw.stateChanged.connect(self.event_setting_pw)
        self.show_settingpw.stateChanged.connect(self.event_setpw_show)

        # Event: cloud option
        self.cloud_enable.stateChanged.connect(self.event_cloud)
        self.modbus_monitor_config.currentIndexChanged.connect(self.event_modbus_monitor)

        # Event: OP mode
        self.ch1_tcpclient.clicked.connect(self.event_opmode)
        self.ch1_tcpserver.clicked.connect(self.event_opmode)
        self.ch1_tcpmixed.clicked.connect(self.event_opmode)
        self.ch1_udp.clicked.connect(self.event_opmode)

        self.ch2_tcpclient.clicked.connect(self.event_opmode)
        self.ch2_tcpserver.clicked.connect(self.event_opmode)
        self.ch2_tcpmixed.clicked.connect(self.event_opmode)
        self.ch2_udp.clicked.connect(self.event_opmode)

        # Event: Search method
        self.broadcast.clicked.connect(self.event_search_method)
        self.unicast_ip.clicked.connect(self.event_search_method)
        # self.unicast_mac.clicked.connect(self.event_search_method)

        self.pgbar = QProgressBar()
        self.statusbar.addPermanentWidget(self.pgbar)

        # progress thread
        self.th_search = ThreadProgress()
        self.th_search.change_value.connect(self.value_changed)

        # check if device selected
        self.list_device.itemSelectionChanged.connect(self.dev_selected)

        # Menu event - File
        self.actionSave.triggered.connect(self.dialog_save_file)
        self.actionLoad.triggered.connect(self.dialog_load_file)
        self.actionExit.triggered.connect(self.msg_exit)

        # Menu event - Help
        self.about_wiz.triggered.connect(self.about_info)

        # Menu event - Option
        self.net_adapter_info()
        self.netconfig_menu.triggered[QAction].connect(self.net_ifs_selected)
        # Menu event - Option - Search option
        self.action_set_wait_time.triggered.connect(self.input_search_wait_time)
        self.action_retry_search.triggered.connect(self.input_retry_search)

        # network interface selection
        self.net_interface.currentIndexChanged.connect(self.net_changed)

        # Tab changed
        self.generalTab.currentChanged.connect(self.tab_changed)

        # data refresh
        self.refresh_no.clicked.connect(self.get_refresh_time)
        self.refresh_1s.clicked.connect(self.get_refresh_time)
        self.refresh_5s.clicked.connect(self.get_refresh_time)
        self.refresh_10s.clicked.connect(self.get_refresh_time)
        self.refresh_30s.clicked.connect(self.get_refresh_time)

        # gpio config
        self.gpioa_config.currentIndexChanged.connect(self.gpio_check)
        self.gpiob_config.currentIndexChanged.connect(self.gpio_check)
        self.gpioc_config.currentIndexChanged.connect(self.gpio_check)
        self.gpiod_config.currentIndexChanged.connect(self.gpio_check)

    # TODO: factory reset ToolButton - 20181121
    def init_btn_factory(self):
        # factory_option = ['Factory default settings', 'Factory default firmware']
        self.factory_setting_action = QAction('Factory default settings', self)
        self.factory_firmware_action = QAction('Factory default firmware', self)
        
        self.btn_factory.addAction(self.factory_setting_action)
        self.btn_factory.addAction(self.factory_firmware_action)

        # for opt in factory_option:
        #     self.btn_factory.addAction(QAction(opt, self))

    def tab_changed(self):
        # self.selected_devinfo()
        if self.generalTab.currentIndex() == 0:
            try:
                if self.datarefresh is not None:
                    if self.datarefresh.isRunning():
                        self.datarefresh.terminate()
            except Exception as e:
                print('[ERROR] tab_changed(): %r' % e)
        elif self.generalTab.currentIndex() == 2 and 'WIZ750' in self.curr_dev:
            self.gpio_check()
            self.get_refresh_time()

    def net_ifs_selected(self, netifs):
        ifs = netifs.text().split(':')
        selected_ip = ifs[0]
        selected_name = ifs[1]

        print('net_ifs_selected() %s: %s' % (selected_ip, selected_name))
        
        self.statusbar.showMessage(' Selected: %s: %s' % (selected_ip, selected_name))
        self.selected_eth = selected_ip

    def value_changed(self, value):
        self.pgbar.show()
        self.pgbar.setValue(value)

    def dev_selected(self):
        if len(self.list_device.selectedItems()) == 0:
            self.disable_object()
        else:
            self.object_config()

    def net_changed(self, ifs):
        print('====> net_changed()', self.net_interface.currentText())
        ifs = self.net_interface.currentText().split(':')
        selected_ip = ifs[0]
        selected_name = ifs[1]

        self.statusbar.showMessage(' Selected eth: %s: %s' % (selected_ip, selected_name))
        self.selected_eth = selected_ip
    
    # Get network adapter & IP list
    def net_adapter_info(self):
        self.netconfig_menu = QMenu('Network Interface Config', self)
        self.netconfig_menu.setFont(self.midfont)
        self.menuOption.addMenu(self.netconfig_menu)

        adapters = ifaddr.get_adapters() 
        self.net_list = []
        
        for adapter in adapters:
            # print("Net Interface:", adapter.nice_name)
            for ip in adapter.ips:
                if len(ip.ip) > 6:
                    ipv4_addr = ip.ip
                    if ipv4_addr == '127.0.0.1':
                        pass
                    else:
                        net_ifs = ipv4_addr + ':' + adapter.nice_name

                        #-- get network interface list
                        self.net_list.append(adapter.nice_name)
                        netconfig = QAction(net_ifs, self)
                        self.netconfig_menu.addAction(netconfig)
                        self.net_interface.addItem(net_ifs)
                else:
                    ipv6_addr = ip.ip

    def disable_object(self):
        self.btn_reset.setEnabled(False)
        self.btn_factory.setEnabled(False)
        self.btn_upload.setEnabled(False)
        self.btn_setting.setEnabled(False)
        self.btn_saveconfig.setEnabled(False)
        self.btn_loadconfig.setEnabled(False)

        self.generalTab.setEnabled(False)
        self.channel_tab.setEnabled(False)

    def object_config(self):
        self.selected_devinfo()

        # Enable buttons
        self.btn_reset.setEnabled(True)
        self.btn_factory.setEnabled(True)
        self.btn_upload.setEnabled(True)
        self.btn_setting.setEnabled(True)
        self.btn_saveconfig.setEnabled(True)
        self.btn_loadconfig.setEnabled(True)

        # Enable tab group
        self.generalTab.setEnabled(True)
        self.generalTab.setTabEnabled(0, True)

        # tab config
        self.general_tab_config()
        self.channel_tab_config()

        # TODO: WIZ750SR 또는 다른 모듈 버전별로 오브젝트 enable/disable
        self.object_config_for_version()

        self.refresh_grp.setEnabled(True)
        self.exp_gpio.setEnabled(True)

        self.channel_tab.setEnabled(True)
        self.event_passwd_enable()
        
        # enable menu
        self.save_config.setEnabled(True)
        self.load_config.setEnabled(True)

        self.event_opmode()
        self.event_search_method()
        self.event_ip_alloc()
        self.event_atmode()
        self.event_keepalive()
        self.event_cloud()
        self.event_setting_pw()
        self.event_localport_fix()
        self.event_modbus_monitor()
        self.event_cert_changed()

        self.gpio_check()

    def event_certificate_clicked(self):
        print('event_certificate_clicked')
        # tab change
        self.generalTab.setCurrentIndex(4)

    # # button click events
    def event_setting_clicked(self):
        if 'WIZ2000' in self.curr_dev:
            self.input_setting_pw('setting')
        else:
            self.do_setting()

    def event_reset_clicked(self):
        if 'WIZ2000' in self.curr_dev:
            self.input_setting_pw('reset')
        else:
            self.do_reset()
        
    def event_factory_setting(self):
        if 'WIZ2000' in self.curr_dev:
            self.input_setting_pw('factory_setting')
        else:
            self.msg_factory_setting()
    
    def event_factory_firmware(self):
        if 'WIZ2000' in self.curr_dev:
            self.input_setting_pw('factory_firmware')
        else:
            self.msg_factory_firmware()
    
    # factory reset options
    # option: factory button / menu 1, menu 2
    def event_factory_option_clicked(self, option):
        print('event_factory_option_clicked', option.text())
        opt = option.text()

        if 'settings' in opt:
            self.event_factory_setting()
        elif 'firmware' in opt:
            self.event_factory_firmware()

    def event_upload_clicked(self):
        if 'WIZ2000' in self.curr_dev:
            self.input_setting_pw('upload')
        else:
            self.update_btn_clicked()

    def gpio_check(self):
        if self.gpioa_config.currentIndex() == 1: self.gpioa_set.setEnabled(True)
        else: self.gpioa_set.setEnabled(False)
        if self.gpiob_config.currentIndex() == 1: self.gpiob_set.setEnabled(True)
        else: self.gpiob_set.setEnabled(False)
        if self.gpioc_config.currentIndex() == 1: self.gpioc_set.setEnabled(True)
        else: self.gpioc_set.setEnabled(False)
        if self.gpiod_config.currentIndex() == 1: self.gpiod_set.setEnabled(True)
        else: self.gpiod_set.setEnabled(False)

    # 펌웨어 버전 별 오브젝트 설정
    def object_config_for_version(self):
        if 'WIZ750' in self.curr_dev: 
            if version_compare('1.2.0', self.curr_ver) <= 0:
                # setcmd['TR'] = self.tcp_timeout.text()
                self.tcp_timeout.setEnabled(True)
            else:
                self.tcp_timeout.setEnabled(False)
        
        if 'WIZ2000' in self.curr_dev:
            self.tcp_timeout.setEnabled(True)
            self.factory_setting_action.setEnabled(True)
            self.factory_firmware_action.setEnabled(True)
        else:
            self.factory_setting_action.setEnabled(True)
            self.factory_firmware_action.setEnabled(False)


    def general_tab_config(self):
        # for WIZ2000
        if 'WIZ2000' in self.curr_dev:
            self.generalTab.insertTab(3, self.wiz2000_tab, self.wiz2000_tab_text)
            self.generalTab.insertTab(4, self.wiz2000_cloud_tab, self.wiz2000_cloud_tab_text)
            self.generalTab.insertTab(5, self.wiz2000_certificate_tab, self.wiz2000_certificate_text)

            self.generalTab.setTabEnabled(3, True)
            self.generalTab.setTabEnabled(4, True)
            self.generalTab.setTabEnabled(5, True)
            self.ch1_localport_fix.setEnabled(True)
        else:
            self.generalTab.removeTab(5)
            self.generalTab.removeTab(4)
            self.generalTab.removeTab(3)

            self.ch1_localport_fix.setEnabled(False)

        # User I/O tab (WIZ750SR)
        if 'WIZ750' in self.curr_dev:
            self.generalTab.insertTab(2, self.userio_tab, self.userio_tab_text)
            self.generalTab.setTabEnabled(2, True)
        else:
            if 'WIZ2000' in self.curr_dev:
                if len(self.generalTab) == 6:
                    self.generalTab.removeTab(2)
                elif len(self.generalTab) == 5:
                    pass
            else:
                self.generalTab.removeTab(2)

    def channel_tab_config(self):
        # channel tab config
        if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev or 'WIZ2000' in self.curr_dev:
            self.channel_tab.removeTab(1)
            self.channel_tab.setTabEnabled(0, True)
        elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
            self.channel_tab.insertTab(1, self.tab_ch1, self.ch1_tab_text)
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, True)

    def event_cert_changed(self):
        cert = self.certificate_detail.toPlainText()
        if len(cert) > 0:
            self.btn_device_cert_update.setEnabled(True)
        else: 
            self.btn_device_cert_update.setEnabled(False)

    def event_modbus_monitor(self):
        if self.modbus_monitor_config.currentIndex() == 0:
            self.monitor_ch1_id.setEnabled(False)
            self.monitor_ch2_id.setEnabled(False)
            self.monitor_ch3_id.setEnabled(False)
            self.monitor_ch4_id.setEnabled(False)
        elif self.modbus_monitor_config.currentIndex() == 1:
            self.monitor_ch1_id.setEnabled(True)
            self.monitor_ch2_id.setEnabled(False)
            self.monitor_ch3_id.setEnabled(False)
            self.monitor_ch4_id.setEnabled(False)
        elif self.modbus_monitor_config.currentIndex() == 2:
            self.monitor_ch1_id.setEnabled(True)
            self.monitor_ch2_id.setEnabled(True)
            self.monitor_ch3_id.setEnabled(False)
            self.monitor_ch4_id.setEnabled(False)
        elif self.modbus_monitor_config.currentIndex() == 3:
            self.monitor_ch1_id.setEnabled(True)
            self.monitor_ch2_id.setEnabled(True)
            self.monitor_ch3_id.setEnabled(True)
            self.monitor_ch4_id.setEnabled(False)
        elif self.modbus_monitor_config.currentIndex() == 4:
            self.monitor_ch1_id.setEnabled(True)
            self.monitor_ch2_id.setEnabled(True)
            self.monitor_ch3_id.setEnabled(True)
            self.monitor_ch4_id.setEnabled(True)
        
    def event_cloud(self):
        if self.cloud_enable.isChecked():
            self.groupbox_cloudinfo.setEnabled(True)
            self.groupbox_monitor.setEnabled(True)
            self.event_modbus_monitor()
        else:
            self.groupbox_cloudinfo.setEnabled(False)
            self.groupbox_monitor.setEnabled(False)
    
    def event_setting_pw(self):
        if self.enable_setting_pw.isChecked():
            self.setting_pw.setEnabled(True)
        elif self.enable_setting_pw.isChecked() is False:
            self.setting_pw.setEnabled(False)

    def event_localport_fix(self):
        if self.ch1_localport_fix.isChecked():
            self.ch1_localport.setEnabled(False)
        elif self.ch1_localport_fix.isChecked() is False:
            self.ch1_localport.setEnabled(True)

    def event_ip_alloc(self):
        if self.ip_dhcp.isChecked() is True:
            self.localip.setEnabled(False)
            self.subnet.setEnabled(False)
            self.gateway.setEnabled(False)
            self.dns_addr.setEnabled(False)
        elif self.ip_dhcp.isChecked() is False:
            self.localip.setEnabled(True)
            self.subnet.setEnabled(True)
            self.gateway.setEnabled(True)
            self.dns_addr.setEnabled(True)

    def event_keepalive(self):
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
    
    def event_atmode(self):
        if self.at_enable.isChecked() is True:
            self.at_hex1.setEnabled(True)
            self.at_hex2.setEnabled(True)
            self.at_hex3.setEnabled(True)
        elif self.at_enable.isChecked() is False:
            self.at_hex1.setEnabled(False)
            self.at_hex2.setEnabled(False)
            self.at_hex3.setEnabled(False)

    def event_input_idcode(self):
        if self.show_idcodeinput.isChecked() is True:
            self.searchcode_input.setEchoMode(QLineEdit.Normal)
        elif self.show_idcodeinput.isChecked() is False:
            self.searchcode_input.setEchoMode(QLineEdit.Password)

    def event_idcode(self):
        if self.show_idcode.isChecked() is True:
            self.searchcode.setEchoMode(QLineEdit.Normal)
        elif self.show_idcode.isChecked() is False:
            self.searchcode.setEchoMode(QLineEdit.Password)

    def event_passwd(self):
        if self.show_connectpw.isChecked() is True:
            self.connect_pw.setEchoMode(QLineEdit.Normal)
        elif self.show_connectpw.isChecked() is False:
            self.connect_pw.setEchoMode(QLineEdit.Password)

    def event_setpw_show(self):
        if self.show_settingpw.isChecked() is True:
            self.setting_pw.setEchoMode(QLineEdit.Normal)
        elif self.show_settingpw.isChecked() is False:
            self.setting_pw.setEchoMode(QLineEdit.Password)

    def event_passwd_enable(self):
        if self.enable_connect_pw.isChecked() is True:
            self.connect_pw.setEnabled(True)
        elif self.enable_connect_pw.isChecked() is False:
            self.connect_pw.setEnabled(False)

    def event_opmode(self):
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

    def event_search_method(self):
        if self.broadcast.isChecked() is True:
            self.search_ipaddr.setEnabled(False)
            self.search_port.setEnabled(False)
        elif self.unicast_ip.isChecked() is True:
            self.search_ipaddr.setEnabled(True)
            self.search_port.setEnabled(True)

    def sock_close(self):
        # 기존 연결 fin 
        if self.cli_sock is not None:
            if self.cli_sock.state is not SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()

    def connect_over_tcp(self, serverip, port):
        retrynum = 0
        self.cli_sock = TCPClient(2, serverip, port)
        # print('sock state: %r' % (self.cli_sock.state))

        while True:
            if retrynum > 6:
                break
            retrynum += 1

            if self.cli_sock.state is SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()
                cur_state = self.cli_sock.state
                try:
                    self.cli_sock.open()
                    if self.cli_sock.state is SOCK_OPEN_STATE:
                        print('[%r] is OPEN' % (serverip))
                    time.sleep(0.2)
                except Exception as e:
                    sys.stdout.write('TCP Socket open error: %r\r\n' % e)
            elif self.cli_sock.state is SOCK_OPEN_STATE:
                cur_state = self.cli_sock.state
                try:
                    self.cli_sock.connect()
                    if self.cli_sock.state is SOCK_CONNECT_STATE:
                        print('[%r] is CONNECTED' % (serverip))
                except Exception as e:
                    sys.stdout.write('TCP Socket connect error: %r\r\n' % e)
            elif self.cli_sock.state is SOCK_CONNECT_STATE:
                break
        if retrynum > 6:
            sys.stdout.write('Device [%s] TCP connection failed.\r\n' % (serverip))
            return None
        else:
            sys.stdout.write('Device [%s] TCP connected\r\n' % (serverip))
            return self.cli_sock

    def socket_config(self):
        # Broadcast
        # if self.broadcast.isChecked() or self.unicast_mac.isChecked():
        if self.broadcast.isChecked():
            if self.selected_eth is None:
                self.conf_sock = WIZUDPSock(5000, 50001, "")
            else:
                self.conf_sock = WIZUDPSock(5000, 50001, self.selected_eth)
                print('selected eth IP address:', self.selected_eth)

            # self.conf_sock = WIZUDPSock(5000, 50001)
            self.conf_sock.open()

        # TCP unicast
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            print('unicast: ip: %r, port: %r' % (ip_addr, port))

            ## network check
            net_response = self.net_check_ping(ip_addr)

            if net_response == 0:
                self.conf_sock = self.connect_over_tcp(ip_addr, port)

                if self.conf_sock is None:
                    self.isConnected = False
                    print('TCP connection failed!: %s' % self.conf_sock)
                    self.statusbar.showMessage(' TCP connection failed: %s' % ip_addr)
                    self.msg_connection_failed()
                else:
                    self.isConnected = True
                self.btn_search.setEnabled(True)
            else:
                self.statusbar.showMessage(' Network unreachable: %s' % ip_addr)
                self.btn_search.setEnabled(True)
                self.msg_not_connected(ip_addr)

    # expansion GPIO config
    def refresh_gpio(self, mac_addr):
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
                # print('refresh_gpio', cmd_list)

                if self.unicast_ip.isChecked():
                    self.datarefresh = DataRefresh(self.conf_sock, cmd_list, 'tcp', self.intv_time)
                else:
                    self.datarefresh = DataRefresh(self.conf_sock, cmd_list, 'udp', self.intv_time)
                self.threads.append(self.datarefresh)
                self.datarefresh.resp_check.connect(self.gpio_update)
                self.datarefresh.start()
        
    def get_refresh_time(self):
        self.selected_devinfo()

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
        
        self.refresh_gpio(self.curr_mac)

    def gpio_update(self, num):
        if num == 0:
            pass
        else:
            if not self.datarefresh.rcv_list:
                pass
            else:
                resp = self.datarefresh.rcv_list[0]
                cmdset_list = resp.splitlines()

                try:
                    ## Expansion GPIO
                    for i in range(len(cmdset_list)):
                        if num < 2:
                            if b'CA' in cmdset_list[i]: self.gpioa_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CB' in cmdset_list[i]: self.gpiob_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CC' in cmdset_list[i]: self.gpioc_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CD' in cmdset_list[i]: self.gpiod_config.setCurrentIndex(int(cmdset_list[i][2:]))

                        if b'GA' in cmdset_list[i]: self.gpioa_get.setText(cmdset_list[i][2:].decode())
                        if b'GB' in cmdset_list[i]: self.gpiob_get.setText(cmdset_list[i][2:].decode())
                        if b'GC' in cmdset_list[i]: self.gpioc_get.setText(cmdset_list[i][2:].decode())
                        if b'GD' in cmdset_list[i]: self.gpiod_get.setText(cmdset_list[i][2:].decode())
                except Exception as e:
                    print('[ERROR] gpio_update(): %r' % e)
                    # self.msg_error('[ERROR] gpio_update(): %r' % e)

    def do_search_retry(self, num):
        self.search_retry_flag = True
        # search retry number
        self.search_retrynum = num
        print('mac_list:', self.mac_list)

        self.search_pre()

    def do_search_normal(self):
        self.search_retry_flag = False
        self.search_pre()

    def search_pre(self):
        if self.wizmsghandler is not None and self.wizmsghandler.isRunning():
            self.wizmsghandler.wait()
            # print('wait')
        else:
            # 기존 연결 close
            self.sock_close()

            cmd_list = []
            # default search id code
            self.code = " "
            self.all_response = []
            self.pgbar.setFormat('Searching..')
            self.pgbar.setRange(0, 100)
            self.th_search.start()
            self.processing()

            if self.search_retry_flag:
                print('keep searched list')
                pass
            else:
                # List table initial (clear)
                self.list_device.clear()
                while self.list_device.rowCount() > 0:
                    self.list_device.removeRow(0)

            item_mac = QTableWidgetItem()
            item_mac.setText("Mac address")
            item_mac.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(0, item_mac)

            item_name = QTableWidgetItem()
            item_name.setText("Name")
            item_name.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(1, item_name)
            
            self.socket_config()
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
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SEARCHALL, self.search_pre_wait_time)
                else:
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SEARCHALL, self.search_pre_wait_time)
                self.wizmsghandler.search_result.connect(self.get_search_result)
                self.wizmsghandler.start()


    def processing(self):
        self.btn_search.setEnabled(False)
        # QTimer.singleShot(1500, lambda: self.btn_search.setEnabled(True))
        QTimer.singleShot(4500, lambda: self.pgbar.hide())

    def search_each_dev(self, dev_info_list):
        cmd_list = []
        self.eachdev_info = []

        self.code = " "
        # self.all_response = []
        self.pgbar.setFormat('Search for each device...')
        
        if self.broadcast.isChecked():
            self.socket_config()
        else:
            # tcp unicast일 경우 search_pre에서 이미 커넥션이 수립되어 있음
            pass

        # Search devices
        if self.isConnected or self.broadcast.isChecked():
            self.statusbar.showMessage(' Get each device information...')

            if len(self.searchcode_input.text()) == 0: 
                self.code = " "
            else: 
                self.code = self.searchcode_input.text()

            # dev_info => [mac_addr, name, version]
            for dev_info in dev_info_list:
                # print('dev_info', dev_info)
                cmd_list = self.wizmakecmd.search(dev_info[0], self.code, dev_info[1], dev_info[2])
                # print(cmd_list)
                th_name = "dev_%s" % dev_info[0]
                if self.unicast_ip.isChecked(): 
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SEARCHALL, self.search_wait_time_each)
                else: 
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SEARCHALL, self.search_wait_time_each)
                th_name.searched_data.connect(self.getsearch_each_dev)
                th_name.start()
                th_name.wait()
                self.statusbar.showMessage(' Done.')

    def getsearch_each_dev(self, dev_data):
        # print('getsearch_each_dev', dev_data)
        profile = {}

        try:
            if dev_data is not None:
                self.eachdev_info.append(dev_data)
                # print('eachdev_info', len(self.eachdev_info), self.eachdev_info)
                for i in range(len(self.eachdev_info)):
                    cmdsets = self.eachdev_info[i].splitlines()
                    for i in range(len(cmdsets)):
                        # print('cmdsets', i, cmdsets[i], cmdsets[i][:2], cmdsets[i][2:])
                        if cmdsets[i][:2] == b'MA':
                            pass
                        else:
                            cmd = cmdsets[i][:2].decode()
                            param = cmdsets[i][2:].decode()
                            profile[cmd] = param
                
                    # print('profile', profile)
                    self.dev_profile[profile['MC']] = profile
                    profile = {}

                    self.all_response = self.eachdev_info

                    # when retry search
                    if self.search_retrynum:
                        print('search_retrynum: ', self.search_retrynum)
                        self.search_retrynum = self.search_retrynum - 1
                        self.search_pre()
                    else:
                        pass
            else:
                pass
        except Exception as e:
            print('[ERROR] getsearch_each_dev(): %r' % e)
            self.msg_error('[ERROR] getsearch_each_dev(): %r' % e)

        # print('self.dev_profile', self.dev_profile)

    def get_search_result(self, devnum):

        if self.search_retry_flag:
            pass
        else:
            # init old info
            self.mac_list = []
            self.dev_name = []
            self.vr_list = []
            self.st_list = []

        if self.wizmsghandler.isRunning():
            self.wizmsghandler.wait()
        if devnum >= 0:
            self.searched_devnum = devnum
            # print('searched device num:', self.searched_devnum)
            self.searched_num.setText(str(self.searched_devnum))
            self.btn_search.setEnabled(True)

            if devnum == 0:
                print('No device.')
            else:
                if self.search_retry_flag:
                    print('search retry flag on')
                    new_mac_list = self.wizmsghandler.mac_list
                    new_mn_list = self.wizmsghandler.mn_list
                    new_vr_list = self.wizmsghandler.vr_list
                    new_st_list = self.wizmsghandler.st_list
                    new_resp_list = self.wizmsghandler.rcv_list

                    # check mac list                    
                    for i in range(len(new_mac_list)):
                        if new_mac_list[i] in self.mac_list:
                            pass
                        else:
                            self.mac_list.append(new_mac_list[i])
                            self.dev_name.append(new_mn_list[i])
                            self.vr_list.append(new_vr_list[i])
                            self.st_list.append(new_st_list[i])
                            self.all_response.append(new_resp_list[i])

                    # print('keep list len >>', len(self.mac_list), len(self.dev_name), len(self.vr_list), len(self.st_list))
                    # print('keep list >>', self.mac_list, self.dev_name, self.vr_list, self.st_list)
                    
                else:
                    self.mac_list = self.wizmsghandler.mac_list
                    self.dev_name = self.wizmsghandler.mn_list
                    self.vr_list = self.wizmsghandler.vr_list
                    self.st_list = self.wizmsghandler.st_list
                    # all response
                    self.all_response = self.wizmsghandler.rcv_list

                # print('all_response', len(self.all_response), self.all_response)
                # print('get_search_result():', self.mac_list, self.dev_name, self.vr_list, self.st_list)
            
                # row length = the number of searched devices
                self.list_device.setRowCount(len(self.mac_list))
                
                try:
                    for i in range(0, len(self.mac_list)):
                        # device = "%s | %s" % (self.mac_list[i].decode(), self.dev_name[i].decode())
                        self.list_device.setItem(i, 0, QTableWidgetItem(self.mac_list[i].decode()))
                        self.list_device.setItem(i, 1, QTableWidgetItem(self.dev_name[i].decode()))
                except Exception as e:
                    print('[ERROR] main_gui get_search_result(): %r' % e)

                # resize for data
                self.list_device.resizeColumnsToContents()
                self.list_device.resizeRowsToContents()
                
                # row/column resize disable
                self.list_device.horizontalHeader().setSectionResizeMode(2)
                self.list_device.verticalHeader().setSectionResizeMode(2)

            self.statusbar.showMessage(' Find %d devices' % devnum)
            self.get_dev_list()
        else: 
            print('search error')

    def get_dev_list(self):
        # basic_data = None
        self.searched_dev = []
        self.dev_data = {}
        
        # print(self.mac_list, self.dev_name, self.vr_list)
        if self.mac_list is not None:
            try:
                for i in range(len(self.mac_list)):
                    # self.searched_dev.append([self.mac_list[i].decode(), self.dev_name[i].decode(), self.vr_list[i].decode()])
                    # self.dev_data[self.mac_list[i].decode()] = [self.dev_name[i].decode(), self.vr_list[i].decode()]
                    self.searched_dev.append([self.mac_list[i].decode(), self.dev_name[i].decode(), self.vr_list[i].decode(), self.st_list[i].decode()])
                    self.dev_data[self.mac_list[i].decode()] = [self.dev_name[i].decode(), self.vr_list[i].decode(), self.st_list[i].decode()]
            except Exception as e:
                print('[ERROR] main_gui get_dev_list(): %r' % e)

            # print('get_dev_list()', self.searched_dev, self.dev_data)
            self.search_each_dev(self.searched_dev)
        else: print('There is no device.')

    def dev_clicked(self):
        dev_info = []
        if self.generalTab.currentIndex() == 2 and 'WIZ750' in self.curr_dev:
            self.gpio_check()
            self.get_refresh_time()
        for currentItem in self.list_device.selectedItems():
            # print('Click info:', currentItem, currentItem.row(), currentItem.column(), currentItem.text())
            # print('clicked', self.list_device.selectedItems()[0].text())
            # self.getdevinfo(currentItem.row())
            clicked_mac = self.list_device.selectedItems()[0].text()

        self.get_clicked_devinfo(clicked_mac)
        
    def get_clicked_devinfo(self, macaddr):
        self.object_config()

        # device profile(json format)
        if macaddr in self.dev_profile:
            dev_data = self.dev_profile[macaddr]
            # print('clicked device information:', dev_data)

            self.fill_devinfo(dev_data)
        else:
            if ( len(self.dev_profile) != self.searched_devnum ):
                print('warning: 검색된 장치의 수와 프로파일된 장치의 수가 다릅니다.')
            print('warning: retry search')

    def check_dev_data(self):
        pass

    # TODO: decode exception handling
    def fill_devinfo(self, dev_data):
        # print('fill_devinfo', dev_data)
        try:
            # device info (RO)
            if 'MN' in dev_data: 
                self.dev_type.setText(dev_data['MN'])
            if 'VR' in dev_data: 
                self.fw_version.setText(dev_data['VR'])
            # device info - channel 1
            if 'ST' in dev_data:
                self.ch1_status.setText(dev_data['ST'])
            if 'UN' in dev_data : 
                self.ch1_uart_name.setText(dev_data['UN'])
            # Network - general
            if 'IM' in dev_data:
                if dev_data['IM'] == '0': 
                    self.ip_static.setChecked(True)
                elif dev_data['IM'] == '1': 
                    self.ip_dhcp.setChecked(True)
            if 'LI' in dev_data : 
                self.localip.setText(dev_data['LI'])
                self.localip_addr = dev_data['LI']
            if 'SM' in dev_data: self.subnet.setText(dev_data['SM'])
            if 'GW' in dev_data: self.gateway.setText(dev_data['GW'])
            if 'DS' in dev_data: self.dns_addr.setText(dev_data['DS'])
            # TCP transmisstion retry count
            if 'TR' in dev_data: 
                if dev_data['TR'] == '0':
                    self.tcp_timeout.setText('8')
                else:
                    self.tcp_timeout.setText(dev_data['TR'])
            # etc - general
            if 'CP' in dev_data: 
                self.enable_connect_pw.setChecked(int(dev_data['CP']))
            if 'NP' in dev_data: 
                if dev_data['NP'] == ' ':
                    self.connect_pw.setText(None)
                else:
                    self.connect_pw.setText(dev_data['NP'])
            # command mode (AT mode)
            if 'TE' in dev_data: self.at_enable.setChecked(int(dev_data['TE']))
            if 'SS' in dev_data: 
                self.at_hex1.setText(dev_data['SS'][0:2])
                self.at_hex2.setText(dev_data['SS'][2:4])
                self.at_hex3.setText(dev_data['SS'][4:6])
            # search id code
            if 'SP' in dev_data: 
                if dev_data['SP'] == ' ':
                    self.searchcode.clear()
                else:
                    self.searchcode.setText(dev_data['SP'])
            # Debug msg - for test
            if 'DG' in dev_data:
                pass
                # TODO => serial debug 드랍박스로 다시 변경: 동작 변경요망
                if int(dev_data['DG']) < 2:
                    self.serial_debug.setCurrentIndex(int(dev_data['DG']))
                elif dev_data['DG'] == '4':
                    self.serial_debug.setCurrentIndex(2)
            # Network - channel 1
            if 'OP' in dev_data:
                if dev_data['OP'] == '0': 
                    self.ch1_tcpclient.setChecked(True)
                elif dev_data['OP'] == '1': 
                    self.ch1_tcpserver.setChecked(True)
                elif dev_data['OP'] == '2': 
                    self.ch1_tcpmixed.setChecked(True)
                elif dev_data['OP'] == '3': 
                    self.ch1_udp.setChecked(True)
            
            if 'LP' in dev_data:
                self.ch1_localport.setText(dev_data['LP'])
            if 'RH' in dev_data:
                self.ch1_remoteip.setText(dev_data['RH'])
            if 'RP' in dev_data:
                self.ch1_remoteport.setText(dev_data['RP'])
            # serial - channel 1
            if 'BR' in dev_data:
                self.ch1_baud.setCurrentIndex(int(dev_data['BR']))
            if 'DB' in dev_data:
                if len(dev_data['DB']) > 2:
                    pass
                else: 
                    self.ch1_databit.setCurrentIndex(int(dev_data['DB']))
            if 'PR' in dev_data: self.ch1_parity.setCurrentIndex(int(dev_data['PR']))
            if 'SB' in dev_data: self.ch1_stopbit.setCurrentIndex(int(dev_data['SB']))
            if 'FL' in dev_data: self.ch1_flow.setCurrentIndex(int(dev_data['FL']))
            if 'PT' in dev_data: self.ch1_pack_time.setText(dev_data['PT'])
            if 'PS' in dev_data: self.ch1_pack_size.setText(dev_data['PS'])
            if 'PD' in dev_data: self.ch1_pack_char.setText(dev_data['PD'])
            # Inactive timer - channel 1
            if 'IT' in dev_data: self.ch1_inact_timer.setText(dev_data['IT'])
            # TCP keep alive - channel 1
            if 'KA' in dev_data:
                if dev_data['KA'] == '0': self.ch1_keepalive_enable.setChecked(False)
                elif dev_data['KA'] == '1': self.ch1_keepalive_enable.setChecked(True)
            if 'KI' in dev_data: self.ch1_keepalive_initial.setText(dev_data['KI'])
            if 'KE' in dev_data: self.ch1_keepalive_retry.setText(dev_data['KE'])
            # reconnection - channel 1
            if 'RI' in dev_data: self.ch1_reconnection.setText(dev_data['RI'])
            
            # Status pin ( status_phy / status_dtr || status_tcpst / status_dsr )
            if 'SC' in dev_data:
                if dev_data['SC'][0:1] == '0':
                    self.status_phy.setChecked(True)
                elif dev_data['SC'][0:1] == '1':
                    self.status_dtr.setChecked(True)
                if dev_data['SC'][1:2] == '0':
                    self.status_tcpst.setChecked(True)
                elif dev_data['SC'][1:2] == '1':
                    self.status_dsr.setChecked(True)

            # # Channel 2 config (For two Port device)
            if self.curr_dev in TWO_PORT_DEV:
                # device info - channel 2
                if 'QS' in dev_data: self.ch2_status.setText(dev_data['QS'])
                if 'EN' in dev_data: 
                    self.ch2_uart_name.setText(dev_data['EN'])
                # Network - channel 2
                if 'QO' in dev_data: 
                    if dev_data['QO'] == '0': self.ch2_tcpclient.setChecked(True)
                    elif dev_data['QO'] == '1': self.ch2_tcpserver.setChecked(True)
                    elif dev_data['QO'] == '2': self.ch2_tcpmixed.setChecked(True)
                    elif dev_data['QO'] == '3': self.ch2_udp.setChecked(True)
                if 'QL' in dev_data: self.ch2_localport.setText(dev_data['QL'])
                if 'QH' in dev_data: self.ch2_remoteip.setText(dev_data['QH'])
                if 'QP' in dev_data: self.ch2_remoteport.setText(dev_data['QP'])
                # serial - channel 2
                if 'EB' in dev_data: 
                    if (len(dev_data['EB']) > 4):
                        pass 
                    else:
                        self.ch2_baud.setCurrentIndex(int(dev_data['EB']))

                if 'ED' in dev_data: 
                    if (len(dev_data['ED']) > 2):   
                        pass 
                    else:
                        self.ch2_databit.setCurrentIndex(int(dev_data['ED']))
                if 'EP' in dev_data: self.ch2_parity.setCurrentIndex(int(dev_data['EP']))
                if 'ES' in dev_data: self.ch2_stopbit.setCurrentIndex(int(dev_data['ES']))
                if 'EF' in dev_data: 
                    if (len(dev_data['EF']) > 2):   
                        pass
                    else:
                        self.ch2_flow.setCurrentIndex(int(dev_data['EF']))
                if 'NT' in dev_data: self.ch2_pack_time.setText(dev_data['NT'])
                if 'NS' in dev_data: self.ch2_pack_size.setText(dev_data['NS'])
                if 'ND' in dev_data: 
                    if (len(dev_data['ND']) > 2):
                        pass
                    else:
                        self.ch2_pack_char.setText(dev_data['ND'])
                # Inactive timer - channel 2
                if 'RV' in dev_data: self.ch2_inact_timer.setText(dev_data['RV'])
                # TCP keep alive - channel 2
                if 'RA' in dev_data: 
                    if dev_data['RA'] == '0': self.ch2_keepalive_enable.setChecked(False)
                    elif dev_data['RA'] == '1': self.ch2_keepalive_enable.setChecked(True)
                if 'RS' in dev_data: 
                    self.ch2_keepalive_initial.setText(dev_data['RS'])
                if 'RE' in dev_data: self.ch2_keepalive_retry.setText(dev_data['RE'])
                # reconnection - channel 2
                if 'RR' in dev_data: self.ch2_reconnection.setText(dev_data['RR'])

            # for WIZ2000 device server
            elif 'WIZ2000' in self.curr_dev:
                if 'MB' in dev_data:
                    if dev_data['MB'] == '0': 
                        self.modbus_s2e.setChecked(True)
                    elif dev_data['MB'] == '1': 
                        self.modbus_rtu_tcp.setChecked(True)
                    elif dev_data['MB'] == '2': 
                        self.modbus_asci_tcp.setChecked(True)
                # if 'MM' in dev_data:    # channel 2
                #     pass
                if 'SE' in dev_data:    # tls 1.2 option
                    if dev_data['SE'] == '0': self.tls_enable.setChecked(False)
                    elif dev_data['SE'] == '1': self.tls_enable.setChecked(True)
                
                # device alias
                # dev_alias / dev_group
                if 'AL' in dev_data:
                    self.dev_alias.setText(dev_data['AL'])
                if 'GR' in dev_data:
                    self.dev_group.setText(dev_data['GR'])
                # TCP connection success msg
                if 'AM' in dev_data:
                    self.tcp_success_msg.setCurrentIndex(int(dev_data['AM']))
                # Local port fix
                if 'LF' in dev_data:
                    if dev_data['LF'] == '1': 
                        self.ch1_localport_fix.setChecked(True)
                    elif dev_data['LF'] == '0': 
                        self.ch1_localport_fix.setChecked(False)
                # NTP server
                if 'N0' in dev_data:
                    self.ntp_server0.setText(dev_data['N0'])
                if 'N1' in dev_data:
                    self.ntp_server1.setText(dev_data['N1'])
                if 'N2' in dev_data:
                    self.ntp_server2.setText(dev_data['N2'])
                # cloud options
                if 'CE' in dev_data:    
                    if dev_data['CE'] == '0': 
                        self.cloud_enable.setChecked(False)
                    elif dev_data['CE'] == '1': 
                        self.cloud_enable.setChecked(True)
                # setting password enable
                if 'AE' in dev_data:
                    if dev_data['AE'] == '1': 
                        self.enable_setting_pw.setChecked(True)
                        # setting password
                        if 'AP' in dev_data:
                            # print('<AP> parameter:', dev_data['AP'], type(dev_data['AP']), isinstance(dev_data['AP'], type('\xd3M4\xd3M4')))
                            # print('<AP> parameter b64decode:', base64.b64decode(dev_data['AP'].encode('utf-8')))
                            # TODO: base64로 인코딩된 string인지 체크
                            try:
                                self.curr_setting_pw = base64.b64decode(dev_data['AP'].encode('utf-8')).decode()
                            except Exception as e:
                                print('[ERROR] main_gui fill_devinfo() AE command: %r' % e)
                            self.setting_pw.setText(self.curr_setting_pw)
                    elif dev_data['AE'] == '0': 
                        self.enable_setting_pw.setChecked(False)
                        
                # modbud monitoring
                if 'CM' in dev_data:
                    self.modbus_monitor_config.setCurrentIndex(int(dev_data['CM']))
                    if dev_data['CM'] == '0':
                        pass
                    elif dev_data['CM'] == '1':
                        if 'C0' in dev_data: self.monitor_ch1_id.setText(dev_data['C0'])
                    elif dev_data['CM'] == '2':
                        if 'C0' in dev_data: self.monitor_ch1_id.setText(dev_data['C0'])
                        if 'C1' in dev_data: self.monitor_ch2_id.setText(dev_data['C1'])
                    elif dev_data['CM'] == '3':
                        if 'C0' in dev_data: self.monitor_ch1_id.setText(dev_data['C0'])
                        if 'C1' in dev_data: self.monitor_ch2_id.setText(dev_data['C1'])
                        if 'C2' in dev_data: self.monitor_ch3_id.setText(dev_data['C2'])
                    elif dev_data['CM'] == '4':
                        if 'C0' in dev_data: self.monitor_ch1_id.setText(dev_data['C0'])
                        if 'C1' in dev_data: self.monitor_ch2_id.setText(dev_data['C1'])
                        if 'C2' in dev_data: self.monitor_ch3_id.setText(dev_data['C2'])
                        if 'C3' in dev_data: self.monitor_ch4_id.setText(dev_data['C3'])
                
                if 'UP' in dev_data:
                    try:
                        value = self.uptime_value(int(dev_data['UP'])) 
                        # uptime = time.strftime('%DA%H:%M:%S', time.gmtime(second)
                        # print('## uptime value:', dev_data['UP'], value)
                        self.device_uptime.display(value)
                    except Exception as e:
                        print('[ERROR] fill_devinfo() UP cmd', e)

            self.object_config()
        except Exception as e:
            print('[ERROR] fill_devinfo(): %r' % e)
            self.msg_error('Get device information error %r' % e)

    def uptime_value(self, second):
        try: 
            day = second / (3600*24)
            rem = second % (3600*24)
            hour = rem / 3600
            rem = rem % 3600
            mins = rem / 60
            secs = rem % 60

            if day > 1:
                val = '%3dd %02d:%02d:%02d' % (day, hour, mins, secs)
            else:
                val = '%02d:%02d:%02d' % (hour, mins, secs)
        except Exception as e:
            print('[ERROR] get_uptime()', e)
        return val

    def msg_error(self, error):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setFont(self.midfont)
        msgbox.setWindowTitle("Unexcepted error")
        text = "<div style=text-align:center>Unexcepted error occurred." \
                + "<br>Please report the issue with detail message." \
                + "<br><a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'>Github Issue page</a></div>"
        msgbox.setText(text)
        # detail info
        msgbox.setDetailedText(str(error))
        msgbox.exec_() 
    
    def getinfo_for_setting(self, row_index):
        self.rcv_data[row_index] = self.set_reponse[0]
        # print('getinfo_for_setting set_response', self.set_reponse)

    # get each object's value for setting
    def get_object_value(self):
        self.selected_devinfo()

        setcmd = {}

        try:
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
            if self.serial_debug.currentIndex() == 2: 
                setcmd['DG'] = '4'
            else: 
                setcmd['DG'] = str(self.serial_debug.currentIndex())

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
            if 'WIZ107' in self.curr_dev or 'WIZ108' in self.curr_dev:
                pass
            else:
                if self.status_phy.isChecked(): 
                    upper_val = '0'
                elif self.status_dtr.isChecked(): 
                    upper_val = '1'
                if self.status_tcpst.isChecked(): 
                    lower_val = '0'
                elif self.status_dsr.isChecked(): 
                    lower_val = '1'
                setcmd['SC'] = upper_val + lower_val

            if 'WIZ750' in self.curr_dev: 
                if version_compare('1.2.0', self.curr_ver) <= 0:
                    setcmd['TR'] = self.tcp_timeout.text()
                else:
                    pass
            elif 'WIZ752' in self.curr_dev:
                pass

            # Expansion GPIO
            if self.curr_st == 'BOOT':
                pass
            else:
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
            if self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
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

            # for WIZ2000 device server
            if 'WIZ2000' in self.curr_dev:
                # modbus setting (ch1)
                if self.modbus_s2e.isChecked(): setcmd['MB'] = '0'
                elif self.modbus_rtu_tcp.isChecked(): setcmd['MB'] = '1'
                elif self.modbus_asci_tcp.isChecked(): setcmd['MB'] = '2'
                # modbus setting (ch2)
                # if 'MM' in dev_data:
                #     pass
                # tls 1.2 option
                if not self.tls_enable.isChecked():
                    setcmd['SE'] = '0'
                elif self.tls_enable.isChecked():
                    setcmd['SE'] = '1'            
                # setting pw
                if self.enable_setting_pw.isChecked():
                    setcmd['AE'] = '1'
                    if self.setting_pw.text():
                        try: 
                            print('new Set PW', self.setting_pw.text(), base64.b64encode(self.setting_pw.text().encode('utf-8')).decode())
                            setcmd['AP'] = base64.b64encode(self.setting_pw.text().encode('utf-8')).decode()
                        except Exception as e:
                            print('[ERROR] main_gui get_object_value() AE/AP command: %r' % e)
                    else:
                        print('Setting pw enabled, but empty')
                # device alias config
                setcmd['AL'] = self.dev_alias.text()
                setcmd['GR'] = self.dev_group.text()
                # tcp auto msg
                setcmd['AM'] = str(self.tcp_success_msg.currentIndex())
                # local port fix
                if not self.ch1_localport_fix.isChecked():
                    setcmd['LF'] = '0'
                elif self.ch1_localport_fix.isChecked():
                    setcmd['LF'] = '1'

                # cloud monitor option
                if not self.cloud_enable.isChecked():
                    setcmd['CE'] = '0'
                elif self.cloud_enable.isChecked():
                    setcmd['CE'] = '1'
                    # ntp server
                    setcmd['N0'] = self.ntp_server0.text()
                    setcmd['N1'] = self.ntp_server1.text()
                    setcmd['N2'] = self.ntp_server2.text()
                    
                    # modbus monitoring config
                    setcmd['CM'] = str(self.modbus_monitor_config.currentIndex())
                    if self.modbus_monitor_config.currentIndex() == 0:
                        pass
                    elif self.modbus_monitor_config.currentIndex() == 1:
                        setcmd['C0'] = str(self.monitor_ch1_id.text())
                    elif self.modbus_monitor_config.currentIndex() == 2:
                        setcmd['C0'] = str(self.monitor_ch1_id.text())
                        setcmd['C1'] = str(self.monitor_ch2_id.text())
                    elif self.modbus_monitor_config.currentIndex() == 3:
                        setcmd['C0'] = str(self.monitor_ch1_id.text())
                        setcmd['C1'] = str(self.monitor_ch2_id.text())
                        setcmd['C2'] = str(self.monitor_ch3_id.text())
                    elif self.modbus_monitor_config.currentIndex() == 4:
                        setcmd['C0'] = str(self.monitor_ch1_id.text())
                        setcmd['C1'] = str(self.monitor_ch2_id.text())
                        setcmd['C2'] = str(self.monitor_ch3_id.text())
                        setcmd['C3'] = str(self.monitor_ch4_id.text())
        except Exception as e:
            print('[ERROR] get_object_value(): %r' % e)

        # print('setcmd:', setcmd)
        return setcmd

    # copy current cert to clipboard
    # def btn_cert_copy_clipboard_clicked(self):
    #     cert = self.certificate_detail.toPlainText()
    #     try:
    #         clip = Tk()
    #         clip.withdraw()
    #         clip.clipboard_clear()
    #         clip.clipboard_append(cert)
    #         clip.update()
    #         clip.destroy()
    #     except Exception as e:
    #         print('[ERROR] btn_cert_copy_clipboard_clicked(): %r' % e)

    def get_certificate_from_device(self):
        pass
    
    def btn_cert_update_clicked(self):
        self.cert_update_over_tcp()
        # if self.cert_tcp_client.isChecked():
        #     self.cert_update_over_tcp()
        # elif self.cert_cloud.isChecked():
        #     pass

    def cert_update_over_tcp(self):
        print('cert_update_over_tcp()')
        if self.unicast_ip.isChecked() and self.isConnected:
            self.input_setting_pw('update_cert')
        else:
            self.update_cert_net_check()

    def update_cert_net_check(self):
        print('update_cert_net_check()')
        response = self.net_check_ping(self.localip_addr)
        if response == 0:
            self.input_setting_pw('update_cert')
        else:
            self.statusbar.showMessage(' Certificate update warning.')
            self.msg_upload_warning(self.localip_addr)

    # def update_device_cert(self):
    #     print('update_device_cert()')
    #     self.selected_devinfo()
    #     mac_addr = self.curr_mac

    #     if len(self.searchcode_input.text()) == 0:
    #         self.code = " "
    #     else:
    #         self.code = self.searchcode_input.text()

    #     # certificate channel type
    #     cert = self.certificate_detail.toPlainText()
    #     if self.cert_tcp_client.isChecked():
    #         mode_cmd = 'TC'
    #     elif self.cert_cloud.isChecked():
    #         mode_cmd = 'WC'

    #     # Certificate update
    #     try: 
    #         if self.broadcast.isChecked():
    #             self.t_certup = CertUploadThread(self.conf_sock, mac_addr, self.code, self.encoded_setting_pw, cert, None, None, self.curr_dev, mode_cmd)
    #         elif self.unicast_ip.isChecked():
    #             ip_addr = self.search_ipaddr.text()
    #             port = int(self.search_port.text())
    #             self.t_certup = CertUploadThread(self.conf_sock, mac_addr, self.code, self.encoded_setting_pw, cert, ip_addr, port, self.curr_dev, mode_cmd)
    #         self.t_certup.uploading_size.connect(self.pgbar.setValue)
    #         self.t_certup.upload_result.connect(self.update_result)
    #         self.t_certup.error_flag.connect(self.update_error)
    #         try:
    #             self.t_certup.start()
    #         except Exception as e:
    #             print('update_device_cert() thread start error', e)
    #             self.update_result(-1)
    #     except Exception as e:
    #         print('update_device_cert() error', e)

    # def get_certificate_from_server(self):
    #     self.clear_certificate()
    #     # ?: need host address verify or check if host has SSL certificate
    #     try: 
    #         url = self.cert_server.text()
    #         addr = urlsplit(url).hostname
    #         port = 443
    #     except Exception as e:
    #         print('[ERROR] get_certificate_from_server() get addr', e)

    #     try:
    #         # TODO: CHECK ssl_version
    #         cert = ssl.get_server_certificate((addr, port))
    #         self.certificate_detail.setText(cert)
    #         # certificate size
    #         self.cert_size.setText(str(len(cert)))
    #         self.statusbar.showMessage("")

    #         # TODO: 다운받은 certificate를 디바이스로 전송
    #         # self.msg_certificate_success(file_name)

    #     except Exception as e:
    #         self.certificate_detail.setText('Fail to get certificate from server.\nPlease check the address')
    #         self.statusbar.showMessage(' Warning: fail to get certificate from server.')
    #         print('[ERROR] get_certificate_from_server():', e)

    def clear_certificate(self):
        self.certificate_detail.setText("")
        self.cert_size.setText("")

    def dialog_save_certificate(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Certificate","server.crt","Certificate Files (*.crt);;All Files (*)")

        if fname:
            fileName = fname
            print(fileName)
            self.save_certificate(fileName)

            # QFileinfo
            self.saved_path = QFileInfo(fileName).path()
            print('===> path:', self.saved_path)

    def save_certificate(self, file_name):
        # file_name = '%s.CA' % self.cert_server.text()
        f = open(file_name, 'w')
        text = self.certificate_detail.toPlainText()
        f.write(text)
        f.close()
    
    def dialog_load_certificate(self):
        if self.saved_path is None:
            fname, _ = QFileDialog.getOpenFileName(self, "Load Certificate", "", "Certificate Files (*.crt);;All Files (*)")
        else:
            fname, _ = QFileDialog.getOpenFileName(self, "Load Certificate",  self.saved_path, "Certificate Files (*.crt);;All Files (*)")
        
        if fname:
            fileName = fname
            print(fileName)
            self.load_certificate(fileName)

    # read certificate from file
    def load_certificate(self, file_name):
        try:
            f = open(file_name, 'r')
            cert = f.read()
            print('load_certificate()', cert)
            self.certificate_detail.setText(cert)
            self.cert_size.setText(str(len(cert)))
        except Exception as e:
            print('load_certificate()', e)
        
        f.close()

    #? encode setting password
    def encode_setting_pw(self, setpw, mode):
        print('encode_setting_pw', setpw, mode)
        try:
            if not setpw:
                self.use_setting_pw = False
                self.encoded_setting_pw = ''
            else:
                self.use_setting_pw = True
                self.encoded_setting_pw = base64.b64encode(setpw.encode('utf-8'))
                print('setpw_base64', self.encoded_setting_pw)

            # TODO: mode 판별 기준 재정립
            if mode == 'setting':
                self.do_setting()
            elif mode == 'reset':
                self.do_reset()
            elif mode == 'upload':
                # do firmware update
                self.firmware_update(self.fw_filename, self.fw_filesize)
            elif mode == 'factory_setting':
                self.msg_factory_setting()
            elif mode == 'factory_firmware':
                self.msg_factory_firmware()
            # certificate update
            elif mode == 'update_cert':
                # self.update_device_cert()
                pass
        except Exception as e:
            print('[ERROR] encode_setting_pw(): %r' % e)

    # from device?
    def check_setting_pw(self):
        pass

    def do_setting(self):
        self.disable_object()

        self.set_reponse = None

        self.sock_close()

        if len(self.list_device.selectedItems()) == 0:
            # print('Device is not selected')
            self.msg_dev_not_selected()
        else:
            self.statusbar.showMessage(' Setting device...')
            # matching set command
            setcmd = self.get_object_value()
            # self.selected_devinfo()

            if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev:
                print('One port dev setting')
                # Parameter validity check 
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
                print('Two port dev setting')
                # Parameter validity check 
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz752cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif 'WIZ2000' in self.curr_dev:
                print('WIZ2000 device setting...')
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz2000cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('WIZ2000: Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif 'W7500_S2E' in self.curr_dev or 'W7500P_S2E':
                print('W7500(P)-S2E setting...')
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        print('Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            else:
                invalid_flag = -1
                print('The device is not supported')

            # print('invalid flag: %d' % invalid_flag)
            if invalid_flag > 0:
                pass
            elif invalid_flag == 0:
                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()
                
                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, self.code, self.encoded_setting_pw, 
                            list(setcmd.keys()), list(setcmd.values()), self.curr_dev, self.curr_ver)
                # print('do_setting() cmdlist: ', cmd_list)

                # socket config
                self.socket_config() 

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
                else:
                    self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
                self.wizmsghandler.set_result.connect(self.get_setting_result)
                self.wizmsghandler.start()

    def get_setting_result(self, resp_len):
        set_result = {}

        if resp_len > 100:
            self.statusbar.showMessage(' Set device complete!')

            # complete pop-up
            self.msg_set_success()
            
            if self.isConnected and self.unicast_ip.isChecked():
                print('close socket')
                self.conf_sock.shutdown()

            # get setting result
            self.set_reponse = self.wizmsghandler.rcv_list[0]
            
            cmdsets = self.set_reponse.splitlines()
            for i in range(len(cmdsets)):
                if cmdsets[i][:2] == b'MA':
                    pass
                else:
                    try:
                        cmd = cmdsets[i][:2].decode()
                        param = cmdsets[i][2:].decode()
                    except Exception as e:
                        print('[ERROR] main_gui get_setting_result(): %r' % e)
                    set_result[cmd] = param

            try:
                clicked_mac = self.list_device.selectedItems()[0].text()
                self.dev_profile[clicked_mac] = set_result

                self.fill_devinfo(clicked_mac)
            except Exception as e:
                print('get_setting_result() error:', e)
                

            self.dev_clicked()
        elif resp_len == -1:
            print('Setting: no response from device.')
            self.statusbar.showMessage(' Setting: no response from device.')
            self.msg_set_error()
        elif resp_len == -3:
            print('Setting: wrong password')
            self.statusbar.showMessage(' Setting: wrong password.')
            self.msg_setting_pw_error()
        elif resp_len < 50:
            print('Warning: setting is did not well.')
            self.statusbar.showMessage(' Warning: setting is did not well.')
            self.msg_set_warning()
        
        self.object_config()

    def selected_devinfo(self):
        # 선택된 장치 정보 get
        for currentItem in self.list_device.selectedItems():
            if currentItem.column() == 0:
                self.curr_mac = currentItem.text()
                self.curr_ver = self.dev_data[self.curr_mac][1]
                self.curr_st = self.dev_data[self.curr_mac][2]
                # print('current device:', self.curr_mac, self.curr_ver, self.curr_st)
            elif currentItem.column() == 1:
                self.curr_dev = currentItem.text()
                # print('current dev name:', self.curr_dev)
            self.statusbar.showMessage(' Current device [%s : %s], %s' % (self.curr_mac, self.curr_dev, self.curr_ver))

    def update_result(self, result):
        if result < 0:
            # self.statusbar.showMessage(' Firmware update failed.')
            self.msg_upload_failed()
        elif result > 0:
            self.statusbar.showMessage(' Firmware update complete!')
            print('FW Update OK')
            self.pgbar.setValue(8)
            self.msg_upload_success()
        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        self.pgbar.hide()

    def update_error(self, error):
        try:
            if self.t_fwup.isRunning():
                self.t_fwup.terminate()
            if self.t_certup.isRunning():
                self.t_certup.terminate()
        except Exception as e:
            print('update_error() error', e)

        if error == -1:
            self.statusbar.showMessage(' Firmware update failed. No response from device.')
        elif error == -2:
            self.statusbar.showMessage(' Firmware update: Nework connection failed.')
            self.msg_connection_failed()
        elif error == -3:
            self.statusbar.showMessage(' Firmware update error.')
        # self.msg_upload_failed()

    # 'FW': firmware upload
    def firmware_update(self, filename, filesize):
        self.sock_close()

        self.pgbar.setFormat('Uploading..')
        # self.pgbar.setRange(0, filesize)
        self.pgbar.setValue(0)
        self.pgbar.setRange(0, 8)
        self.pgbar.show()

        self.selected_devinfo()
        self.statusbar.showMessage(' Firmware update started. Please wait...')
        mac_addr = self.curr_mac
        print('firmware_update %s, %s' % (mac_addr, filename))
        self.socket_config()

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        # WIZ2000 not use 'AB' command
        # FW update
        if self.broadcast.isChecked():
            self.t_fwup = FWUploadThread(self.conf_sock, mac_addr, self.code, self.encoded_setting_pw, filename, filesize, None, None, self.curr_dev)
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            self.t_fwup = FWUploadThread(self.conf_sock, mac_addr, self.code, self.encoded_setting_pw, filename, filesize, ip_addr, port, self.curr_dev)
        self.t_fwup.uploading_size.connect(self.pgbar.setValue)
        self.t_fwup.upload_result.connect(self.update_result)
        self.t_fwup.error_flag.connect(self.update_error)
        try:
            self.t_fwup.start()
        except Exception as e:
            print('fw uplooad error', e)
            self.update_result(-1)  

    def firmware_file_open(self):    
        fname, _ = QFileDialog.getOpenFileName(self, 'Firmware file open', '', 'Binary Files (*.bin);;All Files (*)')

        if fname:
            self.fw_filename = fname
            # # get path
            # path = self.fw_filename.split('/')
            # dirpath = ''
            # for i in range(len(path) - 1):
            #     dirpath += (path[i] + '/')
            # # print('dirpath:', dirpath)
            # print(fw_filename)

            # get file size
            self.fd = open(self.fw_filename, "rb")
            self.data = self.fd.read(-1)
            
            if 'WIZ107' in self.curr_dev or 'WIZ108' in self.curr_dev:
                # for support WIZ107SR & WIZ108SR 
                self.fw_filesize = 51 * 1024
            else:
                self.fw_filesize = len(self.data)
            
            print('firmware_file_open: filesize: ', self.fw_filesize)
            
            self.fd.close()
            # upload start
            if 'WIZ2000' in self.curr_dev:
                self.input_setting_pw('upload')
            else:
                self.firmware_update(self.fw_filename, self.fw_filesize)

    def net_check_ping(self, dst_ip):
        self.statusbar.showMessage(' Checking the network...')
        # serverip = self.localip_addr
        serverip = dst_ip
        # do_ping = subprocess.Popen("ping " + ("-n 1 " if sys.platform.lower()=="win32" else "-c 1 ") + serverip, 
        do_ping = subprocess.Popen("ping " + ("-n 1 " if "win" in sys.platform.lower() else "-c 1 ") + serverip, 
                                    stdout=None, stderr=None, shell=True)
        ping_response = do_ping.wait()
        print('ping response', ping_response)
        return ping_response

    def upload_net_check(self):
        response = self.net_check_ping(self.localip_addr)
        if response == 0:
            self.statusbar.showMessage(' Firmware update: Select App boot Firmware file. (.bin)')
            self.firmware_file_open()
        else:
            self.statusbar.showMessage(' Firmware update warning!')
            self.msg_upload_warning(self.localip_addr)

    def update_btn_clicked(self):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.msg_dev_not_selected()
        else:
            if self.unicast_ip.isChecked() and self.isConnected:
                self.firmware_file_open()
            else:
                self.upload_net_check()

    def reset_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(' Reset complete.')
            self.msg_reset_seccess()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(' Reset/Factory failed: no response from device.')

        self.object_config()

    def factory_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(' Factory reset complete.')
            self.msg_factory_seccess()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(' Reset/Factory failed: no response from device.')
        
        self.object_config()
    
    def do_reset(self):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.msg_dev_not_selected()
        else:
            self.sock_close()

            self.selected_devinfo()
            mac_addr = self.curr_mac
            
            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()

            cmd_list = self.wizmakecmd.reset(mac_addr, self.code, self.encoded_setting_pw, self.curr_dev)
            print('Reset: %s' % cmd_list)

            self.socket_config() 

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            self.wizmsghandler.set_result.connect(self.reset_result)
            self.wizmsghandler.start()

    def do_factory_reset(self, mode):
        if len(self.list_device.selectedItems()) == 0:
            print('Device is not selected')
            self.msg_dev_not_selected()
        else:
            self.sock_close()

            self.statusbar.showMessage(' Factory reset?')
            self.selected_devinfo()
            mac_addr = self.curr_mac

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()
            # WIZ2000: factory reset option
            if mode == 'setting':
                cmd_list = self.wizmakecmd.factory_reset(mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, "")
            elif mode == 'firmware':
                cmd_list = self.wizmakecmd.factory_reset(mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, "0")

            print('Factory: %s' % cmd_list)

            self.socket_config()
            
            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            self.wizmsghandler.set_result.connect(self.factory_result)
            self.wizmsghandler.start()

    # TODO: setting pw check
    def input_setting_pw(self, mode):
        text, okbtn = QInputDialog.getText(self, "Setting password", "Input setting password", QLineEdit.Password, "")
        if okbtn:
            print(text, len(text))
            if self.enable_setting_pw.isChecked():
                if not text:
                    # password를 넣어라
                    print('========== need password')
                else: 
                    self.encode_setting_pw(text, mode)
            else:
                self.encode_setting_pw(text, mode)
    
    # def input_certificate_server(self):
    #     text, okbtn = QInputDialog.getText(self, "Update certificate", "Input the host address", QLineEdit.Normal, "")
    #     if okbtn:
    #         print('input_certificate_server()', text, len(text))
    #         # TODO: certificate update function
    #         self.get_certificate_from_server(text)

    # To set the wait time when no response from the device when searching
    def input_search_wait_time(self):        
        self.search_wait_time, okbtn = QInputDialog.getInt(self, "Set the wating time for search", 
                                        "Input wating time for search:\n(Default: 3 seconds)", self.search_wait_time, 2, 10, 1)
        if okbtn:
            print('input_search_wait_time()', self.search_wait_time)
            self.search_pre_wait_time = self.search_wait_time
        else:
            pass

    def input_retry_search(self):
        inputdlg = QInputDialog(self)
        name = 'Do Search'
        inputdlg.setOkButtonText(name)
        self.retry_search_num, okbtn = inputdlg.getInt(self, "Retry search devices",
                "Search for additional devices,\nand the list of detected devices is maintained.\n\nInput for search retry number(option):", self.retry_search_num, 1, 10, 1)

        if okbtn:
            print('input_retry_search()', self.retry_search_num)
            self.do_search_retry(self.retry_search_num)
        else:
            # self.do_search_retry(1)
            pass


    def about_info(self):
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

    def msg_not_support(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Not supported device")
        msgbox.setTextFormat(Qt.RichText)
        text = "The device is not supported.<br>Please contact us by the link below.<br><br>" \
                "<a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'># Github issue page</a>"
        msgbox.setText(text)
        msgbox.exec_()

    def msg_invalid(self, params):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Invalid parameter")
        msgbox.setText("Invalid parameter.\nPlease check the values.")
        msgbox.setInformativeText(params)
        msgbox.exec_()

        self.object_config()

    def msg_dev_not_selected(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning")
        msgbox.setText("Device is not selected.")
        msgbox.exec_()

    def msg_invalid_response(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Invalid Response")
        msgbox.setText("Did not receive a valid response from the device.\nPlease check if the device is supported device or firmware is the latest version.")
        msgbox.exec_()

    def msg_set_warning(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Setting")
        msgbox.setText("Setting did not well.\nPlease check the device or check the firmware version.")
        msgbox.exec_()

    def msg_set_error(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Setting Failed")
        msgbox.setText("Setting failed.\nNo response from device.")
        msgbox.exec_()

    def msg_setting_pw_error(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Setting Failed")
        msgbox.setText("Setting failed.\nWrong password.")
        msgbox.exec_()

    def msg_set_success(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Setting success", "Device configuration complete!", QMessageBox.Yes)

    def msg_certificate_success(self, filename):
        msgbox = QMessageBox(self)
        text = "Certificate downlaod complete!\n%s" % filename
        msgbox.question(self, "Certificate download success", text, QMessageBox.Yes)

    def msg_upload_warning(self, dst_ip):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: upload/update")
        msgbox.setText("Destination IP is unreachable: %s\nPlease check if the device is in the same subnet with the PC." % dst_ip)
        msgbox.exec_()

    def msg_upload_failed(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setWindowTitle("Error: Firmware upload")
        msgbox.setText("Firmware update failed.\nPlease check the device's status.")
        msgbox.exec_()

    def msg_upload_success(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Firmware upload success", "Firmware update complete!", QMessageBox.Yes)
    
    def msg_connection_failed(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setWindowTitle("Error: Connection failed")
        msgbox.setText("Network connection failed.\nConnection is refused.")
        msgbox.exec_()

    def msg_not_connected(self, dst_ip):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Network")
        msgbox.setText("Destination IP is unreachable: %s\nPlease check the network status." % dst_ip)
        msgbox.exec_()

    def msg_reset(self):
        self.statusbar.showMessage(' Reset device?')
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Reset", "Do you really want to reset the device?", QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.do_reset()

    def msg_reset_seccess(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Reset", "Reset complete!", QMessageBox.Yes)

    def msg_factory_seccess(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Factory Reset", "Factory reset complete!", QMessageBox.Yes)

    def msg_factory_setting(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Factory default settings", 
        "Do you really want to factory reset?\nAll settings will be initialized.", 
            QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.do_factory_reset('setting')

    def msg_factory_firmware(self):
        # factory reset firmware
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Factory default firmware", 
        "Do you really want to factory reset the firmware?\nThe firmware and all settings will be initialized to factory default.", 
            QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.do_factory_reset('firmware')

    def msg_exit(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(self, "Exit", "Do you really close this program?", QMessageBox.Yes | QMessageBox.No)
        if btnReply == QMessageBox.Yes:
            self.close()

    def dialog_save_file(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Configuration","WIZCONF.cfg","Config File (*.cfg);;Text Files (*.txt);;All Files (*)")

        if fname:
            fileName = fname
            print(fileName)
            self.save_configuration(fileName)

            # QFileinfo
            self.saved_path = QFileInfo(fileName).path()
            print('===> path:', self.saved_path)

    def save_configuration(self, filename):
        setcmd = self.get_object_value()
        # print('save_configuration: setcmd', setcmd)
        set_list = list(setcmd.keys())

        f = open(filename, 'w+')
        for cmd in set_list:
            cmdset = '%s%s\n' % (cmd, setcmd.get(cmd))
            f.write(cmdset)
        f.close()

        self.statusbar.showMessage(' Configuration is saved to \'%s\'.' % filename)

    def dialog_load_file(self):
        if self.saved_path is None:
            fname, _ = QFileDialog.getOpenFileName(self, "Load Configuration", "WIZCONF.cfg","Config File (*.cfg);;Text Files (*.txt);;All Files (*)")
        else:
            fname, _ = QFileDialog.getOpenFileName(self, "Load Configuration", self.saved_path, "Config File (*.cfg);;Text Files (*.txt);;All Files (*)")
        
        if fname:
            fileName = fname
            print(fileName)
            self.load_configuration(fileName)

    def load_configuration(self, data_file):
        cmd_list = []
        load_profile = {}
        cmd = ""
        param = ""

        self.selected_devinfo()
        f = open(data_file, 'r')
        for line in f:
            line = re.sub('[\n]', '', line)
            if len(line) > 2:
                cmd_list.append(line.encode())
        print('load_configuration: cmdlist', len(cmd_list), cmd_list)

        try:
            for i in range(0, len(cmd_list)):
                # print('cmd_list', i, cmd_list[i], cmd_list[i][:2], cmd_list[i][2:])
                if cmd_list[i][:2] == b'MA' or len(cmd_list[i]) < 2:
                    pass
                else:
                    cmd = cmd_list[i][:2].decode()
                    param = cmd_list[i][2:].decode()
                    # print('cmd_list', i, cmd_list[i], cmd, param)
                    load_profile[cmd] = param
                # print(load_profile)
        except Exception as e:
            print('[ERROR] main_gui load_configuration(): %r' % e)

        f.close()
        self.fill_devinfo(load_profile)

    def set_btn_icon(self):
        # Set Button icon 
        self.icon_save = QIcon()
        self.icon_save.addPixmap(QPixmap(resource_path('gui/save_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_saveconfig.setIcon(self.icon_save)
        self.btn_saveconfig.setIconSize(QSize(40, 40))
        self.btn_saveconfig.setFont(self.midfont)

        self.icon_load = QIcon()
        self.icon_load.addPixmap(QPixmap(resource_path('gui/load_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_loadconfig.setIcon(self.icon_load)
        self.btn_loadconfig.setIconSize(QSize(40, 40))
        self.btn_loadconfig.setFont(self.midfont)

        self.icon_search = QIcon()
        self.icon_search.addPixmap(QPixmap(resource_path('gui/search_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_search.setIcon(self.icon_search)
        self.btn_search.setIconSize(QSize(40, 40))
        self.btn_search.setFont(self.midfont)

        self.icon_setting = QIcon()
        self.icon_setting.addPixmap(QPixmap(resource_path('gui/setting_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_setting.setIcon(self.icon_setting)
        self.btn_setting.setIconSize(QSize(40, 40))
        self.btn_setting.setFont(self.midfont)

        self.icon_upload = QIcon()
        self.icon_upload.addPixmap(QPixmap(resource_path('gui/upload_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_upload.setIcon(self.icon_upload)
        self.btn_upload.setIconSize(QSize(40, 40))
        self.btn_upload.setFont(self.midfont)

        self.icon_reset = QIcon()
        self.icon_reset.addPixmap(QPixmap(resource_path('gui/reset_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_reset.setIcon(self.icon_reset)
        self.btn_reset.setIconSize(QSize(40, 40))
        self.btn_reset.setFont(self.midfont)

        self.icon_factory = QIcon()
        self.icon_factory.addPixmap(QPixmap(resource_path('gui/factory_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_factory.setIcon(self.icon_factory)
        self.btn_factory.setIconSize(QSize(40, 40))
        self.btn_factory.setFont(self.midfont)

        self.icon_exit = QIcon()
        self.icon_exit.addPixmap(QPixmap(resource_path('gui/exit_48.ico')), QIcon.Normal, QIcon.Off)
        self.btn_exit.setIcon(self.icon_exit)
        self.btn_exit.setIconSize(QSize(40, 40))
        self.btn_exit.setFont(self.midfont)

    def font_init(self):
        self.midfont = QFont()
        self.midfont.setPixelSize(12)    # pointsize(9)

        self.smallfont = QFont()
        self.smallfont.setPixelSize(11)

        self.certfont = QFont()
        self.certfont.setPixelSize(10)
        self.certfont.setFamily('Consolas')

    def gui_init(self):
        self.font_init()

        # fix font pixel size 
        self.centralwidget.setFont(self.midfont)
        self.list_device.setFont(self.smallfont)
        for i in range(self.list_device.columnCount()):
            self.list_device.horizontalHeaderItem(i).setFont(self.smallfont)

        self.generalTab.setFont(self.smallfont)
        self.channel_tab.setFont(self.smallfont)
        self.group_searchmethod.setFont(self.smallfont)
        self.input_searchcode.setFont(self.smallfont)
        self.statusbar.setFont(self.smallfont)
        self.menuBar.setFont(self.midfont)
        self.menuFile.setFont(self.midfont)
        self.menuOption.setFont(self.midfont)
        self.menuHelp.setFont(self.midfont)
        self.action_set_wait_time.setFont(self.midfont)
        self.action_retry_search.setFont(self.midfont)
        self.tcp_timeout_label.setFont(self.smallfont)
        self.atmode_desc.setFont(self.smallfont)
        self.searchcode_desc.setFont(self.smallfont)
        
        self.modbus_asci_tcp.setFont(self.smallfont)
        self.modbus_rtu_tcp.setFont(self.smallfont)
        self.modbus_s2e.setFont(self.smallfont)
        self.ch1_reconnection_label.setFont(self.smallfont)
        self.ch2_reconnection_label.setFont(self.smallfont)
        self.gpioa_label.setFont(self.smallfont)
        self.gpiob_label.setFont(self.smallfont)
        self.gpioc_label.setFont(self.smallfont)
        self.gpiod_label.setFont(self.smallfont)

        self.certificate_detail.setFont(self.certfont)
            
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
