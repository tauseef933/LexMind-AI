"""Lightweight character splitter (no langchain / transformers / torch)."""

from __future__ import annotations


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks, preferring paragraph / sentence / word
    boundaries when possible.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " ", ""]
    return _recursive_split(text, separators, chunk_size, chunk_overlap)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []

    sep = ""
    rest: list[str] = []
    for i, candidate in enumerate(separators):
        if candidate == "" or candidate in text:
            sep = candidate
            rest = separators[i + 1 :]
            break

    pieces = list(text) if sep == "" else text.split(sep)
    merged: list[str] = []
    buf = ""

    for piece in pieces:
        addition = piece if not buf else (buf + sep + piece if sep else buf + piece)
        if len(addition) <= chunk_size:
            buf = addition
            continue

        if buf:
            merged.append(buf)

        if len(piece) > chunk_size:
            if rest:
                merged.extend(_recursive_split(piece, rest, chunk_size, chunk_overlap))
            else:
                start = 0
                while start < len(piece):
                    end = min(start + chunk_size, len(piece))
                    merged.append(piece[start:end])
                    if end == len(piece):
                        break
                    start = max(0, end - chunk_overlap)
            buf = ""
        else:
            # Start a new buffer, carrying overlap from previous chunk.
            if chunk_overlap and merged:
                tail = merged[-1][-chunk_overlap:]
                buf = tail + sep + piece if sep else tail + piece
                if len(buf) > chunk_size:
                    buf = piece
            else:
                buf = piece

    if buf:
        merged.append(buf)

    return [c for c in merged if c.strip()]
