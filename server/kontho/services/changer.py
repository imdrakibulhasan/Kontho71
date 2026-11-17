"""Voice changer (speech-to-speech): keep the words, timing and pacing, change the voice.

Pipeline: (optional) remove background noise -> transcribe with timestamps -> re-speak every
segment with the target voice, forced to the original segment duration -> place on the original
timeline. Optionally mixes the original background back in.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import audio as A
from ..engines import get_engine
from ..engines.base import SynthesisOptions
from . import tts as T
from . import voices as V


def convert(path: Path, voice_id: str, settings: dict | None = None, model_id: str | None = None,
            remove_background_noise: bool = False, keep_background: bool = False,
            language: str | None = None, seed: int | None = None) -> tuple[np.ndarray, int, str]:
    voice = T.resolve_voice(voice_id)
    engine = get_engine("tts")
    background = None
    src = path
    if remove_background_noise or keep_background:
        vocals, bg, sep_sr = get_engine("isolation").separate(path)
        src = A.save_wav(path.with_name(path.stem + "_vocals.wav"), vocals, sep_sr)
        if keep_background:
            background = (bg, sep_sr)
    tr = get_engine("stt").transcribe(src, language=language)
    total = A.probe_duration(path) or tr.duration
    vs = T.VoiceSettings.from_dict(settings)
    spec = V.voice_spec(voice)
    sr = 24000
    out = A.silence(total, sr)
    for i, seg in enumerate(tr.segments):
        if not seg.text.strip():
            continue
        dur = max(0.3, seg.end - seg.start)
        opts = T.make_options(vs, spec.seed, language or tr.language, model_id, seed, i)
        opts = SynthesisOptions(language=opts.language, speed=opts.speed, seed=opts.seed, guidance=opts.guidance,
                                steps=opts.steps, duration=dur if engine.supports_duration else None)
        clip, csr = engine.synthesize(seg.text, spec, opts)
        clip = A.resample(clip, csr, sr)
        clip = A.fit_to_duration(clip, sr, dur)
        out = A.overlay(out, clip, sr, seg.start)
    if background is not None:
        out = A.mix(out, A.resample(background[0], background[1], sr), gain_b=0.9)
    return A.peak_normalize(out), sr, tr.text
