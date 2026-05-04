"""Manifest writers for the scrape run.

Three artefacts are produced under ``data/raw/manifests/``:

* ``scrape_manifest.json`` — high-level run metadata (counts per category,
  start/finish timestamps).
* ``image_manifest.json`` — per-image record: source URL, local path, entity
  associations, alt text, dimensions.
* ``source_registry.json`` — every URL visited with status code and output
  file.

Each writer is independently loadable so the image downloader (which runs
after the fandom scraper) can pick up image references collected earlier.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_DIR = Path("/data/raw/manifests")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


class SourceRegistry:
    """Append-only log of every URL visited during a scrape run."""

    def __init__(self, path: Path = MANIFEST_DIR / "source_registry.json"):
        self._path = path
        self._lock = threading.Lock()
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, list) else []
        except Exception:
            logger.exception("Could not read %s; starting fresh", self._path)
            return []

    def record(
        self,
        url: str,
        status_code: int | None,
        output_file: str | None = None,
    ) -> None:
        with self._lock:
            self._entries.append({
                "url": url,
                "status_code": status_code,
                "output_file": output_file,
                "scraped_at": _now(),
            })

    def save(self) -> None:
        with self._lock:
            _atomic_write(self._path, self._entries)


class ImageManifest:
    """Persistent map of image_id -> metadata.

    Populated incrementally: page parsers add entries with source_url and
    entity associations; the downloader fills in ``local_path``, ``width``,
    ``height`` after successful download.
    """

    def __init__(self, path: Path = MANIFEST_DIR / "image_manifest.json"):
        self._path = path
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.exception("Could not read %s; starting fresh", self._path)
            return {}

    def add_reference(
        self,
        image_id: str,
        source_url: str,
        entity_id: str,
        entity_type: str,
        alt_text: str = "",
        caption: str = "",
        section: str = "",
        tags: list[str] | None = None,
        category_folder: str | None = None,
    ) -> None:
        """Record an image reference without overwriting download results."""
        with self._lock:
            entry = self._entries.setdefault(image_id, {})
            # Don't clobber download outcomes if we already have them.
            entry.setdefault("local_path", None)
            entry.setdefault("width", None)
            entry.setdefault("height", None)
            entry["source_url"] = source_url
            entry["entity_id"] = entity_id
            entry["entity_type"] = entity_type
            entry["alt_text"] = alt_text
            entry["caption"] = caption
            entry["section"] = section
            entry["tags"] = tags or []
            if category_folder:
                entry["category_folder"] = category_folder
            entry.setdefault("first_seen_at", _now())

    def mark_downloaded(
        self,
        image_id: str,
        local_path: str,
        width: int,
        height: int,
    ) -> None:
        with self._lock:
            entry = self._entries.setdefault(image_id, {})
            entry["local_path"] = local_path
            entry["width"] = width
            entry["height"] = height
            entry["downloaded_at"] = _now()

    def mark_skipped(self, image_id: str, reason: str) -> None:
        with self._lock:
            entry = self._entries.setdefault(image_id, {})
            entry["skipped"] = True
            entry["skip_reason"] = reason

    def items(self) -> list[tuple[str, dict]]:
        with self._lock:
            return list(self._entries.items())

    def __len__(self) -> int:
        return len(self._entries)

    def save(self) -> None:
        with self._lock:
            _atomic_write(self._path, self._entries)


class ScrapeManifest:
    """Top-level run metadata: timestamps and per-category counts."""

    def __init__(self, path: Path = MANIFEST_DIR / "scrape_manifest.json"):
        self._path = path
        self._lock = threading.Lock()
        self._data = {
            "started_at": _now(),
            "completed_at": None,
            "categories": {},
            "totals": {
                "pages_scraped": 0,
                "pages_failed": 0,
                "images_referenced": 0,
                "images_downloaded": 0,
                "images_skipped": 0,
            },
            "user_agent": "Mozilla/5.0 (compatible; RE-Lore-Oracle-Research-Bot/1.0)",
        }

    def record_page(self, category: str, success: bool) -> None:
        with self._lock:
            cat = self._data["categories"].setdefault(
                category, {"pages_scraped": 0, "pages_failed": 0}
            )
            if success:
                cat["pages_scraped"] += 1
                self._data["totals"]["pages_scraped"] += 1
            else:
                cat["pages_failed"] += 1
                self._data["totals"]["pages_failed"] += 1

    def add_image_referenced(self, n: int = 1) -> None:
        with self._lock:
            self._data["totals"]["images_referenced"] += n

    def add_image_downloaded(self, n: int = 1) -> None:
        with self._lock:
            self._data["totals"]["images_downloaded"] += n

    def add_image_skipped(self, n: int = 1) -> None:
        with self._lock:
            self._data["totals"]["images_skipped"] += n

    def save(self) -> None:
        with self._lock:
            self._data["completed_at"] = _now()
            _atomic_write(self._path, self._data)
