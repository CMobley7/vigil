"""Tests for weather_fetch.py."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from weather_fetch import (
    _celsius_to_fahrenheit,
    _wmo_lookup,
    fetch_weather,
    main,
)

# --- Fixtures ---


def _mock_api_response() -> dict[str, Any]:
    """Build a minimal Open-Meteo API response."""
    return {
        "hourly": {
            "time": [f"2026-03-10T{h:02d}:00" for h in range(24)],
            "temperature_2m": [10.0 + h for h in range(24)],
            "precipitation_probability": [h * 2 for h in range(24)],
            "weather_code": [0] * 12 + [61] * 12,
            "wind_speed_10m": [15.0] * 24,
        },
        "daily": {
            "time": [f"2026-03-{10 + d:02d}" for d in range(10)],
            "weather_code": [0, 1, 2, 3, 45, 61, 71, 80, 95, 0],
            "temperature_2m_max": [20.0 + d for d in range(10)],
            "temperature_2m_min": [5.0 + d for d in range(10)],
            "precipitation_probability_max": [10 * d for d in range(10)],
        },
    }


# --- Tests ---


class TestFetchReturnsValidJson:
    def test_output_has_required_keys(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_api_response()
        mock_resp.raise_for_status.return_value = None

        with patch("weather_fetch.httpx.get", return_value=mock_resp):
            result = fetch_weather()

        assert "generated_at" in result
        assert "today_hourly" in result
        assert "ten_day_forecast" in result
        assert "location" in result


class TestHourlyHas24Entries:
    def test_hourly_count(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_api_response()
        mock_resp.raise_for_status.return_value = None

        with patch("weather_fetch.httpx.get", return_value=mock_resp):
            result = fetch_weather()

        assert len(result["today_hourly"]) == 24


class TestForecastHas10Entries:
    def test_forecast_count(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_api_response()
        mock_resp.raise_for_status.return_value = None

        with patch("weather_fetch.httpx.get", return_value=mock_resp):
            result = fetch_weather()

        assert len(result["ten_day_forecast"]) == 10


class TestWmoCodeToEmojiMapping:
    @pytest.mark.parametrize(
        ("code", "expected_icon"),
        [
            (0, "☀️"),
            (61, "🌧️"),
            (95, "⛈️"),
            (999, "❓"),
        ],
    )
    def test_wmo_lookup(self, code: int, expected_icon: str) -> None:
        icon, _desc = _wmo_lookup(code)
        assert icon == expected_icon


class TestCelsiusToFahrenheitConversion:
    @pytest.mark.parametrize(
        ("celsius", "fahrenheit"),
        [
            (0, 32),
            (100, 212),
            (-40, -40),
            (37, 99),
        ],
    )
    def test_conversion(self, celsius: float, fahrenheit: int) -> None:
        assert _celsius_to_fahrenheit(celsius) == fahrenheit


class TestApiTimeoutLogsWarning:
    def test_timeout_produces_error_json(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import httpx

        with (
            patch(
                "weather_fetch.httpx.get",
                side_effect=httpx.TimeoutException("Connection timed out"),
            ),
            pytest.raises(SystemExit),
        ):
            main()

        captured = capsys.readouterr()
        import json

        output = json.loads(captured.out)
        assert "error" in output
        assert output["today_hourly"] == []
        assert output["ten_day_forecast"] == []


class TestEnvVarDefaults:
    def test_missing_weather_lat_uses_default(self) -> None:
        import weather_fetch

        assert weather_fetch.LATITUDE == pytest.approx(35.2271)
        assert weather_fetch.LONGITUDE == pytest.approx(-80.8431)


class TestSafeFloatInvalidInput:
    def test_non_numeric_exits(self) -> None:
        from fm_config import safe_float

        with pytest.raises(SystemExit):
            safe_float("_TEST_BAD_VAR", "not_a_number")
