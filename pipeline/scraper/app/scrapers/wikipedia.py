"""Supplements game markdown files with targeted Wikipedia sections.

Reads existing files under ``data/raw/markdown/games/``. For each, fetches
the Wikipedia page and appends lore-relevant sections under a
``## Wikipedia`` heading. Idempotent: if the marker heading is already
present the file is left unchanged.

Sections harvested (in order, whichever exist on the page):
  Gameplay, Plot, Synopsis, Story, Setting, Characters, Narrative

Development, Reception, Release, Sales and similar off-topic sections
are intentionally excluded to keep the corpus clean for RAG.

Title resolution tries up to three candidates in order:
  1. The plain game title (e.g. "Resident Evil 4")
  2. "{title} (video game)"
  3. "Resident Evil {roman-numeral}" for titles ending in a digit 2-7

Files are processed sequentially — Wikipedia's Terms of Service ask for a
polite crawl rate and the library is synchronous, so each call runs in a
thread executor to avoid blocking the event loop.
"""

import asyncio
import logging
import re
from pathlib import Path

import wikipediaapi
import yaml

from app.scrapers.base import BaseScraper
from app.utils.manifests import ScrapeManifest, SourceRegistry

logger = logging.getLogger(__name__)

_MARKDOWN_GAMES_DIR = Path("/data/raw/markdown/games")
_MARKER = "## Wikipedia"

_ROMAN = {2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}

# Sections to harvest, checked case-insensitively against page section titles.
# Order matters — sections are appended in the order they appear in this list.
_WANTED_SECTIONS = (
    "gameplay",
    "plot",
    "synopsis",
    "story",
    "setting",
    "characters",
    "narrative",
)

_WIKI = wikipediaapi.Wikipedia(
    user_agent="RE-Lore-RAG-System/1.0 (hamd.ashfaque@gmail.com)",
    language="en",
    extract_format=wikipediaapi.ExtractFormat.WIKI,
)


def _candidate_titles(title: str) -> list[str]:
    candidates = [title, f"{title} (video game)"]
    m = re.search(r"\b(\d)\b$", title)
    if m:
        n = int(m.group(1))
        if n in _ROMAN:
            roman_title = title[: m.start()].rstrip() + " " + _ROMAN[n]
            candidates.append(roman_title)
    return candidates


def _fetch_sections_sync(title: str) -> tuple[str | None, str | None]:
    """Try each candidate title and return (harvested_text, page_url) on first hit."""
    for candidate in _candidate_titles(title):
        page = _WIKI.page(candidate)
        if not page.exists():
            continue

        # Build a lookup of lowercased section title → section object.
        sections_by_name = {s.title.lower(): s for s in page.sections}

        parts: list[str] = []
        for wanted in _WANTED_SECTIONS:
            sec = sections_by_name.get(wanted)
            if sec and sec.text.strip():
                parts.append(f"### {sec.title}\n\n{sec.text.strip()}")

        if not parts:
            # Page exists but has none of our target sections — skip.
            continue

        return "\n\n".join(parts), page.fullurl

    return None, None


class WikipediaScraper(BaseScraper):
    def __init__(
        self,
        source_registry: SourceRegistry,
        scrape_manifest: ScrapeManifest,
        *,
        max_pages: int = 500,
    ):
        super().__init__(max_pages=max_pages)
        self._registry = source_registry
        self._scrape_manifest = scrape_manifest

    async def run(self, target: str = "all") -> None:
        if target not in ("all", "games"):
            logger.info("WikipediaScraper: target=%s, skipping", target)
            return
        if not _MARKDOWN_GAMES_DIR.exists():
            logger.info("WikipediaScraper: %s does not exist, skipping", _MARKDOWN_GAMES_DIR)
            return

        files = sorted(_MARKDOWN_GAMES_DIR.glob("*.md"))
        if not files:
            logger.info("WikipediaScraper: no game markdown files found")
            return

        loop = asyncio.get_running_loop()
        supplemented = 0
        for path in files:
            if await self._supplement(loop, path):
                supplemented += 1

        logger.info("WikipediaScraper: supplemented %d/%d game files", supplemented, len(files))

    async def _supplement(self, loop: asyncio.AbstractEventLoop, path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8")
            if _MARKER in content:
                return False

            fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
            if not fm_match:
                logger.warning("No frontmatter detected in %s", path)
                return False
            fm = yaml.safe_load(fm_match.group(1)) or {}
            title = fm.get("title")
            if not title:
                return False

            text, page_url = await loop.run_in_executor(
                None, _fetch_sections_sync, title
            )

            if not text:
                logger.debug("No relevant Wikipedia sections found for: %s", title)
                self._registry.record(
                    f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}", None
                )
                return False

            self._registry.record(page_url, 200)
            new_content = content.rstrip() + f"\n\n{_MARKER}\n\n{text}\n"
            path.write_text(new_content, encoding="utf-8")
            logger.debug("Supplemented %s with %d chars", path.name, len(text))
            return True
        except Exception:
            logger.exception("Wikipedia supplement failed for %s", path)
            return False
