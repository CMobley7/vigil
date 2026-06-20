"""Tests for configured local time helpers."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from unittest.mock import patch

from vigil.clock import local_display_date, local_today_iso


class _FixedDateTime:
    """Fixed datetime class for patching vigil.clock.datetime."""

    @classmethod
    def now(cls, tz: tzinfo | None) -> datetime:
        """Return a UTC instant that is still the prior day in New York."""
        return datetime(2026, 3, 10, 0, 30, tzinfo=UTC).astimezone(tz)


class TestClock:
    """Verify date helpers use the configured local timezone."""

    def test_local_today_uses_configured_timezone(self) -> None:
        with (
            patch("vigil.clock.VIGIL_TIMEZONE", "America/New_York"),
            patch("vigil.clock.datetime", _FixedDateTime),
        ):
            assert local_today_iso() == "2026-03-09"

    def test_display_date_uses_configured_timezone(self) -> None:
        with (
            patch("vigil.clock.VIGIL_TIMEZONE", "America/New_York"),
            patch("vigil.clock.datetime", _FixedDateTime),
        ):
            assert local_display_date() == "Monday, March 9, 2026"
