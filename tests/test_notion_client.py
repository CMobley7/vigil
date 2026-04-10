"""Tests for notion_client module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from notion_client import (
    NotionClient,
    bulleted_list,
    callout,
    divider,
    heading_2,
    heading_3,
    paragraph,
    table,
    toggle,
)

# ---------------------------------------------------------------------------
# Block builder tests
# ---------------------------------------------------------------------------


class TestHeading2:
    """Tests for the heading_2 block builder."""

    def test_structure(self) -> None:
        block = heading_2("Hello")
        assert block["type"] == "heading_2"
        assert block["heading_2"]["rich_text"][0]["text"]["content"] == "Hello"

    def test_object_key(self) -> None:
        block = heading_2("X")
        assert block["object"] == "block"


class TestHeading3:
    """Tests for the heading_3 block builder."""

    def test_structure(self) -> None:
        block = heading_3("Sub")
        assert block["type"] == "heading_3"
        assert block["heading_3"]["rich_text"][0]["text"]["content"] == "Sub"


class TestParagraph:
    """Tests for the paragraph block builder."""

    def test_structure(self) -> None:
        block = paragraph("Some text")
        assert block["type"] == "paragraph"
        assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Some text"

    def test_truncates_at_2000_chars(self) -> None:
        long_text = "x" * 3000
        block = paragraph(long_text)
        content = block["paragraph"]["rich_text"][0]["text"]["content"]
        assert len(content) == 2000


class TestBulletedList:
    """Tests for the bulleted_list block builder."""

    def test_structure(self) -> None:
        block = bulleted_list("Item 1")
        assert block["type"] == "bulleted_list_item"
        rt = block["bulleted_list_item"]["rich_text"]
        assert rt[0]["text"]["content"] == "Item 1"


class TestCallout:
    """Tests for the callout block builder."""

    def test_default_icon(self) -> None:
        block = callout("Note text")
        assert block["callout"]["icon"]["emoji"] == "📝"

    def test_custom_icon(self) -> None:
        block = callout("Warning", icon="⚠️")
        assert block["callout"]["icon"]["emoji"] == "⚠️"
        assert block["callout"]["rich_text"][0]["text"]["content"] == "Warning"


class TestDivider:
    """Tests for the divider block builder."""

    def test_structure(self) -> None:
        block = divider()
        assert block["type"] == "divider"
        assert block["divider"] == {}


class TestTable:
    """Tests for the table block builder."""

    def test_dimensions(self) -> None:
        block = table(["A", "B"], [["1", "2"], ["3", "4"]])
        assert block["table"]["table_width"] == 2
        assert block["table"]["has_column_header"] is True
        # 1 header row + 2 data rows = 3 children
        assert len(block["table"]["children"]) == 3

    def test_cell_content(self) -> None:
        block = table(["Col"], [["val"]])
        data_row = block["table"]["children"][1]
        cell_text = data_row["table_row"]["cells"][0][0]["text"]["content"]
        assert cell_text == "val"

    def test_empty_rows(self) -> None:
        block = table(["A"], [])
        assert len(block["table"]["children"]) == 1  # header only


class TestToggle:
    """Tests for the toggle block builder."""

    def test_structure(self) -> None:
        child = paragraph("inner")
        block = toggle("Title", [child])
        assert block["type"] == "toggle"
        assert block["toggle"]["rich_text"][0]["text"]["content"] == "Title"
        assert block["toggle"]["children"] == [child]

    def test_empty_children(self) -> None:
        block = toggle("Empty", [])
        assert block["toggle"]["children"] == []


# ---------------------------------------------------------------------------
# NotionClient tests
# ---------------------------------------------------------------------------


def _mock_response(json_data: dict[str, Any], status: int = 200) -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestNotionClientCreatePage:
    """Tests for NotionClient.create_page."""

    @patch("notion_client.httpx.Client")
    def test_returns_page_id(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"id": "page-123"})

        client = NotionClient("test-token")
        page_id = client.create_page("db-456", "My Page", "📋")

        assert page_id == "page-123"

    @patch("notion_client.httpx.Client")
    def test_sends_correct_payload(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"id": "x"})

        client = NotionClient("test-token")
        client.create_page("db-id", "Title", "🎯")

        args, kwargs = mock_http.post.call_args
        assert args[0] == "/pages"
        payload = kwargs["json"]
        assert payload["parent"]["database_id"] == "db-id"
        assert payload["icon"]["emoji"] == "🎯"
        title_text = payload["properties"]["title"]["title"][0]["text"]["content"]
        assert title_text == "Title"

    @patch("notion_client.httpx.Client")
    def test_headers_include_version(self, mock_client_cls: MagicMock) -> None:
        NotionClient("my-token")
        _, kwargs = mock_client_cls.call_args
        headers = kwargs["headers"]
        assert headers["Notion-Version"] == "2022-06-28"
        assert headers["Authorization"] == "Bearer my-token"


class TestNotionClientCreateChildPage:
    """Tests for NotionClient.create_child_page."""

    @patch("notion_client.httpx.Client")
    def test_uses_page_parent(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.post.return_value = _mock_response({"id": "child-1"})

        client = NotionClient("t")
        result = client.create_child_page("parent-1", "Child", "📖")

        assert result == "child-1"
        payload = mock_http.post.call_args[1]["json"]
        assert payload["parent"]["page_id"] == "parent-1"


class TestNotionClientAppendBlocks:
    """Tests for NotionClient.append_blocks."""

    @patch("notion_client.httpx.Client")
    def test_single_batch(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})

        client = NotionClient("t")
        blocks = [paragraph("a"), paragraph("b")]
        client.append_blocks("page-1", blocks)

        mock_http.patch.assert_called_once()
        payload = mock_http.patch.call_args[1]["json"]
        assert len(payload["children"]) == 2

    @patch("notion_client.httpx.Client")
    def test_chunks_at_100(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http
        mock_http.patch.return_value = _mock_response({})

        client = NotionClient("t")
        blocks = [paragraph(f"p{i}") for i in range(150)]
        client.append_blocks("page-1", blocks)

        assert mock_http.patch.call_count == 2
        first_payload = mock_http.patch.call_args_list[0][1]["json"]
        second_payload = mock_http.patch.call_args_list[1][1]["json"]
        assert len(first_payload["children"]) == 100
        assert len(second_payload["children"]) == 50

    @patch("notion_client.httpx.Client")
    def test_empty_blocks(self, mock_client_cls: MagicMock) -> None:
        mock_http = MagicMock()
        mock_client_cls.return_value = mock_http

        client = NotionClient("t")
        client.append_blocks("page-1", [])

        mock_http.patch.assert_not_called()
