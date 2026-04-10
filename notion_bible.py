"""Build Notion blocks for Bible reading sub-pages.

Transforms the output of :func:`bible_reading.extract_today_reading` into
Notion block dicts for two sub-pages:

- 📖 Morning Bible Reading (Good Morning Mercies devotional)
- 🌙 Evening Bible Reading (ESV passage + study notes in toggle blocks)

Study note order: ESV Study Bible → Reformation Study Bible → MacArthur.
"""

from __future__ import annotations

from typing import Any

from notion_client import heading_2, heading_3, paragraph, toggle

# Map from bible_reading.py study note keys → display names.
# Order determines rendering order (ESV Study → Reformation → MacArthur).
_STUDY_NOTE_ORDER: list[tuple[str, str]] = [
    ("esv_study", "ESV Study Bible"),
    ("reformation", "Reformation Study Bible"),
    ("macarthur", "MacArthur Study Bible"),
]


def build_morning_devotional_blocks(reading: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Notion blocks for the 📖 Morning Bible Reading sub-page.

    Args:
        reading: Output of ``extract_today_reading()``.

    Returns:
        List of Notion block dicts.
    """
    blocks: list[dict[str, Any]] = []
    devotional = reading.get("morning_devotional")

    if not devotional or not isinstance(devotional, dict):
        blocks.append(paragraph("No devotional content available for today."))
        return blocks

    day_key = devotional.get("day", "Today")
    text = devotional.get("text")

    blocks.append(heading_2(f"Good Morning Mercies — {day_key}"))

    if text:
        # Split long text into ≤2000-char paragraphs (Notion limit).
        for chunk in _chunk_text(text, max_len=2000):
            blocks.append(paragraph(chunk))
    else:
        note = devotional.get("note", "Content not found.")
        blocks.append(paragraph(f"⚠️ {note}"))

    return blocks


def build_evening_reading_blocks(reading: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Notion blocks for the 🌙 Evening Bible Reading sub-page.

    Args:
        reading: Output of ``extract_today_reading()``.

    Returns:
        List of Notion block dicts.
    """
    blocks: list[dict[str, Any]] = []
    bible = reading.get("bible_reading")

    if not bible or not isinstance(bible, dict):
        blocks.append(paragraph("No Bible reading scheduled for today."))
        return blocks

    reference = bible.get("reference", "Unknown")
    esv_text = bible.get("esv_text")

    # -- ESV passage --
    blocks.append(heading_2(f"{reference} (ESV)"))

    if esv_text:
        for chunk in _chunk_text(esv_text, max_len=2000):
            blocks.append(paragraph(chunk))
    else:
        blocks.append(paragraph("⚠️ Passage text not found in ESV Bible file."))

    # -- Study Notes --
    study_notes = bible.get("study_notes")
    if isinstance(study_notes, dict):
        blocks.append(heading_2("Study Notes"))

        for key, display_name in _STUDY_NOTE_ORDER:
            note_text = study_notes.get(key)
            if note_text:
                children = [
                    paragraph(chunk) for chunk in _chunk_text(note_text, max_len=2000)
                ]
            else:
                children = [paragraph("No notes available for this passage.")]

            blocks.append(heading_3(display_name))
            blocks.append(toggle(display_name, children))

    return blocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk_text(text: str, *, max_len: int = 2000) -> list[str]:
    """Split long text into chunks of at most *max_len* characters.

    Splits on paragraph boundaries (double newlines) first, then on single
    newlines, and finally hard-truncates if a single line exceeds the limit.

    Args:
        text: The text to chunk.
        max_len: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        # +2 for the double newline separator
        addition = len(para) + (2 if current else 0)
        if current_len + addition > max_len and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if len(para) > max_len:
            # Hard truncate oversized paragraphs
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for i in range(0, len(para), max_len):
                chunks.append(para[i : i + max_len])
        else:
            current.append(para)
            current_len += addition

    if current:
        chunks.append("\n\n".join(current))

    return chunks
