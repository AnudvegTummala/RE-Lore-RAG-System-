import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path("/data/checkpoints")


class Checkpoint:
    def __init__(self, name: str):
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _CHECKPOINT_DIR / f"{name}.json"
        self._state: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                return {}
        return {}

    def is_done(self, key: str) -> bool:
        return self._state.get(key, False)

    def mark_done(self, key: str) -> None:
        self._state[key] = True
        self._path.write_text(json.dumps(self._state, indent=2))
