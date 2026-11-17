# Contributing to Kontho

Thanks for helping build an open voice AI studio!

## Development setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e "server[dev]"
# run the API with mock engines (no model downloads)
KONTHO_TTS_ENGINE=mock KONTHO_STT_ENGINE=mock KONTHO_SFX_ENGINE=mock \
KONTHO_ISOLATION_ENGINE=mock KONTHO_TRANSLATE_ENGINE=mock kontho serve --reload
# in another terminal
cd web && npm install && npm run dev
```

## Tests

```bash
cd server && pytest -q          # backend, runs on mock engines in ~10 s
cd web && npm run build         # type-check + build the UI
```

To exercise real models, install the extras (`./scripts/install.sh`) and run the server without the mock variables.

## Guidelines

- Keep the HTTP API compatible with ElevenLabs where an equivalent endpoint exists; mark extensions clearly.
- New AI backends go in `server/kontho/engines/` behind the existing interfaces, with a `mock` path covered by tests.
- Heavy dependencies belong in an optional extra in `server/pyproject.toml`, never in the core install.
- Document model licenses in the README when adding a model.
- Voice cloning features must keep the consent confirmation.
