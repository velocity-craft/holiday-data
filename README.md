# holiday-data

Public holiday data for [OmniWake](https://github.com/velocity-craft) — 195+ countries, v2 schema, served via GitHub Pages.

## Quick Start

```
Base URL: https://velocity-craft.github.io/holiday-data/
Manifest: https://velocity-craft.github.io/holiday-data/manifest.json
Country:  https://velocity-craft.github.io/holiday-data/countries/{CC}.json
```

Country codes follow ISO 3166-1 alpha-2 (e.g., `US`, `KR`, `IN`).

## Repository Layout

```
holiday-data/
├── authoring/                  ← human-edited source data  [CC-BY-4.0]
│   ├── templates.json          ← ~80 holiday definitions, 8 languages
│   ├── rules.json              ← date computation rules
│   └── overrides/
│       └── {CC}.json           ← per-country holiday list + name overrides
│
├── scripts/                    ← build tooling              [MIT]
│   ├── build.py                ← generates dist/ from authoring/
│   └── validate.py             ← schema + format checks
│
├── dist/                       ← generated output           [CC-BY-4.0]
│   ├── manifest.json           ← OTA patch manifest
│   └── countries/
│       └── {CC}.json           ← v2 schema country packs
│
├── docs/
│   └── AUTHORING_SCHEMA.md     ← authoring format reference
│
├── .github/
│   └── workflows/
│       └── build.yml           ← CI: build → validate → publish to gh-pages
│
├── LICENSE                     ← MIT (scripts/, .github/)
├── LICENSE-DATA                ← CC-BY-4.0 (authoring/, dist/)
└── NOTICE                      ← attribution text for data reuse
```

## License

This repository uses a **dual license**:

| Directory | License |
|-----------|---------|
| `scripts/`, `.github/` | [MIT](LICENSE) |
| `authoring/`, `dist/` | [CC BY 4.0](LICENSE-DATA) |

When **reusing the data** (any files in `authoring/` or `dist/`), you must include the attribution text from [NOTICE](NOTICE).

When **reusing the build scripts** (any files in `scripts/` or `.github/`), the MIT license applies — no attribution required.

## v2 Country Pack Schema

```json
{
  "schemaVersion": 2,
  "countryCode": "US",
  "countryName": "United States",
  "timeZone": "America/New_York",
  "years": [2026, 2027],
  "holidays": [
    {
      "date": "2026-01-01",
      "localizedNames": {
        "ko": "신정",
        "en": "New Year's Day",
        "ja": "元日",
        "zh": "元旦",
        "es": "Año Nuevo",
        "fr": "Jour de l'An",
        "de": "Neujahr",
        "pt": "Ano Novo"
      },
      "type": "PUBLIC"
    }
  ]
}
```

Supported `type` values: `PUBLIC`, `OBSERVANCE`, `OPTIONAL`.

## OTA Manifest Schema

```json
{
  "schemaVersion": 1,
  "patches": []
}
```

The `patches` array is empty at launch. Corrections are distributed as patches without requiring an app update.

## Building Locally

```bash
pip install python-holidays pytz
python scripts/build.py
python scripts/validate.py
```

Output is written to `dist/`. The build is deterministic (sorted keys, sorted holidays by date).

## Year Coverage

Each country pack covers **current year + next year**. The CI workflow regenerates packs on every push to `main`.

## Deployment

GitHub Actions publishes `dist/` to the `gh-pages` branch on every push to `main`. GitHub Pages serves that branch at the base URL above.

## Contributing

1. Edit `authoring/overrides/{CC}.json` for country-specific corrections
2. Edit `authoring/templates.json` for holiday name translations
3. Run `python scripts/build.py && python scripts/validate.py` locally
4. Open a PR — CI will validate on the PR, publish only after merge to `main`
