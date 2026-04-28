import re


def extract_frontmatter(text: str) -> tuple[dict, str]:
    import yaml
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return meta, body
