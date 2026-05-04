"""Shared parsing logic for Fandom entity pages.

Every category-specific parser delegates here. The output shape is uniform
across all entity types — only ``entity_type`` and the choice of which
infobox keys to harvest as relations differ.
"""

from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from app.utils.cleaner import (
    clean_wiki_text,
    is_ui_image,
    normalize_image_url,
    slug,
)

# Headings whose content we drop entirely.
_TRAILING_SECTIONS = {
    "references",
    "notes",
    "external links",
    "see also",
    "further reading",
    "navigation",
}

# Top-level container classes that aren't body content.
_NON_CONTENT_CLASSES = (
    "navbox",
    "noprint",
    "succession-box",
    "references",
    "reflist",
    "toc",
    "infobox",
    "portable-infobox",
    "notice",
    "sidebar",
    "ambox",
    "gallery",
    "thumb",
    "messagebox",
)

# Infobox label keywords whose linked values are taken as related games.
_GAME_INFOBOX_LABELS = (
    "appearance",
    "appearances",
    "game",
    "games",
    "debut",
    "first appearance",
    "origin",
    "originated",
    "series",
    "title",
)


def _has_non_content_class(tag: Tag) -> bool:
    classes = tag.get("class") or []
    return any(any(needle in c.lower() for needle in _NON_CONTENT_CLASSES) for c in classes)


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1", class_="page-header__title")
    if h1:
        return clean_wiki_text(h1.get_text(separator=" "))
    h1 = soup.find("h1", id="firstHeading")
    if h1:
        return clean_wiki_text(h1.get_text(separator=" "))
    if soup.title:
        return clean_wiki_text(soup.title.get_text(separator=" ").split("|")[0])
    return "Unknown"


def _extract_categories(soup: BeautifulSoup) -> list[str]:
    """Page-footer category links — used as tags."""
    tags: list[str] = []
    seen: set[str] = set()
    for a in soup.select(".page-header__categories a, #articleCategories a, .page-categories a"):
        text = clean_wiki_text(a.get_text(separator=" "))
        if not text:
            continue
        s = slug(text)
        if s and s not in seen:
            seen.add(s)
            tags.append(s)
    # Fallback: catlinks in classic MediaWiki layout
    for a in soup.select("#catlinks a"):
        text = clean_wiki_text(a.get_text(separator=" "))
        if not text or text.lower() in ("categories", "category"):
            continue
        s = slug(text)
        if s and s not in seen:
            seen.add(s)
            tags.append(s)
    return tags


def _extract_infobox(soup: BeautifulSoup) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (key_value_pairs, key_to_links).

    ``key_to_links`` maps each label to the list of linked-text values inside
    that row, used to harvest related entities (related games, organizations,
    etc.).
    """
    pairs: dict[str, str] = {}
    links: dict[str, list[str]] = {}
    aside = soup.select_one("aside.portable-infobox")
    if not aside:
        return pairs, links
    for row in aside.select(".pi-data"):
        label_el = row.select_one(".pi-data-label")
        value_el = row.select_one(".pi-data-value")
        if not label_el or not value_el:
            continue
        label = clean_wiki_text(label_el.get_text(separator=" "))
        value = clean_wiki_text(value_el.get_text(separator=" "))
        if not label:
            continue
        pairs[label] = value
        link_texts: list[str] = []
        for a in value_el.find_all("a"):
            t = clean_wiki_text(a.get_text(separator=" "))
            if t:
                link_texts.append(t)
        if link_texts:
            links[label] = link_texts
    return pairs, links


def _related_games_from_infobox(infobox_links: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for label, values in infobox_links.items():
        if not any(needle in label.lower() for needle in _GAME_INFOBOX_LABELS):
            continue
        for v in values:
            s = slug(v)
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _is_trailing_heading(text: str) -> bool:
    return text.strip().lower() in _TRAILING_SECTIONS


def _list_to_markdown(list_tag: Tag, ordered: bool) -> str:
    lines: list[str] = []
    for i, li in enumerate(list_tag.find_all("li", recursive=False), start=1):
        text = clean_wiki_text(li.get_text(separator=" "))
        if not text:
            continue
        prefix = f"{i}. " if ordered else "- "
        lines.append(prefix + text)
    return "\n".join(lines)


def _extract_body_and_images(
    soup: BeautifulSoup,
    entity_slug: str,
) -> tuple[list[dict], list[dict]]:
    """Walk the article body and emit (sections, images).

    Sections is a list of ``{"name": str, "content": str}`` and is guaranteed
    to start with a "Summary" section (which may be empty if no preamble).
    """
    parser_output = soup.select_one(".mw-parser-output") or soup.select_one("#mw-content-text")
    sections: list[dict] = [{"name": "Summary", "content": ""}]
    images: list[dict] = []
    seen_image_urls: set[str] = set()
    img_idx = 0
    skip_until_next_h2 = False
    current_section = "Infobox"

    if not parser_output:
        return sections, images

    # Capture infobox image first so it's image_id 01.
    aside = soup.select_one("aside.portable-infobox")
    if aside:
        for img in aside.find_all("img"):
            entry = _make_image_entry(img, entity_slug, img_idx, seen_image_urls, current_section)
            if entry:
                images.append(entry)
                img_idx += 1

    current_section = "Summary"

    for element in parser_output.find_all(recursive=False):
        if not isinstance(element, Tag):
            continue
        if _has_non_content_class(element):
            continue
        name = element.name

        if name in ("h2", "h3"):
            heading_text = clean_wiki_text(element.get_text(separator=" "))
            if not heading_text:
                continue
            if _is_trailing_heading(heading_text):
                skip_until_next_h2 = name == "h2"
                if name == "h2":
                    # Drop everything until end (or until another h2 we'd want)
                    # Trailing sections are at the end of the page on Fandom.
                    break
                continue
            if skip_until_next_h2 and name != "h2":
                continue
            skip_until_next_h2 = False
            current_section = heading_text
            sections.append({"name": heading_text, "content": ""})
            continue

        if skip_until_next_h2:
            continue

        if name == "p":
            text = clean_wiki_text(element.get_text(separator=" "))
            if text:
                sections[-1]["content"] += text + "\n\n"
        elif name == "ul":
            md = _list_to_markdown(element, ordered=False)
            if md:
                sections[-1]["content"] += md + "\n\n"
        elif name == "ol":
            md = _list_to_markdown(element, ordered=True)
            if md:
                sections[-1]["content"] += md + "\n\n"
        elif name == "blockquote":
            text = clean_wiki_text(element.get_text(separator=" "))
            if text:
                sections[-1]["content"] += f"> {text}\n\n"
        elif name == "div":
            # Recurse into a content div (some wikis nest content)
            for child in element.find_all(["p", "ul", "ol"], recursive=False):
                if child.name == "p":
                    text = clean_wiki_text(child.get_text(separator=" "))
                    if text:
                        sections[-1]["content"] += text + "\n\n"
                elif child.name in ("ul", "ol"):
                    md = _list_to_markdown(child, ordered=child.name == "ol")
                    if md:
                        sections[-1]["content"] += md + "\n\n"

        # Capture inline images: the element itself if it's an <img>, plus
        # any nested <img> descendants.
        img_elements = [element] if name == "img" else element.find_all("img")
        for img in img_elements:
            entry = _make_image_entry(img, entity_slug, img_idx, seen_image_urls, current_section)
            if entry:
                images.append(entry)
                img_idx += 1

    return sections, images


def _extract_caption(img: Tag) -> str:
    """Walk up from an <img> to find a Fandom/MediaWiki figure caption.

    Checks (in order):
    1. <figcaption> sibling or ancestor
    2. .thumbcaption inside the nearest .thumbinner wrapper
    3. .caption class anywhere in the nearest figure-like ancestor
    """
    # Walk up at most 5 levels to find a caption container.
    node = img.parent
    for _ in range(5):
        if node is None:
            break
        if node.name == "figure":
            figcaption = node.find("figcaption")
            if figcaption:
                return clean_wiki_text(figcaption.get_text(separator=" "))
        thumbcaption = node.find(class_="thumbcaption")
        if thumbcaption:
            return clean_wiki_text(thumbcaption.get_text(separator=" "))
        caption_el = node.find(class_="caption")
        if caption_el:
            return clean_wiki_text(caption_el.get_text(separator=" "))
        node = node.parent
    return ""


def _make_image_entry(
    img: Tag,
    entity_slug: str,
    idx: int,
    seen_urls: set[str],
    section: str = "",
) -> dict | None:
    src = img.get("data-src") or img.get("src") or ""
    if not src or is_ui_image(src):
        return None
    src = normalize_image_url(src)
    if src in seen_urls:
        return None
    seen_urls.add(src)
    alt = clean_wiki_text(img.get("alt", "") or "")
    caption = _extract_caption(img)
    image_id = f"{entity_slug}-img-{idx + 1:02d}"
    return {
        "image_id": image_id,
        "source_url": src,
        "alt_text": alt,
        "caption": caption,
        "section": section,
        "is_concept_art": _looks_like_concept_art(src, alt),
    }


def _looks_like_concept_art(url: str, alt: str) -> bool:
    haystack = f"{url} {alt}".lower()
    return any(needle in haystack for needle in ("concept", "artwork", "design sketch"))


def _build_body_markdown(title: str, sections: list[dict]) -> str:
    parts: list[str] = [f"# {title}", ""]
    for sec in sections:
        content = sec["content"].strip()
        if sec["name"] == "Summary":
            if content:
                parts.append(content)
                parts.append("")
            continue
        parts.append(f"## {sec['name']}")
        parts.append("")
        if content:
            parts.append(content)
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def parse_entity_page(
    soup: BeautifulSoup,
    source_url: str,
    entity_type: str,
    *,
    scraped_at: str | None = None,
    api_title: str | None = None,
    api_categories: list[str] | None = None,
) -> dict:
    """Parse a Fandom article into the canonical entity record."""
    title = api_title or _extract_title(soup)
    name_slug = slug(title) or "unknown"
    entity_slug = f"{entity_type}-{name_slug}"

    infobox_pairs, infobox_links = _extract_infobox(soup)
    related_games = _related_games_from_infobox(infobox_links)
    # Prefer API-supplied categories (reliable); fall back to HTML scraping.
    if api_categories is not None:
        tags = [slug(c) for c in api_categories if slug(c)]
    else:
        tags = _extract_categories(soup)
    sections, images = _extract_body_and_images(soup, name_slug)
    body_md = _build_body_markdown(title, sections)

    image_refs = [img["image_id"] for img in images]

    frontmatter: dict = {
        "id": entity_slug,
        "entity_type": entity_type,
        "title": title,
        "source_name": "Resident Evil Wiki",
        "source_url": source_url,
        "franchise": "Resident Evil",
        "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
        "tags": tags,
        "image_refs": image_refs,
        "related_games": related_games,
    }
    if infobox_pairs:
        frontmatter["infobox"] = infobox_pairs

    return {
        "frontmatter": frontmatter,
        "body": body_md,
        "slug": name_slug,
        "images": images,
    }
