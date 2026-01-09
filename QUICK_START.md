# 빠른 시작 가이드

## 🚀 30초 만에 이해하기

### 무엇이 바뀌었나?

#### 이전 (v1.5.8.1까지)
```python
# 새 장치 추가하려면...
# wizcmdset.py 파일 열고
# 100줄 넘는 코드를 손으로 타이핑
# 오타 하나면 전체가 망가짐
```

#### 지금 (v2.0)
```json
// config/devices/devices_sample.json 파일 열고
{
  "model_id": "NEW_DEVICE",
  "display_name": "새 장치",
  "command_set": "common"  // 끝!
}
```

---

## 📁 핵심 파일 3개만 기억하기

### 1. 장치/명령어 정의
**파일**: `config/devices/devices_sample.json`
**용도**: 새 장치 추가, 명령어 수정, 옵션 변경
**예시**:
```json
{
  "device_models": [
    {
      "model_id": "WIZ750SR",        // 장치 ID
      "display_name": "WIZ750SR",    // 화면 표시 이름
      "command_set": "wiz75x_extended" // 어떤 명령어 사용할지
    }
  ]
}
```

### 2. 비즈니스 로직
**파일**: `core/services/device_service.py`
**용도**: 검증, 장치 관리 로직
**언제 수정**: 새로운 검증 규칙 추가할 때

### 3. UI 어댑터
**파일**: `adapters/qt_adapter.py`
**용도**: UI 표시 방법
**언제 수정**: 화면 표시 방식 변경할 때

---

## 💡 실전 예제

### 예제 1: 새 장치 추가 (5분)

1. **JSON 파일 열기**
```bash
# config/devices/devices_sample.json 편집
```

2. **장치 정보 추가**
```json
{
  "device_models": [
    // ... 기존 장치들 ...
    {
      "model_id": "MY_NEW_DEVICE",
      "display_name": "나의 새 장치",
      "category": "1-port",
      "command_set": "common"  // 기본 명령어 세트 사용
    }
  ]
}
```

3. **검증**
```bash
python scripts/validate_config.py
```

4. **실행**
```bash
python main_gui.py
```

5. **로그 확인**
```
[INFO] [New Architecture] Available models: ..., MY_NEW_DEVICE
```

**끝!**

---

### 예제 2: Baudrate 옵션 추가 (1분)

1. **JSON 파일에서 BR 명령어 찾기**
```json
{
  "code": "BR",
  "name": "Baudrate",
  "options": {
    "0": "300",
    "1": "600",
    // ... 기존 값들 ...
    "11": "230400"
  }
}
```

2. **새 옵션 추가**
```json
{
  "code": "BR",
  "options": {
    "0": "300",
    // ... 기존 값들 ...
    "11": "230400",
    "12": "921600"  // 새 옵션
  }
}
```

3. **재시작**
```bash
python main_gui.py
```

**끝!**

---

### 예제 3: IP 검증 패턴 수정 (30초)

1. **JSON에서 LI 명령어 찾기**
```json
{
  "code": "LI",
  "name": "Local IP",
  "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$"
}
```

2. **패턴 수정** (예: 192.168.x.x만 허용)
```json
{
  "code": "LI",
  "pattern": "^192\\.168\\.\\d{1,3}\\.\\d{1,3}$"
}
```

3. **재시작 → 끝!**

---

## 🔍 구조 한눈에 보기

```
명령어 정의 (JSON)
    ↓
Core (검증/관리)
    ↓
Service (비즈니스 로직)
    ↓
Adapter (UI 변환)
    ↓
Qt UI (화면 표시)
```

### 데이터 흐름 예시

```
1. JSON 로드
   config/devices/devices_sample.json
   → 4개 모델, 53개 명령어

2. 사용자가 IP 입력
   UI: "192.168.1.100"

3. 검증 (Service)
   device_service.validate_config()
   → JSON의 pattern으로 자동 검증

4. 결과 표시 (Adapter)
   qt_adapter.show_error() 또는
   qt_adapter.highlight_invalid_field()
```

---

## 📊 기존 vs 신규 비교표

| 작업 | 기존 코드 라인 | 신규 JSON 라인 | 시간 |
|------|----------------|----------------|------|
| 새 장치 추가 | 100+ | 10 | 5분 |
| 명령어 옵션 추가 | 20+ | 1 | 30초 |
| 검증 패턴 수정 | 30+ | 1 | 30초 |
| 펌웨어 버전별 명령어 | 50+ | 5 | 2분 |

---

## 🎓 더 알아보기

### 상세 가이드
- **실용 가이드**: [NEW_ARCHITECTURE_GUIDE.md](NEW_ARCHITECTURE_GUIDE.md)
  - 상세한 시나리오별 설명
  - 마이그레이션 가이드
  - FAQ

- **전체 요약**: [FINAL_SUMMARY.md](FINAL_SUMMARY.md)
  - 아키텍처 전체 구조
  - 구현된 기능 목록
  - 테스트 결과

- **실행 환경**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
  - uv 사용법
  - 의존성 설치
  - 문제 해결

---

## ⚡ 바로 시도해보기

### 1. 설정 파일 보기
```bash
# JSON 파일 열기
notepad config/devices/devices_sample.json
# 또는
code config/devices/devices_sample.json
```

### 2. 검증 테스트
```bash
python scripts/validate_config.py
```

### 3. 실행해서 로그 확인
```bash
python main_gui.py
# [New Architecture] 로그 확인
```

---

## 💬 핵심 요약

1. **새 장치 추가**: JSON 파일에 10줄 추가
2. **명령어 수정**: JSON에서 해당 부분 편집
3. **코드 수정**: 거의 필요 없음
4. **기존 기능**: 그대로 작동 (병행 실행)

**"코드를 덜 짜고, 설정으로 더 많이 한다"**

---

**다음 단계**: [NEW_ARCHITECTURE_GUIDE.md](NEW_ARCHITECTURE_GUIDE.md)에서 실제 사용 시나리오 확인
