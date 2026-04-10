"""Build Notion blocks for the Todoist sub-page.

Fetches today's and overdue tasks from the Todoist REST API v2 and
transforms them into Notion block dicts for the ✅ To-Do List sub-page.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from fm_config import TODOIST_API_TOKEN
from notion_client import bulleted_list, heading_2, paragraph

logger = logging.getLogger(__name__)

_TODOIST_API_URL = "https://api.todoist.com/rest/v2/tasks"


# Todoist priority 4 = P1 (urgent), 1 = P4 (no priority)
_PRIORITY_MAP: dict[int, str] = {4: "P1", 3: "P2", 2: "P3", 1: "P4"}


def fetch_todoist_tasks() -> list[dict[str, Any]]:
    """Fetch today's and overdue tasks from Todoist.

    Returns:
        List of task dicts with keys: content, priority, due_string, is_overdue.

    Raises:
        httpx.HTTPStatusError: On Todoist API errors.
    """
    if not TODOIST_API_TOKEN:
        logger.warning("TODOIST_API_TOKEN not set — skipping Todoist fetch")
        return []

    headers = {"Authorization": f"Bearer {TODOIST_API_TOKEN}"}

    resp = httpx.get(
        _TODOIST_API_URL,
        headers=headers,
        params={"filter": "today | overdue"},
        timeout=15,
    )
    resp.raise_for_status()

    tasks_raw: list[dict[str, Any]] = resp.json()
    tasks: list[dict[str, Any]] = []

    for task in tasks_raw:
        due = task.get("due") or {}
        due_date = due.get("date", "")
        due_string = due.get("string", "")
        is_overdue = due.get("is_recurring", False) is False and bool(due_date)

        tasks.append(
            {
                "content": task.get("content", ""),
                "priority": task.get("priority", 1),
                "due_string": due_string,
                "due_date": due_date,
                "is_overdue": is_overdue,
            }
        )

    # Sort by priority descending (4=P1 first), then by content
    tasks.sort(key=lambda t: (-t["priority"], t["content"]))
    return tasks


def build_todoist_blocks(
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build Notion blocks for the ✅ To-Do List sub-page.

    Args:
        tasks: Output of ``fetch_todoist_tasks()``.

    Returns:
        List of Notion block dicts.
    """
    if not tasks:
        return [paragraph("No tasks scheduled for today. 🎉")]

    blocks: list[dict[str, Any]] = []

    # Split into today's tasks and overdue
    today_tasks = [t for t in tasks if not t.get("is_overdue")]
    overdue_tasks = [t for t in tasks if t.get("is_overdue")]

    # -- Today's Tasks --
    blocks.append(heading_2("Today's Tasks"))
    if today_tasks:
        for task in today_tasks:
            label = _format_task(task)
            blocks.append(bulleted_list(label))
    else:
        blocks.append(paragraph("No tasks for today."))

    # -- Overdue --
    if overdue_tasks:
        blocks.append(heading_2("Overdue"))
        for task in overdue_tasks:
            label = f"⚠️ {_format_task(task)}"
            blocks.append(bulleted_list(label))

    return blocks


def _format_task(task: dict[str, Any]) -> str:
    """Format a single task as a readable string.

    Args:
        task: Task dict from ``fetch_todoist_tasks()``.
    """
    priority = _PRIORITY_MAP.get(task.get("priority", 1), "P4")
    content = task.get("content", "")
    due = task.get("due_string", "")
    label = f"[{priority}] {content}"
    if due:
        label += f" — {due}"
    return label
