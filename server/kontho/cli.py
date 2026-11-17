"""Command line: ``kontho serve`` and ``kontho download``."""

from __future__ import annotations

import argparse
import os


def main() -> None:
    p = argparse.ArgumentParser(prog="kontho", description="Kontho open-source voice AI studio")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the API + web studio")
    s.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    s.add_argument("--reload", action="store_true")
    d = sub.add_parser("download", help="pre-download and load the configured models")
    d.add_argument("--only", nargs="*", choices=["tts", "stt", "sfx", "isolation", "translate"])
    args = p.parse_args()

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("kontho.main:app", host=args.host, port=args.port, reload=args.reload)
    elif args.cmd == "download":
        from .engines import EngineUnavailable, get_engine

        for kind in args.only or ["tts", "stt", "isolation", "translate", "sfx"]:
            try:
                print(f"Loading {kind} engine...", flush=True)
                get_engine(kind)
                print(f"  ok: {kind}")
            except EngineUnavailable as exc:
                print(f"  skipped: {exc}")


if __name__ == "__main__":
    main()
