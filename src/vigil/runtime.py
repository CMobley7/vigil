"""Private runtime file helpers for Vigil handoff data."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from vigil.config import VIGIL_RUNTIME_DIR

if TYPE_CHECKING:
    from pathlib import Path

STATE_FILE = VIGIL_RUNTIME_DIR / "daily_brief_state.json"
FM_CACHE_FILE = VIGIL_RUNTIME_DIR / "daily_brief_fm_output.json"


def ensure_private_dir(path: Path) -> None:
    """Create a private runtime directory for sensitive handoff files.

    Args:
        path: Directory path to create or harden.
    """
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def write_private_text(path: Path, text: str) -> None:
    """Write text to a file with owner-only permissions.

    Args:
        path: Destination file path.
        text: Text to write.
    """
    ensure_private_dir(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
        file_obj.write(text)
    path.chmod(0o600)
