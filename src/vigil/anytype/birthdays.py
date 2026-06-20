"""Build Markdown body for the Birthdays sub-object.

Checks ``contacts.json`` for contacts whose birthday matches today.
Optionally calls Claude Sonnet via OpenRouter for personalized messages.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from vigil.anytype.client import md_heading, md_paragraph
from vigil.clock import local_today_mmdd, local_year
from vigil.config import BIRTHDAY_USE_LLM, CONTACTS_PATH, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

_STUB_MSG = "🎂🎉 Happy birthday, {name}! I pray you have a wonderful day! 🙏🎈"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def check_birthdays_today(
    contacts_path: str | None = None,
) -> list[dict[str, Any]]:
    """Check contacts.json for birthdays matching today's date.

    Args:
        contacts_path: Override path to contacts JSON.  Falls back to
            ``CONTACTS_PATH`` from env.

    Returns:
        List of contact dicts that have a birthday today.
    """
    path = Path(contacts_path or CONTACTS_PATH)
    if not path.exists():
        logger.warning("Contacts file not found: %s", path)
        return []

    try:
        contacts: list[dict[str, Any]] = json.loads(
            path.read_text(encoding="utf-8"),
        )
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read contacts: %s", exc)
        return []

    today_mmdd = local_today_mmdd()
    matches: list[dict[str, Any]] = []

    for contact in contacts:
        birthday = contact.get("birthday", "")
        if not birthday:
            continue
        # birthday format: YYYY-MM-DD → extract MM-DD
        if birthday[5:] == today_mmdd:
            birth_year = int(birthday[:4])
            age = local_year() - birth_year
            matches.append({**contact, "age": age})

    return matches


def build_birthday_body(birthdays: list[dict[str, Any]]) -> str:
    """Build Markdown body for the 🎂 Birthdays sub-object.

    Args:
        birthdays: List of contact dicts with today's birthday.

    Returns:
        Markdown string for the birthday body.
    """
    if not birthdays:
        return md_paragraph("No birthdays today.")

    sections: list[str] = []

    for contact in birthdays:
        name = contact.get("name", "Unknown")
        age = contact.get("age", "?")
        relationship = contact.get("relationship", "")

        sections.append(md_heading(f"🎂 Happy Birthday, {name}!", level=2))

        meta = f"Age: {age}"
        if relationship:
            meta += f" | Relationship: {relationship}"
        sections.append(md_paragraph(meta))

        # Draft message
        message = _draft_birthday_message(name)
        sections.append(md_paragraph(message))

    return "\n\n".join(sections)


def _draft_birthday_message(name: str) -> str:
    """Draft a birthday message — stub or LLM-generated.

    Args:
        name: Contact's name.

    Returns:
        Birthday message string.
    """
    if not BIRTHDAY_USE_LLM or not OPENROUTER_API_KEY:
        return _STUB_MSG.format(name=name)

    try:
        return _call_sonnet_for_message(name)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning(
            "LLM birthday message failed for %s: %s — using stub",
            name,
            exc,
        )
        return _STUB_MSG.format(name=name)


def _call_sonnet_for_message(name: str) -> str:
    """Call Claude Sonnet via OpenRouter for a personalized birthday message.

    Args:
        name: Contact's name.

    Returns:
        Generated birthday message.

    Raises:
        httpx.HTTPStatusError: On API errors.
    """
    resp = httpx.post(
        _OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-sonnet-4-6-20250310",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Write a warm, heartfelt birthday message for "
                        f"{name}. Keep it 2-3 sentences. Include a "
                        f"prayer or blessing. Use emojis."
                    ),
                },
            ],
            "max_tokens": 200,
        },
        timeout=20,
    )
    resp.raise_for_status()
    choices = resp.json().get("choices", [])
    if choices:
        content: str = choices[0]["message"]["content"]
        return content
    return _STUB_MSG.format(name=name)
