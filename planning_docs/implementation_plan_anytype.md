# Implementation Plan: Notion → Anytype Migration

> **Goal:** Replace the Notion API backend with Anytype's local-first API.
> Rename all `notion_*` modules to `anytype_*`, rewrite the API client to use
> Anytype's REST API (served headless via the Anytype CLI on the VPS), update
> the setup guide, and update the RISEN prompts to reflect the new LLM model
> strategy (ChatGPT Plus OAuth primary, OpenRouter fallback).

---

## §1 — Problem Statement

### 1.1 Notion is a cloud dependency with no E2EE

The current system writes all daily brief data (Bible reading, finances,
messages, replies) to Notion's servers via their REST API. Notion does not
offer end-to-end encryption. The data is readable by Notion's infrastructure.
For a system that handles financial data, personal messages, and drafted
replies, this is an unacceptable privacy posture.

### 1.2 Anytype provides local-first E2EE with a mature API

Anytype is a local-first, E2EE knowledge tool. Data is encrypted before it
leaves the device. Anytype provides a stable REST API (latest version:
`2025-11-08`) with full CRUD for spaces, objects, properties, types, and
templates. The API supports **Markdown in the body field**, which maps directly
to our existing block builders.

### 1.3 Anytype CLI enables headless VPS operation

The [Anytype CLI](https://github.com/anyproto/anytype-cli) runs Anytype as a
headless server (`anytype serve` or `anytype service install`). It exposes the
full API at `http://127.0.0.1:31012` and supports bot accounts and headless
API key generation. This is exactly what we need for the VPS cron job.

### 1.4 LLM model strategy needs updating

The current RISEN prompts hardcode model references. The new strategy is:

| Task | Primary (ChatGPT Plus OAuth, $20/mo) | Fallback (OpenRouter, reasoning on) |
|------|------|---------|
| General summarization | GPT-5.4 | Gemini 3.1 Pro |
| Chanry's messages | GPT-5.4 + special prompt | Claude Opus 4.6 |
| General replies | GPT-5.4 + special prompt | Claude Sonnet 4.6 |
| Image generation | 9 text prompts (no generation) | N/A |

---

## §2 — Design Decisions

### 2.1 Anytype's object model replaces Notion's page/block model

**Notion model (current):**
```
Database → Page (parent) → Child Pages (sub-pages) → Blocks (content)
```
Each sub-page (Bible, Weather, etc.) is a Notion child page with blocks
appended via `PATCH /blocks/{page_id}/children`.

**Anytype model (target):**
```
Space → Object (parent, type_key="page") → Child Objects (linked pages)
```
Each sub-page becomes an Anytype object with its content in the `body` field
as **Markdown**. No block builder API — the body field accepts a single
Markdown string.

**Key simplification:** Anytype's `body` takes raw Markdown. Our current
block builders (`heading_2()`, `paragraph()`, `table()`, etc.) return
Notion-specific dict structures. In the Anytype version, we replace these
with **Markdown string builders** — much simpler.

### 2.2 `AnytypeClient` replaces `NotionClient`

The `NotionClient` (307 lines) wraps the Notion REST API with:
- `create_page(database_id, title, icon)` → page ID
- `create_child_page(parent_id, title, icon)` → page ID
- `append_blocks(page_id, blocks)` → None

The `AnytypeClient` will wrap the Anytype API with:
- `list_spaces()` → list of space dicts
- `create_object(space_id, name, icon, body, type_key)` → object ID
- `update_object(space_id, object_id, body)` → None
- `get_object(space_id, object_id)` → object dict
- `search_objects(space_id, query, types)` → list of objects
- `delete_object(space_id, object_id)` → None

**API base URL:** `http://127.0.0.1:31012` (Anytype CLI headless server)
**API version header:** `Anytype-Version: 2025-11-08`
**Auth:** `Authorization: Bearer <ANYTYPE_API_KEY>`

### 2.3 Block builders become Markdown builders

**Before (Notion):**
```python
from notion_client import heading_2, paragraph, table, divider

blocks = [
    heading_2("Today's Weather"),
    paragraph("Sunny, 75°F"),
    divider(),
    table(["Time", "Temp"], [["9 AM", "68°F"]]),
]
client.append_blocks(page_id, blocks)
```

**After (Anytype):**
```python
from anytype_client import md_heading, md_paragraph, md_table, md_divider

body = "\n\n".join([
    md_heading("Today's Weather", level=2),
    md_paragraph("Sunny, 75°F"),
    md_divider(),
    md_table(["Time", "Temp"], [["9 AM", "68°F"]]),
])
client.update_object(space_id, object_id, body=body)
```

The Markdown builders are trivial string-returning functions, not dict-returning
functions. This reduces `anytype_client.py` significantly (from 307).

### 2.4 Anytype cloud sync (free tier, 1 GB) for device sync

The VPS writes to Anytype via the local API. Anytype's cloud sync (free tier,
$0/yr, 1 GB E2EE storage) syncs to your Pixel, iPad, and Mac automatically.
No self-hosted `any-sync` network needed. Data is E2EE before it leaves the
VPS.

### 2.5 Reply tracking via PATCH with Markdown strikethrough

When a reply is sent, the RISEN prompt instructs the LLM to:
1. Search for today's daily brief object via `POST /v1/spaces/{space_id}/search`
2. Retrieve the object via `GET /v1/spaces/{space_id}/objects/{object_id}`
3. Parse the existing `body` Markdown
4. Wrap the drafted reply in `~~strikethrough~~` and append the actual sent text
5. PATCH the object body via `PATCH /v1/spaces/{space_id}/objects/{object_id}`

This uses the Anytype API's **Markdown body patching** feature (added
`2025-11-08` API version).

### 2.6 Style prompt compilation step in setup guide

A new setup guide step instructs the user to:
1. Compile 10-15 past messages to Chanry → create a `chanry_style.md` prompt
2. Compile 10-15 past messages to friends → create a `reply_style.md` prompt
3. These files are referenced by the RISEN prompts as few-shot examples

### 2.7 Image generation → text prompts only

The LLM generates 3 message variations for Chanry. For each variation, it
generates 3 image prompts (9 total). These are **text descriptions only** —
the user generates the actual image manually for free (via ChatGPT Plus
DALL-E or any other tool). No `Nano Banana` API calls. $0/yr image cost.

---

## §3 — Dependency Graph (After Changes)

### 3.1 File rename mapping

| Old file | New file | Actual lines | Change type |
|----------|----------|-------------|-------------|
| `notion_client.py` | `anytype_client.py` | 307 | **REWRITE** |
| `notion_writer.py` | `anytype_writer.py` | 140 | **REWRITE** |
| `notion_bible.py` | `anytype_bible.py` | 156 | **MODIFY** (import + API calls) |
| `notion_weather.py` | `anytype_weather.py` | 154 | **MODIFY** (import + API calls) |
| `notion_finance.py` | `anytype_finance.py` | 249 | **MODIFY** (import + API calls + standalone script) |
| `notion_todoist.py` | `anytype_todoist.py` | 124 | **MODIFY** (import + API calls) |
| `notion_birthdays.py` | `anytype_birthdays.py` | 165 | **MODIFY** (import + API calls) |
| `tests/test_notion_client.py` | `tests/test_anytype_client.py` | 242 | **REWRITE** |
| `tests/test_notion_writer.py` | `tests/test_anytype_writer.py` | 421 | **REWRITE** |
| `tests/test_notion_bible.py` | `tests/test_anytype_bible.py` | 156 | **MODIFY** |
| `tests/test_notion_weather.py` | `tests/test_anytype_weather.py` | 225 | **MODIFY** |
| `tests/test_notion_finance.py` | `tests/test_anytype_finance.py` | 187 | **MODIFY** |
| `tests/test_notion_todoist.py` | `tests/test_anytype_todoist.py` | 98 | **MODIFY** |
| `tests/test_notion_birthdays.py` | `tests/test_anytype_birthdays.py` | 188 | **MODIFY** |

### 3.2 Files that need Notion → Anytype env var renames

| File | Change needed |
|------|---------------|
| `fm_config.py` (line 118-119) | Rename `NOTION_TOKEN` → `ANYTYPE_API_KEY`, `NOTION_DAILY_BRIEFS_DB` → `ANYTYPE_SPACE_ID` |

> [!IMPORTANT]
> `fm_config.py` exports `NOTION_TOKEN` and `NOTION_DAILY_BRIEFS_DB` as module-level
> constants. Both `notion_writer.py` and `notion_finance.py` import these from
> `fm_config`. To avoid a chicken-and-egg problem during migration:
> 1. **Phase 0:** Add `ANYTYPE_API_KEY` and `ANYTYPE_SPACE_ID` as NEW aliases
>    in `fm_config.py` (keep the old `NOTION_*` lines intact)
> 2. **Phases 1-3:** New `anytype_*` modules import the new names
> 3. **Phase 5:** Delete old `notion_*` files
> 4. **Phase 7:** Remove old `NOTION_*` lines from `fm_config.py`

### 3.3 Import graph (after changes)

```
anytype_client.py    → httpx (already a dependency)
anytype_writer.py    → fm_config (ANYTYPE_API_KEY, ANYTYPE_SPACE_ID, CONTACTS_PATH)
                     → anytype_client.py, anytype_bible.py, anytype_weather.py,
                       anytype_todoist.py, anytype_finance.py, anytype_birthdays.py,
                       bible_reading.py, weather_fetch.py
anytype_bible.py     → anytype_client.py (md_* builders only)
anytype_weather.py   → anytype_client.py (md_* builders only)
anytype_finance.py   → fm_config (ANYTYPE_API_KEY), anytype_client.py
anytype_todoist.py   → anytype_client.py (md_* builders only)
anytype_birthdays.py → anytype_client.py (md_* builders only)
```

### 3.4 `notion_finance.py` is a standalone script (special case)

`notion_finance.py` has a `main()` function that is called **by the Phase 2
LLM sweep** (not by the writer). The LLM runs `python3 notion_finance.py`
after writing editorial content. The script:
1. Reads the state file `/tmp/daily_brief_state.json`
2. Reads the FM cache file `/tmp/daily_brief_fm_output.json`
3. Gets `finance_page_id` from `state["sub_pages"]["finance"]`
4. Creates its own `NotionClient(NOTION_TOKEN)`
5. Appends finance data blocks to the page

The `anytype_finance.py` replacement must preserve this standalone pattern:
1. Read the state file (new format: `state["sub_objects"]["finance"]`)
2. Read the FM cache file
3. Create its own `AnytypeClient(ANYTYPE_API_KEY)`
4. Update the finance object body via `client.update_object()`

### 3.5 Unchanged files

- `bible_reading.py` — data-fetching only, no Notion/Anytype dependency
- `weather_fetch.py` — data-fetching only, no Notion/Anytype dependency
- `financial_monitor.py` — data-fetching only, no Notion/Anytype dependency
- `fm_fetchers.py`, `fm_evaluators.py` — unchanged
- `tests/test_bible_reading.py`, `tests/test_weather_fetch.py`,
  `tests/test_financial_monitor.py` — unchanged

> [!NOTE]
> There is no `tests/conftest.py` file in this project.

---

## §4 — File-by-File Changes

### 4.1 New Files (Rewrites)

---

#### [NEW] `anytype_client.py`

Replaces `notion_client.py`. Thin wrapper around Anytype's REST API using
`httpx`. Key differences from Notion:

- **Base URL:** `http://127.0.0.1:31012` (configurable via `ANYTYPE_API_URL` env var)
- **Auth:** `Authorization: Bearer <ANYTYPE_API_KEY>` (env var)
- **Version header:** `Anytype-Version: 2025-11-08`
- **Content model:** `body` field accepts Markdown (no block arrays)
- **Object creation payload:**
  ```python
  {
      "name": "📋 Daily Brief — April 10, 2026",
      "type_key": "page",
      "icon": {"emoji": "📋", "format": "emoji"},
      "body": "## Bible Reading\n\nGenesis 1-3...",
  }
  ```

**Public API surface:**

```python
class AnytypeClient:
    def __init__(self, api_key: str, base_url: str = "http://127.0.0.1:31012") -> None: ...
    def list_spaces(self) -> list[dict[str, Any]]: ...
    def create_object(self, space_id: str, name: str, icon: str,
                      body: str, type_key: str = "page") -> str: ...
    def update_object(self, space_id: str, object_id: str, *,
                      body: str | None = None, name: str | None = None) -> None: ...
    def get_object(self, space_id: str, object_id: str) -> dict[str, Any]: ...
    def search_objects(self, space_id: str, query: str,
                       types: list[str] | None = None) -> list[dict[str, Any]]: ...
    def delete_object(self, space_id: str, object_id: str) -> None: ...
```

**Markdown builder functions (module-level):**

```python
def md_heading(text: str, level: int = 2) -> str: ...
def md_paragraph(text: str) -> str: ...
def md_bullet(text: str) -> str: ...
def md_callout(text: str, icon: str = "📝") -> str: ...
def md_divider() -> str: ...
def md_table(headers: list[str], rows: list[list[str]]) -> str: ...
def md_toggle(title: str, content: str) -> str: ...
```

> [!IMPORTANT]
> Anytype's `body` field has no documented character limit like Notion's 2000-char
> block limit. However, always test with a full daily brief to verify the API
> accepts content of that length (~5000-10000 chars).

---

#### [NEW] `anytype_writer.py`

Replaces `notion_writer.py`. The orchestrator that creates the daily brief
parent object and all sub-page objects.

**Key differences from Notion version:**
- Imports `ANYTYPE_API_KEY`, `ANYTYPE_SPACE_ID`, `CONTACTS_PATH` from `fm_config`
  (same pattern as current `notion_writer.py` importing from `fm_config`)
- Uses `space_id` instead of `database_id` for the parent container
- Creates 6 sub-page objects as standalone objects in the space (Anytype has
  no parent-child page nesting via the API)
- Sub-pages: `morning_bible`, `evening_bible`, `weather`, `todoist`, `finance`,
  `birthdays` — same as current `notion_writer.py`
- Each sub-page's content is a single Markdown `body` string
- Calls domain modules to get Markdown strings, NOT blocks
- Writes state file to `/tmp/daily_brief_state.json` (same path as before)
- State file format changes: `sub_objects` replaces `sub_pages`

**Environment variables (loaded via `fm_config.py`):**
- `ANYTYPE_API_KEY` — replaces `NOTION_TOKEN` (in `fm_config.py`)
- `ANYTYPE_SPACE_ID` — replaces `NOTION_DAILY_BRIEFS_DB` (in `fm_config.py`)

**Environment variable (loaded by `AnytypeClient.__init__` from `os.environ`):**
- `ANYTYPE_API_URL` — optional, defaults to `http://127.0.0.1:31012`
  (NOT in `fm_config.py` — this is a client-level concern)

---

### 4.2 Modified Files (Rename + API Adaptation)

Each `notion_*.py` domain module follows the same pattern:
1. Rename `notion_` prefix to `anytype_`
2. Change `from notion_client import heading_2, paragraph, ...` to
   `from anytype_client import md_heading, md_paragraph, ...`
3. Replace Notion block-builder function calls with Markdown builder calls
4. Change the `build_*_blocks()` function to return a **Markdown string**
   instead of a `list[dict[str, Any]]`
5. The writer calls `client.create_object(space_id, name, icon, body=body_md)`
   — domain modules do NOT call the client themselves

**Exception:** `anytype_finance.py` is ALSO a standalone script (see §3.4).
Its `build_finance_blocks()` → `build_finance_body()` returns a Markdown
string, but its `main()` function creates its own `AnytypeClient` and calls
`client.update_object()`.

---

#### [DELETE] `notion_client.py`, `notion_writer.py`, `notion_bible.py`, `notion_weather.py`, `notion_finance.py`, `notion_todoist.py`, `notion_birthdays.py`

All 7 Notion source files are deleted after their Anytype replacements are
created and tests pass.

#### [DELETE] `tests/test_notion_client.py`, `tests/test_notion_writer.py`, `tests/test_notion_bible.py`, `tests/test_notion_weather.py`, `tests/test_notion_finance.py`, `tests/test_notion_todoist.py`, `tests/test_notion_birthdays.py`

All 7 Notion test files are deleted after their Anytype replacements pass.

---

### 4.3 Setup Guide Changes

#### [MODIFY] `setup-guide.md` (project root, NOT planning_docs/)

**Step 4 — Notion Account + Integration → Anytype Account + CLI Setup**

Complete rewrite. The new step covers:
1. Install the Anytype desktop app on Mac/iPad/Pixel (for viewing the daily briefs)
2. Create an Anytype account (free tier, 1 GB E2EE sync)
3. Create a space called "Daily Briefs" in the desktop app
4. On the VPS, install the Anytype CLI:
   ```bash
   /usr/bin/env bash -c "$(curl -fsSL https://raw.githubusercontent.com/anyproto/anytype-cli/HEAD/install.sh)"
   ```
5. Create a bot account and generate an API key:
   ```bash
   anytype auth create openclaw-bot
   anytype auth apikey create openclaw-daily-brief
   ```
6. Install the Anytype CLI as a systemd service:
   ```bash
   anytype service install
   anytype service start
   ```
7. Join the "Daily Briefs" space from the CLI (or create a new space)
8. Get the space ID:
   ```bash
   curl http://127.0.0.1:31012/v1/spaces \
     -H "Authorization: Bearer <YOUR_API_KEY>" \
     -H "Anytype-Version: 2025-11-08"
   ```
9. Set environment variables:
   ```bash
   export ANYTYPE_API_KEY="your-api-key"
   export ANYTYPE_SPACE_ID="bafyrei...your-space-id"
   ```

**NEW Step — Compile Style Prompts (between Steps 3 and 4)**

1. Compile 10-15 past messages **to Chanry** into `chanry_style.md`:
   - Include variety: morning messages, sweet messages, funny messages
   - These serve as few-shot examples for GPT-5.4's special prompt
2. Compile 10-15 past messages **to friends** into `reply_style.md`:
   - Include variety: casual texts, substantive replies, group chat messages
   - These serve as few-shot examples for the general reply prompt
3. Upload both to VPS:
   ```bash
   scp chanry_style.md reply_style.md root@<vps-ip>:/home/openclaw/data/
   ```

**Step 10 — Deploy OpenClaw via Coolify**

Add ChatGPT Plus OAuth onboarding:
- During onboarding, select `--auth-choice openai-codex`
- This bridges the $20/mo ChatGPT Plus subscription for GPT-5.4 access
- No per-token billing for primary LLM usage

**Step 13c — Deploy Notion Modules → Deploy Anytype Modules**

Update file names in all SCP commands and env vars to reflect `anytype_*` names.

**Step 15c — Phase 2 RISEN Prompt Updates**

- Replace all model references:
  - "Claude Sonnet 4.6 (via OpenRouter)" → "GPT-5.4 (via ChatGPT Plus OAuth)"
  - "Claude Opus 4.6 with extended thinking (via OpenRouter)" → per-task routing
- Add fallback instructions per task
- Replace "Google's Nano Banana (latest, via OpenRouter) for image generation"
  with "Generate 9 detailed image prompts (3 per message variation) as text"

> [!WARNING]
> The Anytype API rate limit is 60 requests burst, then 1/sec. A full daily
> brief with 6 sub-pages + parent = 7 API calls. This is well within burst
> limits. The carryover search + update adds 2-3 more calls. Total: ~10 calls
> per morning sweep, no rate limit concern.

---

## §5 — Anytype API Reference (Quick Sheet)

All endpoints use base URL `http://127.0.0.1:31012/v1` (CLI headless) or
`http://localhost:31009/v1` (desktop app).

| Operation | Method | Endpoint | Key fields |
|-----------|--------|----------|------------|
| List spaces | `GET` | `/spaces` | — |
| Create space | `POST` | `/spaces` | `name`, `description` |
| Create object | `POST` | `/spaces/{sid}/objects` | `name`, `type_key`, `body`, `icon` |
| Get object | `GET` | `/spaces/{sid}/objects/{oid}` | — |
| Update object | `PATCH` | `/spaces/{sid}/objects/{oid}` | `body`, `name` |
| Delete object | `DELETE` | `/spaces/{sid}/objects/{oid}` | — |
| Search in space | `POST` | `/spaces/{sid}/search` | `query`, `types`, `sort` |
| Global search | `POST` | `/search` | `query`, `types`, `sort` |

**Headers (all requests):**
```
Authorization: Bearer <ANYTYPE_API_KEY>
Content-Type: application/json
Anytype-Version: 2025-11-08
```

**Rate limits:** 60 burst, then 1/sec. Disable with `ANYTYPE_API_DISABLE_RATE_LIMIT=1`.

---

## §6 — Verification Plan

### 6.1 Automated gates

```bash
./scripts/check.sh
```

All 6 gates must pass. Target: ≥90% coverage (currently 99%).

### 6.2 Specific regression targets

| Test file | What to verify |
|-----------|----------------|
| `test_anytype_client.py` | All CRUD operations, markdown builders, auth |
| `test_anytype_writer.py` | Parent + sub-page creation, state file, error handling |
| `test_anytype_bible.py` | Bible content → markdown conversion |
| `test_anytype_weather.py` | Weather data → markdown conversion |
| `test_anytype_finance.py` | Finance data → markdown table conversion |
| `test_anytype_todoist.py` | Todoist tasks → markdown list conversion |
| `test_anytype_birthdays.py` | Birthday data → markdown conversion |
| `test_bible_reading.py` | UNCHANGED — must still pass |
| `test_weather_fetch.py` | UNCHANGED — must still pass |
| `test_financial_monitor.py` | UNCHANGED — must still pass |

### 6.3 Manual smoke tests

```bash
# Verify Anytype CLI is running
curl http://127.0.0.1:31012/v1/spaces \
  -H "Authorization: Bearer $ANYTYPE_API_KEY" \
  -H "Anytype-Version: 2025-11-08"

# Create a test object
uv run python -c "
from anytype_client import AnytypeClient
c = AnytypeClient(api_key='$ANYTYPE_API_KEY')
spaces = c.list_spaces()
print(spaces)
"

# Run the full writer
uv run python anytype_writer.py
```

### 6.4 Deletion verification

```bash
# These should return NO results:
grep -rn "notion" --include="*.py" . | grep -v .venv | grep -v __pycache__
# These files should NOT exist:
ls notion_*.py 2>&1  # "No such file"
ls tests/test_notion_*.py 2>&1  # "No such file"
```

---

## §7 — Gotchas and Hazards

### 7.1 Anytype API runs on localhost only

The API is bound to `127.0.0.1`. It is NOT accessible over the network. The
cron job on the VPS talks to `127.0.0.1:31012`. This is correct and secure.
Do NOT expose port 31012 via UFW or WireGuard.

### 7.2 Desktop app vs CLI — different default ports

- Desktop app: `http://localhost:31009`
- CLI headless: `http://127.0.0.1:31012`

The implementation must use an env var (`ANYTYPE_API_URL`) to allow either.
Default to `http://127.0.0.1:31012` (CLI).

### 7.3 Anytype has no parent-child page hierarchy via API

Unlike Notion where `create_child_page(parent_id, ...)` creates a nested page,
Anytype objects are flat within a space. To group daily brief sub-pages:
- Use a **naming convention**: `📋 Daily Brief — April 10, 2026` (parent),
  `📖 Bible — April 10, 2026` (child), etc.
- Use the search API to find today's objects by date string in the name
- The writer stores all object IDs in the state file for Phase 2 to consume

### 7.4 `httpx` is already a dependency

The project already uses `httpx` (for `notion_client.py` and other modules).
No new dependency needed for `anytype_client.py`. The `requests` library
shown in Anytype's example code should NOT be used — stick with `httpx` for
consistency.

### 7.5 `fm_config.py` must be updated

`fm_config.py` lines 118-119 currently export:
```python
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DAILY_BRIEFS_DB = os.environ.get("NOTION_DAILY_BRIEFS_DB", "")
```

**Migration strategy (alias-then-delete):**
1. **Phase 0:** Add new aliases below the old lines:
   ```python
   # Anytype migration — aliases for new modules. Remove old NOTION_* after Phase 5.
   ANYTYPE_API_KEY = os.environ.get("ANYTYPE_API_KEY", "")
   ANYTYPE_SPACE_ID = os.environ.get("ANYTYPE_SPACE_ID", "")
   ```
2. **Phase 7:** Remove the old `NOTION_*` lines and the migration comment.

Both `anytype_writer.py` and `anytype_finance.py` import from `fm_config`
using the new names. The old `notion_*` modules continue to import the old
names until they are deleted in Phase 5.

### 7.6 ChatGPT Plus OAuth bridge risks

The ChatGPT Plus OAuth bridge is an unofficial integration. Risks:
- OpenAI could break or restrict the device code flow at any time
- Rate limits may apply beyond the normal ChatGPT Plus usage limits
- The fallback to OpenRouter must be tested and ready

### 7.7 Cleanup: grep for ALL remaining Notion references

After migration, grep the ENTIRE repo:
```bash
grep -rn "notion\|Notion\|NOTION" . --include="*.py" --include="*.md" \
  --include="*.yml" --include="*.toml" | grep -v .venv | grep -v __pycache__ \
  | grep -v .agents
```
Fix ALL remaining references in:
- `fm_config.py` (old NOTION_* aliases — remove in Phase 7)
- `setup-guide.md` (all occurrences — file is at project root, NOT planning_docs/)
- `pyproject.toml` (if any per-file-ignores reference `notion_*`)
- `.github/workflows/ci.yml` (currently has no Notion references)
- `scripts/check.sh` (if any)
- Ignore `.agents/` directory — third-party, not our code

### 7.8 State file format change

The state file at `/tmp/daily_brief_state.json` changes format:

**Before (Notion):**
```json
{
  "parent_page_id": "abc123",
  "sub_pages": {"bible": "def456", "weather": "ghi789"}
}
```

**After (Anytype):**
```json
{
  "space_id": "bafyrei...spaceid",
  "parent_object_id": "bafybei...parentid",
  "sub_objects": {"bible": "bafybei...bibleid", "weather": "bafybei...weatherid"}
}
```

The Phase 2 RISEN prompt must be updated to read the new key names.

---

## §8 — What's NOT Changing

- `bible_reading.py` — data-only, no API dependency
- `weather_fetch.py` — data-only, no API dependency
- `financial_monitor.py` — data-only, no API dependency
- `fm_fetchers.py`, `fm_evaluators.py` — data-only
- `scripts/check.sh` — untouched
- `.github/workflows/ci.yml` — untouched (no Notion references)
- `pyproject.toml` — minimal change (update per-file-ignores if needed)
- Test files for data-only modules — untouched

**Note:** `fm_config.py` IS changing (env var renames). See §7.5.
