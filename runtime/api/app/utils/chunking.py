import re


def chunk_by_heading(text: str, max_chars: int = 800) -> list[str]:
    sections = re.split(r"\n#{1,3} ", text)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
        else:
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 2 > max_chars and current:
                    chunks.append(current.strip())
                    current = para
                else:
                    current = f"{current}\n\n{para}" if current else para
            if current.strip():
                chunks.append(current.strip())
    return chunks
