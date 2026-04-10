"""Tests for notion_writer orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from notion_writer import _FM_CACHE_FILE, _STATE_FILE, main


def _mock_client() -> MagicMock:
    """Return a mock NotionClient."""
    client = MagicMock()
    client.create_page.return_value = "parent-page-id"
    client.create_child_page.side_effect = lambda _p, title, _i: f"id-{title}"
    client.append_blocks.return_value = None
    return client


class TestMain:
    """Tests for the main orchestrator."""

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch("notion_writer.extract_today_reading")
    @patch("notion_writer.fetch_weather")
    @patch("notion_writer.fetch_todoist_tasks")
    @patch("notion_writer.check_birthdays_today")
    @patch("notion_writer.subprocess.check_output")
    def test_creates_state_file(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify state file is written with all sub-page IDs."""
        client = _mock_client()
        mock_client_cls.return_value = client

        mock_bible.return_value = {
            "morning_devotional": {"day": "Day 1", "text": "Text"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "In the beginning",
                "study_notes": {},
            },
        }
        mock_weather.return_value = {
            "today_hourly": [],
            "ten_day_forecast": [],
        }
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        # Redirect state file to tmp
        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(
                type(_STATE_FILE),
                "write_text",
                state_path.write_text,
            ),
            patch.object(
                type(_FM_CACHE_FILE),
                "write_text",
                fm_path.write_text,
            ),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert "parent_page_id" in state
        assert state["parent_page_id"] == "parent-page-id"
        assert "sub_pages" in state

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch("notion_writer.extract_today_reading")
    @patch("notion_writer.fetch_weather")
    @patch("notion_writer.fetch_todoist_tasks")
    @patch("notion_writer.check_birthdays_today")
    @patch("notion_writer.subprocess.check_output")
    def test_fault_tolerance(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify one module failing doesn't block others."""
        client = _mock_client()
        mock_client_cls.return_value = client

        # Bible fails
        mock_bible.side_effect = RuntimeError("Bible file missing")
        # Weather succeeds
        mock_weather.return_value = {
            "today_hourly": [],
            "ten_day_forecast": [],
        }
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(
                type(_STATE_FILE),
                "write_text",
                state_path.write_text,
            ),
            patch.object(
                type(_FM_CACHE_FILE),
                "write_text",
                fm_path.write_text,
            ),
        ):
            main()

        state = json.loads(state_path.read_text())
        # Bible should be None (failed), weather should have an ID
        assert state["sub_pages"]["morning_bible"] is None
        assert state["sub_pages"]["evening_bible"] is None
        assert state["sub_pages"]["weather"] is not None

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch("notion_writer.extract_today_reading")
    @patch("notion_writer.fetch_weather")
    @patch("notion_writer.fetch_todoist_tasks")
    @patch("notion_writer.check_birthdays_today")
    @patch("notion_writer.subprocess.check_output")
    def test_no_birthdays_skips_subpage(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify birthdays sub-page is skipped when empty."""
        client = _mock_client()
        mock_client_cls.return_value = client

        mock_bible.return_value = {
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        }
        mock_weather.return_value = {
            "today_hourly": [],
            "ten_day_forecast": [],
        }
        mock_todoist.return_value = []
        mock_birthdays.return_value = []  # No birthdays
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(
                type(_STATE_FILE),
                "write_text",
                state_path.write_text,
            ),
            patch.object(
                type(_FM_CACHE_FILE),
                "write_text",
                fm_path.write_text,
            ),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_pages"]["birthdays"] is None

    @patch("notion_writer.NOTION_TOKEN", "")
    def test_exits_without_token(self) -> None:
        """Verify script exits if NOTION_TOKEN is empty."""
        with pytest.raises(SystemExit):
            main()

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    def test_exits_without_db_id(self) -> None:
        """Verify script exits if NOTION_DAILY_BRIEFS_DB is empty."""
        with pytest.raises(SystemExit):
            main()

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch(
        "notion_writer.extract_today_reading",
        return_value={
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        },
    )
    @patch("notion_writer.fetch_weather", side_effect=RuntimeError("API down"))
    @patch("notion_writer.fetch_todoist_tasks", return_value=[])
    @patch("notion_writer.check_birthdays_today", return_value=[])
    @patch(
        "notion_writer.subprocess.check_output",
        return_value=json.dumps({"brokerage_data": {}, "bank_data": {}}),
    )
    def test_weather_failure_degrades(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Weather failure leaves weather sub-page as None."""
        client = _mock_client()
        mock_client_cls.return_value = client

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"
        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_pages"]["weather"] is None
        assert state["sub_pages"]["morning_bible"] is not None

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch(
        "notion_writer.extract_today_reading",
        return_value={
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        },
    )
    @patch(
        "notion_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch(
        "notion_writer.fetch_todoist_tasks",
        side_effect=RuntimeError("Todoist down"),
    )
    @patch("notion_writer.check_birthdays_today", return_value=[])
    @patch(
        "notion_writer.subprocess.check_output",
        return_value=json.dumps({"brokerage_data": {}, "bank_data": {}}),
    )
    def test_todoist_failure_degrades(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Todoist failure leaves todoist sub-page as None."""
        client = _mock_client()
        mock_client_cls.return_value = client

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"
        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_pages"]["todoist"] is None
        assert state["sub_pages"]["weather"] is not None

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch(
        "notion_writer.extract_today_reading",
        return_value={
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        },
    )
    @patch(
        "notion_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch("notion_writer.fetch_todoist_tasks", return_value=[])
    @patch("notion_writer.check_birthdays_today", return_value=[])
    @patch(
        "notion_writer.subprocess.check_output",
        side_effect=RuntimeError("FM failed"),
    )
    def test_finance_failure_degrades(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Finance subprocess failure leaves finance sub-page as None."""
        client = _mock_client()
        mock_client_cls.return_value = client

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"
        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_pages"]["finance"] is None
        assert state["sub_pages"]["todoist"] is not None

    @patch("notion_writer.NOTION_DAILY_BRIEFS_DB", "db-id")
    @patch("notion_writer.NOTION_TOKEN", "test-token")
    @patch("notion_writer.NotionClient")
    @patch(
        "notion_writer.extract_today_reading",
        return_value={
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        },
    )
    @patch(
        "notion_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch("notion_writer.fetch_todoist_tasks", return_value=[])
    @patch(
        "notion_writer.check_birthdays_today",
        side_effect=RuntimeError("contacts broken"),
    )
    @patch(
        "notion_writer.subprocess.check_output",
        return_value=json.dumps({"brokerage_data": {}, "bank_data": {}}),
    )
    def test_birthday_failure_degrades(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Birthday check failure leaves birthdays sub-page as None."""
        client = _mock_client()
        mock_client_cls.return_value = client

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"
        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_pages"]["birthdays"] is None
        assert state["sub_pages"]["finance"] is not None
