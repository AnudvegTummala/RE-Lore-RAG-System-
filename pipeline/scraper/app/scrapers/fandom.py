"""Fandom (Resident Evil Wiki) scraper.

For each configured category we walk the entire category listing (following
``category-page__pagination-next`` links until exhausted), then fetch each
linked article page, parse it via the matching category parser, and write a
markdown file with YAML frontmatter. Image references collected during
parsing are registered with the shared ``ImageManifest`` so the downstream
image downloader can fetch them.

Concurrency is bounded by the shared ``Semaphore(5)`` in ``BaseScraper``;
the rate limiter additionally enforces a 1.5-3.0s per-domain gap. The
checkpoint is consulted to skip already-scraped URLs and is auto-flushed
every 10 successful pages.
"""

import asyncio
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.parsers import (
    character_parser,
    enemy_parser,
    game_parser,
    location_parser,
    organization_parser,
    virus_parser,
    weapon_parser,
)
from app.scrapers.base import BaseScraper
from app.utils.checkpoint import Checkpoint
from app.utils.manifests import ImageManifest, ScrapeManifest, SourceRegistry
from app.utils.markdown_writer import MarkdownWriter

logger = logging.getLogger(__name__)

_BASE_URL = "https://residentevil.fandom.com"

# (category_key) -> (fandom path, entity_type, output folder)
_CATEGORIES: dict[str, tuple[str, str, str]] = {
    "characters":    ("/wiki/Category:Characters",             "character",    "characters"),
    "games":         ("/wiki/Category:Games",                  "game",         "games"),
    "enemies":       ("/wiki/Category:Enemies",                "enemy",        "enemies"),
    "locations":     ("/wiki/Category:Locations",              "location",     "locations"),
    "organizations": ("/wiki/Category:Organizations",          "organization", "organizations"),
    "viruses":       ("/wiki/Category:Viruses_and_Parasites",  "virus",        "viruses"),
    "weapons":       ("/wiki/Category:Weapons",                "weapon",       "weapons"),
}

_PARSERS = {
    "character":    character_parser.parse_character,
    "game":         game_parser.parse_game,
    "enemy":        enemy_parser.parse_enemy,
    "location":     location_parser.parse_location,
    "organization": organization_parser.parse_organization,
    "virus":        virus_parser.parse_virus,
    "weapon":       weapon_parser.parse_weapon,
}


class FandomScraper(BaseScraper):
    def __init__(
        self,
        image_manifest: ImageManifest,
        source_registry: SourceRegistry,
        scrape_manifest: ScrapeManifest,
        *,
        max_pages: int = 500,
    ):
        super().__init__(max_pages=max_pages)
        self._image_manifest = image_manifest
        self._registry = source_registry
        self._scrape_manifest = scrape_manifest
        self._checkpoint = Checkpoint("scraper_state")
        self._writer = MarkdownWriter()
        self._page_count = 0
        self._page_count_lock = asyncio.Lock()

    async def run(self, target: str = "all") -> None:
        if target == "all":
            categories = _CATEGORIES
        else:
            if target not in _CATEGORIES:
                logger.error("Unknown scrape target: %s", target)
                return
            categories = {target: _CATEGORIES[target]}

        async with self.build_client() as client:
            for cat_key, (path, entity_type, folder) in categories.items():
                if self._budget_remaining() <= 0:
                    logger.info("Page budget exhausted; stopping at category=%s", cat_key)
                    break
                logger.info("Scraping category: %s", cat_key)
                await self._scrape_category(client, cat_key, path, entity_type, folder)

        self._checkpoint.save()
        logger.info(
            "FandomScraper done. Pages this run: %d. Total in checkpoint: %d. Counts: %s",
            self._page_count,
            self._checkpoint.total,
            self._checkpoint.counts,
        )

    def _budget_remaining(self) -> int:
        return max(0, self.max_pages - self._page_count)

    async def _scrape_category(
        self,
        client: httpx.AsyncClient,
        category_key: str,
        path: str,
        entity_type: str,
        folder: str,
    ) -> None:
        category_url = urljoin(_BASE_URL, path)
        article_urls = await self._collect_article_urls(client, category_url)
        logger.info("  category=%s discovered=%d urls", category_key, len(article_urls))

        pending = [u for u in article_urls if not self._checkpoint.is_done(u)]
        skipped = len(article_urls) - len(pending)
        if skipped:
            logger.info("  category=%s skipping %d already-completed urls", category_key, skipped)

        budget = self._budget_remaining()
        if len(pending) > budget:
            logger.info(
                "  category=%s capping pending=%d to budget=%d",
                category_key, len(pending), budget,
            )
            pending = pending[:budget]

        tasks = [
            self._scrape_article(client, url, category_key, entity_type, folder)
            for url in pending
        ]
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=False)

    async def _collect_article_urls(
        self,
        client: httpx.AsyncClient,
        category_url: str,
    ) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        next_url: str | None = category_url
        page_no = 0
        while next_url:
            page_no += 1
            html = await self.fetch(client, next_url)
            self._registry.record(next_url, 200 if html else None)
            if not html:
                logger.warning("Could not fetch category listing %s", next_url)
                break
            soup = BeautifulSoup(html, "lxml")

            for a in soup.select("a.category-page__member-link"):
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("/wiki/Category:"):
                    continue  # subcategory
                full = urljoin(_BASE_URL, href)
                if full in seen:
                    continue
                seen.add(full)
                urls.append(full)

            nxt = soup.select_one("a.category-page__pagination-next")
            href = nxt.get("href") if nxt else None
            next_url = urljoin(_BASE_URL, href) if href else None
            if page_no > 200:
                logger.warning("Pagination guard tripped at %d pages for %s", page_no, category_url)
                break
        return urls

    async def _scrape_article(
        self,
        client: httpx.AsyncClient,
        url: str,
        category_key: str,
        entity_type: str,
        folder: str,
    ) -> None:
        try:
            html = await self.fetch(client, url)
            if not html:
                self._registry.record(url, None)
                self._scrape_manifest.record_page(category_key, success=False)
                return

            soup = BeautifulSoup(html, "lxml")
            parser = _PARSERS[entity_type]
            parsed = parser(soup, url)

            output_path = self._writer.write(
                folder,
                parsed["slug"],
                parsed["frontmatter"],
                parsed["body"],
            )

            for img in parsed["images"]:
                folder_for_image = "concept-art" if img["is_concept_art"] else folder
                self._image_manifest.add_reference(
                    image_id=img["image_id"],
                    source_url=img["source_url"],
                    entity_id=parsed["frontmatter"]["id"],
                    entity_type=parsed["frontmatter"]["entity_type"],
                    alt_text=img["alt_text"],
                    category_folder=folder_for_image,
                )

            self._registry.record(url, 200, str(output_path))
            self._checkpoint.mark_done(
                url,
                category=category_key,
                output_file=str(output_path),
            )
            self._scrape_manifest.record_page(category_key, success=True)
            self._scrape_manifest.add_image_referenced(len(parsed["images"]))
            async with self._page_count_lock:
                self._page_count += 1
        except Exception:
            logger.exception("Failed to scrape %s", url)
            self._scrape_manifest.record_page(category_key, success=False)
