"""Build Notion blocks for the Finance sub-page.

Transforms ``financial_monitor.py`` JSON output into Notion block dicts
for the 📈 Stocks & Finances sub-page (data tables only — the LLM adds
editorial content in Phase 2).

CLI usage (called by Phase 2 LLM after writing editorial)::

    python3 notion_finance.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from fm_config import NOTION_TOKEN
from notion_client import NotionClient, heading_2, paragraph, table

logger = logging.getLogger(__name__)

_STATE_FILE = Path("/tmp/daily_brief_state.json")  # noqa: S108
_FM_CACHE_FILE = Path("/tmp/daily_brief_fm_output.json")  # noqa: S108


def build_finance_blocks(fm_output: dict[str, Any]) -> list[dict[str, Any]]:
    """Build Notion blocks for the 📈 Stocks & Finances sub-page.

    Creates portfolio summary table, account balances table, and recent
    transactions table.  Editorial sections (Action Items, Economy
    Snapshot) are added by the LLM in Phase 2 before this script runs.

    Args:
        fm_output: Parsed JSON output of ``financial_monitor.py``.

    Returns:
        List of Notion block dicts.
    """
    blocks: list[dict[str, Any]] = []

    # -- Portfolio Summary --
    blocks.extend(_build_portfolio_section(fm_output))

    # -- Account Balances --
    blocks.extend(_build_balances_section(fm_output))

    # -- Recent Transactions --
    blocks.extend(_build_transactions_section(fm_output))

    return blocks


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_portfolio_section(
    fm_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build portfolio summary blocks.

    Args:
        fm_output: Financial monitor output dict.
    """
    blocks: list[dict[str, Any]] = []
    blocks.append(heading_2("📊 Portfolio Summary"))

    total = fm_output.get("total_portfolio_value")
    if total is not None:
        blocks.append(paragraph(f"Total Portfolio Value: ${total:,.2f}"))

    brokerage = fm_output.get("brokerage_data", {})
    holdings: list[dict[str, Any]] = brokerage.get("holdings", [])

    if holdings:
        headers = [
            "Ticker",
            "Shares",
            "Price",
            "Avg Cost",
            "Gain/Loss",
            "Gain%",
            "Weight",
            "Target",
        ]
        rows: list[list[str]] = []
        for h in holdings:
            gain = h.get("unrealized_gain", 0)
            gain_pct = h.get("unrealized_gain_pct", 0)
            rows.append(
                [
                    str(h.get("ticker", "")),
                    str(h.get("shares", "")),
                    _fmt_dollar(h.get("current_price")),
                    _fmt_dollar(h.get("avg_cost")),
                    _fmt_dollar(gain),
                    f"{gain_pct:+.1f}%" if gain_pct is not None else "—",
                    _fmt_pct(h.get("actual_weight")),
                    _fmt_pct(h.get("target_weight")),
                ]
            )
        blocks.append(table(headers, rows))
    else:
        blocks.append(paragraph("No holdings data available."))

    return blocks


def _build_balances_section(
    fm_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build account balances blocks.

    Args:
        fm_output: Financial monitor output dict.
    """
    blocks: list[dict[str, Any]] = []
    blocks.append(heading_2("💰 Account Balances"))

    bank_data = fm_output.get("bank_data", {})
    balances: list[dict[str, Any]] = bank_data.get("balances", [])

    if balances:
        headers = ["Bank", "Account", "Balance"]
        rows = [
            [
                str(b.get("bank", "")),
                str(b.get("account", "")),
                _fmt_dollar(b.get("balance")),
            ]
            for b in balances
        ]
        blocks.append(table(headers, rows))
    else:
        blocks.append(paragraph("No account balance data available."))

    return blocks


def _build_transactions_section(
    fm_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build recent transactions blocks.

    Args:
        fm_output: Financial monitor output dict.
    """
    blocks: list[dict[str, Any]] = []

    bank_data = fm_output.get("bank_data", {})
    txns: list[dict[str, Any]] = bank_data.get("transactions", [])

    count = len(txns)
    blocks.append(heading_2(f"🏦 Recent Transactions (last {count})"))

    if txns:
        headers = ["Date", "Amount", "Description", "Bank"]
        rows = [
            [
                str(t.get("date", "")),
                _fmt_dollar(t.get("amount")),
                str(t.get("description", "")),
                str(t.get("bank", "")),
            ]
            for t in txns
        ]
        blocks.append(table(headers, rows))
    else:
        blocks.append(paragraph("No recent transactions available."))

    return blocks


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _fmt_dollar(val: float | int | None) -> str:
    """Format a dollar amount.

    Args:
        val: Dollar amount, or None.
    """
    if val is None:
        return "—"
    return f"${val:,.2f}"


def _fmt_pct(val: float | int | None) -> str:
    """Format a percentage.

    Args:
        val: Percentage value, or None.
    """
    if val is None:
        return "—"
    return f"{val:.1f}%"


# ---------------------------------------------------------------------------
# CLI entrypoint — called by Phase 2 LLM after writing editorial
# ---------------------------------------------------------------------------


def main() -> None:
    """Append finance data tables to existing 📈 page.

    Reads ``/tmp/daily_brief_state.json`` for the finance page ID and
    ``/tmp/daily_brief_fm_output.json`` for cached FM data.  Called by the
    Phase 2 LLM as its final step to place data tables below editorial.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set -- aborting")
        sys.exit(1)

    try:
        state = json.loads(_STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Cannot read state file: %s", exc)
        sys.exit(1)

    try:
        fm_output = json.loads(_FM_CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Cannot read FM cache file: %s", exc)
        sys.exit(1)

    finance_page_id: str | None = state.get("sub_pages", {}).get("finance")
    if not finance_page_id:
        logger.error("No finance page ID in state file")
        sys.exit(1)

    client = NotionClient(NOTION_TOKEN)
    client.append_blocks(finance_page_id, build_finance_blocks(fm_output))


if __name__ == "__main__":  # pragma: no cover
    main()
