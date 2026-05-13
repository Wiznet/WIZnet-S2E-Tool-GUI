# Roadmap: v1.6.3 Device Module Architecture

## Overview

DeviceSpec YAML 시스템에 모듈 메타데이터와 스키마 검증을 추가하여 장치 프로파일 에디터의 데이터 기반을 구축한다. 기존 specs/commands/*.yaml 구조를 유지하면서 meta: 블록과 JSON Schema를 점진적으로 추가하는 방식으로 진행한다. 기능 변화 없이 구조를 강화한다.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Schema Definition** - 장치 YAML 및 커맨드 그룹 YAML JSON Schema 정의
- [ ] **Phase 2: Module Metadata** - specs/commands/*.yaml 각 파일에 meta: 블록 추가
- [ ] **Phase 3: Loader Integration** - device_spec_loader.py 메타 로딩 + 호환성 검증 + 스키마 검증 통합

## Phase Details

### Phase 1: Schema Definition
**Goal**: 장치 YAML과 커맨드 그룹 YAML의 구조를 JSON Schema로 명문화하여 이후 작업의 데이터 계약을 확립한다
**Depends on**: Nothing (first phase)
**Requirements**: SCH-01
**Success Criteria** (what must be TRUE):
  1. `specs/schema/device.schema.json` 파일이 존재하고 기존 specs/devices/*.yaml 전체에 대해 유효성을 통과한다
  2. `specs/schema/command-group.schema.json` 파일이 존재하고 기존 specs/commands/*.yaml 전체에 대해 유효성을 통과한다
  3. meta: 블록 필드(id, name, category, description, requires, conflicts)가 스키마에 정의되어 있다
**Plans**: TBD

### Phase 2: Module Metadata
**Goal**: specs/commands/*.yaml 10개 파일 각각에 meta: 블록을 추가하여 에디터가 모듈을 카테고리별로 나열하고 조립 가능성을 판단할 수 있게 한다
**Depends on**: Phase 1
**Requirements**: MOD-01
**Success Criteria** (what must be TRUE):
  1. specs/commands/ 하위 모든 YAML 파일(base, ddns, gpio, modbus, pppoe, retransmit, security, telnet, two_port, w55rp20_ext)에 meta: 블록이 존재한다
  2. 각 meta: 블록이 Phase 1에서 정의한 command-group.schema.json을 통과한다
  3. requires/conflicts 필드가 실제 장치 조합 제약을 반영한다 (예: pppoe requires base, gpio conflicts security)
**Plans**: TBD

### Phase 3: Loader Integration
**Goal**: device_spec_loader.py가 모듈 메타데이터를 로딩하고 command_groups 호환성을 검증하며, YAML 로드 시 스키마 자동 검증이 실행된다
**Depends on**: Phase 2
**Requirements**: MOD-02, MOD-03, SCH-02
**Success Criteria** (what must be TRUE):
  1. `device_spec_loader.py`가 모듈 메타데이터를 로딩하고 DeviceSpec 객체에서 접근 가능하다 (예: `spec.module_meta["base"].name`)
  2. 유효하지 않은 command_groups 조합(requires/conflicts 위반)을 로딩 시 경고 또는 오류로 보고한다
  3. 잘못된 구조의 YAML 로드 시 스키마 검증 오류 메시지가 명확하게 출력된다
  4. 기존 장치 YAML 전체(specs/devices/*.yaml)가 수정 없이 정상 로딩된다 (회귀 없음)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema Definition | 0/TBD | Not started | - |
| 2. Module Metadata | 0/TBD | Not started | - |
| 3. Loader Integration | 0/TBD | Not started | - |
