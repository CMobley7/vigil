"""Evaluator functions for the Financial Health Monitor.

Each evaluator takes structured data from a fetcher and returns a list of
alert dicts with severity, category, condition, details, and action.
"""

from __future__ import annotations

import re
from typing import Any

from vigil.config import (
    AVUV_SP500_LAG,
    BITCOIN_CEILING,
    BITCOIN_FLOOR,
    CAPEX_CUT_THRESHOLD,
    DRIFT_REBALANCE,
    DRIFT_REDIRECT,
    IBIT_MAX_PCT_OF_401K,
    INFLATION_THRESHOLD,
    KNOWN_VENDORS,
    LARGE_TRANSACTION_THRESHOLD,
    LOW_BALANCE_THRESHOLD,
    NLR_DIP_THRESHOLD,
    SAHM_RULE_THRESHOLD,
    TARGETS_BY_CATEGORY,
    UNEMPLOYMENT_RECESSION_THRESHOLD,
)

# Regex for bank transaction failure detection
FAIL_PATTERN = re.compile(r"\b(nsf|returned|failed|declined|bounced)\b")


def evaluate_account_red_flags(bank_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate red-flag conditions on bank transactions from OFX.

    Args:
        bank_data: Output of :func:`fetch_bank_data`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not bank_data or bank_data.get("source") != "ofx":
        return alerts

    # Low balance checks
    for bal in bank_data.get("balances", []):
        if bal["balance"] < LOW_BALANCE_THRESHOLD:
            alerts.append(
                {
                    "severity": "HIGH",
                    "category": "account",
                    "condition": f"Low balance on {bal['bank']}/{bal['account']}",
                    "details": (
                        f"Balance is ${bal['balance']:,.2f} "
                        f"(threshold: ${LOW_BALANCE_THRESHOLD:,.2f})"
                    ),
                    "action": (
                        f"Review {bal['bank']}/{bal['account']} and consider transfer."
                    ),
                }
            )

    # Large unknown transactions
    for txn in bank_data.get("transactions", []):
        if abs(txn["amount"]) > LARGE_TRANSACTION_THRESHOLD:
            payee = txn["name"]
            if payee not in KNOWN_VENDORS and payee != "Unknown":
                alerts.append(
                    {
                        "severity": "MEDIUM",
                        "category": "account",
                        "condition": (
                            f"Large transaction on {txn['bank']}/{txn['account']}"
                        ),
                        "details": (
                            f"${abs(txn['amount']):,.2f} to/from '{payee}' "
                            f"on {txn['date']}"
                        ),
                        "action": "Verify this transaction is expected.",
                    }
                )

    # Failed/returned transactions
    for txn in bank_data.get("transactions", []):
        memo_lower = (txn.get("memo") or "").lower()
        name_lower = (txn.get("name") or "").lower()
        combined = f"{name_lower} {memo_lower}"
        if FAIL_PATTERN.search(combined):
            alerts.append(
                {
                    "severity": "HIGH",
                    "category": "account",
                    "condition": (
                        f"Possible failed payment on {txn['bank']}/{txn['account']}"
                    ),
                    "details": (
                        f"Transaction '{txn['name']}' on "
                        f"{txn['date']}: {txn.get('memo', '')}"
                    ),
                    "action": "Investigate immediately — possible missed payment.",
                }
            )

    return alerts


def evaluate_portfolio_drift(
    brokerage_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Check each ticker's actual weight vs. target using SnapTrade positions.

    Uses true portfolio weights from brokerage position data (not price proxies).

    Args:
        brokerage_data: Output of :func:`fetch_brokerage_data`.

    Returns:
        List of alert dicts with drift severity.
    """
    alerts: list[dict[str, Any]] = []

    if not brokerage_data:
        return alerts

    for account in brokerage_data.get("accounts", []):
        category = account.get("category")
        if not category:
            continue

        targets = TARGETS_BY_CATEGORY.get(category)
        if not targets:
            continue

        account_name = account.get("name", "Unknown")
        total_value = account.get("total_value", 0)
        if total_value <= 0:
            continue

        for holding in account.get("holdings", []):
            ticker = holding.get("ticker")
            if not ticker or ticker not in targets:
                continue

            actual_pct = holding.get("actual_pct", 0.0)
            target_pct = targets[ticker]
            drift = abs(actual_pct - target_pct)

            if drift >= DRIFT_REBALANCE:
                direction = "overweight" if actual_pct > target_pct else "underweight"
                alerts.append(
                    {
                        "severity": "HIGH",
                        "category": "drift",
                        "condition": f"{ticker} rebalance needed in {account_name}",
                        "details": (
                            f"{ticker}: actual {actual_pct:.1f}%, "
                            f"target {target_pct:.1f}% "
                            f"(drift {drift:.1f}%, {direction}). "
                            f"Threshold: ±{DRIFT_REBALANCE}%."
                        ),
                        "action": (
                            f"Sell {direction} position and rebalance "
                            f"{ticker} in {account_name}."
                        ),
                    }
                )
            elif drift >= DRIFT_REDIRECT:
                direction = "overweight" if actual_pct > target_pct else "underweight"
                alerts.append(
                    {
                        "severity": "MEDIUM",
                        "category": "drift",
                        "condition": (
                            f"{ticker} redirect contributions in {account_name}"
                        ),
                        "details": (
                            f"{ticker}: actual {actual_pct:.1f}%, "
                            f"target {target_pct:.1f}% "
                            f"(drift {drift:.1f}%, {direction}). "
                            f"Threshold: ±{DRIFT_REDIRECT}%."
                        ),
                        "action": (
                            f"Direct next 2-3 contributions to "
                            f"{'underweight' if actual_pct < target_pct else 'other'} "
                            f"positions in {account_name}."
                        ),
                    }
                )
            # drift between DRIFT_NOISE (3%) and DRIFT_REDIRECT (5%) → monitor only

    return alerts


def evaluate_mid_year_triggers(
    market_data: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate mid-year triggers from Section VIII.d of the portfolio doc.

    Args:
        market_data: Output of :func:`fetch_market_data`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not market_data:
        return alerts

    btc_data = market_data.get("BTC-USD", {})
    btc_price = btc_data.get("price")

    dxy_data = market_data.get("DX-Y.NYB", {})
    dxy_price = dxy_data.get("price")

    spy_data = market_data.get("SPY", {})
    spy_return_3m = spy_data.get("return_3m")

    nlr_data = market_data.get("NLR", {})
    nlr_price = nlr_data.get("price")
    nlr_high = nlr_data.get("recent_high")

    avuv_data = market_data.get("AVUV", {})
    avuv_return_3m = avuv_data.get("return_3m")

    # Trigger: Bitcoin below $50k → trim IBIT to 3%
    if btc_price and btc_price < BITCOIN_FLOOR:
        alerts.append(
            {
                "severity": "HIGH",
                "category": "trigger",
                "condition": "Bitcoin below $50k",
                "details": (
                    f"BTC at ${btc_price:,.0f}. "
                    f"Trigger: trim IBIT to 3%, add to SMH or NLR."
                ),
                "action": "Trim IBIT to 3% of 401k, redistribute to SMH or NLR.",
            }
        )

    # Trigger: Bitcoin over $200k → trim IBIT to 4%
    if btc_price and btc_price > BITCOIN_CEILING:
        alerts.append(
            {
                "severity": "HIGH",
                "category": "trigger",
                "condition": "Bitcoin above $200k",
                "details": (
                    f"BTC at ${btc_price:,.0f}. "
                    f"Trigger: trim IBIT to 4%, profits into COWZ."
                ),
                "action": "Trim IBIT to 4%, move profits into COWZ.",
            }
        )

    # Trigger: DXY back above 105 sustained → reduce VEA to 5%
    if dxy_price and dxy_price > 105:
        alerts.append(
            {
                "severity": "MEDIUM",
                "category": "trigger",
                "condition": "DXY above 105",
                "details": (
                    f"DXY at {dxy_price:.1f}. "
                    f"Trigger: reduce VEA to 5%, add to AVUV and COWZ."
                ),
                "action": (
                    "If sustained, reduce VEA from 11% to 5%, add to AVUV and COWZ."
                ),
            }
        )

    # Trigger: NLR down 20%+ from recent high → buy the dip
    if nlr_price and nlr_high and nlr_high > 0:
        nlr_drawdown = ((nlr_price - nlr_high) / nlr_high) * 100
        if nlr_drawdown <= NLR_DIP_THRESHOLD:
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "category": "trigger",
                    "condition": "NLR down 20%+ from recent high",
                    "details": (
                        f"NLR at ${nlr_price:.2f}, recent high ${nlr_high:.2f} "
                        f"({nlr_drawdown:.1f}% drawdown). Trigger: buy the dip."
                    ),
                    "action": (
                        "If no fundamental change, next 3 contributions go to NLR."
                    ),
                }
            )

    # Trigger: AVUV trails S&P by 8%+ over 3 months → trim to 8%
    if avuv_return_3m is not None and spy_return_3m is not None:
        avuv_vs_spy = avuv_return_3m - spy_return_3m
        if avuv_vs_spy <= AVUV_SP500_LAG:
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "category": "trigger",
                    "condition": "AVUV trailing S&P by 8%+",
                    "details": (
                        f"AVUV 3-month return: {avuv_return_3m:+.1f}%, "
                        f"SPY: {spy_return_3m:+.1f}% (gap: {avuv_vs_spy:+.1f}%). "
                        f"Trigger: trim AVUV to 8%, add to SMH."
                    ),
                    "action": "Trim AVUV from 12% to 8%, add to SMH.",
                }
            )

    return alerts


def evaluate_recession_signals(
    recession_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Evaluate recession indicators from FRED.

    Portfolio trigger (Section VIII.d):
    "Recession signals (unemployment >5%%, inverted curve):
     raise COWZ to 20%%, fund from SMH and AVUV."

    Args:
        recession_data: Output of :func:`fetch_recession_indicators`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not recession_data:
        return alerts

    # Check unemployment rate
    unrate = recession_data.get("unemployment_rate", {})
    if (
        unrate.get("value") is not None
        and unrate["value"] > UNEMPLOYMENT_RECESSION_THRESHOLD
    ):
        alerts.append(
            {
                "severity": "HIGH",
                "category": "recession",
                "condition": (
                    f"Unemployment above {UNEMPLOYMENT_RECESSION_THRESHOLD}%"
                ),
                "details": (
                    f"Unemployment rate at {unrate['value']:.1f}% "
                    f"(as of {unrate['date']}). "
                    f"Threshold: {UNEMPLOYMENT_RECESSION_THRESHOLD}%."
                ),
                "action": "Raise COWZ to 20%, fund from SMH and AVUV.",
            }
        )

    # Check yield curve inversion
    spread = recession_data.get("yield_curve_spread", {})
    if spread.get("inverted"):
        alerts.append(
            {
                "severity": "HIGH",
                "category": "recession",
                "condition": "Yield curve inverted (10Y-2Y spread negative)",
                "details": (
                    f"10Y-2Y Treasury spread at {spread['value']:.2f}% "
                    f"(as of {spread['date']}). "
                    f"An inverted yield curve has preceded every recession since 1955."
                ),
                "action": "Raise COWZ to 20%, fund from SMH and AVUV.",
            }
        )

    # Check Sahm Rule
    sahm = recession_data.get("sahm_rule", {})
    if sahm.get("triggered"):
        alerts.append(
            {
                "severity": "CRITICAL",
                "category": "recession",
                "condition": "Sahm Rule recession indicator triggered",
                "details": (
                    f"Sahm Rule indicator at {sahm['value']:.2f} "
                    f"(as of {sahm['date']}). Threshold: {SAHM_RULE_THRESHOLD}. "
                    f"This indicator has correctly identified every US recession "
                    f"since 1970 in real time."
                ),
                "action": (
                    "RECESSION LIKELY. Immediately raise COWZ to 20%, "
                    "fund from SMH and AVUV. Review full defensive playbook."
                ),
            }
        )

    return alerts


def evaluate_hyperscaler_capex(
    capex_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Evaluate hyperscaler capex trends.

    Portfolio trigger (Section VIII.d):
    "Hyperscaler Q2 earnings cut capex guidance >15%%:
     trim SMH from 25%% to 18%%, add to VEA and COWZ."

    Args:
        capex_data: Output of :func:`fetch_hyperscaler_capex`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not capex_data:
        return alerts

    cutters: list[dict[str, Any]] = []
    for ticker, data in capex_data.items():
        yoy = data.get("yoy_change_pct")
        if yoy is not None and yoy <= CAPEX_CUT_THRESHOLD:
            cutters.append(
                {
                    "ticker": ticker,
                    "capex_millions": data["latest_capex_millions"],
                    "yoy_change_pct": yoy,
                    "quarter": data["quarter_date"],
                }
            )

    if cutters:
        cutter_names = ", ".join(c["ticker"] for c in cutters)
        details_parts: list[str] = []
        for c in cutters:
            details_parts.append(
                f"{c['ticker']}: ${c['capex_millions']:,.0f}M capex "
                f"({c['yoy_change_pct']:+.1f}% YoY, Q ending {c['quarter']})"
            )

        alerts.append(
            {
                "severity": "HIGH",
                "category": "capex",
                "condition": f"Hyperscaler capex cut >15% detected: {cutter_names}",
                "details": "; ".join(details_parts),
                "action": "Trim SMH from 25% to 18%, add to VEA and COWZ.",
            }
        )

    return alerts


def evaluate_inflation_trigger(
    recession_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Evaluate inflation trigger from Section VIII.d.

    Portfolio trigger:
    "Fed pauses cuts, inflation back above 3%:
     trim VEA from 11% to 5%, add to COWZ."

    Args:
        recession_data: Output of :func:`fetch_recession_indicators`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not recession_data:
        return alerts

    inflation = recession_data.get("inflation", {})
    if inflation.get("above_threshold"):
        alerts.append(
            {
                "severity": "HIGH",
                "category": "trigger",
                "condition": f"Inflation above {INFLATION_THRESHOLD}%",
                "details": (
                    f"CPI YoY at {inflation['value']:.2f}% "
                    f"(as of {inflation['date']}). "
                    f"Threshold: {INFLATION_THRESHOLD}%. "
                    f"Fed likely to pause or reverse cuts."
                ),
                "action": "Trim VEA from 11% to 5%, add to COWZ.",
            }
        )

    return alerts


def evaluate_ibit_concentration(
    brokerage_data: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Evaluate IBIT concentration in 401k accounts.

    Portfolio trigger (Section VIII.d):
    "IBIT appreciates past 10% of 401k portfolio:
     mechanically trim back to 7%, add to NLR."

    Uses SnapTrade positions to compute IBIT's actual weight in accounts
    that hold it. If weight exceeds ``IBIT_MAX_PCT_OF_401K``, triggers
    a mechanical trim alert.

    Args:
        brokerage_data: Output of :func:`fetch_brokerage_data`.

    Returns:
        List of alert dicts.
    """
    alerts: list[dict[str, Any]] = []

    if not brokerage_data:
        return alerts

    for account in brokerage_data.get("accounts", []):
        account_name = account.get("name", "Unknown")
        total_value = account.get("total_value", 0)
        if total_value <= 0:
            continue

        for holding in account.get("holdings", []):
            ticker = holding.get("ticker")
            if ticker != "IBIT":
                continue

            actual_pct = holding.get("actual_pct", 0.0)
            if actual_pct > IBIT_MAX_PCT_OF_401K:
                alerts.append(
                    {
                        "severity": "HIGH",
                        "category": "trigger",
                        "condition": (
                            f"IBIT exceeds {IBIT_MAX_PCT_OF_401K}% "
                            f"of portfolio in {account_name}"
                        ),
                        "details": (
                            f"IBIT at {actual_pct:.1f}% of {account_name} "
                            f"(${holding.get('market_value', 0):,.0f}). "
                            f"Max allowed: {IBIT_MAX_PCT_OF_401K}%."
                        ),
                        "action": (
                            f"Mechanically trim IBIT to 7% in {account_name}, "
                            f"add proceeds to NLR."
                        ),
                    }
                )

    return alerts
