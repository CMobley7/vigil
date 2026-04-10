"""Notion API client and block builder utilities.

Thin wrapper around the Notion REST API using ``httpx``.  Provides a
:class:`NotionClient` for page/block CRUD plus pure-function block builders
that return plain ``dict`` objects—no Notion SDK dependency needed.

Configuration:
    ``NOTION_TOKEN``            — Notion internal integration token.
    ``NOTION_DAILY_BRIEFS_DB``  — Database ID for the Daily Briefs database.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_MAX_BLOCKS_PER_REQUEST = 100


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class NotionClient:
    """Thin wrapper around the Notion REST API.

    Args:
        token: Notion internal integration token.
    """

    def __init__(self, token: str) -> None:
        """Initialize with a Notion integration token."""
        self._client = httpx.Client(
            base_url=_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": _NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    # -- pages ---------------------------------------------------------------

    def create_page(
        self,
        database_id: str,
        title: str,
        icon: str,
    ) -> str:
        """Create a top-level page in a Notion database.

        Args:
            database_id: Target database UUID.
            title: Page title text.
            icon: Emoji string used as the page icon.

        Returns:
            The page ID of the newly created page.

        Raises:
            httpx.HTTPStatusError: On Notion API errors.
        """
        payload: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}],
                },
            },
        }
        resp = self._client.post("/pages", json=payload)
        resp.raise_for_status()
        page_id: str = resp.json()["id"]
        return page_id

    def create_child_page(
        self,
        parent_id: str,
        title: str,
        icon: str,
    ) -> str:
        """Create a child page under an existing page.

        Args:
            parent_id: Parent page UUID.
            title: Child page title text.
            icon: Emoji string used as the page icon.

        Returns:
            The page ID of the newly created child page.

        Raises:
            httpx.HTTPStatusError: On Notion API errors.
        """
        payload: dict[str, Any] = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}],
                },
            },
        }
        resp = self._client.post("/pages", json=payload)
        resp.raise_for_status()
        page_id: str = resp.json()["id"]
        return page_id

    # -- blocks --------------------------------------------------------------

    def append_blocks(
        self,
        page_id: str,
        blocks: list[dict[str, Any]],
    ) -> None:
        """Append children blocks to a page.

        Automatically chunks into batches of 100 to respect Notion's limit.

        Args:
            page_id: Target page UUID.
            blocks: List of Notion block dicts.

        Raises:
            httpx.HTTPStatusError: On Notion API errors.
        """
        for i in range(0, len(blocks), _MAX_BLOCKS_PER_REQUEST):
            chunk = blocks[i : i + _MAX_BLOCKS_PER_REQUEST]
            resp = self._client.patch(
                f"/blocks/{page_id}/children",
                json={"children": chunk},
            )
            resp.raise_for_status()


# ---------------------------------------------------------------------------
# Block builders — pure functions returning Notion block dicts
# ---------------------------------------------------------------------------


def heading_2(text: str) -> dict[str, Any]:
    """Build a heading_2 block.

    Args:
        text: Heading text content.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def heading_3(text: str) -> dict[str, Any]:
    """Build a heading_3 block.

    Args:
        text: Heading text content.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def paragraph(text: str) -> dict[str, Any]:
    """Build a paragraph block.

    Args:
        text: Paragraph text content.  Limited to 2000 chars by Notion.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }


def bulleted_list(text: str) -> dict[str, Any]:
    """Build a bulleted_list_item block.

    Args:
        text: Item text content.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def callout(text: str, icon: str = "📝") -> dict[str, Any]:
    """Build a callout block.

    Args:
        text: Callout body text.
        icon: Emoji icon for the callout.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"type": "emoji", "emoji": icon},
        },
    }


def divider() -> dict[str, Any]:
    """Build a divider block.

    Returns:
        Notion block dict.
    """
    return {"object": "block", "type": "divider", "divider": {}}


def table(
    headers: list[str],
    rows: list[list[str]],
) -> dict[str, Any]:
    """Build a table block with header row.

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of cell strings.

    Returns:
        Notion block dict.
    """

    def _row_block(cells: list[str]) -> dict[str, Any]:
        return {
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": cell}}] for cell in cells
                ],
            },
        }

    header_row = _row_block(headers)
    data_rows = [_row_block(row) for row in rows]

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": [header_row, *data_rows],
        },
    }


def toggle(title: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a toggle block with nested children.

    Args:
        title: Toggle heading text.
        children: List of child blocks inside the toggle.

    Returns:
        Notion block dict.
    """
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children,
        },
    }
