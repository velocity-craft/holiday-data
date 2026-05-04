#!/usr/bin/env python3
"""
build.py — generates dist/countries/{CC}.json from authoring/

Usage:
    python scripts/build.py [--years YEAR,YEAR]

Dependencies:
    pip install pytz convertdate
    pip install ephem   # optional — enables solar_term / astronomical rules
"""

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_DIR   = SCRIPT_DIR.parent
AUTHORING_DIR = REPO_DIR / "authoring"
DIST_DIR      = REPO_DIR / "dist"

CURRENT_YEAR  = date.today().year
TARGET_YEARS  = [CURRENT_YEAR, CURRENT_YEAR + 1]

WEEKDAY_MAP = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
REQUIRED_LOCALES = ("ko", "en", "ja", "zh", "es", "fr", "de", "pt")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_private_keys(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Easter algorithms
# ---------------------------------------------------------------------------

def easter_western(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def easter_eastern(year: int) -> date:
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    f = (d + e + 114) // 31
    g = (d + e + 114) % 31 + 1
    julian = date(year, f, g)
    # Julian → Gregorian: +13 days (valid for 1900–2099)
    return julian + timedelta(days=13)


# ---------------------------------------------------------------------------
# Rule resolvers
# ---------------------------------------------------------------------------

def resolve_fixed(rule: dict, year: int) -> date:
    return date(year, rule["month"], rule["day"])


def resolve_nth_weekday(rule: dict, year: int) -> date:
    wd    = WEEKDAY_MAP[rule["weekday"]]
    first = date(year, rule["month"], 1)
    delta = (wd - first.weekday()) % 7
    return first + timedelta(days=delta + 7 * (rule["ordinal"] - 1))


def resolve_last_weekday(rule: dict, year: int) -> date:
    wd = WEEKDAY_MAP[rule["weekday"]]
    m  = rule["month"]
    last = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else date(year, 12, 31)
    delta = (last.weekday() - wd) % 7
    return last - timedelta(days=delta)


def resolve_nearest_weekday_before_or_on(rule: dict, year: int) -> date:
    target = date(year, rule["month"], rule["day"])
    wd     = WEEKDAY_MAP[rule["weekday"]]
    delta  = (target.weekday() - wd) % 7
    return target - timedelta(days=delta)


def resolve_computus(rule: dict, year: int) -> date:
    return easter_western(year) if rule["variant"] == "western" else easter_eastern(year)


def resolve_offset(rule: dict, year: int, rules: dict, cache: dict) -> date:
    base = _resolve(rule["base"], year, rules, cache)
    return base + timedelta(days=rule["days"])


def resolve_chinese_lunisolar(rule: dict, year: int) -> date | None:
    try:
        from convertdate import chinese
    except ImportError:
        raise RuntimeError("pip install convertdate")
    month = rule["month"]
    day   = rule["day"]
    try:
        greg = chinese.to_gregorian(year, month, day)
        return date(*greg)
    except Exception:
        return None


def resolve_korean_lunisolar(rule: dict, year: int) -> date | None:
    try:
        from convertdate import chinese  # Korean uses same algorithm
    except ImportError:
        raise RuntimeError("pip install convertdate")
    month = rule["month"]
    day   = rule["day"]
    if day == -1:
        # Last day of the previous lunar month = day before Lunar New Year
        new_year_greg = chinese.to_gregorian(year, 1, 1)
        return date(*new_year_greg) - timedelta(days=1)
    try:
        greg = chinese.to_gregorian(year, month, day)
        return date(*greg)
    except Exception:
        return None


def resolve_hijri(rule: dict, year: int) -> date | None:
    try:
        from convertdate import islamic
    except ImportError:
        raise RuntimeError("pip install convertdate")
    hijri_month = rule["month"]
    hijri_day   = rule["day"]
    # Estimate overlapping Hijri year(s) for the given Gregorian year
    approx_hy = math.floor((year - 622) * 1.030684)
    for hy in range(approx_hy - 1, approx_hy + 2):
        try:
            greg = islamic.to_gregorian(hy, hijri_month, hijri_day)
            d = date(*greg)
            if d.year == year:
                return d
        except (ValueError, OverflowError):
            pass
    return None


def resolve_hindu_lunisolar(rule: dict, year: int) -> date | None:
    # Delegate to python-holidays for Hindu calendar (complex computation)
    try:
        import holidays as pyhol
    except ImportError:
        raise RuntimeError("pip install holidays")
    month_name = rule.get("month", "")
    tithi      = rule.get("tithi", "")
    keyword_map = {
        ("kartika",  "amavasya"): ["Diwali", "Deepavali"],
        ("phalguna", "purnima"):  ["Holi"],
    }
    keywords = keyword_map.get((month_name, tithi), [])
    ih = pyhol.country_holidays("IN", years=year)
    for d, name in ih.items():
        for kw in keywords:
            if kw.lower() in name.lower():
                return d
    return None


def resolve_solar_term(rule: dict, year: int) -> date:
    longitude = rule["longitude"]  # ecliptic degrees (e.g., 15 for Qingming)
    try:
        import ephem
        target_lon = math.radians(longitude)
        sun = ephem.Sun()
        # Search Mar 20 – Apr 20
        lo = ephem.Date(f"{year}/3/20")
        hi = ephem.Date(f"{year}/4/20")
        for _ in range(50):
            mid = (lo + hi) / 2
            sun.compute(mid, epoch=ephem.J2000)
            lon = float(ephem.Ecliptic(sun, epoch=ephem.J2000).lon)
            if lon < target_lon:
                lo = mid
            else:
                hi = mid
        dt = ephem.Date((lo + hi) / 2).datetime()
        return date(dt.year, dt.month, dt.day)
    except ImportError:
        # Fallback: Qingming ≈ Apr 4 in leap years, Apr 5 otherwise
        return date(year, 4, 4 if (year % 4 == 0 and year % 100 != 0) else 5)


def resolve_astronomical(rule: dict, year: int) -> date:
    event   = rule["event"]
    tz_name = rule.get("timezone", "UTC")
    try:
        import ephem, pytz
        if event == "autumnal_equinox":
            d = ephem.next_autumnal_equinox(f"{year}/9/1")
        elif event == "vernal_equinox":
            d = ephem.next_vernal_equinox(f"{year}/3/1")
        else:
            return date(year, 9, 23)
        tz  = pytz.timezone(tz_name)
        dt  = ephem.Date(d).datetime()
        dtl = pytz.utc.localize(dt).astimezone(tz)
        return dtl.date()
    except ImportError:
        fallbacks = {"autumnal_equinox": date(year, 9, 23), "vernal_equinox": date(year, 3, 20)}
        return fallbacks.get(event, date(year, 9, 23))


# ---------------------------------------------------------------------------
# Central rule dispatcher
# ---------------------------------------------------------------------------

def _resolve(rule_id: str, year: int, rules: dict, cache: dict) -> date | None:
    key = (rule_id, year)
    if key in cache:
        return cache[key]
    rule  = rules[rule_id]
    rtype = rule["type"]
    if rtype == "fixed":
        result = resolve_fixed(rule, year)
    elif rtype == "nth_weekday":
        result = resolve_nth_weekday(rule, year)
    elif rtype == "last_weekday":
        result = resolve_last_weekday(rule, year)
    elif rtype == "nearest_weekday_before_or_on":
        result = resolve_nearest_weekday_before_or_on(rule, year)
    elif rtype == "computus":
        result = resolve_computus(rule, year)
    elif rtype == "offset":
        result = resolve_offset(rule, year, rules, cache)
    elif rtype == "lunisolar":
        cal = rule["calendar"]
        if cal == "chinese":
            result = resolve_chinese_lunisolar(rule, year)
        elif cal == "korean":
            result = resolve_korean_lunisolar(rule, year)
        elif cal == "hijri":
            result = resolve_hijri(rule, year)
        elif cal == "hindu":
            result = resolve_hindu_lunisolar(rule, year)
        else:
            raise ValueError(f"Unknown lunisolar calendar: {cal}")
    elif rtype == "solar_term":
        result = resolve_solar_term(rule, year)
    elif rtype == "astronomical":
        result = resolve_astronomical(rule, year)
    else:
        raise ValueError(f"Unknown rule type: {rtype}")
    cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Country pack builder
# ---------------------------------------------------------------------------

def build_country(override: dict, templates: dict, rules: dict, years: list[int]) -> dict:
    cc      = override["countryCode"]
    cache: dict = {}
    entries = []

    for h_def in override["holidays"]:
        tmpl_id      = h_def["template"]
        rule_id      = h_def["rule"]
        h_type       = h_def.get("type", "PUBLIC")
        name_override = h_def.get("nameOverride", {})

        if tmpl_id not in templates:
            print(f"  WARN [{cc}]: unknown template '{tmpl_id}'", file=sys.stderr)
            continue
        if rule_id not in rules:
            print(f"  WARN [{cc}]: unknown rule '{rule_id}'", file=sys.stderr)
            continue

        localized = dict(templates[tmpl_id]["localizedNames"])
        localized.update(name_override)
        # Ensure all 8 locales present (fill with en fallback if missing)
        for loc in REQUIRED_LOCALES:
            if loc not in localized:
                localized[loc] = localized.get("en", templates[tmpl_id]["defaultName"])

        for year in years:
            try:
                d = _resolve(rule_id, year, rules, cache)
            except Exception as exc:
                print(f"  WARN [{cc}] rule '{rule_id}' year {year}: {exc}", file=sys.stderr)
                continue
            if d is None:
                continue
            entries.append({
                "date": d.isoformat(),
                "localizedNames": dict(sorted(localized.items())),
                "type": h_type,
            })

    # Sort by date; deduplicate (keep first)
    seen: set = set()
    holidays_out = []
    for h in sorted(entries, key=lambda x: x["date"]):
        if h["date"] not in seen:
            seen.add(h["date"])
            holidays_out.append(h)

    return {
        "schemaVersion": 2,
        "countryCode": override["countryCode"],
        "countryName": override["countryName"],
        "timeZone": override["timeZone"],
        "years": sorted(years),
        "holidays": holidays_out,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build holiday packs from authoring/")
    parser.add_argument(
        "--years", default=None,
        help="Comma-separated years, e.g. 2026,2027 (default: current + next)"
    )
    args = parser.parse_args()

    years = TARGET_YEARS
    if args.years:
        years = [int(y.strip()) for y in args.years.split(",")]

    templates_raw = load_json(AUTHORING_DIR / "templates.json")
    rules_raw     = load_json(AUTHORING_DIR / "rules.json")

    templates = {k: strip_private_keys(v) for k, v in templates_raw["templates"].items()}
    rules     = {k: strip_private_keys(v) for k, v in rules_raw["rules"].items()}

    overrides_dir = AUTHORING_DIR / "overrides"
    countries_dir = DIST_DIR / "countries"
    countries_dir.mkdir(parents=True, exist_ok=True)

    override_files = sorted(overrides_dir.glob("*.json"))
    if not override_files:
        print("ERROR: no override files in authoring/overrides/", file=sys.stderr)
        sys.exit(1)

    count = 0
    for path in override_files:
        override = load_json(path)
        cc = override.get("countryCode", path.stem)
        print(f"Building {cc}...", end=" ")
        pack = build_country(override, templates, rules, years)
        out_path = countries_dir / f"{cc}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"→ {len(pack['holidays'])} holidays")
        count += 1

    manifest = {"patches": [], "schemaVersion": 1}
    with open(DIST_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"\n✓  Built {count} pack(s) for years {years}")
    print(f"✓  Manifest written to dist/manifest.json")


if __name__ == "__main__":
    main()
