"""Audio helpers built on numpy + soundfile + ffmpeg (ffmpeg must be on PATH)."""

from __future__ import annotations

import io
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class AudioError(RuntimeError):
    pass


def _run(args: list[str], data: bytes | None = None) -> bytes:
    proc = subprocess.run(args, input=data, capture_output=True)
    if proc.returncode != 0:
        raise AudioError(proc.stderr.decode(errors="replace")[-2000:])
    return proc.stdout


def load_audio(path: str | Path, sr: int | None = 24000, mono: bool = True) -> tuple[np.ndarray, int]:
    """Decode any audio/video file to float32 numpy (mono by default)."""
    args = [FFMPEG, "-nostdin", "-v", "error", "-i", str(path), "-vn"]
    if mono:
        args += ["-ac", "1"]
    if sr:
        args += ["-ar", str(sr)]
    args += ["-f", "wav", "-acodec", "pcm_f32le", "-"]
    data, rate = sf.read(io.BytesIO(_run(args)), dtype="float32", always_2d=False)
    return np.ascontiguousarray(data, dtype=np.float32), int(rate)


def save_wav(path: str | Path, audio: np.ndarray, sr: int) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(audio, -1.0, 1.0), sr, subtype="PCM_16")
    return path


def probe_duration(path: str | Path) -> float:
    out = _run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float(out.decode().strip())
    except ValueError:
        return 0.0


def has_video(path: str | Path) -> bool:
    out = _run([FFPROBE, "-v", "error", "-select_streams", "v", "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", str(path)])
    return b"video" in out


def silence(seconds: float, sr: int) -> np.ndarray:
    return np.zeros(max(0, int(round(seconds * sr))), dtype=np.float32)


def cut(audio: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    return audio[max(0, int(start * sr)): max(0, int(end * sr))]


def peak_normalize(audio: np.ndarray, peak: float = 0.95) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio if m < 1e-6 else (audio * (peak / m)).astype(np.float32)


def concat(parts: list[np.ndarray], sr: int, gap: float = 0.0, fade_ms: float = 8.0) -> np.ndarray:
    out: list[np.ndarray] = []
    n_fade = int(sr * fade_ms / 1000)
    for i, p in enumerate(parts):
        p = p.astype(np.float32, copy=True)
        if n_fade and p.size > 2 * n_fade:
            ramp = np.linspace(0, 1, n_fade, dtype=np.float32)
            p[:n_fade] *= ramp
            p[-n_fade:] *= ramp[::-1]
        out.append(p)
        if gap and i < len(parts) - 1:
            out.append(silence(gap, sr))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def overlay(base: np.ndarray, clip: np.ndarray, sr: int, at: float, gain: float = 1.0) -> np.ndarray:
    start = int(at * sr)
    end = start + clip.size
    if end > base.size:
        base = np.concatenate([base, np.zeros(end - base.size, dtype=np.float32)])
    base[start:end] += clip * gain
    return base


def mix(a: np.ndarray, b: np.ndarray, gain_b: float = 1.0) -> np.ndarray:
    n = max(a.size, b.size)
    out = np.zeros(n, dtype=np.float32)
    out[: a.size] += a
    out[: b.size] += b * gain_b
    return out


def resample(audio: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
    if sr == target_sr or audio.size == 0:
        return audio
    raw = _run([FFMPEG, "-nostdin", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                "-ar", str(target_sr), "-f", "f32le", "-"], audio.astype(np.float32).tobytes())
    return np.frombuffer(raw, dtype=np.float32).copy()


def time_stretch(audio: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Speed audio up (factor > 1) or slow it down (< 1) without changing pitch."""
    if audio.size == 0 or abs(factor - 1.0) < 0.01:
        return audio
    filters = []
    f = factor
    while f > 2.0:
        filters.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        filters.append("atempo=0.5")
        f /= 0.5
    filters.append(f"atempo={f:.4f}")
    raw = _run([FFMPEG, "-nostdin", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                "-filter:a", ",".join(filters), "-f", "f32le", "-"], audio.astype(np.float32).tobytes())
    return np.frombuffer(raw, dtype=np.float32).copy()


def fit_to_duration(audio: np.ndarray, sr: int, target: float, max_speedup: float = 1.35) -> np.ndarray:
    """Make a clip fit ``target`` seconds: speed up (bounded) when too long, pad when short."""
    cur = audio.size / sr
    if target <= 0 or cur <= 0:
        return audio
    if cur > target * 1.02:
        audio = time_stretch(audio, sr, min(cur / target, max_speedup))
    return audio


# ---------------------------------------------------------------- output formats
@dataclass
class OutputFormat:
    codec: str  # mp3 | pcm | wav | opus | ulaw | alaw | flac
    sample_rate: int
    bitrate: int | None = None

    @property
    def content_type(self) -> str:
        return {
            "mp3": "audio/mpeg", "wav": "audio/wav", "pcm": "audio/pcm", "opus": "audio/ogg",
            "ulaw": "audio/basic", "alaw": "audio/basic", "flac": "audio/flac",
        }[self.codec]

    @property
    def extension(self) -> str:
        return {"pcm": "pcm", "ulaw": "ulaw", "alaw": "alaw", "opus": "ogg"}.get(self.codec, self.codec)


def parse_output_format(fmt: str | None) -> OutputFormat:
    """Parse ElevenLabs-style output formats, e.g. ``mp3_44100_128``, ``pcm_16000``, ``wav_24000``."""
    fmt = (fmt or "mp3_44100_128").lower()
    m = re.fullmatch(r"(mp3|pcm|wav|opus|ulaw|alaw|flac)(?:_(\d+))?(?:_(\d+))?", fmt)
    if not m:
        raise ValueError(f"Unsupported output_format: {fmt}")
    codec = m.group(1)
    rate = int(m.group(2) or (8000 if codec in {"ulaw", "alaw"} else 44100))
    bitrate = int(m.group(3)) if m.group(3) else (128 if codec in {"mp3", "opus"} else None)
    return OutputFormat(codec, rate, bitrate)


def encode(audio: np.ndarray, sr: int, fmt: OutputFormat | str) -> bytes:
    if isinstance(fmt, str):
        fmt = parse_output_format(fmt)
    audio = np.clip(audio.astype(np.float32), -1.0, 1.0)
    base = [FFMPEG, "-nostdin", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
            "-ar", str(fmt.sample_rate), "-ac", "1"]
    codec_args = {
        "mp3": ["-c:a", "libmp3lame", "-b:a", f"{fmt.bitrate}k", "-f", "mp3"],
        "wav": ["-c:a", "pcm_s16le", "-f", "wav"],
        "pcm": ["-c:a", "pcm_s16le", "-f", "s16le"],
        "opus": ["-c:a", "libopus", "-b:a", f"{fmt.bitrate}k", "-f", "ogg"],
        "ulaw": ["-c:a", "pcm_mulaw", "-f", "mulaw"],
        "alaw": ["-c:a", "pcm_alaw", "-f", "alaw"],
        "flac": ["-c:a", "flac", "-f", "flac"],
    }[fmt.codec]
    return _run(base + codec_args + ["-"], audio.tobytes())


def mux_video(video_path: str | Path, audio_path: str | Path, out_path: str | Path) -> Path:
    """Replace the audio track of a video (video stream copied, no re-encode)."""
    _run([FFMPEG, "-nostdin", "-v", "error", "-y", "-i", str(video_path), "-i", str(audio_path),
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_path)])
    return Path(out_path)
