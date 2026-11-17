"""Engine interfaces. Every AI capability is a swappable engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class VoiceSpec:
    """How to make a voice: clone from a reference clip and/or describe it (voice design)."""

    ref_audio: str | None = None
    ref_text: str | None = None
    instruct: str | None = None  # e.g. "female, young adult, warm"
    seed: int | None = None


@dataclass
class SynthesisOptions:
    language: str | None = None
    speed: float = 1.0
    duration: float | None = None  # force an exact length in seconds (used by dubbing / voice changer)
    seed: int | None = None
    guidance: float | None = None  # how closely to follow the reference / prompt
    steps: int | None = None  # diffusion / flow-matching steps (quality vs speed)


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str = "speaker_0"
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    language: str
    text: str
    segments: list[Segment]
    duration: float = 0.0


class TTSEngine(ABC):
    name = "base"
    supports_cloning = False
    supports_design = False
    supports_duration = False

    @abstractmethod
    def synthesize(self, text: str, voice: VoiceSpec, opts: SynthesisOptions) -> tuple[np.ndarray, int]:
        """Return (mono float32 audio, sample rate)."""


class STTEngine(ABC):
    name = "base"

    @abstractmethod
    def transcribe(self, path: str | Path, language: str | None = None, diarize: bool = False,
                   num_speakers: int | None = None) -> Transcript: ...


class SFXEngine(ABC):
    name = "base"

    @abstractmethod
    def generate(self, prompt: str, duration: float, prompt_influence: float = 0.3,
                 seed: int | None = None) -> tuple[np.ndarray, int]: ...


class IsolationEngine(ABC):
    name = "base"

    @abstractmethod
    def separate(self, path: str | Path) -> tuple[np.ndarray, np.ndarray, int]:
        """Return (vocals, background, sample rate), both mono float32."""


class TranslateEngine(ABC):
    name = "base"

    @abstractmethod
    def translate(self, texts: list[str], source: str, target: str) -> list[str]: ...
