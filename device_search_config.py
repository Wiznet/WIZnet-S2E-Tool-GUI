"""장비 검색 타이밍 및 성능 설정 관리

이 모듈은 config/device_search_timing.yaml 파일을 로드하고
검증하며, 타입 안전한 접근자를 제공합니다.

Example:
    >>> config = DeviceSearchConfig()
    >>> timeout = config.get_phase1_broadcast_timeout()
    >>> print(timeout)  # 3.0

    >>> if config.is_auto_tune_enabled():
    ...     multiplier = config.get_auto_tune_rtt_multiplier()
"""

import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from decimal import Decimal


# YAML Decimal 지원: float를 Decimal로 로드/저장
class DecimalSafeLoader(yaml.SafeLoader):
    """Decimal을 지원하는 YAML Loader (float → Decimal)"""
    pass


class DecimalSafeDumper(yaml.SafeDumper):
    """Decimal을 지원하는 YAML Dumper (Decimal → float 표현)"""
    def ignore_aliases(self, data):
        """앵커/참조 비활성화 (가독성 향상)"""
        return True


def decimal_constructor(loader, node):
    """YAML float를 Decimal로 변환"""
    value = loader.construct_scalar(node)
    return Decimal(value)


def decimal_representer(dumper, data):
    """Decimal을 YAML float로 변환 (정확한 표현 유지)"""
    # Decimal을 문자열로 변환하되, 불필요한 소수점 제거
    str_value = str(data)
    # 정수면 .0 추가 (YAML float 타입 명시)
    if '.' not in str_value and 'E' not in str_value and 'e' not in str_value:
        str_value += '.0'
    return dumper.represent_scalar('tag:yaml.org,2002:float', str_value)


# YAML Loader/Dumper에 Decimal 지원 등록
DecimalSafeLoader.add_constructor(
    'tag:yaml.org,2002:float',
    decimal_constructor
)
DecimalSafeDumper.add_representer(
    Decimal,
    decimal_representer
)


class DeviceSearchConfig:
    """장비 검색 타이밍 및 성능 설정 관리 클래스

    파일 로딩 우선순위:
        1. 사용자 지정 파일 (인자로 전달)
        2. config/device_search_timing.yaml (사용자 설정)
        3. config/device_search_timing.default.yaml (기본값)
        4. 하드코딩 기본값 (DEFAULTS)

    Attributes:
        config (dict): 로드된 설정 값
    """

    # 하드코딩 기본값 (폴백)
    DEFAULTS = {
        'search': {
            'phase1': {
                'broadcast_timeout_sec': 3.0,
                'loop_select_timeout_sec': 0.5,
                'emit_stabilization_ms': 50,
            },
            'phase3': {
                'device_query_timeout_sec': 1.5,
                'set_command_delay_ms': 500,
            },
            'tcp': {
                'scan_timeout_sec': 2.0,
                'max_parallel_workers': 15,
            },
            'retry': {
                'delay_between_retries_ms': 100,
                'max_retry_count_limit': 100,
                'default_max_retry': 3,
            },
            'options': {
                'expected_device_count': 0,
                'max_retry_count': 3,
            },
        },
        'ui': {
            'progress_bar': {
                'auto_hide_delay_ms': 1000,
                'update_percent': 10,
            },
            'tooltips': {
                'show_delay_ms': 100,
            },
            'background_threads': {
                'progress_update_interval_ms': 15,
            },
        },
        'experimental': {
            'auto_tune': {
                'enabled': False,
                'rtt_multiplier': 2.0,
                'min_timeout_sec': 0.3,
                'max_timeout_sec': 1.0,
            },
            'skip_phase1_emit_delay': False,
            'reuse_phase1_socket': False,
            'max_parallel_sockets': 0,
            'phase3_on_demand': False,
        },
        'active_preset': 'normal',
        'logging': {
            'enable_timing_logs': True,
            'verbose_debug': False,
            'show_timing_in_statusbar': False,
        },
    }

    @staticmethod
    def get_defaults():
        """기본값 dict 반환 (다이얼로그 Reset 버튼용)"""
        return DeviceSearchConfig.DEFAULTS['search'].copy()

    def __init__(self, config_path: Optional[str] = None):
        """설정 파일 로드

        Args:
            config_path: 선택적 설정 파일 경로 (None이면 자동 탐색)
        """
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self._apply_active_preset()
        self.config_file_path = Path('config/device_search_timing.yaml')  # 사용자 설정 파일 경로

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """YAML 파일 로드 (우선순위 순서)

        Args:
            config_path: 사용자 지정 파일 경로

        Returns:
            dict: 병합된 설정 값
        """
        paths = []

        if config_path:
            paths.append(Path(config_path))

        # config 폴더에서 탐색
        paths.extend([
            Path('config/device_search_timing.yaml'),
            Path('config/device_search_timing.default.yaml'),
        ])

        for path in paths:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        loaded = yaml.load(f, Loader=DecimalSafeLoader)
                        merged = self._merge_config(self.DEFAULTS, loaded or {})
                        print(f"[Config] Loaded: {path}")
                        return merged
                except Exception as e:
                    print(f"[Config] Warning: Failed to load {path}: {e}")

        print("[Config] Using hardcoded defaults (no config file found)")
        return self.DEFAULTS.copy()

    def _merge_config(self, defaults: Dict, user_config: Dict) -> Dict:
        """재귀적으로 기본값과 사용자 설정 병합

        Args:
            defaults: 기본값 딕셔너리
            user_config: 사용자 설정 딕셔너리

        Returns:
            dict: 병합된 설정
        """
        result = defaults.copy()
        for key, value in user_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_active_preset(self):
        """active_preset이 지정되어 있으면 해당 프리셋 값으로 덮어씀"""
        active = self.config.get('active_preset')
        if active and active in self.config.get('presets', {}):
            preset = self.config['presets'][active]
            # preset의 search 값으로 덮어씀
            if 'search' in preset:
                self.config['search'] = self._merge_config(
                    self.config['search'],
                    preset['search']
                )
            print(f"[Config] Applied preset: {active} ({preset.get('name', active)})")

    # ============================================================
    # Phase 1 타임아웃 접근자
    # ============================================================
    def get_phase1_broadcast_timeout(self) -> float:
        """Phase 1 브로드캐스트 타임아웃 (초)

        Returns:
            float: 타임아웃 값 (초)
        """
        return float(self.config['search']['phase1']['broadcast_timeout_sec'])

    def get_phase1_loop_select_timeout(self) -> float:
        """Phase 1 루프 select 타임아웃 (초)

        Returns:
            float: 타임아웃 값 (초)
        """
        return float(self.config['search']['phase1']['loop_select_timeout_sec'])

    def get_phase1_emit_stabilization_ms(self) -> int:
        """Phase 1 emit 전 안정화 대기 (밀리초)

        Returns:
            int: 대기 시간 (밀리초)
        """
        return self.config['search']['phase1']['emit_stabilization_ms']

    # ============================================================
    # Phase 3 타임아웃 접근자
    # ============================================================
    def get_phase3_device_query_timeout(self) -> float:
        """Phase 3 개별 장비 쿼리 타임아웃 (초)

        Returns:
            float: 타임아웃 값 (초)
        """
        return float(self.config['search']['phase3']['device_query_timeout_sec'])

    def get_phase3_set_command_delay_ms(self) -> int:
        """Phase 3 SET 명령 후 대기 (밀리초)

        Returns:
            int: 대기 시간 (밀리초)
        """
        return self.config['search']['phase3']['set_command_delay_ms']

    # ============================================================
    # TCP 설정 접근자
    # ============================================================
    def get_tcp_scan_timeout(self) -> float:
        """TCP 포트 스캔 타임아웃 (초)

        Returns:
            float: 타임아웃 값 (초)
        """
        return float(self.config['search']['tcp']['scan_timeout_sec'])

    def get_tcp_max_parallel_workers(self) -> int:
        """TCP 스캔 최대 동시 연결 수

        Returns:
            int: 최대 worker 수
        """
        return self.config['search']['tcp']['max_parallel_workers']

    # ============================================================
    # UI 접근자
    # ============================================================
    def get_pgbar_update_percent(self) -> int:
        """Progress bar 갱신 퍼센트 (방어적 버전)

        Returns:
            int: 갱신 퍼센트 (1~100, 기본값: 10)

        Raises:
            없음 (항상 유효한 값 반환)
        """
        try:
            value = int(self.config['ui']['progress_bar']['update_percent'])
            # 범위 검증 및 제한
            if value < 1:
                self.logger.warning(f"pgbar_update_percent={value} < 1, using default 10")
                return 10
            if value > 100:
                self.logger.warning(f"pgbar_update_percent={value} > 100, clamped to 100")
                return 100
            return value
        except (KeyError, TypeError, ValueError) as e:
            self.logger.warning(f"Failed to load pgbar_update_percent: {e}, using default 10")
            return 10  # 기본값

    def get_pgbar_auto_hide_delay_ms(self) -> int:
        """Progress bar 자동 숨김 딜레이 (밀리초)

        Returns:
            int: 딜레이 시간 (밀리초)
        """
        return self.config['ui']['progress_bar']['auto_hide_delay_ms']

    # ============================================================
    # 실험적 기능 접근자
    # ============================================================
    def is_auto_tune_enabled(self) -> bool:
        """Auto-tune 활성화 여부

        Returns:
            bool: True면 RTT 기반 자동 조정, False면 고정값
        """
        return self.config['experimental']['auto_tune']['enabled']

    def get_auto_tune_rtt_multiplier(self) -> float:
        """Auto-tune RTT 배수

        Returns:
            float: RTT 배수 (기본 2.0)
        """
        return float(self.config['experimental']['auto_tune']['rtt_multiplier'])

    def get_auto_tune_min_timeout(self) -> float:
        """Auto-tune 최소 타임아웃 (초)

        Returns:
            float: 최소값 (초)
        """
        return float(self.config['experimental']['auto_tune']['min_timeout_sec'])

    def get_auto_tune_max_timeout(self) -> float:
        """Auto-tune 최대 타임아웃 (초)

        Returns:
            float: 최대값 (초)
        """
        return float(self.config['experimental']['auto_tune']['max_timeout_sec'])

    def is_skip_phase1_emit_delay(self) -> bool:
        """Phase 1 emit 전 msleep 건너뛰기 여부

        Returns:
            bool: True면 msleep 생략, False면 정상 동작
        """
        return self.config['experimental']['skip_phase1_emit_delay']

    def is_reuse_phase1_socket(self) -> bool:
        """Phase 1 소켓 재사용 여부

        Returns:
            bool: True면 재사용, False면 전용 소켓 생성
        """
        return self.config['experimental']['reuse_phase1_socket']

    # ============================================================
    # 범용 접근자
    # ============================================================
    def get(self, *keys, default=None) -> Any:
        """중첩된 키로 값 가져오기

        Args:
            *keys: 중첩된 키 경로
            default: 키가 없을 때 반환할 기본값

        Returns:
            Any: 설정 값 또는 기본값

        Example:
            >>> config.get('search', 'phase1', 'broadcast_timeout_sec')
            3.0
            >>> config.get('nonexistent', 'key', default=999)
            999
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    # ============================================================
    # 설정 관리 메서드 (저장, 업데이트, 기본값 복원)
    # ============================================================
    def get_current_values(self) -> Dict[str, Any]:
        """현재 설정 값 조회 (다이얼로그 초기화용)

        Returns:
            dict: {
                'phase1_loop_select_timeout': float,
                'phase1_emit_stabilization_ms': int,
                'skip_phase1_emit_delay': bool,
                'phase3_device_query_timeout': float,
                'tcp_max_parallel_workers': int,
                'pgbar_update_percent': int,
                'pgbar_auto_hide_delay_ms': int
            }
        """
        return {
            'phase1_broadcast_timeout': self.get_phase1_broadcast_timeout(),
            'phase1_loop_select_timeout': self.get_phase1_loop_select_timeout(),
            'phase1_emit_stabilization_ms': self.get_phase1_emit_stabilization_ms(),
            'skip_phase1_emit_delay': self.is_skip_phase1_emit_delay(),
            'phase3_device_query_timeout': self.get_phase3_device_query_timeout(),
            'tcp_max_parallel_workers': self.get_tcp_max_parallel_workers(),
            'pgbar_update_percent': self.get_pgbar_update_percent(),
            'pgbar_auto_hide_delay_ms': self.get_pgbar_auto_hide_delay_ms(),
            'expected_device_count': self.config.get('search', {}).get('options', {}).get('expected_device_count', 0),
            'max_retry_count': self.config.get('search', {}).get('options', {}).get('max_retry_count', 3),
            'show_timing_in_statusbar': self.config.get('logging', {}).get('show_timing_in_statusbar', False),
            'phase3_on_demand': self.config.get('experimental', {}).get('phase3_on_demand', False),
            'delay_between_retries_ms': int(self.config.get('search', {}).get('retry', {}).get('delay_between_retries_ms', 100)),
        }

    def save_config(self) -> bool:
        """현재 설정을 YAML 파일에 저장

        Returns:
            bool: 성공 여부
        """
        try:
            # config 디렉토리 확인/생성
            config_dir = Path('config')
            if not config_dir.exists():
                config_dir.mkdir(parents=True)

            # YAML 파일 쓰기 (Decimal 지원)
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f,
                         Dumper=DecimalSafeDumper,
                         default_flow_style=False,
                         allow_unicode=True,
                         sort_keys=False)

            self.logger.info(f"Config saved to {self.config_file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

    def update_config_values(self, updates: Dict[str, Any]) -> bool:
        """설정 값 업데이트 및 저장

        Args:
            updates: 업데이트할 설정 dict

        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 입력 검증 및 config dict 업데이트
            if 'phase1_broadcast_timeout' in updates:
                value = float(updates['phase1_broadcast_timeout'])
                if not (0.5 <= value <= 10.0):
                    raise ValueError(f"phase1_broadcast_timeout must be 0.5~10.0, got {value}")
                self.config['search']['phase1']['broadcast_timeout_sec'] = value

            if 'phase1_loop_select_timeout' in updates:
                value = float(updates['phase1_loop_select_timeout'])
                if not (0.1 <= value <= 5.0):
                    raise ValueError(f"phase1_loop_select_timeout must be 0.1~5.0, got {value}")
                self.config['search']['phase1']['loop_select_timeout_sec'] = value

            if 'phase1_emit_stabilization_ms' in updates:
                value = int(updates['phase1_emit_stabilization_ms'])
                if not (0 <= value <= 500):
                    raise ValueError(f"phase1_emit_stabilization_ms must be 0~500, got {value}")
                self.config['search']['phase1']['emit_stabilization_ms'] = value

            if 'skip_phase1_emit_delay' in updates:
                self.config['experimental']['skip_phase1_emit_delay'] = bool(updates['skip_phase1_emit_delay'])

            if 'phase3_device_query_timeout' in updates:
                value = float(updates['phase3_device_query_timeout'])
                if not (0.5 <= value <= 5.0):
                    raise ValueError(f"phase3_device_query_timeout must be 0.5~5.0, got {value}")
                self.config['search']['phase3']['device_query_timeout_sec'] = value

            if 'tcp_max_parallel_workers' in updates:
                value = int(updates['tcp_max_parallel_workers'])
                if not (1 <= value <= 50):
                    raise ValueError(f"tcp_max_parallel_workers must be 1~50, got {value}")
                self.config['search']['tcp']['max_parallel_workers'] = value

            if 'pgbar_update_percent' in updates:
                value = int(updates['pgbar_update_percent'])
                if not (1 <= value <= 100):
                    raise ValueError(f"pgbar_update_percent must be 1~100, got {value}")
                self.config['ui']['progress_bar']['update_percent'] = value

            if 'pgbar_auto_hide_delay_ms' in updates:
                value = int(updates['pgbar_auto_hide_delay_ms'])
                if not (0 <= value <= 10000):
                    raise ValueError(f"pgbar_auto_hide_delay_ms must be 0~10000, got {value}")
                self.config['ui']['progress_bar']['auto_hide_delay_ms'] = value

            # Search options validation
            if 'expected_device_count' in updates:
                value = int(updates['expected_device_count'])
                if not (0 <= value <= 1000):
                    raise ValueError(f"expected_device_count must be 0~1000, got {value}")
                self.config.setdefault('search', {}).setdefault('options', {})['expected_device_count'] = value

            if 'max_retry_count' in updates:
                value = int(updates['max_retry_count'])
                if not (1 <= value <= 100):
                    raise ValueError(f"max_retry_count must be 1~100, got {value}")
                self.config.setdefault('search', {}).setdefault('options', {})['max_retry_count'] = value

            if 'delay_between_retries_ms' in updates:
                value = int(updates['delay_between_retries_ms'])
                if not (0 <= value <= 5000):
                    raise ValueError(f"delay_between_retries_ms must be 0~5000, got {value}")
                self.config.setdefault('search', {}).setdefault('retry', {})['delay_between_retries_ms'] = value

            if 'show_timing_in_statusbar' in updates:
                self.config.setdefault('logging', {})['show_timing_in_statusbar'] = bool(updates['show_timing_in_statusbar'])

            if 'phase3_on_demand' in updates:
                self.config.setdefault('experimental', {})['phase3_on_demand'] = bool(updates['phase3_on_demand'])

            # 2. YAML 파일에 저장
            return self.save_config()

        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"Failed to update config: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """설정을 기본값으로 복원

        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 기본값 YAML 파일 읽기
            default_path = Path('config/device_search_timing.default.yaml')

            if default_path.exists():
                with open(default_path, 'r', encoding='utf-8') as f:
                    loaded = yaml.load(f, Loader=DecimalSafeLoader)
                    self.config = self._merge_config(self.DEFAULTS, loaded or {})
            else:
                # 폴백: 하드코딩 기본값 사용
                self.logger.warning("Default YAML not found, using hardcoded defaults")
                self.config = self.DEFAULTS.copy()

            # 2. 프리셋 적용
            self._apply_active_preset()

            # 3. 사용자 설정 파일에 저장
            return self.save_config()

        except Exception as e:
            self.logger.error(f"Failed to reset to defaults: {e}")
            return False


# 테스트 코드 (모듈 직접 실행 시)
if __name__ == '__main__':
    print("=== DeviceSearchConfig 테스트 ===\n")

    config = DeviceSearchConfig()

    print(f"Phase 1 브로드캐스트 타임아웃: {config.get_phase1_broadcast_timeout()}초")
    print(f"Phase 1 루프 select 타임아웃: {config.get_phase1_loop_select_timeout()}초")
    print(f"Phase 3 장비 쿼리 타임아웃: {config.get_phase3_device_query_timeout()}초")
    print(f"pgbar 갱신 퍼센트: {config.get_pgbar_update_percent()}%")
    print(f"Auto-tune 활성화: {config.is_auto_tune_enabled()}")
    print(f"skip_emit_delay: {config.is_skip_phase1_emit_delay()}")
    print(f"소켓 재사용: {config.is_reuse_phase1_socket()}")

    print("\n=== 범용 접근자 테스트 ===")
    print(f"TCP scan timeout: {config.get('search', 'tcp', 'scan_timeout_sec')}초")
    print(f"존재하지 않는 키: {config.get('nonexistent', default='기본값')}")

    print("\n테스트 완료!")
