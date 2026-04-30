from bs4 import BeautifulSoup

from app.parsers.common import parse_entity_page


def parse_weapon(
    soup: BeautifulSoup,
    source_url: str,
    scraped_at: str | None = None,
) -> dict:
    return parse_entity_page(soup, source_url, "weapon", scraped_at=scraped_at)
