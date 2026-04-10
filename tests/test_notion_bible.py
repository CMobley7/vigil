"""Tests for notion_bible module."""

from __future__ import annotations

from typing import Any

from notion_bible import (
    _chunk_text,
    build_evening_reading_blocks,
    build_morning_devotional_blocks,
)

# ---------------------------------------------------------------------------
# Fixtures — mock reading plan data
# ---------------------------------------------------------------------------


def _full_reading() -> dict[str, Any]:
    """Return a realistic extract_today_reading() result."""
    return {
        "date": "2026-03-10",
        "morning_devotional": {
            "day": "Day 69",
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


# ---------------------------------------------------------------------------
# Morning devotional
# ---------------------------------------------------------------------------


class TestBuildMorningDevotionalBlocks:
    """Tests for build_morning_devotional_blocks."""

    def test_has_heading_with_day_key(self) -> None:
        blocks = build_morning_devotional_blocks(_full_reading())
        assert blocks[0]["type"] == "heading_2"
        text = blocks[0]["heading_2"]["rich_text"][0]["text"]["content"]
        assert "Day 69" in text

    def test_has_devotional_text(self) -> None:
        blocks = build_morning_devotional_blocks(_full_reading())
        para = blocks[1]
        assert para["type"] == "paragraph"
        assert "mercies" in para["paragraph"]["rich_text"][0]["text"]["content"]

    def test_missing_devotional_shows_placeholder(self) -> None:
        reading: dict[str, Any] = {"date": "2026-03-10"}
        blocks = build_morning_devotional_blocks(reading)
        assert len(blocks) == 1
        content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "No devotional" in content

    def test_devotional_text_none_shows_warning(self) -> None:
        reading: dict[str, Any] = {
            "morning_devotional": {
                "day": "Day 69",
                "text": None,
                "note": "File missing",
            },
        }
        blocks = build_morning_devotional_blocks(reading)
        content = blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "File missing" in content


# ---------------------------------------------------------------------------
# Evening Bible reading
# ---------------------------------------------------------------------------


class TestBuildEveningReadingBlocks:
    """Tests for build_evening_reading_blocks."""

    def test_has_reference_heading(self) -> None:
        blocks = build_evening_reading_blocks(_full_reading())
        heading = blocks[0]
        assert heading["type"] == "heading_2"
        text = heading["heading_2"]["rich_text"][0]["text"]["content"]
        assert "Genesis 1-3 (ESV)" == text

    def test_has_esv_text(self) -> None:
        blocks = build_evening_reading_blocks(_full_reading())
        assert blocks[1]["type"] == "paragraph"
        assert "beginning" in blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]

    def test_study_notes_in_correct_order(self) -> None:
        blocks = build_evening_reading_blocks(_full_reading())
        # Find all heading_3 blocks — should be ESV Study, Reformation, MacArthur
        h3_blocks = [b for b in blocks if b["type"] == "heading_3"]
        titles = [b["heading_3"]["rich_text"][0]["text"]["content"] for b in h3_blocks]
        assert titles == [
            "ESV Study Bible",
            "Reformation Study Bible",
            "MacArthur Study Bible",
        ]

    def test_study_notes_in_toggles(self) -> None:
        blocks = build_evening_reading_blocks(_full_reading())
        toggle_blocks = [b for b in blocks if b["type"] == "toggle"]
        assert len(toggle_blocks) == 3
        # First toggle should contain ESV study note
        inner = toggle_blocks[0]["toggle"]["children"][0]
        assert "ESV note" in inner["paragraph"]["rich_text"][0]["text"]["content"]

    def test_missing_study_notes_shows_placeholder(self) -> None:
        reading = _full_reading()
        reading["bible_reading"]["study_notes"]["macarthur"] = None
        blocks = build_evening_reading_blocks(reading)
        toggle_blocks = [b for b in blocks if b["type"] == "toggle"]
        mac_toggle = toggle_blocks[2]  # MacArthur is third
        inner = mac_toggle["toggle"]["children"][0]
        assert "No notes" in inner["paragraph"]["rich_text"][0]["text"]["content"]

    def test_no_bible_reading_shows_placeholder(self) -> None:
        reading: dict[str, Any] = {"date": "2026-03-10"}
        blocks = build_evening_reading_blocks(reading)
        assert len(blocks) == 1
        content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "No Bible reading" in content


# ---------------------------------------------------------------------------
# Chunk text helper
# ---------------------------------------------------------------------------


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
