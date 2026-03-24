"""Text chunking strategies.

Splits source text into chunks for embedding. Supports multiple strategies:
- single: No splitting, embed the full text as one chunk
- paragraph: Split on paragraph boundaries (double newline)
- fixed: Fixed token-count chunks with overlap
- sliding: Sliding window with configurable overlap
"""

import logging
import re

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    strategy: str = "paragraph",
    max_size: int = 512,
    min_size: int = 50,
    overlap: int = 50,
) -> list[str]:
    """Split text into chunks using the specified strategy.

    Args:
        text: Source text to chunk.
        strategy: Chunking strategy name.
        max_size: Maximum chunk size in characters.
        min_size: Minimum chunk size (smaller chunks are merged).
        overlap: Overlap size for sliding/fixed strategies.

    Returns:
        List of chunk strings.
    """
    text = text.strip()
    if not text:
        return []

    if strategy == "single":
        return [text]

    if strategy == "paragraph":
        return _chunk_paragraph(text, max_size, min_size)

    if strategy == "fixed":
        return _chunk_fixed(text, max_size, overlap)

    if strategy == "sliding":
        return _chunk_sliding(text, max_size, overlap)

    logger.warning("Unknown chunking strategy '%s', falling back to paragraph", strategy)
    return _chunk_paragraph(text, max_size, min_size)


def _chunk_paragraph(text: str, max_size: int, min_size: int) -> list[str]:
    """Split on paragraph boundaries, merge small paragraphs."""
    # Split on double newline, then single newline, then sentence
    paragraphs = re.split(r"\n\s*\n", text)

    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= max_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # If paragraph itself exceeds max_size, split by sentences
            if len(para) > max_size:
                sentences = re.split(r"(?<=[.!?。])\s+", para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_size:
                        current = f"{current} {sent}" if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current and len(current) >= min_size:
        chunks.append(current)
    elif current and chunks:
        chunks[-1] = f"{chunks[-1]}\n\n{current}"
    elif current:
        chunks.append(current)

    return chunks if chunks else [text]


def _chunk_fixed(text: str, max_size: int, overlap: int) -> list[str]:
    """Fixed-size chunking with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks if chunks else [text]


def _chunk_sliding(text: str, max_size: int, overlap: int) -> list[str]:
    """Sliding window — same as fixed but ensures word boundaries."""
    words = text.split()
    if not words:
        return [text]

    chunks = []
    current_words: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > max_size and current_words:
            chunks.append(" ".join(current_words))
            # Keep overlap words
            overlap_chars = 0
            overlap_words: list[str] = []
            for w in reversed(current_words):
                overlap_chars += len(w) + 1
                if overlap_chars > overlap:
                    break
                overlap_words.insert(0, w)
            current_words = overlap_words
            current_len = sum(len(w) + 1 for w in current_words)

        current_words.append(word)
        current_len += word_len

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks if chunks else [text]
