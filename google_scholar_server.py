import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

from google_scholar_web_search import (
    advanced_google_scholar_search,
    get_author_info as _get_author_info,
    google_scholar_search,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize FastMCP server for Google Scholar
mcp = FastMCP("scholar_pubmed")


@mcp.tool()
async def search_google_scholar_key_words(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Search for articles on Google Scholar using key words.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)

    Returns:
        List of dictionaries containing article information
    """
    logging.info("Searching Google Scholar: query=%r, num_results=%s", query, num_results)
    try:
        return await asyncio.to_thread(google_scholar_search, query, num_results)
    except Exception as e:
        return [{"error": f"An error occurred while searching Google Scholar: {str(e)}"}]


@mcp.tool()
async def search_google_scholar_advanced(
    query: str,
    author: Optional[str] = None,
    year_range: Optional[Tuple[int, int]] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """Search for articles on Google Scholar using advanced filters.

    Args:
        query: General search query
        author: Author name
        year_range: tuple containing (start_year, end_year)
        num_results: Number of results to return (default: 5)

    Returns:
        List of dictionaries containing article information
    """
    logging.info(
        "Advanced search: query=%r, author=%r, year_range=%s, num_results=%s",
        query,
        author,
        year_range,
        num_results,
    )
    try:
        return await asyncio.to_thread(
            advanced_google_scholar_search, query, author, year_range, num_results
        )
    except Exception as e:
        return [{"error": f"An error occurred while performing advanced search: {str(e)}"}]


@mcp.tool()
async def get_author_info(author_name: str) -> Dict[str, Any]:
    """Get detailed information about an author from Google Scholar.

    Args:
        author_name: Name of the author to search for

    Returns:
        Dictionary containing author information
    """
    logging.info("Retrieving author information for: %r", author_name)
    try:
        return await asyncio.to_thread(_get_author_info, author_name)
    except Exception as e:
        return {"error": f"An error occurred while retrieving author information: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
