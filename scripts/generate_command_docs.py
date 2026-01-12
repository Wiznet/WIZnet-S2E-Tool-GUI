#!/usr/bin/env python3
"""
명령어 레퍼런스 문서 자동 생성 스크립트

Usage:
    python generate_command_docs.py
    python generate_command_docs.py --output docs/COMMAND_REFERENCE.md
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class CommandDocsGenerator:
    """명령어 문서 생성기"""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = None
        self.command_cache = {}

    def load_config(self) -> bool:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[ERROR] Failed to load config: {e}")
            return False

    def resolve_commands(self, cmdset_name: str, visited=None) -> dict:
        """명령어 세트 상속 해결"""
        if visited is None:
            visited = set()

        if cmdset_name in self.command_cache:
            return self.command_cache[cmdset_name]

        if cmdset_name in visited:
            return {}

        visited.add(cmdset_name)

        command_sets = self.config.get('command_sets', {})
        if cmdset_name not in command_sets:
            return {}

        cmdset = command_sets[cmdset_name]
        commands = {}

        # 부모 명령어 먼저 로드
        if 'inherits_from' in cmdset:
            parent_commands = self.resolve_commands(cmdset['inherits_from'], visited)
            commands.update(parent_commands)

        # 자신의 명령어로 덮어쓰기
        if 'commands' in cmdset:
            commands.update(cmdset['commands'])

        self.command_cache[cmdset_name] = commands
        return commands

    def get_device_commands(self, model_id: str) -> dict:
        """장치 모델의 명령어 가져오기"""
        device_models = self.config.get('device_models', {})
        if model_id not in device_models:
            return {}

        model = device_models[model_id]

        # 기본 명령어 세트에서 시작
        cmdset_name = model.get('inherits_from', 'common')
        commands = self.resolve_commands(cmdset_name)

        # 펌웨어 버전별 명령어 추가 (최신 버전 기준)
        if 'firmware_support' in model:
            fw_support = model['firmware_support']
            if 'version_overrides' in fw_support:
                # 모든 버전의 추가 명령어 포함
                for version, overrides in fw_support['version_overrides'].items():
                    if 'added_commands' in overrides:
                        # 추가된 명령어 코드만 있으므로, 실제 명령어 정의는 찾아야 함
                        pass

        return commands

    def generate_markdown(self, output_path: str):
        """Markdown 문서 생성"""
        if not self.config:
            return False

        lines = []

        # 헤더
        lines.append("# WIZnet S2E 명령어 레퍼런스")
        lines.append("")
        lines.append(f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**소스**: {self.config_path}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 목차
        lines.append("## 목차")
        lines.append("")
        device_models = self.config.get('device_models', {})
        for model_id, model_data in device_models.items():
            display_name = model_data.get('display_name', model_id)
            lines.append(f"- [{display_name}](#{model_id.lower().replace('_', '-')})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 각 장치 모델별 명령어
        for model_id, model_data in device_models.items():
            display_name = model_data.get('display_name', model_id)
            category = model_data.get('category', 'Unknown')

            lines.append(f"## {display_name}")
            lines.append("")
            lines.append(f"**모델 ID**: `{model_id}`")
            lines.append(f"**카테고리**: {category}")
            lines.append("")

            # 펌웨어 정보
            if 'firmware_support' in model_data:
                fw_support = model_data['firmware_support']
                if 'min_version' in fw_support:
                    lines.append(f"**최소 펌웨어 버전**: {fw_support['min_version']}")
                    lines.append("")

            # 명령어 테이블
            commands = self.get_device_commands(model_id)

            if commands:
                lines.append("### 명령어 목록")
                lines.append("")
                lines.append("| 코드 | 이름 | 접근 | 패턴 | 옵션 | UI 위젯 |")
                lines.append("|------|------|------|------|------|---------|")

                for code in sorted(commands.keys()):
                    cmd = commands[code]
                    name = cmd.get('name', code)
                    access = cmd.get('access', 'N/A')

                    # 접근 모드 한글화
                    access_kr = {
                        'RO': '읽기전용',
                        'RW': '읽기/쓰기',
                        'WO': '쓰기전용'
                    }.get(access, access)

                    pattern = cmd.get('pattern', '')
                    if pattern:
                        # 패턴이 너무 길면 줄임
                        if len(pattern) > 30:
                            pattern = pattern[:27] + '...'
                        pattern = f"`{pattern}`"
                    else:
                        pattern = '-'

                    options = cmd.get('options', {})
                    if options:
                        opt_count = len(options)
                        options_str = f"{opt_count}개 옵션"
                    else:
                        options_str = '-'

                    ui_widget = cmd.get('ui_widget', '-')

                    lines.append(f"| `{code}` | {name} | {access_kr} | {pattern} | {options_str} | `{ui_widget}` |")

                lines.append("")

                # 옵션이 있는 명령어 상세 정보
                lines.append("### 명령어 상세")
                lines.append("")

                for code in sorted(commands.keys()):
                    cmd = commands[code]
                    options = cmd.get('options', {})

                    if options:
                        name = cmd.get('name', code)
                        lines.append(f"#### {code} - {name}")
                        lines.append("")

                        # 옵션 테이블
                        lines.append("| 값 | 설명 |")
                        lines.append("|-----|------|")

                        for value, description in sorted(options.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                            lines.append(f"| `{value}` | {description} |")

                        lines.append("")

            else:
                lines.append("*명령어 없음*")
                lines.append("")

            lines.append("---")
            lines.append("")

        # 명령어 세트 정보
        lines.append("## 명령어 세트")
        lines.append("")

        command_sets = self.config.get('command_sets', {})
        for cmdset_name, cmdset_data in command_sets.items():
            lines.append(f"### {cmdset_name}")
            lines.append("")

            if 'inherits_from' in cmdset_data:
                lines.append(f"**상속**: `{cmdset_data['inherits_from']}`")
                lines.append("")

            commands = cmdset_data.get('commands', {})
            lines.append(f"**명령어 수**: {len(commands)}")
            lines.append("")

        # 파일 작성
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"[OK] Generated command reference: {output_path}")
        return True


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate command reference documentation from JSON config"
    )
    parser.add_argument(
        '--config',
        default='config/devices/devices_sample.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--output',
        default='docs/COMMAND_REFERENCE.md',
        help='Output markdown file path'
    )

    args = parser.parse_args()

    generator = CommandDocsGenerator(args.config)

    if not generator.load_config():
        sys.exit(1)

    if not generator.generate_markdown(args.output):
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
