#!/usr/bin/env python3
"""Extract today's Bible passage and devotional from markdown files.

Reads a reading plan JSON, then extracts the correct passage text from
pre-converted markdown files. This avoids sending 3000+ page markdown
files to the LLM — only today's content is returned.

Usage:
    python3 bible_reading.py

Configuration via environment variables:
    READING_PLAN_PATH — path to reading_plan.json
    BOOKS_DIR         — directory containing markdown book files
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fm_config import BOOKS_DIR, READING_PLAN_PATH

logger = logging.getLogger(__name__)


# Expected filenames in BOOKS_DIR
DEVOTIONAL_FILE = "good_morning_mercies.md"
ESV_BIBLE_FILE = "esv_bible.md"
STUDY_BIBLE_FILES: dict[str, str] = {
    "reformation": "reformation_study_bible.md",
    "macarthur": "macarthur_study_bible.md",
    "esv_study": "esv_study_bible.md",
}

# Regex to parse Bible references like:
#   "Genesis 1-3", "1 Samuel 4-6", "Song of Solomon 1-2", "Psalm 119:1-88"
REFERENCE_RE = re.compile(r"^(.+?)\s+(\d+)(?::(\d+))?(?:-(\d+)(?::(\d+))?)?$")


def _parse_reference(ref: str) -> dict[str, Any]:
    """Parse a Bible passage reference into structured components.

    Handles multi-word book names (e.g., "1 Samuel", "Song of Solomon")
    and verse-level references (e.g., "Psalm 119:1-88").

    Args:
        ref: A passage reference string (e.g., "Genesis 1-3").

    Returns:
        Dict with keys: ``book``, ``start_chapter``, ``start_verse``,
        ``end_chapter``, ``end_verse``.
    """
    match = REFERENCE_RE.match(ref.strip())
    if not match:
        return {
            "book": ref,
            "start_chapter": None,
            "start_verse": None,
            "end_chapter": None,
            "end_verse": None,
        }

    book = match.group(1).strip()
    start_chapter = int(match.group(2))
    start_verse = int(match.group(3)) if match.group(3) else None
    raw_end = int(match.group(4)) if match.group(4) else None
    end_colon_verse = int(match.group(5)) if match.group(5) else None

    # "Psalm 119:1-88" → same chapter, verse range (start_verse=1, end_verse=88)
    # "Genesis 1-3"    → chapter range (no start_verse)
    # "Genesis 1:1-3:5" → chapter:verse to chapter:verse
    end_chapter: int = start_chapter
    end_verse: int | None = None
    if start_verse is not None and end_colon_verse is None and raw_end is not None:
        # e.g. "Psalm 119:1-88" → same-chapter verse range
        end_chapter = start_chapter
        end_verse = raw_end
    elif raw_end is not None:
        end_chapter = raw_end
        end_verse = end_colon_verse

    return {
        "book": book,
        "start_chapter": start_chapter,
        "start_verse": start_verse,
        "end_chapter": end_chapter,
        "end_verse": end_verse,
    }


def _extract_chapter_range(
    markdown: str,
    book: str,
    start_chapter: int,
    end_chapter: int,
    start_verse: int | None = None,
    end_verse: int | None = None,
) -> str | None:
    """Extract a range of chapters (or verses) from a Bible markdown file.

    Searches for ``# {Book}`` then ``## Chapter {N}`` headings.

    Args:
        markdown: Full markdown content of the Bible file.
        book: Book name (e.g., "Genesis").
        start_chapter: Starting chapter number.
        end_chapter: Ending chapter number (inclusive).
        start_verse: Optional starting verse number.
        end_verse: Optional ending verse number.

    Returns:
        Extracted text, or ``None`` if the book/chapter wasn't found.
    """
    lines = markdown.splitlines()
    in_book = False
    in_target_chapter = False
    current_chapter = 0
    result_lines: list[str] = []

    # Patterns to match book and chapter headings
    book_pattern = re.compile(rf"^#\s+{re.escape(book)}\s*$", re.IGNORECASE)
    chapter_pattern = re.compile(r"^##\s+Chapter\s+(\d+)", re.IGNORECASE)
    # Fallback: some markdown formats use "## BookName ChapterNum"
    alt_chapter_pattern = re.compile(rf"^#+\s+{re.escape(book)}\s+(\d+)", re.IGNORECASE)

    for line in lines:
        # Check if we've found the book heading
        if not in_book:
            if book_pattern.match(line):
                in_book = True
            continue

        # Check for chapter headings within the book
        chapter_match = chapter_pattern.match(line) or alt_chapter_pattern.match(line)
        if chapter_match:
            current_chapter = int(chapter_match.group(1))
            if current_chapter > end_chapter:
                break  # Past our target range
            in_target_chapter = start_chapter <= current_chapter <= end_chapter
            if in_target_chapter:
                result_lines.append(line)
            continue

        # Check if we've hit the next book (another # heading)
        if line.startswith("# ") and in_book:
            break

        if in_target_chapter:
            result_lines.append(line)

    if not result_lines:
        return None

    text = "\n".join(result_lines).strip()

    # If verse-level reference, try to extract just those verses
    if start_verse is not None and end_verse is not None:
        text = _extract_verse_range(text, start_verse, end_verse)

    return text or None


def _extract_verse_range(text: str, start_verse: int, end_verse: int) -> str:
    """Extract a specific verse range from chapter text.

    Looks for verse markers like ``**1** ...`` or ``1. ...`` or just ``1 ...``
    at the start of lines.

    Args:
        text: Chapter text to search.
        start_verse: First verse number to include.
        end_verse: Last verse number to include.

    Returns:
        Extracted verse text, or the full text if verse markers aren't found.
    """
    lines = text.splitlines()
    verse_pattern = re.compile(r"^\*{0,2}(\d+)\*{0,2}[\.\s]")
    result_lines: list[str] = []
    in_range = False

    for line in lines:
        match = verse_pattern.match(line.strip())
        if match:
            verse_num = int(match.group(1))
            if start_verse <= verse_num <= end_verse:
                in_range = True
                result_lines.append(line)
            elif verse_num > end_verse:
                break
            else:
                in_range = False
        elif in_range:
            result_lines.append(line)

    # If we didn't find verse markers, return the full text
    return "\n".join(result_lines).strip() if result_lines else text


def _extract_devotional(markdown: str, day_key: str) -> str | None:
    """Extract a devotional entry by heading.

    Tries multiple heading formats: ``## Day N``, ``## January 1``,
    ``## March 10``, etc.

    Args:
        markdown: Full markdown content of the devotional book.
        day_key: The key from the reading plan (e.g., "Day 69" or "March 10").

    Returns:
        Extracted devotional text, or ``None`` if not found.
    """
    heading_pattern = re.compile(rf"^##\s+{re.escape(day_key)}\s*$", re.IGNORECASE)
    lines = markdown.splitlines()
    result_lines: list[str] = []
    in_section = False

    for line in lines:
        if heading_pattern.match(line):
            in_section = True
            continue
        if in_section:
            # Stop at the next ## heading
            if line.startswith("## "):
                break
            result_lines.append(line)

    return "\n".join(result_lines).strip() if result_lines else None


def _read_file_safe(path: Path) -> str | None:
    """Read a file, returning ``None`` if it doesn't exist.

    Args:
        path: Path to the file.

    Returns:
        File contents as string, or ``None`` on error.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return None
    except OSError as exc:
        logger.warning("Error reading %s: %s", path, exc)
        return None


def extract_today_reading() -> dict[str, Any]:
    """Extract today's Bible reading and devotional from local files.

    Returns:
        Dict with ``date``, ``morning_devotional``, ``bible_reading`` keys.
    """
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    # Load reading plan
    plan_path = Path(READING_PLAN_PATH)
    if not plan_path.exists():
        return {"date": today, "error": "reading_plan.json not found"}

    try:
        plan: list[dict[str, str]] = json.loads(plan_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"date": today, "error": f"Failed to parse reading plan: {exc}"}

    # Find today's entry
    today_entry = None
    for entry in plan:
        if entry.get("date") == today:
            today_entry = entry
            break

    if today_entry is None:
        return {"date": today, "warning": "no reading scheduled for today"}

    result: dict[str, Any] = {"date": today}

    # --- Morning devotional ---
    devotional_key = today_entry.get("morning_devotional", "")
    devotional_md = _read_file_safe(BOOKS_DIR / DEVOTIONAL_FILE)

    if devotional_md and devotional_key:
        text = _extract_devotional(devotional_md, devotional_key)
        result["morning_devotional"] = {
            "day": devotional_key,
            "text": text,
        }
        if text is None:
            logger.warning(
                "Could not find devotional entry for '%s' in %s",
                devotional_key,
                DEVOTIONAL_FILE,
            )
    else:
        result["morning_devotional"] = {
            "day": devotional_key,
            "text": None,
            "note": (
                f"File missing: {DEVOTIONAL_FILE}" if not devotional_md else "No key"
            ),
        }

    # --- Bible reading ---
    reference = today_entry.get("bible_reading", "")
    parsed = _parse_reference(reference)

    esv_md = _read_file_safe(BOOKS_DIR / ESV_BIBLE_FILE)
    esv_text = None
    if esv_md and parsed["start_chapter"] is not None:
        esv_text = _extract_chapter_range(
            esv_md,
            parsed["book"],
            parsed["start_chapter"],
            parsed["end_chapter"],
            parsed["start_verse"],
            parsed["end_verse"],
        )

    study_notes: dict[str, str | None] = {}
    for key, filename in STUDY_BIBLE_FILES.items():
        study_md = _read_file_safe(BOOKS_DIR / filename)
        if study_md and parsed["start_chapter"] is not None:
            notes = _extract_chapter_range(
                study_md,
                parsed["book"],
                parsed["start_chapter"],
                parsed["end_chapter"],
                parsed["start_verse"],
                parsed["end_verse"],
            )
            study_notes[key] = notes
        else:
            study_notes[key] = None
            if not (BOOKS_DIR / filename).exists():
                logger.warning("Study Bible file missing: %s", filename)

    result["bible_reading"] = {
        "reference": reference,
        "esv_text": esv_text,
        "study_notes": study_notes,
    }

    return result


def main() -> None:
    """Extract today's reading and print JSON to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    result = extract_today_reading()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
