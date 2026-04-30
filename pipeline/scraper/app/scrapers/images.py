"""Image downloader.

Reads pending entries from the shared :class:`ImageManifest` (those without
a ``local_path``), fetches the bytes via the rate-limited base scraper,
validates dimensions with Pillow, and saves to
``data/raw/images/{category_folder}/{image_id}.{ext}``.

Filters applied:
  * URL-based UI filter (``cleaner.is_ui_image``) — runs before download.
  * Dimension filter — drops anything smaller than 100x100 after decoding.
"""

import asyncio
import io
import logging
import re
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from app.scrapers.base import BaseScraper
from app.utils.checkpoint import Checkpoint
from app.utils.cleaner import is_ui_image
from app.utils.manifests import ImageManifest, ScrapeManifest, SourceRegistry

logger = logging.getLogger(__name__)

_IMAGE_ROOT = Path("/data/raw/images")
_MIN_DIMENSION = 100
_VALID_EXT = {"jpg", "jpeg", "png", "webp", "gif"}


def _guess_extension(url: str, content_type: str | None) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct.endswith("/jpeg") or ct.endswith("/jpg"):
            return "jpg"
        if ct.endswith("/png"):
            return "png"
        if ct.endswith("/webp"):
            return "webp"
        if ct.endswith("/gif"):
            return "gif"
    match = re.search(r"\.(jpe?g|png|webp|gif)(?:[?/]|$)", url.lower())
    if match:
        ext = match.group(1)
        return "jpg" if ext == "jpeg" else ext
    return "jpg"


class ImageDownloader(BaseScraper):
    def __init__(
        self,
        image_manifest: ImageManifest,
        source_registry: SourceRegistry,
        scrape_manifest: ScrapeManifest,
        *,
        max_pages: int = 5000,
    ):
        super().__init__(max_pages=max_pages)
        self._manifest = image_manifest
        self._registry = source_registry
        self._scrape_manifest = scrape_manifest
        self._checkpoint = Checkpoint("image_state")

    async def run(self, **_: object) -> None:
        items = self._manifest.items()
        if not items:
            logger.info("ImageDownloader: no images in manifest")
            return

        pending = [
            (image_id, meta)
            for image_id, meta in items
            if not meta.get("local_path") and not self._checkpoint.is_done(image_id)
        ]
        logger.info(
            "ImageDownloader: %d total, %d pending (rest already downloaded or checkpointed)",
            len(items),
            len(pending),
        )
        if not pending:
            self._checkpoint.save()
            self._manifest.save()
            return

        async with self.build_client() as client:
            tasks = [self._download(client, image_id, meta) for image_id, meta in pending]
            await asyncio.gather(*tasks, return_exceptions=False)

        self._checkpoint.save()
        self._manifest.save()
        logger.info(
            "ImageDownloader done. Counts: %s",
            self._checkpoint.counts,
        )

    async def _download(
        self,
        client: httpx.AsyncClient,
        image_id: str,
        meta: dict,
    ) -> None:
        url = meta.get("source_url")
        if not url:
            return

        if is_ui_image(url):
            self._manifest.mark_skipped(image_id, "ui_image_url")
            self._scrape_manifest.add_image_skipped()
            self._checkpoint.mark_done(image_id, category="skipped")
            return

        folder_name = meta.get("category_folder") or meta.get("entity_type") or "misc"
        out_dir = _IMAGE_ROOT / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            data = await self.fetch(client, url, binary=True)
        except Exception:
            logger.exception("Image fetch raised for %s", url)
            self._registry.record(url, None)
            self._scrape_manifest.add_image_skipped()
            self._manifest.mark_skipped(image_id, "fetch_error")
            return

        if not data:
            self._registry.record(url, None)
            self._scrape_manifest.add_image_skipped()
            self._manifest.mark_skipped(image_id, "fetch_failed")
            return

        try:
            with Image.open(io.BytesIO(data)) as img:
                width, height = img.size
                pil_format = (img.format or "").lower()
        except (UnidentifiedImageError, OSError):
            logger.warning("Unidentified image: %s", url)
            self._registry.record(url, 200)
            self._scrape_manifest.add_image_skipped()
            self._manifest.mark_skipped(image_id, "unidentified_image")
            return

        if width < _MIN_DIMENSION or height < _MIN_DIMENSION:
            self._registry.record(url, 200)
            self._scrape_manifest.add_image_skipped()
            self._manifest.mark_skipped(
                image_id,
                f"too_small_{width}x{height}",
            )
            return

        ext = pil_format if pil_format in _VALID_EXT else _guess_extension(url, None)
        if ext == "jpeg":
            ext = "jpg"
        local_path = out_dir / f"{image_id}.{ext}"
        local_path.write_bytes(data)

        self._manifest.mark_downloaded(
            image_id,
            local_path=str(local_path),
            width=width,
            height=height,
        )
        self._registry.record(url, 200, str(local_path))
        self._scrape_manifest.add_image_downloaded()
        self._checkpoint.mark_done(image_id, category=folder_name, output_file=str(local_path))
