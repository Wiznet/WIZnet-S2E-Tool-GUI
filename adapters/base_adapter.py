"""Base adapter interface for UI frameworks.

This module defines the abstract interface that all UI adapters must implement.
The adapter pattern separates Core business logic from UI-specific code.

Core → Adapter → UI Framework (Qt/Web/CLI)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Any

from core.models.device_config import DeviceInfo, DeviceConfig
from core.models.device_model import DeviceModel


class BaseUIAdapter(ABC):
    """Abstract base class for UI adapters.

    UI adapters translate between Core business logic and UI-specific code.
    They handle:
    - Displaying data from Core to UI
    - Translating UI events to Core operations
    - Managing UI state updates
    """

    # ========================================================================
    # Core → UI: Display Methods
    # ========================================================================

    @abstractmethod
    def show_devices(self, devices: List[DeviceInfo]):
        """Display discovered devices in UI.

        Args:
            devices: List of discovered devices with MAC, IP, model, firmware
        """
        pass

    @abstractmethod
    def show_device_config(self, config: DeviceConfig, model: DeviceModel):
        """Display device configuration in UI.

        Args:
            config: Device configuration with parameter values
            model: Device model with command definitions
        """
        pass

    @abstractmethod
    def show_error(self, message: str, title: Optional[str] = None):
        """Display error message to user.

        Args:
            message: Error message text
            title: Optional error dialog title
        """
        pass

    @abstractmethod
    def show_warning(self, message: str, title: Optional[str] = None):
        """Display warning message to user.

        Args:
            message: Warning message text
            title: Optional warning dialog title
        """
        pass

    @abstractmethod
    def show_info(self, message: str, title: Optional[str] = None):
        """Display information message to user.

        Args:
            message: Info message text
            title: Optional info dialog title
        """
        pass

    @abstractmethod
    def show_progress(self, message: str, value: Optional[int] = None, maximum: Optional[int] = None):
        """Show progress indicator.

        Args:
            message: Progress message
            value: Current progress value (None for indeterminate)
            maximum: Maximum progress value
        """
        pass

    @abstractmethod
    def hide_progress(self):
        """Hide progress indicator."""
        pass

    @abstractmethod
    def ask_confirmation(self, message: str, title: Optional[str] = None) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message
            title: Optional dialog title

        Returns:
            True if user confirmed, False otherwise
        """
        pass

    @abstractmethod
    def get_selected_device(self) -> Optional[DeviceInfo]:
        """Get currently selected device from UI.

        Returns:
            Selected device info or None
        """
        pass

    @abstractmethod
    def get_device_config_from_ui(self) -> Dict[str, str]:
        """Get device configuration values from UI input fields.

        Returns:
            Dictionary mapping command codes to values (e.g., {'LI': '192.168.1.100'})
        """
        pass

    @abstractmethod
    def enable_ui(self, enabled: bool):
        """Enable or disable UI controls.

        Args:
            enabled: True to enable, False to disable
        """
        pass

    # ========================================================================
    # UI → Core: Event Handler Registration
    # ========================================================================

    def register_search_handler(self, handler: Callable[[], None]):
        """Register handler for search button click.

        Args:
            handler: Callback function to execute on search
        """
        self._search_handler = handler

    def register_configure_handler(self, handler: Callable[[DeviceInfo], None]):
        """Register handler for configure/read button click.

        Args:
            handler: Callback function with selected device
        """
        self._configure_handler = handler

    def register_apply_handler(self, handler: Callable[[DeviceInfo, Dict[str, str]], None]):
        """Register handler for apply/write button click.

        Args:
            handler: Callback function with device and config values
        """
        self._apply_handler = handler

    def register_upload_handler(self, handler: Callable[[DeviceInfo, str], None]):
        """Register handler for firmware upload.

        Args:
            handler: Callback function with device and firmware file path
        """
        self._upload_handler = handler

    # ========================================================================
    # Utility Methods
    # ========================================================================

    @abstractmethod
    def update_command_fields(self, model: DeviceModel, firmware_version: str):
        """Update UI fields based on device model and firmware version.

        This enables/disables fields based on:
        - Command access (RO/RW/WO)
        - Firmware version support
        - Device category (one-port vs two-port)

        Args:
            model: Device model with command definitions
            firmware_version: Current firmware version
        """
        pass

    @abstractmethod
    def set_field_value(self, command_code: str, value: str):
        """Set value of a specific command field in UI.

        Args:
            command_code: Command code (e.g., 'LI', 'MC')
            value: Value to set
        """
        pass

    @abstractmethod
    def get_field_value(self, command_code: str) -> Optional[str]:
        """Get value of a specific command field from UI.

        Args:
            command_code: Command code (e.g., 'LI', 'MC')

        Returns:
            Field value or None
        """
        pass

    @abstractmethod
    def validate_fields(self, model: DeviceModel) -> bool:
        """Validate all UI fields against command patterns.

        Args:
            model: Device model with command validation patterns

        Returns:
            True if all fields valid, False otherwise
        """
        pass

    @abstractmethod
    def highlight_invalid_field(self, command_code: str, error_message: str):
        """Highlight a field as invalid and show error.

        Args:
            command_code: Command code of invalid field
            error_message: Validation error message
        """
        pass

    @abstractmethod
    def clear_field_highlights(self):
        """Clear all field validation highlights."""
        pass

    # ========================================================================
    # Lifecycle Methods
    # ========================================================================

    def initialize(self):
        """Initialize adapter. Called after UI is ready."""
        pass

    def cleanup(self):
        """Clean up resources. Called before shutdown."""
        pass
