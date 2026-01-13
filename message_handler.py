# -*- coding: utf-8 -*-
"""
중앙화된 메시지 핸들러

모든 사용자 메시지(에러, 경고, 정보)를 일관된 방식으로 처리
"""

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from enum import Enum
from typing import Optional
import logging


class MessageType(Enum):
    """메시지 타입"""
    INFO = "Information"
    WARNING = "Warning"
    ERROR = "Error"
    QUESTION = "Question"


class MessageHandler:
    """메시지 핸들러 클래스"""

    def __init__(self, parent=None, logger: Optional[logging.Logger] = None):
        """
        Args:
            parent: 부모 위젯 (QWidget)
            logger: 로거 (선택사항)
        """
        self.parent = parent
        self.logger = logger or logging.getLogger(__name__)

    def show(
        self,
        title: str,
        message: str,
        msg_type: MessageType = MessageType.INFO,
        detailed_text: Optional[str] = None,
        rich_text: bool = False
    ) -> int:
        """메시지 박스 표시

        Args:
            title: 메시지 박스 제목
            message: 메시지 내용
            msg_type: 메시지 타입
            detailed_text: 상세 정보 (선택사항)
            rich_text: HTML 리치 텍스트 사용 여부

        Returns:
            사용자 응답 (QMessageBox 상수)
        """
        msgbox = QMessageBox(self.parent)
        msgbox.setWindowTitle(title)
        msgbox.setText(message)

        if rich_text:
            msgbox.setTextFormat(Qt.RichText)

        if detailed_text:
            msgbox.setInformativeText(detailed_text)

        # 아이콘 설정
        if msg_type == MessageType.INFO:
            msgbox.setIcon(QMessageBox.Information)
        elif msg_type == MessageType.WARNING:
            msgbox.setIcon(QMessageBox.Warning)
        elif msg_type == MessageType.ERROR:
            msgbox.setIcon(QMessageBox.Critical)
        elif msg_type == MessageType.QUESTION:
            msgbox.setIcon(QMessageBox.Question)

        # 로그 기록
        log_msg = f"[{msg_type.value}] {title}: {message}"
        if msg_type == MessageType.ERROR:
            self.logger.error(log_msg)
        elif msg_type == MessageType.WARNING:
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)

        return msgbox.exec_()

    def info(self, title: str, message: str, detailed_text: Optional[str] = None):
        """정보 메시지"""
        return self.show(title, message, MessageType.INFO, detailed_text)

    def warning(self, title: str, message: str, detailed_text: Optional[str] = None):
        """경고 메시지"""
        return self.show(title, message, MessageType.WARNING, detailed_text)

    def error(self, title: str, message: str, detailed_text: Optional[str] = None):
        """에러 메시지"""
        return self.show(title, message, MessageType.ERROR, detailed_text)

    def question(
        self,
        title: str,
        message: str,
        yes_text: str = "Yes",
        no_text: str = "No"
    ) -> bool:
        """예/아니오 질문

        Args:
            title: 제목
            message: 메시지
            yes_text: Yes 버튼 텍스트
            no_text: No 버튼 텍스트

        Returns:
            True if Yes, False if No
        """
        msgbox = QMessageBox(self.parent)
        msgbox.setWindowTitle(title)
        msgbox.setText(message)
        msgbox.setIcon(QMessageBox.Question)

        yes_btn = msgbox.addButton(yes_text, QMessageBox.YesRole)
        msgbox.addButton(no_text, QMessageBox.NoRole)

        msgbox.exec_()
        return msgbox.clickedButton() == yes_btn

    # ========================================================================
    # 도메인 특화 메시지들
    # ========================================================================

    def device_not_selected(self):
        """장치가 선택되지 않음"""
        return self.warning(
            "Device Not Selected",
            "Please select a device from the list first."
        )

    def device_not_supported(self, device_name: Optional[str] = None):
        """지원되지 않는 장치"""
        msg = f"The device '{device_name}' is not supported." if device_name else \
              "The device is not supported."
        return self.error(
            "Not Supported Device",
            f"{msg}<br>Please contact us by the link below.<br><br>"
            "<a href='https://github.com/Wiznet/WIZnet-S2E-Tool-GUI/issues'>"
            "# Github issue page</a>",
            rich_text=True
        )

    def invalid_parameter(self, param_details: str):
        """잘못된 매개변수"""
        return self.warning(
            "Invalid Parameter",
            "Invalid parameter. Please check the values.",
            detailed_text=param_details
        )

    def setting_success(self):
        """설정 성공"""
        return self.info(
            "Setting Complete",
            "Device configuration has been updated successfully."
        )

    def setting_warning(self):
        """설정 경고"""
        return self.warning(
            "Setting Warning",
            "Setting did not complete successfully.\n"
            "Please check the device or firmware version."
        )

    def setting_error(self):
        """설정 에러"""
        return self.error(
            "Setting Error",
            "Failed to configure the device.\n"
            "Please check the device connection and try again."
        )

    def setting_password_error(self):
        """비밀번호 에러"""
        return self.error(
            "Setting Password Error",
            "Incorrect setting password.\n"
            "Please enter the correct password."
        )

    def upload_success(self):
        """펌웨어 업로드 성공"""
        return self.info(
            "Upload Complete",
            "Firmware upload completed successfully.\n"
            "The device will restart automatically."
        )

    def upload_warning(self, dst_ip: str):
        """펌웨어 업로드 경고"""
        return self.warning(
            "Upload Warning",
            f"Failed to upload firmware to {dst_ip}.\n"
            "Please check the device connection and try again."
        )

    def connection_failed(self):
        """연결 실패"""
        return self.error(
            "Connection Failed",
            "Failed to connect to the device.\n"
            "Please check the network connection."
        )

    def not_connected(self, dst_ip: str):
        """연결되지 않음"""
        return self.warning(
            "Not Connected",
            f"Device at {dst_ip} is not responding.\n"
            "Please check if the device is online."
        )

    def reset_confirm(self) -> bool:
        """재부팅 확인"""
        return self.question(
            "Reset Device",
            "Are you sure you want to reset the device?\n"
            "The device will restart.",
            yes_text="Reset",
            no_text="Cancel"
        )

    def reset_success(self):
        """재부팅 성공"""
        return self.info(
            "Reset Complete",
            "Device reset command sent successfully."
        )

    def factory_reset_confirm(self) -> bool:
        """공장 초기화 확인"""
        return self.question(
            "Factory Reset",
            "WARNING: This will reset ALL settings to factory defaults.\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            yes_text="Factory Reset",
            no_text="Cancel"
        )

    def factory_reset_success(self):
        """공장 초기화 성공"""
        return self.info(
            "Factory Reset Complete",
            "Device has been reset to factory defaults."
        )

    def firmware_update_confirm(self) -> bool:
        """펌웨어 업데이트 확인"""
        return self.question(
            "Firmware Update",
            "WARNING: Do not turn off the device during firmware update.\n"
            "The update process may take several minutes.\n\n"
            "Continue with firmware update?",
            yes_text="Update",
            no_text="Cancel"
        )

    def exit_confirm(self) -> bool:
        """종료 확인"""
        return self.question(
            "Exit",
            "Are you sure you want to exit?",
            yes_text="Exit",
            no_text="Cancel"
        )

    def validation_errors(self, errors: dict):
        """검증 에러 목록 표시

        Args:
            errors: {field_name: error_message} 딕셔너리
        """
        if not errors:
            return

        error_list = "\n".join([f"• {field}: {msg}" for field, msg in errors.items()])
        return self.error(
            "Validation Failed",
            "The following errors were found:",
            detailed_text=error_list
        )


# ============================================================================
# 편의 함수 (전역 인스턴스 없이 사용)
# ============================================================================

def show_info(parent, title: str, message: str):
    """정보 메시지 표시 (전역 함수)"""
    handler = MessageHandler(parent)
    return handler.info(title, message)


def show_warning(parent, title: str, message: str):
    """경고 메시지 표시 (전역 함수)"""
    handler = MessageHandler(parent)
    return handler.warning(title, message)


def show_error(parent, title: str, message: str):
    """에러 메시지 표시 (전역 함수)"""
    handler = MessageHandler(parent)
    return handler.error(title, message)


def ask_question(parent, title: str, message: str) -> bool:
    """예/아니오 질문 (전역 함수)"""
    handler = MessageHandler(parent)
    return handler.question(title, message)
