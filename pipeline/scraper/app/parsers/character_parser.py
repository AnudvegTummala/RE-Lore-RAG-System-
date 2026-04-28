from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.utils.cleaner import clean_wiki_text, slug


def parse_character(soup: BeautifulSoup, source_url: str, scraped_at: str | None = None) -> dict:
    title = soup.find("h1", class_="page-header__title")
    name = title.get_text(strip=True) if title else "Unknown"

    sections: dict[str, str] = {}
    for heading in soup.find_all(["h2", "h3"]):
        section_name = heading.get_text(strip=True)
        content_parts = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h2", "h3"):
                break
            content_parts.append(clean_wiki_text(sibling.get_text(separator=" ")))
        if content_parts:
            sections[section_name] = " ".join(content_parts)

    frontmatter = {
        "id": f"character-{slug(name)}",
        "entity_type": "character",
        "title": name,
        "source_name": "Resident Evil Wiki",
        "source_url": source_url,
        "franchise": "Resident Evil",
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
        "tags": [],
        "image_refs": [],
    }

    body_parts = [f"# {name}"]
    for section, content in sections.items():
        body_parts.append(f"\n## {section}\n{content}")
    body = "\n".join(body_parts)

    return {"frontmatter": frontmatter, "body": body, "slug": f"character-{slug(name)}"}
