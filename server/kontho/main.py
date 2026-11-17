"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, db, jobs
from .api.routes import router
from .config import get_settings
from .services.voices import seed_premade

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    s = get_settings()
    db.init_db()
    seed_premade()
    jobs.recover_interrupted()

    app = FastAPI(
        title="Kontho API",
        version=__version__,
        description="Open-source voice AI: text-to-speech, voice cloning & design, speech-to-text, voice changer, "
                    "sound effects, voice isolation and dubbing. ElevenLabs-compatible endpoints.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",")],
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["history-item-id"])
    app.include_router(router)

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    web = Path(s.web_dir)
    if (web / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith(("v1/", "v2/", "docs", "openapi.json")):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = (web / full_path).resolve()
            if full_path and target.is_file() and web.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(web / "index.html")

    return app


app = create_app()
