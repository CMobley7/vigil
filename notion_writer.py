"""Orchestrator for deterministic Notion daily brief pages (Phase 1).

Creates the daily brief parent page and all deterministic sub-pages
(Bible, weather, Todoist, finances, birthdays).  Writes a state file
at ``/tmp/daily_brief_state.json`` for the Phase 2 LLM sweep.

Usage::

    python3 notion_writer.py
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bible_reading import extract_today_reading
from fm_config import (
    CONTACTS_PATH,
    NOTION_DAILY_BRIEFS_DB,
    NOTION_TOKEN,
)
from notion_bible import build_evening_reading_blocks, build_morning_devotional_blocks
from notion_birthdays import build_birthday_blocks, check_birthdays_today
from notion_client import NotionClient
from notion_todoist import build_todoist_blocks, fetch_todoist_tasks
from notion_weather import build_weather_blocks
from weather_fetch import fetch_weather

logger = logging.getLogger(__name__)

_STATE_FILE = Path("/tmp/daily_brief_state.json")  # noqa: S108 — intentional handoff path for Phase 2 LLM
_FM_CACHE_FILE = Path("/tmp/daily_brief_fm_output.json")  # noqa: S108 — cache for Phase 2


def main() -> None:
    """Create the daily brief parent page and sub-pages."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set -- aborting")
        sys.exit(1)
    if not NOTION_DAILY_BRIEFS_DB:
        logger.error("NOTION_DAILY_BRIEFS_DB not set -- aborting")
        sys.exit(1)

    client = NotionClient(NOTION_TOKEN)

    # 1. Create parent page in Daily Briefs database
    today = datetime.now(tz=UTC).strftime("%A, %B %-d, %Y")
    parent_id = client.create_page(NOTION_DAILY_BRIEFS_DB, today, "📋")

    sub_pages: dict[str, str | None] = {
        "morning_bible": None,
        "evening_bible": None,
        "weather": None,
        "todoist": None,
        "finance": None,
        "birthdays": None,
    }

    # 2. Bible reading (two sub-pages)
    try:
        reading = extract_today_reading()
        morning_id = client.create_child_page(
            parent_id, "📖 Morning Bible Reading", "📖"
        )
        client.append_blocks(morning_id, build_morning_devotional_blocks(reading))
        sub_pages["morning_bible"] = morning_id
        evening_id = client.create_child_page(
            parent_id, "🌙 Evening Bible Reading", "🌙"
        )
        client.append_blocks(evening_id, build_evening_reading_blocks(reading))
        sub_pages["evening_bible"] = evening_id
    except Exception as exc:
        logger.warning("Bible reading failed: %s", exc)

    # 3. Weather
    try:
        weather = fetch_weather()
        weather_id = client.create_child_page(parent_id, "🌤️ Weather", "🌤️")
        client.append_blocks(weather_id, build_weather_blocks(weather))
        sub_pages["weather"] = weather_id
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)

    # 4. Todoist
    try:
        tasks = fetch_todoist_tasks()
        todo_id = client.create_child_page(parent_id, "✅ To-Do List", "✅")
        client.append_blocks(todo_id, build_todoist_blocks(tasks))
        sub_pages["todoist"] = todo_id
    except Exception as exc:
        logger.warning("Todoist fetch failed: %s", exc)

    # 5. Financial data — run financial_monitor.py and cache output for Phase 2.
    #    Create an empty sub-page; Phase 2 LLM appends editorial first, then
    #    triggers notion_finance.py to append data tables below it.
    try:
        fm_raw = subprocess.check_output(
            [sys.executable, "financial_monitor.py"],
            text=True,
        )
        _FM_CACHE_FILE.write_text(fm_raw)
        finance_id = client.create_child_page(parent_id, "📈 Stocks & Finances", "📈")
        sub_pages["finance"] = finance_id
    except Exception as exc:
        logger.warning("Financial monitor failed: %s", exc)

    # 6. Birthdays (skip sub-page if none)
    try:
        birthdays = check_birthdays_today(CONTACTS_PATH)
        if birthdays:
            bday_id = client.create_child_page(parent_id, "🎂 Birthdays", "🎂")
            client.append_blocks(bday_id, build_birthday_blocks(birthdays))
            sub_pages["birthdays"] = bday_id
    except Exception as exc:
        logger.warning("Birthday check failed: %s", exc)

    # 7. Write state file for Phase 2 (LLM sweep) handoff
    state: dict[str, Any] = {
        "date": today,
        "parent_page_id": parent_id,
        "sub_pages": sub_pages,
    }
    _STATE_FILE.write_text(json.dumps(state, indent=2))
    print(json.dumps(state, indent=2))  # noqa: T201 — stdout for cron logging


if __name__ == "__main__":  # pragma: no cover
    main()
