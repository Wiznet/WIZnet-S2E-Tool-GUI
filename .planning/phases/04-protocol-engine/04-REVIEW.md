---
phase: 04-protocol-engine
reviewed: 2026-05-18T12:09:01Z
depth: quick
files_reviewed: 5
files_reviewed_list:
  - WIZ550MSGHandler.py
  - WIZ550Profile.py
  - tests/conftest.py
  - tests/test_wiz550_handler.py
  - tests/test_wiz550_profile.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-18T12:09:01Z
**Depth:** quick
**Files Reviewed:** 5
**Status:** issues_found

## Summary

WIZ550 프로토콜 핸들러(`WIZ550MSGHandler.py`)와 Config 구조체 변환 레이어(`WIZ550Profile.py`), 그리고 Phase 4 테스트 스위트를 검토했다. 전체적인 구조는 견고하며, XOR 암호화 로직·헤더 파싱·struct 포맷 정의 모두 설계 명세와 일치한다.

발견된 문제는 보안 취약점 1건(패스워드 길이 불일치), 예외 처리 누락 1건, 프로덕션 코드 내 assert 남용 1건이 주요 항목이다. 치명적 보안 이슈나 프로토콜 파싱 버그는 없다.

---

## Warnings

### WR-01: `password.strip()`으로 인한 pw_len/pw_enc 불일치

**File:** `WIZ550MSGHandler.py:145`, `WIZ550MSGHandler.py:160`

**Issue:**
`_build_set_info`와 `_build_reset` 두 함수에서 `pw_len` 계산에 `.strip()`을 사용하고 있다. 그러나 `pw_enc`에는 strip되지 않은 원본 password가 들어간다.

```python
# 현재 (버그)
pw_enc = password.encode('ascii', errors='replace')[:16].ljust(16, b'\x00')
pw_len = min(len(password.strip()), 16)   # 공백 제거 후 길이
```

예: `password = 'secret '` (뒤에 공백) → `pw_enc`에는 `b'secret '`이 담기지만 `pw_len=6`이 아닌 `pw_len=6`... 실제로는 `len('secret '.strip())=6` vs `len('secret ')=7` → `pw_len`은 6이지만 실제 암호화된 바이트는 7자. 서버가 `pw_len=6`으로 6자를 읽으면 마지막 공백이 잘린 암호를 비교하게 되어 인증 실패가 발생할 수 있다.

반대 방향도 문제: 공백 없는 암호는 정상이지만, 공백이 포함된 암호를 설정한 장치에 다시 접속할 때 pw_len 불일치로 연결 거부가 발생할 수 있다.

**Fix:**
```python
# _build_set_info (line 143~146) 및 _build_reset (line 158~161) 동일하게 수정
pw_bytes = password.encode('ascii', errors='replace')[:16]
pw_enc   = pw_bytes.ljust(16, b'\x00')
pw_len   = len(pw_bytes)   # strip() 제거 — 원본 길이 그대로
payload  = mac_b + bytes([pw_len]) + pw_enc + config_data
```

---

### WR-02: `_parse_get_info_reply`에서 `ImportError` 외 예외 미처리

**File:** `WIZ550MSGHandler.py:268-285`

**Issue:**
`try` 블록에서 `ImportError`만 잡고 있다. `WIZ550Profile`이 정상적으로 import된 이후 `parse_sr()` / `parse_s2e()` / `parse_web()` 내부에서 발생하는 예외(`struct.error`, `ValueError` 등)는 전파되어 호출자(`WIZ550Getter.run()`)의 `except Exception as e` 핸들러에 잡히고 `get_done.emit({})` 없이 QThread가 종료된다.

실제로 `WIZ550Getter.run()` (line 417)이 `except Exception as e`로 예외를 잡으므로 크래시는 없지만, `self.get_done.emit(result)` 호출 시 `result={}` 빈 dict가 emit되므로 UI에 무음 실패로 보인다. 기술적으로 허용 가능한 설계이나, 의도를 코드에 명시하지 않아 유지보수 위험이 있다.

```python
# 현재
try:
    from WIZ550Profile import parse_sr, parse_s2e, parse_web
    if device_type == 'WIZ550SR':
        return parse_sr(system_info)
    ...
except ImportError:
    ...
return {}
```

**Fix:**
예외 범위를 명확히 하거나, 의도를 주석으로 명시한다.
```python
try:
    from WIZ550Profile import parse_sr, parse_s2e, parse_web
    if device_type == 'WIZ550SR':
        return parse_sr(system_info)
    elif device_type == 'WIZ550S2E':
        return parse_s2e(system_info)
    elif device_type == 'WIZ550WEB':
        return parse_web(system_info)
    else:
        logger.warning(f"[WIZ550] 미지 device_type: {device_type}")
        return {}
except ImportError:
    logger.warning("[WIZ550] WIZ550Profile 미구현")
    return {'mac': src_mac, 'local_ip': '0.0.0.0', '_proto': 'wiz550', '_raw_config': system_info}
except Exception as e:
    logger.error(f"[WIZ550] GET_INFO 파싱 오류: {e}")
    return {}
```

---

### WR-03: 프로덕션 코드에서 `assert` 사용 — `python -O` 시 무력화

**File:** `WIZ550Profile.py:266`, `WIZ550Profile.py:348`, `WIZ550Profile.py:448`, `WIZ550Profile.py:460`

**Issue:**
`build_sr()`, `build_web()`, `build_s2e()` 함수에서 빌드 결과 크기 검증을 `assert`로 수행하고 있다. Python 최적화 모드(`python -O` 또는 PyInstaller 일부 빌드 설정)에서는 assert가 완전히 제거되어 잘못된 크기의 bytes가 반환되어도 탐지되지 않는다.

```python
# WIZ550Profile.py line 266
assert len(raw) == SR_SIZE   # python -O 에서 무효
```

모듈 최상단의 struct 포맷 크기 검증 assert(line 68, 102, 113, 118)는 모듈 import 시 실행되므로 더 심각하다 — import 자체가 실패할 수 있다.

**Fix:**
프로덕션 코드에서는 assert 대신 명시적 조건 검사를 사용한다.
```python
# 모듈 레벨 포맷 검증 (line 68)
if struct.calcsize(SR_FORMAT) != SR_SIZE:
    raise RuntimeError(f"SR struct 크기 오류: {struct.calcsize(SR_FORMAT)} != {SR_SIZE}")

# build 함수 내 크기 검증 (line 266)
if len(raw) != SR_SIZE:
    raise RuntimeError(f"build_sr 결과 크기 오류: {len(raw)} != {SR_SIZE}")
```

---

## Info

### IN-01: `valid=0xFF` 생성 제외 — 스펙 일치 여부 불명확

**File:** `WIZ550MSGHandler.py:55`

**Issue:**
`_make_valid_and_key()`에서 `random.randint(0, 0x7E)`를 사용하여 `valid` 최대값이 `0xFE`로 제한된다. `valid=0xFF`는 XOR key=`0x7F`로 유효한 값이지만 생성되지 않는다. Java 원본 스펙에서 `0xFF` 제외가 명시되어 있는지 확인이 필요하다.

**Fix:**
Java 원본 코드를 확인하여 의도적 제외라면 주석 추가, 아니라면 `random.randint(0, 0x7F)`로 수정:
```python
valid = 0x80 + random.randint(0, 0x7F)  # 0x80~0xFF (Java 원본 동일)
key = valid & 0x7F                       # 0x00~0x7F
```

---

### IN-02: `conftest.py`에 `data_bits=3` — 주석 레이블과 실제 장치 값 불명확

**File:** `tests/conftest.py:111`

**Issue:**
SR Config 더미 데이터에서 `data_bits=3`으로 설정하고 주석을 `# data_bits (8-bit)`로 표기했다. WIZ550 장치에서 `data_bits` 필드가 실제 비트 수를 저장하는지(8), 아니면 인덱스값(3=8bit)을 저장하는지 모호하다. 테스트 픽스처가 잘못된 값을 사용한다면 왕복 테스트(roundtrip)가 실제 장치 바이트 구조를 검증하지 못한다.

**Fix:**
Java 원본 `WIZ550SR_Config.java` 의 data_bits 인코딩 방식을 확인하고, 픽스처 주석을 명확히 한다:
```python
3,   # data_bits: 3=8bit (장치 인코딩 방식 per WIZ550SR_Config.java)
# 또는
8,   # data_bits: 실제 비트 수 그대로 저장
```

---

_Reviewed: 2026-05-18T12:09:01Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
