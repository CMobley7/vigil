"""Tests for anytype_bible module."""

from __future__ import annotations

from typing import Any

from anytype_bible import (
    _chunk_text,
    build_evening_reading_body,
    build_morning_devotional_body,
)


def _full_reading() -> dict[str, Any]:
    """Return a realistic extract_today_reading() result."""
    return {
        "date": "2026-04-10",
        "morning_devotional": {
            "day": "Day 100",
            "text": "God's mercies are new every morning.",
        },
        "bible_reading": {
            "reference": "Genesis 1-3",
            "esv_text": "In the beginning, God created the heavens and the earth.",
            "study_notes": {
                "esv_study": "ESV note on Genesis 1.",
                "reformation": "Reformation note on Genesis 1.",
                "macarthur": "MacArthur note on Genesis 1.",
            },
        },
    }


class TestBuildMorningDevotionalBody:
    """Tests for build_morning_devotional_body."""

    def test_contains_day_key(self) -> None:
        result = build_morning_devotional_body(_full_reading())
        assert "Day 100" in result

    def test_contains_devotional_text(self) -> None:
        result = build_morning_devotional_body(_full_reading())
        assert "mercies" in result

    def test_is_markdown_heading(self) -> None:
        result = build_morning_devotional_body(_full_reading())
        assert result.startswith("## ")

    def test_missing_devotional_shows_placeholder(self) -> None:
        reading: dict[str, Any] = {"date": "2026-04-10"}
        result = build_morning_devotional_body(reading)
        assert "No devotional" in result

    def test_devotional_text_none_shows_warning(self) -> None:
        reading: dict[str, Any] = {
            "morning_devotional": {
                "day": "Day 100",
                "text": None,
                "note": "File missing",
            },
        }
        result = build_morning_devotional_body(reading)
        assert "File missing" in result


class TestBuildEveningReadingBody:
    """Tests for build_evening_reading_body."""

    def test_contains_reference_heading(self) -> None:
        result = build_evening_reading_body(_full_reading())
        assert "Genesis 1-3 (ESV)" in result

    def test_contains_esv_text(self) -> None:
        result = build_evening_reading_body(_full_reading())
        assert "beginning" in result

    def test_study_notes_in_correct_order(self) -> None:
        result = build_evening_reading_body(_full_reading())
        esv_pos = result.find("ESV Study Bible")
        ref_pos = result.find("Reformation Study Bible")
        mac_pos = result.find("MacArthur Study Bible")
        assert esv_pos < ref_pos < mac_pos

    def test_study_notes_use_toggle_syntax(self) -> None:
        result = build_evening_reading_body(_full_reading())
        assert "<details>" in result
        assert "<summary>" in result

    def test_missing_study_notes_shows_placeholder(self) -> None:
        reading = _full_reading()
        reading["bible_reading"]["study_notes"]["macarthur"] = None
        result = build_evening_reading_body(reading)
        assert "No notes" in result

    def test_no_bible_reading_shows_placeholder(self) -> None:
        reading: dict[str, Any] = {"date": "2026-04-10"}
        result = build_evening_reading_body(reading)
        assert "No Bible reading" in result

    def test_no_esv_text_shows_warning(self) -> None:
        reading = _full_reading()
        reading["bible_reading"]["esv_text"] = None
        result = build_evening_reading_body(reading)
        assert "not found" in result.lower() or "⚠️" in result


class TestChunkText:
    """Tests for _chunk_text."""

    def test_short_text_unchanged(self) -> None:
        assert _chunk_text("short") == ["short"]

    def test_splits_on_double_newline(self) -> None:
        text = "a" * 1500 + "\n\n" + "b" * 1500
        chunks = _chunk_text(text, max_len=2000)
        assert len(chunks) == 2
        assert chunks[0].startswith("a")
        assert chunks[1].startswith("b")

    def test_hard_truncates_oversized_paragraph(self) -> None:
        text = "x" * 5000
        chunks = _chunk_text(text, max_len=2000)
        assert len(chunks) == 3
        assert all(len(c) <= 2000 for c in chunks)
