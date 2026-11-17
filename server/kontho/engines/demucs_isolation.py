"""Voice isolation / background separation with Demucs (MIT)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import audio as A
from ..config import get_settings
from .base import IsolationEngine


class DemucsIsolation(IsolationEngine):
    name = "demucs"

    def __init__(self) -> None:
        import torch
        from demucs.pretrained import get_model

        self.torch = torch
        self.model = get_model(get_settings().demucs_model)
        self.model.eval()
        self.device = get_settings().resolved_device()
        if self.device == "mps":
            self.device = "cpu"
        self.model.to(self.device)

    def separate(self, path: str | Path):
        from demucs.apply import apply_model

        sr = int(self.model.samplerate)
        audio, _ = A.load_audio(path, sr=sr, mono=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        wav = self.torch.from_numpy(audio.T.copy()).float()  # (channels, samples)
        ref = wav.mean(0)
        mean, std = ref.mean(), ref.std() + 1e-8
        with self.torch.no_grad():
            sources = apply_model(self.model, ((wav - mean) / std)[None].to(self.device),
                                  device=self.device, split=True, overlap=0.25, progress=False)[0]
        sources = (sources * std + mean).cpu().numpy()  # (n_sources, channels, samples)
        idx = list(self.model.sources).index("vocals")
        vocals = sources[idx].mean(0).astype(np.float32)
        background = np.delete(sources, idx, axis=0).sum(0).mean(0).astype(np.float32)
        return vocals, background, sr
