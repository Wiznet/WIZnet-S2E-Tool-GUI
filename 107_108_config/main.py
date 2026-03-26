"""
107_108_config/main.py
WIZ107SR / WIZ108SR Config Tool — Python/PyQt5 변환

VB.NET frmMain.vb 충실 변환:
  - 검색 (Search All / Direct IP)
  - 설정 적용 (Set)
  - 리셋 / 공장 초기화
  - 모든 UI 필드 (DisplayValue 기준)
  - 응답 길이 체크 없음 — parse_response() 결과만 사용 (VB.NET 원본 방식)

WIZ107SR / WIZ108SR 자동 구분: MN 커맨드 응답값으로만 구분.
프로토콜은 동일하므로 별도 분기 없음.
"""
from __future__ import annotations

import sys
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QRadioButton, QSplitter, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from .sec import (
    BAUD_TABLE, build_set_fields, factory_reset_packet,
    has_valid_mac, parse_response, reset_packet,
    search_packet, set_packet,
)
from .transport import TCPWorker, UDPWorker

# ── 네트워크 인터페이스 목록 ─────────────────────────────────────────────────

def _load_ips() -> list[tuple[str, str]]:
    """(ip, label) 목록 반환."""
    try:
        import ifaddr
        rows: list[tuple[int, tuple, str, str]] = []
        virtual_kw = ["virtualbox", "vmware", "hyper-v", "docker", "wsl",
                       "tap", "npcap", "virtual", "vbox", "bridge", "loopback"]
        for adapter in ifaddr.get_adapters():
            for ip_info in adapter.ips:
                ip = ip_info.ip
                if not isinstance(ip, str):
                    continue
                if ip == "127.0.0.1":
                    continue
                parts = ip.split(".")
                if len(parts) != 4:
                    continue
                try:
                    ip_tuple = tuple(int(p) for p in parts)
                except ValueError:
                    continue
                name_lower = adapter.nice_name.lower()
                is_virtual = any(kw in name_lower for kw in virtual_kw)
                pri = 2 if ip.startswith("169.254.") else (1 if is_virtual else 0)
                rows.append((pri, ip_tuple, ip, f"{ip}  ({adapter.nice_name})"))
        rows.sort(key=lambda r: (r[0], r[1]))
        return [(ip, lbl) for _, _, ip, lbl in rows] if rows else []
    except Exception:
        import socket
        try:
            hostname = socket.gethostname()
            seen: set[str] = set()
            result: list[tuple[str, str]] = []
            for info in socket.getaddrinfo(hostname, None):
                if info[0].name == "AF_INET":
                    ip = info[4][0]
                    if ip not in seen and ip != "127.0.0.1":
                        seen.add(ip)
                        result.append((ip, ip))
            return result
        except Exception:
            return []


# ── 장치 목록 아이템 ─────────────────────────────────────────────────────────

class DeviceItem(QListWidgetItem):
    """장치 목록 한 항목. fields: parse_response() 반환 dict."""

    def __init__(self, fields: dict[str, str]) -> None:
        mac  = fields.get("MC", "??:??:??:??:??:??")
        mn   = fields.get("MN", "Unknown")
        ip   = fields.get("LI", "?")
        ver  = fields.get("VR", "?")
        super().__init__(f"{mac}  │  {mn}  │  {ip}  │  v{ver}")
        self.fields = fields


# ── 메인 윈도우 ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """WIZ107SR / WIZ108SR Config Tool 메인 윈도우."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WIZ107SR / WIZ108SR Configuration Tool")
        self.resize(960, 700)

        self._ips = _load_ips()
        self._src_ip: str = self._ips[0][0] if self._ips else ""
        self._worker: Optional[UDPWorker | TCPWorker] = None
        self._selected_fields: dict[str, str] = {}   # 현재 선택 장치
        self._search_pwd: str = " "
        self._direct_ip: str = ""
        self._is_broadcast: bool = True

        self._build_ui()
        self._set_controls_enabled(False)

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # 좌측: 장치 목록 + 툴바
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self._build_toolbar())
        lv.addWidget(QLabel("Discovered devices:"))
        self._lst_devices = QListWidget()
        self._lst_devices.currentItemChanged.connect(self._on_device_selected)
        lv.addWidget(self._lst_devices)
        splitter.addWidget(left)

        # 우측: 설정 탭
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        self._build_tab_network()
        self._build_tab_serial()
        self._build_tab_options()
        self._build_tab_ddns()
        rv.addWidget(self._tabs)

        # Apply / Reset / Factory 버튼
        rv.addWidget(self._build_action_buttons())
        splitter.addWidget(right)
        splitter.setSizes([340, 620])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)

        # NIC 선택
        h.addWidget(QLabel("Interface:"))
        self._cmb_nic = QComboBox()
        for ip, lbl in self._ips:
            self._cmb_nic.addItem(lbl, ip)
        self._cmb_nic.currentIndexChanged.connect(self._on_nic_changed)
        h.addWidget(self._cmb_nic)

        # 검색 모드
        self._rb_broadcast = QRadioButton("Broadcast")
        self._rb_broadcast.setChecked(True)
        self._rb_broadcast.toggled.connect(lambda c: setattr(self, "_is_broadcast", c))
        h.addWidget(self._rb_broadcast)
        self._rb_direct = QRadioButton("Direct IP:")
        h.addWidget(self._rb_direct)
        self._edit_direct_ip = QLineEdit()
        self._edit_direct_ip.setPlaceholderText("192.168.x.x")
        self._edit_direct_ip.setFixedWidth(120)
        h.addWidget(self._edit_direct_ip)

        # 검색 패스워드
        h.addWidget(QLabel("Search Pwd:"))
        self._edit_sch_pwd = QLineEdit()
        self._edit_sch_pwd.setPlaceholderText("(empty = space)")
        self._edit_sch_pwd.setFixedWidth(100)
        h.addWidget(self._edit_sch_pwd)

        # 검색 버튼
        self._btn_search = QPushButton("Search")
        self._btn_search.clicked.connect(self._do_search)
        h.addWidget(self._btn_search)

        h.addStretch()
        return w

    # ── Network 탭 ──────────────────────────────────────────────────────────

    def _build_tab_network(self) -> None:
        tab = QWidget()
        g = QGridLayout(tab)

        # 장치 정보 (읽기 전용)
        g.addWidget(QLabel("MAC:"), 0, 0)
        self._lbl_mac = QLabel("—")
        g.addWidget(self._lbl_mac, 0, 1)
        g.addWidget(QLabel("Model:"), 0, 2)
        self._lbl_model = QLabel("—")
        g.addWidget(self._lbl_model, 0, 3)
        g.addWidget(QLabel("Version:"), 0, 4)
        self._lbl_ver = QLabel("—")
        g.addWidget(self._lbl_ver, 0, 5)

        # IP Mode
        g.addWidget(QLabel("IP Mode:"), 1, 0)
        im_box = QWidget()
        im_h = QHBoxLayout(im_box)
        im_h.setContentsMargins(0, 0, 0, 0)
        self._rb_static = QRadioButton("Static")
        self._rb_dhcp   = QRadioButton("DHCP")
        self._rb_ppp    = QRadioButton("PPPoE")
        self._rb_static.setChecked(True)
        self._rb_static.toggled.connect(self._on_ip_mode_changed)
        self._rb_dhcp.toggled.connect(self._on_ip_mode_changed)
        self._rb_ppp.toggled.connect(self._on_ip_mode_changed)
        for rb in (self._rb_static, self._rb_dhcp, self._rb_ppp):
            im_h.addWidget(rb)
        im_h.addStretch()
        g.addWidget(im_box, 1, 1, 1, 5)

        for row, (lbl, attr) in enumerate([
            ("Local IP:",  "_edit_li"),
            ("Subnet:",    "_edit_sm"),
            ("Gateway:",   "_edit_gw"),
            ("DNS:",       "_edit_ds"),
        ], start=2):
            g.addWidget(QLabel(lbl), row, 0)
            edit = QLineEdit()
            setattr(self, attr, edit)
            g.addWidget(edit, row, 1, 1, 2)

        # PPPoE
        g.addWidget(QLabel("PPPoE ID:"), 6, 0)
        self._edit_pi = QLineEdit()
        g.addWidget(self._edit_pi, 6, 1, 1, 2)
        g.addWidget(QLabel("PPPoE Pwd:"), 7, 0)
        self._edit_pp = QLineEdit()
        self._edit_pp.setEchoMode(QLineEdit.Password)
        g.addWidget(self._edit_pp, 7, 1, 1, 2)

        # Local Port
        g.addWidget(QLabel("Local Port:"), 8, 0)
        self._edit_lp = QLineEdit()
        g.addWidget(self._edit_lp, 8, 1)

        # Operation Mode
        g.addWidget(QLabel("Op Mode:"), 9, 0)
        op_box = QWidget()
        op_h = QHBoxLayout(op_box)
        op_h.setContentsMargins(0, 0, 0, 0)
        self._rb_client = QRadioButton("Client")
        self._rb_server = QRadioButton("Server")
        self._rb_mixed  = QRadioButton("Mixed")
        self._rb_udp    = QRadioButton("UDP")
        self._rb_client.setChecked(True)
        self._rb_client.toggled.connect(self._on_op_mode_changed)
        self._rb_server.toggled.connect(self._on_op_mode_changed)
        self._rb_mixed.toggled.connect(self._on_op_mode_changed)
        self._rb_udp.toggled.connect(self._on_op_mode_changed)
        for rb in (self._rb_client, self._rb_server, self._rb_mixed, self._rb_udp):
            op_h.addWidget(rb)
        op_h.addStretch()
        g.addWidget(op_box, 9, 1, 1, 5)

        g.addWidget(QLabel("Remote Host:"), 10, 0)
        self._edit_rh = QLineEdit()
        g.addWidget(self._edit_rh, 10, 1, 1, 2)
        g.addWidget(QLabel("Remote Port:"), 11, 0)
        self._edit_rp = QLineEdit()
        g.addWidget(self._edit_rp, 11, 1)
        g.addWidget(QLabel("Reconnect(ms):"), 12, 0)
        self._edit_ri = QLineEdit()
        g.addWidget(self._edit_ri, 12, 1)

        # Network Protocol (PO)
        g.addWidget(QLabel("Net Protocol:"), 13, 0)
        po_box = QWidget()
        po_h = QHBoxLayout(po_box)
        po_h.setContentsMargins(0, 0, 0, 0)
        self._rb_raw    = QRadioButton("Raw (TCP)")
        self._rb_telnet = QRadioButton("Telnet")
        self._rb_raw.setChecked(True)
        po_h.addWidget(self._rb_raw)
        po_h.addWidget(self._rb_telnet)
        po_h.addStretch()
        g.addWidget(po_box, 13, 1, 1, 3)

        # Connection Password
        g.addWidget(QLabel("Conn Pwd:"), 14, 0)
        cp_box = QWidget()
        cp_h = QHBoxLayout(cp_box)
        cp_h.setContentsMargins(0, 0, 0, 0)
        self._chk_cp = QCheckBox("Enable")
        self._chk_cp.toggled.connect(lambda c: self._edit_np.setEnabled(c))
        self._edit_np = QLineEdit()
        self._edit_np.setEchoMode(QLineEdit.Password)
        self._edit_np.setEnabled(False)
        cp_h.addWidget(self._chk_cp)
        cp_h.addWidget(self._edit_np)
        cp_h.addStretch()
        g.addWidget(cp_box, 14, 1, 1, 3)

        g.setRowStretch(15, 1)
        self._tabs.addTab(tab, "Network")

    # ── Serial 탭 ────────────────────────────────────────────────────────────

    def _build_tab_serial(self) -> None:
        tab = QWidget()
        g = QGridLayout(tab)

        baud_items  = [str(b) for b in BAUD_TABLE]
        db_items    = ["7-bit", "8-bit", "9-bit"]
        parity_items = ["None", "Odd", "Even"]
        stop_items  = ["1-bit", "2-bit"]
        flow_items  = ["None", "XON/XOFF", "CTS/RTS"]

        def _cmb(items: list[str]) -> QComboBox:
            c = QComboBox()
            c.addItems(items)
            return c

        g.addWidget(QLabel("Baud Rate:"),  0, 0)
        self._cmb_br = _cmb(baud_items)
        self._cmb_br.setCurrentIndex(6)   # 9600 default
        g.addWidget(self._cmb_br, 0, 1)

        g.addWidget(QLabel("Data Bit:"),   1, 0)
        self._cmb_db = _cmb(db_items)
        self._cmb_db.setCurrentIndex(1)   # 8-bit default
        self._cmb_db.currentIndexChanged.connect(self._on_db_changed)
        g.addWidget(self._cmb_db, 1, 1)

        g.addWidget(QLabel("Parity:"),     2, 0)
        self._cmb_pr = _cmb(parity_items)
        self._cmb_pr.currentIndexChanged.connect(self._on_parity_changed)
        g.addWidget(self._cmb_pr, 2, 1)

        g.addWidget(QLabel("Stop Bit:"),   3, 0)
        self._cmb_sb = _cmb(stop_items)
        self._cmb_sb.currentIndexChanged.connect(self._on_sb_changed)
        g.addWidget(self._cmb_sb, 3, 1)

        g.addWidget(QLabel("Flow Ctrl:"),  4, 0)
        self._cmb_fl = _cmb(flow_items)
        g.addWidget(self._cmb_fl, 4, 1)

        # Data Packing
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        g.addWidget(sep, 5, 0, 1, 2)
        g.addWidget(QLabel("Pack Timer(ms):"), 6, 0)
        self._edit_pt = QLineEdit("0")
        g.addWidget(self._edit_pt, 6, 1)
        g.addWidget(QLabel("Pack Size:"), 7, 0)
        self._edit_ps = QLineEdit("0")
        g.addWidget(self._edit_ps, 7, 1)
        g.addWidget(QLabel("Pack Char(hex):"), 8, 0)
        self._edit_pd = QLineEdit("00")
        g.addWidget(self._edit_pd, 8, 1)

        g.setRowStretch(9, 1)
        self._tabs.addTab(tab, "Serial")

    # ── Options 탭 ───────────────────────────────────────────────────────────

    def _build_tab_options(self) -> None:
        tab = QWidget()
        g = QGridLayout(tab)

        g.addWidget(QLabel("Inactive Timer(ms):"), 0, 0)
        self._edit_it = QLineEdit("0")
        g.addWidget(self._edit_it, 0, 1)

        # Keep Alive
        self._chk_ka = QCheckBox("Keep Alive")
        self._chk_ka.toggled.connect(self._on_ka_changed)
        g.addWidget(self._chk_ka, 1, 0)
        g.addWidget(QLabel("Initial Interval(ms):"), 2, 0)
        self._edit_ki = QLineEdit("7000")
        self._edit_ki.setEnabled(False)
        g.addWidget(self._edit_ki, 2, 1)
        g.addWidget(QLabel("Retry Interval(ms):"), 3, 0)
        self._edit_ke = QLineEdit("1000")
        self._edit_ke.setEnabled(False)
        g.addWidget(self._edit_ke, 3, 1)

        # Debug
        self._chk_dg = QCheckBox("Debug Message")
        g.addWidget(self._chk_dg, 4, 0)

        # Trigger
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        g.addWidget(sep, 5, 0, 1, 2)
        self._chk_te = QCheckBox("Software Trigger")
        self._chk_te.toggled.connect(self._on_te_changed)
        g.addWidget(self._chk_te, 6, 0)
        trig_box = QWidget()
        th = QHBoxLayout(trig_box)
        th.setContentsMargins(0, 0, 0, 0)
        self._edit_ss1 = QLineEdit()
        self._edit_ss1.setPlaceholderText("XX")
        self._edit_ss1.setFixedWidth(40)
        self._edit_ss1.setEnabled(False)
        self._edit_ss2 = QLineEdit()
        self._edit_ss2.setPlaceholderText("XX")
        self._edit_ss2.setFixedWidth(40)
        self._edit_ss2.setEnabled(False)
        self._edit_ss3 = QLineEdit()
        self._edit_ss3.setPlaceholderText("XX")
        self._edit_ss3.setFixedWidth(40)
        self._edit_ss3.setEnabled(False)
        for e in (self._edit_ss1, self._edit_ss2, self._edit_ss3):
            th.addWidget(e)
        th.addStretch()
        g.addWidget(trig_box, 6, 1)

        # Search Password
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        g.addWidget(sep2, 7, 0, 1, 2)
        g.addWidget(QLabel("Search Password:"), 8, 0)
        self._edit_sp = QLineEdit()
        g.addWidget(self._edit_sp, 8, 1)

        g.setRowStretch(9, 1)
        self._tabs.addTab(tab, "Options")

    # ── DDNS 탭 ──────────────────────────────────────────────────────────────

    def _build_tab_ddns(self) -> None:
        tab = QWidget()
        g = QGridLayout(tab)

        self._chk_dd = QCheckBox("Enable DDNS")
        self._chk_dd.toggled.connect(self._on_ddns_changed)
        g.addWidget(self._chk_dd, 0, 0, 1, 2)

        ddns_servers = ["DynDNS", "NO-IP", "Changeip", "DNS-O-MATIC",
                        "ZoneEdit", "Namecheap", "3322.org"]
        g.addWidget(QLabel("DDNS Server:"), 1, 0)
        self._cmb_dx = QComboBox()
        self._cmb_dx.addItems(ddns_servers)
        self._cmb_dx.setEnabled(False)
        g.addWidget(self._cmb_dx, 1, 1)

        g.addWidget(QLabel("Server Port:"), 2, 0)
        self._edit_dp = QLineEdit()
        self._edit_dp.setEnabled(False)
        g.addWidget(self._edit_dp, 2, 1)

        g.addWidget(QLabel("DDNS ID:"), 3, 0)
        self._edit_di = QLineEdit()
        self._edit_di.setEnabled(False)
        g.addWidget(self._edit_di, 3, 1)

        g.addWidget(QLabel("DDNS Password:"), 4, 0)
        self._edit_dw = QLineEdit()
        self._edit_dw.setEchoMode(QLineEdit.Password)
        self._edit_dw.setEnabled(False)
        g.addWidget(self._edit_dw, 4, 1)

        g.addWidget(QLabel("Domain Host:"), 5, 0)
        self._edit_dh = QLineEdit()
        self._edit_dh.setEnabled(False)
        g.addWidget(self._edit_dh, 5, 1)

        g.setRowStretch(6, 1)
        self._tabs.addTab(tab, "DDNS")

    def _build_action_buttons(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 4, 0, 0)

        self._btn_set     = QPushButton("Apply Settings")
        self._btn_reset   = QPushButton("Reset Device")
        self._btn_factory = QPushButton("Factory Reset")

        self._btn_set.clicked.connect(self._do_set)
        self._btn_reset.clicked.connect(self._do_reset)
        self._btn_factory.clicked.connect(self._do_factory_reset)

        for b in (self._btn_set, self._btn_reset, self._btn_factory):
            h.addWidget(b)
        h.addStretch()
        return w

    # ── UI 이벤트 핸들러 ──────────────────────────────────────────────────────

    def _on_nic_changed(self, idx: int) -> None:
        self._src_ip = self._cmb_nic.itemData(idx) or ""

    def _on_ip_mode_changed(self) -> None:
        is_static = self._rb_static.isChecked()
        is_ppp    = self._rb_ppp.isChecked()
        for e in (self._edit_li, self._edit_sm, self._edit_gw, self._edit_ds):
            e.setEnabled(is_static)
        self._edit_pi.setEnabled(is_ppp)
        self._edit_pp.setEnabled(is_ppp)

    def _on_op_mode_changed(self) -> None:
        is_client = self._rb_client.isChecked()
        is_mixed  = self._rb_mixed.isChecked()
        is_udp    = self._rb_udp.isChecked()
        needs_rh  = is_client or is_mixed or is_udp
        self._edit_rh.setEnabled(needs_rh)
        self._edit_rp.setEnabled(needs_rh)
        self._edit_ri.setEnabled(is_client or is_mixed)

    def _on_ka_changed(self, checked: bool) -> None:
        self._edit_ki.setEnabled(checked)
        self._edit_ke.setEnabled(checked)

    def _on_te_changed(self, checked: bool) -> None:
        for e in (self._edit_ss1, self._edit_ss2, self._edit_ss3):
            e.setEnabled(checked)

    def _on_ddns_changed(self, checked: bool) -> None:
        for w in (self._cmb_dx, self._edit_dp, self._edit_di,
                  self._edit_dw, self._edit_dh):
            w.setEnabled(checked)

    def _on_db_changed(self, idx: int) -> None:
        """DB=2 (9-bit): PR=None 고정, SB=1 고정 (WIZ107/108 제약)."""
        if idx == 2:  # 9-bit
            self._cmb_pr.setCurrentIndex(0)
            self._cmb_pr.setEnabled(False)
            self._cmb_sb.setCurrentIndex(0)
            self._cmb_sb.setEnabled(False)
        else:
            self._cmb_pr.setEnabled(True)
            self._cmb_sb.setEnabled(True)

    def _on_parity_changed(self, idx: int) -> None:
        """PR=ODD/EVEN: DB에서 9-bit 제거."""
        if idx > 0:  # ODD or EVEN
            if self._cmb_db.count() == 3:
                self._cmb_db.removeItem(2)   # 9-bit 항목 제거
        else:
            if self._cmb_db.count() == 2:
                self._cmb_db.addItem("9-bit")

    def _on_sb_changed(self, idx: int) -> None:
        """SB=2: DB에서 9-bit 제거, PR에서 ODD/EVEN 제거."""
        if idx == 1:  # 2-bit
            if self._cmb_db.count() == 3:
                self._cmb_db.removeItem(2)
            while self._cmb_pr.count() > 1:
                self._cmb_pr.removeItem(self._cmb_pr.count() - 1)
        else:
            if self._cmb_db.count() == 2:
                self._cmb_db.addItem("9-bit")
            if self._cmb_pr.count() == 1:
                self._cmb_pr.addItems(["Odd", "Even"])

    # ── 장치 선택 ─────────────────────────────────────────────────────────────

    def _on_device_selected(self, current: QListWidgetItem, _prev) -> None:
        if not isinstance(current, DeviceItem):
            return
        self._selected_fields = current.fields
        self._display_value(current.fields)
        self._set_controls_enabled(True)

    def _display_value(self, f: dict[str, str]) -> None:
        """frmMain.DisplayValue() 변환: dict → UI 채우기."""
        # 장치 정보
        self._lbl_mac.setText(f.get("MC", "—"))
        self._lbl_model.setText(f.get("MN", "—"))
        self._lbl_ver.setText(f.get("VR", "—"))

        # IP Mode
        im = f.get("IM", "0")
        if im == "0":
            self._rb_static.setChecked(True)
        elif im == "1":
            self._rb_dhcp.setChecked(True)
        else:
            self._rb_ppp.setChecked(True)
        self._edit_li.setText(f.get("LI", ""))
        self._edit_sm.setText(f.get("SM", ""))
        self._edit_gw.setText(f.get("GW", ""))
        self._edit_ds.setText(f.get("DS", ""))
        self._edit_pi.setText(f.get("PI", "").strip())
        self._edit_pp.setText(f.get("PP", "").strip())
        self._edit_lp.setText(f.get("LP", ""))
        self._on_ip_mode_changed()

        # Op Mode
        op = f.get("OP", "0")
        {"0": self._rb_client, "1": self._rb_server,
         "2": self._rb_mixed,  "3": self._rb_udp}.get(op, self._rb_client).setChecked(True)
        self._edit_rh.setText(f.get("RH", ""))
        self._edit_rp.setText(f.get("RP", ""))
        self._edit_ri.setText(f.get("RI", ""))
        self._on_op_mode_changed()

        # Network Protocol (PO)
        if f.get("PO", "0") == "1":
            self._rb_telnet.setChecked(True)
        else:
            self._rb_raw.setChecked(True)

        # Connection Password (CP/NP)
        cp = f.get("CP", "0") == "1"
        self._chk_cp.setChecked(cp)
        self._edit_np.setText(f.get("NP", "").strip())
        self._edit_np.setEnabled(cp)

        # DDNS
        dd = f.get("DD", "0") == "1"
        self._chk_dd.setChecked(dd)
        try:
            self._cmb_dx.setCurrentIndex(int(f.get("DX", "0")))
        except ValueError:
            pass
        self._edit_dp.setText(f.get("DP", ""))
        self._edit_di.setText(f.get("DI", ""))
        self._edit_dw.setText(f.get("DW", "").strip())
        self._edit_dh.setText("")  # VB.NET 원본도 항상 빈칸으로 표시

        # Serial
        try:
            self._cmb_br.setCurrentIndex(int(f.get("BR", "6")))
        except ValueError:
            pass
        try:
            self._cmb_db.setCurrentIndex(int(f.get("DB", "1")))
        except ValueError:
            pass
        try:
            self._cmb_pr.setCurrentIndex(int(f.get("PR", "0")))
        except ValueError:
            pass
        try:
            self._cmb_sb.setCurrentIndex(int(f.get("SB", "0")))
        except ValueError:
            pass
        try:
            self._cmb_fl.setCurrentIndex(int(f.get("FL", "0")))
        except ValueError:
            pass

        # Debug
        self._chk_dg.setChecked(f.get("DG", "0") == "1")

        # Data packing
        self._edit_pt.setText(f.get("PT", "0"))
        self._edit_ps.setText(f.get("PS", "0"))
        self._edit_pd.setText(f.get("PD", "00"))

        # Options
        self._edit_it.setText(f.get("IT", "0"))
        self._edit_ri.setText(f.get("RI", "0"))

        # Keep Alive
        ka = f.get("KA", "0") == "1"
        self._chk_ka.setChecked(ka)
        self._edit_ki.setText(f.get("KI", "7000"))
        self._edit_ke.setText(f.get("KE", "1000"))
        self._edit_ki.setEnabled(ka)
        self._edit_ke.setEnabled(ka)

        # Trigger
        te = f.get("TE", "0") == "1"
        self._chk_te.setChecked(te)
        ss = f.get("SS", "000000")
        if len(ss) >= 6:
            self._edit_ss1.setText(ss[0:2])
            self._edit_ss2.setText(ss[2:4])
            self._edit_ss3.setText(ss[4:6])
        for e in (self._edit_ss1, self._edit_ss2, self._edit_ss3):
            e.setEnabled(te)

        # Search Password
        self._edit_sp.setText(f.get("SP", "").strip())

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (self._tabs, self._btn_set, self._btn_reset, self._btn_factory):
            w.setEnabled(enabled)

    # ── 검색 ──────────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        self._stop_worker()
        pwd = self._edit_sch_pwd.text().strip() or " "
        self._search_pwd = pwd
        self._lst_devices.clear()
        self._set_controls_enabled(False)
        self.statusBar().showMessage("Searching...")

        if self._rb_broadcast.isChecked():
            pkt = search_packet(pwd=pwd)
            self._worker = UDPWorker(self._src_ip, pkt, timeout=3.0)
        else:
            direct_ip = self._edit_direct_ip.text().strip()
            if not direct_ip:
                QMessageBox.warning(self, "Error", "Please input direct IP address.")
                return
            self._direct_ip = direct_ip
            pkt = search_packet(pwd=pwd)
            self._worker = TCPWorker(direct_ip, pkt, timeout=3.0)

        self._worker.data_arrived.connect(self._on_search_data)
        self._worker.finished.connect(self._on_search_done)
        self._worker.error.connect(lambda e: self.statusBar().showMessage(f"Error: {e}"))
        self._worker.start()

    def _on_search_data(self, data: bytes) -> None:
        """응답 도착 → parse → 장치 목록에 추가 (MAC 유효하면)."""
        fields = parse_response(data)
        if has_valid_mac(fields):
            # 기존 항목 교체 또는 신규 추가
            for i in range(self._lst_devices.count()):
                item = self._lst_devices.item(i)
                if isinstance(item, DeviceItem) and item.fields.get("MC") == fields.get("MC"):
                    item.fields = fields
                    item.setText(DeviceItem(fields).text())
                    return
            self._lst_devices.addItem(DeviceItem(fields))

    def _on_search_done(self) -> None:
        count = self._lst_devices.count()
        self.statusBar().showMessage(f"Found: {count} device(s)")

    # ── 설정 적용 ─────────────────────────────────────────────────────────────

    def _do_set(self) -> None:
        if not self._selected_fields:
            return
        fields = self._collect_set_fields()
        if fields is None:
            return   # validation failed

        mac = self._selected_fields.get("MC", "FF:FF:FF:FF:FF:FF")
        sp  = self._edit_sp.text().strip() or " "
        pkt = set_packet(mac, fields, pwd=sp)

        self._stop_worker()
        self.statusBar().showMessage("Applying settings...")
        self._btn_set.setEnabled(False)

        if self._rb_broadcast.isChecked():
            self._worker = UDPWorker(self._src_ip, pkt, timeout=3.0)
        else:
            target_ip = self._selected_fields.get("LI", self._direct_ip)
            self._worker = TCPWorker(target_ip, pkt, timeout=3.0)

        self._worker.data_arrived.connect(self._on_set_data)
        self._worker.finished.connect(self._on_set_done)
        self._worker.error.connect(lambda e: self.statusBar().showMessage(f"Error: {e}"))
        self._worker.start()

    def _on_set_data(self, data: bytes) -> None:
        """
        SET 응답 수신.
        VB.NET 원본과 동일: 응답 길이 체크 없음. MAC 유효하면 UI 갱신.
        """
        fields = parse_response(data)
        if has_valid_mac(fields):
            self._selected_fields = fields
            self._display_value(fields)
            # 장치 목록도 갱신
            for i in range(self._lst_devices.count()):
                item = self._lst_devices.item(i)
                if isinstance(item, DeviceItem) and item.fields.get("MC") == fields.get("MC"):
                    item.fields = fields
                    item.setText(DeviceItem(fields).text())
                    break
            self.statusBar().showMessage("Settings applied successfully.")
        elif fields.get("ER"):
            QMessageBox.warning(self, "Device Error", fields["ER"])

    def _on_set_done(self) -> None:
        self._btn_set.setEnabled(True)
        # 응답이 없었던 경우 (IM 변경 등 즉시 리부트 시)에도 성공 메시지
        if "Applying" in self.statusBar().currentMessage():
            self.statusBar().showMessage(
                "Command sent. Device may have rebooted. Re-search to verify."
            )

    # ── 리셋 / 공장 초기화 ────────────────────────────────────────────────────

    def _do_reset(self) -> None:
        if not self._selected_fields:
            return
        ret = QMessageBox.question(self, "Reset Device",
                                   "Do you really want to reset the selected device?")
        if ret != QMessageBox.Yes:
            return
        mac = self._selected_fields.get("MC", "")
        sp  = self._edit_sp.text().strip() or " "
        pkt = reset_packet(mac, sp)
        self._send_command_packet(pkt)
        self.statusBar().showMessage("Reset command sent.")

    def _do_factory_reset(self) -> None:
        if not self._selected_fields:
            return
        ret = QMessageBox.question(self, "Factory Reset",
                                   "This will erase all settings. Continue?")
        if ret != QMessageBox.Yes:
            return
        mac = self._selected_fields.get("MC", "")
        sp  = self._edit_sp.text().strip() or " "
        pkt = factory_reset_packet(mac, sp)
        self._send_command_packet(pkt)
        self.statusBar().showMessage("Factory reset command sent.")

    def _send_command_packet(self, pkt: bytes) -> None:
        self._stop_worker()
        if self._rb_broadcast.isChecked():
            self._worker = UDPWorker(self._src_ip, pkt, timeout=1.0)
        else:
            target_ip = self._selected_fields.get("LI", self._direct_ip)
            self._worker = TCPWorker(target_ip, pkt, timeout=1.0)
        self._worker.finished.connect(lambda: None)
        self._worker.start()

    # ── CalcSetMsg 변환 ───────────────────────────────────────────────────────

    def _collect_set_fields(self) -> dict[str, str] | None:
        """
        UI 값 수집 + 유효성 검사 → SET 필드 dict 반환.
        실패 시 에러 메시지 표시 후 None 반환.
        frmMain.CalcSetMsg() 완전 변환.
        """
        def _ip_ok(ip: str) -> bool:
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            try:
                return all(0 <= int(p) <= 255 for p in parts)
            except ValueError:
                return False

        def _num_ok(s: str, lo: int, hi: int) -> bool:
            try:
                return lo <= int(s) <= hi
            except ValueError:
                return False

        def _err(msg: str) -> None:
            QMessageBox.critical(self, "Error", msg)

        im = "0" if self._rb_static.isChecked() else \
             "1" if self._rb_dhcp.isChecked() else "2"

        li = sm = gw = ds = ""
        if im == "0":
            li = self._edit_li.text().strip()
            if not _ip_ok(li):
                _err("Please input a valid IP address."); return None
            sm = self._edit_sm.text().strip()
            if not _ip_ok(sm):
                _err("Please input a correct subnet mask."); return None
            gw = self._edit_gw.text().strip()
            if not _ip_ok(gw):
                _err("Please input a correct gateway IP address."); return None
            ds = self._edit_ds.text().strip()
            if not _ip_ok(ds):
                _err("Please input a valid DNS server IP address."); return None

        pi = pp = ""
        if im == "2":
            pi = self._edit_pi.text().strip()
            if not pi:
                _err("Please input your PPPoE ID."); return None
            pp = self._edit_pp.text().strip()
            if not pp:
                _err("Please input your PPPoE password."); return None

        lp = self._edit_lp.text().strip()
        if not _num_ok(lp, 1, 65535):
            _err("Please input a valid port number (1~65535)."); return None

        op = "0" if self._rb_client.isChecked() else \
             "1" if self._rb_server.isChecked() else \
             "2" if self._rb_mixed.isChecked() else "3"

        rh = rp = ri = ""
        if op in ("0", "2", "3"):
            rh = self._edit_rh.text().strip()
            if not rh:
                _err("Please input remote host IP/domain name."); return None
            rp = self._edit_rp.text().strip()
            if not _num_ok(rp, 1, 65535):
                _err("Please input a port number between 1 and 65535."); return None
        if op in ("0", "2"):
            ri = self._edit_ri.text().strip()
            if not _num_ok(ri, 0 if op == "2" else 1, 65535):
                _err("Reconnection interval should be between 1 and 65535."); return None

        cp = "1" if self._chk_cp.isChecked() else "0"
        np_val = ""
        if cp == "1":
            np_val = self._edit_np.text().strip()
            if not np_val:
                _err("Please input the connection password or disable it."); return None

        dd = "1" if self._chk_dd.isChecked() else "0"
        dx = dp = di = dw = dh = ""
        if dd == "1":
            dx = str(self._cmb_dx.currentIndex())
            dp = self._edit_dp.text().strip()
            if not _num_ok(dp, 1, 65535):
                _err("The DDNS server port should be between 1 and 65535."); return None
            di = self._edit_di.text().strip()
            if not di:
                _err("Please input your DDNS ID."); return None
            dw = self._edit_dw.text().strip()
            if not dw:
                _err("Please input your DDNS password."); return None
            dh = self._edit_dh.text().strip()
            if not dh:
                _err("Please input your DDNS domain name."); return None

        po = "1" if self._rb_telnet.isChecked() else "0"
        dg = "1" if self._chk_dg.isChecked() else "0"

        br = str(self._cmb_br.currentIndex())
        db = str(self._cmb_db.currentIndex())
        pr = str(self._cmb_pr.currentIndex())
        sb = str(self._cmb_sb.currentIndex())
        fl = str(self._cmb_fl.currentIndex())

        pt = self._edit_pt.text().strip()
        if not _num_ok(pt, 0, 65535):
            _err("The serial data packing interval should be between 0 and 65535."); return None
        ps = self._edit_ps.text().strip()
        if not _num_ok(ps, 0, 255):
            _err("The packing size of serial data should be between 0 and 255."); return None
        pd_val = self._edit_pd.text().strip()
        try:
            if not (0 <= int(pd_val, 16) <= 255):
                raise ValueError
        except ValueError:
            _err("Please input the packing character indicator in hex (00~FF)."); return None

        it = self._edit_it.text().strip()
        if not _num_ok(it, 0, 65535):
            _err("The inactive timer should be between 0 and 65535."); return None

        te = "1" if self._chk_te.isChecked() else "0"
        ss = ""
        if te == "1":
            s1 = self._edit_ss1.text().strip().zfill(2)
            s2 = self._edit_ss2.text().strip().zfill(2)
            s3 = self._edit_ss3.text().strip().zfill(2)
            if len(s1) != 2 or len(s2) != 2 or len(s3) != 2:
                _err("Please input software trigger code (2-digit hex each)."); return None
            ss = s1 + s2 + s3

        sp = self._edit_sp.text().strip() or " "
        ka = "1" if self._chk_ka.isChecked() else "0"
        ki = self._edit_ki.text().strip()
        ke = self._edit_ke.text().strip()

        return build_set_fields(
            im=im, li=li, sm=sm, gw=gw, ds=ds,
            pi=pi, pp=pp, lp=lp,
            op=op, rh=rh, rp=rp, ri=ri,
            cp=cp, np_val=np_val,
            dd=dd, dx=dx, dp=dp, di=di, dw=dw, dh=dh,
            po=po, dg=dg,
            br=br, db=db, pr=pr, sb=sb, fl=fl,
            pt=pt, ps=ps, pd=pd_val,
            it=it, te=te, ss=ss,
            sp=sp, ka=ka, ki=ki, ke=ke,
        )

    # ── 워커 정리 ─────────────────────────────────────────────────────────────

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(500)
            self._worker = None

    def closeEvent(self, event) -> None:
        self._stop_worker()
        super().closeEvent(event)


# ── 엔트리포인트 ──────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
