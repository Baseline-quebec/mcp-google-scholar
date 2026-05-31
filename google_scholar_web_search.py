"""Direct Google Scholar scraping helpers (no third-party scholarly stack).

This module deliberately avoids the ``scholarly`` dependency (and its
transitive ``free-proxy`` / ``fake-useragent`` / ``selenium`` chain). Every
request goes straight to ``scholar.google.com`` with ``requests`` + ``bs4``.
"""

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlencode

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
}
_TIMEOUT = 20

# Markers specific to Google's anti-bot interstitial. Kept narrow on purpose:
# a bare "captcha" substring would false-positive on legitimate results about
# CAPTCHA research, so we rely on phrases that only the block page contains.
_BLOCK_MARKERS = ("/sorry/", "unusual traffic", "not a robot")


def _is_blocked(html: str) -> bool:
    """Detect Google Scholar's CAPTCHA / rate-limit interstitial."""
    lowered = html.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _parse_int(text: str) -> int:
    """Parse an integer that may carry thousands separators; 0 on failure."""
    digits = text.replace(",", "").replace("\xa0", "").strip()
    return int(digits) if digits.isdigit() else 0


def _parse_results(html: str, num_results: int) -> List[Dict[str, Any]]:
    """Parse a Google Scholar results page into a list of article dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []

    for item in soup.find_all("div", class_="gs_ri"):
        if len(results) >= num_results:
            break

        title_tag = item.find("h3", class_="gs_rt")
        title = title_tag.get_text(strip=True) if title_tag else "No title available"

        link_tag = title_tag.find("a") if title_tag else None
        link = link_tag.get("href", "No link available") if link_tag else "No link available"

        authors_tag = item.find("div", class_="gs_a")
        authors = authors_tag.get_text(strip=True) if authors_tag else "No authors available"

        abstract_tag = item.find("div", class_="gs_rs")
        abstract = abstract_tag.get_text(strip=True) if abstract_tag else "No abstract available"

        results.append(
            {
                "Title": title,
                "Authors": authors,
                "Abstract": abstract,
                "URL": link,
            }
        )

    return results


def google_scholar_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Search Google Scholar using a simple keyword query."""
    search_url = f"https://scholar.google.com/scholar?q={quote_plus(query)}"
    response = requests.get(search_url, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200:
        return [{"error": f"Failed to fetch data. HTTP Status code: {response.status_code}"}]
    if _is_blocked(response.text):
        return [{"error": "Google Scholar served a CAPTCHA / rate limit; try again later."}]
    return _parse_results(response.text, num_results)


def advanced_google_scholar_search(
    query: str,
    author: Optional[str] = None,
    year_range: Optional[Tuple[int, int]] = None,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """Search Google Scholar using advanced filters (author, year range)."""
    params: Dict[str, Any] = {"q": query}
    if author:
        params["as_sauthors"] = author
    if year_range:
        start_year, end_year = year_range
        params["as_ylo"] = start_year
        params["as_yhi"] = end_year

    search_url = "https://scholar.google.com/scholar?" + urlencode(params)
    response = requests.get(search_url, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200:
        return [{"error": f"Failed to fetch data. HTTP Status code: {response.status_code}"}]
    if _is_blocked(response.text):
        return [{"error": "Google Scholar served a CAPTCHA / rate limit; try again later."}]
    return _parse_results(response.text, num_results)


def _find_author_id(author_name: str) -> Optional[str]:
    """Resolve an author name to a Google Scholar author id via profile search."""
    search_url = (
        "https://scholar.google.com/citations?view_op=search_authors&mauthors="
        f"{quote_plus(author_name)}&hl=en"
    )
    response = requests.get(search_url, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200 or _is_blocked(response.text):
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    first = soup.find("h3", class_="gs_ai_name")
    link = first.find("a") if first else None
    if not link or "href" not in link.attrs:
        return None

    href = link["href"]  # e.g. /citations?user=XXXX&hl=en
    if "user=" not in href:
        return None
    return href.split("user=", 1)[1].split("&", 1)[0]


def get_author_info(author_name: str, max_publications: int = 5) -> Dict[str, Any]:
    """Scrape an author's public Google Scholar profile (no scholarly dep)."""
    author_id = _find_author_id(author_name)
    if not author_id:
        return {
            "error": (
                f"No Google Scholar profile found for '{author_name}' "
                "(or Google Scholar served a CAPTCHA / rate limit)."
            )
        }

    profile_url = (
        f"https://scholar.google.com/citations?user={quote_plus(author_id)}"
        "&hl=en&cstart=0&pagesize=100"
    )
    response = requests.get(profile_url, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200:
        return {"error": f"Failed to fetch profile. HTTP Status code: {response.status_code}"}
    if _is_blocked(response.text):
        return {"error": "Google Scholar served a CAPTCHA / rate limit; try again later."}

    soup = BeautifulSoup(response.text, "html.parser")

    name_tag = soup.find(id="gsc_prf_in")
    name = name_tag.get_text(strip=True) if name_tag else "N/A"

    affiliation_tag = soup.find("div", class_="gsc_prf_il")
    affiliation = affiliation_tag.get_text(strip=True) if affiliation_tag else "N/A"

    interests = [a.get_text(strip=True) for a in soup.select("#gsc_prf_int a")]

    cited_cells = soup.select("td.gsc_rsb_std")
    citedby = _parse_int(cited_cells[0].get_text()) if cited_cells else 0

    publications: List[Dict[str, Any]] = []
    for row in soup.select("tr.gsc_a_tr")[:max_publications]:
        title_tag = row.select_one("a.gsc_a_at")
        year_tag = row.select_one("span.gsc_a_h")
        citations_tag = row.select_one("a.gsc_a_ac")
        publications.append(
            {
                "title": title_tag.get_text(strip=True) if title_tag else "N/A",
                "year": year_tag.get_text(strip=True) if year_tag else "N/A",
                "citations": _parse_int(citations_tag.get_text()) if citations_tag else 0,
            }
        )

    return {
        "name": name,
        "affiliation": affiliation,
        "interests": interests,
        "citedby": citedby,
        "publications": publications,
    }


if __name__ == "__main__":
    for result in google_scholar_search("machine learning", num_results=3):
        print(result)
    print(get_author_info("Steven A Cholewiak"))
