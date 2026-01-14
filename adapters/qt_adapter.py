"""Qt-specific adapter implementation.

This adapter connects Core business logic to PyQt5 UI.
It translates Core operations to Qt widget manipulation and vice versa.
"""

from typing import List, Dict, Optional, Callable
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem, QLineEdit, QComboBox

from .base_adapter import BaseUIAdapter
from core.models.device_config import DeviceInfo, DeviceConfig
from core.models.device_model import DeviceModel


class QtAdapter(BaseUIAdapter):
    """Qt-specific implementation of UI adapter.

    This adapter works with existing WIZWindow (main_gui.py) to:
    - Display data in Qt widgets
    - Handle Qt events and delegate to Core
    - Manage UI state based on Core responses

    Note: Does not inherit from QObject since we don't need signals/slots.
    The adapter is a simple bridge between Core and Qt widgets.
    """

    def __init__(self, window):
        """Initialize Qt adapter.

        Args:
            window: WIZWindow instance (main_gui.py)
        """
        super().__init__()
        self.window = window
        self.logger = window.logger

        # Event handlers
        self._search_handler = None
        self._configure_handler = None
        self._apply_handler = None
        self._upload_handler = None

    # ========================================================================
    # Core → UI: Display Methods
    # ========================================================================

    def show_devices(self, devices: List[DeviceInfo]):
        """Display discovered devices in Qt table widget."""
        try:
            table = self.window.list_device
            table.clear()
            table.setRowCount(len(devices))

            for row, device in enumerate(devices):
                # MAC address
                item_mac = QTableWidgetItem(device.mac_addr)
                table.setItem(row, 0, item_mac)

                # Device name/model
                display_name = device.product_name or device.model_id
                item_name = QTableWidgetItem(display_name)
                table.setItem(row, 1, item_name)

                # IP address (if available)
                if device.ip_addr:
                    item_ip = QTableWidgetItem(device.ip_addr)
                    table.setItem(row, 2, item_ip)

                # Store full device info in row data
                table.item(row, 0).setData(0x0100, device)  # Qt.UserRole

            self.logger.info(f"Displayed {len(devices)} devices in table")

        except Exception as e:
            self.logger.error(f"Error displaying devices: {e}")
            self.show_error(f"Failed to display devices: {e}")

    def show_device_config(self, config: DeviceConfig, model: DeviceModel):
        """Display device configuration in Qt input fields."""
        try:
            self.logger.info(f"Displaying config for {model.model_id}")

            # Get commands for this firmware version
            commands = model.get_commands_for_version(config.firmware_version)

            # Update each field
            for cmd_code, command in commands.items():
                value = config.get_parameter(cmd_code, "")
                self.set_field_value(cmd_code, value)

            # Update field states (enabled/disabled) based on model
            self.update_command_fields(model, config.firmware_version)

        except Exception as e:
            self.logger.error(f"Error displaying config: {e}")
            self.show_error(f"Failed to display configuration: {e}")

    def show_error(self, message: str, title: Optional[str] = None):
        """Display error message dialog."""
        QMessageBox.critical(
            self.window,
            title or "Error",
            message
        )
        self.logger.error(f"Error shown to user: {message}")

    def show_warning(self, message: str, title: Optional[str] = None):
        """Display warning message dialog."""
        QMessageBox.warning(
            self.window,
            title or "Warning",
            message
        )
        self.logger.warning(f"Warning shown to user: {message}")

    def show_info(self, message: str, title: Optional[str] = None):
        """Display information message dialog."""
        QMessageBox.information(
            self.window,
            title or "Information",
            message
        )
        self.logger.info(f"Info shown to user: {message}")

    def show_progress(self, message: str, value: Optional[int] = None, maximum: Optional[int] = None):
        """Show progress bar."""
        try:
            pgbar = self.window.pgbar
            pgbar.setFormat(message)

            if value is not None and maximum is not None:
                pgbar.setRange(0, maximum)
                pgbar.setValue(value)
            else:
                # Indeterminate progress
                pgbar.setRange(0, 0)

            pgbar.show()

        except Exception as e:
            self.logger.error(f"Error showing progress: {e}")

    def hide_progress(self):
        """Hide progress bar."""
        try:
            self.window.pgbar.hide()
        except Exception as e:
            self.logger.error(f"Error hiding progress: {e}")

    def ask_confirmation(self, message: str, title: Optional[str] = None) -> bool:
        """Ask user for confirmation."""
        reply = QMessageBox.question(
            self.window,
            title or "Confirm",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def get_selected_device(self) -> Optional[DeviceInfo]:
        """Get currently selected device from table."""
        try:
            table = self.window.list_device
            selected_rows = table.selectedItems()

            if not selected_rows:
                return None

            # Get first column (MAC) of selected row
            row = selected_rows[0].row()
            mac_item = table.item(row, 0)

            if mac_item:
                # Retrieve stored DeviceInfo
                device = mac_item.data(0x0100)  # Qt.UserRole
                return device

        except Exception as e:
            self.logger.error(f"Error getting selected device: {e}")

        return None

    def get_device_config_from_ui(self) -> Dict[str, str]:
        """Get device configuration values from UI input fields."""
        config = {}

        try:
            # This will be implemented to read from specific Qt widgets
            # For now, return empty dict as placeholder
            # TODO: Map command codes to Qt widget names and read values
            pass

        except Exception as e:
            self.logger.error(f"Error reading config from UI: {e}")

        return config

    def enable_ui(self, enabled: bool):
        """Enable or disable UI controls."""
        try:
            # Enable/disable main buttons
            self.window.btn_search.setEnabled(enabled)
            self.window.btn_setting.setEnabled(enabled)
            self.window.btn_apply.setEnabled(enabled)

            # Enable/disable tab widget
            self.window.tabWidget.setEnabled(enabled)

        except Exception as e:
            self.logger.error(f"Error setting UI state: {e}")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def update_command_fields(self, model: DeviceModel, firmware_version: str):
        """Update UI fields based on device model and firmware version."""
        try:
            commands = model.get_commands_for_version(firmware_version)

            # Enable/disable fields based on command access
            for cmd_code, command in commands.items():
                # Get widget for this command
                widget = self._get_widget_for_command(cmd_code)
                if widget:
                    # Disable if read-only
                    widget.setEnabled(command.is_writable())

            self.logger.info(f"Updated field states for {model.model_id} v{firmware_version}")

        except Exception as e:
            self.logger.error(f"Error updating command fields: {e}")

    def set_field_value(self, command_code: str, value: str):
        """Set value of a specific command field in UI."""
        try:
            widget = self._get_widget_for_command(command_code)
            if widget:
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QComboBox):
                    # Find index of value in combo box
                    index = widget.findText(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                    else:
                        # Try to find by option code
                        index = widget.findData(value)
                        if index >= 0:
                            widget.setCurrentIndex(index)

        except Exception as e:
            self.logger.error(f"Error setting field value for {command_code}: {e}")

    def get_field_value(self, command_code: str) -> Optional[str]:
        """Get value of a specific command field from UI."""
        try:
            widget = self._get_widget_for_command(command_code)
            if widget:
                if isinstance(widget, QLineEdit):
                    return widget.text()
                elif isinstance(widget, QComboBox):
                    # Return option code (data), not display text
                    return widget.currentData()

        except Exception as e:
            self.logger.error(f"Error getting field value for {command_code}: {e}")

        return None

    def validate_fields(self, model: DeviceModel) -> bool:
        """Validate all UI fields against command patterns."""
        all_valid = True

        try:
            commands = model.commands

            for cmd_code, command in commands.items():
                if not command.is_writable():
                    continue

                value = self.get_field_value(cmd_code)
                if value and not command.validate(value):
                    self.highlight_invalid_field(
                        cmd_code,
                        f"Invalid value for {command.name}"
                    )
                    all_valid = False

        except Exception as e:
            self.logger.error(f"Error validating fields: {e}")
            return False

        return all_valid

    def highlight_invalid_field(self, command_code: str, error_message: str):
        """Highlight a field as invalid and show error."""
        try:
            widget = self._get_widget_for_command(command_code)
            if widget and isinstance(widget, QLineEdit):
                # Set red border
                widget.setStyleSheet("border: 1px solid red;")
                widget.setToolTip(error_message)

        except Exception as e:
            self.logger.error(f"Error highlighting field {command_code}: {e}")

    def clear_field_highlights(self):
        """Clear all field validation highlights."""
        try:
            # Reset all QLineEdit widgets to default style
            for widget in self.window.findChildren(QLineEdit):
                widget.setStyleSheet("")
                widget.setToolTip("")

        except Exception as e:
            self.logger.error(f"Error clearing highlights: {e}")

    def _get_widget_for_command(self, command_code: str):
        """Get Qt widget for a command code.

        This maps command codes to actual Qt widget names in the UI.
        Widget naming convention: <command_code>_input or similar.

        Args:
            command_code: Command code (e.g., 'LI', 'MC')

        Returns:
            Qt widget or None
        """
        # Common widget name patterns
        possible_names = [
            f"{command_code.lower()}_input",
            f"input_{command_code.lower()}",
            f"{command_code}_input",
            f"txt_{command_code.lower()}",
            f"cmb_{command_code.lower()}",
        ]

        for name in possible_names:
            widget = self.window.findChild((QLineEdit, QComboBox), name)
            if widget:
                return widget

        return None

    # ========================================================================
    # Lifecycle Methods
    # ========================================================================

    def initialize(self):
        """Initialize adapter. Called after UI is ready."""
        self.logger.info("QtAdapter initialized")

        # Connect Qt signals to handlers if defined
        if hasattr(self.window, 'btn_search'):
            self.window.btn_search.clicked.connect(self._on_search_clicked)

        if hasattr(self.window, 'btn_setting'):
            self.window.btn_setting.clicked.connect(self._on_configure_clicked)

        if hasattr(self.window, 'btn_apply'):
            self.window.btn_apply.clicked.connect(self._on_apply_clicked)

    def cleanup(self):
        """Clean up resources. Called before shutdown."""
        self.logger.info("QtAdapter cleanup")

    # ========================================================================
    # Internal Event Handlers
    # ========================================================================

    def _on_search_clicked(self):
        """Handle search button click."""
        if self._search_handler:
            try:
                self._search_handler()
            except Exception as e:
                self.logger.error(f"Search handler error: {e}")
                self.show_error(f"Search failed: {e}")

    def _on_configure_clicked(self):
        """Handle configure/read button click."""
        if self._configure_handler:
            try:
                device = self.get_selected_device()
                if device:
                    self._configure_handler(device)
                else:
                    self.show_warning("Please select a device first.")
            except Exception as e:
                self.logger.error(f"Configure handler error: {e}")
                self.show_error(f"Configuration failed: {e}")

    def _on_apply_clicked(self):
        """Handle apply/write button click."""
        if self._apply_handler:
            try:
                device = self.get_selected_device()
                if device:
                    config = self.get_device_config_from_ui()
                    self._apply_handler(device, config)
                else:
                    self.show_warning("Please select a device first.")
            except Exception as e:
                self.logger.error(f"Apply handler error: {e}")
                self.show_error(f"Apply failed: {e}")
