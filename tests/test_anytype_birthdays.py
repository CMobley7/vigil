"""Tests for anytype_birthdays module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from anytype_birthdays import build_birthday_body, check_birthdays_today


class TestCheckBirthdaysToday:
    """Tests for check_birthdays_today."""

    def test_no_file_returns_empty(self, tmp_path: Path) -> None:
        result = check_birthdays_today(str(tmp_path / "nonexistent.json"))
        assert result == []

    def test_no_matches(self, tmp_path: Path) -> None:
        contacts = [{"name": "Alice", "birthday": "1990-12-25"}]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))
        result = check_birthdays_today(str(path))
        assert isinstance(result, list)

    @patch("anytype_birthdays.datetime")
    def test_matches_today(self, mock_dt: MagicMock, tmp_path: Path) -> None:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "04-10"
        mock_now.year = 2026

        contacts = [
            {"name": "John", "birthday": "1990-04-10", "relationship": "friend"},
            {"name": "Jane", "birthday": "1992-06-15"},
        ]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))

        result = check_birthdays_today(str(path))
        assert len(result) == 1
        assert result[0]["name"] == "John"
        assert result[0]["age"] == 36

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "contacts.json"
        bad_file.write_text("{not valid json!!!")
        result = check_birthdays_today(str(bad_file))
        assert result == []

    @patch("anytype_birthdays.datetime")
    def test_contact_without_birthday_skipped(
        self, mock_dt: MagicMock, tmp_path: Path
    ) -> None:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "04-10"
        mock_now.year = 2026

        contacts = [
            {"name": "NoBday"},
            {"name": "EmptyBday", "birthday": ""},
            {"name": "Match", "birthday": "1990-04-10"},
        ]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))

        result = check_birthdays_today(str(path))
        assert len(result) == 1
        assert result[0]["name"] == "Match"


class TestBuildBirthdayBody:
    """Tests for build_birthday_body."""

    def test_returns_string(self) -> None:
        result = build_birthday_body([])
        assert isinstance(result, str)

    def test_empty_list(self) -> None:
        result = build_birthday_body([])
        assert "No birthdays" in result

    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", False)
    def test_has_heading_with_name(self) -> None:
        birthdays = [{"name": "John", "age": 36, "relationship": "friend"}]
        result = build_birthday_body(birthdays)
        assert "John" in result

    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", False)
    def test_has_stub_message(self) -> None:
        birthdays = [{"name": "John", "age": 36, "relationship": "friend"}]
        result = build_birthday_body(birthdays)
        assert "pray" in result
        assert "John" in result

    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", False)
    def test_meta_includes_age_and_relationship(self) -> None:
        birthdays = [{"name": "Alice", "age": 30, "relationship": "sister"}]
        result = build_birthday_body(birthdays)
        assert "30" in result
        assert "sister" in result

    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", False)
    def test_uses_markdown_heading(self) -> None:
        birthdays = [{"name": "Bob", "age": 25}]
        result = build_birthday_body(birthdays)
        assert "## " in result or "### " in result


class TestLlmBirthdayMessage:
    """Tests for the LLM-generated birthday message paths."""

    @patch("anytype_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("anytype_birthdays.httpx.post")
    def test_successful_llm_response(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Happy bday from LLM!"}}],
        }
        mock_post.return_value = mock_resp

        from anytype_birthdays import _call_sonnet_for_message

        result = _call_sonnet_for_message("Alice")
        assert result == "Happy bday from LLM!"
        mock_post.assert_called_once()

    @patch("anytype_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("anytype_birthdays.httpx.post")
    def test_empty_choices_returns_stub(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": []}
        mock_post.return_value = mock_resp

        from anytype_birthdays import _call_sonnet_for_message

        result = _call_sonnet_for_message("Bob")
        assert "Bob" in result
        assert result.startswith("🎂🎉")

    @patch("anytype_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("anytype_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("anytype_birthdays.httpx.post", side_effect=httpx.ConnectError("fail"))
    def test_llm_exception_falls_back_to_stub(self, mock_post: MagicMock) -> None:
        from anytype_birthdays import _draft_birthday_message

        result = _draft_birthday_message("Carol")
        assert "Carol" in result
        assert result.startswith("🎂🎉")
        mock_post.assert_called_once()
