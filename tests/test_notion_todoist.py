"""Tests for notion_todoist module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from notion_todoist import build_todoist_blocks, fetch_todoist_tasks


class TestBuildTodoistBlocks:
    """Tests for build_todoist_blocks."""

    def test_empty_tasks(self) -> None:
        blocks = build_todoist_blocks([])
        assert len(blocks) == 1
        content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "No tasks" in content

    def test_today_tasks_section(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Take medication",
                "priority": 4,
                "due_string": "7:00 AM",
                "due_date": "2026-03-10",
                "is_overdue": False,
            },
        ]
        blocks = build_todoist_blocks(tasks)
        heading = blocks[0]
        assert heading["type"] == "heading_2"
        text = heading["heading_2"]["rich_text"][0]["text"]["content"]
        assert "Today" in text

    def test_overdue_section(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Submit report",
                "priority": 4,
                "due_string": "Mar 8",
                "due_date": "2026-03-08",
                "is_overdue": True,
            },
        ]
        blocks = build_todoist_blocks(tasks)
        headings = [b for b in blocks if b["type"] == "heading_2"]
        titles = [h["heading_2"]["rich_text"][0]["text"]["content"] for h in headings]
        assert "Overdue" in titles

    def test_priority_labels(self) -> None:
        tasks: list[dict[str, Any]] = [
            {
                "content": "Urgent task",
                "priority": 4,
                "due_string": "",
                "due_date": "",
                "is_overdue": False,
            },
        ]
        blocks = build_todoist_blocks(tasks)
        bullets = [b for b in blocks if b["type"] == "bulleted_list_item"]
        text = bullets[0]["bulleted_list_item"]["rich_text"][0]
        assert "[P1]" in text["text"]["content"]


class TestFetchTodoistTasks:
    """Tests for fetch_todoist_tasks with mocked API."""

    @patch("notion_todoist.TODOIST_API_TOKEN", "")
    def test_empty_token_returns_empty(self) -> None:
        result = fetch_todoist_tasks()
        assert result == []

    @patch("notion_todoist.TODOIST_API_TOKEN", "test-token")
    @patch("notion_todoist.httpx.get")
    def test_fetches_and_sorts_tasks(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "content": "Low priority",
                "priority": 1,
                "due": {"date": "2026-03-10", "string": "today"},
            },
            {
                "content": "High priority",
                "priority": 4,
                "due": {"date": "2026-03-10", "string": "today"},
            },
        ]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        tasks = fetch_todoist_tasks()
        assert len(tasks) == 2
        # High priority should come first
        assert tasks[0]["content"] == "High priority"
        assert tasks[1]["content"] == "Low priority"
