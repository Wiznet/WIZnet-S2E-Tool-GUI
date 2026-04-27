"""
terminal/receive_display.py
Receive data display widget.
- 50ms QTimer batch render — no UI freeze under high-speed data
- ASCII display + non-ASCII → [HH] inline hex
- Newlines (\r\n) rendered as line breaks (option: raw [HH])
- TX (blue) / RX (white) color coding
- Timestamp: absolute / elapsed / delta modes
- Auto-scroll: pauses on scroll-up, resumes at bottom
- Max line trim, Ctrl+F search, Ctrl++/- font size, right-click menu
"""

import html
import time
from collections import deque
from datetime import datetime

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

COLOR_RX = '#e0e0e0'
COLOR_TX = '#82b4ff'
COLOR_EVENT = '#a0e0a0'
COLOR_TS = '#808080'
BG_COLOR = '#1e1e1e'

NEWLINE_CHARS = {0x0D, 0x0A}

TS_ABSOLUTE = 0
TS_ELAPSED = 1
TS_DELTA = 2


def _bytes_to_display(data: bytes, show_raw_newlines: bool = False,
                      encoding: str = 'ascii') -> str:
    result = []
    i = 0
    while i < len(data):
        b = data[i]
        if not show_raw_newlines and b in (0x0D, 0x0A):
            if b == 0x0D and i + 1 < len(data) and data[i + 1] == 0x0A:
                result.append('<br>')
                i += 2
                continue
            result.append('<br>')
            i += 1
            continue
        if 0x20 <= b <= 0x7E:
            result.append(html.escape(chr(b)))
        else:
            result.append(f'<span style="color:#ff9966;">[{b:02X}]</span>')
        i += 1
    return ''.join(result)


class SearchBar(QWidget):
    find_next = pyqtSignal(str)
    find_prev = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText('Search...')
        self.input.returnPressed.connect(lambda: self.find_next.emit(self.input.text()))
        layout.addWidget(self.input)
        btn_prev = QPushButton('◀')
        btn_prev.setFixedWidth(28)
        btn_prev.clicked.connect(lambda: self.find_prev.emit(self.input.text()))
        layout.addWidget(btn_prev)
        btn_next = QPushButton('▶')
        btn_next.setFixedWidth(28)
        btn_next.clicked.connect(lambda: self.find_next.emit(self.input.text()))
        layout.addWidget(btn_next)
        btn_close = QPushButton('✕')
        btn_close.setFixedWidth(24)
        btn_close.clicked.connect(self.closed)
        layout.addWidget(btn_close)
        self.result_label = QLabel('')
        layout.addWidget(self.result_label)

    def focus(self):
        self.input.setFocus()
        self.input.selectAll()


class ReceiveDisplay(QWidget):
    def __init__(self, max_lines: int = 2000, parent=None):
        super().__init__(parent)
        self.max_lines = max_lines
        self._buf: deque = deque()
        self._paused = False
        self._auto_scroll = True
        self._ts_mode = TS_ABSOLUTE
        self._session_start = time.time()
        self._last_ts = time.time()
        self._show_raw_nl = False
        self._inline_events = True
        self._encoding = 'ascii'
        self._font_size = 10
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        toolbar = QWidget()
        hbox = QHBoxLayout(toolbar)
        hbox.setContentsMargins(2, 2, 2, 2)
        hbox.setSpacing(4)

        self.btn_pause = QPushButton('⏸')
        self.btn_pause.setCheckable(True)
        self.btn_pause.setFixedSize(32, 26)
        self.btn_pause.setStyleSheet('color: #111; font-size: 13px;')
        self.btn_pause.setToolTip('Pause display (buffer continues)')
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        hbox.addWidget(self.btn_pause)

        _BTN = 'font-size: 13px;'
        _SZ = (32, 26)

        self.btn_ts = QPushButton('🕐')
        self.btn_ts.setFixedSize(*_SZ)
        self.btn_ts.setStyleSheet(_BTN)
        self.btn_ts.setToolTip('Timestamp: Abs (click to change)')
        self.btn_ts.clicked.connect(self._cycle_ts_mode)
        hbox.addWidget(self.btn_ts)

        self.btn_nl = QPushButton('¶')
        self.btn_nl.setCheckable(True)
        self.btn_nl.setFixedSize(*_SZ)
        self.btn_nl.setStyleSheet(_BTN)
        self.btn_nl.setToolTip('Show newlines as raw hex [0D][0A]')
        self.btn_nl.toggled.connect(self._on_nl_toggled)
        hbox.addWidget(self.btn_nl)

        self.btn_event = QPushButton('≡')
        self.btn_event.setCheckable(True)
        self.btn_event.setChecked(True)
        self.btn_event.setFixedSize(*_SZ)
        self.btn_event.setStyleSheet(_BTN)
        self.btn_event.setToolTip('Show events inline in data stream')
        self.btn_event.toggled.connect(self._on_event_toggled)
        hbox.addWidget(self.btn_event)

        hbox.addStretch()

        self.stats_label = QLabel('TX: 0 B  RX: 0 B')
        self.stats_label.setStyleSheet('color: #c8c8c8; font-size: 11px;')
        hbox.addWidget(self.stats_label)

        btn_clear = QPushButton('🗑')
        btn_clear.setFixedSize(*_SZ)
        btn_clear.setStyleSheet(_BTN)
        btn_clear.setToolTip('Clear (Ctrl+L)')
        btn_clear.clicked.connect(self.clear)
        hbox.addWidget(btn_clear)

        vbox.addWidget(toolbar)

        self._event_bar = QLabel('')
        self._event_bar.setStyleSheet(
            f'background:{BG_COLOR}; color:{COLOR_EVENT}; padding:2px 4px; font-size:9px;'
        )
        self._event_bar.hide()
        vbox.addWidget(self._event_bar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet(
            f'QPlainTextEdit {{ background:{BG_COLOR}; color:{COLOR_RX}; '
            f'border:none; font-family:Consolas,Courier,monospace; '
            f'font-size:{self._font_size}pt; }}'
        )
        self.text.setMaximumBlockCount(0)
        self.text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text.customContextMenuRequested.connect(self._show_context_menu)
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        vbox.addWidget(self.text)

        self._search_bar = SearchBar()
        self._search_bar.hide()
        self._search_bar.find_next.connect(self._do_find_next)
        self._search_bar.find_prev.connect(self._do_find_prev)
        self._search_bar.closed.connect(self._search_bar.hide)
        vbox.addWidget(self._search_bar)

        from PyQt5.QtWidgets import QShortcut
        QShortcut(QKeySequence('Ctrl+F'), self, self._toggle_search)
        QShortcut(QKeySequence('Ctrl+L'), self, self.clear)
        QShortcut(QKeySequence('Ctrl+='), self, self._font_larger)
        QShortcut(QKeySequence('Ctrl++'), self, self._font_larger)
        QShortcut(QKeySequence('Ctrl+-'), self, self._font_smaller)

    def append_rx(self, data: bytes):
        self._buf.append(('rx', data, time.time()))

    def append_tx(self, data: bytes):
        self._buf.append(('tx', data, time.time()))

    def append_event(self, text: str):
        self._buf.append(('event', text.encode(), time.time()))

    def update_stats(self, tx: int, rx: int):
        def _fmt(n):
            if n < 1024:
                return f'{n} B'
            return f'{n / 1024:.1f} KB'
        self.stats_label.setText(f'TX: {_fmt(tx)}  RX: {_fmt(rx)}')
        self.stats_label.setToolTip(f'TX: {tx:,} bytes\nRX: {rx:,} bytes')

    def clear(self):
        self.text.clear()
        self._buf.clear()
        self.stats_label.setText('TX: 0 B  RX: 0 B')
        self.stats_label.setToolTip('')

    def set_max_lines(self, n: int):
        self.max_lines = n

    def set_encoding(self, enc: str):
        self._encoding = enc

    def _flush(self):
        if self._paused or not self._buf:
            return
        chunks = []
        while self._buf:
            chunks.append(self._buf.popleft())

        html_parts = []
        for kind, data, ts in chunks:
            ts_str = self._format_ts(ts)
            self._last_ts = ts
            if kind == 'event':
                text = data.decode('utf-8', errors='replace')
                if self._inline_events:
                    html_parts.append(
                        f'<span style="color:{COLOR_EVENT};">'
                        f'─── {html.escape(text)} ───</span><br>'
                    )
                else:
                    self._event_bar.setText(f'● {text}')
                continue
            color = COLOR_TX if kind == 'tx' else COLOR_RX
            display = _bytes_to_display(data, self._show_raw_nl, self._encoding)
            if ts_str:
                html_parts.append(
                    f'<span style="color:{COLOR_TS}; font-size:8pt;">[{ts_str}]</span>'
                    f'<span style="color:{color};"> {display}</span>'
                )
            else:
                html_parts.append(f'<span style="color:{color};">{display}</span>')

        if not html_parts:
            return

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text.setTextCursor(cursor)
        self.text.appendHtml(''.join(html_parts))

        doc = self.text.document()
        while doc.blockCount() > self.max_lines:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        if self._auto_scroll:
            sb = self.text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _format_ts(self, ts: float) -> str:
        if self._ts_mode == TS_ABSOLUTE:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime('%H:%M:%S.') + f'{dt.microsecond // 1000:03d}'
        if self._ts_mode == TS_ELAPSED:
            elapsed = ts - self._session_start
            m = int(elapsed // 60)
            s = elapsed - m * 60
            return f'+{m:02d}:{s:06.3f}'
        delta = ts - self._last_ts
        return f'Δ{delta:.3f}s'

    def _on_pause_toggled(self, checked: bool):
        self._paused = checked
        self.btn_pause.setText('▶' if checked else '⏸')

    def _cycle_ts_mode(self):
        self._ts_mode = (self._ts_mode + 1) % 3
        labels = ['Abs (HH:MM:SS)', 'Elapsed (+MM:SS)', 'Delta (Δs)']
        self.btn_ts.setToolTip(f'Timestamp: {labels[self._ts_mode]} — click to change')

    def _on_nl_toggled(self, checked: bool):
        self._show_raw_nl = checked

    def _on_event_toggled(self, checked: bool):
        self._inline_events = checked
        self._event_bar.setVisible(not checked)

    def _on_scroll_changed(self, val: int):
        sb = self.text.verticalScrollBar()
        self._auto_scroll = (val == sb.maximum())

    def _toggle_search(self):
        if self._search_bar.isVisible():
            self._search_bar.hide()
        else:
            self._search_bar.show()
            self._search_bar.focus()

    def _do_find_next(self, text: str):
        if not text:
            return
        found = self.text.find(text)
        if not found:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.text.setTextCursor(cursor)
            self.text.find(text)

    def _do_find_prev(self, text: str):
        if not text:
            return
        from PyQt5.QtGui import QTextDocument
        self.text.find(text, QTextDocument.FindBackward)

    def _font_larger(self):
        self._font_size = min(self._font_size + 1, 24)
        self._update_font()

    def _font_smaller(self):
        self._font_size = max(self._font_size - 1, 6)
        self._update_font()

    def _update_font(self):
        self.text.setStyleSheet(
            f'QPlainTextEdit {{ background:{BG_COLOR}; color:{COLOR_RX}; '
            f'border:none; font-family:Consolas,Courier,monospace; '
            f'font-size:{self._font_size}pt; }}'
        )

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('Copy (Selection)', self.text.copy)
        menu.addAction('Copy All', self._copy_all)
        menu.addSeparator()
        menu.addAction('Save Selection', self._save_selection)
        menu.addAction('Save All', self._save_all)
        menu.addSeparator()
        menu.addAction('Clear (Ctrl+L)', self.clear)
        menu.exec_(self.text.mapToGlobal(pos))

    def _copy_all(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text.toPlainText())

    def _save_selection(self):
        self._save_to_file(self.text.textCursor().selectedText())

    def _save_all(self):
        self._save_to_file(self.text.toPlainText())

    def _save_to_file(self, text: str):
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save', '', 'Text files (*.txt);;All files (*)'
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
            except OSError as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, 'Save Failed', str(e))
