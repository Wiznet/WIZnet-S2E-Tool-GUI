"""Global device registry for loading and managing device models."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models.command import Command
from .models.device_model import DeviceModel


class DeviceRegistry:
    """전역 장치 레지스트리"""

    def __init__(self, config_path: Optional[str] = None):
        self._models: Dict[str, DeviceModel] = {}
        self._command_sets: Dict[str, Dict[str, Command]] = {}

        if config_path:
            self.load_from_file(config_path)

    def load_from_file(self, config_path: str):
        """설정 파일에서 로드"""
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self._parse_config(config)

    def _parse_config(self, config: dict):
        """설정 파싱"""
        # 1. 명령어 세트 파싱
        self._parse_command_sets(config.get('command_sets', {}))

        # 2. 장치 모델 파싱
        self._parse_device_models(config.get('device_models', {}))

    def _parse_command_sets(self, command_sets: dict):
        """명령어 세트 파싱 (상속 처리)"""
        self._command_sets.clear()

        # 먼저 모든 명령어 세트를 파싱 (상속 없이)
        for cmdset_name, cmdset_data in command_sets.items():
            commands = {}
            for cmd_code, cmd_data in cmdset_data.get('commands', {}).items():
                commands[cmd_code] = Command.from_dict(cmd_code, cmd_data)
            self._command_sets[cmdset_name] = commands

        # 상속 관계 해결
        resolved = {}
        for cmdset_name in command_sets:
            resolved[cmdset_name] = self._resolve_command_set(
                cmdset_name, command_sets
            )

        self._command_sets = resolved

    def _resolve_command_set(
        self,
        cmdset_name: str,
        all_cmdsets: dict,
        visited: Optional[set] = None
    ) -> Dict[str, Command]:
        """명령어 세트 상속 해결"""
        if visited is None:
            visited = set()

        if cmdset_name in visited:
            # 순환 상속 감지
            return {}

        visited.add(cmdset_name)

        if cmdset_name not in all_cmdsets:
            return {}

        cmdset_data = all_cmdsets[cmdset_name]
        result = {}

        # 부모 명령어 세트 먼저 가져오기
        if 'inherits_from' in cmdset_data:
            parent_name = cmdset_data['inherits_from']
            parent_commands = self._resolve_command_set(
                parent_name, all_cmdsets, visited
            )
            result.update(parent_commands)

        # 현재 명령어 세트로 오버라이드
        for cmd_code, cmd_data in cmdset_data.get('commands', {}).items():
            result[cmd_code] = Command.from_dict(cmd_code, cmd_data)

        return result

    def _parse_device_models(self, device_models: dict):
        """장치 모델 파싱"""
        self._models.clear()

        for model_id, model_data in device_models.items():
            # 상속된 명령어 세트 가져오기
            commands = {}

            if 'inherits_from' in model_data:
                cmdset_name = model_data['inherits_from']
                if cmdset_name in self._command_sets:
                    commands = self._command_sets[cmdset_name].copy()

            # 장치별 특수 명령어로 오버라이드
            for cmd_code, cmd_data in model_data.get('specific_commands', {}).items():
                commands[cmd_code] = Command.from_dict(cmd_code, cmd_data)

            # DeviceModel 생성
            self._models[model_id] = DeviceModel.from_dict(
                model_id, model_data, commands
            )

    def get_model(self, model_id: str) -> Optional[DeviceModel]:
        """모델 ID로 장치 모델 가져오기"""
        return self._models.get(model_id)

    def list_models(self) -> List[str]:
        """모든 장치 모델 ID 목록"""
        return list(self._models.keys())

    def list_models_by_category(self, category: str) -> List[str]:
        """카테고리별 장치 모델 목록"""
        return [
            model_id
            for model_id, model in self._models.items()
            if model.category == category
        ]

    def get_command_set(self, cmdset_name: str) -> Optional[Dict[str, Command]]:
        """명령어 세트 가져오기"""
        return self._command_sets.get(cmdset_name)

    def list_command_sets(self) -> List[str]:
        """모든 명령어 세트 이름 목록"""
        return list(self._command_sets.keys())


# 전역 레지스트리 인스턴스 (싱글톤)
_global_registry: Optional[DeviceRegistry] = None


def get_global_registry() -> DeviceRegistry:
    """전역 레지스트리 가져오기"""
    global _global_registry
    if _global_registry is None:
        # 기본 설정 파일 경로
        default_config = Path(__file__).parent.parent / 'config' / 'devices' / 'devices_sample.json'
        if default_config.exists():
            _global_registry = DeviceRegistry(str(default_config))
        else:
            _global_registry = DeviceRegistry()
    return _global_registry


def set_global_registry(registry: DeviceRegistry):
    """전역 레지스트리 설정"""
    global _global_registry
    _global_registry = registry
