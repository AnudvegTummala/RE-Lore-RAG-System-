"""Supplements game markdown files with a Wikipedia summary section.

Reads existing files under ``data/raw/markdown/games/``. For each, queries
Wikipedia's REST summary endpoint (``/api/rest_v1/page/summary/{title}``)
and appends the returned ``extract`` under a ``## Wikipedia Summary``
heading. Idempotent: if the marker heading is already present, the file is
left unchanged.
"""

import asyncio
import json
import logging
import re
import urllib.parse
from pathlib import Path

import httpx
import yaml

from app.scrapers.base import BaseScraper
from app.utils.manifests import ScrapeManifest, SourceRegistry

logger = logging.getLogger(__name__)

_MARKDOWN_GAMES_DIR = Path("/data/raw/markdown/games")
_API_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"
_MARKER = "## Wikipedia Summary"


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

        async with self.build_client() as client:
            tasks = [self._supplement(client, p) for p in files]
            await asyncio.gather(*tasks, return_exceptions=False)

        logger.info("WikipediaScraper: supplemented %d game files", len(files))

    async def _supplement(self, client: httpx.AsyncClient, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
            if _MARKER in content:
                return

            fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
            if not fm_match:
                logger.warning("No frontmatter detected in %s", path)
                return
            fm = yaml.safe_load(fm_match.group(1)) or {}
            title = fm.get("title")
            if not title:
                return

            extract = await self._fetch_extract(client, title)
            if not extract:
                # Try a disambiguated title
                extract = await self._fetch_extract(client, f"{title} (video game)")
            if not extract:
                return

            new_content = content.rstrip() + f"\n\n{_MARKER}\n\n{extract}\n"
            path.write_text(new_content, encoding="utf-8")
            logger.debug("Supplemented %s with %d chars", path.name, len(extract))
        except Exception:
            logger.exception("Wikipedia supplement failed for %s", path)

    async def _fetch_extract(self, client: httpx.AsyncClient, title: str) -> str | None:
        normalized = title.replace(" ", "_")
        encoded = urllib.parse.quote(normalized, safe="")
        url = f"{_API_BASE}/{encoded}"

        text = await self.fetch(client, url)
        self._registry.record(url, 200 if text else None)
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if data.get("type") == "disambiguation":
            return None
        extract = (data.get("extract") or "").strip()
        return extract or None
