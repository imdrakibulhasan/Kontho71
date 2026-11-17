"""Runtime configuration, read from environment variables (prefix ``KONTHO_``)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"KONTHO_{name}", default)


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "./data")).resolve())
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))  # auto | cuda | cpu | mps

    # Engine selection. "mock" engines need no models and are used for tests / UI development.
    tts_engine: str = field(default_factory=lambda: _env("TTS_ENGINE", "omnivoice"))
    stt_engine: str = field(default_factory=lambda: _env("STT_ENGINE", "whisper"))
    sfx_engine: str = field(default_factory=lambda: _env("SFX_ENGINE", "audioldm2"))
    isolation_engine: str = field(default_factory=lambda: _env("ISOLATION_ENGINE", "demucs"))
    translate_engine: str = field(default_factory=lambda: _env("TRANSLATE_ENGINE", "nllb"))

    # Model locations / ids
    omnivoice_model: str = field(default_factory=lambda: _env("OMNIVOICE_MODEL", "k2-fsa/OmniVoice"))
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "large-v3-turbo"))
    sfx_model: str = field(default_factory=lambda: _env("SFX_MODEL", "cvssp/audioldm2"))
    demucs_model: str = field(default_factory=lambda: _env("DEMUCS_MODEL", "htdemucs"))
    nllb_model: str = field(default_factory=lambda: _env("NLLB_MODEL", "facebook/nllb-200-distilled-600M"))

    # OpenAI-compatible LLM for translation (works with Ollama, vLLM, LM Studio, OpenAI...)
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "http://localhost:11434/v1"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "qwen2.5:7b-instruct"))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", "ollama"))

    # Optional Hugging Face token for gated models (pyannote, Stable Audio Open)
    hf_token: str = field(default_factory=lambda: os.environ.get("HF_TOKEN", ""))

    # Auth: when enabled every /v1 request needs an "xi-api-key" (or "Authorization: Bearer") header.
    auth_enabled: bool = field(default_factory=lambda: _env_bool("AUTH", False))
    admin_key: str = field(default_factory=lambda: _env("ADMIN_KEY", ""))

    workers: int = field(default_factory=lambda: int(_env("WORKERS", "1")))
    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "500")))
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "*"))
    web_dir: Path = field(
        default_factory=lambda: Path(_env("WEB_DIR", str(Path(__file__).resolve().parents[2] / "web" / "dist")))
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kontho.db"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    def resolved_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.files_dir.mkdir(parents=True, exist_ok=True)
    return s
