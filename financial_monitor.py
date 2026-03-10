#!/usr/bin/env python3
"""Financial Health Monitor for OpenClaw.

Connects to SnapTrade (brokerage positions/drift), OFX Direct Connect (bank
transactions), FRED (recession indicators), and yfinance (market data, capex).
Evaluates all conditions from the Chairman's Portfolio Allocation.

Usage:
    python3 financial_monitor.py

Outputs JSON to stdout for the LLM to evaluate.

Dependencies (see pyproject.toml):
    snaptrade-python-sdk, ofxtools, fredapi, yfinance

Configuration:
    Set environment variables — see implementation_plan.md Step 13b.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from fm_config import (
    ALL_TICKERS,
    CHECKLIST_PATH,
    DRIFT_NOISE,
    DRIFT_REBALANCE,
    DRIFT_REDIRECT,
    FRED_API_KEY,
    OFX_BANKS_CONFIG,
    OVERALL_TARGETS,
    SNAPTRADE_CONSUMER_KEY,
)
from fm_evaluators import (
    evaluate_account_red_flags,
    evaluate_hyperscaler_capex,
    evaluate_mid_year_triggers,
    evaluate_portfolio_drift,
    evaluate_recession_signals,
)
from fm_fetchers import (
    fetch_bank_data,
    fetch_brokerage_data,
    fetch_hyperscaler_capex,
    fetch_market_data,
    fetch_recession_indicators,
    parse_checklist,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SUMMARY & MAIN
# ---------------------------------------------------------------------------


def build_daily_summary(
    market_data: dict[str, dict[str, Any]],
    recession_data: dict[str, Any] | None = None,
    capex_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a human-readable daily portfolio summary.

    Args:
        market_data: Output of :func:`fetch_market_data`.
        recession_data: Output of :func:`fetch_recession_indicators`.
        capex_data: Output of :func:`fetch_hyperscaler_capex`.

    Returns:
        Summary dict with positions, BTC, DXY, indicators, and capex.
    """
    summary: dict[str, Any] = {
        "date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        "positions": {},
    }

    if not market_data:
        return summary

    for ticker in ALL_TICKERS:
        data = market_data.get(ticker, {})
        summary["positions"][ticker] = {
            "price": data.get("price"),
            "daily_change_pct": data.get("change_pct"),
            "return_3m_pct": data.get("return_3m"),
        }

    # Add Bitcoin and DXY for context
    btc = market_data.get("BTC-USD", {})
    if btc.get("price"):
        summary["bitcoin_usd"] = btc["price"]

    dxy = market_data.get("DX-Y.NYB", {})
    if dxy.get("price"):
        summary["dxy_index"] = dxy["price"]

    # Add recession indicators
    if recession_data:
        summary["recession_indicators"] = recession_data

    # Add hyperscaler capex summary
    if capex_data:
        summary["hyperscaler_capex"] = capex_data

    return summary


def main() -> None:
    """Run all data fetches and evaluations, output JSON to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    output: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "status": "ok",
        "alerts": [],
        "daily_summary": None,
        "brokerage_data": None,
        "bank_data": None,
        "checklist": None,
        "portfolio_config": {
            "overall_targets": OVERALL_TARGETS,
            "drift_thresholds": {
                "noise": DRIFT_NOISE,
                "redirect_contributions": DRIFT_REDIRECT,
                "force_rebalance": DRIFT_REBALANCE,
            },
        },
    }

    # 1. Parse the checklist
    checklist = parse_checklist(CHECKLIST_PATH)
    output["checklist"] = checklist

    # 2. Fetch market data (always needed for drift + triggers)
    market_data = fetch_market_data()
    if not market_data:
        output["alerts"].append(
            {
                "severity": "WARNING",
                "category": "system",
                "condition": "Market data unavailable",
                "details": "yfinance could not fetch current prices.",
                "action": "Check internet connectivity and yfinance installation.",
            }
        )
        output["market_data"] = None
    else:
        output["market_data"] = "fetched"  # data is large, just note it arrived

    # 3. Fetch brokerage data from SnapTrade
    brokerage_data = fetch_brokerage_data()
    output["brokerage_data"] = brokerage_data
    if brokerage_data is None and SNAPTRADE_CONSUMER_KEY:
        output["alerts"].append(
            {
                "severity": "WARNING",
                "category": "system",
                "condition": "SnapTrade brokerage data unavailable",
                "details": "Could not fetch brokerage positions from SnapTrade.",
                "action": "Check SnapTrade credentials and API status.",
            }
        )

    # 4. Fetch bank data from OFX
    bank_data = fetch_bank_data()
    output["bank_data"] = bank_data
    if bank_data is None and OFX_BANKS_CONFIG:
        output["alerts"].append(
            {
                "severity": "WARNING",
                "category": "system",
                "condition": "OFX bank data unavailable",
                "details": "Could not fetch bank transactions via OFX.",
                "action": "Check OFX bank config and credentials.",
            }
        )

    # 5. Fetch recession indicators from FRED
    recession_data = fetch_recession_indicators()
    if recession_data is None and FRED_API_KEY:
        output["alerts"].append(
            {
                "severity": "WARNING",
                "category": "system",
                "condition": "FRED recession data unavailable",
                "details": "Could not fetch recession indicators from FRED API.",
                "action": "Check FRED API key and internet connectivity.",
            }
        )
        output["recession_data"] = None
    else:
        output["recession_data"] = recession_data

    # 6. Fetch hyperscaler capex data
    capex_data = fetch_hyperscaler_capex()

    # 7. Build daily summary
    if market_data:
        output["daily_summary"] = build_daily_summary(
            market_data, recession_data, capex_data
        )

    # 8. Evaluate all conditions
    if bank_data:
        output["alerts"].extend(evaluate_account_red_flags(bank_data))
    if brokerage_data:
        output["alerts"].extend(evaluate_portfolio_drift(brokerage_data))
    if market_data:
        output["alerts"].extend(evaluate_mid_year_triggers(market_data))
    output["alerts"].extend(evaluate_recession_signals(recession_data))
    output["alerts"].extend(evaluate_hyperscaler_capex(capex_data))

    # 9. Set overall status based on data availability and alerts
    system_warnings = [a for a in output["alerts"] if a["category"] == "system"]
    if system_warnings:
        output["status"] = "partial_data"

    severities = [a["severity"] for a in output["alerts"]]
    if "CRITICAL" in severities:
        output["status"] = "critical"
    elif "HIGH" in severities:
        if output["status"] != "partial_data":
            output["status"] = "alerts_triggered"
    elif not system_warnings and "MEDIUM" not in severities:
        output["status"] = "all_clear"

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
