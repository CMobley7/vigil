"""Configured local time helpers for daily operations."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from vigil.config import VIGIL_TIMEZONE


def _timezone() -> ZoneInfo:
    """Return the configured local timezone.

    Raises:
        ValueError: If ``VIGIL_TIMEZONE`` is not a valid IANA timezone.
    """
    try:
        return ZoneInfo(VIGIL_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        msg = f"Invalid VIGIL_TIMEZONE: {VIGIL_TIMEZONE}"
        raise ValueError(msg) from exc


def local_now() -> datetime:
    """Return the current time in Vigil's configured local timezone."""
    return datetime.now(tz=_timezone())


def local_today_iso() -> str:
    """Return today's local date as ``YYYY-MM-DD``."""
    return local_now().date().isoformat()


def local_today_mmdd() -> str:
    """Return today's local month/day as ``MM-DD``."""
    return local_now().strftime("%m-%d")


def local_year() -> int:
    """Return the current local year."""
    return local_now().year


def local_display_date() -> str:
    """Return the local date for human-readable daily brief titles."""
    now = local_now()
    return f"{now.strftime('%A, %B')} {now.day}, {now.year}"
