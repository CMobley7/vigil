# Handoff Prompt: Notion → Anytype Migration

> **Purpose:** This prompt gives a fresh LLM agent all the context needed to
> execute the Anytype migration without re-reading the entire codebase or
> conversation history. Read this FIRST, then the `task_list_anytype.md`,
> then the `implementation_plan_anytype.md`.

---

## Who You Are

You are an L10 Principal Software Engineer executing a backend migration for
the **OpenClaw** project. You are replacing the Notion API backend with the
Anytype API. You will:

1. Rename all `notion_*` source and test files to `anytype_*`
2. Rewrite `anytype_client.py` (the API wrapper) and `anytype_writer.py`
   (the orchestrator) from scratch
3. Adapt the 5 domain modules to use Markdown builders instead of Notion blocks
4. Update the setup guide to replace all Notion references with Anytype
5. Delete all old `notion_*` files after the migration is complete

You are working with Python 3.12+ and using `httpx` for HTTP, `ruff` for
linting/formatting, `mypy` for type-checking, and `pytest` for testing.

---

## Project Location and Structure

```
/home/cmobley/Documents/Projects/Reports/openclaw/
├── anytype_client.py         ← NEW: Anytype API client + Markdown builders
├── anytype_writer.py         ← NEW: Daily brief orchestrator
├── anytype_bible.py          ← NEW: Replaces notion_bible.py
├── anytype_weather.py        ← NEW: Replaces notion_weather.py
├── anytype_finance.py        ← NEW: Replaces notion_finance.py (also standalone script)
├── anytype_todoist.py        ← NEW: Replaces notion_todoist.py
├── anytype_birthdays.py      ← NEW: Replaces notion_birthdays.py
├── bible_reading.py          ← UNCHANGED (data-fetching only)
├── weather_fetch.py          ← UNCHANGED (data-fetching only)
├── financial_monitor.py      ← UNCHANGED (data-fetching only)
├── fm_config.py              ← MODIFY: Rename NOTION_* env vars to ANYTYPE_*
├── fm_fetchers.py            ← UNCHANGED
├── fm_evaluators.py          ← UNCHANGED
├── pyproject.toml
├── setup-guide.md            ← UPDATE: Replace Notion with Anytype (project root!)
├── scripts/check.sh          ← Local quality gate (6 gates)
├── planning_docs/
│   ├── implementation_plan_anytype.md  ← READ THIS
│   └── task_list_anytype.md  ← YOUR CHECKLIST
├── tests/
│   ├── test_anytype_client.py    ← NEW
│   ├── test_anytype_writer.py    ← NEW
│   ├── test_anytype_bible.py     ← NEW
│   ├── test_anytype_weather.py   ← NEW
│   ├── test_anytype_finance.py   ← NEW
│   ├── test_anytype_todoist.py   ← NEW
│   ├── test_anytype_birthdays.py ← NEW
│   ├── test_bible_reading.py     ← UNCHANGED
│   ├── test_weather_fetch.py     ← UNCHANGED
│   └── test_financial_monitor.py ← UNCHANGED
└── .github/workflows/ci.yml     ← No Notion references (unchanged)
```

> [!IMPORTANT]
> `setup-guide.md` is at the **project root**, NOT inside `planning_docs/`.
> There is NO `tests/conftest.py` in this project.

---

## Critical Context

### 1. Anytype API — How It Works

The Anytype API is a **local-only REST API** served by the Anytype CLI
(`anytype serve`) or the desktop app. It runs on `http://127.0.0.1:31012`
(CLI) or `http://localhost:31009` (desktop app).

**Authentication:**
```
Authorization: Bearer <ANYTYPE_API_KEY>
Content-Type: application/json
Anytype-Version: 2025-11-08
```

**Object creation:**
```bash
curl -X POST 'http://127.0.0.1:31012/v1/spaces/<SPACE_ID>/objects' \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Anytype-Version: 2025-11-08" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "📋 Daily Brief — April 10, 2026",
    "type_key": "page",
    "icon": {"emoji": "📋", "format": "emoji"},
    "body": "## Section 1\n\nContent here..."
  }'
```

**Object update:**
```bash
curl -X PATCH 'http://127.0.0.1:31012/v1/spaces/<SPACE_ID>/objects/<OBJ_ID>' \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Anytype-Version: 2025-11-08" \
  -H "Content-Type: application/json" \
  -d '{"body": "Updated Markdown content"}'
```

**Search:**
```bash
curl -X POST 'http://127.0.0.1:31012/v1/spaces/<SPACE_ID>/search?offset=0&limit=10' \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Anytype-Version: 2025-11-08" \
  -H "Content-Type: application/json" \
  -d '{"query": "Daily Brief", "types": ["page"]}'
```

**Rate limits:** 60 burst, then 1/sec. Plenty for our ~10 calls per sweep.

### 2. Key Concept: Notion Blocks → Markdown Body

This is the **most important conceptual change**.

**Notion (old):** Content is built as a list of block dicts, then appended:
```python
blocks = [heading_2("Title"), paragraph("Text"), table(...)]
client.append_blocks(page_id, blocks)
```

**Anytype (new):** Content is a single Markdown string in the `body` field:
```python
body = "\n\n".join([md_heading("Title"), md_paragraph("Text"), md_table(...)])
client.create_object(space_id, name, icon, body=body)
```

The Markdown builders are trivial string-returning functions:
```python
def md_heading(text: str, level: int = 2) -> str:
    return f"{'#' * level} {text}"

def md_paragraph(text: str) -> str:
    return text

def md_bullet(text: str) -> str:
    return f"- {text}"

def md_divider() -> str:
    return "---"

def md_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    data_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *data_lines])

def md_callout(text: str, icon: str = "📝") -> str:
    return f"> {icon} {text}"

def md_toggle(title: str, content: str) -> str:
    # Anytype renders <details> as toggles
    return f"<details>\n<summary>{title}</summary>\n\n{content}\n</details>"
```

### 3. No Parent-Child Hierarchy in Anytype

Anytype objects are **flat within a space**. There is no
`create_child_page(parent_id, ...)` equivalent. Instead:

- Use a **naming convention** to group objects by date:
  - Parent: `📋 Daily Brief — April 10, 2026`
  - Sub-pages: `📖 Bible — April 10, 2026`, `🌤 Weather — April 10, 2026`, etc.
- The writer creates 6 sub-page objects: `morning_bible`, `evening_bible`,
  `weather`, `todoist`, `finance`, `birthdays`
- The state file at `/tmp/daily_brief_state.json` stores all object IDs
- The search API finds today's objects by date query

### 4. `fm_config.py` — Alias-Then-Delete Strategy

`fm_config.py` (lines 118-119) currently exports:
```python
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DAILY_BRIEFS_DB = os.environ.get("NOTION_DAILY_BRIEFS_DB", "")
```

**In Phase 0**, add new aliases BELOW the old lines (keep old lines intact):
```python
# Anytype migration — aliases for new modules. Remove old NOTION_* after Phase 5.
ANYTYPE_API_KEY = os.environ.get("ANYTYPE_API_KEY", "")
ANYTYPE_SPACE_ID = os.environ.get("ANYTYPE_SPACE_ID", "")
```

**In Phase 7**, remove the old `NOTION_*` lines.

This avoids breaking old `notion_*` modules during the transition. Both
`anytype_writer.py` and `anytype_finance.py` import from `fm_config`.

### 5. Environment Variables

Old (Notion):
```
NOTION_TOKEN=secret_xxx
NOTION_DAILY_BRIEFS_DB=abc123
```

New (Anytype):
```
ANYTYPE_API_KEY=zhSG/zQRmgAD...       # loaded via fm_config.py
ANYTYPE_SPACE_ID=bafyrei...spaceid     # loaded via fm_config.py
ANYTYPE_API_URL=http://127.0.0.1:31012 # optional, loaded by AnytypeClient from os.environ (NOT fm_config)
```

### 6. LLM Model Strategy

| Task | Primary (ChatGPT Plus OAuth) | Fallback (OpenRouter, reasoning on) |
|------|-----|---------|
| General summarization | GPT-5.4 | Gemini 3.1 Pro |
| Chanry's messages | GPT-5.4 + special prompt | Claude Opus 4.6 |
| General replies | GPT-5.4 + special prompt | Claude Sonnet 4.6 |
| Image generation | 9 text prompts (no API gen) | N/A |

All fallback OpenRouter models should have reasoning enabled.

### 7. Reply Style Prompts

You do NOT need to create the style prompt content — the user will populate
`chanry_style.md` and `reply_style.md` with their own message history. The
setup guide must include clear instructions for:
1. What kind of messages to include (variety of tones, lengths, contexts)
2. Where to save the files on the VPS (`/home/openclaw/data/`)
3. How these files are referenced by the RISEN prompts

### 8. Image Prompts — Text Only

The LLM generates 3 message variations for Chanry. For each, it writes 3
detailed image prompts = 9 total. These are **text descriptions, not API
calls**. The user generates the image manually using ChatGPT Plus DALL-E or
any free tool.

Example output in the daily brief:
```markdown
### 🎨 Image Prompt 1 — Sunrise at the Lake
A serene lakeside sunrise with soft pink and gold clouds reflecting on
still water. Two small silhouetted figures sitting on the dock, one
leaning on the other. Style: dreamy watercolor, pastel palette.
```

### 9. Reply Tracking (Strikethrough)

When a reply is sent:
1. Search for today's daily brief objects
2. GET the relevant sub-page object
3. Parse the Markdown body
4. Wrap the drafted reply in `~~strikethrough~~`
5. Append the actual sent text below
6. PATCH the object body

### 10. `notion_finance.py` is a Standalone Script (Special Case)

`notion_finance.py` has its own `main()` called by the Phase 2 LLM sweep
(`python3 notion_finance.py`). It reads the state file, creates its own
`NotionClient`, and appends finance data blocks. The `anytype_finance.py`
replacement must:
1. Read the new state file format: `state["sub_objects"]["finance"]`
2. Create its own `AnytypeClient(ANYTYPE_API_KEY)` (imported from `fm_config`)
3. Update the finance object body via `client.update_object()`

### 11. Domain Module Interaction Pattern

Domain modules (bible, weather, todoist, birthdays) are **pure functions**:
- They accept data and return a **Markdown string** (NOT a block list)
- They do NOT instantiate clients or call any API
- The writer calls `create_object(space_id, name, icon, body=md_string)`

**Exception:** `anytype_finance.py` is also callable standalone (see §10).

### 12. Existing Patterns to Follow

- **TDD:** Red → Green → Refactor. Write tests first.
- **httpx, not requests:** The project uses `httpx.Client`. The Anytype
  example code uses `requests`. Do NOT import requests — use httpx.
- **Google-style docstrings:** All public functions need them.
- **Type strictness:** `mypy --strict` must pass. No `Any` in signatures
  unless absolutely required by the API response shape.
- **Coverage:** Target ≥90%. Current is 99%.

### 13. Quality Gates

Run after EVERY logical chunk of work:
```bash
./scripts/check.sh
```

This runs:
1. `ruff check` (lint)
2. `ruff check --extend-select RUF100` (stale noqa)
3. `ruff format --check` (formatting)
4. `mypy .` (type check)
5. `pytest --cov` (tests + coverage)
6. `pip-audit` (security)

**All 6 gates must pass before moving to the next task.**

---

## Execution Order

Follow the `task_list_anytype.md` checklist strictly. The order is:

1. **Phase 0:** Read existing Notion source files + add `fm_config.py` aliases
2. **Phase 1:** Create `anytype_client.py` + tests (the foundation)
3. **Phase 2:** Create `anytype_writer.py` + tests (the orchestrator)
4. **Phase 3:** Migrate domain modules (`anytype_bible.py`, etc.) + tests
5. **Phase 4:** Update `setup-guide.md` (Anytype CLI, env vars, style prompts)
6. **Phase 5:** Delete all `notion_*` files
7. **Phase 6:** Final grep audit + full gate pass
8. **Phase 7:** Remove old `NOTION_*` from `fm_config.py`, update `pyproject.toml`

**DO NOT skip phases. DO NOT delete Notion files until Phase 5.**
**DO NOT remove old NOTION_* lines from fm_config.py until Phase 7.**

---

## Hazards to Avoid

1. **Do NOT import `requests`.** Use `httpx.Client`. The project does not
   have `requests` as a dependency.
2. **Do NOT expose port 31012** via UFW or any firewall rule. The API is
   localhost-only and that is correct.
3. **Do NOT hardcode the base URL.** Use `ANYTYPE_API_URL` env var with
   a default of `http://127.0.0.1:31012`.
4. **Do NOT create parent-child page relationships.** Anytype objects are
   flat. Use naming conventions.
5. **Do NOT use `Any` in type annotations** unless the variable is
   genuinely opaque JSON from the API response.
6. **Do NOT use the `notion-client` Python package.** It doesn't exist in this
   project's dependencies — the current `notion_client.py` is a hand-rolled
   wrapper. Same pattern applies for Anytype: hand-roll `anytype_client.py`.
7. **Do NOT create or use a third-party Anytype Python SDK**
   (e.g., `charlesneimog-anytype-client`). We keep the wrapper thin and local.
