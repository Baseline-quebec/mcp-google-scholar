"""Tests for the FastMCP server layer.

These guard two things: that the MCP tools expose a non-empty description to
the model (a regression for the bug where the docstring sat after the first
statement and was silently dropped), and that the async wrappers convert
exceptions from the scraping layer into structured error payloads.
"""

from unittest.mock import patch

import pytest

import google_scholar_server as srv


@pytest.mark.asyncio
async def test_all_tools_have_descriptions() -> None:
    tools = await srv.mcp.list_tools()
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {
        "search_google_scholar_key_words",
        "search_google_scholar_advanced",
        "get_author_info",
    }
    # Regression: a misplaced docstring leaves the description empty.
    for tool in tools:
        assert tool.description and tool.description.strip(), f"{tool.name} has no description"
        assert "Google Scholar" in tool.description


@pytest.mark.asyncio
async def test_keyword_search_passes_through_results() -> None:
    payload = [{"Title": "T", "Authors": "A", "Abstract": "X", "URL": "u"}]
    with patch.object(srv, "google_scholar_search", return_value=payload) as m:
        result = await srv.search_google_scholar_key_words("q", num_results=3)
    m.assert_called_once_with("q", 3)
    assert result == payload


@pytest.mark.asyncio
async def test_keyword_search_wraps_exception() -> None:
    with patch.object(srv, "google_scholar_search", side_effect=RuntimeError("boom")):
        result = await srv.search_google_scholar_key_words("q")
    assert len(result) == 1
    assert "boom" in result[0]["error"]


@pytest.mark.asyncio
async def test_advanced_search_wraps_exception() -> None:
    with patch.object(srv, "advanced_google_scholar_search", side_effect=ValueError("bad")):
        result = await srv.search_google_scholar_advanced("q", author="X")
    assert "bad" in result[0]["error"]


@pytest.mark.asyncio
async def test_get_author_info_passes_through() -> None:
    payload = {"name": "Jane", "publications": []}
    with patch.object(srv, "_get_author_info", return_value=payload) as m:
        result = await srv.get_author_info("Jane")
    m.assert_called_once_with("Jane")
    assert result == payload


@pytest.mark.asyncio
async def test_get_author_info_wraps_exception() -> None:
    with patch.object(srv, "_get_author_info", side_effect=KeyError("k")):
        result = await srv.get_author_info("Jane")
    assert "error" in result
