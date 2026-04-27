"""
terminal/macro_panel.py
F1~F12 macro/sequence panel.
- Left (30%): slot list (QListWidget) + Add/Remove slot buttons
- Right (70%): F-key label, name edit, Run/Stop/Insert controls + sequence table
- F1~F12 shortcuts run the corresponding slot directly
- BytePalette: Insert▾ button → QMenu (no clipping)
"""

import json

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QMenu, QMessageBox, QPushButton,
    QShortcut, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

MIN_MACROS = 3
MAX_MACROS = 12

BYTE_PALETTE = [
    ('NUL', b'\x00'), ('SOH', b'\x01'), ('STX', b'\x02'), ('ETX', b'\x03'),
    ('CR', b'\r'), ('LF', b'\n'), ('CR+LF', b'\r\n'),
    ('ESC', b'\x1b'), ('DEL', b'\x7f'), ('0xFF', b'\xff'),
]


# ──────────────────────────────────────────────────────────────
# Sequence runner thread
# ──────────────────────────────────────────────────────────────

class MacroRunner(QThread):
    row_started = pyqtSignal(int)
    finished_all = pyqtSignal()

    def __init__(self, rows: list, send_fn, parent=None):
        """rows: [(message_bytes, delay_ms), ...]"""
        super().__init__(parent)
        self._rows = rows
        self._send = send_fn
        self._abort = False

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
                elapsed = 0
                while elapsed < delay and not self._abort:
                    self.msleep(min(10, delay - elapsed))
                    elapsed += 10
        self.finished_all.emit()


# ──────────────────────────────────────────────────────────────
# Sequence table
# ──────────────────────────────────────────────────────────────

class MacroSequenceTable(QTableWidget):
    """Message + Delay(ms) 2-column table. Always keeps a blank row at the bottom."""

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(['Message', 'Delay (ms)'])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 90)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        self.verticalHeader().setVisible(False)
        self.setStyleSheet("""
            QTableWidget { gridline-color: #888; }
            QHeaderView::section {
                background-color: palette(button);
                border: none;
                border-right: 1px solid #888;
                border-bottom: 1px solid #888;
                padding: 2px 4px;
            }
        """)
        self._add_empty_row()
        self.cellChanged.connect(self._on_cell_changed)

    def _add_empty_row(self):
        row = self.rowCount()
        self.insertRow(row)
        delay_item = QTableWidgetItem('0')
        delay_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 0, QTableWidgetItem(''))
        self.setItem(row, 1, delay_item)

    def _on_cell_changed(self, row, col):
        if row == self.rowCount() - 1:
            msg = self.item(row, 0)
            if msg and msg.text().strip():
                self._add_empty_row()

    def get_rows(self) -> list:
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
        self.blockSignals(True)
        self.setRowCount(0)
        for msg, delay in rows:
            r = self.rowCount()
            self.insertRow(r)
            di = QTableWidgetItem(str(delay))
            di.setTextAlignment(Qt.AlignCenter)
            self.setItem(r, 0, QTableWidgetItem(msg))
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
        row = self.currentRow()
        if row < 0:
            row = max(0, self.rowCount() - 1)
        item = self.item(row, 0)
        if item is None:
            item = QTableWidgetItem('')
            self.setItem(row, 0, item)
        item.setText(item.text() + text)


# ──────────────────────────────────────────────────────────────
# Macro panel
# ──────────────────────────────────────────────────────────────

class MacroPanel(QWidget):
    send_requested = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._count = MIN_MACROS
        self._slot_data = [
            {'name': f'Macro {i + 1}', 'rows': []}
            for i in range(MAX_MACROS)
        ]
        self._runner = None
        self._build_ui()
        self._bind_fkeys()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left: slot list (30%) ──────────────────────────────
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 2, 0)
        left_vbox.setSpacing(2)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.currentRowChanged.connect(self._switch_to)
        left_vbox.addWidget(self._list, 1)

        slot_btns = QHBoxLayout()
        self._btn_add_slot = QPushButton('+ Slot')
        self._btn_add_slot.setFixedHeight(22)
        self._btn_add_slot.setToolTip(f'Add slot (max {MAX_MACROS})')
        self._btn_add_slot.clicked.connect(self._add_slot)
        slot_btns.addWidget(self._btn_add_slot)

        self._btn_del_slot = QPushButton('- Slot')
        self._btn_del_slot.setFixedHeight(22)
        self._btn_del_slot.setToolTip(f'Remove last slot (min {MIN_MACROS})')
        self._btn_del_slot.clicked.connect(self._remove_slot)
        slot_btns.addWidget(self._btn_del_slot)
        left_vbox.addLayout(slot_btns)

        splitter.addWidget(left)

        # ── Right: controls + table (70%) ─────────────────────
        right = QWidget()
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(2, 0, 0, 0)
        right_vbox.setSpacing(4)

        ctrl = QWidget()
        hbox = QHBoxLayout(ctrl)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)

        self._lbl_fkey = QLabel('F1')
        self._lbl_fkey.setFixedWidth(24)
        self._lbl_fkey.setAlignment(Qt.AlignCenter)
        self._lbl_fkey.setStyleSheet('color:#808080; font-size:9px;')
        hbox.addWidget(self._lbl_fkey)

        hbox.addWidget(QLabel('Name:'))
        self._name_edit = QLineEdit()
        self._name_edit.setMinimumWidth(60)
        self._name_edit.textChanged.connect(self._on_name_changed)
        hbox.addWidget(self._name_edit, 1)

        self._btn_run = QPushButton('Run')
        self._btn_run.setFixedHeight(24)
        self._btn_run.clicked.connect(self._run_current)
        hbox.addWidget(self._btn_run)

        self._btn_stop = QPushButton('Stop')
        self._btn_stop.setFixedHeight(24)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_current)
        hbox.addWidget(self._btn_stop)

        btn_insert = QPushButton('Insert▾')
        btn_insert.setFixedHeight(24)
        btn_insert.clicked.connect(self._show_byte_menu)
        hbox.addWidget(btn_insert)

        btn_exp = QPushButton('Export')
        btn_exp.setFixedHeight(24)
        btn_exp.clicked.connect(self._export)
        hbox.addWidget(btn_exp)

        btn_imp = QPushButton('Import')
        btn_imp.setFixedHeight(24)
        btn_imp.clicked.connect(self._import)
        hbox.addWidget(btn_imp)

        ctrl.setMaximumHeight(32)
        right_vbox.addWidget(ctrl)

        self.table = MacroSequenceTable()
        right_vbox.addWidget(self.table, 1)

        splitter.addWidget(right)
        splitter.setSizes([120, 280])

        vbox.addWidget(splitter, 1)

        # BytePalette QMenu
        self._byte_menu = QMenu(self)
        for name, raw in BYTE_PALETTE:
            if raw == b'\r':
                esc = '\\r'
            elif raw == b'\n':
                esc = '\\n'
            elif raw == b'\r\n':
                esc = '\\r\\n'
            else:
                esc = ''.join(f'\\x{b:02x}' for b in raw)
            action = self._byte_menu.addAction(f'{name}  ({esc})')
            action.triggered.connect(
                lambda _, r=esc: self.table.insert_at_cursor(r)
            )
        self._btn_insert_ref = btn_insert

        self._populate_list()
        self._switch_to(0)

    def _populate_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for i in range(self._count):
            name = self._slot_data[i].get('name', f'Macro {i + 1}')
            self._list.addItem(f'F{i + 1}: {name}')
        self._list.setCurrentRow(self._current)
        self._list.blockSignals(False)

    def _show_byte_menu(self):
        btn = self._btn_insert_ref
        self._byte_menu.exec_(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _bind_fkeys(self):
        for i in range(MAX_MACROS):
            sc = QShortcut(QKeySequence(f'F{i + 1}'), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda idx=i: self._run_slot(idx))

    # ── Slot navigation ────────────────────────────────────────

    def _switch_to(self, idx: int):
        if idx < 0 or idx >= self._count:
            return
        if idx != self._current:
            self._save_current()
        self._current = idx
        data = self._slot_data[idx]
        self._lbl_fkey.setText(f'F{idx + 1}')
        self._name_edit.blockSignals(True)
        self._name_edit.setText(data.get('name', f'Macro {idx + 1}'))
        self._name_edit.blockSignals(False)
        self.table.set_rows(data.get('rows', []))
        self._btn_del_slot.setEnabled(self._count > MIN_MACROS)
        self._btn_add_slot.setEnabled(self._count < MAX_MACROS)
        self._list.blockSignals(True)
        self._list.setCurrentRow(idx)
        self._list.blockSignals(False)
        self._btn_run.setFocus()

    def _add_slot(self):
        if self._count >= MAX_MACROS:
            return
        self._save_current()
        idx = self._count
        self._count += 1
        name = f'Macro {idx + 1}'
        self._slot_data[idx] = {'name': name, 'rows': []}
        self._list.blockSignals(True)
        self._list.addItem(f'F{idx + 1}: {name}')
        self._list.blockSignals(False)
        self._switch_to(idx)

    def _remove_slot(self):
        if self._count <= MIN_MACROS:
            return
        self._save_current()
        self._count -= 1
        self._list.blockSignals(True)
        self._list.takeItem(self._count)
        self._list.blockSignals(False)
        if self._current >= self._count:
            self._current = self._count - 1
        self._switch_to(self._current)

    def _save_current(self):
        self._slot_data[self._current] = {
            'name': self._name_edit.text(),
            'rows': self.table.get_rows(),
        }

    def _on_name_changed(self, text: str):
        self._slot_data[self._current]['name'] = text
        item = self._list.item(self._current)
        if item:
            item.setText(f'F{self._current + 1}: {text}')

    # ── Run / Stop ─────────────────────────────────────────────

    def _run_current(self):
        self._run_slot(self._current)

    def _run_slot(self, idx: int):
        if idx >= self._count:
            return
        if idx != self._current:
            self._switch_to(idx)
        self._save_current()
        rows = self.table.get_rows()
        if not rows:
            return
        if self._runner and self._runner.isRunning():
            self._runner.abort()
            self._runner.wait()

        from .comm_handlers import _encode_escape
        parsed = [(_encode_escape(msg), delay) for msg, delay in rows]

        self._runner = MacroRunner(parsed, self._do_send, self)
        self._runner.row_started.connect(self.table.highlight_row)
        self._runner.finished_all.connect(self._on_run_done)
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._runner.start()

    def _stop_current(self):
        if self._runner:
            self._runner.abort()

    def _on_run_done(self):
        self.table.highlight_row(-1)
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _do_send(self, data: bytes):
        self.send_requested.emit(data)

    # ── Serialization ──────────────────────────────────────────

    def get_all_data(self) -> list:
        self._save_current()
        return {'slots': list(self._slot_data), 'count': self._count}

    def set_all_data(self, data):
        if isinstance(data, dict):
            slots = data.get('slots', [])
            self._count = max(MIN_MACROS, min(MAX_MACROS, data.get('count', MIN_MACROS)))
        else:
            slots = data
            self._count = min(MAX_MACROS, max(MIN_MACROS, len(slots)))
        for i in range(MAX_MACROS):
            if i < len(slots):
                self._slot_data[i] = slots[i]
        if self._current >= self._count:
            self._current = self._count - 1
        self._populate_list()
        self._switch_to(self._current)

    # ── Export / Import ─────────────────────────────────────────

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Macros', 'macros.json', 'JSON (*.json)'
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'macros': self.get_all_data()}, f,
                          ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(self, 'Export Failed', str(e))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Macros', '', 'JSON (*.json)'
        )
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                obj = json.load(f)
            macros = obj.get('macros', obj if isinstance(obj, list) else [])
            self.set_all_data(macros)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            QMessageBox.warning(self, 'Import Failed', str(e))
