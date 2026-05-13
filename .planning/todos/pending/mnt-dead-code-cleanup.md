---
id: mnt-dead-code-cleanup
title: "Dead code 및 import 중복 정리"
area: maintenance
priority: low
created: 2026-05-13
---

## 작업 내용

코드 품질 개선 — 에디터 방향 아키텍처와 무관하게 틈틈이 처리 가능한 정리 작업.

### 항목별

1. **TCPMulticastScanner.py 삭제** — 파일 상단 주석에 deprecated/미사용 명시됨
2. **version_compare_old() 삭제** — `WIZMakeCMD.py:143`, 이미 `version_compare()`로 대체됨
3. **device_spec_loader 함수 내 import 중복 제거** — `main_gui.py:1475,1488,1531` 3회 반복 → 모듈 레벨로 이동
4. **main_gui.py:4908 TODO 처리** — 테스트용 임시 비활성화 코드 잔류

## 완료 기준

각 항목 독립적으로 커밋 가능. 전체 완료 필요 없음.
