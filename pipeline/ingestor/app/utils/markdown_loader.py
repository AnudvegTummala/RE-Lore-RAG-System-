from pathlib import Path
import frontmatter as fm


def load_markdown_files(path: Path) -> dict:
    post = fm.load(str(path))
    return {
        "frontmatter": dict(post.metadata),
        "body": post.content,
        "source_file": str(path),
    }
