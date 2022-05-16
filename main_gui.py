# -*- coding: utf-8 -*-

from binascii import Incomplete
from wizsocket.TCPClient import TCPClient
from WIZMakeCMD import WIZMakeCMD, version_compare, ONE_PORT_DEV, TWO_PORT_DEV, SECURITY_DEVICE
from WIZ2000CMDSET import WIZ2000CMDSET
from WIZ752CMDSET import WIZ752CMDSET
from WIZ750CMDSET import WIZ750CMDSET
from WIZ510SSLCMDSET import WIZ510SSLCMDSET
from WIZUDPSock import WIZUDPSock
from FWUploadThread import FWUploadThread
from WIZMSGHandler import WIZMSGHandler, DataRefresh
from certificatethread import certificatethread
from utils import get_logger

import sys
import time
import re
import os
import subprocess
import base64
import logging
# import ssl

# Additional package
from PyQt5 import QtWidgets, QtCore, QtGui, uic
import ifaddr


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

VERSION = 'V1.4.3.7 Dev'


def resource_path(relative_path):
    # Get absolute path to resource, works for dev and for PyInstaller
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# Load ui files
uic_logger = logging.getLogger('PyQt5.uic')
uic_logger.setLevel(logging.INFO)
main_window = uic.loadUiType(resource_path('gui/wizconfig_gui.ui'))[0]


class WIZWindow(QtWidgets.QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle(f'WIZnet S2E Configuration Tool {VERSION}')

        self.logger = get_logger(self.__class__.__name__, os.path.expanduser('~'), 'wizconfig')
        if 'Dev' in VERSION:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info(f'Start configuration tool (version: {VERSION})')

        # GUI font size init
        self.midfont = None
        self.smallfont = None
        self.btnfont = None

        self.gui_init()

        # Main icon
        self.setWindowIcon(QtGui.QIcon(resource_path('gui/icon.ico')))
        self.set_btn_icon()

        self.wiz750cmdObj = WIZ750CMDSET(1)
        self.wiz752cmdObj = WIZ752CMDSET(1)
        self.wiz2000cmdObj = WIZ2000CMDSET(1)
        self.wiz510sslcmdObj = WIZ510SSLCMDSET(1)
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
        self.curr_setting_pw = ''  # setting pw value

        # Certificate
        self.rootca_filename = None
        self.clientcert_filename = None
        self.privatekey_filename = None

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

        self.localip_addr = None

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

        # Initial UI object
        self.init_ui_object()

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
        self.btn_factory.triggered[QtWidgets.QAction].connect(self.event_factory_option_clicked)

        # configuration save/load button
        self.btn_saveconfig.clicked.connect(self.dialog_save_file)
        self.btn_loadconfig.clicked.connect(self.dialog_load_file)

        # self.btn_upload.clicked.connect(self.update_btn_clicked)
        self.btn_upload.clicked.connect(self.event_upload_clicked)
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
        # self.enable_setting_pw.stateChanged.connect(self.event_setting_pw)
        # self.show_settingpw.stateChanged.connect(self.event_setpw_show)

        # Event: OP mode
        self.ch1_tcpclient.clicked.connect(self.event_opmode)
        self.ch1_tcpserver.clicked.connect(self.event_opmode)
        self.ch1_tcpmixed.clicked.connect(self.event_opmode)
        self.ch1_udp.clicked.connect(self.event_opmode)
        self.ch1_ssl_tcpclient.clicked.connect(self.event_opmode)
        self.ch1_mqttclient.clicked.connect(self.event_opmode)
        self.ch1_mqtts_client.clicked.connect(self.event_opmode)

        self.ch2_tcpclient.clicked.connect(self.event_opmode)
        self.ch2_tcpserver.clicked.connect(self.event_opmode)
        self.ch2_tcpmixed.clicked.connect(self.event_opmode)
        self.ch2_udp.clicked.connect(self.event_opmode)

        # Event: Search method
        self.broadcast.clicked.connect(self.event_search_method)
        self.unicast_ip.clicked.connect(self.event_search_method)
        # self.unicast_mac.clicked.connect(self.event_search_method)

        self.pgbar = QtWidgets.QProgressBar()
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
        self.netconfig_menu.triggered[QtWidgets.QAction].connect(self.net_ifs_selected)
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

        # Manage certificate for WIZ510SSL
        self.btn_load_rootca.clicked.connect(lambda: self.load_cert_btn_clicked('OC'))
        self.btn_load_client_cert.clicked.connect(lambda: self.load_cert_btn_clicked('LC'))
        self.btn_load_privatekey.clicked.connect(lambda: self.load_cert_btn_clicked('PK'))
        # self.btn_load_fwfile.clicked.connect(lambda: self.load_cert_btn_clicked('UP'))

        self.btn_save_rootca.clicked.connect(lambda: self.save_cert_btn_clicked('OC'))
        self.btn_save_client_cert.clicked.connect(lambda: self.save_cert_btn_clicked('LC'))
        self.btn_save_privatekey.clicked.connect(lambda: self.save_cert_btn_clicked('PK'))
        # self.btn_upload_fw.clicked.connect(lambda: self.save_cert_btn_clicked('UP'))

        self.textedit_rootca.textChanged.connect(self.event_rootca_changed)
        self.textedit_client_cert.textChanged.connect(self.event_client_cert_changed)
        self.textedit_privatekey.textChanged.connect(self.event_privatekey_changed)
        # self.textedit_upload_fw.textChanged.connect(self.event_uploadfw_changed)

        self.cert_object_config()

    def init_ui_object(self):
        """
        Initial config based WIZ750SR series
        """
        # Tab information save
        self.userio_tab_text = self.generalTab.tabText(2)
        self.mqtt_tab_text = self.generalTab.tabText(3)
        self.certificate_tab_text = self.generalTab.tabText(4)

        self.ch1_tab_text = self.channel_tab.tabText(1)

        # Initial tab
        self.generalTab.removeTab(5)
        self.generalTab.removeTab(4)
        self.generalTab.removeTab(3)
        self.generalTab.removeTab(2)
        # default: one port device
        self.channel_tab.removeTab(1)

        # for WIZ510SSL (not default)
        self.group_current_bank.hide()
        self.group_dtrdsr.hide()

        # for WIZ5XXSR-RP
        self.groupbox_ch1_timeout.hide()
        # self.groupbox_ch1_timeout.setEnabled(False)

    def init_btn_factory(self):
        # factory_option = ['Factory default settings', 'Factory default firmware']
        self.factory_setting_action = QtWidgets.QAction('Factory default settings', self)
        self.factory_firmware_action = QtWidgets.QAction('Factory default firmware', self)

        self.btn_factory.addAction(self.factory_setting_action)
        self.btn_factory.addAction(self.factory_firmware_action)

    def tab_changed(self):
        """
        When tab changed
        - check user IO tab
        """
        # if 'WIZ750' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if 'WIZ750' in self.curr_dev:
            if self.generalTab.currentIndex() == 2:
                self.logger.debug(f'Start DataRefresh: {self.curr_dev}, currentTab: {self.generalTab.currentIndex()}')
                # Expansion GPIO tab
                self.gpio_check()
                self.get_refresh_time()
            else:
                try:
                    if self.datarefresh is not None:
                        self.logger.debug(f'Stop DataRefresh: {self.curr_dev}, currentTab: {self.generalTab.currentIndex()}')
                        if self.datarefresh.isRunning():
                            self.datarefresh.terminate()
                except Exception as e:
                    self.logger.error(e)

    def net_ifs_selected(self, netifs):
        ifs = netifs.text().split(':')
        selected_ip = ifs[0]
        selected_name = ifs[1]

        self.logger.info('net_ifs_selected() %s: %s' % (selected_ip, selected_name))

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
        self.logger.info(self.net_interface.currentText())
        ifs = self.net_interface.currentText().split(':')
        selected_ip = ifs[0]
        selected_name = ifs[1]

        self.statusbar.showMessage(' Selected eth: %s: %s' % (selected_ip, selected_name))
        self.selected_eth = selected_ip

    # Get network adapter & IP list
    def net_adapter_info(self):
        self.netconfig_menu = QtWidgets.QMenu('Network Interface Config', self)
        self.netconfig_menu.setFont(self.midfont)
        self.menuOption.addMenu(self.netconfig_menu)

        adapters = ifaddr.get_adapters()
        self.net_list = []

        for adapter in adapters:
            self.logger.debug(f"Net Interface: {adapter.nice_name}")
            for ip in adapter.ips:
                if len(ip.ip) > 6:
                    ipv4_addr = ip.ip
                    if ipv4_addr == '127.0.0.1':
                        pass
                    else:
                        net_ifs = ipv4_addr + ':' + adapter.nice_name

                        # -- get network interface list
                        self.net_list.append(adapter.nice_name)
                        netconfig = QtWidgets.QAction(net_ifs, self)
                        self.netconfig_menu.addAction(netconfig)
                        self.net_interface.addItem(net_ifs)
                else:
                    # ipv6_addr = ip.ip
                    pass

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

        # object enable/disable
        self.object_config_for_device()

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
        # self.event_setting_pw()
        # self.event_localport_fix()
        # self.event_cert_changed()

        self.gpio_check()

    # Certificate manager tab events
    def cert_object_config(self):
        self.event_rootca_changed()
        self.event_client_cert_changed()
        self.event_privatekey_changed()
        # self.event_uploadfw_changed()

    def event_rootca_changed(self):
        if (len(self.textedit_rootca.toPlainText()) > 0):
            self.btn_save_rootca.setEnabled(True)
        else:
            self.btn_save_rootca.setEnabled(False)

    def event_client_cert_changed(self):
        if (len(self.textedit_client_cert.toPlainText()) > 0):
            self.btn_save_client_cert.setEnabled(True)
        else:
            self.btn_save_client_cert.setEnabled(False)

    def event_privatekey_changed(self):
        if (len(self.textedit_privatekey.toPlainText()) > 0):
            self.btn_save_privatekey.setEnabled(True)
        else:
            self.btn_save_privatekey.setEnabled(False)

    # Button click events
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
        self.logger.info(option.text())
        opt = option.text()

        if 'settings' in opt:
            self.event_factory_setting()
        elif 'firmware' in opt:
            self.event_factory_firmware()

    def event_upload_clicked(self):
        if self.localip_addr is not None:
            self.update_btn_clicked()
        else:
            self.show_msgbox("Warning", "Local IP information could not be found. Check the Network configuration.", QtWidgets.QMessageBox.Warning)

    def gpio_check(self):
        if 'WIZ5XX' in self.curr_dev:
            gpio_list = ['a', 'b']
        else:
            gpio_list = ['a', 'b', 'c', 'd']

        for name in gpio_list:
            gpio_config = getattr(self, f'gpio{name}_config')
            gpio_set = getattr(self, f'gpio{name}_set')
            if gpio_config.currentIndex() == 1:
                gpio_set.setEnabled(True)
            else:
                gpio_set.setEnabled(False)

    # Object config for some Devices or F/W version
    def object_config_for_device(self):
        if 'WIZ750' in self.curr_dev:
            if version_compare('1.2.0', self.curr_ver) <= 0:
                # setcmd['TR'] = self.tcp_timeout.text()
                self.tcp_timeout.setEnabled(True)
            else:
                self.tcp_timeout.setEnabled(False)

            # 'OP' option
            self.ch1_ssl_tcpclient.setEnabled(False)
            self.ch1_mqttclient.setEnabled(False)
            self.ch1_mqtts_client.setEnabled(False)

        # SC: Status pin option
        if 'WIZ107' in self.curr_dev or 'WIZ108' in self.curr_dev:
            pass
        else:
            if self.curr_dev in SECURITY_DEVICE:
                self.radiobtn_group_s0.hide()
                self.radiobtn_group_s1.hide()
                self.group_dtrdsr.show()
                if 'WIZ5XXSR' in self.curr_dev:
                    self.groupbox_ch1_timeout.show()
                    self.groupbox_ch1_timeout.setEnabled(True)
                else:
                    self.groupbox_ch1_timeout.hide()
                    self.groupbox_ch1_timeout.setEnabled(False)
            else:
                self.radiobtn_group_s0.show()
                self.radiobtn_group_s1.show()
                self.group_dtrdsr.hide()
                self.groupbox_ch1_timeout.hide()

        if self.curr_dev in SECURITY_DEVICE:
            self.tcp_timeout.setEnabled(True)
            self.factory_setting_action.setEnabled(True)
            self.factory_firmware_action.setEnabled(True)
            # 'OP' option
            self.ch1_ssl_tcpclient.setEnabled(True)
            self.ch1_mqttclient.setEnabled(True)
            self.ch1_mqtts_client.setEnabled(True)
            # Current bank (RO)
            self.group_current_bank.show()
            if 'WIZ5XXSR' in self.curr_dev:
                self.group_current_bank.hide()
                # self.combobox_current_bank.setEnabled(True)
            else:
                self.combobox_current_bank.setEnabled(False)
        else:
            self.factory_setting_action.setEnabled(True)
            self.factory_firmware_action.setEnabled(False)
            # 'OP' option
            self.ch1_ssl_tcpclient.setEnabled(False)
            self.ch1_mqttclient.setEnabled(False)
            self.ch1_mqtts_client.setEnabled(False)
            # Current bank (RO)
            self.group_current_bank.hide()

        # op channel#2 option
        self.ch2_ssl_tcpclient.setEnabled(False)
        self.ch2_mqttclient.setEnabled(False)
        self.ch2_mqtts_client.setEnabled(False)

    def general_tab_config(self):
        # General tab ui setup by device
        if self.curr_dev in SECURITY_DEVICE:
            # self.logger.debug(f'general_tab_config() length: {len(self.generalTab)}')
            if len(self.generalTab) < 4:
                # self.generalTab.insertTab(3, self.wiz510ssl_tab, self.wiz510ssl_tab_text)
                self.generalTab.insertTab(3, self.mqtt_tab, self.mqtt_tab_text)
                self.generalTab.insertTab(4, self.certificate_tab, self.certificate_tab_text)

                self.generalTab.setTabEnabled(3, True)
                self.generalTab.setTabEnabled(4, True)
                # self.generalTab.setTabEnabled(5, True)
                # self.group_setting_pw.setEnabled(False)
        else:
            # self.generalTab.removeTab(5)
            self.generalTab.removeTab(4)
            self.generalTab.removeTab(3)

        # User I/O tab
        """
        - WIZ750SR
        - WIZ750SR-100
        - WIZ5XXSR-RP (only use A,B)
        """
        # if 'WIZ750' in self.curr_dev or 'W7500' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if 'WIZ750' in self.curr_dev or 'W7500' in self.curr_dev:
            # ! Check current tab length
            self.logger.debug(f'totalTab: {len(self.generalTab)}, currentTab: {self.generalTab.currentIndex()}')
            # self.generalTab.insertTab(2, self.userio_tab, self.userio_tab_text)
            # self.generalTab.setTabEnabled(2, True)
            if 'WIZ5XXSR' in self.curr_dev:
                # if len(self.generalTab) == 4:
                #     # Basic settings / User I/O / Options / MQTT Options / Certificate manager
                #     self.generalTab.insertTab(2, self.userio_tab, self.userio_tab_text)
                #     self.generalTab.setTabEnabled(2, True)
                # # Use IO A, B only
                # self.frame_gpioc.setEnabled(False)
                # self.frame_gpiod.setEnabled(False)
                pass
            else:
                if len(self.generalTab) == 2:
                    # Basic settings / User I/O / Options
                    self.generalTab.insertTab(2, self.userio_tab, self.userio_tab_text)
                    self.generalTab.setTabEnabled(2, True)
                self.frame_gpioc.setEnabled(True)
                self.frame_gpiod.setEnabled(True)
        else:
            # if 'WIZ510SSL' in self.curr_dev:
            if self.curr_dev in SECURITY_DEVICE:
                if len(self.generalTab) == 5:
                    # Remove userio tab
                    self.generalTab.removeTab(2)
                elif len(self.generalTab) == 4:
                    # Already removed userio tab
                    pass
            # else:
            #     self.generalTab.removeTab(2)

    def channel_tab_config(self):
        # channel tab config
        if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev or self.curr_dev in SECURITY_DEVICE:
            self.channel_tab.removeTab(1)
            self.channel_tab.setTabEnabled(0, True)
        elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
            self.channel_tab.insertTab(1, self.tab_ch1, self.ch1_tab_text)
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, True)

    def event_localport_fix(self):
        if self.ch1_localport_fix.isChecked():
            self.ch1_localport.setEnabled(False)
        else:
            self.ch1_localport.setEnabled(True)

    def event_ip_alloc(self):
        if self.ip_dhcp.isChecked():
            self.localip.setEnabled(False)
            self.subnet.setEnabled(False)
            self.gateway.setEnabled(False)
            self.dns_addr.setEnabled(False)
        else:
            self.localip.setEnabled(True)
            self.subnet.setEnabled(True)
            self.gateway.setEnabled(True)
            self.dns_addr.setEnabled(True)

    def event_keepalive(self):
        if self.ch1_keepalive_enable.isChecked():
            self.ch1_keepalive_initial.setEnabled(True)
            self.ch1_keepalive_retry.setEnabled(True)
        else:
            self.ch1_keepalive_initial.setEnabled(False)
            self.ch1_keepalive_retry.setEnabled(False)

        if self.ch2_keepalive_enable.isChecked():
            self.ch2_keepalive_initial.setEnabled(True)
            self.ch2_keepalive_retry.setEnabled(True)
        else:
            self.ch2_keepalive_initial.setEnabled(False)
            self.ch2_keepalive_retry.setEnabled(False)

    def event_atmode(self):
        if self.at_enable.isChecked():
            self.at_hex1.setEnabled(True)
            self.at_hex2.setEnabled(True)
            self.at_hex3.setEnabled(True)
        else:
            self.at_hex1.setEnabled(False)
            self.at_hex2.setEnabled(False)
            self.at_hex3.setEnabled(False)

    def event_input_idcode(self):
        if self.show_idcodeinput.isChecked():
            self.searchcode_input.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.searchcode_input.setEchoMode(QtWidgets.QLineEdit.Password)

    def event_idcode(self):
        if self.show_idcode.isChecked():
            self.searchcode.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.searchcode.setEchoMode(QtWidgets.QLineEdit.Password)

    def event_passwd(self):
        if self.show_connectpw.isChecked():
            self.connect_pw.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.connect_pw.setEchoMode(QtWidgets.QLineEdit.Password)

    def event_setpw_show(self):
        if self.show_settingpw.isChecked():
            self.lineedit_setting_pw.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.lineedit_setting_pw.setEchoMode(QtWidgets.QLineEdit.Password)

    def event_passwd_enable(self):
        if self.enable_connect_pw.isChecked():
            self.connect_pw.setEnabled(True)
        else:
            self.connect_pw.setEnabled(False)

    def event_opmode(self):
        if self.ch1_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
        elif self.ch1_tcpserver.isChecked():
            self.ch1_remote.setEnabled(False)
        elif self.ch1_tcpmixed.isChecked():
            self.ch1_remote.setEnabled(True)
        elif self.ch1_udp.isChecked():
            self.ch1_remote.setEnabled(True)
        elif self.ch1_ssl_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
        elif self.ch1_mqttclient.isChecked():
            self.ch1_remote.setEnabled(True)
        elif self.ch1_mqtts_client.isChecked():
            self.ch1_remote.setEnabled(True)

        if self.ch2_tcpclient.isChecked():
            self.ch2_remote.setEnabled(True)
        elif self.ch2_tcpserver.isChecked():
            self.ch2_remote.setEnabled(False)
        elif self.ch2_tcpmixed.isChecked():
            self.ch2_remote.setEnabled(True)
        elif self.ch2_udp.isChecked():
            self.ch2_remote.setEnabled(True)

    def event_search_method(self):
        if self.broadcast.isChecked():
            self.search_ipaddr.setEnabled(False)
            self.search_port.setEnabled(False)
        elif self.unicast_ip.isChecked():
            self.search_ipaddr.setEnabled(True)
            self.search_port.setEnabled(True)

    def sock_close(self):
        # 기존 연결 fin
        if self.cli_sock is not None:
            if self.cli_sock.state != SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()

    def connect_over_tcp(self, serverip, port):
        retrynum = 0
        self.cli_sock = TCPClient(2, serverip, port)
        # print('sock state: %r' % (self.cli_sock.state))

        while True:
            if retrynum > 6:
                break
            retrynum += 1

            if self.cli_sock.state == SOCK_CLOSE_STATE:
                self.cli_sock.shutdown()
                try:
                    self.cli_sock.open()
                    if self.cli_sock.state == SOCK_OPEN_STATE:
                        self.logger.info('[%r] is OPEN' % (serverip))
                    time.sleep(0.2)
                except Exception as e:
                    self.logger.error(e)
            elif self.cli_sock.state == SOCK_OPEN_STATE:
                try:
                    self.cli_sock.connect()
                    if self.cli_sock.state == SOCK_CONNECT_STATE:
                        self.logger.info('[%r] is CONNECTED' % (serverip))
                except Exception as e:
                    self.logger.error(e)
            elif self.cli_sock.state == SOCK_CONNECT_STATE:
                break
        if retrynum > 6:
            self.logger.info('Device [%s] TCP connection failed.\r\n' % (serverip))
            return None
        else:
            self.logger.info('Device [%s] TCP connected\r\n' % (serverip))
            return self.cli_sock

    def socket_config(self):
        # Broadcast
        if self.broadcast.isChecked():
            if self.selected_eth is None:
                self.conf_sock = WIZUDPSock(5000, 50001, "")
            else:
                self.conf_sock = WIZUDPSock(5000, 50001, self.selected_eth)
                self.logger.info(self.selected_eth)

            self.conf_sock.open()

        # TCP unicast
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            self.logger.info('unicast: ip: %r, port: %r' % (ip_addr, port))

            # network check
            net_response = self.net_check_ping(ip_addr)

            if net_response == 0:
                self.conf_sock = self.connect_over_tcp(ip_addr, port)

                if self.conf_sock is None:
                    self.isConnected = False
                    self.logger.info('TCP connection failed!: %s' % self.conf_sock)
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

                cmd_list = self.wizmakecmd.get_gpiovalue(mac_addr, self.code, self.curr_dev)
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

        if self.refresh_no.isChecked():
            self.intv_time = 0
        elif self.refresh_1s.isChecked():
            self.intv_time = 1
        elif self.refresh_5s.isChecked():
            self.intv_time = 5
        elif self.refresh_10s.isChecked():
            self.intv_time = 10
        elif self.refresh_30s.isChecked():
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
                # cmdset_list = resp.splitlines()
                cmdset_list = resp.split(b"\r\n")

                try:
                    # Expansion GPIO
                    for i in range(len(cmdset_list)):
                        if num < 2:
                            if b'CA' in cmdset_list[i]:
                                self.gpioa_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CB' in cmdset_list[i]:
                                self.gpiob_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CC' in cmdset_list[i]:
                                self.gpioc_config.setCurrentIndex(int(cmdset_list[i][2:]))
                            if b'CD' in cmdset_list[i]:
                                self.gpiod_config.setCurrentIndex(int(cmdset_list[i][2:]))

                        if b'GA' in cmdset_list[i]:
                            self.gpioa_get.setText(cmdset_list[i][2:].decode())
                        if b'GB' in cmdset_list[i]:
                            self.gpiob_get.setText(cmdset_list[i][2:].decode())
                        if b'GC' in cmdset_list[i]:
                            self.gpioc_get.setText(cmdset_list[i][2:].decode())
                        if b'GD' in cmdset_list[i]:
                            self.gpiod_get.setText(cmdset_list[i][2:].decode())
                except Exception as e:
                    self.logger.error(e)

    def do_search_retry(self, num):
        self.search_retry_flag = True
        # search retry number
        self.search_retrynum = num
        self.logger.info(self.mac_list)

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
                self.logger.info('keep searched list')
                pass
            else:
                # List table initial (clear)
                self.list_device.clear()
                while self.list_device.rowCount() > 0:
                    self.list_device.removeRow(0)

            item_mac = QtWidgets.QTableWidgetItem()
            item_mac.setText("Mac address")
            item_mac.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(0, item_mac)

            item_name = QtWidgets.QTableWidgetItem()
            item_name.setText("Name")
            item_name.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(1, item_name)

            self.socket_config()
            self.logger.debug('search: conf_sock: %s' % self.conf_sock)

            # Search devices
            if self.isConnected or self.broadcast.isChecked():
                self.statusbar.showMessage(' Searching devices...')

                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.presearch("FF:FF:FF:FF:FF:FF", self.code)
                self.logger.debug(cmd_list)

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, 'tcp', OP_SEARCHALL, self.search_pre_wait_time)
                else:
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, 'udp', OP_SEARCHALL, self.search_pre_wait_time)
                self.wizmsghandler.search_result.connect(self.get_search_result)
                self.wizmsghandler.start()

    def processing(self):
        self.btn_search.setEnabled(False)
        # QtCore.QTimer.singleShot(1500, lambda: self.btn_search.setEnabled(True))
        QtCore.QTimer.singleShot(4500, lambda: self.pgbar.hide())

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
                self.logger.debug(dev_info)
                cmd_list = self.wizmakecmd.search(dev_info[0], self.code, dev_info[1], dev_info[2])
                # print(cmd_list)
                th_name = "dev_%s" % dev_info[0]
                if self.unicast_ip.isChecked():
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'tcp',
                                            OP_SEARCHALL, self.search_wait_time_each)
                else:
                    th_name = WIZMSGHandler(self.conf_sock, cmd_list, 'udp',
                                            OP_SEARCHALL, self.search_wait_time_each)
                th_name.searched_data.connect(self.getsearch_each_dev)
                th_name.start()
                th_name.wait()
                self.statusbar.showMessage(' Done.')

    def getsearch_each_dev(self, dev_data):
        # self.logger.info(dev_data)
        profile = {}

        try:
            if dev_data is not None:
                self.eachdev_info.append(dev_data)
                # print('eachdev_info', len(self.eachdev_info), self.eachdev_info)
                for i in range(len(self.eachdev_info)):
                    # cmdsets = self.eachdev_info[i].splitlines()
                    cmdsets = self.eachdev_info[i].split(b"\r\n")

                    for i in range(len(cmdsets)):
                        # print('cmdsets', i, cmdsets[i], cmdsets[i][:2], cmdsets[i][2:])
                        if cmdsets[i][:2] == b'MA':
                            pass
                        else:
                            cmd = cmdsets[i][:2].decode()
                            param = cmdsets[i][2:].decode()
                            profile[cmd] = param

                    # self.logger.info(profile)
                    self.dev_profile[profile['MC']] = profile
                    profile = {}

                    self.all_response = self.eachdev_info

                    # when retry search
                    if self.search_retrynum:
                        self.logger.info(self.search_retrynum)
                        self.search_retrynum = self.search_retrynum - 1
                        self.search_pre()
                    else:
                        pass
            else:
                pass
        except Exception as e:
            self.logger.error(e)
            self.msg_error('[ERROR] getsearch_each_dev(): {}'.format(e))

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
            # self.logger.info(self.searched_devnum)
            self.searched_num.setText(str(self.searched_devnum))
            self.btn_search.setEnabled(True)

            if devnum == 0:
                self.logger.info('No device.')
            else:
                if self.search_retry_flag:
                    self.logger.info('search retry flag on')
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
                        self.list_device.setItem(
                            i, 0, QtWidgets.QTableWidgetItem(self.mac_list[i].decode()))
                        self.list_device.setItem(
                            i, 1, QtWidgets.QTableWidgetItem(self.dev_name[i].decode()))
                except Exception as e:
                    self.logger.error(e)

                # resize for data
                self.list_device.resizeColumnsToContents()
                self.list_device.resizeRowsToContents()

                # row/column resize disable
                self.list_device.horizontalHeader().setSectionResizeMode(2)
                self.list_device.verticalHeader().setSectionResizeMode(2)

            self.statusbar.showMessage(' Find %d devices' % devnum)
            self.get_dev_list()
        else:
            self.logger.error('search error')

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
                    self.searched_dev.append([self.mac_list[i].decode(), self.dev_name[i].decode(
                    ), self.vr_list[i].decode(), self.st_list[i].decode()])
                    self.dev_data[self.mac_list[i].decode()] = [self.dev_name[i].decode(
                    ), self.vr_list[i].decode(), self.st_list[i].decode()]
            except Exception as e:
                self.logger.error(e)

            # print('get_dev_list()', self.searched_dev, self.dev_data)
            self.search_each_dev(self.searched_dev)
        else:
            self.logger.info('There is no device.')

    def dev_clicked(self):
        # dev_info = []
        # clicked_mac = ""
        # if 'WIZ750' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if 'WIZ750' in self.curr_dev:
            if self.generalTab.currentIndex() == 2:
                self.gpio_check()
                self.get_refresh_time()
        # for currentItem in self.list_device.selectedItems():
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
            if (len(self.dev_profile) != self.searched_devnum):
                self.logger.info('[Warning] 검색된 장치의 수와 프로파일된 장치의 수가 다릅니다.')
            self.logger.info('[Warning] retry search')

    def remove_empty_value(self, data):
        # remove empty value
        for k, v in data.items():
            if not any([k, v]):
                del data[k]

    # Check: decode exception handling
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
            if 'UN' in dev_data:
                self.ch1_uart_name.setText(dev_data['UN'])
            # Network - general
            if 'IM' in dev_data:
                if dev_data['IM'] == '0':
                    self.ip_static.setChecked(True)
                elif dev_data['IM'] == '1':
                    self.ip_dhcp.setChecked(True)
            if 'LI' in dev_data:
                self.localip.setText(dev_data['LI'])
                self.localip_addr = dev_data['LI']
            if 'SM' in dev_data:
                self.subnet.setText(dev_data['SM'])
            if 'GW' in dev_data:
                self.gateway.setText(dev_data['GW'])
            if 'DS' in dev_data:
                self.dns_addr.setText(dev_data['DS'])
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
            if 'TE' in dev_data:
                self.at_enable.setChecked(int(dev_data['TE']))
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
                # serial debug (dropbox)
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
                elif dev_data['OP'] == '4':
                    self.ch1_ssl_tcpclient.setChecked(True)
                elif dev_data['OP'] == '5':
                    self.ch1_mqttclient.setChecked(True)
                elif dev_data['OP'] == '6':
                    self.ch1_mqtts_client.setChecked(True)
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
            if 'PR' in dev_data:
                self.ch1_parity.setCurrentIndex(int(dev_data['PR']))
            if 'SB' in dev_data:
                self.ch1_stopbit.setCurrentIndex(int(dev_data['SB']))
            if 'FL' in dev_data:
                self.ch1_flow.setCurrentIndex(int(dev_data['FL']))
            if 'PT' in dev_data:
                self.ch1_pack_time.setText(dev_data['PT'])
            if 'PS' in dev_data:
                self.ch1_pack_size.setText(dev_data['PS'])
            if 'PD' in dev_data:
                self.ch1_pack_char.setText(dev_data['PD'])
            # Inactive timer - channel 1
            if 'IT' in dev_data:
                self.ch1_inact_timer.setText(dev_data['IT'])
            # TCP keep alive - channel 1
            if 'KA' in dev_data:
                if dev_data['KA'] == '0':
                    self.ch1_keepalive_enable.setChecked(False)
                elif dev_data['KA'] == '1':
                    self.ch1_keepalive_enable.setChecked(True)
            if 'KI' in dev_data:
                self.ch1_keepalive_initial.setText(dev_data['KI'])
            if 'KE' in dev_data:
                self.ch1_keepalive_retry.setText(dev_data['KE'])
            # reconnection - channel 1
            if 'RI' in dev_data:
                self.ch1_reconnection.setText(dev_data['RI'])

            # Status pin ( status_phy / status_dtr || status_tcpst / status_dsr )
            if 'SC' in dev_data:
                if dev_data['SC'][0:1] == '0':
                    self.status_phy.setChecked(True)
                    self.checkbox_enable_dtr.setChecked(False)
                elif dev_data['SC'][0:1] == '1':
                    self.status_dtr.setChecked(True)
                    self.checkbox_enable_dtr.setChecked(True)
                if dev_data['SC'][1:2] == '0':
                    self.status_tcpst.setChecked(True)
                    self.checkbox_enable_dsr.setChecked(False)
                elif dev_data['SC'][1:2] == '1':
                    self.status_dsr.setChecked(True)
                    self.checkbox_enable_dsr.setChecked(True)

            # # Channel 2 config (For two Port device)
            if self.curr_dev in TWO_PORT_DEV:
                # device info - channel 2
                if 'QS' in dev_data:
                    self.ch2_status.setText(dev_data['QS'])
                if 'EN' in dev_data:
                    self.ch2_uart_name.setText(dev_data['EN'])
                # Network - channel 2
                if 'QO' in dev_data:
                    if dev_data['QO'] == '0':
                        self.ch2_tcpclient.setChecked(True)
                    elif dev_data['QO'] == '1':
                        self.ch2_tcpserver.setChecked(True)
                    elif dev_data['QO'] == '2':
                        self.ch2_tcpmixed.setChecked(True)
                    elif dev_data['QO'] == '3':
                        self.ch2_udp.setChecked(True)
                if 'QL' in dev_data:
                    self.ch2_localport.setText(dev_data['QL'])
                if 'QH' in dev_data:
                    self.ch2_remoteip.setText(dev_data['QH'])
                if 'QP' in dev_data:
                    self.ch2_remoteport.setText(dev_data['QP'])
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
                if 'EP' in dev_data:
                    self.ch2_parity.setCurrentIndex(int(dev_data['EP']))
                if 'ES' in dev_data:
                    self.ch2_stopbit.setCurrentIndex(int(dev_data['ES']))
                if 'EF' in dev_data:
                    if (len(dev_data['EF']) > 2):
                        pass
                    else:
                        self.ch2_flow.setCurrentIndex(int(dev_data['EF']))
                if 'NT' in dev_data:
                    self.ch2_pack_time.setText(dev_data['NT'])
                if 'NS' in dev_data:
                    self.ch2_pack_size.setText(dev_data['NS'])
                if 'ND' in dev_data:
                    if (len(dev_data['ND']) > 2):
                        pass
                    else:
                        self.ch2_pack_char.setText(dev_data['ND'])
                # Inactive timer - channel 2
                if 'RV' in dev_data:
                    self.ch2_inact_timer.setText(dev_data['RV'])
                # TCP keep alive - channel 2
                if 'RA' in dev_data:
                    if dev_data['RA'] == '0':
                        self.ch2_keepalive_enable.setChecked(False)
                    elif dev_data['RA'] == '1':
                        self.ch2_keepalive_enable.setChecked(True)
                if 'RS' in dev_data:
                    self.ch2_keepalive_initial.setText(dev_data['RS'])
                if 'RE' in dev_data:
                    self.ch2_keepalive_retry.setText(dev_data['RE'])
                # reconnection - channel 2
                if 'RR' in dev_data:
                    self.ch2_reconnection.setText(dev_data['RR'])

            elif self.curr_dev in SECURITY_DEVICE:
                """
                Security device options
                """
                # New options for WIZ510SSL
                # mqtt options
                if 'QU' in dev_data:
                    if dev_data['QU'] == ' ':
                        self.lineedit_mqtt_username.clear()
                    else:
                        self.lineedit_mqtt_username.setText(dev_data['QU'])
                if 'QP' in dev_data:
                    if dev_data['QP'] == ' ':
                        self.lineedit_mqtt_password.clear()
                    else:
                        self.lineedit_mqtt_password.setText(dev_data['QP'])
                if 'QC' in dev_data:
                    if dev_data['QC'] == ' ':
                        self.lineedit_mqtt_clientid.clear()
                    else:
                        self.lineedit_mqtt_clientid.setText(dev_data['QC'])
                if 'QK' in dev_data:
                    if dev_data['QK'] == ' ':
                        self.lineedit_mqtt_keepalive.clear()
                    else:
                        self.lineedit_mqtt_keepalive.setText(dev_data['QK'])
                if 'PU' in dev_data:
                    if dev_data['PU'] == ' ':
                        self.lineedit_mqtt_pubtopic.clear()
                    else:
                        self.lineedit_mqtt_pubtopic.setText(dev_data['PU'])
                if 'U0' in dev_data:
                    if dev_data['U0'] == ' ':
                        self.lineedit_mqtt_subtopic_0.clear()
                    else:
                        self.lineedit_mqtt_subtopic_0.setText(dev_data['U0'])
                if 'U1' in dev_data:
                    if dev_data['U1'] == ' ':
                        self.lineedit_mqtt_subtopic_1.clear()
                    else:
                        self.lineedit_mqtt_subtopic_1.setText(dev_data['U1'])
                if 'U2' in dev_data:
                    if dev_data['U2'] == ' ':
                        self.lineedit_mqtt_subtopic_2.clear()
                    else:
                        self.lineedit_mqtt_subtopic_2.setText(dev_data['U2'])
                if 'QO' in dev_data:
                    self.combobox_mqtt_qos.setCurrentIndex(int(dev_data['QO']))
                # Root CA options
                if 'RC' in dev_data:
                    self.combobox_rootca_option.setCurrentIndex(int(dev_data['RC']))
                # Client cert options
                if 'CE' in dev_data:
                    if dev_data['CE'] == '1':
                        self.checkbox_enable_client_cert.setChecked(True)
                        # client cert password (will be added)
                        # setcmd[''] = self.lineedit_client_cert_pw.text()
                    elif dev_data['CE'] == '0':
                        self.checkbox_enable_client_cert.setChecked(False)
                # Current flash bank (RO)
                if 'BA' in dev_data:
                    self.combobox_current_bank.setCurrentIndex(int(dev_data['BA']))
                # SSL Timeout
                if 'WIZ5XXSR' in self.curr_dev:
                    if 'SO' in dev_data:
                        self.lineedit_ch1_ssl_recv_timeout.setText(dev_data['SO'])

            self.object_config()
        except Exception as e:
            self.logger.error(e)
            self.msg_error('Get device information error {}'.format(e))

    def msg_error(self, error):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Critical)
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
            if self.ip_static.isChecked():
                setcmd['IM'] = '0'
            elif self.ip_dhcp.isChecked():
                setcmd['IM'] = '1'
            setcmd['DS'] = self.dns_addr.text()
            # etc - general
            if self.enable_connect_pw.isChecked():
                setcmd['CP'] = '1'
                setcmd['NP'] = self.connect_pw.text()
            else:
                setcmd['CP'] = '0'
            # command mode (AT mode)
            if self.at_enable.isChecked():
                setcmd['TE'] = '1'
                setcmd['SS'] = self.at_hex1.text() + self.at_hex2.text() + self.at_hex3.text()
            elif self.at_enable.isChecked() is False:
                setcmd['TE'] = '0'

            # search id code: max 8 bytes
            if len(self.searchcode.text()) == 0:
                setcmd['SP'] = ' '
            else:
                setcmd['SP'] = self.searchcode.text()

            # Debug msg
            if self.serial_debug.currentIndex() == 2:
                setcmd['DG'] = '4'
            else:
                setcmd['DG'] = str(self.serial_debug.currentIndex())

            # Network - channel 1
            if self.curr_dev in SECURITY_DEVICE:
                if self.ch1_tcpclient.isChecked():
                    setcmd['OP'] = '0'
                elif self.ch1_tcpserver.isChecked():
                    setcmd['OP'] = '1'
                elif self.ch1_tcpmixed.isChecked():
                    setcmd['OP'] = '2'
                elif self.ch1_udp.isChecked():
                    setcmd['OP'] = '3'
                elif self.ch1_ssl_tcpclient.isChecked():
                    setcmd['OP'] = '4'
                elif self.ch1_mqttclient.isChecked():
                    setcmd['OP'] = '5'
                elif self.ch1_mqtts_client.isChecked():
                    setcmd['OP'] = '6'
            else:
                if self.ch1_tcpclient.isChecked():
                    setcmd['OP'] = '0'
                elif self.ch1_tcpserver.isChecked():
                    setcmd['OP'] = '1'
                elif self.ch1_tcpmixed.isChecked():
                    setcmd['OP'] = '2'
                elif self.ch1_udp.isChecked():
                    setcmd['OP'] = '3'
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
            if self.ch1_keepalive_enable.isChecked():
                setcmd['KA'] = '1'
                setcmd['KI'] = self.ch1_keepalive_initial.text()
                setcmd['KE'] = self.ch1_keepalive_retry.text()
            else:
                setcmd['KA'] = '0'
            setcmd['KI'] = self.ch1_keepalive_initial.text()
            setcmd['KE'] = self.ch1_keepalive_retry.text()
            # reconnection - channel 1
            setcmd['RI'] = self.ch1_reconnection.text()
            # Status pin
            if 'WIZ107' in self.curr_dev or 'WIZ108' in self.curr_dev:
                pass
            else:
                # initial value
                upper_val = '0'
                lower_val = '0'
                if self.curr_dev in SECURITY_DEVICE:
                    if self.checkbox_enable_dtr.isChecked():
                        upper_val = '1'
                    else:
                        upper_val = '0'
                    if self.checkbox_enable_dsr.isChecked():
                        lower_val = '1'
                    else:
                        lower_val = '0'
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
                if self.ch2_tcpclient.isChecked():
                    setcmd['QO'] = '0'
                elif self.ch2_tcpserver.isChecked():
                    setcmd['QO'] = '1'
                elif self.ch2_tcpmixed.isChecked():
                    setcmd['QO'] = '2'
                elif self.ch2_udp.isChecked():
                    setcmd['QO'] = '3'
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
                if self.ch2_keepalive_enable.isChecked():
                    setcmd['RA'] = '1'
                    setcmd['RS'] = self.ch2_keepalive_initial.text()
                    setcmd['RE'] = self.ch2_keepalive_retry.text()
                else:
                    setcmd['RA'] = '0'
                # reconnection - channel 2
                setcmd['RR'] = self.ch2_reconnection.text()
            if self.curr_dev in SECURITY_DEVICE:
                # New options for WIZ510SSL (Security devices)
                # mqtt options
                setcmd['QU'] = self.lineedit_mqtt_username.text()
                setcmd['QP'] = self.lineedit_mqtt_password.text()
                setcmd['QC'] = self.lineedit_mqtt_clientid.text()
                setcmd['QK'] = self.lineedit_mqtt_keepalive.text()
                setcmd['PU'] = self.lineedit_mqtt_pubtopic.text()
                setcmd['U0'] = self.lineedit_mqtt_subtopic_0.text()
                setcmd['U1'] = self.lineedit_mqtt_subtopic_1.text()
                setcmd['U2'] = self.lineedit_mqtt_subtopic_2.text()
                setcmd['QO'] = str(self.combobox_mqtt_qos.currentIndex())
                # Root CA options
                setcmd['RC'] = str(self.combobox_rootca_option.currentIndex())
                # Client cert options
                if self.checkbox_enable_client_cert.isChecked():
                    setcmd['CE'] = '1'
                    # client cert password (will be added)
                    # setcmd[''] = self.lineedit_client_cert_pw.text()
                else:
                    setcmd['CE'] = '0'
                # 2022.05.10 add option
                if 'WIZ5XXSR' in self.curr_dev:
                    # Bank setting (WIZ510SSL's BA command -> RO)
                    setcmd['BA'] = str(self.combobox_current_bank.currentIndex())
                    # Add ssl timeout option
                    setcmd['SO'] = self.lineedit_ch1_ssl_recv_timeout.text()

        except Exception as e:
            self.logger.error(e)

        # print('setcmd:', setcmd)
        return setcmd

    # ? encode setting password
    def encode_setting_pw(self, setpw, mode):
        self.logger.info(setpw, mode)
        try:
            if not setpw:
                self.use_setting_pw = False
                self.encoded_setting_pw = ''
            else:
                self.use_setting_pw = True
                self.encoded_setting_pw = base64.b64encode(setpw.encode('utf-8'))
                self.logger.info(self.encoded_setting_pw)

            # TODO: mode 판별 기준
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
                pass
                # self.update_device_cert()
        except Exception as e:
            self.logger.error(e)

    def do_setting(self):
        self.disable_object()

        self.set_reponse = None

        self.sock_close()

        if len(self.list_device.selectedItems()) == 0:
            # self.logger.info('Device is not selected')
            self.show_msgbox("Warning", "Device is not selected.", QtWidgets.QMessageBox.Warning)
            # self.msg_dev_not_selected()
        else:
            self.statusbar.showMessage(' Setting device...')
            # matching set command
            setcmd = self.get_object_value()
            # self.selected_devinfo()

            if self.curr_dev in ONE_PORT_DEV or 'WIZ750' in self.curr_dev:
                self.logger.info('One port dev setting')
                # Parameter validity check
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        self.logger.warning(
                            'Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif self.curr_dev in TWO_PORT_DEV or 'WIZ752' in self.curr_dev:
                self.logger.info('Two port dev setting')
                # Parameter validity check
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz752cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        self.logger.warning(
                            'Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            elif self.curr_dev in SECURITY_DEVICE:
                self.logger.info('Security device setting...')
                invalid_flag = 0
                # ! temp comment to develop
                # setcmd_cmd = list(setcmd.keys())
                # for i in range(len(setcmd)):
                #     if self.wiz510sslcmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                #         self.logger.info('WIZ510SSL: Invalid parameter: %s %s' %
                #                           (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                #         self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                #         invalid_flag += 1
            elif 'W7500_S2E' in self.curr_dev or 'W7500P_S2E':
                self.logger.info('W7500(P)-S2E setting...')
                invalid_flag = 0
                setcmd_cmd = list(setcmd.keys())
                for i in range(len(setcmd)):
                    if self.wiz750cmdObj.isvalidparameter(setcmd_cmd[i], setcmd.get(setcmd_cmd[i])) is False:
                        self.logger.warning(
                            'Invalid parameter: %s %s' % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i])))
                        self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                        invalid_flag += 1
            else:
                invalid_flag = -1
                self.logger.info('The device not supported')

            # self.logger.info('invalid flag: %d' % invalid_flag)
            if invalid_flag > 0:
                pass
            elif invalid_flag == 0:
                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.setcommand(self.curr_mac, self.code, self.encoded_setting_pw,
                                                      list(setcmd.keys()), list(setcmd.values()), self.curr_dev, self.curr_ver)
                # self.logger.info(cmd_list)

                # socket config
                self.socket_config()

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
                else:
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
                self.wizmsghandler.set_result.connect(self.get_setting_result)
                self.wizmsghandler.start()

    def get_setting_result(self, resp_len):
        set_result = {}

        if resp_len > 100:
            self.statusbar.showMessage(' Set device complete!')

            # complete pop-up
            self.msg_set_success()

            if self.isConnected and self.unicast_ip.isChecked():
                self.logger.info('close socket')
                self.conf_sock.shutdown()

            # get setting result
            self.set_reponse = self.wizmsghandler.rcv_list[0]

            # cmdsets = self.set_reponse.splitlines()
            cmdsets = self.set_reponse.split(b"\r\n")

            for i in range(len(cmdsets)):
                if cmdsets[i][:2] == b'MA':
                    pass
                else:
                    try:
                        cmd = cmdsets[i][:2].decode()
                        param = cmdsets[i][2:].decode()

                        set_result[cmd] = param
                    except Exception as e:
                        self.logger.error(e)

            try:
                clicked_mac = self.list_device.selectedItems()[0].text()
                self.dev_profile[clicked_mac] = set_result
            except Exception as e:
                self.logger.error(e)

            self.dev_clicked()
        elif resp_len == -1:
            self.logger.warning('Setting: no response from device.')
            self.statusbar.showMessage(' Setting: no response from device.')
            self.msg_set_error()
        elif resp_len == -3:
            self.logger.warning('Setting: wrong password')
            self.statusbar.showMessage(' Setting: wrong password.')
            self.msg_setting_pw_error()
        elif resp_len < 50:
            self.logger.warning('Warning: setting is did not well.')
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
            self.statusbar.showMessage(' Current device [%s : %s], %s' % (
                self.curr_mac, self.curr_dev, self.curr_ver))

    def update_result(self, result):
        if result < 0:
            text = "Firmware update failed.\n"
            if result == -1:
                text += "Please check the device's status."
            elif result == -2:
                text += "No response from device."
            # self.show_msgbox("Error", text, QtWidgets.QMessageBox.Critical)
        elif result > 0:
            self.statusbar.showMessage(' Firmware update complete!')
            self.logger.info('FW Update OK')
            self.pgbar.setValue(8)
            self.msg_upload_success()
        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        self.pgbar.hide()

    def update_error(self, error):
        self.logger.error(f'Firmware update error: {error}')

        text = ""
        if error == -1:
            text = ' Firmware update failed. No response from device.'
            self.statusbar.showMessage(text)
            self.show_msgbox("Error", text, QtWidgets.QMessageBox.Critical)
            # self.msg_upload_failed()
        elif error == -2:
            text = ' Firmware update: Network connection failed.'
            self.statusbar.showMessage(text)
            self.msg_connection_failed()
        elif error == -3:
            text = ' Firmware update error.'
            self.statusbar.showMessage(text)
        self.logger.error(text)

        try:
            if self.t_fwup.isRunning():
                self.t_fwup.terminate()
        except Exception as e:
            self.logger.error(e)

    def cert_result(self, result):
        if result < 0:
            self.show_msgbox(
                "Error",
                "Certificate update failed.\nPlease check the device's status.",
                QtWidgets.QMessageBox.Critical)
        elif result > 0:
            self.statusbar.showMessage(' Certificate update complete!')
            self.logger.info('Certificate Update OK')
            self.pgbar.setValue(8)
            # self.msg_upload_success()
            self.show_msgbox_info("Upload complete", "Certificate update complete!")
        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        self.pgbar.hide()

    def cert_error(self, error):
        try:
            if self.th_cert.isRunning():
                self.th_cert.terminate()
        except Exception as e:
            self.logger.error(e)

        if error == -1:
            self.statusbar.showMessage(' Certificate update failed. No response from device.')
        elif error == -2:
            self.statusbar.showMessage(' Certificate update: Nework connection failed.')
            self.msg_connection_failed()
        elif error == -3:
            self.statusbar.showMessage(' Certificate update error.')

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
        self.logger.info('firmware_update %s, %s' % (mac_addr, filename))
        self.socket_config()

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        # Firmware update
        if self.broadcast.isChecked():
            self.t_fwup = FWUploadThread(self.conf_sock, mac_addr, self.code,
                                         self.encoded_setting_pw, filename, filesize, None, None, self.curr_dev)
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            self.t_fwup = FWUploadThread(self.conf_sock, mac_addr, self.code,
                                         self.encoded_setting_pw, filename, filesize, ip_addr, port, self.curr_dev)
        self.t_fwup.uploading_size.connect(self.pgbar.setValue)
        self.t_fwup.upload_result.connect(self.update_result)
        self.t_fwup.error_flag.connect(self.update_error)
        try:
            self.t_fwup.start()
        except Exception as e:
            self.logger.error(e)
            self.update_result(-1)

    def firmware_file_open(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Firmware file open', '', 'Binary Files (*.bin);;All Files (*)')

        if fname:
            self.fw_filename = fname

            # get file size
            with open(self.fw_filename, "rb") as fd:
                self.data = fd.read(-1)

                if 'WIZ107' in self.curr_dev or 'WIZ108' in self.curr_dev:
                    # for support WIZ107SR & WIZ108SR
                    self.fw_filesize = 51 * 1024
                else:
                    self.fw_filesize = len(self.data)

                self.logger.info(self.fw_filesize)

            if self.curr_dev in SECURITY_DEVICE:
                self.logger.info('SECURITY_DEVICE update')
                if 'WIZ5XXSR' in self.curr_dev:
                    self.logger.info('WIZ5XXSR update')
                    self.firmware_update(self.fw_filename, self.fw_filesize)
                else:
                    # Get current bank number
                    doc = QtGui.QTextDocument()
                    doc.setHtml(str(self.combobox_current_bank.currentIndex()))
                    bankval = doc.toPlainText()

                    msgbox = QtWidgets.QMessageBox(self)
                    msgbox.setTextFormat(QtCore.Qt.RichText)
                    text = f"- Current bank: {bankval}\n- Selected file: {self.fw_filename.split('/')[-1]}\n\nThe bank number must match with current device bank number.\nDo you want to update now?"
                    btnReply = msgbox.question(
                        self, "Firmware upload - Check the Bank number", text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                    if btnReply == QtWidgets.QMessageBox.Yes:
                        self.firmware_update(self.fw_filename, self.fw_filesize)
                    else:
                        pass
            else:
                # upload start
                self.firmware_update(self.fw_filename, self.fw_filesize)

    def net_check_ping(self, dst_ip):
        self.statusbar.showMessage(' Checking the network...')
        # serverip = self.localip_addr
        serverip = dst_ip
        # do_ping = subprocess.Popen("ping " + ("-n 1 " if sys.platform.lower()=="win32" else "-c 1 ") + serverip,
        do_ping = subprocess.Popen("ping " + ("-n 1 " if "win" in sys.platform.lower() else "-c 1 ") + serverip,
                                   stdout=None, stderr=None, shell=True)
        ping_response = do_ping.wait()
        self.logger.info(ping_response)
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
            self.logger.info('Device is not selected')
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QtWidgets.QMessageBox.Warning)
        else:
            if self.unicast_ip.isChecked() and self.isConnected:
                self.firmware_file_open()
            else:
                self.upload_net_check()

    def reset_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(' Reset complete.')
            self.msg_reset_success()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(' Reset/Factory failed: no response from device.')

        self.object_config()

    def factory_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(' Factory reset complete.')
            self.msg_factory_success()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(' Reset/Factory failed: no response from device.')

        self.object_config()

    def do_reset(self):
        if len(self.list_device.selectedItems()) == 0:
            self.logger.info('Device is not selected')
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QtWidgets.QMessageBox.Warning)
        else:
            self.sock_close()

            self.selected_devinfo()
            mac_addr = self.curr_mac

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()

            cmd_list = self.wizmakecmd.reset(
                mac_addr, self.code, self.encoded_setting_pw, self.curr_dev)
            self.logger.info('Reset: %s' % cmd_list)

            self.socket_config()

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            self.wizmsghandler.set_result.connect(self.reset_result)
            self.wizmsghandler.start()

    def do_factory_reset(self, mode):
        cmd_list = []
        if len(self.list_device.selectedItems()) == 0:
            self.logger.info('Device is not selected')
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QtWidgets.QMessageBox.Warning)
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
                cmd_list = self.wizmakecmd.factory_reset(
                    mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, "")
            elif mode == 'firmware':
                cmd_list = self.wizmakecmd.factory_reset(
                    mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, "0")

            self.logger.info('Factory: %s' % cmd_list)

            self.socket_config()

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, 'tcp', OP_SETCOMMAND, 2)
            else:
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, 'udp', OP_SETCOMMAND, 2)
            self.wizmsghandler.set_result.connect(self.factory_result)
            self.wizmsghandler.start()

    # TODO: setting pw check
    def input_setting_pw(self, mode):
        text, okbtn = QtWidgets.QInputDialog.getText(
            self, "Setting password", "Input setting password", QtWidgets.QLineEdit.Password, "")
        if okbtn:
            self.logger.info('{}, {}'.format(text, len(text)))
            if self.enable_setting_pw.isChecked():
                if not text:
                    self.logger.warning('need password to setting')
                else:
                    self.encode_setting_pw(text, mode)
            else:
                self.encode_setting_pw(text, mode)

    # To set the wait time when no response from the device when searching
    def input_search_wait_time(self):
        self.search_wait_time, okbtn = QtWidgets.QInputDialog.getInt(self, "Set the wating time for search",
                                                                     "Input wating time for search:\n(Default: 3 seconds)", self.search_wait_time, 2, 10, 1)
        if okbtn:
            self.logger.info(self.search_wait_time)
            self.search_pre_wait_time = self.search_wait_time
        else:
            pass

    def input_retry_search(self):
        inputdlg = QtWidgets.QInputDialog(self)
        name = 'Do Search'
        inputdlg.setOkButtonText(name)
        self.retry_search_num, okbtn = inputdlg.getInt(self, "Retry search devices",
                                                       "Search for additional devices,\nand the list of detected devices is maintained.\n\nInput for search retry number(option):", self.retry_search_num, 1, 10, 1)

        if okbtn:
            self.logger.info(self.retry_search_num)
            self.do_search_retry(self.retry_search_num)
        else:
            # self.do_search_retry(1)
            pass

    def append_textedit(self, variable, text):
        # self.logger.info(text)
        variable.append(text)
        variable.moveCursor(QtGui.QTextCursor.End)

    def load_cert_btn_clicked(self, cmd):
        print("load_cert_btn_clicked()", cmd)

        ext = '(*.crt)||(*.pem)'
        if cmd == "UP":
            ext = '*.bin'

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open File', '', ext + ';;All Files (*)')
        if fname:
            # Save file name to variable
            if cmd == "OC":
                self.rootca_filename = fname
                self.append_textedit(getattr(self, 'textedit_rootca'), fname)
            elif cmd == "LC":
                self.clientcert_filename = fname
                self.append_textedit(getattr(self, 'textedit_client_cert'), fname)
            elif cmd == "PK":
                self.privatekey_filename = fname
                self.append_textedit(getattr(self, 'textedit_privatekey'), fname)
            elif cmd == "UP":
                self.fw_filename = fname
                # self.append_textedit(getattr(self, 'textedit_upload_fw'), fname)
            self.logger.info('file load: %s\r\n', fname)

            self.logger.debug(f'{self.rootca_filename}, {self.clientcert_filename}, {self.privatekey_filename}')

            # Need to verify selected certificate

    def save_cert_btn_clicked(self, cmd):
        self.logger.debug(cmd)
        self.selected_devinfo()
        mac_addr = self.curr_mac

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        filename = ''
        # Certificate update
        if cmd == "OC":
            filename = self.rootca_filename
        elif cmd == "LC":
            filename = self.clientcert_filename
        elif cmd == "PK":
            filename = self.privatekey_filename
        elif cmd == "UP":
            filename = self.fw_filename

        try:
            if self.broadcast.isChecked():
                ip_addr = self.localip.text()
                port = 50002
            elif self.unicast_ip.isChecked():
                ip_addr = self.search_ipaddr.text()
                port = int(self.search_port.text())

            self.th_cert = certificatethread(
                self.conf_sock, mac_addr, self.code, self.encoded_setting_pw, filename, ip_addr, port, self.curr_dev, cmd)
            self.th_cert.uploading_size.connect(self.pgbar.setValue)
            if cmd == "UP":
                self.th_cert.upload_result.connect(self.update_result)
                self.th_cert.error_flag.connect(self.update_error)
            else:
                self.th_cert.upload_result.connect(self.cert_result)
                self.th_cert.error_flag.connect(self.cert_error)
            try:
                self.th_cert.start()
            except Exception as e:
                self.logger.error(e)
                self.update_result(-1)
        except Exception as e:
            self.logger.error(e)

    # ============================================ messagebox
    def show_msgbox(self, title, msg, type):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(type)
        msgbox.setWindowTitle(title)
        msgbox.setText(msg)
        msgbox.exec_()

    def show_msgbox_richtext(self, title, msg, type):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(type)
        msgbox.setWindowTitle(title)
        msgbox.setTextFormat(QtCore.Qt.RichText)
        msgbox.setText(msg)
        msgbox.exec_()

    def show_msgbox_info(self, title, msg):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Information)
        msgbox.setWindowTitle(title)
        msgbox.setText(msg)
        msgbox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msgbox.exec_()

    def about_info(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setTextFormat(QtCore.Qt.RichText)
        text = "<div style=text-align:center><font size=5 color=darkblue>About WIZnet-S2E-Tool-GUI</font>" \
            + "<br><a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI'><font color=darkblue size=4>* Github repository</font></a>" \
            + "<br><br><font size=4 color=black>Version " + VERSION \
            + "<br><br><font size=5 color=black>WIZnet website</font><br>" \
            + "<a href='http://www.wiznet.io/'><font color=black>WIZnet Official homepage</font></a>"  \
            + "<br><a href='https://forum.wiznet.io/'><font color=black>WIZnet Forum</font></a>" \
            + "<br><a href='https://docs.wiznet.io/'><font color=black>WIZnet Documents</font></a>" \
            + "<br><br>2022 WIZnet Co.</font><br></div>"
        msgbox.about(self, "About WIZnet-S2E-Tool-GUI", text)

    def msg_not_support(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Not supported device")
        msgbox.setTextFormat(QtCore.Qt.RichText)
        text = "The device != supported.<br>Please contact us by the link below.<br><br>" \
            "<a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'># Github issue page</a>"
        msgbox.setText(text)
        msgbox.exec_()

    def msg_invalid(self, params):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Invalid parameter")
        msgbox.setText("Invalid parameter.\nPlease check the values.")
        msgbox.setInformativeText(params)
        msgbox.exec_()

        self.object_config()

    # def msg_dev_not_selected(self):
    #     msgbox = QtWidgets.QMessageBox(self)
    #     msgbox.setIcon(QtWidgets.QMessageBox.Warning)
    #     msgbox.setWindowTitle("Warning")
    #     msgbox.setText("Device is not selected.")
    #     msgbox.exec_()

    def msg_invalid_response(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Invalid Response")
        msgbox.setText(
            "Did not receive a valid response from the device.\nPlease check if the device is supported device or firmware is the latest version.")
        msgbox.exec_()

    def msg_set_warning(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Setting")
        msgbox.setText(
            "Setting did not well.\nPlease check the device or check the firmware version.")
        msgbox.exec_()

    def msg_set_error(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Setting Failed")
        msgbox.setText("Setting failed.\nNo response from device.")
        msgbox.exec_()

    def msg_setting_pw_error(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Setting Failed")
        msgbox.setText("Setting failed.\nWrong password.")
        msgbox.exec_()

    def msg_set_success(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.question(self, "Setting success", "Device configuration complete!",
                        QtWidgets.QMessageBox.Yes)

    def msg_certificate_success(self, filename):
        msgbox = QtWidgets.QMessageBox(self)
        text = "Certificate downlaod complete!\n%s" % filename
        msgbox.question(self, "Certificate download success", text, QtWidgets.QMessageBox.Yes)

    def msg_upload_warning(self, dst_ip):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: upload/update")
        msgbox.setText(
            "Destination IP is unreachable: %s\nPlease check if the device is in the same subnet with the PC." % dst_ip)
        msgbox.exec_()

    # def msg_upload_failed(self):
    #     msgbox = QtWidgets.QMessageBox(self)
    #     msgbox.setIcon(QtWidgets.QMessageBox.Critical)
    #     msgbox.setWindowTitle("Error: Firmware upload")
    #     msgbox.setText("Firmware update failed.\nPlease check the device's status.")
    #     msgbox.exec_()

    def msg_upload_success(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.question(self, "Firmware upload success",
                        "Firmware update complete!", QtWidgets.QMessageBox.Yes)

    def msg_connection_failed(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Critical)
        msgbox.setWindowTitle("Error: Connection failed")
        msgbox.setText("Network connection failed.\nConnection is refused.")
        msgbox.exec_()

    def msg_not_connected(self, dst_ip):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIcon(QtWidgets.QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Network")
        msgbox.setText("Destination IP is unreachable: %s\nPlease check the network status." % dst_ip)
        msgbox.exec_()

    def msg_reset(self):
        self.statusbar.showMessage(' Reset device?')
        msgbox = QtWidgets.QMessageBox(self)
        btnReply = msgbox.question(
            self, "Reset", "Do you really want to reset the device?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if btnReply == QtWidgets.QMessageBox.Yes:
            self.do_reset()

    def msg_reset_success(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.question(self, "Reset", "Reset complete!", QtWidgets.QMessageBox.Yes)

    def msg_factory_success(self):
        msgbox = QtWidgets.QMessageBox(self)
        msgbox.question(self, "Factory Reset", "Factory reset complete!", QtWidgets.QMessageBox.Yes)

    def msg_factory_setting(self):
        msgbox = QtWidgets.QMessageBox(self)
        btnReply = msgbox.question(self, "Factory default settings",
                                   "Do you really want to factory reset?\nAll settings will be initialized.",
                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if btnReply == QtWidgets.QMessageBox.Yes:
            self.do_factory_reset('setting')

    def msg_factory_firmware(self):
        # factory reset firmware
        msgbox = QtWidgets.QMessageBox(self)
        btnReply = msgbox.question(self, "Factory default firmware",
                                   "Do you really want to factory reset the firmware?\nThe firmware and all settings will be initialized to factory default.",
                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if btnReply == QtWidgets.QMessageBox.Yes:
            self.do_factory_reset('firmware')

    def msg_exit(self):
        msgbox = QtWidgets.QMessageBox(self)
        btnReply = msgbox.question(
            self, "Exit", "Do you really close this program?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if btnReply == QtWidgets.QMessageBox.Yes:
            self.close()

    def dialog_save_file(self):
        mac_part = self.curr_mac.replace(':', '')[6:]
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Configuration", f"WIZCONF-{self.curr_dev}-{mac_part}.cfg", "Config File (*.cfg);;Text Files (*.txt);;All Files (*)")

        if fname:
            fileName = fname
            self.logger.info(fileName)
            self.save_configuration(fileName)

            self.saved_path = QtCore.QFileInfo(fileName).path()
            self.logger.info(self.saved_path)

    def save_configuration(self, filename):
        setcmd = self.get_object_value()
        # self.logger.info(setcmd)
        set_list = list(setcmd.keys())

        with open(filename, 'w+', encoding='utf-8') as f:
            for cmd in set_list:
                cmdset = '%s%s\n' % (cmd, setcmd.get(cmd))
                f.write(cmdset)

        self.statusbar.showMessage(' Configuration is saved to \'%s\'.' % filename)

    def dialog_load_file(self):
        if self.saved_path is None:
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Load Configuration", "WIZCONF.cfg", "Config File (*.cfg);;Text Files (*.txt);;All Files (*)")
        else:
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Load Configuration", self.saved_path, "Config File (*.cfg);;Text Files (*.txt);;All Files (*)")

        if fname:
            fileName = fname
            self.logger.info(fileName)
            self.load_configuration(fileName)

    def load_configuration(self, data_file):
        cmd_list = []
        load_profile = {}
        cmd = ""
        param = ""

        self.selected_devinfo()

        with open(data_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = re.sub('[\n]', '', line)
                if len(line) > 2:
                    cmd_list.append(line.encode())
            self.logger.info(cmd_list)

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
            self.logger.error(e)

        self.fill_devinfo(load_profile)

    def config_button_icon(self, iconfile, btnname):
        button = getattr(self, btnname)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(resource_path(iconfile)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(40, 40))
        button.setFont(self.midfont)

    def set_btn_icon(self):
        self.config_button_icon('gui/save_48.ico', 'btn_saveconfig')
        self.config_button_icon('gui/load_48.ico', 'btn_loadconfig')
        self.config_button_icon('gui/search_48.ico', 'btn_search')
        self.config_button_icon('gui/setting_48.ico', 'btn_setting')
        self.config_button_icon('gui/upload_48.ico', 'btn_upload')
        self.config_button_icon('gui/reset_48.ico', 'btn_reset')
        self.config_button_icon('gui/factory_48.ico', 'btn_factory')
        self.config_button_icon('gui/exit_48.ico', 'btn_exit')

    def font_init(self):
        self.midfont = QtGui.QFont()
        self.midfont.setPixelSize(12)    # pointsize(9)

        self.smallfont = QtGui.QFont()
        self.smallfont.setPixelSize(11)

        self.certfont = QtGui.QFont()
        self.certfont.setPixelSize(10)
        self.certfont.setFamily('Consolas')

        self.largefont = QtGui.QFont()
        self.largefont.setPixelSize(45)
        # self.largefont.setBold(True)

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

        self.ch1_reconnection_label.setFont(self.smallfont)
        self.ch2_reconnection_label.setFont(self.smallfont)
        self.gpioa_label.setFont(self.smallfont)
        self.gpiob_label.setFont(self.smallfont)
        self.gpioc_label.setFont(self.smallfont)
        self.gpiod_label.setFont(self.smallfont)

        # self.certificate_detail.setFont(self.certfont)


class ThreadProgress(QtCore.QThread):
    change_value = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        # QtCore.QThread.__init__(self)
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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    wizwindow = WIZWindow()
    wizwindow.show()
    app.exec_()
