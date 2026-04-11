"""Vigil CLI — Typer-based command-line interface.

Dispatches to the appropriate domain module based on the subcommand.

Usage::

    vigil brief    # run Phase 1 daily brief
    vigil monitor  # run standalone financial monitor
"""

from __future__ import annotations

import typer

from vigil.anytype.writer import main as writer_main
from vigil.financial.monitor import main as monitor_main

app = typer.Typer(
    name="vigil",
    help="Vigilant Integrated Guidance for Individual Living.",
    no_args_is_help=True,
)


@app.command()
def brief() -> None:
    """Build the daily brief — Phase 1 (deterministic, no LLM)."""
    writer_main()


@app.command()
def monitor() -> None:
    """Run the financial health monitor (standalone)."""
    monitor_main()


if __name__ == "__main__":  # pragma: no cover
    app()
