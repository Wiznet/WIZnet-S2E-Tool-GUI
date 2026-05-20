"""
GitHub release list → select → download/extract dialog.
Emits firmware_ready(bin_path, filesize) signal on completion, then auto-closes.

fw_type_list (optional): WIZ550처럼 같은 장치가 여러 repo를 갖는 경우
  [{"label": "SR", "family": {...}, "device_spec": {...}}, ...]
  제공 시 "Type:" 콤보가 Release 위에 표시되고, 선택 변경 시 릴리스 목록 갱신.
"""
import os

from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QLineEdit,
)


class _FetchReleasesThread(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, fetcher, repo):
        super().__init__()
        self._fetcher = fetcher
        self._repo = repo

    def run(self):
        try:
            self.done.emit(self._fetcher.get_releases(self._repo))
        except Exception as e:
            self.error.emit(str(e))


class _DownloadThread(QThread):
    done = pyqtSignal(str, int)   # (bin_path, filesize)
    error = pyqtSignal(str)

    def __init__(self, fetcher, asset, dest_dir, extract_file):
        super().__init__()
        self._fetcher = fetcher
        self._asset = asset
        self._dest_dir = dest_dir
        self._extract_file = extract_file

    def run(self):
        try:
            path, size = self._fetcher.download_and_extract(
                self._asset, self._dest_dir, self._extract_file
            )
            self.done.emit(path, size)
        except Exception as e:
            self.error.emit(str(e))


class FWGitDialog(QDialog):
    firmware_ready = pyqtSignal(str, int)   # (bin_path, filesize)

    def __init__(self, parent, device_name, family, device_spec, fetcher, dl_path,
                 fw_type_list=None, wiz550_config=None):
        """
        fw_type_list: [{"label": str, "family": dict, "device_spec": dict}, ...]
          None 또는 빈 리스트면 타입 선택 행 미표시.
        wiz550_config: {"target_ip": str, "target_mac": str, "localip_addr": str, "pw_setting": str}
          제공 시 다운로드 완료 후 TFTP 업로드를 이 창 안에서 자동 진행.
        """
        super().__init__(parent)
        self._device_name  = device_name
        self._family       = family
        self._device_spec  = device_spec
        self._fetcher      = fetcher
        self._dl_path      = dl_path
        self._fw_type_list = fw_type_list or []
        self._wiz550_config = wiz550_config
        self._releases     = []
        self._current_asset = None
        self._fetch_thread  = None
        self._dl_thread     = None
        self._upload_thread = None
        self._tmp_bin_path  = None

        self.setWindowTitle("FW from Git")
        self.setFixedWidth(540)
        self.setModal(True)
        self._build_ui()
        self._start_fetch()

    # ── UI ───────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        row = 0

        # Device / repository info
        grid.addWidget(QLabel("Device:"), row, 0)
        self._lbl_device = QLabel()
        self._lbl_device.setWordWrap(True)
        self._refresh_device_label()
        grid.addWidget(self._lbl_device, row, 1)
        row += 1

        # Type 콤보 (fw_type_list 제공 시에만)
        if self._fw_type_list:
            grid.addWidget(QLabel("Type:"), row, 0)
            self._combo_type = QComboBox()
            for entry in self._fw_type_list:
                self._combo_type.addItem(entry["label"])
            self._combo_type.currentIndexChanged.connect(self._on_type_changed)
            grid.addWidget(self._combo_type, row, 1)
            row += 1

        # Release selection row
        grid.addWidget(QLabel("Release:"), row, 0)
        rel_row = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setMinimumWidth(260)
        self._combo.currentIndexChanged.connect(self._update_asset_label)
        rel_row.addWidget(self._combo, 1)
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.setFixedWidth(80)
        self._btn_refresh.clicked.connect(self._start_fetch)
        rel_row.addWidget(self._btn_refresh)
        grid.addLayout(rel_row, row, 1)
        row += 1

        # Asset row
        grid.addWidget(QLabel("Asset:"), row, 0)
        self._lbl_asset = QLabel("—")
        self._lbl_asset.setWordWrap(True)
        grid.addWidget(self._lbl_asset, row, 1)
        row += 1

        # Password 행 (WIZ550 업로드 모드에서만 표시)
        if self._wiz550_config is not None:
            grid.addWidget(QLabel("Password:"), row, 0)
            self._edit_pw = QLineEdit()
            self._edit_pw.setEchoMode(QLineEdit.Password)
            self._edit_pw.setPlaceholderText("Optional")
            if self._wiz550_config.get('pw_setting'):
                self._edit_pw.setText(self._wiz550_config['pw_setting'])
            grid.addWidget(self._edit_pw, row, 1)

        root.addLayout(grid)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep1)

        # Download path row
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Save Path:"))
        self._lbl_dlpath = QLabel(self._dl_path)
        self._lbl_dlpath.setWordWrap(True)
        path_row.addWidget(self._lbl_dlpath, 1)
        btn_change = QPushButton("Browse...")
        btn_change.setFixedWidth(70)
        btn_change.clicked.connect(self._change_dl_path)
        path_row.addWidget(btn_change)
        root.addLayout(path_row)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep2)

        # Progress bar (hidden by default)
        self._pgbar = QProgressBar()
        self._pgbar.setRange(0, 0)   # indeterminate
        self._pgbar.setVisible(False)
        root.addWidget(self._pgbar)

        # Bottom button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_dl = QPushButton("Download")
        self._btn_dl.setEnabled(False)
        self._btn_dl.setDefault(True)
        self._btn_dl.clicked.connect(self._on_download)
        btn_row.addWidget(self._btn_dl)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    def _refresh_device_label(self):
        self._lbl_device.setText(
            f"<b>{self._device_name}</b>  "
            f"<span style='color:gray'>({self._family['repo']})</span>"
        )

    # ── Type 변경 ────────────────────────────────────────────────────
    def _on_type_changed(self, index):
        if index < 0 or index >= len(self._fw_type_list):
            return
        entry = self._fw_type_list[index]
        self._family      = entry["family"]
        self._device_spec = entry["device_spec"]
        self._refresh_device_label()
        self._start_fetch()

    # ── Fetch releases ───────────────────────────────────────────────
    def _start_fetch(self):
        self._set_busy(True)
        self._combo.clear()
        self._lbl_asset.setText("Fetching releases...")
        self._lbl_asset.setStyleSheet("")
        self._releases = []
        self._current_asset = None
        self._fetch_thread = _FetchReleasesThread(self._fetcher, self._family["repo"])
        self._fetch_thread.done.connect(self._on_releases_fetched)
        self._fetch_thread.error.connect(self._on_fetch_error)
        self._fetch_thread.start()

    def _on_releases_fetched(self, releases):
        self._releases = releases
        self._combo.blockSignals(True)
        self._combo.clear()
        for r in releases:
            date = r.get("published_at", "")[:10]
            self._combo.addItem(f"{r['tag_name']}  ({date})")
        self._combo.blockSignals(False)
        self._set_busy(False)
        if releases:
            self._update_asset_label(0)
        else:
            self._lbl_asset.setText("No releases found.")

    def _on_fetch_error(self, msg):
        self._set_busy(False)
        self._lbl_asset.setText("Fetch failed")
        self._lbl_asset.setStyleSheet("color: red;")
        QMessageBox.critical(self, "Error", f"Failed to fetch releases:\n{msg}")

    def _update_asset_label(self, index):
        if not self._releases or index < 0 or index >= len(self._releases):
            self._current_asset = None
            self._btn_dl.setEnabled(False)
            return
        release = self._releases[index]
        asset = self._fetcher.find_asset(release, self._device_spec, self._family)
        self._current_asset = asset
        if asset:
            extract = self._device_spec.get("extract_file") or "(direct use)"
            self._lbl_asset.setText(f"{asset['name']}  →  {extract}")
            self._lbl_asset.setStyleSheet("")
            self._btn_dl.setEnabled(True)
        else:
            self._lbl_asset.setText("No matching asset for this release.")
            self._lbl_asset.setStyleSheet("color: red;")
            self._btn_dl.setEnabled(False)

    # ── Download ─────────────────────────────────────────────────────
    def _on_download(self):
        self._set_busy(True)
        extract_file = self._device_spec.get("extract_file")
        self._dl_thread = _DownloadThread(
            self._fetcher,
            self._current_asset,
            self._dl_path,
            extract_file,
        )
        self._dl_thread.done.connect(self._on_download_done)
        self._dl_thread.error.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_download_done(self, path, size):
        self._tmp_bin_path = path
        if self._wiz550_config is not None:
            self._start_wiz550_upload(path)
        else:
            self._set_busy(False)
            self.firmware_ready.emit(path, size)
            self.accept()

    def _on_download_error(self, msg):
        self._set_busy(False)
        self._cleanup_tmp()
        QMessageBox.critical(self, "Error", f"Download failed:\n{msg}")

    # ── WIZ550 인라인 TFTP 업로드 ─────────────────────────────────────
    def _start_wiz550_upload(self, fw_path):
        from WIZ550FWUploadThread import WIZ550FWUploadThread
        cfg = self._wiz550_config
        self._lbl_asset.setText("Starting TFTP upload...")
        self._lbl_asset.setStyleSheet("color: gray;")
        password = self._edit_pw.text() if hasattr(self, '_edit_pw') else ''
        self._upload_thread = WIZ550FWUploadThread(
            mode='auto',
            fw_path=fw_path,
            target_ip=cfg['target_ip'],
            target_mac=cfg['target_mac'],
            server_ip=cfg['localip_addr'],
            server_port=69,
            password=password,
            iface_ip=cfg['localip_addr'],
        )
        self._upload_thread.progress.connect(self._on_upload_progress)
        self._upload_thread.finished.connect(self._on_upload_finished)
        self._upload_thread.error.connect(self._on_upload_error)
        self._upload_thread.start()

    def _on_upload_progress(self, msg: str):
        self._lbl_asset.setText(msg)
        self._lbl_asset.setStyleSheet("color: gray;")

    def _on_upload_finished(self, success: bool):
        self._set_busy(False)
        self._cleanup_tmp()
        if success:
            self._lbl_asset.setText("Upload complete!")
            self._lbl_asset.setStyleSheet("color: green;")
            QTimer.singleShot(1500, self.accept)
        else:
            current = self._lbl_asset.text()
            if current in {"Starting TFTP upload...", "Sending firmware upload request...",
                           "Waiting for device response..."}:
                self._lbl_asset.setText(
                    "Upload timed out — no response from device. "
                    "Check connection and retry."
                )
            self._lbl_asset.setStyleSheet("color: red;")

    def _on_upload_error(self, msg: str):
        self._set_busy(False)
        self._cleanup_tmp()
        self._lbl_asset.setText(f"Upload error: {msg}")
        self._lbl_asset.setStyleSheet("color: red;")

    def _cleanup_tmp(self):
        if self._tmp_bin_path and os.path.isfile(self._tmp_bin_path):
            try:
                os.remove(self._tmp_bin_path)
            except OSError:
                pass
        self._tmp_bin_path = None

    # ── Save path ────────────────────────────────────────────────────
    def _change_dl_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self._dl_path
        )
        if path:
            self._dl_path = path
            self._lbl_dlpath.setText(path)

    # ── 닫기 안전 정리 ────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._upload_thread is not None and self._upload_thread.isRunning():
            self._upload_thread.stop()
            self._upload_thread.wait(3000)
        event.accept()

    # ── Helpers ──────────────────────────────────────────────────────
    def _set_busy(self, busy: bool):
        self._pgbar.setVisible(busy)
        self._btn_refresh.setEnabled(not busy)
        self._combo.setEnabled(not busy)
        if self._fw_type_list:
            self._combo_type.setEnabled(not busy)
        if not busy:
            self._btn_dl.setEnabled(self._current_asset is not None)
        else:
            self._btn_dl.setEnabled(False)
