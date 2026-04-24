"""
terminal/receive_display.py
수신 데이터 표시 위젯.
- 50ms QTimer 배치 렌더로 고속 데이터에서도 UI 프리즈 없음
- ASCII 표시 + 비ASCII → [HH] 인라인 HEX
- 개행문자(\r\n) 실제 줄바꿈 렌더 (옵션으로 [HH] raw 표시)
- 송신(파랑) / 수신(흰색) 색상 구분
- 타임스탬프 3모드: 절대시각 / 경과시간 / 패킷 간격
- 자동 스크롤: 사용자가 스크롤 올리면 일시정지, 맨 아래로 내리면 재개
- 최대 줄 수 초과 시 상단 trim
- Ctrl+F 검색, Ctrl++/- 폰트 크기, 우클릭 메뉴
"""

import html
import time
from collections import deque
from datetime import datetime

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QAction, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

# 색상 (CSS)
COLOR_RX    = '#e0e0e0'   # 수신: 밝은 회색
COLOR_TX    = '#82b4ff'   # 송신: 파랑
COLOR_EVENT = '#a0e0a0'   # 이벤트: 연두
COLOR_TS    = '#808080'   # 타임스탬프: 회색
BG_COLOR    = '#1e1e1e'   # 배경: 다크

NEWLINE_CHARS = {0x0D, 0x0A}

TS_ABSOLUTE = 0
TS_ELAPSED  = 1
TS_DELTA    = 2


def _bytes_to_display(data: bytes, show_raw_newlines: bool = False,
                      encoding: str = 'ascii') -> str:
    """
    bytes → HTML 표시 문자열.
    가독 ASCII는 그대로, 비ASCII는 [HH], 개행은 <br> 또는 [HH].
    """
    result = []
    i = 0
    while i < len(data):
        b = data[i]
        if not show_raw_newlines and b in (0x0D, 0x0A):
            # \r\n 쌍은 하나의 <br>로
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
    """수신창 내 검색 바 (Ctrl+F로 토글)."""
    find_next    = pyqtSignal(str)
    find_prev    = pyqtSignal(str)
    closed       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.input = QLineEdit()
        self.input.setPlaceholderText('검색...')
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
    """수신 데이터 표시 컨테이너 (display + 검색 바 + 툴바)."""

    def __init__(self, max_lines: int = 2000, parent=None):
        super().__init__(parent)
        self.max_lines     = max_lines
        self._buf: deque   = deque()          # (kind, data) kind: 'rx'|'tx'|'event'
        self._paused       = False
        self._auto_scroll  = True
        self._ts_mode      = TS_ABSOLUTE
        self._session_start = time.time()
        self._last_ts      = time.time()
        self._show_raw_nl  = False
        self._inline_events = True
        self._encoding     = 'ascii'
        self._font_size    = 10
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    # ── UI 구성 ────────────────────────────────────────────────

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 툴바
        toolbar = QWidget()
        hbox = QHBoxLayout(toolbar)
        hbox.setContentsMargins(2, 2, 2, 2)
        hbox.setSpacing(4)

        self.btn_pause = QPushButton('⏸')
        self.btn_pause.setCheckable(True)
        self.btn_pause.setFixedWidth(28)
        self.btn_pause.setToolTip('수신 일시정지 (버퍼는 계속 수신)')
        self.btn_pause.toggled.connect(self._on_pause_toggled)
        hbox.addWidget(self.btn_pause)

        self.btn_ts = QPushButton('🕐')
        self.btn_ts.setFixedWidth(28)
        self.btn_ts.setToolTip('타임스탬프 모드 전환')
        self.btn_ts.clicked.connect(self._cycle_ts_mode)
        hbox.addWidget(self.btn_ts)

        self.btn_nl = QPushButton('[NL]')
        self.btn_nl.setCheckable(True)
        self.btn_nl.setFixedWidth(40)
        self.btn_nl.setToolTip('개행문자 raw [HH] 표시')
        self.btn_nl.toggled.connect(self._on_nl_toggled)
        hbox.addWidget(self.btn_nl)

        self.btn_event = QPushButton('≡')
        self.btn_event.setCheckable(True)
        self.btn_event.setChecked(True)
        self.btn_event.setFixedWidth(28)
        self.btn_event.setToolTip('이벤트 인라인/분리 표시 토글')
        self.btn_event.toggled.connect(self._on_event_toggled)
        hbox.addWidget(self.btn_event)

        hbox.addStretch()

        self.stats_label = QLabel('TX: 0 B  RX: 0 B')
        self.stats_label.setStyleSheet('color: #808080; font-size: 9px;')
        hbox.addWidget(self.stats_label)

        btn_clear = QPushButton('🗑')
        btn_clear.setFixedWidth(28)
        btn_clear.setToolTip('수신창 지우기 (Ctrl+L)')
        btn_clear.clicked.connect(self.clear)
        hbox.addWidget(btn_clear)

        vbox.addWidget(toolbar)

        # 이벤트 상태바 (분리 모드)
        self._event_bar = QLabel('')
        self._event_bar.setStyleSheet(
            f'background:{BG_COLOR}; color:{COLOR_EVENT}; padding:2px 4px; font-size:9px;'
        )
        self._event_bar.hide()
        vbox.addWidget(self._event_bar)

        # 수신 텍스트
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet(
            f'QPlainTextEdit {{ background:{BG_COLOR}; color:{COLOR_RX}; '
            f'border:none; font-family:Consolas,Courier,monospace; font-size:{self._font_size}pt; }}'
        )
        self.text.setMaximumBlockCount(0)   # 수동으로 trim
        self.text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text.customContextMenuRequested.connect(self._show_context_menu)
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        vbox.addWidget(self.text)

        # 검색 바
        self._search_bar = SearchBar()
        self._search_bar.hide()
        self._search_bar.find_next.connect(self._do_find_next)
        self._search_bar.find_prev.connect(self._do_find_prev)
        self._search_bar.closed.connect(self._search_bar.hide)
        vbox.addWidget(self._search_bar)

        # 단축키
        from PyQt5.QtWidgets import QShortcut
        QShortcut(QKeySequence('Ctrl+F'), self, self._toggle_search)
        QShortcut(QKeySequence('Ctrl+L'), self, self.clear)
        QShortcut(QKeySequence('Ctrl+='), self, self._font_larger)
        QShortcut(QKeySequence('Ctrl++'), self, self._font_larger)
        QShortcut(QKeySequence('Ctrl+-'), self, self._font_smaller)

    # ── 공개 API ────────────────────────────────────────────────

    def append_rx(self, data: bytes):
        """수신 데이터 버퍼에 추가."""
        self._buf.append(('rx', data, time.time()))

    def append_tx(self, data: bytes):
        """송신 데이터 버퍼에 추가 (에코 표시용)."""
        self._buf.append(('tx', data, time.time()))

    def append_event(self, text: str):
        """연결/해제 등 이벤트 메시지."""
        self._buf.append(('event', text.encode(), time.time()))

    def update_stats(self, tx: int, rx: int):
        def _fmt(n):
            if n < 1024:
                return f'{n} B'
            return f'{n / 1024:.1f} KB'
        self.stats_label.setText(f'TX: {_fmt(tx)}  RX: {_fmt(rx)}')
        self.stats_label.setToolTip(
            f'TX: {tx:,} bytes\nRX: {rx:,} bytes'
        )

    def clear(self):
        self.text.clear()
        self._buf.clear()

    def set_max_lines(self, n: int):
        self.max_lines = n

    def set_encoding(self, enc: str):
        self._encoding = enc

    # ── 내부 렌더링 ─────────────────────────────────────────────

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

        # 줄 수 초과 시 상단 trim
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
            return datetime.fromtimestamp(ts).strftime('%H:%M:%S.') + \
                   f'{int(datetime.fromtimestamp(ts).microsecond / 1000):03d}'
        if self._ts_mode == TS_ELAPSED:
            elapsed = ts - self._session_start
            m = int(elapsed // 60)
            s = elapsed - m * 60
            return f'+{m:02d}:{s:06.3f}'
        # DELTA
        delta = ts - self._last_ts
        return f'Δ{delta:.3f}s'

    # ── 슬롯 ────────────────────────────────────────────────────

    def _on_pause_toggled(self, checked: bool):
        self._paused = checked
        self.btn_pause.setText('▶' if checked else '⏸')

    def _cycle_ts_mode(self):
        self._ts_mode = (self._ts_mode + 1) % 3
        labels = ['🕐 절대', '⏱ 경과', 'Δ 간격']
        self.btn_ts.setToolTip(f'타임스탬프: {labels[self._ts_mode]}')

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
            f'border:none; font-family:Consolas,Courier,monospace; font-size:{self._font_size}pt; }}'
        )

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction('복사 (선택 영역)', self.text.copy)
        menu.addAction('전체 복사', self._copy_all)
        menu.addSeparator()
        menu.addAction('선택 영역 파일로 저장', self._save_selection)
        menu.addAction('전체 파일로 저장', self._save_all)
        menu.addSeparator()
        menu.addAction('지우기 (Ctrl+L)', self.clear)
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
            self, '저장', '', 'Text files (*.txt);;All files (*)'
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
            except OSError as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, '저장 실패', str(e))
