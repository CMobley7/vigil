"""Tests for notion_weather module."""

from __future__ import annotations

from typing import Any

from notion_weather import (
    _fmt_pct,
    _fmt_temp,
    _fmt_wind,
    _hour_in_range,
    _parse_hour_label,
    build_weather_blocks,
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
                "date": "Monday 03/10",
                "high_f": 75,
                "low_f": 55,
                "precip_pct": 10,
                "icon": "☀️",
                "description": "Clear",
            },
            {
                "date": "Tuesday 03/11",
                "high_f": 68,
                "low_f": 50,
                "precip_pct": 40,
                "icon": "🌧️",
                "description": "Rain",
            },
        ],
    }


class TestBuildWeatherBlocks:
    """Tests for build_weather_blocks."""

    def test_has_today_heading(self) -> None:
        blocks = build_weather_blocks(_sample_weather())
        heading = blocks[0]
        assert heading["type"] == "heading_2"
        text = heading["heading_2"]["rich_text"][0]["text"]["content"]
        assert "High 75" in text
        assert "Low 55" in text

    def test_hourly_table_filters_by_range(self) -> None:
        blocks = build_weather_blocks(_sample_weather())
        # Find table blocks
        tables = [b for b in blocks if b["type"] == "table"]
        assert len(tables) >= 1
        hourly_table = tables[0]
        # 3 AM should be filtered out, leaving 6 AM and 12 PM
        # 1 header + 2 data rows = 3 children
        children = hourly_table["table"]["children"]
        assert len(children) == 3  # header + 2 data rows

    def test_forecast_table_present(self) -> None:
        blocks = build_weather_blocks(_sample_weather())
        tables = [b for b in blocks if b["type"] == "table"]
        assert len(tables) == 2  # hourly + 10-day
        forecast_table = tables[1]
        # header + 2 forecast days = 3
        assert len(forecast_table["table"]["children"]) == 3

    def test_empty_weather_shows_placeholder(self) -> None:
        blocks = build_weather_blocks({})
        heading = blocks[0]
        text = heading["heading_2"]["rich_text"][0]["text"]["content"]
        assert "unavailable" in text


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


class TestParseHourLabelEdgeCases:
    """Edge cases for _parse_hour_label."""

    def test_single_part_returns_none(self) -> None:
        assert _parse_hour_label("6") is None

    def test_three_parts_returns_none(self) -> None:
        assert _parse_hour_label("6 AM EST") is None

    def test_non_numeric_returns_none(self) -> None:
        assert _parse_hour_label("six AM") is None


class TestBuildWeatherBlocksHourlyAllOutOfRange:
    """Test the 'no hourly data in range' paragraph branch."""

    def test_all_hourly_outside_range(self) -> None:
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
                    "date": "Monday 03/10",
                    "high_f": 70,
                    "low_f": 50,
                    "precip_pct": 0,
                    "icon": "☀️",
                    "description": "Clear",
                },
            ],
        }
        blocks = build_weather_blocks(weather)
        paragraphs = [b for b in blocks if b["type"] == "paragraph"]
        content = paragraphs[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "6 AM - 10 PM" in content


class TestBuildWeatherBlocksEmptyForecast:
    """Test the empty forecast fallback paragraph."""

    def test_no_forecast(self) -> None:
        weather: dict[str, Any] = {
            "today_hourly": [],
            "ten_day_forecast": [],
        }
        blocks = build_weather_blocks(weather)
        paragraphs = [b for b in blocks if b["type"] == "paragraph"]
        texts = [p["paragraph"]["rich_text"][0]["text"]["content"] for p in paragraphs]
        assert any("10-day forecast" in t for t in texts)
