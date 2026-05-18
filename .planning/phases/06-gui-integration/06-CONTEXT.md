# Phase 6: GUI Integration - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning (pending Phase 4, 5 completion)

<domain>

## Phase Boundary

WIZ550 장치 검색·설정 UI를 main_gui.py에 통합한다.
WIZ550Searcher/Getter/Setter/Resetter (Phase 4)와 DeviceSpec YAML (Phase 5)를 연결하여
기존 WIZ5xxSR / WIZ1x0SR 흐름과 나란히 동작하도록 한다.

WIZ550 전용 설정 패널은 **Python 코드로 동적 생성** — .ui 파일 수정 없음.

</domain>

<decisions>

## Implementation Decisions

### UI 생성 방식

- **D-01**: WIZ550 설정 패널을 `.ui` 파일이 아닌 **Python 코드로 동적 생성**
  - 근거: SR / S2E / WEB 3개 장치가 서로 다른 필드 집합을 가짐.
    장치 선택 시 DeviceSpec YAML을 읽어 해당 위젯을 즉시 빌드하는 방식이 자연스럽다.
    기존 `gui/wizconfig_gui.ui`(10,625줄)에 3개 장치 분기를 추가하면 유지보수 부담이 급증.

### 레이아웃 원칙 — Auto Layout (Qt 매핑)

- **D-02**: **QVBoxLayout + QHBoxLayout 계층** 우선 사용 — QGridLayout 최소화
  - Figma Auto Layout ≈ CSS Flexbox ≈ QVBoxLayout/QHBoxLayout
  - QGridLayout은 명확한 표 구조(열 정렬이 필수인 경우)에만 허용
  - 방향: 섹션 간 = QVBoxLayout, 필드 행 = QHBoxLayout

- **D-03**: **DESIGN.md 간격 토큰** → Qt setSpacing / setContentsMargins 에 매핑

  | 토큰 | 값 | Qt 사용처 |
  |------|----|-----------|
  | spacing.xxs | 4px | setSpacing(4) — 라벨·값 밀착 그룹 |
  | spacing.xs | 8px | setSpacing(8) — 행 간격(필드 rows) |
  | spacing.sm | 12px | setSpacing(12) — 그룹 간격(QGroupBox 내) |
  | spacing.md | 16px | setContentsMargins(16,16,16,16) — 패널 외곽 여백 |
  | spacing.lg | 24px | 섹션 간 대여백 (필요 시) |

- **D-04**: **크기 정책** — Fill / Hug / Fixed Auto Layout 의미를 Qt에 적용
  - 레이블: `setSizePolicy(Fixed, Preferred)` — 고정 폭 (QLabel minimum width 설정)
  - 입력 필드: `setSizePolicy(Expanding, Preferred)` — 가용 폭 채움 (Fill)
  - 섹션 컨테이너: `setSizePolicy(Preferred, Preferred)` — 내용 감쌈 (Hug)
  - 패널 루트: `setSizePolicy(Expanding, Expanding)` — 탭 내 가득 채움

### 컬러 토큰 적용

- **D-05**: DESIGN.md 컬러 토큰 → Qt 스타일시트에 매핑

  | 토큰 | 값 | 사용처 |
  |------|----|--------|
  | colors.primary | #cc785c | Apply 버튼 배경 |
  | colors.success | #5db872 | 성공 메시지/상태 아이콘 |
  | colors.error | #c64545 | 오류 메시지/검증 실패 |
  | colors.canvas | #faf9f5 | 패널 배경 (필요 시) |
  | colors.text | #181715 | 기본 텍스트 |

  기존 버튼 스타일(#e08000 오렌지)은 **새로 추가하는 WIZ550 UI 요소에만** 교체 적용.
  기존 UI 전체 교체 금지 — 회귀 위험.

### 코드 구조

- **D-06**: 동적 UI 빌드 함수 패턴

  ```python
  def _build_wiz550_panel(self, device_type: str) -> QWidget:
      """
      device_type: 'WIZ550SR' | 'WIZ550S2E' | 'WIZ550WEB'
      DeviceSpec YAML 기반으로 해당 장치 설정 패널을 빌드하여 반환.
      """
      panel = QWidget()
      root = QVBoxLayout(panel)
      root.setSpacing(8)               # spacing.xs
      root.setContentsMargins(16, 16, 16, 16)  # spacing.md

      spec = device_spec_loader.load(device_type)
      for section_name, fields in spec.sections.items():
          grp = QGroupBox(section_name)
          grp_layout = QVBoxLayout(grp)
          grp_layout.setSpacing(8)     # spacing.xs

          for field in fields:
              row = QHBoxLayout()
              row.setSpacing(8)        # spacing.xs
              lbl = QLabel(field.label)
              lbl.setFixedWidth(120)   # 레이블 열 고정폭
              widget = self._make_field_widget(field)
              row.addWidget(lbl)
              row.addWidget(widget)
              grp_layout.addLayout(row)

          root.addWidget(grp)

      return panel

  def _apply_wiz550_panel(self, device_type: str):
      """현재 선택 장치에 맞는 패널로 교체."""
      if hasattr(self, '_wiz550_panel') and self._wiz550_panel:
          self._wiz550_panel.setParent(None)
      self._wiz550_panel = self._build_wiz550_panel(device_type)
      self.wiz550_tab_area.addWidget(self._wiz550_panel)
  ```

### main_gui.py 연결 포인트

- **D-07**: 기존 검색 흐름 확장 방식 — WIZ1x0SR과 동일 패턴 적용

  | 기존 (WIZ1x0SR) | WIZ550 추가 |
  |-----------------|------------|
  | `search_pre()` → WIZ1x0Searcher | `search_pre()` → WIZ550Searcher 병행 시작 |
  | `get_search_result()` 시그널 | `wiz550_search_done` 시그널 추가 |
  | `search_each_dev()` 에 WIZ1x0 처리 | WIZ550 장치 처리 분기 추가 |
  | 장치 선택 → `_apply_wiz1x0_compact_layout()` | 장치 선택 → `_apply_wiz550_panel(device_type)` |

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design System
- `~/.claude/DESIGN.md` — 간격 토큰(spacing.*), 컬러 토큰(colors.*), 타이포그래피, 컴포넌트 스타일 정의

### Auto Layout Qt 매핑
- D-02 ~ D-05 (이 파일 위) — 토큰·정책 매핑표 완비

### Phase 4 산출물 (구현 완료 후 참조)
- `WIZ550MSGHandler.py` — WIZ550Searcher/Getter/Setter/Resetter 클래스명 확인
- `WIZ550Profile.py` — parse_sr() / parse_s2e() / parse_web() 함수 시그니처 확인

### Phase 5 산출물 (구현 완료 후 참조)
- `specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml` — section/field 구조 확인

### Existing Pattern (참조 구현)
- `main_gui.py` — `_apply_wiz1x0_compact_layout()`, `_apply_wiz1x0_field_widths()`, `_connect_wiz1x0_signals()` — WIZ550 연결의 직접 참조 모델
- `WIZ1x0MSGHandler.py` — QThread + 시그널 연결 패턴

### Requirements
- `.planning/REQUIREMENTS.md` §UI — Phase 6 범위 REQ-ID: UI-01~04

</canonical_refs>

<deferred>

## Deferred Ideas

- 기존 WIZ5xxSR / WIZ1x0SR UI 전체에 DESIGN.md 토큰 소급 적용 — 별도 UI 정리 Phase에서
- QSS 전역 테마 파일 도입 — 현재는 개별 setStyleSheet() 로컬 적용만
- WIZ550WEB 웹 관리 페이지 임베드 — 범위 외

</deferred>

---

*Phase: 06-gui-integration*
*Context gathered: 2026-05-15*
