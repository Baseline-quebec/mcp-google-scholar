"""Tests for the direct Google Scholar scraping helpers.

Every test exercises real parsing logic against fixture HTML; network access
is replaced by a fake ``requests.get``. Each assertion is chosen so that
inverting the corresponding branch in the implementation turns the test red.
"""

from typing import List, Optional
from unittest.mock import patch

import pytest

import google_scholar_web_search as gs

# --------------------------------------------------------------------------- #
# Fixtures HTML
# --------------------------------------------------------------------------- #

RESULTS_HTML = """
<html><body>
  <div class="gs_ri">
    <h3 class="gs_rt"><a href="http://example.com/p1">Paper One</a></h3>
    <div class="gs_a">A Author, B Author - 2020 - example.com</div>
    <div class="gs_rs">Abstract of the first paper.</div>
  </div>
  <div class="gs_ri">
    <h3 class="gs_rt"><a href="http://example.com/p2">Paper Two</a></h3>
    <div class="gs_a">C Author - 2021 - example.org</div>
    <div class="gs_rs">Abstract of the second paper.</div>
  </div>
</body></html>
"""

# A result block missing the link href, the authors and the abstract.
PARTIAL_RESULTS_HTML = """
<html><body>
  <div class="gs_ri">
    <h3 class="gs_rt"><a>Titleless link</a></h3>
  </div>
</body></html>
"""

# Legitimate results page that happens to be about CAPTCHA research; must NOT
# be treated as a block page (regression for the old bare-substring check).
CAPTCHA_TOPIC_HTML = """
<html><body>
  <div class="gs_ri">
    <h3 class="gs_rt"><a href="http://example.com/c">Breaking CAPTCHA systems</a></h3>
    <div class="gs_a">D Author - 2019 - example.com</div>
    <div class="gs_rs">A study of captcha solving with deep learning.</div>
  </div>
</body></html>
"""

BLOCK_HTML = """
<html><body>
  Our systems have detected unusual traffic from your computer network.
  Please show you're not a robot.
</body></html>
"""

AUTHOR_SEARCH_HTML = """
<html><body>
  <div class="gs_ai_t">
    <h3 class="gs_ai_name"><a href="/citations?user=ABC123&amp;hl=en">Jane Doe</a></h3>
  </div>
</body></html>
"""

AUTHOR_SEARCH_NO_RESULT_HTML = "<html><body><div>No results</div></body></html>"

# A profile link that lacks the ``user=`` query parameter.
AUTHOR_SEARCH_NO_USER_HTML = """
<html><body>
  <h3 class="gs_ai_name"><a href="/citations?hl=en">Jane Doe</a></h3>
</body></html>
"""

# A profile entry whose anchor has no href at all.
AUTHOR_SEARCH_NO_HREF_HTML = """
<html><body>
  <h3 class="gs_ai_name"><a>Jane Doe</a></h3>
</body></html>
"""

PROFILE_HTML = """
<html><body>
  <div id="gsc_prf_in">Jane Doe</div>
  <div class="gsc_prf_il">Professor, University of Test</div>
  <div id="gsc_prf_int">
    <a class="gsc_prf_inta" href="#">Machine Learning</a>
    <a class="gsc_prf_inta" href="#">Optimization</a>
  </div>
  <table>
    <tr><td class="gsc_rsb_sc1">Citations</td><td class="gsc_rsb_std">1,234</td></tr>
  </table>
  <table id="gsc_a_b">
    <tr class="gsc_a_tr">
      <td class="gsc_a_t"><a class="gsc_a_at">First Publication</a></td>
      <td class="gsc_a_c"><a class="gsc_a_ac">100</a></td>
      <td class="gsc_a_y"><span class="gsc_a_h">2020</span></td>
    </tr>
    <tr class="gsc_a_tr">
      <td class="gsc_a_t"><a class="gsc_a_at">Second Publication</a></td>
      <td class="gsc_a_c"><a class="gsc_a_ac">2,500</a></td>
      <td class="gsc_a_y"><span class="gsc_a_h">2021</span></td>
    </tr>
    <tr class="gsc_a_tr">
      <td class="gsc_a_t"><a class="gsc_a_at">Third Publication</a></td>
      <td class="gsc_a_c"><a class="gsc_a_ac"></a></td>
      <td class="gsc_a_y"><span class="gsc_a_h">2022</span></td>
    </tr>
  </table>
</body></html>
"""


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


def _patch_get(responses: List[FakeResponse]):
    """Patch ``gs.requests.get`` to yield the given responses in order."""
    return patch.object(gs.requests, "get", side_effect=responses)


# --------------------------------------------------------------------------- #
# _is_blocked
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "html, expected",
    [
        (BLOCK_HTML, True),
        ("<html>redirected to /sorry/index</html>", True),
        ("<html>please show you're not a robot</html>", True),
        (RESULTS_HTML, False),
        (CAPTCHA_TOPIC_HTML, False),  # regression: "captcha" word must not block
        ("", False),
    ],
)
def test_is_blocked(html: str, expected: bool) -> None:
    assert gs._is_blocked(html) is expected


# --------------------------------------------------------------------------- #
# _parse_int
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("42", 42),
        ("1,234", 1234),
        ("2\xa0500", 2500),
        ("", 0),
        ("N/A", 0),
        ("  7 ", 7),
    ],
)
def test_parse_int(text: str, expected: int) -> None:
    assert gs._parse_int(text) == expected


# --------------------------------------------------------------------------- #
# _parse_results
# --------------------------------------------------------------------------- #


def test_parse_results_extracts_all_fields() -> None:
    results = gs._parse_results(RESULTS_HTML, num_results=5)
    assert len(results) == 2
    assert results[0] == {
        "Title": "Paper One",
        "Authors": "A Author, B Author - 2020 - example.com",
        "Abstract": "Abstract of the first paper.",
        "URL": "http://example.com/p1",
    }
    assert results[1]["URL"] == "http://example.com/p2"


def test_parse_results_respects_num_results() -> None:
    assert len(gs._parse_results(RESULTS_HTML, num_results=1)) == 1
    assert len(gs._parse_results(RESULTS_HTML, num_results=0)) == 0


def test_parse_results_handles_missing_fields_without_keyerror() -> None:
    # Regression: an <a> tag without href must not raise KeyError.
    results = gs._parse_results(PARTIAL_RESULTS_HTML, num_results=5)
    assert len(results) == 1
    assert results[0]["URL"] == "No link available"
    assert results[0]["Authors"] == "No authors available"
    assert results[0]["Abstract"] == "No abstract available"
    assert results[0]["Title"] == "Titleless link"


def test_parse_results_empty_page() -> None:
    assert gs._parse_results("<html><body></body></html>", num_results=5) == []


# --------------------------------------------------------------------------- #
# _find_author_id
# --------------------------------------------------------------------------- #


def test_find_author_id_extracts_id() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_HTML)]):
        assert gs._find_author_id("Jane Doe") == "ABC123"


def test_find_author_id_no_result_returns_none() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_NO_RESULT_HTML)]):
        assert gs._find_author_id("Nobody") is None


def test_find_author_id_blocked_returns_none() -> None:
    with _patch_get([FakeResponse(BLOCK_HTML)]):
        assert gs._find_author_id("Jane Doe") is None


def test_find_author_id_http_error_returns_none() -> None:
    with _patch_get([FakeResponse("", status_code=503)]):
        assert gs._find_author_id("Jane Doe") is None


def test_find_author_id_href_without_user_returns_none() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_NO_USER_HTML)]):
        assert gs._find_author_id("Jane Doe") is None


def test_find_author_id_anchor_without_href_returns_none() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_NO_HREF_HTML)]):
        assert gs._find_author_id("Jane Doe") is None


# --------------------------------------------------------------------------- #
# google_scholar_search
# --------------------------------------------------------------------------- #


def test_google_scholar_search_success() -> None:
    with _patch_get([FakeResponse(RESULTS_HTML)]):
        results = gs.google_scholar_search("deep learning", num_results=2)
    assert [r["Title"] for r in results] == ["Paper One", "Paper Two"]


def test_google_scholar_search_block_returns_error() -> None:
    with _patch_get([FakeResponse(BLOCK_HTML)]):
        results = gs.google_scholar_search("anything")
    assert len(results) == 1
    assert "CAPTCHA" in results[0]["error"]


def test_google_scholar_search_http_error_returns_error() -> None:
    with _patch_get([FakeResponse("", status_code=429)]):
        results = gs.google_scholar_search("anything")
    assert "429" in results[0]["error"]


def test_google_scholar_search_captcha_topic_is_not_blocked() -> None:
    # A legitimate query about CAPTCHAs must still return parsed results.
    with _patch_get([FakeResponse(CAPTCHA_TOPIC_HTML)]):
        results = gs.google_scholar_search("captcha solving")
    assert results[0]["Title"] == "Breaking CAPTCHA systems"


# --------------------------------------------------------------------------- #
# advanced_google_scholar_search
# --------------------------------------------------------------------------- #


def test_advanced_search_builds_filter_params() -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs):
        captured["url"] = url
        return FakeResponse(RESULTS_HTML)

    with patch.object(gs.requests, "get", side_effect=fake_get):
        gs.advanced_google_scholar_search(
            "neural nets", author="Hinton", year_range=(2010, 2020), num_results=2
        )

    url = captured["url"]
    assert "as_sauthors=Hinton" in url
    assert "as_ylo=2010" in url
    assert "as_yhi=2020" in url


def test_advanced_search_omits_unset_filters() -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs):
        captured["url"] = url
        return FakeResponse(RESULTS_HTML)

    with patch.object(gs.requests, "get", side_effect=fake_get):
        gs.advanced_google_scholar_search("neural nets")

    url = captured["url"]
    assert "as_sauthors" not in url
    assert "as_ylo" not in url


def test_advanced_search_block_returns_error() -> None:
    with _patch_get([FakeResponse(BLOCK_HTML)]):
        results = gs.advanced_google_scholar_search("anything")
    assert "CAPTCHA" in results[0]["error"]


def test_advanced_search_http_error_returns_error() -> None:
    with _patch_get([FakeResponse("", status_code=500)]):
        results = gs.advanced_google_scholar_search("anything")
    assert "500" in results[0]["error"]


# --------------------------------------------------------------------------- #
# get_author_info
# --------------------------------------------------------------------------- #


def test_get_author_info_parses_profile() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_HTML), FakeResponse(PROFILE_HTML)]):
        info = gs.get_author_info("Jane Doe")

    assert info["name"] == "Jane Doe"
    assert info["affiliation"] == "Professor, University of Test"
    assert info["interests"] == ["Machine Learning", "Optimization"]
    assert info["citedby"] == 1234  # thousands separator parsed
    assert len(info["publications"]) == 3
    assert info["publications"][0] == {
        "title": "First Publication",
        "year": "2020",
        "citations": 100,
    }
    assert info["publications"][1]["citations"] == 2500
    assert info["publications"][2]["citations"] == 0  # empty citation cell


def test_get_author_info_respects_max_publications() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_HTML), FakeResponse(PROFILE_HTML)]):
        info = gs.get_author_info("Jane Doe", max_publications=2)
    assert len(info["publications"]) == 2


def test_get_author_info_not_found_returns_error() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_NO_RESULT_HTML)]):
        info = gs.get_author_info("Nobody")
    assert "error" in info
    assert "Nobody" in info["error"]


def test_get_author_info_profile_blocked_returns_error() -> None:
    # Author id resolves, but the profile page is a CAPTCHA wall.
    with _patch_get([FakeResponse(AUTHOR_SEARCH_HTML), FakeResponse(BLOCK_HTML)]):
        info = gs.get_author_info("Jane Doe")
    assert "error" in info
    assert "CAPTCHA" in info["error"]


def test_get_author_info_profile_http_error_returns_error() -> None:
    with _patch_get([FakeResponse(AUTHOR_SEARCH_HTML), FakeResponse("", status_code=500)]):
        info = gs.get_author_info("Jane Doe")
    assert "500" in info["error"]


# --------------------------------------------------------------------------- #
# Type sanity
# --------------------------------------------------------------------------- #


def test_year_range_type_alias_is_optional() -> None:
    # The default path (no filters) must not raise on a None year_range.
    sig: Optional[tuple] = None
    with _patch_get([FakeResponse(RESULTS_HTML)]):
        results = gs.advanced_google_scholar_search("x", year_range=sig)
    assert isinstance(results, list)
