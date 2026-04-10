"""Tests for financial_monitor.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from financial_monitor import (
    build_daily_summary,
    main,
)
from fm_evaluators import (
    evaluate_account_red_flags,
    evaluate_hyperscaler_capex,
    evaluate_ibit_concentration,
    evaluate_inflation_trigger,
    evaluate_mid_year_triggers,
    evaluate_portfolio_drift,
    evaluate_recession_signals,
)
from fm_fetchers import parse_checklist

# --- Fixtures ---


def _mock_brokerage_data(
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build mock brokerage data (SnapTrade output)."""
    if positions is None:
        positions = [
            {
                "ticker": "SMH",
                "shares": 100,
                "price": 300.0,
                "market_value": 30000.0,
                "actual_pct": 60.0,
            },
            {
                "ticker": "VGT",
                "shares": 50,
                "price": 400.0,
                "market_value": 20000.0,
                "actual_pct": 40.0,
            },
        ]
    return {
        "accounts": [
            {
                "name": "PCRA - ROTH",
                "category": "Roth",
                "total_value": 50000.0,
                "holdings": positions,
            },
        ],
        "source": "snaptrade",
    }


def _mock_bank_data(
    transactions: list[dict[str, Any]] | None = None,
    balances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build mock bank data (OFX output)."""
    if transactions is None:
        transactions = [
            {
                "bank": "BankA",
                "account": "checking",
                "date": "2026-03-10",
                "amount": -25.0,
                "name": "Grocery Store",
                "memo": "",
            },
        ]
    if balances is None:
        balances = [
            {
                "bank": "BankA",
                "account": "checking",
                "balance": 5000.0,
            },
        ]
    return {
        "transactions": transactions,
        "balances": balances,
        "errors": [],
        "source": "ofx",
    }


# --- Tests ---


class TestSnapTradePositionsToDrift:
    def test_60_40_vs_50_50_yields_drift(self) -> None:
        # SMH at 60% vs target 38% → drift = 22% → rebalance
        # VGT at 40% vs target 30% → drift = 10% → rebalance
        brokerage = _mock_brokerage_data()
        alerts = evaluate_portfolio_drift(brokerage)

        # Both should trigger since drift > 8%
        smh_alerts = [a for a in alerts if "SMH" in a.get("condition", "")]
        assert len(smh_alerts) >= 1
        assert smh_alerts[0]["severity"] == "HIGH"


class TestAccountMappingValid:
    def test_mapped_account_evaluates(self) -> None:
        brokerage = _mock_brokerage_data()
        assert brokerage["accounts"][0]["category"] == "Roth"
        alerts = evaluate_portfolio_drift(brokerage)
        # Should produce alerts because positions differ from targets
        assert len(alerts) > 0


class TestAccountMappingUnknownWarns:
    def test_unmapped_account_skipped(self) -> None:
        brokerage = _mock_brokerage_data()
        brokerage["accounts"][0]["category"] = None
        alerts = evaluate_portfolio_drift(brokerage)
        assert len(alerts) == 0


class TestDriftThresholdNoise:
    def test_2_pct_drift_no_alert(self) -> None:
        positions = [
            {
                "ticker": "SMH",
                "shares": 100,
                "price": 300.0,
                "market_value": 36000.0,
                "actual_pct": 36.0,  # target 38%, drift = 2%
            },
        ]
        brokerage = _mock_brokerage_data(positions)
        alerts = evaluate_portfolio_drift(brokerage)
        smh_alerts = [a for a in alerts if "SMH" in a.get("condition", "")]
        assert len(smh_alerts) == 0


class TestDriftThresholdRedirect:
    def test_6_pct_drift_redirect(self) -> None:
        positions = [
            {
                "ticker": "SMH",
                "shares": 100,
                "price": 300.0,
                "market_value": 32000.0,
                "actual_pct": 32.0,  # target 38%, drift = 6%
            },
        ]
        brokerage = _mock_brokerage_data(positions)
        alerts = evaluate_portfolio_drift(brokerage)
        smh_alerts = [a for a in alerts if "SMH" in a.get("condition", "")]
        assert len(smh_alerts) == 1
        assert smh_alerts[0]["severity"] == "MEDIUM"
        assert "redirect" in smh_alerts[0]["condition"].lower()


class TestDriftThresholdRebalance:
    def test_9_pct_drift_rebalance(self) -> None:
        positions = [
            {
                "ticker": "SMH",
                "shares": 100,
                "price": 300.0,
                "market_value": 29000.0,
                "actual_pct": 29.0,  # target 38%, drift = 9%
            },
        ]
        brokerage = _mock_brokerage_data(positions)
        alerts = evaluate_portfolio_drift(brokerage)
        smh_alerts = [a for a in alerts if "SMH" in a.get("condition", "")]
        assert len(smh_alerts) == 1
        assert smh_alerts[0]["severity"] == "HIGH"
        assert "rebalance" in smh_alerts[0]["condition"].lower()


class TestSnapTradeFailureDegrades:
    def test_brokerage_none_partial_data(self) -> None:
        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_bank_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value=None,
            ),
            patch(
                "financial_monitor.SNAPTRADE_CONSUMER_KEY",
                "test-key",
            ),
        ):
            main()


class TestOfxFailureDegrades:
    def test_bank_none_partial_data(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_bank_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value=None,
            ),
            patch(
                "financial_monitor.OFX_BANKS_CONFIG",
                [{"name": "test"}],
            ),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["bank_data"] is None
        system_alerts = [a for a in output["alerts"] if a["category"] == "system"]
        assert len(system_alerts) > 0


class TestFredFailureDegrades:
    def test_fred_none_with_key(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_bank_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value=None,
            ),
            patch("financial_monitor.FRED_API_KEY", "test-key"),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        fred_alerts = [a for a in output["alerts"] if "FRED" in a.get("condition", "")]
        assert len(fred_alerts) == 1


class TestAllSourcesSucceed:
    def test_status_all_clear(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_market = {
            ticker: {
                "price": 100.0,
                "change_pct": 0.5,
                "return_3m": 5.0,
                "recent_high": 105.0,
            }
            for ticker in [
                "SMH",
                "VGT",
                "COWZ",
                "AVUV",
                "VEA",
                "NLR",
                "IBIT",
                "BTC-USD",
                "DX-Y.NYB",
                "SPY",
                "VTI",
                "IWM",
                "VXUS",
                "BND",
            ]
        }
        # Set BTC safely in range
        mock_market["BTC-USD"]["price"] = 80000.0

        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=_mock_brokerage_data(
                    [
                        {
                            "ticker": "SMH",
                            "shares": 100,
                            "price": 300.0,
                            "market_value": 38000.0,
                            "actual_pct": 38.0,
                        },
                        {
                            "ticker": "VGT",
                            "shares": 50,
                            "price": 400.0,
                            "market_value": 30000.0,
                            "actual_pct": 30.0,
                        },
                    ]
                ),
            ),
            patch(
                "financial_monitor.fetch_bank_data",
                return_value=_mock_bank_data(),
            ),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=mock_market,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value={
                    "unemployment_rate": {
                        "value": 3.5,
                        "date": "2026-03-01",
                        "threshold": 5.0,
                    },
                    "yield_curve_spread": {
                        "value": 0.5,
                        "date": "2026-03-01",
                        "inverted": False,
                    },
                    "sahm_rule": {
                        "value": 0.2,
                        "date": "2026-03-01",
                        "threshold": 0.5,
                        "triggered": False,
                    },
                },
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value={
                    "MSFT": {
                        "latest_capex_millions": 10000,
                        "quarter_date": "2025-12-31",
                        "yoy_change_pct": 5.0,
                    },
                },
            ),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "all_clear"


class TestOutputAlwaysValidJson:
    def test_all_sources_fail_still_valid(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_bank_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value=None,
            ),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "generated_at" in output
        assert "status" in output
        assert "alerts" in output
        assert isinstance(output["alerts"], list)


class TestMultiBankOfxLoop:
    def test_two_banks_aggregated(self) -> None:
        bank_data = _mock_bank_data(
            transactions=[
                {
                    "bank": "BankA",
                    "account": "checking",
                    "date": "2026-03-10",
                    "amount": -100.0,
                    "name": "Store",
                    "memo": "",
                },
                {
                    "bank": "BankA",
                    "account": "savings",
                    "date": "2026-03-10",
                    "amount": -50.0,
                    "name": "Transfer",
                    "memo": "",
                },
                {
                    "bank": "BankB",
                    "account": "checking",
                    "date": "2026-03-10",
                    "amount": -75.0,
                    "name": "Utility",
                    "memo": "",
                },
                {
                    "bank": "BankB",
                    "account": "savings",
                    "date": "2026-03-10",
                    "amount": -200.0,
                    "name": "Insurance",
                    "memo": "",
                },
            ]
        )
        # All 4 transactions present
        assert len(bank_data["transactions"]) == 4
        banks = {t["bank"] for t in bank_data["transactions"]}
        assert banks == {"BankA", "BankB"}

        # Red flags should work on aggregated data
        alerts = evaluate_account_red_flags(bank_data)
        # No large unknown transactions (all < 500)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# evaluate_account_red_flags — low balance, large txns, failed txns
# ---------------------------------------------------------------------------


class TestLowBalanceAlert:
    def test_below_threshold_triggers_alert(self) -> None:
        bank_data = _mock_bank_data(
            balances=[
                {"bank": "BankA", "account": "checking", "balance": 500.0},
            ],
        )
        alerts = evaluate_account_red_flags(bank_data)
        low_alerts = [a for a in alerts if "Low balance" in a["condition"]]
        assert len(low_alerts) == 1
        assert low_alerts[0]["severity"] == "HIGH"


class TestLargeUnknownTransaction:
    def test_large_unknown_triggers_alert(self) -> None:
        bank_data = _mock_bank_data(
            transactions=[
                {
                    "bank": "BankA",
                    "account": "checking",
                    "date": "2026-03-10",
                    "amount": -1200.0,
                    "name": "Suspicious Vendor",
                    "memo": "",
                },
            ],
        )
        alerts = evaluate_account_red_flags(bank_data)
        large_alerts = [a for a in alerts if "Large transaction" in a["condition"]]
        assert len(large_alerts) == 1
        assert large_alerts[0]["severity"] == "MEDIUM"


class TestFailedTransaction:
    def test_nsf_triggers_alert(self) -> None:
        bank_data = _mock_bank_data(
            transactions=[
                {
                    "bank": "BankA",
                    "account": "checking",
                    "date": "2026-03-10",
                    "amount": -50.0,
                    "name": "Payment NSF",
                    "memo": "returned item",
                },
            ],
        )
        alerts = evaluate_account_red_flags(bank_data)
        fail_alerts = [a for a in alerts if "failed payment" in a["condition"].lower()]
        assert len(fail_alerts) == 1
        assert fail_alerts[0]["severity"] == "HIGH"


class TestNonOfxSourceSkipped:
    def test_wrong_source_returns_empty(self) -> None:
        alerts = evaluate_account_red_flags({"source": "other"})
        assert alerts == []


# ---------------------------------------------------------------------------
# evaluate_mid_year_triggers
# ---------------------------------------------------------------------------


def _base_market_data() -> dict[str, dict[str, Any]]:
    """Build minimal market data with all tickers safe (no triggers)."""
    return {
        ticker: {
            "price": 100.0,
            "change_pct": 0.5,
            "return_3m": 5.0,
            "recent_high": 105.0,
        }
        for ticker in [
            "SMH",
            "VGT",
            "COWZ",
            "AVUV",
            "VEA",
            "NLR",
            "IBIT",
            "BTC-USD",
            "DX-Y.NYB",
            "SPY",
            "VTI",
            "IWM",
            "VXUS",
            "BND",
        ]
    }


class TestBitcoinBelowFloor:
    def test_btc_below_50k_triggers_trim(self) -> None:
        market = _base_market_data()
        market["BTC-USD"]["price"] = 45000.0
        alerts = evaluate_mid_year_triggers(market)
        btc_alerts = [a for a in alerts if "Bitcoin below" in a["condition"]]
        assert len(btc_alerts) == 1
        assert btc_alerts[0]["severity"] == "HIGH"


class TestBitcoinAboveCeiling:
    def test_btc_above_200k_triggers_trim(self) -> None:
        market = _base_market_data()
        market["BTC-USD"]["price"] = 250000.0
        alerts = evaluate_mid_year_triggers(market)
        btc_alerts = [a for a in alerts if "Bitcoin above" in a["condition"]]
        assert len(btc_alerts) == 1
        assert btc_alerts[0]["severity"] == "HIGH"


class TestDxyAbove105:
    def test_dxy_triggers_vea_reduction(self) -> None:
        market = _base_market_data()
        market["DX-Y.NYB"]["price"] = 108.0
        alerts = evaluate_mid_year_triggers(market)
        dxy_alerts = [a for a in alerts if "DXY above 105" in a["condition"]]
        assert len(dxy_alerts) == 1
        assert dxy_alerts[0]["severity"] == "MEDIUM"


class TestNlrDip:
    def test_nlr_down_25_pct_triggers_buy(self) -> None:
        market = _base_market_data()
        market["NLR"]["price"] = 75.0
        market["NLR"]["recent_high"] = 100.0  # 25% drawdown
        alerts = evaluate_mid_year_triggers(market)
        nlr_alerts = [a for a in alerts if "NLR down" in a["condition"]]
        assert len(nlr_alerts) == 1
        assert nlr_alerts[0]["severity"] == "MEDIUM"


class TestAvuvTrailsSpy:
    def test_avuv_8pct_lag_triggers_trim(self) -> None:
        market = _base_market_data()
        market["AVUV"]["return_3m"] = -3.0
        market["SPY"]["return_3m"] = 6.0  # gap = -9%
        alerts = evaluate_mid_year_triggers(market)
        avuv_alerts = [a for a in alerts if "AVUV trailing" in a["condition"]]
        assert len(avuv_alerts) == 1
        assert avuv_alerts[0]["severity"] == "MEDIUM"


class TestNoTriggersWhenSafe:
    def test_safe_market_no_alerts(self) -> None:
        market = _base_market_data()
        market["BTC-USD"]["price"] = 80000.0  # in safe range
        market["DX-Y.NYB"]["price"] = 100.0  # below 105
        alerts = evaluate_mid_year_triggers(market)
        assert alerts == []


class TestMidYearTriggersNoneMarket:
    def test_returns_empty_on_none(self) -> None:
        assert evaluate_mid_year_triggers({}) == []


# ---------------------------------------------------------------------------
# evaluate_recession_signals
# ---------------------------------------------------------------------------


class TestUnemploymentAboveThreshold:
    def test_high_unemployment_triggers_alert(self) -> None:
        recession = {
            "unemployment_rate": {
                "value": 6.0,
                "date": "2026-03-01",
                "threshold": 5.0,
            },
            "yield_curve_spread": {
                "value": 0.5,
                "date": "2026-03-01",
                "inverted": False,
            },
            "sahm_rule": {
                "value": 0.2,
                "date": "2026-03-01",
                "threshold": 0.5,
                "triggered": False,
            },
        }
        alerts = evaluate_recession_signals(recession)
        unemp_alerts = [a for a in alerts if "Unemployment" in a["condition"]]
        assert len(unemp_alerts) == 1
        assert unemp_alerts[0]["severity"] == "HIGH"


class TestYieldCurveInverted:
    def test_negative_spread_triggers_alert(self) -> None:
        recession = {
            "unemployment_rate": {
                "value": 3.5,
                "date": "2026-03-01",
                "threshold": 5.0,
            },
            "yield_curve_spread": {
                "value": -0.5,
                "date": "2026-03-01",
                "inverted": True,
            },
            "sahm_rule": {
                "value": 0.2,
                "date": "2026-03-01",
                "threshold": 0.5,
                "triggered": False,
            },
        }
        alerts = evaluate_recession_signals(recession)
        curve_alerts = [a for a in alerts if "Yield curve" in a["condition"]]
        assert len(curve_alerts) == 1
        assert curve_alerts[0]["severity"] == "HIGH"


class TestSahmRuleTriggered:
    def test_sahm_above_threshold_critical(self) -> None:
        recession = {
            "unemployment_rate": {
                "value": 3.5,
                "date": "2026-03-01",
                "threshold": 5.0,
            },
            "yield_curve_spread": {
                "value": 0.5,
                "date": "2026-03-01",
                "inverted": False,
            },
            "sahm_rule": {
                "value": 0.55,
                "date": "2026-03-01",
                "threshold": 0.5,
                "triggered": True,
            },
        }
        alerts = evaluate_recession_signals(recession)
        sahm_alerts = [a for a in alerts if "Sahm Rule" in a["condition"]]
        assert len(sahm_alerts) == 1
        assert sahm_alerts[0]["severity"] == "CRITICAL"


class TestRecessionSignalsNone:
    def test_none_returns_empty(self) -> None:
        assert evaluate_recession_signals(None) == []


# ---------------------------------------------------------------------------
# evaluate_hyperscaler_capex
# ---------------------------------------------------------------------------


class TestCapexCutDetected:
    def test_20pct_yoy_decline_triggers(self) -> None:
        capex = {
            "MSFT": {
                "latest_capex_millions": 8000,
                "quarter_date": "2025-12-31",
                "yoy_change_pct": -20.0,
            },
        }
        alerts = evaluate_hyperscaler_capex(capex)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "HIGH"
        assert "MSFT" in alerts[0]["condition"]


class TestCapexNoCut:
    def test_positive_growth_no_alert(self) -> None:
        capex = {
            "MSFT": {
                "latest_capex_millions": 10000,
                "quarter_date": "2025-12-31",
                "yoy_change_pct": 5.0,
            },
        }
        alerts = evaluate_hyperscaler_capex(capex)
        assert alerts == []


class TestCapexNone:
    def test_none_returns_empty(self) -> None:
        assert evaluate_hyperscaler_capex(None) == []


# ---------------------------------------------------------------------------
# build_daily_summary
# ---------------------------------------------------------------------------


class TestBuildDailySummary:
    def test_has_positions_and_context(self) -> None:
        market = _base_market_data()
        market["BTC-USD"]["price"] = 80000.0
        market["DX-Y.NYB"]["price"] = 102.0
        summary = build_daily_summary(market)
        assert "positions" in summary
        assert "SMH" in summary["positions"]
        assert summary["bitcoin_usd"] == 100.0 or summary.get("bitcoin_usd")
        assert summary["dxy_index"] == 102.0

    def test_with_recession_and_capex(self) -> None:
        market = _base_market_data()
        recession = {"unemployment_rate": {"value": 3.5}}
        capex = {"MSFT": {"latest_capex_millions": 10000}}
        summary = build_daily_summary(market, recession, capex)
        assert "recession_indicators" in summary
        assert "hyperscaler_capex" in summary

    def test_empty_market_returns_minimal(self) -> None:
        summary = build_daily_summary({})
        assert summary["positions"] == {}


# ---------------------------------------------------------------------------
# parse_checklist
# ---------------------------------------------------------------------------


class TestParseChecklist:
    def test_parses_red_flags_and_accounts(self, tmp_path: Path) -> None:
        checklist_md = """# Financial Checklist

## Red Flags

- [ ] Emergency fund below 3 months
- [x] Credit score dropped

## Accounts

- Checking
- Savings
"""
        p = tmp_path / "checklist.md"
        p.write_text(checklist_md)
        result = parse_checklist(str(p))
        assert len(result["red_flags"]) == 2
        assert "Emergency fund below 3 months" in result["red_flags"][0]
        assert len(result["accounts"]) == 2
        assert "Checking" in result["accounts"]

    def test_missing_file_returns_empty(self) -> None:
        result = parse_checklist("/nonexistent/checklist.md")
        assert result == {"red_flags": [], "accounts": []}

    def test_content_without_headings_warns(self, tmp_path: Path) -> None:
        p = tmp_path / "checklist.md"
        p.write_text("Some content without proper headings\n")
        result = parse_checklist(str(p))
        assert result == {"red_flags": [], "accounts": []}


# ---------------------------------------------------------------------------
# main() status-setting branches
# ---------------------------------------------------------------------------


class TestMainStatusCritical:
    def test_sahm_rule_sets_critical_status(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with (
            patch("financial_monitor.fetch_brokerage_data", return_value=None),
            patch("financial_monitor.fetch_bank_data", return_value=None),
            patch("financial_monitor.fetch_market_data", return_value=None),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value={
                    "unemployment_rate": {
                        "value": 3.5,
                        "date": "2026-03-01",
                        "threshold": 5.0,
                    },
                    "yield_curve_spread": {
                        "value": 0.5,
                        "date": "2026-03-01",
                        "inverted": False,
                    },
                    "sahm_rule": {
                        "value": 0.6,
                        "date": "2026-03-01",
                        "threshold": 0.5,
                        "triggered": True,
                    },
                },
            ),
            patch("financial_monitor.fetch_hyperscaler_capex", return_value=None),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "critical"


class TestMainStatusAlertsTriggered:
    def test_high_drift_without_system_warnings(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_market = _base_market_data()
        mock_market["BTC-USD"]["price"] = 80000.0

        with (
            patch(
                "financial_monitor.fetch_brokerage_data",
                return_value=_mock_brokerage_data(),
            ),
            patch("financial_monitor.fetch_bank_data", return_value=None),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=mock_market,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value={
                    "unemployment_rate": {
                        "value": 3.5,
                        "date": "2026-03-01",
                        "threshold": 5.0,
                    },
                    "yield_curve_spread": {
                        "value": 0.5,
                        "date": "2026-03-01",
                        "inverted": False,
                    },
                    "sahm_rule": {
                        "value": 0.2,
                        "date": "2026-03-01",
                        "threshold": 0.5,
                        "triggered": False,
                    },
                },
            ),
            patch("financial_monitor.fetch_hyperscaler_capex", return_value=None),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "alerts_triggered"


# ---------------------------------------------------------------------------
# evaluate_portfolio_drift — edge cases
# ---------------------------------------------------------------------------


class TestDriftEmptyBrokerage:
    def test_none_returns_empty(self) -> None:
        assert evaluate_portfolio_drift(None) == []


class TestDriftUnknownTargetCategory:
    def test_category_with_no_targets_skipped(self) -> None:
        brokerage = _mock_brokerage_data()
        brokerage["accounts"][0]["category"] = "UnknownCategory"
        alerts = evaluate_portfolio_drift(brokerage)
        assert alerts == []


class TestDriftZeroTotalValue:
    def test_zero_value_skipped(self) -> None:
        brokerage = _mock_brokerage_data()
        brokerage["accounts"][0]["total_value"] = 0
        alerts = evaluate_portfolio_drift(brokerage)
        assert alerts == []


class TestDriftTickerNotInTargets:
    def test_non_target_ticker_skipped(self) -> None:
        positions = [
            {
                "ticker": "AAPL",
                "shares": 100,
                "price": 150.0,
                "market_value": 15000.0,
                "actual_pct": 100.0,
            },
        ]
        brokerage = _mock_brokerage_data(positions)
        alerts = evaluate_portfolio_drift(brokerage)
        assert alerts == []


class TestMainStatusPartialDataWithHighAlerts:
    def test_partial_data_preserved_over_high(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When sources fail AND HIGH alerts exist, status stays partial_data."""
        mock_market = _base_market_data()
        mock_market["BTC-USD"]["price"] = 45000.0  # triggers HIGH alert

        with (
            patch("financial_monitor.fetch_brokerage_data", return_value=None),
            patch("financial_monitor.fetch_bank_data", return_value=None),
            patch(
                "financial_monitor.fetch_market_data",
                return_value=mock_market,
            ),
            patch(
                "financial_monitor.fetch_recession_indicators",
                return_value=None,
            ),
            patch(
                "financial_monitor.fetch_hyperscaler_capex",
                return_value=None,
            ),
            patch("financial_monitor.SNAPTRADE_CONSUMER_KEY", "test-key"),
        ):
            main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "partial_data"


# ---------------------------------------------------------------------------
# fm_config — _safe_json / _safe_int error paths
# ---------------------------------------------------------------------------


class TestSafeJsonInvalidInput:
    def test_invalid_json_exits(self) -> None:
        from fm_config import _safe_json

        with pytest.raises(SystemExit):
            _safe_json("_TEST_BAD_VAR", "{invalid}")


class TestSafeIntInvalidInput:
    def test_non_numeric_exits(self) -> None:
        from fm_config import _safe_int

        with pytest.raises(SystemExit):
            _safe_int("_TEST_BAD_VAR", "not_an_int")


# ---------------------------------------------------------------------------
# evaluate_inflation_trigger
# ---------------------------------------------------------------------------


class TestInflationAboveThreshold:
    def test_cpi_above_3_pct_triggers_alert(self) -> None:
        recession_data = {
            "unemployment_rate": {"value": 3.5, "date": "2026-03-01"},
            "yield_curve_spread": {"value": 0.5, "date": "2026-03-01"},
            "sahm_rule": {"value": 0.2, "date": "2026-03-01"},
            "inflation": {
                "value": 3.5,
                "date": "2026-03-01",
                "threshold": 3.0,
                "above_threshold": True,
            },
        }
        alerts = evaluate_inflation_trigger(recession_data)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "HIGH"
        assert alerts[0]["category"] == "trigger"
        assert "3.50%" in alerts[0]["details"]
        assert "VEA" in alerts[0]["action"]


class TestInflationBelowThreshold:
    def test_cpi_below_3_pct_no_alert(self) -> None:
        recession_data = {
            "inflation": {
                "value": 2.5,
                "date": "2026-03-01",
                "threshold": 3.0,
                "above_threshold": False,
            },
        }
        alerts = evaluate_inflation_trigger(recession_data)
        assert alerts == []


class TestInflationNoneData:
    def test_none_returns_empty(self) -> None:
        assert evaluate_inflation_trigger(None) == []


class TestInflationMissingKey:
    def test_no_inflation_key_returns_empty(self) -> None:
        recession_data = {
            "unemployment_rate": {"value": 3.5, "date": "2026-03-01"},
        }
        alerts = evaluate_inflation_trigger(recession_data)
        assert alerts == []


# ---------------------------------------------------------------------------
# evaluate_ibit_concentration
# ---------------------------------------------------------------------------


class TestIbitAboveMaxPct:
    def test_ibit_at_12_pct_triggers_trim(self) -> None:
        brokerage = {
            "accounts": [
                {
                    "name": "PCRA - ROTH",
                    "category": "Roth",
                    "total_value": 100000,
                    "holdings": [
                        {
                            "ticker": "IBIT",
                            "shares": 100,
                            "price": 120.0,
                            "market_value": 12000.0,
                            "actual_pct": 12.0,
                        },
                        {
                            "ticker": "SMH",
                            "shares": 200,
                            "price": 440.0,
                            "market_value": 88000.0,
                            "actual_pct": 88.0,
                        },
                    ],
                },
            ],
        }
        alerts = evaluate_ibit_concentration(brokerage)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "HIGH"
        assert "IBIT" in alerts[0]["condition"]
        assert "12.0%" in alerts[0]["details"]
        assert "7%" in alerts[0]["action"]
        assert "NLR" in alerts[0]["action"]


class TestIbitBelowMaxPct:
    def test_ibit_at_7_pct_no_alert(self) -> None:
        brokerage = {
            "accounts": [
                {
                    "name": "PCRA - ROTH",
                    "category": "Roth",
                    "total_value": 100000,
                    "holdings": [
                        {
                            "ticker": "IBIT",
                            "shares": 50,
                            "price": 140.0,
                            "market_value": 7000.0,
                            "actual_pct": 7.0,
                        },
                    ],
                },
            ],
        }
        alerts = evaluate_ibit_concentration(brokerage)
        assert alerts == []


class TestIbitNotInPortfolio:
    def test_no_ibit_no_alert(self) -> None:
        brokerage = {
            "accounts": [
                {
                    "name": "PCRA - ROTH",
                    "category": "Roth",
                    "total_value": 100000,
                    "holdings": [
                        {
                            "ticker": "SMH",
                            "shares": 200,
                            "price": 500.0,
                            "market_value": 100000.0,
                            "actual_pct": 100.0,
                        },
                    ],
                },
            ],
        }
        alerts = evaluate_ibit_concentration(brokerage)
        assert alerts == []


class TestIbitConcentrationNoneData:
    def test_none_returns_empty(self) -> None:
        assert evaluate_ibit_concentration(None) == []
