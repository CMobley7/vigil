"""Anytype API client and Markdown builder utilities.

Thin wrapper around the Anytype local REST API using ``httpx``.  Provides an
:class:`AnytypeClient` for object CRUD plus pure-function Markdown builders
that return plain ``str`` objects — no third-party Anytype SDK dependency.

The API is served by the Anytype CLI (``anytype serve``) on
``http://127.0.0.1:31012`` or by the desktop app on
``http://localhost:31009``.  The base URL is configurable via the
``ANYTYPE_API_URL`` environment variable (client-level concern; defaults to
the CLI port).

Configuration:
    ``ANYTYPE_API_URL``  — Optional override for the base URL (env var only,
                           not in fm_config — this is a client-level concern).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Self

import httpx

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:31012"
_ANYTYPE_VERSION = "2025-11-08"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class AnytypeClient:
    """Thin wrapper around the Anytype local REST API.

    Args:
        api_key: Anytype API key (generated via ``anytype auth apikey create``).
        base_url: Override the default base URL.  If not provided, the
            ``ANYTYPE_API_URL`` env var is checked, then ``http://127.0.0.1:31012``.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        """Initialize the client with authentication headers."""
        resolved_base = base_url or os.environ.get("ANYTYPE_API_URL", _DEFAULT_BASE_URL)
        self._client = httpx.Client(
            base_url=resolved_base,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Anytype-Version": _ANYTYPE_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> Self:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager and close the client."""
        self.close()

    # -- spaces --------------------------------------------------------------

    def list_spaces(self) -> list[dict[str, Any]]:
        """List all spaces visible to the API key.

        Returns:
            List of space dicts from the ``data`` field.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        resp = self._client.get("/v1/spaces")
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json().get("data", [])
        return data

    # -- objects -------------------------------------------------------------

    def create_object(
        self,
        space_id: str,
        name: str,
        icon: str,
        body: str,
        type_key: str = "page",
    ) -> str:
        """Create a new object in a space with Markdown body content.

        Args:
            space_id: Target space ID.
            name: Object name/title (supports emoji prefix).
            icon: Emoji character used as the object icon.
            body: Markdown string for the object body.
            type_key: Anytype type key (default: ``"page"``).

        Returns:
            The object ID of the newly created object.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        payload: dict[str, Any] = {
            "name": name,
            "type_key": type_key,
            "icon": {"emoji": icon, "format": "emoji"},
            "body": body,
        }
        resp = self._client.post(f"/v1/spaces/{space_id}/objects", json=payload)
        resp.raise_for_status()
        object_id: str = resp.json()["object"]["id"]
        return object_id

    def update_object(
        self,
        space_id: str,
        object_id: str,
        *,
        body: str | None = None,
        name: str | None = None,
    ) -> None:
        """Partially update an existing object.

        Omitting a field leaves it unchanged on the server.

        Args:
            space_id: Space ID containing the object.
            object_id: Target object ID.
            body: New Markdown body content, or ``None`` to leave unchanged.
            name: New object name, or ``None`` to leave unchanged.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        payload: dict[str, Any] = {}
        if body is not None:
            payload["body"] = body
        if name is not None:
            payload["name"] = name

        resp = self._client.patch(
            f"/v1/spaces/{space_id}/objects/{object_id}", json=payload
        )
        resp.raise_for_status()

    def get_object(self, space_id: str, object_id: str) -> dict[str, Any]:
        """Retrieve a single object by ID.

        Args:
            space_id: Space ID containing the object.
            object_id: Target object ID.

        Returns:
            Object dict from the ``object`` field.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        resp = self._client.get(f"/v1/spaces/{space_id}/objects/{object_id}")
        resp.raise_for_status()
        obj: dict[str, Any] = resp.json()["object"]
        return obj

    def search_objects(
        self,
        space_id: str,
        query: str,
        types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for objects within a space.

        Args:
            space_id: Space to search within.
            query: Search query string.
            types: Optional list of type keys to filter by (e.g., ``["page"]``).

        Returns:
            List of matching object dicts from the ``data`` field.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        payload: dict[str, Any] = {"query": query}
        if types is not None:
            payload["types"] = types

        resp = self._client.post(f"/v1/spaces/{space_id}/search", json=payload)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json().get("data", [])
        return data

    def delete_object(self, space_id: str, object_id: str) -> None:
        """Delete an object from a space.

        Args:
            space_id: Space ID containing the object.
            object_id: Target object ID.

        Raises:
            httpx.HTTPStatusError: On Anytype API errors.
        """
        resp = self._client.delete(f"/v1/spaces/{space_id}/objects/{object_id}")
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Markdown builder functions — pure functions returning str
# ---------------------------------------------------------------------------


def md_heading(text: str, level: int = 2) -> str:
    """Build a Markdown heading.

    Args:
        text: Heading text content.
        level: Heading level (1-6).

    Returns:
        Markdown heading string, e.g. ``"## My Heading"``.
    """
    return f"{'#' * level} {text}"


def md_paragraph(text: str) -> str:
    """Return text as a Markdown paragraph (identity function).

    Args:
        text: Paragraph text content.

    Returns:
        The text unchanged.
    """
    return text


def md_bullet(text: str) -> str:
    """Build a Markdown bullet list item.

    Args:
        text: List item text content.

    Returns:
        Markdown bullet string, e.g. ``"- My item"``.
    """
    return f"- {text}"


def md_callout(text: str, icon: str = "📝") -> str:
    """Build a Markdown blockquote as a callout.

    Args:
        text: Callout body text.
        icon: Emoji icon prefix.

    Returns:
        Markdown blockquote string, e.g. ``"> 📝 Note"``.
    """
    return f"> {icon} {text}"


def md_divider() -> str:
    """Build a Markdown horizontal rule.

    Returns:
        ``"---"``
    """
    return "---"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a Markdown table with a header row.

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of cell strings.

    Returns:
        Markdown table string.
    """
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    data_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *data_lines])


def md_toggle(title: str, content: str) -> str:
    """Build a collapsible toggle block using HTML ``<details>`` tags.

    Anytype renders ``<details>`` elements as toggle blocks.

    Args:
        title: Toggle heading text (shown in the ``<summary>`` element).
        content: Toggle body content (Markdown string).

    Returns:
        HTML ``<details>`` block string.
    """
    return f"<details>\n<summary>{title}</summary>\n\n{content}\n</details>"
