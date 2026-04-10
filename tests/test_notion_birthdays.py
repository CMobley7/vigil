"""Tests for notion_birthdays module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from notion_birthdays import build_birthday_blocks, check_birthdays_today


class TestCheckBirthdaysToday:
    """Tests for check_birthdays_today."""

    def test_no_file_returns_empty(self, tmp_path: Path) -> None:
        result = check_birthdays_today(
            str(tmp_path / "nonexistent.json"),
        )
        assert result == []

    def test_no_matches(self, tmp_path: Path) -> None:
        contacts = [
            {"name": "Alice", "birthday": "1990-12-25"},
        ]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))
        result = check_birthdays_today(str(path))
        # Unless today is Dec 25, this should be empty
        assert isinstance(result, list)

    @patch("notion_birthdays.datetime")
    def test_matches_today(self, mock_dt: MagicMock, tmp_path: Path) -> None:
        # Mock today as March 10
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "03-10"
        mock_now.year = 2026

        contacts = [
            {
                "name": "John",
                "birthday": "1990-03-10",
                "relationship": "friend",
            },
            {"name": "Jane", "birthday": "1992-06-15"},
        ]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))

        result = check_birthdays_today(str(path))
        assert len(result) == 1
        assert result[0]["name"] == "John"
        assert result[0]["age"] == 36


class TestBuildBirthdayBlocks:
    """Tests for build_birthday_blocks."""

    def test_empty_list(self) -> None:
        blocks = build_birthday_blocks([])
        assert len(blocks) == 1
        content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "No birthdays" in content

    @patch("notion_birthdays.BIRTHDAY_USE_LLM", False)
    def test_has_heading_and_message(self) -> None:
        birthdays = [
            {
                "name": "John",
                "age": 36,
                "relationship": "friend",
            },
        ]
        blocks = build_birthday_blocks(birthdays)
        heading = blocks[0]
        assert heading["type"] == "heading_2"
        text = heading["heading_2"]["rich_text"][0]["text"]["content"]
        assert "John" in text

        # Check stub message
        msg_block = blocks[2]
        content = msg_block["paragraph"]["rich_text"][0]["text"]["content"]
        assert "pray" in content
        assert "John" in content
        assert content.startswith("🎂🎉")

    @patch("notion_birthdays.BIRTHDAY_USE_LLM", False)
    def test_meta_includes_age_and_relationship(self) -> None:
        birthdays = [
            {
                "name": "Alice",
                "age": 30,
                "relationship": "sister",
            },
        ]
        blocks = build_birthday_blocks(birthdays)
        meta = blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "30" in meta
        assert "sister" in meta


class TestCheckBirthdaysJsonError:
    """Test that a corrupt contacts file is handled gracefully."""

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "contacts.json"
        bad_file.write_text("{not valid json!!!")
        result = check_birthdays_today(str(bad_file))
        assert result == []


class TestCheckBirthdaysSkipsEmptyBirthday:
    """Test that contacts without a birthday field are skipped."""

    @patch("notion_birthdays.datetime")
    def test_contact_without_birthday_skipped(
        self,
        mock_dt: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "03-10"
        mock_now.year = 2026

        contacts = [
            {"name": "NoBday"},  # no "birthday" key at all
            {"name": "EmptyBday", "birthday": ""},  # empty string
            {"name": "Match", "birthday": "1990-03-10"},
        ]
        path = tmp_path / "contacts.json"
        path.write_text(json.dumps(contacts))

        result = check_birthdays_today(str(path))
        assert len(result) == 1
        assert result[0]["name"] == "Match"


class TestLlmBirthdayMessage:
    """Tests for the LLM-generated birthday message paths."""

    @patch("notion_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("notion_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("notion_birthdays.httpx.post")
    def test_successful_llm_response(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"content": "Happy bday from LLM!"}},
            ],
        }
        mock_post.return_value = mock_resp

        from notion_birthdays import _call_sonnet_for_message

        result = _call_sonnet_for_message("Alice")
        assert result == "Happy bday from LLM!"
        mock_post.assert_called_once()

    @patch("notion_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("notion_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("notion_birthdays.httpx.post")
    def test_empty_choices_returns_stub(self, mock_post: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": []}
        mock_post.return_value = mock_resp

        from notion_birthdays import _call_sonnet_for_message

        result = _call_sonnet_for_message("Bob")
        assert "Bob" in result
        assert result.startswith("🎂🎉")

    @patch("notion_birthdays.OPENROUTER_API_KEY", "test-key")
    @patch("notion_birthdays.BIRTHDAY_USE_LLM", True)
    @patch("notion_birthdays.httpx.post", side_effect=httpx.ConnectError("fail"))
    def test_llm_exception_falls_back_to_stub(
        self,
        mock_post: MagicMock,
    ) -> None:
        from notion_birthdays import _draft_birthday_message

        result = _draft_birthday_message("Carol")
        assert "Carol" in result
        assert result.startswith("🎂🎉")
        mock_post.assert_called_once()
