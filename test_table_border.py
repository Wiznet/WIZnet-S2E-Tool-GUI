"""
테이블 헤더 하단 경계선 테스트.
실행: uv run python test_table_border.py

각 탭에서 다른 방식을 시도한다.
"""
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)


def _make_base_table() -> QTableWidget:
    t = QTableWidget(3, 2)
    t.setHorizontalHeaderLabels(['Message', 'Delay (ms)'])
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    t.setColumnWidth(1, 90)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.verticalHeader().setVisible(False)
    for r in range(3):
        t.setItem(r, 0, QTableWidgetItem(f'message {r+1}'))
        t.setItem(r, 1, QTableWidgetItem('0'))
    return t


# ── 탭 A: 아무것도 안 한 기본 상태 ─────────────────────────────
def make_tab_a():
    w = QWidget()
    v = QVBoxLayout(w)
    t = _make_base_table()
    v.addWidget(t, 1)
    return w, 'A: 기본'


# ── 탭 B: gridline-color CSS 만 ────────────────────────────────
def make_tab_b():
    w = QWidget()
    v = QVBoxLayout(w)
    t = _make_base_table()
    t.setStyleSheet('QTableWidget { gridline-color: #888; }')
    v.addWidget(t, 1)
    return w, 'B: gridline CSS'


# ── 탭 C: QHeaderView::section border-bottom CSS ───────────────
def make_tab_c():
    w = QWidget()
    v = QVBoxLayout(w)
    t = _make_base_table()
    t.setStyleSheet("""
        QTableWidget { gridline-color: #888; }
        QHeaderView::section {
            background-color: palette(button);
            border: none;
            border-right: 1px solid #888;
            border-bottom: 1px solid #888;
            padding: 2px 4px;
        }
    """)
    v.addWidget(t, 1)
    return w, 'C: header CSS'


# ── 탭 D: paintSection 서브클래스 ─────────────────────────────
class BottomLineHeader(QHeaderView):
    _COLOR = QColor('#888888')

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        painter.save()
        painter.setPen(QPen(self._COLOR, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.restore()


def make_tab_d():
    w = QWidget()
    v = QVBoxLayout(w)
    t = _make_base_table()
    t.setHorizontalHeader(BottomLineHeader(t))
    t.setHorizontalHeaderLabels(['Message', 'Delay (ms)'])
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    t.setColumnWidth(1, 90)
    t.setStyleSheet('QTableWidget { gridline-color: #888; }')
    v.addWidget(t, 1)
    return w, 'D: paintSection'


# ── 탭 E: C + D 조합 ───────────────────────────────────────────
def make_tab_e():
    w = QWidget()
    v = QVBoxLayout(w)
    t = _make_base_table()
    t.setHorizontalHeader(BottomLineHeader(t))
    t.setHorizontalHeaderLabels(['Message', 'Delay (ms)'])
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    t.setColumnWidth(1, 90)
    t.setStyleSheet("""
        QTableWidget { gridline-color: #888; }
        QHeaderView::section {
            background-color: palette(button);
            border: none;
            border-right: 1px solid #888;
            border-bottom: 1px solid #888;
            padding: 2px 4px;
        }
    """)
    v.addWidget(t, 1)
    return w, 'E: CSS + paintSection'


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = QTabWidget()
    win.setWindowTitle('테이블 헤더 하단선 테스트')
    win.resize(500, 300)

    for factory in (make_tab_a, make_tab_b, make_tab_c, make_tab_d, make_tab_e):
        widget, label = factory()
        win.addTab(widget, label)

    win.show()
    sys.exit(app.exec_())
