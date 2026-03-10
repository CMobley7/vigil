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
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIG — All via environment variables
# ---------------------------------------------------------------------------

# SnapTrade credentials
SNAPTRADE_CONSUMER_KEY = os.environ.get("SNAPTRADE_CONSUMER_KEY", "")
SNAPTRADE_CLIENT_ID = os.environ.get("SNAPTRADE_CLIENT_ID", "")
SNAPTRADE_USER_ID = os.environ.get("SNAPTRADE_USER_ID", "")
SNAPTRADE_USER_SECRET = os.environ.get("SNAPTRADE_USER_SECRET", "")

# Account name mapping (SnapTrade account names → portfolio categories)
ACCOUNT_MAP: dict[str, str] = json.loads(os.environ.get("ACCOUNT_MAP", "{}"))

# OFX bank config — JSON array of banks, each with accounts
OFX_BANKS_CONFIG: list[dict[str, Any]] = json.loads(
    os.environ.get("OFX_BANKS_CONFIG", "[]")
)

CHECKLIST_PATH = os.environ.get("CHECKLIST_PATH", "data/financial_checklist.md")

# FRED API key — free from https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# How many days of transactions to look back for red-flag checks
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))

# Large transaction threshold (in dollars)
LARGE_TRANSACTION_THRESHOLD = float(
    os.environ.get("LARGE_TRANSACTION_THRESHOLD", "500")
)

# Low balance threshold (in dollars)
LOW_BALANCE_THRESHOLD = float(os.environ.get("LOW_BALANCE_THRESHOLD", "1000"))

# Known vendors (pipe-separated) — transactions from these won't trigger alerts
KNOWN_VENDORS: list[str] = (
    os.environ.get("KNOWN_VENDORS", "").split("|")
    if os.environ.get("KNOWN_VENDORS")
    else []
)

# ---------------------------------------------------------------------------
# PORTFOLIO TARGETS — From Chairman's Final Portfolio Allocation (March 2026)
# ---------------------------------------------------------------------------

# Overall 401k targets (Section III)
OVERALL_TARGETS: dict[str, float] = {
    "SMH": 25.0,
    "VGT": 20.0,
    "COWZ": 15.0,
    "AVUV": 12.0,
    "VEA": 11.0,
    "NLR": 10.0,
    "IBIT": 7.0,
}

# Per-account targets
ROTH_TARGETS: dict[str, float] = {
    "SMH": 38.0,
    "VGT": 30.0,
    "AVUV": 18.0,
    "IBIT": 10.0,
    "VEA": 4.0,
}

TRADITIONAL_TARGETS: dict[str, float] = {
    "COWZ": 45.0,
    "NLR": 30.0,
    "VEA": 25.0,
}

HSA_TARGETS: dict[str, float] = {
    "SMH": 38.0,
    "VGT": 30.0,
    "AVUV": 18.0,
    "IBIT": 10.0,
    "VEA": 4.0,
}

# Map category names (from ACCOUNT_MAP values) to target dicts
TARGETS_BY_CATEGORY: dict[str, dict[str, float]] = {
    "Roth": ROTH_TARGETS,
    "Traditional": TRADITIONAL_TARGETS,
    "HSA": HSA_TARGETS,
}

# Drift thresholds (Section VIII.c)
DRIFT_NOISE = 3.0  # +/- 3% → do nothing
DRIFT_REDIRECT = 5.0  # +/- 5% → next 2-3 contributions go to underweight
DRIFT_REBALANCE = 8.0  # +/- 8% → sell overweight, buy underweight

# Contribution priority if tied (Section VIII.b)
ROTH_PRIORITY = ["SMH", "VGT", "AVUV", "IBIT", "VEA"]
TRADITIONAL_PRIORITY = ["COWZ", "NLR", "VEA"]

# Mid-year trigger thresholds (Section VIII.d)
BITCOIN_FLOOR = 50_000
BITCOIN_CEILING = 200_000
IBIT_MAX_PCT_OF_401K = 10.0
NLR_DIP_THRESHOLD = -20.0  # percent from recent high
AVUV_SP500_LAG = -8.0  # percent underperformance over 3 months

# Recession trigger thresholds (Section VIII.d)
UNEMPLOYMENT_RECESSION_THRESHOLD = 5.0  # unemployment > 5%
SAHM_RULE_THRESHOLD = 0.50  # Sahm rule >= 0.50 signals recession

# Hyperscaler capex guidance tracking (Section VIII.d)
HYPERSCALER_TICKERS = ["MSFT", "AMZN", "META", "GOOGL"]
CAPEX_CUT_THRESHOLD = -15.0  # percent YoY decline signals a cut

# Benchmark for year-end review (Section VIII.e)
BENCHMARK: dict[str, int] = {"VTI": 45, "IWM": 14, "VXUS": 21, "BND": 20}

# All portfolio tickers
ALL_TICKERS = ["SMH", "VGT", "COWZ", "AVUV", "VEA", "NLR", "IBIT"]

# Supplemental tickers for trigger checks
TRIGGER_TICKERS = ["BTC-USD", "DX-Y.NYB", "SPY"]

# Regex for bank transaction failure detection (evaluate_account_red_flags)
_FAIL_PATTERN = re.compile(r"\b(nsf|returned|failed|declined|bounced)\b")


# ---------------------------------------------------------------------------
# DATA FETCHERS
# ---------------------------------------------------------------------------


def parse_checklist(path: str) -> dict[str, list[str]]:
    """Parse the markdown financial checklist into structured conditions.

    Args:
        path: Filesystem path to the markdown checklist file.

    Returns:
        Dict with ``red_flags`` and ``accounts`` lists.
    """
    checklist: dict[str, list[str]] = {"red_flags": [], "accounts": []}
    try:
        content = Path(path).read_text()
    except FileNotFoundError:
        return checklist

    current_section: str | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if "## Red Flags" in stripped:
            current_section = "red_flags"
        elif "## Accounts" in stripped:
            current_section = "accounts"
        elif current_section == "red_flags" and stripped.startswith("- ["):
            condition = re.sub(r"^- \[.\]\s*", "", stripped)
            checklist["red_flags"].append(condition)
        elif current_section == "accounts" and stripped.startswith("- "):
            account_name = stripped.lstrip("- ").strip()
            checklist["accounts"].append(account_name)

    return checklist


def fetch_brokerage_data() -> dict[str, Any] | None:  # pragma: no cover
    """Fetch brokerage positions from SnapTrade.

    Returns a dict with per-account positions and drift data,
    or ``None`` if SnapTrade credentials are missing or the call fails.
    """
    if not all(
        [
            SNAPTRADE_CONSUMER_KEY,
            SNAPTRADE_CLIENT_ID,
            SNAPTRADE_USER_ID,
            SNAPTRADE_USER_SECRET,
        ]
    ):
        logger.warning("SnapTrade credentials not configured — skipping brokerage data")
        return None

    try:  # pragma: no cover
        from snaptrade_client import SnapTrade  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("snaptrade-python-sdk not installed")
        return None

    try:  # pragma: no cover
        snaptrade = SnapTrade(
            consumer_key=SNAPTRADE_CONSUMER_KEY,
            client_id=SNAPTRADE_CLIENT_ID,
        )

        accounts = snaptrade.account_information.list_user_accounts(
            user_id=SNAPTRADE_USER_ID,
            user_secret=SNAPTRADE_USER_SECRET,
        )

        accounts_data: list[dict[str, Any]] = []
        for account in accounts:
            account_name = getattr(account, "name", str(account.id))
            category = ACCOUNT_MAP.get(account_name)
            if category is None:
                logger.warning(
                    "Unmapped SnapTrade account: %s — skipping drift check",
                    account_name,
                )

            positions = snaptrade.account_information.get_user_account_positions(
                user_id=SNAPTRADE_USER_ID,
                user_secret=SNAPTRADE_USER_SECRET,
                account_id=account.id,
            )

            holdings: list[dict[str, Any]] = []
            total_value = 0.0
            for pos in positions:
                ticker = getattr(pos.symbol, "ticker", None) if pos.symbol else None
                market_value = float(pos.market_value) if pos.market_value else 0.0
                total_value += market_value
                holdings.append(
                    {
                        "ticker": ticker,
                        "shares": float(pos.units) if pos.units else 0.0,
                        "price": float(pos.price) if pos.price else 0.0,
                        "market_value": market_value,
                    }
                )

            # Calculate actual percentages
            for holding in holdings:
                if total_value > 0:
                    holding["actual_pct"] = round(
                        (holding["market_value"] / total_value) * 100, 2
                    )
                else:
                    holding["actual_pct"] = 0.0

            accounts_data.append(
                {
                    "name": account_name,
                    "category": category,
                    "total_value": round(total_value, 2),
                    "holdings": holdings,
                }
            )

        return {"accounts": accounts_data, "source": "snaptrade"}

    except Exception as exc:
        logger.warning("SnapTrade fetch failed: %s", exc)
        return None


def fetch_bank_data() -> dict[str, Any] | None:  # pragma: no cover
    """Fetch bank transactions via OFX Direct Connect.

    Loops over all banks and accounts defined in ``OFX_BANKS_CONFIG``.
    Returns aggregated transaction data or ``None`` if no banks configured
    or all fetches fail.
    """
    if not OFX_BANKS_CONFIG:
        logger.warning("OFX_BANKS_CONFIG not configured — skipping bank data")
        return None

    try:  # pragma: no cover
        from ofxtools.OFXClient import OFXClient  # type: ignore[import-not-found]
        from ofxtools.Parser import OFXTree  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("ofxtools not installed")
        return None

    cutoff_date = datetime.now(tz=UTC) - timedelta(days=LOOKBACK_DAYS)
    all_transactions: list[dict[str, Any]] = []
    bank_balances: list[dict[str, Any]] = []
    errors: list[str] = []

    for bank in OFX_BANKS_CONFIG:
        bank_name = bank.get("name", "Unknown")
        try:
            client = OFXClient(
                url=bank["url"],
                org=bank["org"],
                fid=bank["fid"],
            )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            errors.append(f"{bank_name}: client init failed: {exc}")
            continue

        for acct in bank.get("accounts", []):
            acct_id = acct.get("id", "unknown")
            try:
                request = client.statement_request(
                    user=bank["user"],
                    password=bank["pass"],
                    acctid=acct_id,
                    accttype=acct.get("type", "CHECKING"),
                    dtstart=cutoff_date,
                )
                response = client.download(request)
                parser = OFXTree()
                parser.parse(response)
                ofx = parser.convert()

                for stmt in ofx.statements:
                    # Capture balance
                    if hasattr(stmt, "available_balance") and stmt.available_balance:
                        bank_balances.append(
                            {
                                "bank": bank_name,
                                "account": acct_id,
                                "balance": float(stmt.available_balance),
                            }
                        )

                    for txn in stmt.transactions:
                        all_transactions.append(
                            {
                                "bank": bank_name,
                                "account": acct_id,
                                "date": str(txn.dtposted.date())
                                if txn.dtposted
                                else None,
                                "amount": float(txn.trnamt) if txn.trnamt else 0.0,
                                "name": txn.name or "Unknown",
                                "memo": txn.memo or "",
                            }
                        )
            except Exception as exc:
                errors.append(f"{bank_name}/{acct_id}: {exc}")
                logger.warning(
                    "OFX fetch failed for %s/%s: %s",
                    bank_name,
                    acct_id,
                    exc,
                )

    if errors:
        logger.warning("OFX errors: %s", "; ".join(errors))

    if not all_transactions and not bank_balances:
        return None

    return {
        "transactions": all_transactions,
        "balances": bank_balances,
        "errors": errors,
        "source": "ofx",
    }


def fetch_market_data() -> dict[str, dict[str, Any]] | None:  # pragma: no cover
    """Fetch current prices for all portfolio + trigger tickers via yfinance.

    Returns:
        Dict of ``{ticker: {price, change_pct, return_3m, recent_high}}``,
        or ``None`` if yfinance is unavailable.
    """
    try:  # pragma: no cover
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("yfinance not installed")
        return None

    try:  # pragma: no cover
        all_symbols = ALL_TICKERS + TRIGGER_TICKERS + list(BENCHMARK.keys())
        data: dict[str, dict[str, Any]] = {}

        for ticker in all_symbols:
            t = yf.Ticker(ticker)
            info = t.fast_info
            hist_3m = t.history(period="3mo")

            price = info.last_price if info.last_price else None
            prev_close = info.previous_close if info.previous_close else None
            change_pct = None
            if price and prev_close:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)

            # 3-month return for drift and trigger calculations
            return_3m = None
            if not hist_3m.empty and len(hist_3m) > 1:
                start_price = hist_3m["Close"].iloc[0]
                end_price = hist_3m["Close"].iloc[-1]
                if start_price > 0:
                    return_3m = round(
                        ((end_price - start_price) / start_price) * 100, 2
                    )

            # Recent high (for NLR dip calculation)
            recent_high = None
            if not hist_3m.empty:
                recent_high = round(float(hist_3m["High"].max()), 2)

            data[ticker] = {
                "price": round(price, 2) if price else None,
                "change_pct": change_pct,
                "return_3m": return_3m,
                "recent_high": recent_high,
            }

        return data

    except Exception as exc:
        logger.warning("yfinance fetch failed: %s", exc)
        return None


def fetch_recession_indicators() -> dict[str, Any] | None:  # pragma: no cover
    """Fetch recession indicators from the FRED API.

    Series used:
      - UNRATE:       Civilian Unemployment Rate (monthly, %%)
      - T10Y2Y:       10-Year minus 2-Year Treasury Spread (daily, %%)
      - SAHMREALTIME: Sahm Rule Recession Indicator (monthly)

    Returns:
        Dict with indicator values, or ``None`` on failure.
    """
    if not FRED_API_KEY:
        return None

    try:  # pragma: no cover
        from fredapi import Fred  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("fredapi not installed")
        return None

    try:  # pragma: no cover
        fred = Fred(api_key=FRED_API_KEY)

        # Unemployment rate (most recent value)
        unrate = fred.get_series("UNRATE")
        latest_unrate = float(unrate.dropna().iloc[-1]) if not unrate.empty else None
        unrate_date = (
            str(unrate.dropna().index[-1].date()) if not unrate.empty else None
        )

        # 10Y-2Y Treasury spread (yield curve)
        t10y2y = fred.get_series("T10Y2Y")
        latest_spread = float(t10y2y.dropna().iloc[-1]) if not t10y2y.empty else None
        spread_date = (
            str(t10y2y.dropna().index[-1].date()) if not t10y2y.empty else None
        )

        # Sahm Rule recession indicator
        sahm = fred.get_series("SAHMREALTIME")
        latest_sahm = float(sahm.dropna().iloc[-1]) if not sahm.empty else None
        sahm_date = str(sahm.dropna().index[-1].date()) if not sahm.empty else None

        return {
            "unemployment_rate": {
                "value": latest_unrate,
                "date": unrate_date,
                "threshold": UNEMPLOYMENT_RECESSION_THRESHOLD,
            },
            "yield_curve_spread": {
                "value": latest_spread,
                "date": spread_date,
                "inverted": (latest_spread < 0 if latest_spread is not None else None),
            },
            "sahm_rule": {
                "value": latest_sahm,
                "date": sahm_date,
                "threshold": SAHM_RULE_THRESHOLD,
                "triggered": (
                    latest_sahm >= SAHM_RULE_THRESHOLD
                    if latest_sahm is not None
                    else None
                ),
            },
        }

    except Exception as exc:
        logger.warning("FRED API fetch failed: %s", exc)
        return None


def fetch_hyperscaler_capex() -> dict[str, Any] | None:  # pragma: no cover
    """Pull recent quarterly capex for hyperscalers via yfinance.

    Checks if any hyperscaler's capex declined >15%% YoY,
    triggering the "cut capex guidance" alert.

    Returns:
        Dict of ``{ticker: {latest_capex_millions, quarter_date, yoy_change_pct}}``,
        or ``None`` on failure.
    """
    try:  # pragma: no cover
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError:
        return None

    try:  # pragma: no cover
        capex_data: dict[str, Any] = {}

        for ticker in HYPERSCALER_TICKERS:
            t = yf.Ticker(ticker)
            cf = t.quarterly_cashflow
            if cf is None or cf.empty:
                continue

            capex_row = None
            for label in [
                "Capital Expenditure",
                "CapitalExpenditure",
                "capitalExpenditure",
                "Capital Expenditures",
            ]:
                if label in cf.index:
                    capex_row = cf.loc[label]
                    break

            if capex_row is None:
                continue

            valid_quarters = capex_row.dropna()
            if len(valid_quarters) < 2:
                continue

            latest_q = valid_quarters.iloc[0]
            latest_q_date = str(valid_quarters.index[0].date())

            # YoY comparison (4 quarters ago) or QoQ fallback
            yoy_change = None
            if len(valid_quarters) >= 5:
                year_ago_q = valid_quarters.iloc[4]
                if year_ago_q != 0:
                    yoy_change = round(
                        ((abs(latest_q) - abs(year_ago_q)) / abs(year_ago_q)) * 100,
                        1,
                    )
            elif len(valid_quarters) >= 2:
                prev_q = valid_quarters.iloc[1]
                if prev_q != 0:
                    yoy_change = round(
                        ((abs(latest_q) - abs(prev_q)) / abs(prev_q)) * 100, 1
                    )

            capex_data[ticker] = {
                "latest_capex_millions": round(abs(float(latest_q)) / 1e6, 0),
                "quarter_date": latest_q_date,
                "yoy_change_pct": yoy_change,
            }

        return capex_data if capex_data else None

    except Exception as exc:
        logger.warning("Hyperscaler capex fetch failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# EVALUATORS
# ---------------------------------------------------------------------------


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
        if _FAIL_PATTERN.search(combined):
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
    brokerage_data: dict[str, Any],
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
            # drift < DRIFT_NOISE → do nothing (noise)

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
        if output["status"] == "partial_data":
            output["status"] = "partial_data"  # keep partial_data if sources failed
        else:
            output["status"] = "alerts_triggered"
    elif not system_warnings and "MEDIUM" not in severities:
        output["status"] = "all_clear"

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()
