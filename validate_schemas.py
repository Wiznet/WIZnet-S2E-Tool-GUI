"""
validate_schemas.py — WIZnet DeviceSpec YAML 스키마 검증 스크립트

사용법:
    python validate_schemas.py
    uv run python validate_schemas.py

종료 코드:
    0 — 모든 YAML이 스키마 통과
    1 — 하나 이상의 YAML이 스키마 실패
"""
import json
import sys
from pathlib import Path

import yaml

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema 패키지가 필요합니다.")
    print("       pip install jsonschema==4.26.0")
    sys.exit(1)

SPECS_DIR = Path(__file__).parent / "specs"
SCHEMA_DIR = SPECS_DIR / "schema"


def validate_all() -> None:
    device_schema = json.loads((SCHEMA_DIR / "device.schema.json").read_text(encoding="utf-8"))
    cmd_schema = json.loads((SCHEMA_DIR / "command-group.schema.json").read_text(encoding="utf-8"))

    errors: list[str] = []

    print("=== Device YAML ===")
    for f in sorted((SPECS_DIR / "devices").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=data, schema=device_schema)
            print(f"  OK  {f.name}")
        except jsonschema.ValidationError as e:
            errors.append(f"FAIL {f.name}: {e.message}")
            print(f"  FAIL {f.name}: {e.message}")

    print("\n=== Command Group YAML ===")
    for f in sorted((SPECS_DIR / "commands").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=data, schema=cmd_schema)
            print(f"  OK  {f.name}")
        except jsonschema.ValidationError as e:
            errors.append(f"FAIL {f.name}: {e.message}")
            print(f"  FAIL {f.name}: {e.message}")

    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        sys.exit(1)
    print("All schemas valid.")


if __name__ == "__main__":
    validate_all()
