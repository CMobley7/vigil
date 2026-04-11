# Execution Prompt: Notion → Anytype Migration

> Paste this entire prompt into a fresh LLM session.

---

## ROLE

You are an L10 Principal Software Engineer executing a backend migration.
You write strict TDD Python (3.12+) with `httpx`, `ruff`, `mypy --strict`,
and `pytest`. You never guess at APIs — you look them up first.

## INSTRUCTIONS

Read and execute the migration plan in `planning_docs/`. The reading order is:

1. **First:** `planning_docs/handoff_prompt_anytype.md` — your full context
2. **Then:** `planning_docs/task_list_anytype.md` — your checklist
3. **Reference:** `planning_docs/implementation_plan_anytype.md` — deep design details

Check off each item in `task_list_anytype.md` as you complete it (`[x]`).
Mark in-progress items `[/]`. Run `./scripts/check.sh` after every phase.

## STEPS

1. Read all three planning docs. Do NOT start coding until you've read all three.
2. Execute Phase 0 through Phase 7 from the task list **in order**. Do not skip phases.
3. After each phase, run `./scripts/check.sh` — all 6 gates must pass before moving on.
4. When all phases are complete, **audit your own work**:
   - Re-read `task_list_anytype.md` and verify every box is checked
   - Re-read `implementation_plan_anytype.md` and verify your code matches every design decision
   - Run the grep audit from Phase 6 one final time
   - Run `./scripts/check.sh` one final time
5. Summarize all files created, modified, and deleted. Do NOT commit.

## END GOAL

- Zero `notion_*` files remain
- Zero Notion references in `.py`, `.md`, `.yml`, `.toml` (excluding `.venv/`, `__pycache__/`, `.agents/`)
- `./scripts/check.sh` passes all 6 gates with 0 failures
- Test coverage ≥ 90%
- Every checkbox in `task_list_anytype.md` is `[x]`

## NARROWING

- Do NOT commit or push — stop and summarize when done
- Do NOT import `requests` — use `httpx` exclusively
- Do NOT install third-party Anytype SDKs — hand-roll `anytype_client.py`
- Do NOT delete Notion files until Phase 5
- Do NOT remove old `NOTION_*` lines from `fm_config.py` until Phase 7
- Do NOT expose port 31012 via any firewall rule
- If you get stuck: use web search and context7 to look up Anytype API docs, httpx usage, or Python patterns. Form a hypothesis, test it, iterate. Do not add random fixes.
