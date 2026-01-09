#!/usr/bin/env python3
"""
Adapter and Service Layer 테스트 스크립트

Usage:
    python tests/test_adapter.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.device_registry import DeviceRegistry
from core.services.device_service import DeviceService
from core.models.device_config import DeviceInfo


def test_device_service():
    """DeviceService 테스트"""
    print("[*] Testing DeviceService...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))
    service = DeviceService(registry)

    # 모델 조회 테스트
    models = service.list_device_models()
    print(f"[OK] Service has {len(models)} device models")

    # 특정 모델 가져오기
    wiz750sr = service.get_device_model('WIZ750SR')
    if wiz750sr:
        print(f"[OK] Got model: {wiz750sr.display_name}")
    else:
        print("[FAIL] Could not get WIZ750SR model")
        return False

    # 명령어 조회 테스트
    commands = service.get_commands_for_device('WIZ750SR', '1.0.0')
    if commands:
        print(f"[OK] WIZ750SR v1.0.0 has {len(commands)} commands")
    else:
        print("[FAIL] Could not get commands")
        return False

    return True


def test_validation():
    """설정 검증 테스트"""
    print("\n[*] Testing configuration validation...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))
    service = DeviceService(registry)

    # 테스트 장치 정보
    device = DeviceInfo(
        mac_addr='00:08:DC:12:34:56',
        model_id='WIZ750SR',
        firmware_version='1.0.0',
        ip_addr='192.168.1.100'
    )

    # 유효한 설정
    valid_config = {
        'LI': '192.168.1.100',
        'SM': '255.255.255.0',
        'BR': '12',  # 115200
    }

    errors = service.validate_config(device, valid_config)
    if not errors:
        print("[OK] Valid config passed validation")
    else:
        print(f"[FAIL] Valid config failed: {errors}")
        return False

    # 잘못된 IP 주소
    invalid_config = {
        'LI': '999.999.999.999',  # Invalid IP
    }

    errors = service.validate_config(device, invalid_config)
    if errors and 'LI' in errors:
        print("[OK] Invalid IP detected correctly")
    else:
        print("[FAIL] Invalid IP not detected")
        return False

    # 읽기 전용 명령어 쓰기 시도
    readonly_config = {
        'VR': '1.2.3',  # VR is read-only
    }

    errors = service.validate_config(device, readonly_config)
    if errors and 'VR' in errors:
        print("[OK] Read-only command write blocked")
    else:
        print("[FAIL] Read-only command write not blocked")
        return False

    # 알 수 없는 명령어
    unknown_config = {
        'UNKNOWN': 'value',
    }

    errors = service.validate_config(device, unknown_config)
    if errors and 'UNKNOWN' in errors:
        print("[OK] Unknown command detected")
    else:
        print("[FAIL] Unknown command not detected")
        return False

    return True


def test_firmware_version_commands():
    """펌웨어 버전별 명령어 테스트"""
    print("\n[*] Testing firmware version support in service...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))
    service = DeviceService(registry)

    # v1.0.0 (MB 없음)
    commands_v1_0_0 = service.get_commands_for_device('WIZ750SR', '1.0.0')
    has_mb_v1_0_0 = commands_v1_0_0 and 'MB' in commands_v1_0_0

    # v1.4.4 (MB 있음)
    commands_v1_4_4 = service.get_commands_for_device('WIZ750SR', '1.4.4')
    has_mb_v1_4_4 = commands_v1_4_4 and 'MB' in commands_v1_4_4

    print(f"[OK] WIZ750SR v1.0.0: MB = {has_mb_v1_0_0}")
    print(f"[OK] WIZ750SR v1.4.4: MB = {has_mb_v1_4_4}")

    if not has_mb_v1_0_0 and has_mb_v1_4_4:
        print("[OK] Firmware version support working in service")
        return True
    else:
        print("[FAIL] Firmware version support not working")
        return False


def test_adapter_interface():
    """어댑터 인터페이스 테스트"""
    print("\n[*] Testing adapter interface...")

    # BaseAdapter를 상속하는 Mock 어댑터
    from adapters.base_adapter import BaseUIAdapter

    class MockAdapter(BaseUIAdapter):
        def __init__(self):
            self.displayed_devices = []
            self.errors = []
            self.warnings = []
            self.info_messages = []

        def show_devices(self, devices):
            self.displayed_devices = devices

        def show_device_config(self, config, model):
            pass

        def show_error(self, message, title=None):
            self.errors.append(message)

        def show_warning(self, message, title=None):
            self.warnings.append(message)

        def show_info(self, message, title=None):
            self.info_messages.append(message)

        def show_progress(self, message, value=None, maximum=None):
            pass

        def hide_progress(self):
            pass

        def ask_confirmation(self, message, title=None):
            return True

        def get_selected_device(self):
            return self.displayed_devices[0] if self.displayed_devices else None

        def get_device_config_from_ui(self):
            return {}

        def enable_ui(self, enabled):
            pass

        def update_command_fields(self, model, firmware_version):
            pass

        def set_field_value(self, command_code, value):
            pass

        def get_field_value(self, command_code):
            return None

        def validate_fields(self, model):
            return True

        def highlight_invalid_field(self, command_code, error_message):
            pass

        def clear_field_highlights(self):
            pass

    # Mock 어댑터 테스트
    adapter = MockAdapter()

    # 장치 표시 테스트
    test_devices = [
        DeviceInfo(
            mac_addr='00:08:DC:11:11:11',
            model_id='WIZ750SR',
            firmware_version='1.0.0',
            ip_addr='192.168.1.100'
        ),
        DeviceInfo(
            mac_addr='00:08:DC:22:22:22',
            model_id='W55RP20-S2E',
            firmware_version='1.1.8',
            ip_addr='192.168.1.101'
        ),
    ]

    adapter.show_devices(test_devices)
    if len(adapter.displayed_devices) == 2:
        print("[OK] Adapter show_devices() works")
    else:
        print("[FAIL] Adapter show_devices() failed")
        return False

    # 메시지 표시 테스트
    adapter.show_error("Test error")
    adapter.show_warning("Test warning")
    adapter.show_info("Test info")

    if (len(adapter.errors) == 1 and
        len(adapter.warnings) == 1 and
        len(adapter.info_messages) == 1):
        print("[OK] Adapter message methods work")
    else:
        print("[FAIL] Adapter message methods failed")
        return False

    # 이벤트 핸들러 등록 테스트
    handler_called = [False]

    def test_handler():
        handler_called[0] = True

    adapter.register_search_handler(test_handler)
    if hasattr(adapter, '_search_handler'):
        adapter._search_handler()
        if handler_called[0]:
            print("[OK] Adapter event handler registration works")
        else:
            print("[FAIL] Handler not called")
            return False
    else:
        print("[FAIL] Handler not registered")
        return False

    return True


def main():
    """메인 함수"""
    print("="*60)
    print("WIZnet S2E Adapter & Service Layer Test")
    print("="*60)
    print()

    try:
        # 테스트 실행
        tests = [
            ("DeviceService", test_device_service),
            ("Validation", test_validation),
            ("Firmware Version", test_firmware_version_commands),
            ("Adapter Interface", test_adapter_interface),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
                    print(f"[FAIL] {test_name} test failed")
            except Exception as e:
                failed += 1
                print(f"[FAIL] {test_name} test error: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "="*60)
        if failed == 0:
            print(f"[PASS] All {passed} tests passed!")
        else:
            print(f"[FAIL] {passed} passed, {failed} failed")
        print("="*60)

        sys.exit(0 if failed == 0 else 1)

    except Exception as e:
        print("\n" + "="*60)
        print(f"[FAIL] Test suite failed: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
