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
from typing import Any

from vigil.anytype.client import AnytypeClient, md_heading, md_paragraph, md_table
from vigil.config import ANYTYPE_API_KEY, TARGETS_BY_CATEGORY
from vigil.runtime import FM_CACHE_FILE, STATE_FILE

logger = logging.getLogger(__name__)

_STATE_FILE = STATE_FILE
_FM_CACHE_FILE = FM_CACHE_FILE


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

    holdings = _normalize_holdings(fm_output)

    if holdings:
        headers = [
            "Account",
            "Ticker",
            "Shares",
            "Price",
            "Market Value",
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
                    str(h.get("account", "")),
                    str(h.get("ticker", "")),
                    str(h.get("shares", "")),
                    _fmt_dollar(h.get("price")),
                    _fmt_dollar(h.get("market_value")),
                    _fmt_dollar(h.get("avg_cost")),
                    _fmt_dollar(gain),
                    f"{gain_pct:+.1f}%" if gain_pct is not None else "—",
                    _fmt_pct(h.get("actual_pct")),
                    _fmt_pct(h.get("target_pct")),
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
                _transaction_description(t),
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


def _normalize_holdings(fm_output: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize legacy and current financial monitor holdings shapes."""
    brokerage = fm_output.get("brokerage_data")
    if not isinstance(brokerage, dict):
        return []

    accounts = brokerage.get("accounts")
    if isinstance(accounts, list):
        normalized: list[dict[str, Any]] = []
        for account in accounts:
            if not isinstance(account, dict):
                continue
            account_name = str(account.get("name", ""))
            category = account.get("category")
            targets = (
                TARGETS_BY_CATEGORY.get(category, {})
                if isinstance(category, str)
                else {}
            )
            for holding in account.get("holdings", []):
                if not isinstance(holding, dict):
                    continue
                ticker = holding.get("ticker")
                normalized.append(
                    {
                        "account": account_name,
                        "ticker": ticker,
                        "shares": holding.get("shares"),
                        "price": holding.get("price"),
                        "market_value": holding.get("market_value"),
                        "avg_cost": holding.get("avg_cost"),
                        "unrealized_gain": holding.get("unrealized_gain"),
                        "unrealized_gain_pct": holding.get("unrealized_gain_pct"),
                        "actual_pct": holding.get("actual_pct"),
                        "target_pct": targets.get(ticker)
                        if isinstance(ticker, str)
                        else None,
                    }
                )
        return normalized

    legacy_holdings = brokerage.get("holdings", [])
    if not isinstance(legacy_holdings, list):
        return []

    return [
        {
            "account": str(holding.get("account", "")),
            "ticker": holding.get("ticker"),
            "shares": holding.get("shares"),
            "price": holding.get("current_price"),
            "market_value": holding.get("market_value"),
            "avg_cost": holding.get("avg_cost"),
            "unrealized_gain": holding.get("unrealized_gain"),
            "unrealized_gain_pct": holding.get("unrealized_gain_pct"),
            "actual_pct": holding.get("actual_weight"),
            "target_pct": holding.get("target_weight"),
        }
        for holding in legacy_holdings
        if isinstance(holding, dict)
    ]


def _transaction_description(txn: dict[str, Any]) -> str:
    """Return the best available transaction description."""
    for key in ("description", "name", "memo"):
        value = txn.get(key)
        if value:
            return str(value)
    return ""


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

    Reads the private runtime state file for the finance object ID and cached
    FM data.  Called by the Phase 2 LLM as its final step to place data tables
    below editorial.
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
