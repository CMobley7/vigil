"""Tests for bible_reading.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from bible_reading import (
    _extract_chapter_range,
    _extract_devotional,
    _extract_verse_range,
    _parse_reference,
    _read_file_safe,
    extract_today_reading,
    main,
)

# --- Fixtures ---


SAMPLE_BIBLE_MD = """\
# Genesis

## Chapter 1

In the beginning God created the heavens and the earth.

## Chapter 2

Thus the heavens and the earth were completed.

## Chapter 3

Now the serpent was more crafty than any beast.

## Chapter 4

Now the man had relations with his wife Eve.

# Exodus

## Chapter 1

Now these are the names of the sons of Israel.
"""

SAMPLE_DEVOTIONAL_MD = """\
## Day 68

Yesterday's devotional text.

## Day 69

Today is the day that the Lord has made.
Let us rejoice and be glad in it.

## Day 70

Tomorrow's devotional text.
"""

SAMPLE_DEVOTIONAL_DATE_MD = """\
## March 9

Yesterday's devotional text.

## March 10

Today is the day that the Lord has made.
Let us rejoice and be glad in it.

## March 11

Tomorrow's devotional text.
"""

SAMPLE_PLAN = [
    {
        "date": "2026-03-10",
        "morning_devotional": "Day 69",
        "bible_reading": "Genesis 1-3",
    },
]


# --- Tests ---


class TestParseSimpleReference:
    def test_genesis_1_3(self) -> None:
        result = _parse_reference("Genesis 1-3")
        assert result["book"] == "Genesis"
        assert result["start_chapter"] == 1
        assert result["end_chapter"] == 3


class TestParseNumberedBook:
    def test_1_samuel_4_6(self) -> None:
        result = _parse_reference("1 Samuel 4-6")
        assert result["book"] == "1 Samuel"
        assert result["start_chapter"] == 4
        assert result["end_chapter"] == 6


class TestParseMultiWordBook:
    def test_song_of_solomon(self) -> None:
        result = _parse_reference("Song of Solomon 1-2")
        assert result["book"] == "Song of Solomon"
        assert result["start_chapter"] == 1
        assert result["end_chapter"] == 2


class TestParseVerseReference:
    def test_psalm_119_1_88(self) -> None:
        result = _parse_reference("Psalm 119:1-88")
        assert result["book"] == "Psalm"
        assert result["start_chapter"] == 119
        assert result["start_verse"] == 1
        assert result["end_verse"] == 88


class TestExtractChapterRange:
    def test_extracts_genesis_1_3(self) -> None:
        text = _extract_chapter_range(SAMPLE_BIBLE_MD, "Genesis", 1, 3)
        assert text is not None
        assert "In the beginning" in text
        assert "Now the serpent" in text
        # Should NOT include Chapter 4
        assert "relations with his wife" not in text


class TestExtractDevotionalByDay:
    def test_extracts_day_69(self) -> None:
        text = _extract_devotional(SAMPLE_DEVOTIONAL_MD, "Day 69")
        assert text is not None
        assert "Lord has made" in text
        assert "Yesterday" not in text


class TestExtractDevotionalByDate:
    def test_extracts_march_10(self) -> None:
        text = _extract_devotional(SAMPLE_DEVOTIONAL_DATE_MD, "March 10")
        assert text is not None
        assert "Lord has made" in text


class TestMissingReadingPlan:
    def test_returns_error_json(self, tmp_path: Path) -> None:
        with patch(
            "bible_reading.READING_PLAN_PATH",
            str(tmp_path / "nonexistent.json"),
        ):
            result = extract_today_reading()

        assert "error" in result
        assert "not found" in result["error"]


class TestDateNotInPlan:
    def test_returns_warning(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(
            json.dumps(
                [
                    {
                        "date": "2000-01-01",
                        "morning_devotional": "Day 1",
                        "bible_reading": "Genesis 1",
                    },
                ]
            )
        )

        with patch("bible_reading.READING_PLAN_PATH", str(plan_file)):
            result = extract_today_reading()

        assert "warning" in result
        assert "no reading scheduled" in result["warning"]


class TestMissingMarkdownFile:
    def test_returns_reference_without_text(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.json"
        # Use a far-future date we can mock
        plan_data = [
            {
                "date": "2026-03-10",
                "morning_devotional": "Day 69",
                "bible_reading": "Genesis 1-3",
            },
        ]
        plan_file.write_text(json.dumps(plan_data))

        with (
            patch("bible_reading.READING_PLAN_PATH", str(plan_file)),
            patch("bible_reading.BOOKS_DIR", tmp_path / "books"),
            patch(
                "bible_reading.datetime",
            ) as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2026-03-10"
            mock_dt.fromisoformat = lambda s: s
            result = extract_today_reading()

        assert result["bible_reading"]["reference"] == "Genesis 1-3"
        assert result["bible_reading"]["esv_text"] is None


class TestOutputSchemaValid:
    def test_has_required_keys(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(SAMPLE_PLAN))

        books_dir = tmp_path / "books"
        books_dir.mkdir()
        (books_dir / "good_morning_mercies.md").write_text(SAMPLE_DEVOTIONAL_MD)
        (books_dir / "esv_bible.md").write_text(SAMPLE_BIBLE_MD)

        with (
            patch("bible_reading.READING_PLAN_PATH", str(plan_file)),
            patch("bible_reading.BOOKS_DIR", books_dir),
            patch(
                "bible_reading.datetime",
            ) as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2026-03-10"
            mock_dt.fromisoformat = lambda s: s
            result = extract_today_reading()

        assert "date" in result
        assert "morning_devotional" in result
        assert "bible_reading" in result


# ---------------------------------------------------------------------------
# _extract_verse_range
# ---------------------------------------------------------------------------


class TestExtractVerseRange:
    def test_extracts_verse_subset(self) -> None:
        text = """**1** In the beginning God created.
**2** The earth was without form.
**3** And God said, Let there be light.
**4** And God saw the light.
**5** And God called the light Day.
**6** And God said, Let there be a firmament."""
        result = _extract_verse_range(text, 2, 4)
        assert "without form" in result
        assert "saw the light" in result
        assert "In the beginning" not in result
        assert "firmament" not in result

    def test_no_verse_markers_returns_full_text(self) -> None:
        text = "Some plain prose without verse markers."
        result = _extract_verse_range(text, 1, 5)
        assert result == text


# ---------------------------------------------------------------------------
# _read_file_safe
# ---------------------------------------------------------------------------


class TestReadFileSafe:
    def test_missing_file_returns_none(self) -> None:
        assert _read_file_safe(Path("/nonexistent/bible.md")) is None

    def test_valid_file_returns_content(self, tmp_path: Path) -> None:
        p = tmp_path / "test.md"
        p.write_text("Hello World")
        assert _read_file_safe(p) == "Hello World"


# ---------------------------------------------------------------------------
# extract_today_reading — malformed JSON
# ---------------------------------------------------------------------------


class TestMalformedReadingPlan:
    def test_invalid_json_returns_error(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text("{invalid json")

        with patch("bible_reading.READING_PLAN_PATH", str(plan_file)):
            result = extract_today_reading()

        assert "error" in result
        assert "Failed to parse" in result["error"]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestBibleReadingMain:
    def test_main_outputs_json(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(SAMPLE_PLAN))

        books_dir = tmp_path / "books"
        books_dir.mkdir()
        (books_dir / "good_morning_mercies.md").write_text(SAMPLE_DEVOTIONAL_MD)
        (books_dir / "esv_bible.md").write_text(SAMPLE_BIBLE_MD)

        with (
            patch("bible_reading.READING_PLAN_PATH", str(plan_file)),
            patch("bible_reading.BOOKS_DIR", books_dir),
            patch("bible_reading.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2026-03-10"
            mock_dt.fromisoformat = lambda s: s
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "date" in output


# ---------------------------------------------------------------------------
# _extract_chapter_range — alt pattern and book boundary
# ---------------------------------------------------------------------------

SAMPLE_ALT_FORMAT_MD = """\
# Genesis

## Genesis 1

In the beginning God created the heavens and the earth.

## Genesis 2

Thus the heavens and the earth were completed.

# Exodus

## Exodus 1

Now these are the names of the sons of Israel.
"""


class TestExtractWithAltChapterFormat:
    def test_alt_heading_format(self) -> None:
        text = _extract_chapter_range(SAMPLE_ALT_FORMAT_MD, "Genesis", 1, 1)
        assert text is not None
        assert "In the beginning" in text


class TestExtractChapterNotFound:
    def test_nonexistent_book_returns_none(self) -> None:
        assert _extract_chapter_range(SAMPLE_BIBLE_MD, "Revelation", 1, 3) is None


# ---------------------------------------------------------------------------
# extract_today_reading — study notes path
# ---------------------------------------------------------------------------


class TestStudyNotesExtraction:
    def test_study_notes_populated(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(SAMPLE_PLAN))

        books_dir = tmp_path / "books"
        books_dir.mkdir()
        (books_dir / "good_morning_mercies.md").write_text(SAMPLE_DEVOTIONAL_MD)
        (books_dir / "esv_bible.md").write_text(SAMPLE_BIBLE_MD)
        (books_dir / "reformation_study_bible.md").write_text(SAMPLE_BIBLE_MD)

        with (
            patch("bible_reading.READING_PLAN_PATH", str(plan_file)),
            patch("bible_reading.BOOKS_DIR", books_dir),
            patch("bible_reading.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.strftime.return_value = "2026-03-10"
            mock_dt.fromisoformat = lambda s: s
            result = extract_today_reading()

        assert result["bible_reading"]["study_notes"]["reformation"] is not None
