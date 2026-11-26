#!/usr/bin/env python3
"""Validate all mongory-spec fixture files against schema.json (Draft 2020-12) and check VERSION."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema.json"
VERSION_PATH = ROOT / "VERSION"
FIXTURES_DIR = ROOT / "fixtures"


def main() -> int:
    errors: list[str] = []

    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"VERSION: expected semver X.Y.Z, got {version!r}")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    fixture_files = sorted(FIXTURES_DIR.rglob("*.json"))
    if not fixture_files:
        errors.append("fixtures/: no .json files found")

    total_suites = 0
    total_checks = 0
    for path in fixture_files:
        rel = path.relative_to(ROOT)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON: {exc}")
            continue

        file_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        for err in file_errors:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            errors.append(f"{rel} [{loc}]: {err.message}")

        if isinstance(data, list):
            seen_desc: set[str] = set()
            for idx, suite in enumerate(data):
                total_suites += 1
                if isinstance(suite, dict):
                    desc = suite.get("description")
                    if isinstance(desc, str):
                        if desc in seen_desc:
                            errors.append(f"{rel} [{idx}]: duplicate description {desc!r}")
                        seen_desc.add(desc)
                    records = suite.get("records")
                    if isinstance(records, list):
                        total_checks += len(records)
                    elif suite.get("error") is True:
                        total_checks += 1

    if errors:
        for line in errors:
            print(f"ERROR: {line}", file=sys.stderr)
        print(f"Validation FAILED with {len(errors)} error(s).", file=sys.stderr)
        return 1

    print(
        f"OK: VERSION={version}, {len(fixture_files)} fixture files, "
        f"{total_suites} suites, {total_checks} checks validated against schema.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
