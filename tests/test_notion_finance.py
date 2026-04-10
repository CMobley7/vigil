"""Tests for notion_finance module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from notion_finance import build_finance_blocks, main


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
                    "date": "2026-03-09",
                    "amount": -150.00,
                    "description": "Grocery Store",
                    "bank": "Chase",
                },
                {
                    "date": "2026-03-08",
                    "amount": -800.00,
                    "description": "Rent Payment",
                    "bank": "Chase",
                },
            ],
        },
    }


class TestBuildFinanceBlocks:
    """Tests for build_finance_blocks."""

    def test_has_portfolio_heading(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        headings = [b for b in blocks if b["type"] == "heading_2"]
        titles = [h["heading_2"]["rich_text"][0]["text"]["content"] for h in headings]
        assert any("Portfolio" in t for t in titles)

    def test_has_total_value_paragraph(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        paras = [b for b in blocks if b["type"] == "paragraph"]
        texts = [p["paragraph"]["rich_text"][0]["text"]["content"] for p in paras]
        assert any("$150,000.00" in t for t in texts)

    def test_portfolio_table_has_correct_columns(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        tables = [b for b in blocks if b["type"] == "table"]
        assert len(tables) >= 1
        portfolio_table = tables[0]
        assert portfolio_table["table"]["table_width"] == 8

    def test_portfolio_table_has_holdings(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        tables = [b for b in blocks if b["type"] == "table"]
        portfolio_table = tables[0]
        # header + 2 holdings = 3 rows
        assert len(portfolio_table["table"]["children"]) == 3

    def test_balances_table_present(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        headings = [b for b in blocks if b["type"] == "heading_2"]
        titles = [h["heading_2"]["rich_text"][0]["text"]["content"] for h in headings]
        assert any("Balance" in t for t in titles)

    def test_transactions_table_present(self) -> None:
        blocks = build_finance_blocks(_sample_fm_output())
        headings = [b for b in blocks if b["type"] == "heading_2"]
        titles = [h["heading_2"]["rich_text"][0]["text"]["content"] for h in headings]
        assert any("Transactions" in t for t in titles)

    def test_empty_data_shows_placeholders(self) -> None:
        blocks = build_finance_blocks({})
        paras = [b for b in blocks if b["type"] == "paragraph"]
        texts = [p["paragraph"]["rich_text"][0]["text"]["content"] for p in paras]
        assert any("No holdings" in t for t in texts)
        assert any("No account" in t for t in texts)
        assert any("No recent" in t for t in texts)


# ---------------------------------------------------------------------------
# CLI entrypoint tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() CLI entrypoint."""

    @patch("notion_finance.NOTION_TOKEN", "test-token")
    @patch("notion_finance.NotionClient")
    def test_main_appends_to_correct_page(
        self,
        mock_client_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Verify main reads state + FM cache and appends to finance page."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.append_blocks.return_value = None

        state = {"sub_pages": {"finance": "page-123"}}
        fm_data: dict[str, Any] = {
            "brokerage_data": {},
            "bank_data": {},
        }

        state_file = tmp_path / "state.json"
        fm_file = tmp_path / "fm.json"
        state_file.write_text(json.dumps(state))
        fm_file.write_text(json.dumps(fm_data))

        with (
            patch("notion_finance._STATE_FILE", state_file),
            patch("notion_finance._FM_CACHE_FILE", fm_file),
        ):
            main()

        mock_client.append_blocks.assert_called_once()
        args = mock_client.append_blocks.call_args[0]
        assert args[0] == "page-123"
        assert len(args[1]) > 0  # non-empty block list

    @patch("notion_finance.NOTION_TOKEN", "test-token")
    def test_main_exits_on_missing_state_file(self, tmp_path: Path) -> None:
        """Verify SystemExit when state file doesn't exist."""
        missing = tmp_path / "nonexistent.json"
        with (
            patch("notion_finance._STATE_FILE", missing),
            pytest.raises(SystemExit),
        ):
            main()

    @patch("notion_finance.NOTION_TOKEN", "test-token")
    def test_main_exits_on_no_finance_page_id(self, tmp_path: Path) -> None:
        """Verify SystemExit when finance page ID is null."""
        state = {"sub_pages": {"finance": None}}
        fm_data: dict[str, Any] = {"brokerage_data": {}}

        state_file = tmp_path / "state.json"
        fm_file = tmp_path / "fm.json"
        state_file.write_text(json.dumps(state))
        fm_file.write_text(json.dumps(fm_data))

        with (
            patch("notion_finance._STATE_FILE", state_file),
            patch("notion_finance._FM_CACHE_FILE", fm_file),
            pytest.raises(SystemExit),
        ):
            main()
