"""
terminal/terminal_settings.py
QSettings 기반 터미널 상태 저장/복원.
- 매크로 12개 슬롯 (이름 + 시퀀스)
- 도킹 상태, 창 위치/크기
- 연결 프로파일 (추후 확장)
"""

import json

from PyQt5.QtCore import QSettings


class TerminalSettings:
    ORG  = 'WIZnet'
    APP  = 'S2EToolGUI_Terminal'
    KEY_MACROS   = 'macros/data'
    KEY_GEOMETRY = 'window/geometry'
    KEY_FLOATING = 'window/floating'

    def __init__(self):
        self._s = QSettings(self.ORG, self.APP)

    # ── 매크로 ──────────────────────────────────────────────────

    def save_macros(self, data: list):
        """data: [{'name': str, 'rows': [(msg, delay), ...]}, ...]"""
        try:
            self._s.setValue(self.KEY_MACROS, json.dumps(data, ensure_ascii=False))
        except (OSError, TypeError):
            pass

    def load_macros(self) -> list:
        raw = self._s.value(self.KEY_MACROS, None)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    # ── 창 상태 ─────────────────────────────────────────────────

    def save_geometry(self, geometry_bytes, floating: bool):
        self._s.setValue(self.KEY_GEOMETRY, geometry_bytes)
        self._s.setValue(self.KEY_FLOATING, floating)

    def load_geometry(self):
        return (
            self._s.value(self.KEY_GEOMETRY, None),
            self._s.value(self.KEY_FLOATING, False, type=bool),
        )
