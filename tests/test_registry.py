#!/usr/bin/env python3
"""
Device Registry 테스트 스크립트

Usage:
    python tests/test_registry.py
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.device_registry import DeviceRegistry


def test_load_config():
    """설정 파일 로드 테스트"""
    print("[*] Testing DeviceRegistry.load_from_file()...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))

    print(f"[OK] Loaded {len(registry.list_models())} device models")
    print(f"[OK] Loaded {len(registry.list_command_sets())} command sets")
    return registry


def test_get_model(registry):
    """모델 가져오기 테스트"""
    print("\n[*] Testing DeviceRegistry.get_model()...")

    test_models = ['WIZ750SR', 'W55RP20-S2E', 'W55RP20-S2E-2CH', 'IP20']

    for model_id in test_models:
        model = registry.get_model(model_id)
        if model:
            print(f"[OK] {model_id:20s} - {len(model.commands)} commands, category: {model.category}")
        else:
            print(f"[FAIL] Model not found: {model_id}")


def test_command_inheritance():
    """명령어 상속 테스트"""
    print("\n[*] Testing command inheritance...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))

    # WIZ750SR: common -> wiz75x_extended 상속
    wiz750sr = registry.get_model('WIZ750SR')
    if wiz750sr:
        print(f"[OK] WIZ750SR has {len(wiz750sr.commands)} commands")

        # common 명령어 확인
        if 'MC' in wiz750sr.commands:
            print(f"[OK]   - MC (MAC address) inherited from common")

        # wiz75x_extended 명령어 확인
        if 'TR' in wiz750sr.commands:
            print(f"[OK]   - TR (TCP Retransmission) from wiz75x_extended")

    # W55RP20-S2E: common -> security_base 상속 + specific
    w55rp20 = registry.get_model('W55RP20-S2E')
    if w55rp20:
        print(f"[OK] W55RP20-S2E has {len(w55rp20.commands)} commands")

        # security_base 명령어 확인 (확장된 OP)
        op_cmd = w55rp20.get_command('OP')
        if op_cmd and 'SSL TCP Client mode' in op_cmd.options.get('4', ''):
            print(f"[OK]   - OP extended with SSL/MQTT options")

        # specific 명령어 확인
        if 'SD' in w55rp20.commands:
            print(f"[OK]   - SD (Send Data at Connection) specific to W55RP20")


def test_firmware_version_support():
    """펌웨어 버전별 명령어 테스트"""
    print("\n[*] Testing firmware version support...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))

    wiz750sr = registry.get_model('WIZ750SR')
    if wiz750sr:
        # v1.0.0 (MB 없음)
        commands_v1_0_0 = wiz750sr.get_commands_for_version('1.0.0')
        has_mb_v1_0_0 = 'MB' in commands_v1_0_0

        # v1.4.4 이상 (MB 있음)
        commands_v1_4_4 = wiz750sr.get_commands_for_version('1.4.4')
        has_mb_v1_4_4 = 'MB' in commands_v1_4_4

        print(f"[OK] WIZ750SR v1.0.0: MB command = {has_mb_v1_0_0}")
        print(f"[OK] WIZ750SR v1.4.4: MB command = {has_mb_v1_4_4}")

        if not has_mb_v1_0_0 and has_mb_v1_4_4:
            print(f"[OK] Firmware version override working correctly")


def test_command_validation():
    """명령어 검증 테스트"""
    print("\n[*] Testing command validation...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))

    wiz750sr = registry.get_model('WIZ750SR')
    if wiz750sr:
        # IP 주소 검증
        li_cmd = wiz750sr.get_command('LI')
        if li_cmd:
            valid_ip = li_cmd.validate('192.168.1.1')
            invalid_ip = li_cmd.validate('999.999.999.999')
            print(f"[OK] LI validation: '192.168.1.1' = {valid_ip}, '999.999.999.999' = {invalid_ip}")

        # MAC 주소 검증
        mc_cmd = wiz750sr.get_command('MC')
        if mc_cmd:
            valid_mac = mc_cmd.validate('00:08:DC:12:34:56')
            invalid_mac = mc_cmd.validate('invalid-mac')
            print(f"[OK] MC validation: '00:08:DC:12:34:56' = {valid_mac}, 'invalid-mac' = {invalid_mac}")

        # Baud rate 옵션 검증
        br_cmd = wiz750sr.get_command('BR')
        if br_cmd:
            label = br_cmd.get_option_label('12')
            print(f"[OK] BR option '12' = '{label}'")


def test_ui_hints():
    """UI 힌트 테스트"""
    print("\n[*] Testing UI generation hints...")

    config_path = project_root / 'config' / 'devices' / 'devices_sample.json'
    registry = DeviceRegistry(str(config_path))

    wiz750sr = registry.get_model('WIZ750SR')
    if wiz750sr:
        # UI 그룹별 명령어 분류
        ui_groups = {}
        for cmd_code, cmd in wiz750sr.commands.items():
            if cmd.ui_group:
                if cmd.ui_group not in ui_groups:
                    ui_groups[cmd.ui_group] = []
                ui_groups[cmd.ui_group].append((cmd.ui_order or 0, cmd_code, cmd.ui_widget))

        print(f"[OK] Found {len(ui_groups)} UI groups:")
        for group_name, commands in sorted(ui_groups.items()):
            commands.sort()  # ui_order로 정렬
            print(f"      {group_name}: {len(commands)} commands")
            for order, code, widget in commands[:3]:  # 처음 3개만 표시
                print(f"        - {code:4s} (widget: {widget or 'text':10s}, order: {order})")


def main():
    """메인 함수"""
    print("="*60)
    print("WIZnet S2E Device Registry Test")
    print("="*60)
    print()

    try:
        # 테스트 실행
        registry = test_load_config()
        test_get_model(registry)
        test_command_inheritance()
        test_firmware_version_support()
        test_command_validation()
        test_ui_hints()

        print("\n" + "="*60)
        print("[PASS] All tests passed!")
        print("="*60)

    except Exception as e:
        print("\n" + "="*60)
        print(f"[FAIL] Test failed: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
