#!/usr/bin/env bash
# Install Kontho locally (Linux / macOS / WSL).
#   ./scripts/install.sh            -> CPU or Apple Silicon
#   ./scripts/install.sh --cuda     -> NVIDIA GPU (CUDA 12.x wheels)
#   ./scripts/install.sh --minimal  -> TTS + STT only (no dubbing translation / SFX / isolation)
set -euo pipefail
cd "$(dirname "$0")/.."

CUDA=0; MINIMAL=0
for a in "$@"; do
  case "$a" in
    --cuda) CUDA=1 ;;
    --minimal) MINIMAL=1 ;;
    *) echo "unknown option $a"; exit 1 ;;
  esac
done

command -v ffmpeg >/dev/null || { echo "ffmpeg is required: install it (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip wheel

if [ "$CUDA" = 1 ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
elif [ "$(uname)" = "Linux" ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
else
  pip install torch torchaudio
fi

if [ "$MINIMAL" = 1 ]; then
  pip install -e "server[tts,stt]"
else
  pip install -e "server[tts,stt,isolation,translate,sfx]"
fi
pip install --no-deps omnivoice==0.2.1

if command -v npm >/dev/null; then
  (cd web && npm ci && npm run build)
else
  echo "npm not found: skipping the web studio build (the API still works; see README)"
fi

echo
echo "Done. Start the server with:"
echo "  . .venv/bin/activate && kontho serve"
echo "then open http://localhost:8000"
