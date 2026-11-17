"""Voice-design vocabulary (OmniVoice instruct items) and a forgiving parser for free-form descriptions."""

from __future__ import annotations

import re

OPTIONS: dict[str, list[str]] = {
    "gender": ["male", "female"],
    "age": ["child", "teenager", "young adult", "middle-aged", "elderly"],
    "pitch": ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"],
    "accent": ["american accent", "british accent", "australian accent", "canadian accent", "indian accent",
               "chinese accent", "japanese accent", "korean accent", "portuguese accent", "russian accent"],
    "style": ["whisper"],
}
VALID = {item for items in OPTIONS.values() for item in items}

SYNONYMS = {
    "man": "male", "boy": "male", "masculine": "male", "woman": "female", "girl": "female", "feminine": "female",
    "lady": "female", "kid": "child", "children": "child", "teen": "teenager", "young": "young adult",
    "adult": "young adult", "middle aged": "middle-aged", "old": "elderly", "senior": "elderly", "aged": "elderly",
    "deep": "low pitch", "low": "low pitch", "bass": "very low pitch", "very deep": "very low pitch",
    "high": "high pitch", "squeaky": "very high pitch", "medium pitch": "moderate pitch", "normal pitch": "moderate pitch",
    "whispering": "whisper", "whispered": "whisper", "american": "american accent", "british": "british accent",
    "english accent": "british accent", "australian": "australian accent", "canadian": "canadian accent",
    "indian": "indian accent", "south asian accent": "indian accent", "chinese": "chinese accent",
    "japanese": "japanese accent", "korean": "korean accent", "portuguese": "portuguese accent",
    "russian": "russian accent",
}


def normalize(description: str) -> tuple[str, list[str]]:
    """Return (instruct string with valid items only, list of ignored words)."""
    if re.search(r"[一-鿿]", description):  # Chinese instructs are passed through untouched
        return description, []
    picked: dict[str, str] = {}
    ignored: list[str] = []
    for raw in re.split(r"[,;/\n]+|\band\b", description.lower()):
        term = re.sub(r"\s+", " ", raw).strip(" .-")
        if not term:
            continue
        item = term if term in VALID else SYNONYMS.get(term)
        if item is None:  # try each word / pair of words inside the phrase
            words = term.split()
            found = [SYNONYMS.get(" ".join(words[i:i + 2])) or (" ".join(words[i:i + 2]) if " ".join(words[i:i + 2]) in VALID else None)
                     for i in range(len(words))]
            found += [w if w in VALID else SYNONYMS.get(w) for w in words]
            found = [f for f in found if f]
            if not found:
                ignored.append(term)
                continue
            item = found[0]
            for extra in found[1:]:
                _put(picked, extra)
        _put(picked, item)
    order = ["gender", "age", "pitch", "accent", "style"]
    return ", ".join(picked[k] for k in order if k in picked), ignored


def _put(picked: dict[str, str], item: str) -> None:
    for cat, items in OPTIONS.items():
        if item in items and cat not in picked:
            picked[cat] = item
