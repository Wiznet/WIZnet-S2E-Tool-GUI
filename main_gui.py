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
from WIZ1x0MSGHandler import WIZ1x0Searcher, WIZ1x0Setter
from WIZ550MSGHandler import (
    WIZ550Searcher,
    WIZ550Getter,
    WIZ550Setter,
    WIZ550Resetter,
    OP_REMOTE_RESET,
    OP_FACTORY_RESET,
)
from wiz550_fw_dialog import WIZ550FWDialog
from certificatethread import certificatethread
from device_search_config import DeviceSearchConfig
from device_spec_loader import load_device, detect_device

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
import json
import subprocess
import webbrowser
import logging
import datetime
import csv
from pathlib import Path
from enum import Enum

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
    # QTabWidget,
    QLabel,
    # QGridLayout,
    QToolTip,
    QPushButton,
    QToolButton,
    QStyle,
    # QRadioButton,
    # QComboBox,
    # QCheckBox,
    # QGroupBox,
)
import ifaddr

# CSV MRU Manager
from csv_mru_manager import CSVMRUManager

# Terminal utility
from terminal.terminal_panel import TerminalPanel


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
    RETRY_DELAY_MS: int = 100  # 반복 간 딜레이 (밀리초)


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
        # pgbar 처리는 _finalize_timer(search_each_dev 완료 시)에서 담당
        # 여기서 pgbar를 건드리면 Phase 3 도중 hide()가 발화하는 타이밍 버그 발생

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

        html = "<h3>Errors occurred during search</h3><ul>"
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
        msgbox.setWindowTitle("Search Error")
        msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)  # IDE 경고 무시 (실제 작동함)
        msgbox.setText(self.to_html())
        msgbox.setStandardButtons(QMessageBox.Ok)
        msgbox.exec_()


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
        logger.debug("ClickableInfoLabel.mousePressEvent called")
        if ev and ev.button() == QtCore.Qt.MouseButton(1):  # 왼쪽 버튼만
            tooltip_text = self.toolTip()
            logger.debug(f"Tooltip text: {tooltip_text}")
            if tooltip_text:
                # 1단계: 기존 툴팁 숨기기 (호버 툴팁 제거)
                QToolTip.hideText()
                logger.debug("hideText() called")

                # 2단계: 클릭 위치 계산 (글로벌 좌표계)
                pos = self.mapToGlobal(ev.pos())
                logger.debug(f"Tooltip position: {pos}")

                # 3단계: 100ms 딜레이 후 툴팁 표시
                # → Qt 내부에서 hideText() 처리 완료 대기
                QtCore.QTimer.singleShot(100, lambda: self._show_tooltip_delayed(pos, tooltip_text))
                logger.debug("Timer scheduled for delayed tooltip")

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
        logger.debug("_show_tooltip_delayed called")
        QToolTip.showText(pos, text, self, self.rect(), UITooltipSettings.TOOLTIP_DURATION_MS)
        logger.debug(f"showText() executed with duration={UITooltipSettings.TOOLTIP_DURATION_MS}ms")


# VERSION = 'V1.5.5.1'  # github 이슈 #36 수정
VERSION = f'V{Path(resource_path("version")).read_text().strip()}'


# Load ui files
uic_logger = logging.getLogger("PyQt5.uic")
uic_logger.setLevel(logging.WARNING)
main_window = uic.loadUiType(resource_path("gui/wizconfig_gui.ui"))[0]


class WIZWindow(QMainWindow, main_window):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ch0_flow .ui 정적 항목 보존 (BUG-W550-AC anti-stale 복원용).
        # WIZ550 진입 시 콤보를 enum 2항목으로 재구성하므로, 일반 장치 복귀 시 되돌린다.
        self._default_flow_items = [
            self.ch0_flow.itemText(i) for i in range(self.ch0_flow.count())
        ]

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
        self.dev_data = {}
        self.searched_dev = []
        self.searched_devnum = None
        self.conf_sock = None
        self._finalize_timer = None
        self.mode_list = []
        self._timing_t0 = None
        self.all_response = []
        self.eachdev_info = []
        self.final_status_message = ""
        self.tab_structure = {}
        self.factory_setting_action: "QAction | None" = None
        self.factory_firmware_action: "QAction | None" = None
        self.netconfig_menu: "QMenu | None" = None
        self.net_list = []
        self.t_fwup = None
        self.th_cert = None
        self.certfont = None
        self.largefont = None
        self.csv_load_mode = False
        # init search option
        self.retry_search_num = 1
        self.search_wait_time = 3
        # CSV MRU Manager 초기화
        self.csv_mru_manager = CSVMRUManager()
        # CSV 경로 기억 (Save/Load Searched Results) - config/ui_state.json에서 로드
        self.last_csv_directory = self.csv_mru_manager.get_last_directory()

        # FW from Git
        try:
            from fw_git_fetcher import FWGitFetcher
            self._fw_fetcher = FWGitFetcher(resource_path("config/fw_sources.json"))
        except Exception as e:
            self.logger.warning(f"FWGitFetcher init failed: {e}")
            self._fw_fetcher = None
        self._fw_download_path = self._load_fw_download_path()

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
        # 직전 Apply에서 BOOT/UPGRADE 상태로 인해 축소 전송이 일어났는지
        self._setcmd_reduced = False

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
        WIZMSGHandler.set_command_delay_ms = self.timing_config.get_phase3_set_command_delay_ms()

        # 로그 레벨 초기 적용 + config 파일 실시간 감시
        _init_level = self.timing_config.get_log_level()
        self.logger.setLevel(_init_level)
        self.logger.info(f"[Config] Log level: {logging.getLevelName(_init_level)} (from {self.timing_config.config_file_path})")
        self._config_watcher = QtCore.QFileSystemWatcher(
            [str(self.timing_config.config_file_path)], self
        )
        self._config_watcher.fileChanged.connect(self._on_config_file_changed)
        # Windows에서 atomic save(temp→rename) 방식 편집기가 fileChanged를 못 올리는 경우 폴링으로 보완
        self._config_poll_mtime = os.path.getmtime(str(self.timing_config.config_file_path))
        self._config_poll_timer = QtCore.QTimer(self)
        self._config_poll_timer.timeout.connect(self._poll_config_file)
        self._config_poll_timer.start(2000)

        # 검증으로 기준값 복구된 설정이 있으면 GUI 표시 후 1회 통지 (P5)
        if getattr(self.timing_config, 'last_resets', None):
            QtCore.QTimer.singleShot(0, self._notify_config_resets)

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
        self.intv_time = 0

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
            # btn_upload uses setMenu() in init_ui_object() — clicked handled by menu actions
            self.btn_exit.clicked.connect(self.msg_exit)
        except Exception as e:
            self.logger.error(f"button event register error: {e}")

        # State Changed Event
        self.show_idcode.stateChanged.connect(self.event_idcode)
        self.show_connectpw.stateChanged.connect(self.event_passwd)
        self.show_idcodeinput.stateChanged.connect(self.event_input_idcode)
        self.enable_connect_pw.stateChanged.connect(self.event_passwd_enable)
        self.at_enable.stateChanged.connect(self.event_atmode)
        self.ch0_keepalive_enable.stateChanged.connect(self.event_keepalive)
        self.ch1_keepalive_enable.stateChanged.connect(self.event_keepalive)
        self.ip_dhcp.clicked.connect(self.event_ip_alloc)
        self.ip_static.clicked.connect(self.event_ip_alloc)
        self.ip_pppoe.clicked.connect(self.event_ip_alloc)

        # WIZ1x0SR 검색 체크박스 → 경고 레이블 show/hide
        self.chk_wiz1x0_search.stateChanged.connect(
            lambda state: self.lbl_wiz1x0_search_warn.setStyleSheet(
                "color: #e08000;" if state == Qt.Checked else "color: transparent;"
            )
        )

        # WIZ107SR/108SR: DDNS enable 토글, Network Protocol, 9-bit databit 제약
        self.ddns_enable.stateChanged.connect(self.event_ddns_enable)
        self.ch0_databit.currentIndexChanged.connect(self.event_ch0_databit_changed)

        # Event: OP mode
        self.ch0_tcpclient.clicked.connect(self.event_opmode)
        self.ch0_tcpserver.clicked.connect(self.event_opmode)
        self.ch0_tcpmixed.clicked.connect(self.event_opmode)
        self.ch0_udp.clicked.connect(self.event_opmode)
        self.ch0_ssl_tcpclient.clicked.connect(self.event_opmode)
        self.ch0_mqttclient.clicked.connect(self.event_opmode)
        self.ch0_mqtts_client.clicked.connect(self.event_opmode)

        self.ch1_tcpclient.clicked.connect(self.event_opmode)
        self.ch1_tcpserver.clicked.connect(self.event_opmode)
        self.ch1_tcpmixed.clicked.connect(self.event_opmode)
        self.ch1_udp.clicked.connect(self.event_opmode)

        # Event: Search method
        self.broadcast.clicked.connect(self._on_broadcast_selected)
        self.unicast_ip.clicked.connect(self._on_unicast_selected)
        # self.unicast_mac.clicked.connect(self.event_search_method)
        self.localip.textChanged.connect(
            lambda text: self.search_ipaddr.setText(text) if text and self.unicast_ip.isChecked() else None
        )

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
        self.actionDeviceSearch = QAction("Device Search", self)
        self.actionDeviceSearch.setShortcut(QtGui.QKeySequence("F5"))
        self.actionDeviceSearch.setShortcutContext(Qt.WindowShortcut)
        self.actionDeviceSearch.triggered.connect(self._on_search_button_clicked)
        self.menuFile.insertAction(self.actionExit, self.actionDeviceSearch)
        self.menuFile.insertSeparator(self.actionExit)
        self.actionExit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.actionExit.setShortcutContext(Qt.ApplicationShortcut)

        self._sc_apply = QtWidgets.QShortcut(QtGui.QKeySequence("F4"), self)
        self._sc_apply.setContext(Qt.WindowShortcut)
        self._sc_apply.activated.connect(self.btn_setting.click)

        self._action_apply = QAction("Apply Settings", self)
        self._action_apply.setShortcut(QtGui.QKeySequence("F4"))
        self._action_apply.triggered.connect(self.btn_setting.click)
        self.menuFile.insertAction(self.actionExit, self._action_apply)
        self.menuFile.insertSeparator(self.actionExit)

        self._sc_fw_upload = QtWidgets.QShortcut(QtGui.QKeySequence("F8"), self)
        self._sc_fw_upload.setContext(Qt.WindowShortcut)
        self._sc_fw_upload.activated.connect(self.btn_upload.click)

        self._action_terminal = QAction("Terminal", self)
        self._action_terminal.setCheckable(True)
        self._action_terminal.setShortcut(QtGui.QKeySequence("Ctrl+T"))
        self._action_terminal.setShortcutContext(Qt.ApplicationShortcut)
        self._action_terminal.triggered.connect(self._toggle_terminal)
        self.menuOption.addSeparator()
        self.menuOption.addAction(self._action_terminal)

        self._action_fw_dl_path = QAction("FW Download Path...", self)
        self._action_fw_dl_path.triggered.connect(self.event_set_fw_download_path)
        self.menuOption.addAction(self._action_fw_dl_path)

        self.menuOption.addSeparator()
        self._log_level_menu = QMenu("Log Level", self)
        self._log_level_actions = {}
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR"):
            act = QAction(lvl, self)
            act.setCheckable(True)
            self._log_level_menu.addAction(act)
            self._log_level_actions[lvl] = act
        self._sync_log_level_menu(logging.getLevelName(self.logger.level))
        self._log_level_menu.triggered.connect(self._on_log_level_menu)
        self.menuOption.addMenu(self._log_level_menu)

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

        if self.netconfig_menu is not None:
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

        # Init network interface - 첫 번째 유효한 어댑터 자동 선택
        if self.combobox_net_interface.count() > 1:
            self.combobox_net_interface.setCurrentIndex(1)
            self.net_changed(1)
        else:
            self.combobox_net_interface.setCurrentIndex(0)

        self.cert_object_config()

        # ── 터미널 패널 초기화 ──────────────────────────────────
        self._terminal_panel = TerminalPanel(self)

        # 메인 툴바(gridLayout_102)에 터미널 버튼 삽입 — btn_exit 왼쪽
        # btn_exit: row=0, col=4 in gridLayout_102
        _grid = self.gridLayout_102
        _grid.removeWidget(self.btn_exit)

        self._btn_terminal = QToolButton()
        self._btn_terminal.setIcon(QApplication.style().standardIcon(QStyle.SP_ComputerIcon))
        self._btn_terminal.setText('Terminal')
        self._btn_terminal.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self._btn_terminal.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
        )
        self._btn_terminal.setCheckable(True)
        self._btn_terminal.setMinimumSize(85, 68)
        self._btn_terminal.setMaximumSize(240, 100)
        self._btn_terminal.setIconSize(QtCore.QSize(32, 32))
        self._btn_terminal.setFont(self.midfont)
        self._btn_terminal.setToolTip('Open/Close Terminal Panel')
        self._btn_terminal.clicked.connect(self._toggle_terminal)
        _grid.addWidget(self._btn_terminal, 0, 4)
        _grid.addWidget(self.btn_exit, 0, 5)

        self._sync_toolbar_stretch(_grid)

        self._terminal_panel.panel_hidden.connect(self._on_terminal_panel_hidden)

        # 장치 목록 우클릭 메뉴
        self.list_device.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_device.customContextMenuRequested.connect(
            self._device_list_context_menu
        )

    @funclog(logger)
    def init_ui_object(self):
        """
        Initial config based WIZ750SR series
        """
        # Tab information save
        # .ui 탭 순서: basic(0), advance(1), ddns_pppoe(2), userio(3), mqtt(4), certificate(5)
        self.ddns_pppoe_tab_text = self.generalTab.tabText(2)
        self.userio_tab_text = self.generalTab.tabText(3)
        self.mqtt_tab_text = self.generalTab.tabText(4)
        self.certificate_tab_text = self.generalTab.tabText(5)
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
                "ddns_pppoe_tab": SysTabObjectText(self.ddns_pppoe_tab, self.ddns_pppoe_tab_text),
                "userio_tab": SysTabObjectText(self.userio_tab, self.userio_tab_text),
                "mqtt_tab": SysTabObjectText(self.mqtt_tab, self.mqtt_tab_text),
                "certificate_tab": SysTabObjectText(
                    self.certificate_tab, self.certificate_tab_text
                ),
            }
        except Exception as e:
            self.logger.error(f"init_ui_object: {e}")

        # Initial tab — 높은 인덱스부터 제거
        self.generalTab.removeTab(6)
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
        self.groupbox_ch0_timeout.hide()
        # self.groupbox_ch0_timeout.setEnabled(False)

        # group_packing_12는 기본적으로 숨김 (W55RP20-S2E일 때만 표시)
        self.group_packing_12.hide()

        # group_packing_13은 기본적으로 숨김 (W55RP20-S2E, W232N, IP20일 때만 표시)
        self.group_packing_13.hide()

        # Channel 1 Modbus 옵션 그룹은 기본적으로 숨김
        self.ch1_group_modbus_option.hide()

        # Channel 1(탭) 연결/패킹 그룹 기본 숨김
        self.group_packing_14.hide()
        self.group_packing_15.hide()

        # Channel #1 Timeout group is only used for dedicated two-port security models
        self.groupbox_ch1_timeout.hide()
        self.groupbox_ch1_timeout.setEnabled(False)

        self.ch0_serial_connection_condition_connect.setMaxLength(30)
        self.ch0_serial_connection_condition_disconnect.setMaxLength(30)
        self.ch0_ethernet_connection_condition.setMaxLength(30)
        self.ch1_ethernet_connection_condition.setMaxLength(30)
        self.ch1_serial_connection_condition_connect.setMaxLength(30)
        self.ch1_serial_connection_condition_disconnect.setMaxLength(30)

        # DeviceSearchConfig 초기화 (앱 시작 시)
        if not hasattr(self, 'device_search_config'):
            self.device_search_config = DeviceSearchConfig()

        # 검색 옵션을 DeviceSearchConfig에서 로드
        config = self.device_search_config.get_current_values()
        self.retry_search_expected_count = config.get('expected_device_count', 0)
        self.retry_search_max_count = config.get('max_retry_count', 3)  # 기본값 3

        # cumulative_mode는 항상 True (UI 옵션 제거, 기능 유지)
        self.cumulative_mode = True

        # WIZ1x0SR 검색 스레드 (FIND/IMIN, UDP:1460)
        self.wiz1x0_searcher = None
        self._wiz1x0_search_pending = False  # WIZ1x0Searcher 완료 대기 중 플래그
        self._search_phase3_done = False      # search_each_dev() 완료 플래그
        # WIZ1x0SR 전용 패널: 초기 hidden, 시그널 연결
        self.wiz1x0_tab.setVisible(False)
        # WIZ550 검색 스레드 초기화 (Phase 6 — UI-01, D-07)
        self.wiz550_searcher = None
        self._wiz550_search_pending = False
        # WIZ550 QThread references — prevent "Destroyed while running" via GC (CR-01)
        self._wiz550_getter = None
        self._wiz550_setter = None
        self._wiz550_resetter = None
        self._connect_wiz1x0_signals()
        self._apply_wiz1x0_compact_layout()
        self._apply_wiz1x0_field_widths()

        # 디버깅 편의를 위한 기본값 설정 (Search method 라디오 버튼만)
        self.broadcast.setChecked(True)  # UDP Broadcast 검색 선택
        self.logger.info(f"검색 설정 로드 완료: expected_device_count={self.retry_search_expected_count}, max_retry_count={self.retry_search_max_count}, cumulative_mode=True")

        # WIZ5XXSR-RP_E-SAVE 의 MQTT subtopic 확장(U3~U9) 흔적.
        # E-SAVE 지원은 `E-Save` 브랜치에서만 유지하며 이 계열에는 커맨드
        # (WIZMakeCMD.cmd_wiz5xxsr_esave)도 .ui 위젯(lineedit_mqtt_subtopic_3~9)도
        # 없다. 그래서 아래 코드는 주석을 풀면 AttributeError 로 죽는다.
        # 여기 남은 subtopic 위젯은 _0/_1/_2 뿐이다.
        # `E-Save` 브랜치는 2023-08 에 갈라져 develop 이 474 커밋 앞서 있어
        # 그대로 가져올 수 없다. 요구사항·재구현 절차는 research 문서 참조:
        # 2026-08-25-esave-branch-requirements-extraction.md
        # for i in range(3, 10):
        #     lineedit_subtopic = getattr(self, f'lineedit_mqtt_subtopic_{i}')
        #     # lineedit_subtopic.hide()
        #     lineedit_subtopic.setEnabled(False)

        # btn_upload → 드롭다운 메뉴 (FW from local PC / FW from Git)
        upload_menu = QMenu(self)
        self._act_fw_local = upload_menu.addAction("FW from local PC")
        self._act_fw_git   = upload_menu.addAction("FW from Git")
        self.btn_upload.setMenu(upload_menu)
        self._act_fw_local.triggered.connect(self.event_upload_clicked)
        self._act_fw_git.triggered.connect(self.event_fw_from_git)

    def _sync_toolbar_stretch(self, grid):
        """툴바 gridLayout의 컬럼별 버튼 수를 세어 columnStretch를 자동 배분.
        버튼이 추가·제거될 때 다시 호출하면 비율이 자동 갱신된다."""
        col_count = {}
        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item is None:
                continue
            _, col, _, _ = grid.getItemPosition(i)
            widget = item.widget()
            layout = item.layout()
            if isinstance(widget, (QPushButton, QToolButton)):
                col_count[col] = col_count.get(col, 0) + 1
            elif layout is not None:
                n = sum(
                    1 for j in range(layout.count())
                    if isinstance(layout.itemAt(j).widget(), (QPushButton, QToolButton))
                )
                if n:
                    col_count[col] = col_count.get(col, 0) + n
        for col, n in col_count.items():
            grid.setColumnStretch(col, n)

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
        if not self.curr_dev:
            return
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
        text = netifs.text()
        if ':' not in text:
            return
        ifs = text.split(":", 1)
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
            mac_item = next((item for item in self.list_device.selectedItems() if item.column() == 0), None)
            if mac_item and mac_item.text() not in self.dev_profile:
                # Phase 3 미완료: curr_mac/dev/ver/st 는 설정하되 Apply 버튼 활성화는 스킵
                self.selected_devinfo()
                self.statusbar.showMessage('Retrieving device info, please wait...')
                return
            # WIZ550: minimal enable instead of object_config() (no command_groups in YAML → schema error)
            if mac_item and self.dev_profile.get(mac_item.text(), {}).get('_proto') == 'wiz550':
                self.selected_devinfo()
                for btn in (self.btn_reset, self.btn_factory, self.btn_upload,
                            self.btn_setting, self.btn_saveconfig, self.btn_loadconfig):
                    btn.setEnabled(True)
                self.generalTab.setEnabled(True)
                self.generalTab.setTabEnabled(0, True)
                self.channel_tab.setEnabled(True)
                self.refresh_grp.setEnabled(True)
                return
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
                # IPv4만 처리 (ifaddr에서 IPv4는 str, IPv6는 tuple)
                if isinstance(ip.ip, str):
                    ipv4_addr = ip.ip
                    if ipv4_addr != "127.0.0.1":
                        net_ifs = ipv4_addr + ":" + adapter.nice_name
                        nice_name_lower = adapter.nice_name.lower()

                        # 가상 어댑터 판별
                        virtual_keywords = [
                            'virtualbox', 'vmware', 'hyper-v', 'vethernet',
                            'docker', 'wsl', 'tap-windows', 'npcap',
                            'virtual', 'vbox', 'bridge', 'loopback'
                        ]
                        is_virtual = any(k in nice_name_lower for k in virtual_keywords)

                        # 우선순위: 0=일반, 1=가상, 2=APIPA(169.254.*)
                        if ipv4_addr.startswith("169.254."):
                            priority = 2
                        elif is_virtual:
                            priority = 1
                        else:
                            priority = 0

                        ip_tuple = tuple(int(p) for p in ipv4_addr.split('.'))
                        adapter_list.append((priority, ip_tuple, net_ifs, adapter.nice_name))

        # 우선순위 → 같은 우선순위 내에서 IP 숫자 정렬 (첫 번째 옥텟 그룹핑 자연히 포함)
        adapter_list.sort(key=lambda x: (x[0], x[1]))

        # 정렬된 순서로 추가
        for priority, ip_tuple, net_ifs, nice_name in adapter_list:
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
        # 첫 번째 어댑터 자동 선택 후 net_changed 직접 호출 (index 변화 없을 때 signal 미발생 방지)
        if self.combobox_net_interface.count() > 1:
            self.combobox_net_interface.setCurrentIndex(1)
            self.net_changed(1)
        else:
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
        self.logger.debug("disable_object::channel_tab set tab disabled")
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
            self.logger.debug("object_config::channel_tab set tab enabled")
            self.channel_tab.setEnabled(True)
        else:
            self.logger.debug("object_config::channel_tab set tab disabled")
            self.channel_tab.setEnabled(False)
        self.event_passwd_enable()

        # enable menu
        self.save_config.setEnabled(True)
        self.load_config.setEnabled(True)

        self.event_opmode()
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
        # WIZ550 장치이면 전용 Apply 흐름으로 라우팅 (UI-03, Phase 6)
        if (hasattr(self, 'curr_mac') and self.curr_mac
                and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
            self.apply_wiz550()
            return
        if self.curr_dev == self.WIZ1X0_DISPLAY_NAME:
            self.apply_1x0()
            return
        self.do_setting()

    def event_reset_clicked(self):
        # WIZ550 장치이면 전용 Reset 흐름으로 라우팅 (UI-04, Phase 6)
        if (hasattr(self, 'curr_mac') and self.curr_mac
                and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
            self.reset_wiz550(op_code=OP_REMOTE_RESET)
            return
        if self.curr_dev == self.WIZ1X0_DISPLAY_NAME:
            self.show_msgbox("Info", "WIZ1x0SR automatically restarts when Apply is performed.", QMessageBox.Information)
            return
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
            # WIZ550 장치이면 전용 FactoryReset 흐름으로 라우팅 (UI-04, Phase 6)
            if (hasattr(self, 'curr_mac') and self.curr_mac
                    and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
                self.reset_wiz550(op_code=OP_FACTORY_RESET)
            else:
                self.event_factory_setting()
        elif "firmware" in opt:
            self.event_factory_firmware()

    def event_upload_clicked(self):
        # WIZ550 장치 전용 다이얼로그 (D-06)
        if (hasattr(self, 'curr_mac') and self.curr_mac
                and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'):
            self.upload_wiz550()
            return
        # 기존 WIZ1x0SR 처리 (미지원)
        if self.curr_dev == self.WIZ1X0_DISPLAY_NAME:
            self.show_msgbox("Info", "WIZ1x0SR firmware upload is not supported.", QMessageBox.Information)
            return
        # 기존 WIZ5xxSR 처리
        if self.localip_addr is not None:
            self.update_btn_clicked()
        else:
            self.show_msgbox(
                "Warning",
                "Local IP information could not be found. Check the Network configuration.",
                QMessageBox.Warning,
            )

    def upload_wiz550(self):
        """WIZ550 장치 TFTP FW 업로드 다이얼로그 실행 (D-06)."""
        if not self.curr_mac or self.curr_mac not in self.dev_profile:
            self.show_msgbox("Warning", "Unable to load device information. Please reselect the device.", QMessageBox.Warning)
            return

        dev_data = self.dev_profile[self.curr_mac]
        # WIZ550 profile은 'local_ip' 키 사용; 일반 장치는 'IP'
        target_ip = dev_data.get('local_ip', '') or dev_data.get('IP', '')
        target_mac = self.curr_mac
        # TFTP 서버 바인딩 IP = PC NIC IP (selected_eth), 장치 IP(localip_addr)가 아님
        localip = self.selected_eth or ''

        if not target_ip:
            self.show_msgbox("Warning", "Device IP information is missing. Please search for the device again.", QMessageBox.Warning)
            return

        dlg = WIZ550FWDialog(
            localip_addr=localip,
            target_ip=target_ip,
            target_mac=target_mac,
            parent=self,
        )
        dlg.exec_()

    def gpio_check(self):
        if not self.curr_dev:
            return
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

    def _current_ch0_opmode_index(self):
        if self.ch0_tcpclient.isChecked():
            return 0
        if self.ch0_tcpserver.isChecked():
            return 1
        if self.ch0_tcpmixed.isChecked():
            return 2
        if self.ch0_udp.isChecked():
            return 3
        if self.ch0_ssl_tcpclient.isChecked():
            return 4
        if self.ch0_mqttclient.isChecked():
            return 5
        if self.ch0_mqtts_client.isChecked():
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
        # 이 판정은 UI enable 뿐 아니라 get_object_value() 의 MB/PO 전송 여부도
        # 결정하므로 BOOT 만 제외한다. UPGRADE(DHCP·DNS 대기)는 앱이 도는
        # 일시 상태라 Modbus 커맨드를 정상 처리한다.
        if self.curr_st in DeviceStatusMinimum:
            return False
        if self._uses_mb_modbus():
            if self._is_wiz750sr_series():
                current_mode = self._current_ch0_opmode_index()
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
        if not self.curr_dev or not self.curr_ver:
            return

        # W55RP20-S2E, W232N, IP20인 경우에만 group_packing_12 표시 (SD/DD 기능)
        if self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
            self.group_packing_12.show()
            self.group_packing_13.show()
        else:
            self.group_packing_12.hide()
            self.group_packing_13.hide()

        is_security_two_port = self.curr_dev in SECURITY_TWO_PORT_DEV
        is_legacy_two_port = (
            (self.curr_dev in TWO_PORT_DEV or "WIZ752" in self.curr_dev)
            and not is_security_two_port
        )

        if is_legacy_two_port:
            self.ch0_group_modbus_option.hide()
            self.ch0_modbus_protocol.setCurrentIndex(0)
        else:
            self.ch0_group_modbus_option.show()

        if is_security_two_port:
            self.groupbox_ch1_timeout.show()
            self.groupbox_ch1_timeout.setEnabled(True)
        else:
            self.groupbox_ch1_timeout.hide()
            self.groupbox_ch1_timeout.setEnabled(False)

        self.logger.debug(
            f"model={self.curr_dev},ver={self.curr_ver},version compare={version_compare(self.curr_ver, '1.0.8')},status={self.curr_st}"
        )
        if self.curr_st in DeviceStatusMinimum:
            self.ch0_modbus_protocol.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)
            self.ch1_group_modbus_option.hide()
            return

        supports_modbus = not is_legacy_two_port and self._modbus_supported()
        self.ch0_modbus_protocol.setEnabled(supports_modbus)
        if not supports_modbus:
            self.ch0_modbus_protocol.setCurrentIndex(0)

        if is_security_two_port:
            self.ch1_group_modbus_option.show()
            self.ch1_modbus_protocol.setEnabled(True)
            self.group_packing_14.show()
            self.group_packing_15.show()
        else:
            self.ch1_group_modbus_option.hide()
            self.ch1_modbus_protocol.setCurrentIndex(0)
            self.group_packing_14.hide()
            self.group_packing_15.hide()

        self._config_serial_for_device()
        self._config_status_pin_for_device()
        self._config_security_options()

    def _apply_widget_override(self, widget, spec, name, default_enabled=True):
        """spec.ui_config.widget_overrides[name] 의 enabled/tooltip 을 위젯에 적용.

        YAML(`ui.widget_overrides`)이 위젯 활성 상태의 단일 기준이다.
        override 가 없으면 default_enabled(기본 활성)로 둔다 → 장치 전환 시 잔류 방지.
        예: WIZ550SR 은 data_bits 8 고정(FW DATA7BIT_ENABLE=0)이라 ch0_databit override(enabled:false).
        근거: doc/dev/WIZ550-serial-fw-reference-ko.md
        """
        wo = spec.ui_config.widget_overrides.get(name) if spec else None
        enabled = wo.enabled if (wo and wo.enabled is not None) else default_enabled
        widget.setEnabled(enabled)
        widget.setToolTip((wo.tooltip or "") if (wo and not enabled) else "")

    def _apply_visible_override(self, widget, spec, name, default_visible=True):
        """spec.ui_config.widget_overrides[name] 의 visible 만 위젯에 적용 (enabled/tooltip 불간섭).

        override 가 없으면 default_visible(기본 보임)로 리셋 → 장치 전환 시 직전 잔류 제거.
        enabled 상태는 다른 로직이 관리하므로 여기서 건드리지 않는다 (회귀 방지).
        """
        wo = spec.ui_config.widget_overrides.get(name) if spec else None
        visible = wo.visible if (wo and wo.visible is not None) else default_visible
        widget.setVisible(visible)

    def _apply_common_gating(self, spec) -> None:
        """장치 전환 시 'visible override 대상이지만 다른 곳에서 가시성을 재설정하지 않는'
        위젯을 baseline(보임)으로 리셋한 뒤 YAML override 를 적용한다. anti-stale 단일 지점.

        대상 4개:
          - ch0_mqttclient / ch0_modbus_protocol / ch0_uart_name: 코드 어디서도 setVisible 미호출
            → 한 장치(예: WIZ550SR)가 숨기면 복원할 곳이 없어 stale. 여기서 리셋이 필수.
          - ip_pppoe: 일반 경로(_apply_serial_from_spec)가 has_pppoe 로 최종 결정하므로
            여기선 wiz550 경로의 override(숨김) 적용 + 일반 경로용 리셋(보임)만 담당.
            (일반 경로에서는 이 호출 직후 has_pppoe 로직이 다시 좁힌다 → 순서 의존)
        override 없으면 default_visible=True. 위젯 누락 시 getattr 가드로 크래시 방지.
        """
        for name in ('ch0_mqttclient', 'ch0_modbus_protocol', 'ch0_uart_name', 'ip_pppoe'):
            w = getattr(self, name, None)
            if w is not None:
                self._apply_visible_override(w, spec, name)

    def _apply_serial_from_spec(self, spec) -> None:
        """DeviceSpec 기반으로 시리얼 포트 UI 설정."""
        # 0. 공통 게이팅 리셋 (anti-stale) — ip_pppoe 는 아래 has_pppoe 로직이 다시 좁히므로
        #    반드시 그 전에 호출한다. 나머지 3개는 여기서만 가시성이 복원된다.
        self._apply_common_gating(spec)
        # 1. ch0_baud
        br_entry = spec.cmdset.get('BR')
        if br_entry:
            sorted_br = sorted(br_entry.values.items(), key=lambda x: int(x[0]))
            br_strings = [v for _, v in sorted_br]
            current_br = None
            if self.curr_mac in self.dev_profile:
                br_raw = self.dev_profile[self.curr_mac].get('BR')
                if br_raw is not None:
                    try:
                        current_br = br_entry.values.get(str(int(br_raw)))
                    except (ValueError, TypeError):
                        pass
            self.ch0_baud.clear()
            self.ch0_baud.addItems(br_strings)
            if current_br:
                idx = self.ch0_baud.findText(current_br)
                if idx >= 0:
                    self.ch0_baud.setCurrentIndex(idx)

        # 2. ch1_baud (2채널 장치)
        if spec.channels == 2:
            eb_entry = spec.cmdset.get('EB')
            if eb_entry:
                sorted_eb = sorted(eb_entry.values.items(), key=lambda x: int(x[0]))
                eb_strings = [v for _, v in sorted_eb]
                current_eb = None
                if self.curr_mac in self.dev_profile:
                    eb_raw = self.dev_profile[self.curr_mac].get('EB')
                    if eb_raw is not None:
                        try:
                            current_eb = eb_entry.values.get(str(int(eb_raw)))
                        except (ValueError, TypeError):
                            pass
                self.ch1_baud.clear()
                self.ch1_baud.addItems(eb_strings)
                if current_eb:
                    idx = self.ch1_baud.findText(current_eb)
                    if idx >= 0:
                        self.ch1_baud.setCurrentIndex(idx)

        # 3. ip_pppoe — IM['2'] 존재 여부
        im_entry = spec.cmdset.get('IM')
        has_pppoe = im_entry is not None and '2' in im_entry.values
        self.ip_pppoe.setVisible(has_pppoe)

        # 4. DB 9-bit 항목
        db_entry = spec.cmdset.get('DB')
        has_9bit = db_entry is not None and '2' in db_entry.values
        if has_9bit:
            if self.ch0_databit.count() < 3:
                self.ch0_databit.addItem("9-bit")
        else:
            if self.ch0_databit.count() > 2:
                self.ch0_databit.removeItem(2)
            self.ch0_parity.setEnabled(True)
            self.ch0_stopbit.setEnabled(True)

        # 4b. ch0_databit — widget_override 기준 (WIZ550SR=8 고정 잠금, 그 외=활성).
        #     일반 장치 선택 시 항상 호출되어 SR 잠금 후 전환 잔류를 방지한다.
        self._apply_widget_override(self.ch0_databit, spec, 'ch0_databit')

        # 5. tcp_timeout — TR in search_cmd_list + widget_override
        tr_in_spec = 'TR' in spec.search_cmd_list
        wo = spec.ui_config.widget_overrides.get('tcp_timeout')
        visible = wo.visible if (wo and wo.visible is not None) else tr_in_spec
        enabled = wo.enabled if (wo and wo.enabled is not None) else tr_in_spec
        self.tcp_timeout.setVisible(visible)
        self.tcp_timeout_label.setVisible(visible)
        self.tcp_timeout.setEnabled(enabled)
        tip = (wo.tooltip or "") if (wo and not enabled) else ""
        self.tcp_timeout.setToolTip(tip)
        self.tcp_timeout_label.setToolTip(tip)
        self.tcp_timeout.setAttribute(Qt.WA_AlwaysShowToolTips, bool(tip))

        # 6. 콜백
        if has_9bit:
            self.event_ch0_databit_changed(self.ch0_databit.currentIndex())
        if 'DD' in spec.cmdset:
            self.event_ddns_enable()

    def _config_serial_for_device(self):
        """장치별 보드레이트/시리얼 포트 설정."""
        if not self.curr_dev:
            return
        spec_name = detect_device(self.curr_dev) or self.curr_dev
        try:
            spec = load_device(spec_name, self.curr_ver)
        except FileNotFoundError:
            self.logger.warning(f"_config_serial_for_device: spec not found for {spec_name!r}")
            return
        self._apply_serial_from_spec(spec)

    def _config_status_pin_for_device(self):
        """SC 상태 핀 옵션 설정."""
        if not self.curr_dev:
            return
        spec_name = detect_device(self.curr_dev) or self.curr_dev
        try:
            spec = load_device(spec_name, self.curr_ver)
        except FileNotFoundError:
            self.logger.warning(f"_config_status_pin_for_device: spec not found for {spec_name!r}")
            return

        # 이전 기준: curr_dev in SECURITY_DEVICE
        is_security = spec.family in ("security", "security_two_port")
        # 이전 기준: "WIZ107" in curr_dev or "WIZ108" in curr_dev → early return(no-op)
        # 신규: SC 없는 non-security → 명시적 hide (이전 장치 상태 잔류 방지)
        has_sc = 'SC' in spec.cmdset

        if is_security:
            self.radiobtn_group_s0.hide()
            self.radiobtn_group_s1.hide()
            self.group_dtrdsr.show()
            # 이전 기준: 'WIZ5XXSR' in curr_dev or curr_dev in W55RP20_FAMILY
            #             or 'W232N' in curr_dev or 'IP20' in curr_dev
            # 신규: security 기본값 True, 예외(WIZ510SSL)만 widget_override로 선언
            wo = spec.ui_config.widget_overrides.get('groupbox_ch0_timeout')
            ch1_to_vis = wo.visible if (wo and wo.visible is not None) else True
            self.groupbox_ch0_timeout.setVisible(ch1_to_vis)
            self.groupbox_ch0_timeout.setEnabled(ch1_to_vis)
        elif has_sc:
            self.radiobtn_group_s0.show()
            self.radiobtn_group_s1.show()
            self.group_dtrdsr.hide()
            self.groupbox_ch0_timeout.hide()
            self.groupbox_ch0_timeout.setEnabled(False)
        else:
            # SC 없는 non-security (WIZ107SR/108SR)
            self.radiobtn_group_s0.hide()
            self.radiobtn_group_s1.hide()
            self.group_dtrdsr.hide()
            self.groupbox_ch0_timeout.hide()
            self.groupbox_ch0_timeout.setEnabled(False)

    def _config_security_options(self):
        """SECURITY_DEVICE 관련 옵션 및 ch2 공통 옵션 설정."""
        if not self.curr_dev:
            return
        spec_name = detect_device(self.curr_dev) or self.curr_dev
        try:
            spec = load_device(spec_name, self.curr_ver)
        except FileNotFoundError:
            self.logger.warning(f"_config_security_options: spec not found for {spec_name!r}")
            return

        # 이전 기준: curr_dev in SECURITY_DEVICE
        is_security = spec.family in ("security", "security_two_port")

        # tcp_timeout: 이전에는 SECURITY_DEVICE에서 setEnabled(True) 강제 호출
        # 신규: _apply_serial_from_spec()에서 TR in search_cmd_list 기반으로 이미 처리 → 제거

        # factory_setting: 항상 활성 (이전과 동일)
        if self.factory_setting_action is not None:
            self.factory_setting_action.setEnabled(True)
        # factory_firmware: 이전 기준: SECURITY_DEVICE 여부 / 신규: spec.family 기반
        if self.factory_firmware_action is not None:
            self.factory_firmware_action.setEnabled(is_security)

        # ssl/mqtt: 이전 기준: SECURITY_DEVICE 여부
        # 신규: OP.values에 해당 인덱스 존재 여부 (결과 동일 — OP 4/5/6 보유 장치 = SECURITY_DEVICE)
        op_entry = spec.cmdset.get('OP')
        op_vals = op_entry.values if op_entry else {}
        self.ch0_ssl_tcpclient.setEnabled('4' in op_vals)
        self.ch0_mqttclient.setEnabled('5' in op_vals)
        self.ch0_mqtts_client.setEnabled('6' in op_vals)

        # group_current_bank: 이전 기준: SECURITY_DEVICE이면서 WIZ5XXSR/W55RP20/W232N/IP20 제외
        # = 사실상 WIZ510SSL만 표시. 신규: widget_override visible: true (WIZ510SSL.yaml에만 선언)
        wo_bank = spec.ui_config.widget_overrides.get('group_current_bank')
        bank_visible = wo_bank.visible if (wo_bank and wo_bank.visible is not None) else False
        self.group_current_bank.setVisible(bank_visible)
        if bank_visible:
            self.combobox_current_bank.setEnabled(False)

        # ch2 ssl/mqtt: 항상 비활성 (이전과 동일)
        self.ch1_ssl_tcpclient.setEnabled(False)
        self.ch1_mqttclient.setEnabled(False)
        self.ch1_mqtts_client.setEnabled(False)

    def general_tab_config(self):
        """버튼 아래 일반 탭을 장비 종류와 상태에 따라 다르게 설정합니다.
        SECURITY_DEVICE 이면 BOOT/UPGRADE 모드가 아닌 경우 mqtt, 인증서 탭을 추가합니다.
        @mason 이사가 BOOT/UPGRADE 모드일 때 advance_tab 도 뺐으면 좋겠다고 해서 기존 코드에 advance_tab 추가 코드도 작성
        그 외 장비는 basic_tab, advance_tab 만 보여줌
        """
        if not self.curr_dev:
            return
        # General tab ui setup by device
        n_tabs: int = self.generalTab.count()
        self.logger.debug(f"n_tabs={n_tabs}")
        # 탭 인덱스(순서)와 이름을 구해 역순으로 정렬
        list_tabs: list = []
        for _i, _t in enumerate(range(n_tabs)):
            list_tabs.append(SysTabIndex(_i, self.generalTab.widget(_t).objectName()))
        list_tabs.sort(reverse=True)
        self.logger.debug(f"list_tabs={list_tabs}")
        if self.curr_dev in SECURITY_DEVICE:
            # print(f"tabs in generalTab({self.generalTab}) has {self.generalTab.count()} tabs")
            # self.generalTab.count() 가 탭 추가/삭제하는 과정에서 신뢰불가.
            # insertTab에 첫번째 인수로 인덱스를 줘도 실제로는 마지막 인덱스가 할당됨. 인덱스 보장 안됨.
            # 최초 한번 정확히 계산 후 자신의 작업을 계획에 맞게 진행해야 함.
            # BOOT/UPGRADE 상태라면 mqtt, certificate, advance 탭 삭제
            # 디바이스 상태가 DeviceStatusMinimum 이면 ExcludeTabInMinimum 에 속한 탭 삭제
            # 디바이스 상태가 DeviceStatusMinimum 이 아니면 ExcludeTabInMinimum 탭이 없으면 탭 추가
            if self.curr_st in DeviceStatusMinimum:
                _tab: SysTabIndex
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
                        self.logger.debug(f"_new_tab={_new_tab},_new_tab_object={_new_tab_object}")
                        if _new_tab_object is None:
                            continue
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
            self.logger.debug(f"list_tabs={list_tabs}")
            for _tab in list_tabs:
                self.logger.debug(f"tab={_tab}")
                if _tab.name in ExcludeTabInCommon:
                    self.generalTab.removeTab(_tab.idx)
                    list_tabs.remove(_tab)
                # WIZ107SR/108SR이 아닌 장치에서 ddns_pppoe_tab 제거
                elif _tab.name == "ddns_pppoe_tab" and not (
                    "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev
                ):
                    self.generalTab.removeTab(_tab.idx)
                    list_tabs.remove(_tab)
            next_tab_idx: int = len(list_tabs)
            # 넣어야할 탭 넣기
            for _new_tab in IncludeTabInCommon:
                if _new_tab not in repr(list_tabs):
                    _new_tab_object = self.tab_structure.get(_new_tab)
                    if _new_tab_object is None:
                        continue
                    self.generalTab.insertTab(
                        next_tab_idx, _new_tab_object.object, _new_tab_object.ui_text
                    )
                    self.generalTab.setTabEnabled(next_tab_idx, True)
                    next_tab_idx += 1
            # WIZ107SR/108SR 전용: DDNS/PPPoE 탭 추가
            if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
                if "ddns_pppoe_tab" not in repr(list_tabs):
                    ddns_tab_obj = self.tab_structure.get("ddns_pppoe_tab")
                    if ddns_tab_obj is not None:
                        self.generalTab.insertTab(
                            next_tab_idx, ddns_tab_obj.object, ddns_tab_obj.ui_text
                        )
                        self.generalTab.setTabEnabled(next_tab_idx, True)

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

        # WIZ550S2E mqtt 탭은 fill_devinfo_wiz550 에서 fw_ver 홀짝 확인 후 추가/제거.

    def channel_tab_config(self):
        if not self.curr_dev:
            return
        # channel tab config
        self.logger.debug(f"channel_tab_config::curr_st={self.curr_st}")
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
                self.logger.debug("channel_tab_config::channel_tab set tab enabled security 2port")
                self.channel_tab.setTabEnabled(0, True)
                self.channel_tab.setTabEnabled(1, True)
                return
            self.channel_tab.removeTab(1)
            self.logger.debug("channel_tab_config::channel_tab set tab enabled 1port")
            self.channel_tab.setTabEnabled(0, True)
        elif self.curr_dev in TWO_PORT_DEV or "WIZ752" in self.curr_dev:
            self.channel_tab.insertTab(1, self.tab_ch1, self.ch1_tab_text)
            self.logger.debug("channel_tab_config::channel_tab set tab enabled 2port")
            self.channel_tab.setTabEnabled(0, True)
            self.channel_tab.setTabEnabled(1, True)

    def event_localport_fix(self):
        if self.ch0_localport_fix.isChecked():
            self.ch0_localport.setEnabled(False)
        else:
            self.ch0_localport.setEnabled(True)

    def event_ip_alloc(self):
        # DHCP / PPPoE: IP 주소 필드 비활성화 (서버에서 자동 할당)
        if self.ip_dhcp.isChecked() or self.ip_pppoe.isChecked():
            self.localip.setEnabled(False)
            self.subnet.setEnabled(False)
            self.gateway.setEnabled(False)
            self.dns_addr.setEnabled(False)
        else:
            self.localip.setEnabled(True)
            self.subnet.setEnabled(True)
            self.gateway.setEnabled(True)
            self.dns_addr.setEnabled(True)

    def event_ddns_enable(self):
        """WIZ107SR/108SR: DDNS Enable 체크박스 토글에 따라 DDNS 설정 필드 활성화/비활성화"""
        enabled = self.ddns_enable.isChecked()
        for widget in (
            self.ddns_server_idx,
            self.ddns_server_port,
            self.ddns_user_id,
            self.ddns_password,
            self.ddns_domain,
        ):
            widget.setEnabled(enabled)

    def event_ch0_databit_changed(self, index):
        """WIZ107SR/108SR: 9-bit 선택 시 Parity=NONE, Stop bit=1 자동 설정 및 잠금"""
        if not (self.curr_dev and ("WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev)):
            return
        # index 2 = 9-bit
        is_9bit = (index == 2)
        if is_9bit:
            self.ch0_parity.setCurrentIndex(0)   # NONE
            self.ch0_stopbit.setCurrentIndex(0)  # 1-bit
        self.ch0_parity.setEnabled(not is_9bit)
        self.ch0_stopbit.setEnabled(not is_9bit)

    def event_keepalive(self):
        if self.ch0_keepalive_enable.isChecked():
            self.ch0_keepalive_initial.setEnabled(True)
            self.ch0_keepalive_retry.setEnabled(True)
        else:
            self.ch0_keepalive_initial.setEnabled(False)
            self.ch0_keepalive_retry.setEnabled(False)

        if self.ch1_keepalive_enable.isChecked():
            self.ch1_keepalive_initial.setEnabled(True)
            self.ch1_keepalive_retry.setEnabled(True)
        else:
            self.ch1_keepalive_initial.setEnabled(False)
            self.ch1_keepalive_retry.setEnabled(False)

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
        if self.ch0_tcpclient.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch0_tcpserver.isChecked():
            self.ch0_remote.setEnabled(False)
            self.ch0_group_modbus_option.setEnabled(True)

        elif self.ch0_tcpmixed.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch0_udp.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(True)

        elif self.ch0_ssl_tcpclient.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch0_mqttclient.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch0_mqtts_client.isChecked():
            self.ch0_remote.setEnabled(True)
            self.ch0_group_modbus_option.setEnabled(False)
            self.ch0_modbus_protocol.setCurrentIndex(0)

        ch1_modbus_available = self._modbus_supported()
        self.ch0_modbus_protocol.setEnabled(ch1_modbus_available)
        if not ch1_modbus_available:
            self.ch0_modbus_protocol.setCurrentIndex(0)

        supports_ch2_modbus = self.curr_dev in SECURITY_TWO_PORT_DEV

        if self.ch1_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(False)
                self.ch1_modbus_protocol.setCurrentIndex(0)
            else:
                self.ch0_group_modbus_option.setEnabled(False)
                self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch1_tcpserver.isChecked():
            self.ch1_remote.setEnabled(False)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(True)
            else:
                self.ch0_group_modbus_option.setEnabled(True)

        elif self.ch1_tcpmixed.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(False)
                self.ch1_modbus_protocol.setCurrentIndex(0)
            else:
                self.ch0_group_modbus_option.setEnabled(False)
                self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch1_udp.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(True)
            else:
                self.ch0_group_modbus_option.setEnabled(True)

        elif self.ch1_ssl_tcpclient.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(False)
                self.ch1_modbus_protocol.setCurrentIndex(0)
            else:
                self.ch0_group_modbus_option.setEnabled(False)
                self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch1_mqttclient.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(False)
                self.ch1_modbus_protocol.setCurrentIndex(0)
            else:
                self.ch0_group_modbus_option.setEnabled(False)
                self.ch0_modbus_protocol.setCurrentIndex(0)

        elif self.ch1_mqtts_client.isChecked():
            self.ch1_remote.setEnabled(True)
            if supports_ch2_modbus:
                self.ch1_group_modbus_option.setEnabled(False)
                self.ch1_modbus_protocol.setCurrentIndex(0)
            else:
                self.ch0_group_modbus_option.setEnabled(False)
                self.ch0_modbus_protocol.setCurrentIndex(0)

    def _on_broadcast_selected(self):
        self.search_ipaddr.setEnabled(False)
        self.search_port.setEnabled(False)
        self._reset_retry_counter()

    def _on_unicast_selected(self):
        if self.localip.text():
            self.search_ipaddr.setText(self.localip.text())
        self.search_ipaddr.setEnabled(True)
        self.search_port.setEnabled(True)
        self._reset_retry_counter()

    def _reset_retry_counter(self):
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

    # ── 프로토콜 계열 판정 (issue #67) ──────────────────────────────
    # 바이너리 설정 프로토콜 장치군 — ASCII 커맨드(TCP/UDP:50001)를 해석하지 못한다.
    #   'wiz550': UDP:6550 XOR 바이너리 (WIZ550SR/S2E/WEB — WIZ550MSGHandler)
    #   'wiz1x0': UDP:1460 FIND/SETT 바이너리 (WIZ100/105/110SR — WIZ1x0Profile)
    # search_each_dev()의 동일 판정과 값을 공유한다 — 수정 시 반드시 함께.
    BINARY_PROTOS = ('wiz550', 'wiz1x0')
    # '_proto'는 실시간 검색 결과에만 실리는 휘발성 필드다. CSV 로드
    # (load_searched_results_from_csv)는 dev_profile을 MC/MN/VR/... 만으로
    # 재구성하므로 '_proto'가 유실된다. 그 경우 CSV에도 살아남는 'MN'(장치명)으로
    # 2차 판정한다.
    # WIZ1x0 계열의 목록 표시명. 프로토콜에 모델명 필드 자체가 없어(100/105/110
    # 구별 불가) 도구가 붙이는 고정 이름이다. _merge_wiz1x0_results·curr_dev 비교·
    # BINARY_MN_PREFIXES가 전부 이 상수를 공유한다 — 표시명을 바꾸려면 여기만.
    WIZ1X0_DISPLAY_NAME = 'WIZ1x0SR'
    # 이 프리픽스는 "도구가 목록에 표시하는 이름" 기준이다 (CSV Device Name 컬럼의
    # 실제 출처가 그 표시명이므로):
    #   WIZ550 계열 → device_type ('WIZ550SR'/'WIZ550S2E'/'WIZ550WEB')
    #   WIZ1x0 계열 → WIZ1X0_DISPLAY_NAME
    # 주의: 'WIZ1'로 줄이면 WIZ107SR/108SR(ASCII 계열)까지 잘못 걸린다.
    BINARY_MN_PREFIXES = ('WIZ550', WIZ1X0_DISPLAY_NAME.upper())

    def _is_binary_proto_dev(self, mac):
        """mac 장치가 바이너리 설정 프로토콜 계열인지 판정한다.

        미선택(mac이 None/빈값)은 False — "바이너리라고 확인된 바 없음"이라는
        뜻이다. IP Address 검색은 아직 목록에 없는 장치를 IP로 찾는 기능이므로,
        정체 미상의 대상에는 ASCII TCP를 시도하는 것이 기본값이어야 한다.
        """
        if not mac:
            return False
        prof = self.dev_profile.get(mac, {})
        if prof.get('_proto') in self.BINARY_PROTOS:
            return True
        # '_proto' 유실 경로(CSV 로드 등) 대비: 장치명으로 재판정
        mn = str(prof.get('MN', '')).upper()
        return mn.startswith(self.BINARY_MN_PREFIXES)

    def socket_config(self):
        try:
            # Broadcast
            if self.broadcast.isChecked():
                bind_ip = self.selected_eth or ""
                self.conf_sock = WIZUDPSock(5000, 50001, bind_ip)
                self.logger.debug(f"socket_config: bind_ip={bind_ip!r}")
                try:
                    self.conf_sock.open()
                except OSError as e:
                    # selected_eth IP가 소멸(장치 재부팅/IP 변경 등)된 경우 INADDR_ANY로 재시도
                    self.logger.warning(f"socket_config: bind({bind_ip!r}) 실패({e}) → INADDR_ANY로 재시도")
                    self.conf_sock = WIZUDPSock(5000, 50001, "")
                    self.conf_sock.open()

            # IP Address unicast
            elif self.unicast_ip.isChecked():
                ip_addr = self.search_ipaddr.text()
                port = int(self.search_port.text())
                self.logger.debug(f"unicast: ip={ip_addr!r}, port={port}")

                # (1) TCP를 시도할 것인가 — 장치의 프로토콜 능력만으로 결정한다.
                # 바이너리 계열(WIZ550/WIZ1x0)은 ASCII 커맨드를 TCP로 해석하지
                # 못하므로 시도 자체가 낭비다. 그 외(ASCII 계열 + 미선택)는 시도한다.
                # 미선택을 반드시 포함해야 하는 이유: IP Address 검색은 "아직 목록에
                # 없는 장치를 IP로 찾는" 기능이라, 선택된 장치(curr_mac)를 전제로
                # 삼으면 닭-달걀이 되어 최초 검색이 영구히 불가능해진다.
                # (85f2865가 이 전제를 넣으면서 WIZ107SR 등 ASCII 장치의 TCP unicast
                # 검색이 통째로 죽었다 — issue #67)
                _tcp_mode = not self._is_binary_proto_dev(self.curr_mac)

                # (2) 차단 다이얼로그를 띄울 것인가 — (1)과는 별개의 UX 판단이다.
                # 사용자가 특정 ASCII 장치를 지목해 둔 상태의 실패만 "확정 실패"로
                # 보고 모달로 알린다. 미선택 상태의 실패는 탐색 시도 중 하나일
                # 뿐이므로 상태바로만 알리고 흐름을 막지 않는다.
                # (aa7b467이 복구한 WIZ5xxSR 다이얼로그 동작을 이 플래그가 이어받음.
                #  85f2865에서 이 두 판단이 _tcp_mode 하나로 합쳐지며 의미가 어긋난
                #  것이 #67의 근본 원인 — 다시 합치지 말 것)
                _show_dialog = _tcp_mode and bool(self.curr_mac)

                if _tcp_mode:
                    net_response = self.net_check_ping(ip_addr)
                    if net_response == 0:
                        self.conf_sock = self.connect_over_tcp(ip_addr, port)
                        if self.conf_sock is None:
                            self.isConnected = False
                            self.logger.info("TCP connection failed!: %s" % ip_addr)
                            # 다이얼로그를 띄우지 않는 경로에서도 상태바에는 반드시
                            # 남긴다. isConnected=False면 search_pre()의 검색 블록이
                            # 통째로 스킵되어, 사용자에게는 설명 없이 "0 devices"만
                            # 보이기 때문.
                            self.statusbar.showMessage(" TCP connection failed: %s" % ip_addr)
                            if _show_dialog:
                                self.msg_connection_failed()
                        else:
                            self.isConnected = True
                    else:
                        self.statusbar.showMessage(" Network unreachable: %s" % ip_addr)
                        if _show_dialog:
                            self.msg_not_connected(ip_addr)
                else:
                    # 바이너리 계열 선택 상태: ping·TCP 생략.
                    # (85f2865가 없애려던 무의미한 ping/TCP 대기를 이 분기가 유지)
                    self.logger.debug(f"binary-proto unicast: skip ping/TCP for {ip_addr}")
                    prof = self.dev_profile.get(self.curr_mac or '', {})
                    is_wiz1x0 = (
                        prof.get('_proto') == 'wiz1x0'
                        or str(prof.get('MN', '')).upper().startswith(
                            self.WIZ1X0_DISPLAY_NAME.upper()
                        )
                    )
                    if is_wiz1x0:
                        # WIZ1x0은 IP 지정 검색 채널이 미구현(VB6 TCP:1461 미이식).
                        # 이 분기 뒤에 도는 것은 WIZ550Searcher(UDP:6550)뿐이라
                        # WIZ1x0을 찾을 수 없다 — "검색 중" 거짓 안내 대신 사실을 알린다.
                        self.statusbar.showMessage(
                            " WIZ1x0SR: IP-address search not supported."
                            " Use Broadcast + 'WIZ1x0SR search' checkbox."
                        )
                    else:
                        # WIZ550 계열: WIZ550Searcher가 UDP:6550으로 unicast 검색 수행
                        self.statusbar.showMessage(f" Searching device: {ip_addr} via UDP:6550...")
                self.btn_search.setEnabled(True)

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
            if self.datarefresh is None or not self.datarefresh.rcv_list:
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
        # self.logger.info("[TIMING] System timer started at button click")

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
        # self.logger.info(f"[TIMING] {self._T()} search_pre() 진입 (retry #{self.retry_search_current})")

        if self.wizmsghandler is not None and self.wizmsghandler.isRunning():
            # self.logger.info(f"[TIMING] {self._T()} wizmsghandler 아직 실행 중 → wait() 대기")
            self.wizmsghandler.wait()
            # self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 완료")
            # print('wait')
        else:
            # 기존 연결 close
            self.sock_close()
            # self.logger.info(f"[TIMING] {self._T()} sock_close() 완료")

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
            if getattr(self, 'retry_search_current', 0) == 0:
                self.pgbar.hide()  # 완전히 새 검색: 이전 pgbar 초기화
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
            item_detected.setText("Detected")
            item_detected.setFont(self.midfont)
            self.list_device.setHorizontalHeaderItem(2, item_detected)

            # Set socket for search
            # self.logger.info(f"[TIMING] {self._T()} socket_config() 시작")
            _t_sock = time.time()
            self.socket_config()
            # self.logger.info(f"[TIMING] {self._T()} socket_config() 완료 ({(time.time() - _t_sock) * 1000:.1f}ms 소요)")
            _conf_sock = "None" if not hasattr(self, "conf_sock") else self.conf_sock
            # self.logger.info(f"search: conf_sock: {_conf_sock}")

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
                    # self.logger.info(f"[TIMING] {self._T()} wizmsghandler.start() 완료 → search_pre() 종료")

                # WIZ1x0SR 검색 (체크박스 ON 시)
                # 이전 searcher가 아직 실행 중이면 새로 시작하지 않음
                # → 반복 검색 retry마다 bind(5001) 시도 → WinError 10048 방지
                self._search_phase3_done = False
                if self.chk_wiz1x0_search.isChecked():
                    if self.wiz1x0_searcher is None or not self.wiz1x0_searcher.isRunning():
                        self._wiz1x0_search_pending = True
                        self.wiz1x0_searcher = WIZ1x0Searcher(
                            iface_ip=self.selected_eth if self.selected_eth else "",
                            repeat=3,
                            timeout=self.search_pre_wait_time,
                        )
                        self.wiz1x0_searcher.search_done.connect(self._merge_wiz1x0_results)
                        self.wiz1x0_searcher.start()
                        # self.logger.info(f"[TIMING] {self._T()} WIZ1x0Searcher.start() 완료")
                    else:
                        pass  # self.logger.info(f"[TIMING] {self._T()} WIZ1x0Searcher 이미 실행 중 — skip")
                else:
                    self._wiz1x0_search_pending = False

            # WIZ550 검색 — TCP unicast 모드에서도 항상 병행 실행 (WIZ550은 UDP 6550 전용)
            if self.wiz550_searcher is None or not self.wiz550_searcher.isRunning():
                self._wiz550_search_pending = True
                _wiz550_target_ip = (
                    self.search_ipaddr.text().strip()
                    if self.unicast_ip.isChecked() else ""
                )
                self.wiz550_searcher = WIZ550Searcher(
                    iface_ip=self.selected_eth if self.selected_eth else "",
                    timeout=self.search_pre_wait_time,
                    target_ip=_wiz550_target_ip,
                )
                self.wiz550_searcher.search_done.connect(self._merge_wiz550_results)
                self.wiz550_searcher.start()

    def _merge_wiz1x0_results(self, results: list):
        """WIZ1x0Searcher 완료 콜백 — 결과를 기존 device list에 병합."""
        self._wiz1x0_search_pending = False
        self.logger.info(f"[WIZ1x0] 검색 완료: {len(results)}개")

        existing_macs = self.mac_list_str()
        new_results = [(mac, d) for mac, d in results if mac not in existing_macs]
        if new_results:
            for mac_str, board_dict in new_results:
                self.mac_list.append(mac_str.encode())
                # 표시명 상수 공유 — BINARY_MN_PREFIXES(CSV 폴백 판정)가 이 값에 의존
                self.mn_list.append(self.WIZ1X0_DISPLAY_NAME)
                ver = board_dict.get('appver_str', '0.0')
                self.vr_list.append(ver.encode())
                self.st_list.append(b'normal')
                self.mode_list.append(b'0')
                self.detected_list.append(True)
                self.dev_profile[mac_str] = board_dict
            self.searched_devnum = len(self.mac_list)
            self.searched_num.setText(str(self.searched_devnum))
            _wiz1x0_bg = QtGui.QColor(0xE0, 0xF4, 0xFF)  # 연한 하늘색 배경
            for mac_str, board_dict in new_results:
                row = self.list_device.rowCount()
                self.list_device.insertRow(row)
                for col, text in [(0, mac_str), (1, self.WIZ1X0_DISPLAY_NAME), (2, "✓")]:
                    item = QTableWidgetItem(text)
                    item.setBackground(_wiz1x0_bg)
                    self.list_device.setItem(row, col, item)
            self.list_device.resizeRowsToContents()
            QApplication.processEvents()
        else:
            self.logger.debug("[WIZ1x0] 신규 장치 없음 (모두 중복 또는 결과 없음)")

        # Phase 3가 이미 끝난 경우 → Done 메시지를 최종 총수로 갱신 + pgbar 숨김
        if self._search_phase3_done:
            total = len(self.mac_list)
            import re
            base = getattr(self, 'final_status_message', f" Done. {total} devices found")
            # 숫자 부분만 갱신 (타이밍 등 뒤 문자열 보존)
            updated = re.sub(r'\d+(?= device)', str(total), base, count=1)
            # "WIZ1x0SR (UDP:1460) Searching..." 잔재 제거
            updated = re.sub(r'\s*\+\s*WIZ1x0SR \(UDP:1460\) Searching\.\.\.', '', updated)
            self.final_status_message = updated
            self.statusbar.showMessage(self.final_status_message)
            # Phase 3 완료 후 pgbar hide가 pending 상태였으면 이제 숨김
            self.pgbar.hide()

    def _merge_wiz550_results(self, results: list):
        """WIZ550Searcher 완료 콜백 — 검색 결과를 기존 장치 목록에 병합 (UI-01, D-07)."""
        self._wiz550_search_pending = False
        self.logger.info(f"[WIZ550] 검색 완료: {len(results)}개")

        existing_macs = self.mac_list_str()
        self.logger.debug(f"[WIZ550] existing_macs={existing_macs}, results_macs={[d['mac'] for d in results]}")
        new_results = [d for d in results if d['mac'] not in existing_macs]
        if new_results:
            _wiz550_bg = QtGui.QColor(0xD0, 0xFF, 0xD0)  # 연한 녹색 배경 (WIZ1x0 하늘색과 구분)
            for device_dict in new_results:
                mac_str = device_dict['mac']
                self.mac_list.append(mac_str.encode())
                self.mn_list.append(device_dict.get('device_type', 'WIZ550SR'))
                self.vr_list.append(device_dict.get('fw_str', '').encode())
                self.st_list.append(b'normal')
                self.mode_list.append(b'0')
                self.detected_list.append(True)
                self.dev_profile[mac_str] = device_dict  # _proto='wiz550' 포함

            self.searched_devnum = len(self.mac_list)
            self.searched_num.setText(str(self.searched_devnum))

            for device_dict in new_results:
                mac_str = device_dict['mac']
                row = self.list_device.rowCount()
                self.list_device.insertRow(row)
                for col, text in [
                    (0, mac_str),
                    (1, device_dict.get('device_type', 'WIZ550SR')),
                    (2, device_dict.get('fw_str', '')),
                ]:
                    item = QTableWidgetItem(text)
                    item.setBackground(_wiz550_bg)
                    self.list_device.setItem(row, col, item)
            self.list_device.resizeRowsToContents()
            QApplication.processEvents()
        else:
            self.logger.debug("[WIZ550] 신규 장치 없음 (모두 중복 또는 결과 없음)")

        # WIZMSGHandler가 실행되지 않은 경로(WIZ550 unicast 전용)에서는
        # get_search_result()가 호출되지 않으므로 get_dev_list()가 누락됨.
        # TCP unicast 흐름과 동일하게 get_dev_list()를 트리거해
        # search_each_dev() → _finalize_timer → pgbar.hide() 경로를 밟게 한다.
        _msghandler_done = (self.wizmsghandler is None or
                            not self.wizmsghandler.isRunning())
        if _msghandler_done:
            QtCore.QTimer.singleShot(0, self.get_dev_list)

    def mac_list_str(self):
        """self.mac_list를 str 집합으로 반환 (중복 체크용)."""
        result = set()
        for m in self.mac_list:
            try:
                result.add(m.decode('utf-8', errors='replace'))
            except Exception:
                pass
        return result

    def processing(self):
        self.btn_search.setEnabled(False)
        self.statusbar.showMessage(" Searching...")
        # 이전 검색의 자동 숨김 타이머 취소 (Phase 3 도중 hide() 방지)
        if hasattr(self, '_finalize_timer') and self._finalize_timer is not None:
            self._finalize_timer.stop()
        if getattr(self, 'retry_search_current', 0) == 0:
            # 첫 번째 검색: indeterminate 애니메이션 시작
            self.pgbar.setFormat(" ")
            self.pgbar.setRange(0, 0)
            self.pgbar.show()
        # k>0: 이미 표시 중 → 그대로 유지

    def _stop_pgbar_fill_timer(self):
        pass  # 타이머 없음 (하위 호환용 stub)

    def search_each_dev(self, dev_info_list):
        """Phase 3: 개별 장비 정보 조회 (pgbar 최적화 적용)"""
        cmd_list = []
        self.eachdev_info = []

        self.code = " "
        # self.all_response = []
        # WIZ1x0SR + WIZ550: 바이너리 프로토콜 장치 → WIZ5xxSR 텍스트 커맨드 제외 (UI-01, Pitfall 3)
        # 판정은 _is_binary_proto_dev로 통일 (issue #67 — MN 폴백 포함)
        dev_info_list = [
            d for d in dev_info_list
            if not self._is_binary_proto_dev(d[0])
        ]
        # self.logger.info(f"search_each_dev() dev_info_list: {dev_info_list}")
        total_devs = len(dev_info_list)

        # pgbar 최적화: 갱신 간격 계산
        try:
            update_percent = self.timing_config.get_pgbar_update_percent()
        except Exception as e:
            self.logger.warning(f"get_pgbar_update_percent 실패: {e}, 기본값 10 사용")
            update_percent = 10

        update_interval = self._calc_pgbar_update_interval(total_devs, update_percent)
        self.logger.debug(f"pgbar 갱신 간격: {update_interval}개마다 (총 {total_devs}개, {update_percent}%)")

        self.statusbar.showMessage(f" Querying devices... (0/{total_devs})")
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

                    if self._should_update_pgbar(idx, total_devs, update_interval):
                        self.statusbar.showMessage(f" Querying devices... ({idx + 1}/{total_devs})")
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

                # 모든 스레드 동시 대기 (병렬 실행, 총 시간 ≈ 최장 RTT)
                for idx, th in enumerate(threads):
                    th.wait()

                    if self._should_update_pgbar(idx, len(threads), update_interval):
                        self.statusbar.showMessage(f" Querying devices... ({idx + 1}/{total_devs})")
                        QApplication.processEvents()

                # 전용 소켓 정리
                for sock in dev_socks:
                    try:
                        sock.close()
                    except Exception:
                        pass

        # 시그널 큐 플러시: 미처리 getsearch_each_dev 시그널 모두 소화
        QApplication.processEvents()

        # System time 즉시 계산 (auto_hide_delay 전)
        if hasattr(self, '_timing_t0') and self._timing_t0 is not None:
            final_system_time = time.time() - self._timing_t0
            # self.logger.info(f"[TIMING] Phase 3 완료 System time: {final_system_time:.2f}s")

            # show_timing_in_statusbar 활성화 시 statusbar 메시지에 System time 반영
            show_timing = self.timing_config.get('logging', 'show_timing_in_statusbar', default=False)
            if show_timing and hasattr(self, 'final_status_message') and self.final_status_message:
                import re
                msg = re.sub(r',?\s*System\s+[\d.]+\s+seconds?\)?', '', self.final_status_message)
                msg = msg.rstrip(')')
                if '(' in msg:
                    msg += f", System {final_system_time:.2f} seconds)"
                else:
                    msg += f" (System {final_system_time:.2f} seconds)"
                self.final_status_message = msg

        # Phase 3 완료 마킹 — _merge_wiz1x0_results()에서 Done 지연 여부 판단에 사용
        self._search_phase3_done = True

        # Done 메시지 즉시 표시 (auto_hide_delay 전)
        # WIZ1x0SR 검색이 아직 진행 중이면 대기 메시지로 대체
        if hasattr(self, 'final_status_message'):
            if self._wiz1x0_search_pending:
                self.statusbar.showMessage(
                    self.final_status_message.rstrip() + "  +  WIZ1x0SR (UDP:1460) Searching..."
                )
            else:
                self.statusbar.showMessage(self.final_status_message)

        # 완료: indeterminate → determinate 전환 후 100%
        self.pgbar.setRange(0, 100)
        self.pgbar.setFormat(" ")
        self.pgbar.setValue(100)

        # _finalize_search: pgbar.hide()만 담당 (WIZ1x0SR 검색 중이면 대기)
        def _finalize_search():
            if self._wiz1x0_search_pending:
                return  # WIZ1x0SR 완료 후 _merge_wiz1x0_results에서 hide() 호출
            self.pgbar.hide()

        # cancellable QTimer: 이전 타이머를 stop()한 뒤 재시작
        if not hasattr(self, '_finalize_timer') or self._finalize_timer is None:
            self._finalize_timer = QtCore.QTimer(self)
            self._finalize_timer.setSingleShot(True)
        self._finalize_timer.stop()
        try:
            self._finalize_timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._finalize_timer.timeout.connect(_finalize_search)
        self._finalize_timer.start(self.timing_config.get_pgbar_auto_hide_delay_ms())

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
                self.logger.info(f"[GET] {mc} ({profile.get('MN','?')}) ip={profile.get('LI','?')}")
                self.logger.debug(f"[GET] {mc}: {profile}")

                # Phase 3 완료: 해당 행 색 복원 (주황-빨강 → 정상)
                for idx, mac_bytes in enumerate(self.mac_list):
                    mac_str = (
                        mac_bytes.decode('utf-8', errors='replace')
                        if isinstance(mac_bytes, bytes)
                        else str(mac_bytes)
                    )
                    if mac_str == mc:
                        for col in (0, 1):
                            _item = self.list_device.item(idx, col)
                            if _item:
                                _item.setForeground(QtGui.QColor(0, 0, 0))
                        break

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
                                self.mn_list[idx] = mn_from_profile
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
                self.statusbar.showMessage(" [Error] No MAC address (MC) in device response — item skipped")

            # 구 retry 메커니즘 (cumulative 모드에서는 항상 0)
            if self.search_retrynum:
                self.logger.info(self.search_retrynum)
                self.search_retrynum -= 1
                self.search_pre()

        except Exception as e:
            self.logger.error(e)
            self.msg_error("[ERROR] getsearch_each_dev(): {}".format(e))

    def get_search_result(self, devnum):
        # self.logger.info(f"[TIMING] {self._T()} get_search_result() 진입 (devnum={devnum}, emit→진입 시각)")

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
                self.logger.debug(f"유지/갱신 모드: 기존 {len(self.mac_list)}개 장비 유지, 검색됨 초기화")

        # Determine data source (wizmsghandler for UDP/TCP unicast)
        # CSV Load 모드에서는 건너뜀 (이미 데이터가 self.mac_list 등에 있음)
        data_source = None
        if not csv_load_mode and self.wizmsghandler is not None:
            data_source = self.wizmsghandler
            if self.wizmsghandler.isRunning():
                # self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 시작 (get_search_result에서 아직 실행 중)")
                self.wizmsghandler.wait()
                # self.logger.info(f"[TIMING] {self._T()} wizmsghandler.wait() 완료")

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
                    self.logger.debug(
                        f"[DIAG] WIZMSGHandler lists: mac={len(_d.mac_list)}"
                        f" mn={len(_d.mn_list)} vr={len(_d.vr_list)}"
                        f" st={len(_d.st_list)} mode={len(_d.mode_list)}"
                        f" rcv={len(_d.rcv_list)}"
                    )
                    # 정렬 이상 감지
                    lens = [len(_d.mac_list), len(_d.mn_list), len(_d.vr_list), len(_d.st_list)]
                    if len(set(lens)) > 1:
                        self.logger.warning(f"[DIAG] WIZMSGHandler 리스트 길이 불일치! {lens}")
                    # mn_list 내용 (비정상 바이트 포함 여부)
                    for _i, _mn in enumerate(_d.mn_list):
                        if '(' in _mn:
                            self.logger.warning(f"[DIAG] mn_list[{_i}] non-printable bytes: {_mn!r}")
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
                        # self.logger.info(f"[TIMING] {self._T()} _merge_search_results() 시작")
                        self._merge_search_results(new_mac_list, new_mn_list, new_vr_list, new_st_list, new_mode_list)
                        # self.logger.info(f"[TIMING] {self._T()} _merge_search_results() 완료")
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
                self.logger.debug(
                    f"[DIAG] 병합 후 self lists: mac={_self_lens[0]}"
                    f" mn={_self_lens[1]} vr={_self_lens[2]}"
                    f" st={_self_lens[3]} detected={_self_lens[4]}"
                )
                if len(set(_self_lens)) > 1:
                    self.logger.warning(f"[DIAG] self 리스트 길이 불일치! {_self_lens}")

                # row length = the number of searched devices
                # self.logger.info(f"[TIMING] {self._T()} 테이블 업데이트 시작 ({len(self.mac_list)}행)")
                self.list_device.setRowCount(len(self.mac_list))

                _loading_color = QtGui.QColor(200, 80, 0)  # 주황-빨강: Phase 3 수집 중
                _wiz550_bg = QtGui.QColor(0xD0, 0xFF, 0xD0)
                _black = QtGui.QColor(0, 0, 0)
                for i in range(0, len(self.mac_list)):
                    try:
                        mac_str = self.mac_list[i].decode('utf-8', errors='replace')
                        is_wiz550 = self.dev_profile.get(mac_str, {}).get('_proto') == 'wiz550'
                        fg = _black if is_wiz550 else _loading_color
                        # MAC 주소
                        item_mac = QTableWidgetItem(mac_str)
                        item_mac.setForeground(fg)
                        if is_wiz550:
                            item_mac.setBackground(_wiz550_bg)
                        self.list_device.setItem(i, 0, item_mac)
                        # 장비 이름
                        mn_str = self.mn_list[i] if i < len(self.mn_list) else ''
                        item_mn = QTableWidgetItem(mn_str)
                        item_mn.setForeground(fg)
                        if is_wiz550:
                            item_mn.setBackground(_wiz550_bg)
                        self.list_device.setItem(i, 1, item_mn)
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
                # self.logger.info(f"[TIMING] {self._T()} 테이블 업데이트 완료 (resize 포함: {(time.time() - _t_resize) * 1000:.1f}ms)")

            # mac_list 기반으로 카운트 재동기화 — WIZ550/_merge_wiz550_results가 먼저
            # 완료됐을 때 devnum(일반 프로토콜 수)이 전체 수를 덮어쓰는 것을 방지
            _total = len(self.mac_list)
            if _total != self.searched_devnum:
                self.searched_devnum = _total
                self.searched_num.setText(str(_total))

            # 반복 검색 로직 (유지/갱신 모드 + UDP broadcast 전용)
            # devnum == 0이어도 반복 검색 수행 (처음 응답 없던 장비가 나중에 응답할 수 있음)
            if self.cumulative_mode and self.broadcast.isChecked():
                self.retry_search_current += 1

                # 유지/갱신으로 발견된 전체 장비 수 (핵심 지표)
                total_count = len(self.mac_list)
                # 이번 검색에서 새로 발견된 장비 수 (로깅용 참고 정보)
                newly_detected = sum(1 for d in self.detected_list if d)

                self.logger.debug(f"반복 검색 {self.retry_search_current}회차: 전체 {total_count}개 (이번 검색: {newly_detected}개)")

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
                    self.logger.debug(f"최대 반복 횟수 도달: {self.retry_search_current}/{self.retry_search_max_count}")

                # 계속 반복할지 결정
                if should_continue:
                    self.logger.debug(f"반복 검색 계속: {self.retry_search_current + 1}회차 시작")
                    # 약간의 딜레이 후 재검색 (상수 사용)
                    # self.logger.info(f"[TIMING] {self._T()} QTimer.singleShot({RetrySearchLimits.RETRY_DELAY_MS}ms) 설정 → _continue_retry_search 예약")
                    QtCore.QTimer.singleShot(RetrySearchLimits.RETRY_DELAY_MS, self._continue_retry_search)
                    return  # get_dev_list() 호출하지 않음
                else:
                    # 반복 종료 - 타이밍 정보는 show_timing 옵션에 따라 표시
                    show_timing = self.timing_config.get('logging', 'show_timing_in_statusbar', default=False)
                    if show_timing:
                        if self.retry_search_start_time is not None:
                            elapsed = time.time() - self.retry_search_start_time
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries, {elapsed:.2f} seconds)"
                        else:
                            status_msg = f" Done. {total_count} devices found ({self.retry_search_current} retries)"
                    else:
                        status_msg = f" Done. {total_count} devices found"
                    if self.retry_search_start_time is not None:
                        self.retry_search_start_time = None  # 리셋

                    self.logger.info(f"반복 검색 완료: 총 {self.retry_search_current}회, {total_count}개 장비 발견")

                    # 상태바 메시지 업데이트 (진행바는 텍스트 없이 바만 표시)
                    self.final_status_message = status_msg
                    if self._wiz1x0_search_pending:
                        self.statusbar.showMessage(
                            self.final_status_message.rstrip() + "  +  WIZ1x0SR (UDP:1460) Searching..."
                        )
                    else:
                        self.statusbar.showMessage(self.final_status_message)

                    # 카운터 리셋
                    self.retry_search_current = 0
            else:
                # 일반 검색 완료 (비 반복 모드) - pgbar는 search_each_dev에서 처리
                # 타이밍 정보는 show_timing 옵션에 따라 표시
                show_timing = self.timing_config.get('logging', 'show_timing_in_statusbar', default=False)
                if show_timing and self.search_start_time is not None:
                    elapsed = time.time() - self.search_start_time
                    self.final_status_message = f" Done. {devnum} devices found ({elapsed:.2f} seconds)"
                else:
                    self.final_status_message = f" Done. {devnum} devices found"
                if self.search_start_time is not None:
                    self.search_start_time = None  # Reset for next search

                if self._wiz1x0_search_pending:
                    self.statusbar.showMessage(
                        self.final_status_message.rstrip() + "  +  WIZ1x0SR (UDP:1460) Searching..."
                    )
                else:
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
            # self.logger.info(f"[TIMING] {self._T()} _continue_retry_search() 진입 (QTimer 발화)")
            # search_pre 재호출 (detected_list는 유지)
            self.search_pre()
        except Exception as e:
            self.logger.error(f"반복 검색 중 오류: {e}")
            self.retry_search_current = 0
            # 사용자에게 알림
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Repeated Search Error",
                f"An error occurred during repeated search:\n{str(e)}\n\nSearch will be stopped."
            )

    # =========================================================================
    # Phase 2: 방어적 헬퍼 메서드
    # =========================================================================

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
                # 기존 장비 발견 → 데이터 갱신 (비어있지 않은 값만 덮어씀)
                idx = existing_mac_map[new_mac_str]
                if i < len(new_mn_list) and new_mn_list[i]:
                    self.mn_list[idx] = new_mn_list[i]
                if i < len(new_vr_list) and new_vr_list[i]:
                    self.vr_list[idx] = new_vr_list[i]
                if i < len(new_st_list) and new_st_list[i]:
                    self.st_list[idx] = new_st_list[i]
                if new_mode_list and i < len(new_mode_list) and new_mode_list[i]:
                    self.mode_list[idx] = new_mode_list[i]
                self.detected_list[idx] = True
                self.logger.debug(f"장비 갱신: {new_mac_str}")
            else:
                # 신규 장비 → 목록에 추가
                self.mac_list.append(new_mac_list[i])
                self.mn_list.append(new_mn_list[i] if i < len(new_mn_list) else '')
                self.vr_list.append(new_vr_list[i] if i < len(new_vr_list) else b'')
                self.st_list.append(new_st_list[i] if i < len(new_st_list) else b'')
                self.mode_list.append(new_mode_list[i] if new_mode_list and i < len(new_mode_list) else b'')
                self.detected_list.append(True)
                existing_mac_map[new_mac_str] = len(self.mac_list) - 1  # 이후 중복 방지
                self.logger.debug(f"신규 장비 추가: {new_mac_str}")

        detected_count = sum(1 for d in self.detected_list if d)
        total_count = len(self.mac_list)
        self.logger.debug(f"검색 결과 유지/갱신: 전체 {total_count}개 (현재 검색: {detected_count}개)")

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
                            self.mn_list[i],
                            self.vr_list[i].decode('utf-8', errors='replace'),
                            self.st_list[i].decode('utf-8', errors='replace'),
                        ]
                    )
                    self.dev_data[self.mac_list[i].decode('utf-8', errors='replace')] = [
                        self.mn_list[i],
                        self.vr_list[i].decode('utf-8', errors='replace'),
                        self.st_list[i].decode('utf-8', errors='replace'),
                    ]
            except Exception as e:
                self.logger.error(e)

            # print('get_dev_list()', self.searched_dev, self.dev_data)
            phase3_on_demand = self.timing_config.get('experimental', 'phase3_on_demand', default=False)
            if phase3_on_demand:
                # B-2: Phase 3 스킵 → Phase 1 완료 즉시 Done 처리
                self.logger.info("[B-2] phase3_on_demand 활성화: search_each_dev() 스킵")
                QApplication.processEvents()
                self.pgbar.setRange(0, 100)
                self.pgbar.setFormat(" ")
                self.pgbar.setValue(100)
                if not hasattr(self, '_finalize_timer') or self._finalize_timer is None:
                    self._finalize_timer = QtCore.QTimer(self)
                    self._finalize_timer.setSingleShot(True)
                self._finalize_timer.stop()
                try:
                    self._finalize_timer.timeout.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self._finalize_timer.timeout.connect(lambda: self.pgbar.hide())
                self._finalize_timer.start(self.timing_config.get_pgbar_auto_hide_delay_ms())
            else:
                self.search_each_dev(self.searched_dev)
        else:
            self.logger.info("There is no device.")

    def dev_clicked(self, param=None, call_from=None):
        # dev_info = []
        # clicked_mac = ""
        # if 'WIZ750' in self.curr_dev or 'WIZ5XX' in self.curr_dev:
        if self.curr_dev and ("WIZ750" in self.curr_dev or "WIZ750SR-T1L" in self.curr_dev):
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
        if macaddr not in self.dev_profile:
            self.statusbar.showMessage('Retrieving device info, please wait...')
            QToolTip.showText(QtGui.QCursor.pos(), "Collecting device information.\nPlease click again after the search completes.", self)
            return

        # WIZ1x0SR 전용 UI 패널
        if self.dev_profile.get(macaddr, {}).get('_proto') == 'wiz1x0':
            self.curr_mac = macaddr
            self.curr_dev = self.WIZ1X0_DISPLAY_NAME
            self._show_wiz1x0_panel(True)
            self.fill_devinfo_1x0(self.dev_profile[macaddr])
            return

        # WIZ550: reuse existing generalTab (no dynamic panel)
        if self.dev_profile.get(macaddr, {}).get('_proto') == 'wiz550':
            self.curr_mac = macaddr
            d = self.dev_profile[macaddr]
            device_type = d.get('device_type', 'WIZ550SR')
            self.curr_dev = device_type
            self.curr_ver = d.get('fw_str', '')
            self.curr_st = DeviceStatus.boot if d.get('is_boot') else DeviceStatus.app
            # hide wiz1x0 panel and restore generalTab
            self._show_wiz1x0_panel(False)
            # BOOT 상태에서는 Apply 차단 (BOOT 펌웨어는 SET_INFO 미처리)
            self.btn_setting.setEnabled(self.curr_st not in DeviceStatusMinimum)
            # show basic_tab + advance_tab, remove mqtt/certificate tabs
            self.general_tab_config()
            # fetch latest config via GET_INFO
            self._wiz550_getter = WIZ550Getter(
                target_mac=macaddr,
                device_type=device_type,
                iface_ip=self.selected_eth or "",
            )
            self._wiz550_getter.get_done.connect(
                lambda cfg, mac=macaddr, dtype=device_type:
                    self._on_wiz550_get_done(cfg, mac, dtype)
            )
            self._wiz550_getter.start()
            self.statusbar.showMessage(f" Reading WIZ550 settings... ({macaddr})")
            return

        # standard device: hide wiz1x0 panel and restore default UI
        self._show_wiz1x0_panel(False)

        try:
            self.object_config()
        except Exception as e:
            self.logger.error(f"get_clicked_devinfo:object_config:{e}")

        # print(f"2nd caller={call_from}")
        # @TODO 문구 개선 (2024-07-17 `2b3a96b` 이후 그대로). 두 가지가 부정확하다.
        #   1) UPGRADE 상태의 원인을 DHCP 로 단정한다. DNS 해석 중일 수도 있다
        #   2) "Retry" 가 무엇인지 모호하다. 이 팝업을 닫고 장치를 다시 클릭해도
        #      상태는 갱신되지 않는다 — Search 를 다시 돌려야 한다는 안내가 빠졌다
        # 안: "Device is not ready yet - it may still be acquiring an IP address
        #      or resolving DNS. Run Search again to refresh the status, or set
        #      a static IP."
        # 사용자 노출 문구라 실기기에서 이 팝업이 실제로 뜨는 상황을 확인한 뒤 바꾼다.
        if self.curr_st == DeviceStatus.upgrade and call_from is None:
            self.show_msgbox(
                "Info",
                "DHCP has not completed. Retry after DHCP done or set a static IP",
                QMessageBox.Information,
            )
        # device profile(json format)
        if macaddr in self.dev_profile:
            dev_data = self.dev_profile[macaddr]
            self.logger.debug(f"clicked device information: {dev_data}")
            self.logger.debug(f"SD in dev_data: {'SD' in dev_data}")
            if 'SD' in dev_data:
                self.logger.debug(f"SD value: '{dev_data['SD']}'")
            else:
                self.logger.debug("SD not found in dev_data")
            if "ST" in dev_data and dev_data["ST"] in DeviceStatusMinimum:
                self.logger.debug("get_clicked_devinfo::channel_tab set tab disabled")
                self.channel_tab.setEnabled(False)

            else:
                self.logger.debug("get_clicked_devinfo::channel_tab set tab enabled")
                self.channel_tab.setEnabled(True)

            try:
                self.fill_devinfo(dev_data)
            except Exception as e:
                self.logger.error(f"get_clicked_devinfo:fill_devinfo:{e}")
        else:
            if len(self.dev_profile) != self.searched_devnum:
                self.logger.info(
                    "[Warning] 검색된 장치의 수와 프로파일된 장치의 수가 다릅니다."
                )
            # B-2: 온디맨드 Phase 3 조회
            if self.timing_config.get('experimental', 'phase3_on_demand', default=False):
                self._query_single_device(macaddr)
            else:
                self.logger.info("[Warning] retry search")

    def _query_single_device(self, macaddr):
        """B-2: 단일 장비 온디맨드 Phase 3 조회"""
        dev_info = next((d for d in self.searched_dev if d[0] == macaddr), None)
        if dev_info is None:
            self.logger.warning(f"[B-2] _query_single_device: {macaddr} not in searched_dev")
            return
        self.statusbar.showMessage(f" Querying {macaddr}...")
        QApplication.processEvents()
        try:
            code = self.code if hasattr(self, 'code') and self.code else " "
            cmd_list = self.wizmakecmd.search(dev_info[0], code, dev_info[1], dev_info[2], dev_info[3])
            dev_sock = WIZUDPSock(0, 50001, self.selected_eth or "", localport=0)
            dev_sock.open()
            th = WIZMSGHandler(dev_sock, cmd_list, "udp", Opcode.OP_SEARCHALL, self.search_wait_time_each)
            th.searched_data.connect(self.getsearch_each_dev)
            th.start()
            th.wait()
            dev_sock.close()
            if macaddr in self.dev_profile:
                self.fill_devinfo(self.dev_profile[macaddr])
            else:
                self.statusbar.showMessage(f" No response from {macaddr}")
        except Exception as e:
            self.logger.error(f"[B-2] _query_single_device error: {e}")
            self.statusbar.showMessage(f" Error querying {macaddr}: {e}")

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
    # ──────────────────────────────────────────────────────────────
    # WIZ550 UI fill (reusing existing generalTab widgets)
    # ──────────────────────────────────────────────────────────────

    def _load_wiz550_baud_items(self, device_name: str) -> list:
        """WIZ550 YAML spec 의 baud_rate choices 키(실제 bps 정수값)를 str 목록으로 반환.

        YAML choices 의 키가 실제 bps 정수값이므로 str(key) 형태로 반환한다.
        ch0_baud 는 findText(str(baud)) 방식으로 조회하므로 "115200" 형태와 호환된다.
        YAML 수정 시 자동 반영되며, _apply_serial_from_spec() 이 일반 장치 선택 시
        ch0_baud 를 재구성하므로 WIZ550 → 일반 장치 전환 시 별도 복원 불필요.
        """
        try:
            import yaml as _yaml
            from device_spec_loader import DEVICES_DIR
            path = DEVICES_DIR / f"{device_name}.yaml"
            if path.exists():
                with open(path, encoding='utf-8') as f:
                    data = _yaml.safe_load(f)
                for section in (data.get('ui') or {}).get('sections', []):
                    if section.get('id') == 'serial':
                        for fld in section.get('fields', []):
                            if fld.get('id') == 'baud_rate':
                                choices = fld.get('choices') or {}
                                return [str(k) for k in sorted(int(k) for k in choices.keys())]
        except Exception as e:
            self.logger.warning(f"[WIZ550] baud_items 로드 실패 ({device_name}): {e}")
        # fallback: WIZ550S2E 기본값 (300 포함)
        return ['300', '600', '1200', '2400', '4800', '9600',
                '19200', '38400', '57600', '115200', '230400', '460800']

    def fill_devinfo_wiz550(self, d: dict):
        """Fill existing generalTab widgets directly from parse_sr/s2e/web result dict."""
        # Device info
        self.dev_type.setText(d.get('module_name', d.get('device_type', '')))
        self.fw_version.setText(d.get('fw_str', ''))

        # Network
        dhcp = bool(d.get('dhcp_use', 0))
        self.ip_dhcp.setChecked(dhcp)
        self.ip_static.setChecked(not dhcp)
        self.event_ip_alloc()   # DHCP면 IP/subnet/gateway 비활성화
        self.localip.setText(d.get('local_ip', ''))
        self.localip_addr = d.get('local_ip', '')
        self.subnet.setText(d.get('subnet', ''))
        self.gateway.setText(d.get('gateway', ''))
        self.dns_addr.setText(d.get('dns_server_ip', ''))

        # Working mode (Java 원본: 0=Client, 1=Server, 2=TCP Mixed, 3=UDP, 4=MQTT)
        for rb in (self.ch0_tcpclient, self.ch0_tcpserver, self.ch0_tcpmixed, self.ch0_udp):
            rb.setEnabled(True)
        # MQTT 지원: WIZ550S2E + fw_ver[1] 홀수 (v1.1.x/v1.3.x) 조건.
        # fw_ver[1] 짝수(v1.2.x/v1.4.x)는 Modbus 빌드 → MQTT 미지원.
        # Java 원본 판별 로직과 동일: (fw_ver[1] % 2) != 0 → MQTT.
        _fw_ver = d.get('fw_ver', b'\x00\x00\x00')
        _is_mqtt_fw = (
            d.get('device_type') == 'WIZ550S2E'
            and len(_fw_ver) >= 2
            and (_fw_ver[1] % 2 != 0)
        )
        self.ch0_mqttclient.setEnabled(_is_mqtt_fw)
        if d.get('device_type') == 'WIZ550S2E' and not _is_mqtt_fw:
            self.ch0_mqttclient.setToolTip(
                f"MQTT는 FW 홀수 minor 버전(v1.1/v1.3.x)만 지원합니다. "
                f"현재: {d.get('fw_str', '?')} (Modbus 빌드)"
            )
        else:
            self.ch0_mqttclient.setToolTip("")
        wmode = d.get('working_mode', 0)
        if wmode == 0:
            self.ch0_tcpclient.setChecked(True)
        elif wmode == 1:
            self.ch0_tcpserver.setChecked(True)
        elif wmode == 2:
            self.ch0_tcpmixed.setChecked(True)
        elif wmode == 3:
            self.ch0_udp.setChecked(True)
        elif wmode == 4:
            self.ch0_mqttclient.setChecked(True)
        self.event_opmode()

        # Ports
        self.ch0_localport.setText(str(d.get('local_port', 0)))
        self.ch0_remoteip.setText(d.get('remote_ip', ''))
        self.ch0_remoteport.setText(str(d.get('remote_port', 0)))

        # Serial — baud_rate: YAML spec 기반으로 ch0_baud 재구성 (device_type 별 지원 범위 적용)
        # WIZ550SR: 600~460800 (300 제외), WIZ550S2E/WEB: 300~460800 (YAML choices 그대로)
        # 일반 장치로 전환 시 _apply_serial_from_spec() 이 ch0_baud 를 재구성하므로 복원 불필요.
        baud = d.get('baud_rate', 115200)
        _baud_items = self._load_wiz550_baud_items(d.get('device_type', 'WIZ550SR'))
        self.ch0_baud.blockSignals(True)
        self.ch0_baud.clear()
        for _item in _baud_items:
            self.ch0_baud.addItem(_item)
        self.ch0_baud.blockSignals(False)
        # baud 값이 지원 목록에 없으면 가장 가까운 값으로 클램핑 (legacy 장치 방어)
        if self.ch0_baud.findText(str(baud)) < 0:
            baud = min((int(x) for x in _baud_items), key=lambda x: abs(x - baud), default=115200)
        idx = self.ch0_baud.findText(str(baud))
        if idx >= 0:
            self.ch0_baud.setCurrentIndex(idx)
        # WIZ550 data_bits: 실제값 그대로 저장 (7=7bit, 8=8bit) — 인덱스 아님
        _db_text = {7: '7', 8: '8'}.get(d.get('data_bits', 8), '8')
        _db_idx = self.ch0_databit.findText(_db_text)
        if _db_idx >= 0:
            self.ch0_databit.setCurrentIndex(_db_idx)
        # data_bits 잠금: WIZ550SR=8 고정(FW DATA7BIT_ENABLE=0), S2E=7/8 활성.
        # YAML widget_override(ch0_databit)가 단일 기준. 근거: doc/dev/WIZ550-serial-fw-reference-ko.md (BUG-W550-5)
        try:
            _w550_spec = load_device(d.get('device_type', 'WIZ550SR'), self.curr_ver)
            self._apply_widget_override(self.ch0_databit, _w550_spec, 'ch0_databit')
            # 공통 게이팅: WIZ550 미지원 기능(mqtt/modbus/uart_interface/pppoe) 위젯 숨김 (YAML override 기준)
            self._apply_common_gating(_w550_spec)
        except Exception as e:
            self.logger.warning(f"[WIZ550] widget override 적용 실패: {e}")
        self.ch0_parity.setCurrentIndex(d.get('parity', 0))
        # WIZ550 stop_bits: 실제값 저장 (1=1bit, 2=2bits) → UI 콤보 인덱스로 변환
        self.ch0_stopbit.setCurrentIndex(max(0, d.get('stop_bits', 1) - 1))
        # BUG NOTE (flow_control): WIZ550SR FW v1.2.2 — uartHandler.c serial_info_init() 의
        # Flow Control switch 가 serial->flow_control 대신 serial->parity 를 잘못 참조.
        # flow_control 필드는 구조체에 저장·전송되지만 UART HW 에 적용되지 않음.
        # config tool 은 값 그대로 전송 (변경하지 않음). 상세: WIZ550SR.yaml flow_control 주석 참조.
        # BUG-W550-AC: ch0_flow .ui 정적 항목(NONE/XON-XOFF/RTS-CTS/...)은 WIZ550 enum
        # ({0:None,1:RTS/CTS})과 인덱스 의미가 달라, flow값을 그대로 인덱스로 쓰면 표시·저장이
        # 어긋난다(S2E 실버그). WIZ550 진입 시 콤보를 enum 항목으로 재구성한다.
        self.ch0_flow.clear()
        self.ch0_flow.addItems(["None", "RTS/CTS"])
        self.ch0_flow.setCurrentIndex(d.get('flow_control', 0))

        # Packing / Timer
        self.ch0_pack_time.setText(str(d.get('packing_time', 0)))
        self.ch0_pack_size.setText(str(d.get('packing_size', 0)))
        self.ch0_inact_timer.setText(str(d.get('inactivity', 0)))
        self.ch0_reconnection.setText(str(d.get('reconnection', 0)))

        # Passwords / AT mode
        self.searchcode.setText(d.get('pw_setting', ''))
        pw_c = d.get('pw_connect', '')
        self.enable_connect_pw.setChecked(bool(pw_c))
        self.connect_pw.setText(pw_c)
        self.at_enable.setChecked(bool(d.get('serial_command', 0)))

        # MQTT 필드: s2e_variant=='mqtt' 응답에서만 값 있음. 아니면 빈값(anti-stale).
        self.lineedit_mqtt_username.setText(d.get('mqtt_user', ''))
        self.lineedit_mqtt_password.setText(d.get('mqtt_pw', ''))
        self.lineedit_mqtt_pubtopic.setText(d.get('mqtt_pub_topic', ''))
        self.lineedit_mqtt_subtopic_0.setText(d.get('mqtt_sub_topic', ''))

        # mqtt 탭: fw_ver 홀짝 확인 후 추가/제거 (Modbus FW면 탭 불필요)
        _mqtt_tab_obj = self.tab_structure.get("mqtt_tab")
        if _mqtt_tab_obj is not None:
            _tab_names = [self.generalTab.widget(i).objectName()
                          for i in range(self.generalTab.count())]
            _mqtt_name = _mqtt_tab_obj.object.objectName()
            if _is_mqtt_fw:
                if _mqtt_name not in _tab_names:
                    self.generalTab.insertTab(
                        self.generalTab.count(), _mqtt_tab_obj.object, _mqtt_tab_obj.ui_text
                    )
            else:
                for i in range(self.generalTab.count()):
                    if self.generalTab.widget(i).objectName() == _mqtt_name:
                        self.generalTab.removeTab(i)
                        break

    def _on_wiz550_get_done(self, cfg: dict, macaddr: str, device_type: str):
        """WIZ550Getter completion callback — merge GET_INFO response into dev_profile and fill UI."""
        if not cfg:
            self.statusbar.showMessage(f" Failed to read WIZ550 settings: {macaddr}")
            self.logger.warning(f"[WIZ550] GET_INFO 응답 없음: {macaddr}")
            return

        # dev_profile에 병합 (Discovery 정보 보존)
        self.dev_profile.setdefault(macaddr, {}).update(cfg)
        self.logger.info(f"[WIZ550] GET {macaddr} ({device_type}): {cfg}")

        # B-02 Stage 2: GET_INFO 완료 후에 위젯에 값 채우기
        self.fill_devinfo_wiz550(cfg)
        self.statusbar.showMessage(f" WIZ550 settings loaded: {macaddr}")

    # ──────────────────────────────────────────────────────────────
    # WIZ550 Apply / Reset / FactoryReset (UI-03, UI-04, Wave 3)
    # ──────────────────────────────────────────────────────────────

    def fill_setinfo_wiz550(self) -> dict:
        """Read WIZ550 settings from existing generalTab widgets and return as dict."""
        # based on dev_profile copy — preserves readonly fields such as mac/module_type/fw_ver
        d = self.dev_profile.get(self.curr_mac, {}).copy()

        # Network
        d['dhcp_use'] = 1 if self.ip_dhcp.isChecked() else 0
        d['local_ip'] = self.localip.text().strip()
        d['subnet'] = self.subnet.text().strip()
        d['gateway'] = self.gateway.text().strip()
        d['dns_server_ip'] = self.dns_addr.text().strip()

        # Working mode (Java 원본: 0=Client, 1=Server, 2=TCP Mixed, 3=UDP, 4=MQTT)
        if self.ch0_tcpclient.isChecked():
            d['working_mode'] = 0
        elif self.ch0_tcpserver.isChecked():
            d['working_mode'] = 1
        elif self.ch0_tcpmixed.isChecked():
            d['working_mode'] = 2
        elif self.ch0_udp.isChecked():
            d['working_mode'] = 3
        elif self.ch0_mqttclient.isChecked():
            d['working_mode'] = 4

        # Ports
        try:
            d['local_port'] = int(self.ch0_localport.text())
        except ValueError:
            d['local_port'] = 0
        d['remote_ip'] = self.ch0_remoteip.text().strip()
        try:
            d['remote_port'] = int(self.ch0_remoteport.text())
        except ValueError:
            d['remote_port'] = 0

        # Serial — ch0_baud text ("115200") → int
        try:
            d['baud_rate'] = int(self.ch0_baud.currentText())
        except ValueError:
            pass
        # WIZ550 data_bits: 실제값 그대로 저장 (7 또는 8) — 인덱스 아님
        _db_str = self.ch0_databit.currentText()
        d['data_bits'] = int(_db_str) if _db_str.isdigit() else 8
        d['parity'] = self.ch0_parity.currentIndex()
        # WIZ550 stop_bits: UI 콤보 인덱스 → 실제값 (index 0→1, index 1→2)
        d['stop_bits'] = self.ch0_stopbit.currentIndex() + 1
        d['flow_control'] = self.ch0_flow.currentIndex()

        # Packing / Timer
        try:
            d['packing_time'] = int(self.ch0_pack_time.text())
        except ValueError:
            d['packing_time'] = 0
        try:
            d['packing_size'] = int(self.ch0_pack_size.text())
        except ValueError:
            d['packing_size'] = 0
        try:
            d['inactivity'] = int(self.ch0_inact_timer.text())
        except ValueError:
            d['inactivity'] = 0
        try:
            d['reconnection'] = int(self.ch0_reconnection.text())
        except ValueError:
            d['reconnection'] = 0

        # Passwords / AT mode
        d['pw_setting'] = self.searchcode.text()
        d['pw_connect'] = self.connect_pw.text() if self.enable_connect_pw.isChecked() else ''
        d['serial_command'] = 1 if self.at_enable.isChecked() else 0

        # MQTT (BUG-W550-6): working_mode=4(mqtt)면 variant 지정해야 build 가 MQTT_FORMAT 사용.
        # 미지정 시 WIZ550Profile build 가 base(162B)로 처리 → mqtt 필드 전송 누락.
        if d.get('working_mode') == 4:
            d['s2e_variant'] = 'mqtt'
            d['mqtt_user']      = self.lineedit_mqtt_username.text()
            d['mqtt_pw']        = self.lineedit_mqtt_password.text()
            d['mqtt_pub_topic'] = self.lineedit_mqtt_pubtopic.text()
            d['mqtt_sub_topic'] = self.lineedit_mqtt_subtopic_0.text()

        return d

    def apply_wiz550(self):
        """
        WIZ550 설정 Apply — 비밀번호 입력 → Profile 빌드 → WIZ550Setter 시작 (UI-03).
        D-05: Apply 버튼 #cc785c (신규 WIZ550 UI에만 적용, 기존 UI 불변).
        """
        if not hasattr(self, 'curr_mac') or not self.curr_mac:
            return
        d_profile = self.dev_profile.get(self.curr_mac, {})
        device_type = d_profile.get('device_type', 'WIZ550SR')

        # 비밀번호 입력 다이얼로그
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        pw, ok = QInputDialog.getText(
            self,
            "WIZ550 Settings Password",
            "Settings password (leave blank if none):",
            QLineEdit.Password,
            d_profile.get('pw_setting', ''),
        )
        if not ok:
            return  # 취소

        # collect values from widgets (based on dev_profile copy — readonly fields preserved automatically)
        d = self.fill_setinfo_wiz550()
        d['pw_setting'] = pw  # dialog input takes precedence
        self.logger.info(
            f"[WIZ550] SET build: wmode={d.get('working_mode')} "
            f"flow={d.get('flow_control')} variant={d.get('s2e_variant', 'base')} "
            f"mqtt_user={d.get('mqtt_user', '')!r}"
        )

        # Profile bytes 빌드
        try:
            from WIZ550Profile import build_sr, build_s2e, build_web
            builders = {
                'WIZ550SR':  build_sr,
                'WIZ550S2E': build_s2e,
                'WIZ550WEB': build_web,
            }
            builder = builders.get(device_type, build_sr)
            config_bytes = builder(d)
        except Exception as e:
            self.logger.error(f"[WIZ550] Profile 빌드 오류: {e}")
            self.statusbar.showMessage(f" WIZ550 Apply Error: {e}")
            return

        # 현재 장비 IP (검색 시 수집된 값) — 폼의 새 IP가 아니라 장비가 실제 있는 IP로 전송
        target_ip = d_profile.get('local_ip', '') or d.get('local_ip', '')
        if not target_ip:
            self.statusbar.showMessage(" WIZ550 Apply Error: No IP address")
            return

        self._wiz550_setter = WIZ550Setter(
            target_ip=target_ip,
            target_mac=self.curr_mac,
            password=pw,
            config_data=config_bytes,
            iface_ip=self.selected_eth or "",
        )
        self._wiz550_setter.set_done.connect(self._on_wiz550_set_done)
        self._wiz550_setter.start()
        self.statusbar.showMessage(f" Sending WIZ550 settings... ({self.curr_mac})")

    def _on_wiz550_set_done(self, success: bool):
        """WIZ550Setter 완료 콜백 — 성공/실패 메시지 표시 (D-05 컬러)."""
        self.logger.info(f"[WIZ550] SET done: success={success}")
        from PyQt5.QtWidgets import QMessageBox
        if success:
            # D-05: 성공 색상 #5db872
            self.statusbar.showMessage(" WIZ550 settings saved")
            self.statusbar.setStyleSheet("QStatusBar { color: #5db872; }")
            QMessageBox.information(
                self, "WIZ550 Apply", "Settings were saved successfully."
            )
        else:
            # D-05: 오류 색상 #c64545
            self.statusbar.showMessage(" Failed to save WIZ550 settings (no response or wrong password)")
            self.statusbar.setStyleSheet("QStatusBar { color: #c64545; }")
            QMessageBox.warning(
                self, "WIZ550 Apply Failed",
                "Failed to save settings.\nPlease check the password or device connection."
            )
        # statusbar 색상을 3초 후 원상복구
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.statusbar.setStyleSheet(""))

    def reset_wiz550(self, op_code: int = None):
        """
        WIZ550 Reset 전송 — REMOTE_RESET(0xE0) 또는 FACTORY_RESET(0xF0) (UI-04).
        op_code 기본값: OP_REMOTE_RESET
        """
        if op_code is None:
            op_code = OP_REMOTE_RESET

        if not hasattr(self, 'curr_mac') or not self.curr_mac:
            return

        d_profile = self.dev_profile.get(self.curr_mac, {})
        target_ip = d_profile.get('local_ip', '')
        if not target_ip:
            self.statusbar.showMessage(" WIZ550 Reset Error: No IP address")
            return

        # 비밀번호 입력
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        op_name = "Factory Reset" if op_code == OP_FACTORY_RESET else "Reset"
        pw, ok = QInputDialog.getText(
            self,
            f"WIZ550 {op_name}",
            f"{op_name} password (leave blank if none):",
            QLineEdit.Password,
            d_profile.get('pw_setting', ''),
        )
        if not ok:
            return

        self._wiz550_resetter = WIZ550Resetter(
            target_ip=target_ip,
            target_mac=self.curr_mac,
            password=pw,
            op_code=op_code,
            iface_ip=self.selected_eth or "",
        )
        self._wiz550_resetter.reset_done.connect(
            lambda success, name=op_name: self._on_wiz550_reset_done(success, name)
        )
        self._wiz550_resetter.start()
        self.statusbar.showMessage(f" Sending WIZ550 {op_name}... ({self.curr_mac})")

    def _on_wiz550_reset_done(self, success: bool, op_name: str = "Reset"):
        """WIZ550Resetter 완료 콜백 — 결과 표시 (UI-04)."""
        from PyQt5.QtWidgets import QMessageBox
        if success:
            self.statusbar.showMessage(f" WIZ550 {op_name} complete")
            QMessageBox.information(
                self, f"WIZ550 {op_name}", f"{op_name} completed."
            )
        else:
            self.statusbar.showMessage(f" WIZ550 {op_name} failed")
            QMessageBox.warning(
                self, f"WIZ550 {op_name} Failed",
                f"{op_name} failed.\nPlease check the device connection."
            )

    # ──────────────────────────────────────────────────────────────
    # WIZ1x0SR 전용 UI (바이너리 프로토콜, 완전 분리)
    # ──────────────────────────────────────────────────────────────

    def _show_wiz1x0_panel(self, show: bool):
        """WIZ1x0SR 전용 패널 ↔ 기존 generalTab 전환."""
        self.wiz1x0_tab.setVisible(show)
        self.generalTab.setVisible(not show)
        self.channel_tab.setVisible(not show)
        self.btn_setting.setEnabled(show)

    def _wiz1x0_ip_alloc_changed(self):
        """WIZ1x0SR: IP 할당 방식에 따라 IP 필드 활성/비활성."""
        is_manual = self.wiz1x0_ip_static.isChecked()
        for w in (self.wiz1x0_localip, self.wiz1x0_subnet, self.wiz1x0_gw, self.wiz1x0_dns_ip):
            w.setEnabled(is_manual)
        is_pppoe = self.wiz1x0_ip_pppoe.isChecked()
        self.wiz1x0_pppoe_id.setEnabled(is_pppoe)
        self.wiz1x0_pppoe_pw.setEnabled(is_pppoe)

    def _wiz1x0_dns_enable_changed(self, state):
        """WIZ1x0SR: DNS 사용 여부에 따라 DNS IP / Domain 필드 활성/비활성."""
        enabled = bool(state)
        self.wiz1x0_dns_ip.setEnabled(enabled and self.wiz1x0_ip_static.isChecked())
        self.wiz1x0_domain.setEnabled(enabled)

    def _wiz1x0_scfg_enable_changed(self, state):
        """WIZ1x0SR: Serial Config Trigger 활성/비활성."""
        enabled = bool(state)
        for w in (self.wiz1x0_scfg1, self.wiz1x0_scfg2, self.wiz1x0_scfg3):
            w.setEnabled(enabled)

    def _wiz1x0_tcppass_enable_changed(self, state):
        """WIZ1x0SR: TCP Password 활성/비활성."""
        self.wiz1x0_tcppass.setEnabled(bool(state))

    def _set_widget_width_from_sample(self, widget, sample_text: str, extra_px: int = 24):
        """샘플 문자열 기준으로 위젯 폭을 계산해 고정."""
        width = max(widget.minimumSizeHint().width(), widget.fontMetrics().horizontalAdvance(sample_text) + extra_px)
        widget.setMaximumWidth(width)
        return width

    def _remove_layout_spacers(self, layout):
        """WIZ1x0SR compact 배치를 위해 불필요한 spacer를 제거."""
        for index in reversed(range(layout.count())):
            item = layout.itemAt(index)
            if item.spacerItem() is not None:
                layout.takeAt(index)

    def _apply_wiz1x0_compact_layout(self):
        """WIZ1x0SR UI를 내용 길이 기준의 compact layout으로 정리."""
        compact_groups = (
            self.grp_wiz1x0_ipmode,
            self.grp_wiz1x0_opmode,
            self.grp_wiz1x0_serial_params,
            self.grp_wiz1x0_packing,
            self.grp_wiz1x0_tcppass,
            self.grp_wiz1x0_scfg,
        )
        for widget in compact_groups:
            widget.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)

        for layout in (
            self.hbox_wiz1x0_ipmode,
            self.hbox_wiz1x0_opmode,
            self.hbox_wiz1x0_tcppass,
            self.hbox_wiz1x0_scfg,
        ):
            self._remove_layout_spacers(layout)
            layout.setSpacing(8)

        self.vbox_wiz1x0_net.setAlignment(self.grp_wiz1x0_ipmode, Qt.AlignLeft)
        self.vbox_wiz1x0_net.setAlignment(self.gridLayout_wiz1x0_ipfields, Qt.AlignLeft)
        self.vbox_wiz1x0_outer.setAlignment(self.wiz1x0_meta, Qt.AlignLeft)
        self.vbox_wiz1x0_mid.setAlignment(self.grp_wiz1x0_opmode, Qt.AlignLeft)
        self.vbox_wiz1x0_mid.setAlignment(self.gridLayout_wiz1x0_dns, Qt.AlignLeft)
        self.vbox_wiz1x0_mid.setAlignment(self.grp_wiz1x0_serial_params, Qt.AlignLeft)
        self.vbox_wiz1x0_opt.setAlignment(self.gridLayout_wiz1x0_misc, Qt.AlignLeft)
        self.vbox_wiz1x0_opt.setAlignment(self.grp_wiz1x0_packing, Qt.AlignLeft)
        self.vbox_wiz1x0_opt.setAlignment(self.grp_wiz1x0_tcppass, Qt.AlignLeft)
        self.vbox_wiz1x0_opt.setAlignment(self.grp_wiz1x0_scfg, Qt.AlignLeft)

        for layout in (self.gridLayout_wiz1x0_ipfields, self.gridLayout_wiz1x0_dns, self.gridLayout_wiz1x0_misc, self.gridLayout_wiz1x0_pack):
            layout.setHorizontalSpacing(8)
            layout.setVerticalSpacing(4)
            layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        for widget in (
            self.wiz1x0_localip,
            self.wiz1x0_myport,
            self.wiz1x0_subnet,
            self.wiz1x0_gw,
            self.wiz1x0_pppoe_id,
            self.wiz1x0_pppoe_pw,
            self.wiz1x0_peerip,
            self.wiz1x0_peerport,
        ):
            self.gridLayout_wiz1x0_ipfields.setAlignment(widget, Qt.AlignLeft)

        for widget in (
            self.wiz1x0_dns_enable,
            self.lbl_wiz1x0_dns_ip,
            self.wiz1x0_dns_ip,
            self.lbl_wiz1x0_domain,
            self.wiz1x0_domain,
        ):
            self.gridLayout_wiz1x0_dns.setAlignment(widget, Qt.AlignLeft)

        for widget in (
            self.wiz1x0_inactivity,
            self.wiz1x0_pack_time,
            self.wiz1x0_pack_size,
            self.wiz1x0_pack_char,
        ):
            if widget in (self.wiz1x0_inactivity,):
                self.gridLayout_wiz1x0_misc.setAlignment(widget, Qt.AlignLeft)
            else:
                self.gridLayout_wiz1x0_pack.setAlignment(widget, Qt.AlignLeft)

    def _apply_wiz1x0_field_widths(self):
        """WIZ1x0SR 필드 폭을 최대 예상 값 기준으로 조정."""
        line_edit_samples = {
            self.wiz1x0_localip: "999.999.999.999",
            self.wiz1x0_subnet: "999.999.999.999",
            self.wiz1x0_gw: "999.999.999.999",
            self.wiz1x0_dns_ip: "999.999.999.999",
            self.wiz1x0_peerip: "999.999.999.999",
            self.wiz1x0_domain: "X" * 40,
            self.wiz1x0_pppoe_id: "X" * 40,
            self.wiz1x0_pppoe_pw: "X" * 40,
            self.wiz1x0_myport: "65535",
            self.wiz1x0_peerport: "65535",
            self.wiz1x0_version: "V9.9.9",
            self.wiz1x0_inactivity: "65535",
            self.wiz1x0_pack_time: "65535",
            self.wiz1x0_pack_size: "255",
            self.wiz1x0_pack_char: "FF",
            self.wiz1x0_tcppass: "12345678",
            self.wiz1x0_scfg1: "FF",
            self.wiz1x0_scfg2: "FF",
            self.wiz1x0_scfg3: "FF",
        }
        for widget, sample in line_edit_samples.items():
            width = self._set_widget_width_from_sample(widget, sample)
            if widget in (self.wiz1x0_domain, self.wiz1x0_pppoe_id, self.wiz1x0_pppoe_pw):
                widget.setMinimumWidth(width)

        combo_samples = {
            self.wiz1x0_baud: "230400",
            self.wiz1x0_databit: "8-bit",
            self.wiz1x0_parity: "None",
            self.wiz1x0_stopbit: "1-bit",
            self.wiz1x0_flow: "Xon/Xoff",
        }
        for widget, sample in combo_samples.items():
            self._set_widget_width_from_sample(widget, sample, extra_px=40)

        self.gridLayout_wiz1x0_ipfields.setColumnStretch(1, 0)
        self.gridLayout_wiz1x0_ipfields.setColumnStretch(2, 0)
        self.gridLayout_wiz1x0_ipfields.setColumnStretch(3, 0)
        self.gridLayout_wiz1x0_dns.setColumnStretch(1, 0)
        self.gridLayout_wiz1x0_dns.setColumnStretch(2, 0)
        self.gridLayout_wiz1x0_misc.setColumnStretch(1, 0)
        self.gridLayout_wiz1x0_misc.setColumnStretch(2, 0)
        self.gridLayout_wiz1x0_pack.setColumnStretch(1, 0)
        self.gridLayout_wiz1x0_pack.setColumnStretch(2, 0)

    def _connect_wiz1x0_signals(self):
        """WIZ1x0SR 전용 위젯 시그널 연결 (초기화 시 한 번만 호출)."""
        for rb in (self.wiz1x0_ip_static, self.wiz1x0_ip_dhcp, self.wiz1x0_ip_pppoe):
            rb.clicked.connect(self._wiz1x0_ip_alloc_changed)
        self.wiz1x0_dns_enable.stateChanged.connect(self._wiz1x0_dns_enable_changed)
        self.wiz1x0_scfg_enable.stateChanged.connect(self._wiz1x0_scfg_enable_changed)
        self.wiz1x0_en_tcppass.stateChanged.connect(self._wiz1x0_tcppass_enable_changed)
        self.btn_wiz1x0_toggle.toggled.connect(self._toggle_wiz1x0_view)

    def _toggle_wiz1x0_view(self, full_mode: bool):
        """WIZ1x0SR: Full 세로 모드(checked=True) ↔ 탭 모드 전환."""
        self.btn_wiz1x0_toggle.setText("⊟ Tabs" if full_mode else "☰ Full")
        if full_mode:
            # Tab → Full: 탭에서 꺼내 세로 스크롤 영역에 배치
            while self.wiz1x0_tabwidget.count():
                self.wiz1x0_tabwidget.removeTab(0)
            for w in (self.wiz1x0_col_net, self.wiz1x0_col_mid, self.wiz1x0_col_opt):
                self.vbox_wiz1x0_full.addWidget(w)
                w.setVisible(True)
            self.wiz1x0_tabwidget.setVisible(False)
            self.wiz1x0_fullscroll.setVisible(True)
        else:
            # Full → Tab: col 위젯들을 QTabWidget 탭으로 이동
            for w in (self.wiz1x0_col_net, self.wiz1x0_col_mid, self.wiz1x0_col_opt):
                self.vbox_wiz1x0_full.removeWidget(w)
            self.wiz1x0_tabwidget.addTab(self.wiz1x0_col_net, "Network")
            self.wiz1x0_tabwidget.addTab(self.wiz1x0_col_mid, "Mode && Serial")
            self.wiz1x0_tabwidget.addTab(self.wiz1x0_col_opt, "Options")
            self.wiz1x0_fullscroll.setVisible(False)
            self.wiz1x0_tabwidget.setVisible(True)

    def fill_devinfo_1x0(self, d: dict):
        """WIZ1x0SR board_dict → wiz1x0_tab 전용 위젯 채우기."""
        # ── Network 탭 ──────────────────────────────────────────────
        ip_alloc = d.get('ip_alloc', 'Static')
        self.wiz1x0_ip_static.setChecked(ip_alloc == 'Static')
        self.wiz1x0_ip_dhcp.setChecked(ip_alloc == 'DHCP')
        self.wiz1x0_ip_pppoe.setChecked(ip_alloc == 'PPPoE')

        self.wiz1x0_localip.setText(d.get('ip', ''))
        self.wiz1x0_subnet.setText(d.get('subnet', ''))
        self.wiz1x0_gw.setText(d.get('gw', ''))
        self.wiz1x0_myport.setText(str(d.get('myport', 0)))
        self.wiz1x0_peerip.setText(d.get('peerip', ''))
        self.wiz1x0_peerport.setText(str(d.get('peerport', 0)))
        self.wiz1x0_pppoe_id.setText(d.get('pppoe_id', ''))
        self.wiz1x0_pppoe_pw.setText(d.get('pppoe_pass', ''))

        # 동작 모드 (WIZ1x0: bserver 0=Client, 1=Mixed, 2=Server)
        udp_on = bool(d.get('udp', 0))
        self.wiz1x0_udp.setChecked(udp_on)
        op = d.get('bserver', 0)
        self.wiz1x0_op_client.setChecked(op == 0)
        self.wiz1x0_op_mixed.setChecked(op == 1)   # 1=Mixed (WIZ107/108과 역전!)
        self.wiz1x0_op_server.setChecked(op == 2)  # 2=Server (WIZ107/108과 역전!)

        # DNS
        dns_on = bool(d.get('dns_flag', 0))
        self.wiz1x0_dns_enable.setChecked(dns_on)
        self.wiz1x0_dns_ip.setText(d.get('dns_ip', ''))
        self.wiz1x0_domain.setText(d.get('domain', ''))

        # 필드 활성/비활성 초기 적용
        self._wiz1x0_ip_alloc_changed()
        self._wiz1x0_dns_enable_changed(dns_on)

        # ── Serial 탭 ───────────────────────────────────────────────
        from WIZ1x0Profile import SPEED_BPS_LIST
        speed_bps = d.get('speed_bps', 9600)
        idx = SPEED_BPS_LIST.index(speed_bps) if speed_bps in SPEED_BPS_LIST else 3
        self.wiz1x0_baud.setCurrentIndex(idx)

        databit = d.get('databit', 8)
        self.wiz1x0_databit.setCurrentIndex(0 if databit == 7 else 1)

        parity_map = {'None': 0, 'Odd': 1, 'Even': 2}
        self.wiz1x0_parity.setCurrentIndex(parity_map.get(d.get('parity_str', 'None'), 0))

        flow_map = {'None': 0, 'Xon/Xoff': 1, 'CTS/RTS': 2}
        self.wiz1x0_flow.setCurrentIndex(flow_map.get(d.get('flow_str', 'None'), 0))

        # ── Option 탭 ───────────────────────────────────────────────
        self.wiz1x0_version.setText(d.get('appver_str', ''))
        self.wiz1x0_debug.setChecked(d.get('debug_on', False))

        self.wiz1x0_inactivity.setText(str(d.get('I_time', 0)))
        self.wiz1x0_pack_time.setText(str(d.get('D_time', 0)))
        self.wiz1x0_pack_size.setText(str(d.get('D_size', 0)))
        self.wiz1x0_pack_char.setText(f"{d.get('D_ch', 0):02X}")

        en_tcppass = bool(d.get('en_tcppass', 0))
        self.wiz1x0_en_tcppass.setChecked(en_tcppass)
        self.wiz1x0_tcppass.setText(d.get('tcppass', ''))
        self._wiz1x0_tcppass_enable_changed(en_tcppass)

        # Serial Trigger (펌웨어 v1.2 이상만 활성)
        appver = d.get('appver', b'\x00\x00')
        fw_major = appver[0] if len(appver) >= 1 else 0
        fw_minor = appver[1] if len(appver) >= 2 else 0
        scfg_supported = (fw_major > 1) or (fw_major == 1 and fw_minor >= 2)
        scfg_on = bool(d.get('scfg', 0)) and scfg_supported
        self.wiz1x0_scfg_enable.setChecked(scfg_on)
        self.wiz1x0_scfg_enable.setEnabled(scfg_supported)
        scfg_hex = d.get('scfg_str', '000000').zfill(6)
        self.wiz1x0_scfg1.setText(scfg_hex[0:2])
        self.wiz1x0_scfg2.setText(scfg_hex[2:4])
        self.wiz1x0_scfg3.setText(scfg_hex[4:6])
        self._wiz1x0_scfg_enable_changed(scfg_on)

        self.statusbar.showMessage(f" WIZ1x0SR [{d.get('mac', '')}]  FW {d.get('appver_str', '')}")

    def fill_setinfo_1x0(self) -> dict:
        """wiz1x0_tab 전용 위젯 → WIZ1x0SR board_dict 수집 (Apply 핸들러용)."""
        from WIZ1x0Profile import SPEED_BPS_LIST

        d = dict(self.dev_profile.get(self.curr_mac, {}))  # 기존 값 베이스

        # ── Network ─────────────────────────────────────────────────
        if self.wiz1x0_ip_static.isChecked():
            d['ip_alloc'] = 'Static'
        elif self.wiz1x0_ip_dhcp.isChecked():
            d['ip_alloc'] = 'DHCP'
        else:
            d['ip_alloc'] = 'PPPoE'

        d['ip']         = self.wiz1x0_localip.text()
        d['subnet']     = self.wiz1x0_subnet.text()
        d['gw']         = self.wiz1x0_gw.text()
        d['myport']     = int(self.wiz1x0_myport.text() or 0)
        d['peerip']     = self.wiz1x0_peerip.text()
        d['peerport']   = int(self.wiz1x0_peerport.text() or 0)
        d['pppoe_id']   = self.wiz1x0_pppoe_id.text()
        d['pppoe_pass'] = self.wiz1x0_pppoe_pw.text()

        # 동작 모드 (WIZ1x0: Client=0, Mixed=1, Server=2 — WIZ107/108과 역전!)
        d['udp'] = 1 if self.wiz1x0_udp.isChecked() else 0
        if self.wiz1x0_op_client.isChecked():
            d['op_mode'] = 'Client'
        elif self.wiz1x0_op_server.isChecked():
            d['op_mode'] = 'Server'
        elif self.wiz1x0_op_mixed.isChecked():
            d['op_mode'] = 'Mixed'

        # DNS
        d['dns_flag'] = 1 if self.wiz1x0_dns_enable.isChecked() else 0
        d['dns_ip']   = self.wiz1x0_dns_ip.text()
        d['domain']   = self.wiz1x0_domain.text()

        # ── Serial ──────────────────────────────────────────────────
        idx = self.wiz1x0_baud.currentIndex()
        d['speed_bps'] = SPEED_BPS_LIST[idx] if idx < len(SPEED_BPS_LIST) else 9600
        d['databit']   = 7 if self.wiz1x0_databit.currentIndex() == 0 else 8
        parity_list    = ['None', 'Odd', 'Even']
        d['parity_str'] = parity_list[self.wiz1x0_parity.currentIndex()]
        d['stopbit']   = 1  # 1-bit 고정
        flow_list      = ['None', 'Xon/Xoff', 'CTS/RTS']
        d['flow_str']  = flow_list[self.wiz1x0_flow.currentIndex()]

        # ── Option ──────────────────────────────────────────────────
        d['debug_on'] = self.wiz1x0_debug.isChecked()
        d['I_time']   = int(self.wiz1x0_inactivity.text() or 0)
        d['D_time']   = int(self.wiz1x0_pack_time.text() or 0)
        d['D_size']   = int(self.wiz1x0_pack_size.text() or 0)
        d['D_ch']     = int(self.wiz1x0_pack_char.text() or '0', 16)

        d['en_tcppass'] = 1 if self.wiz1x0_en_tcppass.isChecked() else 0
        d['tcppass']    = self.wiz1x0_tcppass.text()

        d['scfg']     = 1 if self.wiz1x0_scfg_enable.isChecked() else 0
        d['scfg_str'] = (
            self.wiz1x0_scfg1.text().zfill(2) +
            self.wiz1x0_scfg2.text().zfill(2) +
            self.wiz1x0_scfg3.text().zfill(2)
        )

        return d

    def apply_1x0(self):
        """WIZ1x0SR Apply 버튼 처리."""
        d = self.fill_setinfo_1x0()
        target_ip = d.get('ip', '')
        if not target_ip or target_ip == '0.0.0.0':
            self.show_msgbox("Error", "No valid IP address.", QMessageBox.Warning)
            return

        reply = QMessageBox.question(
            self, "Apply",
            f"Settings will be applied.\n{target_ip}\n\nNote: WIZ1x0SR saves and restarts immediately on Apply.",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Ok:
            return

        self._last_1x0_board_dict = d   # 프로파일 폴백용 보관
        self.setter_1x0 = WIZ1x0Setter(target_ip, d, iface_ip=self.selected_eth or "")
        self.setter_1x0.set_done.connect(self._on_1x0_set_done)
        self.setter_1x0.start()
        self.statusbar.showMessage(" Applying WIZ1x0SR settings...")

    def _on_1x0_set_done(self, success: bool, response_data: bytes):
        if success:
            mac = self.curr_mac
            # SETC 응답이 완전한 167바이트면 파싱해서 프로파일 갱신
            updated = False
            if response_data and mac in self.dev_profile:
                from WIZ1x0Profile import parse_imin, BOARD_INFO_SIZE
                if len(response_data) >= 4 + BOARD_INFO_SIZE:
                    imin_data = b'IMIN' + response_data[4:]
                    parsed = parse_imin(imin_data)
                    if parsed:
                        self.dev_profile[mac] = parsed
                        updated = True
            # SETC 응답 없거나 파싱 실패 시 → 전송한 값으로 프로파일 갱신
            if not updated and hasattr(self, '_last_1x0_board_dict') and mac in self.dev_profile:
                self.dev_profile[mac].update(self._last_1x0_board_dict)
            self.statusbar.showMessage(" WIZ1x0SR settings complete — please re-run Device Search after the device restarts")
        else:
            self.statusbar.showMessage(" WIZ1x0SR settings failed — no response (SETC timeout)")
            self.show_msgbox("Error", "WIZ1x0SR settings failed — no response", QMessageBox.Warning)

    # ──────────────────────────────────────────────────────────────

    def fill_devinfo(self, dev_data):
        if not self.curr_dev or not self.curr_ver:
            return
        self.logger.debug(f"fill_devinfo type={type(dev_data)}")
        try:
            # device info (RO)
            if "MN" in dev_data:
                self.dev_type.setText(dev_data["MN"])
            if "VR" in dev_data:
                self.fw_version.setText(dev_data["VR"])
            # device info - channel 1
            if "ST" in dev_data:
                self.ch0_status.setText(dev_data["ST"])
            if "UN" in dev_data:
                self.ch0_uart_name.setText(dev_data["UN"])
            # Network - general
            if "IM" in dev_data:
                if dev_data["IM"] == "0":
                    self.ip_static.setChecked(True)
                elif dev_data["IM"] == "1":
                    self.ip_dhcp.setChecked(True)
                elif dev_data["IM"] == "2" and (
                    "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev
                ):
                    self.ip_pppoe.setChecked(True)
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
                    self.ch0_tcpclient.setChecked(True)
                elif dev_data["OP"] == "1":
                    self.ch0_tcpserver.setChecked(True)
                elif dev_data["OP"] == "2":
                    self.ch0_tcpmixed.setChecked(True)
                elif dev_data["OP"] == "3":
                    self.ch0_udp.setChecked(True)
                elif dev_data["OP"] == "4":
                    self.ch0_ssl_tcpclient.setChecked(True)
                elif dev_data["OP"] == "5":
                    self.ch0_mqttclient.setChecked(True)
                elif dev_data["OP"] == "6":
                    self.ch0_mqtts_client.setChecked(True)
            if "LP" in dev_data:
                self.ch0_localport.setText(dev_data["LP"])
            if "RH" in dev_data:
                self.ch0_remoteip.setText(dev_data["RH"])
            if "RP" in dev_data:
                self.ch0_remoteport.setText(dev_data["RP"])
            # serial - channel 1
            if "BR" in dev_data:
                self.ch0_baud.setCurrentIndex(int(dev_data["BR"]))
            if "DB" in dev_data:
                if len(dev_data["DB"]) > 2:
                    pass
                else:
                    self.ch0_databit.setCurrentIndex(int(dev_data["DB"]))
            if "PR" in dev_data:
                self.ch0_parity.setCurrentIndex(int(dev_data["PR"]))
            if "SB" in dev_data:
                self.ch0_stopbit.setCurrentIndex(int(dev_data["SB"]))
            if "FL" in dev_data:
                # BUG-W550-AC anti-stale: WIZ550 경로가 콤보를 2항목으로 재구성했을 수 있으므로
                # 일반 장치 진입 시 .ui 원래 flow 항목으로 복원한 뒤 FL 인덱스 적용.
                if self.ch0_flow.count() != len(self._default_flow_items):
                    self.ch0_flow.clear()
                    self.ch0_flow.addItems(self._default_flow_items)
                self.ch0_flow.setCurrentIndex(int(dev_data["FL"]))
            if "PT" in dev_data:
                self.ch0_pack_time.setText(dev_data["PT"])
            if "PS" in dev_data:
                self.ch0_pack_size.setText(dev_data["PS"])
            if "PD" in dev_data:
                self.ch0_pack_char.setText(dev_data["PD"])
            # Send Data at Connection - W55RP20-S2E only (버전 1.1.8 이상)
            if "SD" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                self.logger.debug(f"Loading SD data: '{dev_data['SD']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["SD"] == " ":
                    self.ch0_serial_connection_condition_connect.clear()
                else:
                    self.ch0_serial_connection_condition_connect.setText(dev_data["SD"])
            # Send Data at Disconnection - W55RP20-S2E only (버전 1.1.8 이상)
            if "DD" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                self.logger.debug(f"Loading DD data: '{dev_data['DD']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["DD"] == " ":
                    self.ch0_serial_connection_condition_disconnect.clear()
                else:
                    self.ch0_serial_connection_condition_disconnect.setText(dev_data["DD"])
            # Ethernet Data Connection Condition - W55RP20-S2E, W232N, IP20 (버전 1.1.8 이상)
            if "SE" in dev_data and self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver, "1.1.8") >= 0:
                self.logger.debug(f"Loading SE data: '{dev_data['SE']}'")
                # 공백(" ")인 경우 빈 문자열로 표시
                if dev_data["SE"] == " ":
                    self.ch0_ethernet_connection_condition.clear()
                else:
                    self.ch0_ethernet_connection_condition.setText(dev_data["SE"])
            # Inactive timer - channel 1
            if "IT" in dev_data:
                self.ch0_inact_timer.setText(dev_data["IT"])
            # TCP keep alive - channel 1
            if "KA" in dev_data:
                if dev_data["KA"] == "0":
                    self.ch0_keepalive_enable.setChecked(False)
                elif dev_data["KA"] == "1":
                    self.ch0_keepalive_enable.setChecked(True)
            if "KI" in dev_data:
                self.ch0_keepalive_initial.setText(dev_data["KI"])
            if "KE" in dev_data:
                self.ch0_keepalive_retry.setText(dev_data["KE"])
            # reconnection - channel 1
            if "RI" in dev_data:
                self.ch0_reconnection.setText(dev_data["RI"])

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

            # WIZ107SR / WIZ108SR 전용: DDNS / PPPoE 탭 필드 로드
            if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
                # PPPoE 설정 (IM=2일 때만 유효)
                self.pppoe_id.setText(dev_data.get("PI", "").strip())
                self.pppoe_pw.setText(dev_data.get("PP", "").strip())
                # DDNS Enable
                dd_val = dev_data.get("DD", "0").strip()
                self.ddns_enable.setChecked(dd_val == "1")
                # DDNS 서버 설정
                dx_val = dev_data.get("DX", "0").strip()
                try:
                    self.ddns_server_idx.setCurrentIndex(int(dx_val))
                except (ValueError, TypeError):
                    self.ddns_server_idx.setCurrentIndex(0)
                self.ddns_server_port.setText(dev_data.get("DP", "").strip())
                self.ddns_user_id.setText(dev_data.get("DI", "").strip())
                self.ddns_password.setText(dev_data.get("DW", "").strip())
                self.ddns_domain.setText(dev_data.get("DH", "").strip())
                # Network Protocol (PO): TCP Raw(0) / Telnet(1)
                po_val = dev_data.get("PO", "0").strip()
                self.po_telnet.setChecked(po_val == "1")
                self.po_tcp_raw.setChecked(po_val != "1")
                # DDNS 필드 활성화 상태 초기 적용
                self.event_ddns_enable()

            # Modbus (PO/MB depending on device) — WIZ107SR/108SR 제외
            desired_key = self._modbus_param_key()
            fallback_key = "MB" if desired_key == "PO" else "PO"
            for modbus_key in (desired_key, fallback_key):
                if modbus_key in dev_data and dev_data[modbus_key] != "":
                    try:
                        modbus_val = int(dev_data[modbus_key])
                        self.ch0_modbus_protocol.setCurrentIndex(modbus_val)
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
                    self.ch1_status.setText(dev_data["QS"])
                if "EN" in dev_data:
                    self.ch1_uart_name.setText(dev_data["EN"])
                # Network - channel 2
                if "QO" in dev_data:
                    if dev_data["QO"] == "0":
                        self.ch1_tcpclient.setChecked(True)
                    elif dev_data["QO"] == "1":
                        self.ch1_tcpserver.setChecked(True)
                    elif dev_data["QO"] == "2":
                        self.ch1_tcpmixed.setChecked(True)
                    elif dev_data["QO"] == "3":
                        self.ch1_udp.setChecked(True)
                if "QL" in dev_data:
                    self.ch1_localport.setText(dev_data["QL"])
                if "QH" in dev_data:
                    self.ch1_remoteip.setText(dev_data["QH"])
                if "QP" in dev_data:
                    self.ch1_remoteport.setText(dev_data["QP"])
                # serial - channel 2
                if "EB" in dev_data:
                    if len(dev_data["EB"]) > 4:
                        pass
                    else:
                        self.ch1_baud.setCurrentIndex(int(dev_data["EB"]))

                if "ED" in dev_data:
                    if len(dev_data["ED"]) > 2:
                        pass
                    else:
                        self.ch1_databit.setCurrentIndex(int(dev_data["ED"]))
                if "EP" in dev_data:
                    self.ch1_parity.setCurrentIndex(int(dev_data["EP"]))
                if "ES" in dev_data:
                    self.ch1_stopbit.setCurrentIndex(int(dev_data["ES"]))
                if "EF" in dev_data:
                    if len(dev_data["EF"]) > 2:
                        pass
                    else:
                        self.ch1_flow.setCurrentIndex(int(dev_data["EF"]))
                if "NT" in dev_data:
                    self.ch1_pack_time.setText(dev_data["NT"])
                if "NS" in dev_data:
                    self.ch1_pack_size.setText(dev_data["NS"])
                if "ND" in dev_data:
                    if len(dev_data["ND"]) > 2:
                        pass
                    else:
                        self.ch1_pack_char.setText(dev_data["ND"])
                # Inactive timer - channel 2
                if "RV" in dev_data:
                    self.ch1_inact_timer.setText(dev_data["RV"])
                # TCP keep alive - channel 2
                if "RA" in dev_data:
                    if dev_data["RA"] == "0":
                        self.ch1_keepalive_enable.setChecked(False)
                    elif dev_data["RA"] == "1":
                        self.ch1_keepalive_enable.setChecked(True)
                if "RS" in dev_data:
                    self.ch1_keepalive_initial.setText(dev_data["RS"])
                if "RE" in dev_data:
                    self.ch1_keepalive_retry.setText(dev_data["RE"])
                # reconnection - channel 2
                if "RR" in dev_data:
                    self.ch1_reconnection.setText(dev_data["RR"])

            elif self.curr_dev in SECURITY_TWO_PORT_DEV:
                self.lineedit_ch1_ssl_recv_timeout.setText("0")
                self.ch1_modbus_protocol.setCurrentIndex(0)
                self.ch1_serial_connection_condition_connect.clear()
                self.ch1_serial_connection_condition_disconnect.clear()
                self.ch1_ethernet_connection_condition.clear()

                if "QS" in dev_data:
                    self.ch1_status.setText(dev_data["QS"])
                if "EN" in dev_data:
                    self.ch1_uart_name.setText(dev_data["EN"])

                if "AO" in dev_data:
                    ao_val = dev_data["AO"]
                    if ao_val == "0":
                        self.ch1_tcpclient.setChecked(True)
                    elif ao_val == "1":
                        self.ch1_tcpserver.setChecked(True)
                    elif ao_val == "2":
                        self.ch1_tcpmixed.setChecked(True)
                    elif ao_val == "3":
                        self.ch1_udp.setChecked(True)
                    elif ao_val == "4":
                        self.ch1_ssl_tcpclient.setChecked(True)
                    elif ao_val == "5":
                        self.ch1_mqttclient.setChecked(True)
                    elif ao_val == "6":
                        self.ch1_mqtts_client.setChecked(True)

                if "QL" in dev_data:
                    self.ch1_localport.setText(dev_data["QL"])
                if "QH" in dev_data:
                    self.ch1_remoteip.setText(dev_data["QH"])
                if "AP" in dev_data:
                    self.ch1_remoteport.setText(dev_data["AP"])

                if "EB" in dev_data and len(dev_data["EB"]) <= 4:
                    self.ch1_baud.setCurrentIndex(int(dev_data["EB"]))
                if "ED" in dev_data and len(dev_data["ED"]) <= 2:
                    self.ch1_databit.setCurrentIndex(int(dev_data["ED"]))
                if "EP" in dev_data:
                    self.ch1_parity.setCurrentIndex(int(dev_data["EP"]))
                if "ES" in dev_data:
                    self.ch1_stopbit.setCurrentIndex(int(dev_data["ES"]))
                if "EF" in dev_data and len(dev_data["EF"]) <= 2:
                    self.ch1_flow.setCurrentIndex(int(dev_data["EF"]))

                if "AT" in dev_data:
                    self.ch1_pack_time.setText(dev_data["AT"])
                if "NS" in dev_data:
                    self.ch1_pack_size.setText(dev_data["NS"])
                if "ND" in dev_data and len(dev_data["ND"]) <= 2:
                    self.ch1_pack_char.setText(dev_data["ND"])

                if "RV" in dev_data:
                    self.ch1_inact_timer.setText(dev_data["RV"])

                if "RA" in dev_data:
                    self.ch1_keepalive_enable.setChecked(dev_data["RA"] == "1")
                if "RS" in dev_data:
                    self.ch1_keepalive_initial.setText(dev_data["RS"])
                if "RE" in dev_data:
                    self.ch1_keepalive_retry.setText(dev_data["RE"])
                if "RR" in dev_data:
                    self.ch1_reconnection.setText(dev_data["RR"])

                # RO: SSL recv timeout for channel 2 (2-channel devices only)
                if "RO" in dev_data and self.curr_dev in SECURITY_TWO_PORT_DEV:
                    self.lineedit_ch1_ssl_recv_timeout.setText(dev_data["RO"])

                if "EO" in dev_data:
                    try:
                        self.ch1_modbus_protocol.setCurrentIndex(int(dev_data["EO"]))
                    except Exception as ex:
                        self.logger.error(f"Error parsing EO: {dev_data['EO']} -> {ex}")

                if "RD" in dev_data:
                    if dev_data["RD"] == " ":
                        self.ch1_serial_connection_condition_connect.clear()
                    else:
                        self.ch1_serial_connection_condition_connect.setText(dev_data["RD"])

                if "RF" in dev_data:
                    if dev_data["RF"] == " ":
                        self.ch1_serial_connection_condition_disconnect.clear()
                    else:
                        self.ch1_serial_connection_condition_disconnect.setText(dev_data["RF"])

                if "EE" in dev_data:
                    if dev_data["EE"] == " ":
                        self.ch1_ethernet_connection_condition.clear()
                    else:
                        self.ch1_ethernet_connection_condition.setText(dev_data["EE"])

            # SECURITY_TWO_PORT_DEV도 SECURITY_DEVICE에 속하므로 elif가 아닌 if 사용
            #
            # BOOT(부트로더)에서는 MQTT/인증서 커맨드가 응답에 없으므로 건너뛴다.
            # UPGRADE 는 앱이 도는 일시 상태라 응답에 값이 모두 들어 있고,
            # get_object_value() 도 이 항목들을 전송하므로 UI 를 채워야 한다.
            # 채우지 않으면 이전 장치의 값이 남아 그대로 전송될 수 있다.
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
                        self.lineedit_ch0_ssl_recv_timeout.setText(dev_data["SO"])

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

    # get each object's value for setting
    def get_object_value(self):
        self.selected_devinfo()
        if not self.curr_dev or not self.curr_ver:
            return
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
            elif self.ip_pppoe.isChecked() and (
                "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev
            ):
                setcmd["IM"] = "2"
            setcmd["DS"] = self.dns_addr.text()
            # boot 명령에 SP 도 포함되어야 함.
            # search id code: max 8 bytes
            if len(self.searchcode.text()) == 0:
                setcmd["SP"] = " "
            else:
                setcmd["SP"] = self.searchcode.text()
            # 장비 상태가 BOOT(부트로더) 이면 네트워크 기본 설정만 전송한다.
            # 이 지점 이후의 항목(OP/RH/RP, BR 등 시리얼 전체, 타이머, MQTT, 인증서)은
            # 패킷에 실리지 않으므로, 조용히 누락되지 않도록 사용자에게 알린다.
            # UPGRADE 가 제외되는 이유는 wizcmdset.DeviceStatusMinimum 주석 참고.
            # @TODO: GUI 도 막아야 함 — 일반 장치는 BOOT 에서도 Apply 버튼이 열려 있다.
            #        (WIZ550 경로만 btn_setting.setEnabled() 로 차단 중)
            if self.curr_st in DeviceStatusMinimum:
                self._setcmd_reduced = True
                self.logger.warning(
                    f"Setting: device status is {self.curr_st} — "
                    f"only network settings are sent ({sorted(setcmd.keys())}). "
                    "Serial/OP/Remote host and other options are skipped."
                )
                self.statusbar.showMessage(
                    f" Warning: device is in {self.curr_st} state — "
                    "only network settings will be applied."
                )
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
                if self.ch0_tcpclient.isChecked():
                    setcmd["OP"] = "0"
                elif self.ch0_tcpserver.isChecked():
                    setcmd["OP"] = "1"
                elif self.ch0_tcpmixed.isChecked():
                    setcmd["OP"] = "2"
                elif self.ch0_udp.isChecked():
                    setcmd["OP"] = "3"
                elif self.ch0_ssl_tcpclient.isChecked():
                    setcmd["OP"] = "4"
                elif self.ch0_mqttclient.isChecked():
                    setcmd["OP"] = "5"
                elif self.ch0_mqtts_client.isChecked():
                    setcmd["OP"] = "6"
            else:
                if self.ch0_tcpclient.isChecked():
                    setcmd["OP"] = "0"
                elif self.ch0_tcpserver.isChecked():
                    setcmd["OP"] = "1"
                elif self.ch0_tcpmixed.isChecked():
                    setcmd["OP"] = "2"
                elif self.ch0_udp.isChecked():
                    setcmd["OP"] = "3"
            setcmd["LP"] = self.ch0_localport.text()
            setcmd["RH"] = self.ch0_remoteip.text()
            setcmd["RP"] = self.ch0_remoteport.text()
            # serial - channel 1
            setcmd["BR"] = str(self.ch0_baud.currentIndex())
            setcmd["DB"] = str(self.ch0_databit.currentIndex())
            setcmd["PR"] = str(self.ch0_parity.currentIndex())
            setcmd["SB"] = str(self.ch0_stopbit.currentIndex())
            setcmd["FL"] = str(self.ch0_flow.currentIndex())
            # 문맥으로 보면 ch0_modbus_protocol.isEnabled() 로 처리하는게 맞지만 항상 False 가 나와서 모델&버전 비교로 대체 #36
            if self._modbus_supported():
                modbus_key = self._modbus_param_key()
                self.logger.debug(
                    f"set {modbus_key} valid, self.curr_dev={self.curr_dev}, self.curr_ver={self.curr_ver}"
                )
                setcmd[modbus_key] = str(self.ch0_modbus_protocol.currentIndex())

            setcmd["PT"] = self.ch0_pack_time.text()
            setcmd["PS"] = self.ch0_pack_size.text()
            setcmd["PD"] = self.ch0_pack_char.text()
            # Send Data at Connection - W55RP20-S2E, W232N, IP20 (버전 1.1.8 이상)
            if self.curr_dev in (W55RP20_FAMILY + ("W232N", "IP20")) and version_compare(self.curr_ver or "", "1.1.8") >= 0:
                sd_data = self.ch0_serial_connection_condition_connect.text()
                # 최대 30글자로 제한
                if len(sd_data) > 30:
                    sd_data = sd_data[:30]
                    self.ch0_serial_connection_condition_connect.setText(sd_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                self.logger.debug(f"Saving SD data: '{sd_data}'")
                setcmd["SD"] = sd_data if sd_data else " "

                # Send Data at Disconnection - W55RP20-S2E, W232N, IP20
                dd_data = self.ch0_serial_connection_condition_disconnect.text()
                # 최대 30글자로 제한
                if len(dd_data) > 30:
                    dd_data = dd_data[:30]
                    self.ch0_serial_connection_condition_disconnect.setText(dd_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                self.logger.debug(f"Saving DD data: '{dd_data}'")
                setcmd["DD"] = dd_data if dd_data else " "

                # Ethernet Data Connection Condition - W55RP20-S2E, W232N, IP20
                se_data = self.ch0_ethernet_connection_condition.text()
                # 최대 30글자로 제한
                if len(se_data) > 30:
                    se_data = se_data[:30]
                    self.ch0_ethernet_connection_condition.setText(se_data)  # UI도 업데이트
                # 빈 문자열인 경우 공백 전송 (MQTT와 동일한 방식)
                self.logger.debug(f"Saving SE data: '{se_data}'")
                setcmd["SE"] = se_data if se_data else " "
            # Inactive timer - channel 1
            setcmd["IT"] = self.ch0_inact_timer.text()
            # TCP keep alive - channel 1
            if self.ch0_keepalive_enable.isChecked():
                setcmd["KA"] = "1"
                setcmd["KI"] = self.ch0_keepalive_initial.text()
                setcmd["KE"] = self.ch0_keepalive_retry.text()
            else:
                setcmd["KA"] = "0"
            setcmd["KI"] = self.ch0_keepalive_initial.text()
            setcmd["KE"] = self.ch0_keepalive_retry.text()
            # reconnection - channel 1
            setcmd["RI"] = self.ch0_reconnection.text()
            # WIZ107SR / WIZ108SR 전용: DDNS / PPPoE 커맨드 저장
            if "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
                # PPPoE
                setcmd["PI"] = self.pppoe_id.text() or " "
                setcmd["PP"] = self.pppoe_pw.text() or " "
                # DDNS Enable
                setcmd["DD"] = "1" if self.ddns_enable.isChecked() else "0"
                setcmd["DX"] = str(self.ddns_server_idx.currentIndex())
                setcmd["DP"] = self.ddns_server_port.text() or " "
                setcmd["DI"] = self.ddns_user_id.text() or " "
                setcmd["DW"] = self.ddns_password.text() or " "
                setcmd["DH"] = self.ddns_domain.text() or " "
                # Network Protocol (PO): TCP Raw(0) / Telnet(1)
                setcmd["PO"] = "1" if self.po_telnet.isChecked() else "0"

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

            if "WIZ752" in self.curr_dev or "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev:
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
            # BOOT 에서는 GPIO 커맨드가 처리되지 않으므로 제외. UPGRADE 는 포함한다
            # (위 조기 반환과 동일한 이유 — DeviceStatusMinimum 주석 참고).
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
                if self.ch1_tcpclient.isChecked():
                    setcmd["QO"] = "0"
                elif self.ch1_tcpserver.isChecked():
                    setcmd["QO"] = "1"
                elif self.ch1_tcpmixed.isChecked():
                    setcmd["QO"] = "2"
                elif self.ch1_udp.isChecked():
                    setcmd["QO"] = "3"
                setcmd["QL"] = self.ch1_localport.text()
                setcmd["QH"] = self.ch1_remoteip.text()
                setcmd["QP"] = self.ch1_remoteport.text()
                # serial - channel 2
                setcmd["EB"] = str(self.ch1_baud.currentIndex())
                setcmd["ED"] = str(self.ch1_databit.currentIndex())
                setcmd["EP"] = str(self.ch1_parity.currentIndex())
                setcmd["ES"] = str(self.ch1_stopbit.currentIndex())
                setcmd["EF"] = str(self.ch1_flow.currentIndex())
                setcmd["NT"] = self.ch1_pack_time.text()
                setcmd["NS"] = self.ch1_pack_size.text()
                setcmd["ND"] = self.ch1_pack_char.text()
                # Inactive timer - channel 2
                setcmd["RV"] = self.ch1_inact_timer.text()
                # TCP keep alive - channel 2
                if self.ch1_keepalive_enable.isChecked():
                    setcmd["RA"] = "1"
                    setcmd["RS"] = self.ch1_keepalive_initial.text()
                    setcmd["RE"] = self.ch1_keepalive_retry.text()
                else:
                    setcmd["RA"] = "0"
                # reconnection - channel 2
                setcmd["RR"] = self.ch1_reconnection.text()
            elif self.curr_dev in SECURITY_TWO_PORT_DEV:
                if self.ch1_tcpclient.isChecked():
                    setcmd["AO"] = "0"
                elif self.ch1_tcpserver.isChecked():
                    setcmd["AO"] = "1"
                elif self.ch1_tcpmixed.isChecked():
                    setcmd["AO"] = "2"
                elif self.ch1_udp.isChecked():
                    setcmd["AO"] = "3"
                elif self.ch1_ssl_tcpclient.isChecked():
                    setcmd["AO"] = "4"
                elif self.ch1_mqttclient.isChecked():
                    setcmd["AO"] = "5"
                elif self.ch1_mqtts_client.isChecked():
                    setcmd["AO"] = "6"

                setcmd["QL"] = self.ch1_localport.text()
                setcmd["QH"] = self.ch1_remoteip.text()
                setcmd["AP"] = self.ch1_remoteport.text()

                setcmd["EB"] = str(self.ch1_baud.currentIndex())
                setcmd["ED"] = str(self.ch1_databit.currentIndex())
                setcmd["EP"] = str(self.ch1_parity.currentIndex())
                setcmd["ES"] = str(self.ch1_stopbit.currentIndex())
                setcmd["EF"] = str(self.ch1_flow.currentIndex())

                setcmd["AT"] = self.ch1_pack_time.text()
                setcmd["NS"] = self.ch1_pack_size.text()
                setcmd["ND"] = self.ch1_pack_char.text()

                setcmd["RV"] = self.ch1_inact_timer.text()

                if self.ch1_keepalive_enable.isChecked():
                    setcmd["RA"] = "1"
                    setcmd["RS"] = self.ch1_keepalive_initial.text()
                    setcmd["RE"] = self.ch1_keepalive_retry.text()
                else:
                    setcmd["RA"] = "0"

                setcmd["RR"] = self.ch1_reconnection.text()

                # RO: SSL recv timeout for channel 2 (2-channel devices only)
                if self.curr_dev in SECURITY_TWO_PORT_DEV:
                    setcmd["RO"] = self.lineedit_ch1_ssl_recv_timeout.text()
                setcmd["EO"] = str(self.ch1_modbus_protocol.currentIndex())

                rd_data = self.ch1_serial_connection_condition_connect.text()
                if len(rd_data) > 30:
                    rd_data = rd_data[:30]
                    self.ch1_serial_connection_condition_connect.setText(rd_data)
                setcmd["RD"] = rd_data if rd_data else " "

                rf_data = self.ch1_serial_connection_condition_disconnect.text()
                if len(rf_data) > 30:
                    rf_data = rf_data[:30]
                    self.ch1_serial_connection_condition_disconnect.setText(rf_data)
                setcmd["RF"] = rf_data if rf_data else " "

                ee_data = self.ch1_ethernet_connection_condition.text()
                if len(ee_data) > 30:
                    ee_data = ee_data[:30]
                    self.ch1_ethernet_connection_condition.setText(ee_data)
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
                    setcmd["SO"] = self.lineedit_ch0_ssl_recv_timeout.text()

        except Exception as e:
            self.logger.error(e)

        logger.debug(f"setcmd: {setcmd}")
        return setcmd

    def _load_setting_spec(self):
        """현재 선택 장치의 DeviceSpec 로드. 없으면 None (레거시 검증으로 폴백)."""
        if not self.curr_dev:
            return None
        spec_name = detect_device(self.curr_dev) or self.curr_dev
        try:
            return load_device(spec_name, self.curr_ver)
        except FileNotFoundError:
            self.logger.warning(
                f"_load_setting_spec: spec not found for {spec_name!r} — 레거시 검증 사용"
            )
            return None

    def _subnet_mismatch(self):
        """
        선택 장치 IP 가 PC 대역 밖이면 (장치IP, PC IP, prefix) 반환, 아니면 None.
        판단할 정보가 없으면 None (= 문제 없음으로 취급).
        """
        dev_ip = (self.localip_addr or "").strip()
        pc_ip = (self.selected_eth or "").strip()
        if not dev_ip or not pc_ip:
            return None
        try:
            import ipaddress
            prefix = None
            for ad in ifaddr.get_adapters():
                for ip in ad.ips:
                    if isinstance(ip.ip, str) and ip.ip == pc_ip:
                        prefix = ip.network_prefix
                        break
                if prefix is not None:
                    break
            if prefix is None:
                self.logger.info(f"_subnet_mismatch: {pc_ip} 넷마스크 미확인 — 검사 생략")
                return None
            pc_net = ipaddress.ip_interface(f"{pc_ip}/{prefix}").network
            if ipaddress.ip_address(dev_ip) in pc_net:
                return None
            return dev_ip, pc_ip, prefix
        except Exception as e:
            self.logger.info(f"_subnet_mismatch: 검사 생략 ({e})")
            return None

    def _check_upload_subnet(self) -> bool:
        """
        펌웨어 업로드 전 장치 IP 가 PC 와 같은 대역인지 본다. 진행 가능하면 True.

        업로드는 장치가 알려준 자기 IP 로 TCP 접속해서 진행된다
        (FW 응답 = local_ip:port). 대역이 다르면 접속이 안 되는데, 그때는 이미
        장치가 펌웨어 대기 모드로 들어가 설정 채널 응답까지 멈춘 뒤다.
        그래서 시작 전에 확인한다.

        라우팅으로 닿는 구성도 있을 수 있어 차단하지 않고 확인을 받는다.
        """
        mismatch = self._subnet_mismatch()
        if mismatch is None:
            return True
        dev_ip, pc_ip, prefix = mismatch

        self.logger.warning(
            f"[FW] 대역 불일치 — 장치 {dev_ip} / PC {pc_ip}/{prefix} : 업로드 접속 실패 가능"
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Network mismatch")
        box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        box.setText(
            f"The device and this PC are on different subnets.<br><br>"
            f"Device: <b>{dev_ip}</b><br>PC: <b>{pc_ip}/{prefix}</b>"
        )
        box.setInformativeText(
            "Firmware upload connects directly to the device IP, so it will "
            "likely fail.\n"
            "Change the device IP to the same subnet, or add an address in the "
            "device's subnet to this PC, then try again.\n\n"
            "Search uses broadcast, so the device still appears in the list "
            "even when the subnets differ.\n\n"
            "Continue anyway?"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        return box.exec_() == QMessageBox.Yes

    def _verify_fw_image(self, filepath: str) -> bool:
        """
        업로드 직전 이미지 검증. 통과하면 True, 막으면 False.

        파일명 표기와 벡터 테이블 판정을 대조해 둘이 어긋나거나 APP 이 아니면
        차단한다. 검증 기준(fw_image.profile)이 없는 장치도 차단한다 —
        근거 없이 통과시키면 다른 이미지를 그대로 굽게 된다.
        """
        try:
            from fw_image_check import FWImageChecker, OK
            from fw_git_fetcher import FWGitFetcher
            if getattr(self, "_fw_image_checker", None) is None:
                self._fw_image_checker = FWImageChecker(
                    resource_path("config/fw_image_defaults.yaml"), logger=self.logger
                )
            spec = self._load_setting_spec()
            result = self._fw_image_checker.check(
                filepath,
                getattr(spec, "fw_image", None) if spec else None,
                FWGitFetcher.is_non_app_name,
            )
        except Exception as e:
            # 검증기 자체가 실패하면 판단 근거가 없으므로 막는다
            self.logger.error(f"_verify_fw_image failed: {e}")
            self.show_msgbox(
                "Warning",
                f"Firmware image check could not be performed.\n{e}",
                QMessageBox.Warning,
            )
            return False

        if result["result"] == OK:
            return True

        self.logger.warning(
            f"[FWImageCheck] 업로드 차단 — {result['reason']} / {result['detail']}"
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Firmware image check")
        box.setText(result["reason"])
        box.setInformativeText("Please select an APP firmware file.")
        box.setDetailedText(result["detail"])
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()
        return False

    def _get_set_response_timeout(self):
        """
        SET 명령 응답 대기 타임아웃(초). Advanced Search Options에서 조정 가능.

        WIZ5XXSR-RP 계열은 별도 값을 사용한다. 해당 장치는 TCP client 접속 실패 시
        `connect()`가 최대 1.8초(RCR 8 x RTR 200ms) 블로킹되고, SET 직후 플래시
        저장(4KB 섹터 소거, 최대 400ms급)이 겹쳐 일반 타임아웃으로는 응답을
        놓치는 경우가 있다 (TASKS.md BUG-WIZ5XX-SET-NORESP).
        """
        try:
            if self.curr_dev and "WIZ5XXSR" in self.curr_dev:
                timeout = self.timing_config.get_phase3_set_response_timeout_5xx()
            else:
                timeout = self.timing_config.get_phase3_set_response_timeout()
        except Exception as e:
            self.logger.warning(f"_get_set_response_timeout: {e} — 기본값 2초 사용")
            return 2
        self.logger.debug(f"SET response timeout: {timeout}s (dev={self.curr_dev})")
        return timeout

    def _is_valid_setcmd_param(self, spec, cmd, value):
        """
        SET 파라미터 검증. 커맨드 단위로 DeviceSpec 우선, 없으면 레거시 cmdset 폴백.

        DeviceSpec(specs/*.yaml)은 FW 소스 기준으로 정비된 값이므로 우선한다.
        아직 spec에 정의되지 않은 커맨드(GPIO/Modbus 등)는 레거시가 계속 담당한다.
        """
        if spec is not None and cmd in spec.cmdset:
            return bool(spec.cmdset[cmd].is_valid(value)), "spec"
        return bool(self.cmdset.isvalidparameter(cmd, value)), "legacy"

    def do_setting(self):
        self.disable_object()

        self.set_reponse = None
        self._setcmd_reduced = False

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
            if setcmd is None:
                return

            # Update cmdset
            self.cmdset.get_cmdset(self.curr_dev, self.curr_st, self.curr_ver)
            self.logger.info(f"Device setting: {self.curr_dev}")
            # Parameter validity check (DeviceSpec 우선 + 레거시 폴백)
            invalid_flag = 0
            self.logger.debug(f"do_setting::setcmd={setcmd}")
            spec = self._load_setting_spec()
            for cmd, value in setcmd.items():
                is_valid, source = self._is_valid_setcmd_param(spec, cmd, value)
                if not is_valid:
                    self.logger.warning(
                        f"Invalid parameter [{source}]: {cmd} {value!r}"
                    )
                    self.msg_invalid(value)
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

                set_timeout = self._get_set_response_timeout()
                if self.unicast_ip.isChecked():
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, "tcp", Opcode.OP_SETCOMMAND, set_timeout
                    )
                else:
                    self.wizmsghandler = WIZMSGHandler(
                        self.conf_sock, cmd_list, "udp", Opcode.OP_SETCOMMAND, set_timeout
                    )
                self.wizmsghandler.set_result.connect(self.get_setting_result)
                self.wizmsghandler.start()

    def _get_expected_min_resp_len(self, devname: str, version: str) -> int:
        """
        장치별 SET 응답 최소 예상 길이.

        SET 패킷 말미에 SearchMsg(GET cmds) + SV + RT 가 항상 붙으며,
        장치는 SearchMsg 에 대한 응답을 전송함.
        각 응답 라인 최소 길이: cmd(2) + value(1) + CRLF(2) = 5 bytes
        여기에 MA prefix(10) + PW 라인(5+) 을 더해 최소값 산출.

        이 값보다 짧으면 장치가 SearchMsg 처리 전에 리부트한 것 (IM 모드 변경 등).
        """
        from WIZMakeCMD import (
            cmd_107sr, cmd_1p_advanced, cmd_1p_default, cmd_2p_default,
            cmd_security_base, cmd_wiz5xxsr_added, cmd_w55rp20_added,
            ONE_PORT_DEV, TWO_PORT_DEV, SECURITY_DEVICE,
            version_compare,
        )
        if "WIZ107SR" in devname or "WIZ108SR" in devname:
            n = len(cmd_107sr)                          # 42
        elif devname in TWO_PORT_DEV or "752" in devname:
            n = len(cmd_2p_default)
        elif devname in SECURITY_DEVICE:
            n = len(cmd_security_base + cmd_wiz5xxsr_added)
        elif devname in ONE_PORT_DEV:
            if version_compare("1.2.0", version) <= 0:
                n = len(cmd_1p_advanced)                # 44
            else:
                n = len(cmd_1p_default)                 # 40
        else:
            n = len(cmd_1p_default)

        # MA prefix(10) + PW 라인(최소 5) + 커맨드 응답(최소 5 bytes/cmd)
        return 10 + 5 + n * 5

    def _refresh_status_from_set_result(self, set_result):
        """
        SET 응답의 ST 값으로 curr_st / dev_data 를 최신화한다.

        curr_st 는 검색 시점(get_dev_list)에만 채워지므로, 재검색 없이 Apply 를
        반복하면 과거 상태가 남는다. BOOT/UPGRADE 가 남아 있으면
        get_object_value() 가 네트워크 설정만 담고 조기 반환하여
        시리얼/OP/Remote host 등이 조용히 누락된다.

        dev_data[mac] 는 [MN, VR, ST] 형태이며, dev_clicked() 가 여기서
        curr_st 를 다시 읽으므로 dev_data 를 함께 갱신한다.
        """
        new_st = set_result.get("ST")
        if not new_st:
            return
        new_st = new_st.strip()
        if not new_st or new_st == self.curr_st:
            return

        prev_st = self.curr_st
        self.curr_st = new_st
        entry = self.dev_data.get(self.curr_mac)
        if isinstance(entry, list) and len(entry) >= 3:
            entry[2] = new_st
        self.logger.info(f"Device status refreshed from SET response: {prev_st} -> {new_st}")

    def get_setting_result(self, resp_len):
        if not self.curr_dev or not self.curr_ver:
            return
        prev_channel_tab_index = self.channel_tab.currentIndex()
        set_result = {}

        if resp_len == -1:
            self.logger.warning("Setting: no response from device.")
            self.statusbar.showMessage(" Setting: no response from device.")
            self.msg_set_error()

        elif resp_len == -3:
            self.logger.warning("Setting: wrong password")
            self.statusbar.showMessage(" Setting: wrong password.")
            self.msg_setting_pw_error()

        elif resp_len > 0:
            if self.wizmsghandler is None:
                return
            self.set_reponse = self.wizmsghandler.rcv_list[0]

            # ── 응답 파싱 (VB.NET parsingMsg() 방식) ──────────────────────
            # MA prefix(10 bytes) 제거 후 \r\n 단위로 분리
            payload = (self.set_reponse[10:]
                       if len(self.set_reponse) >= 10 and self.set_reponse[:2] == b"MA"
                       else self.set_reponse)
            for chunk in payload.split(b"\r\n"):
                if len(chunk) < 3 or chunk[:2] == b"MA":
                    continue
                try:
                    cmd   = chunk[:2].decode("ascii")
                    param = chunk[2:].decode("utf-8", errors="replace")
                    set_result[cmd] = param
                except Exception as e:
                    self.logger.error(e)

            mc = set_result.get("MC", "")
            er = set_result.get("ER", "")

            # 장치별 최소 예상 응답 길이
            min_len = self._get_expected_min_resp_len(self.curr_dev, self.curr_ver)
            self.logger.info(
                f"Setting resp_len={resp_len}, expected_min={min_len}, "
                f"MC='{mc}', ER='{er}'"
            )

            if er:
                # 장치가 ER 필드를 반환 → 오류 내용 표시
                self.logger.warning(f"Setting: device error response: {er}")
                self.statusbar.showMessage(f" Setting error: {er}")
                self.msg_set_warning(er)

            elif len(mc) == 17:
                # ── 정상 성공: MAC 유효 (VB.NET: nSec.MC.data.Length == 17) ──
                if self._setcmd_reduced:
                    self.statusbar.showMessage(
                        f" Set complete — network settings only "
                        f"(device was in {self.curr_st} state)."
                    )
                else:
                    self.statusbar.showMessage(" Set device complete!")
                self.msg_set_success()

                # SET 응답에 포함된 ST 로 장치 상태를 최신화한다.
                # curr_st 는 원래 검색 시점(dev_data)에만 갱신되어, 재검색 없이 Apply 를
                # 반복하면 과거 상태(BOOT/UPGRADE)가 남아 설정이 조용히 축소 전송된다.
                # 응답에 이미 ST 가 들어 있으므로 추가 통신 없이 자가 치유가 가능하다.
                self._refresh_status_from_set_result(set_result)

                if self.isConnected and self.unicast_ip.isChecked():
                    self.logger.info("close socket")
                    if self.conf_sock is not None:
                        self.conf_sock.close()

                try:
                    clicked_mac = self.list_device.selectedItems()[0].text()
                    if clicked_mac in self.dev_profile:
                        self.dev_profile[clicked_mac].update(set_result)
                    else:
                        self.dev_profile[clicked_mac] = set_result
                except Exception as e:
                    self.logger.error(e)

                self.dev_clicked(call_from=sys._getframe().f_code.co_name)

            elif resp_len >= min_len:
                # 응답 길이는 충분하나 MAC 파싱 실패 → 포맷 이상
                self.logger.warning(
                    f"Setting: resp_len={resp_len} >= min({min_len}) "
                    "but MC field invalid. Unexpected response format."
                )
                self.statusbar.showMessage(" Warning: setting response format unexpected.")
                self.msg_set_warning()

            else:
                # 응답이 min_len 미만 → IM 모드 변경 등 즉시 리부트
                # 커맨드는 전달됐으나 SearchMsg 응답 전에 리부트
                self.logger.info(
                    f"Setting: short response ({resp_len} bytes < min {min_len}). "
                    "Device rebooted before full response (e.g. IP mode change). "
                    "Command was delivered."
                )
                self.statusbar.showMessage(
                    " Setting sent. Device rebooted (IP mode change). Re-search to verify."
                )

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
                row = currentItem.row()
                _dev_info = self.dev_data.get(self.curr_mac)
                if _dev_info is not None:
                    self.curr_ver = _dev_info[1]
                    self.curr_st = _dev_info[2]
                else:
                    # Phase 3 미완료: Phase 1 데이터로 폴백 (curr_ver 빈 문자열 방지)
                    self.curr_ver = (
                        self.vr_list[row].decode('utf-8', errors='replace')
                        if row < len(self.vr_list) else ''
                    )
                    self.curr_st = (
                        self.st_list[row].decode('utf-8', errors='replace')
                        if row < len(self.st_list) else ''
                    )
                selected_row = row
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

        # IP Address 유니캐스트 라벨·포트 자동 갱신: WIZ550 ↔ WIZ5xxSR
        if self.curr_mac:
            _proto = self.dev_profile.get(self.curr_mac, {}).get('_proto', '')
            if _proto == 'wiz550':
                self.unicast_ip.setText("IP Address")
                self.search_port.setText("6550")
            else:
                self.unicast_ip.setText("TCP unicast")
                if self.search_port.text() == "6550":
                    self.search_port.setText("50001")

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
            if self.conf_sock is not None:
                self.conf_sock.close()
        self.pgbar.hide()

    def update_error(self, error):
        self.logger.error(f"Firmware update error: {error}")

        text = ""
        if error == -1:
            text = " Firmware update failed. No response from device."
            self.statusbar.showMessage(text)
            # 대역이 다르면 장치가 응답을 안 한 게 아니라 접속이 안 된 것이다.
            # "No response" 만 보여주면 원인을 엉뚱한 데서 찾게 된다.
            mismatch = self._subnet_mismatch()
            detail = text
            if mismatch:
                dev_ip, pc_ip, prefix = mismatch
                detail = (
                    f"{text}\n\n"
                    f"The device ({dev_ip}) is on a different subnet from this "
                    f"PC ({pc_ip}/{prefix}).\n"
                    f"Firmware upload connects directly to the device IP, so it "
                    f"fails when the subnets differ.\n"
                    f"Change the device IP to the same subnet, or add an address "
                    f"in the device's subnet to this PC."
                )
            self.show_msgbox("Error", detail, QMessageBox.Critical)
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
            if self.t_fwup is not None and self.t_fwup.isRunning():
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
            if self.conf_sock is not None:
                self.conf_sock.close()
        self.pgbar.hide()

    def cert_error(self, error):
        try:
            if self.th_cert is not None and self.th_cert.isRunning():
                self.th_cert.terminate()
        except Exception as e:
            self.logger.error(e)

        if error == -1:
            self.statusbar.showMessage(
                " Certificate update failed. No response from device."
            )
        elif error == -2:
            self.statusbar.showMessage(" Certificate update: Network connection failed.")
            self.msg_connection_failed()
        elif error == -3:
            self.statusbar.showMessage(" Certificate update error.")

    # ── FW from Git ───────────────────────────────────────────────────────────
    def _load_fw_download_path(self) -> str:
        try:
            cfg = os.path.join("config", "ui_state.json")
            if os.path.exists(cfg):
                with open(cfg, encoding="utf-8") as f:
                    state = json.load(f)
                p = state.get("fw", {}).get("download_path", "")
                if p:
                    return p
        except Exception:
            pass
        from pathlib import Path
        return str(Path.home() / "Downloads")

    def _save_fw_download_path(self, path: str):
        cfg = os.path.join("config", "ui_state.json")
        try:
            state = {}
            if os.path.exists(cfg):
                with open(cfg, encoding="utf-8") as f:
                    state = json.load(f)
            state.setdefault("fw", {})["download_path"] = path
            os.makedirs("config", exist_ok=True)
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"FW download path save failed: {e}")

    def event_set_fw_download_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select FW Download Path", self._fw_download_path
        )
        if path:
            self._fw_download_path = path
            self._save_fw_download_path(path)

    def _handle_unsupported_fw_device(self):
        """
        FW from Git 에 배포처가 등록되지 않은 장치를 만났을 때의 처리.
        사용자에게 알리고, 동의하면 툴 저장소 이슈로 남긴다.
        """
        # 공개 배포처가 없음을 이미 확인한 장치는 사유를 그대로 알린다.
        # 이슈로 물어볼 것이 없으므로 등록 제안도 하지 않는다.
        reason = self._fw_fetcher.find_unsupported(self.curr_dev)
        if reason:
            self.show_msgbox_richtext(
                "Unsupported device",
                f"<b>FW from Git</b> is not supported for "
                f"<b>{self.curr_dev}</b>.<br><br>"
                f"{reason}<br><br>"
                f"Download the firmware file yourself and use "
                f"<b>Firmware Upload</b> instead.",
                QMessageBox.Warning,
            )
            self.logger.info(
                f"[FW from Git] {self.curr_dev}: 미지원 장치 (사유: {reason})"
            )
            return

        supported = ", ".join(sorted(set(self._fw_fetcher.supported_devices())))
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Unsupported device")
        box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        box.setText(
            f"No firmware source is registered for <b>{self.curr_dev}</b>.<br><br>"
            f"Stopping here so that firmware for another product is not "
            f"installed by mistake.<br>"
            f"Download the firmware file yourself and use "
            f"<b>Firmware Upload</b> instead."
        )
        box.setDetailedText(f"Registered devices:\n{supported}")
        box.setInformativeText(
            "Report this device so it can be added to the supported list?"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes)
        if box.exec_() != QMessageBox.Yes:
            return

        try:
            from fw_issue_reporter import FWIssueReporter
            from fw_git_dialog import ReportUnsupportedThread
        except Exception as e:
            self.logger.warning(f"issue reporter import failed: {e}")
            return

        reporter = FWIssueReporter(
            "Wiznet/WIZnet-S2E-Tool-GUI", VERSION, logger=self.logger
        )
        self._fw_issue_thread = ReportUnsupportedThread(
            reporter, self.curr_dev, self.curr_ver or ""
        )
        self._fw_issue_thread.done.connect(self._on_fw_issue_reported)
        self._fw_issue_thread.start()

    def _on_fw_issue_reported(self, result: dict):
        """이슈 보고 결과 안내. manual 이면 사용자가 직접 제출하도록 브라우저를 연다."""
        action = result.get("action", "")
        url = result.get("url", "")
        msg = result.get("message", "")
        self.logger.info(f"[FW from Git] unsupported device report: {action} {url}")

        if action == "manual" and url:
            webbrowser.open(url)
        if action == "error":
            self.show_msgbox(
                "Warning", f"Failed to report the issue.\n{msg}", QMessageBox.Warning
            )
            return
        body = msg + (f"\n\n{url}" if url else "")
        self.show_msgbox("Information", body, QMessageBox.Information)

    def event_fw_from_git(self):
        if not self.curr_dev:
            self.show_msgbox("Warning", "Please select a device first.", QMessageBox.Warning)
            return
        if self._fw_fetcher is None:
            self.show_msgbox(
                "Warning",
                "Failed to load FW from Git configuration file (fw_sources.json).",
                QMessageBox.Warning,
            )
            return
        # 받아놓고 못 올리는 일이 없도록 다이얼로그를 열기 전에 대역부터 확인한다
        if not self._check_upload_subnet():
            return

        is_wiz550 = (
            hasattr(self, 'curr_mac') and self.curr_mac
            and self.dev_profile.get(self.curr_mac, {}).get('_proto') == 'wiz550'
        )

        if is_wiz550:
            # device_type 기반으로 해당 장치에 맞는 펌웨어만 표시 — 잘못된 이미지 플래싱 방지
            _dev_type = self.dev_profile.get(self.curr_mac, {}).get('device_type', '')
            if 'SR' in _dev_type.upper():
                _wiz550_type_map = [("SR", "wiz550sr")]
            else:
                # S2E / WEB — SR 이미지 노출 방지
                _wiz550_type_map = [
                    ("SE / MQTT",  "wiz550s2e"),
                    ("SE-MODBUS",  "wiz550s2e_modbus"),
                ]
            fw_type_list = []
            for label, fid in _wiz550_type_map:
                fam, dspec = self._fw_fetcher.find_family_by_id(fid)
                if fam and dspec:
                    fw_type_list.append({"label": label, "family": fam, "device_spec": dspec})
            family      = fw_type_list[0]["family"]
            device_spec = fw_type_list[0]["device_spec"]
            display_name = self.curr_dev
        else:
            fw_type_list = []
            family, device_spec = self._fw_fetcher.find_device(self.curr_dev)
            if family is None:
                # 등록되지 않은 장치를 임의의 family 로 대체하면 다른 제품의
                # 이미지를 그대로 플래싱하게 된다(예: WIZ5XXSR-RP -> IP20).
                # 추측하지 않고 중단한다.
                self._handle_unsupported_fw_device()
                return
            display_name = self.curr_dev

        wiz550_config = None
        if is_wiz550 and self.curr_mac and self.curr_mac in self.dev_profile:
            _d = self.dev_profile[self.curr_mac]
            _tip = _d.get('local_ip', '') or _d.get('IP', '')
            if _tip:
                wiz550_config = {
                    'target_ip':   _tip,
                    'target_mac':  self.curr_mac,
                    'localip_addr': self.selected_eth or '',
                    'pw_setting':  _d.get('pw_setting', '').strip(),
                }

        from fw_git_dialog import FWGitDialog
        dlg = FWGitDialog(
            self, display_name, family, device_spec,
            self._fw_fetcher, self._fw_download_path,
            fw_type_list=fw_type_list or None,
            wiz550_config=wiz550_config,
            image_validator=self._verify_fw_image,
        )
        dlg.firmware_ready.connect(self._on_fw_git_ready)
        dlg.exec_()

    def _on_fw_git_ready(self, filepath: str, filesize: int):
        # 배포처 설정이 잘못돼 부트로더나 병합본이 뽑혀 나와도 굽지 않도록,
        # 수동 선택 경로와 같은 검증을 여기에도 건다.
        if not self._verify_fw_image(filepath):
            self._cleanup_fw_git_file(filepath)
            return
        if self.localip_addr is None:
            self.show_msgbox(
                "Warning",
                "Local IP information could not be found. Check the Network configuration.",
                QMessageBox.Warning,
            )
            return
        # WIZ107/108SR 특수 케이스 (firmware_file_open()과 동일)
        if self.curr_dev and (
            "WIZ107" in self.curr_dev or "WIZ108" in self.curr_dev
        ):
            filesize = 51 * 1024
        self.firmware_update(filepath, filesize)
        if self.t_fwup is not None:
            _path = filepath
            self.t_fwup.upload_result.connect(
                lambda _, p=_path: self._cleanup_fw_git_file(p)
            )

    def _cleanup_fw_git_file(self, path: str):
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

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
        if self.t_fwup is None:
            self.logger.error("firmware_update: t_fwup not initialized (no search mode selected)")
            self.update_result(-1)
            return
        self.t_fwup.uploading_size.connect(self.pgbar.setValue)
        self.t_fwup.upload_result.connect(self.update_result)
        self.t_fwup.error_flag.connect(self.update_error)
        try:
            self.t_fwup.start()
        except Exception as e:
            self.logger.error(e)
            self.update_result(-1)

    def firmware_file_open(self):
        if not self.curr_dev:
            return
        fname, _ = QFileDialog.getOpenFileName(
            self, "Firmware file open", "", "Binary Files (*.bin);;All Files (*)"
        )

        if fname:
            # 파일명 표기 + 벡터 테이블 대조. 둘이 어긋나거나 APP 이 아니면 중단.
            if not self._verify_fw_image(fname):
                return
            if not self._check_upload_subnet():
                return

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
                    msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)
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
            ["ping", "-n", "1", serverip]
            if sys.platform == "win32"
            else ["ping", "-c", "1", serverip],
            stdout=None,
            stderr=None,
            shell=False,
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
                if self.conf_sock is not None:
                    self.conf_sock.close()
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
                if self.conf_sock is not None:
                    self.conf_sock.close()
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
        self.logger.debug(f"load_cert_btn_clicked cmd={cmd}")

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
            ip_addr = self.localip.text()
            port = 50002
            if self.unicast_ip.isChecked():
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
        msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)
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
            self.logger.debug(f"The latest release version is: {latest_release}")
            if VERSION.lower() != str(latest_release).lower():
                self.show_msgbox_info(
                    "Update Available",
                    f"Version {latest_release} is available.\nPlease download the latest version from the Github.",
                )
        except Exception as e:
            self.logger.error(e)

    def about_info(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLabel
        from PyQt5.QtCore import QUrl

        dialog = QDialog(self)
        dialog.setWindowTitle("About WIZnet-S2E-Tool-GUI")
        dialog.setFixedWidth(420)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 14, 20, 10)
        layout.setSpacing(6)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setFrameShape(QtWidgets.QFrame.NoFrame)
        browser.setReadOnly(True)
        browser.setStyleSheet(
            "background: white; border: 1px solid #c0c0c0; border-radius: 4px; padding: 8px;"
        )
        browser.document().setDocumentMargin(0)
        gh = "https://github.com/Wiznet/WIZnet-S2E-Tool-GUI"
        browser.setHtml(
            f"<html><body style='font-family:Arial,sans-serif;font-size:13px;margin:0;padding:0;'>"
            f"<h2 style='margin:0 0 6px 0;'>About WIZnet-S2E-Tool-GUI</h2>"
            f"<p style='margin:2px 0;'>Configuration Tool for WIZnet serial to ethernet devices.</p>"
            f"<p style='margin:2px 0;'>Version: <b>{VERSION}</b></p>"
            f"<p style='margin:2px 0;'>Author: WIZnet</p>"
            f"<p style='margin:2px 0;'>Github: <a href='{gh}'>Repository</a>"
            f" &nbsp;|&nbsp; <a href='{gh}/releases'>Release</a></p>"
            f"<p style='margin:8px 0 2px 0;'><b>Web site</b></p>"
            f"<p style='margin:2px 0;'><a href='http://www.wiznet.io/'>WIZnet Official homepage</a></p>"
            f"<p style='margin:2px 0;'><a href='https://forum.wiznet.io/'>WIZnet Forum</a></p>"
            f"<p style='margin:2px 0;'><a href='https://docs.wiznet.io/'>WIZnet Document</a></p>"
            f"<p style='margin:8px 0 0 0;'><small>{datetime.datetime.now().year} WIZnet Co., Ltd.</small></p>"
            f"</body></html>"
        )
        layout.addWidget(browser)

        ver_label = QLabel("Checking for updates...")
        ver_label.setStyleSheet("color: gray; font-size: 12px; padding: 2px 0;")
        layout.addWidget(ver_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        self._ver_thread = VersionCheckThread()

        def _on_version(latest):
            if not latest:
                ver_label.setText("Version check failed (network error)")
                ver_label.setStyleSheet("color: gray; font-size: 12px;")
            elif latest.lstrip('vV') == VERSION.lstrip('vV'):
                ver_label.setText("✓ You are up to date")
                ver_label.setStyleSheet("color: green; font-size: 12px;")
            else:
                ver_label.setText(
                    f"{latest} is available. "
                    f"<a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/releases'>"
                    f"Download</a>"
                )
                ver_label.setTextFormat(QtCore.Qt.RichText)
                ver_label.setOpenExternalLinks(True)
                ver_label.setStyleSheet("color: #c07000; font-size: 12px;")

        self._ver_thread.finished.connect(_on_version)
        self._ver_thread.start()

        dialog.exec_()
        self._ver_thread.quit()

    def menu_document(self):
        self.logger.info("Menu: documentation")
        # documentation pop-up
        webbrowser.open("https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/wiki")

    def msg_not_support(self):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Not supported device")
        msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)
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

    def msg_set_warning(self, device_error=None):
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Warning)
        msgbox.setWindowTitle("Warning: Setting")
        if device_error:
            msgbox.setText(
                f"Device returned an error:\n{device_error}\n\n"
                "Please check the parameter or the firmware version."
            )
        else:
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
        mac_part = (self.curr_mac or "").replace(":", "")[6:]
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
        if setcmd is None:
            return
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
            QtGui.QPixmap(resource_path(iconfile)), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off
        )
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(32, 32))
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
        self.menuBar.setFont(self.midfont)  # type: ignore[union-attr]
        self.menuFile.setFont(self.midfont)
        self.menuOption.setFont(self.midfont)
        self.menuHelp.setFont(self.midfont)
        self.action_set_wait_time.setFont(self.midfont)
        self.action_retry_search.setFont(self.midfont)
        self.tcp_timeout_label.setFont(self.smallfont)
        self.atmode_desc.setFont(self.smallfont)
        self.searchcode_desc.setFont(self.smallfont)

        self.ch0_reconnection_label.setFont(self.smallfont)
        self.ch1_reconnection_label.setFont(self.smallfont)
        self.gpioa_label.setFont(self.smallfont)
        self.gpiob_label.setFont(self.smallfont)
        self.gpioc_label.setFont(self.smallfont)
        self.gpiod_label.setFont(self.smallfont)

        # self.certificate_detail.setFont(self.certfont)

        # ⓘ 아이콘 라벨 설정 (클릭 및 빠른 호버 지원)
        # NOTE: 1.5.7 UI 복원으로 인해 info 라벨들이 제거되어 비활성화
        # self._setup_info_labels()

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
                        "Settings Saved",
                        "Search timing settings have been saved.\n\n"
                        "Some settings will take effect from the next search."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Save Failed",
                        "Failed to save settings.\n"
                        "Please check the log."
                    )

        except Exception as e:
            self.logger.error(f"타이밍 설정 다이얼로그 오류: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while configuring timing settings:\n{e}"
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
        dialog.setWindowTitle("Search Timing Settings")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # === Phase 1 타이밍 그룹 ===
        phase1_group = QGroupBox("Phase 1 Timing (UDP Broadcast / TCP Multicast)")
        phase1_layout = QFormLayout()

        # Loop Select Timeout
        dialog.spin_loop_timeout = QDoubleSpinBox()
        dialog.spin_loop_timeout.setRange(0.1, 5.0)
        dialog.spin_loop_timeout.setSingleStep(0.1)
        dialog.spin_loop_timeout.setDecimals(1)
        dialog.spin_loop_timeout.setSuffix(" sec")
        dialog.spin_loop_timeout.setValue(current_values['phase1_loop_select_timeout'])
        dialog.spin_loop_timeout.setToolTip(
            "Additional wait time after the last response\n"
            "Recommended: 0.5s (normal), 1.0s (legacy devices), 0.3s (fast)"
        )
        phase1_layout.addRow("Loop Select Timeout:", dialog.spin_loop_timeout)

        # Emit Stabilization Delay
        dialog.spin_emit_delay = QSpinBox()
        dialog.spin_emit_delay.setRange(0, 500)
        dialog.spin_emit_delay.setSingleStep(10)
        dialog.spin_emit_delay.setSuffix(" ms")
        dialog.spin_emit_delay.setValue(current_values['phase1_emit_stabilization_ms'])
        dialog.spin_emit_delay.setToolTip(
            "PyQt signal queue stabilization wait time\n"
            "Recommended: 50ms (experimental: 0~100ms)"
        )
        phase1_layout.addRow("Emit Stabilization Delay:", dialog.spin_emit_delay)

        # Skip Emit Delay (Experimental)
        dialog.check_skip_delay = QCheckBox()
        dialog.check_skip_delay.setChecked(current_values['skip_phase1_emit_delay'])
        dialog.check_skip_delay.setToolTip(
            "Experimental: Skip the pre-emit delay\n"
            "Saves about 50ms when enabled, but signal queue may be unstable"
        )
        phase1_layout.addRow("Skip Emit Delay (Experimental):", dialog.check_skip_delay)

        phase1_group.setLayout(phase1_layout)
        main_layout.addWidget(phase1_group)

        # === Phase 3 타이밍 그룹 ===
        phase3_group = QGroupBox("Phase 3 Timing (Per-Device Query)")
        phase3_layout = QFormLayout()

        # Device Query Timeout
        dialog.spin_query_timeout = QDoubleSpinBox()
        dialog.spin_query_timeout.setRange(0.5, 5.0)
        dialog.spin_query_timeout.setSingleStep(0.1)
        dialog.spin_query_timeout.setDecimals(1)
        dialog.spin_query_timeout.setSuffix(" sec")
        dialog.spin_query_timeout.setValue(current_values['phase3_device_query_timeout'])
        dialog.spin_query_timeout.setToolTip(
            "Per-device response wait time\n"
            "Recommended: 1.5s (normal), 1.0s (fast), 2.0s (slow/distant)"
        )
        phase3_layout.addRow("Device Query Timeout:", dialog.spin_query_timeout)

        # SET Command Post-Response Delay
        dialog.spin_set_delay = QSpinBox()
        dialog.spin_set_delay.setRange(0, 2000)
        dialog.spin_set_delay.setSingleStep(100)
        dialog.spin_set_delay.setSuffix(" ms")
        dialog.spin_set_delay.setValue(current_values['phase3_set_command_delay_ms'])
        dialog.spin_set_delay.setToolTip(
            "Wait time after SET response before re-querying the device.\n"
            "The device reboots immediately after SET, and dev_clicked() queries it\n"
            "right after — without this delay the device is mid-reboot and won't respond.\n\n"
            "Default: 500 ms (recommended — do not reduce for older/slow devices).\n"
            "Reducing below 200 ms risks SET-after-reboot query failures."
        )
        phase3_layout.addRow("SET Response Delay:", dialog.spin_set_delay)

        # SET Response Timeout (일반 장치)
        dialog.spin_set_timeout = QDoubleSpinBox()
        dialog.spin_set_timeout.setRange(1.0, 15.0)
        dialog.spin_set_timeout.setSingleStep(0.5)
        dialog.spin_set_timeout.setDecimals(1)
        dialog.spin_set_timeout.setSuffix(" sec")
        dialog.spin_set_timeout.setValue(current_values['phase3_set_response_timeout'])
        dialog.spin_set_timeout.setToolTip(
            "How long to wait for the device response after Apply.\n"
            "Exceeding this shows \"Setting failed\" even if the device applied the setting.\n\n"
            "Default: 2.0 s"
        )
        phase3_layout.addRow("SET Response Timeout:", dialog.spin_set_timeout)

        # SET Response Timeout (WIZ5XXSR-RP 전용)
        dialog.spin_set_timeout_5xx = QDoubleSpinBox()
        dialog.spin_set_timeout_5xx.setRange(1.0, 30.0)
        dialog.spin_set_timeout_5xx.setSingleStep(0.5)
        dialog.spin_set_timeout_5xx.setDecimals(1)
        dialog.spin_set_timeout_5xx.setSuffix(" sec")
        dialog.spin_set_timeout_5xx.setValue(current_values['phase3_set_response_timeout_5xx'])
        dialog.spin_set_timeout_5xx.setToolTip(
            "SET response timeout applied only to WIZ5XXSR-RP devices.\n\n"
            "These devices block up to 1.8 s inside connect() when the remote host is\n"
            "unreachable (RCR 8 x RTR 200 ms), and the flash save right after SET\n"
            "(4 KB sector erase, up to ~400 ms) can overlap with it. The general 2.0 s\n"
            "timeout can therefore be too short in some situations.\n\n"
            "Default: 2.0 s (same as the general value). Raise it toward 5.0 s if\n"
            "\"Setting failed\" appears while the setting is actually applied."
        )
        phase3_layout.addRow("SET Response Timeout (WIZ5XXSR-RP):", dialog.spin_set_timeout_5xx)

        phase3_group.setLayout(phase3_layout)
        main_layout.addWidget(phase3_group)

        # === TCP 설정 그룹 ===
        tcp_group = QGroupBox("TCP Settings (TCP Multicast / Mixed Search)")
        tcp_layout = QFormLayout()

        # Max Parallel Workers
        dialog.spin_tcp_workers = QSpinBox()
        dialog.spin_tcp_workers.setRange(1, 50)
        dialog.spin_tcp_workers.setSingleStep(5)
        dialog.spin_tcp_workers.setValue(current_values['tcp_max_parallel_workers'])
        dialog.spin_tcp_workers.setToolTip(
            "Maximum number of concurrent connections\n"
            "Recommended: 15 (adjust based on network bandwidth)"
        )
        tcp_layout.addRow("Max Parallel Workers:", dialog.spin_tcp_workers)

        tcp_group.setLayout(tcp_layout)
        main_layout.addWidget(tcp_group)

        # === UI 설정 그룹 ===
        ui_group = QGroupBox("UI Settings")
        ui_layout = QFormLayout()

        # Progress Bar Update Percent
        dialog.spin_pgbar_percent = QSpinBox()
        dialog.spin_pgbar_percent.setRange(1, 100)
        dialog.spin_pgbar_percent.setSingleStep(5)
        dialog.spin_pgbar_percent.setSuffix(" %")
        dialog.spin_pgbar_percent.setValue(current_values['pgbar_update_percent'])
        dialog.spin_pgbar_percent.setToolTip(
            "Progress bar update percent\n"
            "Smaller = updates more often (smoother but slower)\n"
            "Larger = updates less often (faster but choppier)\n"
            "Recommended: 5~20%"
        )
        ui_layout.addRow("Progress Bar Update Interval:", dialog.spin_pgbar_percent)

        # Progress Bar Auto Hide Delay
        dialog.spin_pgbar_hide = QSpinBox()
        dialog.spin_pgbar_hide.setRange(0, 10000)
        dialog.spin_pgbar_hide.setSingleStep(500)
        dialog.spin_pgbar_hide.setSuffix(" ms")
        dialog.spin_pgbar_hide.setValue(current_values['pgbar_auto_hide_delay_ms'])
        dialog.spin_pgbar_hide.setToolTip(
            "Wait time before auto-hiding Progress bar after search completes\n"
            "0 = hide immediately"
        )
        ui_layout.addRow("Progress Bar Auto-Hide Delay:", dialog.spin_pgbar_hide)

        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)

        # === 버튼 박스 ===
        button_box = QDialogButtonBox()
        btn_save = button_box.addButton("Save", QDialogButtonBox.AcceptRole)
        btn_cancel = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        btn_reset = button_box.addButton("Restore Defaults", QDialogButtonBox.ResetRole)

        # 버튼 툴팁
        if btn_save is not None:
            btn_save.setToolTip("Save and apply settings")
        if btn_cancel is not None:
            btn_cancel.setToolTip("Discard changes and close")
        if btn_reset is not None:
            btn_reset.setToolTip("Restore all settings to defaults")

        # 시그널 연결
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        if btn_reset is not None:
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
            'phase3_set_command_delay_ms': dialog.spin_set_delay.value(),
            'phase3_set_response_timeout': dialog.spin_set_timeout.value(),
            'phase3_set_response_timeout_5xx': dialog.spin_set_timeout_5xx.value(),
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
            WIZMSGHandler.set_command_delay_ms = new_values['phase3_set_command_delay_ms']

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
            "Confirm Restore Defaults",
            "Restore all timing settings to defaults?\n\n"
            "This is saved immediately and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 1. DeviceSearchConfig 기본값 복원
                if not self.timing_config.reset_to_defaults():
                    QMessageBox.warning(
                        dialog,
                        "Restore Failed",
                        "Failed to restore defaults.\nPlease check the log."
                    )
                    return

                # 2. 다이얼로그 위젯 값 업데이트
                defaults = self.timing_config.get_current_values()
                dialog.spin_loop_timeout.setValue(defaults['phase1_loop_select_timeout'])
                dialog.spin_emit_delay.setValue(defaults['phase1_emit_stabilization_ms'])
                dialog.check_skip_delay.setChecked(defaults['skip_phase1_emit_delay'])
                dialog.spin_query_timeout.setValue(defaults['phase3_device_query_timeout'])
                dialog.spin_set_delay.setValue(defaults['phase3_set_command_delay_ms'])
                dialog.spin_set_timeout.setValue(defaults['phase3_set_response_timeout'])
                dialog.spin_set_timeout_5xx.setValue(defaults['phase3_set_response_timeout_5xx'])
                dialog.spin_tcp_workers.setValue(defaults['tcp_max_parallel_workers'])
                dialog.spin_pgbar_percent.setValue(defaults['pgbar_update_percent'])
                dialog.spin_pgbar_hide.setValue(defaults['pgbar_auto_hide_delay_ms'])

                # 3. WIZMSGHandler 클래스 변수 업데이트
                from WIZMSGHandler import WIZMSGHandler
                WIZMSGHandler.loop_select_timeout = defaults['phase1_loop_select_timeout']
                WIZMSGHandler.emit_stabilization_ms = defaults['phase1_emit_stabilization_ms']
                WIZMSGHandler.skip_phase1_emit_delay = defaults['skip_phase1_emit_delay']
                WIZMSGHandler.set_command_delay_ms = defaults['phase3_set_command_delay_ms']

                # 4. 인스턴스 변수 업데이트
                self.search_wait_time_each = defaults['phase3_device_query_timeout']

                QMessageBox.information(
                    dialog,
                    "Restore Complete",
                    "All settings have been restored to defaults."
                )

                self.logger.info("타이밍 설정 기본값 복원 완료")

            except Exception as e:
                self.logger.error(f"기본값 복원 실패: {e}")
                QMessageBox.critical(
                    dialog,
                    "Error",
                    f"An error occurred while restoring defaults:\n{e}"
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
                "Error",
                f"An error occurred while configuring advanced search options:\n{e}"
            )

    def _notify_config_resets(self):
        """검증으로 기준값 복구된 설정 항목을 GUI 표시 후 1회 통지한다 (P5)."""
        resets = getattr(self.timing_config, 'last_resets', None)
        if not resets:
            return
        lines = "\n".join(f"  - {k}: {bad} -> {good}" for k, bad, good in resets)
        QMessageBox.warning(
            self,
            "설정값 자동 복구",
            "일부 검색 설정값이 허용 범위를 벗어나 기준값으로 복구되었습니다:\n\n"
            f"{lines}\n\n원본은 .invalid.bak 으로 백업되었습니다.",
        )

    def _poll_config_file(self):
        """QFileSystemWatcher 미감지 보완용 2초 폴링"""
        path = str(self.timing_config.config_file_path)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        if mtime != self._config_poll_mtime:
            self._config_poll_mtime = mtime
            self._on_config_file_changed(path)

    def _sync_log_level_menu(self, level_str: str):
        """Log Level 메뉴 체크 상태를 현재 레벨에 맞게 동기화"""
        for lvl, act in self._log_level_actions.items():
            act.setChecked(lvl == level_str.upper())

    def _on_log_level_menu(self, action: QAction):
        """Log Level 메뉴 선택 → 즉시 반영 + YAML 저장"""
        import yaml
        level_str = action.text().upper()
        level = getattr(logging, level_str, logging.INFO)
        self.logger.setLevel(level)
        self.logger.info(f"[Config] Log level: {level_str}")
        self._sync_log_level_menu(level_str)
        path = str(self.timing_config.config_file_path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            data.setdefault('logging', {})['level'] = level_str
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            self.logger.warning(f"[Config] YAML 저장 실패: {e}")

    def _on_config_file_changed(self, path: str):
        """config 파일 변경 감지 → 로그 레벨 즉시 반영"""
        import yaml
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            level_str = data.get('logging', {}).get('level', 'INFO').upper()
            level = getattr(__import__('logging'), level_str, __import__('logging').INFO)
            self.logger.setLevel(level)
            self.logger.info(f"[Config] 로그 레벨 변경: {level_str}")
            self._sync_log_level_menu(level_str)
        except Exception as e:
            self.logger.warning(f"[Config] 로그 레벨 변경 실패: {e}")
        # 일부 에디터는 파일을 삭제 후 재생성 → watcher에서 제거됨, 재등록
        if path not in self._config_watcher.files():
            self._config_watcher.addPath(path)

    def _get_current_search_config(self):
        """현재 검색 설정 읽기 (DeviceSearchConfig + 내부 변수)"""
        if not hasattr(self, 'device_search_config'):
            self.device_search_config = DeviceSearchConfig()
            # 앱 시작 시 config 파일의 delay 값을 상수에 반영
            saved_delay = self.device_search_config.config.get('search', {}).get('retry', {}).get('delay_between_retries_ms', 100)
            RetrySearchLimits.RETRY_DELAY_MS = int(saved_delay)

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
        search_group = QGroupBox("Search Options")  # 검색 옵션
        search_layout = QFormLayout()

        # 예상 장비 수
        dialog.spin_expected_device_count = QSpinBox()
        dialog.spin_expected_device_count.setRange(0, 1000)
        dialog.spin_expected_device_count.setSingleStep(1)
        dialog.spin_expected_device_count.setValue(config.get('expected_device_count', 0))
        dialog.spin_expected_device_count.setToolTip(
            "Expected number of devices to find (0 = unlimited)\n"  # 검색 시 예상되는 장비 수 (0 = 무제한)
            "Search stops early when this count is reached"          # 이 수에 도달하면 검색 조기 종료
        )
        search_layout.addRow("Expected Device Count:", dialog.spin_expected_device_count)  # 예상 장비 수

        # 최대 반복 횟수
        dialog.spin_max_retry_count = QSpinBox()
        dialog.spin_max_retry_count.setRange(1, 100)
        dialog.spin_max_retry_count.setSingleStep(1)
        dialog.spin_max_retry_count.setValue(config.get('max_retry_count', 3))
        dialog.spin_max_retry_count.setToolTip(
            "Maximum number of search retries\n"             # 검색 반복 최대 횟수
            "Recommended: 3 (normal), 1 (fast search)"       # 권장: 일반 3회, 빠른 검색 1회
        )
        search_layout.addRow("Max Retry Count:", dialog.spin_max_retry_count)  # 최대 반복 횟수

        # 반복 간 딜레이
        dialog.spin_retry_delay_ms = QSpinBox()
        dialog.spin_retry_delay_ms.setRange(0, 5000)
        dialog.spin_retry_delay_ms.setSingleStep(50)
        dialog.spin_retry_delay_ms.setSuffix(" ms")
        dialog.spin_retry_delay_ms.setValue(config.get('delay_between_retries_ms', 100))
        dialog.spin_retry_delay_ms.setToolTip(
            "Delay between consecutive search retries\n"      # 반복 검색 간 딜레이
            "Recommended: 100ms (default)"                    # 권장: 100ms (기본값)
        )
        search_layout.addRow("Retry Interval Delay:", dialog.spin_retry_delay_ms)  # 반복 간 딜레이

        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)

        # === Phase 1 타이밍 그룹 ===
        phase1_group = QGroupBox("Broadcast Search Timing (Phase 1)")  # Phase 1 타이밍 (UDP Broadcast / TCP Multicast)
        phase1_layout = QFormLayout()

        # Broadcast Timeout (장비 못 찾을 때 딜레이의 핵심 파라미터)
        dialog.dspin_broadcast_timeout = QDoubleSpinBox()
        dialog.dspin_broadcast_timeout.setRange(0.5, 10.0)
        dialog.dspin_broadcast_timeout.setSingleStep(0.5)
        dialog.dspin_broadcast_timeout.setDecimals(1)
        dialog.dspin_broadcast_timeout.setSuffix(" sec")  # 초
        dialog.dspin_broadcast_timeout.setValue(config.get('phase1_broadcast_timeout', 3.0))
        dialog.dspin_broadcast_timeout.setToolTip(
            "Wait time for UDP broadcast responses (per search attempt)\n"  # UDP Broadcast 응답 대기 시간 (1회 검색당 대기)
            "Total wait when no device found = retry count × this value\n"  # 장비 못 찾을 때: 반복횟수 × 이 값 = 총 대기 시간
            "Recommended: 3.0s (normal), 2.0s (fast network), 5.0s (slow network)"  # 권장: 일반 3.0초, 빠른 네트워크 2.0초, 느린 네트워크 5.0초
        )
        phase1_layout.addRow("Broadcast Timeout:", dialog.dspin_broadcast_timeout)

        # Loop Select Timeout
        dialog.dspin_loop_select_timeout = QDoubleSpinBox()
        dialog.dspin_loop_select_timeout.setRange(0.1, 10.0)
        dialog.dspin_loop_select_timeout.setSingleStep(0.1)
        dialog.dspin_loop_select_timeout.setDecimals(1)
        dialog.dspin_loop_select_timeout.setSuffix(" sec")  # 초
        dialog.dspin_loop_select_timeout.setValue(config.get('phase1_loop_select_timeout', 0.5))
        dialog.dspin_loop_select_timeout.setToolTip(
            "Additional wait time after the last device response\n"  # 마지막 응답 이후 추가 응답 대기 시간
            "Recommended: 0.5s (normal), 1.0s (legacy devices), 0.3s (fast)"  # 권장: 일반 0.5초, 구형 장비 1.0초, 고속 0.3초
        )
        phase1_layout.addRow("Loop Select Timeout:", dialog.dspin_loop_select_timeout)

        # Emit 안정화 딜레이
        dialog.spin_emit_delay = QSpinBox()
        dialog.spin_emit_delay.setRange(0, 1000)
        dialog.spin_emit_delay.setSingleStep(10)
        dialog.spin_emit_delay.setSuffix(" ms")
        dialog.spin_emit_delay.setValue(config.get('phase1_emit_stabilization_ms', 50))
        dialog.spin_emit_delay.setToolTip(
            "PyQt signal queue stabilization wait time\n"  # PyQt signal queue 안정화 대기 시간
            "Recommended: 50ms (experimental: 0~100ms)"   # 권장: 50ms (실험적: 0~100ms)
        )
        phase1_layout.addRow("Signal Stabilization Delay:", dialog.spin_emit_delay)  # Emit 안정화 딜레이

        # Emit 딜레이 건너뛰기 (실험적)
        dialog.cb_skip_emit_delay = QCheckBox()
        dialog.cb_skip_emit_delay.setChecked(config.get('skip_phase1_emit_delay', False))
        dialog.cb_skip_emit_delay.setToolTip(
            "⚠ Experimental: Skip the signal stabilization delay\n"  # 실험적 기능: Emit 전 딜레이 생략
            "Saves ~50ms but may cause signal queue instability"      # 활성화 시 약 50ms 단축되지만 signal queue 불안정 가능성
        )
        phase1_layout.addRow("Skip Signal Delay (Experimental):", dialog.cb_skip_emit_delay)  # Emit 딜레이 건너뛰기 (실험적)

        phase1_group.setLayout(phase1_layout)
        main_layout.addWidget(phase1_group)

        # === Phase 3 타이밍 그룹 ===
        phase3_group = QGroupBox("Device Query Timing (Phase 3)")  # Phase 3 타이밍 (장비 정보 조회)
        phase3_layout = QFormLayout()

        # 장비 쿼리 타임아웃
        dialog.dspin_device_query_timeout = QDoubleSpinBox()
        dialog.dspin_device_query_timeout.setRange(0.5, 10.0)
        dialog.dspin_device_query_timeout.setSingleStep(0.1)
        dialog.dspin_device_query_timeout.setDecimals(1)
        dialog.dspin_device_query_timeout.setSuffix(" sec")  # 초
        dialog.dspin_device_query_timeout.setValue(config.get('phase3_device_query_timeout', 1.5))
        dialog.dspin_device_query_timeout.setToolTip(
            "Timeout for querying individual device information\n"  # 개별 장비 정보 조회 타임아웃
            "Recommended: 1.5s (normal), 2.0s (legacy devices), 1.0s (fast)"  # 권장: 일반 1.5초, 구형 장비 2.0초, 고속 1.0초
        )
        phase3_layout.addRow("Device Query Timeout:", dialog.dspin_device_query_timeout)  # 장비 쿼리 타임아웃

        phase3_group.setLayout(phase3_layout)
        main_layout.addWidget(phase3_group)

        # === TCP 설정 그룹 ===
        tcp_group = QGroupBox("TCP Settings")  # TCP 설정
        tcp_layout = QFormLayout()

        # 최대 병렬 워커 수
        dialog.spin_tcp_max_workers = QSpinBox()
        dialog.spin_tcp_max_workers.setRange(1, 50)
        dialog.spin_tcp_max_workers.setSingleStep(1)
        dialog.spin_tcp_max_workers.setValue(config.get('tcp_max_parallel_workers', 15))
        dialog.spin_tcp_max_workers.setToolTip(
            "Max parallel connections for TCP Multicast scan\n"  # TCP Multicast 검색 시 최대 병렬 연결 수
            "Recommended: 15 (normal), 5 (low-end PC), 30 (high-end PC)"  # 권장: 일반 15, 저성능 PC 5, 고성능 PC 30
        )
        tcp_layout.addRow("Max Parallel Workers:", dialog.spin_tcp_max_workers)  # 최대 병렬 워커 수

        tcp_group.setLayout(tcp_layout)
        main_layout.addWidget(tcp_group)

        # === UI 설정 그룹 ===
        ui_group = QGroupBox("UI Settings")  # UI 설정
        ui_layout = QFormLayout()

        # Progress Bar 갱신 주기
        dialog.spin_pgbar_update_step = QSpinBox()
        dialog.spin_pgbar_update_step.setRange(1, 50)
        dialog.spin_pgbar_update_step.setSingleStep(1)
        dialog.spin_pgbar_update_step.setSuffix(" %")
        dialog.spin_pgbar_update_step.setValue(config.get('pgbar_update_percent', 10))
        dialog.spin_pgbar_update_step.setToolTip(
            "Progress bar update interval (%)\n"       # 진행바 업데이트 주기 (%)
            "Smaller value = smoother but higher CPU"  # 값이 작을수록 부드럽지만 CPU 사용 증가
        )
        ui_layout.addRow("Progress Bar Update Step:", dialog.spin_pgbar_update_step)  # Progress Bar 갱신 주기

        # Progress Bar 자동 숨김 딜레이
        dialog.spin_pgbar_auto_hide_delay = QSpinBox()
        dialog.spin_pgbar_auto_hide_delay.setRange(500, 10000)
        dialog.spin_pgbar_auto_hide_delay.setSingleStep(100)
        dialog.spin_pgbar_auto_hide_delay.setSuffix(" ms")
        dialog.spin_pgbar_auto_hide_delay.setValue(config.get('pgbar_auto_hide_delay_ms', 1000))
        dialog.spin_pgbar_auto_hide_delay.setToolTip(
            "Delay before progress bar auto-hides after search completes\n"  # 검색 완료 후 진행바 자동 숨김 시간
            "Recommended: 1000ms (1 second)"                                 # 권장: 1000ms (1초)
        )
        ui_layout.addRow("Progress Bar Auto-hide Delay:", dialog.spin_pgbar_auto_hide_delay)  # Progress Bar 자동 숨김

        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)

        # === 디버그 설정 ===
        debug_group = QGroupBox("Debug / Experimental")  # 디버그 / 실험적 기능
        debug_layout = QFormLayout()

        dialog.cb_show_timing = QCheckBox("Show search duration in status bar")  # System 소요 시간 표시
        dialog.cb_show_timing.setChecked(config.get('show_timing_in_statusbar', False))
        dialog.cb_show_timing.setToolTip(
            "Show elapsed time in the status bar after search completes\n"  # 검색 완료 시 상태바에 System 소요 시간 표시
            "Debug option for performance measurement (default: off)"       # 성능 측정용 디버그 옵션 (기본값: 꺼짐)
        )
        debug_layout.addRow("Show Elapsed Time:", dialog.cb_show_timing)  # 타이밍 표시

        dialog.cb_phase3_on_demand = QCheckBox("Query device info on click (on-demand)")  # 장비 클릭 시 정보 조회 (온디맨드)
        dialog.cb_phase3_on_demand.setChecked(config.get('phase3_on_demand', False))
        dialog.cb_phase3_on_demand.setToolTip(
            "Fetch device details only when a device is clicked.\n"     # 검색 후 장비를 클릭할 때 해당 장비 정보를 조회합니다.
            "Faster search completion, but first click takes 1~2s.\n"   # 검색 완료가 빠르지만 첫 클릭 시 약 1~2초 대기가 발생합니다.
            "(Experimental, default: off)"                               # (실험적 기능, 기본값: 꺼짐)
        )
        debug_layout.addRow("On-demand Query:", dialog.cb_phase3_on_demand)  # 온디맨드 조회

        debug_group.setLayout(debug_layout)
        main_layout.addWidget(debug_group)

        # === 버튼 영역 ===
        button_layout = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_layout.accepted.connect(dialog.accept)
        button_layout.rejected.connect(dialog.reject)

        # 기본값 복원 버튼 추가
        reset_button = QPushButton("Restore Defaults")  # 기본값 복원
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
            'delay_between_retries_ms': dialog.spin_retry_delay_ms.value(),

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

            # 디버그 / 실험적
            'show_timing_in_statusbar': dialog.cb_show_timing.isChecked(),
            'phase3_on_demand': dialog.cb_phase3_on_demand.isChecked(),
        }

    def _apply_advanced_search_settings(self, updates):
        """Advanced Search Options 설정 적용"""
        try:
            # 내부 변수 업데이트
            self.retry_search_expected_count = updates['expected_device_count']
            self.retry_search_max_count = updates['max_retry_count']
            if 'delay_between_retries_ms' in updates:
                RetrySearchLimits.RETRY_DELAY_MS = int(updates['delay_between_retries_ms'])

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

            # timing_config 인메모리 동기화 (즉시 적용)
            self.timing_config.config.setdefault('logging', {})['show_timing_in_statusbar'] = updates.get('show_timing_in_statusbar', False)
            self.timing_config.config.setdefault('experimental', {})['phase3_on_demand'] = updates.get('phase3_on_demand', False)
            if 'pgbar_auto_hide_delay_ms' in updates:
                self.timing_config.config.setdefault('ui', {}).setdefault('progress_bar', {})['auto_hide_delay_ms'] = int(updates['pgbar_auto_hide_delay_ms'])

            self.logger.info(f"Advanced search options applied: {updates}")
            QtWidgets.QMessageBox.information(
                self,
                "Settings Saved",  # 설정 저장
                "Advanced search options have been saved.\n\n"  # 고급 검색 옵션이 저장되었습니다.
                "Some settings will take effect from the next search."  # 일부 설정은 다음 검색부터 적용됩니다.
            )

        except Exception as e:
            self.logger.error(f"Failed to apply advanced search options: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings:\n{e}"
            )

    def _reset_advanced_dialog_to_defaults(self, dialog):
        """Advanced Search Options 다이얼로그 기본값 복원"""
        reply = QtWidgets.QMessageBox.question(
            dialog,
            "Confirm Restore Defaults",
            "Restore all advanced search options to defaults?\n\n"
            "This is saved immediately and cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # DeviceSearchConfig 기본값 복원
                if not self.device_search_config.reset_to_defaults():
                    QtWidgets.QMessageBox.warning(
                        dialog,
                        "Restore Failed",
                        "Failed to restore defaults.\nPlease check the log."
                    )
                    return

                # 다이얼로그 위젯 값 업데이트
                from device_search_config import DeviceSearchConfig
                defaults = DeviceSearchConfig.get_defaults()

                # 검색 옵션 기본값
                dialog.spin_expected_device_count.setValue(0)
                dialog.spin_max_retry_count.setValue(3)
                dialog.spin_retry_delay_ms.setValue(defaults['retry']['delay_between_retries_ms'])
                RetrySearchLimits.RETRY_DELAY_MS = defaults['retry']['delay_between_retries_ms']

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

                # 디버그 / 실험적 기본값
                dialog.cb_show_timing.setChecked(False)
                dialog.cb_phase3_on_demand.setChecked(False)

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

                # timing_config 인메모리 동기화
                self.timing_config.config.setdefault('logging', {})['show_timing_in_statusbar'] = False
                self.timing_config.config.setdefault('experimental', {})['phase3_on_demand'] = False

                QtWidgets.QMessageBox.information(
                    dialog,
                    "Restore Complete",
                    "All settings have been restored to defaults."
                )

                self.logger.info("Advanced search options 기본값 복원 완료")

            except Exception as e:
                self.logger.error(f"기본값 복원 실패: {e}")
                QtWidgets.QMessageBox.critical(
                    dialog,
                    "Error",
                    f"An error occurred while restoring defaults:\n{e}"
                )

    # ========== CSV 저장/불러오기 ==========

    @staticmethod
    def _csv_safe(value: str) -> str:
        s = str(value).strip()
        if s and s[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
            return "'" + s
        return s

    def save_searched_results_to_csv(self):
        """검색 결과를 CSV 파일로 저장"""
        # 검색 결과 확인
        if not hasattr(self, 'mac_list') or not self.mac_list:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Failed",
                "No searched devices found."
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
            "Save Search Results",
            default_path,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 헤더 (Phase 1 모든 정보 포함)
                # Protocol: dev_profile['_proto'] 영속화 (wiz550/wiz1x0, ASCII는 빈칸).
                # 로드 시 이 값으로 _proto를 복원해 바이너리 장치 판정이 유지된다
                # (issue #67 — 없으면 _is_binary_proto_dev의 MN 폴백이 커버)
                writer.writerow([
                    'Mac Address', 'Device Name', 'Firmware Version', 'Status', 'Operation Mode', 'Detected',
                    'IP Address', 'Subnet Mask', 'Gateway', 'DNS', 'IP Mode', 'Local Port', 'Protocol'
                ])

                # 데이터
                for i in range(len(self.mac_list)):
                    mac = self.mac_list[i].decode('utf-8') if isinstance(self.mac_list[i], bytes) else self.mac_list[i]
                    name = self.mn_list[i]
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
                    proto = profile.get('_proto', '')

                    writer.writerow([self._csv_safe(x) for x in [
                        mac, name, version, status, op_mode, detected,
                        ip_addr, subnet, gateway, dns, ip_mode, local_port, proto
                    ]])

            # 저장 성공 시 MRU 업데이트 (Save: 초기화)
            self.csv_mru_manager.add_saved_file(file_path, memo="")
            self.last_csv_directory = os.path.dirname(file_path)
            self.csv_mru_manager.set_last_directory(self.last_csv_directory)  # config 파일에 저장
            self.logger.info(f"Saved {len(self.mac_list)} devices to {file_path}")
            QtWidgets.QMessageBox.information(
                self,
                "Saved",
                f"{len(self.mac_list)} device(s) saved."
            )
        except Exception as e:
            self.logger.error(f"Failed to save CSV: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save CSV:\n{e}"
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
            "Load Search Results",
            default_path,
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        # 기존 결과 확인
        if hasattr(self, 'mac_list') and self.mac_list:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm",
                "Overwrite existing search results?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # 헤더 검증 (기본 필드만 필수, Operation Mode와 네트워크 정보는 선택)
                required_headers = {'Mac Address', 'Device Name', 'Firmware Version', 'Status', 'Detected'}
                if not required_headers.issubset(set(reader.fieldnames or [])):
                    raise ValueError(f"Missing CSV headers: {required_headers - set(reader.fieldnames or [])}")

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
                    mn_list.append(row['Device Name'])
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
                        'local_port': row.get('Local Port', ''),
                        # Protocol 컬럼(선택): _proto 복원용. 구버전 CSV엔 없음 → 빈값
                        # (그 경우 _is_binary_proto_dev의 MN 폴백이 판정을 커버)
                        'proto': row.get('Protocol', ''),
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
                    name_str = self.mn_list[i]
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
                    # Protocol 컬럼이 있던 CSV면 _proto 복원 (바이너리 장치 판정 유지)
                    if net_info['proto']:
                        self.dev_profile[mac_str]['_proto'] = net_info['proto']

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
                "Error",
                f"Failed to load CSV:\n{e}"
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
        # self.logger.info("[TIMING] System timer started (CSV Load → Phase 2)")

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
                self.mn_list[i]
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

    # ── 터미널 패널 ─────────────────────────────────────────────

    def _toggle_terminal(self, checked: bool):
        for ctrl in (self._btn_terminal, self._action_terminal):
            ctrl.blockSignals(True)
            ctrl.setChecked(checked)
            ctrl.blockSignals(False)
        if checked:
            self._terminal_panel.snap_to()
            self._terminal_panel.show()
        else:
            self._terminal_panel.hide()
            self._center_main_window()

    def _on_terminal_panel_hidden(self):
        self._toggle_terminal(False)

    def _center_main_window(self):
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        avail = screen.availableGeometry()
        geo = self.frameGeometry()
        self.move(
            avail.x() + max(0, (avail.width() - geo.width()) // 2),
            avail.y() + max(0, (avail.height() - geo.height()) // 2),
        )

    def moveEvent(self, event):
        super().moveEvent(event)
        self._terminal_panel.follow_main()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._terminal_panel.follow_main()

    def _device_list_context_menu(self, pos):
        items = self.list_device.selectedItems()
        if not items:
            return
        menu = QMenu(self)
        act_terminal = menu.addAction('🖥 Open in Terminal')
        action = menu.exec_(self.list_device.viewport().mapToGlobal(pos))
        if action == act_terminal:
            self._open_device_in_terminal()

    def _open_device_in_terminal(self):
        mac_item = next(
            (item for item in self.list_device.selectedItems() if item.column() == 0),
            None,
        )
        if not mac_item:
            return
        mac = mac_item.text()
        profile = self.dev_profile.get(mac, {})
        if not profile:
            return
        device_info = self._get_device_info_for_terminal(profile)
        active = [t for t in (
            self._terminal_panel.tab_udp,
            self._terminal_panel.tab_tcpc,
            self._terminal_panel.tab_tcps,
            self._terminal_panel.tab_serial,
        ) if t._connected]
        if active:
            QMessageBox.information(
                self, 'Terminal',
                'A tab is currently connected; auto-fill is skipped.\n'
                'Please disconnect and try again.',
            )
        else:
            self._terminal_panel.fill_from_device(device_info)
        self._terminal_panel.show()
        self._btn_terminal.setChecked(True)

    def _get_device_info_for_terminal(self, profile: dict) -> dict:
        """dev_profile 항목 → terminal fill_from_device() 용 dict 변환."""
        PARITY_IDX = {0: 'None', 1: 'Odd', 2: 'Even'}
        STOPBITS_IDX = {0: '1', 1: '2'}
        OP_MODE_MAP = {
            '0': 'TCP Client',
            '1': 'TCP Server',
            '2': 'TCP Client',   # Mixed → Client 로 처리
            '3': 'UDP',
        }

        if profile.get('_proto') == 'wiz1x0':
            udp_on = bool(profile.get('udp', 0))
            bserver = profile.get('bserver', 0)
            if udp_on:
                op_mode = 'UDP'
            elif bserver == 2:
                op_mode = 'TCP Server'
            else:
                op_mode = 'TCP Client'
            return {
                'ip':       profile.get('ip', ''),
                'port':     profile.get('myport', 5000),
                'op_mode':  op_mode,
                'baudrate': profile.get('speed_bps', 9600),
                'databits': profile.get('databit', 8),
                'parity':   profile.get('parity_str', 'None'),
                'stopbits': '1',
            }

        op_str = profile.get('OP', '1')
        op_mode = OP_MODE_MAP.get(op_str, 'TCP Server')

        br_idx = int(profile.get('BR', 6))
        baudrate_str = BAUDRATE_BASE[br_idx] if br_idx < len(BAUDRATE_BASE) else '9600'

        db_idx = int(profile.get('DB', 1) if profile.get('DB', '1') else 1)
        databits = 7 if db_idx == 0 else 8

        pr_idx = int(profile.get('PR', 0) if profile.get('PR', '0') else 0)
        parity = PARITY_IDX.get(pr_idx, 'None')

        sb_idx = int(profile.get('SB', 0) if profile.get('SB', '0') else 0)
        stopbits = STOPBITS_IDX.get(sb_idx, '1')

        return {
            'ip':       profile.get('LI', ''),
            'port':     int(profile.get('LP', 5000) or 5000),
            'op_mode':  op_mode,
            'baudrate': int(baudrate_str),
            'databits': databits,
            'parity':   parity,
            'stopbits': stopbits,
        }


class VersionCheckThread(QtCore.QThread):
    finished = QtCore.pyqtSignal(str)

    def run(self):
        try:
            latest = get_latest_release_version("Wiznet", "WIZnet-S2E-Tool-GUI")
            self.finished.emit(latest or "")
        except Exception:
            self.finished.emit("")


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
        self.wait()


if __name__ == "__main__":
    # High DPI mode
    # PyQt5 High DPI (일부 환경에서 속성 없을 수 있음)
    logger.debug(f"sys.platform={sys.platform}")
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore[attr-defined]
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore[attr-defined]

    app = QApplication(sys.argv)
    wizwindow = WIZWindow()
    wizwindow.show()
    app.exec_()
