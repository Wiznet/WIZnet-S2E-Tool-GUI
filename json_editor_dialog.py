# -*- coding: utf-8 -*-
"""
간단한 JSON 에디터 다이얼로그
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QMessageBox, QLabel, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import json
from pathlib import Path


class JSONEditorDialog(QDialog):
    """JSON 설정 파일 에디터"""

    def __init__(self, json_path, parent=None):
        super().__init__(parent)
        self.json_path = Path(json_path)
        self.init_ui()
        self.load_json()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("JSON Configuration Editor")
        self.resize(800, 600)

        layout = QVBoxLayout()

        # 파일 경로 표시
        path_label = QLabel(f"File: {self.json_path}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # JSON 에디터
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Courier New", 10))
        layout.addWidget(self.editor)

        # 버튼들
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_json)

        self.format_btn = QPushButton("Format")
        self.format_btn.clicked.connect(self.format_json)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_json)

        self.save_as_btn = QPushButton("Save As...")
        self.save_as_btn.clicked.connect(self.save_as_json)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.format_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.save_as_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_json(self):
        """JSON 파일 로드"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor.setPlainText(content)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load JSON:\n{e}")

    def validate_json(self):
        """JSON 검증"""
        content = self.editor.toPlainText()

        try:
            json.loads(content)
            QMessageBox.information(self, "Validation", "JSON is valid!")
            return True
        except json.JSONDecodeError as e:
            QMessageBox.warning(
                self,
                "Validation Error",
                f"Invalid JSON at line {e.lineno}, column {e.colno}:\n{e.msg}"
            )
            return False

    def format_json(self):
        """JSON 포맷팅"""
        content = self.editor.toPlainText()

        try:
            data = json.loads(content)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self.editor.setPlainText(formatted)
            QMessageBox.information(self, "Format", "JSON formatted successfully!")
        except json.JSONDecodeError as e:
            QMessageBox.warning(
                self,
                "Format Error",
                f"Cannot format invalid JSON:\n{e.msg}"
            )

    def save_json(self):
        """JSON 저장"""
        if not self.validate_json():
            return

        content = self.editor.toPlainText()

        try:
            # 백업 생성
            backup_path = self.json_path.with_suffix('.json.backup')
            if self.json_path.exists():
                import shutil
                shutil.copy2(self.json_path, backup_path)

            # 저장
            with open(self.json_path, 'w', encoding='utf-8') as f:
                f.write(content)

            QMessageBox.information(
                self,
                "Save",
                f"JSON saved successfully!\n\nBackup: {backup_path.name}"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save JSON:\n{e}")

    def save_as_json(self):
        """다른 이름으로 저장"""
        if not self.validate_json():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save JSON As",
            str(self.json_path),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            content = self.editor.toPlainText()

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                QMessageBox.information(self, "Save As", f"JSON saved to:\n{file_path}")
                self.accept()

            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save JSON:\n{e}")
