#!/usr/bin/env python3
"""
JSON 설정 파일 검증 스크립트

Usage:
    python validate_config.py
    python validate_config.py --verbose
"""

import json
import sys
from pathlib import Path
import re

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ConfigValidator:
    """설정 파일 검증기"""

    def __init__(self, config_path: str, verbose: bool = False):
        self.config_path = Path(config_path)
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        self.config = None

    def load_config(self) -> bool:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.log_info(f"[OK] Loaded config from {self.config_path}")
            return True
        except FileNotFoundError:
            self.add_error(f"Config file not found: {self.config_path}")
            return False
        except json.JSONDecodeError as e:
            self.add_error(f"Invalid JSON: {e}")
            return False

    def validate_schema_version(self) -> bool:
        """스키마 버전 검증"""
        if 'schema_version' not in self.config:
            self.add_error("Missing 'schema_version' field")
            return False

        version = self.config['schema_version']
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            self.add_error(f"Invalid schema_version format: {version}")
            return False

        self.log_info(f"[OK] Schema version: {version}")
        return True

    def validate_command_sets(self) -> bool:
        """명령어 세트 검증"""
        if 'command_sets' not in self.config:
            self.add_error("Missing 'command_sets' field")
            return False

        command_sets = self.config['command_sets']
        if not isinstance(command_sets, dict) or len(command_sets) == 0:
            self.add_error("'command_sets' must be a non-empty dictionary")
            return False

        all_valid = True
        for cmdset_name, cmdset_data in command_sets.items():
            self.log_info(f"  Validating command set: {cmdset_name}")

            # 상속 검증
            if 'inherits_from' in cmdset_data:
                parent = cmdset_data['inherits_from']
                if parent not in command_sets:
                    self.add_error(
                        f"Command set '{cmdset_name}' inherits from unknown set '{parent}'"
                    )
                    all_valid = False

            # 명령어 검증
            if 'commands' not in cmdset_data:
                self.add_error(f"Command set '{cmdset_name}' missing 'commands' field")
                all_valid = False
                continue

            commands = cmdset_data['commands']
            for cmd_code, cmd_data in commands.items():
                if not self.validate_command(cmd_code, cmd_data, cmdset_name):
                    all_valid = False

        if all_valid:
            self.log_info(f"[OK] All {len(command_sets)} command sets valid")
        return all_valid

    def validate_command(self, code: str, data: dict, parent: str) -> bool:
        """단일 명령어 검증"""
        # 필수 필드 검증
        required_fields = ['name', 'access']
        for field in required_fields:
            if field not in data:
                self.add_error(
                    f"Command '{code}' in '{parent}' missing required field '{field}'"
                )
                return False

        # Access 모드 검증
        if data['access'] not in ['RO', 'RW', 'WO']:
            self.add_error(
                f"Command '{code}' in '{parent}' has invalid access mode: {data['access']}"
            )
            return False

        # 정규식 패턴 검증
        if 'pattern' in data and data['pattern']:
            try:
                re.compile(data['pattern'])
            except re.error as e:
                self.add_error(
                    f"Command '{code}' in '{parent}' has invalid regex pattern: {e}"
                )
                return False

        # UI 위젯 검증
        valid_widgets = ['text', 'number', 'combo', 'checkbox', 'ip', 'mac', 'textarea']
        if 'ui_widget' in data and data['ui_widget'] not in valid_widgets:
            self.add_warning(
                f"Command '{code}' in '{parent}' has unknown ui_widget: {data['ui_widget']}"
            )

        return True

    def validate_device_models(self) -> bool:
        """장치 모델 검증"""
        if 'device_models' not in self.config:
            self.add_error("Missing 'device_models' field")
            return False

        device_models = self.config['device_models']
        if not isinstance(device_models, dict) or len(device_models) == 0:
            self.add_error("'device_models' must be a non-empty dictionary")
            return False

        all_valid = True
        for model_id, model_data in device_models.items():
            self.log_info(f"  Validating device model: {model_id}")

            # 필수 필드 검증
            required_fields = ['display_name', 'category']
            for field in required_fields:
                if field not in model_data:
                    self.add_error(f"Device model '{model_id}' missing field '{field}'")
                    all_valid = False

            # 카테고리 검증
            valid_categories = [
                'ONE_PORT', 'TWO_PORT',
                'SECURITY_ONE_PORT', 'SECURITY_TWO_PORT'
            ]
            if 'category' in model_data and model_data['category'] not in valid_categories:
                self.add_error(
                    f"Device model '{model_id}' has invalid category: {model_data['category']}"
                )
                all_valid = False

            # 상속 검증
            if 'inherits_from' in model_data:
                parent_cmdset = model_data['inherits_from']
                if parent_cmdset not in self.config['command_sets']:
                    self.add_error(
                        f"Device model '{model_id}' inherits from unknown command set '{parent_cmdset}'"
                    )
                    all_valid = False

            # 펌웨어 지원 검증
            if 'firmware_support' in model_data:
                if not self.validate_firmware_support(model_id, model_data['firmware_support']):
                    all_valid = False

        if all_valid:
            self.log_info(f"[OK] All {len(device_models)} models valid")
        return all_valid

    def validate_firmware_support(self, model_id: str, fw_support: dict) -> bool:
        """펌웨어 지원 정보 검증"""
        if 'min_version' in fw_support:
            if not re.match(r'^\d+\.\d+\.\d+', fw_support['min_version']):
                self.add_error(
                    f"Device model '{model_id}' has invalid min_version format"
                )
                return False

        if 'version_overrides' in fw_support:
            for version, overrides in fw_support['version_overrides'].items():
                if not re.match(r'^\d+\.\d+\.\d+', version):
                    self.add_error(
                        f"Device model '{model_id}' has invalid version override: {version}"
                    )
                    return False

                # 추가된 명령어가 실제로 존재하는지 검증
                if 'added_commands' in overrides:
                    for cmd_code in overrides['added_commands']:
                        # 이 검증은 실제 명령어 세트를 완전히 해결한 후 가능
                        pass

        return True

    def validate_command_inheritance(self) -> bool:
        """명령어 상속 체인 검증"""
        command_sets = self.config['command_sets']
        visited = set()

        def check_cycle(name, chain):
            if name in chain:
                self.add_error(f"Circular inheritance detected: {' -> '.join(chain + [name])}")
                return False
            if name in visited:
                return True

            visited.add(name)
            if name not in command_sets:
                return True

            cmdset = command_sets[name]
            if 'inherits_from' in cmdset:
                parent = cmdset['inherits_from']
                return check_cycle(parent, chain + [name])
            return True

        all_valid = True
        for cmdset_name in command_sets:
            if not check_cycle(cmdset_name, []):
                all_valid = False

        if all_valid:
            self.log_info("[OK] No circular inheritance detected")
        return all_valid

    def generate_statistics(self):
        """통계 생성"""
        if not self.config:
            return

        cmdsets = self.config.get('command_sets', {})
        models = self.config.get('device_models', {})

        total_commands = sum(
            len(cs.get('commands', {})) for cs in cmdsets.values()
        )

        print("\n" + "="*60)
        print("[STATS] Configuration Statistics")
        print("="*60)
        print(f"  Command Sets:   {len(cmdsets)}")
        print(f"  Total Commands: {total_commands}")
        print(f"  Device Models:  {len(models)}")
        print()
        print("  Device Models:")
        for model_id, model_data in models.items():
            category = model_data.get('category', 'Unknown')
            print(f"    - {model_id:20s} ({category})")
        print("="*60)

    def add_error(self, message: str):
        """에러 추가"""
        self.errors.append(message)
        print(f"[ERROR] {message}")

    def add_warning(self, message: str):
        """경고 추가"""
        self.warnings.append(message)
        if self.verbose:
            print(f"[WARN] {message}")

    def log_info(self, message: str):
        """정보 로그"""
        if self.verbose:
            print(f"[INFO] {message}")

    def validate_all(self) -> bool:
        """전체 검증 수행"""
        print("[*] Validating WIZnet S2E Configuration...")
        print()

        if not self.load_config():
            return False

        validators = [
            ("Schema Version", self.validate_schema_version),
            ("Command Sets", self.validate_command_sets),
            ("Device Models", self.validate_device_models),
            ("Inheritance Chain", self.validate_command_inheritance),
        ]

        all_valid = True
        for name, validator in validators:
            print(f"Validating {name}...")
            if not validator():
                all_valid = False
            print()

        # 통계 출력
        if all_valid:
            self.generate_statistics()

        # 결과 요약
        print("\n" + "="*60)
        if all_valid:
            print("[PASS] Validation PASSED")
            print(f"   {len(self.warnings)} warning(s)")
        else:
            print("[FAIL] Validation FAILED")
            print(f"   {len(self.errors)} error(s)")
            print(f"   {len(self.warnings)} warning(s)")
        print("="*60)

        return all_valid


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate WIZnet S2E device configuration JSON"
    )
    parser.add_argument(
        '--config',
        default='config/devices/devices_sample.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    validator = ConfigValidator(args.config, verbose=args.verbose)
    success = validator.validate_all()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
