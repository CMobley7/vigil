"""Centralised configuration for all Vigil modules.

Data file paths derive from ``VIGIL_DATA_DIR`` (default: ``data/``).
Portfolio targets are hardcoded from the Chairman's Portfolio Allocation
document (March 2026).  All other values are sourced from environment
variables.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIG — All via environment variables
# ---------------------------------------------------------------------------


def safe_json(var: str, default: str) -> Any:  # noqa: ANN401 — parsed JSON is inherently untyped
    """Parse JSON from an environment variable with a clear error on failure.

    Args:
        var: Environment variable name.
        default: Default JSON string if the variable is not set.

    Returns:
        Parsed JSON value.
    """
    raw = os.environ.get(var, default)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid JSON for %s: %r", var, raw)
        sys.exit(1)


def safe_int(var: str, default: str) -> int:
    """Parse an int from an environment variable with a clear error on failure.

    Args:
        var: Environment variable name.
        default: Default value if the variable is not set.

    Returns:
        Parsed integer value.
    """
    raw = os.environ.get(var, default)
    try:
        return int(raw)
    except ValueError:
        logger.error("Invalid integer for %s: %r", var, raw)
        sys.exit(1)


def safe_float(var: str, default: str) -> float:
    """Parse a float from an environment variable with a clear error on failure.

    Args:
        var: Environment variable name.
        default: Default value if the variable is not set.

    Returns:
        Parsed float value.
    """
    raw = os.environ.get(var, default)
    try:
        return float(raw)
    except ValueError:
        logger.error("Invalid float for %s: %r", var, raw)
        sys.exit(1)


# SnapTrade credentials
SNAPTRADE_CONSUMER_KEY = os.environ.get("SNAPTRADE_CONSUMER_KEY", "")
SNAPTRADE_CLIENT_ID = os.environ.get("SNAPTRADE_CLIENT_ID", "")
SNAPTRADE_USER_ID = os.environ.get("SNAPTRADE_USER_ID", "")
SNAPTRADE_USER_SECRET = os.environ.get("SNAPTRADE_USER_SECRET", "")

# Account name mapping (SnapTrade account names → portfolio categories)
ACCOUNT_MAP: dict[str, str] = safe_json("ACCOUNT_MAP", "{}")

# OFX bank config — JSON array of banks, each with accounts
OFX_BANKS_CONFIG: list[dict[str, Any]] = safe_json("OFX_BANKS_CONFIG", "[]")

# ---------------------------------------------------------------------------
# Data directory root — all file-based config paths derive from this
# ---------------------------------------------------------------------------
VIGIL_DATA_DIR = Path(os.environ.get("VIGIL_DATA_DIR", "data"))

# Directory for manually downloaded QFX/OFX statement files (e.g., Chase credit cards)
OFX_STATEMENTS_DIR = os.environ.get("OFX_STATEMENTS_DIR", "")

CHECKLIST_PATH = os.environ.get(
    "CHECKLIST_PATH", str(VIGIL_DATA_DIR / "financial_checklist.md")
)

# FRED API key — free from https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# How many days of transactions to look back for red-flag checks
LOOKBACK_DAYS = safe_int("LOOKBACK_DAYS", "7")

# Max transactions to include in output (most recent, sorted by date desc)
MAX_RECENT_TRANSACTIONS = safe_int("MAX_RECENT_TRANSACTIONS", "10")

# Large transaction threshold (in dollars)
LARGE_TRANSACTION_THRESHOLD = safe_float("LARGE_TRANSACTION_THRESHOLD", "500")

# Low balance threshold (in dollars)
LOW_BALANCE_THRESHOLD = safe_float("LOW_BALANCE_THRESHOLD", "1000")

# Known vendors (pipe-separated) — transactions from these won't trigger alerts
KNOWN_VENDORS: list[str] = (
    os.environ.get("KNOWN_VENDORS", "").split("|")
    if os.environ.get("KNOWN_VENDORS")
    else []
)

# ---------------------------------------------------------------------------
# Anytype API
# ---------------------------------------------------------------------------
ANYTYPE_API_KEY = os.environ.get("ANYTYPE_API_KEY", "")
ANYTYPE_SPACE_ID = os.environ.get("ANYTYPE_SPACE_ID", "")

# ---------------------------------------------------------------------------
# Todoist (read-only, for daily brief task list display)
# ---------------------------------------------------------------------------
TODOIST_API_TOKEN = os.environ.get("TODOIST_API_TOKEN", "")

# ---------------------------------------------------------------------------
# Bible Reading
# ---------------------------------------------------------------------------
READING_PLAN_PATH = os.environ.get(
    "READING_PLAN_PATH", str(VIGIL_DATA_DIR / "reading_plan.json")
)
BOOKS_DIR = Path(os.environ.get("BOOKS_DIR", str(VIGIL_DATA_DIR / "books")))

# ---------------------------------------------------------------------------
# Birthdays
# ---------------------------------------------------------------------------
CONTACTS_PATH = os.environ.get("CONTACTS_PATH", str(VIGIL_DATA_DIR / "contacts.json"))

# ---------------------------------------------------------------------------
# Optional: LLM for birthday messages via OpenRouter
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BIRTHDAY_USE_LLM = os.environ.get("BIRTHDAY_USE_LLM", "false").lower() == "true"

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
INFLATION_THRESHOLD = 3.0  # CPI YoY > 3% → trim VEA, add to COWZ

# Hyperscaler capex guidance tracking (Section VIII.d)
HYPERSCALER_TICKERS = ["MSFT", "AMZN", "META", "GOOGL"]
CAPEX_CUT_THRESHOLD = -15.0  # percent YoY decline signals a cut

# Benchmark for year-end review (Section VIII.e)
BENCHMARK: dict[str, int] = {"VTI": 45, "IWM": 14, "VXUS": 21, "BND": 20}

# All portfolio tickers
ALL_TICKERS = ["SMH", "VGT", "COWZ", "AVUV", "VEA", "NLR", "IBIT"]

# Supplemental tickers for trigger checks
TRIGGER_TICKERS = ["BTC-USD", "DX-Y.NYB", "SPY"]
