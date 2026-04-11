"""Tests for anytype_finance module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from anytype_finance import build_finance_body, main


def _sample_fm_output() -> dict[str, Any]:
    """Return a minimal financial_monitor.py output."""
    return {
        "total_portfolio_value": 150000.00,
        "brokerage_data": {
            "holdings": [
                {
                    "ticker": "VTI",
                    "shares": 100,
                    "current_price": 250.00,
                    "avg_cost": 220.00,
                    "unrealized_gain": 3000.00,
                    "unrealized_gain_pct": 13.6,
                    "actual_weight": 60.0,
                    "target_weight": 55.0,
                },
                {
                    "ticker": "VXUS",
                    "shares": 50,
                    "current_price": 60.00,
                    "avg_cost": 55.00,
                    "unrealized_gain": 250.00,
                    "unrealized_gain_pct": 9.1,
                    "actual_weight": 20.0,
                    "target_weight": 25.0,
                },
            ],
        },
        "bank_data": {
            "balances": [
                {
                    "bank": "Chase",
                    "account": "Checking",
                    "balance": 5000.00,
                },
            ],
            "transactions": [
                {
                    "date": "2026-04-09",
                    "amount": -150.00,
                    "description": "Grocery Store",
                    "bank": "Chase",
                },
                {
                    "date": "2026-04-08",
                    "amount": -800.00,
                    "description": "Rent Payment",
                    "bank": "Chase",
                },
            ],
        },
    }


class TestBuildFinanceBody:
    """Tests for build_finance_body."""

    def test_returns_string(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert isinstance(result, str)

    def test_has_portfolio_heading(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "Portfolio" in result

    def test_has_total_value(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "$150,000.00" in result

    def test_portfolio_table_has_ticker_columns(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "Ticker" in result
        assert "VTI" in result
        assert "VXUS" in result

    def test_balances_heading_present(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "Balance" in result

    def test_transactions_heading_present(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "Transactions" in result

    def test_empty_data_shows_placeholders(self) -> None:
        result = build_finance_body({})
        assert "No holdings" in result
        assert "No account" in result
        assert "No recent" in result

    def test_is_markdown_table(self) -> None:
        result = build_finance_body(_sample_fm_output())
        assert "| Ticker |" in result or "Ticker" in result


class TestMain:
    """Tests for the main() CLI entrypoint."""

    @patch("anytype_finance.ANYTYPE_API_KEY", "test-key")
    @patch("anytype_finance.AnytypeClient")
    def test_main_calls_update_object(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify main reads state + FM cache and calls update_object."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.update_object.return_value = None

        state = {
            "space_id": "space-1",
            "sub_objects": {"finance": "obj-123"},
        }
        fm_data: dict[str, Any] = {
            "brokerage_data": {},
            "bank_data": {},
        }

        state_file = tmp_path / "state.json"
        fm_file = tmp_path / "fm.json"
        state_file.write_text(json.dumps(state))
        fm_file.write_text(json.dumps(fm_data))

        with (
            patch("anytype_finance._STATE_FILE", state_file),
            patch("anytype_finance._FM_CACHE_FILE", fm_file),
        ):
            main()

        mock_client.update_object.assert_called_once()
        call_kwargs = mock_client.update_object.call_args
        # space_id, object_id positional, body keyword
        assert "obj-123" in str(call_kwargs)
        assert "space-1" in str(call_kwargs)

    @patch("anytype_finance.ANYTYPE_API_KEY", "test-key")
    def test_main_exits_on_missing_state_file(self, tmp_path: Path) -> None:
        """Verify SystemExit when state file doesn't exist."""
        missing = tmp_path / "nonexistent.json"
        with (
            patch("anytype_finance._STATE_FILE", missing),
            pytest.raises(SystemExit),
        ):
            main()

    @patch("anytype_finance.ANYTYPE_API_KEY", "test-key")
    def test_main_exits_on_no_finance_object_id(self, tmp_path: Path) -> None:
        """Verify SystemExit when finance object ID is null."""
        state = {"space_id": "sp-1", "sub_objects": {"finance": None}}
        fm_data: dict[str, Any] = {"brokerage_data": {}}

        state_file = tmp_path / "state.json"
        fm_file = tmp_path / "fm.json"
        state_file.write_text(json.dumps(state))
        fm_file.write_text(json.dumps(fm_data))

        with (
            patch("anytype_finance._STATE_FILE", state_file),
            patch("anytype_finance._FM_CACHE_FILE", fm_file),
            pytest.raises(SystemExit),
        ):
            main()

    @patch("anytype_finance.ANYTYPE_API_KEY", "")
    def test_main_exits_without_api_key(self, tmp_path: Path) -> None:
        """Verify SystemExit when ANYTYPE_API_KEY is empty."""
        state_file = tmp_path / "state.json"
        fm_file = tmp_path / "fm.json"
        state_file.write_text("{}")
        fm_file.write_text("{}")
        with (
            patch("anytype_finance._STATE_FILE", state_file),
            patch("anytype_finance._FM_CACHE_FILE", fm_file),
            pytest.raises(SystemExit),
        ):
            main()
