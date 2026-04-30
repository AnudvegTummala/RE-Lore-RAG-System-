"""Fandom (Resident Evil Wiki) scraper.

URL discovery uses the MediaWiki API (api.php) rather than HTML category
pages, which avoids Cloudflare challenges on the rendered pages. For each
configured category the scraper:

  1. Calls the categorymembers API recursively (BFS, depth ≤ 5) to collect
     every article pageid in the category tree, then converts pageids to
     full wiki URLs in a single titles lookup.
  2. Fetches each article page as HTML, parses it via the matching category
     parser, and writes a markdown file with YAML frontmatter.
  3. Registers image references with the shared ImageManifest.

Concurrency is bounded by the shared ``Semaphore(5)`` in ``BaseScraper``;
the rate limiter additionally enforces a 1.5-3.0 s per-domain gap. The
checkpoint is consulted to skip already-scraped URLs and is auto-flushed
every 10 successful pages.
"""

import asyncio
import json
import logging
import urllib.parse
from collections import deque

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
_API_URL = f"{_BASE_URL}/api.php"

# Max subcategory recursion depth during BFS URL discovery.
_MAX_SUBCAT_DEPTH = 5

# (category_key) -> (fandom category name, entity_type, output folder)
# Category names verified against the live wiki's Category:Lore_by_type tree.
_CATEGORIES: dict[str, tuple[str, str, str]] = {
    "characters":    ("Characters",       "character",    "characters"),
    "games":         ("Games",            "game",         "games"),
    "enemies":       ("Creatures",        "enemy",        "enemies"),
    "locations":     ("Locations",        "location",     "locations"),
    "organizations": ("Organisations",    "organization", "organizations"),
    "viruses":       ("Biological_agents","virus",        "viruses"),
    "weapons":       ("Equipment",        "weapon",       "weapons"),
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
            for cat_key, (cat_name, entity_type, folder) in categories.items():
                if self._budget_remaining() <= 0:
                    logger.info("Page budget exhausted; stopping at category=%s", cat_key)
                    break
                logger.info("Scraping category: %s", cat_key)
                await self._scrape_category(client, cat_key, cat_name, entity_type, folder)

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
        category_name: str,
        entity_type: str,
        folder: str,
    ) -> None:
        article_urls = await self._collect_article_urls(client, category_name)
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

    # ------------------------------------------------------------------
    # MediaWiki API — URL discovery
    # ------------------------------------------------------------------

    async def _api_get(self, client: httpx.AsyncClient, params: dict) -> dict | None:
        """GET the Fandom MediaWiki API and return parsed JSON, or None on failure."""
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        url = _API_URL + "?" + urllib.parse.urlencode(params)
        text = await self.fetch(client, url)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("JSON decode failed for API call: %s", url)
            return None

    async def _collect_article_urls(
        self,
        client: httpx.AsyncClient,
        category_name: str,
    ) -> list[str]:
        """BFS through the category tree via the MediaWiki API.

        Collects all article pageids (namespace 0) under the given category,
        recursing into subcategories up to _MAX_SUBCAT_DEPTH levels deep.
        Returns full wiki URLs for each article.
        """
        page_ids: set[int] = set()
        visited_cats: set[str] = set()

        # Queue entries: (category_name, depth)
        queue: deque[tuple[str, int]] = deque()
        queue.append((f"Category:{category_name}", 0))
        visited_cats.add(f"Category:{category_name}")

        while queue:
            cat_title, depth = queue.popleft()
            cm_continue: str | None = None

            while True:
                params: dict = {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": cat_title,
                    "cmlimit": "500",
                    "cmtype": "page|subcat",
                    "cmnamespace": "0|14",
                }
                if cm_continue:
                    params["cmcontinue"] = cm_continue

                data = await self._api_get(client, params)
                if not data:
                    break

                members = data.get("query", {}).get("categorymembers", [])
                for member in members:
                    ns = member.get("ns", -1)
                    title = member.get("title", "")
                    pageid = member.get("pageid")

                    if ns == 0 and pageid:
                        page_ids.add(pageid)
                    elif ns == 14 and depth < _MAX_SUBCAT_DEPTH:
                        if title not in visited_cats:
                            visited_cats.add(title)
                            queue.append((title, depth + 1))

                cont = data.get("continue", {})
                cm_continue = cont.get("cmcontinue")
                if not cm_continue:
                    break

        if not page_ids:
            logger.warning("No articles found under Category:%s", category_name)
            return []

        # Convert pageids to URLs in batches of 50 (API limit for prop=info).
        urls: list[str] = []
        id_list = list(page_ids)
        for i in range(0, len(id_list), 50):
            batch = id_list[i : i + 50]
            batch_urls = await self._pageids_to_urls(client, batch)
            urls.extend(batch_urls)

        logger.debug(
            "Category:%s — visited %d subcategories, resolved %d article URLs",
            category_name, len(visited_cats), len(urls),
        )
        return urls

    async def _pageids_to_urls(
        self,
        client: httpx.AsyncClient,
        page_ids: list[int],
    ) -> list[str]:
        """Resolve a batch of pageids to full wiki URLs via prop=info."""
        params = {
            "action": "query",
            "prop": "info",
            "pageids": "|".join(str(pid) for pid in page_ids),
            "inprop": "url",
        }
        data = await self._api_get(client, params)
        if not data:
            return []

        urls: list[str] = []
        pages = data.get("query", {}).get("pages", [])
        # formatversion=2 returns pages as a list; formatversion=1 returns a dict
        if isinstance(pages, dict):
            pages = pages.values()
        for page in pages:
            full_url = page.get("fullurl")
            if full_url:
                urls.append(full_url)
        return urls

    # ------------------------------------------------------------------
    # Article fetching and parsing
    # ------------------------------------------------------------------

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
