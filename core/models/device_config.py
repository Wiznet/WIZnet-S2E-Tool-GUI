"""Device configuration and info models."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DeviceInfo:
    """검색된 장치 정보"""

    mac_addr: str
    model_id: str
    firmware_version: str
    ip_addr: Optional[str] = None
    status: Optional[str] = None
    product_name: Optional[str] = None
    raw_data: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'mac_addr': self.mac_addr,
            'model_id': self.model_id,
            'firmware_version': self.firmware_version,
            'ip_addr': self.ip_addr,
            'status': self.status,
            'product_name': self.product_name,
            'raw_data': self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceInfo':
        """딕셔너리에서 생성"""
        return cls(
            mac_addr=data.get('mac_addr', ''),
            model_id=data.get('model_id', ''),
            firmware_version=data.get('firmware_version', ''),
            ip_addr=data.get('ip_addr'),
            status=data.get('status'),
            product_name=data.get('product_name'),
            raw_data=data.get('raw_data', {}),
        )


@dataclass
class DeviceConfig:
    """장치 설정"""

    model_id: str
    firmware_version: str
    parameters: Dict[str, str] = field(default_factory=dict)

    def set_parameter(self, code: str, value: str):
        """파라미터 설정"""
        self.parameters[code] = value

    def get_parameter(self, code: str, default: Optional[str] = None) -> Optional[str]:
        """파라미터 가져오기"""
        return self.parameters.get(code, default)

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'model_id': self.model_id,
            'firmware_version': self.firmware_version,
            'parameters': self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceConfig':
        """딕셔너리에서 생성"""
        return cls(
            model_id=data.get('model_id', ''),
            firmware_version=data.get('firmware_version', ''),
            parameters=data.get('parameters', {}),
        )

    @classmethod
    def from_device_info(cls, device_info: DeviceInfo) -> 'DeviceConfig':
        """DeviceInfo에서 생성"""
        return cls(
            model_id=device_info.model_id,
            firmware_version=device_info.firmware_version,
            parameters=device_info.raw_data.copy(),
        )
