"""Topic-aware chunks with source page spans and no extra GPT calls.

GPT labels semantic sections while transcribing each PDF page. This module
combines adjacent sections with the same topic across page boundaries, splitting
oversized sections at paragraph boundaries only as a size safety limit.
"""
import re
import unicodedata

from components.chunking import chunk_page, normalize_extraction

MAX_SEMANTIC_CHARS = 2400


def topic_key(topic: str) -> str:
    value = unicodedata.normalize("NFKC", topic).casefold()
    return re.sub(r"[^\w\u0e00-\u0e7f]+", "", value)


def unique_keywords(values: list[str]) -> list[str]:
    seen: set[str] = set()
    terms = []
    for value in values:
        term = " ".join(str(value).split())[:80]
        key = term.casefold()
        if len(term) >= 2 and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms[:12]


def build_semantic_chunks(pages: list[tuple], max_chars: int = MAX_SEMANTIC_CHARS) -> list[dict]:
    """Return text, topic, page_no (first), page_end (last), keywords in reading order.

    A legacy four-field page has no semantic labels and is never merged across
    pages. Blank pages produce no chunks. No text is supplied from other files.
    """
    if max_chars < 100:
        raise ValueError("INVALID_SEMANTIC_CHUNK_SIZE")
    result: list[dict] = []
    for page in pages:
        page_no, page_text, page_keywords, _note = page[:4]
        sections = page[4] if len(page) >= 5 else []
        if not sections:
            sections = [{"topic": "", "text": page_text, "keywords": page_keywords}]
        for section in sections:
            text = normalize_extraction(section.get("text", ""))
            if not text:
                continue
            topic = " ".join(str(section.get("topic", "")).split())[:255]
            keywords = unique_keywords(section.get("keywords") or page_keywords or [])
            # Semantic boundaries are primary; size splitting is a safety limit.
            for part in chunk_page(text, max_chars=max_chars, overlap=0):
                previous = result[-1] if result else None
                same_topic = bool(topic_key(topic)) and previous is not None and (
                    topic_key(previous["topic"]) == topic_key(topic))
                contiguous = bool(previous is not None and
                    (page_no == previous["page_end"] or
                     (page_no is not None and previous["page_end"] is not None and
                      page_no == previous["page_end"] + 1)))
                if (same_topic and contiguous and len(previous["text"]) + len(part) + 2 <= max_chars):
                    previous["text"] += "\n\n" + part
                    previous["page_end"] = page_no
                    previous["keywords"] = unique_keywords(previous["keywords"] + keywords)
                else:
                    result.append({
                        "page_no": page_no, "page_end": page_no,
                        "topic": topic, "text": part, "keywords": keywords,
                    })
    return result
