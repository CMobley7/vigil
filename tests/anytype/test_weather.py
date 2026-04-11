"""Tests for anytype_weather module."""

from __future__ import annotations

from typing import Any

from vigil.anytype.weather import (
    _fmt_pct,
    _fmt_temp,
    _fmt_wind,
    _hour_in_range,
    _parse_hour_label,
    build_weather_body,
)


def _sample_weather() -> dict[str, Any]:
    """Return a minimal weather response."""
    return {
        "today_hourly": [
            {
                "hour": "6 AM",
                "temp_f": 55,
                "precip_pct": 10,
                "wind_mph": 8,
                "icon": "☀️",
                "description": "Clear",
            },
            {
                "hour": "12 PM",
                "temp_f": 72,
                "precip_pct": 0,
                "wind_mph": 12,
                "icon": "🌤️",
                "description": "Partly cloudy",
            },
            {
                "hour": "3 AM",
                "temp_f": 45,
                "precip_pct": 0,
                "wind_mph": 5,
                "icon": "🌙",
                "description": "Clear",
            },
        ],
        "ten_day_forecast": [
            {
                "date": "Monday 04/10",
                "high_f": 75,
                "low_f": 55,
                "precip_pct": 10,
                "icon": "☀️",
                "description": "Clear",
            },
            {
                "date": "Tuesday 04/11",
                "high_f": 68,
                "low_f": 50,
                "precip_pct": 40,
                "icon": "🌧️",
                "description": "Rain",
            },
        ],
    }


class TestBuildWeatherBody:
    """Tests for build_weather_body."""

    def test_is_string(self) -> None:
        result = build_weather_body(_sample_weather())
        assert isinstance(result, str)

    def test_has_today_heading(self) -> None:
        result = build_weather_body(_sample_weather())
        assert "## " in result
        assert "75" in result  # high temp
        assert "55" in result  # low temp

    def test_hourly_table_present(self) -> None:
        result = build_weather_body(_sample_weather())
        # Markdown table has | separators
        assert "| Hour |" in result or "Hour" in result

    def test_3am_hourly_filtered_out(self) -> None:
        result = build_weather_body(_sample_weather())
        # "3 AM" should NOT appear in hourly section
        # The hourly table only shows 6AM-10PM entries
        lines = result.splitlines()
        hourly_lines = [line for line in lines if "3 AM" in line]
        assert hourly_lines == []

    def test_forecast_heading_present(self) -> None:
        result = build_weather_body(_sample_weather())
        assert "10-Day Forecast" in result

    def test_empty_weather_shows_placeholder(self) -> None:
        result = build_weather_body({})
        assert "unavailable" in result.lower() or "Unavailable" in result

    def test_empty_forecast_shows_placeholder(self) -> None:
        weather: dict[str, Any] = {"today_hourly": [], "ten_day_forecast": []}
        result = build_weather_body(weather)
        assert "unavailable" in result.lower() or "Unavailable" in result

    def test_all_hourly_outside_range_shows_placeholder(self) -> None:
        weather: dict[str, Any] = {
            "today_hourly": [
                {
                    "hour": "2 AM",
                    "temp_f": 40,
                    "precip_pct": 0,
                    "wind_mph": 3,
                    "icon": "🌙",
                    "description": "Clear",
                },
                {
                    "hour": "11 PM",
                    "temp_f": 42,
                    "precip_pct": 0,
                    "wind_mph": 4,
                    "icon": "🌙",
                    "description": "Clear",
                },
            ],
            "ten_day_forecast": [
                {
                    "date": "Monday",
                    "high_f": 70,
                    "low_f": 50,
                    "precip_pct": 0,
                    "icon": "☀️",
                    "description": "Clear",
                },
            ],
        }
        result = build_weather_body(weather)
        assert "6 AM - 10 PM" in result


class TestParseHourLabel:
    """Tests for _parse_hour_label."""

    def test_morning(self) -> None:
        assert _parse_hour_label("6 AM") == 6

    def test_noon(self) -> None:
        assert _parse_hour_label("12 PM") == 12

    def test_midnight(self) -> None:
        assert _parse_hour_label("12 AM") == 0

    def test_afternoon(self) -> None:
        assert _parse_hour_label("3 PM") == 15

    def test_invalid(self) -> None:
        assert _parse_hour_label("bad") is None

    def test_single_part_returns_none(self) -> None:
        assert _parse_hour_label("6") is None

    def test_three_parts_returns_none(self) -> None:
        assert _parse_hour_label("6 AM EST") is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_hour_label("six AM") is None


class TestHourInRange:
    """Tests for _hour_in_range."""

    def test_in_range(self) -> None:
        assert _hour_in_range("6 AM") is True
        assert _hour_in_range("10 PM") is True

    def test_out_of_range(self) -> None:
        assert _hour_in_range("3 AM") is False
        assert _hour_in_range("11 PM") is False

    def test_invalid_label_out_of_range(self) -> None:
        assert _hour_in_range("") is False
        assert _hour_in_range("nope") is False


class TestFormattingHelpers:
    """Tests for _fmt_temp, _fmt_pct, _fmt_wind with None inputs."""

    def test_fmt_temp_none(self) -> None:
        assert _fmt_temp(None) == "—"

    def test_fmt_temp_value(self) -> None:
        assert _fmt_temp(72) == "72°F"

    def test_fmt_pct_none(self) -> None:
        assert _fmt_pct(None) == "—"

    def test_fmt_pct_value(self) -> None:
        assert _fmt_pct(45) == "45%"

    def test_fmt_wind_none(self) -> None:
        assert _fmt_wind(None) == "—"

    def test_fmt_wind_value(self) -> None:
        assert _fmt_wind(12) == "12 mph"
