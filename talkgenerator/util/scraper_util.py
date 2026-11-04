from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def create_page_scraper(
    scraping_function: Callable[[str, int], Sequence[T] | None],
) -> Callable[[str, int], list[T]]:
    def scrape_pages(search_term: str, amount: int) -> list[T]:
        results: list[T] = []
        page = 1
        while len(results) < amount:
            new_quotes = scraping_function(search_term, page)
            if not new_quotes:
                break
            results.extend(new_quotes)
            page += 1

        return results[0:amount]

    return scrape_pages
