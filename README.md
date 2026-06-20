# vigil

An automated daily operations system that builds a structured Anytype daily
brief — Bible readings, weather, tasks, finances, and morning messages —
with zero LLM cost for the deterministic Phase 1 step.

## Architecture

**Phase 1 (6:30 AM, no LLM):** `vigil brief` creates the parent object and
all deterministic sub-objects in Anytype: Bible devotionals, weather
forecast, Todoist tasks, financial alerts, and birthday checks. Produces a
state file for Phase 2.

**Phase 2 (6:40 AM, LLM):** An OpenClaw or Hermes Agent cron job reads the
state file and fills in the intelligence-dependent sub-objects: message
summaries, drafted replies, financial editorial, and a morning message with
AI-generated images.

**Phase 3 (every 3 hours, LLM):** A periodic sweep cron job checks for new
messages, calendar changes, and financial alerts throughout the day — keeping
the daily brief current without manual intervention.

All three phases run unattended via cron on a VPS. Phase 1 is pure Python
(zero LLM cost). Phases 2 and 3 use OpenClaw or Hermes Agent with
version-controlled RISEN prompts from `prompts/`.

## Package Layout

```
src/vigil/
├── __init__.py
├── cli.py            # Typer CLI — entry point (vigil brief, vigil monitor)
├── bible.py          # Bible reading plan parser (BOOKS_DIR, reading plan JSON)
├── config.py         # Centralised config / env-var loading
├── weather.py        # Open-Meteo weather fetcher
├── anytype/
│   ├── client.py     # Anytype REST API wrapper + Markdown builders
│   ├── bible.py      # Bible → Anytype body builder
│   ├── birthdays.py  # Birthday checker + body builder
│   ├── finance.py    # Finance → Anytype body + main() updater
│   ├── todoist.py    # Todoist task fetcher + body builder
│   ├── weather.py    # Weather → Anytype body builder
│   └── writer.py     # Phase 1 daily brief orchestrator
└── financial/
    ├── evaluators.py # Portfolio drift, recession, inflation evaluators
    ├── fetchers.py   # SnapTrade, OFX, FRED, yfinance data fetchers
    └── monitor.py    # Financial monitor orchestrator
```

## Quick Start

```bash
uv sync --dev              # install dependencies
cp .env.example .env       # fill in your API keys
set -a; source .env; set +a # load env vars; Vigil does not auto-load .env
uv run vigil brief         # run Phase 1 (creates Anytype objects)
uv run vigil monitor       # run standalone financial monitor
uv run vigil --help        # see all available commands
```

## Quality Gates

```bash
./scripts/check.sh         # ruff lint + format + mypy + pytest + pip-audit
./scripts/check.sh --fast  # skip pip-audit
```

## Environment Variables

| Variable | Description |
|---|---|
| `VIGIL_DATA_DIR` | Root data directory (default: `data/`) — sub-paths derive from this |
| `VIGIL_RUNTIME_DIR` | Private runtime directory for Phase 2 state/cache files |
| `VIGIL_TIMEZONE` | Local date boundary for daily briefs, Todoist, and birthdays |
| `ANYTYPE_API_KEY` | Anytype API key |
| `ANYTYPE_SPACE_ID` | Anytype space ID for the Daily Briefs space |
| `TODOIST_API_TOKEN` | Todoist API token |
| `CONTACTS_PATH` | Path to contacts JSON (default: `$VIGIL_DATA_DIR/contacts.json`) |
| `BIRTHDAY_USE_LLM` | `"true"` to use OpenRouter/Sonnet for birthday messages |
| `OPENROUTER_API_KEY` | OpenRouter API key (for birthday LLM messages) |
| `READING_PLAN_PATH` | Path to reading plan JSON (default: `$VIGIL_DATA_DIR/reading_plan.json`) |
| `BOOKS_DIR` | Directory containing book Markdown files (default: `$VIGIL_DATA_DIR/books/`) |
| `WEATHER_LAT` | Latitude (default: 35.2271) |
| `WEATHER_LON` | Longitude (default: -80.8431) |
| `WEATHER_TZ` | Timezone (default: America/New_York) |
| `SNAPTRADE_CLIENT_ID` | SnapTrade client ID |
| `SNAPTRADE_CONSUMER_KEY` | SnapTrade consumer key |
| `SNAPTRADE_USER_ID` | SnapTrade user ID |
| `SNAPTRADE_USER_SECRET` | SnapTrade user secret |
| `FRED_API_KEY` | FRED API key (free at fred.stlouisfed.org) |
| `ACCOUNT_MAP` | JSON mapping SnapTrade account names → portfolio categories |
| `OFX_BANKS_CONFIG` | JSON array of OFX bank connection configs |

See `data/examples/` for schema examples.

## Deployment

Full VPS deployment instructions are available in two variants:

- [`docs/setup-guide-openclaw.md`](docs/setup-guide-openclaw.md)
- [`docs/setup-guide-hermes.md`](docs/setup-guide-hermes.md)

## Prompts

Version-controlled RISEN prompts for OpenClaw or Hermes Agent cron jobs:

| File | Used by |
|---|---|
| `prompts/heartbeat.md` | Agent periodic heartbeat check |
| `prompts/morning_sweep.md` | Phase 2 LLM morning sweep (6:40 AM) |
| `prompts/periodic_sweep.md` | Every-3-hour message check |

One-time setup prompts for initial data preparation:

| File | Purpose |
|---|---|
| `prompts/setup/generate_voice_profile.md` | Generate a voice/style profile from raw messages |
| `prompts/setup/generate_reply_style.md` | Generate a reply style guide from message exchanges |
| `prompts/setup/convert_reading_plan.md` | Convert a reading plan to JSON |
| `prompts/setup/convert_contacts.md` | Convert contacts to JSON |

## Tests

```bash
uv run pytest                        # run all 237 tests
uv run pytest tests/anytype/         # anytype module tests only
uv run pytest tests/financial/       # financial module tests only
uv run pytest tests/test_cli.py      # CLI dispatch tests
```

Coverage: 97.36% across `src/vigil/`.
