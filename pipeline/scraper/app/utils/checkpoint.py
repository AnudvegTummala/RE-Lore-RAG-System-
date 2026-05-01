import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path("/data/checkpoints")
_DEFAULT_SAVE_EVERY = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Checkpoint:
    """Resumable checkpoint store.

    Tracks completed keys (typically URLs) on disk so a scraper can resume
    after interruption. State is auto-flushed to disk every ``save_every``
    new completions. Per-category counts are maintained for manifest output.

    State schema:
        {
          "completed": { "<key>": { "category": str, "output_file": str,
                                    "completed_at": iso8601 } },
          "counts":    { "<category>": int },
          "started_at":   iso8601,
          "last_updated": iso8601
        }
    """

    def __init__(self, name: str, save_every: int = _DEFAULT_SAVE_EVERY):
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _CHECKPOINT_DIR / f"{name}.json"
        self._save_every = save_every
        self._lock = threading.Lock()
        self._pending = 0
        self._state = self._load()

    def _empty_state(self) -> dict:
        return {
            "completed": {},
            "counts": {},
            "started_at": _now(),
            "last_updated": None,
        }

    def _load(self) -> dict:
        if not self._path.exists():
            return self._empty_state()
        try:
            data = json.loads(self._path.read_text())
        except Exception:
            logger.exception("Could not read checkpoint %s; starting fresh", self._path)
            return self._empty_state()

        if not isinstance(data, dict) or "completed" not in data:
            # Migrate legacy {"<key>": true} format
            completed = {
                k: {"category": None, "output_file": None, "completed_at": None}
                for k, v in (data or {}).items()
                if v
            }
            return {
                "completed": completed,
                "counts": {},
                "started_at": _now(),
                "last_updated": None,
            }
        return data

    def is_done(self, key: str) -> bool:
        return key in self._state["completed"]

    def mark_done(
        self,
        key: str,
        *,
        category: str | None = None,
        output_file: str | None = None,
    ) -> None:
        with self._lock:
            if key in self._state["completed"]:
                return
            self._state["completed"][key] = {
                "category": category,
                "output_file": output_file,
                "completed_at": _now(),
            }
            if category:
                self._state["counts"][category] = (
                    self._state["counts"].get(category, 0) + 1
                )
            self._pending += 1
            if self._pending >= self._save_every:
                self._flush_locked()

    def save(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        self._state["last_updated"] = _now()
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._state, indent=2))
        tmp.replace(self._path)
        self._pending = 0

    def completed_keys(self) -> set[str]:
        return set(self._state["completed"].keys())

    @property
    def total(self) -> int:
        return len(self._state["completed"])

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._state["counts"])

    @property
    def started_at(self) -> str:
        return self._state["started_at"]
