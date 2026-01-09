"""Device service for business logic operations.

This service handles device-related operations without any UI dependencies.
It coordinates between DeviceRegistry (data) and network operations.
"""

from typing import List, Dict, Optional, Callable
import logging

from core.device_registry import DeviceRegistry, get_global_registry
from core.models.device_config import DeviceInfo, DeviceConfig
from core.models.device_model import DeviceModel


class DeviceService:
    """Service for device operations (search, configure, upload).

    This service is UI-agnostic and can be used by any adapter (Qt/Web/CLI).
    """

    def __init__(self, registry: Optional[DeviceRegistry] = None):
        """Initialize device service.

        Args:
            registry: Device registry (uses global if not specified)
        """
        self.registry = registry or get_global_registry()
        self.logger = logging.getLogger(__name__)

        # Network components (will be injected from main_gui.py for now)
        self.wizmakecmd = None
        self.conf_sock = None
        self.wizmsghandler = None

    # ========================================================================
    # Device Discovery
    # ========================================================================

    def search_devices(
        self,
        search_code: str = " ",
        broadcast: bool = True,
        on_progress: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[List[DeviceInfo]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """Search for devices on network.

        This is a wrapper around existing search functionality.
        For Phase 1-B, it delegates to existing WIZMakeCMD/WIZMSGHandler.

        Args:
            search_code: Search code (default: " " for all)
            broadcast: Use broadcast or unicast
            on_progress: Callback for progress updates
            on_complete: Callback when search completes
            on_error: Callback on error
        """
        try:
            if on_progress:
                on_progress("Searching devices...")

            # TODO: Phase 2 will implement this in Core
            # For now, this is a placeholder that will call existing code
            self.logger.info(f"Search devices (code={search_code}, broadcast={broadcast})")

            # Existing search logic will be gradually migrated here

        except Exception as e:
            self.logger.error(f"Search error: {e}")
            if on_error:
                on_error(str(e))

    # ========================================================================
    # Device Configuration
    # ========================================================================

    def read_device_config(
        self,
        device: DeviceInfo,
        on_progress: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[DeviceConfig, DeviceModel], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """Read configuration from device.

        Args:
            device: Target device
            on_progress: Callback for progress updates
            on_complete: Callback when read completes
            on_error: Callback on error
        """
        try:
            if on_progress:
                on_progress(f"Reading config from {device.mac_addr}...")

            # Get device model
            model = self.registry.get_model(device.model_id)
            if not model:
                raise ValueError(f"Unknown device model: {device.model_id}")

            # TODO: Phase 2 will implement network read in Core
            # For now, this is a placeholder
            self.logger.info(f"Read config from {device.model_id} ({device.mac_addr})")

            # Existing read logic will be gradually migrated here

        except Exception as e:
            self.logger.error(f"Read config error: {e}")
            if on_error:
                on_error(str(e))

    def write_device_config(
        self,
        device: DeviceInfo,
        config: Dict[str, str],
        on_progress: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """Write configuration to device.

        Args:
            device: Target device
            config: Configuration dictionary (command_code -> value)
            on_progress: Callback for progress updates
            on_complete: Callback when write completes
            on_error: Callback on error
        """
        try:
            if on_progress:
                on_progress(f"Writing config to {device.mac_addr}...")

            # Get device model
            model = self.registry.get_model(device.model_id)
            if not model:
                raise ValueError(f"Unknown device model: {device.model_id}")

            # Validate config
            commands = model.get_commands_for_version(device.firmware_version)
            for cmd_code, value in config.items():
                if cmd_code not in commands:
                    raise ValueError(f"Unknown command: {cmd_code}")

                command = commands[cmd_code]
                if not command.is_writable():
                    raise ValueError(f"Command {cmd_code} is read-only")

                if not command.validate(value):
                    raise ValueError(f"Invalid value for {cmd_code}: {value}")

            # TODO: Phase 2 will implement network write in Core
            # For now, this is a placeholder
            self.logger.info(f"Write config to {device.model_id} ({device.mac_addr})")
            self.logger.debug(f"Config: {config}")

            # Existing write logic will be gradually migrated here

            if on_complete:
                on_complete()

        except Exception as e:
            self.logger.error(f"Write config error: {e}")
            if on_error:
                on_error(str(e))

    # ========================================================================
    # Device Model Queries
    # ========================================================================

    def get_device_model(self, model_id: str) -> Optional[DeviceModel]:
        """Get device model by ID.

        Args:
            model_id: Model ID (e.g., 'WIZ750SR')

        Returns:
            Device model or None
        """
        return self.registry.get_model(model_id)

    def list_device_models(self) -> List[str]:
        """Get list of all supported device models.

        Returns:
            List of model IDs
        """
        return self.registry.list_models()

    def get_commands_for_device(
        self,
        model_id: str,
        firmware_version: str
    ) -> Optional[Dict]:
        """Get commands for a specific device and firmware version.

        Args:
            model_id: Model ID
            firmware_version: Firmware version

        Returns:
            Dictionary of commands or None
        """
        model = self.registry.get_model(model_id)
        if not model:
            return None

        return model.get_commands_for_version(firmware_version)

    # ========================================================================
    # Validation
    # ========================================================================

    def validate_config(
        self,
        device: DeviceInfo,
        config: Dict[str, str]
    ) -> Dict[str, str]:
        """Validate device configuration.

        Args:
            device: Device info
            config: Configuration dictionary

        Returns:
            Dictionary of validation errors (command_code -> error_message)
        """
        errors = {}

        try:
            model = self.registry.get_model(device.model_id)
            if not model:
                return {"_model": f"Unknown device model: {device.model_id}"}

            commands = model.get_commands_for_version(device.firmware_version)

            for cmd_code, value in config.items():
                if cmd_code not in commands:
                    errors[cmd_code] = f"Unknown command: {cmd_code}"
                    continue

                command = commands[cmd_code]

                if not command.is_writable():
                    errors[cmd_code] = f"{command.name} is read-only"
                    continue

                if not command.validate(value):
                    errors[cmd_code] = f"Invalid value for {command.name}"

        except Exception as e:
            self.logger.error(f"Validation error: {e}")
            errors["_exception"] = str(e)

        return errors

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def parse_device_response(self, raw_data: bytes) -> Optional[DeviceInfo]:
        """Parse device response packet into DeviceInfo.

        This will be implemented in Phase 2 when network layer is migrated.

        Args:
            raw_data: Raw response packet

        Returns:
            DeviceInfo or None
        """
        # TODO: Implement packet parsing
        # For now, this is handled by existing WIZMSGHandler
        pass

    def build_command_packet(
        self,
        device: DeviceInfo,
        command_code: str,
        value: Optional[str] = None
    ) -> Optional[bytes]:
        """Build command packet for device.

        This will be implemented in Phase 2 when network layer is migrated.

        Args:
            device: Target device
            command_code: Command code
            value: Value (for write commands)

        Returns:
            Packet bytes or None
        """
        # TODO: Implement packet building
        # For now, this is handled by existing WIZMakeCMD
        pass
