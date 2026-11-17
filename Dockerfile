# Kontho - open-source voice AI studio
#
# CPU image:   docker build -t kontho .
# NVIDIA GPU:  docker build -t kontho:gpu --build-arg BASE_IMAGE=pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime --build-arg TORCH=preinstalled .

ARG BASE_IMAGE=python:3.11-slim

# ---------- web studio
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- server
FROM ${BASE_IMAGE}
ARG TORCH=cpu
ARG EXTRAS=tts,stt,isolation,translate,sfx
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    KONTHO_DATA_DIR=/data KONTHO_WEB_DIR=/app/web/dist HF_HOME=/models
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 git \
    && rm -rf /var/lib/apt/lists/*
RUN if [ "$TORCH" = "cpu" ]; then \
      pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu; \
    fi
WORKDIR /app
COPY server/ /app/server/
COPY README.md /app/README.md
RUN pip install "/app/server[${EXTRAS}]" && pip install --no-deps omnivoice==0.2.1
COPY --from=web /web/dist /app/web/dist
VOLUME ["/data", "/models"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["kontho", "serve", "--host", "0.0.0.0", "--port", "8000"]
