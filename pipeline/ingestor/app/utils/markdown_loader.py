from pathlib import Path

from app.utils.frontmatter import extract_frontmatter


def load_markdown_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = extract_frontmatter(text)
    return {
        "frontmatter": fm,
        "body": body,
        "source_file": str(path),
    }


def load_markdown_dir(root: Path) -> list[dict]:
    docs = []
    for path in sorted(root.rglob("*.md")):
        try:
            docs.append(load_markdown_file(path))
        except Exception:
            pass
    return docs
