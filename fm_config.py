"""Configuration constants for the Financial Health Monitor.

All values are sourced from environment variables or hardcoded from the
Chairman's Portfolio Allocation document (March 2026).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

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
FAIL_PATTERN = re.compile(r"\b(nsf|returned|failed|declined|bounced)\b")
