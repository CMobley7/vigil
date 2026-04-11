"""Build Markdown body for the Finance sub-object.

Transforms ``vigil.financial.monitor`` JSON output into a Markdown string
for the 📈 Stocks & Finances sub-object (data tables only — the LLM adds
editorial content in Phase 2).

CLI usage (called by Phase 2 LLM after writing editorial)::

    python -m vigil.anytype.finance
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from vigil.anytype.client import AnytypeClient, md_heading, md_paragraph, md_table
from vigil.config import ANYTYPE_API_KEY

logger = logging.getLogger(__name__)

_STATE_FILE = Path("/tmp/daily_brief_state.json")  # noqa: S108
_FM_CACHE_FILE = Path("/tmp/daily_brief_fm_output.json")  # noqa: S108


def build_finance_body(fm_output: dict[str, Any]) -> str:
    """Build Markdown body for the 📈 Stocks & Finances sub-object.

    Creates portfolio summary table, account balances table, and recent
    transactions table.  Editorial sections (Action Items, Economy
    Snapshot) are added by the LLM in Phase 2 before this script runs.

    Args:
        fm_output: Parsed JSON output of ``vigil.financial.monitor``.

    Returns:
        Markdown string for the finance body.
    """
    sections: list[str] = []

    sections.extend(_build_portfolio_section(fm_output))
    sections.extend(_build_balances_section(fm_output))
    sections.extend(_build_transactions_section(fm_output))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_portfolio_section(fm_output: dict[str, Any]) -> list[str]:
    """Build portfolio summary Markdown sections.

    Args:
        fm_output: Financial monitor output dict.
    """
    sections: list[str] = [md_heading("📊 Portfolio Summary", level=2)]

    total = fm_output.get("total_portfolio_value")
    if total is not None:
        sections.append(md_paragraph(f"Total Portfolio Value: ${total:,.2f}"))

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
        sections.append(md_table(headers, rows))
    else:
        sections.append(md_paragraph("No holdings data available."))

    return sections


def _build_balances_section(fm_output: dict[str, Any]) -> list[str]:
    """Build account balances Markdown sections.

    Args:
        fm_output: Financial monitor output dict.
    """
    sections: list[str] = [md_heading("💰 Account Balances", level=2)]

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
        sections.append(md_table(headers, rows))
    else:
        sections.append(md_paragraph("No account balance data available."))

    return sections


def _build_transactions_section(fm_output: dict[str, Any]) -> list[str]:
    """Build recent transactions Markdown sections.

    Args:
        fm_output: Financial monitor output dict.
    """
    bank_data = fm_output.get("bank_data", {})
    txns: list[dict[str, Any]] = bank_data.get("transactions", [])

    count = len(txns)
    sections: list[str] = [
        md_heading(f"🏦 Recent Transactions (last {count})", level=2)
    ]

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
        sections.append(md_table(headers, rows))
    else:
        sections.append(md_paragraph("No recent transactions available."))

    return sections


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
    """Update finance object body with data tables.

    Reads ``/tmp/daily_brief_state.json`` for the finance object ID and
    ``/tmp/daily_brief_fm_output.json`` for cached FM data.  Called by the
    Phase 2 LLM as its final step to place data tables below editorial.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not ANYTYPE_API_KEY:
        logger.error("ANYTYPE_API_KEY not set -- aborting")
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

    space_id: str = state.get("space_id", "")
    finance_object_id: str | None = state.get("sub_objects", {}).get("finance")

    if not finance_object_id:
        logger.error("No finance object ID in state file")
        sys.exit(1)

    client = AnytypeClient(ANYTYPE_API_KEY)
    client.update_object(
        space_id,
        finance_object_id,
        body=build_finance_body(fm_output),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
