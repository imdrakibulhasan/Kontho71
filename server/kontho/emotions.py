"""Emotion tags: ``[angry] text [calm] more text``.

The TTS engine copies emotion from its reference clip, so each voice can hold one reference clip
per emotion. While synthesizing, every emotion tag switches the reference for the text that
follows it. Tags are parsed generously, so ElevenLabs-style prompts work unchanged:
``[warm, smooth, gentle storytelling tone, tense]`` -> ``tense``.
"""

from __future__ import annotations

import re

# canonical emotion -> (label, Bengali label)
EMOTIONS: dict[str, tuple[str, str]] = {
    "neutral": ("Neutral", "স্বাভাবিক"),
    "calm": ("Calm", "শান্ত"),
    "warm": ("Warm", "উষ্ণ"),
    "happy": ("Happy", "খুশি"),
    "excited": ("Excited", "উত্তেজিত"),
    "sad": ("Sad", "দুঃখ"),
    "crying": ("Crying", "কান্না"),
    "worried": ("Worried", "চিন্তিত"),
    "tense": ("Tense", "টানটান"),
    "scared": ("Scared", "ভয়"),
    "angry": ("Angry", "রাগ"),
    "shouting": ("Shouting", "চিৎকার"),
    "surprised": ("Surprised", "অবাক"),
    "mysterious": ("Mysterious", "রহস্য"),
    "pleading": ("Pleading", "অনুনয়"),
    "laughing": ("Laughing", "হাসি"),
    "whisper": ("Whisper", "ফিসফিস"),
}

ALIASES: dict[str, str] = {
    # neutral / storytelling
    "normal": "neutral", "default": "neutral", "narration": "neutral", "storytelling": "neutral",
    "quiet": "calm", "soft": "calm", "relaxed": "calm", "peaceful": "calm", "serene": "calm",
    "gentle": "warm", "tender": "warm", "kind": "warm", "loving": "warm", "affectionate": "warm", "smiling": "warm",
    "humble": "warm",
    "joyful": "happy", "joy": "happy", "cheerful": "happy", "hopeful": "happy", "glad": "happy", "relieved": "happy",
    "proud": "happy",
    "thrilled": "excited", "energetic": "excited", "enthusiastic": "excited", "hyped": "excited",
    "somber": "sad", "sorrowful": "sad", "melancholic": "sad", "grief": "sad", "remorseful": "sad", "regretful": "sad",
    "heartbroken": "sad", "disappointed": "sad",
    "cry": "crying", "sobbing": "crying", "tearful": "crying", "weeping": "crying",
    "concerned": "worried", "anxious": "worried", "nervous": "worried", "uneasy": "worried",
    "urgent": "tense", "serious": "tense", "suspense": "tense", "dramatic": "tense", "intense": "tense",
    "afraid": "scared", "fear": "scared", "fearful": "scared", "terrified": "scared", "panicked": "scared",
    "panic": "scared", "desperate": "scared", "frightened": "scared",
    "annoyed": "angry", "irritated": "angry", "furious": "angry", "mad": "angry", "frustrated": "angry", "sharp": "angry",
    "stern": "angry",
    "shout": "shouting", "yelling": "shouting", "yell": "shouting", "screaming": "shouting", "scream": "shouting",
    "surprise": "surprised", "amazed": "surprised", "shocked": "surprised", "stunned": "surprised",
    "astonished": "surprised", "doubtful": "surprised", "confused": "surprised",
    "mystery": "mysterious", "eerie": "mysterious", "ominous": "mysterious",
    "begging": "pleading", "pleading": "pleading", "imploring": "pleading",
    "laugh": "laughing", "amused": "laughing", "giggling": "laughing",
    "whispering": "whisper", "whispers": "whisper", "whispered": "whisper",
}

# when a voice has no clip for an emotion, try these (then the voice's normal reference)
FALLBACKS: dict[str, list[str]] = {
    "calm": ["warm", "neutral"], "warm": ["calm", "happy"], "happy": ["warm", "excited"],
    "excited": ["happy", "surprised"], "sad": ["crying", "worried", "calm"], "crying": ["sad", "pleading"],
    "worried": ["tense", "sad", "scared"], "tense": ["worried", "scared", "mysterious"],
    "scared": ["worried", "tense", "crying"], "angry": ["shouting", "tense"], "shouting": ["angry", "scared"],
    "surprised": ["excited", "scared"], "mysterious": ["tense", "calm", "whisper"],
    "pleading": ["crying", "sad"], "laughing": ["happy", "excited"], "whisper": ["mysterious", "calm"],
}

# non-verbal tags the TTS engine renders itself: keep them in the text
NONVERBAL = {"laughter", "sigh", "surprise-ah", "surprise-oh", "surprise-wa", "question-ah",
             "dissatisfaction-hnn", "breath", "cough"}

_TAG = re.compile(r"\[([^\[\]]{1,120})\]")
RESET = "neutral"


def canonical(word: str) -> str | None:
    w = re.sub(r"[^a-z\- ]", "", word.lower()).strip()
    if not w:
        return None
    if w in EMOTIONS:
        return w
    if w in ALIASES:
        return ALIASES[w]
    for token in reversed(w.replace("-", " ").split()):  # "out of breath" / "very angry"
        if token in EMOTIONS:
            return token
        if token in ALIASES:
            return ALIASES[token]
    return None


def tag_emotion(tag: str) -> str | None:
    """Emotion named by a tag; with several words the last recognised one wins."""
    found = [e for e in (canonical(p) for p in re.split(r"[,;/|]", tag)) if e]
    if not found:
        return None
    specific = [e for e in found if e != "neutral"]
    return (specific or found)[-1]


def parse(text: str, default: str | None = None) -> list[tuple[str | None, str]]:
    """Split text into (emotion, text) runs. Emotion tags are removed, ``[pause]`` becomes a pause,
    non-verbal tags are kept and unknown descriptive tags (e.g. ``[rural accent]``) are dropped."""
    runs: list[tuple[str | None, str]] = []
    current = default
    buf: list[str] = []
    pos = 0

    def flush() -> None:
        chunk = re.sub(r"\s+", " ", "".join(buf)).strip()
        if chunk:
            runs.append((current, chunk))
        buf.clear()

    for m in _TAG.finditer(text):
        buf.append(text[pos:m.start()])
        pos = m.end()
        raw = m.group(1).strip()
        low = raw.lower()
        if low in NONVERBAL:
            buf.append(f"[{low}]")
            continue
        if low in ("pause", "short pause", "long pause", "beat"):
            buf.append(" … ")
            continue
        emo = tag_emotion(raw)
        if emo is not None:
            flush()
            current = None if emo == RESET else emo
        # unknown descriptive tags are dropped silently
    buf.append(text[pos:])
    flush()
    merged: list[tuple[str | None, str]] = []
    for emo, chunk in runs:  # merge neighbours with the same emotion
        if merged and merged[-1][0] == emo:
            merged[-1] = (emo, merged[-1][1] + " " + chunk)
        else:
            merged.append((emo, chunk))
    return merged


def resolve(requested: str, available: set[str]) -> str | None:
    """Best available clip for ``requested`` (exact, then fallbacks), or None for the base voice."""
    if requested in available:
        return requested
    for alt in FALLBACKS.get(requested, []):
        if alt in available:
            return alt
    return None


def catalog() -> list[dict]:
    return [{"emotion": k, "name": v[0], "name_bn": v[1],
             "aliases": sorted(a for a, t in ALIASES.items() if t == k)} for k, v in EMOTIONS.items()]
