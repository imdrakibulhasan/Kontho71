"""Text utilities: sentence splitting (Latin, Bengali, Devanagari, CJK...) and chunking."""

from __future__ import annotations

import re

# Sentence enders: . ! ? plus Bengali/Hindi danda (। ॥), CJK (。！？), Arabic (؟ ۔)
_SENT_END = re.compile(r"(?<=[.!?।॥。！？؟۔…])\s+|(?<=[。！？])|\n{2,}")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_END.split(text.strip()) if p and p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def chunk_text(text: str, max_chars: int = 280) -> list[str]:
    """Group sentences into chunks of at most ``max_chars`` (long sentences are split on commas/spaces)."""
    chunks: list[str] = []
    buf = ""
    for sent in split_sentences(text):
        pieces = [sent]
        if len(sent) > max_chars:
            pieces = _hard_split(sent, max_chars)
        for piece in pieces:
            if buf and len(buf) + 1 + len(piece) > max_chars:
                chunks.append(buf)
                buf = piece
            else:
                buf = f"{buf} {piece}".strip()
    if buf:
        chunks.append(buf)
    return chunks


def _hard_split(sentence: str, max_chars: int) -> list[str]:
    out: list[str] = []
    buf = ""
    for tok in re.split(r"(?<=[,;:،])\s+|\s+", sentence):
        if buf and len(buf) + 1 + len(tok) > max_chars:
            out.append(buf)
            buf = tok
        else:
            buf = f"{buf} {tok}".strip()
    if buf:
        out.append(buf)
    return out


def apply_pronunciations(text: str, rules: list[dict]) -> str:
    """Apply pronunciation-dictionary replacements (whole-word, case-sensitive)."""
    for r in rules:
        term = r.get("term") or ""
        if term:
            text = re.sub(rf"(?<!\w){re.escape(term)}(?!\w)", r.get("replacement", ""), text)
    return text
