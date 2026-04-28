import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_RAW_DIR = Path("/data/raw/markdown")


class MarkdownWriter:
    def write(self, category: str, slug: str, frontmatter: dict, body: str) -> None:
        out_dir = _RAW_DIR / category
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{slug}.md"

        fm_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        content = f"---\n{fm_str}---\n\n{body}\n"
        path.write_text(content, encoding="utf-8")
        logger.debug("Wrote %s", path)
