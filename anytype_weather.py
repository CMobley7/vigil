"""Build Markdown body for the Weather sub-object.

Transforms the output of :func:`weather_fetch.fetch_weather` into a
Markdown string for the 🌤️ Weather sub-object.
"""

from __future__ import annotations

from typing import Any

from anytype_client import md_heading, md_paragraph, md_table


def build_weather_body(weather: dict[str, Any]) -> str:
    """Build Markdown body for the 🌤️ Weather sub-object.

    Args:
        weather: Output of ``fetch_weather()``.

    Returns:
        Markdown string for the weather body.
    """
    sections: list[str] = []

    hourly = weather.get("today_hourly", [])
    forecast = weather.get("ten_day_forecast", [])

    # -- Today summary from first forecast entry --
    if forecast:
        today = forecast[0]
        icon = today.get("icon", "🌤️")
        desc = today.get("description", "")
        high = _fmt_temp(today.get("high_f"))
        low = _fmt_temp(today.get("low_f"))
        sections.append(
            md_heading(f"Today — {icon} {desc}, High {high} / Low {low}", level=2)
        )
    else:
        sections.append(md_heading("Today — Weather data unavailable", level=2))

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
            sections.append(md_table(headers, rows))
        else:
            sections.append(md_paragraph("No hourly data in 6 AM - 10 PM range."))
    else:
        sections.append(md_paragraph("Hourly forecast data unavailable."))

    # -- 10-day forecast table --
    sections.append(md_heading("10-Day Forecast", level=2))

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
        sections.append(md_table(headers, rows))
    else:
        sections.append(md_paragraph("10-day forecast data unavailable."))

    return "\n\n".join(sections)


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
