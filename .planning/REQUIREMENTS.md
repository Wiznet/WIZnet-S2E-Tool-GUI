# Requirements: v1.6.3 Device Module Architecture

## Active Requirements

### Module Metadata (에디터 기반 구축)

- [ ] **MOD-01**: `specs/commands/*.yaml` 각 파일에 `meta:` 블록 추가
  - 포함 필드: `id`, `name`, `category`, `description`, `requires`, `conflicts`
  - 에디터가 모듈을 카테고리별로 나열하고 조립 가능성을 판단하는 기반
- [ ] **MOD-02**: `device_spec_loader.py`가 모듈 메타데이터 로딩 지원
  - `load_module_meta()` 또는 기존 로더 확장
  - 로드된 메타데이터를 DeviceSpec 객체에서 접근 가능하게
- [ ] **MOD-03**: 장치 YAML `command_groups` 호환성 검증
  - `requires`/`conflicts` 기반으로 조합 유효성 체크
  - 유효하지 않은 조합은 로더에서 경고 또는 오류

### Schema Validation (데이터 품질)

- [ ] **SCH-01**: 장치 YAML 및 커맨드 YAML JSON Schema 정의
  - `specs/schema/device.schema.json`, `specs/schema/command-group.schema.json`
- [ ] **SCH-02**: `device_spec_loader.py` 로딩 시 스키마 검증 자동 실행
  - 유효하지 않은 YAML 로드 시 명확한 오류 메시지

## Future Requirements

- 시각적 모듈 조립 에디터 UI (별도 프로젝트)
- 모듈 조합으로부터 장치 YAML 자동 생성

## Out of Scope

- refactored/ 아키텍처 작업 — 보류/폐기 예정
- WizVSP 재구현 — 별도 계획 필요
- 신규 장치 지원 추가 — 이번 마일스톤은 구조 개선만

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SCH-01 | Phase 1 | Pending |
| MOD-01 | Phase 2 | Pending |
| MOD-02 | Phase 3 | Pending |
| MOD-03 | Phase 3 | Pending |
| SCH-02 | Phase 3 | Pending |
