"""Lightweight engines with no model downloads. Used for tests, CI and UI development.

They produce placeholder audio (tones / noise) - not real speech.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from .. import audio as A
from .base import (IsolationEngine, Segment, SFXEngine, STTEngine, SynthesisOptions, Transcript,
                   TranslateEngine, TTSEngine, VoiceSpec, Word)

SR = 24000


def _seed_from(*parts: object) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


class MockTTS(TTSEngine):
    name = "mock"
    supports_cloning = True
    supports_design = True
    supports_duration = True

    def synthesize(self, text: str, voice: VoiceSpec, opts: SynthesisOptions) -> tuple[np.ndarray, int]:
        dur = opts.duration or max(0.4, len(text) * 0.06 / max(opts.speed, 0.25))
        t = np.arange(int(dur * SR), dtype=np.float32) / SR
        base = 110 + (_seed_from(voice.ref_audio, voice.instruct) % 160)
        # a syllable-like amplitude envelope so it "sounds" like speech rhythm
        env = 0.5 * (1 - np.cos(2 * np.pi * 4 * t)) * 0.3
        wave = np.sin(2 * np.pi * base * t) + 0.3 * np.sin(2 * np.pi * base * 2 * t)
        return (wave * env).astype(np.float32), SR


class MockSTT(STTEngine):
    name = "mock"

    def transcribe(self, path, language=None, diarize=False, num_speakers=None) -> Transcript:
        dur = A.probe_duration(path) or 1.0
        n = max(1, min(4, int(dur // 2)))
        step = dur / n
        segs = []
        for i in range(n):
            text = f"Mock sentence number {i + 1}."
            start, end = i * step, (i + 1) * step
            words = [Word(w, start + j * (end - start) / 4, start + (j + 1) * (end - start) / 4)
                     for j, w in enumerate(text.split())]
            spk = f"speaker_{i % (num_speakers or 1)}" if diarize else "speaker_0"
            segs.append(Segment(start, end, text, spk, words))
        return Transcript(language or "en", " ".join(s.text for s in segs), segs, dur)


class MockSFX(SFXEngine):
    name = "mock"

    def generate(self, prompt, duration, prompt_influence=0.3, seed=None):
        rng = np.random.default_rng(seed if seed is not None else _seed_from(prompt))
        n = int(duration * 16000)
        noise = rng.standard_normal(n).astype(np.float32) * 0.2
        env = np.linspace(1, 0.2, n, dtype=np.float32)
        return noise * env, 16000


class MockIsolation(IsolationEngine):
    name = "mock"

    def separate(self, path: str | Path):
        audio, sr = A.load_audio(path, sr=24000)
        return audio, np.zeros_like(audio), sr


class MockTranslate(TranslateEngine):
    name = "mock"

    def translate(self, texts, source, target):
        return [f"[{target}] {t}" for t in texts]
