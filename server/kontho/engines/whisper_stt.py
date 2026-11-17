"""Speech-to-text with faster-whisper (MIT), word timestamps and optional pyannote diarization."""

from __future__ import annotations

from pathlib import Path

from ..audio import load_audio
from ..config import get_settings
from .base import Segment, STTEngine, Transcript, Word


class WhisperSTT(STTEngine):
    name = "whisper"

    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        s = get_settings()
        device = s.resolved_device()
        device = "cuda" if device == "cuda" else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(s.whisper_model, device=device, compute_type=compute)
        self._diarizer = None

    def transcribe(self, path: str | Path, language: str | None = None, diarize: bool = False,
                   num_speakers: int | None = None) -> Transcript:
        # decode with ffmpeg ourselves (16 kHz mono) - avoids PyAV version issues
        audio, _ = load_audio(path, sr=16000)
        segments, info = self.model.transcribe(audio, language=language or None, word_timestamps=True,
                                               vad_filter=True, beam_size=5)
        segs: list[Segment] = []
        for s in segments:
            words = [Word(w.word.strip(), float(w.start), float(w.end)) for w in (s.words or [])]
            segs.append(Segment(float(s.start), float(s.end), s.text.strip(), "speaker_0", words))
        if diarize and segs:
            self._assign_speakers(path, segs, num_speakers)
        return Transcript(info.language, " ".join(s.text for s in segs).strip(), segs, float(info.duration))

    def _assign_speakers(self, path, segs: list[Segment], num_speakers: int | None) -> None:
        """Label segments with pyannote speaker turns (needs the [diarize] extra + HF_TOKEN)."""
        try:
            if self._diarizer is None:
                from pyannote.audio import Pipeline

                self._diarizer = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                                          use_auth_token=get_settings().hf_token or None)
            kw = {"num_speakers": num_speakers} if num_speakers else {}
            diar = self._diarizer(str(path), **kw)
            turns = [(t.start, t.end, spk) for t, _, spk in diar.itertracks(yield_label=True)]
        except Exception as exc:  # diarization is best-effort
            import logging

            logging.getLogger(__name__).warning("Diarization unavailable (%s); using a single speaker.", exc)
            return
        names: dict[str, str] = {}
        for seg in segs:
            best, best_ov = None, 0.0
            for a, b, spk in turns:
                ov = min(b, seg.end) - max(a, seg.start)
                if ov > best_ov:
                    best, best_ov = spk, ov
            if best is not None:
                seg.speaker = names.setdefault(best, f"speaker_{len(names)}")
