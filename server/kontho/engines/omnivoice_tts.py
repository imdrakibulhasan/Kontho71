"""Text-to-speech, zero-shot voice cloning and voice design with k2-fsa OmniVoice (Apache-2.0).

OmniVoice supports 600+ languages (including Bengali, French, Hindi, Arabic...), cloning from a
3-20 s reference clip, voice design from a text description, inline non-verbal tags such as
``[laughter]`` / ``[sigh]``, and exact target durations (used for dubbing lip/timing fit).
"""

from __future__ import annotations

import os
import threading

import numpy as np

from ..config import get_settings
from .base import SynthesisOptions, TTSEngine, VoiceSpec


class OmniVoiceTTS(TTSEngine):
    name = "omnivoice"
    supports_cloning = True
    supports_design = True
    supports_duration = True

    def __init__(self) -> None:
        import torch  # noqa: F401  (fail fast if the [tts] extra is missing)
        from omnivoice import OmniVoice

        s = get_settings()
        self.device = s.resolved_device()
        dtype_name = os.environ.get("KONTHO_OMNIVOICE_DTYPE", "float16")
        import torch as _t

        self._torch = _t
        self.model = OmniVoice.from_pretrained(s.omnivoice_model, device_map=self.device,
                                               dtype=getattr(_t, dtype_name))
        self.sr = int(self.model.sampling_rate)
        self._prompts: dict[tuple, object] = {}
        self._lock = threading.Lock()

    def _clone_prompt(self, ref_audio: str, ref_text: str | None):
        key = (ref_audio, os.path.getmtime(ref_audio), ref_text)
        if key not in self._prompts:
            self._prompts[key] = self.model.create_voice_clone_prompt(ref_audio=ref_audio, ref_text=ref_text or None)
        return self._prompts[key]

    def synthesize(self, text: str, voice: VoiceSpec, opts: SynthesisOptions) -> tuple[np.ndarray, int]:
        kwargs: dict = {
            "text": text,
            "language": opts.language or None,
            "speed": opts.speed if opts.duration is None else None,
            "duration": opts.duration,
            "num_step": opts.steps or 32,
            "guidance_scale": opts.guidance or 2.0,
        }
        with self._lock:  # the model is not re-entrant
            seed = opts.seed if opts.seed is not None else voice.seed
            if seed is not None:
                self._torch.manual_seed(int(seed))
            if voice.ref_audio:
                kwargs["voice_clone_prompt"] = self._clone_prompt(voice.ref_audio, voice.ref_text)
            elif voice.instruct:
                kwargs["instruct"] = voice.instruct
            audios = self.model.generate(**kwargs)
        audio = np.asarray(audios[0], dtype=np.float32).reshape(-1)
        return audio, self.sr
