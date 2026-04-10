"""Build Notion blocks for the Weather sub-page.

Transforms the output of :func:`weather_fetch.fetch_weather` into
Notion block dicts for the 🌤️ Weather sub-page.
"""

from __future__ import annotations

from typing import Any

from notion_client import heading_2, paragraph, table


def build_weather_blocks(weather: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Notion blocks for the 🌤️ Weather sub-page.

    Args:
        weather: Output of ``fetch_weather()``.

    Returns:
        List of Notion block dicts.
    """
    blocks: list[dict[str, Any]] = []

    hourly = weather.get("today_hourly", [])
    forecast = weather.get("ten_day_forecast", [])

    # -- Today summary from first forecast entry --
    if forecast:
        today = forecast[0]
        icon = today.get("icon", "🌤️")
        desc = today.get("description", "")
        high = _fmt_temp(today.get("high_f"))
        low = _fmt_temp(today.get("low_f"))
        blocks.append(heading_2(f"Today — {icon} {desc}, High {high} / Low {low}"))
    else:
        blocks.append(heading_2("Today — Weather data unavailable"))

    # -- Hourly table (6 AM - 10 PM only) --
    if hourly:
        filtered = [h for h in hourly if _hour_in_range(h.get("hour", ""))]
        if filtered:
            headers = ["Hour", "Temp", "Precip%", "Wind", "Conditions"]
            rows = [
                [
                    h.get("hour", ""),
                    _fmt_temp(h.get("temp_f")),
                    _fmt_pct(h.get("precip_pct")),
                    _fmt_wind(h.get("wind_mph")),
                    f"{h.get('icon', '')} {h.get('description', '')}",
                ]
                for h in filtered
            ]
            blocks.append(table(headers, rows))
        else:
            blocks.append(paragraph("No hourly data in 6 AM - 10 PM range."))
    else:
        blocks.append(paragraph("Hourly forecast data unavailable."))

    # -- 10-day forecast table --
    blocks.append(heading_2("10-Day Forecast"))

    if forecast:
        headers = ["Day", "High", "Low", "Precip%", "Conditions"]
        rows = [
            [
                day.get("date", ""),
                _fmt_temp(day.get("high_f")),
                _fmt_temp(day.get("low_f")),
                _fmt_pct(day.get("precip_pct")),
                f"{day.get('icon', '')} {day.get('description', '')}",
            ]
            for day in forecast
        ]
        blocks.append(table(headers, rows))
    else:
        blocks.append(paragraph("10-day forecast data unavailable."))

    return blocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_hour_label(label: str) -> int | None:
    """Parse hour label like '6 AM' → 6, '10 PM' → 22.

    Args:
        label: Hour string from weather data.

    Returns:
        Hour as 24-hour int, or None if unparseable.
    """
    label = label.strip().upper()
    try:
        parts = label.split()
        if len(parts) != 2:
            return None
        num = int(parts[0])
        meridiem = parts[1]
        if meridiem == "AM":
            return num if num != 12 else 0
        if meridiem == "PM":
            return num + 12 if num != 12 else 12
    except (ValueError, IndexError):
        return None
    return None


def _hour_in_range(label: str) -> bool:
    """Check if an hour label falls in 6 AM - 10 PM.

    Args:
        label: Hour string from weather data.
    """
    hour = _parse_hour_label(label)
    if hour is None:
        return False
    return 6 <= hour <= 22


def _fmt_temp(val: float | int | None) -> str:
    """Format temperature value.

    Args:
        val: Temperature in Fahrenheit, or None.
    """
    if val is None:
        return "—"
    return f"{round(val)}°F"


def _fmt_pct(val: float | int | None) -> str:
    """Format percentage value.

    Args:
        val: Percentage, or None.
    """
    if val is None:
        return "—"
    return f"{round(val)}%"


def _fmt_wind(val: float | int | None) -> str:
    """Format wind speed.

    Args:
        val: Wind speed in mph, or None.
    """
    if val is None:
        return "—"
    return f"{round(val)} mph"
