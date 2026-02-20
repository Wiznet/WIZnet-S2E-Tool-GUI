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
from pathlib import Path
from typing import Any, Dict, Optional


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
                'default_max_retry': 1,
            },
        },
        'ui': {
            'progress_bar': {
                'auto_hide_delay_ms': 2000,
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
        },
        'active_preset': 'normal',
        'logging': {
            'enable_timing_logs': True,
            'verbose_debug': False,
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        """설정 파일 로드

        Args:
            config_path: 선택적 설정 파일 경로 (None이면 자동 탐색)
        """
        self.config = self._load_config(config_path)
        self._apply_active_preset()

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
                        loaded = yaml.safe_load(f)
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
        return self.config['search']['phase1']['broadcast_timeout_sec']

    def get_phase1_loop_select_timeout(self) -> float:
        """Phase 1 루프 select 타임아웃 (초)

        Returns:
            float: 타임아웃 값 (초)
        """
        return self.config['search']['phase1']['loop_select_timeout_sec']

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
        return self.config['search']['phase3']['device_query_timeout_sec']

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
        return self.config['search']['tcp']['scan_timeout_sec']

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
        """Progress bar 갱신 퍼센트

        Returns:
            int: 갱신 퍼센트 (1~100)
        """
        return self.config['ui']['progress_bar']['update_percent']

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
        return self.config['experimental']['auto_tune']['rtt_multiplier']

    def get_auto_tune_min_timeout(self) -> float:
        """Auto-tune 최소 타임아웃 (초)

        Returns:
            float: 최소값 (초)
        """
        return self.config['experimental']['auto_tune']['min_timeout_sec']

    def get_auto_tune_max_timeout(self) -> float:
        """Auto-tune 최대 타임아웃 (초)

        Returns:
            float: 최대값 (초)
        """
        return self.config['experimental']['auto_tune']['max_timeout_sec']

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
