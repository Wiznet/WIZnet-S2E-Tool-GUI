#!/usr/bin/env python3
"""Decimal YAML 처리 테스트"""

from device_search_config import DeviceSearchConfig
from decimal import Decimal

def test_decimal_yaml():
    print("=" * 60)
    print("YAML Decimal 처리 테스트")
    print("=" * 60)

    # 1. 설정 로드
    print("\n[1] 설정 로드 중...")
    config = DeviceSearchConfig()

    # 2. 값 확인 (Decimal 타입인지)
    print("\n[2] 값 타입 확인:")

    timeout_value = config.config.get('search', {}).get('phase3', {}).get('device_query_timeout_sec')
    broadcast_value = config.config.get('search', {}).get('phase1', {}).get('broadcast_timeout_sec')

    print(f"  device_query_timeout_sec:")
    print(f"    값: {timeout_value}")
    print(f"    타입: {type(timeout_value)}")
    print(f"    Decimal 여부: {isinstance(timeout_value, Decimal)}")

    print(f"\n  broadcast_timeout_sec:")
    print(f"    값: {broadcast_value}")
    print(f"    타입: {type(broadcast_value)}")
    print(f"    Decimal 여부: {isinstance(broadcast_value, Decimal)}")

    # 3. 값 수정 (Decimal로)
    print("\n[3] device_query_timeout_sec를 Decimal('1.0')으로 수정...")
    config.config['search']['phase3']['device_query_timeout_sec'] = Decimal('1.0')

    # 4. 저장
    print("\n[4] 설정 저장 중...")
    success = config.save_config()
    print(f"  저장 결과: {'성공' if success else '실패'}")

    # 5. 다시 로드해서 확인
    print("\n[5] 재로드 후 확인:")
    config2 = DeviceSearchConfig()
    timeout_value2 = config2.config.get('search', {}).get('phase3', {}).get('device_query_timeout_sec')

    print(f"  device_query_timeout_sec:")
    print(f"    값: {timeout_value2}")
    print(f"    타입: {type(timeout_value2)}")
    print(f"    정확한 값: {timeout_value2 == Decimal('1.0')}")
    print(f"    문자열 표현: '{timeout_value2}'")

    # 6. YAML 파일 내용 직접 확인
    print("\n[6] YAML 파일 내용 확인:")
    with open('config/device_search_timing.yaml', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'device_query_timeout_sec' in line:
                print(f"  Line {i}: {line.rstrip()}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)

if __name__ == '__main__':
    test_decimal_yaml()
