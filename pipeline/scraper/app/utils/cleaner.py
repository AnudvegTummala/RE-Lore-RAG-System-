import re

# URL fragments that identify Fandom/wikia chrome rather than content imagery.
_UI_IMAGE_PATTERNS = (
    "site-logo",
    "favicon",
    "wiki-background",
    "wiki-wordmark",
    "/skin-images/",
    "community-header",
    "fandom-header",
    "site-navigation",
    "footer-logo",
    "/static/images/",
    "powered-by",
)


def clean_wiki_text(raw: str) -> str:
    """Remove footnote refs and collapse whitespace from wiki HTML text."""
    text = re.sub(r"\[\d+\]", "", raw)
    text = re.sub(r"\[edit\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slug(title: str) -> str:
    """Lowercase, hyphen-separated slug suitable for filenames and ids."""
    title = title.lower().strip()
    # Replace common punctuation that should become a hyphen separator
    title = re.sub(r"[–—/]", "-", title)  # en/em-dash, slash
    # Strip apostrophes and other punctuation entirely
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_]+", "-", title)
    title = re.sub(r"-+", "-", title)
    return title.strip("-")


def is_ui_image(url: str) -> bool:
    """Return True if the URL looks like wikia chrome rather than article content."""
    if not url:
        return True
    lowered = url.lower()
    if lowered.startswith("data:"):
        return True
    return any(pat in lowered for pat in _UI_IMAGE_PATTERNS)


def normalize_image_url(url: str) -> str:
    """Strip Fandom thumbnail size suffixes to get the canonical image URL.

    Fandom serves images like
    ``.../image.png/revision/latest/scale-to-width-down/300?cb=...``.
    The full-resolution image is at ``.../image.png/revision/latest`` (or
    just at the base path for non-versioned hosts).
    """
    if not url:
        return url
    # Drop the cache-buster query string
    url = re.sub(r"\?cb=[^&]*", "", url)
    url = re.sub(r"\?.*$", "", url)
    # Drop scale-to-width-down/N or thumb suffixes
    url = re.sub(r"/scale-to-width-down/\d+/?$", "", url)
    url = re.sub(r"/scale-to-width/\d+/?$", "", url)
    url = re.sub(r"/thumb/\d+/?$", "", url)
    return url
