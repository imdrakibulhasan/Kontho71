"""Text-to-sound-effects with diffusers: AudioLDM2 (default) or Stable Audio Open.

Set ``KONTHO_SFX_MODEL`` to e.g. ``stabilityai/stable-audio-open-1.0`` (gated, needs HF_TOKEN)
for higher quality 44.1 kHz stereo effects up to 47 s.
"""

from __future__ import annotations

import numpy as np

from ..config import get_settings
from .base import SFXEngine


class DiffusersSFX(SFXEngine):
    name = "audioldm2"

    def __init__(self) -> None:
        import torch

        s = get_settings()
        self.torch = torch
        self.device = s.resolved_device()
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model_id = s.sfx_model
        self.stable = "stable-audio" in self.model_id
        token = s.hf_token or None
        if self.stable:
            from diffusers import StableAudioPipeline

            self.pipe = StableAudioPipeline.from_pretrained(self.model_id, torch_dtype=dtype, token=token)
            self.sr = int(self.pipe.vae.sampling_rate)
        else:
            from diffusers import AudioLDM2Pipeline

            self.pipe = AudioLDM2Pipeline.from_pretrained(self.model_id, torch_dtype=dtype, token=token)
            self.sr = 16000
        self.pipe = self.pipe.to(self.device)

    def generate(self, prompt: str, duration: float, prompt_influence: float = 0.3, seed: int | None = None):
        gen = self.torch.Generator(device="cpu").manual_seed(int(seed)) if seed is not None else None
        # prompt_influence (0..1, ElevenLabs semantics) -> classifier-free guidance scale
        guidance = 2.0 + 8.0 * float(prompt_influence)
        neg = "low quality, distorted, muffled, noise artifacts"
        if self.stable:
            out = self.pipe(prompt, negative_prompt=neg, num_inference_steps=100, audio_end_in_s=min(duration, 47.0),
                            guidance_scale=guidance, generator=gen).audios
            audio = out[0].float().cpu().numpy().mean(0)
        else:
            out = self.pipe(prompt, negative_prompt=neg, num_inference_steps=200, audio_length_in_s=duration,
                            guidance_scale=guidance, generator=gen).audios
            audio = np.asarray(out[0])
        return audio.astype(np.float32).reshape(-1), self.sr
