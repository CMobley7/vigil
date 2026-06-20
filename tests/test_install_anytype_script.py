"""Tests for Anytype install script supply-chain safeguards."""

from __future__ import annotations

from pathlib import Path


def test_anytype_installer_requires_pin_or_explicit_latest() -> None:
    """Installer must not silently fetch the latest release by default."""
    script = Path("scripts/install-anytype.sh").read_text(encoding="utf-8")

    assert "ANYTYPE_VERSION is required" in script
    assert "ANYTYPE_ALLOW_LATEST" in script


def test_anytype_installer_supports_checksum_verification() -> None:
    """Installer must support SHA-256 verification of downloaded tarballs."""
    script = Path("scripts/install-anytype.sh").read_text(encoding="utf-8")

    assert "ANYTYPE_SHA256" in script
    assert "sha256sum -c" in script
