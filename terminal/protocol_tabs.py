"""
terminal/protocol_tabs.py
Protocol tab widgets: UDP / TCP Client / TCP Server / Serial.
Each tab has connection settings + ReceiveDisplay + send area.
"""

from collections import deque
import socket

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
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
    '\\r': b'\r',
    '\\n': b'\n',
    '\\r\\n': b'\r\n',
}

HISTORY_MAX = 50
QUICK_CONN_MAX = 5


# ──────────────────────────────────────────────────────────────
# Send widget
# ──────────────────────────────────────────────────────────────

class SendWidget(QWidget):
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

        # Row 1: input + Send (same line)
        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self.input = QTextEdit()
        self.input.setFixedHeight(48)
        self.input.setPlaceholderText('Input — Ctrl+Enter: Send, Ctrl+↑/↓: History')
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input.setStyleSheet('QTextEdit { border: 1px solid #666; border-radius: 2px; }')
        input_row.addWidget(self.input)

        self.btn_send = QPushButton('Send')
        self.btn_send.setFixedSize(60, 48)
        self.btn_send.setToolTip('Send (Ctrl+Enter)')
        self.btn_send.clicked.connect(self._send_once)
        input_row.addWidget(self.btn_send)

        vbox.addLayout(input_row)

        # Row 2: options
        opts = QHBoxLayout()
        opts.setSpacing(6)

        self.chk_escape = QCheckBox('Escape')
        self.chk_escape.setChecked(True)
        self.chk_escape.setToolTip(r'Interpret \\r \\n \\xHH escape sequences')
        opts.addWidget(self.chk_escape)

        opts.addWidget(QLabel('Line End:'))
        self.cmb_le = QComboBox()
        self.cmb_le.addItems(LINE_ENDINGS)
        self.cmb_le.setCurrentText('\\r\\n')
        self.cmb_le.setFixedWidth(70)
        opts.addWidget(self.cmb_le)

        self.btn_periodic = QPushButton('Periodic')
        self.btn_periodic.setCheckable(True)
        self.btn_periodic.setFixedWidth(65)
        self.btn_periodic.toggled.connect(self._on_periodic_toggled)
        opts.addWidget(self.btn_periodic)

        self.spn_interval = QSpinBox()
        self.spn_interval.setRange(10, 60000)
        self.spn_interval.setValue(1000)
        self.spn_interval.setSuffix(' ms')
        self.spn_interval.setFixedWidth(80)
        opts.addWidget(self.spn_interval)

        opts.addStretch()

        vbox.addLayout(opts)

        QShortcut(QKeySequence('Ctrl+Return'), self, self._send_once)
        QShortcut(QKeySequence('Ctrl+Up'), self, self._history_prev)
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
        self.btn_periodic.setText('Stop' if checked else 'Periodic')
        if checked:
            self.spn_interval.valueChanged.connect(self._periodic_timer.setInterval)
            self._periodic_timer.start(self.spn_interval.value())
        else:
            try:
                self.spn_interval.valueChanged.disconnect(self._periodic_timer.setInterval)
            except TypeError:
                pass
            self._periodic_timer.stop()

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
# Base tab
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

        self._conn_group = QGroupBox('Connection')
        self._conn_group.setMaximumHeight(100)
        self._conn_vbox = QVBoxLayout(self._conn_group)
        self._conn_vbox.setContentsMargins(6, 4, 6, 4)
        self._conn_vbox.setSpacing(3)
        self._vbox.addWidget(self._conn_group)

        self.display = ReceiveDisplay()
        self._vbox.addWidget(self.display, stretch=1)

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
# UDP tab
# ──────────────────────────────────────────────────────────────

class UDPTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('UDP')
        self._add_fields()

    def _add_fields(self):
        self._conn_group.setMaximumHeight(80)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(QLabel('Remote IP:Port:'))
        self.inp_remote_ip = QLineEdit('192.168.0.100')
        self.inp_remote_ip.setFixedWidth(130)
        row1.addWidget(self.inp_remote_ip)
        _lbl_colon = QLabel(':')
        _lbl_colon.setFixedWidth(8)
        row1.addWidget(_lbl_colon)
        self.spn_remote_port = QSpinBox()
        self.spn_remote_port.setRange(1, 65535)
        self.spn_remote_port.setValue(5000)
        self.spn_remote_port.setFixedWidth(72)
        row1.addWidget(self.spn_remote_port)
        self.btn_conn = QPushButton('Bind & Open')
        self.btn_conn.setToolTip('Bind & Open (Ctrl+K)')
        self.btn_conn.clicked.connect(self._toggle_connection)
        row1.addWidget(self.btn_conn)
        row1.addStretch()
        self._conn_vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addWidget(QLabel('Local Port:'))
        self.spn_local_port = QSpinBox()
        self.spn_local_port.setRange(0, 65535)
        self.spn_local_port.setValue(0)
        self.spn_local_port.setSpecialValueText('auto')
        self.spn_local_port.setFixedWidth(72)
        row2.addWidget(self.spn_local_port)
        row2.addStretch()
        self._conn_vbox.addLayout(row2)

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
        h.data_received.connect(lambda data, ip, port: self.display.append_rx(data))
        h.error_occurred.connect(lambda e: self.display.append_event(f'Error: {e}'))
        h.status_changed.connect(self._on_status)
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        h.start()

    def _on_status(self, status: str):
        if status == 'bound':
            self.btn_conn.setText('Close')
            lbl = f'{self.inp_remote_ip.text()}:{self.spn_remote_port.value()}'
            self.display.append_event(f'UDP Bound → {lbl}')
            self._set_connected(lbl)
        elif status in ('closed', 'error'):
            self.btn_conn.setText('Bind & Open')
            self.display.append_event('UDP Closed')
            self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, ip: str, port: int, **_):
        self.inp_remote_ip.setText(ip)
        self.spn_remote_port.setValue(port)


# ──────────────────────────────────────────────────────────────
# TCP Client tab
# ──────────────────────────────────────────────────────────────

class TCPClientTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('TCP Client')
        self._add_fields()

    def _add_fields(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel('Remote IP/Port:'))
        self.inp_ip = QLineEdit('192.168.0.100')
        self.inp_ip.setFixedWidth(130)
        row.addWidget(self.inp_ip)
        _lbl_colon = QLabel(':')
        _lbl_colon.setFixedWidth(8)
        row.addWidget(_lbl_colon)
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(5000)
        self.spn_port.setFixedWidth(72)
        row.addWidget(self.spn_port)
        self.btn_conn = QPushButton('Connect')
        self.btn_conn.setToolTip('Connect (Ctrl+K)')
        self.btn_conn.clicked.connect(self._toggle_connection)
        row.addWidget(self.btn_conn)
        self.chk_reconnect = QCheckBox('Auto Reconnect')
        row.addWidget(self.chk_reconnect)
        self.spn_reconnect = QSpinBox()
        self.spn_reconnect.setRange(1, 60)
        self.spn_reconnect.setValue(5)
        self.spn_reconnect.setSuffix(' s')
        self.spn_reconnect.setFixedWidth(55)
        self.spn_reconnect.setEnabled(False)
        self.chk_reconnect.toggled.connect(self.spn_reconnect.setEnabled)
        row.addWidget(self.spn_reconnect)
        self._conn_vbox.addLayout(row)
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
        h.error_occurred.connect(lambda e: self.display.append_event(f'Error: {e}'))
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        self.btn_conn.setText('Connecting...')
        self.btn_conn.setEnabled(False)
        h.start()

    def _on_connected(self):
        self.btn_conn.setText('Disconnect')
        self.btn_conn.setEnabled(True)
        lbl = f'{self.inp_ip.text()}:{self.spn_port.value()}'
        self.display.append_event(f'TCP Connected → {lbl}')
        self._set_connected(lbl)

    def _on_disconnected(self, reason: str):
        self.btn_conn.setText('Connect')
        self.btn_conn.setEnabled(True)
        self.display.append_event(f'TCP Disconnected: {reason}')
        self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, ip: str, port: int, **_):
        self.inp_ip.setText(ip)
        self.spn_port.setValue(port)


# ──────────────────────────────────────────────────────────────
# TCP Server tab
# ──────────────────────────────────────────────────────────────

class TCPServerTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('TCP Server')
        self._add_fields()

    def _add_fields(self):
        local_ip = self._get_local_ip()
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel('Local IP/Port:'))
        lbl_ip = QLabel(local_ip)
        lbl_ip.setStyleSheet('color:#606060;')
        row.addWidget(lbl_ip)
        _lbl_colon = QLabel(':')
        _lbl_colon.setFixedWidth(8)
        row.addWidget(_lbl_colon)
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(5000)
        self.spn_port.setFixedWidth(72)
        row.addWidget(self.spn_port)
        self.btn_listen = QPushButton('Listen')
        self.btn_listen.setToolTip('Listen (Ctrl+K)')
        self.btn_listen.clicked.connect(self._toggle_listen)
        row.addWidget(self.btn_listen)
        self.lbl_client = QLabel('Client: None')
        self.lbl_client.setStyleSheet('color:#808080; font-size:9px;')
        row.addWidget(self.lbl_client)
        row.addStretch()
        self._conn_vbox.addLayout(row)
        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_listen)

    @staticmethod
    def _get_local_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
        except OSError:
            return '0.0.0.0'

    def _toggle_listen(self):
        if self._connected:
            self._do_stop()
        else:
            self._do_listen()

    def _do_listen(self):
        self.btn_listen.setEnabled(False)
        h = TCPServerHandler(self.spn_port.value())
        h.data_received.connect(lambda data, ip, port: self.display.append_rx(data))
        h.client_connected.connect(self._on_client_connected)
        h.client_disconnected.connect(self._on_client_disconnected)
        h.new_client_request.connect(self._on_new_client_request)
        h.error_occurred.connect(lambda e: self.display.append_event(f'Error: {e}'))
        h.status_changed.connect(self._on_status_changed)
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        h.start()

    def _on_status_changed(self, status: str):
        if status == 'listening':
            self.btn_listen.setText('Stop')
            self.btn_listen.setEnabled(True)
            self.display.append_event(f'Listening on port {self.spn_port.value()}')
            self._set_connected(f':{self.spn_port.value()}')
        elif status in ('closed', 'error'):
            self.btn_listen.setText('Listen')
            self.btn_listen.setEnabled(True)
            self.lbl_client.setText('Client: None')
            self.display.append_event('Server Stopped')
            self._set_disconnected()

    def _on_client_connected(self, ip: str, port: int):
        self.lbl_client.setText(f'Client: {ip}:{port}')
        self.display.append_event(f'Client connected: {ip}:{port}')

    def _on_client_disconnected(self, ip: str, port: int):
        self.lbl_client.setText('Client: None')
        self.display.append_event(f'Client disconnected: {ip}:{port}')

    def _on_new_client_request(self, ip: str, port: int):
        reply = QMessageBox.question(
            self, 'New Client Request',
            f'Connection request from {ip}:{port}.\n'
            'Disconnect current client and accept?',
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
# Serial tab
# ──────────────────────────────────────────────────────────────

BAUDRATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
PARITIES = ['None', 'Even', 'Odd', 'Mark', 'Space']
STOPBITS = ['1', '1.5', '2']
DATABITS = [5, 6, 7, 8]


class SerialTab(BaseProtocolTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_group.setTitle('Serial')
        self._conn_group.setMaximumHeight(120)
        self._add_fields()
        self._refresh_ports()

    def _add_fields(self):
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(QLabel('Port:'))
        self.cmb_port = QComboBox()
        self.cmb_port.setMinimumWidth(90)
        row1.addWidget(self.cmb_port)
        btn_refresh = QPushButton('🔄')
        btn_refresh.setFixedWidth(28)
        btn_refresh.setToolTip('Refresh port list')
        btn_refresh.clicked.connect(self._refresh_ports)
        row1.addWidget(btn_refresh)
        row1.addWidget(QLabel('Baud:'))
        self.cmb_baud = QComboBox()
        self.cmb_baud.addItems([str(b) for b in BAUDRATES])
        self.cmb_baud.setCurrentText('115200')
        self.cmb_baud.setFixedWidth(85)
        row1.addWidget(self.cmb_baud)
        self.btn_conn = QPushButton('Open')
        self.btn_conn.setToolTip('Open (Ctrl+K)')
        self.btn_conn.clicked.connect(self._toggle_connection)
        row1.addWidget(self.btn_conn)
        row1.addStretch()
        self._conn_vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addWidget(QLabel('Data:'))
        self.cmb_data = QComboBox()
        self.cmb_data.addItems([str(d) for d in DATABITS])
        self.cmb_data.setCurrentText('8')
        self.cmb_data.setFixedWidth(50)
        row2.addWidget(self.cmb_data)
        row2.addWidget(QLabel('Parity:'))
        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(PARITIES)
        self.cmb_parity.setFixedWidth(70)
        row2.addWidget(self.cmb_parity)
        row2.addWidget(QLabel('Stop:'))
        self.cmb_stop = QComboBox()
        self.cmb_stop.addItems(STOPBITS)
        self.cmb_stop.setFixedWidth(50)
        row2.addWidget(self.cmb_stop)
        row2.addStretch()
        self._conn_vbox.addLayout(row2)

        QShortcut(QKeySequence('Ctrl+K'), self, self._toggle_connection)

    def _refresh_ports(self):
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        ports = list_serial_ports()
        self.cmb_port.addItems(ports if ports else ['(none)'])
        if current in ports:
            self.cmb_port.setCurrentText(current)

    def _toggle_connection(self):
        if self._connected:
            self._do_disconnect()
        else:
            self._do_connect()

    def _do_connect(self):
        port = self.cmb_port.currentText()
        if not port or port == '(none)':
            QMessageBox.warning(self, 'Error', 'Select a valid port.')
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
        h.error_occurred.connect(lambda e: self.display.append_event(f'Error: {e}'))
        h.stats_updated.connect(self.display.update_stats)
        self._handler = h
        self.btn_conn.setText('Opening...')
        self.btn_conn.setEnabled(False)
        h.start()

    def _on_connected(self):
        self.btn_conn.setText('Close')
        self.btn_conn.setEnabled(True)
        port = self.cmb_port.currentText()
        baud = self.cmb_baud.currentText()
        self.display.append_event(f'Serial opened: {port} @ {baud}')
        self._set_connected(f'{port}@{baud}')

    def _on_disconnected(self, reason: str):
        self.btn_conn.setText('Open')
        self.btn_conn.setEnabled(True)
        self.display.append_event(f'Serial closed: {reason}')
        self._set_disconnected()

    def _do_disconnect(self):
        if self._handler:
            self._handler.stop()

    def fill_from_device(self, baudrate: int = 115200,
                         databits: int = 8, parity: str = 'None',
                         stopbits: str = '1', **_):
        self.cmb_baud.setCurrentText(str(baudrate))
        self.cmb_data.setCurrentText(str(databits))
        self.cmb_parity.setCurrentText(parity)
        self.cmb_stop.setCurrentText(stopbits)
