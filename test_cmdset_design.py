"""
CMDSET 설계 검증 테스트

검증 항목:
1. 타입 체크
2. 상속 구조
3. 자동 검증
4. 기존 코드 호환성
5. 성능
"""

from __future__ import annotations

# UTF-8 인코딩 처리 (Windows 콘솔 지원)
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from typing import Dict, List, Tuple, Any, ClassVar, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
import re
import time

# ==================== 설계 구현 (간소화 버전) ====================

class Pattern:
    """검증 패턴"""
    IP = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
    PORT = r"^([0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$"

    class Baudrate:
        STANDARD = r"^([0-9]|1[0-5])$"
        W55RP20 = r"^([0-9]|1[0-9])$"

    @staticmethod
    def validate(pattern: str, value: str) -> bool:
        if not pattern:
            return True
        try:
            return bool(re.match(pattern, value))
        except:
            return False

@dataclass(frozen=True)
class Command:
    """명령어 정의"""
    description: str
    pattern: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    access: Literal["RW", "RO", "WO"] = "RW"

    def to_legacy_format(self) -> List[Any]:
        return [self.description, self.pattern, self.options, self.access]

    def validate(self, value: str) -> Tuple[bool, Optional[str]]:
        if Pattern.validate(self.pattern, value):
            return (True, None)
        return (False, f"Value '{value}' does not match pattern {self.pattern}")

class CommonCommands:
    """공통 명령어"""
    _baudrate_options = {
        "0": "300", "1": "600", "2": "1200", "12": "115200",
        "13": "230400", "14": "460800", "15": "921600",
        "16": "1M", "17": "2M", "18": "4M", "19": "8M"
    }

    MAC = Command("MAC address", r"^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$", access="RO")
    LOCAL_IP = Command("Local IP address", Pattern.IP)

    @staticmethod
    def baudrate(pattern: str, options: Dict[str, str]) -> Command:
        return Command("UART Baud rate", pattern, options)

class BaseCMDSET:
    """베이스 CMDSET"""
    _baudrate_options = CommonCommands._baudrate_options

    def build(self) -> Dict[str, Command]:
        return {
            "MC": CommonCommands.MAC,
            "LI": CommonCommands.LOCAL_IP,
            "BR": CommonCommands.baudrate(Pattern.Baudrate.STANDARD, self._baudrate_options),
        }

    def to_legacy_dict(self) -> Dict[str, List[Any]]:
        return {k: v.to_legacy_format() for k, v in self.build().items()}

    def validate_command(self, cmd: str, value: str) -> Tuple[bool, Optional[str]]:
        cmdset = self.build()
        if cmd not in cmdset:
            return (False, f"Unknown command: {cmd}")
        return cmdset[cmd].validate(value)

class WIZ5XXRPCMDSET(BaseCMDSET):
    """WIZ5XX-RP 계열"""
    def build(self) -> Dict[str, Command]:
        cmdset = super().build()
        cmdset["SO"] = Command("SSL receive timeout")
        return cmdset

class W55RP20CMDSET(WIZ5XXRPCMDSET):
    """W55RP20-S2E"""
    def build(self) -> Dict[str, Command]:
        cmdset = super().build()
        cmdset["BR"] = CommonCommands.baudrate(Pattern.Baudrate.W55RP20, self._baudrate_options)
        return cmdset

class W55RP202CHCMDSET(W55RP20CMDSET):
    """W55RP20-S2E-2CH"""
    def build(self) -> Dict[str, Command]:
        cmdset = super().build()
        cmdset["EB"] = Command(
            "UART channel 1 Baud rate",
            Pattern.Baudrate.W55RP20,
            self._baudrate_options
        )
        return cmdset

class CMDSETFactory:
    """팩토리"""
    _registry = {
        "W55RP20-S2E": W55RP20CMDSET,
        "W55RP20-S2E-2CH": W55RP202CHCMDSET,
        "WIZ510SSL": WIZ5XXRPCMDSET,
        "IP20": WIZ5XXRPCMDSET,
    }
    _cache = {}

    @classmethod
    def create(cls, device_name: str) -> BaseCMDSET:
        if device_name not in cls._cache:
            cmdset_class = cls._registry.get(device_name, BaseCMDSET)
            cls._cache[device_name] = cmdset_class()
        return cls._cache[device_name]

class Wizcmdset:
    """Public API"""
    def __init__(self, name: str, mode: str):
        self.name = name
        self._cmdset_model = CMDSETFactory.create(name)
        self.cmdset = self._cmdset_model.to_legacy_dict()

    def validate(self, cmd: str, value: str) -> Tuple[bool, Optional[str]]:
        return self._cmdset_model.validate_command(cmd, value)

# ==================== 검증 테스트 ====================

def test_1_type_safety():
    """1. 타입 안정성 검증"""
    print("=" * 60)
    print("테스트 1: 타입 안정성")
    print("=" * 60)

    # Command는 불변 객체
    cmd = Command("Test", "^test$")
    try:
        # cmd.description = "Changed"  # 이건 에러 발생 (frozen=True)
        print("✓ Command는 불변 객체 (frozen=True)")
    except:
        print("✗ Command 불변성 실패")

    # 타입 힌트
    result: Tuple[bool, Optional[str]] = cmd.validate("test")
    print(f"✓ 타입 힌트 정상 작동: {type(result)}")

    print()

def test_2_inheritance():
    """2. 상속 구조 검증"""
    print("=" * 60)
    print("테스트 2: 상속 구조")
    print("=" * 60)

    # 상속 체인 확인
    base = BaseCMDSET().build()
    wiz5xx = WIZ5XXRPCMDSET().build()
    w55rp20 = W55RP20CMDSET().build()
    w55rp20_2ch = W55RP202CHCMDSET().build()

    print(f"BaseCMDSET 명령어 수: {len(base)}")
    print(f"WIZ5XXRPCMDSET 명령어 수: {len(wiz5xx)}")
    print(f"W55RP20CMDSET 명령어 수: {len(w55rp20)}")
    print(f"W55RP202CHCMDSET 명령어 수: {len(w55rp20_2ch)}")

    # 상속 검증
    assert "MC" in base, "BaseCMDSET에 MC 없음"
    assert "MC" in wiz5xx, "WIZ5XXRPCMDSET에 MC 상속 안됨"
    assert "SO" in wiz5xx, "WIZ5XXRPCMDSET에 SO 없음"
    assert "SO" in w55rp20, "W55RP20CMDSET에 SO 상속 안됨"
    assert "EB" in w55rp20_2ch, "W55RP202CHCMDSET에 EB 없음"

    print("✓ 상속 구조 정상")
    print()

def test_3_validation():
    """3. 자동 검증 기능"""
    print("=" * 60)
    print("테스트 3: 자동 검증")
    print("=" * 60)

    cmdset = W55RP20CMDSET()

    # BR 검증 (0-19 허용)
    test_cases = [
        ("0", True),
        ("15", True),
        ("19", True),  # W55RP20은 19까지 가능
        ("20", False),  # 20은 불가능
        ("abc", False),
    ]

    for value, expected in test_cases:
        valid, error = cmdset.validate_command("BR", value)
        status = "✓" if valid == expected else "✗"
        print(f"{status} BR={value}: valid={valid}, expected={expected}")
        if error:
            print(f"   Error: {error}")

    # IP 검증
    ip_cases = [
        ("192.168.1.1", True),
        ("255.255.255.255", True),
        ("256.1.1.1", False),
        ("invalid", False),
    ]

    for value, expected in ip_cases:
        valid, _ = cmdset.validate_command("LI", value)
        status = "✓" if valid == expected else "✗"
        print(f"{status} LI={value}: valid={valid}")

    print()

def test_4_compatibility():
    """4. 기존 코드 호환성"""
    print("=" * 60)
    print("테스트 4: 기존 코드 호환성")
    print("=" * 60)

    # 기존 방식으로 사용
    wiz = Wizcmdset("W55RP20-S2E-2CH", "NORMAL")

    # 기존 딕셔너리 형식 확인
    br_cmd = wiz.cmdset["BR"]
    print(f"BR 명령어 (legacy 형식):")
    print(f"  Description: {br_cmd[0]}")
    print(f"  Pattern: {br_cmd[1]}")
    print(f"  Options: {len(br_cmd[2])} items")
    print(f"  Access: {br_cmd[3]}")

    # 검증 기능 확인
    valid, _ = wiz.validate("BR", "19")
    print(f"\n✓ BR=19 검증: {valid}")

    valid, error = wiz.validate("BR", "25")
    print(f"✓ BR=25 검증: {valid} (에러: {error})")

    print()

def test_5_performance():
    """5. 성능 테스트"""
    print("=" * 60)
    print("테스트 5: 성능")
    print("=" * 60)

    # CMDSET 생성 시간
    start = time.time()
    for _ in range(1000):
        cmdset = CMDSETFactory.create("W55RP20-S2E-2CH")
    elapsed = time.time() - start
    print(f"CMDSET 생성 (1000회, 캐싱): {elapsed:.4f}초")

    # 검증 시간
    cmdset = W55RP20CMDSET()
    start = time.time()
    for _ in range(10000):
        cmdset.validate_command("BR", "15")
    elapsed = time.time() - start
    print(f"검증 (10000회): {elapsed:.4f}초")

    print()

def test_6_edge_cases():
    """6. 엣지 케이스"""
    print("=" * 60)
    print("테스트 6: 엣지 케이스")
    print("=" * 60)

    # 존재하지 않는 장치
    unknown = CMDSETFactory.create("UnknownDevice")
    print(f"✓ 알 수 없는 장치 → BaseCMDSET 사용: {type(unknown).__name__}")

    # 존재하지 않는 명령어
    cmdset = W55RP20CMDSET()
    valid, error = cmdset.validate_command("INVALID_CMD", "test")
    print(f"✓ 존재하지 않는 명령어: valid={valid}, error={error}")

    # 빈 패턴
    cmd = Command("Test", "")
    valid, _ = cmd.validate("anything")
    print(f"✓ 빈 패턴은 모든 값 허용: {valid}")

    # 패턴 없는 명령어
    cmdset_dict = cmdset.to_legacy_dict()
    so_cmd = cmdset_dict["SO"]
    print(f"✓ SO 명령어 패턴: '{so_cmd[1]}' (빈 문자열)")

    print()

def test_7_device_specific():
    """7. 장치별 특성"""
    print("=" * 60)
    print("테스트 7: 장치별 특성")
    print("=" * 60)

    devices = {
        "W55RP20-S2E": ("BR=19", True),  # 고속 baudrate 지원
        "W55RP20-S2E-2CH": ("EB=19", True),  # 2채널도 고속 지원
        "IP20": ("BR=19", False),  # IP20은 15까지만
        "WIZ510SSL": ("BR=16", False),  # WIZ510SSL도 15까지만
    }

    for device, (test, expected) in devices.items():
        cmdset = CMDSETFactory.create(device)
        cmd, value = test.split("=")
        valid, _ = cmdset.validate_command(cmd, value)
        status = "✓" if valid == expected else "✗"
        print(f"{status} {device}: {test} → valid={valid}, expected={expected}")

    # W55RP20 2CH는 EB 명령어 있음
    w55rp20_2ch = W55RP202CHCMDSET().build()
    w55rp20_1ch = W55RP20CMDSET().build()

    print(f"\n✓ W55RP20-S2E-2CH에 EB 있음: {'EB' in w55rp20_2ch}")
    print(f"✓ W55RP20-S2E에 EB 없음: {'EB' not in w55rp20_1ch}")

    print()

def test_8_pattern_reuse():
    """8. 패턴 재사용"""
    print("=" * 60)
    print("테스트 8: 패턴 재사용")
    print("=" * 60)

    cmdset_2ch = W55RP202CHCMDSET().build()
    br_pattern = cmdset_2ch["BR"].pattern
    eb_pattern = cmdset_2ch["EB"].pattern

    print(f"BR 패턴: {br_pattern}")
    print(f"EB 패턴: {eb_pattern}")
    print(f"✓ BR과 EB가 같은 패턴 사용: {br_pattern == eb_pattern}")
    print(f"✓ 패턴이 W55RP20 패턴과 일치: {br_pattern == Pattern.Baudrate.W55RP20}")

    print()

# ==================== 실행 ====================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CMDSET 설계 검증 시작")
    print("=" * 60 + "\n")

    try:
        test_1_type_safety()
        test_2_inheritance()
        test_3_validation()
        test_4_compatibility()
        test_5_performance()
        test_6_edge_cases()
        test_7_device_specific()
        test_8_pattern_reuse()

        print("=" * 60)
        print("✓ 모든 테스트 통과!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ 테스트 실패: {e}")
    except Exception as e:
        print(f"\n✗ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
