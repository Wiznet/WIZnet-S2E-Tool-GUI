# -*- coding: utf-8 -*-

from wizsocket.TCPClient import TCPClient
from WIZMakeCMD import (
    WIZMakeCMD,
    version_compare,
    ONE_PORT_DEV,
    TWO_PORT_DEV,
    SECURITY_DEVICE,
)

from WIZUDPSock import WIZUDPSock
from FWUploadThread import FWUploadThread
from WIZMSGHandler import WIZMSGHandler, DataRefresh
from certificatethread import certificatethread
from TCPMulticastScanner import TCPMulticastScanner
from network_utils import get_subnet_hosts, get_adapter_subnet_info, extract_ip_from_device_response
from device_search_config import DeviceSearchConfig

from wizcmdset import (
    Wizcmdset,
    DeviceStatus,
    DeviceStatusMinimum,
    SysTabIndex,
    SysTabObjectText,
    ExcludeTabInMinimum,
    ExcludeTabInCommon,
    IncludeTabInCommon,
)
from constants import Opcode, SockState
from utils import logger, funclog, get_latest_release_version

import sys
import time
import re
import os
import subprocess
import webbrowser
import logging
import datetime
import csv
from pathlib import Path

# Additional package
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QFileDialog,
    QDialog,
    QMenu,
    QAction,
    QProgressBar,
    QInputDialog,
    QTabWidget,
    QLabel,
    QGridLayout,
    QToolTip,
    # QRadioButton,
    # QComboBox,
    # QCheckBox,
    # QGroupBox,
)
import ifaddr

# CSV MRU Manager
from csv_mru_manager import CSVMRUManager


SECURITY_TWO_PORT_DEV = ("W55RP20-S2E-2CH",)
W55RP20_FAMILY = ("W55RP20-S2E", "W55RP20-S2E-2CH")


class RetrySearchLimits:
    """반복 검색 설정 상수 (중앙 관리)"""

    # 예상 장비 수 제한
    EXPECTED_DEVICE_MIN = 0
    EXPECTED_DEVICE_MAX = 1000
    EXPECTED_DEVICE_DEFAULT = 0

    # 최대 반복 횟수 제한
    MAX_RETRY_MIN = 1
    MAX_RETRY_MAX = 100
    MAX_RETRY_DEFAULT = 1

    # 기타 설정
    RETRY_DELAY_MS = 100  # 반복 간 딜레이 (밀리초)


class UITooltipSettings:
    """UI 툴팁 설정 상수"""

    TOOLTIP_DELAY_MS = 300  # 툴팁 표시 지연 시간 (밀리초)
    TOOLTIP_DURATION_MS = 5000  # 툴팁 표시 지속 시간 (밀리초)


# =============================================================================
# Phase 2: 방탄(Bulletproof) 헬퍼 클래스
# =============================================================================

class SearchContext:
    """검색 리소스 자동 관리 (Context Manager - RAII 패턴)

    사용:
        with SearchContext(self):
            self.search_pre()
        # 예외 발생 시에도 자동 복구

    보장:
        - 검색 버튼 상태 복구
        - Progress bar 정리
        - 예외 발생 시에도 항상 cleanup 실행
    """

    def __init__(self, gui):
        self.gui = gui
        self.logger = gui.logger
        self.original_btn_state = None
        self.cleanup_done = False

    def __enter__(self):
        self.logger.debug("[SearchContext] 진입: UI 상태 백업")

        # 현재 상태 백업
        self.original_btn_state = self.gui.btn_search.isEnabled()

        # 검색 상태로 전환
        self.gui.btn_search.setEnabled(False)
        self.gui.pgbar.show()
        self.gui.pgbar.setValue(0)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cleanup_done:
            return False

        self.cleanup_done = True

        if exc_type is not None:
            self.logger.error(f"[SearchContext] 예외 발생: {exc_type.__name__}: {exc_val}")

        self.logger.debug("[SearchContext] 종료: UI 상태 복구")

        # 항상 복구 (예외 여부 무관)
        self.gui.btn_search.setEnabled(True)
        self.gui.pgbar.setFormat("Done")
        self.gui.pgbar.setValue(100)

        # 2초 후 pgbar 숨김
        QtCore.QTimer.singleShot(2000, lambda: self.gui.pgbar.hide())

        return False  # 예외 전파 (False = 예외 재발생)


class SearchErrorCollector:
    """검색 중 발생한 에러 수집 및 일괄 표시 (Qutebrowser 패턴)

    사용:
        collector = SearchErrorCollector()

        try:
            # 작업 1
        except Exception as e:
            collector.add("Phase 1 failed", e)

        if collector.has_errors():
            collector.show_msgbox(self)
    """

    def __init__(self):
        self.errors = []

    def add(self, context, exception, traceback_str=None):
        """에러 추가

        Args:
            context: 에러 발생 위치 설명 (예: "Phase 1 broadcast")
            exception: Exception 객체
            traceback_str: traceback 문자열 (선택)
        """
        import traceback as tb

        self.errors.append({
            'context': context,
            'type': type(exception).__name__,
            'message': str(exception),
            'traceback': traceback_str or tb.format_exc()
        })

    def has_errors(self):
        return len(self.errors) > 0

    def to_html(self):
        """HTML 형식 에러 메시지 생성"""
        if not self.has_errors():
            return ""

        html = "<h3>검색 중 오류 발생</h3><ul>"
        for err in self.errors:
            html += f"""
            <li>
                <b>{err['context']}</b>: {err['type']}<br/>
                <small>{err['message']}</small>
            </li>
            """
        html += "</ul>"
        return html

    def show_msgbox(self, parent):
        """에러 메시지박스 표시"""
        msgbox = QMessageBox(parent)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("검색 오류")
        msgbox.setTextFormat(QtCore.Qt.RichText)  # IDE 경고 무시 (실제 작동함)
        msgbox.setText(self.to_html())
        msgbox.setStandardButtons(QMessageBox.Ok)
        msgbox.exec_()


from enum import Enum


class SearchState(Enum):
    """검색 상태 열거형"""
    IDLE = "idle"
    PHASE1_BROADCAST = "phase1_broadcast"
    PHASE1_TCP_SCAN = "phase1_tcp_scan"  # Mixed search
    PHASE3_QUERY = "phase3_query"
    RETRYING = "retrying"
    ERROR = "error"


class SearchStateMachine:
    """검색 상태 머신

    보장:
        - 무효한 상태 전환 방지
        - 상태 전환 로그 자동 기록
        - 현재 상태 조회
    """

    def __init__(self, logger):
        self.state = SearchState.IDLE
        self.logger = logger

        # 유효한 상태 전환 정의
        self.valid_transitions = {
            SearchState.IDLE: [
                SearchState.PHASE1_BROADCAST,
                SearchState.PHASE1_TCP_SCAN
            ],
            SearchState.PHASE1_BROADCAST: [
                SearchState.PHASE3_QUERY,
                SearchState.RETRYING,
                SearchState.ERROR,
                SearchState.IDLE
            ],
            SearchState.PHASE1_TCP_SCAN: [
                SearchState.PHASE3_QUERY,
                SearchState.ERROR,
                SearchState.IDLE
            ],
            SearchState.PHASE3_QUERY: [
                SearchState.IDLE,
                SearchState.ERROR
            ],
            SearchState.RETRYING: [
                SearchState.PHASE1_BROADCAST,
                SearchState.IDLE,
                SearchState.ERROR
            ],
            SearchState.ERROR: [
                SearchState.IDLE
            ]
        }

    def can_transition_to(self, new_state):
        """상태 전환 가능 여부"""
        return new_state in self.valid_transitions.get(self.state, [])

    def transition(self, new_state, force=False):
        """상태 전환

        Args:
            new_state: 전환할 상태
            force: True이면 검증 건너뜀 (강제 IDLE 복귀 등)

        Raises:
            ValueError: 무효한 상태 전환 시도
        """
        if force:
            self.logger.warning(f"[State] FORCED: {self.state.value} → {new_state.value}")
            self.state = new_state
            return

        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid state transition: {self.state.value} → {new_state.value}"
            )

        self.logger.info(f"[State] {self.state.value} → {new_state.value}")
        self.state = new_state

    def reset(self):
        """강제로 IDLE 상태로 리셋"""
        self.transition(SearchState.IDLE, force=True)

    def is_idle(self):
        return self.state == SearchState.IDLE

    def is_searching(self):
        return self.state in [
            SearchState.PHASE1_BROADCAST,
            SearchState.PHASE1_TCP_SCAN,
            SearchState.PHASE3_QUERY
        ]


# Baudrate list base - common part for all devices (up to 230400)
# Items 0-13, index-aligned with gui/wizconfig_gui.ui
BAUDRATE_BASE = (
    "300", "600", "1200", "1800", "2400", "4800", "9600",
    "14400", "19200", "28800", "38400", "57600", "115200",
    "230400"
)


def resource_path(relative_path):
    # Get absolute path to resource, works for dev and for PyInstaller
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class ClickableInfoLabel(QLabel):
    """클릭 가능한 정보 아이콘 라벨 (ⓘ)

    기능:
    - UI에서 ⓘ 아이콘으로 표시되는 정보 라벨
    - 마우스 호버 시 툴팁 표시 (빠른 반응: 300ms)
    - 클릭 시에도 툴팁 표시 (사용자 편의성)
    - 손가락 커서로 클릭 가능함을 시각적으로 표시

    사용 위치:
    - Search method 제목 옆 (검색 방법 전체 설명)
    - TCP multicast 옆 (서브넷 스캔 설명)
    - Mixed 옆 (UDP + TCP 혼합 방식 설명)

    구현 특징:
    - QLabel 상속으로 UI 파일의 일반 QLabel을 런타임에 교체 가능
    - hideText() → 100ms 딜레이 → showText() 패턴으로 클릭 툴팁 안정화
    - Qt 기본 호버 툴팁과 클릭 툴팁 모두 지원
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 마우스 커서를 손가락 모양(PointingHandCursor)으로 변경
        # → 사용자에게 클릭 가능함을 시각적으로 알림
        try:
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape(13)))  # 13 = PointingHandCursor
        except Exception:
            pass

        # 툴팁 표시 지속 시간 설정 (5000ms = 5초)
        # → 충분한 시간 동안 정보를 읽을 수 있도록
        self.setToolTipDuration(UITooltipSettings.TOOLTIP_DURATION_MS)

    def mousePressEvent(self, ev):
        """마우스 클릭 시 툴팁 표시

        동작 원리:
        1. 왼쪽 버튼 클릭 감지
        2. 기존 툴팁 숨기기 (hideText)
        3. 100ms 딜레이 (Qt 내부 상태 초기화 대기)
        4. 새 툴팁 표시 (showText)

        왜 이렇게 구현했는가:
        - QToolTip.showText()를 바로 호출하면 표시 안 됨
        - hideText() + 딜레이 + showText() 패턴이 안정적으로 동작
        - 호버 툴팁과 클릭 툴팁이 충돌하지 않도록 조정
        """
        print("[DEBUG] ClickableInfoLabel.mousePressEvent called")
        if ev and ev.button() == QtCore.Qt.MouseButton(1):  # 왼쪽 버튼만
            tooltip_text = self.toolTip()
            print(f"[DEBUG] Tooltip text: {tooltip_text}")
            if tooltip_text:
                # 1단계: 기존 툴팁 숨기기 (호버 툴팁 제거)
                QToolTip.hideText()
                print("[DEBUG] hideText() called")

                # 2단계: 클릭 위치 계산 (글로벌 좌표계)
                pos = self.mapToGlobal(ev.pos())
                print(f"[DEBUG] Tooltip position: {pos}")

                # 3단계: 100ms 딜레이 후 툴팁 표시
                # → Qt 내부에서 hideText() 처리 완료 대기
                QtCore.QTimer.singleShot(100, lambda: self._show_tooltip_delayed(pos, tooltip_text))
                print("[DEBUG] Timer scheduled for delayed tooltip")

        # 부모 클래스의 이벤트 처리도 실행 (이벤트 전파)
        super().mousePressEvent(ev)

    def _show_tooltip_delayed(self, pos, text):
        """딜레이 후 툴팁 표시 (내부 헬퍼 메서드)

        Args:
            pos: 툴팁 표시 위치 (QPoint, 글로벌 좌표)
            text: 툴팁 텍스트 내용

        Note:
            - QTimer.singleShot()에서 호출됨
            - hideText() 이후 충분한 시간 경과 후 실행
        """
        print("[DEBUG] _show_tooltip_delayed called")
        QToolTip.showText(pos, text, self, self.rect(), UITooltipSettings.TOOLTIP_DURATION_MS)
        print(f"[DEBUG] showText() executed with duration={UITooltipSettings.TOOLTIP_DURATION_MS}ms")


# VERSION = 'V1.5.5.1'  # github 이슈 #36 수정
VERSION = f'V{Path(resource_path("version")).read_text().strip()}'
print(f"VERSION={VERSION}")


# Load ui files
uic_logger = logging.getLogger("PyQt5.uic")
uic_logger.setLevel(logging.WARNING)
main_window = uic.loadUiType(resource_path("gui/wizconfig_gui.ui"))[0]


class WIZWindow(QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowTitle(f"WIZnet S2E Configuration Tool {VERSION}")

        self.logger = logger
        if "Dev" in VERSION:
            self.logger.setLevel(logging.DEBUG)

        self.logger.info(f"Start configuration tool (version: {VERSION})")

        # GUI font size init
        self.midfont = None
        self.smallfont = None
        self.btnfont = None

        self.gui_init()

        # Main icon
        self.setWindowIcon(QtGui.QIcon(resource_path("gui/icon.ico")))
        self.set_btn_icon()

        # load default cmdset
        self.cmdset = Wizcmdset("WIZ750SR")
        self.wizmakecmd = WIZMakeCMD()

        self.dev_profile = {}
        self.searched_devnum = None
        # init search option
        self.retry_search_num = 1
        self.search_wait_time = 3
        # CSV MRU Manager 초기화
        self.csv_mru_manager = CSVMRUManager()
        # CSV 경로 기억 (Save/Load Searched Results) - config/ui_state.json에서 로드
        self.last_csv_directory = self.csv_mru_manager.get_last_directory()

        # check if use setting password
        self.use_setting_pw = False
        # self.entered_set_pw = ''  # setting pw bak
        self.encoded_setting_pw = ""
        self.curr_setting_pw = ""  # setting pw value

        # Certificate
        self.rootca_filename = None
        self.clientcert_filename = None
        self.privatekey_filename = None

        self.mac_list = []
        self.mn_list = []
        self.vr_list = []
        self.st_list = []
        self.threads = []
        self.curr_mac = None
        self.curr_dev = None
        self.curr_ver = None
        self.curr_st = None

        # Load device search timing configuration
        self.timing_config = DeviceSearchConfig()
        self.search_pre_wait_time = self.timing_config.get_phase1_broadcast_timeout()
        self.search_wait_time_each = self.timing_config.get_phase3_device_query_timeout()
        self.search_retry_flag = False
        self.search_retrynum = 0

        # Apply configuration to WIZMSGHandler class variables
        WIZMSGHandler.loop_select_timeout = self.timing_config.get_phase1_loop_select_timeout()
        WIZMSGHandler.emit_stabilization_ms = self.timing_config.get_phase1_emit_stabilization_ms()
        WIZMSGHandler.skip_phase1_emit_delay = self.timing_config.is_skip_phase1_emit_delay()

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

        # TCP multicast scanner and search timing
        self.tcp_scanner = None
        self.search_start_time = None

        # 검색 결과 유지/갱신 관련
        self.detected_list = []  # 검색됨 상태 목록 (bool)
        self.cumulative_mode = False  # 검색 결과 유지/갱신 모드 활성화 여부

        # 반복 검색 관련 (UDP broadcast 전용)
        self.retry_search_current = 0  # 현재 반복 횟수
        self.retry_search_expected_count = 0  # 예상 장비 수
        self.retry_search_max_count = 1  # 최대 반복 횟수
        self.retry_search_start_time = None  # 반복 검색 시작 시간

        # Initial UI object
        self.init_ui_object()

        # Initial factory reset toolbutton
        self.init_btn_factory()

        # device select event
        self.list_device.itemClicked.connect(self.dev_clicked)

        """ Button event """
        try:
            self.btn_search.clicked.connect(self._on_search_button_clicked)

            # WIZ2000: need setting password (setting, reset, upload, factory)
            self.btn_setting.clicked.connect(self.event_setting_clicked)
            self.btn_reset.clicked.connect(self.event_reset_clicked)

            # factory reset
            self.btn_factory.clicked.connect(self.event_factory_setting)
            self.btn_factory.triggered[QAction].connect(
                self.event_factory_option_clicked
            )

            # configuration save/load button
            self.btn_saveconfig.clicked.connect(self.dialog_save_file)
            self.btn_loadconfig.clicked.connect(self.dialog_load_file)

            # self.btn_upload.clicked.connect(self.update_btn_clicked)
            self.btn_upload.clicked.connect(self.event_upload_clicked)
            self.btn_exit.clicked.connect(self.msg_exit)
        except Exception as e:
            self.logger.error(f"button event register error: {e}")

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

        # Event: modbus
        # self.unicast_mac.clicked.connect(self.event_search_method)

        self.pgbar = QProgressBar()
        self.statusbar.addPermanentWidget(self.pgbar)

        # progress thread
        self.search_progress_thread = ThreadProgress()
        self.search_progress_thread.change_value.connect(self.value_changed)

        # check if device selected
        self.list_device.itemSelectionChanged.connect(self.dev_selected)

        # Menu event - File
        self.actionSave.triggered.connect(self.dialog_save_file)
        self.actionLoad.triggered.connect(self.dialog_load_file)
        self.actionSaveSearchResults.triggered.connect(self.save_searched_results_to_csv)
        self.actionLoadSearchResults.triggered.connect(self.load_searched_results_from_csv)
        self.actionExit.triggered.connect(self.msg_exit)

        # Menu event - Help
        self.about_wiz.triggered.connect(self.about_info)
        self.action_document.triggered.connect(self.menu_document)

        # Menu event - Option
        self.net_adapter_info()

        self.netconfig_menu.triggered[QAction].connect(self.net_ifs_selected)
        # Menu event - Option - Advanced Search Options
        self.actionAdvancedSearchOptions.triggered.connect(self.event_open_advanced_search_options)
        # Menu event - Option - Search option
        self.action_set_wait_time.triggered.connect(self.input_search_wait_time)
        self.action_retry_search.triggered.connect(self.input_retry_search)

        # network interface selection
        self.combobox_net_interface.currentIndexChanged.connect(self.net_changed)

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
        self.btn_load_rootca.clicked.connect(lambda: self.load_cert_btn_clicked("OC"))
        self.btn_load_client_cert.clicked.connect(
            lambda: self.load_cert_btn_clicked("LC")
        )
        self.btn_load_privatekey.clicked.connect(
            lambda: self.load_cert_btn_clicked("PK")
        )
        # self.btn_load_fwfile.clicked.connect(lambda: self.load_cert_btn_clicked('UP'))

        self.btn_save_rootca.clicked.connect(lambda: self.save_cert_btn_clicked("OC"))
        self.btn_save_client_cert.clicked.connect(
            lambda: self.save_cert_btn_clicked("LC")
        )
        self.btn_save_privatekey.clicked.connect(
            lambda: self.save_cert_btn_clicked("PK")
        )
        # self.btn_upload_fw.clicked.connect(lambda: self.save_cert_btn_clicked('UP'))

        self.textedit_rootca.textChanged.connect(self.event_rootca_changed)
        self.textedit_client_cert.textChanged.connect(self.event_client_cert_changed)
        self.textedit_privatekey.textChanged.connect(self.event_privatekey_changed)
        # self.textedit_upload_fw.textChanged.connect(self.event_uploadfw_changed)

        # Init network interface
        self.combobox_net_interface.setCurrentIndex(0)

        self.cert_object_config()

    @funclog(logger)
    def init_ui_object(self):
        """
        Initial config based WIZ750SR series
        """
        # Tab information save
        self.userio_tab_text = self.generalTab.tabText(2)
        self.mqtt_tab_text = self.generalTab.tabText(3)
        self.certificate_tab_text = self.generalTab.tabText(4)
        self.ch1_tab_text = self.channel_tab.tabText(1)
        inital_tab_count = self.generalTab.count()
        for _i in range(inital_tab_count):
            self.logger.debug(f"({_i}:{self.generalTab.tabText(_i)})")
        try:
            self.tab_structure = {
                "basic_tab": SysTabObjectText(
                    self.basic_tab, self.generalTab.tabText(0)
                ),
                "advance_tab": SysTabObjectText(
                    self.advance_tab, self.generalTab.tabText(1)
                ),
                "userio_tab": SysTabObjectText(self.userio_tab, self.userio_tab_text),
                "mqtt_tab": SysTabObjectText(self.mqtt_tab, self.mqtt_tab_text),
                "certificate_tab": SysTabObjectText(
                    self.certificate_tab, self.certificate_tab_text
                ),
            }
        except Exception as e:
            print(f"ERROR:init_ui_object:{e}")

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
        
        # group_packing_12는 기본적으로 숨김 (W55RP20-S2E일 때만 표시)
        self.group_packing_12.hide()
        
        # group_packing_13은 기본적으로 숨김 (W55RP20-S2E, W232N, IP20일 때만 표시)
        self.group_packing_13.hide()

        # Channel 1 Modbus 옵션 그룹은 기본적으로 숨김
        self.group_modubs_option_2.hide()

        # Channel 1(탭) 연결/패킹 그룹 기본 숨김
        self.group_packing_14.hide()
        self.group_packing_15.hide()

        # Channel #1 Timeout group is only used for dedicated two-port security models
        self.groupbox_ch1_timeout_2.hide()
        self.groupbox_ch1_timeout_2.setEnabled(False)

        # ch1_pack_char_3 최대 30글자로 제한 (W55RP20-S2E, W232N, IP20 SD 명령어용)
        self.ch1_pack_char_3.setMaxLength(30)
        # ch1_pack_char_4 최대 30글자로 제한 (W55RP20-S2E, W232N, IP20 DD 명령어용)
        self.ch1_pack_char_4.setMaxLength(30)
        # ch1_pack_char_5 최대 30글자로 제한 (W55RP20-S2E, W232N, IP20 SE 명령어용)
        self.ch1_pack_char_5.setMaxLength(30)
        # Channel 1 전용 (연결/절단/이더넷 전송 데이터)
        self.ch1_pack_char_7.setMaxLength(30)
        self.ch1_pack_char_8.setMaxLength(30)
        self.ch1_pack_char_9.setMaxLength(30)

        # DeviceSearchConfig 초기화 (앱 시작 시)
        if not hasattr(self, 'device_search_config'):
            self.device_search_config = DeviceSearchConfig()

        # 검색 옵션을 DeviceSearchConfig에서 로드
        config = self.device_search_config.get_current_values()
        self.retry_search_expected_count = config.get('expected_device_count', 0)
        self.retry_search_max_count = config.get('max_retry_count', 3)  # 기본값 3

        # cumulative_mode는 항상 True (UI 옵션 제거, 기능 유지)
        self.cumulative_mode = True

        # 디버깅 편의를 위한 기본값 설정 (Search method 라디오 버튼만)
        self.broadcast.setChecked(True)  # UDP Broadcast 검색 선택
        self.logger.info(f"검색 설정 로드 완료: expected_device_count={self.retry_search_expected_count}, max_retry_count={self.retry_search_max_count}, cumulative_mode=True")

        # for WIZ5XXSR custom module
        # @TODO: a6e5282d1e 에서 U3~U9 가 삭제되어 아래 코드도 삭제되어야 함
        # for i in range(3, 10):
        #     lineedit_subtopic = getattr(self, f'lineedit_mqtt_subtopic_{i}')
        #     # lineedit_subtopic.hide()
        #     lineedit_subtopic.setEnabled(False)

    def init_btn_factory(self):
        # factory_option = ['Factory default settings', 'Factory default firmware']
        self.factory_setting_action = QAction("Factory default settings", self)
        self.factory_firmware_action = QAction("Factory default firmware", self)

        self.btn_factory.addAction(self.factory_setting_action)
        self.btn_factory.addAction(self.factory_firmware_action)

    # @funclog(logger)
    def tab_changed(self):
        """
        When tab changed
        - check user IO tab
        """
        if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev:
            if self.generalTab.currentIndex() == 2:
                self.logger.debug(
                    f"Start DataRefresh: {self.curr_dev}, currentTab: {self.generalTab.currentIndex()}"
                )
                # Expansion GPIO tab
                self.gpio_check()
                self.get_refresh_time()
            else:
                try:
                    if self.datarefresh is not None:
                        self.logger.debug(
                            f"Stop DataRefresh: {self.curr_dev}, currentTab: {self.generalTab.currentIndex()}"
                        )
                        if self.datarefresh.isRunning():
                            self.datarefresh.terminate()
                except Exception as e:
                    self.logger.error(e)

    @funclog(logger)
    def net_ifs_selected(self, netifs):
        ifs = netifs.text().split(":")
        selected_ip = ifs[0]
        selected_name = ifs[1]

        self.logger.info("net_ifs_selected() %s: %s" % (selected_ip, selected_name))

        self.statusbar.showMessage(" Selected: %s: %s" % (selected_ip, selected_name))
        self.selected_eth = selected_ip

    def value_changed(self, value):
        self.pgbar.show()
        self.pgbar.setValue(value)

    def dev_selected(self):
        if len(self.list_device.selectedItems()) == 0:
            self.disable_object()
        else:
            self.object_config()

    def net_changed(self, index):
        net_text = self.combobox_net_interface.currentText()
        self.logger.info(f"net_changed() called - currentText={net_text!r}")

        # 1) placeholder 혹은 잘못된 값일 경우
        if not net_text or ":" not in net_text:
            self.statusbar.showMessage("No valid network interface selected.")
            self.selected_eth = None
            return

        # 2) ':'로 split
        ifs = net_text.split(":", 1)  # 최대 1회만 나누기
        selected_ip = ifs[0]
        selected_name = ifs[1]

        self.statusbar.showMessage(f"Selected eth: {selected_ip} - {selected_name}")
        self.selected_eth = selected_ip


    # Get network adapter & IP list
    def net_adapter_info(self):
        self.netconfig_menu = QMenu("Network Interface Config", self)
        self.netconfig_menu.setFont(self.midfont)
        self.menuOption.addMenu(self.netconfig_menu)

        # combobox init
        self.combobox_net_interface.clear()
        self.combobox_net_interface.addItem("<Select Network Interface>")

        adapters = ifaddr.get_adapters()
        self.net_list = []

        # 네트워크 인터페이스를 수집하여 정렬 (물리 어댑터 우선, 가상 어댑터는 최하위)
        adapter_list = []
        for adapter in adapters:
            self.logger.debug(f"Net Interface: {adapter.nice_name}")
            for ip in adapter.ips:
                if len(ip.ip) > 6:
                    ipv4_addr = ip.ip
                    if ipv4_addr != "127.0.0.1":
                        net_ifs = ipv4_addr + ":" + adapter.nice_name
                        nice_name_lower = adapter.nice_name.lower()

                        # 가상 어댑터 판별 (이름 기반)
                        virtual_keywords = [
                            'virtualbox', 'vmware', 'hyper-v', 'vethernet',
                            'docker', 'wsl', 'tap-windows', 'npcap',
                            'virtual', 'vbox', 'bridge', 'loopback'
                        ]
                        is_virtual = any(keyword in nice_name_lower for keyword in virtual_keywords)

                        # 우선순위 결정:
                        # 0: 물리 Ethernet
                        # 1: 물리 Wi-Fi
                        # 2: 기타 물리 인터페이스
                        # 3: 가상 어댑터
                        # 4: APIPA/link-local (169.254.*)
                        if ipv4_addr.startswith("169.254."):
                            priority = 4  # APIPA/link-local (최하위)
                        elif is_virtual:
                            priority = 3  # 가상 어댑터
                        elif 'ethernet' in nice_name_lower or 'eth' in nice_name_lower:
                            priority = 0  # 물리 Ethernet
                        elif 'wireless' in nice_name_lower or 'wi-fi' in nice_name_lower or 'wifi' in nice_name_lower:
                            priority = 1  # 물리 Wi-Fi
                        else:
                            priority = 2  # 기타 물리 인터페이스

                        adapter_list.append((priority, net_ifs, adapter.nice_name))

        # 우선순위로 정렬 (물리 어댑터 먼저, 가상 어댑터는 나중)
        adapter_list.sort(key=lambda x: (x[0], x[1]))

        # 정렬된 순서로 추가
        for priority, net_ifs, nice_name in adapter_list:
            self.net_list.append(nice_name)
            netconfig = QAction(net_ifs, self)
            self.netconfig_menu.addAction(netconfig)
            self.combobox_net_interface.addItem(net_ifs)

        # add refresh action 
        refresh_action = QAction("Refresh", self)
        refresh_action.setFont(self.midfont)
        refresh_action.triggered.connect(self.on_refresh_network_adapter)
        self.netconfig_menu.addSeparator()
        self.netconfig_menu.addAction(refresh_action)
        # Default: not selected
        self.combobox_net_interface.setCurrentIndex(0)
        # 힌트 텍스트 설정
        # self.combobox_net_interface.setPlaceholderText('<Select Network Interface>')
        
    def on_refresh_network_adapter(self):
        # 1) "Network Interface Config" 메뉴 제거
        for action in self.menuOption.actions():
            # menuBar에서 addMenu(...)는 결국 QAction을 반환
            if action.text() == "Network Interface Config":
                # self.menuOption에서 해당 QAction(=서브메뉴)을 제거
                self.menuOption.removeAction(action)
                break

        # 2) net_adapter_info() 다시 호출
        self.net_adapter_info()

        # 3) 로그 남기기
        self.logger.info("Network interface config menu re-created.")
        self.statusbar.showMessage("Network interface config menu re-created.")

    

    def disable_object(self):
        self.btn_reset.setEnabled(False)
        self.btn_factory.setEnabled(False)
        self.btn_upload.setEnabled(False)
        self.btn_setting.setEnabled(False)
        self.btn_saveconfig.setEnabled(False)
        self.btn_loadconfig.setEnabled(False)

        self.generalTab.setEnabled(False)
        print("disable_object::channel_tab set tab disabled")
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

        if self.curr_st not in DeviceStatusMinimum:
            print("object_config::channel_tab set tab enabled")
            self.channel_tab.setEnabled(True)
        else:
            print("object_config::channel_tab set tab disabled")
            self.channel_tab.setEnabled(False)
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
        if len(self.textedit_rootca.toPlainText()) > 0:
            self.btn_save_rootca.setEnabled(True)
        else:
            self.btn_save_rootca.setEnabled(False)

    def event_client_cert_changed(self):
        if len(self.textedit_client_cert.toPlainText()) > 0:
            self.btn_save_client_cert.setEnabled(True)
        else:
            self.btn_save_client_cert.setEnabled(False)

    def event_privatekey_changed(self):
        if len(self.textedit_privatekey.toPlainText()) > 0:
            self.btn_save_privatekey.setEnabled(True)
        else:
            self.btn_save_privatekey.setEnabled(False)

    # Button click events
    def event_setting_clicked(self):
        self.do_setting()

    def event_reset_clicked(self):
        self.do_reset()

    def event_factory_setting(self):
        self.msg_factory_setting()

    def event_factory_firmware(self):
        self.msg_factory_firmware()

    # factory reset options
    # option: factory button / menu 1, menu 2
    def event_factory_option_clicked(self, option):
        self.logger.info(option.text())
        opt = option.text()

        if "settings" in opt:
            self.event_factory_setting()
        elif "firmware" in opt:
            self.event_factory_firmware()

    def event_upload_clicked(self):
        if self.localip_addr is not None:
            self.update_btn_clicked()
        else:
            self.show_msgbox(
                "Warning",
                "Local IP information could not be found. Check the Network configuration.",
                QMessageBox.Warning,
            )

    def gpio_check(self):
        if "WIZ5XX" in self.curr_dev:
            gpio_list = ["a", "b"]
        else:
            gpio_list = ["a", "b", "c", "d"]

        for name in gpio_list:
            gpio_config = getattr(self, f"gpio{name}_config")
            gpio_set = getattr(self, f"gpio{name}_set")
            if gpio_config.currentIndex() == 1:
                gpio_set.setEnabled(True)
            else:
                gpio_set.setEnabled(False)

    def _is_wiz750sr_series(self) -> bool:
        return bool(self.curr_dev and "WIZ750SR" in self.curr_dev)

    def _current_ch1_opmode_index(self):
        if self.ch1_tcpclient.isChecked():
            return 0
        if self.ch1_tcpserver.isChecked():
            return 1
        if self.ch1_tcpmixed.isChecked():
            return 2
        if self.ch1_udp.isChecked():
            return 3
        if self.ch1_ssl_tcpclient.isChecked():
            return 4
        if self.ch1_mqttclient.isChecked():
            return 5
        if self.ch1_mqtts_client.isChecked():
            return 6
        return None

    def _uses_mb_modbus(self) -> bool:
        if not self.curr_dev or not self.curr_ver:
            return False
        return ("WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev) and version_compare(self.curr_ver, "1.4.4") >= 0

    def _modbus_param_key(self) -> str:
        return "MB" if self._uses_mb_modbus() else "PO"

    def _modbus_supported(self) -> bool:
        if not self.curr_dev or not self.curr_ver:
            return False
        if self.curr_st in DeviceStatusMinimum:
            return False
        if self._uses_mb_modbus():
            if self._is_wiz750sr_series():
                current_mode = self._current_ch1_opmode_index()
                if current_mode not in (1, 3):
                    return False
            return True
        if "WIZ5XXSR" in self.curr_dev and version_compare("1.0.8", self.curr_ver) <= 0:
            return True
        if self.curr_dev in W55RP20_FAMILY:
            return True
        if "W232N" in self.curr_dev or "IP20" in self.curr_dev:
            return True
        return False

    def _get_current_baud_from_profile(self, max_supported_br_index):
        """
        Retrieve the current baudrate string from dev_profile based on BR index.

        Args:
            max_supported_br_index: Maximum BR index supported by the device
                                    (13: WIZ750SR/W232N, 14: Others, 15: IP20, 19: W55RP20)

        Returns:
            str or None: Baudrate string (e.g., "115200") or None if not found
        """
        if self.curr_mac not in self.dev_profile:
            return None

        dev_data = self.dev_profile[self.curr_mac]
        if "BR" not in dev_data:
            return None

        try:
            br_index = int(dev_data["BR"])
        except (ValueError, TypeError):
            return None

        # Validate BR index is within supported range
        if br_index < 0 or br_index > max_supported_br_index:
            return None

        # Map BR index to baudrate string
        if br_index < len(BAUDRATE_BASE):
            return BAUDRATE_BASE[br_index]
        elif br_index == 14:
            return "460800"
        elif br_index == 15:
            return "921600"
        elif br_index == 16:
            return "1M"
        elif br_index == 17:
            return "2M"
        elif br_index == 18:
            return "4M"
        elif br_index == 19:
            return "8M"

        return None

    # Object config for some Devices or F/W version
    def object_config_for_device(self):
        # IP20도 Certificate manager 탭 표시 (SSL/MQTTS 지원)
        # if self.curr_dev == "IP20":
        #     # certificate_tab_text는 init_ui_object에서 저장됨
        #     n_tabs = self.generalTab.count()
        #     for idx in range(n_tabs):
        #         if self.generalTab.tabText(idx) == self.certificate_tab_text:
        #             self.generalTab.removeTab(idx)
        #             break

        # W55RP20-S2E, W232N, IP20인 경우에만 group_packing_12 표시 (SD/DD 기능)
        # 버전이 1.1.8 이상인 경우에만 표시
        if self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
            self.group_packing_12.show()
            self.group_packing_13.show()
        else:
            self.group_packing_12.hide()
            self.group_packing_13.hide()
        
        # ...existing code...
        is_security_two_port = self.curr_dev in SECURITY_TWO_PORT_DEV
        is_legacy_two_port = (
            (self.curr_dev in TWO_PORT_DEV or "WIZ752" in self.curr_dev)
            and not is_security_two_port
        )

        # Channel #0 Modbus option is hidden on legacy two-port models that reuse the UI
        if is_legacy_two_port:
            self.group_modubs_option.hide()
            self.modbus_protocol.setCurrentIndex(0)
        else:
            self.group_modubs_option.show()

        # Channel #1 timeout widgets are only applicable to security two-port devices
        if is_security_two_port:
            self.groupbox_ch1_timeout_2.show()
            self.groupbox_ch1_timeout_2.setEnabled(True)
        else:
            self.groupbox_ch1_timeout_2.hide()
            self.groupbox_ch1_timeout_2.setEnabled(False)

        # WIZ5XX 가 아니면 modbus 는 사용 불가 #36
        print(
            f"model={self.curr_dev},ver={self.curr_ver},version compare={version_compare(self.curr_ver, '1.0.8')},status={self.curr_st}"
        )
        if self.curr_st in DeviceStatusMinimum:
            # Ensure Modbus option is not left enabled when device is in BOOT/UPGRADE
            self.modbus_protocol.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)
            self.group_modubs_option_2.hide()
            return

        supports_modbus = not is_legacy_two_port and self._modbus_supported()
        self.modbus_protocol.setEnabled(supports_modbus)
        if not supports_modbus:
            self.modbus_protocol.setCurrentIndex(0)

        if is_security_two_port:
            self.group_modubs_option_2.show()
            self.modbus_protocol_2.setEnabled(True)
            self.group_packing_14.show()
            self.group_packing_15.show()
        else:
            self.group_modubs_option_2.hide()
            self.modbus_protocol_2.setCurrentIndex(0)
            self.group_packing_14.hide()
            self.group_packing_15.hide()
        if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev or "W232N" in self.curr_dev:
            if version_compare("1.2.0", self.curr_ver) <= 0:
                # setcmd['TR'] = self.tcp_timeout.text()
                self.tcp_timeout.setEnabled(True)
            else:
                self.tcp_timeout.setEnabled(False)

            # 'OP' option
            self.ch1_ssl_tcpclient.setEnabled(False)
            self.ch1_mqttclient.setEnabled(False)
            self.ch1_mqtts_client.setEnabled(False)

            # Baudrate configuration - get current device's BR value from dev_profile
            current_baud = self._get_current_baud_from_profile(13)  # WIZ750SR/W232N: max BR index 13 (230400)

            # Baudrate configuration for WIZ750SR/W232N (max 230400)
            self.ch1_baud.clear()
            self.ch1_baud.addItems(BAUDRATE_BASE)  # 300 ~ 230400 (14 items)

            # Restore current device's selection
            if current_baud:
                idx = self.ch1_baud.findText(current_baud)
                if idx >= 0:
                    self.ch1_baud.setCurrentIndex(idx)
        elif self.curr_dev in W55RP20_FAMILY:
            # W55RP20: 펌웨어 버전에 따라 고속 보드레이트 지원 여부 결정
            # - FW < 1.2.1: BR 0-15 (최대 921600)
            # - FW >= 1.2.1: BR 0-19 (최대 8M, 1M/2M/4M/8M 지원)
            supports_high_speed = False
            if hasattr(self, 'curr_ver') and self.curr_ver:
                supports_high_speed = version_compare(self.curr_ver, "1.2.1") >= 0

            # Baudrate configuration - get current device's BR value from dev_profile
            max_br_index = 19 if supports_high_speed else 15
            current_baud = self._get_current_baud_from_profile(max_br_index)

            # Baudrate configuration for W55RP20
            self.ch1_baud.clear()
            self.ch1_baud.addItems(BAUDRATE_BASE)  # 300 ~ 230400 (14 items)
            self.ch1_baud.addItem("460800")  # Add 460800 (index 14)
            self.ch1_baud.addItem("921600")  # Add 921600 (index 15)

            # 펌웨어 1.2.1 이상에서만 고속 보드레이트 추가
            if supports_high_speed:
                self.ch1_baud.addItem("1M")  # Add 1M (index 16)
                self.ch1_baud.addItem("2M")  # Add 2M (index 17)
                self.ch1_baud.addItem("4M")  # Add 4M (index 18)
                self.ch1_baud.addItem("8M")  # Add 8M (index 19)

            # Restore current device's selection
            if current_baud:
                idx = self.ch1_baud.findText(current_baud)
                if idx >= 0:
                    self.ch1_baud.setCurrentIndex(idx)

            # 2CH device: ch2_baud도 ch1_baud와 동일하게 구성 (버전에 따라)
            if self.curr_dev in SECURITY_TWO_PORT_DEV:
                # ch2_baud의 현재 EB 값 가져오기
                current_ch2_baud = None
                if self.curr_mac in self.dev_profile:
                    dev_data = self.dev_profile[self.curr_mac]
                    if "EB" in dev_data:
                        try:
                            eb_index = int(dev_data["EB"])
                            if 0 <= eb_index <= max_br_index:
                                if eb_index < len(BAUDRATE_BASE):
                                    current_ch2_baud = BAUDRATE_BASE[eb_index]
                                elif eb_index == 14:
                                    current_ch2_baud = "460800"
                                elif eb_index == 15:
                                    current_ch2_baud = "921600"
                                elif eb_index == 16:
                                    current_ch2_baud = "1M"
                                elif eb_index == 17:
                                    current_ch2_baud = "2M"
                                elif eb_index == 18:
                                    current_ch2_baud = "4M"
                                elif eb_index == 19:
                                    current_ch2_baud = "8M"
                        except (ValueError, TypeError):
                            pass

                # ch2_baud를 ch1_baud와 동일하게 구성
                self.ch2_baud.clear()
                self.ch2_baud.addItems(BAUDRATE_BASE)  # 0-13
                self.ch2_baud.addItem("460800")  # 14
                self.ch2_baud.addItem("921600")  # 15
                if supports_high_speed:
                    self.ch2_baud.addItem("1M")   # 16
                    self.ch2_baud.addItem("2M")   # 17
                    self.ch2_baud.addItem("4M")   # 18
                    self.ch2_baud.addItem("8M")   # 19

                # ch2_baud 현재 선택값 복원
                if current_ch2_baud:
                    idx = self.ch2_baud.findText(current_ch2_baud)
                    if idx >= 0:
                        self.ch2_baud.setCurrentIndex(idx)
        elif "IP20" in self.curr_dev:
            # Baudrate configuration - get current device's BR value from dev_profile
            current_baud = self._get_current_baud_from_profile(15)  # IP20: max BR index 15 (921600)

            # Baudrate configuration for IP20 (max 921600)
            self.ch1_baud.clear()
            self.ch1_baud.addItems(BAUDRATE_BASE)  # 300 ~ 230400 (14 items)
            self.ch1_baud.addItem("460800")  # Add 460800 (index 14)
            self.ch1_baud.addItem("921600")  # Add 921600 (index 15)

            # Restore current device's selection
            if current_baud:
                idx = self.ch1_baud.findText(current_baud)
                if idx >= 0:
                    self.ch1_baud.setCurrentIndex(idx)
        else:
            # Baudrate configuration - get current device's BR value from dev_profile
            current_baud = self._get_current_baud_from_profile(14)  # Other devices: max BR index 14 (460800)

            # Baudrate configuration for other devices (max 460800)
            self.ch1_baud.clear()
            self.ch1_baud.addItems(BAUDRATE_BASE)  # 300 ~ 230400 (14 items)
            self.ch1_baud.addItem("460800")  # Add 460800 (index 14)

            # Restore current device's selection
            if current_baud:
                idx = self.ch1_baud.findText(current_baud)
                if idx >= 0:
                    self.ch1_baud.setCurrentIndex(idx)

            # TODO: ch2_baud (EB) 관리 개선 필요 - 2채널 baudrate 목록 관리 로직 검토 및 리팩토링
            # Remove 921600 from ch2 if exists
            idx_921 = self.ch2_baud.findText("921600")
            if idx_921 != -1:
                self.ch2_baud.removeItem(idx_921)


        # SC: Status pin option
        if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
            pass
        else:
            if self.curr_dev in SECURITY_DEVICE:
                self.radiobtn_group_s0.hide()
                self.radiobtn_group_s1.hide()
                self.group_dtrdsr.show()
                if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
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
            # IP20도 SSL, MQTTs 지원
            self.ch1_ssl_tcpclient.setEnabled(True)
            self.ch1_mqtts_client.setEnabled(True)
            self.ch1_mqttclient.setEnabled(True)
            # Current bank (RO)
            self.group_current_bank.show()
            if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
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
        """버튼 아래 일반 탭을 장비 종류와 상태에 따라 다르게 설정합니다.
        SECURITY_DEVICE 이면 BOOT/UPGRADE 모드가 아닌 경우 mqtt, 인증서 탭을 추가합니다.
        @mason 이사가 BOOT/UPGRADE 모드일 때 advance_tab 도 뺐으면 좋겠다고 해서 기존 코드에 advance_tab 추가 코드도 작성
        그 외 장비는 basic_tab, advance_tab 만 보여줌
        """
        # General tab ui setup by device
        n_tabs: int = self.generalTab.count()
        print(f"n_tabs={n_tabs}")
        # 탭 인덱스(순서)와 이름을 구해 역순으로 정렬
        list_tabs: list = []
        for _i, _t in enumerate(range(n_tabs)):
            list_tabs.append(SysTabIndex(_i, self.generalTab.widget(_t).objectName()))
        list_tabs.sort(reverse=True)
        print("list_tabs=", list_tabs)
        if self.curr_dev in SECURITY_DEVICE:
            # print(f"tabs in generalTab({self.generalTab}) has {self.generalTab.count()} tabs")
            # self.generalTab.count() 가 탭 추가/삭제하는 과정에서 신뢰불가.
            # insertTab에 첫번째 인수로 인덱스를 줘도 실제로는 마지막 인덱스가 할당됨. 인덱스 보장 안됨.
            # 최초 한번 정확히 계산 후 자신의 작업을 계획에 맞게 진행해야 함.
            # BOOT/UPGRADE 상태라면 mqtt, certificate, advance 탭 삭제
            # 디바이스 상태가 DeviceStatusMinimum 이면 ExcludeTabInMinimum 에 속한 탭 삭제
            # 디바이스 상태가 DeviceStatusMinimum 이 아니면 ExcludeTabInMinimum 탭이 없으면 탭 추가
            if self.curr_st in DeviceStatusMinimum:
                _tab: tuple[int, QTabWidget]
                for _tab in list_tabs:
                    if _tab.name in ExcludeTabInMinimum:
                        self.generalTab.removeTab(_tab.idx)
                        list_tabs.remove(_tab)
            else:
                next_tab_idx: int = n_tabs
                _new_tab: str
                for _new_tab in ExcludeTabInMinimum:
                    if _new_tab not in repr(list_tabs):
                        _new_tab_object = self.tab_structure.get(_new_tab)
                        print(f"_new_tab={_new_tab},_new_tab_object={_new_tab_object}")
                        self.generalTab.insertTab(
                            next_tab_idx,
                            _new_tab_object.object,
                            _new_tab_object.ui_text,
                        )
                        self.generalTab.setTabEnabled(next_tab_idx, True)
                        next_tab_idx += 1
            #     # # self.generalTab.setTabEnabled(5, True)
            #     # # self.group_setting_pw.setEnabled(False)
            # for _t in range(self.generalTab.count()):
            #     print(f"tab({_t}): name={self.generalTab.widget(_t).objectName()},obj={self.generalTab.widget(_t)}")
        else:
            # 빼야할 탭 빼기
            print("list_tabs=", list_tabs)
            for _tab in list_tabs:
                print("tab=", _tab)
                if _tab.name in ExcludeTabInCommon:
                    self.generalTab.removeTab(_tab.idx)
                    list_tabs.remove(_tab)
            next_tab_idx: int = len(list_tabs)
            # 넣어야할 탭 넣기
            for _new_tab in IncludeTabInCommon:
                if _new_tab not in repr(list_tabs):
                    _new_tab_object = self.tab_structure.get(_new_tab)
                    self.generalTab.insertTab(
                        next_tab_idx, _new_tab_object.object, _new_tab_object.ui_text
                    )
                    self.generalTab.setTabEnabled(next_tab_idx, True)
                    next_tab_idx += 1

        # User I/O tab
        """
        - WIZ750SR
        - WIZ750SR-100
        - WIZ5XXSR-RP (only use A,B)
        """
        # if 'WIZ750' in self.curr_dev or 'W7500' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev or "W7500" in self.curr_dev:
            # ! Check current tab length
            # self.logger.debug(f'totalTab: {len(self.generalTab)}, currentTab: {self.generalTab.currentIndex()}')
            # self.generalTab.insertTab(2, self.userio_tab, self.userio_tab_text)
            # self.generalTab.setTabEnabled(2, True)
            if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
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
                elif len(self.generalTab) == 3:
                    if self.generalTab.tabText(2) == self.userio_tab_text:
                        pass
                    else:
                        # Exception case: Basic settings / Options / MQTT Options
                        self.generalTab.removeTab(2)
                        self.generalTab.insertTab(
                            2, self.userio_tab, self.userio_tab_text
                        )
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
        print("channel_tab_config::curr_st=", self.curr_st)
        if self.curr_st in DeviceStatusMinimum:
            n_tabs = self.channel_tab.count()
            for i in reversed(range(1, n_tabs + 1)):
                self.channel_tab.removeTab(i)
            self.channel_tab.setTabEnabled(0, False)
        elif (
            self.curr_dev in ONE_PORT_DEV
            or "WIZ750" in self.curr_dev
            or "WIZ750SR-T1L" in self.curr_dev
            or self.curr_dev in SECURITY_DEVICE
        ):
            if self.curr_dev in SECURITY_TWO_PORT_DEV:
                self.channel_tab.insertTab(1, self.tab_ch1, self.ch1_tab_text)
                print("channel_tab_config::channel_tab set tab enabled security 2port")
                self.channel_tab.setTabEnabled(0, True)
                self.channel_tab.setTabEnabled(1, True)
                return
            self.channel_tab.removeTab(1)
            print("channel_tab_config::channel_tab set tab enabled 1port")
            self.channel_tab.setTabEnabled(0, True)
        elif self.curr_dev in TWO_PORT_DEV or "WIZ752" in self.curr_dev:
            self.channel_tab.insertTab(1, self.tab_ch1, self.ch1_tab_text)
            print("channel_tab_config::channel_tab set tab enabled 2port")
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
            self.searchcode_input.setEchoMode(QLineEdit.Normal)
        else:
            self.searchcode_input.setEchoMode(QLineEdit.Password)

    def event_idcode(self):
        if self.show_idcode.isChecked():
            self.searchcode.setEchoMode(QLineEdit.Normal)
        else:
            self.searchcode.setEchoMode(QLineEdit.Password)

    def event_passwd(self):
        if self.show_connectpw.isChecked():
            self.connect_pw.setEchoMode(QLineEdit.Normal)
        else:
            self.connect_pw.setEchoMode(QLineEdit.Password)

    def event_passwd_enable(self):
        if self.enable_connect_pw.isChecked():
            self.connect_pw.setEnabled(True)
        else:
            self.connect_pw.setEnabled(False)

    def event_opmode(self):
        if self.ch1_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)

        elif self.ch1_tcpserver.isChecked():
            self.ch1_remote.setEnabled(False)
            self.group_modubs_option.setEnabled(True)

        elif self.ch1_tcpmixed.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)

        elif self.ch1_udp.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(True)

        elif self.ch1_ssl_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)

        elif self.ch1_mqttclient.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)

        elif self.ch1_mqtts_client.isChecked():
            self.ch1_remote.setEnabled(True)
            self.group_modubs_option.setEnabled(False)
            self.modbus_protocol.setCurrentIndex(0)

        ch1_modbus_available = self._modbus_supported()
        self.modbus_protocol.setEnabled(ch1_modbus_available)
        if not ch1_modbus_available:
            self.modbus_protocol.setCurrentIndex(0)

        supports_ch2_modbus = self.curr_dev in SECURITY_TWO_PORT_DEV

        if self.ch2_tcpclient.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(False)
                self.modbus_protocol_2.setCurrentIndex(0)
            else:
                self.group_modubs_option.setEnabled(False)
                self.modbus_protocol.setCurrentIndex(0)

        elif self.ch2_tcpserver.isChecked():
            self.ch2_remote.setEnabled(False)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(True)
            else:
                self.group_modubs_option.setEnabled(True)

        elif self.ch2_tcpmixed.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(False)
                self.modbus_protocol_2.setCurrentIndex(0)
            else:
                self.group_modubs_option.setEnabled(False)
                self.modbus_protocol.setCurrentIndex(0)

        elif self.ch2_udp.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(True)
            else:
                self.group_modubs_option.setEnabled(True)

        elif self.ch2_ssl_tcpclient.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(False)
                self.modbus_protocol_2.setCurrentIndex(0)
            else:
                self.group_modubs_option.setEnabled(False)
                self.modbus_protocol.setCurrentIndex(0)

        elif self.ch2_mqttclient.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(False)
                self.modbus_protocol_2.setCurrentIndex(0)
            else:
                self.group_modubs_option.setEnabled(False)
                self.modbus_protocol.setCurrentIndex(0)

        elif self.ch2_mqtts_client.isChecked():
            self.ch2_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.group_modubs_option_2.setEnabled(False)
                self.modbus_protocol_2.setCurrentIndex(0)
            else:
                self.group_modubs_option.setEnabled(False)
                self.modbus_protocol.setCurrentIndex(0)

    def event_search_method(self):
        self.logger.info(f"localip.text()={self.localip.text()}")
        if self.localip.text():
            self.search_ipaddr.setText(self.localip.text())

        # UDP Broadcast - disable all input fields
        if self.broadcast.isChecked():
            self.search_ipaddr.setEnabled(False)
            self.search_port.setEnabled(False)

        # TCP Unicast - enable IP and port
        elif self.unicast_ip.isChecked():
            self.search_ipaddr.setEnabled(True)
            self.search_port.setEnabled(True)

        # 검색 방법 변경 시 반복 검색 카운터 리셋
        if self.retry_search_current > 0:
            self.logger.info(f"검색 방법 변경: 반복 검색 카운터 리셋 ({self.retry_search_current} → 0)")
            self.retry_search_current = 0

    def sock_close(self):
        # 기존 연결 fin
        if self.cli_sock is not None:
            if self.cli_sock.state != SockState.SOCK_CLOSE:
                self.cli_sock.shutdown()

    def connect_over_tcp(self, serverip, port):
        retrynum = 0
        self.cli_sock = TCPClient(5, serverip, port)
        # print('sock state: %r' % (self.cli_sock.state))
        _outer_begin = time.time()
        max_fail_count = 4
        while True:
            if retrynum > max_fail_count:
                break
            retrynum += 1

            if self.cli_sock.state == SockState.SOCK_CLOSE:
                begin = time.time()
                self.cli_sock.shutdown()
                try:
                    self.cli_sock.open()
                    if self.cli_sock.state == SockState.SOCK_OPEN:
                        self.logger.info("[%r] is OPEN" % (serverip))
                    time.sleep(0.2)
                except Exception as e:
                    self.logger.error(f"opening {serverip}:{e}")
                finally:
                    self.logger.info(f"{time.time() - begin} seconds elapsed")
            elif self.cli_sock.state == SockState.SOCK_OPEN:
                try:
                    self.cli_sock.connect()
                    if self.cli_sock.state == SockState.SOCK_CONNECT:
                        self.logger.info("[%r] is CONNECTED" % (serverip))
                except Exception as e:
                    self.logger.error(f"opening {serverip}:{e}")
            elif self.cli_sock.state == SockState.SOCK_CONNECT:
                break
        self.logger.info(f"Totaly {time.time() - _outer_begin:.3f} seconds elapsed")
        if retrynum > max_fail_count:
            self.logger.info("Device [%s] TCP connection failed.\r\n" % (serverip))
            # 다음 소켓을 초기화하지 않으면 이미 종료된 이전 접속 정보가 남아서 다음 오류가 발생함
            # WinError 10057 소켓이 연결되어 있지 않거나 Sendto 호출을 사용하여 데이터그램 소켓에 보내는 경우에 주소가 제공되지 않아서 데이터를 보내거나 받도록 요청할 수 없습니다
            self.cli_sock = None
            return None
        else:
            self.logger.info("Device [%s] TCP connected\r\n" % (serverip))
        return self.cli_sock

    def socket_config(self):
        try:
            # Broadcast
            if self.broadcast.isChecked():
                if self.selected_eth is None:
                    self.conf_sock = WIZUDPSock(5000, 50001, "")
                else:
                    self.conf_sock = WIZUDPSock(5000, 50001, self.selected_eth)
                    self.logger.debug(self.selected_eth)

                self.conf_sock.open()

            # TCP unicast
            elif self.unicast_ip.isChecked():
                ip_addr = self.search_ipaddr.text()
                port = int(self.search_port.text())
                self.logger.info("unicast: ip: %r, port: %r" % (ip_addr, port))

                # network check
                net_response = self.net_check_ping(ip_addr)

                if net_response == 0:
                    self.conf_sock = self.connect_over_tcp(ip_addr, port)

                    if self.conf_sock is None:
                        self.isConnected = False
                        self.logger.info("TCP connection failed!: %s" % self.conf_sock)
                        self.statusbar.showMessage(
                            " TCP connection failed: %s" % ip_addr
                        )
                        self.msg_connection_failed()
                    else:
                        self.isConnected = True
                    self.btn_search.setEnabled(True)
                else:
                    self.statusbar.showMessage(" Network unreachable: %s" % ip_addr)
                    self.btn_search.setEnabled(True)
                    self.msg_not_connected(ip_addr)

        except Exception as e:
            self.logger.error(f"socket_config error: {e}")

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

                cmd_list = self.wizmakecmd.get_gpiovalue(
                    mac_addr, self.code, self.curr_dev
                )
                # print('refresh_gpio', cmd_list)

                if self.unicast_ip.isChecked():
                    self.datarefresh = DataRefresh(
                        self.conf_sock, cmd_list, "tcp", self.intv_time
                    )
                else:
                    self.datarefresh = DataRefresh(
                        self.conf_sock, cmd_list, "udp", self.intv_time
                    )
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
                            if b"CA" in cmdset_list[i]:
                                self.gpioa_config.setCurrentIndex(
                                    int(cmdset_list[i][2:])
                                )
                            if b"CB" in cmdset_list[i]:
                                self.gpiob_config.setCurrentIndex(
                                    int(cmdset_list[i][2:])
                                )
                            if b"CC" in cmdset_list[i]:
                                self.gpioc_config.setCurrentIndex(
                                    int(cmdset_list[i][2:])
                                )
                            if b"CD" in cmdset_list[i]:
                                self.gpiod_config.setCurrentIndex(
                                    int(cmdset_list[i][2:])
                                )

                        if b"GA" in cmdset_list[i]:
                            self.gpioa_get.setText(cmdset_list[i][2:].decode())
                        if b"GB" in cmdset_list[i]:
                            self.gpiob_get.setText(cmdset_list[i][2:].decode())
                        if b"GC" in cmdset_list[i]:
                            self.gpioc_get.setText(cmdset_list[i][2:].decode())
                        if b"GD" in cmdset_list[i]:
                            self.gpiod_get.setText(cmdset_list[i][2:].decode())
                except Exception as e:
                    self.logger.error(e)

    def _on_search_button_clicked(self):
        """검색 버튼 클릭 이벤트 핸들러 - 타이머 시작"""
        # Device Search 버튼 클릭 시 항상 이전 검색 결과 클리어
        # (cumulative_mode와 상관없이 클리어 - 반복 검색 시에만 누적 유지)
        self.mac_list = []
        self.mn_list = []
        self.vr_list = []
        self.st_list = []
        self.mode_list = []  # OP (Operation Mode) - Phase 1에서 받는 정보
        self.detected_list = []
        self.list_device.clearContents()
        self.list_device.setRowCount(0)
        self.searched_num.setText("0")
        self.logger.info("이전 검색 결과 클리어 (Device Search 버튼 클릭)")

        # 새 검색 시작 - 반복 검색 카운터 리셋 및 타이머 시작
        self.retry_search_current = 0
        self._timing_t0 = time.time()
        self.logger.info("[TIMING] System timer started at button click")

        # 실제 검색 함수 호출
        self.do_search_normal()

    def do_search_retry(self, num):
        try:
            self.search_retry_flag = True
            # search retry number
            self.search_retrynum = num
            self.logger.info(self.mac_list)

            self.search_pre()
        except Exception as e:
            self.logger.error(f"do_search_normal error: {e}")
            self.search_error_msgbox()

    def do_search_normal(self):
        """일반 검색 시작 (방어적 버전 - SearchContext 적용)

        보장:
            - 예외 발생 시에도 UI 상태 복구
            - 검색 버튼 항상 재활성화
            - pgbar 항상 정리
        """
        try:
            with SearchContext(self):
                self.search_retry_flag = False
                self.search_pre()
        except Exception as e:
            self.logger.error(f"do_search_normal 예외: {e}", exc_info=True)
            self.search_error_msgbox()
        # SearchContext __exit__에서 자동으로 UI 복구됨

    def search_error_msgbox(self):
        self.show_msgbox(
            "Device search failed",
            "There was a problem searching the device.\nCheck and set the network adapter.",
            QMessageBox.Warning,
        )

    def _T(self):
        """[TIMING] 기준 시각 이후 경과 시간 문자열 반환"""
        t0 = getattr(self, '_timing_t0', None)
        if t0 is not None:
            return f"+{time.time() - t0:.3f}s"
        return "+?.???s"

    def search_pre(self):
        # 타이밍은 do_search_normal()에서 이미 설정됨
        self.logger.info(f"[TIMING] {self._T()} search_pre() 진입 (retry #{self.retry_search_current})")

        if self.wizmsghandler is not None and self.wizmsghandler.isRunning():
            self.logger.info(f"[TIMING] {self._T()} wizmsghandler 아직 실행 중 → wait() 대기")
            self.wizmsghandler.wait()
            self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 완료")
            # print('wait')
        else:
            # 기존 연결 close
            self.sock_close()
            self.logger.info(f"[TIMING] {self._T()} sock_close() 완료")

            # 첫 검색 시작 시 설정 읽기 (유지/갱신 모드 + UDP broadcast)
            if self.retry_search_current == 0 and self.cumulative_mode and self.broadcast.isChecked():
                # 내부 변수에서 값 읽기 (Advanced Search Options에서 설정된 값 사용)
                # 값 검증 (범위 체크)
                expected = getattr(self, 'retry_search_expected_count', 0)
                if expected < RetrySearchLimits.EXPECTED_DEVICE_MIN:
                    expected = RetrySearchLimits.EXPECTED_DEVICE_MIN
                    self.logger.warning(f"예상 장비 수 범위 미만 → {expected}로 설정")
                elif expected > RetrySearchLimits.EXPECTED_DEVICE_MAX:
                    expected = RetrySearchLimits.EXPECTED_DEVICE_MAX
                    self.logger.warning(f"예상 장비 수 범위 초과 → {expected}로 제한")
                self.retry_search_expected_count = expected

                max_retry = getattr(self, 'retry_search_max_count', 3)
                if max_retry < RetrySearchLimits.MAX_RETRY_MIN:
                    max_retry = RetrySearchLimits.MAX_RETRY_MIN
                    self.logger.warning(f"최대 반복 횟수 범위 미만 → {max_retry}로 설정")
                elif max_retry > RetrySearchLimits.MAX_RETRY_MAX:
                    max_retry = RetrySearchLimits.MAX_RETRY_MAX
                    self.logger.warning(f"최대 반복 횟수 범위 초과 → {max_retry}로 제한")
                self.retry_search_max_count = max_retry

                self.logger.info(f"반복 검색 시작: 예상 {self.retry_search_expected_count}개, 최대 {self.retry_search_max_count}회")
                # 반복 검색 시작 시간 기록
                self.retry_search_start_time = time.time()

            cmd_list = []
            # default search id code
            self.code = " "
            self.all_response = []
            self.pgbar.hide()  # 이전 검색 잔여 진행바 즉시 숨김
            self.pgbar.setRange(0, 100)
            self.processing()

            if self.search_retry_flag:
                self.logger.info("keep searched list")
                pass
            else:
                # 유지/갱신 모드가 OFF이면 기존 결과 삭제
                if not self.cumulative_mode:
                    # List table initial (clear)
                    self.list_device.setRowCount(0)
                # 유지/갱신 모드: 테이블 초기화하지 않음 (행 유지)

            # 테이블 헤더 설정 (매번 재설정)
            item_mac = QTableWidgetItem()
            item_mac.setText("Mac address")
            item_mac.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(0, item_mac)

            item_name = QTableWidgetItem()
            item_name.setText("Name")
            item_name.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(1, item_name)

            item_detected = QTableWidgetItem()
            item_detected.setText("검색됨")
            item_detected.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(2, item_detected)

            # Set socket for search
            self.logger.info(f"[TIMING] {self._T()} socket_config() 시작")
            _t_sock = time.time()
            self.socket_config()
            self.logger.info(f"[TIMING] {self._T()} socket_config() 완료 ({(time.time()-_t_sock)*1000:.1f}ms 소요)")
            _conf_sock = "None" if not hasattr(self, "conf_sock") else self.conf_sock
            self.logger.info(f"search: conf_sock: {_conf_sock}")

            # Search devices
            if self.isConnected or self.broadcast.isChecked():
                self.statusbar.showMessage(" Searching devices...")

                # Start timing
                self.search_start_time = time.time()

                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.presearch("FF:FF:FF:FF:FF:FF", self.code)
                self.logger.debug(cmd_list)

                # TCP unicast mode
                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock,
                        cmd_list,
                        "tcp",
                        Opcode.OP_SEARCHALL,
                        self.search_pre_wait_time,
                        presearch=True,
                    )
                    self.wizmsghandler.search_result.connect(self.get_search_result)
                    self.wizmsghandler.start()

                # UDP broadcast mode (default)
                else:
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock,
                        cmd_list,
                        "udp",
                        Opcode.OP_SEARCHALL,
                        self.search_pre_wait_time,
                        presearch=True,
                    )
                    self.wizmsghandler.search_result.connect(self.get_search_result)
                    self.wizmsghandler.start()
                    self.logger.info(f"[TIMING] {self._T()} wizmsghandler.start() 완료 → search_pre() 종료")

    def processing(self):
        self.btn_search.setEnabled(False)
        # pgbar hide는 search_each_dev() 완료 후 _finalize_search()에서 처리

    def search_each_dev(self, dev_info_list):
        """Phase 3: 개별 장비 정보 조회 (pgbar 최적화 적용)"""
        cmd_list = []
        self.eachdev_info = []

        self.code = " "
        # self.all_response = []
        self.logger.info(f"search_each_dev() dev_info_list: {dev_info_list}")
        total_devs = len(dev_info_list)

        # pgbar 최적화: 갱신 간격 계산
        try:
            update_percent = self.timing_config.get_pgbar_update_percent()
        except Exception as e:
            self.logger.warning(f"get_pgbar_update_percent 실패: {e}, 기본값 10 사용")
            update_percent = 10

        update_interval = self._calc_pgbar_update_interval(total_devs, update_percent)
        self.logger.debug(f"pgbar 갱신 간격: {update_interval}개마다 (총 {total_devs}개, {update_percent}%)")

        # 반복 검색 모드: 전체 진행률 계산 (현재 반복의 시작 진행률)
        if self.cumulative_mode and self.broadcast.isChecked() and self.retry_search_max_count > 1:
            base_progress = int((self.retry_search_current / self.retry_search_max_count) * 100)
            self.logger.debug(f"반복 검색 진행률: {self.retry_search_current + 1}/{self.retry_search_max_count}, base_progress={base_progress}%")
        else:
            base_progress = 0

        self.statusbar.showMessage(f" Querying devices... (0/{total_devs})")
        self.pgbar.setFormat(" ")
        self.pgbar.setValue(base_progress)
        self.pgbar.show()
        QApplication.processEvents()

        if self.broadcast.isChecked():
            self.socket_config()
        else:
            # tcp unicast일 경우 search_pre에서 이미 커넥션이 수립되어 있음
            pass

        # Search devices
        if self.isConnected or self.broadcast.isChecked():
            pass

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()

            if self.unicast_ip.isChecked():
                # TCP unicast: 단일 연결, 순차 처리 (pgbar 최적화 적용)
                for idx, dev_info in enumerate(dev_info_list):
                    self.logger.debug(dev_info)
                    cmd_list = self.wizmakecmd.search(
                        dev_info[0], self.code, dev_info[1], dev_info[2], dev_info[3]
                    )
                    th = WIZMSGHandler(
                        self.conf_sock,
                        cmd_list,
                        "tcp",
                        Opcode.OP_SEARCHALL,
                        self.search_wait_time_each,
                    )
                    th.searched_data.connect(self.getsearch_each_dev)
                    th.start()
                    th.wait()

                    # 조건부 pgbar 갱신 (최적화)
                    if self._should_update_pgbar(idx, total_devs, update_interval):
                        self.statusbar.showMessage(f" Querying devices... ({idx + 1}/{total_devs})")
                        # 반복 검색 모드: 전체 진행률 계산
                        if self.cumulative_mode and self.broadcast.isChecked() and self.retry_search_max_count > 1:
                            phase_progress = int(((idx + 1) / total_devs) * 100)
                            total_progress = base_progress + int((phase_progress / 100) * (100 / self.retry_search_max_count))
                            self.pgbar.setValue(total_progress)
                        QApplication.processEvents()
            else:
                # UDP (broadcast/multicast/mixed): 장비마다 전용 소켓 → 전체 동시 시작
                threads = []
                dev_socks = []
                peer_port = 50001  # WIZ 장비 수신 포트 (고정값)
                local_ip = self.selected_eth if self.selected_eth is not None else ""

                for dev_info in dev_info_list:
                    self.logger.debug(dev_info)
                    cmd_list = self.wizmakecmd.search(
                        dev_info[0], self.code, dev_info[1], dev_info[2], dev_info[3]
                    )
                    # 장비마다 독립 소켓 (localport=0 → OS가 포트 자동 할당)
                    dev_sock = WIZUDPSock(0, peer_port, local_ip, localport=0)
                    dev_sock.open()
                    dev_socks.append(dev_sock)

                    th = WIZMSGHandler(
                        dev_sock,
                        cmd_list,
                        "udp",
                        Opcode.OP_SEARCHALL,
                        self.search_wait_time_each,
                    )
                    th.searched_data.connect(self.getsearch_each_dev)
                    th.start()
                    threads.append(th)

                # 모든 스레드 동시 대기 (병렬 실행, 총 시간 ≈ 최장 RTT) (pgbar 최적화 적용)
                for idx, th in enumerate(threads):
                    th.wait()

                    # 조건부 pgbar 갱신 (최적화)
                    if self._should_update_pgbar(idx, len(threads), update_interval):
                        self.statusbar.showMessage(f" Querying devices... ({idx + 1}/{total_devs})")
                        # 반복 검색 모드: 전체 진행률 계산
                        if self.cumulative_mode and self.broadcast.isChecked() and self.retry_search_max_count > 1:
                            phase_progress = int(((idx + 1) / total_devs) * 100)
                            total_progress = base_progress + int((phase_progress / 100) * (100 / self.retry_search_max_count))
                            self.pgbar.setValue(total_progress)
                        QApplication.processEvents()

                # 전용 소켓 정리
                for sock in dev_socks:
                    try:
                        sock.close()
                    except Exception:
                        pass

        # Restore the final status message (without final system time yet)
        if hasattr(self, 'final_status_message'):
            self.statusbar.showMessage(self.final_status_message)
        self.pgbar.setFormat(" ")

        # 반복 검색 모드: 현재 반복의 끝 진행률 설정
        if self.cumulative_mode and self.broadcast.isChecked() and self.retry_search_max_count > 1:
            # 현재 반복 완료 시점의 진행률
            end_progress = int(((self.retry_search_current + 1) / self.retry_search_max_count) * 100)
            self.pgbar.setValue(end_progress)
            self.logger.debug(f"Phase 3 완료: 진행률 {end_progress}% (반복 {self.retry_search_current + 1}/{self.retry_search_max_count})")
        else:
            self.pgbar.setValue(100)

        # Hide progress bar after a delay and calculate final system time when truly done
        def _finalize_search():
            """진행바 숨김 + 최종 System 시간 계산"""
            self.pgbar.hide()

            # 최종 System 시간 계산 (진행바 완전히 숨겨진 시점)
            if hasattr(self, '_timing_t0') and self._timing_t0 is not None:
                final_system_time = time.time() - self._timing_t0
                self.logger.info(f"[TIMING] Final system time (after pgbar hidden): {final_system_time:.2f}s")

                # 기존 메시지의 System 시간 부분을 최종 시간으로 업데이트
                if hasattr(self, 'final_status_message') and self.final_status_message:
                    import re
                    # 기존 System 시간 제거
                    msg = re.sub(r',?\s*System\s+[\d.]+\s+seconds?\)?', '', self.final_status_message)
                    # 최종 System 시간 추가
                    msg = msg.rstrip(')')
                    if '(' in msg:
                        msg += f", System {final_system_time:.2f} seconds)"
                    else:
                        msg += f" (System {final_system_time:.2f} seconds)"
                    self.final_status_message = msg
                    self.statusbar.showMessage(msg)

        QtCore.QTimer.singleShot(2000, _finalize_search)

    def getsearch_each_dev(self, dev_data):
        try:
            if dev_data is None:
                return

            # 현재 수신된 패킷만 파싱 (기존 O(N²) 전체 재처리 → O(1))
            profile = {}
            cmdsets = dev_data.split(b"\r\n")
            for cmdset in cmdsets:
                if len(cmdset) < 2 or cmdset[:2] == b"MA":
                    continue
                cmd = cmdset[:2].decode('utf-8', errors='replace')
                param = cmdset[2:].decode('utf-8', errors='replace')
                profile[cmd] = param

            mc = profile.get("MC")
            if mc:
                self.dev_profile[mc] = profile
                self.logger.debug(f"dev_profile 갱신: {mc}")

                # 브로드캐스트 응답(mn_list)이 비어있으면 개별 쿼리 결과로 채우기
                mn_from_profile = profile.get("MN", "")
                if mn_from_profile:
                    for idx, mac_bytes in enumerate(self.mac_list):
                        mac_str = (
                            mac_bytes.decode('utf-8', errors='replace')
                            if isinstance(mac_bytes, bytes)
                            else str(mac_bytes)
                        )
                        if mac_str == mc:
                            if idx < len(self.mn_list) and not self.mn_list[idx]:
                                self.mn_list[idx] = mn_from_profile.encode('utf-8')
                                if self.list_device.rowCount() > idx:
                                    self.list_device.setItem(
                                        idx, 1, QTableWidgetItem(mn_from_profile)
                                    )
                                self.logger.debug(
                                    f"mn_list[{idx}] 빈 MN → dev_profile로 갱신: {mn_from_profile!r}"
                                )
                            break
            else:
                self.logger.error(
                    f"getsearch_each_dev: 'MC' 필드 없음, "
                    f"profile keys={list(profile.keys())}, "
                    f"raw={repr(dev_data[:80])}"
                )
                self.statusbar.showMessage(" [오류] 장비 응답에 MAC 주소(MC) 없음 — 해당 항목 건너뜀")

            # 구 retry 메커니즘 (cumulative 모드에서는 항상 0)
            if self.search_retrynum:
                self.logger.info(self.search_retrynum)
                self.search_retrynum -= 1
                self.search_pre()

        except Exception as e:
            self.logger.error(e)
            self.msg_error("[ERROR] getsearch_each_dev(): {}".format(e))

    def get_search_result(self, devnum):
        self.logger.info(f"[TIMING] {self._T()} get_search_result() 진입 (devnum={devnum}, emit→진입 시각)")

        # CSV Load 모드 체크
        csv_load_mode = getattr(self, 'csv_load_mode', False)
        if csv_load_mode:
            self.logger.info("CSV Load 모드: Phase 1 데이터 이미 로드됨, wizmsghandler 건너뜀")

        if self.search_retry_flag:
            pass
        else:
            # 유지/갱신 모드가 OFF이면 기존 데이터 삭제
            if not self.cumulative_mode:
                # CSV Load 모드가 아닐 때만 초기화 (CSV는 이미 데이터 로드됨)
                if not csv_load_mode:
                    # init old info
                    self.mac_list = []
                    self.mn_list = []
                    self.vr_list = []
                    self.st_list = []
                    self.mode_list = []
                    self.detected_list = []
            else:
                # 유지/갱신 모드: 기존 데이터 유지, 모든 "검색됨" 상태를 False로 초기화
                self.detected_list = [False] * len(self.mac_list)
                self.logger.info(f"유지/갱신 모드: 기존 {len(self.mac_list)}개 장비 유지, 검색됨 초기화")

        # Determine data source (wizmsghandler for UDP/TCP unicast)
        # CSV Load 모드에서는 건너뜀 (이미 데이터가 self.mac_list 등에 있음)
        data_source = None
        if not csv_load_mode and self.wizmsghandler is not None:
            data_source = self.wizmsghandler
            if self.wizmsghandler.isRunning():
                self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 시작 (get_search_result에서 아직 실행 중)")
                self.wizmsghandler.wait()
                self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 완료")

        if devnum >= 0:
            self.searched_devnum = devnum
            # self.logger.info(self.searched_devnum)
            self.searched_num.setText(str(self.searched_devnum))
            self.btn_search.setEnabled(True)

            if devnum == 0:
                self.logger.info("No device.")
            else:
                # [DIAG] WIZMSGHandler 수신 리스트 길이 검증
                if data_source:
                    _d = data_source
                    self.logger.info(
                        f"[DIAG] WIZMSGHandler lists: mac={len(_d.mac_list)}"
                        f" mn={len(_d.mn_list)} vr={len(_d.vr_list)}"
                        f" st={len(_d.st_list)} mode={len(_d.mode_list)}"
                        f" rcv={len(_d.rcv_list)}"
                    )
                    # 정렬 이상 감지
                    lens = [len(_d.mac_list), len(_d.mn_list), len(_d.vr_list), len(_d.st_list)]
                    if len(set(lens)) > 1:
                        self.logger.warning(f"[DIAG] WIZMSGHandler 리스트 길이 불일치! {lens}")
                    # mn_list 내용 (비ASCII 포함 여부)
                    for _i, _mn in enumerate(_d.mn_list):
                        try:
                            _mn.decode('ascii')
                        except Exception:
                            self.logger.warning(f"[DIAG] mn_list[{_i}] non-ASCII: {_mn!r}")
                # CSV Load 모드: wizmsghandler 데이터 로드 건너뛰기
                # (이미 CSV에서 mac_list, mn_list, vr_list, st_list, mode_list 로드됨)
                if csv_load_mode:
                    self.logger.info(f"CSV Load 모드: {len(self.mac_list)}개 장비 데이터 사용 (wizmsghandler 건너뜀)")
                    # detected_list 설정 (CSV에서 로드한 값 유지)
                    # 테이블 업데이트는 아래 공통 코드에서 처리
                elif self.search_retry_flag:
                    self.logger.info("search retry flag on")
                    new_mac_list = data_source.mac_list if data_source else []
                    new_mn_list = data_source.mn_list if data_source else []
                    new_vr_list = data_source.vr_list if data_source else []
                    new_st_list = data_source.st_list if data_source else []
                    new_mode_list = data_source.mode_list if data_source else []
                    new_resp_list = data_source.rcv_list if data_source else []

                    # check mac list
                    for i in range(len(new_mac_list)):
                        if new_mac_list[i] in self.mac_list:
                            pass
                        else:
                            self.mac_list.append(new_mac_list[i])
                            self.mn_list.append(new_mn_list[i])
                            self.vr_list.append(new_vr_list[i])
                            self.st_list.append(new_st_list[i])
                            self.mode_list.append(new_mode_list[i] if i < len(new_mode_list) else b'')
                            self.all_response.append(new_resp_list[i])

                    # print('keep list len >>', len(self.mac_list), len(self.mn_list), len(self.vr_list), len(self.st_list))
                    # print('keep list >>', self.mac_list, self.mn_list, self.vr_list, self.st_list)

                else:
                    # 새 검색 결과 가져오기
                    new_mac_list = data_source.mac_list if data_source else []
                    new_mn_list = data_source.mn_list if data_source else []
                    new_vr_list = data_source.vr_list if data_source else []
                    new_st_list = data_source.st_list if data_source else []
                    new_mode_list = data_source.mode_list if data_source else []
                    new_rcv_list = data_source.rcv_list if data_source else []

                    # 유지/갱신 모드 처리
                    if self.cumulative_mode:
                        self.logger.info(f"[TIMING] {self._T()} _merge_search_results() 시작")
                        self._merge_search_results(new_mac_list, new_mn_list, new_vr_list, new_st_list, new_mode_list)
                        self.logger.info(f"[TIMING] {self._T()} _merge_search_results() 완료")
                        # all_response도 병합 (기존 + 신규)
                        for rcv in new_rcv_list:
                            if rcv not in self.all_response:
                                self.all_response.append(rcv)
                    else:
                        # 기본 모드: 그냥 새 결과로 교체
                        self.mac_list = new_mac_list
                        self.mn_list = new_mn_list
                        self.vr_list = new_vr_list
                        self.st_list = new_st_list
                        self.mode_list = new_mode_list
                        self.detected_list = [True] * len(self.mac_list)
                        # all response
                        self.all_response = new_rcv_list

                # [DIAG] 병합/교체 후 self 리스트 길이 검증
                _self_lens = [len(self.mac_list), len(self.mn_list), len(self.vr_list),
                              len(self.st_list), len(self.detected_list)]
                self.logger.info(
                    f"[DIAG] 병합 후 self lists: mac={_self_lens[0]}"
                    f" mn={_self_lens[1]} vr={_self_lens[2]}"
                    f" st={_self_lens[3]} detected={_self_lens[4]}"
                )
                if len(set(_self_lens)) > 1:
                    self.logger.warning(f"[DIAG] self 리스트 길이 불일치! {_self_lens}")

                # row length = the number of searched devices
                self.logger.info(f"[TIMING] {self._T()} 테이블 업데이트 시작 ({len(self.mac_list)}행)")
                self.list_device.setRowCount(len(self.mac_list))

                for i in range(0, len(self.mac_list)):
                    try:
                        # MAC 주소
                        self.list_device.setItem(
                            i, 0, QTableWidgetItem(self.mac_list[i].decode('utf-8', errors='replace'))
                        )
                        # 장비 이름
                        mn_str = self.mn_list[i].decode('utf-8', errors='replace') if i < len(self.mn_list) else ''
                        self.list_device.setItem(i, 1, QTableWidgetItem(mn_str))
                        # 검색됨 상태
                        detected_item = QTableWidgetItem()
                        if i < len(self.detected_list) and self.detected_list[i]:
                            detected_item.setText("●")
                            detected_item.setForeground(QtGui.QColor(0, 200, 0))
                        else:
                            detected_item.setText("○")
                            detected_item.setForeground(QtGui.QColor(150, 150, 150))
                        detected_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                        self.list_device.setItem(i, 2, detected_item)
                    except Exception as e:
                        self.logger.error(f"[ROW {i}] 테이블 표시 오류: {e}")

                # resize for data
                _t_resize = time.time()
                self.list_device.resizeColumnsToContents()
                self.list_device.resizeRowsToContents()

                # row/column resize disable
                self.list_device.horizontalHeader().setSectionResizeMode(2)
                self.list_device.verticalHeader().setSectionResizeMode(2)
                self.logger.info(f"[TIMING] {self._T()} 테이블 업데이트 완료 (resize 포함: {(time.time()-_t_resize)*1000:.1f}ms)")

            # 반복 검색 로직 (유지/갱신 모드 + UDP broadcast 전용)
            # devnum == 0이어도 반복 검색 수행 (처음 응답 없던 장비가 나중에 응답할 수 있음)
            if self.cumulative_mode and self.broadcast.isChecked():
                self.retry_search_current += 1

                # 유지/갱신으로 발견된 전체 장비 수 (핵심 지표)
                total_count = len(self.mac_list)
                # 이번 검색에서 새로 발견된 장비 수 (로깅용 참고 정보)
                newly_detected = sum(1 for d in self.detected_list if d)

                self.logger.info(f"반복 검색 {self.retry_search_current}회차: 전체 {total_count}개 (이번 검색: {newly_detected}개)")

                # 조기 종료 조건 체크 (리팩토링)
                reached_expected = (self.retry_search_expected_count > 0 and
                                   total_count >= self.retry_search_expected_count)
                reached_max = self.retry_search_current >= self.retry_search_max_count

                # 종료 조건: 예상 장비 수 도달 OR 최대 반복 횟수 도달
                should_continue = not (reached_expected or reached_max)

                # 로깅: 종료 이유 명시
                if reached_expected:
                    self.logger.info(f"예상 장비 수 도달: {total_count}/{self.retry_search_expected_count}")
                if reached_max:
                    self.logger.info(f"최대 반복 횟수 도달: {self.retry_search_current}/{self.retry_search_max_count}")

                # 계속 반복할지 결정
                if should_continue:
                    self.logger.info(f"반복 검색 계속: {self.retry_search_current + 1}회차 시작")
                    # 약간의 딜레이 후 재검색 (상수 사용)
                    self.logger.info(f"[TIMING] {self._T()} QTimer.singleShot({RetrySearchLimits.RETRY_DELAY_MS}ms) 설정 → _continue_retry_search 예약")
                    QtCore.QTimer.singleShot(RetrySearchLimits.RETRY_DELAY_MS, self._continue_retry_search)
                    return  # get_dev_list() 호출하지 않음
                else:
                    # 반복 종료 - 시간 계산 (Phase 3 이후 최종 업데이트됨)
                    system_time = None  # Phase 3 완료 후 search_each_dev()에서 계산
                    if self.retry_search_start_time is not None:
                        elapsed = time.time() - self.retry_search_start_time
                        if system_time is not None:
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries, {elapsed:.2f} seconds, System {system_time:.2f} seconds)"
                        else:
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries, {elapsed:.2f} seconds)"
                        self.retry_search_start_time = None  # 리셋
                    else:
                        if system_time is not None:
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries, System {system_time:.2f} seconds)"
                        else:
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries)"

                    self.logger.info(f"반복 검색 완료: 총 {self.retry_search_current}회, {total_count}개 장비 발견")

                    # 상태바 메시지 업데이트 (진행바는 텍스트 없이 바만 표시)
                    self.final_status_message = status_msg
                    self.statusbar.showMessage(self.final_status_message)

                    # 카운터 리셋
                    self.retry_search_current = 0
            else:
                # 일반 검색 완료 (비 반복 모드)
                self.pgbar.setFormat(" ")
                self.pgbar.setValue(100)

                # Phase 3 이후 최종 업데이트됨
                system_time = None  # Phase 3 완료 후 search_each_dev()에서 계산
                if self.search_start_time is not None:
                    elapsed = time.time() - self.search_start_time
                    if system_time is not None:
                        self.final_status_message = f" Done. {devnum} devices found ({elapsed:.2f} seconds, System {system_time:.2f} seconds)"
                    else:
                        self.final_status_message = f" Done. {devnum} devices found ({elapsed:.2f} seconds)"
                    self.search_start_time = None  # Reset for next search
                else:
                    if system_time is not None:
                        self.final_status_message = f" Done. {devnum} devices found (System {system_time:.2f} seconds)"
                    else:
                        self.final_status_message = f" Done. {devnum} devices found"

                self.statusbar.showMessage(self.final_status_message)

            QtCore.QTimer.singleShot(0, self.get_dev_list)
        else:
            self.logger.error("search error")

    def _continue_retry_search(self):
        """반복 검색 계속 수행

        Note: detected_list는 초기화하지 않음
        - 유지/갱신 모드에서는 이전 결과를 유지해야 하므로
        - _merge_search_results()에서 새로 발견된 장비만 True로 업데이트
        """
        try:
            self.logger.info(f"[TIMING] {self._T()} _continue_retry_search() 진입 (QTimer 발화)")
            # search_pre 재호출 (detected_list는 유지)
            self.search_pre()
        except Exception as e:
            self.logger.error(f"반복 검색 중 오류: {e}")
            self.retry_search_current = 0
            # 사용자에게 알림
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "반복 검색 오류",
                f"반복 검색 중 오류가 발생했습니다:\n{str(e)}\n\n검색을 중단합니다."
            )

    # =========================================================================
    # Phase 2: 방어적 헬퍼 메서드
    # =========================================================================

    def _sync_detected_list(self):
        """detected_list와 mac_list 길이 동기화

        보장:
            len(self.detected_list) == len(self.mac_list)

        동작:
            - 부족: False로 패딩
            - 초과: 잘라내기
            - 검증: assert로 확인
        """
        current_len = len(self.detected_list)
        target_len = len(self.mac_list)

        if current_len == target_len:
            return  # 이미 동기화됨

        if current_len < target_len:
            # 부족: False로 채움
            padding = [False] * (target_len - current_len)
            self.detected_list.extend(padding)
            self.logger.debug(f"detected_list 패딩: {current_len} → {target_len}")
        else:
            # 초과: 잘라냄
            self.detected_list = self.detected_list[:target_len]
            self.logger.warning(f"detected_list 잘라냄: {current_len} → {target_len}")

        # 검증
        assert len(self.detected_list) == len(self.mac_list), \
            f"Sync failed: detected={len(self.detected_list)}, mac={len(self.mac_list)}"

    def _safe_list_set(self, lst, idx, value, list_name="list"):
        """리스트 인덱스 안전 설정

        Args:
            lst: 대상 리스트
            idx: 인덱스
            value: 설정할 값
            list_name: 로그용 리스트 이름

        Returns:
            bool: 성공 여부
        """
        if not isinstance(lst, list):
            self.logger.error(f"_safe_list_set: {list_name} is not list, type={type(lst)}")
            return False

        if idx < 0:
            self.logger.error(f"_safe_list_set: negative index {idx} for {list_name}")
            return False

        if idx >= len(lst):
            self.logger.error(
                f"_safe_list_set: index {idx} out of range for {list_name} (len={len(lst)})"
            )
            return False

        try:
            lst[idx] = value
            return True
        except Exception as e:
            self.logger.error(f"_safe_list_set: failed to set {list_name}[{idx}] = {value}: {e}")
            return False

    def _calc_pgbar_update_interval(self, total_devs, update_percent):
        """Progress bar 갱신 간격 계산 (방어적 버전)

        Args:
            total_devs: 전체 장비 수 (양의 정수 기대)
            update_percent: 갱신 퍼센트 1~100 (정수 기대)

        Returns:
            int: 갱신 간격 (항상 1 이상, total_devs 이하)

        Examples:
            total_devs=20, percent=10 → 2 (10개마다 1회)
            total_devs=5, percent=10 → 1 (매번)
            total_devs=None → 1 (기본값)
            total_devs=-5 → 1 (기본값)
            percent=200 → 100으로 제한
        """
        # 입력 검증: total_devs
        if total_devs is None:
            self.logger.warning("_calc_pgbar_update_interval: total_devs is None, using 1")
            return 1

        if not isinstance(total_devs, int):
            self.logger.warning(f"_calc_pgbar_update_interval: total_devs is not int, type={type(total_devs)}, using 1")
            return 1

        if total_devs <= 0:
            self.logger.warning(f"_calc_pgbar_update_interval: total_devs={total_devs} <= 0, using 1")
            return 1

        # 입력 검증: update_percent
        if update_percent is None:
            self.logger.warning("_calc_pgbar_update_interval: update_percent is None, using default 10")
            update_percent = 10

        if not isinstance(update_percent, (int, float)):
            self.logger.warning(f"_calc_pgbar_update_interval: update_percent type={type(update_percent)}, using 10")
            update_percent = 10

        # 범위 제한 (1~100)
        if update_percent < 1:
            self.logger.warning(f"_calc_pgbar_update_interval: update_percent={update_percent} < 1, clamped to 1")
            update_percent = 1
        elif update_percent > 100:
            self.logger.warning(f"_calc_pgbar_update_interval: update_percent={update_percent} > 100, clamped to 100")
            update_percent = 100

        # 간격 계산
        interval = int(total_devs * update_percent / 100)

        # 최소 1, 최대 total_devs 보장
        interval = max(1, min(interval, total_devs))

        return interval

    def _should_update_pgbar(self, current_idx, total_devs, update_interval):
        """Progress bar 갱신 여부 판단 (방어적 버전)

        Args:
            current_idx: 현재 인덱스 (0-based)
            total_devs: 전체 장비 수
            update_interval: 갱신 간격

        Returns:
            bool: 갱신 필요 여부

        조건:
            1. 간격마다 갱신 ((idx+1) % interval == 0)
            2. 마지막 장비는 항상 갱신 (idx == total-1)
            3. 잘못된 입력 시 항상 True (안전하게)
        """
        # 입력 검증
        if not isinstance(current_idx, int) or current_idx < 0:
            self.logger.warning(f"_should_update_pgbar: invalid current_idx={current_idx}, returning True")
            return True

        if not isinstance(total_devs, int) or total_devs <= 0:
            self.logger.warning(f"_should_update_pgbar: invalid total_devs={total_devs}, returning True")
            return True

        if not isinstance(update_interval, int) or update_interval <= 0:
            self.logger.warning(f"_should_update_pgbar: invalid update_interval={update_interval}, returning True")
            return True

        # 범위 검증
        if current_idx >= total_devs:
            self.logger.warning(f"_should_update_pgbar: current_idx={current_idx} >= total_devs={total_devs}, returning True")
            return True

        # 조건 1: 간격마다 갱신
        if (current_idx + 1) % update_interval == 0:
            return True

        # 조건 2: 마지막 장비는 항상 갱신
        if current_idx == total_devs - 1:
            return True

        return False

    def _merge_search_results(self, new_mac_list, new_mn_list, new_vr_list, new_st_list, new_mode_list=None):
        """검색 결과 유지/갱신 모드에서 새 검색 결과를 기존 목록과 병합

        Args:
            new_mac_list: 새로 발견된 MAC 주소 목록
            new_mn_list: 새로 발견된 장비 이름 목록
            new_vr_list: 새로 발견된 버전 목록
            new_st_list: 새로 발견된 상태 목록
            new_mode_list: 새로 발견된 동작 모드 목록 (OP - Operation Mode)
        """
        # 기존 MAC 주소 → 인덱스 매핑 생성
        existing_mac_map = {}
        for i, mac in enumerate(self.mac_list):
            mac_str = mac.decode() if isinstance(mac, bytes) else mac
            existing_mac_map[mac_str] = i

        # 새 결과 처리
        for i in range(len(new_mac_list)):
            new_mac = new_mac_list[i]
            new_mac_str = new_mac.decode() if isinstance(new_mac, bytes) else new_mac

            if new_mac_str in existing_mac_map:
                # 기존 장비 발견 → 데이터 갱신
                idx = existing_mac_map[new_mac_str]
                if i < len(new_mn_list):
                    self.mn_list[idx] = new_mn_list[i]
                if i < len(new_vr_list):
                    self.vr_list[idx] = new_vr_list[i]
                if i < len(new_st_list):
                    self.st_list[idx] = new_st_list[i]
                if new_mode_list and i < len(new_mode_list):
                    self.mode_list[idx] = new_mode_list[i]
                self.detected_list[idx] = True
                self.logger.debug(f"장비 갱신: {new_mac_str}")
            else:
                # 신규 장비 → 목록에 추가
                self.mac_list.append(new_mac_list[i])
                self.mn_list.append(new_mn_list[i] if i < len(new_mn_list) else b'')
                self.vr_list.append(new_vr_list[i] if i < len(new_vr_list) else b'')
                self.st_list.append(new_st_list[i] if i < len(new_st_list) else b'')
                self.mode_list.append(new_mode_list[i] if new_mode_list and i < len(new_mode_list) else b'')
                self.detected_list.append(True)
                existing_mac_map[new_mac_str] = len(self.mac_list) - 1  # 이후 중복 방지
                self.logger.info(f"신규 장비 추가: {new_mac_str}")

        detected_count = sum(1 for d in self.detected_list if d)
        total_count = len(self.mac_list)
        self.logger.info(f"검색 결과 유지/갱신: 전체 {total_count}개 (현재 검색: {detected_count}개)")

    def update_scan_progress(self, current, total):
        """TCP multicast 진행률 업데이트"""
        percentage = int((current / total) * 100)
        self.statusbar.showMessage(f" TCP scan: {current}/{total} ({percentage}%)")
        self.pgbar.setFormat(" ")
        self.pgbar.setValue(percentage)
        self.pgbar.show()

    def handle_mixed_phase1(self, devnum):
        """Mixed search Phase 1 (UDP) 완료 처리"""
        # UDP phase elapsed time
        if hasattr(self, 'search_start_time') and self.search_start_time is not None:
            self.udp_elapsed = time.time() - self.search_start_time
            self.logger.info(f"Mixed Phase 1: {devnum} devices via UDP ({self.udp_elapsed:.2f}s)")
        else:
            self.udp_elapsed = 0
            self.logger.info(f"Mixed Phase 1: {devnum} devices via UDP")

        # UDP로 발견된 IP 추출
        found_ips = set()
        for data in self.wizmsghandler.rcv_list:
            ip = extract_ip_from_device_response(data)
            if ip:
                found_ips.add(ip)
                self.logger.debug(f"Found IP via UDP: {ip}")

        # UDP 결과 저장
        self.udp_results = {
            'mac_list': self.wizmsghandler.mac_list[:],
            'mn_list': self.wizmsghandler.mn_list[:],
            'vr_list': self.wizmsghandler.vr_list[:],
            'st_list': self.wizmsghandler.st_list[:],
            'rcv_list': self.wizmsghandler.rcv_list[:]
        }

        # 미발견 IP 계산
        missing_ips = [ip for ip in self.mixed_subnet_hosts if ip not in found_ips]

        if len(missing_ips) == 0:
            self.logger.info("Mixed Phase 1 complete, no additional IPs to scan")
            # Stop progress bar
            self.pgbar.setFormat(" ")
            self.pgbar.setValue(100)
            self.get_search_result(devnum)
            return

        self.logger.info(f"Mixed Phase 2: Scanning {len(missing_ips)} IPs via TCP")
        self.statusbar.showMessage(f" Phase 2: Scanning {len(missing_ips)} additional IPs via TCP...")

        # Record TCP phase start time
        self.tcp_start_time = time.time()

        # Phase 2: TCP scan
        port = int(self.mixed_port.text())
        cmd_list = self.wizmakecmd.presearch("FF:FF:FF:FF:FF:FF", self.code)

        self.tcp_scanner = TCPMulticastScanner(
            missing_ips, port, cmd_list, timeout=2, max_workers=15
        )
        self.tcp_scanner.search_result.connect(self.handle_mixed_phase2)
        self.tcp_scanner.progress_update.connect(self.update_scan_progress)
        self.tcp_scanner.start()

    def handle_mixed_phase2(self, tcp_devnum):
        """Mixed search Phase 2 (TCP) 완료 - 결과 병합"""
        # TCP phase elapsed time
        if hasattr(self, 'tcp_start_time') and self.tcp_start_time is not None:
            tcp_elapsed = time.time() - self.tcp_start_time
            self.logger.info(f"Mixed Phase 2: {tcp_devnum} devices via TCP ({tcp_elapsed:.2f}s)")
        else:
            tcp_elapsed = 0
            self.logger.info(f"Mixed Phase 2: {tcp_devnum} devices via TCP")

        # 결과 병합: UDP + TCP
        tcp_mac = self.tcp_scanner.mac_list if self.tcp_scanner else []
        tcp_mn = self.tcp_scanner.mn_list if self.tcp_scanner else []
        tcp_vr = self.tcp_scanner.vr_list if self.tcp_scanner else []
        tcp_st = self.tcp_scanner.st_list if self.tcp_scanner else []
        tcp_rcv = self.tcp_scanner.rcv_list if self.tcp_scanner else []

        self.mac_list = self.udp_results['mac_list'] + tcp_mac
        self.mn_list = self.udp_results['mn_list'] + tcp_mn
        self.vr_list = self.udp_results['vr_list'] + tcp_vr
        self.st_list = self.udp_results['st_list'] + tcp_st
        self.all_response = self.udp_results['rcv_list'] + tcp_rcv

        total_count = len(self.mac_list)
        self.logger.info(f"Mixed search complete: {total_count} total devices (UDP: {len(self.udp_results['mac_list'])}, TCP: {tcp_devnum})")

        # Stop progress bar
        self.pgbar.setFormat(" ")
        self.pgbar.setValue(100)

        # 검색 완료 처리
        self.searched_devnum = total_count
        self.searched_num.setText(str(self.searched_devnum))
        self.btn_search.setEnabled(True)

        if total_count == 0:
            self.logger.info("No device.")
        else:
            # 테이블에 장치 목록 표시
            self.list_device.setRowCount(len(self.mac_list))

            try:
                for i in range(0, len(self.mac_list)):
                    self.list_device.setItem(
                        i, 0, QTableWidgetItem(self.mac_list[i].decode('utf-8', errors='replace'))
                    )
                    self.list_device.setItem(
                        i, 1, QTableWidgetItem(self.mn_list[i].decode('utf-8', errors='replace'))
                    )
            except Exception as e:
                self.logger.error(e)

            # 테이블 크기 조정
            self.list_device.resizeColumnsToContents()
            self.list_device.resizeRowsToContents()
            self.list_device.horizontalHeader().setSectionResizeMode(2)
            self.list_device.verticalHeader().setSectionResizeMode(2)

        # Phase 3 이후 최종 업데이트됨
        system_time = None  # Phase 3 완료 후 search_each_dev()에서 계산
        if self.search_start_time is not None:
            total_elapsed = time.time() - self.search_start_time
            udp_time = getattr(self, 'udp_elapsed', 0)

            if system_time is not None:
                self.final_status_message = f" Done. {total_count} devices found (UDP: {udp_time:.2f}s, TCP: {tcp_elapsed:.2f}s, Total: {total_elapsed:.2f}s, System {system_time:.2f}s)"
            else:
                self.final_status_message = f" Done. {total_count} devices found (UDP: {udp_time:.2f}s, TCP: {tcp_elapsed:.2f}s, Total: {total_elapsed:.2f}s)"
            self.search_start_time = None
        else:
            if system_time is not None:
                self.final_status_message = f" Done. {total_count} devices found (System {system_time:.2f}s)"
            else:
                self.final_status_message = f" Done. {total_count} devices found"

        self.statusbar.showMessage(self.final_status_message)

        # 장치 목록 갱신
        self.get_dev_list()

    def get_dev_list(self):
        # basic_data = None
        self.searched_dev = []
        self.dev_data = {}

        # print(self.mac_list, self.mn_list, self.vr_list)
        if self.mac_list is not None:
            try:
                for i in range(len(self.mac_list)):
                    # self.searched_dev.append([self.mac_list[i].decode(), self.mn_list[i].decode(), self.vr_list[i].decode()])
                    # self.dev_data[self.mac_list[i].decode()] = [self.mn_list[i].decode(), self.vr_list[i].decode()]
                    self.searched_dev.append(
                        [
                            self.mac_list[i].decode('utf-8', errors='replace'),
                            self.mn_list[i].decode('utf-8', errors='replace'),
                            self.vr_list[i].decode('utf-8', errors='replace'),
                            self.st_list[i].decode('utf-8', errors='replace'),
                        ]
                    )
                    self.dev_data[self.mac_list[i].decode('utf-8', errors='replace')] = [
                        self.mn_list[i].decode('utf-8', errors='replace'),
                        self.vr_list[i].decode('utf-8', errors='replace'),
                        self.st_list[i].decode('utf-8', errors='replace'),
                    ]
            except Exception as e:
                self.logger.error(e)

            # print('get_dev_list()', self.searched_dev, self.dev_data)
            self.search_each_dev(self.searched_dev)
        else:
            self.logger.info("There is no device.")

    def dev_clicked(self, param=None, call_from=None):
        # dev_info = []
        # clicked_mac = ""
        # if 'WIZ750' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev:
            if self.generalTab.currentIndex() == 2:
                self.gpio_check()
                self.get_refresh_time()
        # for currentItem in self.list_device.selectedItems():
        # print('Click info:', currentItem, currentItem.row(), currentItem.column(), currentItem.text())
        # print('clicked', self.list_device.selectedItems()[0].text())
        # self.getdevinfo(currentItem.row())
        clicked_mac = self.list_device.selectedItems()[0].text()

        # print(f"1st caller={call_from},param={param}")
        self.get_clicked_devinfo(clicked_mac, call_from)

    def get_clicked_devinfo(self, macaddr, call_from=None):
        try:
            self.object_config()
        except Exception as e:
            print(f"ERROR:::get_clicked_devinfo:object_config:{e}")

        # print(f"2nd caller={call_from}")
        if self.curr_st == DeviceStatus.upgrade and call_from is None:
            self.show_msgbox(
                "Info",
                "DHCP has not completed. Retry after DHCP done or set a static IP",
                QMessageBox.Information,
            )
        # device profile(json format)
        if macaddr in self.dev_profile:
            dev_data = self.dev_profile[macaddr]
            print("clicked device information:", dev_data)
            print(f"[DEBUG] SD in dev_data: {'SD' in dev_data}")
            if 'SD' in dev_data:
                print(f"[DEBUG] SD value: '{dev_data['SD']}'")
            else:
                print("[DEBUG] SD not found in dev_data")
            if "ST" in dev_data and dev_data["ST"] in DeviceStatusMinimum:
                print("get_clicked_devinfo::I'm in!!")
                print(f"ch1_status={self.ch1_status}")
                print("get_clicked_devinfo::channel_tab set tab disabled")
                self.channel_tab.setEnabled(False)

            else:
                print("get_clicked_devinfo::NOT IN!! channel_tab set tab enabled")
                self.channel_tab.setEnabled(True)

            try:
                self.fill_devinfo(dev_data)
            except Exception as e:
                print(f"ERROR:::get_clicked_devinfo:fill_devinfo:{e}")
        else:
            if len(self.dev_profile) != self.searched_devnum:
                self.logger.info(
                    "[Warning] 검색된 장치의 수와 프로파일된 장치의 수가 다릅니다."
                )
            self.logger.info("[Warning] retry search")

    def remove_empty_value(self, data):
        # remove empty value
        for k, v in data.items():
            if not any([k, v]):
                del data[k]

    def set_localip_addr(self, ip):
        self.localip_addr = ip

    def set_text_command_mode_switch(self, data):
        if not data or len(data) < 6:
            self.logger.error(f"data for command SS = {data}, len={len(data)}")
            return
        self.at_hex1.setText(data[0:2])
        self.at_hex2.setText(data[2:4])
        self.at_hex3.setText(data[4:6])

    def set_debug_message_enable(self, data):
        # serial debug (dropbox)
        if int(data) < 2:
            self.serial_debug.setCurrentIndex(int(data))
        elif data == "4":
            self.serial_debug.setCurrentIndex(2)

    # Check: decode exception handling
    def fill_devinfo(self, dev_data):
        print("fill_devinfo", type(dev_data), dev_data)
        try:
            # device info (RO)
            if "MN" in dev_data:
                self.dev_type.setText(dev_data["MN"])
            if "VR" in dev_data:
                self.fw_version.setText(dev_data["VR"])
            # device info - channel 1
            if "ST" in dev_data:
                self.ch1_status.setText(dev_data["ST"])
            if "UN" in dev_data:
                self.ch1_uart_name.setText(dev_data["UN"])
            # Network - general
            if "IM" in dev_data:
                if dev_data["IM"] == "0":
                    self.ip_static.setChecked(True)
                elif dev_data["IM"] == "1":
                    self.ip_dhcp.setChecked(True)
            if "LI" in dev_data:
                self.localip.setText(dev_data["LI"])
                self.localip_addr = dev_data["LI"]
            if "SM" in dev_data:
                self.subnet.setText(dev_data["SM"])
            if "GW" in dev_data:
                self.gateway.setText(dev_data["GW"])
            if "DS" in dev_data:
                self.dns_addr.setText(dev_data["DS"])
            # TCP transmisstion retry count
            if "TR" in dev_data:
                if dev_data["TR"] == "0":
                    self.tcp_timeout.setText("8")
                else:
                    self.tcp_timeout.setText(dev_data["TR"])
            # etc - general
            # CP 값 검증 필요
            if "CP" in dev_data:
                self.enable_connect_pw.setChecked(int(dev_data["CP"]))
            if "NP" in dev_data:
                if dev_data["NP"] == " ":
                    self.connect_pw.setText(None)
                else:
                    self.connect_pw.setText(dev_data["NP"])
            # command mode (AT mode)
            # TE 값 검증 필요
            if "TE" in dev_data:
                self.at_enable.setChecked(int(dev_data["TE"]))
            if "SS" in dev_data:
                self.at_hex1.setText(dev_data["SS"][0:2])
                self.at_hex2.setText(dev_data["SS"][2:4])
                self.at_hex3.setText(dev_data["SS"][4:6])
            # search id code
            if "SP" in dev_data:
                if dev_data["SP"] == " ":
                    self.searchcode.clear()
                else:
                    self.searchcode.setText(dev_data["SP"])
            # Debug msg - for test
            if "DG" in dev_data:
                # serial debug (dropbox)
                if int(dev_data["DG"]) < 2:
                    self.serial_debug.setCurrentIndex(int(dev_data["DG"]))
                elif dev_data["DG"] == "4":
                    self.serial_debug.setCurrentIndex(2)
            # Network - channel 1
            if "OP" in dev_data:
                if dev_data["OP"] == "0":
                    self.ch1_tcpclient.setChecked(True)
                elif dev_data["OP"] == "1":
                    self.ch1_tcpserver.setChecked(True)
                elif dev_data["OP"] == "2":
                    self.ch1_tcpmixed.setChecked(True)
                elif dev_data["OP"] == "3":
                    self.ch1_udp.setChecked(True)
                elif dev_data["OP"] == "4":
                    self.ch1_ssl_tcpclient.setChecked(True)
                elif dev_data["OP"] == "5":
                    self.ch1_mqttclient.setChecked(True)
                elif dev_data["OP"] == "6":
                    self.ch1_mqtts_client.setChecked(True)
            if "LP" in dev_data:
                self.ch1_localport.setText(dev_data["LP"])
            if "RH" in dev_data:
                self.ch1_remoteip.setText(dev_data["RH"])
            if "RP" in dev_data:
                self.ch1_remoteport.setText(dev_data["RP"])
            # serial - channel 1
            if "BR" in dev_data:
                self.ch1_baud.setCurrentIndex(int(dev_data["BR"]))
            if "DB" in dev_data:
                if len(dev_data["DB"]) > 2:
                    pass
                else:
                    self.ch1_databit.setCurrentIndex(int(dev_data["DB"]))
            if "PR" in dev_data:
                self.ch1_parity.setCurrentIndex(int(dev_data["PR"]))
            if "SB" in dev_data:
                self.ch1_stopbit.setCurrentIndex(int(dev_data["SB"]))
            if "FL" in dev_data:
                self.ch1_flow.setCurrentIndex(int(dev_data["FL"]))
            if "PT" in dev_data:
                self.ch1_pack_time.setText(dev_data["PT"])
            if "PS" in dev_data:
                self.ch1_pack_size.setText(dev_data["PS"])
            if "PD" in dev_data:
                self.ch1_pack_char.setText(dev_data["PD"])
            # Send Data at Connection - W55RP20-S2E only (버전 1.1.8 이상)
            if "SD" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                print(f"[DEBUG] Loading SD data: '{dev_data['SD']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["SD"] == " ":
                    self.ch1_pack_char_3.clear()
                else:
                    self.ch1_pack_char_3.setText(dev_data["SD"])
            # Send Data at Disconnection - W55RP20-S2E only (버전 1.1.8 이상)
            if "DD" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                print(f"[DEBUG] Loading DD data: '{dev_data['DD']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["DD"] == " ":
                    self.ch1_pack_char_4.clear()
                else:
                    self.ch1_pack_char_4.setText(dev_data["DD"])
            # Ethernet Data Connection Condition - W55RP20-S2E, W232N, IP20 (버전 1.1.8 이상)
            if "SE" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                print(f"[DEBUG] Loading SE data: '{dev_data['SE']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["SE"] == " ":
                    self.ch1_pack_char_5.clear()
                else:
                    self.ch1_pack_char_5.setText(dev_data["SE"])
            # Inactive timer - channel 1
            if "IT" in dev_data:
                self.ch1_inact_timer.setText(dev_data["IT"])
            # TCP keep alive - channel 1
            if "KA" in dev_data:
                if dev_data["KA"] == "0":
                    self.ch1_keepalive_enable.setChecked(False)
                elif dev_data["KA"] == "1":
                    self.ch1_keepalive_enable.setChecked(True)
            if "KI" in dev_data:
                self.ch1_keepalive_initial.setText(dev_data["KI"])
            if "KE" in dev_data:
                self.ch1_keepalive_retry.setText(dev_data["KE"])
            # reconnection - channel 1
            if "RI" in dev_data:
                self.ch1_reconnection.setText(dev_data["RI"])

            # Status pin ( status_phy / status_dtr || status_tcpst / status_dsr )
            if "SC" in dev_data:
                if dev_data["SC"][0:1] == "0":
                    self.status_phy.setChecked(True)
                    self.checkbox_enable_dtr.setChecked(False)
                elif dev_data["SC"][0:1] == "1":
                    self.status_dtr.setChecked(True)
                    self.checkbox_enable_dtr.setChecked(True)
                if dev_data["SC"][1:2] == "0":
                    self.status_tcpst.setChecked(True)
                    self.checkbox_enable_dsr.setChecked(False)
                elif dev_data["SC"][1:2] == "1":
                    self.status_dsr.setChecked(True)
                    self.checkbox_enable_dsr.setChecked(True)

            # Modbus (PO/MB depending on device)
            desired_key = self._modbus_param_key()
            fallback_key = "MB" if desired_key == "PO" else "PO"
            for modbus_key in (desired_key, fallback_key):
                if modbus_key in dev_data and dev_data[modbus_key] != "":
                    try:
                        modbus_val = int(dev_data[modbus_key])
                        self.modbus_protocol.setCurrentIndex(modbus_val)
                        self.logger.debug(
                            f"Modbus protocol option ({modbus_key}) set to {modbus_val}"
                        )
                        break
                    except Exception as ex:
                        self.logger.error(
                            f"Error parsing {modbus_key}: {dev_data[modbus_key]} -> {ex}"
                        )

            # # Channel 2 config (For two Port device)
            if self.curr_dev in TWO_PORT_DEV:
                # device info - channel 2
                if "QS" in dev_data:
                    self.ch2_status.setText(dev_data["QS"])
                if "EN" in dev_data:
                    self.ch2_uart_name.setText(dev_data["EN"])
                # Network - channel 2
                if "QO" in dev_data:
                    if dev_data["QO"] == "0":
                        self.ch2_tcpclient.setChecked(True)
                    elif dev_data["QO"] == "1":
                        self.ch2_tcpserver.setChecked(True)
                    elif dev_data["QO"] == "2":
                        self.ch2_tcpmixed.setChecked(True)
                    elif dev_data["QO"] == "3":
                        self.ch2_udp.setChecked(True)
                if "QL" in dev_data:
                    self.ch2_localport.setText(dev_data["QL"])
                if "QH" in dev_data:
                    self.ch2_remoteip.setText(dev_data["QH"])
                if "QP" in dev_data:
                    self.ch2_remoteport.setText(dev_data["QP"])
                # serial - channel 2
                if "EB" in dev_data:
                    if len(dev_data["EB"]) > 4:
                        pass
                    else:
                        self.ch2_baud.setCurrentIndex(int(dev_data["EB"]))

                if "ED" in dev_data:
                    if len(dev_data["ED"]) > 2:
                        pass
                    else:
                        self.ch2_databit.setCurrentIndex(int(dev_data["ED"]))
                if "EP" in dev_data:
                    self.ch2_parity.setCurrentIndex(int(dev_data["EP"]))
                if "ES" in dev_data:
                    self.ch2_stopbit.setCurrentIndex(int(dev_data["ES"]))
                if "EF" in dev_data:
                    if len(dev_data["EF"]) > 2:
                        pass
                    else:
                        self.ch2_flow.setCurrentIndex(int(dev_data["EF"]))
                if "NT" in dev_data:
                    self.ch2_pack_time.setText(dev_data["NT"])
                if "NS" in dev_data:
                    self.ch2_pack_size.setText(dev_data["NS"])
                if "ND" in dev_data:
                    if len(dev_data["ND"]) > 2:
                        pass
                    else:
                        self.ch2_pack_char.setText(dev_data["ND"])
                # Inactive timer - channel 2
                if "RV" in dev_data:
                    self.ch2_inact_timer.setText(dev_data["RV"])
                # TCP keep alive - channel 2
                if "RA" in dev_data:
                    if dev_data["RA"] == "0":
                        self.ch2_keepalive_enable.setChecked(False)
                    elif dev_data["RA"] == "1":
                        self.ch2_keepalive_enable.setChecked(True)
                if "RS" in dev_data:
                    self.ch2_keepalive_initial.setText(dev_data["RS"])
                if "RE" in dev_data:
                    self.ch2_keepalive_retry.setText(dev_data["RE"])
                # reconnection - channel 2
                if "RR" in dev_data:
                    self.ch2_reconnection.setText(dev_data["RR"])

            elif self.curr_dev in SECURITY_TWO_PORT_DEV:
                self.lineedit_ch1_ssl_recv_timeout_2.setText("0")
                self.modbus_protocol_2.setCurrentIndex(0)
                self.ch1_pack_char_8.clear()
                self.ch1_pack_char_9.clear()
                self.ch1_pack_char_7.clear()

                if "QS" in dev_data:
                    self.ch2_status.setText(dev_data["QS"])
                if "EN" in dev_data:
                    self.ch2_uart_name.setText(dev_data["EN"])

                if "AO" in dev_data:
                    ao_val = dev_data["AO"]
                    if ao_val == "0":
                        self.ch2_tcpclient.setChecked(True)
                    elif ao_val == "1":
                        self.ch2_tcpserver.setChecked(True)
                    elif ao_val == "2":
                        self.ch2_tcpmixed.setChecked(True)
                    elif ao_val == "3":
                        self.ch2_udp.setChecked(True)
                    elif ao_val == "4":
                        self.ch2_ssl_tcpclient.setChecked(True)
                    elif ao_val == "5":
                        self.ch2_mqttclient.setChecked(True)
                    elif ao_val == "6":
                        self.ch2_mqtts_client.setChecked(True)

                if "QL" in dev_data:
                    self.ch2_localport.setText(dev_data["QL"])
                if "QH" in dev_data:
                    self.ch2_remoteip.setText(dev_data["QH"])
                if "AP" in dev_data:
                    self.ch2_remoteport.setText(dev_data["AP"])

                if "EB" in dev_data and len(dev_data["EB"]) <= 4:
                    self.ch2_baud.setCurrentIndex(int(dev_data["EB"]))
                if "ED" in dev_data and len(dev_data["ED"]) <= 2:
                    self.ch2_databit.setCurrentIndex(int(dev_data["ED"]))
                if "EP" in dev_data:
                    self.ch2_parity.setCurrentIndex(int(dev_data["EP"]))
                if "ES" in dev_data:
                    self.ch2_stopbit.setCurrentIndex(int(dev_data["ES"]))
                if "EF" in dev_data and len(dev_data["EF"]) <= 2:
                    self.ch2_flow.setCurrentIndex(int(dev_data["EF"]))

                if "AT" in dev_data:
                    self.ch2_pack_time.setText(dev_data["AT"])
                if "NS" in dev_data:
                    self.ch2_pack_size.setText(dev_data["NS"])
                if "ND" in dev_data and len(dev_data["ND"]) <= 2:
                    self.ch2_pack_char.setText(dev_data["ND"])

                if "RV" in dev_data:
                    self.ch2_inact_timer.setText(dev_data["RV"])

                if "RA" in dev_data:
                    self.ch2_keepalive_enable.setChecked(dev_data["RA"] == "1")
                if "RS" in dev_data:
                    self.ch2_keepalive_initial.setText(dev_data["RS"])
                if "RE" in dev_data:
                    self.ch2_keepalive_retry.setText(dev_data["RE"])
                if "RR" in dev_data:
                    self.ch2_reconnection.setText(dev_data["RR"])

                # RO: SSL recv timeout for channel 2 (2-channel devices only)
                if "RO" in dev_data and self.curr_dev in SECURITY_TWO_PORT_DEV:
                    self.lineedit_ch1_ssl_recv_timeout_2.setText(dev_data["RO"])

                if "EO" in dev_data:
                    try:
                        self.modbus_protocol_2.setCurrentIndex(int(dev_data["EO"]))
                    except Exception as ex:
                        self.logger.error(f"Error parsing EO: {dev_data['EO']} -> {ex}")

                if "RD" in dev_data:
                    if dev_data["RD"] == " ":
                        self.ch1_pack_char_8.clear()
                    else:
                        self.ch1_pack_char_8.setText(dev_data["RD"])

                if "RF" in dev_data:
                    if dev_data["RF"] == " ":
                        self.ch1_pack_char_9.clear()
                    else:
                        self.ch1_pack_char_9.setText(dev_data["RF"])

                if "EE" in dev_data:
                    if dev_data["EE"] == " ":
                        self.ch1_pack_char_7.clear()
                    else:
                        self.ch1_pack_char_7.setText(dev_data["EE"])

            # SECURITY_TWO_PORT_DEV도 SECURITY_DEVICE에 속하므로 elif가 아닌 if 사용
            if (
                self.curr_dev in SECURITY_DEVICE
                and "ST" in dev_data
                and dev_data["ST"] not in DeviceStatusMinimum
            ):
                """
                Security device options
                """
                # New options for Security devices
                # MQTT options
                if "QU" in dev_data:
                    if dev_data["QU"] == " ":
                        self.lineedit_mqtt_username.clear()
                    else:
                        self.lineedit_mqtt_username.setText(dev_data["QU"])
                if "QP" in dev_data:
                    if dev_data["QP"] == " ":
                        self.lineedit_mqtt_password.clear()
                    else:
                        self.lineedit_mqtt_password.setText(dev_data["QP"])
                if "QC" in dev_data:
                    if dev_data["QC"] == " ":
                        self.lineedit_mqtt_clientid.clear()
                    else:
                        self.lineedit_mqtt_clientid.setText(dev_data["QC"])
                if "QK" in dev_data:
                    if dev_data["QK"] == " ":
                        self.lineedit_mqtt_keepalive.clear()
                    else:
                        self.lineedit_mqtt_keepalive.setText(dev_data["QK"])
                if "PU" in dev_data:
                    if dev_data["PU"] == " ":
                        self.lineedit_mqtt_pubtopic.clear()
                    else:
                        self.lineedit_mqtt_pubtopic.setText(dev_data["PU"])

                # MQTT subtopics
                if "U0" in dev_data:
                    if dev_data["U0"] == " ":
                        self.lineedit_mqtt_subtopic_0.clear()
                    else:
                        self.lineedit_mqtt_subtopic_0.setText(dev_data["U0"])
                if "U1" in dev_data:
                    if dev_data["U1"] == " ":
                        self.lineedit_mqtt_subtopic_1.clear()
                    else:
                        self.lineedit_mqtt_subtopic_1.setText(dev_data["U1"])
                if "U2" in dev_data:
                    if dev_data["U2"] == " ":
                        self.lineedit_mqtt_subtopic_2.clear()
                    else:
                        self.lineedit_mqtt_subtopic_2.setText(dev_data["U2"])
                if "QO" in dev_data and dev_data["QO"].isdigit():
                    self.combobox_mqtt_qos.setCurrentIndex(int(dev_data["QO"]))
                # Root CA options
                if "RC" in dev_data and dev_data["RC"].isdigit():
                    self.combobox_rootca_option.setCurrentIndex(int(dev_data["RC"]))
                # Client cert options
                if "CE" in dev_data:
                    if dev_data["CE"] == "1":
                        self.checkbox_enable_client_cert.setChecked(True)
                    elif dev_data["CE"] == "0":
                        self.checkbox_enable_client_cert.setChecked(False)
                # Current flash bank (RO)
                if "BA" in dev_data and dev_data["BA"].isdigit():
                    self.combobox_current_bank.setCurrentIndex(int(dev_data["BA"]))
                # SSL Timeout
                if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
                    # SO: SSL recv timeout for channel 1 (all W55RP20 family)
                    if "SO" in dev_data:
                        self.lineedit_ch1_ssl_recv_timeout.setText(dev_data["SO"])

            self.object_config()
        except Exception as e:
            self.logger.error(e)
            self.msg_error("Get device information error {}".format(e))

    def msg_error(self, error):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setFont(self.midfont)
        msgbox.setWindowTitle("An error has occured")
        text = (
            "<div style=text-align:center>Unexcepted error has occurred."
            + "<br>Please report the issue with detail message."
            + "<br><a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'>Github Issue page</a></div>"
        )
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
            setcmd["LI"] = self.localip.text()
            setcmd["SM"] = self.subnet.text()
            setcmd["GW"] = self.gateway.text()
            if self.ip_static.isChecked():
                setcmd["IM"] = "0"
            elif self.ip_dhcp.isChecked():
                setcmd["IM"] = "1"
            setcmd["DS"] = self.dns_addr.text()
            # boot 명령에 SP 도 포함되어야 함.
            # search id code: max 8 bytes
            if len(self.searchcode.text()) == 0:
                setcmd["SP"] = " "
            else:
                setcmd["SP"] = self.searchcode.text()
            # 장비 상태가 BOOT 이면 다른 내용은 저장하지 않음.
            # @TODO: GUI 도 막아야 함
            if self.curr_st in DeviceStatusMinimum:
                logger.debug(f"setcmd: {setcmd}")
                return setcmd
            # etc - general
            if self.enable_connect_pw.isChecked():
                setcmd["CP"] = "1"
                setcmd["NP"] = self.connect_pw.text()
            else:
                setcmd["CP"] = "0"
            # command mode (AT mode)
            if self.at_enable.isChecked():
                setcmd["TE"] = "1"
                setcmd["SS"] = (
                    self.at_hex1.text() + self.at_hex2.text() + self.at_hex3.text()
                )
            elif not self.at_enable.isChecked():
                setcmd["TE"] = "0"
            # Debug msg
            if self.serial_debug.currentIndex() == 2:
                setcmd["DG"] = "4"
            else:
                setcmd["DG"] = str(self.serial_debug.currentIndex())

            # Network - channel 1
            if self.curr_dev in SECURITY_DEVICE:
                if self.ch1_tcpclient.isChecked():
                    setcmd["OP"] = "0"
                elif self.ch1_tcpserver.isChecked():
                    setcmd["OP"] = "1"
                elif self.ch1_tcpmixed.isChecked():
                    setcmd["OP"] = "2"
                elif self.ch1_udp.isChecked():
                    setcmd["OP"] = "3"
                elif self.ch1_ssl_tcpclient.isChecked():
                    setcmd["OP"] = "4"
                elif self.ch1_mqttclient.isChecked():
                    setcmd["OP"] = "5"
                elif self.ch1_mqtts_client.isChecked():
                    setcmd["OP"] = "6"
            else:
                if self.ch1_tcpclient.isChecked():
                    setcmd["OP"] = "0"
                elif self.ch1_tcpserver.isChecked():
                    setcmd["OP"] = "1"
                elif self.ch1_tcpmixed.isChecked():
                    setcmd["OP"] = "2"
                elif self.ch1_udp.isChecked():
                    setcmd["OP"] = "3"
            setcmd["LP"] = self.ch1_localport.text()
            setcmd["RH"] = self.ch1_remoteip.text()
            setcmd["RP"] = self.ch1_remoteport.text()
            # serial - channel 1
            setcmd["BR"] = str(self.ch1_baud.currentIndex())
            setcmd["DB"] = str(self.ch1_databit.currentIndex())
            setcmd["PR"] = str(self.ch1_parity.currentIndex())
            setcmd["SB"] = str(self.ch1_stopbit.currentIndex())
            setcmd["FL"] = str(self.ch1_flow.currentIndex())
            # 문맥으로 보면 modbus_protocol.isEnabled() 로 처리하는게 맞지만 항상 False 가 나와서 모델&버전 비교로 대체 #36
            if self._modbus_supported():
                modbus_key = self._modbus_param_key()
                print(
                    f"set {modbus_key} valid, self.curr_dev={self.curr_dev}, self.curr_ver={self.curr_ver}"
                )
                setcmd[modbus_key] = str(self.modbus_protocol.currentIndex())

            setcmd["PT"] = self.ch1_pack_time.text()
            setcmd["PS"] = self.ch1_pack_size.text()
            setcmd["PD"] = self.ch1_pack_char.text()
            # Send Data at Connection - W55RP20-S2E, W232N, IP20 (버전 1.1.8 이상)
            if self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                sd_data = self.ch1_pack_char_3.text()
                # 최대 30글자로 제한
                if len(sd_data) > 30:
                    sd_data = sd_data[:30]
                    self.ch1_pack_char_3.setText(sd_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                print(f"[DEBUG] Saving SD data: '{sd_data}'")
                setcmd["SD"] = sd_data if sd_data else " "
                
                # Send Data at Disconnection - W55RP20-S2E, W232N, IP20
                dd_data = self.ch1_pack_char_4.text()
                # 최대 30글자로 제한
                if len(dd_data) > 30:
                    dd_data = dd_data[:30]
                    self.ch1_pack_char_4.setText(dd_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                print(f"[DEBUG] Saving DD data: '{dd_data}'")
                setcmd["DD"] = dd_data if dd_data else " "
                
                # Ethernet Data Connection Condition - W55RP20-S2E, W232N, IP20
                se_data = self.ch1_pack_char_5.text()
                # 최대 30글자로 제한
                if len(se_data) > 30:
                    se_data = se_data[:30]
                    self.ch1_pack_char_5.setText(se_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                print(f"[DEBUG] Saving SE data: '{se_data}'")
                setcmd["SE"] = se_data if se_data else " "
            # Inactive timer - channel 1
            setcmd["IT"] = self.ch1_inact_timer.text()
            # TCP keep alive - channel 1
            if self.ch1_keepalive_enable.isChecked():
                setcmd["KA"] = "1"
                setcmd["KI"] = self.ch1_keepalive_initial.text()
                setcmd["KE"] = self.ch1_keepalive_retry.text()
            else:
                setcmd["KA"] = "0"
            setcmd["KI"] = self.ch1_keepalive_initial.text()
            setcmd["KE"] = self.ch1_keepalive_retry.text()
            # reconnection - channel 1
            setcmd["RI"] = self.ch1_reconnection.text()
            # Status pin
            if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
                pass
            else:
                # initial value
                upper_val = "0"
                lower_val = "0"
                if self.curr_dev in SECURITY_DEVICE:
                    if self.checkbox_enable_dtr.isChecked():
                        upper_val = "1"
                    else:
                        upper_val = "0"
                    if self.checkbox_enable_dsr.isChecked():
                        lower_val = "1"
                    else:
                        lower_val = "0"
                else:
                    if self.status_phy.isChecked():
                        upper_val = "0"
                    elif self.status_dtr.isChecked():
                        upper_val = "1"
                    if self.status_tcpst.isChecked():
                        lower_val = "0"
                    elif self.status_dsr.isChecked():
                        lower_val = "1"
                setcmd["SC"] = upper_val + lower_val

            if "WIZ752" in self.curr_dev:
                pass
            else:
                if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev:
                    # Check version
                    if version_compare("1.2.0", self.curr_ver) <= 0:
                        setcmd["TR"] = self.tcp_timeout.text()
                    else:
                        pass
                else:
                    setcmd["TR"] = self.tcp_timeout.text()

            # Expansion GPIO
            if self.curr_st in DeviceStatusMinimum:
                pass
            else:
                if "WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev:
                    setcmd["CA"] = str(self.gpioa_config.currentIndex())
                    setcmd["CB"] = str(self.gpiob_config.currentIndex())
                    setcmd["CC"] = str(self.gpioc_config.currentIndex())
                    setcmd["CD"] = str(self.gpiod_config.currentIndex())
                    if self.gpioa_config.currentIndex() == 1:
                        setcmd["GA"] = str(self.gpioa_set.currentIndex())
                    if self.gpiob_config.currentIndex() == 1:
                        setcmd["GB"] = str(self.gpiob_set.currentIndex())
                    if self.gpioc_config.currentIndex() == 1:
                        setcmd["GC"] = str(self.gpioc_set.currentIndex())
                    if self.gpiod_config.currentIndex() == 1:
                        setcmd["GD"] = str(self.gpiod_set.currentIndex())
                elif "WIZ752" in self.curr_dev:
                    pass

            # for channel 2
            if self.curr_dev in TWO_PORT_DEV or "WIZ752" in self.curr_dev:
                # device info - channel 2
                if self.ch2_tcpclient.isChecked():
                    setcmd["QO"] = "0"
                elif self.ch2_tcpserver.isChecked():
                    setcmd["QO"] = "1"
                elif self.ch2_tcpmixed.isChecked():
                    setcmd["QO"] = "2"
                elif self.ch2_udp.isChecked():
                    setcmd["QO"] = "3"
                setcmd["QL"] = self.ch2_localport.text()
                setcmd["QH"] = self.ch2_remoteip.text()
                setcmd["QP"] = self.ch2_remoteport.text()
                # serial - channel 2
                setcmd["EB"] = str(self.ch2_baud.currentIndex())
                setcmd["ED"] = str(self.ch2_databit.currentIndex())
                setcmd["EP"] = str(self.ch2_parity.currentIndex())
                setcmd["ES"] = str(self.ch2_stopbit.currentIndex())
                setcmd["EF"] = str(self.ch2_flow.currentIndex())
                setcmd["NT"] = self.ch2_pack_time.text()
                setcmd["NS"] = self.ch2_pack_size.text()
                setcmd["ND"] = self.ch2_pack_char.text()
                # Inactive timer - channel 2
                setcmd["RV"] = self.ch2_inact_timer.text()
                # TCP keep alive - channel 2
                if self.ch2_keepalive_enable.isChecked():
                    setcmd["RA"] = "1"
                    setcmd["RS"] = self.ch2_keepalive_initial.text()
                    setcmd["RE"] = self.ch2_keepalive_retry.text()
                else:
                    setcmd["RA"] = "0"
                # reconnection - channel 2
                setcmd["RR"] = self.ch2_reconnection.text()
            elif self.curr_dev in SECURITY_TWO_PORT_DEV:
                if self.ch2_tcpclient.isChecked():
                    setcmd["AO"] = "0"
                elif self.ch2_tcpserver.isChecked():
                    setcmd["AO"] = "1"
                elif self.ch2_tcpmixed.isChecked():
                    setcmd["AO"] = "2"
                elif self.ch2_udp.isChecked():
                    setcmd["AO"] = "3"
                elif self.ch2_ssl_tcpclient.isChecked():
                    setcmd["AO"] = "4"
                elif self.ch2_mqttclient.isChecked():
                    setcmd["AO"] = "5"
                elif self.ch2_mqtts_client.isChecked():
                    setcmd["AO"] = "6"

                setcmd["QL"] = self.ch2_localport.text()
                setcmd["QH"] = self.ch2_remoteip.text()
                setcmd["AP"] = self.ch2_remoteport.text()

                setcmd["EB"] = str(self.ch2_baud.currentIndex())
                setcmd["ED"] = str(self.ch2_databit.currentIndex())
                setcmd["EP"] = str(self.ch2_parity.currentIndex())
                setcmd["ES"] = str(self.ch2_stopbit.currentIndex())
                setcmd["EF"] = str(self.ch2_flow.currentIndex())

                setcmd["AT"] = self.ch2_pack_time.text()
                setcmd["NS"] = self.ch2_pack_size.text()
                setcmd["ND"] = self.ch2_pack_char.text()

                setcmd["RV"] = self.ch2_inact_timer.text()

                if self.ch2_keepalive_enable.isChecked():
                    setcmd["RA"] = "1"
                    setcmd["RS"] = self.ch2_keepalive_initial.text()
                    setcmd["RE"] = self.ch2_keepalive_retry.text()
                else:
                    setcmd["RA"] = "0"

                setcmd["RR"] = self.ch2_reconnection.text()

                # RO: SSL recv timeout for channel 2 (2-channel devices only)
                if self.curr_dev in SECURITY_TWO_PORT_DEV:
                    setcmd["RO"] = self.lineedit_ch1_ssl_recv_timeout_2.text()
                setcmd["EO"] = str(self.modbus_protocol_2.currentIndex())

                rd_data = self.ch1_pack_char_8.text()
                if len(rd_data) > 30:
                    rd_data = rd_data[:30]
                    self.ch1_pack_char_8.setText(rd_data)
                setcmd["RD"] = rd_data if rd_data else " "

                rf_data = self.ch1_pack_char_9.text()
                if len(rf_data) > 30:
                    rf_data = rf_data[:30]
                    self.ch1_pack_char_9.setText(rf_data)
                setcmd["RF"] = rf_data if rf_data else " "

                ee_data = self.ch1_pack_char_7.text()
                if len(ee_data) > 30:
                    ee_data = ee_data[:30]
                    self.ch1_pack_char_7.setText(ee_data)
                setcmd["EE"] = ee_data if ee_data else " "

            if self.curr_dev in SECURITY_DEVICE:
                # New options for WIZ510SSL (Security devices)
                # MQTT options
                setcmd["QU"] = (
                    self.lineedit_mqtt_username.text()
                    if self.lineedit_mqtt_username.text()
                    else " "
                )
                setcmd["QP"] = (
                    self.lineedit_mqtt_password.text()
                    if self.lineedit_mqtt_password.text()
                    else " "
                )
                setcmd["QC"] = (
                    self.lineedit_mqtt_clientid.text()
                    if self.lineedit_mqtt_clientid.text()
                    else " "
                )
                setcmd["QK"] = (
                    self.lineedit_mqtt_keepalive.text()
                    if self.lineedit_mqtt_keepalive.text()
                    else " "
                )
                setcmd["PU"] = (
                    self.lineedit_mqtt_pubtopic.text()
                    if self.lineedit_mqtt_pubtopic.text()
                    else " "
                )
                setcmd["U0"] = (
                    self.lineedit_mqtt_subtopic_0.text()
                    if self.lineedit_mqtt_subtopic_0.text()
                    else " "
                )
                setcmd["U1"] = (
                    self.lineedit_mqtt_subtopic_1.text()
                    if self.lineedit_mqtt_subtopic_1.text()
                    else " "
                )
                setcmd["U2"] = (
                    self.lineedit_mqtt_subtopic_2.text()
                    if self.lineedit_mqtt_subtopic_2.text()
                    else " "
                )
                setcmd["QO"] = str(self.combobox_mqtt_qos.currentIndex())
                # Root CA options
                setcmd["RC"] = str(self.combobox_rootca_option.currentIndex())
                # Client cert options
                if self.checkbox_enable_client_cert.isChecked():
                    setcmd["CE"] = "1"
                    # client cert password (will be added)
                    # setcmd[''] = self.lineedit_client_cert_pw.text()
                else:
                    setcmd["CE"] = "0"
                # 2022.05.10 add option
                if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
                    # Bank setting
                    # setcmd['UF'] = str(self.combobox_current_bank.currentIndex())
                    # Add ssl timeout option
                    setcmd["SO"] = self.lineedit_ch1_ssl_recv_timeout.text()

        except Exception as e:
            self.logger.error(e)

        logger.debug(f"setcmd: {setcmd}")
        return setcmd

    def do_setting(self):
        self.disable_object()

        self.set_reponse = None

        self.sock_close()

        if len(self.list_device.selectedItems()) == 0:
            # self.logger.info('Device is not selected')
            self.show_msgbox("Warning", "Device is not selected.", QMessageBox.Warning)
            # self.msg_dev_not_selected()
        else:
            self.statusbar.showMessage(" Setting device...")
            # matching set command
            setcmd = self.get_object_value()
            # self.selected_devinfo()

            # Update cmdset
            self.cmdset.get_cmdset(self.curr_dev, self.curr_st, self.curr_ver)
            self.logger.info(f"Device setting: {self.curr_dev}")
            # Parameter validity check
            invalid_flag = 0
            setcmd_cmd = list(setcmd.keys())
            print(f"do_setting::setcmd={setcmd}")
            for i in range(len(setcmd)):
                if (
                    self.cmdset.isvalidparameter(
                        setcmd_cmd[i], setcmd.get(setcmd_cmd[i])
                    )
                    is False
                ):
                    self.logger.warning(
                        "Invalid parameter: %s %s"
                        % (setcmd_cmd[i], setcmd.get(setcmd_cmd[i]))
                    )
                    self.msg_invalid(setcmd.get(setcmd_cmd[i]))
                    invalid_flag += 1

            if invalid_flag > 0:
                self.logger.info(f"Setting: invalid flag: {invalid_flag}")
            elif invalid_flag == 0:
                if len(self.searchcode_input.text()) == 0:
                    self.code = " "
                else:
                    self.code = self.searchcode_input.text()

                cmd_list = self.wizmakecmd.setcommand(
                    self.curr_mac,
                    self.code,
                    self.encoded_setting_pw,
                    list(setcmd.keys()),
                    list(setcmd.values()),
                    self.curr_dev,
                    self.curr_ver,
                    self.curr_st,
                )
                # self.logger.debug(cmd_list)

                # socket config
                self.socket_config()

                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, "tcp", Opcode.OP_SETCOMMAND, 2
                    )
                else:
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, "udp", Opcode.OP_SETCOMMAND, 2
                    )
                self.wizmsghandler.set_result.connect(self.get_setting_result)
                self.wizmsghandler.start()

    def get_setting_result(self, resp_len):
        prev_channel_tab_index = self.channel_tab.currentIndex()
        set_result = {}

        if resp_len > 100:
            self.statusbar.showMessage(" Set device complete!")

            # complete pop-up
            self.msg_set_success()

            if self.isConnected and self.unicast_ip.isChecked():
                self.logger.info("close socket")
                self.conf_sock.shutdown()

            # get setting result
            self.set_reponse = self.wizmsghandler.rcv_list[0]

            # cmdsets = self.set_reponse.splitlines()
            cmdsets = self.set_reponse.split(b"\r\n")

            for i in range(len(cmdsets)):
                if cmdsets[i][:2] == b"MA":
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

            # 장비 정보 갱신용으로 부르는 것 같은 데 이 때문에 dev_clicked 에 넣은 메시지 창이 2번 뜸
            self.dev_clicked(call_from=sys._getframe().f_code.co_name)
        elif resp_len == -1:
            self.logger.warning("Setting: no response from device.")
            self.statusbar.showMessage(" Setting: no response from device.")
            self.msg_set_error()
        elif resp_len == -3:
            self.logger.warning("Setting: wrong password")
            self.statusbar.showMessage(" Setting: wrong password.")
            self.msg_setting_pw_error()
        elif resp_len < 50:
            self.logger.warning(f"Warning: setting is did not well. resp_len={resp_len}")
            # 디버깅: 실제 수신된 응답 내용 로깅
            try:
                if hasattr(self, 'wizmsghandler'):
                    self.logger.warning(f"[DEBUG] wizmsghandler exists: {type(self.wizmsghandler)}")
                    if hasattr(self.wizmsghandler, 'rcv_list'):
                        self.logger.warning(f"[DEBUG] rcv_list exists, length: {len(self.wizmsghandler.rcv_list)}")
                        if len(self.wizmsghandler.rcv_list) > 0:
                            raw_response = self.wizmsghandler.rcv_list[0]
                            self.logger.warning(f"[DEBUG] Raw response (bytes): {raw_response}")
                            self.logger.warning(f"[DEBUG] Raw response (hex): {raw_response.hex()}")
                            try:
                                decoded = raw_response.decode('utf-8', errors='replace')
                                self.logger.warning(f"[DEBUG] Decoded response: {decoded}")
                            except Exception as e:
                                self.logger.warning(f"[DEBUG] Failed to decode response: {e}")
                        else:
                            self.logger.warning("[DEBUG] rcv_list is empty")
                    else:
                        self.logger.warning("[DEBUG] wizmsghandler has no rcv_list attribute")
                else:
                    self.logger.warning("[DEBUG] wizmsghandler does not exist")
            except Exception as e:
                self.logger.error(f"[DEBUG] Error while logging response: {e}")
            self.statusbar.showMessage(" Warning: setting is did not well.")
            self.msg_set_warning()

        self.object_config()

        if 0 <= prev_channel_tab_index < self.channel_tab.count():
            self.channel_tab.setCurrentIndex(prev_channel_tab_index)

    def selected_devinfo(self):
        # 선택된 장치 정보 get
        selected_row = -1
        for currentItem in self.list_device.selectedItems():
            # _dev_name = currentItem.text()
            # currentItem = <class 'PyQt5.QtWidgets.QTableWidgetItem'>
            # 현재 0번 열은 맥주소이고 1번 열은 장치명
            if currentItem.column() == 0:
                self.curr_mac = currentItem.text()
                self.curr_ver = self.dev_data[self.curr_mac][1]
                self.curr_st = self.dev_data[self.curr_mac][2]
                selected_row = currentItem.row()
                # print('current device:', self.curr_mac, self.curr_ver, self.curr_st)
            elif currentItem.column() == 1:
                self.curr_dev = currentItem.text()
                selected_row = currentItem.row()
                # print('current dev name:', self.curr_dev)
        
        # 행이 선택되었는데 curr_dev가 설정되지 않은 경우, 해당 행의 1번 열에서 장치명 가져오기
        if selected_row >= 0 and self.curr_dev is None:
            dev_name_item = self.list_device.item(selected_row, 1)
            if dev_name_item:
                self.curr_dev = dev_name_item.text()
        
        self.statusbar.showMessage(
            " Current device [%s : %s], %s"
            % (self.curr_mac, self.curr_dev, self.curr_ver)
        )

    def update_result(self, result):
        if result < 0:
            text = "Firmware update failed. "
            if result == -1:
                text += "Please check the device's status."
            elif result == -2:
                text += "No response from device."
            # self.show_msgbox("Error", text, QMessageBox.Critical)
            self.statusbar.showMessage(text)
        elif result > 0:
            self.statusbar.showMessage(" Firmware update complete!")
            self.logger.info("FW Update OK")
            self.pgbar.setValue(8)
            self.msg_upload_success()
        if self.isConnected and self.unicast_ip.isChecked():
            self.conf_sock.shutdown()
        self.pgbar.hide()

    def update_error(self, error):
        self.logger.error(f"Firmware update error: {error}")

        text = ""
        if error == -1:
            text = " Firmware update failed. No response from device."
            self.statusbar.showMessage(text)
            self.show_msgbox("Error", text, QMessageBox.Critical)
            # self.msg_upload_failed()
        elif error == -2:
            text = " Firmware update: Network connection failed."
            self.statusbar.showMessage(text)
            self.msg_connection_failed()
        elif error == -3:
            text = " Firmware update error."
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
                QMessageBox.Critical,
            )
        elif result > 0:
            self.statusbar.showMessage(" Certificate update complete!")
            self.logger.info("Certificate Update OK")
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
            self.statusbar.showMessage(
                " Certificate update failed. No response from device."
            )
        elif error == -2:
            self.statusbar.showMessage(" Certificate update: Nework connection failed.")
            self.msg_connection_failed()
        elif error == -3:
            self.statusbar.showMessage(" Certificate update error.")

    # 'FW': firmware upload
    def firmware_update(self, filename, filesize):
        self.sock_close()

        self.pgbar.setFormat("Uploading..")
        # self.pgbar.setRange(0, filesize)
        self.pgbar.setValue(0)
        self.pgbar.setRange(0, 8)
        self.pgbar.show()

        self.selected_devinfo()
        self.statusbar.showMessage(" Firmware update started. Please wait...")
        mac_addr = self.curr_mac
        self.logger.info("firmware_update %s, %s" % (mac_addr, filename))
        self.socket_config()

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        # Firmware update
        if self.broadcast.isChecked():
            self.t_fwup = FWUploadThread(
                self.conf_sock,
                mac_addr,
                self.code,
                self.encoded_setting_pw,
                filename,
                filesize,
                None,
                None,
                self.curr_dev,
            )
        elif self.unicast_ip.isChecked():
            ip_addr = self.search_ipaddr.text()
            port = int(self.search_port.text())
            self.t_fwup = FWUploadThread(
                self.conf_sock,
                mac_addr,
                self.code,
                self.encoded_setting_pw,
                filename,
                filesize,
                ip_addr,
                port,
                self.curr_dev,
            )
        self.t_fwup.uploading_size.connect(self.pgbar.setValue)
        self.t_fwup.upload_result.connect(self.update_result)
        self.t_fwup.error_flag.connect(self.update_error)
        try:
            self.t_fwup.start()
        except Exception as e:
            self.logger.error(e)
            self.update_result(-1)

    def firmware_file_open(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Firmware file open", "", "Binary Files (*.bin);;All Files (*)"
        )

        if fname:
            self.fw_filename = fname

            # get file size
            with open(self.fw_filename, "rb") as fd:
                self.data = fd.read(-1)

                if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
                    # for support WIZ107SR & WIZ108SR
                    self.fw_filesize = 51 * 1024
                else:
                    self.fw_filesize = len(self.data)

                self.logger.info(self.fw_filesize)

            if self.curr_dev in SECURITY_DEVICE:
                self.logger.info("SECURITY_DEVICE update")
                if 'WIZ5XXSR' in self.curr_dev or self.curr_dev in W55RP20_FAMILY or 'W232N' in self.curr_dev or 'IP20' in self.curr_dev:
                    self.logger.info(f'{self.curr_dev} update')
                    self.firmware_update(self.fw_filename, self.fw_filesize)
                else:
                    # Get current bank number
                    doc = QtGui.QTextDocument()
                    doc.setHtml(str(self.combobox_current_bank.currentIndex()))
                    bankval = doc.toPlainText()

                    msgbox = QMessageBox(self)
                    msgbox.setTextFormat(QtCore.Qt.RichText)
                    text = f"- Current bank: {bankval}\n- Selected file: {self.fw_filename.split('/')[-1]}\n\nThe bank number must match with current device bank number.\nDo you want to update now?"
                    btnReply = msgbox.question(
                        self,
                        "Firmware upload - Check the Bank number",
                        text,
                        QMessageBox.Yes | QMessageBox.No,
                    )
                    if btnReply == QMessageBox.Yes:
                        self.firmware_update(self.fw_filename, self.fw_filesize)
                    else:
                        pass
            else:
                # upload start
                self.firmware_update(self.fw_filename, self.fw_filesize)

    def net_check_ping(self, dst_ip):
        self.statusbar.showMessage(" Checking the network...")
        # serverip = self.localip_addr
        serverip = dst_ip
        # do_ping = subprocess.Popen("ping " + ("-n 1 " if sys.platform.lower()=="win32" else "-c 1 ") + serverip,
        do_ping = subprocess.Popen(
            "ping "
            + ("-n 1 " if "win" in sys.platform.lower() else "-c 1 ")
            + serverip,
            stdout=None,
            stderr=None,
            shell=True,
        )
        ping_response = do_ping.wait()
        self.logger.info(ping_response)
        return ping_response

    def upload_net_check(self):
        response = self.net_check_ping(self.localip_addr)
        if response == 0:
            self.statusbar.showMessage(
                " Firmware update: Select App boot Firmware file. (.bin)"
            )
            self.firmware_file_open()
        else:
            self.statusbar.showMessage(" Firmware update warning!")
            self.msg_upload_warning(self.localip_addr)

    def update_btn_clicked(self):
        if len(self.list_device.selectedItems()) == 0:
            self.logger.info("Device is not selected")
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QMessageBox.Warning)
        else:
            if self.unicast_ip.isChecked() and self.isConnected:
                self.firmware_file_open()
            else:
                self.upload_net_check()

    def reset_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(" Reset complete.")
            self.msg_reset_success()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(
                " Reset/Factory failed: no response from device."
            )

        self.object_config()

    def factory_result(self, resp_len):
        if resp_len > 0:
            self.statusbar.showMessage(" Factory reset complete.")
            self.msg_factory_success()
            if self.isConnected and self.unicast_ip.isChecked():
                self.conf_sock.shutdown()
        elif resp_len < 0:
            self.statusbar.showMessage(
                " Reset/Factory failed: no response from device."
            )

        self.object_config()

    def do_reset(self):
        if len(self.list_device.selectedItems()) == 0:
            self.logger.info("Device is not selected")
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QMessageBox.Warning)
        else:
            self.sock_close()

            self.selected_devinfo()
            mac_addr = self.curr_mac

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()

            cmd_list = self.wizmakecmd.reset(
                mac_addr, self.code, self.encoded_setting_pw, self.curr_dev
            )
            self.logger.info("Reset: %s" % cmd_list)

            self.socket_config()

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, "tcp", Opcode.OP_SETCOMMAND, 2
                )
            else:
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, "udp", Opcode.OP_SETCOMMAND, 2
                )
            self.wizmsghandler.set_result.connect(self.reset_result)
            self.wizmsghandler.start()

    def do_factory_reset(self, mode):
        cmd_list = []
        if len(self.list_device.selectedItems()) == 0:
            self.logger.info("Device is not selected")
            # self.msg_dev_not_selected()
            self.show_msgbox("Warning", "Device is not selected.", QMessageBox.Warning)
        else:
            self.sock_close()

            self.statusbar.showMessage(" Factory reset?")
            self.selected_devinfo()
            mac_addr = self.curr_mac

            if len(self.searchcode_input.text()) == 0:
                self.code = " "
            else:
                self.code = self.searchcode_input.text()
            # Factory reset option
            if mode == "setting":
                cmd_list = self.wizmakecmd.factory_reset(
                    mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, ""
                )
            elif mode == "firmware":
                cmd_list = self.wizmakecmd.factory_reset(
                    mac_addr, self.code, self.encoded_setting_pw, self.curr_dev, "0"
                )

            self.logger.info("Factory: %s" % cmd_list)

            self.socket_config()

            if self.unicast_ip.isChecked():
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, "tcp", Opcode.OP_SETCOMMAND, 2
                )
            else:
                self.wizmsghandler = WIZMSGHandler(
                    self.conf_sock, cmd_list, "udp", Opcode.OP_SETCOMMAND, 2
                )
            self.wizmsghandler.set_result.connect(self.factory_result)
            self.wizmsghandler.start()

    # To set the wait time when no response from the device when searching
    def input_search_wait_time(self):
        self.search_wait_time, okbtn = QInputDialog.getInt(
            self,
            "Set the wating time for search",
            "Input wating time for search:\n(Default: 3 seconds)",
            self.search_wait_time,
            2,
            10,
            1,
        )
        if okbtn:
            self.logger.info(self.search_wait_time)
            self.search_pre_wait_time = self.search_wait_time
            # Update each search wait time
            # self.search_wait_time_each += 1
        else:
            pass

    def input_retry_search(self):
        inputdlg = QInputDialog(self)
        name = "Do Search"
        inputdlg.setOkButtonText(name)
        self.retry_search_num, okbtn = inputdlg.getInt(
            self,
            "Retry search devices",
            "Search for additional devices,\nand the list of detected devices is maintained.\n\nInput for search retry number(option):",
            self.retry_search_num,
            1,
            10,
            1,
        )

        if okbtn:
            self.logger.info(self.retry_search_num)
            self.do_search_retry(self.retry_search_num)
        else:
            # self.do_search_retry(1)
            pass

    def append_textedit(self, variable, text):
        # self.logger.info(text)
        variable.clear()
        variable.append(text)
        variable.moveCursor(QtGui.QTextCursor.End)

    def load_cert_btn_clicked(self, cmd):
        print("load_cert_btn_clicked()", cmd)

        ext = "Certificate (*.crt *.pem *.key)"
        if cmd == "UP":
            ext = "*.bin"

        fname, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", ext + ";;All Files (*)"
        )
        if fname:
            # Save file name to variable
            if cmd == "OC":
                self.rootca_filename = fname
                self.append_textedit(getattr(self, "textedit_rootca"), fname)
            elif cmd == "LC":
                self.clientcert_filename = fname
                self.append_textedit(getattr(self, "textedit_client_cert"), fname)
            elif cmd == "PK":
                self.privatekey_filename = fname
                self.append_textedit(getattr(self, "textedit_privatekey"), fname)
            elif cmd == "UP":
                self.fw_filename = fname
                # self.append_textedit(getattr(self, 'textedit_upload_fw'), fname)
            self.logger.info("file load: %s\r\n", fname)

            self.logger.debug(
                f"{self.rootca_filename}, {self.clientcert_filename}, {self.privatekey_filename}"
            )

            # Need to verify selected certificate

    def save_cert_btn_clicked(self, cmd):
        self.logger.debug(cmd)
        self.selected_devinfo()
        mac_addr = self.curr_mac

        if len(self.searchcode_input.text()) == 0:
            self.code = " "
        else:
            self.code = self.searchcode_input.text()

        filename = ""
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
                self.conf_sock,
                mac_addr,
                self.code,
                self.encoded_setting_pw,
                filename,
                ip_addr,
                port,
                self.curr_dev,
                cmd,
            )
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
        msgbox = QMessageBox(self)
        msgbox.setIcon(type)
        msgbox.setWindowTitle(title)
        msgbox.setText(msg)
        msgbox.exec_()

    def show_msgbox_richtext(self, title, msg, type):
        msgbox = QMessageBox(self)
        msgbox.setIcon(type)
        msgbox.setWindowTitle(title)
        msgbox.setTextFormat(QtCore.Qt.RichText)
        msgbox.setText(msg)
        msgbox.exec_()

    def show_msgbox_info(self, title, msg):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Information)
        msgbox.setWindowTitle(title)
        msgbox.setText(msg)
        msgbox.setStandardButtons(QMessageBox.Ok)
        msgbox.exec_()

    def check_latest_version(self):
        try:
            latest_release = get_latest_release_version("Wiznet", "WIZnet-S2E-Tool-GUI")
            print(f"The latest release version is: {latest_release}")
            if VERSION.lower() != str(latest_release).lower():
                self.show_msgbox_info(
                    "Update Available",
                    f"Version {latest_release} is available.\nPlease download the latest version from the Github.",
                )
        except Exception as e:
            self.logger.error(e)

    def about_info(self):
        msgbox = QMessageBox(self)
        msgbox.setTextFormat(QtCore.Qt.RichText)
        text = f"""
        <html>
        <head>
        <style>
            body {{
                'font-family': 'Arial, sans-serif';
                'font-size': '14px';
            }}
            p {{
                "font-size": "16px";
                "font-size": "black";
            }}
            {{
                "margin-bottom": "4px";
            }}
        </style>
        </head>
        <body>
            <h2>About WIZnet-S2E-Tool-GUI</h2>
            <p>This is Configuration Tool for WIZnet serial to ethernet devices.</p>
            <p>Version: <b>{VERSION}</b></p>
            <p>Author: WIZnet</p>
            <p>Github: <a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI'>Github repository</a></p>
            <h3>Web site</h3>
            <p><a href='http://www.wiznet.io/'>WIZnet Official homepage</a></p>
            <p><a href='https://forum.wiznet.io/'>WIZnet Forum</a></p>
            <p><a href='https://docs.wiznet.io/'>WIZnet Document</a></p>
            <br><br>{datetime.datetime.now().year} WIZnet Co., Ltd.</font><br>
        </body>
        </html>
        """
        msgbox.about(self, "About WIZnet-S2E-Tool-GUI", text)

    def menu_document(self):
        self.logger.info("Menu: documentation")
        # documentation pop-up
        webbrowser.open("https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki")

    def msg_not_support(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Not supported device")
        msgbox.setTextFormat(QtCore.Qt.RichText)
        text = (
            "The device != supported.<br>Please contact us by the link below.<br><br>"
            "<a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'># Github issue page</a>"
        )
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

    # def msg_dev_not_selected(self):
    #     msgbox = QMessageBox(self)
    #     msgbox.setIcon(QMessageBox.Warning)
    #     msgbox.setWindowTitle("Warning")
    #     msgbox.setText("Device is not selected.")
    #     msgbox.exec_()

    def msg_set_warning(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Setting")
        msgbox.setText(
            "Setting did not well.\nPlease check the device or check the firmware version."
        )
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
        msgbox.question(
            self, "Setting success", "Device configuration complete!", QMessageBox.Yes
        )

    def msg_upload_warning(self, dst_ip):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: upload/update")
        msgbox.setText(
            "Destination IP is unreachable: %s\nPlease check if the device is in the same subnet with the PC."
            % dst_ip
        )
        msgbox.exec_()

    def msg_upload_success(self):
        msgbox = QMessageBox(self)
        msgbox.question(
            self,
            "Firmware upload success",
            "Firmware update complete!",
            QMessageBox.Yes,
        )

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
        msgbox.setText(
            "Destination IP is unreachable: %s\nPlease check the network status."
            % dst_ip
        )
        msgbox.exec_()

    def msg_reset(self):
        self.statusbar.showMessage(" Reset device?")
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(
            self,
            "Reset",
            "Do you really want to reset the device?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if btnReply == QMessageBox.Yes:
            self.do_reset()

    def msg_reset_success(self):
        msgbox = QMessageBox(self)
        msgbox.question(self, "Reset", "Reset complete!", QMessageBox.Yes)

    def msg_factory_success(self):
        msgbox = QMessageBox(self)
        msgbox.question(
            self, "Factory Reset", "Factory reset complete!", QMessageBox.Yes
        )

    def msg_factory_setting(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(
            self,
            "Factory default settings",
            "Do you really want to factory reset?\nAll settings will be initialized.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if btnReply == QMessageBox.Yes:
            self.do_factory_reset("setting")

    def msg_factory_firmware(self):
        # factory reset firmware
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(
            self,
            "Factory default firmware",
            "Do you really want to factory reset the firmware?\nThe firmware and all settings will be initialized to factory default.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if btnReply == QMessageBox.Yes:
            self.do_factory_reset("firmware")

    def msg_exit(self):
        msgbox = QMessageBox(self)
        btnReply = msgbox.question(
            self,
            "Exit",
            "Do you really close this program?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if btnReply == QMessageBox.Yes:
            self.close()

    def dialog_save_file(self):
        mac_part = self.curr_mac.replace(":", "")[6:]
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration",
            f"WIZCONF-{self.curr_dev}-{mac_part}.cfg",
            "Config File (*.cfg);;Text Files (*.txt);;All Files (*)",
        )

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

        with open(filename, "w+", encoding="utf-8") as f:
            for cmd in set_list:
                cmdset = "%s%s\n" % (cmd, setcmd.get(cmd))
                f.write(cmdset)

        self.statusbar.showMessage(" Configuration is saved to '%s'." % filename)

    def dialog_load_file(self):
        if self.saved_path is None:
            fname, _ = QFileDialog.getOpenFileName(
                self,
                "Load Configuration",
                "WIZCONF.cfg",
                "Config File (*.cfg);;Text Files (*.txt);;All Files (*)",
            )
        else:
            fname, _ = QFileDialog.getOpenFileName(
                self,
                "Load Configuration",
                self.saved_path,
                "Config File (*.cfg);;Text Files (*.txt);;All Files (*)",
            )

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

        with open(data_file, "r", encoding="utf-8") as f:
            for line in f:
                line = re.sub("[\n]", "", line)
                if len(line) > 2:
                    cmd_list.append(line.encode())
            self.logger.info(cmd_list)

        try:
            for i in range(0, len(cmd_list)):
                # print('cmd_list', i, cmd_list[i], cmd_list[i][:2], cmd_list[i][2:])
                if cmd_list[i][:2] == b"MA" or len(cmd_list[i]) < 2:
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
        icon.addPixmap(
            QtGui.QPixmap(resource_path(iconfile)), QtGui.QIcon.Normal, QtGui.QIcon.Off
        )
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(40, 40))
        button.setFont(self.midfont)

    def set_btn_icon(self):
        self.config_button_icon("gui/save_48.ico", "btn_saveconfig")
        self.config_button_icon("gui/load_48.ico", "btn_loadconfig")
        self.config_button_icon("gui/search_48.ico", "btn_search")
        self.config_button_icon("gui/setting_48.ico", "btn_setting")
        self.config_button_icon("gui/upload_48.ico", "btn_upload")
        self.config_button_icon("gui/reset_48.ico", "btn_reset")
        self.config_button_icon("gui/factory_48.ico", "btn_factory")
        self.config_button_icon("gui/exit_48.ico", "btn_exit")

    def font_init(self):
        self.midfont = QtGui.QFont()
        self.midfont.setPixelSize(12)  # pointsize(9)

        self.smallfont = QtGui.QFont()
        self.smallfont.setPixelSize(11)

        self.certfont = QtGui.QFont()
        self.certfont.setPixelSize(10)
        self.certfont.setFamily("Consolas")

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

        # ⓘ 아이콘 라벨 설정 (클릭 및 빠른 호버 지원)
        # NOTE: 1.5.7 UI 복원으로 인해 info 라벨들이 제거되어 비활성화
        # self._setup_info_labels()

    def _setup_info_labels(self):
        """ⓘ 아이콘 라벨을 ClickableInfoLabel로 교체

        목적:
        - UI 파일(.ui)에 정의된 일반 QLabel을 ClickableInfoLabel로 런타임 교체
        - 사용자에게 검색 방법에 대한 추가 정보 제공
        - 호버링(300ms 지연) 및 클릭으로 툴팁 표시

        교체 대상:
        1. label_broadcast_info: UDP broadcast 옆 (빠른 브로드캐스트 검색 설명)
        2. label_unicast_info: TCP unicast 옆 (특정 IP 직접 검색 설명)
        3. label_tcp_multicast_info: TCP multicast 옆 (서브넷 스캔 설명)
        4. label_mixed_info: Mixed 옆 (UDP + TCP 혼합 방식 설명)

        구현 방식:
        - UI 파일의 QLabel을 그대로 두고, 프로그램 시작 시 교체
        - 중첩 레이아웃에서도 동작하도록 재귀적 탐색 사용
        - 원본 label의 속성(text, tooltip, 스타일 등) 모두 복사

        호출 시점:
        - WIZWindow.__init__() 마지막에서 호출
        - UI 로딩 완료 후 실행
        """
        self.logger.info("[INFO] _setup_info_labels 시작")

        # group_searchmethod을 강제로 표시
        self.group_searchmethod.setVisible(True)
        self.group_searchmethod.show()

        # 디버깅: 부모 위젯 상태 확인
        self.logger.info(f"[DEBUG] group_searchmethod.isVisible(): {self.group_searchmethod.isVisible()}")
        self.logger.info(f"[DEBUG] broadcast.isChecked(): {self.broadcast.isChecked()}")
        self.logger.info(f"[DEBUG] tcp_multicast.isChecked(): {self.tcp_multicast.isChecked()}")
        self.logger.info(f"[DEBUG] mixed_search.isChecked(): {self.mixed_search.isChecked()}")

        # 1. UDP broadcast 옆 ⓘ 아이콘 교체 
        # → 빠른 네트워크 검색(약 3초 소요)에 대한 설명
        self.logger.info(f"[INFO] label_broadcast_info 타입: {type(self.label_broadcast_info)}")
        self._replace_label_with_clickable(
            old_label=self.label_broadcast_info,
            attr_name='label_broadcast_info'
        )
        self.logger.info(f"[INFO] UDP broadcast info 교체 완료")
        self.logger.info(f"[INFO] label_broadcast_info.isEnabled(): {self.label_broadcast_info.isEnabled()}")
        self.logger.info(f"[INFO] label_broadcast_info.isVisible(): {self.label_broadcast_info.isVisible()}")
        self.logger.info(f"[INFO] label_broadcast_info.toolTip(): {self.label_broadcast_info.toolTip()}")

        # 2. TCP unicast 옆 ⓘ 아이콘 교체
        # → 특정 IP만 검색하는 방식 설명
        self.logger.info(f"[INFO] label_unicast_info 타입: {type(self.label_unicast_info)}")
        self._replace_label_with_clickable(
            old_label=self.label_unicast_info,
            attr_name='label_unicast_info'
        )
        self.logger.info(f"[INFO] TCP unicast info 교체 완료")
        self.logger.info(f"[INFO] label_unicast_info.isEnabled(): {self.label_unicast_info.isEnabled()}")
        self.logger.info(f"[INFO] label_unicast_info.isVisible(): {self.label_unicast_info.isVisible()}")
        self.logger.info(f"[INFO] label_unicast_info.toolTip(): {self.label_unicast_info.toolTip()}")

        # 3. TCP multicast 옆 ⓘ 아이콘 교체
        # → 전체 서브넷 스캔(약 30초 소요)에 대한 상세 설명
        self.logger.info(f"[INFO] label_tcp_multicast_info 타입: {type(self.label_tcp_multicast_info)}")
        self._replace_label_with_clickable(
            old_label=self.label_tcp_multicast_info,
            attr_name='label_tcp_multicast_info'
        )
        self.logger.info(f"[INFO] TCP multicast info 교체 완료")
        self.logger.info(f"[INFO] label_tcp_multicast_info.isEnabled(): {self.label_tcp_multicast_info.isEnabled()}")
        self.logger.info(f"[INFO] label_tcp_multicast_info.isVisible(): {self.label_tcp_multicast_info.isVisible()}")
        self.logger.info(f"[INFO] label_tcp_multicast_info.toolTip(): {self.label_tcp_multicast_info.toolTip()}")

        # 4. Mixed search 옆 ⓘ 아이콘 교체
        # → UDP broadcast 실패 시 TCP unicast 재시도하는 혼합 방식 설명
        self.logger.info(f"[INFO] label_mixed_info 타입: {type(self.label_mixed_info)}")
        self._replace_label_with_clickable(
            old_label=self.label_mixed_info,
            attr_name='label_mixed_info'
        )
        self.logger.info(f"[INFO] Mixed info 교체 완료")
        self.logger.info(f"[INFO] label_mixed_info.isEnabled(): {self.label_mixed_info.isEnabled()}")
        self.logger.info(f"[INFO] label_mixed_info.isVisible(): {self.label_mixed_info.isVisible()}")
        self.logger.info(f"[INFO] label_mixed_info.toolTip(): {self.label_mixed_info.toolTip()}")

        # 전역 설정: 창이 포커스를 잃어도 툴팁 표시
        # → Qt 기본 동작은 창 포커스 잃으면 툴팁 숨김
        # → WA_AlwaysShowToolTips로 항상 표시되도록 변경
        try:
            self.setAttribute(QtCore.Qt.WidgetAttribute(119), True)  # 119 = WA_AlwaysShowToolTips
            self.logger.info("[INFO] WA_AlwaysShowToolTips 속성 설정 완료")
        except Exception as e:
            self.logger.warning(f"[WARN] WA_AlwaysShowToolTips 설정 실패: {e}")

    def _replace_label_with_clickable(self, old_label, attr_name):
        """기존 QLabel을 ClickableInfoLabel로 런타임 교체

        Args:
            old_label: UI 파일에서 로딩한 원본 QLabel 객체
            attr_name: self.<attr_name>으로 저장할 속성 이름 (문자열)

        동작 원리:
        1. 재귀적 레이아웃 탐색으로 위젯 위치 찾기
        2. 원본 label의 모든 속성 복사
        3. 새 ClickableInfoLabel 생성
        4. 원본과 같은 위치에 새 label 배치
        5. self.<attr_name>에 새 label 저장

        왜 이렇게 구현했는가:
        - UI 파일(.ui)을 직접 수정하지 않고 런타임에 교체
        - 중첩 레이아웃(gridLayout_99, gridLayout_100)에서도 동작
        - Qt Designer에서 편집 가능한 UI 유지

        문제 해결 히스토리:
        - 초기: parentWidget().layout()으로 직접 접근 → indexOf() = -1 실패
        - 개선: 재귀적 탐색으로 중첩 레이아웃 안의 위젯도 찾기 성공
        - 결과: TCP multicast/Mixed 옆 i 아이콘 클릭 정상 동작
        """

        # 1단계: 부모 위젯 확인
        parent_widget = old_label.parentWidget()
        if parent_widget is None:
            self.logger.warning(f"[{attr_name}] 부모 위젯을 찾을 수 없음")
            return

        # 2단계: 재귀적 레이아웃 탐색
        def find_layout_containing_widget(search_layout, target_widget):
            """레이아웃 트리를 재귀적으로 탐색하여 위젯을 포함하는 레이아웃 찾기

            Args:
                search_layout: 탐색 시작 레이아웃 (QLayout)
                target_widget: 찾으려는 위젯 (QWidget)

            Returns:
                QLayout: 위젯을 직접 포함하는 레이아웃
                None: 찾지 못함

            동작:
                - 현재 레이아웃에서 indexOf() 확인
                - 못 찾으면 자식 레이아웃들을 재귀적으로 탐색
                - DFS(깊이 우선 탐색) 방식

            예시:
                gridLayout_7 (root)
                ├─ gridLayout_99
                │  └─ label_tcp_multicast_info ← 여기서 찾음
                └─ gridLayout_100
                   └─ label_mixed_info ← 여기서 찾음
            """
            if search_layout is None:
                return None

            # 현재 레이아웃에 위젯이 있는지 확인
            if search_layout.indexOf(target_widget) >= 0:
                return search_layout  # 찾음!

            # 자식 레이아웃들을 재귀적으로 탐색
            for i in range(search_layout.count()):
                item = search_layout.itemAt(i)
                if item and item.layout():  # 아이템이 레이아웃인 경우
                    result = find_layout_containing_widget(item.layout(), target_widget)
                    if result:
                        return result  # 재귀 호출에서 찾음

            return None  # 이 브랜치에서는 못 찾음

        # 재귀 탐색 시작
        root_layout = parent_widget.layout()
        layout = find_layout_containing_widget(root_layout, old_label)

        if layout is None:
            self.logger.warning(f"[{attr_name}] 위젯을 포함하는 레이아웃을 찾을 수 없음")
            return

        self.logger.info(f"[{attr_name}] 위젯을 포함하는 레이아웃 찾음: {type(layout).__name__}")

        # 3단계: 기존 위젯의 속성 복사
        # → 새 label이 원본과 동일하게 보이도록
        tooltip = old_label.toolTip()  # 툴팁 텍스트
        text = old_label.text()  # 표시 텍스트 (ⓘ)
        stylesheet = old_label.styleSheet()  # CSS 스타일
        min_size = old_label.minimumSize()  # 최소 크기
        max_size = old_label.maximumSize()  # 최대 크기
        alignment = old_label.alignment()  # 정렬 방식

        # 4단계: 새 ClickableInfoLabel 생성 및 속성 설정
        new_label = ClickableInfoLabel(parent_widget)
        new_label.setText(text)
        new_label.setToolTip(tooltip)
        new_label.setStyleSheet(stylesheet)
        new_label.setMinimumSize(min_size)
        new_label.setMaximumSize(max_size)
        new_label.setAlignment(alignment)

        # 항상 활성화 상태 유지
        # → 부모 위젯(라디오 버튼 등)이 비활성화되어도 i 아이콘은 클릭 가능
        new_label.setEnabled(True)

        # 항상 표시 상태 유지
        # → ⓘ 아이콘이 항상 보이도록 강제
        new_label.setVisible(True)

        # 5단계: QGridLayout에서 원래 위치 찾아서 교체
        if isinstance(layout, QGridLayout):
            self.logger.debug(f"[{attr_name}] QGridLayout 감지, 총 {layout.count()}개 아이템")

            # indexOf()로 위젯의 인덱스 찾기
            index = layout.indexOf(old_label)
            if index >= 0:
                self.logger.debug(f"[{attr_name}] 위젯을 인덱스 {index}에서 발견")

                # getItemPosition()으로 정확한 (row, col) 위치 가져오기
                row, col, rowspan, colspan = layout.getItemPosition(index)
                self.logger.debug(f"[{attr_name}] 위치: row={row}, col={col}, rowspan={rowspan}, colspan={colspan}")

                # None 체크 (getItemPosition 실패 방지)
                if row is not None and col is not None and rowspan is not None and colspan is not None:
                    # 5-1. 기존 위젯 제거
                    layout.removeWidget(old_label)
                    old_label.deleteLater()  # Qt 객체 삭제 예약

                    # 5-2. 새 위젯을 같은 위치에 추가
                    layout.addWidget(new_label, row, col, rowspan, colspan)
                    self.logger.debug(f"[{attr_name}] 새 위젯을 ({row}, {col})에 추가 완료")

                    # 6단계: 성공 - 새 위젯을 self.<attr_name>에 저장
                    setattr(self, attr_name, new_label)
                    self.logger.debug(f"[{attr_name}] ClickableInfoLabel로 교체 완료")
                    return
                else:
                    self.logger.warning(f"[{attr_name}] getItemPosition 반환값에 None 포함: row={row}, col={col}")

            # 실패: 위치를 찾지 못함
            self.logger.warning(f"[{attr_name}] QGridLayout에서 위치를 찾지 못함 (indexOf={index})")
            setattr(self, attr_name, new_label)  # 속성만 저장, UI는 변경 안 됨
            return
        else:
            # QGridLayout이 아닌 다른 레이아웃 (현재 미지원)
            self.logger.warning(f"[{attr_name}] QGridLayout이 아닌 레이아웃 타입: {type(layout)}")
            setattr(self, attr_name, new_label)  # 속성만 저장
            return

    # ================================================================
    # 타이밍 설정 다이얼로그 관련 메서드
    # ================================================================
    def event_open_timing_settings(self):
        """타이밍 설정 다이얼로그 표시 (기어 아이콘 버튼 클릭 이벤트)"""
        try:
            # 1. 현재 설정 값 읽기
            current_values = self.timing_config.get_current_values()

            # 2. 다이얼로그 생성 및 표시
            dialog = self._create_timing_settings_dialog(current_values)
            result = dialog.exec_()

            # 3. 저장 버튼 클릭 시 적용
            if result == QDialog.Accepted:
                # 다이얼로그의 위젯들에서 값 추출
                new_values = self._extract_dialog_values(dialog)

                # 검증 및 저장
                if self._apply_timing_settings(new_values):
                    QMessageBox.information(
                        self,
                        "설정 저장",
                        "검색 타이밍 설정이 저장되었습니다.\n\n"
                        "일부 설정은 다음 검색부터 적용됩니다."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "저장 실패",
                        "설정 저장에 실패했습니다.\n"
                        "로그를 확인해주세요."
                    )

        except Exception as e:
            self.logger.error(f"타이밍 설정 다이얼로그 오류: {e}")
            QMessageBox.critical(
                self,
                "오류",
                f"타이밍 설정 중 오류가 발생했습니다:\n{e}"
            )

    def _create_timing_settings_dialog(self, current_values: dict) -> QDialog:
        """타이밍 설정 다이얼로그 생성

        Args:
            current_values: 현재 설정 값

        Returns:
            QDialog: 설정 다이얼로그
        """
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
                                      QDoubleSpinBox, QSpinBox, QCheckBox, QGroupBox)

        dialog = QDialog(self)
        dialog.setWindowTitle("검색 타이밍 설정")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # === Phase 1 타이밍 그룹 ===
        phase1_group = QGroupBox("Phase 1 타이밍 (UDP Broadcast / TCP Multicast)")
        phase1_layout = QFormLayout()

        # Loop Select Timeout
        dialog.spin_loop_timeout = QDoubleSpinBox()
        dialog.spin_loop_timeout.setRange(0.1, 5.0)
        dialog.spin_loop_timeout.setSingleStep(0.1)
        dialog.spin_loop_timeout.setDecimals(1)
        dialog.spin_loop_timeout.setSuffix(" 초")
        dialog.spin_loop_timeout.setValue(current_values['phase1_loop_select_timeout'])
        dialog.spin_loop_timeout.setToolTip(
            "마지막 응답 이후 추가 응답 대기 시간\n"
            "권장: 일반 0.5초, 구형 장비 1.0초, 고속 0.3초"
        )
        phase1_layout.addRow("Loop Select Timeout:", dialog.spin_loop_timeout)

        # Emit Stabilization Delay
        dialog.spin_emit_delay = QSpinBox()
        dialog.spin_emit_delay.setRange(0, 500)
        dialog.spin_emit_delay.setSingleStep(10)
        dialog.spin_emit_delay.setSuffix(" ms")
        dialog.spin_emit_delay.setValue(current_values['phase1_emit_stabilization_ms'])
        dialog.spin_emit_delay.setToolTip(
            "PyQt signal queue 안정화 대기 시간\n"
            "권장: 50ms (실험적: 0~100ms)"
        )
        phase1_layout.addRow("Emit 안정화 딜레이:", dialog.spin_emit_delay)

        # Skip Emit Delay (Experimental)
        dialog.check_skip_delay = QCheckBox()
        dialog.check_skip_delay.setChecked(current_values['skip_phase1_emit_delay'])
        dialog.check_skip_delay.setToolTip(
            "⚠ 실험적 기능: Emit 전 딜레이 생략\n"
            "활성화 시 약 50ms 단축되지만 signal queue 불안정 가능성"
        )
        phase1_layout.addRow("Emit 딜레이 건너뛰기 (실험적):", dialog.check_skip_delay)

        phase1_group.setLayout(phase1_layout)
        main_layout.addWidget(phase1_group)

        # === Phase 3 타이밍 그룹 ===
        phase3_group = QGroupBox("Phase 3 타이밍 (개별 장비 쿼리)")
        phase3_layout = QFormLayout()

        # Device Query Timeout
        dialog.spin_query_timeout = QDoubleSpinBox()
        dialog.spin_query_timeout.setRange(0.5, 5.0)
        dialog.spin_query_timeout.setSingleStep(0.1)
        dialog.spin_query_timeout.setDecimals(1)
        dialog.spin_query_timeout.setSuffix(" 초")
        dialog.spin_query_timeout.setValue(current_values['phase3_device_query_timeout'])
        dialog.spin_query_timeout.setToolTip(
            "각 장비 응답 대기 시간\n"
            "권장: 일반 1.5초, 빠른 1.0초, 느린/원거리 2.0초"
        )
        phase3_layout.addRow("장비 쿼리 타임아웃:", dialog.spin_query_timeout)

        phase3_group.setLayout(phase3_layout)
        main_layout.addWidget(phase3_group)

        # === TCP 설정 그룹 ===
        tcp_group = QGroupBox("TCP 설정 (TCP Multicast / Mixed Search)")
        tcp_layout = QFormLayout()

        # Max Parallel Workers
        dialog.spin_tcp_workers = QSpinBox()
        dialog.spin_tcp_workers.setRange(1, 50)
        dialog.spin_tcp_workers.setSingleStep(5)
        dialog.spin_tcp_workers.setValue(current_values['tcp_max_parallel_workers'])
        dialog.spin_tcp_workers.setToolTip(
            "최대 동시 연결 수\n"
            "권장: 15 (네트워크 대역폭에 따라 조정)"
        )
        tcp_layout.addRow("최대 병렬 워커 수:", dialog.spin_tcp_workers)

        tcp_group.setLayout(tcp_layout)
        main_layout.addWidget(tcp_group)

        # === UI 설정 그룹 ===
        ui_group = QGroupBox("UI 설정")
        ui_layout = QFormLayout()

        # Progress Bar Update Percent
        dialog.spin_pgbar_percent = QSpinBox()
        dialog.spin_pgbar_percent.setRange(1, 100)
        dialog.spin_pgbar_percent.setSingleStep(5)
        dialog.spin_pgbar_percent.setSuffix(" %")
        dialog.spin_pgbar_percent.setValue(current_values['pgbar_update_percent'])
        dialog.spin_pgbar_percent.setToolTip(
            "Progress bar 갱신 퍼센트\n"
            "작을수록 자주 갱신 (부드럽지만 느림)\n"
            "클수록 드물게 갱신 (빠르지만 뚝뚝 끊김)\n"
            "권장: 5~20%"
        )
        ui_layout.addRow("Progress Bar 갱신 주기:", dialog.spin_pgbar_percent)

        # Progress Bar Auto Hide Delay
        dialog.spin_pgbar_hide = QSpinBox()
        dialog.spin_pgbar_hide.setRange(0, 10000)
        dialog.spin_pgbar_hide.setSingleStep(500)
        dialog.spin_pgbar_hide.setSuffix(" ms")
        dialog.spin_pgbar_hide.setValue(current_values['pgbar_auto_hide_delay_ms'])
        dialog.spin_pgbar_hide.setToolTip(
            "검색 완료 후 Progress bar 자동 숨김 대기 시간\n"
            "0이면 즉시 숨김"
        )
        ui_layout.addRow("Progress Bar 자동 숨김 딜레이:", dialog.spin_pgbar_hide)

        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)

        # === 버튼 박스 ===
        button_box = QDialogButtonBox()
        btn_save = button_box.addButton("저장", QDialogButtonBox.AcceptRole)
        btn_cancel = button_box.addButton("취소", QDialogButtonBox.RejectRole)
        btn_reset = button_box.addButton("기본값 복원", QDialogButtonBox.ResetRole)

        # 버튼 툴팁
        btn_save.setToolTip("설정을 저장하고 적용합니다")
        btn_cancel.setToolTip("변경사항을 무시하고 닫습니다")
        btn_reset.setToolTip("모든 설정을 기본값으로 되돌립니다")

        # 시그널 연결
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        btn_reset.clicked.connect(lambda: self._reset_dialog_to_defaults(dialog))

        main_layout.addWidget(button_box)

        dialog.setLayout(main_layout)
        return dialog

    def _extract_dialog_values(self, dialog: QDialog) -> dict:
        """다이얼로그에서 사용자 입력 값 추출

        Args:
            dialog: 타이밍 설정 다이얼로그

        Returns:
            dict: 추출된 설정 값
        """
        return {
            'phase1_loop_select_timeout': dialog.spin_loop_timeout.value(),
            'phase1_emit_stabilization_ms': dialog.spin_emit_delay.value(),
            'skip_phase1_emit_delay': dialog.check_skip_delay.isChecked(),
            'phase3_device_query_timeout': dialog.spin_query_timeout.value(),
            'tcp_max_parallel_workers': dialog.spin_tcp_workers.value(),
            'pgbar_update_percent': dialog.spin_pgbar_percent.value(),
            'pgbar_auto_hide_delay_ms': dialog.spin_pgbar_hide.value()
        }

    def _apply_timing_settings(self, new_values: dict) -> bool:
        """새로운 타이밍 설정 적용

        Args:
            new_values: 새로운 설정 값

        Returns:
            bool: 성공 여부
        """
        try:
            # 1. DeviceSearchConfig에 저장
            if not self.timing_config.update_config_values(new_values):
                self.logger.error("타이밍 설정 저장 실패")
                return False

            # 2. WIZMSGHandler 클래스 변수 즉시 업데이트
            from WIZMSGHandler import WIZMSGHandler
            WIZMSGHandler.loop_select_timeout = new_values['phase1_loop_select_timeout']
            WIZMSGHandler.emit_stabilization_ms = new_values['phase1_emit_stabilization_ms']
            WIZMSGHandler.skip_phase1_emit_delay = new_values['skip_phase1_emit_delay']

            # 3. 인스턴스 변수 업데이트 (다음 검색 시 사용)
            self.search_wait_time_each = new_values['phase3_device_query_timeout']

            self.logger.info(f"타이밍 설정 업데이트 완료: {new_values}")
            return True

        except Exception as e:
            self.logger.error(f"타이밍 설정 적용 실패: {e}")
            return False

    def _reset_dialog_to_defaults(self, dialog: QDialog):
        """다이얼로그 값을 기본값으로 리셋

        Args:
            dialog: 타이밍 설정 다이얼로그
        """
        reply = QMessageBox.question(
            dialog,
            "기본값 복원 확인",
            "모든 타이밍 설정을 기본값으로 되돌리시겠습니까?\n\n"
            "이 작업은 즉시 저장되며, 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 1. DeviceSearchConfig 기본값 복원
                if not self.timing_config.reset_to_defaults():
                    QMessageBox.warning(
                        dialog,
                        "복원 실패",
                        "기본값 복원에 실패했습니다.\n로그를 확인해주세요."
                    )
                    return

                # 2. 다이얼로그 위젯 값 업데이트
                defaults = self.timing_config.get_current_values()
                dialog.spin_loop_timeout.setValue(defaults['phase1_loop_select_timeout'])
                dialog.spin_emit_delay.setValue(defaults['phase1_emit_stabilization_ms'])
                dialog.check_skip_delay.setChecked(defaults['skip_phase1_emit_delay'])
                dialog.spin_query_timeout.setValue(defaults['phase3_device_query_timeout'])
                dialog.spin_tcp_workers.setValue(defaults['tcp_max_parallel_workers'])
                dialog.spin_pgbar_percent.setValue(defaults['pgbar_update_percent'])
                dialog.spin_pgbar_hide.setValue(defaults['pgbar_auto_hide_delay_ms'])

                # 3. WIZMSGHandler 클래스 변수 업데이트
                from WIZMSGHandler import WIZMSGHandler
                WIZMSGHandler.loop_select_timeout = defaults['phase1_loop_select_timeout']
                WIZMSGHandler.emit_stabilization_ms = defaults['phase1_emit_stabilization_ms']
                WIZMSGHandler.skip_phase1_emit_delay = defaults['skip_phase1_emit_delay']

                # 4. 인스턴스 변수 업데이트
                self.search_wait_time_each = defaults['phase3_device_query_timeout']

                QMessageBox.information(
                    dialog,
                    "복원 완료",
                    "모든 설정이 기본값으로 복원되었습니다."
                )

                self.logger.info("타이밍 설정 기본값 복원 완료")

            except Exception as e:
                self.logger.error(f"기본값 복원 실패: {e}")
                QMessageBox.critical(
                    dialog,
                    "오류",
                    f"기본값 복원 중 오류가 발생했습니다:\n{e}"
                )

    # ========== Advanced Search Options 다이얼로그 ==========

    def event_open_advanced_search_options(self):
        """Option 메뉴 → Advanced Search Options 선택 시"""
        try:
            # 최신 설정 읽기
            config = self._get_current_search_config()

            # 다이얼로그 생성 및 표시
            dialog = self._create_advanced_search_dialog(config)

            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                # 사용자 입력 추출
                updates = self._extract_advanced_dialog_values(dialog)

                # 설정 적용
                self._apply_advanced_search_settings(updates)

        except Exception as e:
            self.logger.error(f"Advanced Search Options 다이얼로그 오류: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "오류",
                f"고급 검색 옵션 설정 중 오류가 발생했습니다:\n{e}"
            )

    def _get_current_search_config(self):
        """현재 검색 설정 읽기 (DeviceSearchConfig + 내부 변수)"""
        if not hasattr(self, 'device_search_config'):
            self.device_search_config = DeviceSearchConfig()

        config = self.device_search_config.get_current_values()

        # 내부 변수 추가
        config['expected_device_count'] = getattr(self, 'retry_search_expected_count', 0)
        config['max_retry_count'] = getattr(self, 'retry_search_max_count', 3)

        return config

    def _create_advanced_search_dialog(self, config):
        """Advanced Search Options 다이얼로그 UI 생성

        Args:
            config: 현재 설정 값

        Returns:
            QDialog: 설정 다이얼로그
        """
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
                                      QDoubleSpinBox, QSpinBox, QCheckBox, QGroupBox, QPushButton)

        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Search Options")
        dialog.setModal(True)
        dialog.setMinimumWidth(550)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # === 검색 옵션 그룹 ===
        search_group = QGroupBox("검색 옵션")
        search_layout = QFormLayout()

        # 예상 장비 수
        dialog.spin_expected_device_count = QSpinBox()
        dialog.spin_expected_device_count.setRange(0, 1000)
        dialog.spin_expected_device_count.setSingleStep(1)
        dialog.spin_expected_device_count.setValue(config.get('expected_device_count', 0))
        dialog.spin_expected_device_count.setToolTip(
            "검색 시 예상되는 장비 수 (0 = 무제한)\n"
            "이 수에 도달하면 검색 조기 종료"
        )
        search_layout.addRow("예상 장비 수:", dialog.spin_expected_device_count)

        # 최대 반복 횟수
        dialog.spin_max_retry_count = QSpinBox()
        dialog.spin_max_retry_count.setRange(1, 100)
        dialog.spin_max_retry_count.setSingleStep(1)
        dialog.spin_max_retry_count.setValue(config.get('max_retry_count', 3))
        dialog.spin_max_retry_count.setToolTip(
            "검색 반복 최대 횟수\n"
            "권장: 일반 3회, 빠른 검색 1회"
        )
        search_layout.addRow("최대 반복 횟수:", dialog.spin_max_retry_count)

        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)

        # === Phase 1 타이밍 그룹 ===
        phase1_group = QGroupBox("Phase 1 타이밍 (UDP Broadcast / TCP Multicast)")
        phase1_layout = QFormLayout()

        # Broadcast Timeout (장비 못 찾을 때 딜레이의 핵심 파라미터)
        dialog.dspin_broadcast_timeout = QDoubleSpinBox()
        dialog.dspin_broadcast_timeout.setRange(0.5, 10.0)
        dialog.dspin_broadcast_timeout.setSingleStep(0.5)
        dialog.dspin_broadcast_timeout.setDecimals(1)
        dialog.dspin_broadcast_timeout.setSuffix(" 초")
        dialog.dspin_broadcast_timeout.setValue(config.get('phase1_broadcast_timeout', 3.0))
        dialog.dspin_broadcast_timeout.setToolTip(
            "UDP Broadcast 응답 대기 시간 (1회 검색당 대기)\n"
            "장비 못 찾을 때: 반복횟수 × 이 값 = 총 대기 시간\n"
            "권장: 일반 3.0초, 빠른 네트워크 2.0초, 느린 네트워크 5.0초"
        )
        phase1_layout.addRow("Broadcast Timeout:", dialog.dspin_broadcast_timeout)

        # Loop Select Timeout
        dialog.dspin_loop_select_timeout = QDoubleSpinBox()
        dialog.dspin_loop_select_timeout.setRange(0.1, 10.0)
        dialog.dspin_loop_select_timeout.setSingleStep(0.1)
        dialog.dspin_loop_select_timeout.setDecimals(1)
        dialog.dspin_loop_select_timeout.setSuffix(" 초")
        dialog.dspin_loop_select_timeout.setValue(config.get('phase1_loop_select_timeout', 0.5))
        dialog.dspin_loop_select_timeout.setToolTip(
            "마지막 응답 이후 추가 응답 대기 시간\n"
            "권장: 일반 0.5초, 구형 장비 1.0초, 고속 0.3초"
        )
        phase1_layout.addRow("Loop Select Timeout:", dialog.dspin_loop_select_timeout)

        # Emit 안정화 딜레이
        dialog.spin_emit_delay = QSpinBox()
        dialog.spin_emit_delay.setRange(0, 1000)
        dialog.spin_emit_delay.setSingleStep(10)
        dialog.spin_emit_delay.setSuffix(" ms")
        dialog.spin_emit_delay.setValue(config.get('phase1_emit_stabilization_ms', 50))
        dialog.spin_emit_delay.setToolTip(
            "PyQt signal queue 안정화 대기 시간\n"
            "권장: 50ms (실험적: 0~100ms)"
        )
        phase1_layout.addRow("Emit 안정화 딜레이:", dialog.spin_emit_delay)

        # Emit 딜레이 건너뛰기 (실험적)
        dialog.cb_skip_emit_delay = QCheckBox()
        dialog.cb_skip_emit_delay.setChecked(config.get('skip_phase1_emit_delay', False))
        dialog.cb_skip_emit_delay.setToolTip(
            "⚠ 실험적 기능: Emit 전 딜레이 생략\n"
            "활성화 시 약 50ms 단축되지만 signal queue 불안정 가능성"
        )
        phase1_layout.addRow("☐ Emit 딜레이 건너뛰기 (실험적):", dialog.cb_skip_emit_delay)

        phase1_group.setLayout(phase1_layout)
        main_layout.addWidget(phase1_group)

        # === Phase 3 타이밍 그룹 ===
        phase3_group = QGroupBox("Phase 3 타이밍 (장비 정보 조회)")
        phase3_layout = QFormLayout()

        # 장비 쿼리 타임아웃
        dialog.dspin_device_query_timeout = QDoubleSpinBox()
        dialog.dspin_device_query_timeout.setRange(0.5, 10.0)
        dialog.dspin_device_query_timeout.setSingleStep(0.1)
        dialog.dspin_device_query_timeout.setDecimals(1)
        dialog.dspin_device_query_timeout.setSuffix(" 초")
        dialog.dspin_device_query_timeout.setValue(config.get('phase3_device_query_timeout', 1.5))
        dialog.dspin_device_query_timeout.setToolTip(
            "개별 장비 정보 조회 타임아웃\n"
            "권장: 일반 1.5초, 구형 장비 2.0초, 고속 1.0초"
        )
        phase3_layout.addRow("장비 쿼리 타임아웃:", dialog.dspin_device_query_timeout)

        phase3_group.setLayout(phase3_layout)
        main_layout.addWidget(phase3_group)

        # === TCP 설정 그룹 ===
        tcp_group = QGroupBox("TCP 설정")
        tcp_layout = QFormLayout()

        # 최대 병렬 워커 수
        dialog.spin_tcp_max_workers = QSpinBox()
        dialog.spin_tcp_max_workers.setRange(1, 50)
        dialog.spin_tcp_max_workers.setSingleStep(1)
        dialog.spin_tcp_max_workers.setValue(config.get('tcp_max_parallel_workers', 15))
        dialog.spin_tcp_max_workers.setToolTip(
            "TCP Multicast 검색 시 최대 병렬 연결 수\n"
            "권장: 일반 15, 저성능 PC 5, 고성능 PC 30"
        )
        tcp_layout.addRow("최대 병렬 워커 수:", dialog.spin_tcp_max_workers)

        tcp_group.setLayout(tcp_layout)
        main_layout.addWidget(tcp_group)

        # === UI 설정 그룹 ===
        ui_group = QGroupBox("UI 설정")
        ui_layout = QFormLayout()

        # Progress Bar 갱신 주기
        dialog.spin_pgbar_update_step = QSpinBox()
        dialog.spin_pgbar_update_step.setRange(1, 50)
        dialog.spin_pgbar_update_step.setSingleStep(1)
        dialog.spin_pgbar_update_step.setSuffix(" %")
        dialog.spin_pgbar_update_step.setValue(config.get('pgbar_update_percent', 10))
        dialog.spin_pgbar_update_step.setToolTip(
            "진행바 업데이트 주기 (%)\n"
            "값이 작을수록 부드럽지만 CPU 사용 증가"
        )
        ui_layout.addRow("Progress Bar 갱신 주기:", dialog.spin_pgbar_update_step)

        # Progress Bar 자동 숨김 딜레이
        dialog.spin_pgbar_auto_hide_delay = QSpinBox()
        dialog.spin_pgbar_auto_hide_delay.setRange(500, 10000)
        dialog.spin_pgbar_auto_hide_delay.setSingleStep(100)
        dialog.spin_pgbar_auto_hide_delay.setSuffix(" ms")
        dialog.spin_pgbar_auto_hide_delay.setValue(config.get('pgbar_auto_hide_delay_ms', 2000))
        dialog.spin_pgbar_auto_hide_delay.setToolTip(
            "검색 완료 후 진행바 자동 숨김 시간\n"
            "권장: 2000ms (2초)"
        )
        ui_layout.addRow("Progress Bar 자동 숨김:", dialog.spin_pgbar_auto_hide_delay)

        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)

        # === 버튼 영역 ===
        button_layout = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_layout.accepted.connect(dialog.accept)
        button_layout.rejected.connect(dialog.reject)

        # 기본값 복원 버튼 추가
        reset_button = QPushButton("기본값 복원")
        reset_button.clicked.connect(lambda: self._reset_advanced_dialog_to_defaults(dialog))
        button_layout.addButton(reset_button, QDialogButtonBox.ResetRole)

        main_layout.addWidget(button_layout)

        dialog.setLayout(main_layout)
        return dialog

    def _extract_advanced_dialog_values(self, dialog):
        """다이얼로그에서 사용자 입력값 추출"""
        return {
            # 검색 옵션
            'expected_device_count': dialog.spin_expected_device_count.value(),
            'max_retry_count': dialog.spin_max_retry_count.value(),

            # Phase 1 타이밍
            'phase1_broadcast_timeout': dialog.dspin_broadcast_timeout.value(),
            'phase1_loop_select_timeout': dialog.dspin_loop_select_timeout.value(),
            'phase1_emit_stabilization_ms': dialog.spin_emit_delay.value(),
            'skip_phase1_emit_delay': dialog.cb_skip_emit_delay.isChecked(),

            # Phase 3 타이밍
            'phase3_device_query_timeout': dialog.dspin_device_query_timeout.value(),

            # TCP 설정
            'tcp_max_parallel_workers': dialog.spin_tcp_max_workers.value(),

            # UI 설정
            'pgbar_update_percent': dialog.spin_pgbar_update_step.value(),
            'pgbar_auto_hide_delay_ms': dialog.spin_pgbar_auto_hide_delay.value(),
        }

    def _apply_advanced_search_settings(self, updates):
        """Advanced Search Options 설정 적용"""
        try:
            # 내부 변수 업데이트
            self.retry_search_expected_count = updates['expected_device_count']
            self.retry_search_max_count = updates['max_retry_count']

            # YAML 파일 업데이트
            self.device_search_config.update_config_values(updates)

            # 인스턴스 변수 즉시 업데이트 (다음 검색부터 적용)
            if 'phase1_broadcast_timeout' in updates:
                self.search_pre_wait_time = updates['phase1_broadcast_timeout']

            # WIZMSGHandler 클래스 변수 즉시 업데이트
            from WIZMSGHandler import WIZMSGHandler
            WIZMSGHandler.loop_select_timeout = updates['phase1_loop_select_timeout']
            WIZMSGHandler.emit_stabilization_ms = updates['phase1_emit_stabilization_ms']
            WIZMSGHandler.skip_phase1_emit_delay = updates['skip_phase1_emit_delay']

            # 인스턴스 변수 업데이트
            self.search_wait_time_each = updates['phase3_device_query_timeout']

            self.logger.info(f"Advanced search options applied: {updates}")
            QtWidgets.QMessageBox.information(
                self,
                "설정 저장",
                "고급 검색 옵션이 저장되었습니다.\n\n"
                "일부 설정은 다음 검색부터 적용됩니다."
            )

        except Exception as e:
            self.logger.error(f"Failed to apply advanced search options: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "오류",
                f"설정 저장 실패:\n{e}"
            )

    def _reset_advanced_dialog_to_defaults(self, dialog):
        """Advanced Search Options 다이얼로그 기본값 복원"""
        reply = QtWidgets.QMessageBox.question(
            dialog,
            "기본값 복원 확인",
            "모든 고급 검색 옵션을 기본값으로 되돌리시겠습니까?\n\n"
            "이 작업은 즉시 저장되며, 되돌릴 수 없습니다.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # DeviceSearchConfig 기본값 복원
                if not self.device_search_config.reset_to_defaults():
                    QtWidgets.QMessageBox.warning(
                        dialog,
                        "복원 실패",
                        "기본값 복원에 실패했습니다.\n로그를 확인해주세요."
                    )
                    return

                # 다이얼로그 위젯 값 업데이트
                from device_search_config import DeviceSearchConfig
                defaults = DeviceSearchConfig.get_defaults()

                # 검색 옵션 기본값
                dialog.spin_expected_device_count.setValue(0)
                dialog.spin_max_retry_count.setValue(3)

                # Phase 1 타이밍 기본값
                dialog.dspin_broadcast_timeout.setValue(defaults['phase1']['broadcast_timeout_sec'])
                dialog.dspin_loop_select_timeout.setValue(defaults['phase1']['loop_select_timeout_sec'])
                dialog.spin_emit_delay.setValue(defaults['phase1']['emit_stabilization_ms'])
                dialog.cb_skip_emit_delay.setChecked(False)

                # Phase 3 타이밍 기본값
                dialog.dspin_device_query_timeout.setValue(defaults['phase3']['device_query_timeout_sec'])

                # TCP 설정 기본값
                dialog.spin_tcp_max_workers.setValue(defaults['tcp']['max_parallel_workers'])

                # UI 설정 기본값 (device_search_config.py의 DEFAULTS['ui']에서 가져오기)
                full_defaults = DeviceSearchConfig.DEFAULTS
                dialog.spin_pgbar_update_step.setValue(full_defaults['ui']['progress_bar']['update_percent'])
                dialog.spin_pgbar_auto_hide_delay.setValue(full_defaults['ui']['progress_bar']['auto_hide_delay_ms'])

                # 내부 변수 업데이트
                self.retry_search_expected_count = 0
                self.retry_search_max_count = 3

                # WIZMSGHandler 클래스 변수 업데이트
                from WIZMSGHandler import WIZMSGHandler
                WIZMSGHandler.loop_select_timeout = defaults['phase1']['loop_select_timeout_sec']
                WIZMSGHandler.emit_stabilization_ms = defaults['phase1']['emit_stabilization_ms']
                WIZMSGHandler.skip_phase1_emit_delay = False

                # 인스턴스 변수 업데이트
                self.search_wait_time_each = defaults['phase3']['device_query_timeout_sec']

                QtWidgets.QMessageBox.information(
                    dialog,
                    "복원 완료",
                    "모든 설정이 기본값으로 복원되었습니다."
                )

                self.logger.info("Advanced search options 기본값 복원 완료")

            except Exception as e:
                self.logger.error(f"기본값 복원 실패: {e}")
                QtWidgets.QMessageBox.critical(
                    dialog,
                    "오류",
                    f"기본값 복원 중 오류가 발생했습니다:\n{e}"
                )

    # ========== CSV 저장/불러오기 ==========

    def save_searched_results_to_csv(self):
        """검색 결과를 CSV 파일로 저장"""
        # 검색 결과 확인
        if not hasattr(self, 'mac_list') or not self.mac_list:
            QtWidgets.QMessageBox.critical(
                self,
                "저장 실패",
                "검색된 장비가 없습니다."
            )
            return

        # 파일 다이얼로그 (이전 경로 사용)
        default_filename = "searched_results.csv"
        if self.last_csv_directory:
            default_path = os.path.join(self.last_csv_directory, default_filename)
        else:
            default_path = default_filename

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "검색 결과 저장",
            default_path,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 헤더 (Phase 1 모든 정보 포함)
                writer.writerow([
                    'Mac Address', 'Device Name', 'Firmware Version', 'Status', 'Operation Mode', 'Detected',
                    'IP Address', 'Subnet Mask', 'Gateway', 'DNS', 'IP Mode', 'Local Port'
                ])

                # 데이터
                for i in range(len(self.mac_list)):
                    mac = self.mac_list[i].decode('utf-8') if isinstance(self.mac_list[i], bytes) else self.mac_list[i]
                    name = self.mn_list[i].decode('utf-8') if isinstance(self.mn_list[i], bytes) else self.mn_list[i]
                    version = self.vr_list[i].decode('utf-8') if isinstance(self.vr_list[i], bytes) else self.vr_list[i]
                    status = self.st_list[i].decode('utf-8') if isinstance(self.st_list[i], bytes) else self.st_list[i]
                    # Operation Mode (OP) - Phase 1에서 받은 정보
                    op_mode = ''
                    if hasattr(self, 'mode_list') and i < len(self.mode_list):
                        op_mode = self.mode_list[i].decode('utf-8') if isinstance(self.mode_list[i], bytes) else self.mode_list[i]
                    detected = "Yes" if (hasattr(self, 'detected_list') and i < len(self.detected_list) and self.detected_list[i]) else "No"

                    # dev_profile에서 네트워크 정보 가져오기
                    profile = self.dev_profile.get(mac, {})
                    ip_addr = profile.get('LI', '')
                    subnet = profile.get('SM', '')
                    gateway = profile.get('GW', '')
                    dns = profile.get('DS', '')
                    ip_mode = 'DHCP' if profile.get('IM', '0') == '1' else 'Static'
                    local_port = profile.get('LP', '')

                    writer.writerow([
                        mac, name, version, status, op_mode, detected,
                        ip_addr, subnet, gateway, dns, ip_mode, local_port
                    ])

            # 저장 성공 시 MRU 업데이트 (Save: 초기화)
            self.csv_mru_manager.add_saved_file(file_path, memo="")
            self.last_csv_directory = os.path.dirname(file_path)
            self.csv_mru_manager.set_last_directory(self.last_csv_directory)  # config 파일에 저장
            self.logger.info(f"Saved {len(self.mac_list)} devices to {file_path}")
            QtWidgets.QMessageBox.information(
                self,
                "저장 완료",
                f"{len(self.mac_list)}개 장비 정보가 저장되었습니다."
            )
        except Exception as e:
            self.logger.error(f"Failed to save CSV: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "오류",
                f"CSV 저장 실패:\n{e}"
            )

    def load_searched_results_from_csv(self):
        """CSV 파일에서 검색 결과 불러오기"""
        # 파일 다이얼로그 (가장 최근 파일 경로 사용 - 파일명까지 포함)
        # 파일/디렉토리 존재 여부 확인하여 robust하게 처리
        mru_list = self.csv_mru_manager.get_mru_list()
        if mru_list:
            recent_path = mru_list[0]['path']
            if os.path.exists(recent_path):
                # 파일 존재: 파일명까지 선택 (최고의 UX)
                default_path = recent_path
            elif os.path.exists(os.path.dirname(recent_path)):
                # 파일 삭제됨, 디렉토리는 존재: 디렉토리만 사용
                default_path = os.path.dirname(recent_path)
                self.logger.info(f"MRU 파일 없음, 디렉토리 사용: {default_path}")
            else:
                # 디렉토리도 없음 (USB 제거, 네트워크 드라이브 연결 해제 등): last_directory로 폴백
                default_path = self.last_csv_directory if self.last_csv_directory else ""
                self.logger.warning(f"MRU 경로 접근 불가: {recent_path}, 폴백: {default_path}")
        else:
            # MRU 없으면 마지막 디렉토리만 사용
            default_path = self.last_csv_directory if self.last_csv_directory else ""

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "검색 결과 불러오기",
            default_path,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        # 기존 결과 확인
        if hasattr(self, 'mac_list') and self.mac_list:
            reply = QtWidgets.QMessageBox.question(
                self,
                "확인",
                "기존 검색 결과를 덮어쓰시겠습니까?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # 헤더 검증 (기본 필드만 필수, Operation Mode와 네트워크 정보는 선택)
                required_headers = {'Mac Address', 'Device Name', 'Firmware Version', 'Status', 'Detected'}
                if not required_headers.issubset(set(reader.fieldnames)):
                    raise ValueError(f"CSV 헤더 누락: {required_headers - set(reader.fieldnames)}")

                # 데이터 읽기
                mac_list = []
                mn_list = []
                vr_list = []
                st_list = []
                mode_list = []  # OP (Operation Mode) - Phase 1 정보
                detected_list = []
                network_info_list = []  # 네트워크 정보 임시 저장

                for row in reader:
                    mac_list.append(row['Mac Address'].encode('utf-8'))
                    mn_list.append(row['Device Name'].encode('utf-8'))
                    vr_list.append(row['Firmware Version'].encode('utf-8'))
                    st_list.append(row['Status'].encode('utf-8'))
                    # Operation Mode (선택 필드, 없으면 빈 문자열)
                    op_mode = row.get('Operation Mode', '')
                    mode_list.append(op_mode.encode('utf-8') if op_mode else b'')
                    detected_list.append(row['Detected'].lower() == 'yes')

                    # 네트워크 정보 (있으면 저장, 없으면 빈 문자열)
                    network_info_list.append({
                        'ip': row.get('IP Address', ''),
                        'subnet': row.get('Subnet Mask', ''),
                        'gateway': row.get('Gateway', ''),
                        'dns': row.get('DNS', ''),
                        'ip_mode': row.get('IP Mode', 'Static'),
                        'local_port': row.get('Local Port', '')
                    })

                # 내부 변수 업데이트
                self.mac_list = mac_list
                self.mn_list = mn_list
                self.vr_list = vr_list
                self.st_list = st_list
                self.mode_list = mode_list
                self.detected_list = detected_list

                # dev_data 딕셔너리 초기화 (장비 선택 시 필요)
                self.dev_data = {}
                # dev_profile 딕셔너리 초기화 (확장된 프로파일 생성)
                self.dev_profile = {}
                # searched_dev 리스트 초기화
                self.searched_dev = []

                for i in range(len(self.mac_list)):
                    mac_str = self.mac_list[i].decode('utf-8')
                    name_str = self.mn_list[i].decode('utf-8')
                    version_str = self.vr_list[i].decode('utf-8')
                    status_str = self.st_list[i].decode('utf-8')
                    net_info = network_info_list[i]

                    # dev_data 초기화
                    self.dev_data[mac_str] = [name_str, version_str, status_str]

                    # dev_profile 초기화 (네트워크 정보 포함)
                    self.dev_profile[mac_str] = {
                        'MC': mac_str,
                        'MN': name_str,
                        'VR': version_str,
                        'ST': status_str,
                        'LI': net_info['ip'],
                        'SM': net_info['subnet'],
                        'GW': net_info['gateway'],
                        'DS': net_info['dns'],
                        'IM': '1' if net_info['ip_mode'] == 'DHCP' else '0',
                        'LP': net_info['local_port'],
                    }

                    # searched_dev 리스트 초기화
                    self.searched_dev.append([mac_str, name_str, version_str, status_str])

                # 검색 결과 수 업데이트
                self.searched_devnum = len(self.mac_list)
                self.searched_num.setText(str(self.searched_devnum))

                # 테이블 업데이트
                self._update_device_table()

                # 불러오기 성공 시 MRU 업데이트 (Load: access_count 증가)
                self.csv_mru_manager.add_loaded_file(file_path)
                self.last_csv_directory = os.path.dirname(file_path)
                self.csv_mru_manager.set_last_directory(self.last_csv_directory)  # config 파일에 저장
                self.logger.info(f"Loaded {len(self.mac_list)} devices from {file_path}")

                # Phase 2 자동 실행 (최신 정보 재수집)
                # Device Search 버튼 클릭과 동일하게 동작 (반복 검색 옵션 자동 적용)
                self._execute_phase2_from_csv()
        except Exception as e:
            self.logger.error(f"Failed to load CSV: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "오류",
                f"CSV 불러오기 실패:\n{e}"
            )

    def _execute_phase2_from_csv(self):
        """CSV Load 후 Phase 2 실행 (Device Search와 완전히 동일하게 동작)

        핵심 전략:
            - Phase 1은 CSV에서 로드 완료 (mac_list, mn_list, vr_list, st_list, mode_list)
            - get_search_result()를 직접 호출하여 Device Search와 동일한 로직 실행
            - 반복 검색 옵션 자동 적용 (cumulative_mode, retry_search)
            - csv_load_mode 플래그로 wizmsghandler 데이터 로드 건너뜀

        Device Search vs CSV Load:
            - Device Search: Phase 1 (Network Discovery) → get_search_result()
            - CSV Load:      Phase 1 (File Load)         → get_search_result()
            - Phase 2 이후는 완전히 동일 (반복 검색, Progress bar, 타이밍 등)
        """
        self.logger.info(f"Phase 2 실행 (CSV Load): {len(self.mac_list)}개 장비")

        # Device Search와 동일한 초기화
        self.retry_search_current = 0
        self._timing_t0 = time.time()
        self.logger.info("[TIMING] System timer started (CSV Load → Phase 2)")

        # CSV Load 모드 플래그 설정
        # - get_search_result()에서 wizmsghandler 데이터 로드 건너뜀
        # - 이미 CSV에서 mac_list, mn_list 등이 로드됨
        self.csv_load_mode = True

        # get_search_result() 호출 → Device Search와 동일한 로직 실행
        # - 반복 검색 로직 자동 적용
        # - get_dev_list() → search_each_dev() 자동 호출
        # - Progress bar, 타이밍 처리 자동
        devnum = len(self.mac_list)
        self.get_search_result(devnum)

        # 플래그 해제
        self.csv_load_mode = False

    def _update_device_table(self):
        """내부 변수 (mac_list 등)를 기반으로 테이블 업데이트"""
        # 테이블 초기화
        self.list_device.clearContents()
        self.list_device.setRowCount(0)

        # 데이터 채우기
        for i in range(len(self.mac_list)):
            self.list_device.insertRow(i)

            # MAC Address
            mac_item = QTableWidgetItem(
                self.mac_list[i].decode('utf-8') if isinstance(self.mac_list[i], bytes) else self.mac_list[i]
            )
            self.list_device.setItem(i, 0, mac_item)

            # Device Name
            name_item = QTableWidgetItem(
                self.mn_list[i].decode('utf-8') if isinstance(self.mn_list[i], bytes) else self.mn_list[i]
            )
            self.list_device.setItem(i, 1, name_item)

            # Firmware Version
            version_item = QTableWidgetItem(
                self.vr_list[i].decode('utf-8') if isinstance(self.vr_list[i], bytes) else self.vr_list[i]
            )
            self.list_device.setItem(i, 2, version_item)

            # Status
            status_item = QTableWidgetItem(
                self.st_list[i].decode('utf-8') if isinstance(self.st_list[i], bytes) else self.st_list[i]
            )
            self.list_device.setItem(i, 3, status_item)

            # Detected (detected_list가 있는 경우)
            if hasattr(self, 'detected_list') and i < len(self.detected_list):
                detected_item = QTableWidgetItem("Yes" if self.detected_list[i] else "No")
                self.list_device.setItem(i, 4, detected_item)


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
        print("thread: del")
        self.wait()


if __name__ == "__main__":
    
    # High DPI mode
    from PyQt5.QtCore import Qt
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    wizwindow = WIZWindow()
    wizwindow.show()
    app.exec_()
