"""
terminal/macro_panel.py
F1~F12 매크로/시퀀스 패널.
- 12개 고정 슬롯, 각 슬롯은 이름 + 인라인 시퀀스 테이블
- 시퀀스: 메시지 + 딜레이(ms, 기본 0)
- F1~F12 단축키로 직접 실행
- 실행 중 현재 행 하이라이트 + 진행 표시
- Export/Import JSON
- 바이트 팔레트 (0x00, 0xFF, CR, LF 등)
"""

import json
import time

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QShortcut, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

MAX_MACROS = 12

BYTE_PALETTE = [
    ('NUL', b'\x00'), ('SOH', b'\x01'), ('STX', b'\x02'), ('ETX', b'\x03'),
    ('CR',  b'\r'),   ('LF',  b'\n'),   ('CR+LF', b'\r\n'),
    ('ESC', b'\x1b'), ('DEL', b'\x7f'), ('0xFF', b'\xff'),
]


# ──────────────────────────────────────────────────────────────
# 시퀀스 실행 스레드
# ──────────────────────────────────────────────────────────────

class MacroRunner(QThread):
    row_started  = pyqtSignal(int)    # 현재 실행 중인 행 인덱스
    finished_all = pyqtSignal()

    def __init__(self, rows: list, send_fn, parent=None):
        """rows: [(message_bytes, delay_ms), ...]"""
        super().__init__(parent)
        self._rows   = rows
        self._send   = send_fn
        self._abort  = False

    def abort(self):
        self._abort = True

    def run(self):
        for i, (msg, delay) in enumerate(self._rows):
            if self._abort:
                break
            self.row_started.emit(i)
            if msg:
                self._send(msg)
            if delay > 0 and not self._abort:
                # 10ms 단위 대기 (abort 가능)
                elapsed = 0
                while elapsed < delay and not self._abort:
                    self.msleep(min(10, delay - elapsed))
                    elapsed += 10
        self.finished_all.emit()


# ──────────────────────────────────────────────────────────────
# 시퀀스 테이블
# ──────────────────────────────────────────────────────────────

class MacroSequenceTable(QTableWidget):
    """메시지 + 딜레이(ms) 2열 테이블. 맨 아래 빈 행은 항상 유지."""

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(['메시지', '딜레이 (ms)'])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 90)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.verticalHeader().setVisible(False)
        self.setMaximumHeight(160)
        self._add_empty_row()
        self.cellChanged.connect(self._on_cell_changed)

    def _add_empty_row(self):
        row = self.rowCount()
        self.insertRow(row)
        msg_item = QTableWidgetItem('')
        delay_item = QTableWidgetItem('0')
        delay_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 0, msg_item)
        self.setItem(row, 1, delay_item)

    def _on_cell_changed(self, row, col):
        # 마지막 행에 내용이 생기면 새 빈 행 추가
        if row == self.rowCount() - 1:
            msg = self.item(row, 0)
            if msg and msg.text().strip():
                self._add_empty_row()

    def get_rows(self) -> list:
        """[(message_str, delay_ms), ...] — 빈 행 제외."""
        result = []
        for r in range(self.rowCount()):
            msg_item = self.item(r, 0)
            delay_item = self.item(r, 1)
            msg = msg_item.text() if msg_item else ''
            if not msg.strip():
                continue
            try:
                delay = int(delay_item.text()) if delay_item else 0
            except ValueError:
                delay = 0
            result.append((msg, max(0, delay)))
        return result

    def set_rows(self, rows: list):
        """rows: [(message_str, delay_ms), ...]"""
        self.blockSignals(True)
        self.setRowCount(0)
        for msg, delay in rows:
            r = self.rowCount()
            self.insertRow(r)
            self.setItem(r, 0, QTableWidgetItem(msg))
            di = QTableWidgetItem(str(delay))
            di.setTextAlignment(Qt.AlignCenter)
            self.setItem(r, 1, di)
        self._add_empty_row()
        self.blockSignals(False)

    def highlight_row(self, idx: int):
        for r in range(self.rowCount()):
            for c in range(2):
                item = self.item(r, c)
                if item:
                    item.setBackground(
                        Qt.darkGreen if r == idx else Qt.transparent
                    )

    def insert_at_cursor(self, text: str):
        """현재 선택된 메시지 셀에 텍스트 삽입."""
        row = self.currentRow()
        if row < 0:
            row = max(0, self.rowCount() - 1)
        item = self.item(row, 0)
        if item is None:
            item = QTableWidgetItem('')
            self.setItem(row, 0, item)
        item.setText(item.text() + text)


# ──────────────────────────────────────────────────────────────
# 단일 매크로 슬롯
# ──────────────────────────────────────────────────────────────

class MacroSlot(QWidget):
    send_requested = pyqtSignal(bytes)   # 실제 전송할 바이트

    def __init__(self, slot_idx: int, parent=None):
        super().__init__(parent)
        self.slot_idx = slot_idx
        self.fkey     = f'F{slot_idx + 1}'
        self._runner  = None
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 2, 0, 2)
        vbox.setSpacing(2)

        # 헤더 행
        header = QWidget()
        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)

        self.btn_expand = QPushButton('▶')
        self.btn_expand.setFixedWidth(24)
        self.btn_expand.setCheckable(True)
        self.btn_expand.toggled.connect(self._on_expand)
        hbox.addWidget(self.btn_expand)

        fkey_label = QLabel(f'[{self.fkey}]')
        fkey_label.setStyleSheet('color:#808080; font-size:9px;')
        fkey_label.setFixedWidth(32)
        hbox.addWidget(fkey_label)

        self.name_edit = QLineEdit(f'매크로 {self.slot_idx + 1}')
        self.name_edit.setStyleSheet('border:none; background:transparent;')
        hbox.addWidget(self.name_edit)

        self.progress_label = QLabel('')
        self.progress_label.setStyleSheet('color:#80c080; font-size:9px;')
        self.progress_label.setFixedWidth(36)
        hbox.addWidget(self.progress_label)

        self.btn_run = QPushButton(f'▶ {self.fkey}')
        self.btn_run.setFixedWidth(56)
        self.btn_run.clicked.connect(self.run_sequence)
        hbox.addWidget(self.btn_run)

        vbox.addWidget(header)

        # 시퀀스 테이블 (기본 숨김)
        self.table = MacroSequenceTable()
        self.table.hide()
        vbox.addWidget(self.table)

    def _on_expand(self, checked: bool):
        self.btn_expand.setText('▼' if checked else '▶')
        self.table.setVisible(checked)

    def run_sequence(self):
        rows = self.table.get_rows()
        if not rows:
            return
        if self._runner and self._runner.isRunning():
            self._runner.abort()
            self._runner.wait()

        from .comm_handlers import _encode_escape
        parsed = []
        for msg, delay in rows:
            parsed.append((_encode_escape(msg), delay))

        total = len(parsed)
        self._runner = MacroRunner(parsed, self._do_send)
        self._runner.row_started.connect(
            lambda i: self.progress_label.setText(f'{i + 1}/{total}')
        )
        self._runner.finished_all.connect(
            lambda: self.progress_label.setText('')
        )
        self._runner.start()

    def _do_send(self, data: bytes):
        self.send_requested.emit(data)

    def get_data(self) -> dict:
        return {
            'name': self.name_edit.text(),
            'rows': self.table.get_rows(),
        }

    def set_data(self, data: dict):
        self.name_edit.setText(data.get('name', f'매크로 {self.slot_idx + 1}'))
        rows = data.get('rows', [])
        self.table.set_rows(rows)

    def insert_bytes(self, text: str):
        self.table.insert_at_cursor(text)


# ──────────────────────────────────────────────────────────────
# 바이트 팔레트 위젯
# ──────────────────────────────────────────────────────────────

class BytePalette(QWidget):
    byte_clicked = pyqtSignal(str)   # escape 표현 문자열 (예: '\\x00')

    def __init__(self, parent=None):
        super().__init__(parent)
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(2)
        label = QLabel('삽입:')
        label.setStyleSheet('color:#808080; font-size:9px;')
        hbox.addWidget(label)
        for name, raw in BYTE_PALETTE:
            escape_repr = ''.join(f'\\x{b:02x}' for b in raw)
            if raw == b'\r':
                escape_repr = '\\r'
            elif raw == b'\n':
                escape_repr = '\\n'
            elif raw == b'\r\n':
                escape_repr = '\\r\\n'
            btn = QPushButton(name)
            btn.setFixedHeight(20)
            btn.setToolTip(escape_repr)
            btn.clicked.connect(lambda _, r=escape_repr: self.byte_clicked.emit(r))
            hbox.addWidget(btn)
        hbox.addStretch()


# ──────────────────────────────────────────────────────────────
# 매크로 패널 (12개 슬롯 + 팔레트 + Export/Import)
# ──────────────────────────────────────────────────────────────

class MacroPanel(QWidget):
    send_requested = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slots: list[MacroSlot] = []
        self._build_ui()
        self._bind_fkeys()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        # 툴바
        toolbar = QWidget()
        hbox = QHBoxLayout(toolbar)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(QLabel('매크로'))
        hbox.addStretch()
        btn_export = QPushButton('Export')
        btn_export.setFixedHeight(22)
        btn_export.clicked.connect(self._export)
        hbox.addWidget(btn_export)
        btn_import = QPushButton('Import')
        btn_import.setFixedHeight(22)
        btn_import.clicked.connect(self._import)
        hbox.addWidget(btn_import)
        vbox.addWidget(toolbar)

        # 바이트 팔레트
        self._palette = BytePalette()
        self._palette.byte_clicked.connect(self._insert_to_active_slot)
        vbox.addWidget(self._palette)

        # 슬롯 스크롤 영역
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        slot_vbox = QVBoxLayout(container)
        slot_vbox.setContentsMargins(0, 0, 0, 0)
        slot_vbox.setSpacing(2)

        for i in range(MAX_MACROS):
            slot = MacroSlot(i)
            slot.send_requested.connect(self.send_requested)
            self._slots.append(slot)
            slot_vbox.addWidget(slot)

        slot_vbox.addStretch()
        scroll.setWidget(container)
        vbox.addWidget(scroll)

    def _bind_fkeys(self):
        for i, slot in enumerate(self._slots):
            key = f'F{i + 1}'
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(slot.run_sequence)

    def _insert_to_active_slot(self, text: str):
        """포커스된 슬롯 또는 첫 번째 슬롯에 삽입."""
        focused = self.focusWidget()
        for slot in self._slots:
            if slot.table.hasFocus() or slot.name_edit.hasFocus():
                slot.insert_bytes(text)
                return
        if self._slots:
            self._slots[0].insert_bytes(text)

    def get_all_data(self) -> list:
        return [s.get_data() for s in self._slots]

    def set_all_data(self, data: list):
        for i, slot in enumerate(self._slots):
            if i < len(data):
                slot.set_data(data[i])

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '매크로 내보내기', 'macros.json', 'JSON (*.json)'
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'macros': self.get_all_data()}, f,
                          ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(self, '내보내기 실패', str(e))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '매크로 가져오기', '', 'JSON (*.json)'
        )
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                obj = json.load(f)
            macros = obj.get('macros', obj if isinstance(obj, list) else [])
            self.set_all_data(macros)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            QMessageBox.warning(self, '가져오기 실패', str(e))
