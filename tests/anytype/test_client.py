"""Tests for anytype_client module (Anytype REST API wrapper + Markdown builders)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vigil.anytype.client import (
    AnytypeClient,
    md_bullet,
    md_callout,
    md_divider,
    md_heading,
    md_paragraph,
    md_table,
    md_toggle,
)

# ---------------------------------------------------------------------------
# Markdown builder tests
# ---------------------------------------------------------------------------


class TestMdHeading:
    """Tests for md_heading."""

    def test_level_2(self) -> None:
        assert md_heading("Title", level=2) == "## Title"

    def test_level_3(self) -> None:
        assert md_heading("Sub", level=3) == "### Sub"

    def test_default_level_is_2(self) -> None:
        assert md_heading("X") == "## X"

    def test_level_1(self) -> None:
        assert md_heading("Top", level=1) == "# Top"


class TestMdParagraph:
    """Tests for md_paragraph."""

    def test_returns_text_unchanged(self) -> None:
        assert md_paragraph("Hello world") == "Hello world"

    def test_empty_string(self) -> None:
        assert md_paragraph("") == ""


class TestMdBullet:
    """Tests for md_bullet."""

    def test_prepends_dash(self) -> None:
        assert md_bullet("Item 1") == "- Item 1"

    def test_empty_string(self) -> None:
        assert md_bullet("") == "- "


class TestMdCallout:
    """Tests for md_callout."""

    def test_default_icon(self) -> None:
        assert md_callout("Note") == "> 📝 Note"

    def test_custom_icon(self) -> None:
        assert md_callout("Warning", "⚠️") == "> ⚠️ Warning"


class TestMdDivider:
    """Tests for md_divider."""

    def test_returns_triple_dash(self) -> None:
        assert md_divider() == "---"


class TestMdTable:
    """Tests for md_table."""

    def test_single_column_single_row(self) -> None:
        result = md_table(["Col"], [["val"]])
        lines = result.splitlines()
        assert lines[0] == "| Col |"
        assert lines[1] == "| --- |"
        assert lines[2] == "| val |"

    def test_two_columns_two_rows(self) -> None:
        result = md_table(["A", "B"], [["1", "2"], ["3", "4"]])
        lines = result.splitlines()
        assert lines[0] == "| A | B |"
        assert lines[1] == "| --- | --- |"
        assert lines[2] == "| 1 | 2 |"
        assert lines[3] == "| 3 | 4 |"

    def test_empty_rows(self) -> None:
        result = md_table(["A", "B"], [])
        lines = result.splitlines()
        assert len(lines) == 2  # header + separator only


class TestMdToggle:
    """Tests for md_toggle."""

    def test_returns_details_block(self) -> None:
        result = md_toggle("My Title", "My content here")
        assert "<details>" in result
        assert "<summary>My Title</summary>" in result
        assert "My content here" in result
        assert "</details>" in result

    def test_empty_content(self) -> None:
        result = md_toggle("Title", "")
        assert "<details>" in result


# ---------------------------------------------------------------------------
# AnytypeClient tests
# ---------------------------------------------------------------------------


def _mock_response(
    json_data: dict[str, Any] | list[Any],
    status: int = 200,
) -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _error_response(status: int) -> MagicMock:
    """Create a mock httpx response that raises on raise_for_status."""
    resp = MagicMock()
    resp.status_code = status
    request = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"HTTP {status}",
        request=request,
        response=resp,
    )
    return resp


class TestAnytypeClientInit:
    """Tests for AnytypeClient.__init__."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_creates_client_with_correct_headers(
        self, mock_client_cls: MagicMock
    ) -> None:
        AnytypeClient("my-api-key")
        _, kwargs = mock_client_cls.call_args
        headers = kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-api-key"
        assert headers["Anytype-Version"] == "2025-11-08"
        assert headers["Content-Type"] == "application/json"

    @patch("vigil.anytype.client.httpx.Client")
    def test_uses_default_base_url(self, mock_client_cls: MagicMock) -> None:
        AnytypeClient("key")
        _, kwargs = mock_client_cls.call_args
        assert kwargs["base_url"] == "http://127.0.0.1:31012"

    @patch("vigil.anytype.client.httpx.Client")
    def test_accepts_custom_base_url(self, mock_client_cls: MagicMock) -> None:
        AnytypeClient("key", base_url="http://localhost:31009")
        _, kwargs = mock_client_cls.call_args
        assert kwargs["base_url"] == "http://localhost:31009"

    @patch.dict("os.environ", {"ANYTYPE_API_URL": "http://localhost:31009"})
    @patch("vigil.anytype.client.httpx.Client")
    def test_env_var_overrides_default_url(self, mock_client_cls: MagicMock) -> None:
        AnytypeClient("key")
        _, kwargs = mock_client_cls.call_args
        assert kwargs["base_url"] == "http://localhost:31009"

    @patch.dict("os.environ", {"ANYTYPE_API_URL": "http://localhost:31009"})
    @patch("vigil.anytype.client.httpx.Client")
    def test_explicit_base_url_wins_over_env(self, mock_client_cls: MagicMock) -> None:
        AnytypeClient("key", base_url="http://127.0.0.1:31012")
        _, kwargs = mock_client_cls.call_args
        assert kwargs["base_url"] == "http://127.0.0.1:31012"


class TestAnytypeClientListSpaces:
    """Tests for AnytypeClient.list_spaces."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_returns_list_of_spaces(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.get.return_value = _mock_response(
            {"data": [{"id": "space-1", "name": "Daily Briefs"}]}
        )
        client = AnytypeClient("key")
        spaces = client.list_spaces()
        assert len(spaces) == 1
        assert spaces[0]["id"] == "space-1"

    @patch("vigil.anytype.client.httpx.Client")
    def test_raises_on_401(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.get.return_value = _error_response(401)
        client = AnytypeClient("bad-key")
        with pytest.raises(httpx.HTTPStatusError):
            client.list_spaces()


class TestAnytypeClientCreateObject:
    """Tests for AnytypeClient.create_object."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_returns_object_id(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"object": {"id": "obj-123"}})
        client = AnytypeClient("key")
        obj_id = client.create_object(
            space_id="space-1",
            name="📋 Daily Brief",
            icon="📋",
            body="## Hello",
        )
        assert obj_id == "obj-123"

    @patch("vigil.anytype.client.httpx.Client")
    def test_sends_correct_payload(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"object": {"id": "x"}})
        client = AnytypeClient("key")
        client.create_object(
            space_id="s1",
            name="My Page",
            icon="📖",
            body="## Title\n\nContent",
            type_key="page",
        )
        _, kwargs = mock_http.post.call_args
        payload = kwargs["json"]
        assert payload["name"] == "My Page"
        assert payload["type_key"] == "page"
        assert payload["body"] == "## Title\n\nContent"
        assert payload["icon"]["emoji"] == "📖"
        assert payload["icon"]["format"] == "emoji"

    @patch("vigil.anytype.client.httpx.Client")
    def test_default_type_key_is_page(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"object": {"id": "y"}})
        client = AnytypeClient("key")
        client.create_object(space_id="s1", name="P", icon="📋", body="")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["type_key"] == "page"

    @patch("vigil.anytype.client.httpx.Client")
    def test_calls_correct_endpoint(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"object": {"id": "z"}})
        client = AnytypeClient("key")
        client.create_object(space_id="my-space", name="P", icon="📋", body="")
        args, _ = mock_http.post.call_args
        assert args[0] == "/v1/spaces/my-space/objects"

    @patch("vigil.anytype.client.httpx.Client")
    def test_raises_on_404(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _error_response(404)
        client = AnytypeClient("key")
        with pytest.raises(httpx.HTTPStatusError):
            client.create_object("bad-space", "X", "📋", "")


class TestAnytypeClientUpdateObject:
    """Tests for AnytypeClient.update_object."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_updates_body(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})
        client = AnytypeClient("key")
        client.update_object("s1", "obj-1", body="## New body")
        _, kwargs = mock_http.patch.call_args
        assert kwargs["json"]["body"] == "## New body"

    @patch("vigil.anytype.client.httpx.Client")
    def test_updates_name_only(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})
        client = AnytypeClient("key")
        client.update_object("s1", "obj-1", name="New Name")
        _, kwargs = mock_http.patch.call_args
        payload = kwargs["json"]
        assert payload.get("name") == "New Name"
        assert "body" not in payload

    @patch("vigil.anytype.client.httpx.Client")
    def test_updates_both_body_and_name(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})
        client = AnytypeClient("key")
        client.update_object("s1", "obj-1", body="Content", name="Title")
        _, kwargs = mock_http.patch.call_args
        payload = kwargs["json"]
        assert payload["body"] == "Content"
        assert payload["name"] == "Title"

    @patch("vigil.anytype.client.httpx.Client")
    def test_calls_correct_endpoint(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})
        client = AnytypeClient("key")
        client.update_object("sp-1", "ob-1", body="x")
        args, _ = mock_http.patch.call_args
        assert args[0] == "/v1/spaces/sp-1/objects/ob-1"

    @patch("vigil.anytype.client.httpx.Client")
    def test_raises_on_429(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _error_response(429)
        client = AnytypeClient("key")
        with pytest.raises(httpx.HTTPStatusError):
            client.update_object("s1", "o1", body="x")


class TestAnytypeClientGetObject:
    """Tests for AnytypeClient.get_object."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_returns_object_dict(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.get.return_value = _mock_response(
            {"object": {"id": "obj-1", "name": "My Page"}}
        )
        client = AnytypeClient("key")
        obj = client.get_object("s1", "obj-1")
        assert obj["id"] == "obj-1"
        assert obj["name"] == "My Page"

    @patch("vigil.anytype.client.httpx.Client")
    def test_calls_correct_endpoint(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.get.return_value = _mock_response({"object": {"id": "x"}})
        client = AnytypeClient("key")
        client.get_object("sp-99", "ob-99")
        args, _ = mock_http.get.call_args
        assert args[0] == "/v1/spaces/sp-99/objects/ob-99"

    @patch("vigil.anytype.client.httpx.Client")
    def test_raises_on_404(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.get.return_value = _error_response(404)
        client = AnytypeClient("key")
        with pytest.raises(httpx.HTTPStatusError):
            client.get_object("s1", "missing")


class TestAnytypeClientSearchObjects:
    """Tests for AnytypeClient.search_objects."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_returns_list_of_objects(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response(
            {"data": [{"id": "r1"}, {"id": "r2"}]}
        )
        client = AnytypeClient("key")
        results = client.search_objects("s1", "Daily Brief")
        assert len(results) == 2

    @patch("vigil.anytype.client.httpx.Client")
    def test_sends_query_and_types(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"data": []})
        client = AnytypeClient("key")
        client.search_objects("s1", "q", types=["page"])
        _, kwargs = mock_http.post.call_args
        payload = kwargs["json"]
        assert payload["query"] == "q"
        assert payload["types"] == ["page"]

    @patch("vigil.anytype.client.httpx.Client")
    def test_calls_correct_endpoint(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"data": []})
        client = AnytypeClient("key")
        client.search_objects("my-space", "q")
        args, _ = mock_http.post.call_args
        assert args[0] == "/v1/spaces/my-space/search"

    @patch("vigil.anytype.client.httpx.Client")
    def test_types_none_omitted_from_payload(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"data": []})
        client = AnytypeClient("key")
        client.search_objects("s1", "q", types=None)
        _, kwargs = mock_http.post.call_args
        assert "types" not in kwargs["json"]


class TestAnytypeClientDeleteObject:
    """Tests for AnytypeClient.delete_object."""

    @patch("vigil.anytype.client.httpx.Client")
    def test_calls_correct_endpoint(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.delete.return_value = _mock_response({})
        client = AnytypeClient("key")
        client.delete_object("sp-1", "ob-1")
        args, _ = mock_http.delete.call_args
        assert args[0] == "/v1/spaces/sp-1/objects/ob-1"

    @patch("vigil.anytype.client.httpx.Client")
    def test_raises_on_404(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.delete.return_value = _error_response(404)
        client = AnytypeClient("key")
        with pytest.raises(httpx.HTTPStatusError):
            client.delete_object("s1", "missing")
