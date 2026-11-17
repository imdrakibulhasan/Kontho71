"""Translation engines for dubbing: NLLB-200 (local) or any OpenAI-compatible LLM (Ollama, vLLM...)."""

from __future__ import annotations

import json
import re

import httpx

from ..config import get_settings
from ..languages import language_name, nllb_code
from .base import TranslateEngine


class NLLBTranslate(TranslateEngine):
    name = "nllb"

    def __init__(self) -> None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        s = get_settings()
        self.device = s.resolved_device()
        self.tok = AutoTokenizer.from_pretrained(s.nllb_model)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(s.nllb_model).to(self.device)

    def translate(self, texts, source, target):
        if not texts:
            return []
        self.tok.src_lang = nllb_code(source)
        out: list[str] = []
        for i in range(0, len(texts), 16):
            batch = self.tok(texts[i:i + 16], return_tensors="pt", padding=True, truncation=True).to(self.device)
            gen = self.model.generate(**batch, forced_bos_token_id=self.tok.convert_tokens_to_ids(nllb_code(target)),
                                      max_new_tokens=400)
            out += self.tok.batch_decode(gen, skip_special_tokens=True)
        return out


class LLMTranslate(TranslateEngine):
    """Context-aware translation with an OpenAI-compatible chat model. Keeps line alignment."""

    name = "llm"

    def translate(self, texts, source, target):
        if not texts:
            return []
        s = get_settings()
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        prompt = (
            f"Translate these numbered subtitle lines from {language_name(source)} to {language_name(target)} "
            "for a voice-over dub. Keep each line roughly the same length so it fits the same timing, keep "
            "names unchanged, use natural spoken language. Reply ONLY with a JSON array of "
            f"{len(texts)} strings, in order.\n\n{numbered}"
        )
        r = httpx.post(f"{s.llm_base_url.rstrip('/')}/chat/completions", timeout=300,
                       headers={"Authorization": f"Bearer {s.llm_api_key}"},
                       json={"model": s.llm_model, "temperature": 0.2,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", content, re.S)
        result = json.loads(m.group(0)) if m else []
        if len(result) != len(texts):
            raise RuntimeError("LLM returned a different number of lines than requested")
        return [str(x) for x in result]
