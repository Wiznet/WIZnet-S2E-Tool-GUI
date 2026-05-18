# Phase 6: GUI Integration - Research

**Researched:** 2026-05-18
**Domain:** PyQt5 GUI 통합 — main_gui.py + WIZ550MSGHandler/Profile/YAML
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01**: WIZ550 설정 패널을 `.ui` 파일이 아닌 Python 코드로 동적 생성
- **D-02**: QVBoxLayout + QHBoxLayout 계층 우선, QGridLayout 최소화
- **D-03**: DESIGN.md 간격 토큰 → Qt setSpacing/setContentsMargins 매핑
  - spacing.xs (8px) = 행 간격 / spacing.md (16px) = 패널 외곽 여백
- **D-04**: 크기 정책 — 레이블 Fixed, 입력 필드 Expanding
- **D-05**: DESIGN.md 컬러 토큰 → 신규 WIZ550 UI 요소에만 적용
  - Apply 버튼 #cc785c / 성공 #5db872 / 오류 #c64545
- **D-06**: `_build_wiz550_panel(device_type)` 코드 패턴 (YAML sections → QGroupBox → rows)
- **D-07**: `search_pre()` → WIZ550Searcher 병행, `wiz550_search_done` 시그널, `search_each_dev()` 분기

### Claude's Discretion

- 없음 — 모두 Locked

### Deferred Ideas (OUT OF SCOPE)

- 기존 WIZ5xxSR / WIZ1x0SR UI 전체 DESIGN.md 토큰 소급 적용
- QSS 전역 테마 파일 도입
- WIZ550WEB 웹 관리 페이지 임베드
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | 검색 라우팅 — UDP 6550 포트 병렬 검색, 기존 장치 목록에 통합 표시 | WIZ550Searcher.search_done 시그널 + _merge_wiz1x0_results 패턴으로 구현 가능 |
| UI-02 | 장치 선택 → GET_INFO → Profile 파싱 → UI 채우기 (장치 타입별 탭) | WIZ550Getter.get_done 시그널 + _build_wiz550_panel(device_type) |
| UI-03 | Apply → UI 수집 → Profile 빌드 → SET_INFO, 비밀번호 다이얼로그 | WIZ550Setter.set_done(bool) 시그널 + 기존 password 다이얼로그 재사용 |
| UI-04 | Reset / Factory Reset — REMOTE_RESET(0xE0) / FACTORY_RESET(0xF0) | WIZ550Resetter.reset_done(bool) 시그널 |
</phase_requirements>

---

## Summary

Phase 6는 이미 완성된 Phase 4(WIZ550MSGHandler/Profile) + Phase 5(YAML 3종)를 main_gui.py에 연결하는 배선 작업이다. 신규 로직보다 기존 패턴을 정확히 복제하는 것이 핵심이며, WIZ1x0SR 통합 패턴이 직접 참조 모델로 확립되어 있다.

핵심 발견: `device_spec_loader.load_device()`는 WIZ550 YAML을 지원하지 않는다. WIZ550 YAML은 `command_groups` 대신 `ui.sections` 구조를 사용하며, 별도 스키마(`device.wiz550.schema.json`)로 검증된다. `_build_wiz550_panel()`은 `device_spec_loader` 대신 직접 YAML을 파싱하거나 전용 경량 로더를 사용해야 한다.

WIZ550WEB의 `serial_command` 키는 `parse_web()` 반환 dict에 존재하지 않는다. YAML에 `disabled: true`로 명시되어 있으므로, `_build_wiz550_panel()`의 위젯 빌드 단계에서 `field.get('disabled', False)` 체크로 `setEnabled(False)` + `setValue(default)` 처리해야 KeyError를 방지할 수 있다(WR-01 해소).

**Primary recommendation:** WIZ1x0SR 통합 패턴(_merge_wiz1x0_results / get_clicked_devinfo / fill_devinfo_1x0)을 WIZ550 버전으로 1:1 복제하고, YAML 섹션 순회는 간단한 `yaml.safe_load()` 직접 파싱으로 처리한다.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt5 | 프로젝트 기존 | 위젯 생성 (QWidget, QGroupBox, QHBoxLayout, QVBoxLayout) | 기존 스택 |
| yaml (pyyaml) | 프로젝트 기존 | WIZ550 YAML 직접 파싱 | device_spec_loader가 이미 사용 |
| WIZ550MSGHandler | Phase 4 산출물 | WIZ550Searcher/Getter/Setter/Resetter | 완료됨 |
| WIZ550Profile | Phase 4 산출물 | parse_sr/s2e/web, build_sr/s2e/web | 완료됨 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| QMessageBox | PyQt5 내장 | 비밀번호 입력 다이얼로그 | Apply / Reset 시 |
| QInputDialog | PyQt5 내장 | 단순 텍스트 입력 | pw_setting 입력 |
| QScrollArea | PyQt5 내장 | WIZ550WEB (섹션 4개 — 스크롤 필요 가능성) | uart0/uart1 섹션 수 고려 시 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yaml.safe_load() 직접 파싱 | device_spec_loader.load_device() | load_device()는 command_groups 기반 — WIZ550 ui.sections 미지원 |

---

## Architecture Patterns

### Recommended Project Structure

main_gui.py 내 추가 코드 배치:

```
main_gui.py
├── __init_ui_object__ 블록 끝 (line ~882)
│   └── WIZ550 searcher 초기화 (self.wiz550_searcher = None)
├── search_pre() 블록 (line ~2326)
│   └── WIZ550Searcher 시작 (WIZ1x0Searcher 패턴 동일)
├── _merge_wiz550_results(results: list)
│   └── WIZ1x0SR의 _merge_wiz1x0_results 패턴 복제
├── get_clicked_devinfo() (line ~3186)
│   └── _proto == 'wiz550' 분기 추가
├── _show_wiz550_panel(show: bool)
│   └── wiz550_tab 위젯 show/hide + generalTab/channel_tab 전환
├── _build_wiz550_panel(device_type: str) → QWidget
│   └── YAML sections → QGroupBox → 위젯 rows 동적 생성
├── _apply_wiz550_panel(device_type: str)
│   └── 기존 패널 제거 + 신규 패널 삽입
├── fill_devinfo_wiz550(d: dict, device_type: str)
│   └── dict → 동적 위젯 dict에 값 채우기
├── fill_setinfo_wiz550() → dict
│   └── 동적 위젯 dict에서 값 수집 → dict 반환
├── apply_wiz550()
│   └── 비밀번호 → WIZ550Setter 시작
└── _on_wiz550_set_done(success: bool)
    └── 성공/실패 메시지 표시
```

### Pattern 1: WIZ1x0SR 검색 병행 패턴 (직접 참조 모델)

[VERIFIED: main_gui.py line 2326-2336]

```python
# search_pre() 안 — WIZ1x0Searcher 시작 블록 직후에 WIZ550Searcher 추가
if getattr(self, 'chk_wiz550_search', None) and self.chk_wiz550_search.isChecked():
    if self.wiz550_searcher is None or not self.wiz550_searcher.isRunning():
        self.wiz550_searcher = WIZ550Searcher(
            iface_ip=self.selected_eth if self.selected_eth else "",
        )
        self.wiz550_searcher.search_done.connect(self._merge_wiz550_results)
        self.wiz550_searcher.start()
```

### Pattern 2: 검색 결과 병합 (_merge_wiz1x0_results 복제)

[VERIFIED: main_gui.py line 2342-2386]

```python
def _merge_wiz550_results(self, results: list):
    """WIZ550Searcher 완료 콜백 — 결과를 기존 device list에 병합."""
    existing_macs = self.mac_list_str()
    new_results = [d for d in results if d['mac'] not in existing_macs]
    _wiz550_bg = QtGui.QColor(0xE0, 0xFF, 0xE0)  # 연한 녹색 배경
    for device_dict in new_results:
        mac_str = device_dict['mac']
        self.mac_list.append(mac_str.encode())
        self.mn_list.append(device_dict['device_type'])
        self.vr_list.append(device_dict['fw_str'].encode())
        self.st_list.append(b'normal')
        self.mode_list.append(b'0')
        self.detected_list.append(True)
        self.dev_profile[mac_str] = device_dict  # _proto='wiz550' 포함
        row = self.list_device.rowCount()
        self.list_device.insertRow(row)
        for col, text in [(0, mac_str), (1, device_dict['device_type']), (2, "✓")]:
            item = QTableWidgetItem(text)
            item.setBackground(_wiz550_bg)
            self.list_device.setItem(row, col, item)
```

### Pattern 3: 장치 클릭 분기 (_proto == 'wiz550')

[VERIFIED: main_gui.py line 3186 — wiz1x0 분기 직후에 추가]

```python
# get_clicked_devinfo() 안 — wiz1x0 분기 직후
if self.dev_profile.get(macaddr, {}).get('_proto') == 'wiz550':
    self.curr_mac = macaddr
    d = self.dev_profile[macaddr]
    device_type = d.get('device_type', 'WIZ550SR')
    self._show_wiz550_panel(True)

    # GET_INFO로 설정 읽기 (Discovery 응답에는 설정 없음)
    getter = WIZ550Getter(
        target_mac=macaddr,
        device_type=device_type,
        iface_ip=self.selected_eth or "",
    )
    getter.get_done.connect(lambda cfg: self._on_wiz550_get_done(cfg, macaddr, device_type))
    getter.start()
    return
```

### Pattern 4: _build_wiz550_panel() — YAML sections 순회

[VERIFIED: WIZ550SR.yaml / WIZ550S2E.yaml / WIZ550WEB.yaml 구조 확인]

```python
def _build_wiz550_panel(self, device_type: str) -> QWidget:
    import yaml
    from pathlib import Path
    yaml_path = Path(__file__).parent / 'specs' / 'devices' / f'{device_type}.yaml'
    spec = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))

    panel = QWidget()
    root_layout = QVBoxLayout(panel)
    root_layout.setSpacing(8)               # spacing.xs
    root_layout.setContentsMargins(16, 16, 16, 16)  # spacing.md

    self._wiz550_field_widgets = {}  # field.id → QWidget 매핑

    # dev_profile에서 현재 device_type의 fw_version 추출 (S2E condition 판별용)
    d = self.dev_profile.get(self.curr_mac, {})
    fw_ver = d.get('fw_ver', b'\x00\x00\x00')
    has_mqtt = (len(fw_ver) >= 2 and fw_ver[1] % 2 == 1)   # 홀수 → MQTT
    has_modbus = (len(fw_ver) >= 2 and fw_ver[1] % 2 == 0 and fw_ver[1] != 0)  # 짝수 非0 → Modbus

    for section in spec.get('ui', {}).get('sections', []):
        # condition 체크 (WIZ550S2E mqtt/modbus 섹션)
        condition = section.get('condition')
        if condition == 'mqtt' and not has_mqtt:
            continue
        if condition == 'modbus' and not has_modbus:
            continue

        grp = QGroupBox(section['label'])
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(8)

        for field in section.get('fields', []):
            widget = self._make_wiz550_field_widget(field)
            self._wiz550_field_widgets[field['id']] = widget

            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(field['label'])
            lbl.setFixedWidth(140)  # 레이블 열 고정폭
            row.addWidget(lbl)
            row.addWidget(widget)
            grp_layout.addLayout(row)

        root_layout.addWidget(grp)

    root_layout.addStretch()
    return panel
```

### Pattern 5: _make_wiz550_field_widget() — field.type별 위젯 생성

[VERIFIED: WIZ550SR/S2E/WEB.yaml field.type 목록 확인 — ip/text/uint16/dropdown/checkbox/readonly]

```python
def _make_wiz550_field_widget(self, field: dict) -> QWidget:
    ftype = field.get('type', 'text')
    disabled = field.get('disabled', False)

    if ftype == 'readonly':
        w = QLabel(str(field.get('value', '')))
        w.setEnabled(False)
        return w
    elif ftype == 'checkbox':
        w = QCheckBox()
    elif ftype == 'dropdown':
        w = QComboBox()
        for k, v in field.get('choices', {}).items():
            w.addItem(str(v), userData=k)  # userData에 원본 키 보관
    elif ftype in ('ip', 'text'):
        w = QLineEdit()
        if ftype == 'ip':
            w.setPlaceholderText('0.0.0.0')
    elif ftype == 'uint16':
        w = QLineEdit()
        w.setPlaceholderText('0')
    else:
        w = QLineEdit()

    if disabled:
        w.setEnabled(False)

    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return w
```

### Pattern 6: fill_devinfo_wiz550() — dict → 위젯 채우기

[VERIFIED: WIZ550Profile._parse_base_162() 반환 dict 키 목록 확인]

```python
def fill_devinfo_wiz550(self, d: dict):
    """parse_sr/s2e/web 반환 dict → _wiz550_field_widgets에 채우기."""
    for field_id, widget in self._wiz550_field_widgets.items():
        if field_id not in d:
            continue  # WR-01: disabled 필드(serial_command 등) — KeyError 방지
        val = d[field_id]
        if isinstance(widget, QLabel):
            widget.setText(str(val))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(val))
        elif isinstance(widget, QComboBox):
            # choices 키가 bps int(baud_rate) 또는 str(0/1/2) — userData로 매칭
            for i in range(widget.count()):
                stored_key = widget.itemData(i)
                # int/str 타입 모두 str 변환 후 비교
                if str(stored_key) == str(val):
                    widget.setCurrentIndex(i)
                    break
        elif isinstance(widget, QLineEdit):
            widget.setText(str(val))
```

### Pattern 7: WIZ550Getter 시그널 — QThread 안전성

[VERIFIED: WIZ550MSGHandler.py WIZ550Getter.get_done = pyqtSignal(dict)]

```python
# get_done 시그널은 QThread에서 emit → PyQt5가 GUI 스레드로 자동 큐잉
# → 람다 슬롯에서 GUI 위젯 직접 접근 안전

getter.get_done.connect(
    lambda cfg, mac=macaddr, dtype=device_type:
        self._on_wiz550_get_done(cfg, mac, dtype)
)
```

### Pattern 8: Apply 흐름 — WIZ550Setter

[VERIFIED: WIZ550MSGHandler.py WIZ550Setter.__init__ 파라미터 확인]

```python
def apply_wiz550(self):
    d = self.fill_setinfo_wiz550()
    target_ip = d.get('local_ip', '')
    pw = d.get('pw_setting', '')

    from WIZ550Profile import build_sr, build_s2e, build_web
    device_type = self.dev_profile.get(self.curr_mac, {}).get('device_type', 'WIZ550SR')
    builders = {'WIZ550SR': build_sr, 'WIZ550S2E': build_s2e, 'WIZ550WEB': build_web}
    config_bytes = builders[device_type](d)

    setter = WIZ550Setter(
        target_ip=target_ip,
        target_mac=self.curr_mac,
        password=pw,
        config_data=config_bytes,
        iface_ip=self.selected_eth or "",
    )
    setter.set_done.connect(self._on_wiz550_set_done)
    setter.start()
```

### Anti-Patterns to Avoid

- **device_spec_loader.load_device() WIZ550에 사용**: WIZ550 YAML은 `command_groups` 없음 → `FileNotFoundError` 발생. 직접 `yaml.safe_load()` 사용.
- **search_each_dev()에 WIZ550 장치를 넣기**: WIZ550은 SEAR 커맨드 방식이 아닌 GET_INFO 바이너리. `_proto == 'wiz550'` 필터로 제외 필요.
- **_merge_wiz550_results에서 GUI 스레드 블로킹**: QThread 내부에서 GUI 직접 접근 금지 — 시그널/슬롯으로만.
- **disabled 필드 값 접근**: `field.get('disabled', False)` 체크 없이 `d[field_id]` 직접 접근 → WEB serial_command KeyError.
- **초기화 순서 위반**: `self._wiz550_panel`, `self._wiz550_field_widgets` 등 새 속성을 `init_ui_object()` 이전에 참조 금지.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WIZ550 UDP 통신 | 소켓 직접 관리 | WIZ550Searcher/Getter/Setter/Resetter | Phase 4 완성 |
| Config bytes 빌드 | struct.pack 직접 | build_sr/s2e/web | Phase 4 완성 |
| Config bytes 파싱 | struct.unpack 직접 | parse_sr/s2e/web | Phase 4 완성 |
| 비밀번호 다이얼로그 | 커스텀 다이얼로그 | QInputDialog.getText() | 기존 패턴 |
| 장치 목록 중복 제거 | mac 목록 수동 관리 | mac_list_str() 기존 메서드 | 이미 구현됨 |

**Key insight:** Phase 4, 5 산출물이 완성된 상태이므로, Phase 6은 "연결선 그리기"에 집중한다. 복잡한 로직을 새로 구현하는 것이 아니라 기존 WIZ1x0SR 통합 패턴을 WIZ550 버전으로 복제한다.

---

## Common Pitfalls

### Pitfall 1: device_spec_loader.load_device() WIZ550에 사용 불가

**What goes wrong:** `_load_device_impl()`이 YAML의 `command_groups` 키를 순회하는데 WIZ550 YAML에는 이 키가 없다. 또한 `device.schema.json`이 아닌 `device.wiz550.schema.json`으로 검증되므로 스키마 검증도 다름.

**Why it happens:** WIZ550은 바이너리 프로토콜 — 커맨드 기반 WIZ5xxSR 아키텍처와 별도 설계.

**How to avoid:** `_build_wiz550_panel()`에서 `yaml.safe_load()` 직접 사용. `from device_spec_loader import load_device` 호출 금지.

**Warning signs:** `KeyError: 'command_groups'` 또는 `FileNotFoundError: command/*.yaml not found`

### Pitfall 2: WIZ550WEB disabled 필드 KeyError (WR-01)

**What goes wrong:** `parse_web()` 반환 dict에 `serial_command`, `working_mode`, `remote_ip`, `remote_port`, `local_port` 키가 없다. `fill_devinfo_wiz550()`에서 `d[field_id]`로 직접 접근 시 KeyError 크래시.

**Why it happens:** WIZ550WEB 구조체(133B)에 해당 필드 자체가 없음 — WEB 전용 구조체.

**How to avoid:** `fill_devinfo_wiz550()`에서 `if field_id not in d: continue` 가드. `_make_wiz550_field_widget()`에서 `disabled=True` 위젯은 UI에 표시만 하고 값 채우기 스킵.

**Warning signs:** `KeyError: 'serial_command'` on WEB device select

### Pitfall 3: search_each_dev()에서 WIZ550 장치 처리

**What goes wrong:** `search_each_dev()`는 WIZ5xxSR 커맨드(`wizmakecmd.search()`)를 사용한다. WIZ550 장치를 이 파이프라인에 넣으면 잘못된 패킷이 전송됨.

**Why it happens:** `_merge_wiz550_results()`로 목록에 추가 시 `dev_info_list`에 WIZ550 MAC이 포함될 수 있음.

**How to avoid:** `search_each_dev()` 시작 부분에 `_proto != 'wiz1x0'` 필터가 이미 있음. 동일하게 `_proto != 'wiz550'` 필터 추가:

```python
dev_info_list = [
    d for d in dev_info_list
    if self.dev_profile.get(d[0], {}).get('_proto') not in ('wiz1x0', 'wiz550')
]
```

**Warning signs:** WIZ550 장치에 텍스트 커맨드 응답 없음, 타임아웃 로그 폭증

### Pitfall 4: _build_wiz550_panel() 재진입 시 메모리 누수

**What goes wrong:** 같은 장치를 재선택할 때마다 panel QWidget이 새로 생성되고 이전 것이 해제되지 않으면 메모리 누수 발생.

**Why it happens:** `setParent(None)` 없이 새 패널을 layout에 추가.

**How to avoid:** `_apply_wiz550_panel()` 내에서:

```python
if hasattr(self, '_wiz550_panel') and self._wiz550_panel:
    self._wiz550_panel.setParent(None)  # Qt 가비지 컬렉션
```

**Warning signs:** 장치 재선택 반복 시 메모리 사용량 지속 증가

### Pitfall 5: WIZ550S2E condition 섹션 — fw_ver 기반 판별

**What goes wrong:** fw_ver 정보가 Discovery 응답(12B)에는 있지만, GET_INFO 응답 이전에 패널을 빌드하면 fw_ver을 모름.

**Why it happens:** 패널 빌드 타이밍이 GET_INFO 응답 이전이면 condition 판별 불가.

**How to avoid:** 패널 빌드는 GET_INFO 응답 후(`_on_wiz550_get_done()`) 수행. Discovery 응답에서 얻은 `fw_version` 바이트를 `dev_profile[mac]['fw_ver']`에 저장해두고 참조:

```python
# _parse_discovery_reply()가 이미 'fw_version': fw_version bytes 반환
# _build_wiz550_panel()에서 d.get('fw_ver', b'\x00\x00\x00')으로 접근
```

### Pitfall 6: WIZ550 검색 시 chk_wiz550_search 체크박스 UI 요소 추가 필요

**What goes wrong:** WIZ1x0SR은 `self.chk_wiz1x0_search` 체크박스가 .ui 파일에 정의되어 있다. WIZ550 검색 UI 요소가 없으면 검색을 트리거할 방법이 없음.

**Why it happens:** D-01 결정(Python 코드 동적 생성)은 설정 패널에만 적용. 검색 UI(체크박스/버튼)도 .ui 파일 없이 추가하거나, 기존 Search 버튼 흐름에 항상 포함 처리.

**How to avoid:** 가장 단순한 방법 = WIZ550 검색을 기존 Search 버튼에 항상 포함 (체크박스 불필요). WIZ1x0SR처럼 별도 체크박스를 추가한다면 동적으로 toolbar에 추가해야 함. **플래너가 두 방법 중 선택 필요.**

---

## Code Examples

### WIZ550Searcher 시그널 인터페이스

[VERIFIED: WIZ550MSGHandler.py line 312]

```python
# WIZ550Searcher
search_done = pyqtSignal(list)  # list of device_dict
# device_dict 키: device_type, product_code, fw_version, fw_str, mac, mac_bytes, _proto

# WIZ550Getter
get_done = pyqtSignal(dict)  # parse_sr/s2e/web 반환값

# WIZ550Setter
set_done = pyqtSignal(bool)  # True=성공, False=실패

# WIZ550Resetter
reset_done = pyqtSignal(bool)  # True=성공, False=실패
```

### WIZ550 YAML sections 구조 (Phase 6 순회 기준)

[VERIFIED: WIZ550SR.yaml, WIZ550S2E.yaml, WIZ550WEB.yaml]

```
WIZ550SR.yaml → ui.sections: [network(10 fields), serial(5 fields), options(6 fields)]
WIZ550S2E.yaml → ui.sections: [network, serial, options, mqtt(condition:mqtt), modbus(condition:modbus)]
WIZ550WEB.yaml → ui.sections: [network(10 fields, 4 disabled), uart0(5 fields), uart1(5 fields), options(2 fields)]
```

### dev_profile dict 구조 (WIZ550 장치 선택 후)

[VERIFIED: WIZ550MSGHandler._parse_discovery_reply() + WIZ550Profile._parse_base_162()]

```python
# Discovery 직후 (GET_INFO 전)
dev_profile[mac] = {
    'device_type': 'WIZ550SR',   # 'WIZ550SR' | 'WIZ550S2E' | 'WIZ550WEB'
    'fw_version': b'\x01\x00\x00',  # fw_ver bytes (3B)
    'fw_str': '1.0.0',
    'mac': 'AA:BB:CC:DD:EE:FF',
    'mac_bytes': b'\xaa\xbb\xcc\xdd\xee\xff',
    '_proto': 'wiz550',
}

# GET_INFO 후 (parse_sr/s2e/web 결과 merge)
dev_profile[mac].update({
    'local_ip': '192.168.0.100',
    'gateway': '192.168.0.1',
    'baud_rate': 115200,
    ...  # _parse_base_162() 전체 필드
})
```

### _show_wiz550_panel 패턴 (wiz1x0 참조)

[VERIFIED: main_gui.py line 3295-3300]

```python
def _show_wiz550_panel(self, show: bool):
    """WIZ550 전용 패널 ↔ 기존 generalTab 전환. wiz1x0 패턴 동일."""
    if hasattr(self, 'wiz550_tab'):
        self.wiz550_tab.setVisible(show)
    self.generalTab.setVisible(not show)
    self.channel_tab.setVisible(not show)
    # wiz1x0과 공존 시: 둘 다 show=False이면 generalTab 표시
    if show and hasattr(self, 'wiz1x0_tab'):
        self.wiz1x0_tab.setVisible(False)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .ui 파일에 모든 위젯 정의 | Python 코드 동적 생성 (D-01) | Phase 6 설계 결정 | WIZ550 3종 변형 대응 가능 |
| device_spec_loader 재사용 | yaml.safe_load() 직접 파싱 | Phase 5/6 경계 확인 | 경량, 의존성 없음 |

---

## Device Spec Loader 호환성 분석

`device_spec_loader.load_device()`는 WIZ550 YAML을 **지원하지 않는다.**

[VERIFIED: device_spec_loader.py line 395-458 분석]

| 기능 | 기존 load_device() | WIZ550 YAML | 결론 |
|------|-------------------|-------------|------|
| command_groups 로드 | 필수 | 없음 | 미지원 |
| ui.tabs 파싱 | 있음 | 없음 (ui.sections 사용) | 미지원 |
| 스키마 검증 | device.schema.json | device.wiz550.schema.json | 별도 |
| cmdset 빌드 | 핵심 기능 | 불필요 | 불필요 |

**권장:** `_build_wiz550_panel()`에서 `yaml.safe_load(path.read_text())` 직접 호출. 캐싱이 필요하다면 모듈 레벨 `_wiz550_spec_cache = {}` dict 사용.

---

## WIZ550WEB disabled:true 필드 처리 전략

[VERIFIED: WIZ550WEB.yaml line 38-48 + WIZ550Profile.parse_web() 반환 dict 분석]

`parse_web()` 반환 dict에 **존재하지 않는** 필드:

| field.id | disabled | 처리 방법 |
|----------|----------|-----------|
| working_mode | true | 위젯 생성 후 setEnabled(False), 값 채우기 skip |
| remote_ip | true | 위젯 생성 후 setEnabled(False), 값 채우기 skip |
| remote_port | true | 위젯 생성 후 setEnabled(False), 값 채우기 skip |
| local_port | true | 위젯 생성 후 setEnabled(False), 값 채우기 skip |
| serial_command | true | 위젯 생성 후 setEnabled(False), 값 채우기 skip |
| pw_connect | 없음 (필드 자체가 YAML에 없음) | N/A |

`fill_devinfo_wiz550()`에서 `if field_id not in d: continue` 가드로 모두 처리 가능.

---

## WIZ550S2E condition 처리 전략

[VERIFIED: WIZ550S2E.yaml line 97-117 + WIZ550Profile.py S2E_BASE_SIZE, MQTT_SIZE, MODBUS_SIZE]

```python
# condition 판별 로직 (PROF-02 기준)
fw_ver = d.get('fw_ver', b'\x00\x00\x00')  # bytes 3B
if len(fw_ver) >= 2:
    fw_ver_minor = fw_ver[1]
    has_mqtt   = (fw_ver_minor % 2 == 1)          # 홀수 → MQTT 70B
    has_modbus = (fw_ver_minor % 2 == 0 and fw_ver_minor != 0)  # 짝수 非0 → Modbus 2B
else:
    has_mqtt = has_modbus = False
```

단, `fw_ver` 정보는 Discovery 응답(`fw_version` bytes)에서도 얻을 수 있으므로 GET_INFO 이전에도 condition 판별 가능.

---

## 신규 UI 컨테이너 배치 전략

D-01 결정 — `.ui` 파일 수정 없음. WIZ550 패널 컨테이너를 main_gui.py 런타임에 삽입하는 두 가지 옵션:

**옵션 A: wiz1x0_tab과 동일 방식 (QWidget, .ui에 이미 존재)**
- wiz1x0_tab이 `.ui` 파일에 정의된 QWidget임을 확인 [VERIFIED: main_gui.py line 879]
- WIZ550 전용 패널도 동일하게 `.ui`에 빈 QWidget(wiz550_tab)을 추가해야 함
- .ui 파일 수정 = D-01 위반 소지

**옵션 B: 런타임 QWidget 삽입**
- `centralWidget()` 또는 main layout에 동적으로 QWidget 삽입
- `.ui` 파일 수정 불필요
- show/hide 전환 시 layout reflow 가능성 — setVisible()로 제어

**권장: 옵션 B + 단순화** — `generalTab`과 `channel_tab`이 속한 layout에 wiz550 panel을 `addWidget()`으로 삽입하고 `setVisible(False)`로 초기 숨김. 장치 선택 시 show/hide 교체.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (기존 tests/ 디렉토리 확인됨) |
| Config file | pytest.ini 또는 pyproject.toml (확인 필요) |
| Quick run command | `uv run pytest tests/test_wiz550_gui.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | _merge_wiz550_results가 dev_profile에 _proto='wiz550' 장치 추가 | unit | `uv run pytest tests/test_wiz550_gui.py::test_merge_wiz550_results -x` | ❌ Wave 0 |
| UI-01 | search_each_dev가 wiz550 장치를 필터링 | unit | `uv run pytest tests/test_wiz550_gui.py::test_search_each_dev_filters_wiz550 -x` | ❌ Wave 0 |
| UI-02 | _build_wiz550_panel이 SR/S2E/WEB 각각 올바른 섹션 수 반환 | unit | `uv run pytest tests/test_wiz550_gui.py::test_build_panel_sections -x` | ❌ Wave 0 |
| UI-02 | disabled 필드가 setEnabled(False) 상태 | unit | `uv run pytest tests/test_wiz550_gui.py::test_disabled_field_widget -x` | ❌ Wave 0 |
| UI-03 | fill_setinfo_wiz550 → build_sr/s2e/web 왕복 | unit | `uv run pytest tests/test_wiz550_gui.py::test_setinfo_roundtrip -x` | ❌ Wave 0 |
| UI-04 | WIZ550Resetter가 올바른 op_code로 초기화 | unit (Phase 4 기존) | `uv run pytest tests/test_wiz550_handler.py -x` | ✅ |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_wiz550_gui.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_wiz550_gui.py` — UI-01~04 단위 테스트 (PyQt5 QApplication 픽스처 포함)
- [ ] `tests/conftest.py` 확장 — `qapp` 픽스처 추가 (pytest-qt 또는 수동 QApplication)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyQt5 | 동적 패널 위젯 생성 | ✓ | 기존 프로젝트 의존성 | — |
| pyyaml | YAML 직접 파싱 | ✓ | device_spec_loader가 이미 사용 | — |
| pytest | 테스트 실행 | ✓ | tests/ 디렉토리 존재 확인 | — |
| WIZ550MSGHandler | Phase 4 산출물 | ✓ | 완성됨 | — |
| WIZ550Profile | Phase 4 산출물 | ✓ | 완성됨 | — |
| WIZ550*.yaml | Phase 5 산출물 | ✓ | 3개 파일 존재 확인 | — |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | wiz550_tab 컨테이너를 런타임에 centralWidget layout에 addWidget()으로 삽입 가능 | Architecture Patterns | layout 구조가 예상과 다르면 UI 깨짐 — main_gui.py 초기화 코드의 실제 layout 계층 확인 필요 |
| A2 | WIZ550 검색을 기존 Search 버튼에 항상 포함(체크박스 불필요) | Pitfall 6 | 사용자가 체크박스 ON/OFF 원할 경우 .ui 수정 필요 — 플래너 결정 필요 |
| A3 | pytest-qt 없이 `QApplication(sys.argv)` 직접 생성으로 GUI 단위 테스트 가능 | Validation Architecture | pytest-qt가 없으면 위젯 픽스처 복잡 — `uv add pytest-qt` 필요 가능성 |

---

## Open Questions

1. **WIZ550 검색 UI 진입점**
   - What we know: WIZ1x0SR은 chk_wiz1x0_search 체크박스(.ui에 존재)로 제어. WIZ550는 .ui 수정 없이 동적 추가 예정.
   - What's unclear: 항상 포함(조용히 병행)인지, 체크박스로 제어할지.
   - Recommendation: 가장 단순한 방법 = Search 버튼 클릭 시 항상 WIZ550Searcher 병행 시작. D-07에서 "WIZ550Searcher 병행 시작"이라 명시됨 — 체크박스 필요 없을 가능성 높음.

2. **wiz550_tab 컨테이너 삽입 위치**
   - What we know: wiz1x0_tab은 .ui 파일에 정의된 QWidget. generalTab, channel_tab과 같은 계층.
   - What's unclear: main layout에서 정확한 삽입 위치와 방법 (플래너가 main_gui.py layout 계층 추가 조사 필요).
   - Recommendation: Wave 0 작업에서 wiz550_tab QWidget을 Python 코드로 생성하고 `central_widget.layout().addWidget()`으로 삽입, 초기 setVisible(False).

3. **pytest-qt 설치 여부**
   - What we know: tests/ 디렉토리에 conftest.py 존재, Phase 4 테스트는 QThread 없이 순수 단위 테스트.
   - What's unclear: GUI 위젯 테스트에 pytest-qt 필요 여부.
   - Recommendation: Wave 0 작업에서 `uv run pytest --co tests/test_wiz550_gui.py` 실행으로 확인 후 필요 시 설치.

---

## Sources

### Primary (HIGH confidence)

- `WIZ550MSGHandler.py` — WIZ550Searcher/Getter/Setter/Resetter 클래스명, 시그널 인터페이스, 파라미터 전체 확인
- `WIZ550Profile.py` — parse_sr/s2e/web 반환 dict 키 목록, build_sr/s2e/web 파라미터 확인
- `main_gui.py` line 2342-2386 — _merge_wiz1x0_results 패턴 (직접 복제 모델)
- `main_gui.py` line 3162-3300 — dev_clicked, get_clicked_devinfo, _show_wiz1x0_panel 패턴
- `specs/devices/WIZ550SR.yaml`, `WIZ550S2E.yaml`, `WIZ550WEB.yaml` — sections, fields 구조
- `device_spec_loader.py` — WIZ550 미지원 확인 (command_groups 의존성)
- `tests/conftest.py` — 기존 테스트 픽스처 구조 확인

### Secondary (MEDIUM confidence)

- WIZ550WEB disabled 필드 목록: YAML 주석 + parse_web() 반환 dict 대조로 도출
- condition 판별 로직: PROF-02 요구사항 + S2E YAML condition 필드에서 도출

---

## Metadata

**Confidence breakdown:**
- Signal interfaces: HIGH — WIZ550MSGHandler.py 직접 확인
- YAML section structure: HIGH — 3개 파일 모두 확인
- WIZ1x0SR 참조 패턴: HIGH — main_gui.py 함수 본문 확인
- device_spec_loader 호환성: HIGH — 코드 분석으로 미지원 확인
- disabled 필드 처리: HIGH — parse_web() dict 키 목록 대조 완료
- wiz550_tab 삽입 위치: LOW — main_gui.py layout 계층 전체 파악 필요

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (안정적 스택, 30일 유효)
