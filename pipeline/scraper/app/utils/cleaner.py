import re


def clean_wiki_text(raw: str) -> str:
    text = re.sub(r"\[\d+\]", "", raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slug(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_]+", "-", title)
    return title.strip("-")
