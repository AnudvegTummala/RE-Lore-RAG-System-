from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.utils.cleaner import clean_wiki_text, slug


def parse_enemy(soup: BeautifulSoup, source_url: str, scraped_at: str | None = None) -> dict:
    title_tag = soup.find("h1", class_="page-header__title")
    name = title_tag.get_text(strip=True) if title_tag else "Unknown"

    frontmatter = {
        "id": f"enemy-{slug(name)}",
        "entity_type": "enemy",
        "title": name,
        "source_name": "Resident Evil Wiki",
        "source_url": source_url,
        "franchise": "Resident Evil",
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
        "tags": [],
        "image_refs": [],
    }

    return {"frontmatter": frontmatter, "body": f"# {name}", "slug": f"enemy-{slug(name)}"}
