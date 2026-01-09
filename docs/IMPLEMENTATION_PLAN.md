# 구현 우선순위 및 계획

**브랜치**: `feature/refactoring-v2`
**작성일**: 2026-01-09

---

## 🎯 기능 분류

### Tier 1: 즉시 구현 가능 (안정적, 빠름)

**특징**:
- 기존 코드와 충돌 없음
- 독립적으로 작동 가능
- 테스트 및 검증 용이
- 사용자에게 즉시 가치 제공

#### 1.1 JSON 검증 도구 강화 (30분)

**현재 상태**: `scripts/validate_config.py` 있음

**개선 사항**:
```python
# 추가 검증 항목
- 중복 명령어 코드 체크
- 순환 상속 감지
- 사용되지 않는 command_set 경고
- 펌웨어 버전 형식 검증
- 명령어 패턴 실제 테스트 (샘플 값으로)
```

**구현**:
```python
# scripts/validate_config.py에 추가

def validate_command_uniqueness(config):
    """명령어 코드 중복 체크"""
    for cmdset in config['command_sets']:
        codes = [cmd['code'] for cmd in cmdset['commands']]
        duplicates = [c for c in codes if codes.count(c) > 1]
        if duplicates:
            return f"Duplicate command codes in {cmdset['name']}: {duplicates}"
    return None

def test_regex_patterns(config):
    """정규식 패턴을 샘플 값으로 테스트"""
    test_cases = {
        'ipaddr': ['192.168.1.1', '256.0.0.1', 'invalid'],
        'mac': ['00:08:DC:12:34:56', 'invalid'],
        'port': ['80', '65536', 'abc']
    }

    errors = []
    for cmdset in config['command_sets']:
        for cmd in cmdset['commands']:
            if cmd['pattern']:
                # 샘플 값으로 테스트
                pass
    return errors
```

**효과**:
- JSON 편집 시 즉시 오류 발견
- 배포 전 품질 보증

**시간**: 30분

---

#### 1.2 명령어 문서 자동 생성 (1시간)

**기능**: JSON에서 명령어 레퍼런스 문서 자동 생성

**구현**:
```python
# scripts/generate_command_docs.py (새로 작성)

def generate_markdown_docs(json_path, output_path):
    """
    devices_sample.json → COMMAND_REFERENCE.md
    """
    with open(json_path) as f:
        config = json.load(f)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 명령어 레퍼런스\n\n")

        for model in config['device_models']:
            f.write(f"## {model['display_name']}\n\n")

            # 명령어 목록
            commands = get_commands_for_model(model)

            f.write("| 코드 | 이름 | 타입 | 설명 |\n")
            f.write("|------|------|------|------|\n")

            for cmd in commands:
                access = "읽기전용" if cmd['access'] == 'RO' else "읽기/쓰기"
                f.write(f"| {cmd['code']} | {cmd['name']} | {access} | ... |\n")

            f.write("\n")
```

**실행**:
```bash
python scripts/generate_command_docs.py
# → COMMAND_REFERENCE.md 생성
```

**효과**:
- 사용자용 매뉴얼 자동 생성
- JSON 수정하면 문서도 자동 업데이트

**시간**: 1시간

---

#### 1.3 JSON 백업/복원 도구 (30분)

**기능**: JSON 파일 변경 이력 관리

**구현**:
```python
# scripts/manage_config.py (새로 작성)

import shutil
from datetime import datetime

def backup_config():
    """현재 JSON을 타임스탬프와 함께 백업"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = 'config/devices/devices_sample.json'
    dst = f'config/devices/backups/devices_{timestamp}.json'

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)
    print(f"Backed up to: {dst}")

def list_backups():
    """백업 목록 표시"""
    backups = sorted(glob.glob('config/devices/backups/*.json'))
    for i, backup in enumerate(backups, 1):
        print(f"{i}. {os.path.basename(backup)}")
    return backups

def restore_backup(backup_path):
    """백업에서 복원"""
    shutil.copy(backup_path, 'config/devices/devices_sample.json')
    print(f"Restored from: {backup_path}")
```

**사용**:
```bash
# 백업
python scripts/manage_config.py backup

# 목록
python scripts/manage_config.py list

# 복원
python scripts/manage_config.py restore 1
```

**효과**:
- 안전하게 JSON 편집 가능
- 실수 시 즉시 복원

**시간**: 30분

---

#### 1.4 명령어 템플릿 생성기 (1시간)

**기능**: 새 장치/명령어 추가 템플릿

**구현**:
```python
# scripts/create_template.py (새로 작성)

def create_device_template(model_id, display_name, base_model=None):
    """새 장치 템플릿 생성"""
    template = {
        "model_id": model_id,
        "display_name": display_name,
        "category": "1-port",
        "command_set": "common",
        "firmware_support": {
            "min_version": "1.0.0"
        }
    }

    if base_model:
        template["base_model"] = base_model

    return template

def create_command_template(code, name, access="RW"):
    """새 명령어 템플릿 생성"""
    template = {
        "code": code,
        "name": name,
        "pattern": "",
        "access": access,
        "options": {},
        "ui_widget": "text",
        "ui_group": "General",
        "ui_order": 100
    }

    return template
```

**사용**:
```bash
# 새 장치 템플릿
python scripts/create_template.py device "MY_DEVICE" "My Device"

# 새 명령어 템플릿
python scripts/create_template.py command "XX" "My Command"
```

**효과**:
- 오타 방지
- 일관된 구조 유지

**시간**: 1시간

---

### Tier 2: 단순 전환 (안전, 검증됨)

**특징**:
- 로직 변경 없이 호출만 교체
- 기존 기능과 동일한 동작
- Rollback 쉬움

#### 2.1 설정 검증 전환 (2시간) ★ 최우선

**현재 코드**: `main_gui.py` → `do_setting()`

**변경 전**:
```python
def do_setting(self):
    # Legacy 검증
    if not self.cmdset.isvalidparameter('LI', ip_value):
        self.msg_invalid('LI')
        return False
```

**변경 후**:
```python
def do_setting(self):
    if self.use_new_architecture:
        # 새 검증 로직
        config = self._collect_config_from_ui()  # UI에서 모든 값 수집

        device = DeviceInfo(
            mac_addr=self.curr_mac,
            model_id=self.curr_dev,
            firmware_version=self.curr_ver
        )

        errors = self.device_service.validate_config(device, config)

        if errors:
            error_msg = "\n".join([f"{code}: {msg}" for code, msg in errors.items()])
            QMessageBox.critical(self, "Validation Error", error_msg)
            return False

        # 검증 통과 후 기존 로직으로 전송
        for cmd_code, value in config.items():
            cmd = self.wizmakecmd.make_command(cmd_code, value)
            self.send_packet(cmd)
    else:
        # Legacy 검증 (fallback)
        if not self.cmdset.isvalidparameter('LI', ip_value):
            self.msg_invalid('LI')
            return False
```

**헬퍼 함수**:
```python
def _collect_config_from_ui(self):
    """UI에서 모든 설정 값 수집"""
    config = {}

    # Network settings
    config['LI'] = self.edit_localip.text()
    config['SM'] = self.edit_subnet.text()
    config['GW'] = self.edit_gateway.text()

    # Serial settings
    config['BR'] = self.combo_baudrate.currentData()
    config['DB'] = self.combo_databit.currentData()
    # ... 모든 필드

    return config
```

**테스트 방법**:
```python
# 1. 새 검증으로 테스트
self.use_new_architecture = True
# UI에서 잘못된 값 입력 → 에러 표시 확인

# 2. Legacy 검증으로 테스트
self.use_new_architecture = False
# 동일하게 동작하는지 확인
```

**효과**:
- JSON 패턴 수정이 실제로 반영됨
- 사용자가 체감 가능한 첫 변화
- 기존 기능 그대로 유지 (전송 로직은 동일)

**위험도**: 낮음 (검증만 교체, 전송은 그대로)

**시간**: 2시간

---

#### 2.2 에러 메시지 통합 (1시간)

**현재 코드**: 여러 곳에서 `QMessageBox` 직접 호출

**변경 후**:
```python
# 모든 에러 메시지를 통합
def show_validation_error(self, field_name, message):
    if self.use_new_architecture:
        self.qt_adapter.show_error(
            f"{field_name}: {message}",
            "Validation Error"
        )
    else:
        # Legacy
        QMessageBox.critical(self, "Error", message)
```

**효과**:
- 에러 메시지 스타일 일관성
- 나중에 다국어 지원 쉬워짐

**시간**: 1시간

---

### Tier 3: 신중한 설계 필요

**특징**:
- 아키텍처 변경 필요
- 여러 시나리오 고려 필요
- 프로토타입 먼저 만들어 검증

#### 3.1 패킷 에디터 GUI (설계 필요, 1일)

**문제**: 어떤 형태가 좋을까?

**Option A: 텍스트 에디터 (간단, 3시간)**
```python
class SimpleJSONEditor(QDialog):
    def __init__(self):
        self.editor = QTextEdit()
        self.editor.setPlainText(json_content)

        # Save 버튼
        # JSON 검증
        # 자동 포맷팅
```

**장점**: 구현 빠름, 유연함
**단점**: 초보자 어려움

**Option B: 폼 기반 에디터 (중간, 1일)**
```python
class FormJSONEditor(QDialog):
    def __init__(self):
        # 장치 목록 (QListWidget)
        # 선택한 장치의 속성 (QFormLayout)
        # 명령어 목록 (QTableWidget)
        # 추가/삭제/수정 버튼
```

**장점**: 사용자 친화적, 오타 방지
**단점**: 구현 시간 오래 걸림

**Option C: 트리 뷰 에디터 (고급, 2일)**
```python
class TreeJSONEditor(QDialog):
    def __init__(self):
        # QTreeView로 계층 구조 표시
        # 우클릭 메뉴 (추가/삭제/복사)
        # 프로퍼티 패널
        # Drag & Drop 지원
```

**장점**: 전문적, 강력
**단점**: 복잡, 시간 많이 소요

**권장**: **Option A (간단한 텍스트 에디터)부터 시작**
- 3시간이면 완성
- 나중에 Option B/C로 업그레이드 가능

---

#### 3.2 장치 검색 결과 표시 전환 (설계 필요, 2시간)

**문제**: 현재 테이블 구조가 복잡함

**현재 코드**:
```python
def get_search_result(self):
    # 검색 결과를 직접 QTableWidget에 채움
    self.list_device.setRowCount(len(devices))
    for row, device in enumerate(devices):
        self.list_device.setItem(row, 0, QTableWidgetItem(mac))
        self.list_device.setItem(row, 1, QTableWidgetItem(model))
        # ... 10개 이상의 컬럼
```

**새 방식 (Option 1: 직접 전환)**:
```python
def get_search_result(self):
    if self.use_new_architecture:
        devices = []
        for dev_info in search_results:
            devices.append(DeviceInfo(
                mac_addr=dev_info['mac'],
                model_id=dev_info['model'],
                firmware_version=dev_info['version'],
                ip_addr=dev_info['ip']
            ))

        self.qt_adapter.show_devices(devices)
    else:
        # Legacy
        # ... 기존 코드
```

**새 방식 (Option 2: 점진적 전환)**:
```python
def get_search_result(self):
    # 1단계: 데이터만 DeviceInfo로 변환
    devices = self._parse_search_results(search_results)

    # 2단계: 표시는 나중에 전환
    self._display_devices_legacy(devices)
```

**고려사항**:
- 기존 UI 레이아웃 유지 vs 새로 디자인
- 정렬, 필터링 기능 유지
- 선택 이벤트 처리

**권장**: **Option 2 (점진적)**
- 먼저 데이터 구조만 변경
- UI는 기존 그대로 유지
- 안정화 후 UI 개선

**시간**: 2시간

---

#### 3.3 OTA 기능 (설계 필요, 1일)

**고려사항**:

1. **펌웨어 소스**:
   - GitHub Releases? (공식)
   - 로컬 파일? (테스트용)
   - 다른 URL? (커스텀)

2. **다운로드 관리**:
   - 어디에 저장? (임시 폴더?)
   - 다운로드 진행 상황 표시
   - 중단/재개 지원?

3. **플래시 프로세스**:
   - 기존 `FWUploadThread` 활용
   - 에러 처리 (실패 시 롤백?)
   - 장치 재부팅 대기

4. **UI 배치**:
   - 새 메뉴? 새 탭? 다이얼로그?
   - 펌웨어 버전 비교 표시
   - 릴리스 노트 표시

**프로토타입**:
```python
# 먼저 CLI 버전으로 테스트
def download_firmware(device_model, version):
    url = get_firmware_url(device_model, version)
    response = requests.get(url, stream=True)
    # ... 다운로드 ...
    return firmware_path

def flash_firmware(device_mac, firmware_path):
    thread = FWUploadThread(device_mac, firmware_path)
    thread.start()
    # ... 대기 및 결과 확인 ...
```

**권장**: **먼저 CLI 프로토타입 → GUI는 나중에**

**시간**: 5시간 (CLI) + 3시간 (GUI) = 8시간

---

### Tier 4: 장기 계획

**특징**:
- 큰 아키텍처 변경
- 별도 브랜치에서 실험 필요
- 사용자 피드백 필수

#### 4.1 Web UI (별도 프로젝트, 1주+)

**기술 스택 고려**:
- FastAPI + Vue.js?
- Flask + React?
- Django + Vanilla JS?

**범위**:
- 장치 검색
- 설정 조회/변경
- OTA 업데이트
- 실시간 모니터링

**권장**: **먼저 REST API만 구현 → 나중에 프론트엔드**

---

#### 4.2 CLI 도구 (1일)

**기능**:
```bash
# 장치 검색
wizconfig search

# 설정 조회
wizconfig get 00:08:DC:12:34:56

# 설정 변경
wizconfig set 00:08:DC:12:34:56 --ip 192.168.1.100

# 펌웨어 업데이트
wizconfig update 00:08:DC:12:34:56 --firmware firmware.bin
```

**구현**:
```python
# cli.py (새로 작성)
import click
from core.services.device_service import DeviceService

@click.group()
def cli():
    pass

@cli.command()
def search():
    """장치 검색"""
    service = DeviceService(registry)
    devices = service.search_devices()
    for device in devices:
        click.echo(f"{device.mac_addr} - {device.model_id}")

@cli.command()
@click.argument('mac')
def get(mac):
    """설정 조회"""
    # ...
```

**효과**:
- 자동화 스크립트에서 사용 가능
- 배치 작업 가능

**시간**: 1일

---

## 📊 우선순위 요약

### 🟢 즉시 시작 (Tier 1 + Tier 2.1) - 4시간

| 작업 | 시간 | 효과 | 위험도 |
|------|------|------|--------|
| JSON 검증 강화 | 30분 | 품질 향상 | 없음 |
| 명령어 문서 생성 | 1시간 | 사용자 편의 | 없음 |
| JSON 백업/복원 | 30분 | 안전성 | 없음 |
| 명령어 템플릿 | 1시간 | 생산성 | 없음 |
| **설정 검증 전환** | 2시간 | ★ 체감 가능 | 낮음 |

**총 5시간 → 1일 작업**

**결과**:
- 사용자가 JSON 편집의 가치를 즉시 체감
- 안전하고 검증된 도구 제공
- 실제로 작동하는 개선 완성

---

### 🟡 다음 단계 (Tier 2.2 + 간단한 Tier 3) - 6시간

| 작업 | 시간 | 전제 조건 |
|------|------|----------|
| 에러 메시지 통합 | 1시간 | 설정 검증 전환 완료 |
| 간단한 JSON 에디터 | 3시간 | - |
| 장치 검색 전환 (데이터만) | 2시간 | - |

**총 6시간 → 1일 작업**

**결과**:
- GUI에서 JSON 편집 가능
- 데이터 계층 점진적 전환
- 사용자 편의성 대폭 향상

---

### 🟠 신중하게 (Tier 3 나머지) - 설계 후 진행

| 작업 | 설계 시간 | 구현 시간 | 총 |
|------|-----------|----------|-----|
| 고급 JSON 에디터 | 2시간 | 1일 | 1.5일 |
| OTA 기능 (CLI) | 1시간 | 5시간 | 6시간 |
| OTA 기능 (GUI) | 1시간 | 3시간 | 4시간 |
| 장치 검색 전환 (UI) | 1시간 | 2시간 | 3시간 |

**우선순위**:
1. OTA CLI (즉시 사용 가능)
2. 장치 검색 전환 (안정성 검증)
3. 고급 에디터 (사용자 피드백 반영)

---

### 🔴 장기 계획 (Tier 4)

| 작업 | 시간 | 비고 |
|------|------|------|
| CLI 도구 | 1일 | 자동화 필요 시 |
| Web UI | 1주+ | 별도 프로젝트 |
| 다국어 지원 | 2일 | 사용자 요청 시 |

---

## 🎯 추천 실행 계획

### Phase 1: 빠른 승리 (1주)

**Day 1-2** (Tier 1 + 2.1):
```
1. [30분] JSON 검증 강화
2. [1시간] 명령어 문서 생성
3. [30분] JSON 백업/복원
4. [1시간] 명령어 템플릿
5. [2시간] 설정 검증 전환 ★
---
커밋, 테스트, 사용자 확인
```

**Day 3** (Tier 2.2):
```
1. [1시간] 에러 메시지 통합
2. [3시간] 간단한 JSON 에디터
---
커밋, 테스트, 문서 작성
```

**Day 4-5** (피드백 및 안정화):
```
- 버그 수정
- 문서 보완
- 사용자 피드백 수렴
```

**마일스톤**: 사용자가 JSON 편집으로 장치를 추가하고, 검증이 작동하는 것을 확인

---

### Phase 2: 핵심 전환 (1주)

**Day 1-2** (OTA CLI):
```
1. GitHub API 연동
2. 펌웨어 다운로드
3. 플래시 기능
4. CLI 인터페이스
---
테스트 (실제 장치)
```

**Day 3** (장치 검색 전환):
```
1. 데이터 구조 변경
2. 표시 로직 유지
---
regression 테스트
```

**Day 4-5** (통합 및 검증):
```
- 전체 기능 테스트
- 성능 확인
- 문서 완성
```

**마일스톤**: 핵심 기능이 새 아키텍처로 작동

---

### Phase 3: 고급 기능 (선택)

**사용자 요청에 따라**:
- 고급 JSON 에디터
- OTA GUI
- Web UI
- CLI 도구

---

## 🚦 시작 신호

### 지금 바로 시작할 것

**1단계 (30분)**:
```bash
# JSON 검증 강화
# scripts/validate_config.py 편집
```

**2단계 (1시간)**:
```bash
# 명령어 문서 생성
# scripts/generate_command_docs.py 작성
```

**3단계 (2시간)**:
```bash
# 설정 검증 전환
# main_gui.py 수정
```

**4시간 후**: 사용자가 체감할 수 있는 변화 완성

---

### 결정 필요 사항

#### 질문 1: 패킷 에디터 형태
- [ ] A. 간단한 텍스트 에디터 (3시간)
- [ ] B. 폼 기반 에디터 (1일)
- [ ] C. 트리 뷰 에디터 (2일)
- [ ] D. 나중에 결정

**권장**: A부터 시작

---

#### 질문 2: OTA 우선순위
- [ ] A. 즉시 구현 (CLI → GUI)
- [ ] B. Phase 2에서 구현
- [ ] C. 사용자 요청 시 구현
- [ ] D. 불필요

**권장**: B (Phase 2)

---

#### 질문 3: Web UI
- [ ] A. Phase 3에서 프로토타입
- [ ] B. 별도 프로젝트로 분리
- [ ] C. 불필요
- [ ] D. 나중에 결정

**권장**: D (나중에)

---

## 📝 다음 액션

### 즉시 시작 가능

```bash
# 1. JSON 검증 강화
vim scripts/validate_config.py

# 2. 테스트
python scripts/validate_config.py

# 3. 커밋
git add scripts/validate_config.py
git commit -m "feat: JSON 검증 강화 - 중복 체크, 패턴 테스트 추가"

# 4. 다음 작업으로...
```

**시작하시겠습니까?**

---

**작성일**: 2026-01-09
**브랜치**: `feature/refactoring-v2`
**예상 Phase 1 완료**: 1주
**예상 Phase 2 완료**: 2주
