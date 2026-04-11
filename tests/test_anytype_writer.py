"""Tests for anytype_writer orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from anytype_writer import _FM_CACHE_FILE, _STATE_FILE, main


def _mock_client() -> MagicMock:
    """Return a mock AnytypeClient."""
    client = MagicMock()
    client.create_object.side_effect = lambda space_id, name, icon, body, **kw: (
        f"id-{name[:20]}"
    )
    return client


class TestMain:
    """Tests for the anytype_writer main orchestrator."""

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch("anytype_writer.extract_today_reading")
    @patch("anytype_writer.fetch_weather")
    @patch("anytype_writer.fetch_todoist_tasks")
    @patch("anytype_writer.check_birthdays_today")
    @patch("anytype_writer.subprocess.check_output")
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
        """Verify state file is written with all sub-object IDs."""
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
        mock_weather.return_value = {"today_hourly": [], "ten_day_forecast": []}
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert "parent_object_id" in state
        assert "sub_objects" in state
        assert state["space_id"] == "space-123"

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch("anytype_writer.extract_today_reading")
    @patch("anytype_writer.fetch_weather")
    @patch("anytype_writer.fetch_todoist_tasks")
    @patch("anytype_writer.check_birthdays_today")
    @patch("anytype_writer.subprocess.check_output")
    def test_parent_object_uses_daily_brief_name(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify parent object name contains 'Daily Brief'."""
        client = _mock_client()
        mock_client_cls.return_value = client

        mock_bible.return_value = {"morning_devotional": None}
        mock_weather.return_value = {"today_hourly": [], "ten_day_forecast": []}
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        # First call is parent object creation
        first_call = client.create_object.call_args_list[0]
        name_arg = (
            first_call[1]["name"] if "name" in first_call[1] else first_call[0][1]
        )
        assert "Daily Brief" in name_arg

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch("anytype_writer.extract_today_reading")
    @patch("anytype_writer.fetch_weather")
    @patch("anytype_writer.fetch_todoist_tasks")
    @patch("anytype_writer.check_birthdays_today")
    @patch("anytype_writer.subprocess.check_output")
    def test_fault_tolerance_bible_failure(
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

        mock_bible.side_effect = RuntimeError("Bible file missing")
        mock_weather.return_value = {"today_hourly": [], "ten_day_forecast": []}
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_objects"]["morning_bible"] is None
        assert state["sub_objects"]["evening_bible"] is None
        assert state["sub_objects"]["weather"] is not None

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch("anytype_writer.extract_today_reading")
    @patch("anytype_writer.fetch_weather")
    @patch("anytype_writer.fetch_todoist_tasks")
    @patch("anytype_writer.check_birthdays_today")
    @patch("anytype_writer.subprocess.check_output")
    def test_no_birthdays_skips_subobject(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify birthdays sub-object is None when empty."""
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
        mock_weather.return_value = {"today_hourly": [], "ten_day_forecast": []}
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        assert state["sub_objects"]["birthdays"] is None

    @patch("anytype_writer.ANYTYPE_API_KEY", "")
    def test_exits_without_api_key(self) -> None:
        """Verify script exits if ANYTYPE_API_KEY is empty."""
        with pytest.raises(SystemExit):
            main()

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    def test_exits_without_space_id(self) -> None:
        """Verify script exits if ANYTYPE_SPACE_ID is empty."""
        with pytest.raises(SystemExit):
            main()

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch(
        "anytype_writer.extract_today_reading",
        return_value={
            "morning_devotional": {"day": "Day 1", "text": "T"},
            "bible_reading": {
                "reference": "Gen 1",
                "esv_text": "T",
                "study_notes": {},
            },
        },
    )
    @patch("anytype_writer.fetch_weather", side_effect=RuntimeError("API down"))
    @patch("anytype_writer.fetch_todoist_tasks", return_value=[])
    @patch("anytype_writer.check_birthdays_today", return_value=[])
    @patch(
        "anytype_writer.subprocess.check_output",
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
        """Weather failure leaves weather sub-object as None."""
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
        assert state["sub_objects"]["weather"] is None
        assert state["sub_objects"]["morning_bible"] is not None

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch(
        "anytype_writer.extract_today_reading",
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
        "anytype_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch(
        "anytype_writer.fetch_todoist_tasks",
        side_effect=RuntimeError("Todoist down"),
    )
    @patch("anytype_writer.check_birthdays_today", return_value=[])
    @patch(
        "anytype_writer.subprocess.check_output",
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
        """Todoist failure leaves todoist sub-object as None."""
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
        assert state["sub_objects"]["todoist"] is None
        assert state["sub_objects"]["weather"] is not None

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch(
        "anytype_writer.extract_today_reading",
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
        "anytype_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch("anytype_writer.fetch_todoist_tasks", return_value=[])
    @patch("anytype_writer.check_birthdays_today", return_value=[])
    @patch(
        "anytype_writer.subprocess.check_output",
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
        """Finance subprocess failure leaves finance sub-object as None."""
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
        assert state["sub_objects"]["finance"] is None
        assert state["sub_objects"]["todoist"] is not None

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch(
        "anytype_writer.extract_today_reading",
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
        "anytype_writer.fetch_weather",
        return_value={"today_hourly": [], "ten_day_forecast": []},
    )
    @patch("anytype_writer.fetch_todoist_tasks", return_value=[])
    @patch(
        "anytype_writer.check_birthdays_today",
        side_effect=RuntimeError("contacts broken"),
    )
    @patch(
        "anytype_writer.subprocess.check_output",
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
        """Birthday check failure leaves birthdays sub-object as None."""
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
        assert state["sub_objects"]["birthdays"] is None
        assert state["sub_objects"]["finance"] is not None

    @patch("anytype_writer.ANYTYPE_SPACE_ID", "space-123")
    @patch("anytype_writer.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_writer.AnytypeClient")
    @patch("anytype_writer.extract_today_reading")
    @patch("anytype_writer.fetch_weather")
    @patch("anytype_writer.fetch_todoist_tasks")
    @patch("anytype_writer.check_birthdays_today")
    @patch("anytype_writer.subprocess.check_output")
    def test_state_file_has_correct_keys(
        self,
        mock_subprocess: MagicMock,
        mock_birthdays: MagicMock,
        mock_todoist: MagicMock,
        mock_weather: MagicMock,
        mock_bible: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """State file must use space_id, parent_object_id, sub_objects keys."""
        client = _mock_client()
        mock_client_cls.return_value = client

        mock_bible.return_value = {"morning_devotional": None}
        mock_weather.return_value = {"today_hourly": [], "ten_day_forecast": []}
        mock_todoist.return_value = []
        mock_birthdays.return_value = []
        mock_subprocess.return_value = json.dumps(
            {"brokerage_data": {}, "bank_data": {}}
        )

        state_path = tmp_path / "state.json"
        fm_path = tmp_path / "fm.json"

        with (
            patch.object(type(_STATE_FILE), "write_text", state_path.write_text),
            patch.object(type(_FM_CACHE_FILE), "write_text", fm_path.write_text),
        ):
            main()

        state = json.loads(state_path.read_text())
        # Must use new Anytype key names (NOT Notion ones)
        assert "space_id" in state
        assert "parent_object_id" in state
        assert "sub_objects" in state
        # Must NOT use old Notion key names
        assert "parent_page_id" not in state
        assert "sub_pages" not in state
