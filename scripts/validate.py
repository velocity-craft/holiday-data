#!/usr/bin/env python3
"""
validate.py — validates all dist/countries/{CC}.json against the v2 schema

Usage:
    python scripts/validate.py
    python scripts/validate.py --country US   # single country

Exits with code 1 if any ERRORs found.
"""

import json
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_DIR   = SCRIPT_DIR.parent
DIST_DIR   = REPO_DIR / "dist"

REQUIRED_LOCALES = {"ko", "en", "ja", "zh", "es", "fr", "de", "pt"}
VALID_TYPES      = {"PUBLIC", "OBSERVANCE", "OPTIONAL"}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_pack(path: Path) -> tuple[list[str], list[str]]:
    errors   = []
    warnings = []

    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"], []

    cc = data.get("countryCode", path.stem)

    for field in ("schemaVersion", "countryCode", "countryName", "timeZone", "years", "holidays"):
        if field not in data:
            errors.append(f"Missing required field '{field}'")

    # IANA timezone
    try:
        import pytz
        pytz.timezone(data.get("timeZone", "UTC"))
    except Exception:
        errors.append(f"Invalid IANA timezone '{data.get('timeZone')}'")
    except ImportError:
        warnings.append("pytz not installed — timezone check skipped")

    declared_years = set(data.get("years", []))
    seen_dates: dict = {}

    for i, h in enumerate(data.get("holidays", [])):
        d_str = h.get("date", "")

        # Date format + year range
        try:
            d = date.fromisoformat(d_str)
            if d.year not in declared_years:
                errors.append(f"[{i}] date {d_str} outside declared years {sorted(declared_years)}")
        except (ValueError, TypeError):
            errors.append(f"[{i}] invalid date value '{d_str}'")
            continue

        # Duplicate dates
        if d_str in seen_dates:
            errors.append(f"Duplicate date {d_str} (entries {seen_dates[d_str]} and {i})")
        else:
            seen_dates[d_str] = i

        # Locale keys
        names   = h.get("localizedNames", {})
        missing = REQUIRED_LOCALES - set(names.keys())
        if missing:
            errors.append(f"[{i}] {d_str}: missing locale keys {sorted(missing)}")

        # type
        h_type = h.get("type", "PUBLIC")
        if h_type not in VALID_TYPES:
            errors.append(f"[{i}] {d_str}: invalid type '{h_type}' (must be one of {VALID_TYPES})")

        # No internal _keys in output
        for key in h:
            if key.startswith("_"):
                warnings.append(f"[{i}] internal key '{key}' present in dist output (strip it)")

    return errors, warnings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate dist/countries/*.json")
    parser.add_argument("--country", default=None, help="Validate a single country code (e.g. US)")
    args = parser.parse_args()

    countries_dir = DIST_DIR / "countries"
    if not countries_dir.exists():
        print("ERROR: dist/countries/ not found — run build.py first", file=sys.stderr)
        sys.exit(1)

    if args.country:
        files = [countries_dir / f"{args.country.upper()}.json"]
        missing = [f for f in files if not f.exists()]
        if missing:
            print(f"ERROR: {missing[0]} not found", file=sys.stderr)
            sys.exit(1)
    else:
        files = sorted(countries_dir.glob("*.json"))

    if not files:
        print("ERROR: No files in dist/countries/", file=sys.stderr)
        sys.exit(1)

    total_errors   = 0
    total_warnings = 0

    for path in files:
        errors, warnings = validate_pack(path)
        cc = path.stem
        for e in errors:
            print(f"ERROR [{cc}] {e}")
        for w in warnings:
            print(f"WARN  [{cc}] {w}")
        total_errors   += len(errors)
        total_warnings += len(warnings)

    print(f"\nValidated {len(files)} file(s) — {total_errors} error(s), {total_warnings} warning(s)")
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
