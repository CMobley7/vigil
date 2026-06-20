"""Tests for VIGIL_DATA_DIR path derivation in vigil.config."""

from __future__ import annotations

import importlib
from unittest.mock import patch

import vigil.config as config_module


class TestVigilDataDir:
    """Verify that sub-paths derive from VIGIL_DATA_DIR."""

    def test_default_data_dir_is_data(self) -> None:
        """With no env var, VIGIL_DATA_DIR defaults to 'data'."""
        with patch.dict("os.environ", {}, clear=True):
            importlib.reload(config_module)
            assert str(config_module.VIGIL_DATA_DIR) == "data"

    def test_custom_data_dir_propagates_to_contacts(self) -> None:
        """Setting VIGIL_DATA_DIR causes CONTACTS_PATH to derive from it."""
        env = {"VIGIL_DATA_DIR": "/custom/root"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert config_module.CONTACTS_PATH == "/custom/root/contacts.json"

    def test_custom_data_dir_propagates_to_reading_plan(self) -> None:
        """Setting VIGIL_DATA_DIR causes READING_PLAN_PATH to derive from it."""
        env = {"VIGIL_DATA_DIR": "/custom/root"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert config_module.READING_PLAN_PATH == "/custom/root/reading_plan.json"

    def test_custom_data_dir_propagates_to_books_dir(self) -> None:
        """Setting VIGIL_DATA_DIR causes BOOKS_DIR to derive from it."""
        env = {"VIGIL_DATA_DIR": "/custom/root"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert str(config_module.BOOKS_DIR) == "/custom/root/books"

    def test_custom_data_dir_propagates_to_checklist(self) -> None:
        """Setting VIGIL_DATA_DIR causes CHECKLIST_PATH to derive from it."""
        env = {"VIGIL_DATA_DIR": "/custom/root"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert config_module.CHECKLIST_PATH == "/custom/root/financial_checklist.md"

    def test_custom_data_dir_propagates_to_runtime_dir(self) -> None:
        """Default runtime dir lives under VIGIL_DATA_DIR when XDG is unset."""
        env = {"VIGIL_DATA_DIR": "/custom/root"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert str(config_module.VIGIL_RUNTIME_DIR) == "/custom/root/runtime"

    def test_runtime_dir_override_wins(self) -> None:
        """VIGIL_RUNTIME_DIR explicitly controls private handoff location."""
        env = {
            "VIGIL_DATA_DIR": "/custom/root",
            "VIGIL_RUNTIME_DIR": "/run/private/vigil",
        }
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert str(config_module.VIGIL_RUNTIME_DIR) == "/run/private/vigil"

    def test_vigil_timezone_defaults_to_weather_timezone(self) -> None:
        """WEATHER_TZ remains the fallback date boundary for existing configs."""
        env = {"WEATHER_TZ": "America/Chicago"}
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert config_module.VIGIL_TIMEZONE == "America/Chicago"

    def test_individual_path_overrides_data_dir(self) -> None:
        """An explicit CONTACTS_PATH env var takes precedence over VIGIL_DATA_DIR."""
        env = {
            "VIGIL_DATA_DIR": "/custom/root",
            "CONTACTS_PATH": "/absolute/override/contacts.json",
        }
        with patch.dict("os.environ", env, clear=True):
            importlib.reload(config_module)
            assert config_module.CONTACTS_PATH == "/absolute/override/contacts.json"
