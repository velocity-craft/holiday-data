# Authoring Schema Reference

This document defines the format for all files under `authoring/`.

## Overview

The authoring layer separates **what a holiday is** (templates) from **when it occurs** (rules) from **which holidays a country observes** (overrides).

```
authoring/
├── templates.json       ← Named holiday concepts with 8-language names
├── rules.json           ← Date computation rules (fixed / nth-weekday / lunisolar / …)
└── overrides/
    └── {CC}.json        ← Per-country holiday list: template + rule pairs
```

`build.py` reads these three inputs and writes `dist/countries/{CC}.json` in the v2 schema for each country in `overrides/`.

---

## templates.json

**Purpose:** Defines the *identity* of each holiday — its human-readable name in 8 languages. Templates are reused across countries; a country-specific `nameOverride` can override any locale.

```json
{
  "schemaVersion": 1,
  "templates": {
    "<template_id>": {
      "defaultName": "<English fallback>",
      "localizedNames": {
        "ko": "...", "en": "...", "ja": "...", "zh": "...",
        "es": "...", "fr": "...", "de": "...", "pt": "..."
      }
    }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaVersion` | integer | ✓ | Must be `1` |
| `templates` | object | ✓ | Map of template ID → definition |
| `defaultName` | string | ✓ | English fallback if a locale key is missing |
| `localizedNames` | object | ✓ | Must contain all 8 locale keys: `ko en ja zh es fr de pt` |

**Template ID convention:** `snake_case`. Generic IDs for globally reused holidays (`new_year`, `christmas`); country-prefixed for country-specific (`us_thanksgiving`, `japan_culture_day`); `_generic` suffix for placeholder templates used with `nameOverride`.

**Localization gaps:** In Phase A2, country-specific templates may use English as placeholder. Phase A5 runs `translate.py` to fill all gaps. `validate.py` treats missing locale keys as errors.

---

## rules.json

**Purpose:** Defines *how to compute* a holiday date for a given year. Rules are reusable across countries.

```json
{
  "schemaVersion": 1,
  "rules": {
    "<rule_id>": { "type": "<type>", ...type-specific fields... }
  }
}
```

### Rule Types

#### `fixed` — Fixed Gregorian date

```json
"fixed_jan_1": { "type": "fixed", "month": 1, "day": 1 }
```

#### `nth_weekday` — Nth weekday of a month

```json
"nth_mon_jan_3": { "type": "nth_weekday", "month": 1, "weekday": "MON", "ordinal": 3 }
```

`weekday`: `MON` `TUE` `WED` `THU` `FRI` `SAT` `SUN`

#### `last_weekday` — Last weekday of a month

```json
"last_mon_may": { "type": "last_weekday", "month": 5, "weekday": "MON" }
```

#### `nearest_weekday_before_or_on` — Last occurrence on or before a fixed date

```json
"mon_before_may_25": {
  "type": "nearest_weekday_before_or_on",
  "weekday": "MON", "month": 5, "day": 25
}
```

Used for Victoria Day (Canada): Monday on or before May 25.

#### `computus` — Easter

```json
"computus_western": { "type": "computus", "variant": "western" }
"computus_eastern": { "type": "computus", "variant": "eastern" }
```

| Variant | Algorithm |
|---------|-----------|
| `western` | Anonymous Gregorian algorithm |
| `eastern` | Julian Easter converted to Gregorian |

#### `offset` — Days relative to another rule

```json
"offset_computus_western_neg2": {
  "type": "offset", "base": "computus_western", "days": -2
}
```

Common Easter offsets:

| `days` | Holiday |
|--------|---------|
| −2 | Good Friday |
| −1 | Holy Saturday |
| +1 | Easter Monday |
| +39 | Ascension Day |
| +49 | Whit Sunday |
| +50 | Whit Monday |
| +60 | Corpus Christi |

#### `lunisolar` — Lunisolar calendar

```json
"chinese_lunar_1_1":  { "type": "lunisolar", "calendar": "chinese", "month": 1, "day": 1 }
"korean_lunar_8_15":  { "type": "lunisolar", "calendar": "korean",  "month": 8, "day": 15 }
"islamic_shawwal_1":  { "type": "lunisolar", "calendar": "hijri",   "month": 10, "day": 1 }
"hindu_diwali":       { "type": "lunisolar", "calendar": "hindu", "month": "kartika", "tithi": "amavasya" }
```

| `calendar` | Notes |
|------------|-------|
| `chinese` | Chinese lunisolar |
| `korean` | Korean lunisolar. `"day": -1` = last day of previous month |
| `hijri` | Islamic Hijri. Months: Muharram=1 … Dhul Hijjah=12. Dates are **approximate** — actual observance varies by moon sighting. |
| `hindu` | Use month name (`kartika`, `phalguna`, …) + `tithi` name (`amavasya` = new moon, `purnima` = full moon). |

#### `solar_term` — Chinese solar term

```json
"solar_term_qingming": { "type": "solar_term", "longitude": 15 }
```

Date when the sun reaches the given ecliptic longitude (degrees). Qingming = 15° ≈ April 4–5.

#### `astronomical` — Precise astronomical event

```json
"japan_autumnal_equinox_computed": {
  "type": "astronomical", "event": "autumnal_equinox", "timezone": "Asia/Tokyo"
}
```

Used for Japanese equinox holidays. `event`: `autumnal_equinox` or `vernal_equinox`.

---

## overrides/{CC}.json

**Purpose:** Declares which holidays a country observes, linking templates to rules. CC = ISO 3166-1 alpha-2 (uppercase).

```json
{
  "countryCode": "US",
  "countryName": "United States",
  "timeZone": "America/New_York",
  "holidays": [
    { "template": "new_year", "rule": "fixed_jan_1" },
    { "template": "us_thanksgiving", "rule": "nth_thu_nov_4" },
    {
      "template": "independence_day_generic",
      "rule": "fixed_jul_4",
      "nameOverride": { "en": "Independence Day", "ko": "미국 독립기념일" }
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `countryCode` | string | ✓ | ISO 3166-1 alpha-2 (uppercase) |
| `countryName` | string | ✓ | English country name |
| `timeZone` | string | ✓ | IANA timezone (capital / primary zone) |
| `holidays` | array | ✓ | Observed holidays |
| `holidays[].template` | string | ✓ | Key in `templates.json` |
| `holidays[].rule` | string | ✓ | Key in `rules.json` |
| `holidays[].nameOverride` | object | — | Locale → name. Partial override allowed. |
| `holidays[].type` | string | — | `PUBLIC` (default), `OBSERVANCE`, or `OPTIONAL` |

**Multi-timezone countries:** Use the capital city timezone.

---

## Workflows

### Adding a new country

1. Create `authoring/overrides/{CC}.json`
2. For each holiday pick an existing template/rule or add new ones
3. `python scripts/build.py && python scripts/validate.py`
4. Spot-check `dist/countries/{CC}.json`

### Adding a new template

1. Choose a `snake_case` ID
2. Fill all 8 locale keys (use English as placeholder if unknown, run `translate.py` later)
3. Add to `templates.json`

### Adding a new rule

1. Choose a descriptive ID (`fixed_mar_21`, `nth_sun_jun_3`, …)
2. Add to `rules.json` with `type` and required fields
3. Add `_note` for non-obvious rules

---

## validate.py Checks

| Check | Severity |
|-------|----------|
| All 8 locale keys present in `localizedNames` | ERROR |
| All `template` refs resolve in `templates.json` | ERROR |
| All `rule` refs resolve in `rules.json` | ERROR |
| Output dates in declared `years` range | ERROR |
| No duplicate dates per country | ERROR |
| `timeZone` is a valid IANA zone | ERROR |
| `_note` / `_comment` keys absent from `dist/` output | WARNING |
| `nameOverride` locale keys are valid | WARNING |
