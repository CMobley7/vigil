"""Tests for anytype_todoist module."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from vigil.anytype.todoist import build_todoist_body, fetch_todoist_tasks


class TestBuildTodoistBody:
    """Tests for build_todoist_body."""

    def test_returns_string(self) -> None:
        result = build_todoist_body([])
        assert isinstance(result, str)

    def test_empty_tasks(self) -> None:
        result = build_todoist_body([])
        assert "No tasks" in result

    def test_today_tasks_section(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Take medication",
                "priority": 4,
                "due_string": "7:00 AM",
                "due_date": "2026-04-10",
                "is_overdue": False,
            },
        ]
        result = build_todoist_body(tasks)
        assert "Today" in result
        assert "Take medication" in result

    def test_overdue_section(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Submit report",
                "priority": 4,
                "due_string": "Apr 8",
                "due_date": "2026-04-08",
                "is_overdue": True,
            },
        ]
        result = build_todoist_body(tasks)
        assert "Overdue" in result

    def test_priority_labels_in_output(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Urgent task",
                "priority": 4,
                "due_string": "",
                "due_date": "",
                "is_overdue": False,
            },
        ]
        result = build_todoist_body(tasks)
        assert "[P1]" in result

    def test_uses_markdown_bullets(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Do thing",
                "priority": 1,
                "due_string": "",
                "due_date": "",
                "is_overdue": False,
            },
        ]
        result = build_todoist_body(tasks)
        assert "- " in result


class TestFetchTodoistTasks:
    """Tests for fetch_todoist_tasks with mocked API."""

    @patch("vigil.anytype.todoist.TODOIST_API_TOKEN", "")
    def test_empty_token_returns_empty(self) -> None:
        result = fetch_todoist_tasks()
        assert result == []

    @patch("vigil.anytype.todoist.TODOIST_API_TOKEN", "test-token")
    @patch("vigil.anytype.todoist.httpx.get")
    def test_fetches_and_sorts_tasks(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "content": "Low priority",
                "priority": 1,
                "due": {"date": "2026-04-10", "string": "today"},
            },
            {
                "content": "High priority",
                "priority": 4,
                "due": {"date": "2026-04-10", "string": "today"},
            },
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        tasks = fetch_todoist_tasks()
        assert len(tasks) == 2
        assert tasks[0]["content"] == "High priority"
        assert tasks[1]["content"] == "Low priority"

    @patch("vigil.anytype.todoist.TODOIST_API_TOKEN", "test-token")
    @patch("vigil.anytype.todoist.httpx.get")
    def test_today_task_is_not_marked_overdue(self, mock_get: MagicMock) -> None:
        """A non-recurring task due today belongs under today's tasks."""
        today = datetime.now(tz=UTC).date().isoformat()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "content": "Take medication",
                "priority": 4,
                "due": {"date": today, "string": "today"},
            },
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        tasks = fetch_todoist_tasks()

        assert tasks[0]["is_overdue"] is False
