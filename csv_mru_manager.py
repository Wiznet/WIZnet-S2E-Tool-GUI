"""
CSV MRU (Most Recently Used) Manager
검색 결과 CSV 파일의 최근 사용 이력을 관리합니다.

NOTE: dataclass 사용 (Pydantic 전환 대비 설계)
      - Pydantic 전환 시: dataclass → BaseModel, __post_init__ → @validator
"""

import os
import json
import datetime
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional


@dataclass
class CSVMRUEntry:
    """CSV MRU 리스트 항목 (Pydantic 전환 대비 설계)

    Pydantic 전환 시 변경사항:
    - @dataclass → class CSVMRUEntry(BaseModel):
    - __post_init__ → @validator 데코레이터
    - to_dict() → .dict()
    - from_dict() → .parse_obj()

    Fields:
        path: CSV 파일 전체 경로
        saved_at: 마지막 저장 날짜 (ISO 8601)
        last_access: 마지막 접근 날짜 (ISO 8601)
        access_count: 사용 횟수 (>= 1)
        memo: 사용자 메모
    """
    path: str
    saved_at: str
    last_access: str
    access_count: int = 1
    memo: str = ""

    def __post_init__(self):
        """검증 로직 (Pydantic @validator와 유사 구조)"""
        self._validate_path()
        self._validate_access_count()
        self._validate_datetime_format()

    def _validate_path(self):
        """path 검증: 비어있지 않아야 함"""
        if not self.path or not self.path.strip():
            raise ValueError("path cannot be empty")

    def _validate_access_count(self):
        """access_count 검증: 1 이상이어야 함"""
        if self.access_count < 1:
            raise ValueError(f"access_count must be >= 1, got {self.access_count}")

    def _validate_datetime_format(self):
        """datetime ISO 포맷 검증"""
        try:
            datetime.datetime.fromisoformat(self.saved_at)
            datetime.datetime.fromisoformat(self.last_access)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid datetime format (must be ISO 8601): {e}")

    def to_dict(self) -> Dict:
        """dict 변환 (Pydantic .dict()와 호환)"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CSVMRUEntry':
        """dict에서 생성 (Pydantic .parse_obj()와 호환)"""
        return cls(**data)

    def update_access(self, increment_count: bool = True):
        """접근 시간 업데이트 및 카운트 증가"""
        self.last_access = datetime.datetime.now().isoformat()
        if increment_count:
            self.access_count += 1


class CSVMRUManager:
    """CSV 파일 MRU (Most Recently Used) 관리 클래스

    기능:
    - CSV 파일 저장/불러오기 이력 관리
    - 최대 10개 항목 유지
    - 저장 날짜, 접근 날짜, 사용 횟수, 메모 기록
    - 정렬 기능 (최근 접근 순, 사용 횟수 순 등)
    """

    DEFAULT_MAX_ENTRIES = 10
    DEFAULT_CONFIG_PATH = os.path.join("config", "ui_state.json")

    def __init__(self, config_path: Optional[str] = None, max_entries: int = DEFAULT_MAX_ENTRIES):
        """
        Args:
            config_path: UI state JSON 파일 경로 (기본: config/ui_state.json)
            max_entries: 최대 보관 항목 수 (기본: 10)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.max_entries = max_entries
        self.logger = logging.getLogger(__name__)

    def _load_state(self) -> Dict:
        """UI state 파일 읽기"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load UI state: {e}")
            return {}

    def _save_state(self, state: Dict):
        """UI state 파일 저장"""
        try:
            # config 디렉토리 생성 (없는 경우)
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save UI state: {e}")
            raise

    def get_mru_list(self) -> List[Dict]:
        """MRU 리스트 가져오기

        Returns:
            MRU 리스트 (최근 접근 순으로 정렬됨)
        """
        state = self._load_state()
        return state.get('csv', {}).get('mru_list', [])

    def get_most_recent_directory(self) -> str:
        """가장 최근 사용한 파일의 디렉토리 반환

        Returns:
            가장 최근 디렉토리 경로 (없으면 빈 문자열)
        """
        mru_list = self.get_mru_list()
        if mru_list:
            return os.path.dirname(mru_list[0]['path'])
        return ""

    def get_last_directory(self) -> str:
        """마지막 사용한 디렉토리 경로 가져오기 (config 파일에서)

        Returns:
            마지막 디렉토리 경로 (없으면 빈 문자열)
        """
        state = self._load_state()
        return state.get('csv', {}).get('last_directory', '')

    def set_last_directory(self, directory: str):
        """마지막 사용한 디렉토리 경로 저장 (config 파일에)

        Args:
            directory: 디렉토리 경로
        """
        if not directory:
            return

        state = self._load_state()
        if 'csv' not in state:
            state['csv'] = {}

        state['csv']['last_directory'] = directory
        self._save_state(state)
        self.logger.info(f"CSV last directory updated: {directory}")

    def add_saved_file(self, file_path: str, memo: str = ""):
        """CSV 파일 저장 시 MRU 업데이트 (초기화)

        Args:
            file_path: 저장한 CSV 파일 전체 경로
            memo: 사용자 메모 (선택)
        """
        self._update_mru(file_path, is_save=True, memo=memo)

    def add_loaded_file(self, file_path: str):
        """CSV 파일 불러오기 시 MRU 업데이트 (access_count 증가)

        Args:
            file_path: 불러온 CSV 파일 전체 경로
        """
        self._update_mru(file_path, is_save=False)

    def _update_mru(self, file_path: str, is_save: bool, memo: str = ""):
        """MRU 리스트 업데이트 (내부 메서드)

        Args:
            file_path: CSV 파일 전체 경로
            is_save: True이면 Save (초기화), False이면 Load (증가)
            memo: 사용자 메모 (Save 시에만 사용)
        """
        state = self._load_state()

        # CSV MRU 리스트 가져오기
        if 'csv' not in state:
            state['csv'] = {}
        if 'mru_list' not in state['csv']:
            state['csv']['mru_list'] = []

        mru_list = state['csv']['mru_list']
        now = datetime.datetime.now().isoformat()

        # 기존 항목 찾기
        existing_item = None
        for item in mru_list:
            if item['path'] == file_path:
                existing_item = item
                break

        # 기존 항목 제거 (중복 방지 - 덮어쓰기)
        mru_list = [item for item in mru_list if item['path'] != file_path]

        if is_save:
            # Save 시: 초기화 (새로운 파일로 간주)
            new_item = {
                'path': file_path,
                'saved_at': now,
                'last_access': now,
                'access_count': 1,
                'memo': memo  # 새 메모 사용 (덮어쓰기)
            }
        else:
            # Load 시: 기존 값 유지하고 access_count 증가
            if existing_item:
                new_item = {
                    'path': file_path,
                    'saved_at': existing_item.get('saved_at', now),
                    'last_access': now,
                    'access_count': existing_item.get('access_count', 0) + 1,
                    'memo': existing_item.get('memo', '')
                }
            else:
                # 최초 Load (외부에서 생성된 파일)
                new_item = {
                    'path': file_path,
                    'saved_at': now,
                    'last_access': now,
                    'access_count': 1,
                    'memo': ''
                }

        # 새 항목을 맨 앞에 추가 (최신)
        mru_list.insert(0, new_item)

        # 최대 개수만 유지
        mru_list = mru_list[:self.max_entries]

        # 업데이트된 리스트 저장
        state['csv']['mru_list'] = mru_list
        self._save_state(state)

        action = "saved" if is_save else "loaded"
        self.logger.info(
            f"CSV MRU updated ({action}): {file_path} "
            f"(count={new_item['access_count']}, total {len(mru_list)} entries)"
        )

    def update_memo(self, file_path: str, memo: str):
        """특정 파일의 메모 업데이트

        Args:
            file_path: CSV 파일 전체 경로
            memo: 새 메모
        """
        state = self._load_state()
        mru_list = state.get('csv', {}).get('mru_list', [])

        for item in mru_list:
            if item['path'] == file_path:
                item['memo'] = memo
                break

        state.setdefault('csv', {})['mru_list'] = mru_list
        self._save_state(state)
        self.logger.info(f"CSV MRU memo updated: {file_path}")

    def remove_entry(self, file_path: str):
        """MRU 리스트에서 항목 제거

        Args:
            file_path: 제거할 CSV 파일 전체 경로
        """
        state = self._load_state()
        mru_list = state.get('csv', {}).get('mru_list', [])

        mru_list = [item for item in mru_list if item['path'] != file_path]

        state.setdefault('csv', {})['mru_list'] = mru_list
        self._save_state(state)
        self.logger.info(f"CSV MRU entry removed: {file_path}")

    def get_sorted_list(self, sort_by: str = "last_access", reverse: bool = True) -> List[Dict]:
        """정렬된 MRU 리스트 반환

        Args:
            sort_by: 정렬 기준 ('last_access', 'saved_at', 'access_count', 'path')
            reverse: True이면 내림차순, False이면 오름차순

        Returns:
            정렬된 MRU 리스트
        """
        mru_list = self.get_mru_list()

        if sort_by not in ['last_access', 'saved_at', 'access_count', 'path']:
            self.logger.warning(f"Invalid sort_by value: {sort_by}, using 'last_access'")
            sort_by = 'last_access'

        return sorted(mru_list, key=lambda x: x.get(sort_by, ''), reverse=reverse)

    def clear_all(self):
        """모든 MRU 항목 삭제"""
        state = self._load_state()
        state.setdefault('csv', {})['mru_list'] = []
        self._save_state(state)
        self.logger.info("CSV MRU cleared")
