"""Device model definition."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from packaging.version import Version

from .command import Command


@dataclass
class DeviceModel:
    """장치 모델 정의"""

    model_id: str
    display_name: str
    category: str
    commands: Dict[str, Command] = field(default_factory=dict)
    firmware_support: Dict[str, Any] = field(default_factory=dict)
    ui_tabs: List[Dict[str, Any]] = field(default_factory=list)

    def get_commands_for_version(self, version: str) -> Dict[str, Command]:
        """펌웨어 버전에 따른 명령어 세트 반환"""
        result = self.commands.copy()

        if not version or 'version_overrides' not in self.firmware_support:
            return result

        try:
            ver = Version(version)
        except Exception:
            return result

        # 버전별 오버라이드 적용
        for override_ver_str, overrides in self.firmware_support.get('version_overrides', {}).items():
            try:
                override_ver = Version(override_ver_str)
                if ver >= override_ver:
                    # 추가된 명령어
                    if 'added_commands' in overrides:
                        for cmd_code in overrides['added_commands']:
                            if cmd_code in self.commands:
                                result[cmd_code] = self.commands[cmd_code]

                    # 제거된 명령어
                    if 'removed_commands' in overrides:
                        for cmd_code in overrides['removed_commands']:
                            if cmd_code in result:
                                del result[cmd_code]

                    # 수정된 명령어
                    if 'modified_commands' in overrides:
                        for cmd_code, cmd_data in overrides['modified_commands'].items():
                            result[cmd_code] = Command.from_dict(cmd_code, cmd_data)
            except Exception:
                continue

        return result

    def get_command(self, code: str, version: Optional[str] = None) -> Optional[Command]:
        """특정 명령어 가져오기"""
        commands = self.get_commands_for_version(version) if version else self.commands
        return commands.get(code)

    def supports_version(self, version: str) -> bool:
        """펌웨어 버전 지원 여부"""
        if 'min_version' not in self.firmware_support:
            return True

        try:
            ver = Version(version)
            min_ver = Version(self.firmware_support['min_version'])

            if ver < min_ver:
                return False

            if 'max_version' in self.firmware_support:
                max_ver = Version(self.firmware_support['max_version'])
                if ver > max_ver:
                    return False

            return True
        except Exception:
            return True

    def is_one_port(self) -> bool:
        """1포트 장치 여부"""
        return self.category in ['ONE_PORT', 'SECURITY_ONE_PORT']

    def is_two_port(self) -> bool:
        """2포트 장치 여부"""
        return self.category in ['TWO_PORT', 'SECURITY_TWO_PORT']

    def has_security_features(self) -> bool:
        """보안 기능 지원 여부"""
        return self.category in ['SECURITY_ONE_PORT', 'SECURITY_TWO_PORT']

    @classmethod
    def from_dict(cls, model_id: str, data: dict, all_commands: Dict[str, Command]) -> 'DeviceModel':
        """딕셔너리에서 DeviceModel 객체 생성"""
        return cls(
            model_id=model_id,
            display_name=data.get('display_name', model_id),
            category=data.get('category', 'ONE_PORT'),
            commands=all_commands,
            firmware_support=data.get('firmware_support', {}),
            ui_tabs=data.get('ui_tabs', []),
        )

    def to_dict(self) -> dict:
        """DeviceModel 객체를 딕셔너리로 변환"""
        return {
            'display_name': self.display_name,
            'category': self.category,
            'commands': {code: cmd.to_dict() for code, cmd in self.commands.items()},
            'firmware_support': self.firmware_support,
            'ui_tabs': self.ui_tabs,
        }
