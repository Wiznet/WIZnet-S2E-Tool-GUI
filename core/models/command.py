"""Command model definition."""

import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Command:
    """단일 명령어 정의"""

    code: str
    name: str
    pattern: str
    access: str  # "RO", "RW", "WO"
    options: Dict[str, str]
    default: Optional[str] = None
    ui_widget: Optional[str] = None
    ui_group: Optional[str] = None
    ui_order: Optional[int] = None
    description: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None

    def validate(self, value: str) -> bool:
        """값 유효성 검증"""
        if not self.pattern:
            return True

        try:
            return bool(re.match(self.pattern, value))
        except re.error:
            return False

    def get_option_label(self, value: str) -> str:
        """옵션 값의 레이블 반환"""
        return self.options.get(value, value)

    def is_readable(self) -> bool:
        """읽기 가능 여부"""
        return self.access in ['RO', 'RW']

    def is_writable(self) -> bool:
        """쓰기 가능 여부"""
        return self.access in ['RW', 'WO']

    @classmethod
    def from_dict(cls, code: str, data: dict) -> 'Command':
        """딕셔너리에서 Command 객체 생성"""
        return cls(
            code=code,
            name=data.get('name', ''),
            pattern=data.get('pattern', ''),
            access=data.get('access', 'RO'),
            options=data.get('options', {}),
            default=data.get('default'),
            ui_widget=data.get('ui_widget'),
            ui_group=data.get('ui_group'),
            ui_order=data.get('ui_order'),
            description=data.get('description'),
            min_length=data.get('min_length'),
            max_length=data.get('max_length'),
        )

    def to_dict(self) -> dict:
        """Command 객체를 딕셔너리로 변환"""
        result = {
            'name': self.name,
            'pattern': self.pattern,
            'access': self.access,
            'options': self.options,
        }

        if self.default is not None:
            result['default'] = self.default
        if self.ui_widget:
            result['ui_widget'] = self.ui_widget
        if self.ui_group:
            result['ui_group'] = self.ui_group
        if self.ui_order is not None:
            result['ui_order'] = self.ui_order
        if self.description:
            result['description'] = self.description
        if self.min_length is not None:
            result['min_length'] = self.min_length
        if self.max_length is not None:
            result['max_length'] = self.max_length

        return result
