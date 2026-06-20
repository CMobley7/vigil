"""Orchestrator for deterministic Anytype daily brief objects (Phase 1).

Creates the daily brief parent object and all deterministic sub-objects
(Bible, weather, Todoist, finances, birthdays) in the configured Anytype
space.  Writes private state/cache files under ``VIGIL_RUNTIME_DIR`` for the
Phase 2 LLM sweep.

Usage::

    vigil brief
    python -m vigil.anytype.writer
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any

from vigil.anytype.bible import (
    build_evening_reading_body,
    build_morning_devotional_body,
)
from vigil.anytype.birthdays import build_birthday_body, check_birthdays_today
from vigil.anytype.client import AnytypeClient
from vigil.anytype.todoist import build_todoist_body, fetch_todoist_tasks
from vigil.anytype.weather import build_weather_body
from vigil.bible import extract_today_reading
from vigil.clock import local_display_date
from vigil.config import (
    ANYTYPE_API_KEY,
    ANYTYPE_SPACE_ID,
    CONTACTS_PATH,
)
from vigil.runtime import FM_CACHE_FILE, STATE_FILE, write_private_text
from vigil.weather import fetch_weather

logger = logging.getLogger(__name__)

_STATE_FILE = STATE_FILE
_FM_CACHE_FILE = FM_CACHE_FILE


def main() -> None:
    """Create the daily brief parent object and sub-objects in Anytype."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not ANYTYPE_API_KEY:
        logger.error("ANYTYPE_API_KEY not set -- aborting")
        sys.exit(1)
    if not ANYTYPE_SPACE_ID:
        logger.error("ANYTYPE_SPACE_ID not set -- aborting")
        sys.exit(1)

    client = AnytypeClient(ANYTYPE_API_KEY)

    # 1. Create parent object in the Daily Briefs space
    today = local_display_date()
    parent_id = client.create_object(
        space_id=ANYTYPE_SPACE_ID,
        name=f"📋 Daily Brief — {today}",
        icon="📋",
        body="",
        type_key="page",
    )

    sub_objects: dict[str, str | None] = {
        "morning_bible": None,
        "evening_bible": None,
        "weather": None,
        "todoist": None,
        "finance": None,
        "birthdays": None,
    }

    # 2. Bible reading (two sub-objects)
    try:
        reading = extract_today_reading()
        morning_body = build_morning_devotional_body(reading)
        morning_id = client.create_object(
            space_id=ANYTYPE_SPACE_ID,
            name=f"📖 Bible — Morning — {today}",
            icon="📖",
            body=morning_body,
            type_key="page",
        )
        sub_objects["morning_bible"] = morning_id

        evening_body = build_evening_reading_body(reading)
        evening_id = client.create_object(
            space_id=ANYTYPE_SPACE_ID,
            name=f"🌙 Bible — Evening — {today}",
            icon="🌙",
            body=evening_body,
            type_key="page",
        )
        sub_objects["evening_bible"] = evening_id
    except Exception as exc:
        logger.warning("Bible reading failed: %s", exc, exc_info=True)

    # 3. Weather
    try:
        weather = fetch_weather()
        weather_body = build_weather_body(weather)
        weather_id = client.create_object(
            space_id=ANYTYPE_SPACE_ID,
            name=f"🌤️ Weather — {today}",
            icon="🌤️",
            body=weather_body,
            type_key="page",
        )
        sub_objects["weather"] = weather_id
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc, exc_info=True)

    # 4. Todoist
    try:
        tasks = fetch_todoist_tasks()
        todoist_body = build_todoist_body(tasks)
        todo_id = client.create_object(
            space_id=ANYTYPE_SPACE_ID,
            name=f"✅ To-Do List — {today}",
            icon="✅",
            body=todoist_body,
            type_key="page",
        )
        sub_objects["todoist"] = todo_id
    except Exception as exc:
        logger.warning("Todoist fetch failed: %s", exc, exc_info=True)

    # 5. Financial data — run vigil.financial.monitor and cache output for Phase 2.
    #    Create an empty finance object; Phase 2 LLM adds editorial, then triggers
    #    anytype_finance (vigil.anytype.finance) to update the body with data tables.
    try:
        fm_raw = subprocess.check_output(
            [sys.executable, "-m", "vigil.financial.monitor"],
            text=True,
            timeout=120,
        )
        write_private_text(_FM_CACHE_FILE, fm_raw)
        finance_id = client.create_object(
            space_id=ANYTYPE_SPACE_ID,
            name=f"📈 Stocks & Finances — {today}",
            icon="📈",
            body="",
            type_key="page",
        )
        sub_objects["finance"] = finance_id
    except Exception as exc:
        logger.warning("Financial monitor failed: %s", exc, exc_info=True)

    # 6. Birthdays (skip sub-object if none today)
    try:
        birthdays = check_birthdays_today(CONTACTS_PATH)
        if birthdays:
            bday_body = build_birthday_body(birthdays)
            bday_id = client.create_object(
                space_id=ANYTYPE_SPACE_ID,
                name=f"🎂 Birthdays — {today}",
                icon="🎂",
                body=bday_body,
                type_key="page",
            )
            sub_objects["birthdays"] = bday_id
    except Exception as exc:
        logger.warning("Birthday check failed: %s", exc, exc_info=True)

    # 7. Write state file for Phase 2 (LLM sweep) handoff
    state: dict[str, Any] = {
        "date": today,
        "space_id": ANYTYPE_SPACE_ID,
        "parent_object_id": parent_id,
        "sub_objects": sub_objects,
    }
    write_private_text(_STATE_FILE, json.dumps(state, indent=2))
    print(json.dumps(state, indent=2))  # stdout for cron logging


if __name__ == "__main__":  # pragma: no cover
    main()
