"""Text-preserving, page-aware chunking for Thai and mixed math materials.

Use source text (not vector IDs) as the authoritative citation content.
Avoid slicing in the middle of a heading/paragraph when a boundary exists.
"""
import re
import unicodedata


def normalize_extraction(text: str) -> str:
    # NFC preserves Thai combining characters, numbers and mathematical symbols.
    value = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    value = value.replace("\u200b", "").replace("\u00ad", "")
    return "\n".join(line.rstrip() for line in value.split("\n")).strip()


def chunk_page(text: str, max_chars: int = 2200, overlap: int = 180) -> list[str]:
    if not (max_chars > overlap >= 0):
        raise ValueError("INVALID_CHUNK_SETTINGS")
    source = normalize_extraction(text)
    if not source:
        return []
    chunks = []
    start = 0
    while start < len(source):
        end = min(start + max_chars, len(source))
        if end < len(source):
            # Prefer paragraph/line/sentence endings near the target size.
            low = start + max(max_chars // 2, 1)
            section = source[low:end]
            boundaries = list(re.finditer(r"\n\s*\n|\n|[.!?。]\s+|\s+", section))
            if boundaries:
                chosen = low + boundaries[-1].end()
                if chosen > start:
                    end = chosen
        piece = source[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(source):
            break
        # Keep a small context overlap, without duplicating entire short chunks.
        next_start = max(start + 1, end - overlap)
        # Resume at the next word boundary when possible; do not drop text
        # beyond the overlap boundary by skipping meaningful characters.
        start = next_start
    return chunks
