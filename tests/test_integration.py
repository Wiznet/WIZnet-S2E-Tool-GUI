#!/usr/bin/env python3
"""
Phase 2-B Integration Test

Tests the integration of new architecture with main_gui.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all necessary modules can be imported"""
    print("[*] Testing imports...")

    try:
        from core.device_registry import DeviceRegistry
        from core.services.device_service import DeviceService
        print("[OK] Core modules import successfully")

        # QtAdapter requires PyQt5, so skip if not available
        try:
            from adapters.qt_adapter import QtAdapter
            print("[OK] QtAdapter import successful (PyQt5 available)")
        except ImportError:
            print("[SKIP] QtAdapter requires PyQt5 (not available in test env)")

        return True
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False


def test_registry_initialization():
    """Test DeviceRegistry initialization"""
    print("\n[*] Testing DeviceRegistry initialization...")

    try:
        from core.device_registry import DeviceRegistry

        config_path = project_root / 'config' / 'devices' / 'devices_sample.json'

        if not config_path.exists():
            print(f"[FAIL] Config file not found: {config_path}")
            return False

        registry = DeviceRegistry(str(config_path))
        models = registry.list_models()

        print(f"[OK] Registry loaded {len(models)} models")
        print(f"[OK] Models: {', '.join(models)}")

        return True

    except Exception as e:
        print(f"[FAIL] Registry initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_service_initialization():
    """Test DeviceService initialization"""
    print("\n[*] Testing DeviceService initialization...")

    try:
        from core.device_registry import DeviceRegistry
        from core.services.device_service import DeviceService

        config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
        registry = DeviceRegistry(str(config_path))

        service = DeviceService(registry)
        models = service.list_device_models()

        print(f"[OK] Service initialized with {len(models)} models")

        # Test validation
        from core.models.device_config import DeviceInfo

        device = DeviceInfo(
            mac_addr='00:08:DC:12:34:56',
            model_id='WIZ750SR',
            firmware_version='1.0.0'
        )

        config = {'LI': '192.168.1.100', 'BR': '12'}
        errors = service.validate_config(device, config)

        if not errors:
            print("[OK] Service validation working")
        else:
            print(f"[FAIL] Validation failed: {errors}")
            return False

        return True

    except Exception as e:
        print(f"[FAIL] Service initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_qt_adapter_mock():
    """Test QtAdapter with mock window"""
    print("\n[*] Testing QtAdapter (mock)...")

    try:
        # Skip if PyQt5 not available
        try:
            import PyQt5
        except ImportError:
            print("[SKIP] PyQt5 not available, skipping QtAdapter test")
            return True

        from adapters.qt_adapter import QtAdapter
        from core.models.device_config import DeviceInfo

        # Create a minimal mock window
        class MockWindow:
            def __init__(self):
                self.logger = self._create_logger()
                self.list_device = MockTable()
                self.pgbar = MockProgressBar()
                self.btn_search = MockButton()
                self.btn_setting = MockButton()
                self.btn_apply = MockButton()
                self.tabWidget = MockTabWidget()

            def _create_logger(self):
                import logging
                logger = logging.getLogger('test')
                logger.setLevel(logging.INFO)
                return logger

            def findChild(self, types, name):
                return None

            def findChildren(self, widget_type):
                return []

        class MockTable:
            def clear(self): pass
            def setRowCount(self, n): pass
            def setItem(self, row, col, item): pass
            def item(self, row, col): return None
            def selectedItems(self): return []

        class MockProgressBar:
            def setFormat(self, text): pass
            def setRange(self, min, max): pass
            def setValue(self, val): pass
            def show(self): pass
            def hide(self): pass

        class MockButton:
            def setEnabled(self, enabled): pass

            class _clicked:
                def connect(self, handler): pass

            clicked = _clicked()

        class MockTabWidget:
            def setEnabled(self, enabled): pass

        window = MockWindow()
        adapter = QtAdapter(window)

        print("[OK] QtAdapter instantiated")

        # Test show_devices
        devices = [
            DeviceInfo('00:08:DC:11:11:11', 'WIZ750SR', '1.0.0', '192.168.1.100'),
            DeviceInfo('00:08:DC:22:22:22', 'W55RP20-S2E', '1.1.8', '192.168.1.101'),
        ]

        adapter.show_devices(devices)
        print("[OK] show_devices() executed")

        # Test event handler registration
        def test_handler():
            pass

        adapter.register_search_handler(test_handler)
        print("[OK] Event handler registration working")

        return True

    except Exception as e:
        print(f"[FAIL] QtAdapter test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("="*60)
    print("Phase 2-B Integration Test")
    print("="*60)
    print()

    tests = [
        ("Imports", test_imports),
        ("Registry Initialization", test_registry_initialization),
        ("Service Initialization", test_service_initialization),
        ("QtAdapter (Mock)", test_qt_adapter_mock),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n[FAIL] {test_name} test failed")
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] {test_name} test error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    if failed == 0:
        print(f"[PASS] All {passed} tests passed!")
    else:
        print(f"[FAIL] {passed} passed, {failed} failed")
    print("="*60)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
