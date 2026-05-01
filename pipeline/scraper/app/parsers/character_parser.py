from bs4 import BeautifulSoup

from app.parsers.common import parse_entity_page


def parse_character(
    soup: BeautifulSoup,
    source_url: str,
    scraped_at: str | None = None,
    *,
    api_title: str | None = None,
    api_categories: list[str] | None = None,
) -> dict:
    return parse_entity_page(soup, source_url, "character", scraped_at=scraped_at, api_title=api_title, api_categories=api_categories)
