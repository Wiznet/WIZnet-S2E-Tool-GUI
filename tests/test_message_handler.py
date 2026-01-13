#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Handler 테스트

Usage:
    python test_message_handler.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
)
from message_handler import MessageHandler  # noqa: E402


class TestWindow(QMainWindow):
    """메시지 핸들러 테스트 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Message Handler Test")
        self.resize(400, 300)

        # MessageHandler 인스턴스
        self.msg_handler = MessageHandler(parent=self)

        # UI 설정
        central = QWidget()
        layout = QVBoxLayout()

        # 테스트 버튼들
        buttons = [
            ("Info Message", self.test_info),
            ("Warning Message", self.test_warning),
            ("Error Message", self.test_error),
            ("Question (Yes/No)", self.test_question),
            ("Device Not Selected", self.test_device_not_selected),
            ("Invalid Parameter", self.test_invalid_parameter),
            ("Setting Success", self.test_setting_success),
            ("Reset Confirm", self.test_reset_confirm),
            ("Factory Reset Confirm", self.test_factory_reset_confirm),
            ("Validation Errors", self.test_validation_errors),
        ]

        for label, handler in buttons:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def test_info(self):
        """정보 메시지 테스트"""
        self.msg_handler.info(
            "Information",
            "This is an information message."
        )

    def test_warning(self):
        """경고 메시지 테스트"""
        self.msg_handler.warning(
            "Warning",
            "This is a warning message.",
            detailed_text="Additional details about the warning."
        )

    def test_error(self):
        """에러 메시지 테스트"""
        self.msg_handler.error(
            "Error",
            "This is an error message.",
            detailed_text="Error details: Connection timeout"
        )

    def test_question(self):
        """질문 메시지 테스트"""
        result = self.msg_handler.question(
            "Question",
            "Do you want to proceed?"
        )
        print(f"User answered: {'Yes' if result else 'No'}")

    def test_device_not_selected(self):
        """장치 미선택 메시지 테스트"""
        self.msg_handler.device_not_selected()

    def test_invalid_parameter(self):
        """잘못된 매개변수 메시지 테스트"""
        self.msg_handler.invalid_parameter(
            "IP Address: Invalid format\n"
            "Port: Out of range (0-65535)"
        )

    def test_setting_success(self):
        """설정 성공 메시지 테스트"""
        self.msg_handler.setting_success()

    def test_reset_confirm(self):
        """재부팅 확인 테스트"""
        result = self.msg_handler.reset_confirm()
        print(f"Reset confirmed: {result}")

    def test_factory_reset_confirm(self):
        """공장 초기화 확인 테스트"""
        result = self.msg_handler.factory_reset_confirm()
        print(f"Factory reset confirmed: {result}")

    def test_validation_errors(self):
        """검증 에러 테스트"""
        errors = {
            "IP Address": "Invalid format (expected: 192.168.1.1)",
            "Port": "Out of range (must be 0-65535)",
            "MAC Address": "Invalid format (expected: 00:08:DC:XX:XX:XX)"
        }
        self.msg_handler.validation_errors(errors)


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
