"""Build Markdown body for Bible reading sub-objects.

Transforms the output of :func:`vigil.bible.extract_today_reading` into
a Markdown string for two sub-objects:

- 📖 Morning Bible Reading (Good Morning Mercies devotional)
- 🌙 Evening Bible Reading (ESV passage + study notes in toggle blocks)

Study note order: ESV Study Bible → Reformation Study Bible → MacArthur.
"""

from __future__ import annotations

from typing import Any

from vigil.anytype.client import md_heading, md_paragraph, md_toggle

# Map from vigil.bible study note keys → display names.
# Order determines rendering order (ESV Study → Reformation → MacArthur).
_STUDY_NOTE_ORDER: list[tuple[str, str]] = [
    ("esv_study", "ESV Study Bible"),
    ("reformation", "Reformation Study Bible"),
    ("macarthur", "MacArthur Study Bible"),
]


def build_morning_devotional_body(reading: dict[str, Any]) -> str:
    """Build Markdown body for the 📖 Morning Bible Reading sub-object.

    Args:
        reading: Output of ``extract_today_reading()``.

    Returns:
        Markdown string for the morning devotional body.
    """
    sections: list[str] = []
    devotional = reading.get("morning_devotional")

    if not devotional or not isinstance(devotional, dict):
        return md_paragraph("No devotional content available for today.")

    day_key = devotional.get("day", "Today")
    text = devotional.get("text")

    sections.append(md_heading(f"Good Morning Mercies — {day_key}", level=2))

    if text:
        for chunk in _chunk_text(text):
            sections.append(md_paragraph(chunk))
    else:
        note = devotional.get("note", "Content not found.")
        sections.append(md_paragraph(f"⚠️ {note}"))

    return "\n\n".join(sections)


def build_evening_reading_body(reading: dict[str, Any]) -> str:
    """Build Markdown body for the 🌙 Evening Bible Reading sub-object.

    Args:
        reading: Output of ``extract_today_reading()``.

    Returns:
        Markdown string for the evening reading body.
    """
    sections: list[str] = []
    bible = reading.get("bible_reading")

    if not bible or not isinstance(bible, dict):
        return md_paragraph("No Bible reading scheduled for today.")

    reference = bible.get("reference", "Unknown")
    esv_text = bible.get("esv_text")

    # -- ESV passage --
    sections.append(md_heading(f"{reference} (ESV)", level=2))

    if esv_text:
        for chunk in _chunk_text(esv_text):
            sections.append(md_paragraph(chunk))
    else:
        sections.append(md_paragraph("⚠️ Passage text not found in ESV Bible file."))

    # -- Study Notes --
    study_notes = bible.get("study_notes")
    if isinstance(study_notes, dict):
        sections.append(md_heading("Study Notes", level=2))

        for key, display_name in _STUDY_NOTE_ORDER:
            note_text = study_notes.get(key)
            if note_text:
                content = "\n\n".join(
                    md_paragraph(chunk) for chunk in _chunk_text(note_text)
                )
            else:
                content = md_paragraph("No notes available for this passage.")

            sections.append(md_toggle(display_name, content))

    return "\n\n".join(sections)


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
        addition = len(para) + (2 if current else 0)
        if current_len + addition > max_len and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if len(para) > max_len:
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
