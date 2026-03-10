"""Data fetchers for the Financial Health Monitor.

Functions that retrieve data from external sources: SnapTrade (brokerage),
OFX Direct Connect (bank transactions), yfinance (market data, capex),
and FRED (recession indicators).
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fm_config import (
    ALL_TICKERS,
    BENCHMARK,
    CHECKLIST_PATH,
    FRED_API_KEY,
    HYPERSCALER_TICKERS,
    LOOKBACK_DAYS,
    OFX_BANKS_CONFIG,
    SNAPTRADE_CLIENT_ID,
    SNAPTRADE_CONSUMER_KEY,
    SNAPTRADE_USER_ID,
    SNAPTRADE_USER_SECRET,
    TRIGGER_TICKERS,
)

logger = logging.getLogger(__name__)

# Re-export CHECKLIST_PATH for backward compatibility
__all__ = [
    "CHECKLIST_PATH",
    "fetch_bank_data",
    "fetch_brokerage_data",
    "fetch_hyperscaler_capex",
    "fetch_market_data",
    "fetch_recession_indicators",
    "parse_checklist",
]


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

    # Warn if file exists and is non-empty but no sections were parsed
    if content.strip() and not checklist["red_flags"] and not checklist["accounts"]:
        logger.warning(
            "Checklist at %s found but no sections parsed — check heading format",
            path,
        )

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

    from fm_config import ACCOUNT_MAP

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

    from fm_config import SAHM_RULE_THRESHOLD, UNEMPLOYMENT_RECESSION_THRESHOLD

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
