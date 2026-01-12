#!/usr/bin/env python3
"""
장치/명령어 템플릿 생성 도구

Usage:
    python create_template.py device <model_id> <display_name> [--base <base_model>]
    python create_template.py command <code> <name> [--access RW] [--widget text]
    python create_template.py cmdset <name> [--inherits <parent>]
"""

import json
import sys
from pathlib import Path


class TemplateGenerator:
    """템플릿 생성기"""

    def create_device_template(self, model_id: str, display_name: str,
                                category: str = "ONE_PORT",
                                base_model: str = None) -> dict:
        """장치 모델 템플릿 생성"""
        template = {
            model_id: {
                "display_name": display_name,
                "category": category,
                "inherits_from": base_model or "common",
                "firmware_support": {
                    "min_version": "1.0.0"
                }
            }
        }

        return template

    def create_command_template(self, code: str, name: str,
                                 access: str = "RW",
                                 widget: str = "text",
                                 pattern: str = "") -> dict:
        """명령어 템플릿 생성"""
        template = {
            code: {
                "name": name,
                "pattern": pattern,
                "access": access,
                "options": {},
                "ui_widget": widget,
                "ui_group": "General",
                "ui_order": 100
            }
        }

        return template

    def create_cmdset_template(self, name: str, inherits: str = None) -> dict:
        """명령어 세트 템플릿 생성"""
        template = {
            name: {
                "commands": {}
            }
        }

        if inherits:
            template[name]["inherits_from"] = inherits

        return template

    def print_json(self, template: dict):
        """JSON 출력"""
        print(json.dumps(template, indent=2, ensure_ascii=False))

    def add_to_config(self, config_path: str, template_type: str, template: dict) -> bool:
        """설정 파일에 템플릿 추가"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if template_type == 'device':
                if 'device_models' not in config:
                    config['device_models'] = {}
                config['device_models'].update(template)

            elif template_type == 'cmdset':
                if 'command_sets' not in config:
                    config['command_sets'] = {}
                config['command_sets'].update(template)

            elif template_type == 'command':
                # 명령어는 특정 명령어 세트에 추가해야 함
                print("[INFO] Command templates should be added to a specific command set manually")
                return False

            # 백업
            backup_path = str(Path(config_path).with_suffix('.json.backup'))
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # 저장
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"[OK] Added to config: {config_path}")
            print(f"[INFO] Backup saved to: {backup_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to add to config: {e}")
            return False


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate templates for devices and commands"
    )

    subparsers = parser.add_subparsers(dest='type', help='Template type')

    # Device template
    device_parser = subparsers.add_parser('device', help='Create device template')
    device_parser.add_argument('model_id', help='Model ID (e.g., MY_DEVICE)')
    device_parser.add_argument('display_name', help='Display name')
    device_parser.add_argument('--category', default='ONE_PORT',
                               choices=['ONE_PORT', 'TWO_PORT', 'SECURITY_ONE_PORT', 'SECURITY_TWO_PORT'])
    device_parser.add_argument('--base', help='Base model to inherit from')
    device_parser.add_argument('--add-to-config', help='Add to config file')

    # Command template
    cmd_parser = subparsers.add_parser('command', help='Create command template')
    cmd_parser.add_argument('code', help='Command code (e.g., XX)')
    cmd_parser.add_argument('name', help='Command name')
    cmd_parser.add_argument('--access', default='RW', choices=['RO', 'RW', 'WO'])
    cmd_parser.add_argument('--widget', default='text',
                            choices=['text', 'number', 'combo', 'checkbox', 'ipaddr', 'mac', 'ipport'])
    cmd_parser.add_argument('--pattern', default='', help='Regex pattern')

    # Command set template
    cmdset_parser = subparsers.add_parser('cmdset', help='Create command set template')
    cmdset_parser.add_argument('name', help='Command set name')
    cmdset_parser.add_argument('--inherits', help='Parent command set')
    cmdset_parser.add_argument('--add-to-config', help='Add to config file')

    args = parser.parse_args()

    if not args.type:
        parser.print_help()
        sys.exit(1)

    generator = TemplateGenerator()

    if args.type == 'device':
        template = generator.create_device_template(
            args.model_id,
            args.display_name,
            args.category,
            args.base
        )
        generator.print_json(template)

        if args.add_to_config:
            generator.add_to_config(args.add_to_config, 'device', template)

    elif args.type == 'command':
        template = generator.create_command_template(
            args.code,
            args.name,
            args.access,
            args.widget,
            args.pattern
        )
        generator.print_json(template)

    elif args.type == 'cmdset':
        template = generator.create_cmdset_template(
            args.name,
            args.inherits
        )
        generator.print_json(template)

        if args.add_to_config:
            generator.add_to_config(args.add_to_config, 'cmdset', template)


if __name__ == '__main__':
    main()
