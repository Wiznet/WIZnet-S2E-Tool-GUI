"""
terminal/terminal_panel.py
메인 창 오른쪽에 자석처럼 붙는 독립 터미널 창.
- Qt.Tool: 부모 창 위에 뜨지만 Alt+Tab 항목은 하나로 통합
- snap_to(): 메인 창 오른쪽에 딱 붙이기
- follow_main(): 메인 창 이동·리사이즈 시 함께 이동
- moveEvent: 사용자가 직접 드래그해서 threshold 벗어나면 자동 분리
- 📌 버튼으로 언제든 다시 붙이기 가능
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from .macro_panel import MacroPanel
from .protocol_tabs import (
    LINE_ENDINGS, SerialTab, TCPClientTab, TCPServerTab, UDPTab,
)
from .terminal_settings import TerminalSettings


class TerminalPanel(QWidget):
    """
    메인 창(main_window) 오른쪽에 붙는 독립 터미널 창.
    main_gui.py에서 TerminalPanel(self) 로 생성 후
    snap_to() 로 붙이고, moveEvent/resizeEvent에서 follow_main() 호출.
    """

    panel_hidden = pyqtSignal()   # 닫기·숨기기 시 발생 → 툴바 버튼 동기화

    TAB_UDP    = 0
    TAB_TCPC   = 1
    TAB_TCPS   = 2
    TAB_SERIAL = 3

    _SNAP_THRESHOLD = 40   # 이 픽셀 이상 이동하면 분리 판정

    def __init__(self, main_window):
        # Qt.Tool: 부모 창 위에 표시, 태스크바/Alt+Tab 은 부모와 통합
        super().__init__(main_window, Qt.Tool)
        self.setWindowTitle('터미널')
        self.setMinimumWidth(400)
        self._main = main_window
        self._snapped = False
        self._following = False   # 프로그램 이동 중 플래그 (분리 오판 방지)
        self._settings = TerminalSettings()
        self._build_ui()
        self._connect_signals()
        self._restore_state()

    # ── 붙이기 / 따라가기 ──────────────────────────────────────

    def snap_to(self):
        """메인 창 오른쪽에 딱 붙이기."""
        geo = self._main.frameGeometry()
        self._following = True
        self.move(geo.right() + 2, geo.top())
        self.resize(480, geo.height())
        self._following = False
        self._snapped = True

    def follow_main(self):
        """메인 창 이동·리사이즈 후 호출 — snapped 상태일 때만 따라 이동."""
        if self._snapped and self.isVisible():
            geo = self._main.frameGeometry()
            self._following = True
            self.move(geo.right() + 2, geo.top())
            self.resize(self.width(), geo.height())
            self._following = False

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._snapped and not self._following:
            geo = self._main.frameGeometry()
            dx = abs(self.x() - (geo.right() + 2))
            dy = abs(self.y() - geo.top())
            if dx > self._SNAP_THRESHOLD or dy > self._SNAP_THRESHOLD:
                self._snapped = False

    def hideEvent(self, event):
        super().hideEvent(event)
        self.panel_hidden.emit()

    def closeEvent(self, event):
        self.save_state()
        for tab in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial):
            tab.stop()
        event.accept()

    # ── UI 구성 ────────────────────────────────────────────────

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(2)

        vbox.addWidget(self._make_toolbar())

        splitter = QSplitter(Qt.Horizontal)

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

        hbox.addWidget(QLabel('줄 끝(전역):'))
        self.cmb_global_le = QComboBox()
        self.cmb_global_le.addItem('(개별 설정)')
        self.cmb_global_le.addItems(LINE_ENDINGS)
        self.cmb_global_le.setFixedWidth(100)
        self.cmb_global_le.currentTextChanged.connect(self._on_global_le_changed)
        hbox.addWidget(self.cmb_global_le)

        hbox.addStretch()

        btn_exp = QPushButton('Export All')
        btn_exp.setFixedHeight(22)
        btn_exp.clicked.connect(self._export_all)
        hbox.addWidget(btn_exp)

        btn_imp = QPushButton('Import All')
        btn_imp.setFixedHeight(22)
        btn_imp.clicked.connect(self._import_all)
        hbox.addWidget(btn_imp)

        # 붙이기 (분리 상태에서 다시 메인 창에 붙이기)
        btn_snap = QPushButton('📌')
        btn_snap.setFixedWidth(28)
        btn_snap.setToolTip('메인 창에 붙이기')
        btn_snap.clicked.connect(self.snap_to)
        hbox.addWidget(btn_snap)

        btn_close = QPushButton('✕')
        btn_close.setFixedWidth(24)
        btn_close.setToolTip('터미널 닫기')
        btn_close.clicked.connect(self.hide)
        hbox.addWidget(btn_close)

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

        self.macro_panel.send_requested.connect(self._dispatch_send)

        self.tab_tcpc.connection_state_changed.connect(self._enforce_tcp_exclusion)
        self.tab_tcps.connection_state_changed.connect(self._enforce_tcp_exclusion)

    def _on_connection_changed(self, tab_idx: int, name: str,
                               connected: bool, label: str):
        mark = f'● {name}' if connected else name
        self.tabs.setTabText(tab_idx, mark)

    def _dispatch_send(self, data: bytes):
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
        for tab in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial):
            tab.send_widget.set_line_ending(text)

    # ── 장치 자동 채우기 ─────────────────────────────────────────

    def fill_from_device(self, device_info: dict):
        active = [t for t in (self.tab_udp, self.tab_tcpc, self.tab_tcps, self.tab_serial)
                  if t._connected]
        if active:
            return

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

        mode_map = {
            'TCP Server': self.TAB_TCPC,
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
