"""Build Markdown body for the Todoist sub-object.

Fetches today's and overdue tasks from the Todoist REST API v2 and
transforms them into a Markdown string for the ✅ To-Do List sub-object.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from anytype_client import md_bullet, md_heading, md_paragraph
from fm_config import TODOIST_API_TOKEN

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


def build_todoist_body(tasks: list[dict[str, Any]]) -> str:
    """Build Markdown body for the ✅ To-Do List sub-object.

    Args:
        tasks: Output of ``fetch_todoist_tasks()``.

    Returns:
        Markdown string for the task list body.
    """
    if not tasks:
        return md_paragraph("No tasks scheduled for today. 🎉")

    sections: list[str] = []

    today_tasks = [t for t in tasks if not t.get("is_overdue")]
    overdue_tasks = [t for t in tasks if t.get("is_overdue")]

    # -- Today's Tasks --
    sections.append(md_heading("Today's Tasks", level=2))
    if today_tasks:
        for task in today_tasks:
            sections.append(md_bullet(_format_task(task)))
    else:
        sections.append(md_paragraph("No tasks for today."))

    # -- Overdue --
    if overdue_tasks:
        sections.append(md_heading("Overdue", level=2))
        for task in overdue_tasks:
            sections.append(md_bullet(f"⚠️ {_format_task(task)}"))

    return "\n\n".join(sections)


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
