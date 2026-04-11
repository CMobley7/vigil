# Task List: Notion → Anytype Migration

> **Instructions:** Work through this list top-to-bottom. Mark items `[/]`
> when starting and `[x]` when complete. Run `./scripts/check.sh` after
> every phase. Do NOT skip ahead or delete Notion files until Phase 5.

---

## Phase 0 — Read and Understand

- [x] Read `notion_client.py` (307 lines) — understand the full public API
  surface: `NotionClient`, block builders (`heading_2`, `paragraph`, `table`,
  `callout`, `divider`, `bulleted_list`, `toggle`)
- [x] Read `notion_writer.py` — understand the orchestrator flow: parent page
  creation, sub-page creation order, state file write, subprocess calls
- [x] Read `notion_bible.py` — understand how Bible data maps to Notion blocks
- [x] Read `notion_weather.py` — understand weather data → Notion blocks
- [x] Read `notion_finance.py` — understand finance data → Notion blocks
  (tables, callouts, toggles)
- [x] Read `notion_todoist.py` — understand Todoist tasks → Notion blocks
- [x] Read `notion_birthdays.py` — understand birthday data → Notion blocks
- [x] Read all 7 test files in `tests/` to understand the mocking patterns
  (how `NotionClient` is patched, fixture structure, assertion style)
- [x] Read `setup-guide.md` (project root, NOT planning_docs/) — understand
  the current Notion setup steps (Step 4), ChatGPT integration (Step 10),
  and deployment steps (Step 13c)
- [x] Read `implementation_plan_anytype.md` — fully understand the design
  decisions and file mapping
- [x] **Add Anytype aliases to `fm_config.py`** (lines 118-119). Add these
  lines BELOW the existing NOTION_* lines (do NOT remove the old lines yet):
  ```python
  # Anytype migration — aliases for new modules. Remove old NOTION_* after Phase 5.
  ANYTYPE_API_KEY = os.environ.get("ANYTYPE_API_KEY", "")
  ANYTYPE_SPACE_ID = os.environ.get("ANYTYPE_SPACE_ID", "")
  ```
  This ensures the new `anytype_*` modules can import from `fm_config`
  while the old `notion_*` modules still work until they are deleted.
- [x] Run `./scripts/check.sh` — must pass (both old and new names coexist)

---

## Phase 1 — `anytype_client.py` + Tests

> **Goal:** Replace the API client and block builders. This is the foundation
> that everything else depends on.

### 1.1 Write the test first (TDD Red)

- [x] Create `tests/test_anytype_client.py`
- [x] Test `AnytypeClient.__init__` — verify `httpx.Client` is created with
  correct base URL, headers (`Authorization`, `Anytype-Version`, `Content-Type`)
- [x] Test `AnytypeClient.list_spaces()` — mock `GET /v1/spaces`, verify
  return value and error handling
- [x] Test `AnytypeClient.create_object()` — mock `POST /v1/spaces/{sid}/objects`,
  verify payload shape: `name`, `type_key`, `icon`, `body`
- [x] Test `AnytypeClient.update_object()` — mock `PATCH /v1/spaces/{sid}/objects/{oid}`,
  verify partial update handling (body only, name only, both)
- [x] Test `AnytypeClient.get_object()` — mock `GET /v1/spaces/{sid}/objects/{oid}`
- [x] Test `AnytypeClient.search_objects()` — mock `POST /v1/spaces/{sid}/search`,
  verify query/types/sort payload and pagination params
- [x] Test `AnytypeClient.delete_object()` — mock `DELETE /v1/spaces/{sid}/objects/{oid}`
- [x] Test all Markdown builders: `md_heading`, `md_paragraph`, `md_bullet`,
  `md_callout`, `md_divider`, `md_table`, `md_toggle`
  - `md_heading("Title", level=2)` → `"## Title"`
  - `md_heading("Title", level=3)` → `"### Title"`
  - `md_paragraph("Text")` → `"Text"`
  - `md_bullet("Item")` → `"- Item"`
  - `md_callout("Note", "📝")` → `"> 📝 Note"`
  - `md_divider()` → `"---"`
  - `md_table(["A", "B"], [["1", "2"]])` → formatted Markdown table
  - `md_toggle("Title", "Content")` → `<details>` block
- [x] Test HTTP error handling: `httpx.HTTPStatusError` for 401, 404, 429

### 1.2 Write the implementation (TDD Green)

- [x] Create `anytype_client.py`
- [x] Implement `AnytypeClient` class with all methods
- [x] Implement all `md_*` Markdown builder functions (module-level)
- [x] Ensure all tests pass: `pytest tests/test_anytype_client.py -v`

### 1.3 Refactor and verify

- [x] Run `./scripts/check.sh` — all 6 gates must pass
- [x] Verify no `Any` types in function signatures (except API response dicts)
- [x] Verify Google-style docstrings on all public functions

---

## Phase 2 — `anytype_writer.py` + Tests

> **Goal:** Replace the orchestrator that creates the daily brief. This
> depends on `anytype_client.py` and all domain modules.

### 2.1 Write the test first (TDD Red)

- [x] Create `tests/test_anytype_writer.py`
- [x] Test parent object creation: verify `create_object` called with correct
  name pattern (`📋 Daily Brief — {date}`) and `type_key="page"`
- [x] Test sub-page creation: verify each domain module is called and its
  content is passed to `create_object`
- [x] Test state file write: verify `/tmp/daily_brief_state.json` is written
  with correct structure (`space_id`, `parent_object_id`, `sub_objects`)
- [x] Test error handling: verify graceful failure when Anytype API is down
- [x] Test environment variable loading: `ANYTYPE_API_KEY`, `ANYTYPE_SPACE_ID`,
  `ANYTYPE_API_URL`

### 2.2 Write the implementation (TDD Green)

- [x] Create `anytype_writer.py`
- [x] Implement the orchestrator flow:
  1. Import `ANYTYPE_API_KEY`, `ANYTYPE_SPACE_ID`, `CONTACTS_PATH` from `fm_config`
  2. Create `AnytypeClient` with `ANYTYPE_API_KEY`
  3. Create parent object in space
  4. Create 6 sub-page objects: `morning_bible`, `evening_bible`, `weather`,
     `todoist`, `finance`, `birthdays` (same as current `notion_writer.py`)
  5. Call domain modules to get Markdown strings, pass to `create_object()`
  6. Write state file with keys: `space_id`, `parent_object_id`, `sub_objects`
- [x] Ensure all tests pass: `pytest tests/test_anytype_writer.py -v`

### 2.3 Refactor and verify

- [x] Run `./scripts/check.sh` — all 6 gates must pass

---

## Phase 3 — Domain Module Migration

> **Goal:** Rename and adapt each `notion_*.py` domain module. Each module
> follows the same pattern: change imports, replace block builders with
> Markdown builders.

### 3.1 `anytype_bible.py`

- [x] Create `tests/test_anytype_bible.py` (adapt from `test_notion_bible.py`)
  - Change all `from notion_client import ...` to `from anytype_client import ...`
  - Change all block builder assertions to Markdown string assertions
- [x] Create `anytype_bible.py` (adapt from `notion_bible.py`)
  - Change imports: `from anytype_client import md_heading, md_paragraph, ...`
  - Change `build_morning_devotional_blocks()` to return Markdown string
  - Change `build_evening_reading_blocks()` to return Markdown string
  - Domain module does NOT call the client — returns string only
- [x] Run `pytest tests/test_anytype_bible.py -v`
- [x] Run `./scripts/check.sh`

### 3.2 `anytype_weather.py`

- [x] Create `tests/test_anytype_weather.py` (adapt assertions to Markdown strings)
- [x] Create `anytype_weather.py` (returns Markdown string, not block list)
- [x] Run `pytest tests/test_anytype_weather.py -v`
- [x] Run `./scripts/check.sh`

### 3.3 `anytype_finance.py` (**SPECIAL CASE — also a standalone script**)

> [!IMPORTANT]
> `notion_finance.py` has its own `main()` called by the Phase 2 LLM sweep.
> The `anytype_finance.py` replacement must preserve this standalone pattern.
> See implementation plan §3.4 for full details.

- [x] Create `tests/test_anytype_finance.py`
  - Test `build_finance_body()` returns Markdown string (not block list)
  - Test standalone `main()`: reads state file with `sub_objects` key,
    creates `AnytypeClient`, calls `update_object()`
- [x] Create `anytype_finance.py`
  - `build_finance_blocks()` → `build_finance_body()` (returns Markdown string)
  - `main()` reads state file key `sub_objects` (not `sub_pages`)
  - `main()` imports `ANYTYPE_API_KEY` from `fm_config`
  - `main()` calls `AnytypeClient.update_object()` (not `append_blocks()`)
- [x] Run `pytest tests/test_anytype_finance.py -v`
- [x] Run `./scripts/check.sh`

### 3.4 `anytype_todoist.py`

- [x] Create `tests/test_anytype_todoist.py` (adapt assertions to Markdown strings)
- [x] Create `anytype_todoist.py` (returns Markdown string, not block list)
- [x] Run `pytest tests/test_anytype_todoist.py -v`
- [x] Run `./scripts/check.sh`

### 3.5 `anytype_birthdays.py`

- [x] Create `tests/test_anytype_birthdays.py` (adapt assertions to Markdown strings)
- [x] Create `anytype_birthdays.py` (returns Markdown string, not block list)
- [x] Run `pytest tests/test_anytype_birthdays.py -v`
- [x] Run `./scripts/check.sh`

---

## Phase 4 — Setup Guide Update

> **Goal:** Replace all Notion references in `setup-guide.md` with Anytype
> equivalents. Add style prompt compilation step.
>
> **Note:** `fm_config.py` aliases were already added in Phase 0.
> The old `NOTION_*` lines will be removed in Phase 7.

### 4.1 Anytype CLI setup (replaces Notion integration)

- [x] Rewrite Step 4 in `setup-guide.md` (project root, NOT planning_docs/):
  - Install Anytype desktop app on Mac/iPad/Pixel
  - Create Anytype account (free tier, 1 GB E2EE sync)
  - Create "Daily Briefs" space
  - On VPS: install Anytype CLI via official install script
  - Create bot account: `anytype auth create openclaw-bot`
  - Generate API key: `anytype auth apikey create openclaw-daily-brief`
  - Install as systemd service: `anytype service install && anytype service start`
  - Get space ID via API call
  - Set env vars: `ANYTYPE_API_KEY`, `ANYTYPE_SPACE_ID`

### 4.2 Style prompt compilation (new step)

- [x] Add new step between Steps 3 and 4 (renumber as needed):
  - Compile 10-15 past messages to Chanry → `chanry_style.md`
  - Include variety: morning messages, sweet, funny, supportive
  - Compile 10-15 past messages to friends → `reply_style.md`
  - Include variety: casual texts, substantive replies, group chat
  - Upload to VPS: `scp *.md root@<vps-ip>:/home/openclaw/data/`

### 4.3 LLM model updates

- [x] Update Step 10 (OpenClaw deployment):
  - Add ChatGPT Plus OAuth onboarding: `--auth-choice openai-codex`
  - Document $20/mo subscription as primary LLM source
- [x] Update Step 13c (module deployment):
  - Change all file names from `notion_*` to `anytype_*`
  - Change env vars from `NOTION_*` to `ANYTYPE_*`
- [x] Update Step 15c (RISEN prompts):
  - Replace model references per the model strategy table
  - Add fallback instructions
  - Replace image generation with 9 text prompts
  - Update state file format references

### 4.4 Final pass

- [x] Search for ALL remaining "Notion" / "notion" / "NOTION" references in
  `setup-guide.md` (project root!) — fix every one
- [x] Verify the document flows logically end-to-end

---

## Phase 5 — Delete Notion Files

> **Goal:** Remove all old Notion source and test files. Only do this AFTER
> all Anytype files are created and all tests pass.

- [x] Delete `notion_client.py`
- [x] Delete `notion_writer.py`
- [x] Delete `notion_bible.py`
- [x] Delete `notion_weather.py`
- [x] Delete `notion_finance.py`
- [x] Delete `notion_todoist.py`
- [x] Delete `notion_birthdays.py`
- [x] Delete `tests/test_notion_client.py`
- [x] Delete `tests/test_notion_writer.py`
- [x] Delete `tests/test_notion_bible.py`
- [x] Delete `tests/test_notion_weather.py`
- [x] Delete `tests/test_notion_finance.py`
- [x] Delete `tests/test_notion_todoist.py`
- [x] Delete `tests/test_notion_birthdays.py`
- [x] Run `./scripts/check.sh` — all gates must pass with ONLY Anytype files

---

## Phase 6 — Final Audit

> **Goal:** Verify zero Notion references remain anywhere in the repo.

- [x] Run the full grep audit:
  ```bash
  grep -rn "notion\|Notion\|NOTION" . --include="*.py" --include="*.md" \
    --include="*.yml" --include="*.toml" | grep -v .venv | grep -v __pycache__ \
    | grep -v .agents
  ```
- [x] Fix any remaining references in:
  - `fm_config.py` (old NOTION_* aliases should still exist at this point —
    they will be removed in Phase 7)
  - `setup-guide.md` (project root!)
  - `pyproject.toml` (per-file-ignores, if any)
  - `.github/workflows/ci.yml` (currently has no Notion refs — verify)
  - `scripts/check.sh`
  - Any other file (ignore `.agents/` — third-party, not our code)
- [x] Verify no `notion_*` files exist:
  ```bash
  ls notion_*.py 2>&1
  ls tests/test_notion_*.py 2>&1
  ```
- [x] Verify unchanged test files still pass:
  ```bash
  pytest tests/test_bible_reading.py tests/test_weather_fetch.py \
    tests/test_financial_monitor.py -v
  ```
- [x] Final full gate pass: `./scripts/check.sh` — all 6 gates, 0 failures

---

## Phase 7 — Cleanup and `pyproject.toml`

- [x] **Remove old NOTION_* aliases from `fm_config.py`** — delete the lines:
  ```python
  NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
  NOTION_DAILY_BRIEFS_DB = os.environ.get("NOTION_DAILY_BRIEFS_DB", "")
  ```
  Also remove the migration comment. Only `ANYTYPE_API_KEY` and
  `ANYTYPE_SPACE_ID` should remain.
- [x] Update `pyproject.toml` if any per-file-ignores reference `notion_*` files
- [x] Clean up `__pycache__` directories:
  ```bash
  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  ```
- [x] Final `./scripts/check.sh` run
- [x] Summarize all files modified/created/deleted in a final message
- [x] **STOP** — do NOT commit. Await explicit user approval.

---

## Success Criteria

All of the following must be true:

1. ✅ Zero `notion_*` source or test files exist in the repo
2. ✅ Zero "Notion" / "notion" / "NOTION" references in `.py`, `.md`, `.yml`,
   `.toml` files (excluding `.venv/`, `__pycache__/`, and `.agents/`)
3. ✅ `./scripts/check.sh` passes all 6 gates with 0 failures
4. ✅ Test coverage ≥ 90% (target: maintain current ~99%)
5. ✅ `setup-guide.md` contains no Notion setup steps — only Anytype
6. ✅ All `anytype_*` modules have Google-style docstrings
7. ✅ All `anytype_*` modules use `httpx` (not `requests`)
8. ✅ State file format uses `space_id`, `parent_object_id`, `sub_objects`
9. ✅ No hardcoded Anytype base URL — uses `ANYTYPE_API_URL` env var
10. ✅ No commits made — awaiting user approval
