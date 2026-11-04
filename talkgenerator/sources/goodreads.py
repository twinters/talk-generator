"""Quotes scraped from Goodreads' quote search."""

from functools import lru_cache

from bs4 import BeautifulSoup

from talkgenerator.util import http_util, scraper_util

_QUOTE_SEARCH_URL = "https://www.goodreads.com/search"


@lru_cache(maxsize=64)
def _search_quotes_page(search_term: str, page: int) -> list[str] | None:
    params = {
        "page": page,
        "q": search_term,
        "search[source]": "goodreads",
        "search_type": "quotes",
        "tab": "quotes",
    }
    response = http_util.get(_QUOTE_SEARCH_URL, params=params, timeout=8)
    if response is None or not response.ok:
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    # Replace breaks with new lines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # The quote is the text before the em dash that precedes the author's name
    quote_elements = soup.find_all("div", class_="quoteText")
    quotes = [" ".join([part.strip() for part in quote.get_text().split("—")][0:-1]) for quote in quote_elements]
    return [quote for quote in quotes if quote]


search_quotes = scraper_util.create_page_scraper(_search_quotes_page)
