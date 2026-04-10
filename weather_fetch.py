#!/usr/bin/env python3
"""Fetch weather data from Open-Meteo and output JSON for OpenClaw.

Uses the Open-Meteo free API (no key needed) via ``httpx``.
Outputs JSON with today's hourly breakdown and a 10-day forecast,
including WMO weather code → emoji mapping for Notion pages.

Usage:
    python3 weather_fetch.py

Configuration via environment variables:
    WEATHER_LAT  — latitude  (default: 35.2271, Charlotte NC)
    WEATHER_LON  — longitude (default: -80.8431)
    WEATHER_TZ   — timezone  (default: America/New_York)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

import httpx

from fm_config import _safe_float

logger = logging.getLogger(__name__)


# Configuration via env vars
LATITUDE = _safe_float("WEATHER_LAT", "35.2271")
LONGITUDE = _safe_float("WEATHER_LON", "-80.8431")
TIMEZONE = os.environ.get("WEATHER_TZ", "America/New_York")

# Open-Meteo API endpoint (free, no key needed)
API_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 10  # seconds

# WMO weather code → (emoji, description) mapping
# https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("☀️", "Clear sky"),
    1: ("🌤️", "Mainly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Depositing rime fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Moderate drizzle"),
    55: ("🌦️", "Dense drizzle"),
    56: ("🌦️", "Light freezing drizzle"),
    57: ("🌦️", "Dense freezing drizzle"),
    61: ("🌧️", "Slight rain"),
    63: ("🌧️", "Moderate rain"),
    65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Light freezing rain"),
    67: ("🌧️", "Heavy freezing rain"),
    71: ("🌨️", "Slight snow"),
    73: ("🌨️", "Moderate snow"),
    75: ("🌨️", "Heavy snow"),
    77: ("🌨️", "Snow grains"),
    80: ("🌧️", "Slight rain showers"),
    81: ("🌧️", "Moderate rain showers"),
    82: ("🌧️", "Violent rain showers"),
    85: ("🌨️", "Slight snow showers"),
    86: ("🌨️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Thunderstorm with slight hail"),
    99: ("⛈️", "Thunderstorm with heavy hail"),
}


def _wmo_lookup(code: int) -> tuple[str, str]:
    """Return (emoji, description) for a WMO weather code.

    Args:
        code: WMO weather interpretation code.

    Returns:
        Tuple of (emoji icon, human-readable description).
    """
    return WMO_CODES.get(code, ("❓", f"Unknown code {code}"))


def _celsius_to_fahrenheit(celsius: float) -> int:
    """Convert Celsius to Fahrenheit, rounded to int.

    Args:
        celsius: Temperature in degrees Celsius.

    Returns:
        Temperature in degrees Fahrenheit (rounded).
    """
    return round(celsius * 9 / 5 + 32)


def fetch_weather() -> dict[str, Any]:
    """Fetch weather data from Open-Meteo and return structured dict.

    Returns:
        Dict with ``generated_at``, ``location``, ``today_hourly``,
        and ``ten_day_forecast`` keys.

    Raises:
        httpx.HTTPError: On network or API errors.
    """
    params: dict[str, str | float | int] = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation_probability",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
            ]
        ),
        "timezone": TIMEZONE,
        "forecast_days": 10,
    }

    resp = httpx.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # Parse hourly data (first 24 entries = today)
    hourly = data.get("hourly", {})
    hourly_times = hourly.get("time", [])[:24]
    hourly_temps = hourly.get("temperature_2m", [])[:24]
    hourly_precip = hourly.get("precipitation_probability", [])[:24]
    hourly_codes = hourly.get("weather_code", [])[:24]
    hourly_wind = hourly.get("wind_speed_10m", [])[:24]

    today_hourly = []
    for i, time_str in enumerate(hourly_times):
        code = int(hourly_codes[i]) if i < len(hourly_codes) else 0
        icon, description = _wmo_lookup(code)
        hour_dt = datetime.fromisoformat(time_str)
        temp_c = hourly_temps[i] if i < len(hourly_temps) else None
        precip = hourly_precip[i] if i < len(hourly_precip) else None
        wind_kph = hourly_wind[i] if i < len(hourly_wind) else None
        today_hourly.append(
            {
                "hour": hour_dt.strftime("%-I %p"),
                "temp_f": _celsius_to_fahrenheit(temp_c)
                if temp_c is not None
                else None,
                "precip_pct": precip,
                "wind_mph": round(wind_kph * 0.621371)
                if wind_kph is not None
                else None,
                "weather_code": code,
                "icon": icon,
                "description": description,
            }
        )

    # Parse daily data (10-day forecast)
    daily = data.get("daily", {})
    daily_times = daily.get("time", [])
    daily_codes = daily.get("weather_code", [])
    daily_highs = daily.get("temperature_2m_max", [])
    daily_lows = daily.get("temperature_2m_min", [])
    daily_precip = daily.get("precipitation_probability_max", [])

    ten_day_forecast = []
    for i, date_str in enumerate(daily_times):
        code = int(daily_codes[i]) if i < len(daily_codes) else 0
        icon, description = _wmo_lookup(code)
        day_dt = datetime.fromisoformat(date_str)
        high_c = daily_highs[i] if i < len(daily_highs) else None
        low_c = daily_lows[i] if i < len(daily_lows) else None
        precip = daily_precip[i] if i < len(daily_precip) else None
        ten_day_forecast.append(
            {
                "date": day_dt.strftime("%A %m/%d"),
                "high_f": _celsius_to_fahrenheit(high_c)
                if high_c is not None
                else None,
                "low_f": _celsius_to_fahrenheit(low_c) if low_c is not None else None,
                "precip_pct": precip,
                "weather_code": code,
                "icon": icon,
                "description": description,
            }
        )

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "location": {"lat": LATITUDE, "lon": LONGITUDE},
        "today_hourly": today_hourly,
        "ten_day_forecast": ten_day_forecast,
    }


def main() -> None:
    """Fetch weather and print JSON to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        result = fetch_weather()
        print(json.dumps(result, indent=2))
    except httpx.HTTPError as exc:
        logger.warning("Weather API request failed: %s", exc)
        error_output = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "error": f"Weather API request failed: {exc}",
            "location": {"lat": LATITUDE, "lon": LONGITUDE},
            "today_hourly": [],
            "ten_day_forecast": [],
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
