"""
terminal/protocol_tabs.py
4개 프로토콜 탭 위젯: UDP / TCP Client / TCP Server / Serial.
각 탭은 연결 설정 + ReceiveDisplay + 송신 영역 으로 구성된다.
"""

from collections import deque

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QShortcut,
    QSizePolicy, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from .comm_handlers import (
    SerialHandler, TCPClientHandler, TCPServerHandler, UDPHandler,
    _encode_escape, list_serial_ports,
)
from .receive_display import ReceiveDisplay

LINE_ENDINGS = ['None', '\\r', '\\n', '\\r\\n']
LINE_ENDING_BYTES = {
    'None': b'',
    '\\r':  b'\r',
    '\\n':  b'\n',
    '\\r\\n': b'\r\n',
}

HISTORY_MAX = 50
QUICK_CONN_MAX = 5


# ──────────────────────────────────────────────────────────────
# 공통 송신 위젯
# ──────────────────────────────────────────────────────────────

class SendWidget(QWidget):
    """
    송신 입력창 + Escape 토글 + Line Ending + 주기 전송 + 히스토리.
    send_data(bytes) 시그널로 상위에 전달.
    """
    send_data = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: deque = deque(maxlen=HISTORY_MAX)
        self._hist_idx = -1
        self._periodic_timer = QTimer(self)
        self._periodic_timer.timeout.connect(self._send_periodic)
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        # 입력창
        self.input = QTextEdit()
        self.input.setFixedHeight(56)
        self.input.setPlaceholderText('메시지 입력 — Ctrl+Enter: 전송, Ctrl+↑/↓: 히스토리')
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.input)

        # 옵션 행
        opts = QHBoxLayout()
        opts.setSpacing(6)

        self.chk_escape = QCheckBox('Escape 해석')
        self.chk_escape.setChecked(True)
        self.chk_escape.setToolTip(r'\\r\\n \\xHH 등을 실제 바이트로 변환')
        opts.addWidget(self.chk_escape)

        opts.addWidget(QLabel('줄 끝:'))
        self.cmb_le = QComboBox()
        self.cmb_le.addItems(LINE_ENDINGS)
        self.cmb_le.setCurrentText('\\r\\n')
        self.cmb_le.setFixedWidth(70)
        opts.addWidget(self.cmb_le)

        self.chk_periodic = QCheckBox('주기 전송')
        self.chk_periodic.toggled.connect(self._on_periodic_toggled)
        opts.addWidget(self.chk_periodic)

        self.spn_interval = QSpinBox()
        self.spn_interval.setRange(10, 60000)
        self.spn_interval.setValue(1000)
        self.spn_interval.setSuffix(' ms')
        self.spn_interval.setFixedWidth(80)
        self.spn_interval.setEnabled(False)
        opts.addWidget(self.spn_interval)

        opts.addStretch()

        self.btn_send = QPushButton('전송 [Ctrl+↵]')
        self.btn_send.setFixedWidth(100)
        self.btn_send.clicked.connect(self._send_once)
        opts.addWidget(self.btn_send)

        vbox.addLayout(opts)

        # 단축키
        QShortcut(QKeySequence('Ctrl+Return'), self, self._send_once)
        QShortcut(QKeySequence('Ctrl+Up'),   self, self._history_prev)
        QShortcut(QKeySequence('Ctrl+Down'), self, self._history_next)

    def _build_payload(self) -> bytes:
        text = self.input.toPlainText()
        if self.chk_escape.isChecked():
            data = _encode_escape(text)
        else:
            data = text.encode('utf-8', errors='replace')
        le = LINE_ENDING_BYTES.get(self.cmb_le.currentText(), b'')
        return data + le

    def _send_once(self):
        payload = self._build_payload()
        if payload:
            self._history.appendleft(self.input.toPlainText())
            self._hist_idx = -1
            self.send_data.emit(payload)

    def _send_periodic(self):
        payload = self._build_payload()
        if payload:
            self.send_data.emit(payload)

    def _on_periodic_toggled(self, checked: bool):
        self.spn_interval.setEnabled(checked)
        if checked:
            self._periodic_timer.start(self.spn_interval.value())
        else:
            self._periodic_timer.stop()
        self.spn_interval.valueChanged.connect(
            lambda v: self._periodic_timer.setInterval(v) if checked else None
        )

    def _history_prev(self):
        if not self._history:
            return
        self._hist_idx = min(self._hist_idx + 1, len(self._history) - 1)
        self.input.setPlainText(self._history[self._hist_idx])

    def _history_next(self):
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self.input.clear()
            return
        self._hist_idx -= 1
        self.input.setPlainText(self._history[self._hist_idx])

    def set_line_ending(self, le: str):
        if le in LINE_ENDINGS:
            self.cmb_le.setCurrentText(le)


# ──────────────────────────────────────────────────────────────
# 기본 탭 (공통 구조)
# ──────────────────────────────────────────────────────────────

class BaseProtocolTab(QWidget):
    connection_state_changed = pyqtSignal(bool, str)  # connected, label

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handler = None
        self._connected = False
        self._quick_history: deque = deque(maxlen=QUICK_CONN_MAX)
        self._build_base_ui()

    def _build_base_ui(self):
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(4, 4, 4, 4)
        self._vbox.setSpacing(4)

        # 연결 설정 그룹 (서브클래스가 채움)
        self._conn_group = QGroupBox('연결 설정')
        self._conn_form = QFormLayout(self._conn_group)
        self._vbox.addWidget(self._conn_group)

        # 수신 표시
        self.display = ReceiveDisplay()
        self._vbox.addWidget(self.display, stretch=1)

        # 송신
        self.send_widget = SendWidget()
        self.send_widget.send_data.connect(self._on_send)
        self._vbox.addWidget(self.send_widget)

    def _on_send(self, data: bytes):
        if self._handler:
            self._handler.send(data)
            self.display.append_tx(data)

    def _set_connected(self, label: str = ''):
        self._connected = True
        self.connection_state_changed.emit(True, label)

    def _set_disconnected(self, label: str = ''):
        self._connected = False
        self._handler = None
        self.connection_state_changed.emit(False, label)

    def stop(self):
        if self._handler:
            self._handler.stop()
            self._handler.wait(2000)
            self._handler = None


# ──────────────────────────────────────────────────────────────
# UDP 탭
# ──────────────────────────────────────────────────────────────

class UDPTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('UDP 설정')
        self._add_fields()
        self._add_conn_buttons()

    def _add_fields(self):
        self.inp_remote_ip = QLineEdit('192.168.0.100')
        self._conn_form.addRow('Remote IP:', self.inp_remote_ip)

        self.spn_remote_port = QSpinBox()
        self.spn_remote_port.setRange(1, 65535)
        self.spn_remote_port.setValue(5000)
        self._conn_form.addRow('Remote Port:', self.spn_remote_port)

        self.spn_local_port = QSpinBox()
        self.spn_local_port.setRange(0, 65535)
        self.spn_local_port.setValue(0)
        self.spn_local_port.setSpecialValueText('자동')
        self._conn_form.addRow('Local Port (수신):', self.spn_local_port)

    def _add_conn_buttons(self):
        row = QHBoxLayout()
        self.btn_conn = QPushButton('Bind & Open [Ctrl+K]')
        self.btn_conn.clicked.connect(self._toggle_connection)
        row.addWidget(self.btn_conn)
        self._conn_form.addRow('', row.parentWidget() if False else self.btn_conn)
        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_connection)

    def _toggle_connection(self):
        if self._connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        h = UDPHandler(
            self.inp_remote_ip.text().strip(),
            self.spn_remote_port.value(),
            self.spn_local_port.value(),
        )
        h.data_received.connect(
            lambda data, ip, port: self.display.append_rx(data)
        )
        h.error_occurred.connect(
            lambda e: self.display.append_event(f'오류: {e}')
        )
        h.status_changed.connect(self._on_status)
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        h.start()

    def _on_status(self, status: str):
        if status == 'bound':
            self.btn_conn.setText('Close [Ctrl+K]')
            lbl = f'{self.inp_remote_ip.text()}:{self.spn_remote_port.value()}'
            self.display.append_event(f'UDP Bound → {lbl}')
            self._set_connected(lbl)
        elif status in ('closed', 'error'):
            self.btn_conn.setText('Bind & Open [Ctrl+K]')
            self.display.append_event('UDP Closed')
            self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, ip: str, port: int, **_):
        self.inp_remote_ip.setText(ip)
        self.spn_remote_port.setValue(port)


# ──────────────────────────────────────────────────────────────
# TCP Client 탭
# ──────────────────────────────────────────────────────────────

class TCPClientTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('TCP Client 설정')
        self._add_fields()
        self._add_conn_buttons()

    def _add_fields(self):
        self.inp_ip = QLineEdit('192.168.0.100')
        self._conn_form.addRow('Remote IP:', self.inp_ip)

        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(5000)
        self._conn_form.addRow('Remote Port:', self.spn_port)

        reconnect_row = QHBoxLayout()
        self.chk_reconnect = QCheckBox('자동 재연결')
        self.spn_reconnect = QSpinBox()
        self.spn_reconnect.setRange(1, 60)
        self.spn_reconnect.setValue(5)
        self.spn_reconnect.setSuffix(' 초')
        self.spn_reconnect.setEnabled(False)
        self.chk_reconnect.toggled.connect(self.spn_reconnect.setEnabled)
        reconnect_row.addWidget(self.chk_reconnect)
        reconnect_row.addWidget(self.spn_reconnect)
        reconnect_row.addStretch()
        rw = QWidget()
        rw.setLayout(reconnect_row)
        self._conn_form.addRow('재연결:', rw)

    def _add_conn_buttons(self):
        self.btn_conn = QPushButton('Connect [Ctrl+K]')
        self.btn_conn.clicked.connect(self._toggle_connection)
        self._conn_form.addRow('', self.btn_conn)
        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_connection)

    def _toggle_connection(self):
        if self._connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        h = TCPClientHandler(
            self.inp_ip.text().strip(),
            self.spn_port.value(),
            self.chk_reconnect.isChecked(),
            float(self.spn_reconnect.value()),
        )
        h.data_received.connect(self.display.append_rx)
        h.connected.connect(self._on_connected)
        h.disconnected.connect(self._on_disconnected)
        h.error_occurred.connect(lambda e: self.display.append_event(f'오류: {e}'))
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        self.btn_conn.setText('연결 중...')
        self.btn_conn.setEnabled(False)
        h.start()

    def _on_connected(self):
        self.btn_conn.setText('Disconnect [Ctrl+K]')
        self.btn_conn.setEnabled(True)
        lbl = f'{self.inp_ip.text()}:{self.spn_port.value()}'
        self.display.append_event(f'TCP 연결됨 → {lbl}')
        self._set_connected(lbl)

    def _on_disconnected(self, reason: str):
        self.btn_conn.setText('Connect [Ctrl+K]')
        self.btn_conn.setEnabled(True)
        self.display.append_event(f'TCP 연결 끊김: {reason}')
        self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, ip: str, port: int, **_):
        self.inp_ip.setText(ip)
        self.spn_port.setValue(port)


# ──────────────────────────────────────────────────────────────
# TCP Server 탭
# ──────────────────────────────────────────────────────────────

class TCPServerTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('TCP Server 설정')
        self._add_fields()
        self._add_conn_buttons()

    def _add_fields(self):
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(5000)
        self._conn_form.addRow('Local Port:', self.spn_port)

    def _add_conn_buttons(self):
        self.btn_listen = QPushButton('Listen [Ctrl+K]')
        self.btn_listen.clicked.connect(self._toggle_listen)
        self._conn_form.addRow('', self.btn_listen)
        self.lbl_client = QLabel('클라이언트 없음')
        self.lbl_client.setStyleSheet('color:#808080; font-size:9px;')
        self._conn_form.addRow('클라이언트:', self.lbl_client)
        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_listen)

    def _toggle_listen(self):
        if self._connected:
            self._do_stop()
        else:
            self._do_listen()

    def _do_listen(self):
        h = TCPServerHandler(self.spn_port.value())
        h.data_received.connect(
            lambda data, ip, port: self.display.append_rx(data)
        )
        h.client_connected.connect(self._on_client_connected)
        h.client_disconnected.connect(self._on_client_disconnected)
        h.new_client_request.connect(self._on_new_client_request)
        h.error_occurred.connect(lambda e: self.display.append_event(f'오류: {e}'))
        h.status_changed.connect(self._on_status_changed)
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        h.start()

    def _on_status_changed(self, status: str):
        if status == 'listening':
            self.btn_listen.setText('Stop [Ctrl+K]')
            self.display.append_event(f'Listening on port {self.spn_port.value()}')
            self._set_connected(f':{self.spn_port.value()}')
        elif status in ('closed', 'error'):
            self.btn_listen.setText('Listen [Ctrl+K]')
            self.lbl_client.setText('클라이언트 없음')
            self.display.append_event('Server Stopped')
            self._set_disconnected()

    def _on_client_connected(self, ip: str, port: int):
        self.lbl_client.setText(f'{ip}:{port}')
        self.display.append_event(f'클라이언트 연결: {ip}:{port}')

    def _on_client_disconnected(self, ip: str, port: int):
        self.lbl_client.setText('클라이언트 없음')
        self.display.append_event(f'클라이언트 연결 끊김: {ip}:{port}')

    def _on_new_client_request(self, ip: str, port: int):
        reply = QMessageBox.question(
            self, '새 클라이언트 요청',
            f'{ip}:{port} 에서 연결 요청이 들어왔습니다.\n'
            '기존 연결을 끊고 새 연결을 수락할까요?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if self._handler:
            if reply == QMessageBox.Yes:
                self._handler.accept_new_client()
            else:
                self._handler.reject_new_client()

    def _do_stop(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, ip: str, port: int, **_):
        self.spn_port.setValue(port)


# ──────────────────────────────────────────────────────────────
# Serial 탭
# ──────────────────────────────────────────────────────────────

BAUDRATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
PARITIES  = ['None', 'Even', 'Odd', 'Mark', 'Space']
STOPBITS  = ['1', '1.5', '2']
DATABITS  = [5, 6, 7, 8]


class SerialTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('Serial 설정')
        self._add_fields()
        self._add_conn_buttons()
        self._refresh_ports()

    def _add_fields(self):
        # 포트 선택
        port_row = QHBoxLayout()
        self.cmb_port = QComboBox()
        self.cmb_port.setMinimumWidth(100)
        port_row.addWidget(self.cmb_port)
        btn_refresh = QPushButton('🔄')
        btn_refresh.setFixedWidth(28)
        btn_refresh.setToolTip('포트 목록 새로고침')
        btn_refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(btn_refresh)
        port_row.addStretch()
        pw = QWidget(); pw.setLayout(port_row)
        self._conn_form.addRow('Port:', pw)

        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems([str(b) for b in BAUDRATES])
        self.cmb_baud.setCurrentText('115200')
        self._conn_form.addRow('Baud Rate:', self.cmb_baud)

        self.cmb_data = QComboBox()
        self.cmb_data.addItems([str(d) for d in DATABITS])
        self.cmb_data.setCurrentText('8')
        self._conn_form.addRow('Data Bits:', self.cmb_data)

        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(PARITIES)
        self._conn_form.addRow('Parity:', self.cmb_parity)

        self.cmb_stop = QComboBox()
        self.cmb_stop.addItems(STOPBITS)
        self._conn_form.addRow('Stop Bits:', self.cmb_stop)

    def _add_conn_buttons(self):
        self.btn_conn = QPushButton('Open [Ctrl+K]')
        self.btn_conn.clicked.connect(self._toggle_connection)
        self._conn_form.addRow('', self.btn_conn)
        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_connection)

    def _refresh_ports(self):
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        ports = list_serial_ports()
        self.cmb_port.addItems(ports if ports else ['(없음)'])
        if current in ports:
            self.cmb_port.setCurrentText(current)

    def _toggle_connection(self):
        if self._connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        port = self.cmb_port.currentText()
        if not port or port == '(없음)':
            QMessageBox.warning(self, '오류', '유효한 포트를 선택하세요.')
            return
        h = SerialHandler(
            port=port,
            baudrate=int(self.cmb_baud.currentText()),
            bytesize=int(self.cmb_data.currentText()),
            parity=self.cmb_parity.currentText(),
            stopbits=self.cmb_stop.currentText(),
        )
        h.data_received.connect(self.display.append_rx)
        h.connected.connect(self._on_connected)
        h.disconnected.connect(self._on_disconnected)
        h.error_occurred.connect(lambda e: self.display.append_event(f'오류: {e}'))
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        self.btn_conn.setText('연결 중...')
        self.btn_conn.setEnabled(False)
        h.start()

    def _on_connected(self):
        self.btn_conn.setText('Close [Ctrl+K]')
        self.btn_conn.setEnabled(True)
        port = self.cmb_port.currentText()
        baud = self.cmb_baud.currentText()
        self.display.append_event(f'Serial 열림: {port} @ {baud}')
        self._set_connected(f'{port}@{baud}')

    def _on_disconnected(self, reason: str):
        self.btn_conn.setText('Open [Ctrl+K]')
        self.btn_conn.setEnabled(True)
        self.display.append_event(f'Serial 닫힘: {reason}')
        self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, baudrate: int = 115200,
                         databits: int = 8, parity: str = 'None',
                         stopbits: str = '1', **_):
        """Config Tool의 Serial 설정을 자동 채움. COM 포트는 알 수 없으므로 제외."""
        self.cmb_baud.setCurrentText(str(baudrate))
        self.cmb_data.setCurrentText(str(databits))
        self.cmb_parity.setCurrentText(parity)
        self.cmb_stop.setCurrentText(stopbits)
