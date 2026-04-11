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

from vigil.config import (
    ALL_TICKERS,
    BENCHMARK,
    FRED_API_KEY,
    HYPERSCALER_TICKERS,
    LOOKBACK_DAYS,
    OFX_BANKS_CONFIG,
    OFX_STATEMENTS_DIR,
    SNAPTRADE_CLIENT_ID,
    SNAPTRADE_CONSUMER_KEY,
    SNAPTRADE_USER_ID,
    SNAPTRADE_USER_SECRET,
    TRIGGER_TICKERS,
)

logger = logging.getLogger(__name__)

__all__ = [
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
            "Checklist at %s has content but no sections parsed — "
            "expected headings: '## Red Flags', '## Accounts'",
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
        from snaptrade_client import SnapTrade
    except ImportError:
        logger.warning("snaptrade-python-sdk not installed")
        return None

    from vigil.config import ACCOUNT_MAP

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
                shares = float(pos.units) if pos.units else 0.0
                price = float(pos.price) if pos.price else 0.0
                total_value += market_value

                # Cost basis from SnapTrade (may be None if broker doesn't report)
                avg_cost = (
                    float(pos.average_purchase_price)
                    if getattr(pos, "average_purchase_price", None)
                    else None
                )
                cost_basis = round(avg_cost * shares, 2) if avg_cost else None
                unrealized_gain = (
                    round(market_value - cost_basis, 2) if cost_basis else None
                )
                unrealized_gain_pct = (
                    round((unrealized_gain / cost_basis) * 100, 2)
                    if cost_basis and cost_basis > 0 and unrealized_gain is not None
                    else None
                )

                holdings.append(
                    {
                        "ticker": ticker,
                        "shares": shares,
                        "price": price,
                        "avg_cost": avg_cost,
                        "market_value": market_value,
                        "cost_basis": cost_basis,
                        "unrealized_gain": unrealized_gain,
                        "unrealized_gain_pct": unrealized_gain_pct,
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

    except Exception as exc:  # Boundary catch: 3rd-party SDK — log and degrade
        logger.warning("SnapTrade fetch failed: %s", exc)
        return None


def fetch_bank_data() -> dict[str, Any] | None:  # pragma: no cover
    """Fetch bank transactions via OFX Direct Connect and/or statement files.

    Combines two sources:
      1. **Live OFX Direct Connect** — uses ``OFX_BANKS_CONFIG`` to pull
         transactions from banks that support the OFX protocol.
      2. **Manual statement files** — reads ``.qfx`` and ``.ofx`` files from
         ``OFX_STATEMENTS_DIR`` (e.g., downloaded from Chase).

    Either or both sources can be configured. Returns ``None`` only if neither
    is configured or all fetches/parses fail.
    """
    if not OFX_BANKS_CONFIG and not OFX_STATEMENTS_DIR:
        logger.warning(
            "Neither OFX_BANKS_CONFIG nor OFX_STATEMENTS_DIR configured "
            "— skipping bank data"
        )
        return None

    try:  # pragma: no cover
        from ofxtools.OFXClient import OFXClient
        from ofxtools.Parser import OFXTree
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
            except Exception as exc:  # Boundary catch: OFX — log and degrade
                errors.append(f"{bank_name}/{acct_id}: {exc}")
                logger.warning(
                    "OFX fetch failed for %s/%s: %s",
                    bank_name,
                    acct_id,
                    exc,
                )

    # --- Parse manually downloaded QFX/OFX statement files ---
    if OFX_STATEMENTS_DIR:
        stmt_dir = Path(OFX_STATEMENTS_DIR)
        if stmt_dir.is_dir():
            for stmt_file in sorted(stmt_dir.glob("*.[qo]fx")):
                try:
                    parser = OFXTree()
                    with stmt_file.open("rb") as fh:
                        parser.parse(fh)
                    ofx = parser.convert()
                    file_label = stmt_file.stem  # filename without extension

                    for stmt in ofx.statements:
                        if (
                            hasattr(stmt, "available_balance")
                            and stmt.available_balance
                        ):
                            bank_balances.append(
                                {
                                    "bank": file_label,
                                    "account": getattr(stmt, "acctid", file_label),
                                    "balance": float(stmt.available_balance),
                                }
                            )

                        for txn in stmt.transactions:
                            all_transactions.append(
                                {
                                    "bank": file_label,
                                    "account": getattr(stmt, "acctid", file_label),
                                    "date": (
                                        str(txn.dtposted.date())
                                        if txn.dtposted
                                        else None
                                    ),
                                    "amount": (
                                        float(txn.trnamt) if txn.trnamt else 0.0
                                    ),
                                    "name": txn.name or "Unknown",
                                    "memo": txn.memo or "",
                                }
                            )

                    # Move successfully parsed file to processed/ subfolder
                    processed_dir = stmt_dir / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    stmt_file.rename(processed_dir / stmt_file.name)
                    logger.info("Processed OFX file %s -> processed/", stmt_file.name)
                except Exception as exc:  # Boundary catch: file parse -- log, skip
                    errors.append(f"file:{stmt_file.name}: {exc}")
                    logger.warning(
                        "Failed to parse OFX file %s: %s", stmt_file.name, exc
                    )
        else:
            logger.warning(
                "OFX_STATEMENTS_DIR '%s' is not a directory", OFX_STATEMENTS_DIR
            )

    if errors:
        logger.warning("OFX errors: %s", "; ".join(errors))

    if not all_transactions and not bank_balances:
        return None

    # Sort by date descending for consistent output.
    # Trimming to MAX_RECENT_TRANSACTIONS happens in the orchestrator
    # AFTER red-flag evaluation (evaluators need the full transaction list).
    all_transactions.sort(key=lambda t: t.get("date") or "", reverse=True)

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
        import yfinance as yf
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

            price = info.last_price or None
            prev_close = info.previous_close or None
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

    except Exception as exc:  # Boundary catch: yfinance — log and degrade
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
        from fredapi import Fred
    except ImportError:
        logger.warning("fredapi not installed")
        return None

    from vigil.config import (
        INFLATION_THRESHOLD,
        SAHM_RULE_THRESHOLD,
        UNEMPLOYMENT_RECESSION_THRESHOLD,
    )

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

        # CPI for All Urban Consumers (CPIAUCSL) — Year-over-Year % change
        cpi = fred.get_series("CPIAUCSL")
        cpi_yoy: float | None = None
        cpi_date: str | None = None
        if not cpi.empty and len(cpi.dropna()) >= 13:
            cpi_clean = cpi.dropna()
            latest_cpi = float(cpi_clean.iloc[-1])
            year_ago_cpi = float(cpi_clean.iloc[-13])  # 12 months prior
            cpi_yoy = round(((latest_cpi - year_ago_cpi) / year_ago_cpi) * 100, 2)
            cpi_date = str(cpi_clean.index[-1].date())

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
            "inflation": {
                "value": cpi_yoy,
                "date": cpi_date,
                "threshold": INFLATION_THRESHOLD,
                "above_threshold": (
                    cpi_yoy > INFLATION_THRESHOLD if cpi_yoy is not None else None
                ),
            },
        }

    except Exception as exc:  # Boundary catch: FRED API — log and degrade
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
        import yfinance as yf
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

        return capex_data or None

    except Exception as exc:  # Boundary catch: yfinance capex — log and degrade
        logger.warning("Hyperscaler capex fetch failed: %s", exc)
        return None
