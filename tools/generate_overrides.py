#!/usr/bin/env python3
"""
generate_overrides.py — generates authoring/overrides/{CC}.json from python-holidays

Usage:
    python tools/generate_overrides.py              # all countries
    python tools/generate_overrides.py --country DE  # single country
    python tools/generate_overrides.py --dry-run     # stats only, no writes

Requires: pip install holidays pycountry pytz convertdate
"""

import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_DIR   = SCRIPT_DIR.parent
AUTH_DIR   = REPO_DIR / "authoring"

PROBE_YEARS    = [2024, 2025, 2026, 2027]
REQUIRED_LOCS  = ("ko", "en", "ja", "zh", "es", "fr", "de", "pt")
MONTH_ABBR     = ["", "jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec"]
WD_ABBR        = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# ---------------------------------------------------------------------------
# Easter anchors (same algorithm as build.py)
# ---------------------------------------------------------------------------

def _easter_w(year: int) -> date:
    a = year % 19; b = year // 100; c = year % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31; dy = (h + l - 7 * m + 114) % 31 + 1
    return date(year, mo, dy)

def _easter_e(year: int) -> date:
    a = year % 4; b = year % 7; c = year % 19
    d = (19 * c + 15) % 30; e = (2 * a + 4 * b - d + 34) % 7
    f = (d + e + 114) // 31; g = (d + e + 114) % 31 + 1
    return date(year, f, g) + timedelta(days=13)

EASTER_W = {y: _easter_w(y) for y in PROBE_YEARS}
EASTER_E = {y: _easter_e(y) for y in PROBE_YEARS}

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

_STRIP_SUFFIXES = re.compile(
    r"\s*\(observed\)|\s*\(substitute\)|\s*\(in lieu\)|\s*\(estimated\)|\s*\(approximate\)|"
    r"\s*observed$|\s*substitute$|\s*estimated$",
    re.I
)

def norm(name: str) -> str:
    name = _STRIP_SUFFIXES.sub("", name)
    return re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()

def norm_key(name: str) -> str:
    return " ".join(norm(name))

# Common holiday name → existing template ID
TEMPLATE_ALIASES: dict[str, str] = {
    # New Year
    "new years day": "new_year",
    "new year day": "new_year",
    "new years": "new_year",
    "new year": "new_year",
    "new years eve": "new_years_eve",
    # Christmas
    "christmas day": "christmas",
    "christmas": "christmas",
    "christmas eve": "christmas_eve",
    "second day of christmas": "christmas_2nd_day",
    "2nd day of christmas": "christmas_2nd_day",
    "st stephens day": "christmas_2nd_day",
    "boxing day": "boxing_day",
    # Easter
    "good friday": "good_friday",
    "holy saturday": "holy_saturday",
    "easter saturday": "holy_saturday",
    "easter sunday": "easter_sunday",
    "easter": "easter_sunday",
    "easter monday": "easter_monday",
    "ascension day": "ascension_day",
    "ascension thursday": "ascension_day",
    "whit sunday": "whit_sunday",
    "pentecost": "whit_sunday",
    "whit monday": "whit_monday",
    "pentecost monday": "whit_monday",
    "corpus christi": "corpus_christi",
    "all saints day": "all_saints_day",
    "all saints": "all_saints_day",
    "all souls day": "all_souls_day",
    # Catholic
    "epiphany": "epiphany",
    "three kings day": "epiphany",
    "feast of the epiphany": "epiphany",
    "assumption": "assumption",
    "assumption of mary": "assumption",
    "assumption of the virgin mary": "assumption",
    "immaculate conception": "immaculate_conception",
    "feast of immaculate conception": "immaculate_conception",
    # Labour / Workers
    "labour day": "labour_day",
    "labor day": "labour_day",
    "international workers day": "labour_day",
    "workers day": "labour_day",
    "international labour day": "labour_day",
    "may day": "labour_day",
    "international labor day": "labour_day",
    # Islamic
    "eid al fitr": "eid_ul_fitr",
    "eid ul fitr": "eid_ul_fitr",
    "eid al-fitr": "eid_ul_fitr",
    "eid-al-fitr day 1": "eid_ul_fitr",
    "feast of the sacrifice": "eid_al_adha",
    "eid al adha": "eid_al_adha",
    "eid ul adha": "eid_al_adha",
    "eid al-adha": "eid_al_adha",
    "eid-al-adha day 1": "eid_al_adha",
    "islamic new year": "islamic_new_year",
    "hijri new year": "islamic_new_year",
    "al hijra": "islamic_new_year",
    "al-hijra": "islamic_new_year",
    "prophets birthday": "prophet_birthday",
    "prophet birthday": "prophet_birthday",
    "mawlid al nabi": "prophet_birthday",
    "mawlid": "prophet_birthday",
    "birthday of the prophet": "prophet_birthday",
    "laylat al qadr": "laylat_al_qadr",
    "day of ashura": "day_of_ashura",
    "ashura": "day_of_ashura",
    # Lunar
    "chinese new year": "chinese_new_year",
    "lunar new year": "chinese_new_year",
    "spring festival": "chinese_new_year",
    "chinese new year eve": "chinese_new_year_eve",
    "mid autumn festival": "mid_autumn_festival",
    "mid-autumn festival": "mid_autumn_festival",
    "dragon boat festival": "dragon_boat_festival",
    "qingming festival": "qingming",
    "ching ming festival": "qingming",
    "qingming": "qingming",
    "ching ming": "qingming",
    # Women/Children/Family
    "international womens day": "international_womens_day",
    "womens day": "international_womens_day",
    "international women s day": "international_womens_day",
    "childrens day": "children_day",
    "children day": "children_day",
    "mothers day": "mothers_day",
    "mother s day": "mothers_day",
    "fathers day": "fathers_day",
    "father s day": "fathers_day",
    "youth day": "youth_day",
    "teachers day": "teachers_day",
    "teacher s day": "teachers_day",
    # Remembrance/Victory/Freedom
    "remembrance day": "armistice_day_generic",
    "armistice day": "armistice_day_generic",
    "veterans day": "armistice_day_generic",
    "anzac day": "anzac_day",
    "thanksgiving": "thanksgiving_day_generic",
    "thanksgiving day": "thanksgiving_day_generic",
    "human rights day": "human_rights_day",
    "africa freedom day": "liberation_day_generic",
    "africa day": "africa_day",
    # Europe specific
    "europe day": "europe_day",
    "eurovision": "europe_day",
    "bastille day": "bastille_day",
    "victory in europe day": "may_8",
    "victory day": "victory_day_generic",
    "national day": "national_day_generic",
    "republic day": "republic_day_generic",
    "revolution day": "revolution_day_generic",
    "liberation day": "liberation_day_generic",
    "independence day": "independence_day_generic",
    "constitution day": "constitution_day_generic",
    "unification day": "unification_day_generic",
    "national foundation day": "foundation_day_generic",
}

# Name → (template_id, rule_id) for lunisolar/astronomical holidays
# These bypass date-pattern detection since dates shift year-to-year
SPECIAL_RULES: dict[str, tuple[str, str]] = {
    # Islamic
    "eid al fitr": ("eid_ul_fitr", "islamic_shawwal_1"),
    "eid ul fitr": ("eid_ul_fitr", "islamic_shawwal_1"),
    "eid al fitr holiday": ("eid_ul_fitr", "islamic_shawwal_1"),
    "feast of breaking the fast": ("eid_ul_fitr", "islamic_shawwal_1"),
    "eid al adha": ("eid_al_adha", "islamic_dhul_hijja_10"),
    "eid ul adha": ("eid_al_adha", "islamic_dhul_hijja_10"),
    "eid al adha holiday": ("eid_al_adha", "islamic_dhul_hijja_10"),
    "feast of the sacrifice": ("eid_al_adha", "islamic_dhul_hijja_10"),
    "arafat day": ("arafat_day", "islamic_dhul_hijja_9"),
    "islamic new year": ("islamic_new_year", "islamic_muharram_1"),
    "hijri new year": ("islamic_new_year", "islamic_muharram_1"),
    "al hijra": ("islamic_new_year", "islamic_muharram_1"),
    "islamic new year al hijri": ("islamic_new_year", "islamic_muharram_1"),
    "prophets birthday": ("prophet_birthday", "islamic_rabi_12"),
    "mawlid al nabi": ("prophet_birthday", "islamic_rabi_12"),
    "birthday of the prophet muhammad": ("prophet_birthday", "islamic_rabi_12"),
    "day of ashura": ("day_of_ashura", "islamic_muharram_10"),
    "ashura": ("day_of_ashura", "islamic_muharram_10"),
    "isra and mi raj": ("isra_miraj", "islamic_rajab_27"),
    "isra miraj": ("isra_miraj", "islamic_rajab_27"),
    "laylat al qadr": ("laylat_al_qadr", "islamic_ramadan_27"),
    # Chinese lunisolar
    "chinese new year": ("chinese_new_year", "chinese_lunar_1_1"),
    "chinese new year spring festival": ("chinese_new_year", "chinese_lunar_1_1"),
    "spring festival": ("chinese_new_year", "chinese_lunar_1_1"),
    "lunar new year": ("chinese_new_year", "chinese_lunar_1_1"),
    "chinese new year eve": ("chinese_new_year_eve", "chinese_lunar_12_last"),
    "chinese new year s eve": ("chinese_new_year_eve", "chinese_lunar_12_last"),
    "chinese new years eve": ("chinese_new_year_eve", "chinese_lunar_12_last"),
    "mid autumn festival": ("mid_autumn_festival", "chinese_lunar_8_15"),
    "mid-autumn festival": ("mid_autumn_festival", "chinese_lunar_8_15"),
    "dragon boat festival": ("dragon_boat_festival", "chinese_lunar_5_5"),
    "qingming festival": ("qingming", "solar_term_qingming"),
    "tomb sweeping day": ("qingming", "solar_term_qingming"),
    "ching ming festival": ("qingming", "solar_term_qingming"),
    "ching ming": ("qingming", "solar_term_qingming"),
    "qingming": ("qingming", "solar_term_qingming"),
    "labor day golden week": ("labour_day", "fixed_may_1"),
    # Korean lunisolar
    "korean new year": ("chinese_new_year", "korean_lunar_1_1"),
    "seollal": ("chinese_new_year", "korean_lunar_1_1"),
    "the day preceding korean new year": ("chinese_new_year_eve", "korean_lunar_1_neg1"),
    "chuseok": ("mid_autumn_festival", "korean_lunar_8_15"),
    "chuseok holiday": ("mid_autumn_festival", "korean_lunar_8_15"),
    "the second day of korean new year": ("korean_new_year_2nd_day", "korean_lunar_1_2"),
    "the day following chuseok": ("chuseok_2nd_day", "korean_lunar_8_16"),
    "the second day of chuseok": ("chuseok_2nd_day", "korean_lunar_8_16"),
    "the day preceding chuseok": ("chuseok_eve", "korean_lunar_8_14"),
    # Buddha's Birthday (Korean lunar 4/8)
    "buddha s birthday": ("buddha_birthday", "korean_lunar_4_8"),
    "buddhas birthday": ("buddha_birthday", "korean_lunar_4_8"),
    "birthday of the buddha": ("buddha_birthday", "korean_lunar_4_8"),
    "vesak": ("buddha_birthday", "korean_lunar_4_8"),
    # Japanese astronomical
    "vernal equinox day": ("japan_vernal_equinox", "japan_vernal_equinox_computed"),
    "autumnal equinox day": ("japan_autumnal_equinox", "japan_autumnal_equinox_computed"),
    # Islamic — apostrophe variants
    "prophet s birthday": ("prophet_birthday", "islamic_rabi_12"),
    "prophet s birthday mawlid": ("prophet_birthday", "islamic_rabi_12"),
    "day of arafah": ("arafat_day", "islamic_dhul_hijja_9"),
    "arafah day": ("arafat_day", "islamic_dhul_hijja_9"),
    "eid al fitr": ("eid_ul_fitr", "islamic_shawwal_1"),
    # Hindu
    "diwali": ("diwali", "hindu_diwali"),
    "deepavali": ("diwali", "hindu_diwali"),
    "diwali deepavali": ("diwali", "hindu_diwali"),
    "holi": ("holi", "hindu_holi"),
}

# Patterns to skip (observed/substitute/extra days)
_SKIP_RE = re.compile(
    r"observ|substit|in lieu|bridge|extra|additional|alternative holiday|"
    r"2nd day of eid|3rd day of eid|day 2|day 3|day 4",
    re.I
)

def should_skip(name: str) -> bool:
    return bool(_SKIP_RE.search(name))

# ---------------------------------------------------------------------------
# Rule detection
# ---------------------------------------------------------------------------

def detect_rule(dates_by_year: dict) -> tuple[str, dict]:
    valid = {y: d for y, d in dates_by_year.items() if d is not None}
    if not valid:
        return "unknown", {}
    dates = list(valid.values())

    # 1. Fixed
    mds = {(d.month, d.day) for d in dates}
    if len(mds) == 1:
        m, dy = mds.pop()
        return "fixed", {"month": m, "day": dy}

    if len(valid) < 2:
        return "unknown", {}

    # 2. Easter western offset
    if all(y in EASTER_W for y in valid):
        offs = {(d - EASTER_W[y]).days for y, d in valid.items()}
        if len(offs) == 1:
            return "offset_western", {"days": offs.pop()}

    # 3. Easter eastern offset
    if all(y in EASTER_E for y in valid):
        offs = {(d - EASTER_E[y]).days for y, d in valid.items()}
        if len(offs) == 1:
            return "offset_eastern", {"days": offs.pop()}

    # 4. Nth weekday of month
    months = {d.month for d in dates}
    if len(months) == 1:
        month = months.pop()
        wds = {d.weekday() for d in dates}
        if len(wds) == 1:
            wd = wds.pop()
            ordinals = set()
            is_last  = True
            for d in dates:
                first  = date(d.year, month, 1)
                delta  = (wd - first.weekday()) % 7
                first_occ = first + timedelta(days=delta)
                ordinals.add((d - first_occ).days // 7 + 1)
                if (d + timedelta(days=7)).month == month:
                    is_last = False
            if is_last and len(ordinals) <= 2:
                return "last_weekday", {"month": month, "weekday": WD_ABBR[wd]}
            if len(ordinals) == 1:
                return "nth_weekday", {"month": month, "weekday": WD_ABBR[wd], "ordinal": ordinals.pop()}

    return "unknown", {}

# ---------------------------------------------------------------------------
# Rule ID from type+params
# ---------------------------------------------------------------------------

def make_rule_id(rule_type: str, params: dict) -> str | None:
    if rule_type == "fixed":
        return f"fixed_{MONTH_ABBR[params['month']]}_{params['day']}"
    if rule_type == "offset_western":
        days = params["days"]
        if days == 0:
            return "computus_western"
        sign = "pos" if days > 0 else "neg"
        return f"offset_computus_western_{sign}{abs(days)}"
    if rule_type == "offset_eastern":
        days = params["days"]
        if days == 0:
            return "computus_eastern"
        sign = "pos" if days > 0 else "neg"
        return f"offset_computus_eastern_{sign}{abs(days)}"
    if rule_type == "nth_weekday":
        wd = params["weekday"].lower()
        mo = MONTH_ABBR[params["month"]]
        return f"nth_{wd}_{mo}_{params['ordinal']}"
    if rule_type == "last_weekday":
        wd = params["weekday"].lower()
        mo = MONTH_ABBR[params["month"]]
        return f"last_{wd}_{mo}"
    return None

def make_rule_entry(rule_type: str, params: dict) -> dict:
    if rule_type == "fixed":
        return {"type": "fixed", "month": params["month"], "day": params["day"]}
    if rule_type in ("offset_western", "offset_eastern"):
        days = params["days"]
        base = "computus_western" if rule_type == "offset_western" else "computus_eastern"
        if days == 0:
            variant = "western" if rule_type == "offset_western" else "eastern"
            return {"type": "computus", "variant": variant}
        return {"type": "offset", "base": base, "days": days}
    if rule_type == "nth_weekday":
        return {"type": "nth_weekday", "month": params["month"],
                "weekday": params["weekday"], "ordinal": params["ordinal"]}
    if rule_type == "last_weekday":
        return {"type": "last_weekday", "month": params["month"], "weekday": params["weekday"]}
    return {}

# ---------------------------------------------------------------------------
# Country metadata
# ---------------------------------------------------------------------------

import pytz

# Capital/primary timezone overrides (first pytz entry isn't always capital)
TZ_OVERRIDE: dict[str, str] = {
    "AU": "Australia/Sydney",   "BR": "America/Sao_Paulo",
    "CA": "America/Toronto",    "CD": "Africa/Kinshasa",
    "CN": "Asia/Shanghai",      "ES": "Europe/Madrid",
    "ID": "Asia/Jakarta",       "IN": "Asia/Kolkata",
    "KZ": "Asia/Almaty",        "MX": "America/Mexico_City",
    "MN": "Asia/Ulaanbaatar",   "MY": "Asia/Kuala_Lumpur",
    "RU": "Europe/Moscow",      "US": "America/New_York",
}

def country_tz(cc: str) -> str:
    if cc in TZ_OVERRIDE:
        return TZ_OVERRIDE[cc]
    tzs = pytz.country_timezones.get(cc)
    if tzs:
        return tzs[0]
    return "UTC"

def country_name(cc: str) -> str:
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=cc)
        return c.name if c else cc
    except Exception:
        return cc

# ---------------------------------------------------------------------------
# Template & rule registries
# ---------------------------------------------------------------------------

def ensure_rule(rules: dict, rule_id: str, rule_entry: dict) -> str:
    if rule_id and rule_id not in rules:
        rules[rule_id] = rule_entry
    return rule_id

def ensure_template(templates: dict, template_id: str, eng_name: str) -> str:
    if template_id not in templates:
        templates[template_id] = {
            "defaultName": eng_name,
            "localizedNames": {loc: eng_name for loc in REQUIRED_LOCS},
        }
    return template_id

def build_name_index(templates: dict) -> dict[str, str]:
    idx: dict[str, str] = {}
    for tid, tmpl in templates.items():
        for name in [tmpl.get("defaultName", ""), *tmpl.get("localizedNames", {}).values()]:
            k = norm_key(name)
            if k:
                idx[k] = tid
    return idx

# ---------------------------------------------------------------------------
# Main country generator
# ---------------------------------------------------------------------------

def generate_country(cc: str, templates: dict, rules: dict, name_idx: dict) -> dict | None:
    import holidays as pyhol

    by_year: dict[int, dict[date, str]] = {}
    for y in PROBE_YEARS:
        try:
            by_year[y] = dict(pyhol.country_holidays(cc, years=y, language="en_US"))
        except Exception:
            try:
                by_year[y] = dict(pyhol.country_holidays(cc, years=y))
            except Exception:
                pass
    if not any(by_year.values()):
        return None

    # Group: canonical_key → {year: earliest-date}
    # Take the earliest date per name per year to handle multi-day holidays (e.g. CN Golden Week)
    canon: dict[str, dict[int, date]] = defaultdict(dict)
    canon_to_eng: dict[str, str] = {}
    for y, hols in by_year.items():
        for d, name in sorted(hols.items()):   # sorted by date
            if should_skip(name):
                continue
            key = norm_key(name)
            if y not in canon[key]:             # keep earliest occurrence
                canon[key][y] = d
            if key not in canon_to_eng:
                canon_to_eng[key] = name

    entries    = []
    unresolved = []

    for key, dates_by_year in canon.items():
        eng_name  = canon_to_eng[key]
        # Check SPECIAL_RULES first (lunisolar/astronomical bypass date detection)
        special = SPECIAL_RULES.get(key)
        if special:
            tmpl_id, rule_id = special
            # Ensure template/rule exist
            ensure_template(templates, tmpl_id, eng_name)
            if rule_id not in rules:
                pass  # Rule should already exist in rules.json
        else:
            rule_type, rule_params = detect_rule(dates_by_year)
            if rule_type == "unknown":
                unresolved.append(eng_name)
                continue

            rule_id    = make_rule_id(rule_type, rule_params)
            rule_entry = make_rule_entry(rule_type, rule_params)
            ensure_rule(rules, rule_id, rule_entry)

            # Template lookup
            tmpl_id = TEMPLATE_ALIASES.get(key)
            if not tmpl_id:
                tmpl_id = name_idx.get(key)
            if not tmpl_id:
                cc_lower = cc.lower()
                slug = re.sub(r"\s+", "_", re.sub(r"[^a-z0-9 ]", "", key))[:40]
                tmpl_id = f"{cc_lower}_{slug}"
                ensure_template(templates, tmpl_id, eng_name)
                name_idx[key] = tmpl_id

        entries.append({
            "_name":    eng_name,
            "_month":   next(iter(dates_by_year.values())).month,
            "template": tmpl_id,
            "rule":     rule_id,
        })

    if not entries:
        return None

    # Sort by month of first probe year occurrence
    entries.sort(key=lambda e: (e["_month"], e["template"]))
    clean = [{"template": e["template"], "rule": e["rule"]} for e in entries]

    return {
        "countryCode": cc,
        "countryName": country_name(cc),
        "timeZone":    country_tz(cc),
        "holidays":    clean,
        "_unresolved": unresolved,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    import holidays as pyhol

    parser = argparse.ArgumentParser(description="Generate override files from python-holidays")
    parser.add_argument("--country", default=None, help="Single country code (e.g. DE)")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing override files")
    args = parser.parse_args()

    overrides_dir = AUTH_DIR / "overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)

    with open(AUTH_DIR / "templates.json", encoding="utf-8") as f:
        templates_data = json.load(f)
    with open(AUTH_DIR / "rules.json", encoding="utf-8") as f:
        rules_data = json.load(f)

    templates: dict = templates_data["templates"]
    rules:     dict = rules_data["rules"]
    name_idx        = build_name_index(templates)

    all_ccs = sorted(pyhol.list_supported_countries().keys())
    if args.country:
        all_ccs = [args.country.upper()]

    # Skip already-authored countries (unless --force)
    already = set() if args.force else {p.stem for p in overrides_dir.glob("*.json")}

    done      = []
    skipped   = []
    total_unresolved = 0

    for cc in all_ccs:
        if len(cc) != 2:
            continue
        if cc in already:
            print(f"  {cc}: already authored (skip)")
            skipped.append(cc)
            continue

        override = generate_country(cc, templates, rules, name_idx)
        if not override:
            print(f"  {cc}: no holidays detected")
            skipped.append(cc)
            continue

        unresolved = override.pop("_unresolved", [])
        total_unresolved += len(unresolved)

        n = len(override["holidays"])
        print(f"  {cc}: {n} holidays", end="")
        if unresolved:
            print(f"  [{len(unresolved)} unresolved: {unresolved[:3]}{'…' if len(unresolved)>3 else ''}]", end="")
        print()

        if not args.dry_run:
            out = overrides_dir / f"{cc}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(override, f, ensure_ascii=False, indent=2)
        done.append(cc)

    if not args.dry_run:
        with open(AUTH_DIR / "templates.json", "w", encoding="utf-8") as f:
            json.dump(templates_data, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(AUTH_DIR / "rules.json", "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"\n✓  Generated {len(done)} countries, skipped {len(skipped)}")
    print(f"   Templates: {len(templates)}  Rules: {len(rules)}")
    print(f"   Unresolved holiday instances: {total_unresolved}")


if __name__ == "__main__":
    main()
