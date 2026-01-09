"""Example integration of QtAdapter with existing main_gui.py.

This file demonstrates how to incrementally integrate the new Core/Adapter
architecture with the existing WIZWindow class.

Integration Strategy (Strangler Fig Pattern):
1. Create QtAdapter instance in WIZWindow.__init__()
2. Create DeviceService instance
3. Connect adapter event handlers to service methods
4. Gradually migrate functions from WIZWindow to DeviceService
5. Eventually, WIZWindow becomes a thin shell around QtAdapter

Phase 1-B Goal:
- Demonstrate integration without breaking existing functionality
- Start with device search as first migrated feature
"""

# ============================================================================
# Step 1: Add imports to main_gui.py
# ============================================================================

# Add these imports at the top of main_gui.py:
"""
from adapters.qt_adapter import QtAdapter
from core.services.device_service import DeviceService
from core.device_registry import get_global_registry
"""


# ============================================================================
# Step 2: Initialize adapter in WIZWindow.__init__()
# ============================================================================

def wizwindow_init_addon(self):
    """Add this code to WIZWindow.__init__() after existing initialization.

    This creates the adapter and service layers.
    """
    # Initialize Core registry
    config_path = 'config/devices/devices_sample.json'
    try:
        from core.device_registry import DeviceRegistry, set_global_registry
        registry = DeviceRegistry(config_path)
        set_global_registry(registry)
        self.logger.info(f"Loaded device registry: {len(registry.list_models())} models")
    except Exception as e:
        self.logger.warning(f"Could not load device registry: {e}")
        # Continue with legacy mode

    # Initialize adapter
    try:
        from adapters.qt_adapter import QtAdapter
        from core.services.device_service import DeviceService

        self.qt_adapter = QtAdapter(self)
        self.device_service = DeviceService()

        # Connect service to existing network components
        self.device_service.wizmakecmd = self.wizmakecmd
        self.device_service.conf_sock = self.conf_sock

        # Initialize adapter (connects signals)
        self.qt_adapter.initialize()

        self.logger.info("QtAdapter initialized successfully")
        self.use_new_architecture = True

    except Exception as e:
        self.logger.warning(f"Could not initialize QtAdapter: {e}")
        self.use_new_architecture = False


# ============================================================================
# Step 3: Register event handlers
# ============================================================================

def setup_adapter_handlers(window):
    """Register event handlers with adapter.

    This connects UI events to Core services through the adapter.
    """
    adapter = window.qt_adapter
    service = window.device_service

    # Search handler
    def on_search():
        window.logger.info("Search initiated via adapter")
        # For now, delegate to existing search_pre()
        window.search_pre()
        # TODO: Phase 2 will call service.search_devices()

    adapter.register_search_handler(on_search)

    # Configure/Read handler
    def on_configure(device):
        window.logger.info(f"Configure device: {device.mac_addr}")
        # TODO: Call service.read_device_config()
        pass

    adapter.register_configure_handler(on_configure)

    # Apply/Write handler
    def on_apply(device, config):
        window.logger.info(f"Apply config to: {device.mac_addr}")
        # Validate config
        errors = service.validate_config(device, config)
        if errors:
            adapter.show_error(f"Validation errors: {errors}")
            return

        # TODO: Call service.write_device_config()
        pass

    adapter.register_apply_handler(on_apply)


# ============================================================================
# Step 4: Example migration - Device display
# ============================================================================

def migrate_device_display_example(window):
    """Example: Migrate device display to use adapter.

    Old code (in get_search_result):
        rowcount = self.list_device.rowCount()
        self.list_device.insertRow(rowcount)
        item_mac = QTableWidgetItem(mac)
        self.list_device.setItem(rowcount, 0, item_mac)
        ...

    New code (using adapter):
        devices = [DeviceInfo(...), ...]
        self.qt_adapter.show_devices(devices)
    """
    pass


# ============================================================================
# Step 5: Example validation using Core
# ============================================================================

def validate_using_core_example(window, device_model_id, firmware_version):
    """Example: Validate input using Core registry.

    Old code:
        if not self.cmdset.isvalidparameter('LI', value):
            self.msg_invalid('LI')

    New code (using Core):
        model = window.device_service.get_device_model(device_model_id)
        command = model.get_command('LI', firmware_version)
        if not command.validate(value):
            window.qt_adapter.highlight_invalid_field('LI', 'Invalid IP address')
    """
    pass


# ============================================================================
# Step 6: Incremental migration checklist
# ============================================================================

"""
Phase 1-B Migration Checklist:

[x] Create BaseAdapter interface
[x] Create QtAdapter implementation
[x] Create DeviceService
[ ] Integrate adapter into WIZWindow.__init__()
[ ] Connect search button to adapter handler
[ ] Migrate device display to adapter.show_devices()
[ ] Test: Search devices using new architecture
[ ] Migrate device selection to adapter.get_selected_device()
[ ] Migrate validation to use Core Command.validate()
[ ] Test: Validate fields using new architecture

Phase 2 Migration (Future):
[ ] Migrate network layer (WIZMakeCMD, WIZMSGHandler) to Core services
[ ] Implement service.search_devices() fully in Core
[ ] Implement service.read_device_config() fully in Core
[ ] Implement service.write_device_config() fully in Core
[ ] Remove dependency on wizcmdset.py (use Core registry instead)
[ ] Create Web adapter for web UI support
"""


# ============================================================================
# Step 7: Testing the integration
# ============================================================================

def test_integration():
    """Test script for adapter integration.

    Run this to verify the integration works:
    """
    import sys
    from PyQt5.QtWidgets import QApplication
    from main_gui import WIZWindow

    app = QApplication(sys.argv)
    window = WIZWindow()

    # Verify adapter is initialized
    if hasattr(window, 'qt_adapter'):
        print("[OK] QtAdapter initialized")
        print(f"[OK] Registry has {len(window.device_service.list_device_models())} models")

        # Test adapter methods
        window.qt_adapter.show_info("Adapter integration test", "Test")
        print("[OK] Adapter show_info() works")

        # Test service methods
        models = window.device_service.list_device_models()
        print(f"[OK] Available models: {models}")

    else:
        print("[FAIL] QtAdapter not initialized")

    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    # This file is for documentation only
    # Actual integration happens in main_gui.py
    print(__doc__)
