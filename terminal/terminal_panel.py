"""
terminal/terminal_panel.py
QDockWidget 기반 터미널 패널.
- 4개 프로토콜 탭 + 매크로 패널
- 팝아웃(⧉) 버튼: setFloating(True)
- 다중 연결 규칙 강제 (TCP Client + TCP Server 동시 불가)
- 탭 ● 연결 상태 표시
- 장치 설정 자동 채우기 (fill_from_device)
- 전역 Line Ending 일괄 변경
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction, QComboBox, QDockWidget, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSplitter, QTabWidget, QToolBar,
    QVBoxLayout, QWidget,
)

from .macro_panel import MacroPanel
from .protocol_tabs import (
    LINE_ENDINGS, SerialTab, TCPClientTab, TCPServerTab, UDPTab,
)
from .terminal_settings import TerminalSettings


class TerminalPanel(QDockWidget):
    """
    메인 QDockWidget 컨테이너.
    main_gui.py에서 addDockWidget(Qt.RightDockWidgetArea, panel) 으로 붙인다.
    """

    TAB_UDP    = 0
    TAB_TCPC   = 1
    TAB_TCPS   = 2
    TAB_SERIAL = 3

    def __init__(self, parent=None):
        super().__init__('터미널', parent)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea |
                             Qt.BottomDockWidgetArea)
        self.setMinimumWidth(420)
        self._settings = TerminalSettings()
        self._build_ui()
        self._connect_signals()
        self._restore_state()

    # ── UI 구성 ────────────────────────────────────────────────

    def _build_ui(self):
        container = QWidget()
        self.setWidget(container)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)

        # 상단 툴바
        vbox.addWidget(self._make_toolbar())

        # 수평 Splitter: 탭 | 매크로 패널
        splitter = QSplitter(Qt.Horizontal)

        # 탭 위젯
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        self.tab_udp    = UDPTab()
        self.tab_tcpc   = TCPClientTab()
        self.tab_tcps   = TCPServerTab()
        self.tab_serial = SerialTab()

        self.tabs.addTab(self.tab_udp,    'UDP')
        self.tabs.addTab(self.tab_tcpc,   'TCP Client')
        self.tabs.addTab(self.tab_tcps,   'TCP Server')
        self.tabs.addTab(self.tab_serial, 'Serial')

        splitter.addWidget(self.tabs)

        # 매크로 패널
        self.macro_panel = MacroPanel()
        self.macro_panel.setMinimumWidth(200)
        self.macro_panel.setMaximumWidth(300)
        splitter.addWidget(self.macro_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        vbox.addWidget(splitter)

    def _make_toolbar(self) -> QWidget:
        toolbar = QWidget()
        hbox = QHBoxLayout(toolbar)
        hbox.setContentsMargins(2, 0, 2, 0)
        hbox.setSpacing(4)

        hbox.addWidget(QLabel('터미널'))

        # 전역 Line Ending
        hbox.addWidget(QLabel('줄 끝(전역):'))
        self.cmb_global_le = QComboBox()
        self.cmb_global_le.addItem('(개별 설정)')
        self.cmb_global_le.addItems(LINE_ENDINGS)
        self.cmb_global_le.setFixedWidth(100)
        self.cmb_global_le.currentTextChanged.connect(self._on_global_le_changed)
        hbox.addWidget(self.cmb_global_le)

        hbox.addStretch()

        # Export All / Import All
        btn_exp = QPushButton('Export All')
        btn_exp.setFixedHeight(22)
        btn_exp.clicked.connect(self._export_all)
        hbox.addWidget(btn_exp)

        btn_imp = QPushButton('Import All')
        btn_imp.setFixedHeight(22)
        btn_imp.clicked.connect(self._import_all)
        hbox.addWidget(btn_imp)

        # 팝아웃
        btn_popout = QPushButton('⧉')
        btn_popout.setFixedWidth(24)
        btn_popout.setToolTip('독립 창으로 분리')
        btn_popout.clicked.connect(lambda: self.setFloating(True))
        hbox.addWidget(btn_popout)

        return toolbar

    # ── 시그널 연결 ─────────────────────────────────────────────

    def _connect_signals(self):
        tabs_info = [
            (self.TAB_UDP,    self.tab_udp,    'UDP'),
            (self.TAB_TCPC,   self.tab_tcpc,   'TCP Client'),
            (self.TAB_TCPS,   self.tab_tcps,   'TCP Server'),
            (self.TAB_SERIAL, self.tab_serial, 'Serial'),
        ]
        for idx, tab, name in tabs_info:
            tab.connection_state_changed.connect(
                lambda connected, label, i=idx, n=name:
                    self._on_connection_changed(i, n, connected, label)
            )

        # 매크로 → 현재 탭 전송
        self.macro_panel.send_requested.connect(self._dispatch_send)

        # TCP Client + TCP Server 동시 방지
        self.tab_tcpc.connection_state_changed.connect(self._enforce_tcp_exclusion)
        self.tab_tcps.connection_state_changed.connect(self._enforce_tcp_exclusion)

    def _on_connection_changed(self, tab_idx: int, name: str,
                               connected: bool, label: str):
        mark = f'● {name}' if connected else name
        self.tabs.setTabText(tab_idx, mark)

    def _dispatch_send(self, data: bytes):
        """매크로 전송 → 현재 활성 탭의 핸들러로."""
        idx = self.tabs.currentIndex()
        tab_map = {
            self.TAB_UDP:    self.tab_udp,
            self.TAB_TCPC:   self.tab_tcpc,
            self.TAB_TCPS:   self.tab_tcps,
            self.TAB_SERIAL: self.tab_serial,
        }
        tab = tab_map.get(idx)
        if tab and tab._handler:
            tab._handler.send(data)
            tab.display.append_tx(data)

    def _enforce_tcp_exclusion(self, connected: bool, _label: str):
        """TCP Client 와 TCP Server 는 동시에 연결 불가."""
        tcpc_on = self.tab_tcpc._connected
        tcps_on = self.tab_tcps._connected
        if tcpc_on and tcps_on:
            QMessageBox.warning(
                self, '연결 충돌',
                'TCP Client 와 TCP Server 는 동시에 연결할 수 없습니다.\n'
                '현재 연결된 TCP 탭을 먼저 해제하세요.'
            )

    # ── 전역 Line Ending ────────────────────────────────────────

    def _on_global_le_changed(self, text: str):
        if text == '(개별 설정)':
            return
        # 각 탭의 send widget 에 동일 적용
        for tab in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial):
            tab.send_widget.set_line_ending(text)

    # ── 장치 자동 채우기 ─────────────────────────────────────────

    def fill_from_device(self, device_info: dict):
        """
        Config Tool 에서 선택된 장치 정보로 탭 설정 자동 채움.
        device_info 예시:
          {
            'ip': '192.168.0.100',
            'port': 5000,
            'op_mode': 'TCP Server',   # or 'TCP Client', 'UDP'
            'baudrate': 115200, 'databits': 8, 'parity': 'None', 'stopbits': '1'
          }
        """
        # 진행 중인 연결이 있으면 채우지 않음
        active = [t for t in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial)
                  if t._connected]
        if active:
            return  # 경고는 호출 측(context menu)에서 처리

        ip   = device_info.get('ip', '')
        port = device_info.get('port', 5000)
        mode = device_info.get('op_mode', '')

        self.tab_udp.fill_from_device(ip=ip, port=port)
        self.tab_tcpc.fill_from_device(ip=ip, port=port)
        self.tab_tcps.fill_from_device(ip=ip, port=port)
        self.tab_serial.fill_from_device(
            baudrate=device_info.get('baudrate', 115200),
            databits=device_info.get('databits', 8),
            parity=device_info.get('parity', 'None'),
            stopbits=device_info.get('stopbits', '1'),
        )

        # 동작 모드에 따라 추천 탭 활성화
        mode_map = {
            'TCP Server': self.TAB_TCPC,   # 장치가 Server면 우리는 Client로 접속
            'TCP Client': self.TAB_TCPS,
            'UDP':        self.TAB_UDP,
        }
        if mode in mode_map:
            self.tabs.setCurrentIndex(mode_map[mode])

    # ── Export / Import All ─────────────────────────────────────

    def _export_all(self):
        import json
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, '전체 설정 내보내기', 'terminal_config.json', 'JSON (*.json)'
        )
        if not path:
            return
        data = {
            'macros': self.macro_panel.get_all_data(),
            'global_le': self.cmb_global_le.currentText(),
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(self, '내보내기 실패', str(e))

    def _import_all(self):
        import json
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, '전체 설정 가져오기', '', 'JSON (*.json)'
        )
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            if 'macros' in data:
                self.macro_panel.set_all_data(data['macros'])
            if 'global_le' in data:
                idx = self.cmb_global_le.findText(data['global_le'])
                if idx >= 0:
                    self.cmb_global_le.setCurrentIndex(idx)
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, '가져오기 실패', str(e))

    # ── 상태 저장/복원 ───────────────────────────────────────────

    def _restore_state(self):
        macros = self._settings.load_macros()
        if macros:
            self.macro_panel.set_all_data(macros)

    def save_state(self):
        self._settings.save_macros(self.macro_panel.get_all_data())

    def closeEvent(self, event):
        self.save_state()
        # 모든 핸들러 정리
        for tab in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial):
            tab.stop()
        super().closeEvent(event)
